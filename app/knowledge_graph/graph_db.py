from __future__ import annotations

import os
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from neo4j import GraphDatabase, Driver

logger = logging.getLogger("healthai.graph_db")


class Neo4jGraphDatabase:
    """
    Dedicated Graph Database Backend powered by Neo4j.
    Provides multi-hop Cypher traversals across biological nodes,
    shortest pathfinding, node/edge database sync, and GraphRAG context extraction.
    """

    _instance: Optional[Neo4jGraphDatabase] = None

    def __new__(cls, uri: Optional[str] = None, auth: Optional[Tuple[str, str]] = None, **kwargs: Any) -> Neo4jGraphDatabase:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, uri: Optional[str] = None, auth: Optional[Tuple[str, str]] = None, **kwargs: Any) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        self.auth = auth or (user, password)
        self.driver: Optional[Driver] = None

        # Fallback in-memory storage when live Neo4j database server is unreachable
        self._mock_nodes: Dict[str, Dict[str, Any]] = {}
        self._mock_edges: List[Dict[str, Any]] = []

        self._setup_db()

    def _setup_db(self) -> None:
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=self.auth)
            self.driver.verify_connectivity()
            self._init_schema()
            logger.info("Neo4j graph database connected successfully at %s", self.uri)
        except Exception as e:
            logger.warning("Could not connect to live Neo4j instance at %s (%s). Operating in-memory mode.", self.uri, e)
            self.driver = None

    def _init_schema(self) -> None:
        """Create constraints and indexes in Neo4j if connected."""
        if not self.driver:
            return

        constraints = [
            "CREATE CONSTRAINT compound_id IF NOT EXISTS FOR (c:CompoundNode) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT target_id IF NOT EXISTS FOR (t:TargetNode) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT pathway_id IF NOT EXISTS FOR (p:PathwayNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT physiology_id IF NOT EXISTS FOR (p:PhysiologyNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT biomarker_id IF NOT EXISTS FOR (b:BiomarkerNode) REQUIRE b.id IS UNIQUE",
            "CREATE CONSTRAINT phenotype_id IF NOT EXISTS FOR (p:PhenotypeNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:EntityNode) REQUIRE e.id IS UNIQUE",
        ]

        try:
            with self.driver.session() as session:
                for statement in constraints:
                    try:
                        session.run(statement)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Failed initializing Neo4j constraints: %s", e)

    def close(self) -> None:
        """Close Neo4j driver connection."""
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver = None

    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a Cypher query against Neo4j or falls back to in-memory graph store."""
        params = params or {}
        if self.driver:
            try:
                with self.driver.session() as session:
                    result = session.run(query, params)
                    rows: List[Dict[str, Any]] = []
                    for record in result:
                        data = record.data()
                        rows.append(data)
                    return rows
            except Exception as e:
                logger.error("Error executing Cypher query in Neo4j: %s", e)
                # Fall through to in-memory fallback logic

        # In-memory query simulation for fallback mode
        return self._fallback_execute_cypher(query, params)

    def _fallback_execute_cypher(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        q_upper = query.upper()

        # Handle count query (e.g. MATCH (c:CompoundNode) RETURN count(c) AS count)
        if "COUNT(" in q_upper:
            label_match = re.search(r"\(([a-zA-Z0-9_]+):([a-zA-Z0-9_]+)\)", query)
            target_label = label_match.group(2) if label_match else None
            cnt = 0
            for node in self._mock_nodes.values():
                labels = node.get("_labels", set())
                if not target_label or target_label in labels or target_label == "EntityNode":
                    cnt += 1
            return [{"count": cnt}]

        # Handle MERGE / CREATE node query
        if "MERGE (" in q_upper or "CREATE (" in q_upper:
            node_id = params.get("id") or params.get("src") or params.get("eid")
            if node_id:
                node_id = str(node_id)
                label_matches = re.findall(r":([a-zA-Z0-9_]+)", query.split("{")[0])
                node_type_labels = set(label_matches) if label_matches else {"EntityNode"}

                if node_id not in self._mock_nodes:
                    self._mock_nodes[node_id] = {
                        "id": node_id,
                        "label": params.get("label", node_id),
                        "node_type": params.get("nt", "entity"),
                        "_labels": node_type_labels,
                    }
                node_entry = self._mock_nodes[node_id]
                node_entry.setdefault("_labels", set()).update(node_type_labels)
                for k, v in params.items():
                    node_entry[k] = v
            return []

        # Handle MATCH nodes query (e.g. MATCH (e:EntityNode) RETURN ...)
        if "MATCH" in q_upper and "RETURN" in q_upper:
            # Check for specific filter in params e.g. eid
            target_eid = params.get("eid") or params.get("id") or params.get("start_id")
            label_matches = re.findall(r":([a-zA-Z0-9_]+)", query.split("RETURN")[0])
            target_label = label_matches[0] if label_matches else None

            results = []
            limit_match = re.search(r"LIMIT\s+(\d+)", q_upper)
            limit = int(limit_match.group(1)) if limit_match else 1000

            nodes_to_check = [self._mock_nodes[str(target_eid)]] if target_eid and str(target_eid) in self._mock_nodes else list(self._mock_nodes.values())

            for node in nodes_to_check:
                labels = node.get("_labels", set())
                if target_label and target_label not in labels and target_label != "EntityNode" and node.get("node_type") != target_label:
                    continue

                res_row = {}
                # Extract requested fields from RETURN statement
                ret_part = query.split("RETURN", 1)[1].split("LIMIT", 1)[0].strip()
                for col_spec in ret_part.split(","):
                    col_spec = col_spec.strip()
                    if " AS " in col_spec.upper():
                        expr, alias = re.split(r"\s+AS\s+", col_spec, flags=re.IGNORECASE)
                        expr = expr.strip()
                        alias = alias.strip()
                    else:
                        expr = col_spec
                        alias = col_spec.split(".")[-1]

                    field_key = expr.split(".")[-1] if "." in expr else expr
                    res_row[alias] = node.get(field_key) or node.get(alias)

                results.append(res_row)
                if len(results) >= limit:
                    break
            return results

        return []

    def sync_biological_graph(self, bio_graph: Any) -> Dict[str, int]:
        """
        Synchronizes all nodes and edges from a BiologicalGraph or NetworkX DiGraph
        into Neo4j and the fallback graph storage.
        Uses multi-label node indexing (e.g., :EntityNode:CompoundNode) and typed relationships.
        """
        nx_graph = getattr(bio_graph, "graph", bio_graph)
        nodes_synced = 0
        edges_synced = 0

        # 1. Sync Nodes with multi-label support
        for node_id, attrs in nx_graph.nodes(data=True):
            nid = str(node_id)
            nt = str(attrs.get("node_type", "entity")).lower()
            label = str(attrs.get("label") or nid)

            # Local fallback store
            labels = {"EntityNode"}
            node_props = {
                "id": nid,
                "label": label,
                "node_type": nt,
                "_labels": labels,
            }

            if nt == "compound":
                labels.add("CompoundNode")
                node_props.update({
                    "smiles": str(attrs.get("smiles") or ""),
                    "inchikey": str(attrs.get("inchikey") or ""),
                    "drug_class": str(attrs.get("drug_class") or ""),
                    "logP": float(attrs.get("logP") or 0.0),
                    "molecular_weight": float(attrs.get("molecular_weight") or 0.0),
                })
                q = """
                MERGE (c:EntityNode:CompoundNode {id: $id})
                SET c.label = $label, c.node_type = $node_type, c.smiles = $smiles, c.inchikey = $inchikey,
                    c.drug_class = $drug_class, c.logP = $logP, c.molecular_weight = $molecular_weight
                """
                self.execute_cypher(q, node_props)

            elif nt in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
                labels.add("TargetNode")
                node_props.update({
                    "family": str(attrs.get("family") or attrs.get("enzyme_family") or attrs.get("transporter_family") or ""),
                    "category": str(attrs.get("category") or ""),
                    "uniprot_id": str(attrs.get("uniprot_id") or ""),
                    "gene_symbol": str(attrs.get("gene_symbol") or ""),
                })
                q = """
                MERGE (t:EntityNode:TargetNode {id: $id})
                SET t.label = $label, t.node_type = $node_type, t.family = $family, t.category = $category,
                    t.uniprot_id = $uniprot_id, t.gene_symbol = $gene_symbol
                """
                self.execute_cypher(q, node_props)

            elif nt in ("signaling_pathway", "reaction", "pathway"):
                labels.add("PathwayNode")
                node_props.update({
                    "database": str(attrs.get("pathway_database") or "Reactome"),
                })
                q = """
                MERGE (p:EntityNode:PathwayNode {id: $id})
                SET p.label = $label, p.node_type = $node_type, p.database = $database
                """
                self.execute_cypher(q, node_props)

            elif nt in ("physiology", "organ_system"):
                labels.add("PhysiologyNode")
                node_props.update({
                    "organ_system": str(attrs.get("organ_system") or "Systemic"),
                })
                q = """
                MERGE (p:EntityNode:PhysiologyNode {id: $id})
                SET p.label = $label, p.node_type = $node_type, p.organ_system = $organ_system
                """
                self.execute_cypher(q, node_props)

            elif nt in ("biomarker", "lab"):
                labels.add("BiomarkerNode")
                node_props.update({
                    "unit": str(attrs.get("unit") or ""),
                    "panel": str(attrs.get("biomarker_panel") or ""),
                    "safe_lower": float(attrs.get("safe_lower_bound") or 0.0),
                    "safe_upper": float(attrs.get("safe_upper_bound") or 100.0),
                })
                q = """
                MERGE (b:EntityNode:BiomarkerNode {id: $id})
                SET b.label = $label, b.node_type = $node_type, b.unit = $unit, b.panel = $panel,
                    b.safe_lower = $safe_lower, b.safe_upper = $safe_upper
                """
                self.execute_cypher(q, node_props)

            elif nt in ("phenotype", "outcome", "toxicity", "benefit"):
                labels.add("PhenotypeNode")
                node_props.update({
                    "category": str(attrs.get("phenotype_category") or ""),
                    "severity": str(attrs.get("severity") or ""),
                })
                q = """
                MERGE (ph:EntityNode:PhenotypeNode {id: $id})
                SET ph.label = $label, ph.node_type = $node_type, ph.category = $category, ph.severity = $severity
                """
                self.execute_cypher(q, node_props)

            else:
                q_ent = """
                MERGE (e:EntityNode {id: $id})
                SET e.label = $label, e.node_type = $node_type
                """
                self.execute_cypher(q_ent, node_props)

            self._mock_nodes[nid] = node_props
            nodes_synced += 1

        # 2. Sync Edges (with both generic RELATIONSHIP and specific typed relationship)
        for source_id, target_id, attrs in nx_graph.edges(data=True):
            src = str(source_id)
            tgt = str(target_id)
            edge_type = str(attrs.get("edge_type") or "MODULATES")
            mag = float(attrs.get("vector_magnitude") or 1.0)
            ki = float(attrs.get("affinity_ki")) if attrs.get("affinity_ki") is not None else -1.0
            ic50 = float(attrs.get("inhibition_ic50")) if attrs.get("inhibition_ic50") is not None else -1.0

            edge_props = {
                "source": src,
                "target": tgt,
                "edge_type": edge_type,
                "magnitude": mag,
                "ki": ki,
                "ic50": ic50,
            }
            self._mock_edges.append(edge_props)

            # Sanitize relationship type name for Cypher (alphanumeric and underscore)
            clean_rel_type = re.sub(r"[^A-Za-z0-9_]", "_", edge_type.upper()) or "RELATIONSHIP"

            q_rel = f"""
            MATCH (a:EntityNode {{id: $src}}), (b:EntityNode {{id: $tgt}})
            MERGE (a)-[r:RELATIONSHIP {{edge_type: $edge_type}}]->(b)
            SET r.magnitude = $mag, r.affinity_ki = $ki, r.inhibition_ic50 = $ic50
            """
            q_typed = f"""
            MATCH (a:EntityNode {{id: $src}}), (b:EntityNode {{id: $tgt}})
            MERGE (a)-[r:{clean_rel_type} {{edge_type: $edge_type}}]->(b)
            SET r.magnitude = $mag, r.affinity_ki = $ki, r.inhibition_ic50 = $ic50
            """
            try:
                self.execute_cypher(q_rel, {"src": src, "tgt": tgt, "edge_type": edge_type, "mag": mag, "ki": ki, "ic50": ic50})
                if clean_rel_type != "RELATIONSHIP":
                    self.execute_cypher(q_typed, {"src": src, "tgt": tgt, "edge_type": edge_type, "mag": mag, "ki": ki, "ic50": ic50})
                edges_synced += 1
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
        if self.driver:
            try:
                return self.execute_cypher(cypher, {"start_id": start_id})
            except Exception:
                pass

        # Fallback multi-hop traversal in memory
        results = []
        visited = set()
        queue = [(str(start_id), 0)]

        while queue:
            curr_id, depth = queue.pop(0)
            if depth >= max_hops or curr_id in visited:
                continue
            visited.add(curr_id)

            curr_node = self._mock_nodes.get(curr_id, {"id": curr_id, "label": curr_id, "node_type": "entity"})

            for edge in self._mock_edges:
                if edge["source"] == curr_id:
                    tgt_id = edge["target"]
                    tgt_node = self._mock_nodes.get(tgt_id, {"id": tgt_id, "label": tgt_id, "node_type": "entity"})
                    results.append({
                        "source_id": curr_node["id"],
                        "source_label": curr_node.get("label", curr_node["id"]),
                        "target_id": tgt_node["id"],
                        "target_label": tgt_node.get("label", tgt_node["id"]),
                        "target_type": tgt_node.get("node_type", "entity"),
                    })
                    if tgt_id not in visited:
                        queue.append((tgt_id, depth + 1))

        return results

    def get_graphrag_context(self, entity_ids: List[str], max_hops: int = 2) -> Dict[str, Any]:
        """
        Extracts structured GraphRAG subgraph context for LLM prompt integration.
        Formats entities, multi-hop relationship triples, pathway cascades, biomarkers, and outcomes.
        """
        clean_ids = [str(e).strip() for e in entity_ids if e]
        if not clean_ids:
            return {"entities": [], "triples": [], "text_summary": "No entities provided."}

        triples: List[Dict[str, Any]] = []
        entities_found: Dict[str, Dict[str, Any]] = {}

        for eid in clean_ids:
            if eid in self._mock_nodes:
                entities_found[eid] = {
                    "id": self._mock_nodes[eid]["id"],
                    "label": self._mock_nodes[eid].get("label", eid),
                    "node_type": self._mock_nodes[eid].get("node_type", "entity"),
                }

            # Query relationships
            q_rel = """
            MATCH (a:EntityNode {id: $eid})-[r:RELATIONSHIP]->(b:EntityNode)
            RETURN a.id AS source, a.label AS source_label,
                   r.edge_type AS relationship, r.magnitude AS magnitude,
                   b.id AS target, b.label AS target_label, b.node_type AS target_type
            """
            rels = self.execute_cypher(q_rel, {"eid": eid})

            # Fallback relationship gathering if Cypher returned empty or driver offline
            if not rels:
                for edge in self._mock_edges:
                    if edge["source"] == eid:
                        src_n = self._mock_nodes.get(eid, {"id": eid, "label": eid, "node_type": "entity"})
                        tgt_n = self._mock_nodes.get(edge["target"], {"id": edge["target"], "label": edge["target"], "node_type": "entity"})
                        rels.append({
                            "source": eid,
                            "source_label": src_n.get("label", eid),
                            "relationship": edge.get("edge_type", "MODULATES"),
                            "magnitude": edge.get("magnitude", 1.0),
                            "target": edge["target"],
                            "target_label": tgt_n.get("label", edge["target"]),
                            "target_type": tgt_n.get("node_type", "entity"),
                        })

            for r in rels:
                triples.append({
                    "subject": r.get("source_label") or r.get("source"),
                    "predicate": r.get("relationship") or "MODULATES",
                    "object": r.get("target_label") or r.get("target"),
                    "object_type": r.get("target_type"),
                    "magnitude": r.get("magnitude", 1.0),
                })
                tgt_id = r.get("target")
                if tgt_id and tgt_id not in entities_found:
                    entities_found[tgt_id] = {
                        "id": tgt_id,
                        "label": r.get("target_label", tgt_id),
                        "node_type": r.get("target_type", "entity"),
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
_GRAPH_DB_INSTANCE: Optional[Neo4jGraphDatabase] = None


def get_graph_database(uri: Optional[str] = None, auth: Optional[Tuple[str, str]] = None, **kwargs: Any) -> Neo4jGraphDatabase:
    global _GRAPH_DB_INSTANCE
    if _GRAPH_DB_INSTANCE is None:
        _GRAPH_DB_INSTANCE = Neo4jGraphDatabase(uri=uri, auth=auth, **kwargs)
    return _GRAPH_DB_INSTANCE
