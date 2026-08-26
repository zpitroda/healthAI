import pytest
from app.services.catalog_service import CatalogService
from app.services.graph_service import (
    build_selected_compound_graph,
    parse_compound_spec,
    compute_target_combined_effects,
)
from app.services.interaction_engine import InteractionEngine
from app.knowledge_graph.graph import BiologicalGraph, BIOMARKER_CLINICAL_CALIBRATION
from app.knowledge_graph.models import EnzymeNode


def test_bio_tmao_biomarker_calibration_registered():
    """Verify that bio_tmao is calibrated in BIOMARKER_CLINICAL_CALIBRATION."""
    assert "bio_tmao" in BIOMARKER_CLINICAL_CALIBRATION
    cal = BIOMARKER_CLINICAL_CALIBRATION["bio_tmao"]
    assert cal["baseline"] == 3.5
    assert cal["unit"] == "μmol/L"
    assert cal["safe_upper"] == 6.2
    assert cal["kinetic_profile"] == "gut_microbial_metabolism"


def test_enzyme_node_supports_microbial_taxonomy():
    """Verify EnzymeNode supports is_microbial and microbial_source fields."""
    node = EnzymeNode(
        node_id="cnta",
        label="Gut Microbiota Carnitine TMA-Lyase (CntA/CntB)",
        enzyme_family="Microbial Lyase",
        is_microbial=True,
        microbial_source="Gut Microbiota",
    )
    assert node.is_microbial is True
    assert node.microbial_source == "Gut Microbiota"
    assert node.node_type == "enzyme"


def test_catalog_enrichment_for_l_carnitine_and_allicin():
    """Verify catalog resolves L-Carnitine and Allicin with microbial lyase targets."""
    catalog = CatalogService()
    
    # 1. L-Carnitine
    carn = catalog.get_compound("l_carnitine")
    assert carn is not None
    assert "l_carnitine" in carn["key"].lower() or "carnitine" in carn["name"].lower()
    targets = [t.get("target", "").lower() for t in carn.get("receptor_targets", [])]
    assert any("cpt1" in t or "carnitine palmitoyltransferase" in t for t in targets)
    assert any("tma" in t or "lyase" in t or "cnta" in t for t in targets)

    # 2. Allicin
    alli = catalog.get_compound("allicin")
    assert alli is not None
    assert "allicin" in alli["key"].lower() or "garlic" in alli["name"].lower()
    alli_targets = [t.get("target", "").lower() for t in alli.get("receptor_targets", [])]
    assert any("tma" in t or "lyase" in t or "cnta" in t for t in alli_targets)


def test_oral_l_carnitine_elevates_tmao_cascade():
    """Verify that oral L-carnitine generates a significant positive shift in serum TMAO."""
    parsed = [parse_compound_spec("l_carnitine:1000mg:oral")]
    graph = build_selected_compound_graph(parsed)
    
    # Verify graph contains microbial lyase enzyme node with microbial flag
    lyase_nodes = [
        n for n, d in graph.graph.nodes(data=True)
        if any(w in n.lower() for w in ["tma", "lyase", "cnta"])
    ]
    assert len(lyase_nodes) > 0

    # Compute target combined effects and propagate cascade
    effects = compute_target_combined_effects(graph)
    start_nodes = [n for n, d in graph.graph.nodes(data=True) if d.get("node_type") == "compound"]
    results = graph.propagate_cascade(start_node_ids=start_nodes, combined_effects=effects)
    
    tmao_shift = next((s for s in results.get("biomarker_shifts", []) if s["biomarker_id"] == "bio_tmao"), None)
    assert tmao_shift is not None
    assert tmao_shift["estimated_delta"] > 3.0
    assert tmao_shift["estimated_value"] > 6.2  # Exceeds safe upper threshold


