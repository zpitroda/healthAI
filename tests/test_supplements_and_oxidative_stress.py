"""
Tests for dietary supplement ingestion, non-receptor cytoprotective mechanisms,
oxidative stress & inflammation (hs-CRP) axes, and dynamic live enrichment.
"""
import pytest
from app.services.catalog_service import CatalogService
from app.services.interaction_engine import InteractionEngine
from app.services.graph_service import (
    build_selected_compound_graph,
    get_exact_target_cascade_blueprint,
)


def test_supplement_catalog_resolution_and_aliases():
    """Verify all newly seeded supplements and their common brand/chemical aliases resolve properly."""
    service = CatalogService()

    # Direct keys
    supplements = [
        "astaxanthin",
        "coq10",
        "milk_thistle",
        "curcumin",
        "citrus_bergamot",
        "alpha_lipoic_acid",
        "taurine",
        "melatonin",
        "nac",
        "tudca",
        "l_carnitine",
        "l_theanine",
        "berberine",
        "omega_3",
    ]
    for supp in supplements:
        comp = service.get_compound(supp)
        assert comp is not None, f"Failed to retrieve {supp}"
        assert comp.get("name") is not None

    # Common aliases & brand names
    alias_tests = [
        ("asta", "astaxanthin"),
        ("astareal", "astaxanthin"),
        ("ubiquinol", "coq10"),
        ("ubiquinone", "coq10"),
        ("silymarin", "milk_thistle"),
        ("silybin", "milk_thistle"),
        ("turmeric", "curcumin"),
        ("curcuminoids", "curcumin"),
        ("bergamot", "citrus_bergamot"),
        ("bpf", "citrus_bergamot"),
        ("ala", "alpha_lipoic_acid"),
        ("rala", "alpha_lipoic_acid"),
        ("ltaurine", "taurine"),
        ("nacetylcysteine", "nac"),
        ("tauroursodeoxycholicacid", "tudca"),
        ("alcar", "l_carnitine"),
    ]
    for alias, expected_canonical in alias_tests:
        comp = service.get_compound(alias)
        assert comp is not None, f"Failed to resolve alias '{alias}'"
        assert comp.get("canonical_key") == expected_canonical or comp.get("key") == expected_canonical


def test_astaxanthin_non_receptor_antioxidant_cascade():
    """Verify Astaxanthin dynamically drives Nrf2/redox defense, reduces MDA and hs-CRP, and increases GSH."""
    graph = build_selected_compound_graph(["astaxanthin:12mg"])
    results = graph.propagate_cascade(["astaxanthin"])
    
    shifts = {s["biomarker_id"]: s for s in results.get("biomarker_shifts", [])}
    
    # 1. MDA (Lipid Peroxidation) should decrease
    assert "bio_mda" in shifts
    assert shifts["bio_mda"]["direction"] == "DECREASE"
    assert shifts["bio_mda"]["estimated_delta"] < 0
    
    # 2. GSH:GSSG Redox Ratio should increase
    assert "bio_gsh_redox_ratio" in shifts
    assert shifts["bio_gsh_redox_ratio"]["direction"] == "INCREASE"
    assert shifts["bio_gsh_redox_ratio"]["estimated_delta"] > 0
    
    # 3. hs-CRP should decrease
    assert "bio_crp" in shifts
    assert shifts["bio_crp"]["direction"] == "DECREASE"
    assert shifts["bio_crp"]["estimated_delta"] < 0


