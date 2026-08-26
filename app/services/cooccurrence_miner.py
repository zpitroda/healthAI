from __future__ import annotations

import itertools
import logging
import math
import os
import time
from typing import Any, Dict, List, Optional
import httpx

from app.knowledge_graph.graph_db import get_graph_database

logger = logging.getLogger("healthai.cooccurrence_miner")

class CooccurrenceMiner:
    """Mines PubMed for compound co-occurrence and computes PMI scores."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 8.0,
    ) -> None:
        self.api_key = api_key or os.getenv("NCBI_API_KEY")
        self.timeout = timeout
        self.requests_per_second = 10.0 if self.api_key else 3.0
        self._cache: Dict[str, int] = {}

    def count_papers(self, query: str) -> int:
        """
        Queries PubMed E-Utilities ESearch to get result count.
        """
        if query in self._cache:
            return self._cache[query]

        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params: Dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "rettype": "count",
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            time.sleep(1.0 / self.requests_per_second)
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    count_str = data.get("esearchresult", {}).get("count", "0")
                    count = int(count_str)
                    self._cache[query] = count
                    return count
        except Exception as e:
            logger.debug("Failed to count papers for query '%s': %s", query, e)

        return 0

    def compute_pmi(
        self,
        compound_a: str,
        compound_b: str,
        total_papers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Computes Pointwise Mutual Information (PMI) scores to discover literature-backed compound associations.
        """
        if total_papers is None:
            total_papers = self._cache.get("TOTAL_PUBMED_PAPERS", 37000000)

        count_a = self.count_papers(f'"{compound_a}"[Title/Abstract]')
        count_b = self.count_papers(f'"{compound_b}"[Title/Abstract]')
        count_ab = self.count_papers(f'"{compound_a}"[Title/Abstract] AND "{compound_b}"[Title/Abstract]')

        if count_a == 0 or count_b == 0 or count_ab == 0 or total_papers == 0:
            return {
                "compound_a": compound_a,
                "compound_b": compound_b,
                "count_a": count_a,
                "count_b": count_b,
                "count_ab": count_ab,
                "pmi": 0.0,
                "npmi": 0.0,
                "confidence": 0.0,
                "total_papers": total_papers,
            }

        p_a = count_a / total_papers
        p_b = count_b / total_papers
        p_ab = count_ab / total_papers

        pmi = math.log2(p_ab / (p_a * p_b))
        
        # Normalized PMI (NPMI) = PMI / -log2(P(A,B))
        npmi = pmi / -math.log2(p_ab)
        
        # Confidence score bounded between 0 and 1
        confidence = min(1.0, max(0.0, (npmi + 1.0) / 2.0))

        return {
            "compound_a": compound_a,
            "compound_b": compound_b,
            "count_a": count_a,
            "count_b": count_b,
            "count_ab": count_ab,
            "pmi": pmi,
            "npmi": npmi,
            "confidence": confidence,
            "total_papers": total_papers,
        }

    def get_sample_pmids(
        self,
        compound_a: str,
        compound_b: str,
        max_results: int = 5,
    ) -> List[str]:
        """
        Query PubMed ESearch for the pair query and return a list of sample PMIDs.
        """
        query = f'"{compound_a}"[Title/Abstract] AND "{compound_b}"[Title/Abstract]'
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params: Dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            time.sleep(1.0 / self.requests_per_second)
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    id_list = data.get("esearchresult", {}).get("idlist", [])
                    return [str(pmid) for pmid in id_list]
        except Exception as e:
            logger.debug("Failed to get sample PMIDs for '%s' and '%s': %s", compound_a, compound_b, e)

        return []

    def mine_compound_pairs(
        self,
        compounds: List[str],
        min_cooccurrence: int = 3,
        min_npmi: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Main pipeline function to mine pairs of compounds.
        """
        total_papers = self.count_papers('all[Filter]')
        if total_papers == 0:
            total_papers = 37000000
        self._cache["TOTAL_PUBMED_PAPERS"] = total_papers

        # Filter out compounds with < 5 papers
        valid_compounds = []
        for c in compounds:
            if self.count_papers(f'"{c}"[Title/Abstract]') >= 5:
                valid_compounds.append(c)

        pairs = list(itertools.combinations(valid_compounds, 2))
        total_pairs = len(pairs)
        results = []

        for i, (a, b) in enumerate(pairs, 1):
            pmi_result = self.compute_pmi(a, b, total_papers=total_papers)
            
            if pmi_result["count_ab"] >= min_cooccurrence and pmi_result["npmi"] >= min_npmi:
                pmids = self.get_sample_pmids(a, b, max_results=5)
                pmi_result["sample_pmids"] = pmids
                results.append(pmi_result)
                print(f"Mining pair {i}/{total_pairs}: {a} + {b}... co-occurrence: {pmi_result['count_ab']}, NPMI: {pmi_result['npmi']:.2f}")
                logger.info(f"Mining pair {i}/{total_pairs}: {a} + {b}... co-occurrence: {pmi_result['count_ab']}, NPMI: {pmi_result['npmi']:.2f}")

        results.sort(key=lambda x: x["npmi"], reverse=True)
        return results

    def save_to_graph(self, results: List[Dict[str, Any]], graph_db: Any = None) -> int:
        """
        Writes LITERATURE_COOCCURRENCE edges to the graph.
        """
        if graph_db is None:
            graph_db = get_graph_database()

        import datetime
        ts = datetime.datetime.utcnow().isoformat()
        edges_created = 0

        for res in results:
            a = res["compound_a"]
            b = res["compound_b"]

            params = {
                "src": a,
                "tgt": b,
                "count_ab": res["count_ab"],
                "pmi": res["pmi"],
                "npmi": res["npmi"],
                "confidence": res["confidence"],
                "pmids": res.get("sample_pmids", []),
                "ts": ts,
            }

            cypher = '''
            MATCH (a:EntityNode {id: $src}), (b:EntityNode {id: $tgt})
            MERGE (a)-[r:LITERATURE_COOCCURRENCE]->(b)
            SET r.cooccurrence_count = $count_ab,
                r.pmi_score = $pmi,
                r.npmi_score = $npmi,
                r.confidence = $confidence,
                r.sample_pmids = $pmids,
                r.last_mined = $ts
            '''

            try:
                graph_db.execute_cypher(cypher, params)

                # In-memory fallback
                if hasattr(graph_db, "_mock_edges"):
                    graph_db._mock_edges.append({
                        "source": a,
                        "target": b,
                        "edge_type": "LITERATURE_COOCCURRENCE",
                        "cooccurrence_count": res["count_ab"],
                        "pmi_score": res["pmi"],
                        "npmi_score": res["npmi"],
                        "confidence": res["confidence"],
                        "sample_pmids": res.get("sample_pmids", []),
                        "last_mined": ts,
                    })

                if hasattr(graph_db, "_mock_nodes"):
                    if a not in graph_db._mock_nodes:
                        graph_db._mock_nodes[a] = {"id": a, "label": a, "node_type": "compound"}
                    if b not in graph_db._mock_nodes:
                        graph_db._mock_nodes[b] = {"id": b, "label": b, "node_type": "compound"}

                edges_created += 1
            except Exception as e:
                logger.error("Failed to save edge to graph for %s and %s: %s", a, b, e)

        return edges_created
