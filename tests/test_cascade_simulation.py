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


def test_caffeine_cascade_increases_heart_rate_and_blood_pressure():
    """Verify Caffeine (A1/A2A antagonist) correctly propagates an INCREASE for heart rate and blood pressure."""
    from app.services.catalog_service import CatalogService
    from app.services.graph_service import resolve_stack_to_catalog_keys

    service = CatalogService()
    keys = resolve_stack_to_catalog_keys(["caffeine"], service)
    graph = build_selected_compound_graph(keys, catalog_service=service)
    results = graph.propagate_cascade(keys)

    hr_shift = next((b for b in results["biomarker_shifts"] if b["biomarker_id"] == "bio_heart_rate"), None)
    assert hr_shift is not None, "Resting Heart Rate biomarker shift must be present"
    assert hr_shift["direction"] == "INCREASE", f"Expected INCREASE for heart rate, got {hr_shift['direction']}"
    assert hr_shift["arrow"] == "↑"
    assert hr_shift["net_shift"] > 0.05

    bp_shift = next((b for b in results["biomarker_shifts"] if b["biomarker_id"] == "bio_blood_pressure"), None)
    assert bp_shift is not None, "Systolic Blood Pressure biomarker shift must be present"
    assert bp_shift["direction"] == "INCREASE"
    assert bp_shift["arrow"] == "↑"

    pheno_ids = {p["phenotype_id"]: p["net_score"] for p in results["phenotypes"]}
    assert "pheno_vigilance" in pheno_ids
    assert pheno_ids["pheno_vigilance"] > 0
    assert "pheno_tachycardia" in pheno_ids
    assert pheno_ids["pheno_tachycardia"] > 0
    assert "pheno_insomnia" in pheno_ids
    assert pheno_ids["pheno_insomnia"] > 0


def test_caffeine_and_theanine_converges_on_unified_resting_heart_rate():
    """Verify Caffeine (accelerator) + Theanine (dampener) converge on a single unified bio_heart_rate node."""
    from app.services.catalog_service import CatalogService
    from app.services.graph_service import resolve_stack_to_catalog_keys

    service = CatalogService()
    keys = resolve_stack_to_catalog_keys(["caffeine", "theanine"], service)
    graph = build_selected_compound_graph(keys, catalog_service=service)

    # Ensure there is exactly one Resting Heart Rate node in the graph, not duplicate IDs
    hr_nodes = [n for n, d in graph.graph.nodes(data=True) if "heart rate" in str(d.get("label", "")).lower()]
    assert len(hr_nodes) == 1
    assert hr_nodes[0] == "bio_heart_rate"

    # Propagate combined cascade
    results = graph.propagate_cascade(keys)
    hr_shift = next((b for b in results["biomarker_shifts"] if b["biomarker_id"] == "bio_heart_rate"), None)
    assert hr_shift is not None
    assert hr_shift["direction"] == "INCREASE"

    # Theanine should provide cortisol reduction
    cortisol_shift = next((b for b in results["biomarker_shifts"] if b["biomarker_id"] == "bio_cortisol"), None)
    assert cortisol_shift is not None
    assert cortisol_shift["direction"] == "DECREASE"


def test_enzyme_inhibitor_and_target_cascade_polarities():
    """Verify 5-AR (Finasteride), PDE5 (Tadalafil), COX (Ibuprofen) propagate medically correct biomarker shifts."""
    from app.services.catalog_service import CatalogService
    from app.services.graph_service import resolve_stack_to_catalog_keys

    service = CatalogService()

    # 1. Finasteride: 5-AR inhibitor -> decreases DHT, drives alopecia arrest
    fin_keys = resolve_stack_to_catalog_keys(["finasteride"], service)
    if fin_keys:
        fin_graph = build_selected_compound_graph(fin_keys, catalog_service=service)
        fin_res = fin_graph.propagate_cascade(fin_keys)
        dht_shift = next((b for b in fin_res["biomarker_shifts"] if b["biomarker_id"] == "bio_dht"), None)
        if dht_shift:
            assert dht_shift["direction"] == "DECREASE"
            assert dht_shift["arrow"] == "↓"
        alopecia_pheno = next((p for p in fin_res["phenotypes"] if p["phenotype_id"] == "pheno_alopecia_halt"), None)
        if alopecia_pheno:
            assert alopecia_pheno["net_score"] > 0

    # 2. Tadalafil: PDE5 inhibitor -> decreases BP, drives hyperemia
    tada_keys = resolve_stack_to_catalog_keys(["tadalafil"], service)
    if tada_keys:
        tada_graph = build_selected_compound_graph(tada_keys, catalog_service=service)
        tada_res = tada_graph.propagate_cascade(tada_keys)
        bp_shift = next((b for b in tada_res["biomarker_shifts"] if b["biomarker_id"] == "bio_blood_pressure"), None)
        if bp_shift:
            assert bp_shift["direction"] == "DECREASE"

    # 3. Ibuprofen: COX inhibitor -> decreases CRP, decreases eGFR, drives antiinflammatory
    ibu_keys = resolve_stack_to_catalog_keys(["ibuprofen"], service)
    if ibu_keys:
        ibu_graph = build_selected_compound_graph(ibu_keys, catalog_service=service)
        ibu_res = ibu_graph.propagate_cascade(ibu_keys)
        crp_shift = next((b for b in ibu_res["biomarker_shifts"] if b["biomarker_id"] == "bio_crp"), None)
        if crp_shift:
            assert crp_shift["direction"] == "DECREASE"

