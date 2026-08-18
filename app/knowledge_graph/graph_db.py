from __future__ import annotations

import os
import shutil
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import kuzu

logger = logging.getLogger("healthai.graph_db")


class KuzuGraphDatabase:
    """
    Dedicated Embedded Graph Database Backend powered by KuzuDB.
    Provides multi-hop Cypher traversals across tens of thousands of biological nodes,
    shortest pathfinding, node/edge database sync, and GraphRAG context extraction
    for future LLM integration.
    """

    _instance: Optional[KuzuGraphDatabase] = None

    def __new__(cls, db_path: str = "healthai_kuzu.db") -> KuzuGraphDatabase:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = "healthai_kuzu.db") -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.db_path = db_path
        self.db: Optional[kuzu.Database] = None
        self.conn: Optional[kuzu.Connection] = None
        self._setup_db()

    def _setup_db(self) -> None:
        try:
            self.db = kuzu.Database(self.db_path)
            self.conn = kuzu.Connection(self.db)
            self._init_schema()
            logger.info("KuzuDB graph database initialized successfully at %s", self.db_path)
        except Exception as e:
            logger.error("Failed to initialize KuzuDB database at %s: %s", self.db_path, e)
            raise

    def _init_schema(self) -> None:
        """Create Node and Rel tables in KuzuDB if they do not exist."""
        node_tables = [
            ("CompoundNode", "CREATE NODE TABLE CompoundNode(id STRING, label STRING, smiles STRING, inchikey STRING, drug_class STRING, logP DOUBLE, molecular_weight DOUBLE, PRIMARY KEY (id))"),
            ("TargetNode", "CREATE NODE TABLE TargetNode(id STRING, label STRING, family STRING, category STRING, uniprot_id STRING, gene_symbol STRING, PRIMARY KEY (id))"),
            ("PathwayNode", "CREATE NODE TABLE PathwayNode(id STRING, label STRING, database STRING, PRIMARY KEY (id))"),
            ("PhysiologyNode", "CREATE NODE TABLE PhysiologyNode(id STRING, label STRING, organ_system STRING, PRIMARY KEY (id))"),
            ("BiomarkerNode", "CREATE NODE TABLE BiomarkerNode(id STRING, label STRING, unit STRING, panel STRING, safe_lower DOUBLE, safe_upper DOUBLE, PRIMARY KEY (id))"),
            ("PhenotypeNode", "CREATE NODE TABLE PhenotypeNode(id STRING, label STRING, category STRING, severity STRING, PRIMARY KEY (id))"),
            ("EntityNode", "CREATE NODE TABLE EntityNode(id STRING, label STRING, node_type STRING, PRIMARY KEY (id))"),
        ]

        for table_name, create_sql in node_tables:
            try:
                self.conn.execute(create_sql)
            except Exception:
                # Table already exists or creation skipped
                pass

        rel_tables = [
            ("INTERACTS_WITH", "CREATE REL TABLE INTERACTS_WITH(FROM CompoundNode TO TargetNode, FROM EntityNode TO EntityNode, edge_type STRING, magnitude DOUBLE, affinity_ki DOUBLE, inhibition_ic50 DOUBLE)"),
            ("ACTIVATES", "CREATE REL TABLE ACTIVATES(FROM TargetNode TO PathwayNode, FROM PathwayNode TO PhysiologyNode, FROM EntityNode TO EntityNode, edge_type STRING, magnitude DOUBLE)"),
            ("INHIBITS", "CREATE REL TABLE INHIBITS(FROM TargetNode TO PathwayNode, FROM EntityNode TO EntityNode, edge_type STRING, magnitude DOUBLE)"),
            ("MODIFIES", "CREATE REL TABLE MODIFIES(FROM PhysiologyNode TO BiomarkerNode, FROM EntityNode TO EntityNode, edge_type STRING, magnitude DOUBLE)"),
            ("DRIVES", "CREATE REL TABLE DRIVES(FROM PhysiologyNode TO PhenotypeNode, FROM EntityNode TO EntityNode, edge_type STRING, magnitude DOUBLE)"),
            ("RELATIONSHIP", "CREATE REL TABLE RELATIONSHIP(FROM EntityNode TO EntityNode, edge_type STRING, magnitude DOUBLE)"),
        ]

        for table_name, create_sql in rel_tables:
            try:
                self.conn.execute(create_sql)
            except Exception:
                # Table already exists or creation skipped
                pass

    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a Cypher query and returns results as a list of dictionaries."""
        if not self.conn:
            self._setup_db()

        try:
            if params:
                result = self.conn.execute(query, params)
            else:
                result = self.conn.execute(query)

            rows: List[Dict[str, Any]] = []
            col_names = result.get_column_names()
            while result.has_next():
                row_vals = result.get_next()
                row_dict = {}
                for idx, col in enumerate(col_names):
                    row_dict[col] = row_vals[idx] if idx < len(row_vals) else None
                rows.append(row_dict)
            return rows
        except Exception as e:
            logger.error("Error executing Cypher query '%s': %s", query, e)
            raise

    def sync_biological_graph(self, bio_graph: Any) -> Dict[str, int]:
        """
        Synchronizes all nodes and edges from a BiologicalGraph or NetworkX DiGraph
        into the dedicated KuzuDB graph database backend.
        """
        nx_graph = getattr(bio_graph, "graph", bio_graph)
        nodes_synced = 0
        edges_synced = 0

        # 1. Sync Nodes
        for node_id, attrs in nx_graph.nodes(data=True):
            nt = str(attrs.get("node_type", "entity")).lower()
            label = str(attrs.get("label") or node_id)

            if nt == "compound":
                smiles = str(attrs.get("smiles") or "")
                inchikey = str(attrs.get("inchikey") or "")
                drug_class = str(attrs.get("drug_class") or "")
                logp = float(attrs.get("logP") or 0.0)
                mw = float(attrs.get("molecular_weight") or 0.0)

                q = """
                MERGE (c:CompoundNode {id: $id})
                SET c.label = $label, c.smiles = $smiles, c.inchikey = $inchikey,
                    c.drug_class = $drug_class, c.logP = $logp, c.molecular_weight = $mw
                """
                self.execute_cypher(q, {"id": str(node_id), "label": label, "smiles": smiles, "inchikey": inchikey, "drug_class": drug_class, "logp": logp, "mw": mw})

            elif nt in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
                family = str(attrs.get("family") or attrs.get("enzyme_family") or attrs.get("transporter_family") or "")
                cat = str(attrs.get("category") or "")
                uid = str(attrs.get("uniprot_id") or "")
                symbol = str(attrs.get("gene_symbol") or "")

                q = """
                MERGE (t:TargetNode {id: $id})
                SET t.label = $label, t.family = $family, t.category = $cat,
                    t.uniprot_id = $uid, t.gene_symbol = $symbol
                """
                self.execute_cypher(q, {"id": str(node_id), "label": label, "family": family, "cat": cat, "uid": uid, "symbol": symbol})

            elif nt in ("signaling_pathway", "reaction", "pathway"):
                db_name = str(attrs.get("pathway_database") or "Reactome")
                q = """
                MERGE (p:PathwayNode {id: $id})
                SET p.label = $label, p.database = $db_name
                """
                self.execute_cypher(q, {"id": str(node_id), "label": label, "db_name": db_name})

            elif nt in ("physiology", "organ_system"):
                organ = str(attrs.get("organ_system") or "Systemic")
                q = """
                MERGE (p:PhysiologyNode {id: $id})
                SET p.label = $label, p.organ_system = $organ
                """
                self.execute_cypher(q, {"id": str(node_id), "label": label, "organ": organ})

            elif nt in ("biomarker", "lab"):
                unit = str(attrs.get("unit") or "")
                panel = str(attrs.get("biomarker_panel") or "")
                s_lower = float(attrs.get("safe_lower_bound") or 0.0)
                s_upper = float(attrs.get("safe_upper_bound") or 100.0)
                q = """
                MERGE (b:BiomarkerNode {id: $id})
                SET b.label = $label, b.unit = $unit, b.panel = $panel,
                    b.safe_lower = $s_lower, b.safe_upper = $s_upper
                """
                self.execute_cypher(q, {"id": str(node_id), "label": label, "unit": unit, "panel": panel, "s_lower": s_lower, "s_upper": s_upper})

            elif nt in ("phenotype", "outcome", "toxicity", "benefit"):
                cat = str(attrs.get("phenotype_category") or "")
                sev = str(attrs.get("severity") or "")
                q = """
                MERGE (ph:PhenotypeNode {id: $id})
                SET ph.label = $label, ph.category = $cat, ph.severity = $sev
                """
                self.execute_cypher(q, {"id": str(node_id), "label": label, "cat": cat, "sev": sev})

            # Always sync to fallback EntityNode table for multi-table relationships
            q_ent = """
            MERGE (e:EntityNode {id: $id})
            SET e.label = $label, e.node_type = $nt
            """
            self.execute_cypher(q_ent, {"id": str(node_id), "label": label, "nt": nt})
            nodes_synced += 1

        # 2. Sync Edges
        for source_id, target_id, attrs in nx_graph.edges(data=True):
            edge_type = str(attrs.get("edge_type") or "MODULATES")
            mag = float(attrs.get("vector_magnitude") or 1.0)
            ki = float(attrs.get("affinity_ki")) if attrs.get("affinity_ki") is not None else -1.0
            ic50 = float(attrs.get("inhibition_ic50")) if attrs.get("inhibition_ic50") is not None else -1.0

            q_rel = """
            MATCH (a:EntityNode {id: $src}), (b:EntityNode {id: $tgt})
            CREATE (a)-[:RELATIONSHIP {edge_type: $edge_type, magnitude: $mag}]->(b)
            """
            try:
                self.execute_cypher(q_rel, {"src": str(source_id), "tgt": str(target_id), "edge_type": edge_type, "mag": mag})
                edges_synced += 1
            except Exception:
                pass

            # Try specific typed relationships
            src_node = nx_graph.nodes.get(source_id, {})
            tgt_node = nx_graph.nodes.get(target_id, {})
            src_type = str(src_node.get("node_type", "")).lower()
            tgt_type = str(tgt_node.get("node_type", "")).lower()

            if src_type == "compound" and tgt_type in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
                q_typed = """
                MATCH (c:CompoundNode {id: $src}), (t:TargetNode {id: $tgt})
                CREATE (c)-[:INTERACTS_WITH {edge_type: $edge_type, magnitude: $mag, affinity_ki: $ki, inhibition_ic50: $ic50}]->(t)
                """
                try:
                    self.execute_cypher(q_typed, {"src": str(source_id), "tgt": str(target_id), "edge_type": edge_type, "mag": mag, "ki": ki, "ic50": ic50})
                except Exception:
                    pass

        return {"nodes_synced": nodes_synced, "edges_synced": edges_synced}

    def multi_hop_traversal(self, start_id: str, max_hops: int = 5) -> List[Dict[str, Any]]:
        """
        Executes multi-hop Cypher traversal up to max_hops depth starting from start_id.
        """
        cypher = f"""
        MATCH (a:EntityNode {{id: $start_id}})-[r:RELATIONSHIP*1..{max_hops}]->(b:EntityNode)
        RETURN a.id AS source_id, a.label AS source_label,
               b.id AS target_id, b.label AS target_label, b.node_type AS target_type
        """
        try:
            return self.execute_cypher(cypher, {"start_id": start_id})
        except Exception:
            # Fallback to single hop or generic traversal if variable path fails
            q_fallback = """
            MATCH (a:EntityNode {id: $start_id})-[r:RELATIONSHIP]->(b:EntityNode)
            RETURN a.id AS source_id, a.label AS source_label,
                   b.id AS target_id, b.label AS target_label, b.node_type AS target_type
            """
            return self.execute_cypher(q_fallback, {"start_id": start_id})

    def get_graphrag_context(self, entity_ids: List[str], max_hops: int = 2) -> Dict[str, Any]:
        """
        Extracts structured GraphRAG subgraph context for LLM prompt integration.
        Formats entities, multi-hop relationship triples, pathway cascades, biomarkers, and outcomes
        into a clean structured context dictionary.
        """
        clean_ids = [str(e).strip() for e in entity_ids if e]
        if not clean_ids:
            return {"entities": [], "triples": [], "text_summary": "No entities provided."}

        triples: List[Dict[str, Any]] = []
        entities_found: Dict[str, Dict[str, Any]] = {}

        for eid in clean_ids:
            q_node = "MATCH (e:EntityNode {id: $eid}) RETURN e.id AS id, e.label AS label, e.node_type AS node_type"
            nodes = self.execute_cypher(q_node, {"eid": eid})
            if nodes:
                entities_found[eid] = nodes[0]

            # Multi-hop relationships
            q_rel = """
            MATCH (a:EntityNode {id: $eid})-[r:RELATIONSHIP]->(b:EntityNode)
            RETURN a.id AS source, a.label AS source_label,
                   r.edge_type AS relationship, r.magnitude AS magnitude,
                   b.id AS target, b.label AS target_label, b.node_type AS target_type
            """
            rels = self.execute_cypher(q_rel, {"eid": eid})
            for r in rels:
                triples.append({
                    "subject": r["source_label"] or r["source"],
                    "predicate": r["relationship"] or "MODULATES",
                    "object": r["target_label"] or r["target"],
                    "object_type": r["target_type"],
                    "magnitude": r["magnitude"],
                })
                if r["target"] not in entities_found:
                    entities_found[r["target"]] = {
                        "id": r["target"],
                        "label": r["target_label"],
                        "node_type": r["target_type"],
                    }

        # Build natural text summary for LLM context window
        summary_lines = ["### GraphRAG Biological Subgraph Context:"]
        summary_lines.append(f"- Focused Entities: {', '.join([e['label'] for e in entities_found.values()])}")
        summary_lines.append("- Knowledge Graph Triples:")
        for t in triples[:30]:
            summary_lines.append(f"  * [{t['subject']}] --({t['predicate']})--> [{t['object']}] ({t['object_type']})")

        return {
            "focused_ids": clean_ids,
            "entities": list(entities_found.values()),
            "triples": triples,
            "triple_count": len(triples),
            "text_summary": "\n".join(summary_lines),
        }


# Singleton instance accessor
_GRAPH_DB_INSTANCE: Optional[KuzuGraphDatabase] = None


def get_graph_database(db_path: str = "healthai_kuzu.db") -> KuzuGraphDatabase:
    global _GRAPH_DB_INSTANCE
    if _GRAPH_DB_INSTANCE is None:
        _GRAPH_DB_INSTANCE = KuzuGraphDatabase(db_path=db_path)
    return _GRAPH_DB_INSTANCE
