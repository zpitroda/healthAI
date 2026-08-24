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
    shortest pathfinding, node/edge database sync, and scientific GraphRAG context extraction.
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

        constraints_and_indexes = [
            "CREATE CONSTRAINT compound_id IF NOT EXISTS FOR (c:CompoundNode) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT target_id IF NOT EXISTS FOR (t:TargetNode) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT pathway_id IF NOT EXISTS FOR (p:PathwayNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT physiology_id IF NOT EXISTS FOR (p:PhysiologyNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT biomarker_id IF NOT EXISTS FOR (b:BiomarkerNode) REQUIRE b.id IS UNIQUE",
            "CREATE CONSTRAINT phenotype_id IF NOT EXISTS FOR (p:PhenotypeNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:EntityNode) REQUIRE e.id IS UNIQUE",
            "CREATE INDEX compound_smiles IF NOT EXISTS FOR (c:CompoundNode) ON (c.smiles)",
            "CREATE INDEX compound_inchikey IF NOT EXISTS FOR (c:CompoundNode) ON (c.inchikey)",
            "CREATE INDEX target_gene IF NOT EXISTS FOR (t:TargetNode) ON (t.gene_symbol)",
            "CREATE INDEX target_uniprot IF NOT EXISTS FOR (t:TargetNode) ON (t.uniprot_id)",
        ]

        try:
            with self.driver.session() as session:
                for statement in constraints_and_indexes:
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
        into Neo4j and the fallback graph storage with complete scientific fidelity.
        Uses multi-label node indexing (e.g., :EntityNode:CompoundNode) and typed relationships.
        """
        nx_graph = getattr(bio_graph, "graph", bio_graph)
        nodes_synced = 0
        edges_synced = 0

        # 1. Sync Nodes with multi-label support and deep scientific attributes
        for node_id, attrs in nx_graph.nodes(data=True):
            nid = str(node_id)
            nt = str(attrs.get("node_type", "entity")).lower()
            label = str(attrs.get("label") or nid)

            # Base attributes
            labels = {"EntityNode"}
            node_props: Dict[str, Any] = {
                "id": nid,
                "label": label,
                "node_type": nt,
                "category": str(attrs.get("category") or ""),
                "description": str(attrs.get("description") or ""),
                "_labels": labels,
            }

            if nt == "compound":
                labels.add("CompoundNode")
                node_props.update({
                    "canonical_name": str(attrs.get("canonical_name") or label),
                    "smiles": str(attrs.get("smiles") or ""),
                    "inchikey": str(attrs.get("inchikey") or ""),
                    "pubchem_cid": str(attrs.get("pubchem_cid") or ""),
                    "chembl_id": str(attrs.get("chembl_id") or ""),
                    "drug_class": str(attrs.get("drug_class") or ""),
                    "logP": float(attrs.get("logP") or 0.0),
                    "tpsa": float(attrs.get("tpsa") or 0.0),
                    "molecular_weight": float(attrs.get("molecular_weight") or 0.0),
                    "half_life_hours": float(attrs.get("base_half_life") or attrs.get("half_life_hours") or 0.0),
                    "bioavailability_pct": float(attrs.get("bioavailability_pct") or 0.0),
                    "volume_of_distribution": float(attrs.get("volume_of_distribution") or 0.0),
                    "protein_binding_pct": float(attrs.get("protein_binding_pct") or 0.0),
                    "renal_clearance_fraction": float(attrs.get("renal_clearance_fraction") or 0.0),
                    "hepatic_clearance_fraction": float(attrs.get("hepatic_clearance_fraction") or 0.0),
                    "is_narrow_therapeutic_index": bool(attrs.get("is_narrow_therapeutic_index") or False),
                    "cyp_substrates": list(attrs.get("cyp_substrates") or []),
                    "cyp_inhibitors": list(attrs.get("cyp_inhibitors") or []),
                    "cyp_inducers": list(attrs.get("cyp_inducers") or []),
                })
                q = """
                MERGE (c:EntityNode:CompoundNode {id: $id})
                SET c.label = $label, c.node_type = $node_type, c.canonical_name = $canonical_name,
                    c.smiles = $smiles, c.inchikey = $inchikey, c.pubchem_cid = $pubchem_cid,
                    c.chembl_id = $chembl_id, c.drug_class = $drug_class, c.logP = $logP,
                    c.tpsa = $tpsa, c.molecular_weight = $molecular_weight,
                    c.half_life_hours = $half_life_hours, c.bioavailability_pct = $bioavailability_pct,
                    c.volume_of_distribution = $volume_of_distribution, c.protein_binding_pct = $protein_binding_pct,
                    c.renal_clearance_fraction = $renal_clearance_fraction, c.hepatic_clearance_fraction = $hepatic_clearance_fraction,
                    c.is_narrow_therapeutic_index = $is_narrow_therapeutic_index
                """
                self.execute_cypher(q, node_props)

            elif nt in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
                labels.add("TargetNode")
                node_props.update({
                    "family": str(attrs.get("family") or attrs.get("receptor_family") or attrs.get("enzyme_family") or attrs.get("transporter_family") or ""),
                    "uniprot_id": str(attrs.get("uniprot_id") or ""),
                    "gene_symbol": str(attrs.get("gene_symbol") or ""),
                    "subcellular_location": str(attrs.get("subcellular_location") or ""),
                    "direction": str(attrs.get("direction") or ""),
                })
                q = """
                MERGE (t:EntityNode:TargetNode {id: $id})
                SET t.label = $label, t.node_type = $node_type, t.family = $family, t.category = $category,
                    t.uniprot_id = $uniprot_id, t.gene_symbol = $gene_symbol,
                    t.subcellular_location = $subcellular_location, t.direction = $direction
                """
                self.execute_cypher(q, node_props)

            elif nt in ("signaling_pathway", "reaction", "pathway"):
                labels.add("PathwayNode")
                node_props.update({
                    "database": str(attrs.get("pathway_database") or "Reactome"),
                    "pathway_id": str(attrs.get("pathway_id") or ""),
                    "pathway_category": str(attrs.get("pathway_category") or ""),
                })
                q = """
                MERGE (p:EntityNode:PathwayNode {id: $id})
                SET p.label = $label, p.node_type = $node_type, p.database = $database,
                    p.pathway_id = $pathway_id, p.pathway_category = $pathway_category
                """
                self.execute_cypher(q, node_props)

            elif nt in ("physiology", "organ_system"):
                labels.add("PhysiologyNode")
                node_props.update({
                    "organ_system": str(attrs.get("organ_system") or "Systemic"),
                    "physiological_function": str(attrs.get("physiological_function") or ""),
                    "tissue_specificity": str(attrs.get("tissue_specificity") or ""),
                })
                q = """
                MERGE (p:EntityNode:PhysiologyNode {id: $id})
                SET p.label = $label, p.node_type = $node_type, p.organ_system = $organ_system,
                    p.physiological_function = $physiological_function, p.tissue_specificity = $tissue_specificity
                """
                self.execute_cypher(q, node_props)

            elif nt in ("biomarker", "lab"):
                labels.add("BiomarkerNode")
                node_props.update({
                    "unit": str(attrs.get("unit") or ""),
                    "panel": str(attrs.get("biomarker_panel") or ""),
                    "baseline": float(attrs.get("baseline") or 0.0),
                    "safe_lower": float(attrs.get("safe_lower_bound") or 0.0),
                    "safe_upper": float(attrs.get("safe_upper_bound") or 100.0),
                    "gain_up": float(attrs.get("gain_up") or 0.0),
                    "gain_down": float(attrs.get("gain_down") or 0.0),
                    "onset_days": float(attrs.get("onset_days") or 1.0),
                    "half_time_days": float(attrs.get("half_time_days") or 3.0),
                    "time_to_steady_state_weeks": float(attrs.get("time_to_steady_state_weeks") or 1.0),
                    "kinetic_profile": str(attrs.get("kinetic_profile") or "direct_receptor"),
                })
                q = """
                MERGE (b:EntityNode:BiomarkerNode {id: $id})
                SET b.label = $label, b.node_type = $node_type, b.unit = $unit, b.panel = $panel,
                    b.baseline = $baseline, b.safe_lower = $safe_lower, b.safe_upper = $safe_upper,
                    b.gain_up = $gain_up, b.gain_down = $gain_down, b.onset_days = $onset_days,
                    b.half_time_days = $half_time_days, b.time_to_steady_state_weeks = $time_to_steady_state_weeks,
                    b.kinetic_profile = $kinetic_profile
                """
                self.execute_cypher(q, node_props)

            elif nt in ("phenotype", "outcome", "toxicity", "benefit"):
                labels.add("PhenotypeNode")
                node_props.update({
                    "category": str(attrs.get("phenotype_category") or ""),
                    "severity": str(attrs.get("severity") or ""),
                    "clinical_evidence_level": str(attrs.get("clinical_evidence_level") or "established"),
                    "mesh_id": str(attrs.get("mesh_id") or ""),
                })
                q = """
                MERGE (ph:EntityNode:PhenotypeNode {id: $id})
                SET ph.label = $label, ph.node_type = $node_type, ph.category = $category,
                    ph.severity = $severity, ph.clinical_evidence_level = $clinical_evidence_level,
                    ph.mesh_id = $mesh_id
                """
                self.execute_cypher(q, node_props)

            else:
                q_ent = """
                MERGE (e:EntityNode {id: $id})
                SET e.label = $label, e.node_type = $node_type, e.category = $category, e.description = $description
                """
                self.execute_cypher(q_ent, node_props)

            self._mock_nodes[nid] = node_props
            nodes_synced += 1

        # 2. Sync Edges (with generic RELATIONSHIP and specific typed relationship)
        for source_id, target_id, attrs in nx_graph.edges(data=True):
            src = str(source_id)
            tgt = str(target_id)
            edge_type = str(attrs.get("edge_type") or "MODULATES")
            mag = float(attrs.get("vector_magnitude") or 1.0)
            ki = float(attrs.get("affinity_ki")) if attrs.get("affinity_ki") is not None else -1.0
            ic50 = float(attrs.get("inhibition_ic50")) if attrs.get("inhibition_ic50") is not None else -1.0
            ec50 = float(attrs.get("ec50")) if attrs.get("ec50") is not None else -1.0
            inh_type = str(attrs.get("inhibition_type") or "")
            conf = float(attrs.get("confidence") or 1.0)
            ev_level = str(attrs.get("evidence_level") or "in_vitro")
            pmids = list(attrs.get("pmids") or [])
            is_bridge = bool(attrs.get("is_bridge") or False)
            mech_notes = str(attrs.get("mechanism_notes") or attrs.get("description") or "")

            edge_props = {
                "source": src,
                "target": tgt,
                "edge_type": edge_type,
                "magnitude": mag,
                "ki": ki,
                "ic50": ic50,
                "ec50": ec50,
                "inhibition_type": inh_type,
                "confidence": conf,
                "evidence_level": ev_level,
                "pmids": pmids,
                "is_bridge": is_bridge,
                "mechanism_notes": mech_notes,
            }
            self._mock_edges.append(edge_props)

            # Sanitize relationship type name for Cypher
            clean_rel_type = re.sub(r"[^A-Za-z0-9_]", "_", edge_type.upper()) or "RELATIONSHIP"

            q_rel = """
            MATCH (a:EntityNode {id: $src}), (b:EntityNode {id: $tgt})
            MERGE (a)-[r:RELATIONSHIP {edge_type: $edge_type}]->(b)
            SET r.magnitude = $mag, r.affinity_ki = $ki, r.inhibition_ic50 = $ic50,
                r.ec50 = $ec50, r.inhibition_type = $inhibition_type, r.confidence = $conf,
                r.evidence_level = $ev_level, r.is_bridge = $is_bridge, r.mechanism_notes = $mech_notes
            """
            q_typed = f"""
            MATCH (a:EntityNode {{id: $src}}), (b:EntityNode {{id: $tgt}})
            MERGE (a)-[r:{clean_rel_type} {{edge_type: $edge_type}}]->(b)
            SET r.magnitude = $mag, r.affinity_ki = $ki, r.inhibition_ic50 = $ic50,
                r.ec50 = $ec50, r.inhibition_type = $inhibition_type, r.confidence = $conf,
                r.evidence_level = $ev_level, r.is_bridge = $is_bridge, r.mechanism_notes = $mech_notes
            """
            try:
                params = {
                    "src": src, "tgt": tgt, "edge_type": edge_type, "mag": mag,
                    "ki": ki, "ic50": ic50, "ec50": ec50, "inhibition_type": inh_type,
                    "conf": conf, "ev_level": ev_level, "is_bridge": is_bridge,
                    "mech_notes": mech_notes,
                }
                self.execute_cypher(q_rel, params)
                if clean_rel_type != "RELATIONSHIP":
                    self.execute_cypher(q_typed, params)
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

    def trace_causal_chains(self, start_node_ids: List[str], max_depth: int = 5) -> List[List[Dict[str, Any]]]:
        """
        Traces unbroken multi-tier causal reasoning pathways starting from compound nodes
        all the way to clinical biomarkers and outcomes.
        """
        chains: List[List[Dict[str, Any]]] = []

        def dfs(current_id: str, path: List[Dict[str, Any]], visited: Set[str], depth: int) -> None:
            if depth >= max_depth:
                if len(path) > 1:
                    chains.append(list(path))
                return

            outgoing = [e for e in self._mock_edges if e["source"] == current_id]
            if not outgoing:
                if len(path) > 1:
                    chains.append(list(path))
                return

            has_children = False
            for edge in outgoing:
                tgt = edge["target"]
                if tgt in visited:
                    continue
                tgt_node = self._mock_nodes.get(tgt, {"id": tgt, "label": tgt, "node_type": "entity"})
                step = {
                    "source": current_id,
                    "target": tgt,
                    "target_label": tgt_node.get("label", tgt),
                    "target_type": tgt_node.get("node_type", "entity"),
                    "relationship": edge.get("edge_type", "MODULATES"),
                    "magnitude": edge.get("magnitude", 1.0),
                    "affinity_ki": edge.get("ki"),
                    "inhibition_ic50": edge.get("ic50"),
                }
                visited.add(tgt)
                has_children = True
                dfs(tgt, path + [step], visited, depth + 1)
                visited.remove(tgt)

            if not has_children and len(path) > 1:
                chains.append(list(path))

        for start_id in start_node_ids:
            sid = str(start_id)
            if sid in self._mock_nodes:
                s_node = self._mock_nodes[sid]
                root_step = {"source": "ROOT", "target": sid, "target_label": s_node.get("label", sid), "target_type": s_node.get("node_type", "compound")}
                dfs(sid, [root_step], {sid}, 0)

        return chains

    def get_graphrag_context(
        self,
        entity_ids: List[str],
        max_hops: int = 2,
        include_pkpd: bool = True,
        include_kinetics: bool = True,
        include_causal_chains: bool = True,
    ) -> Dict[str, Any]:
        """
        Extracts structured GraphRAG subgraph context optimized for LLM prompt integration.
        Formats entities, multi-hop relationship triples, causal reasoning paths,
        PK/PD parameters, target competition analysis, and natural-language grounding summaries.
        """
        clean_ids = [str(e).strip() for e in entity_ids if e]
        if not clean_ids:
            return {
                "focused_ids": [],
                "entities": [],
                "triples": [],
                "triple_count": 0,
                "causal_chains": [],
                "pkpd_matrix": {},
                "target_competition": [],
                "biomarker_kinetics": [],
                "text_summary": "No entities provided.",
                "formatted_prompt_context": "No biological entities specified.",
            }

        triples: List[Dict[str, Any]] = []
        entities_found: Dict[str, Dict[str, Any]] = {}
        target_to_compounds: Dict[str, List[str]] = {}
        pkpd_matrix: Dict[str, Dict[str, Any]] = {}
        biomarker_kinetics: List[Dict[str, Any]] = []

        def _clean_node_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
            clean: Dict[str, Any] = {}
            for k, v in raw_data.items():
                if isinstance(v, set):
                    clean[k] = sorted(list(v))
                elif isinstance(v, (list, tuple)):
                    clean[k] = list(v)
                else:
                    clean[k] = v
            return clean

        # 1. Discover entities and 1-2 hop relationships
        for eid in clean_ids:
            if eid in self._mock_nodes:
                n_info = _clean_node_data(self._mock_nodes[eid])
                entities_found[eid] = n_info
                if n_info.get("node_type") == "compound" and include_pkpd:
                    pkpd_matrix[eid] = {
                        "name": n_info.get("label", eid),
                        "smiles": n_info.get("smiles"),
                        "inchikey": n_info.get("inchikey"),
                        "drug_class": n_info.get("drug_class"),
                        "half_life_hours": n_info.get("half_life_hours"),
                        "oral_bioavailability_pct": n_info.get("bioavailability_pct"),
                        "volume_of_distribution_L_kg": n_info.get("volume_of_distribution"),
                        "protein_binding_pct": n_info.get("protein_binding_pct"),
                        "renal_clearance_fraction": n_info.get("renal_clearance_fraction"),
                        "hepatic_clearance_fraction": n_info.get("hepatic_clearance_fraction"),
                        "is_narrow_therapeutic_index": n_info.get("is_narrow_therapeutic_index"),
                        "cyp_substrates": n_info.get("cyp_substrates", []),
                        "cyp_inhibitors": n_info.get("cyp_inhibitors", []),
                        "cyp_inducers": n_info.get("cyp_inducers", []),
                    }

            # Query relationships
            q_rel = """
            MATCH (a:EntityNode {id: $eid})-[r:RELATIONSHIP]->(b:EntityNode)
            RETURN a.id AS source, a.label AS source_label, a.node_type AS source_type,
                   r.edge_type AS relationship, r.magnitude AS magnitude,
                   r.affinity_ki AS affinity_ki, r.inhibition_ic50 AS inhibition_ic50,
                   r.ec50 AS ec50, r.inhibition_type AS inhibition_type,
                   r.evidence_level AS evidence_level, r.mechanism_notes AS mechanism_notes,
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
                            "source_type": src_n.get("node_type", "entity"),
                            "relationship": edge.get("edge_type", "MODULATES"),
                            "magnitude": edge.get("magnitude", 1.0),
                            "affinity_ki": edge.get("ki"),
                            "inhibition_ic50": edge.get("ic50"),
                            "ec50": edge.get("ec50"),
                            "inhibition_type": edge.get("inhibition_type"),
                            "evidence_level": edge.get("evidence_level"),
                            "mechanism_notes": edge.get("mechanism_notes"),
                            "target": edge["target"],
                            "target_label": tgt_n.get("label", edge["target"]),
                            "target_type": tgt_n.get("node_type", "entity"),
                        })

            for r in rels:
                tgt_id = str(r.get("target"))
                tgt_type = str(r.get("target_type"))
                tgt_label = str(r.get("target_label") or tgt_id)

                if tgt_type in ("receptor", "enzyme", "transporter", "ion_channel", "target"):
                    target_to_compounds.setdefault(tgt_label, []).append(str(r.get("source_label") or eid))

                triple_obj = {
                    "subject": r.get("source_label") or r.get("source"),
                    "subject_type": r.get("source_type"),
                    "predicate": r.get("relationship") or "MODULATES",
                    "object": tgt_label,
                    "object_type": tgt_type,
                    "magnitude": r.get("magnitude", 1.0),
                    "affinity_ki": r.get("affinity_ki") if r.get("affinity_ki") and r.get("affinity_ki") > 0 else None,
                    "inhibition_ic50": r.get("inhibition_ic50") if r.get("inhibition_ic50") and r.get("inhibition_ic50") > 0 else None,
                    "ec50": r.get("ec50") if r.get("ec50") and r.get("ec50") > 0 else None,
                    "inhibition_type": r.get("inhibition_type") or None,
                    "evidence_level": r.get("evidence_level") or "in_vitro",
                    "mechanism_notes": r.get("mechanism_notes") or None,
                }
                triples.append(triple_obj)

                if tgt_id and tgt_id not in entities_found:
                    raw_tgt_data = self._mock_nodes.get(tgt_id, {
                        "id": tgt_id,
                        "label": tgt_label,
                        "node_type": tgt_type,
                    })
                    tgt_node_data = _clean_node_data(raw_tgt_data)
                    entities_found[tgt_id] = tgt_node_data
                    if tgt_type in ("biomarker", "lab") and include_kinetics:
                        biomarker_kinetics.append({
                            "biomarker": tgt_label,
                            "baseline": tgt_node_data.get("baseline"),
                            "safe_lower": tgt_node_data.get("safe_lower"),
                            "safe_upper": tgt_node_data.get("safe_upper"),
                            "unit": tgt_node_data.get("unit"),
                            "panel": tgt_node_data.get("panel"),
                            "onset_days": tgt_node_data.get("onset_days"),
                            "half_time_days": tgt_node_data.get("half_time_days"),
                            "steady_state_weeks": tgt_node_data.get("time_to_steady_state_weeks"),
                            "kinetic_profile": tgt_node_data.get("kinetic_profile"),
                        })

        # 2. Extract Causal Reasoning Chains
        causal_chains = self.trace_causal_chains(clean_ids, max_depth=max_hops + 3) if include_causal_chains else []

        # 3. Detect Target Competition Clashes
        target_competition = []
        for tgt_name, comp_list in target_to_compounds.items():
            unique_comps = list(set(comp_list))
            if len(unique_comps) > 1:
                target_competition.append({
                    "target": tgt_name,
                    "competing_compounds": unique_comps,
                    "competition_type": "shared_molecular_target",
                    "clinical_significance": f"Dual or competitive modulation at {tgt_name} by {', '.join(unique_comps)}",
                })

        # 4. Construct Structured Prompt Context for LLM
        prompt_sections = [
            "# SCIENTIFIC KNOWLEDGE GRAPH CONTEXT (GRAPHRAG GROUNDING)",
            "> Use the authoritative biological pathways, pharmacokinetic parameters, and causal chains below to ground your clinical and pharmacological reasoning. Do not invent ungrounded mechanisms.",
            "",
            f"## 1. Focused Entities ({len(entities_found)} nodes)",
        ]
        for e in list(entities_found.values())[:20]:
            prompt_sections.append(f"- **{e.get('label')}** ({e.get('node_type')}) | Category: {e.get('category', 'General')}")

        if pkpd_matrix:
            prompt_sections.append("\n## 2. Pharmacokinetic & Clearance Profiles")
            for cid, pk in pkpd_matrix.items():
                prompt_sections.append(
                    f"- **{pk['name']}**: t1/2 = {pk.get('half_life_hours', 'N/A')}h, "
                    f"Bioavailability = {pk.get('oral_bioavailability_pct', 'N/A')}%, "
                    f"Vd = {pk.get('volume_of_distribution_L_kg', 'N/A')} L/kg, "
                    f"Renal (fe) = {pk.get('renal_clearance_fraction', 'N/A')}, "
                    f"Hepatic (fh) = {pk.get('hepatic_clearance_fraction', 'N/A')}"
                )
                if pk.get("cyp_inhibitors"):
                    prompt_sections.append(f"  * CYP Inhibition: {', '.join(pk['cyp_inhibitors'])}")
                if pk.get("cyp_substrates"):
                    prompt_sections.append(f"  * CYP Substrate: {', '.join(pk['cyp_substrates'])}")

        if target_competition:
            prompt_sections.append("\n## 3. Competitive Target Clashes & Cross-Talk")
            for tc in target_competition:
                prompt_sections.append(f"- **{tc['target']}**: Competitively engaged by {', '.join(tc['competing_compounds'])}")

        prompt_sections.append(f"\n## 4. Authoritative Biological Triples ({min(len(triples), 40)} shown)")
        for t in triples[:40]:
            affinity_str = f" [Ki: {t['affinity_ki']} nM]" if t.get("affinity_ki") else ""
            ic50_str = f" [IC50: {t['inhibition_ic50']} nM]" if t.get("inhibition_ic50") else ""
            prompt_sections.append(f"- [{t['subject']}] --({t['predicate']}{affinity_str}{ic50_str})--> [{t['object']}] ({t['object_type']})")

        if causal_chains:
            prompt_sections.append("\n## 5. Multi-Tier Causal Reasoning Chains")
            for i, chain in enumerate(causal_chains[:8], 1):
                steps_str = " ➔ ".join([f"{c['target_label']} ({c['target_type']})" for c in chain])
                prompt_sections.append(f"{i}. {steps_str}")

        if biomarker_kinetics:
            prompt_sections.append("\n## 6. Biomarker Kinetic Calibrations")
            for bk in biomarker_kinetics[:10]:
                prompt_sections.append(
                    f"- **{bk['biomarker']}**: Safe Range [{bk.get('safe_lower')}-{bk.get('safe_upper')} {bk.get('unit')}], "
                    f"Onset: {bk.get('onset_days')}d, Half-Time: {bk.get('half_time_days')}d, Steady-State: {bk.get('steady_state_weeks')}w"
                )

        formatted_context = "\n".join(prompt_sections)

        # Simple text summary
        summary_lines = ["### GraphRAG Biological Subgraph Context:"]
        summary_lines.append(f"- Focused Entities: {', '.join([e['label'] for e in entities_found.values()][:10])}")
        summary_lines.append(f"- Knowledge Triples: {len(triples)} biological associations")
        summary_lines.append(f"- Causal Chains: {len(causal_chains)} complete multi-tier pathways")
        if target_competition:
            summary_lines.append(f"- Target Clashes: {len(target_competition)} shared target interactions")

        return {
            "focused_ids": clean_ids,
            "entities": list(entities_found.values()),
            "triples": triples,
            "triple_count": len(triples),
            "causal_chains": causal_chains[:15],
            "pkpd_matrix": pkpd_matrix,
            "target_competition": target_competition,
            "biomarker_kinetics": biomarker_kinetics,
            "text_summary": "\n".join(summary_lines),
            "formatted_prompt_context": formatted_context,
        }


# Singleton instance accessor
_GRAPH_DB_INSTANCE: Optional[Neo4jGraphDatabase] = None


def get_graph_database(uri: Optional[str] = None, auth: Optional[Tuple[str, str]] = None, **kwargs: Any) -> Neo4jGraphDatabase:
    global _GRAPH_DB_INSTANCE
    if _GRAPH_DB_INSTANCE is None:
        _GRAPH_DB_INSTANCE = Neo4jGraphDatabase(uri=uri, auth=auth, **kwargs)
    return _GRAPH_DB_INSTANCE

