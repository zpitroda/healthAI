from __future__ import annotations

import pytest
from app.knowledge_graph.graph import BiologicalGraph
from app.knowledge_graph.models import (
    BiomarkerNode,
    CompoundNode,
    EdgeData,
    EdgeType,
    PhenotypeNode,
    PhysiologyNode,
    ReceptorNode,
    SignalingPathwayNode,
)
from app.services.graph_service import (
    build_selected_compound_graph,
    filter_graph_by_stack,
)


def test_biological_graph_dynamic_cascade_propagation():
    """Verify signed directional vector propagation down a multi-tier biological cascade."""
    graph = BiologicalGraph()

    # Tier 1: Compound
    graph.add_node(CompoundNode(node_id="drug_x", label="Drug X", logP=2.5, molecular_weight=350.0))

    # Tier 2: Receptor (Antagonist)
    graph.add_node(ReceptorNode(node_id="target_r", label="Receptor R", receptor_family="GPCR"))
    graph.add_edge("drug_x", "target_r", EdgeType.ANTAGONIZES, EdgeData(vector_magnitude=-1.0, affinity_ki=0.005))

    # Tier 3: Signaling Pathway (Receptor normally activates pathway)
    graph.add_node(SignalingPathwayNode(node_id="pathway_s", label="Signaling Pathway S", pathway_database="Reactome"))
    graph.add_edge("target_r", "pathway_s", EdgeType.ACTIVATES_PATHWAY, EdgeData(vector_magnitude=1.0))

    # Tier 4: Physiology
    graph.add_node(PhysiologyNode(node_id="phys_vaso", label="Vascular Tone", organ_system="Cardiovascular"))
    graph.add_edge("pathway_s", "phys_vaso", EdgeType.ALTERS_PHYSIOLOGY, EdgeData(vector_magnitude=1.0))

    # Tier 5: Biomarker
    graph.add_node(BiomarkerNode(node_id="bio_bp", label="Blood Pressure", unit="mmHg", safe_lower_bound=90, safe_upper_bound=120))
    graph.add_edge("phys_vaso", "bio_bp", EdgeType.MODIFIES_BIOMARKER, EdgeData(vector_magnitude=0.8))

    # Tier 6: Phenotype
    graph.add_node(PhenotypeNode(node_id="pheno_stroke_risk", label="Stroke Risk Reduction", phenotype_category="therapeutic_benefit"))
    graph.add_edge("phys_vaso", "pheno_stroke_risk", EdgeType.DRIVES_PHENOTYPE, EdgeData(vector_magnitude=0.7))

    results = graph.propagate_cascade("drug_x")

    assert len(results["activated_pathways"]) > 0
    assert len(results["biomarker_shifts"]) > 0
    assert len(results["phenotypes"]) > 0
    assert len(results["cascade_traces"]) > 0

    bp_shift = next((b for b in results["biomarker_shifts"] if b["biomarker_id"] == "bio_bp"), None)
    assert bp_shift is not None
    assert bp_shift["direction"] == "DECREASE"
    assert bp_shift["arrow"] == "↓"


def test_build_selected_compound_graph_generates_multi_tier_cascade():
    """Verify build_selected_compound_graph dynamically constructs multi-tier cascades."""
    graph = build_selected_compound_graph(["caffeine", "creatine"])
    summary = graph.summarize()

    assert summary["nodes"] >= 6
    assert summary["edges"] >= 5
    assert "compound" in summary["node_types"]

    results = graph.propagate_cascade(["caffeine", "creatine"])
    assert "biomarker_shifts" in results
    assert len(results["biomarker_shifts"]) > 0
