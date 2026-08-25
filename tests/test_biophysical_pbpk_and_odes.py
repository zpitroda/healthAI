import math
import pytest
from app.schemas.pkpd import PKPDSimulationRequest
from app.services.pkpd_engine import PKPDEngine
from app.services.catalog_service import CatalogService
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_rodgers_rowland_pbpk_tissue_partitions():
    """
    Verify Rodgers-Rowland / Poulin-Theil tissue partition calculations:
    1. Highly lipophilic compound (LogP=4.8) distributes strongly into adipose tissue (Kp_adipose > Kp_muscle).
    2. Hydrophilic compound (LogP=0.16) has low adipose partitioning.
    3. P-gp substrate has reduced brain Kp due to active efflux transport.
    """
    lipophilic_comp = {
        "key": "amiodarone_test",
        "name": "Amiodarone Test",
        "logp": 4.8,
        "pka": 8.7,
        "molecular_weight": 645.3,
        "protein_binding_pct": 96.0,
        "transporters": {"substrates": ["P-gp", "BCRP"]},
    }
    kp_lipo = PKPDEngine.calculate_pbpk_tissue_partitions(lipophilic_comp, fu_adjusted=0.04, weight_kg=75.0)
    assert kp_lipo.kp_adipose > kp_lipo.kp_muscle
    assert kp_lipo.kp_liver > 0.1
    assert kp_lipo.kp_brain > 0.01

    hydrophilic_comp = {
        "key": "atenolol_test",
        "name": "Atenolol Test",
        "logp": 0.16,
        "pka": 9.6,
        "molecular_weight": 266.3,
        "protein_binding_pct": 10.0,
        "transporters": {"substrates": []},
    }
    kp_hydro = PKPDEngine.calculate_pbpk_tissue_partitions(hydrophilic_comp, fu_adjusted=0.90, weight_kg=70.0)
    assert kp_hydro.kp_muscle > kp_hydro.kp_adipose
    assert kp_hydro.kp_adipose < 2.0


def test_henderson_hasselbalch_lysosomal_trapping():
    """
    Verify lysosomal ion-trapping biophysics across pH 4.8 (lysosome) vs pH 7.2 (cytosol):
    1. Strong basic lipophilic drug (pKa=9.5, LogP=4.3) exhibits high R_lyso (> 50).
    2. Acidic drug (pKa=3.5, LogP=1.2) exhibits no lysosomal trapping (R_lyso = 1.0, 100% cytosolic).
    """
    basic_lipophilic = {
        "key": "sertraline_test",
        "name": "Sertraline Test",
        "logp": 4.3,
        "pka": 9.5,
        "drug_class": "SSRI Antidepressant Amine",
    }
    lyso_basic = PKPDEngine.calculate_lysosomal_trapping(basic_lipophilic)
    assert lyso_basic.is_lysosomotropic is True
    assert lyso_basic.lysosomal_accumulation_ratio > 50.0
    assert lyso_basic.cytosolic_free_fraction_pct < 80.0

    acidic_drug = {
        "key": "aspirin_test",
        "name": "Aspirin Test",
        "logp": 1.2,
        "pka": 3.5,
        "drug_class": "NSAID Salicylate Acid",
    }
    lyso_acid = PKPDEngine.calculate_lysosomal_trapping(acidic_drug)
    assert lyso_acid.is_lysosomotropic is False
    assert lyso_acid.lysosomal_accumulation_ratio == 1.0
    assert lyso_acid.cytosolic_free_fraction_pct == 100.0


def test_enzyme_turnover_and_mbi_inactivation_ode():
    """
    Verify continuous ODE tracking of active enzyme fraction E(t)/E0:
    When co-administered with a CYP inhibitor, active enzyme activity drops and dynamically recovers.
    """
    substrate = {
        "key": "midazolam_test",
        "name": "Midazolam Test",
        "cyp_enzymes": {"substrates": ["CYP3A4"]},
        "half_life_hours": 2.5,
        "volume_of_distribution": 1.0,
        "bioavailability_f": 0.5,
        "logp": 3.1,
    }
    inhibitor = {
        "key": "ketoconazole_test",
        "name": "Ketoconazole Test",
        "cyp_enzymes": {"inhibitors": ["CYP3A4"]},
        "dose_mg": 200.0,
        "dosing_interval_h": 24.0,
        "half_life_hours": 8.0,
        "volume_of_distribution": 1.5,
        "bioavailability_f": 0.8,
        "logp": 4.3,
    }

    req = PKPDSimulationRequest(
        compound_key="midazolam_test",
        dose_mg=10.0,
        dosing_interval_h=24.0,
        simulation_duration_h=48.0,
        steady_state=False,
    )
    res = PKPDEngine.simulate(substrate, req, co_compounds_data=[inhibitor])

    # Verify active enzyme fraction in time series
    min_enzyme = min(pt.active_enzyme_fraction_pct for pt in res.time_series)
    assert min_enzyme < 100.0
    # Terminal enzyme activity recovers over time
    terminal_enzyme = res.time_series[-1].active_enzyme_fraction_pct
    assert terminal_enzyme > min_enzyme


def test_receptor_tolerance_and_tachyphylaxis_ode():
    """
    Verify continuous receptor internalization ODE:
    High continuous receptor occupancy decreases functional surface receptor density R_surf(t)/R0.
    """
    agonist = {
        "key": "albuterol_test",
        "name": "Albuterol Test",
        "half_life_hours": 4.0,
        "volume_of_distribution": 2.5,
        "bioavailability_f": 0.8,
        "logp": 0.6,
        "pka": 9.3,
        "receptor_targets": [{"target": "Beta-2 Adrenergic Receptor", "action": "agonist", "affinity_nm": 20.0}],
    }
    req = PKPDSimulationRequest(
        compound_key="albuterol_test",
        dose_mg=50.0,  # High dose to drive maximum receptor occupancy
        dosing_interval_h=6.0,
        simulation_duration_h=48.0,
        steady_state=True,
        enable_receptor_tolerance=True,
    )
    res = PKPDEngine.simulate(agonist, req)

    assert res.tachyphylaxis_tolerance_active is True
    min_r_surf = min(pt.surface_receptor_density_pct for pt in res.time_series)
    assert min_r_surf < 98.0, f"Expected receptor desensitization. Min R_surf was {min_r_surf}%"


def test_pbpk_simulation_api_endpoint():
    """Verify FastAPI endpoint /api/pkpd/simulate returns full PBPK tissue time series and biophysical metrics."""
    res = client.post(
        "/api/pkpd/simulate",
        json={
            "compound_key": "caffeine",
            "dose_mg": 200.0,
            "dosing_interval_h": 24.0,
            "simulation_duration_h": 48.0,
            "route": "oral",
            "steady_state": True,
            "enable_pbpk_tissues": True,
            "enable_receptor_tolerance": True,
            "circadian_dosing_time_h": 8.0,
        }
    )
    assert res.status_code == 200
    data = res.json()

    assert "tissue_partition_coefficients" in data
    kp = data["tissue_partition_coefficients"]
    assert "kp_brain" in kp
    assert "kp_liver" in kp
    assert "kp_adipose" in kp

    assert "lysosomal_trapping" in data
    assert "tachyphylaxis_tolerance_active" in data
    assert data["tachyphylaxis_tolerance_active"] is True

    # Check time series points have tissue concentrations
    first_pt = data["time_series"][10]
    assert "c_brain_ng_ml" in first_pt
    assert "c_liver_ng_ml" in first_pt
    assert "surface_receptor_density_pct" in first_pt
    assert "active_enzyme_fraction_pct" in first_pt
