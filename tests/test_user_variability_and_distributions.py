from __future__ import annotations

import pytest
from app.schemas.pkpd import PKPDSimulationRequest
from app.services.pkpd_engine import PKPDEngine
from app.services.catalog_service import CatalogService


def test_user_variability_biometric_scaling():
    """Verify sex, age, height, and weight alter PK/PD parameter scaling and metrics."""
    service = CatalogService()
    compound = service.get_compound("telmisartan") or {
        "key": "telmisartan",
        "name": "Telmisartan",
        "t_half_numeric": 24.0,
        "volume_of_distribution_l_kg": 7.0,
        "renal_clearance_fraction": 0.05,
    }

    # Young male baseline (70kg, 175cm, age 25)
    req_male = PKPDSimulationRequest(
        compound_key="telmisartan",
        dose_mg=40.0,
        sex="male",
        age=25,
        weight_kg=70.0,
        height_cm=175.0,
        steady_state=True,
    )
    res_male = PKPDEngine.simulate(compound, req_male)

    # Older female (55kg, 160cm, age 70)
    req_female = PKPDSimulationRequest(
        compound_key="telmisartan",
        dose_mg=40.0,
        sex="female",
        age=70,
        weight_kg=55.0,
        height_cm=160.0,
        steady_state=True,
    )
    res_female = PKPDEngine.simulate(compound, req_female)

    # Verify biometrics captured in response
    assert res_male.patient_biometrics["sex"] == "male"
    assert res_male.patient_biometrics["lean_body_mass_kg"] > 0
    assert res_female.patient_biometrics["sex"] == "female"
    assert res_female.patient_biometrics["lean_body_mass_kg"] < res_male.patient_biometrics["lean_body_mass_kg"]

    # Exposure (Cmax & AUC) should be higher in lower weight / older female due to lower volume of distribution and age-related clearance reduction
    assert res_female.c_max_ng_ml > res_male.c_max_ng_ml
    assert res_female.auc_0_tau_ng_h_ml > res_male.auc_0_tau_ng_h_ml


def test_population_variability_distribution_curves():
    """Verify log-normal distribution curves (p5, p25, p50, p75, p95) are calculated for PK metrics and time series."""
    service = CatalogService()
    compound = service.get_compound("caffeine") or {
        "key": "caffeine",
        "name": "Caffeine",
        "t_half_numeric": 5.0,
        "volume_of_distribution_l_kg": 0.6,
    }

    req = PKPDSimulationRequest(
        compound_key="caffeine",
        dose_mg=200.0,
        sex="male",
        age=30,
        weight_kg=80.0,
        height_cm=180.0,
        steady_state=True,
    )
    res = PKPDEngine.simulate(compound, req)

    # Check metric distribution objects
    for metric_dist in [res.c_max_distribution, res.c_avg_distribution, res.auc_distribution, res.clearance_distribution, res.half_life_distribution]:
        assert metric_dist.percentiles.p5 < metric_dist.percentiles.p25
        assert metric_dist.percentiles.p25 < metric_dist.percentiles.p50
        assert metric_dist.percentiles.p50 < metric_dist.percentiles.p75
        assert metric_dist.percentiles.p75 < metric_dist.percentiles.p95
        assert metric_dist.std_dev > 0

    # Check time-series point percentile distribution
    tp = res.time_series[10]
    assert tp.c_plasma_distribution is not None
    assert tp.c_plasma_distribution.p5 <= tp.c_plasma_distribution.p25 <= tp.c_plasma_distribution.p50 <= tp.c_plasma_distribution.p75 <= tp.c_plasma_distribution.p95
    assert tp.effect_distribution is not None
    assert tp.effect_distribution.p5 <= tp.effect_distribution.p25 <= tp.effect_distribution.p50 <= tp.effect_distribution.p75 <= tp.effect_distribution.p95


