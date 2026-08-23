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
