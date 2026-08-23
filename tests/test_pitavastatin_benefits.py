import pytest
from app.services.pharmacology_enricher import PharmacologyEnricher
from app.services.pathway_service import PathwayService
from app.services.dosing_service import get_default_compound_dose

def test_pitavastatin_usan_stem_enrichment():
    compound = {"key": "pitavastatin", "name": "Pitavastatin"}
    enriched = PharmacologyEnricher.enrich_compound(compound)
    
    assert enriched.get("drug_class") == "HMG-CoA Reductase Inhibitor (Statin)"
    targets = enriched.get("receptor_targets", [])
    assert any(t.get("target") == "HMG-CoA Reductase" for t in targets)
    assert "OATP1B1" in enriched.get("transporters", {}).get("substrates", [])

def test_pitavastatin_dosing():
    dose = get_default_compound_dose("pitavastatin")
    assert dose["dose_mg"] == 2.0
    assert dose["dose_display"] == "2 mg"

def test_hmgcr_pathway_cascade():
    ps = PathwayService()
    cascade = ps.get_dynamic_target_cascade("HMGCR")
    
    biomarkers = cascade.get("biomarkers", [])
    biomarker_ids = [b["id"] for b in biomarkers]
    
    assert "bio_ldl_c" in biomarker_ids
    assert "bio_total_cholesterol" in biomarker_ids
    assert "bio_apob" in biomarker_ids
    
    phenotypes = cascade.get("phenotypes", [])
    pheno_ids = [p["id"] for p in phenotypes]
    
    assert "pheno_ldl_reduction" in pheno_ids
    assert "pheno_cholesterol_lowering" in pheno_ids
    assert "pheno_cardiovascular_risk_reduction" in pheno_ids

def test_pitavastatin_target_cascade_resolution():
    ps = PathwayService()
    cascade = ps.get_dynamic_target_cascade("HMG-CoA Reductase")
    
    biomarkers = cascade.get("biomarkers", [])
    ldl_bm = next((b for b in biomarkers if b["id"] == "bio_ldl_c"), None)
    assert ldl_bm is not None
    assert ldl_bm["mag"] > 0  # HMGCR enzyme activity drives LDL-C, so inhibition lowers LDL-C

def test_pitavastatin_full_graph_biomarker_propagation():
    from app.services.graph_service import build_selected_compound_graph, compute_target_combined_effects
    g = build_selected_compound_graph(["pitavastatin"])
    eff = compute_target_combined_effects(g)
    res = g.propagate_cascade(["pitavastatin"], combined_effects=eff)
    
    shifts = {b["label"]: b["direction"] for b in res.get("biomarker_shifts", [])}
    assert shifts.get("Serum LDL Cholesterol") == "DECREASE"
    assert shifts.get("Serum Total Cholesterol") == "DECREASE"
    assert shifts.get("Apolipoprotein B (ApoB)") == "DECREASE"
    assert shifts.get("Serum Triglycerides") == "DECREASE"
    assert shifts.get("Serum HDL Cholesterol") == "INCREASE"