def test_missing_biometrics_widens_distribution_curves():
    """Verify that leaving biometric fields blank (None) expands distribution percentile bands due to unknown uncertainty."""
    service = CatalogService()
    compound = service.get_compound("caffeine") or {
        "key": "caffeine",
        "name": "Caffeine",
        "t_half_numeric": 5.0,
        "volume_of_distribution_l_kg": 0.6,
    }

    # Fully specified biometrics
    req_known = PKPDSimulationRequest(
        compound_key="caffeine",
        dose_mg=200.0,
        sex="male",
        age=30,
        weight_kg=70.0,
        height_cm=175.0,
        steady_state=True,
    )
    res_known = PKPDEngine.simulate(compound, req_known)

    # Completely blank/unspecified biometrics
    req_unknown = PKPDSimulationRequest(
        compound_key="caffeine",
        dose_mg=200.0,
        sex=None,
        age=None,
        weight_kg=None,
        height_cm=None,
        steady_state=True,
    )
    res_unknown = PKPDEngine.simulate(compound, req_unknown)

    # Compare distribution widths (p95 - p5)
    known_width = res_known.c_max_distribution.percentiles.p95 - res_known.c_max_distribution.percentiles.p5
    unknown_width = res_unknown.c_max_distribution.percentiles.p95 - res_unknown.c_max_distribution.percentiles.p5

    assert res_unknown.patient_biometrics["unknown_biometrics_count"] == 4
    assert unknown_width > known_width * 1.5  # Significantly wider uncertainty band


def test_cascade_biometric_and_lab_calibration():
    """Verify that propagate_cascade accepts personal biometrics and lab inputs to calibrate baselines and outcome distribution curves."""
    from app.services.graph_service import build_selected_compound_graph
    from app.services.interaction_engine import InteractionEngine

    graph = build_selected_compound_graph(["telmisartan", "testosterone"])

    # 1. Simulate with default (unspecified) biometrics & labs
    res_default = graph.propagate_cascade(["telmisartan", "testosterone"])
    assert "biomarker_shifts" in res_default
    assert "phenotypes" in res_default

    # Verify distribution objects on default result
    for b in res_default["biomarker_shifts"]:
        dist = b.get("distribution")
        assert dist is not None
        assert "p5" in dist and "p95" in dist
        assert dist["p5"] <= dist["p25"] <= dist["p50"] <= dist["p75"] <= dist["p95"]

    for p in res_default["phenotypes"]:
        dist = p.get("distribution")
        assert dist is not None
        assert "p5" in dist and "p95" in dist
        assert "p5_p95_range_str" in p

    # 2. Simulate with user-provided lab baselines (e.g. ALT=65 U/L, BP=135 mmHg)
    user_labs = {"alt_u_l": 65.0, "blood_pressure": 135.0}
    user_biometrics = {"sex": "male", "age": 45, "weight_kg": 90.0, "height_cm": 180.0}
    res_calibrated = graph.propagate_cascade(
        ["telmisartan", "testosterone"],
        patient_biometrics=user_biometrics,
        user_labs=user_labs,
    )

    alt_shift = next((b for b in res_calibrated["biomarker_shifts"] if b["biomarker_id"] == "bio_alt"), None)
    if alt_shift:
        assert alt_shift["baseline_value"] == 65.0  # Personalized lab baseline applied
        assert alt_shift["user_baseline_calibrated"] is True


