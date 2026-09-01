from __future__ import annotations

import copy
import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from neo4j import GraphDatabase, Driver
from cachetools import LRUCache

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
        self._graphrag_cache: LRUCache = LRUCache(maxsize=1000)

        self._setup_db()

    def _setup_db(self) -> None:
        try:
            import socket
            import urllib.parse
            parsed = urllib.parse.urlparse(self.uri.replace("bolt://", "http://"))
            host = parsed.hostname or "localhost"
            port = parsed.port or 7687
            
            # Fast socket probe (0.15s) to avoid slow driver timeout when offline
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.15)
                if sock.connect_ex((host, port)) != 0:
                    self.driver = None
                    return

            self.driver = GraphDatabase.driver(self.uri, auth=self.auth, connection_timeout=0.5, max_connection_lifetime=30.0)
            self.driver.verify_connectivity()
            self._init_schema()
            logger.info("Neo4j graph database connected successfully at %s", self.uri)
        except Exception as e:
            logger.warning("Could not connect to live Neo4j instance at %s (%s). Operating in-memory mode.", self.uri, e)
            self.driver = None

    _schema_initialized = False

    def _init_schema(self) -> None:
        """Create constraints and indexes in Neo4j if connected."""
        if not self.driver or Neo4jGraphDatabase._schema_initialized:
            return
        Neo4jGraphDatabase._schema_initialized = True

        constraints_and_indexes = [
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:EntityNode) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT compound_id IF NOT EXISTS FOR (c:CompoundNode) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT target_id IF NOT EXISTS FOR (t:TargetNode) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT pathway_id IF NOT EXISTS FOR (p:PathwayNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT physiology_id IF NOT EXISTS FOR (p:PhysiologyNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT biomarker_id IF NOT EXISTS FOR (b:BiomarkerNode) REQUIRE b.id IS UNIQUE",
            "CREATE CONSTRAINT phenotype_id IF NOT EXISTS FOR (p:PhenotypeNode) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT citation_id IF NOT EXISTS FOR (c:CitationNode) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT trial_id IF NOT EXISTS FOR (t:ClinicalTrialNode) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (cl:EvidenceClaimNode) REQUIRE cl.id IS UNIQUE",
            "DROP CONSTRAINT citation_pmid IF EXISTS",
            "DROP CONSTRAINT trial_nct IF EXISTS",
            "CREATE INDEX compound_smiles IF NOT EXISTS FOR (c:CompoundNode) ON (c.smiles)",
            "CREATE INDEX compound_inchikey IF NOT EXISTS FOR (c:CompoundNode) ON (c.inchikey)",
            "CREATE INDEX target_gene IF NOT EXISTS FOR (t:TargetNode) ON (t.gene_symbol)",
            "CREATE INDEX target_uniprot IF NOT EXISTS FOR (t:TargetNode) ON (t.uniprot_id)",
            "CREATE INDEX citation_pmid IF NOT EXISTS FOR (c:CitationNode) ON (c.pmid)",
            "CREATE INDEX citation_year IF NOT EXISTS FOR (c:CitationNode) ON (c.pub_year)",
            "CREATE INDEX citation_tier IF NOT EXISTS FOR (c:CitationNode) ON (c.evidence_tier)",
            "CREATE INDEX trial_nct IF NOT EXISTS FOR (t:ClinicalTrialNode) ON (t.nct_id)",
            "CREATE INDEX claim_type IF NOT EXISTS FOR (cl:EvidenceClaimNode) ON (cl.claim_type)",
            "CREATE INDEX claim_dispute IF NOT EXISTS FOR (cl:EvidenceClaimNode) ON (cl.dispute_status)",
            "MATCH (n) WHERE (n:CompoundNode OR n:TargetNode OR n:PathwayNode OR n:PhysiologyNode OR n:BiomarkerNode OR n:PhenotypeNode OR n:CitationNode OR n:ClinicalTrialNode OR n:EvidenceClaimNode) AND NOT n:EntityNode SET n:EntityNode",
        ]

        try:
            with self.driver.session() as session:
                for statement in constraints_and_indexes:
                    try:
                        session.run(statement)
                    except Exception as e:
                        import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)
        except Exception as e:
            logger.debug("Failed initializing Neo4j constraints: %s", e)

    def is_connected(self) -> bool:
        """Check if connected to live Neo4j database, attempting connection if not yet established."""
        if self.driver is None:
            self._setup_db()
        return self.driver is not None

    def close(self) -> None:
        """Close Neo4j driver connection."""
        if self.driver:
            try:
                self.driver.close()
            except Exception as e:
                import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)
            self.driver = None

    @classmethod
    def _sanitize_dict_for_json(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitizes dictionary values into serializable primitives."""
        sanitized = {}
        for k, v in d.items():
            if str(k).startswith("_"):
                continue
            if isinstance(v, (set, tuple)):
                sanitized[str(k)] = list(v)
            elif isinstance(v, dict):
                sanitized[str(k)] = cls._sanitize_dict_for_json(v)
            else:
                sanitized[str(k)] = v
        return sanitized

    @classmethod
    def _sanitize_param_value(cls, val: Any) -> Any:
        """
        Sanitizes a property value for Neo4j.
        Neo4j properties must be primitive types (str, int, float, bool) or lists of primitives.
        Complex dictionaries or lists of dictionaries are serialized to JSON strings.
        """
        if isinstance(val, (set, tuple)):
            val = list(val)
        if isinstance(val, list):
            # Check if list contains complex objects (e.g. dicts like citation objects)
            if any(isinstance(x, (dict, list, set, tuple)) for x in val):
                try:
                    return json.dumps([cls._sanitize_dict_for_json(x) if isinstance(x, dict) else x for x in val])
                except Exception:
                    return [str(x) for x in val]
            # List of primitives
            return [x for x in val if x is not None]
        if isinstance(val, dict):
            try:
                return json.dumps(cls._sanitize_dict_for_json(val))
            except Exception:
                return str(val)
        return val

    @classmethod
    def _clean_neo4j_params(cls, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not params:
            return {}
        clean = {}
        for k, v in params.items():
            if str(k).startswith("_"):
                continue
            clean[k] = cls._sanitize_param_value(v)
        return clean

    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a Cypher query against Neo4j or falls back to in-memory graph store."""
        params = params or {}
        if not self.driver:
            self._setup_db()
        if self.driver:
            try:
                with self.driver.session() as session:
                    clean_params = self._clean_neo4j_params(params)
                    result = session.run(query, clean_params)
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
                label_matches = re.findall(r":([a-zA-Z0-9_]+)", query.split("WHERE")[0].split("RETURN")[0])
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

    def clear_cache(self) -> None:
        """Clears in-memory GraphRAG subgraph context cache."""
        if hasattr(self, "_graphrag_cache"):
            self._graphrag_cache.clear()

    def sync_biological_graph(self, bio_graph: Any) -> Dict[str, int]:
        """
        Synchronizes all nodes and edges from a BiologicalGraph or NetworkX DiGraph
        into Neo4j and the fallback graph storage with complete scientific fidelity.
        Uses multi-label node indexing (e.g., :EntityNode:CompoundNode) and typed relationships.
        """
        self.clear_cache()
        nx_graph = getattr(bio_graph, "graph", bio_graph)
        nodes_synced = 0
        edges_synced = 0
        
        # We will batch the nodes by type and execute them in UNWIND blocks.
        node_batches = {
            "CompoundNode": [],
            "TargetNode": [],
            "PathwayNode": [],
            "PhysiologyNode": [],
            "BiomarkerNode": [],
            "PhenotypeNode": [],
            "CitationNode": [],
            "ClinicalTrialNode": [],
            "EvidenceClaimNode": [],
            "EntityNode": [] # fallback
        }

        # 1. Sync Nodes with multi-label support and deep scientific attributes
        for node_id, attrs in nx_graph.nodes(data=True):
            nid = str(node_id)
            nt = str(attrs.get("node_type", "entity")).lower()
            label = str(attrs.get("label") or nid)

            labels = {"EntityNode"}
            node_props = {
                "id": nid,
                "label": label,
                "node_type": nt,
                "category": str(attrs.get("category") or ""),
                "description": str(attrs.get("description") or ""),
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
                node_batches["CompoundNode"].append(node_props)

            elif nt in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
                labels.add("TargetNode")
                node_props.update({
                    "family": str(attrs.get("family") or attrs.get("receptor_family") or attrs.get("enzyme_family") or attrs.get("transporter_family") or ""),
                    "uniprot_id": str(attrs.get("uniprot_id") or ""),
                    "gene_symbol": str(attrs.get("gene_symbol") or ""),
                    "subcellular_location": str(attrs.get("subcellular_location") or ""),
                    "direction": str(attrs.get("direction") or ""),
                    "is_microbial": bool(attrs.get("is_microbial", False)),
                    "microbial_source": str(attrs.get("microbial_source") or ""),
                })
                node_batches["TargetNode"].append(node_props)

            elif nt in ("signaling_pathway", "reaction", "pathway"):
                labels.add("PathwayNode")
                node_props.update({
                    "database": str(attrs.get("pathway_database") or "Reactome"),
                    "pathway_id": str(attrs.get("pathway_id") or ""),
                    "pathway_category": str(attrs.get("pathway_category") or ""),
                })
                node_batches["PathwayNode"].append(node_props)

            elif nt in ("physiology", "organ_system"):
                labels.add("PhysiologyNode")
                node_props.update({
                    "organ_system": str(attrs.get("organ_system") or "Systemic"),
                    "physiological_function": str(attrs.get("physiological_function") or ""),
                    "tissue_specificity": str(attrs.get("tissue_specificity") or ""),
                })
                node_batches["PhysiologyNode"].append(node_props)

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
                node_batches["BiomarkerNode"].append(node_props)

            elif nt in ("phenotype", "outcome", "toxicity", "benefit"):
                labels.add("PhenotypeNode")
                node_props.update({
                    "category": str(attrs.get("phenotype_category") or ""),
                    "severity": str(attrs.get("severity") or ""),
                    "clinical_evidence_level": str(attrs.get("clinical_evidence_level") or "established"),
                    "mesh_id": str(attrs.get("mesh_id") or ""),
                })
                node_batches["PhenotypeNode"].append(node_props)

            elif nt in ("citation", "study", "paper"):
                labels.add("CitationNode")
                raw_pmid = str(attrs.get("pmid") or "").strip()
                raw_doi = str(attrs.get("doi") or "").strip()
                node_props.update({
                    "pmid": raw_pmid if raw_pmid else None,
                    "doi": raw_doi if raw_doi else None,
                    "title": str(attrs.get("title") or label),
                    "authors": list(attrs.get("authors") or []),
                    "journal": str(attrs.get("journal") or ""),
                    "pub_year": int(attrs.get("pub_year") or 0) if attrs.get("pub_year") else None,
                    "pub_date": str(attrs.get("pub_date") or ""),
                    "evidence_tier": str(attrs.get("evidence_tier") or "clinical_trial"),
                    "sample_size": int(attrs.get("sample_size") or 0) if attrs.get("sample_size") else None,
                    "study_design": str(attrs.get("study_design") or ""),
                    "key_findings": str(attrs.get("key_findings") or ""),
                    "conflict_count": int(attrs.get("conflict_count") or 0),
                    "url": str(attrs.get("url") or ""),
                })
                node_batches["CitationNode"].append(node_props)

            elif nt in ("clinical_trial", "trial"):
                labels.add("ClinicalTrialNode")
                node_props.update({
                    "nct_id": str(attrs.get("nct_id") or nid),
                    "title": str(attrs.get("title") or label),
                    "phase": str(attrs.get("phase") or "Phase II/III"),
                    "status": str(attrs.get("status") or "COMPLETED"),
                    "sponsor": str(attrs.get("sponsor") or ""),
                    "enrollment": int(attrs.get("enrollment") or 0) if attrs.get("enrollment") else None,
                    "conditions": list(attrs.get("conditions") or []),
                    "interventions": list(attrs.get("interventions") or []),
                    "primary_outcomes": list(attrs.get("primary_outcomes") or []),
                    "start_year": int(attrs.get("start_year") or 0) if attrs.get("start_year") else None,
                    "completion_year": int(attrs.get("completion_year") or 0) if attrs.get("completion_year") else None,
                    "url": str(attrs.get("url") or ""),
                })
                node_batches["ClinicalTrialNode"].append(node_props)

            elif nt in ("evidence_claim", "claim"):
                labels.add("EvidenceClaimNode")
                node_props.update({
                    "claim_type": str(attrs.get("claim_type") or "pharmacological_effect"),
                    "subject_id": str(attrs.get("subject_id") or ""),
                    "predicate": str(attrs.get("predicate") or "MODULATES"),
                    "object_id": str(attrs.get("object_id") or ""),
                    "magnitude_value": float(attrs.get("magnitude_value")) if attrs.get("magnitude_value") is not None else None,
                    "magnitude_unit": str(attrs.get("magnitude_unit") or ""),
                    "direction": str(attrs.get("direction") or "neutral"),
                    "consensus_score": float(attrs.get("consensus_score") or 1.0),
                    "dispute_status": str(attrs.get("dispute_status") or "consensus"),
                    "contradiction_index": float(attrs.get("contradiction_index") or 0.0),
                    "discovery_year": int(attrs.get("discovery_year") or 0) if attrs.get("discovery_year") else None,
                    "last_validated_year": int(attrs.get("last_validated_year") or 0) if attrs.get("last_validated_year") else None,
                    "conflicting_pmids": list(attrs.get("conflicting_pmids") or []),
                })
                node_batches["EvidenceClaimNode"].append(node_props)

            else:
                node_batches["EntityNode"].append(node_props)

            mem_props = dict(node_props)
            mem_props["_labels"] = labels
            self._mock_nodes[nid] = mem_props
            nodes_synced += 1

        if self.driver:
            try:
                with self.driver.session() as session:
                    for lbl, batch in node_batches.items():
                        if not batch: continue
                        clean_batch = [self._clean_neo4j_params(row) for row in batch]
                        q = f"""
                        UNWIND $batch AS row
                        MERGE (c:EntityNode {{id: row.id}})
                        SET c:{lbl}
                        SET c += row
                        """
                        session.run(q, {"batch": clean_batch})
            except Exception as e:
                logger.error(f"Error during node batching: {e}")

        # 2. Sync Edges
        edge_batches = {}
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
            citations = list(attrs.get("citations") or [])
            disc_year = int(attrs.get("discovery_year")) if attrs.get("discovery_year") else None
            late_year = int(attrs.get("latest_study_year")) if attrs.get("latest_study_year") else None
            is_conflict = bool(attrs.get("conflict_flag") or False)
            consensus_sc = float(attrs.get("consensus_score")) if attrs.get("consensus_score") is not None else 1.0
            contra_idx = float(attrs.get("contradiction_index")) if attrs.get("contradiction_index") is not None else 0.0
            conf_pmids = list(attrs.get("conflicting_pmids") or [])
            div_rat = str(attrs.get("divergence_rationale") or "")
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
                "citations": citations,
                "discovery_year": disc_year,
                "latest_study_year": late_year,
                "conflict_flag": is_conflict,
                "consensus_score": consensus_sc,
                "contradiction_index": contra_idx,
                "conflicting_pmids": conf_pmids,
                "divergence_rationale": div_rat,
                "is_bridge": is_bridge,
                "mechanism_notes": mech_notes,
            }
            self._mock_edges.append(edge_props)
            
            clean_rel_type = re.sub(r"[^A-Za-z0-9_]", "_", edge_type.upper()) or "RELATIONSHIP"
            if clean_rel_type not in edge_batches:
                edge_batches[clean_rel_type] = []
            edge_batches[clean_rel_type].append(edge_props)
            edges_synced += 1
            
        if self.driver:
            try:
                with self.driver.session() as session:
                    # Run generic RELATIONSHIP batch
                    all_edges = []
                    for batch in edge_batches.values():
                        all_edges.extend(batch)
                    
                    if all_edges:
                        clean_batch = [self._clean_neo4j_params(row) for row in all_edges]
                        q = """
                        UNWIND $batch AS row
                        MATCH (a:EntityNode {id: row.source}), (b:EntityNode {id: row.target})
                        MERGE (a)-[r:RELATIONSHIP {edge_type: row.edge_type}]->(b)
                        SET r += row
                        """
                        session.run(q, {"batch": clean_batch})
                        
                    # Run specific relation type batches
                    for rel_type, batch in edge_batches.items():
                        if rel_type == "RELATIONSHIP": continue
                        clean_batch = [self._clean_neo4j_params(row) for row in batch]
                        q = f"""
                        UNWIND $batch AS row
                        MATCH (a:EntityNode {{id: row.source}}), (b:EntityNode {{id: row.target}})
                        MERGE (a)-[r:{rel_type} {{edge_type: row.edge_type}}]->(b)
                        SET r += row
                        """
                        session.run(q, {"batch": clean_batch})
            except Exception as e:
                logger.error(f"Error during edge batching: {e}")

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
            except Exception as e:
                import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)

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
        Sorts branches by biological potency (binding affinity Ki, IC50, magnitude) so highest-signal paths rank first.
        Uses indexed edge lookup and branch pruning for optimal retrieval performance.
        """
        chains: List[List[Dict[str, Any]]] = []

        # Index mock edges by source ID for O(1) traversal
        outgoing_map: Dict[str, List[Dict[str, Any]]] = {}
        for e in self._mock_edges:
            src = str(e.get("source", ""))
            if src:
                outgoing_map.setdefault(src, []).append(e)

        def _edge_potency(e: Dict[str, Any]) -> float:
            ki = e.get("ki") if e.get("ki") is not None else e.get("affinity_ki")
            ic50 = e.get("ic50") if e.get("ic50") is not None else e.get("inhibition_ic50")
            mag = float(e.get("magnitude") or e.get("vector_magnitude") or 1.0)
            score = abs(mag)
            if ki is not None and float(ki) > 0:
                score += max(0.0, 10.0 - math.log10(max(0.001, float(ki))))
            elif ic50 is not None and float(ic50) > 0:
                score += max(0.0, 8.0 - math.log10(max(0.001, float(ic50))))
            return score

        # Pre-sort outgoing edge lists by potency
        for src, edge_list in outgoing_map.items():
            edge_list.sort(key=_edge_potency, reverse=True)

        seen_chain_signatures: Set[Tuple[str, ...]] = set()

        def dfs(current_id: str, path: List[Dict[str, Any]], visited: Set[str], depth: int) -> None:
            if len(chains) >= 25:
                return
            if depth >= max_depth:
                if len(path) > 1:
                    sig = tuple(step["target"] for step in path)
                    if sig not in seen_chain_signatures:
                        seen_chain_signatures.add(sig)
                        chains.append(list(path))
                return

            outgoing = outgoing_map.get(current_id, [])
            if not outgoing:
                if len(path) > 1:
                    sig = tuple(step["target"] for step in path)
                    if sig not in seen_chain_signatures:
                        seen_chain_signatures.add(sig)
                        chains.append(list(path))
                return

            has_children = False
            for edge in outgoing:
                if len(chains) >= 25:
                    return
                tgt = str(edge["target"])
                if tgt in visited:
                    continue
                tgt_node = self._mock_nodes.get(tgt, {"id": tgt, "label": tgt, "node_type": "entity"})
                step = {
                    "source": current_id,
                    "target": tgt,
                    "target_label": tgt_node.get("label", tgt),
                    "target_type": tgt_node.get("node_type", "entity"),
                    "relationship": edge.get("edge_type") or edge.get("type") or "MODULATES",
                    "magnitude": edge.get("magnitude") or edge.get("vector_magnitude") or 1.0,
                    "affinity_ki": edge.get("ki") if edge.get("ki") is not None else edge.get("affinity_ki"),
                    "inhibition_ic50": edge.get("ic50") if edge.get("ic50") is not None else edge.get("inhibition_ic50"),
                }
                visited.add(tgt)
                has_children = True
                dfs(tgt, path + [step], visited, depth + 1)
                visited.remove(tgt)

            if not has_children and len(path) > 1:
                sig = tuple(step["target"] for step in path)
                if sig not in seen_chain_signatures:
                    seen_chain_signatures.add(sig)
                    chains.append(list(path))

        for start_id in start_node_ids:
            if len(chains) >= 25:
                break
            sid = str(start_id).strip()
            if sid in self._mock_nodes or sid in outgoing_map:
                s_node = self._mock_nodes.get(sid, {"id": sid, "label": sid, "node_type": "compound"})
                root_step = {"source": "ROOT", "target": sid, "target_label": s_node.get("label", sid), "target_type": s_node.get("node_type", "compound")}
                dfs(sid, [root_step], {sid}, 0)

        # Sort extracted causal chains by cumulative path potency
        def _chain_potency(chain: List[Dict[str, Any]]) -> float:
            score = 0.0
            for step in chain:
                if step.get("source") == "ROOT":
                    continue
                ki = step.get("affinity_ki")
                ic50 = step.get("inhibition_ic50")
                mag = abs(float(step.get("magnitude", 1.0)))
                score += mag
                if ki is not None and float(ki) > 0:
                    score += max(0.0, 10.0 - math.log10(max(0.001, float(ki))))
                elif ic50 is not None and float(ic50) > 0:
                    score += max(0.0, 8.0 - math.log10(max(0.001, float(ic50))))
            return score

        chains.sort(key=_chain_potency, reverse=True)
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
        Utilizes LRU in-memory caching and vectorized Cypher execution for high-throughput responses.
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

        cache_key = (
            tuple(sorted(clean_ids)),
            max_hops,
            include_pkpd,
            include_kinetics,
            include_causal_chains,
        )
        if hasattr(self, "_graphrag_cache") and cache_key in self._graphrag_cache:
            return copy.deepcopy(self._graphrag_cache[cache_key])

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

        from app.services.catalog_service import CatalogService
        catalog = CatalogService()

        # Dynamically build and synchronize biological graph for queried entities if missing
        missing_nodes = [eid for eid in clean_ids if eid not in self._mock_nodes]
        if missing_nodes or not self._mock_edges:
            try:
                from app.services.graph_service import build_selected_compound_graph
                bio_subgraph = build_selected_compound_graph(clean_ids, catalog_service=catalog)
                if bio_subgraph and getattr(bio_subgraph, "graph", None):
                    self.sync_biological_graph(bio_subgraph)
            except Exception as sync_err:
                logger.debug("Dynamic subgraph sync notice: %s", sync_err)

        # Batch query live Neo4j driver if available
        batch_rels_by_id: Dict[str, List[Dict[str, Any]]] = {}
        if self.driver:
            q_rel_batch = """
            UNWIND $entity_ids AS eid
            MATCH (a:EntityNode {id: eid})-[r:RELATIONSHIP]->(b:EntityNode)
            RETURN a.id AS source, a.label AS source_label, a.node_type AS source_type,
                   r.edge_type AS relationship, r.magnitude AS magnitude,
                   r.affinity_ki AS affinity_ki, r.inhibition_ic50 AS inhibition_ic50,
                   r.ec50 AS ec50, r.inhibition_type AS inhibition_type,
                   r.evidence_level AS evidence_level, r.mechanism_notes AS mechanism_notes,
                   b.id AS target, b.label AS target_label, b.node_type AS target_type
            """
            try:
                all_batch_rels = self.execute_cypher(q_rel_batch, {"entity_ids": clean_ids})
                for r in all_batch_rels:
                    s_id = str(r.get("source"))
                    batch_rels_by_id.setdefault(s_id, []).append(r)
            except Exception as batch_err:
                logger.debug("Batch Cypher UNWIND query notice: %s", batch_err)

        # 1. Discover entities and 1-2 hop relationships
        for eid in clean_ids:
            # Query authoritative catalog record for exact clinical PK/PD
            comp_data = catalog.get_compound(eid, auto_enrich=False) or catalog.find_by_synonym(eid)

            if eid in self._mock_nodes:
                n_info = _clean_node_data(self._mock_nodes[eid])
                entities_found[eid] = n_info
            elif comp_data:
                entities_found[eid] = {
                    "id": eid,
                    "label": comp_data.get("name") or comp_data.get("canonical_name") or eid,
                    "node_type": "compound",
                    "category": comp_data.get("drug_class") or "Pharmacological Agent",
                }

            if include_pkpd:
                if comp_data:
                    c_name = comp_data.get("name") or comp_data.get("canonical_name") or eid
                    t_half = comp_data.get("t_half_numeric") or comp_data.get("half_life_hours")
                    if t_half is None and comp_data.get("half_life"):
                        hl_str = str(comp_data.get("half_life"))
                        m_paren = re.search(r"\((\d+(?:\.\d+)?)\s*hours?\)", hl_str, re.IGNORECASE)
                        if m_paren:
                            t_half = float(m_paren.group(1))
                        else:
                            m_num = re.search(r"(\d+(?:\.\d+)?)", hl_str)
                            if m_num:
                                t_half = float(m_num.group(1))

                    f_val = comp_data.get("bioavailability_f")
                    if f_val is None:
                        f_val = comp_data.get("oral_bioavailability")
                    f_pct = round(float(f_val) * 100.0, 1) if f_val is not None else None

                    vd = comp_data.get("volume_of_distribution_l_kg") or comp_data.get("volume_of_distribution")
                    pb = comp_data.get("protein_binding_pct") or comp_data.get("protein_binding")
                    fe = comp_data.get("renal_clearance_fraction")
                    fh = comp_data.get("hepatic_clearance_fraction")
                    if fe is not None and fh is None:
                        try:
                            fh = round(1.0 - float(fe), 2)
                        except (ValueError, TypeError):
                            pass

                    cyps = comp_data.get("cyp_enzymes") or {}
                    if isinstance(cyps, str):
                        try:
                            import json
                            cyps = json.loads(cyps)
                        except Exception:
                            cyps = {}

                    route_admin = comp_data.get("route_of_administration") or comp_data.get("default_route") or comp_data.get("route")
                    is_ester = bool(comp_data.get("is_ester"))
                    ester_name = comp_data.get("ester_name")

                    pkpd_matrix[eid] = {
                        "name": c_name,
                        "smiles": comp_data.get("smiles"),
                        "inchikey": comp_data.get("inchikey"),
                        "drug_class": comp_data.get("drug_class"),
                        "half_life_hours": t_half,
                        "oral_bioavailability_pct": f_pct,
                        "route_of_administration": route_admin,
                        "is_ester": is_ester,
                        "ester_name": ester_name,
                        "volume_of_distribution_L_kg": vd,
                        "protein_binding_pct": pb,
                        "renal_clearance_fraction": fe,
                        "hepatic_clearance_fraction": fh,
                        "is_narrow_therapeutic_index": comp_data.get("is_narrow_therapeutic_index", False),
                        "cyp_substrates": cyps.get("substrates", []),
                        "cyp_inhibitors": cyps.get("inhibitors", []),
                        "cyp_inducers": cyps.get("inducers", []),
                    }
                elif eid in self._mock_nodes and self._mock_nodes[eid].get("node_type") == "compound":
                    n_info = entities_found[eid]
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
            rels = batch_rels_by_id.get(eid)
            if rels is None and self.driver:
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
                rels = []
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

        # 3b. Extract Literature Co-occurrences & Curated Associations
        literature_cooccurrences: List[Dict[str, Any]] = []
        curated_associations: List[Dict[str, Any]] = []
        seen_lit_pairs = set()

        for edge in self._mock_edges:
            e_type = edge.get("edge_type") or edge.get("type")
            src = str(edge.get("source", ""))
            tgt = str(edge.get("target", ""))
            if src in clean_ids or tgt in clean_ids:
                pair_key = tuple(sorted([src, tgt]))
                if e_type == "LITERATURE_COOCCURRENCE":
                    if pair_key not in seen_lit_pairs:
                        seen_lit_pairs.add(pair_key)
                        src_label = self._mock_nodes.get(src, {}).get("label", src)
                        tgt_label = self._mock_nodes.get(tgt, {}).get("label", tgt)
                        literature_cooccurrences.append({
                            "source": src,
                            "source_label": src_label,
                            "target": tgt,
                            "target_label": tgt_label,
                            "cooccurrence_count": edge.get("cooccurrence_count", 0),
                            "pmi_score": edge.get("pmi_score", 0.0),
                            "npmi_score": edge.get("npmi_score", 0.0),
                            "confidence": edge.get("confidence", 0.0),
                            "pmids": edge.get("sample_pmids", []) or edge.get("pmids", []),
                            "source_db": edge.get("source_db", "PubMed_PMI"),
                        })
                elif e_type == "CURATED_ASSOCIATION":
                    src_label = self._mock_nodes.get(src, {}).get("label", src)
                    tgt_label = self._mock_nodes.get(tgt, {}).get("label", tgt)
                    curated_associations.append({
                        "source": src,
                        "source_label": src_label,
                        "target": tgt,
                        "target_label": tgt_label,
                        "confidence": edge.get("confidence", 0.8),
                        "evidence_level": edge.get("evidence_level", "curated_database"),
                        "source_db": edge.get("source_db", "CTD/STITCH"),
                        "description": edge.get("description", ""),
                        "pmids": edge.get("pmids", []),
                    })

        # 4. Construct Structured Prompt Context for LLM
        prompt_sections = [
            "# SCIENTIFIC KNOWLEDGE GRAPH CONTEXT (GRAPHRAG GROUNDING)",
            "> Use the authoritative biological pathways, pharmacokinetic parameters, literature co-occurrences, and causal chains below to ground your clinical and pharmacological reasoning. Do not invent ungrounded mechanisms.",
            "",
            f"## 1. Focused Entities ({len(entities_found)} nodes)",
        ]
        for e in list(entities_found.values())[:20]:
            prompt_sections.append(f"- **{e.get('label')}** ({e.get('node_type')}) | Category: {e.get('category', 'General')}")

        if pkpd_matrix:
            prompt_sections.append("\n## 2. Pharmacokinetic & Clearance Profiles")
            for cid, pk in pkpd_matrix.items():
                route_str = f" | Route: {pk.get('route_of_administration')}" if pk.get("route_of_administration") else ""
                ester_str = f" | Ester: {pk.get('ester_name')}" if pk.get("is_ester") and pk.get("ester_name") else ""
                prompt_sections.append(
                    f"- **{pk['name']}**{route_str}{ester_str}: t1/2 = {pk.get('half_life_hours', 'N/A')}h, "
                    f"Bioavailability = {pk.get('oral_bioavailability_pct', 'N/A')}%, "
                    f"Vd = {pk.get('volume_of_distribution_L_kg', 'N/A')} L/kg, "
                    f"Renal (fe) = {pk.get('renal_clearance_fraction', 'N/A')}, "
                    f"Hepatic (fh) = {pk.get('hepatic_clearance_fraction', 'N/A')}"
                )
                if pk.get("cyp_inhibitors"):
                    prompt_sections.append(f"  * CYP Inhibition: {', '.join(pk['cyp_inhibitors'])}")
                if pk.get("cyp_substrates"):
                    prompt_sections.append(f"  * CYP Substrate: {', '.join(pk['cyp_substrates'])}")

        # 3c. Extract Conflicting Results & Scientific Controversies
        conflicts_found: List[Dict[str, Any]] = []
        seen_conflicts = set()
        for edge in self._mock_edges:
            if edge.get("conflict_flag") or (edge.get("consensus_score") is not None and float(edge.get("consensus_score", 1.0)) < 0.85):
                src = str(edge.get("source", ""))
                tgt = str(edge.get("target", ""))
                if src in clean_ids or tgt in clean_ids:
                    ckey = tuple(sorted([src, tgt, str(edge.get("edge_type", ""))]))
                    if ckey not in seen_conflicts:
                        seen_conflicts.add(ckey)
                        src_label = self._mock_nodes.get(src, {}).get("label", src)
                        tgt_label = self._mock_nodes.get(tgt, {}).get("label", tgt)
                        conflicts_found.append({
                            "source": src,
                            "source_label": src_label,
                            "target": tgt,
                            "target_label": tgt_label,
                            "edge_type": edge.get("edge_type", "MODULATES"),
                            "consensus_score": edge.get("consensus_score", 0.5),
                            "contradiction_index": edge.get("contradiction_index", 0.5),
                            "conflicting_pmids": edge.get("conflicting_pmids", []),
                            "divergence_rationale": edge.get("divergence_rationale", "Divergence in published preclinical vs clinical trials"),
                            "supporting_pmids": edge.get("pmids", []),
                        })

        # 3d. Extract Chronological Evidence Milestones
        evidence_timelines: Dict[str, List[Dict[str, Any]]] = {}
        for eid in clean_ids:
            tl = self.get_chronological_evidence_timeline(eid)
            if tl:
                evidence_timelines[eid] = tl

        # 4. Construct Structured Prompt Context for LLM
        prompt_sections = [
            "# SCIENTIFIC KNOWLEDGE GRAPH CONTEXT (GRAPHRAG GROUNDING)",
            "> Use the authoritative biological pathways, pharmacokinetic parameters, literature co-occurrences, chronological timelines, and causal chains below to ground your clinical and pharmacological reasoning. Do not invent ungrounded mechanisms.",
            "",
            f"## 1. Focused Entities ({len(entities_found)} nodes)",
        ]
        for e in list(entities_found.values())[:20]:
            prompt_sections.append(f"- **{e.get('label')}** ({e.get('node_type')}) | Category: {e.get('category', 'General')}")

        if pkpd_matrix:
            prompt_sections.append("\n## 2. Pharmacokinetic & Clearance Profiles")
            for cid, pk in pkpd_matrix.items():
                route_str = f" | Route: {pk.get('route_of_administration')}" if pk.get("route_of_administration") else ""
                ester_str = f" | Ester: {pk.get('ester_name')}" if pk.get("is_ester") and pk.get("ester_name") else ""
                prompt_sections.append(
                    f"- **{pk['name']}**{route_str}{ester_str}: t1/2 = {pk.get('half_life_hours', 'N/A')}h, "
                    f"Bioavailability = {pk.get('oral_bioavailability_pct', 'N/A')}%, "
                    f"Vd = {pk.get('volume_of_distribution_L_kg', 'N/A')} L/kg, "
                    f"Renal (fe) = {pk.get('renal_clearance_fraction', 'N/A')}, "
                    f"Hepatic (fh) = {pk.get('hepatic_clearance_fraction', 'N/A')}"
                )
                if pk.get("cyp_inhibitors"):
                    prompt_sections.append(f"  * CYP Inhibition: {', '.join(pk['cyp_inhibitors'])}")
                if pk.get("cyp_substrates"):
                    prompt_sections.append(f"  * CYP Substrate: {', '.join(pk['cyp_substrates'])}")

        if conflicts_found:
            prompt_sections.append("\n## 3. Scientific Controversies & Conflicting Evidence (Explicitly Account for Divergence)")
            for cf in conflicts_found[:8]:
                opp_pmid_str = f" [Opposing PMIDs: {', '.join(str(p) for p in cf['conflicting_pmids'][:3])}]" if cf.get("conflicting_pmids") else ""
                sup_pmid_str = f" [Supporting PMIDs: {', '.join(str(p) for p in cf['supporting_pmids'][:3])}]" if cf.get("supporting_pmids") else ""
                prompt_sections.append(
                    f"- ⚠️ **{cf['source_label']}** ➔ **{cf['target_label']}** ({cf['edge_type']}): Consensus {cf['consensus_score']*100:.0f}% (Contradiction Index: {cf['contradiction_index']:.2f}). "
                    f"*Rationale*: {cf['divergence_rationale']}.{sup_pmid_str}{opp_pmid_str}"
                )

        if evidence_timelines:
            prompt_sections.append("\n## 4. Chronological Evidence Evolution & Discovery Milestones")
            for cid, milestones in list(evidence_timelines.items())[:4]:
                c_lbl = entities_found.get(cid, {}).get("label", cid)
                m_strs = [f"{m.get('year', 'N/A')}: {m.get('milestone', '')} [{m.get('tier', 'study')}]" for m in milestones[:4]]
                prompt_sections.append(f"- **{c_lbl} Evolution**: {' ➔ '.join(m_strs)}")

        if literature_cooccurrences:
            prompt_sections.append("\n## 5. Empirical Literature Co-occurrences & Pairing Evidence")
            for lit in sorted(literature_cooccurrences, key=lambda x: x.get("npmi_score", 0), reverse=True)[:10]:
                pmid_str = f" [PMIDs: {', '.join(str(p) for p in lit['pmids'][:3])}]" if lit.get("pmids") else ""
                prompt_sections.append(
                    f"- **{lit['source_label']}** ↔ **{lit['target_label']}**: "
                    f"{lit.get('cooccurrence_count', 0)} PubMed papers (NPMI: {lit.get('npmi_score', 0.0):.2f}, Conf: {lit.get('confidence', 0.0):.2f}){pmid_str}"
                )

        if curated_associations:
            prompt_sections.append("\n## 6. Curated Database Associations (STITCH / CTD / DrugBank)")
            for cur in curated_associations[:10]:
                pmid_str = f" [PMIDs: {', '.join(str(p) for p in cur['pmids'][:3])}]" if cur.get("pmids") else ""
                desc_str = f" - {cur['description']}" if cur.get("description") else ""
                prompt_sections.append(
                    f"- **{cur['source_label']}** ➔ **{cur['target_label']}** ({cur.get('source_db')}, Conf: {cur.get('confidence', 0.8):.2f}){desc_str}{pmid_str}"
                )

        if target_competition:
            prompt_sections.append("\n## 7. Competitive Target Clashes & Cross-Talk")
            for tc in target_competition:
                prompt_sections.append(f"- **{tc['target']}**: Competitively engaged by {', '.join(tc['competing_compounds'])}")

        prompt_sections.append(f"\n## 8. Authoritative Biological Triples ({min(len(triples), 40)} shown)")
        for t in triples[:40]:
            affinity_str = f" [Ki: {t['affinity_ki']} nM]" if t.get("affinity_ki") else ""
            ic50_str = f" [IC50: {t['inhibition_ic50']} nM]" if t.get("inhibition_ic50") else ""
            prompt_sections.append(f"- [{t['subject']}] --({t['predicate']}{affinity_str}{ic50_str})--> [{t['object']}] ({t['object_type']})")

        if causal_chains:
            prompt_sections.append("\n## 9. Multi-Tier Causal Reasoning Chains")
            for i, chain in enumerate(causal_chains[:8], 1):
                steps_str = " ➔ ".join([f"{c['target_label']} ({c['target_type']})" for c in chain])
                prompt_sections.append(f"{i}. {steps_str}")

        if biomarker_kinetics:
            prompt_sections.append("\n## 10. Biomarker Kinetic Calibrations")
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
        summary_lines.append(f"- Literature Co-occurrences: {len(literature_cooccurrences)} empirical pairings")
        summary_lines.append(f"- Curated Associations: {len(curated_associations)} database interactions")
        summary_lines.append(f"- Causal Chains: {len(causal_chains)} complete multi-tier pathways")
        if conflicts_found:
            summary_lines.append(f"- Scientific Controversies: {len(conflicts_found)} disputed claims mapped")
        if target_competition:
            summary_lines.append(f"- Target Clashes: {len(target_competition)} shared target interactions")

        res = {
            "focused_ids": clean_ids,
            "entities": list(entities_found.values()),
            "triples": triples,
            "triple_count": len(triples),
            "literature_cooccurrences": literature_cooccurrences,
            "curated_associations": curated_associations,
            "conflicts": conflicts_found,
            "evidence_timelines": evidence_timelines,
            "causal_chains": causal_chains[:15],
            "pkpd_matrix": pkpd_matrix,
            "target_competition": target_competition,
            "biomarker_kinetics": biomarker_kinetics,
            "text_summary": "\n".join(summary_lines),
            "formatted_prompt_context": formatted_context,
        }

        if hasattr(self, "_graphrag_cache"):
            if len(self._graphrag_cache) >= 128:
                try:
                    self._graphrag_cache.pop(next(iter(self._graphrag_cache)))
                except Exception as e:
                    import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)
            self._graphrag_cache[cache_key] = copy.deepcopy(res)

        return res

    def get_chronological_evidence_timeline(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the chronological progression of scientific evidence and discovery milestones
        for a given entity, sorted from earliest to latest publication year.
        """
        eid = str(entity_id).strip().lower()
        if not eid:
            return []

        milestones: List[Dict[str, Any]] = []
        seen_pmids = set()

        # 1. Inspect direct CitationNodes connected or in mock store
        for nid, nprops in self._mock_nodes.items():
            nt = nprops.get("node_type", "")
            if nt in ("citation", "study") and (eid in nid.lower() or eid in str(nprops.get("title", "")).lower() or eid in str(nprops.get("key_findings", "")).lower()):
                pmid = nprops.get("pmid")
                if pmid and pmid not in seen_pmids:
                    seen_pmids.add(pmid)
                    milestones.append({
                        "id": nid,
                        "pmid": pmid,
                        "doi": nprops.get("doi"),
                        "title": nprops.get("title", ""),
                        "journal": nprops.get("journal", ""),
                        "year": nprops.get("pub_year") or 2020,
                        "tier": nprops.get("evidence_tier", "clinical_trial"),
                        "milestone": nprops.get("key_findings") or nprops.get("title", ""),
                        "sample_size": nprops.get("sample_size"),
                        "url": nprops.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    })

        # 2. Inspect edges with citations or PMIDs connected to this entity
        for edge in self._mock_edges:
            if edge.get("source") == eid or edge.get("target") == eid:
                e_pmids = edge.get("pmids", []) or []
                cites = edge.get("citations", []) or []
                d_year = edge.get("discovery_year") or edge.get("latest_study_year")
                e_type = edge.get("edge_type", "MODULATES")

                for c in cites:
                    c_pmid = c.get("pmid")
                    if c_pmid and c_pmid not in seen_pmids:
                        seen_pmids.add(c_pmid)
                        milestones.append({
                            "id": f"pmid_{c_pmid}",
                            "pmid": c_pmid,
                            "doi": c.get("doi"),
                            "title": c.get("title", f"Interaction study for {eid}"),
                            "journal": c.get("journal", "Biomedical Literature"),
                            "year": c.get("pub_year") or d_year or 2018,
                            "tier": c.get("evidence_tier", "clinical_trial"),
                            "milestone": c.get("key_findings") or f"Characterized {e_type} interaction",
                            "sample_size": c.get("sample_size"),
                            "url": c.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{c_pmid}/",
                        })

                for pmid in e_pmids:
                    pmid_str = str(pmid)
                    if pmid_str and pmid_str not in seen_pmids:
                        seen_pmids.add(pmid_str)
                        milestones.append({
                            "id": f"pmid_{pmid_str}",
                            "pmid": pmid_str,
                            "doi": None,
                            "title": f"Validating study for {edge.get('source')} ➔ {edge.get('target')}",
                            "journal": "Peer-Reviewed Literature",
                            "year": d_year or 2015,
                            "tier": edge.get("evidence_level", "in_vivo"),
                            "milestone": edge.get("mechanism_notes") or f"Validated {e_type} pathway",
                            "sample_size": None,
                            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid_str}/",
                        })

        # 3. Fallback to catalog service seed literature if empty
        if not milestones:
            try:
                from app.services.pubmed_service import SEED_LITERATURE_DB
                seeds = SEED_LITERATURE_DB.get(eid, [])
                for s in seeds:
                    milestones.append({
                        "id": f"pmid_{s['pmid']}",
                        "pmid": s["pmid"],
                        "doi": s.get("doi"),
                        "title": s.get("title", ""),
                        "journal": s.get("journal", ""),
                        "year": int(s.get("pub_year", 2015)),
                        "tier": s.get("evidence_type", "Phase III Landmark RCT"),
                        "milestone": s.get("clinical_finding", s.get("title", "")),
                        "sample_size": s.get("sample_size"),
                        "url": s.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/",
                    })
            except Exception as e:
                import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)

        # Sort chronologically
        milestones.sort(key=lambda m: (m.get("year") or 9999, m.get("tier") or ""))
        return milestones

    def get_conflicting_evidence_subgraph(self, entity_ids: List[str]) -> Dict[str, Any]:
        """
        Extracts disputed edges, opposing PMIDs, and divergent scientific hypotheses
        for the given entity IDs.
        """
        clean_ids = set(str(e).strip().lower() for e in entity_ids if e)
        disputed_edges: List[Dict[str, Any]] = []

        for edge in self._mock_edges:
            src = str(edge.get("source", ""))
            tgt = str(edge.get("target", ""))
            if (not clean_ids) or (src in clean_ids or tgt in clean_ids):
                is_disputed = edge.get("conflict_flag") or (edge.get("consensus_score") is not None and float(edge.get("consensus_score", 1.0)) < 0.85)
                if is_disputed:
                    src_label = self._mock_nodes.get(src, {}).get("label", src)
                    tgt_label = self._mock_nodes.get(tgt, {}).get("label", tgt)
                    disputed_edges.append({
                        "source": src,
                        "source_label": src_label,
                        "target": tgt,
                        "target_label": tgt_label,
                        "edge_type": edge.get("edge_type", "MODULATES"),
                        "consensus_score": edge.get("consensus_score", 0.5),
                        "contradiction_index": edge.get("contradiction_index", 0.5),
                        "conflicting_pmids": edge.get("conflicting_pmids", []),
                        "supporting_pmids": edge.get("pmids", []),
                        "divergence_rationale": edge.get("divergence_rationale", "Conflicting results between in vitro high-dose models and human clinical RCTs"),
                    })

        return {
            "entity_ids": list(clean_ids),
            "disputed_edge_count": len(disputed_edges),
            "disputed_edges": disputed_edges,
        }

    def get_temporal_graph_snapshot(self, as_of_year: int) -> Dict[str, Any]:
        """
        Filters the biological knowledge graph to return only the nodes and edges
        that were published/discovered on or before as_of_year.
        """
        def _sanitize(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {str(k): _sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple, set)):
                return [_sanitize(x) for x in obj]
            elif hasattr(obj, "value"):
                return obj.value
            return obj

        cutoff = int(as_of_year)
        active_nodes: Dict[str, Dict[str, Any]] = {}
        active_edges: List[Dict[str, Any]] = []

        for edge in self._mock_edges:
            d_year = edge.get("discovery_year")
            if d_year is None or int(d_year) <= cutoff:
                active_edges.append(_sanitize(edge))
                src = edge.get("source")
                tgt = edge.get("target")
                if src and src in self._mock_nodes:
                    active_nodes[src] = _sanitize(self._mock_nodes[src])
                if tgt and tgt in self._mock_nodes:
                    active_nodes[tgt] = _sanitize(self._mock_nodes[tgt])

        return {
            "as_of_year": cutoff,
            "node_count": len(active_nodes),
            "edge_count": len(active_edges),
            "nodes": list(active_nodes.values()),
            "edges": active_edges,
        }

    def get_evidence_claims_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all structured assertions (binding affinities, clearance mechanisms,
        interactions, biomarker shifts) associated with a given entity.
        """
        eid = str(entity_id).strip().lower()
        claims: List[Dict[str, Any]] = []

        for nid, node in self._mock_nodes.items():
            if node.get("node_type") in ("evidence_claim", "claim"):
                if node.get("subject_id") == eid or node.get("object_id") == eid:
                    claims.append(node)

        # Generate claims dynamically from active edges if explicit claim nodes not merged
        if not claims:
            for edge in self._mock_edges:
                if edge.get("source") == eid or edge.get("target") == eid:
                    src_lbl = self._mock_nodes.get(edge.get("source", ""), {}).get("label", edge.get("source"))
                    tgt_lbl = self._mock_nodes.get(edge.get("target", ""), {}).get("label", edge.get("target"))
                    claims.append({
                        "id": f"claim_{edge.get('source')}_{edge.get('target')}",
                        "node_type": "evidence_claim",
                        "subject": src_lbl,
                        "predicate": edge.get("edge_type", "MODULATES"),
                        "object": tgt_lbl,
                        "affinity_ki": edge.get("ki"),
                        "inhibition_ic50": edge.get("ic50"),
                        "consensus_score": edge.get("consensus_score", 1.0),
                        "dispute_status": "debated" if edge.get("conflict_flag") else "consensus",
                        "discovery_year": edge.get("discovery_year"),
                        "pmids": edge.get("pmids", []),
                        "conflicting_pmids": edge.get("conflicting_pmids", []),
                    })

        return claims

    def ingest_citation(
        self,
        citation: Dict[str, Any],
        entity_id: Optional[str] = None,
        relationship: str = "SUPPORTED_BY",
    ) -> Dict[str, Any]:
        """
        Dynamically ingests a verified citation into the graph database, connecting it
        to an entity (compound/target/pathway) via a typed relationship edge.
        """
        pmid = str(citation.get("pmid") or "").strip()
        if not pmid and not citation.get("doi"):
            return citation

        cid = f"pmid_{pmid}" if pmid else f"doi_{citation.get('doi')}"
        title = str(citation.get("title") or "").rstrip(".")
        journal = str(citation.get("journal") or "PubMed Literature")
        pub_year_raw = str(citation.get("pub_year") or "")
        pub_year = int(pub_year_raw) if pub_year_raw.isdigit() else 2020
        doi = citation.get("doi")
        authors = list(citation.get("authors") or [])
        evidence_tier = str(citation.get("evidence_tier") or citation.get("evidence_type") or "clinical_trial")
        key_findings = str(citation.get("clinical_finding") or citation.get("key_findings") or title)
        abstract_text = str(citation.get("abstract") or citation.get("abstract_text") or "")
        url = str(citation.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""))
        claim_topics = citation.get("claim_topics") or self._extract_claim_topics(title, key_findings, journal)

        # Compute dense semantic vector embedding for Title + Abstract
        from app.services.embedding_service import get_embedding_service
        emb_svc = get_embedding_service()
        embedding = citation.get("embedding") or emb_svc.embed_citation(title=title, abstract=abstract_text, findings=key_findings)

        node_data = {
            "id": cid,
            "label": title[:60],
            "node_type": "citation",
            "pmid": pmid or None,
            "doi": doi or None,
            "title": title,
            "authors": authors,
            "journal": journal,
            "pub_year": pub_year,
            "pub_date": str(citation.get("pub_date", str(pub_year))),
            "evidence_tier": evidence_tier,
            "sample_size": citation.get("sample_size"),
            "study_design": str(citation.get("evidence_type", "RCT / Observational")),
            "key_findings": key_findings,
            "abstract": abstract_text or key_findings,
            "claim_topics": claim_topics,
            "url": url,
            "embedding": embedding,
        }

        # 1. Update in-memory node store
        self._mock_nodes[cid] = copy.deepcopy(node_data)

        # 2. If entity_id is provided, connect entity -> citation
        if entity_id:
            eid = str(entity_id).strip().lower()
            if eid not in self._mock_nodes:
                self._mock_nodes[eid] = {
                    "id": eid,
                    "label": eid.replace("_", " ").title(),
                    "node_type": "compound",
                }
            
            # Check existing edge
            edge_exists = False
            for edge in self._mock_edges:
                if edge.get("source") == eid and edge.get("target") == cid:
                    edge["discovery_year"] = pub_year
                    edge["mechanism_notes"] = key_findings
                    edge_exists = True
                    break
            if not edge_exists:
                self._mock_edges.append({
                    "source": eid,
                    "target": cid,
                    "edge_type": relationship,
                    "confidence": 0.95,
                    "discovery_year": pub_year,
                    "mechanism_notes": key_findings,
                    "pmids": [pmid] if pmid else [],
                })

        # 3. If Neo4j driver connected, execute Cypher MERGE
        if self.driver:
            try:
                with self.driver.session() as session:
                    cypher = """
                    MERGE (c:EntityNode {id: $id})
                    SET c:CitationNode,
                        c.label = $label,
                        c.node_type = $node_type,
                        c.pmid = $pmid,
                        c.doi = $doi,
                        c.title = $title,
                        c.authors = $authors,
                        c.journal = $journal,
                        c.pub_year = $pub_year,
                        c.pub_date = $pub_date,
                        c.evidence_tier = $evidence_tier,
                        c.sample_size = $sample_size,
                        c.study_design = $study_design,
                        c.key_findings = $key_findings,
                        c.abstract = $abstract,
                        c.claim_topics = $claim_topics,
                        c.url = $url
                    """
                    session.run(cypher, self._clean_neo4j_params(node_data))
                    if entity_id:
                        rel_cypher = f"""
                        MERGE (e:EntityNode {{id: $eid}})
                        MERGE (c:EntityNode {{id: $cid}})
                        SET c:CitationNode
                        MERGE (e)-[r:{relationship}]->(c)
                        SET r.discovery_year = $pub_year, r.notes = $key_findings
                        """
                        session.run(rel_cypher, {"eid": str(entity_id).strip().lower(), "cid": cid, "pub_year": pub_year, "key_findings": key_findings})
            except Exception as e:
                logger.debug("Neo4j citation ingest notice: %s", e)

        return node_data

    def get_citations_for_entity(self, entity_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Queries the citation graph database for all :Citation nodes connected
        to the specified entity.
        """
        eid = str(entity_id).strip().lower()
        if not eid:
            return []

        cites: List[Dict[str, Any]] = []
        seen_pmids: Set[str] = set()

        # 1. Neo4j Cypher query if driver connected
        if self.driver:
            try:
                with self.driver.session() as session:
                    q = """
                    MATCH (e:EntityNode {id: $eid})-[r]-(c:CitationNode)
                    RETURN c.id as id, c.pmid as pmid, c.doi as doi, c.title as title,
                           c.journal as journal, c.pub_year as pub_year, c.evidence_tier as evidence_tier,
                           c.key_findings as key_findings, c.url as url, c.authors as authors
                    ORDER BY c.pub_year DESC
                    LIMIT $limit
                    """
                    res = session.run(q, {"eid": eid, "limit": max_results})
                    for record in res:
                        pmid = record.get("pmid")
                        if pmid and pmid not in seen_pmids:
                            seen_pmids.add(pmid)
                            cites.append(dict(record))
            except Exception as cy_err:
                logger.debug("Neo4j get_citations error: %s", cy_err)

        # 2. In-memory graph traversal
        if not cites:
            target_ids = {eid, eid.replace("_", ""), eid.replace("_", "-"), eid.replace("l_", "")}
            for edge in self._mock_edges:
                s = str(edge.get("source", "")).lower()
                t = str(edge.get("target", "")).lower()
                if s in target_ids or t in target_ids:
                    other_id = edge.get("target") if s in target_ids else edge.get("source")
                    if other_id in self._mock_nodes:
                        node = self._mock_nodes[other_id]
                        if node.get("node_type") in ("citation", "study"):
                            pmid = str(node.get("pmid") or "")
                            if pmid and pmid not in seen_pmids:
                                seen_pmids.add(pmid)
                                cites.append({
                                    "id": node.get("id", f"pmid_{pmid}"),
                                    "pmid": pmid,
                                    "doi": node.get("doi"),
                                    "title": node.get("title", ""),
                                    "journal": node.get("journal", ""),
                                    "pub_year": node.get("pub_year") or 2020,
                                    "authors": node.get("authors", []),
                                    "evidence_tier": node.get("evidence_tier", "clinical_trial"),
                                    "clinical_finding": node.get("key_findings") or edge.get("mechanism_notes", ""),
                                    "url": node.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                })

            for nid, node in self._mock_nodes.items():
                if node.get("node_type") in ("citation", "study"):
                    nid_lower = nid.lower()
                    title_lower = str(node.get("title", "")).lower()
                    if any(tid in nid_lower for tid in target_ids) or (len(eid) >= 4 and eid in title_lower):
                        pmid = str(node.get("pmid") or "")
                        if pmid and pmid not in seen_pmids:
                            seen_pmids.add(pmid)
                            cites.append({
                                "id": nid,
                                "pmid": pmid,
                                "doi": node.get("doi"),
                                "title": node.get("title", ""),
                                "journal": node.get("journal", ""),
                                "pub_year": node.get("pub_year") or 2020,
                                "authors": node.get("authors", []),
                                "evidence_tier": node.get("evidence_tier", "clinical_trial"),
                                "clinical_finding": node.get("key_findings", ""),
                                "url": node.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            })

        cites.sort(key=lambda c: int(c.get("pub_year") or 0), reverse=True)
        return cites[:max_results]

    def search_citations(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Searches the citation graph database for citations matching query keywords across
        titles, key findings, journals, connected entities, or PMIDs.
        """
        cleaned = query.strip().lower()
        if not cleaned:
            return []

        tokens = [t for t in re.split(r"[\s_,\-]+", cleaned) if len(t) >= 3]
        if not tokens:
            tokens = [cleaned]

        matches: List[Tuple[int, Dict[str, Any]]] = []
        seen_pmids: Set[str] = set()

        for nid, node in self._mock_nodes.items():
            if node.get("node_type") in ("citation", "study"):
                pmid = str(node.get("pmid") or "")
                if pmid in seen_pmids:
                    continue
                
                title = str(node.get("title", "")).lower()
                findings = str(node.get("key_findings", "")).lower()
                journal = str(node.get("journal", "")).lower()
                topics = " ".join(node.get("claim_topics", []))
                corpus = f"{nid} {pmid} {title} {findings} {journal} {topics}".lower()
                
                score = sum(1 for t in tokens if t in corpus)
                if tokens and any(t in nid.lower() or t in title for t in tokens):
                    score += 5
                if score > 0:
                    seen_pmids.add(pmid)
                    matches.append((score, {
                        "id": nid,
                        "pmid": pmid,
                        "doi": node.get("doi"),
                        "title": node.get("title", ""),
                        "journal": node.get("journal", ""),
                        "pub_year": node.get("pub_year") or 2020,
                        "authors": node.get("authors", []),
                        "evidence_tier": node.get("evidence_tier", "clinical_trial"),
                        "clinical_finding": node.get("key_findings", ""),
                        "url": node.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    }))

        matches.sort(key=lambda m: (m[0], int(m[1].get("pub_year") or 0)), reverse=True)
        return [m[1] for m in matches[:max_results]]

    @staticmethod
    def _extract_claim_topics(title: str, findings: str, journal: str = "") -> List[str]:
        """Classifies biomedical text into standardized physiological/clinical claim topics."""
        text = f"{title} {findings} {journal}".lower()
        topics = []
        topic_map = {
            "neuroprotection": ["neuroprotect", "brain", "cns", "neuron", "bdnf", "ngf", "hippocamp", "dopamin", "serotonin", "excitotox", "cognitive", "stroke", "memory"],
            "angiogenesis": ["angiogen", "vegf", "endothelial", "vascular", "blood vessel", "capillary", "enos", "nos3", "revascular"],
            "wound_healing": ["wound", "healing", "tissue repair", "granulation", "epithelial"],
            "tendon_ligament": ["tendon", "ligament", "collagen", "achilles", "tenocyte", "connective tissue", "biomechanic"],
            "gastric_mucosa": ["gastric", "ulcer", "mucosa", "gut", "gastroprotect", "ibd", "colitis", "duodenal", "stomach", "nsaid"],
            "fistula_urology": ["fistula", "bladder", "vesicovaginal", "urolog", "stone", "rectovaginal"],
            "cardiovascular": ["blood pressure", "hypertension", "arterial", "cardio", "myocard", "infarct", "heart", "ras", "raas", "acei", "statin", "atheroscler"],
            "pharmacokinetics": ["pharmacokinetic", "bioavailab", "half-life", "clearance", "absorption", "cmax", "auc", "metabol"],
            "metabolic_glycemic": ["glucose", "insulin", "diabetes", "ampk", "glycemic", "hba1c", "metformin", "homa-ir"],
            "lipid_management": ["cholesterol", "ldl", "hdl", "apob", "statin", "triglyceride", "lipid"],
            "oncology": ["cancer", "tumor", "oncolog", "carcinoma", "neoplasm", "cytotox"],
            "antiinflammatory": ["anti-inflammatory", "inflammation", "cytokine", "crp", "tnf", "interleukin", "cox-2"],
            "antioxidant": ["antioxidant", "sod", "glutathione", "reactive oxygen", "ros", "oxidative stress"],
            "anabolic_endocrine": ["testosterone", "androgen", "anabolic", "aromatase", "estradiol", "lh", "fsh", "hpta", "hypertrophy"],
        }
        for topic, keywords in topic_map.items():
            if any(k in text for k in keywords):
                topics.append(topic)
        return topics or ["general_pharmacology"]

    def get_citations_for_claim(
        self,
        entity_id: str,
        claim_topic_or_text: str,
        max_results: int = 3,
        min_semantic_score: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves citations linked to entity_id that specifically support the endpoint,
        mechanism, or disease model asserted in claim_topic_or_text.
        Prevents misattributing an unrelated trial (e.g. fistula repair) to a different claim (e.g. neuroprotection).
        """
        eid = str(entity_id).strip().lower()
        if not eid or not claim_topic_or_text:
            return []

        # 1. Get all candidate citations for this entity
        all_cites = self.get_citations_for_entity(eid, max_results=20)
        if not all_cites:
            try:
                from app.services.pubmed_service import SEED_LITERATURE_DB
                norm_k = eid.replace(" ", "_").replace("-", "_")
                seeds = SEED_LITERATURE_DB.get(norm_k) or SEED_LITERATURE_DB.get(eid) or []
                for s in seeds:
                    self.ingest_citation(s, entity_id=eid)
                all_cites = self.get_citations_for_entity(eid, max_results=20)
            except Exception as e:
                import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)
        if not all_cites:
            all_cites = self.search_citations(f"{eid} {claim_topic_or_text}", max_results=10)

        claim_tokens = [t for t in re.split(r"[\s_,\-]+", claim_topic_or_text.lower()) if len(t) >= 3]
        claim_topics = self._extract_claim_topics(claim_topic_or_text, claim_topic_or_text)

        scored: List[Tuple[int, Dict[str, Any]]] = []
        for c in all_cites:
            title = str(c.get("title", "")).lower()
            findings = str(c.get("clinical_finding") or c.get("key_findings") or "").lower()
            journal = str(c.get("journal", "")).lower()
            c_topics = c.get("claim_topics") or self._extract_claim_topics(title, findings, journal)
            c_corpus = f"{title} {findings} {journal}"

            score = 0
            # Topic overlap bonus
            shared_topics = set(claim_topics).intersection(set(c_topics))
            score += len(shared_topics) * 3

            # Token overlap
            token_matches = sum(1 for t in claim_tokens if t in c_corpus)
            score += token_matches

            if score >= min_semantic_score:
                c_copy = copy.deepcopy(c)
                c_copy["claim_topics"] = c_topics
                c_copy["semantic_score"] = score
                scored.append((score, c_copy))

        scored.sort(key=lambda s: (s[0], int(s[1].get("pub_year") or 0)), reverse=True)
        return [s[1] for s in scored[:max_results]]

    def validate_claim_citation_match(
        self,
        claim_text: str,
        citation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluates semantic congruence between an asserted claim and a candidate citation.
        Detects and flags when a citation investigates an endpoint distinct from the claim.
        """
        claim_cleaned = claim_text.strip().lower()
        title = str(citation.get("title", "")).lower()
        findings = str(citation.get("clinical_finding") or citation.get("key_findings") or "").lower()
        journal = str(citation.get("journal", "")).lower()

        claim_topics = set(self._extract_claim_topics(claim_cleaned, claim_cleaned))
        cite_topics = set(citation.get("claim_topics") or self._extract_claim_topics(title, findings, journal))

        shared_topics = claim_topics.intersection(cite_topics)
        claim_tokens = [t for t in re.split(r"[\s_,\-]+", claim_cleaned) if len(t) >= 4]
        token_hits = [t for t in claim_tokens if t in f"{title} {findings}"]

        is_congruent = bool(shared_topics) or (len(token_hits) >= 2)
        confidence = min(1.0, (len(shared_topics) * 0.4) + (len(token_hits) * 0.2))

        divergence_warning = None
        if not is_congruent and cite_topics and claim_topics:
            divergence_warning = (
                f"Claim addresses [{', '.join(claim_topics)}], whereas citation investigates [{', '.join(cite_topics)}]."
            )

        return {
            "is_congruent": is_congruent,
            "confidence": round(confidence, 2),
            "shared_topics": list(shared_topics),
            "token_hits": token_hits,
            "divergence_warning": divergence_warning,
        }

    def search_hybrid_graph_and_literature(
        self,
        query: str,
        entity_ids: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """
        Unified Hybrid RAG combining relational GraphRAG (knowledge graph triples,
        causal chains, receptor kinetics) with text-based literature retrieval (traditional RAG).
        """
        clean_q = str(query or "").strip()
        e_ids = [str(e).strip().lower() for e in (entity_ids or []) if e]

        # 1. GraphRAG Relational Context
        graph_rag_data = {}
        if e_ids:
            try:
                graph_rag_data = self.get_graphrag_context(
                    entity_ids=e_ids,
                    max_hops=2,
                    include_pkpd=True,
                    include_kinetics=True,
                    include_causal_chains=True,
                )
            except Exception as gr_err:
                logger.debug("GraphRAG retrieval notice: %s", gr_err)

        # 2. Traditional / Semantic Literature Retrieval
        from app.services.pubmed_service import PubMedService
        pubmed_svc = PubMedService()
        lit_res = pubmed_svc.hybrid_literature_search(
            query=clean_q,
            entity_id=e_ids[0] if e_ids else None,
            max_results=max_results,
        )

        return {
            "query": clean_q,
            "entity_ids": e_ids,
            "causal_chains": graph_rag_data.get("causal_chains", []),
            "target_competition": graph_rag_data.get("target_competition", []),
            "pkpd_profiles": graph_rag_data.get("pkpd_matrix", {}),
            "citations_found": lit_res.get("citations", []),
            "citation_count": lit_res.get("count", 0),
            "graph_summary": graph_rag_data.get("text_summary", ""),
        }

    def search_citations_semantic(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """
        Performs dense semantic vector similarity search across all cached citation nodes in the graph.
        Returns top matching citations ranked by cosine similarity.
        """
        clean_q = str(query or "").strip()
        if not clean_q:
            return []

        from app.services.embedding_service import get_embedding_service
        emb_svc = get_embedding_service()

        all_citations: List[Dict[str, Any]] = []
        seen_pmids: Set[str] = set()

        for nid, node in self._mock_nodes.items():
            if node.get("node_type") in ("citation", "study"):
                pmid = str(node.get("pmid") or "")
                if pmid and pmid not in seen_pmids:
                    seen_pmids.add(pmid)
                    all_citations.append(dict(node))

        ranked = emb_svc.rank_by_similarity(
            query_text=clean_q,
            candidates=all_citations,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        results = []
        for sim, c in ranked:
            c_copy = copy.deepcopy(c)
            c_copy["similarity_score"] = round(sim, 4)
            results.append(c_copy)
        return results

    def find_similar_citations(
        self,
        pmid: str,
        top_k: int = 4,
        min_similarity: float = 0.20,
    ) -> List[Dict[str, Any]]:
        """
        Finds structurally and mechanistically related studies in the knowledge graph
        by computing cosine similarity against the target paper's vector embedding.
        """
        clean_pmid = str(pmid or "").strip()
        if not clean_pmid:
            return []

        from app.services.embedding_service import get_embedding_service
        emb_svc = get_embedding_service()

        # Find target node
        target_node = None
        for nid, node in self._mock_nodes.items():
            if node.get("node_type") in ("citation", "study") and str(node.get("pmid")) == clean_pmid:
                target_node = node
                break

        if not target_node:
            from app.services.pubmed_service import PubMedService
            pubmed_svc = PubMedService()
            meta = pubmed_svc.fetch_abstract(clean_pmid) or pubmed_svc.fetch_citation_metadata(clean_pmid)
            if meta:
                target_node = self.ingest_citation(meta)

        if not target_node:
            return []

        target_emb = target_node.get("embedding")
        if not target_emb:
            title = target_node.get("title", "")
            abstract = target_node.get("abstract", "") or target_node.get("key_findings", "")
            target_emb = emb_svc.embed_citation(title, abstract)
            target_node["embedding"] = target_emb

        candidates: List[Dict[str, Any]] = []
        seen_pmids: Set[str] = {clean_pmid}

        for nid, node in self._mock_nodes.items():
            if node.get("node_type") in ("citation", "study"):
                p = str(node.get("pmid") or "")
                if p and p not in seen_pmids:
                    seen_pmids.add(p)
                    node_emb = node.get("embedding")
                    if not node_emb:
                        node_emb = emb_svc.embed_citation(node.get("title", ""), node.get("abstract", "") or node.get("key_findings", ""))
                        node["embedding"] = node_emb
                    sim = emb_svc.cosine_similarity(target_emb, node_emb)
                    if sim >= min_similarity:
                        c_copy = copy.deepcopy(node)
                        c_copy["similarity_score"] = round(sim, 4)
                        candidates.append((sim, c_copy))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in candidates[:top_k]]


# Singleton instance accessor
_GRAPH_DB_INSTANCE: Optional[Neo4jGraphDatabase] = None


def get_graph_database(uri: Optional[str] = None, auth: Optional[Tuple[str, str]] = None, **kwargs: Any) -> Neo4jGraphDatabase:
    global _GRAPH_DB_INSTANCE
    if _GRAPH_DB_INSTANCE is None:
        _GRAPH_DB_INSTANCE = Neo4jGraphDatabase(uri=uri, auth=auth, **kwargs)
    return _GRAPH_DB_INSTANCE

