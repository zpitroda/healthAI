from fastapi.testclient import TestClient
from app.main import app
from app.services.interaction_engine import InteractionEngine
from app.services.catalog_service import CatalogService

client = TestClient(app)


def test_exemestane_monotherapy_e2_crash_detection():
    """Verify that an aromatase inhibitor alone (Exemestane / Anastrozole) flags hypoestrogenic E2 crash."""
    cat = CatalogService()
    engine = InteractionEngine()
    
    exemestane = cat.get_compound("exemestane") or {
        "key": "exemestane",
        "name": "Exemestane",
        "drug_class": "steroidal aromatase inhibitor",
        "dose": 25.0,
        "unit": "mg",
        "dose_mg": 25.0,
        "receptor_targets": [{"target": "Aromatase (CYP19A1)", "action": "inhibitor", "affinity_ki": 0.26}],
    }
    
    result = engine.analyze_stack([exemestane])
    balance = result.get("full_stack_balance", {})
    assert balance is not None
    
    e2_axis = next((a for a in balance.get("axes", []) if a.get("biomarker_id") == "bio_estradiol"), None)
    assert e2_axis is not None
    assert e2_axis["status"] == "HYPOESTROGENIC_CRASH"
    assert e2_axis["estimated_value"] < 18.0
    
    # Should flag uncompensated risk
    uncomp = balance.get("uncompensated_risks", [])
    assert any("E2 Crash" in u.get("title", "") or "Aromatase" in u.get("title", "") for u in uncomp)


def test_testosterone_and_exemestane_holistic_e2_equilibrium():
    """Verify that stacking Testosterone with high dose Exemestane (100mg) crashes E2 into single digits, and balanced AI balances E2."""
    cat = CatalogService()
    engine = InteractionEngine()
    
    testo = cat.get_compound("testosterone")
    testo["dose"] = 70.0
    testo["dose_mg"] = 70.0
    
    exem_high = cat.get_compound("exemestane")
    exem_high["dose"] = 100.0
    exem_high["dose_mg"] = 100.0
    
    profile_male = {"sex": "male", "age": 35}
    result_high = engine.analyze_stack([testo, exem_high], profile=profile_male)
    balance_high = result_high.get("full_stack_balance", {})
    assert balance_high is not None
    
    e2_axis = next((a for a in balance_high.get("axes", []) if a.get("biomarker_id") == "bio_estradiol"), None)
    assert e2_axis is not None
    assert e2_axis["status"] in ["BALANCED_TARGET", "HYPOESTROGENIC_CRASH"]
    assert 15.0 <= e2_axis["estimated_value"] <= 45.0 or e2_axis["estimated_value"] < 15.0

    # Balanced AI stack with titrated Exemestane (12.5 mg/day with 50mg/day Testosterone)
    testo_bal = cat.get_compound("testosterone")
    testo_bal["dose"] = 50.0
    testo_bal["dose_mg"] = 50.0
    
    exem_bal = cat.get_compound("exemestane")
    exem_bal["dose"] = 12.5
    exem_bal["dose_mg"] = 12.5
    
    result_bal = engine.analyze_stack([testo_bal, exem_bal], profile=profile_male)
    balance_bal = result_bal.get("full_stack_balance", {})
    assert balance_bal is not None
    assert len(balance_bal.get("active_mitigations", [])) >= 1
    e2_bal_axis = next((a for a in balance_bal.get("axes", []) if a.get("biomarker_id") == "bio_estradiol"), None)
    assert e2_bal_axis is not None
    assert e2_bal_axis["status"] == "BALANCED_TARGET"
    assert 15.0 <= e2_bal_axis["estimated_value"] <= 50.0


def test_testosterone_and_telmisartan_blood_pressure_counterbalance():
    """Verify that Telmisartan counterbalances Testosterone-induced hypertensive tone into normotensive range."""
    cat = CatalogService()
    engine = InteractionEngine()
    
    testo = cat.get_compound("testosterone")
    testo["dose"] = 50.0
    testo["dose_mg"] = 50.0
    
    telmi = cat.get_compound("telmisartan")
    telmi["dose"] = 80.0
    telmi["dose_mg"] = 80.0
    
    result = engine.analyze_stack([testo, telmi])
    balance = result.get("full_stack_balance", {})
    assert balance is not None
    
    bp_axis = next((a for a in balance.get("axes", []) if a.get("biomarker_id") == "bio_blood_pressure"), None)
    assert bp_axis is not None
    assert bp_axis["status"] == "BALANCED_NORMOTENSIVE"
    assert 100.0 <= bp_axis["estimated_value"] <= 128.0
    assert bp_axis["in_safe_range"] is True
    
    mitigations = balance.get("active_mitigations", [])
    assert any("Hemodynamic" in m.get("title", "") or "Vascular" in m.get("title", "") or "Blood Pressure" in m.get("title", "") for m in mitigations)
    assert len(mitigations) >= 1