def test_full_stack_balance_distribution_curves_and_biometrics():
    """Verify Holistic Stack Equilibrium panel returns distribution percentile curves (p5-p95) for all axes and scales CV on unknown biometrics."""
    from app.services.interaction_engine import InteractionEngine

    engine = InteractionEngine()
    compounds = [
        {"key": "testosterone", "name": "Testosterone", "dose": 100, "unit": "mg", "frequency": "weekly"},
        {"key": "telmisartan", "name": "Telmisartan", "dose": 40, "unit": "mg", "frequency": "daily"},
    ]

    # Full biometrics provided
    profile_known = {
        "sex": "male",
        "age": 35,
        "weight_kg": 80.0,
        "height_cm": 182.0,
        "labs": {"alt_u_l": 30.0, "blood_pressure": 122.0},
    }
    analysis_known = engine.analyze_stack(compounds, profile=profile_known)
    balance_known = analysis_known.get("full_stack_balance", {})

    assert "axes" in balance_known
    assert len(balance_known["axes"]) > 0
    assert balance_known["patient_biometrics"]["unknown_biometrics_count"] == 0

    axis_known = balance_known["axes"][0]
    assert "distribution" in axis_known
    dist_k = axis_known["distribution"]
    assert dist_k["p5"] <= dist_k["p25"] <= dist_k["p50"] <= dist_k["p75"] <= dist_k["p95"]

    # Unknown biometrics
    profile_unknown = {"sex": None, "age": None, "weight_kg": None, "height_cm": None}
    analysis_unknown = engine.analyze_stack(compounds, profile=profile_unknown)
    balance_unknown = analysis_unknown.get("full_stack_balance", {})

    assert balance_unknown["patient_biometrics"]["unknown_biometrics_count"] == 4
    axis_un = next((a for a in balance_unknown["axes"] if a["name"] == axis_known["name"]), balance_unknown["axes"][0])

    width_known = dist_k["p95"] - dist_k["p5"]
    width_unknown = axis_un["distribution"]["p95"] - axis_un["distribution"]["p5"]
    assert width_unknown >= width_known  # Uncertainty band expands when biometrics are unknown


def test_demographic_calibrated_reference_ranges():
    """Verify reference ranges (safe_lower, safe_upper) adjust dynamically based on sex (female vs male), age, and BMI, defaulting to general healthy population when unspecified."""
    from app.knowledge_graph.graph import get_demographic_calibrated_reference_range

    # 1. Unspecified sex / no biometrics -> General Healthy Population Default (15.0 - 1000.0 ng/dL for Total Testosterone)
    t_base_gen, t_low_gen, t_high_gen, t_adj_gen = get_demographic_calibrated_reference_range("bio_testosterone", None, 350.0, 15.0, 1000.0)
    assert t_base_gen == 350.0
    assert t_low_gen == 15.0
    assert t_high_gen == 1000.0
    assert len(t_adj_gen) == 0

    # 2. Male sex reference range calibration for Total Testosterone (300-1000 ng/dL)
    male_bio = {"sex": "male", "age": 30, "weight_kg": 75.0, "height_cm": 178.0}
    t_base_m, t_low_m, t_high_m, t_adj_m = get_demographic_calibrated_reference_range("bio_testosterone", male_bio, 350.0, 15.0, 1000.0)
    assert t_base_m == 550.0
    assert t_low_m == 300.0
    assert t_high_m == 1000.0
    assert any("Male Sex" in a for a in t_adj_m)

    # 3. Female sex reference range calibration for Total Testosterone (15-70 ng/dL) and Estradiol (30-200 pg/mL)
    female_bio = {"sex": "female", "age": 28, "weight_kg": 60.0, "height_cm": 165.0}
    t_base_f, t_low_f, t_high_f, t_adj_f = get_demographic_calibrated_reference_range("bio_testosterone", female_bio, 350.0, 15.0, 1000.0)
    assert t_base_f == 35.0
    assert t_low_f == 15.0
    assert t_high_f == 70.0
    assert any("Female Sex" in a for a in t_adj_f)

    e2_base, e2_low, e2_high, e2_adj = get_demographic_calibrated_reference_range("bio_estradiol", female_bio, 35.0, 15.0, 200.0)
    assert e2_low == 30.0
    assert e2_high == 200.0

    # 4. Male senior age (68y) reference range calibration for eGFR and Systolic BP
    senior_bio = {"sex": "male", "age": 68, "weight_kg": 78.0, "height_cm": 175.0}
    egfr_base, egfr_low, egfr_high, egfr_adj = get_demographic_calibrated_reference_range("bio_egfr", senior_bio, 105.0, 60.0, 130.0)
    assert egfr_base < 100.0  # Age-related GFR decline accounted for
    assert any("Age" in a for a in egfr_adj)

    bp_base, bp_low, bp_high, bp_adj = get_demographic_calibrated_reference_range("bio_blood_pressure", senior_bio, 120.0, 90.0, 120.0)
    assert bp_high == 130.0
    assert any("Senior Age" in a for a in bp_adj)

