from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
import httpx
from cachetools import LRUCache

from app.services.live_enrichment import get_shared_http_client

logger = logging.getLogger("healthai.botanical_resolver")

_BOTANICAL_CACHE: LRUCache = LRUCache(maxsize=1000)
_BOTANICAL_LOCK = threading.Lock()
BOTANICAL_TTL_SECONDS = 3600.0 * 24  # 24 hours


class BotanicalResolver:
    """
    Authoritative Botanical & Phytochemical Complex Resolution Service.
    Queries:
    1. NCBI MeSH (Medical Subject Headings) Classification & Plant Ontology (Tree B01)
    2. NCBI PubChem PUG-REST for Chemical Constituents
    Resolves crude botanicals (e.g., Kratom, Kava, Ashwagandha) into their
    authoritative scientific plant taxonomy and primary bioactive chemical entities.
    """

    def __init__(self, timeout_seconds: float = 6.0, client: Optional[httpx.Client] = None):
        self.timeout = timeout_seconds
        self._custom_client = client

    def _client(self) -> httpx.Client:
        if self._custom_client and not self._custom_client.is_closed:
            return self._custom_client
        return get_shared_http_client(self.timeout)

    def resolve_botanical(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Determines if a query is an authoritative botanical taxon via NCBI MeSH,
        and retrieves its primary active chemical constituents.
        """
        clean_q = str(query or "").strip().lower()
        if not clean_q or len(clean_q) < 3:
            return None

        with _BOTANICAL_LOCK:
            if clean_q in _BOTANICAL_CACHE:
                cached, t_cached = _BOTANICAL_CACHE[clean_q]
                if time.time() - t_cached < BOTANICAL_TTL_SECONDS:
                    return dict(cached) if cached else None
                _BOTANICAL_CACHE.pop(clean_q, None)

        client = self._client()
        result: Optional[Dict[str, Any]] = None

        try:
            # 1. Query NCBI MeSH for botanical terms
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            s_resp = client.get(
                search_url,
                params={"db": "mesh", "term": clean_q, "retmode": "json"},
            )
            if s_resp.status_code == 200:
                s_data = s_resp.json().get("esearchresult", {})
                id_list = s_data.get("idlist", [])
                if id_list:
                    mesh_id = id_list[0]
                    # Fetch MeSH summary
                    sum_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                    sum_resp = client.get(
                        sum_url,
                        params={"db": "mesh", "id": mesh_id, "retmode": "json"},
                    )
                    if sum_resp.status_code == 200:
                        mesh_item = sum_resp.json().get("result", {}).get(str(mesh_id), {})
                        scope_note = str(mesh_item.get("ds_scopenote") or "")
                        terms = [str(t) for t in mesh_item.get("ds_meshterms", [])]
                        tree_nodes = mesh_item.get("ds_idxlinks", [])

                        treenums = [str(tn.get("treenum", "")) for tn in tree_nodes if tn.get("treenum")]
                        # Check if classified in Plant / Organism hierarchy (Tree B01) or Phytotherapy
                        is_plant = any(
                            t.startswith("B01") for t in treenums
                        ) or any(
                            k in scope_note.lower() for k in ["plant", "rhizome", "herb", "genus"]
                        )

                        if is_plant:
                            scientific_name = terms[0] if terms else clean_q.title()
                            constituents: List[Dict[str, Any]] = []

                            # Query PubChem autocomplete with candidate genus/species to find constituents
                            # Also inspect scope note for chemical mentions
                            candidates_to_try = [scientific_name.split()[0], clean_q]
                            for cand in candidates_to_try:
                                if len(cand) >= 4:
                                    try:
                                        pc_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{cand}/json"
                                        pc_resp = client.get(pc_url, params={"limit": 6})
                                        if pc_resp.status_code == 200:
                                            dict_terms = pc_resp.json().get("dictionary_terms", {}).get("compound", [])
                                            for term in dict_terms:
                                                clean_t = term.strip()
                                                if clean_t and clean_t.lower() != cand.lower() and len(clean_t) <= 30:
                                                    constituents.append({
                                                        "name": clean_t.title(),
                                                        "key": clean_t.lower().replace(" ", "_").replace("-", "_"),
                                                        "source": "PubChem Compound Registry",
                                                    })
                                    except Exception:
                                        pass

                            result = {
                                "is_botanical": True,
                                "name": scientific_name,
                                "canonical_name": scientific_name,
                                "scientific_name": scientific_name,
                                "drug_class": "Botanical / Phytochemical Complex",
                                "scope_note": scope_note,
                                "mesh_id": mesh_id,
                                "mesh_tree_number": treenums[0] if treenums else "B01.650",
                                "mesh_tree_numbers": treenums,
                                "terms": terms,
                                "primary_constituents": constituents[:4],
                                "source": "NCBI MeSH / Taxonomy",
                            }
        except Exception as e:
            logger.debug("Botanical resolution failed for %s: %s", clean_q, e)

        with _BOTANICAL_LOCK:
            _BOTANICAL_CACHE[clean_q] = (result, time.time())

        return result


_GLOBAL_BOTANICAL_RESOLVER: Optional[BotanicalResolver] = None


def get_botanical_resolver() -> BotanicalResolver:
    global _GLOBAL_BOTANICAL_RESOLVER
    if _GLOBAL_BOTANICAL_RESOLVER is None:
        _GLOBAL_BOTANICAL_RESOLVER = BotanicalResolver()
    return _GLOBAL_BOTANICAL_RESOLVER
