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


def test_two_compartment_open_model_distribution_phases():
    """Verify 2-compartment open models (alpha-distribution & beta-elimination) for lipophilic drugs."""
    amiodarone = {
        "key": "amiodarone",
        "name": "Amiodarone",
        "t_half_numeric": 120.0,
        "bioavailability_f": 0.50,
        "volume_of_distribution_l_kg": 60.0,
        "clearance_l_h_kg": 0.15,
    }
    req = PKPDSimulationRequest(
        compound_key="amiodarone",
        dose_mg=200.0,
        dosing_interval_h=24.0,
        simulation_duration_h=72.0,
        steady_state=False,
    )
    res = PKPDEngine.simulate(amiodarone, req)

    assert res.number_of_compartments == 2
    assert len(res.time_series) > 50

    # Tissue concentration should be populated
    tissue_concs = [pt.c_tissue_ng_ml for pt in res.time_series if pt.c_tissue_ng_ml is not None]
    assert len(tissue_concs) == len(res.time_series)

    # In alpha phase, tissue concentration rises as drug distributes into peripheral compartment
    max_tissue = max(tissue_concs)
    assert max_tissue > 0.0
    # Tissue peak should occur after initial plasma absorption
    peak_tissue_pt = min(res.time_series, key=lambda p: abs((p.c_tissue_ng_ml or 0.0) - max_tissue))
    assert peak_tissue_pt.time_h > 0.0


def test_michaelis_menten_saturable_kinetics():
    """Verify Michaelis-Menten capacity-limited saturable elimination for Phenytoin and Ethanol."""
    phenytoin = {
        "key": "phenytoin",
        "name": "Phenytoin",
        "t_half_numeric": 22.0,
        "bioavailability_f": 0.90,
        "volume_of_distribution_l_kg": 0.70,
        "is_saturable_elimination": True,
        "vmax_mg_h_kg": 0.30,
        "km_ng_ml": 4000.0,
    }

    # Standard dose
    req_std = PKPDSimulationRequest(
        compound_key="phenytoin",
        dose_mg=200.0,
        dosing_interval_h=24.0,
        simulation_duration_h=48.0,
        steady_state=False,
    )
    res_std = PKPDEngine.simulate(phenytoin, req_std)

    # High saturating dose (3x dose)
    req_high = PKPDSimulationRequest(
        compound_key="phenytoin",
        dose_mg=600.0,
        dosing_interval_h=24.0,
        simulation_duration_h=48.0,
        steady_state=False,
    )
    res_high = PKPDEngine.simulate(phenytoin, req_high)

    assert res_std.is_saturable_elimination is True
    assert res_high.is_saturable_elimination is True

    # Under saturable kinetics, 3x dose results in > 3x AUC due to clearance saturation
    assert res_high.auc_0_tau_ng_h_ml > (3.0 * res_std.auc_0_tau_ng_h_ml)


def test_time_resolved_dynamic_ddi_collisions():
    """Verify time-resolved dynamic DDI collision modeling I(t) and instantaneous clearance CL(t)."""
    simvastatin = {
        "key": "simvastatin",
        "name": "Simvastatin",
        "t_half_numeric": 3.0,
        "bioavailability_f": 0.05,
        "volume_of_distribution_l_kg": 3.0,
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
    }
    ketoconazole = {
        "key": "ketoconazole",
        "name": "Ketoconazole",
        "t_half_numeric": 8.0,
        "bioavailability_f": 0.80,
        "volume_of_distribution_l_kg": 2.0,
        "cyp_enzymes": {"substrates": [], "inhibitors": ["CYP3A4"], "inducers": []},
    }

    req = PKPDSimulationRequest(
        compound_key="simvastatin",
        dose_mg=20.0,
        dosing_interval_h=24.0,
        simulation_duration_h=48.0,
        co_administered_compounds=["ketoconazole"],
    )

    res = PKPDEngine.simulate(simvastatin, req, co_compounds_data=[ketoconazole])

    assert res.dynamic_ddi_active is True

    # Check continuous time-resolved inhibitor I(t) and dynamic clearance CL(t)
    inhibitor_concs = [pt.inhibitor_conc_ng_ml for pt in res.time_series if pt.inhibitor_conc_ng_ml is not None]
    clearances = [pt.cl_instantaneous_l_h for pt in res.time_series if pt.cl_instantaneous_l_h is not None]

    assert len(inhibitor_concs) > 0
    assert len(clearances) == len(res.time_series)
    assert max(inhibitor_concs) > 0.0

    # Clearance should fluctuate over time as inhibitor concentration rises and falls
    assert min(clearances) < max(clearances)


def test_steady_state_fluctuation_metrics():
    """Verify PTF, peak-to-trough ratio, and fluctuation risk levels across dosing frequencies."""
    testosterone_cypionate = {
        "key": "testosterone_cypionate",
        "name": "Testosterone Cypionate",
        "t_half_numeric": 120.0,  # 5 days
        "bioavailability_f": 1.0,
        "volume_of_distribution_l_kg": 1.0,
        "absorption_rate_ka": 0.05,
    }

    # Infrequent dosing (every 14 days / 336h or weekly 168h with short absorption) -> fluctuation
    req_infrequent = PKPDSimulationRequest(
        compound_key="testosterone_cypionate",
        dose_mg=200.0,
        dosing_interval_h=336.0,
        simulation_duration_h=336.0,
        steady_state=True,
    )
    res_infreq = PKPDEngine.simulate(testosterone_cypionate, req_infrequent)
    assert res_infreq.fluctuation_pct > 80.0
    assert res_infreq.peak_to_trough_ratio is not None and res_infreq.peak_to_trough_ratio > 2.0
    assert res_infreq.fluctuation_risk_level in ("HIGH", "VOLATILE")
    assert res_infreq.fluctuation_warning is not None

    # Micro-dosed split schedule (every 3.5 days / 84h) -> stable
    req_split = PKPDSimulationRequest(
        compound_key="testosterone_cypionate",
        dose_mg=50.0,
        dosing_interval_h=84.0,
        simulation_duration_h=168.0,
        steady_state=True,
    )
    res_split = PKPDEngine.simulate(testosterone_cypionate, req_split)
    assert res_split.fluctuation_pct < res_infreq.fluctuation_pct
    assert res_split.peak_to_trough_ratio < res_infreq.peak_to_trough_ratio
    assert res_split.fluctuation_risk_level in ("STABLE", "MODERATE")