def test_allicin_counters_and_mitigates_oral_carnitine_tmao():
    """
    Verify that adding Allicin to Oral L-Carnitine inhibits microbial TMA lyase
    and attenuates TMAO elevation by >50%.
    """
    # 1. Oral Carnitine alone
    carn_only = [parse_compound_spec("l_carnitine:1000mg:oral")]
    g_carn = build_selected_compound_graph(carn_only)
    eff_carn = compute_target_combined_effects(g_carn)
    starts_carn = [n for n, d in g_carn.graph.nodes(data=True) if d.get("node_type") == "compound"]
    res_carn = g_carn.propagate_cascade(start_node_ids=starts_carn, combined_effects=eff_carn)
    tmao_carn = next((s["estimated_delta"] for s in res_carn.get("biomarker_shifts", []) if s["biomarker_id"] == "bio_tmao"), 0.0)

    # 2. Oral Carnitine + Allicin (10mg)
    carn_plus_allicin = [
        parse_compound_spec("l_carnitine:1000mg:oral"),
        parse_compound_spec("allicin:10mg:oral"),
    ]
    g_combo = build_selected_compound_graph(carn_plus_allicin)
    eff_combo = compute_target_combined_effects(g_combo)
    starts_combo = [n for n, d in g_combo.graph.nodes(data=True) if d.get("node_type") == "compound"]
    res_combo = g_combo.propagate_cascade(start_node_ids=starts_combo, combined_effects=eff_combo)
    tmao_combo = next((s["estimated_delta"] for s in res_combo.get("biomarker_shifts", []) if s["biomarker_id"] == "bio_tmao"), 0.0)

    assert tmao_carn > 3.0
    # Allicin co-administration must significantly suppress TMAO elevation
    assert tmao_combo < tmao_carn
    reduction_pct = ((tmao_carn - tmao_combo) / tmao_carn) * 100.0
    assert reduction_pct >= 50.0


def test_parenteral_intramuscular_carnitine_bypasses_tmao():
    """
    Verify that Intramuscular L-Carnitine bypasses gut microbiota,
    producing negligible TMAO compared to oral L-Carnitine.
    """
    oral_spec = [parse_compound_spec("l_carnitine:1000mg:oral")]
    g_oral = build_selected_compound_graph(oral_spec)
    eff_oral = compute_target_combined_effects(g_oral)
    starts_oral = [n for n, d in g_oral.graph.nodes(data=True) if d.get("node_type") == "compound"]
    res_oral = g_oral.propagate_cascade(start_node_ids=starts_oral, combined_effects=eff_oral)
    tmao_oral = next((s["estimated_delta"] for s in res_oral.get("biomarker_shifts", []) if s["biomarker_id"] == "bio_tmao"), 0.0)

    im_spec = [parse_compound_spec("l_carnitine:500mg:intramuscular")]
    g_im = build_selected_compound_graph(im_spec)
    eff_im = compute_target_combined_effects(g_im)
    starts_im = [n for n, d in g_im.graph.nodes(data=True) if d.get("node_type") == "compound"]
    res_im = g_im.propagate_cascade(start_node_ids=starts_im, combined_effects=eff_im)
    tmao_im = next((s["estimated_delta"] for s in res_im.get("biomarker_shifts", []) if s["biomarker_id"] == "bio_tmao"), 0.0)

    assert tmao_oral > 3.0
    # IM route bypasses gut lumen -> negligible TMAO elevation (< 0.5 umol/L)
    assert tmao_im < 0.5
    assert tmao_im < (tmao_oral * 0.15)


def test_interaction_engine_detects_tmao_mitigation_pair():
    """
    Verify InteractionEngine identifies oral L-Carnitine + Allicin as a
    SYNERGISTIC gut microbiota mitigation pair.
    """
    engine = InteractionEngine()
    stack = [
        {"name": "L-Carnitine", "key": "l_carnitine", "dose": 1000, "dose_mg": 1000, "unit": "mg", "route": "oral"},
        {"name": "Allicin", "key": "allicin", "dose": 10, "dose_mg": 10, "unit": "mg", "route": "oral"},
    ]
    
    result = engine.analyze_stack(stack)
    
    # Check pairwise synergy
    matrix = result.get("matrix", [])
    assert len(matrix) == 2
    cell = matrix[0][1]
    
    assert cell["severity"] == "SYNERGISTIC"
    assert "GUT_MICROBIOME_MITIGATION" in cell.get("conflict_types", []) or "SYNERGY" in cell.get("conflict_types", [])
    assert "TMAO" in cell.get("title", "") or "Microbiota" in cell.get("title", "")
    assert "CntA/CntB" in cell.get("description", "") or "trimethylamine" in cell.get("description", "").lower()