def test_nac_and_tudca_protect_kidneys_and_liver():
    """Verify NAC provides renal tubular protection and TUDCA protects against canalicular cholestasis."""
    # 1. NAC alone
    graph_nac = build_selected_compound_graph(["nac:1200mg"])
    res_nac = graph_nac.propagate_cascade(["nac"])
    shifts_nac = {s["biomarker_id"]: s for s in res_nac.get("biomarker_shifts", [])}
    
    assert "bio_gsh_redox_ratio" in shifts_nac
    assert shifts_nac["bio_gsh_redox_ratio"]["direction"] == "INCREASE"
    assert "bio_crp" in shifts_nac
    assert shifts_nac["bio_crp"]["direction"] == "DECREASE"
    
    # 2. TUDCA alone
    graph_tudca = build_selected_compound_graph(["tudca:500mg"])
    res_tudca = graph_tudca.propagate_cascade(["tudca"])
    shifts_tudca = {s["biomarker_id"]: s for s in res_tudca.get("biomarker_shifts", [])}
    
    assert "bio_alt" in shifts_tudca
    assert shifts_tudca["bio_alt"]["direction"] == "DECREASE"
    assert "bio_total_bilirubin" in shifts_tudca
    assert shifts_tudca["bio_total_bilirubin"]["direction"] == "DECREASE"


def test_superdrol_plus_tudca_plus_nac_full_stack_balance():
    """
    Verify that 17a-alkylated Superdrol creates hepatic & oxidative strain,
    and adding TUDCA + NAC counterbalances the stack, generating active mitigations.
    """
    engine = InteractionEngine()
    
    # 1. Superdrol alone -> Uncompensated hepatic & oxidative strain
    res_sd_only = engine.analyze_stack([{"name": "methyldrostanolone", "dose_mg": 20.0}])
    balance_sd = res_sd_only["full_stack_balance"]
    
    redox_axis_sd = next((a for a in balance_sd.get("axes", []) if a.get("biomarker_id") == "bio_gsh_redox_ratio"), None)
    assert redox_axis_sd is not None
    assert redox_axis_sd["estimated_value"] < redox_axis_sd["baseline"]
    
    # 2. Superdrol + TUDCA + NAC -> Active mitigations & normalized redox
    res_protected = engine.analyze_stack([
        {"name": "methyldrostanolone", "dose_mg": 10.0},
        {"name": "tudca", "dose_mg": 500.0},
        {"name": "nac", "dose_mg": 1200.0},
    ])
    balance_prot = res_protected["full_stack_balance"]
    mitigations = balance_prot.get("active_mitigations", [])
    
    # Must have active redox and/or hepatic mitigations
    mitig_titles = [m.get("title", "") for m in mitigations]
    assert any("Redox" in t or "Oxidative" in t or "Glutathione" in t or "Equilibrium" in t for t in mitig_titles)


def test_clenbuterol_plus_astaxanthin_and_taurine():
    """Verify Clenbuterol sympathetic & pro-oxidant strain is counterbalanced by Astaxanthin and Taurine."""
    engine = InteractionEngine()
    
    res = engine.analyze_stack([
        {"name": "clenbuterol", "dose_mg": 0.04},
        {"name": "astaxanthin", "dose_mg": 12.0},
        {"name": "taurine", "dose_mg": 2000.0},
    ])
    balance = res["full_stack_balance"]
    axes = balance.get("axes", [])
    
    # Verify Systemic Oxidative Stress & Redox Axis exists
    redox_axis = next((a for a in axes if "Redox" in a.get("name", "") or a.get("biomarker_id") == "bio_gsh_redox_ratio"), None)
    assert redox_axis is not None
    assert redox_axis["in_safe_range"] is True


def test_systemic_inflammation_hscrp_axis_curcumin_and_omega3():
    """Verify Curcumin + Omega-3 drives anti-inflammatory balance in Full Stack Balance."""
    engine = InteractionEngine()
    
    res = engine.analyze_stack([
        {"name": "curcumin", "dose_mg": 500.0},
        {"name": "omega_3", "dose_mg": 2000.0},
    ])
    balance = res["full_stack_balance"]
    axes = balance.get("axes", [])
    
    crp_axis = next((a for a in axes if a.get("biomarker_id") == "bio_crp"), None)
    assert crp_axis is not None
    assert crp_axis["estimated_value"] <= crp_axis["baseline"]
    assert crp_axis["in_safe_range"] is True
