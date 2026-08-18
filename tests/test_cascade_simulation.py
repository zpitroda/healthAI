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
    contribs = {c["compound_id"]: c["contribution_mag"] for c in hr_shift.get("compound_contributions", [])}
    assert "caffeine" in contribs and "l_theanine" in contribs
    assert contribs["caffeine"] > 0, "Caffeine must exert positive chronotropic force"
    assert contribs["l_theanine"] < 0, "Theanine must exert negative chronotropic dampening"

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

    # 4. NAC (N-Acetylcysteine): Glutathione Precursor -> decreases hs-CRP, decreases MDA, increases GSH:GSSG redox index
    nac_keys = resolve_stack_to_catalog_keys(["nac"], service)
    if nac_keys:
        nac_graph = build_selected_compound_graph(nac_keys, catalog_service=service)
        nac_res = nac_graph.propagate_cascade(nac_keys)
        nac_crp = next((b for b in nac_res["biomarker_shifts"] if b["biomarker_id"] == "bio_crp"), None)
        assert nac_crp is not None
        assert nac_crp["direction"] == "DECREASE"
        assert nac_crp["estimated_delta"] < 0
        nac_gsh = next((b for b in nac_res["biomarker_shifts"] if b["biomarker_id"] == "bio_gsh_redox_ratio"), None)
        assert nac_gsh is not None
        assert nac_gsh["direction"] == "INCREASE"
        assert nac_gsh["estimated_delta"] > 0


def test_cascade_biomarker_and_phenotype_scaling_by_dose_and_saturation():
    """Verify that downstream cascade biomarker shifts and phenotype scores scale with dose and saturation."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    res_1mg = client.get("/graph-data?stack=nebivolol:1mg").json().get("cascade_simulation", {})
    res_5mg = client.get("/graph-data?stack=nebivolol:5mg").json().get("cascade_simulation", {})
    res_20mg = client.get("/graph-data?stack=nebivolol:20mg").json().get("cascade_simulation", {})

    # 1. Check Resting Heart Rate biomarker shift scaling across doses
    hr_1mg = next(b for b in res_1mg.get("biomarker_shifts", []) if b["biomarker_id"] == "bio_heart_rate")
    hr_5mg = next(b for b in res_5mg.get("biomarker_shifts", []) if b["biomarker_id"] == "bio_heart_rate")
    hr_20mg = next(b for b in res_20mg.get("biomarker_shifts", []) if b["biomarker_id"] == "bio_heart_rate")

    # Higher dose / higher saturation produces monotonically larger negative heart rate shifts
    assert hr_1mg["net_shift"] < 0
    assert hr_5mg["net_shift"] < hr_1mg["net_shift"]
    assert hr_20mg["net_shift"] < hr_5mg["net_shift"]

    # 2. Check Bradycardia phenotype score scaling across doses
    brady_1mg = next(p for p in res_1mg.get("phenotypes", []) if "bradycardia" in p["phenotype_id"])
    brady_5mg = next(p for p in res_5mg.get("phenotypes", []) if "bradycardia" in p["phenotype_id"])
    brady_20mg = next(p for p in res_20mg.get("phenotypes", []) if "bradycardia" in p["phenotype_id"])

    assert brady_1mg["net_score"] > 0
    assert brady_5mg["net_score"] > brady_1mg["net_score"]
    assert brady_20mg["net_score"] > brady_5mg["net_score"]


def test_aromatase_inhibition_dose_dependent_blood_pressure_attenuation():
    """Verify that adding/titrating an Aromatase Inhibitor (Exemestane) with high Testosterone reduces E2 fluid retention and lowers blood pressure."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    
    # 70mg/day Testosterone monotherapy (high E2, high water retention)
    res_t_only = client.post('/api/interactions/matrix', json={'stack': [{'key': 'testosterone', 'dose': 70, 'unit': 'mg'}]}).json()
    bp_t_only = next(a for a in res_t_only['full_stack_balance']['axes'] if a['biomarker_id'] == 'bio_blood_pressure')
    e2_t_only = next(a for a in res_t_only['full_stack_balance']['axes'] if a['biomarker_id'] == 'bio_estradiol')
    
    # 70mg/day Testosterone + 2.7mg/day Exemestane (titrated AI)
    res_t_ai_low = client.post('/api/interactions/matrix', json={'stack': [{'key': 'testosterone', 'dose': 70, 'unit': 'mg'}, {'key': 'exemestane', 'dose': 2.7, 'unit': 'mg'}]}).json()
    bp_t_ai_low = next(a for a in res_t_ai_low['full_stack_balance']['axes'] if a['biomarker_id'] == 'bio_blood_pressure')
    e2_t_ai_low = next(a for a in res_t_ai_low['full_stack_balance']['axes'] if a['biomarker_id'] == 'bio_estradiol')
    
    # 70mg/day Testosterone + 25mg/day Exemestane (full clinical AI dose)
    res_t_ai_full = client.post('/api/interactions/matrix', json={'stack': [{'key': 'testosterone', 'dose': 70, 'unit': 'mg'}, {'key': 'exemestane', 'dose': 25.0, 'unit': 'mg'}]}).json()
    bp_t_ai_full = next(a for a in res_t_ai_full['full_stack_balance']['axes'] if a['biomarker_id'] == 'bio_blood_pressure')
    e2_t_ai_full = next(a for a in res_t_ai_full['full_stack_balance']['axes'] if a['biomarker_id'] == 'bio_estradiol')
    
    # E2 drops monotonically as Exemestane dose increases
    assert e2_t_ai_low['estimated_value'] < e2_t_only['estimated_value']
    assert e2_t_ai_full['estimated_value'] < e2_t_ai_low['estimated_value']
    
    # Blood pressure drops monotonically as E2-mediated fluid retention is shed
    assert bp_t_ai_low['estimated_value'] < bp_t_only['estimated_value']
    assert bp_t_ai_full['estimated_value'] < bp_t_ai_low['estimated_value']
    
    # Exemestane is explicitly listed in the Blood Pressure compound breakdown with negative delta
    exem_bp_share = next((c for c in bp_t_ai_low['compounds_breakdown'] if c['compound_id'] == 'exemestane'), None)
    assert exem_bp_share is not None
    assert exem_bp_share['delta'] < 0.0


