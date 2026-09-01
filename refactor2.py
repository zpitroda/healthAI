import re

with open(r'l:\healthAI\app\knowledge_graph\graph_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find('    def sync_biological_graph(self, bio_graph: Any) -> Dict[str, int]:')
end_idx = text.find('    def multi_hop_traversal(self, start_id: str, max_hops: int = 5) -> List[Dict[str, Any]]:')

if start_idx == -1 or end_idx == -1:
    print('Failed to find bounds')
    exit(1)

new_func = '''    def sync_biological_graph(self, bio_graph: Any) -> Dict[str, int]:
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
                        UNWIND batch AS row
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
                        UNWIND  AS row
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
                        UNWIND batch AS row
                        MATCH (a:EntityNode {{id: row.source}}), (b:EntityNode {{id: row.target}})
                        MERGE (a)-[r:{rel_type} {{edge_type: row.edge_type}}]->(b)
                        SET r += row
                        """
                        session.run(q, {"batch": clean_batch})
            except Exception as e:
                logger.error(f"Error during edge batching: {e}")

        return {"nodes_synced": nodes_synced, "edges_synced": edges_synced}
'''

text = text[:start_idx] + new_func + text[end_idx:]
with open(r'l:\healthAI\app\knowledge_graph\graph_db.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
