import pytest
from app.services.pkpd_engine import PKPDEngine
from app.schemas.pkpd import PKPDSimulationRequest


def test_pk_parameter_extraction():
    compound = {
        "key": "telmisartan",
        "name": "Telmisartan",
        "t_half_numeric": 24.0,
        "bioavailability_f": 0.5,
        "volume_of_distribution_l_kg": 7.1,
        "clearance_l_h_kg": 0.20,
        "protein_binding_pct": 99.5,
        "fraction_unbound": 0.005,
        "absorption_rate_ka": 1.4,
        "mec_ng_ml": 5.0,
        "mtc_ng_ml": 200.0,
    }
    pk = PKPDEngine.extract_pk_parameters(compound)
    pd_p = PKPDEngine.extract_pd_parameters(compound)
    assert pk.t_half_h == 24.0
    assert pk.bioavailability_f == 0.5
    assert pk.volume_of_distribution_l_kg == 7.1
    assert pk.fraction_unbound == 0.005
    assert pd_p.mec_ng_ml == 5.0
    assert pd_p.mtc_ng_ml == 200.0


def test_pk_simulation_single_oral_dose():
    compound = {
        "key": "telmisartan",
        "name": "Telmisartan",
        "t_half_numeric": 24.0,
        "bioavailability_f": 0.5,
        "volume_of_distribution_l_kg": 7.1,
        "protein_binding_pct": 99.5,
        "fraction_unbound": 0.005,
        "absorption_rate_ka": 1.4,
    }
    req = PKPDSimulationRequest(
        compound_key="telmisartan",
        dose_mg=40.0,
        dosing_interval_h=24.0,
        simulation_duration_h=48.0,
        steady_state=False,
    )
    res = PKPDEngine.simulate(compound, req)
    assert res.c_max_ng_ml > 0
    assert res.t_max_h > 0
    assert len(res.time_series) > 50
    # First point at t=0 for single oral dose should be 0 ng/mL
    assert res.time_series[0].c_plasma_ng_ml == 0.0
    # Free concentration should scale by fraction unbound
    assert abs(res.time_series[10].c_free_ng_ml - res.time_series[10].c_plasma_ng_ml * 0.005) <= 0.05


def test_pk_simulation_steady_state():
    compound = {
        "key": "telmisartan",
        "name": "Telmisartan",
        "t_half_numeric": 24.0,
        "bioavailability_f": 0.5,
        "volume_of_distribution_l_kg": 7.1,
        "protein_binding_pct": 99.5,
        "fraction_unbound": 0.005,
        "absorption_rate_ka": 1.4,
    }
    req = PKPDSimulationRequest(
        compound_key="telmisartan",
        dose_mg=40.0,
        dosing_interval_h=24.0,
        simulation_duration_h=48.0,
        steady_state=True,
    )
    res = PKPDEngine.simulate(compound, req)
    assert res.accumulation_ratio > 1.0
    assert res.c_min_trough_ng_ml > 0
    # At steady state, t=0 concentration is equal to trough Cmin
    assert res.time_series[0].c_plasma_ng_ml == pytest.approx(res.c_min_trough_ng_ml, rel=1e-2)


def test_ddi_aucr_and_cmax_shift():
    substrate = {
        "key": "simvastatin",
        "name": "Simvastatin",
        "t_half_numeric": 3.0,
        "bioavailability_f": 0.05,
        "volume_of_distribution_l_kg": 3.0,
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
    }
    inhibitor = {
        "key": "ketoconazole",
        "name": "Ketoconazole",
        "cyp_enzymes": {"substrates": [], "inhibitors": ["CYP3A4"], "inducers": []},
    }
    aucr, cmax_m, interactions = PKPDEngine.calculate_ddi_shift(substrate, [inhibitor])
    assert aucr > 2.0  # Strong CYP3A4 inhibition elevates simvastatin AUC
    assert cmax_m > 1.0
    assert len(interactions) >= 1

    # Simulate with co-administered inhibitor
    req = PKPDSimulationRequest(
        compound_key="simvastatin",
        dose_mg=20.0,
        co_administered_compounds=["ketoconazole"],
    )
    res = PKPDEngine.simulate(substrate, req, co_compounds_data=[inhibitor])
    assert res.ddi_auc_ratio > 2.0
    assert res.elimination_half_life_effective_h > substrate["t_half_numeric"]


def test_sigmoidal_hill_pd_and_biometric_scaling():
    compound = {
        "key": "atorvastatin",
        "name": "Atorvastatin",
        "t_half_numeric": 14.0,
        "bioavailability_f": 0.20,
        "volume_of_distribution_l_kg": 5.4,
        "fraction_unbound": 0.02,
        "e_max": 100.0,
        "ec50_nm": 5.0,
        "hill_coefficient": 1.0,
        "renal_clearance_fraction": 0.02,
    }
    # Severe renal impairment should have minimal effect on Atorvastatin (primarily biliary)
    req_normal = PKPDSimulationRequest(compound_key="atorvastatin", egfr_ml_min=90.0)
    res_normal = PKPDEngine.simulate(compound, req_normal)

    req_renal = PKPDSimulationRequest(compound_key="atorvastatin", egfr_ml_min=15.0)
    res_renal = PKPDEngine.simulate(compound, req_renal)

    # Renal clearance is only 2%, so half life should only increase slightly (< 5%)
    assert res_renal.elimination_half_life_effective_h <= res_normal.elimination_half_life_effective_h * 1.05
    # Verify PD effect values are bounded [0, 100]
    for pt in res_normal.time_series:
        assert 0.0 <= pt.effect_pct <= 100.0