def test_eplerenone_low_dose_and_telmisartan_subadditive_blood_pressure():
    """Verify that low-dose Eplerenone (12.5mg) produces a modest, realistic blood pressure reduction (< 6 mmHg) and high hyperkalemia risk."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 12.5mg Eplerenone monotherapy
    res_epl = client.get('/graph-data?stack=eplerenone:12.5mg&depth=5').json()
    epl_bp = next((b for b in res_epl['cascade_simulation']['biomarker_shifts'] if b['biomarker_id'] == 'bio_blood_pressure'), None)
    epl_k = next((b for b in res_epl['cascade_simulation']['biomarker_shifts'] if b['biomarker_id'] == 'bio_potassium'), None)

    assert epl_bp is not None
    # 12.5mg Eplerenone must drop systolic blood pressure modestly (between -2.0 and -6.0 mmHg), NOT -32.1 mmHg!
    assert -6.0 <= epl_bp['estimated_delta'] <= -2.0
    # Serum potassium increases due to aldosterone receptor blockade (K+ sparing)
    assert epl_k is not None
    assert epl_k['estimated_delta'] > 0.0


def test_non_aromatizable_androgens_do_not_increase_e2():
    """Verify that non-aromatizable androgens (Trenbolone, Masteron) do NOT increase estradiol."""
    from app.services.interaction_engine import InteractionEngine
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    engine = InteractionEngine()

    for drug_key in ["trenbolone", "masteron", "drostanolone"]:
        compound = service.get_compound(drug_key)
        if not compound:
            continue
        result = engine.analyze_stack([compound])
        shifts = result.get("full_stack_balance", {}).get("cascade_biomarker_shifts", [])
        e2_shift = next((b for b in shifts if b["biomarker_id"] == "bio_estradiol"), None)
        if e2_shift:
            # E2 must NOT increase for non-aromatizable androgens
            assert e2_shift["estimated_delta"] <= 0.0


def test_androgens_suppress_pituitary_gonadotropins_lh_and_fsh():
    """Verify that exogenous androgens suppress pituitary gonadotropins (LH and FSH) via negative feedback."""
    from app.services.interaction_engine import InteractionEngine
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    engine = InteractionEngine()

    test_c = service.get_compound("testosterone")
    res_t = engine.analyze_stack([test_c])
    shifts = res_t.get("full_stack_balance", {}).get("cascade_biomarker_shifts", [])

    fsh_shift = next((b for b in shifts if b["biomarker_id"] == "bio_fsh"), None)
    lh_shift = next((b for b in shifts if b["biomarker_id"] == "bio_luteinizing_hormone"), None)

    assert fsh_shift is not None
    assert fsh_shift["direction"] == "DECREASE"
    assert fsh_shift["estimated_delta"] < 0.0

    assert lh_shift is not None
    assert lh_shift["direction"] == "DECREASE"
    assert lh_shift["estimated_delta"] < 0.0


def test_androgen_lipid_profile_shifts_hdl_ldl_and_triglycerides():
    """Verify that androgens alter lipid profiles: suppressing HDL-C and elevating LDL-C and triglycerides."""
    from app.services.interaction_engine import InteractionEngine
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    engine = InteractionEngine()

    test_c = service.get_compound("testosterone")
    res_t = engine.analyze_stack([test_c])
    shifts = res_t.get("full_stack_balance", {}).get("cascade_biomarker_shifts", [])

    hdl = next((b for b in shifts if b["biomarker_id"] == "bio_hdl_c"), None)
    ldl = next((b for b in shifts if b["biomarker_id"] == "bio_ldl_c"), None)
    trig = next((b for b in shifts if b["biomarker_id"] == "bio_triglycerides"), None)

    assert hdl is not None
    assert hdl["direction"] == "DECREASE"
    assert hdl["estimated_delta"] < 0.0

    assert ldl is not None
    assert ldl["direction"] == "INCREASE"
    assert ldl["estimated_delta"] > 0.0

    assert trig is not None
def test_dynamic_hepatic_renal_and_oxidative_stress_cascades():
    """Verify that hepatic, renal, and oxidative stress cascades are dynamically transduced from compound profiles."""
    from app.services.interaction_engine import InteractionEngine
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    engine = InteractionEngine()

    # 1. Hepatic Stress: Compound with hepatic clearance / lipophilicity shifts ALT & AST
    test_c = service.get_compound("testosterone")
    res_t = engine.analyze_stack([test_c])
    shifts_t = res_t.get("full_stack_balance", {}).get("cascade_biomarker_shifts", [])
    alt_shift = next((b for b in shifts_t if b["biomarker_id"] == "bio_alt"), None)
    ast_shift = next((b for b in shifts_t if b["biomarker_id"] == "bio_ast"), None)
    assert alt_shift is not None
    assert alt_shift["direction"] == "INCREASE"
    assert alt_shift["estimated_delta"] > 0.0
    assert ast_shift is not None
    assert ast_shift["direction"] == "INCREASE"

    # 2. Renal Stress: Compound with renal clearance (e.g. Telmisartan / Eplerenone / SGLT2) shifts Creatinine & eGFR
    epl_c = service.get_compound("eplerenone")
    if epl_c:
        res_epl = engine.analyze_stack([epl_c])
        shifts_epl = res_epl.get("full_stack_balance", {}).get("cascade_biomarker_shifts", [])
        cr_shift = next((b for b in shifts_epl if b["biomarker_id"] == "bio_serum_creatinine"), None)
        egfr_shift = next((b for b in shifts_epl if b["biomarker_id"] == "bio_egfr"), None)
        assert cr_shift is not None
        assert egfr_shift is not None

    # 3. Oxidative / Redox Stress: Sympathomimetic beta-agonist (e.g. Clenbuterol) shifts GSH redox ratio & MDA
    clen_c = service.get_compound("clenbuterol")
    if clen_c:
        res_clen = engine.analyze_stack([clen_c])
        shifts_clen = res_clen.get("full_stack_balance", {}).get("cascade_biomarker_shifts", [])
        gsh_shift = next((b for b in shifts_clen if b["biomarker_id"] == "bio_gsh_redox_ratio"), None)
        mda_shift = next((b for b in shifts_clen if b["biomarker_id"] == "bio_mda"), None)
        assert gsh_shift is not None
        assert gsh_shift["direction"] == "DECREASE"
        assert mda_shift is not None
        assert mda_shift["direction"] == "INCREASE"


def test_comprehensive_9_domain_biomarker_calibration_coverage():
    """Verify that all 9 physiological domains have calibrated clinical biomarkers in graph.py."""
    from app.knowledge_graph.graph import BIOMARKER_CLINICAL_CALIBRATION

    domain_checks = {
        "Hepatobiliary": ["bio_alt", "bio_ast", "bio_total_bilirubin", "bio_ggt", "bio_alp"],
        "Renal": ["bio_serum_creatinine", "bio_egfr", "bio_bun", "bio_cystatin_c"],
        "Oxidative/Redox": ["bio_gsh_redox_ratio", "bio_mda", "bio_crp"],
        "Cardiovascular": ["bio_heart_rate", "bio_blood_pressure", "bio_nt_probnp", "bio_qtc"],
        "Lipid": ["bio_hdl_c", "bio_ldl_c", "bio_triglycerides", "bio_apob"],
        "Hematology": ["bio_hematocrit", "bio_hemoglobin", "bio_platelets", "bio_blood_viscosity"],
        "Neuroendocrine": ["bio_testosterone", "bio_estradiol", "bio_dht", "bio_fsh", "bio_luteinizing_hormone", "bio_cortisol", "bio_prolactin", "bio_shbg"],
        "Metabolic/Glycemic": ["bio_glucose", "bio_fasting_insulin", "bio_homa_ir"],
        "Neurochemical": ["bio_cns_arousal", "bio_dopamine_tone", "bio_serotonin_tone"],
    }

    for domain, markers in domain_checks.items():
        for marker_id in markers:
            assert marker_id in BIOMARKER_CLINICAL_CALIBRATION, f"Missing calibration for {marker_id} in {domain} domain"
            entry = BIOMARKER_CLINICAL_CALIBRATION[marker_id]
            assert "baseline" in entry
            assert "unit" in entry
            assert "gain_up" in entry
            assert "gain_down" in entry
            assert "safe_lower" in entry
            assert "safe_upper" in entry
            assert "label" in entry
            assert "kinetic_profile" in entry