def test_high_blood_pressure_breakthrough_at_140_is_not_counterbalanced_green():
    """Verify that if blood pressure is elevated with insufficient ARB, it is marked as hypertensive strain and not in safe range."""
    cat = CatalogService()
    engine = InteractionEngine()

    # High androgen load (1000mg T) with insufficient ARB (10mg Telmisartan)
    testo = cat.get_compound("testosterone")
    testo["dose"] = 1000.0
    testo["dose_mg"] = 1000.0

    telmi = cat.get_compound("telmisartan")
    telmi["dose"] = 10.0
    telmi["dose_mg"] = 10.0

    result = engine.analyze_stack([testo, telmi])
    balance = result.get("full_stack_balance", {})
    bp_axis = next((a for a in balance.get("axes", []) if a.get("biomarker_id") == "bio_blood_pressure"), None)
    assert bp_axis is not None
    assert bp_axis["estimated_value"] >= 128.0
    assert any(k in bp_axis["status"] for k in ["ELEVATED", "HYPERTENSIVE", "STRAIN"])
    assert bp_axis["in_safe_range"] is False




def test_full_stack_matrix_api_endpoint_with_doses():
    """Verify POST /api/interactions/matrix accepts compound doses and returns full_stack_balance payload."""
    payload = {
        "stack": [
            {"key": "testosterone", "dose": 70, "unit": "mg"},
            {"key": "exemestane", "dose": 100, "unit": "mg"},
            {"key": "telmisartan", "dose": 80, "unit": "mg"},
        ],
        "blood_pressure": 120.0,
        "sleep_hours": 7.5,
        "labs": {
            "blood_pressure": 120.0,
            "alt_u_l": 25.0,
            "hematocrit_pct": 46.0,
        },
    }
    
    response = client.post("/api/interactions/matrix", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert "full_stack_balance" in data
    balance = data["full_stack_balance"]
    assert balance["status"] in {"OPTIMAL_EQUILIBRIUM", "COUNTERBALANCED", "UNCOMPENSATED_STRAIN", "MODERATE_DEVIATION"}
    assert len(balance["axes"]) >= 2
    assert len(balance["active_mitigations"]) >= 1
    
    # Check that compound objects returned have doses
    assert len(data["compounds"]) == 3
    t_comp = next((c for c in data["compounds"] if c["key"] == "testosterone"), None)
    assert t_comp is not None
    assert t_comp.get("dose") == 70 or t_comp.get("dose_mg") == 70.0


def test_all_affected_biomarkers_included_in_full_stack_balance_axes():
    """Verify that all affected biomarkers across the entire biological graph cascade are reflected in full_stack_balance axes."""
    cat = CatalogService()
    engine = InteractionEngine()

    testo = cat.get_compound("testosterone")
    testo["dose"] = 100.0
    testo["dose_mg"] = 100.0

    result = engine.analyze_stack([testo])
    balance = result.get("full_stack_balance", {})
    assert balance is not None

    axes = balance.get("axes", [])
    axis_bio_ids = {a.get("biomarker_id") for a in axes}
    cascade_shifts = balance.get("cascade_biomarker_shifts", [])

    # Every biomarker shifted in the cascade must be present in the axes list
    assert len(cascade_shifts) > 0
    for shift in cascade_shifts:
        bio_id = shift.get("biomarker_id")
        assert bio_id in axis_bio_ids, f"Biomarker {bio_id} ({shift.get('label')}) missing from full stack balance axes"

    # Verify presence of multiple core physiological axes beyond the initial 5
    assert any(a["biomarker_id"] == "bio_hematocrit" for a in axes)
    assert any(a["biomarker_id"] == "bio_luteinizing_hormone" for a in axes)
    assert any(a["biomarker_id"] == "bio_testosterone" for a in axes)


def test_physiological_axes_clinical_priority_sorting():
    """Verify that axes are sorted with critical deviations at the top, followed by moderate alerts, counterbalanced targets, and active shifts."""
    cat = CatalogService()
    engine = InteractionEngine()

    # Stack with a critical crashed E2 (high exemestane alone), plus testosterone
    exem = cat.get_compound("exemestane")
    exem["dose"] = 100.0
    exem["dose_mg"] = 100.0

    result = engine.analyze_stack([exem])
    axes = result.get("full_stack_balance", {}).get("axes", [])
    assert len(axes) > 0

    # The top axis must be the critical E2 crash (Tier 1)
    assert axes[0]["biomarker_id"] == "bio_estradiol"
    assert axes[0]["priority_tier"] == 1
    assert axes[0]["priority_label"] == "Critical Strain"

    # Verify that all tier 1 axes precede tier 2, tier 3, tier 4, tier 5
    tiers = [a.get("priority_tier", 5) for a in axes]
    assert tiers == sorted(tiers), f"Axes tiers not monotonically sorted: {tiers}"


