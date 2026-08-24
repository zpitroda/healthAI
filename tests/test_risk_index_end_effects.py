import pytest
from app.services.catalog_service import CatalogService
from app.services.interaction_engine import InteractionEngine


def test_elevated_testosterone_with_managed_downstream_markers_is_minimal_risk():
    """
    Verify that elevated serum total testosterone (e.g. 1500 ng/dL) does NOT trigger high risk
    or uncompensated risk alerts when downstream markers (blood pressure, lipids, hematocrit, E2) are managed.
    """
    cat = CatalogService()
    engine = InteractionEngine()
    testosterone = cat.get_compound("testosterone_cypionate")

    profile_managed = {
        "labs": {
            "bio_testosterone": 1500.0,
            "testosterone_ng_dl": 1500.0,
            "blood_pressure": 118.0,
            "hdl_c_mg_dl": 55.0,
            "ldl_mg_dl": 90.0,
            "apob_mg_dl": 75.0,
            "hematocrit_pct": 45.0,
            "estradiol_pg_ml": 28.0,
        }
    }

    result = engine.analyze_stack([testosterone], profile=profile_managed)

    assert result["risk_band"] in {"MINIMAL", "LOW"}
    assert result["cumulative_risk_score"] <= 15
    assert len(result["breakdown"]["biomarker_warnings"]) == 0


def test_testosterone_with_pitavastatin_and_telmisartan_registers_active_mitigations():
    """
    Verify that TRT co-administered with Pitavastatin (lipid protection) and Telmisartan (BP control)
    registers active mitigations for lipid and vascular axes, yielding a low cumulative risk score.
    """
    cat = CatalogService()
    engine = InteractionEngine()

    testosterone = cat.get_compound("testosterone_cypionate")
    pitavastatin = cat.get_compound("pitavastatin")
    telmisartan = cat.get_compound("telmisartan")

    result = engine.analyze_stack([testosterone, pitavastatin, telmisartan])

    active_mitigations = result["breakdown"].get("active_mitigations") or []
    mitigation_titles = [m.get("title", "") for m in active_mitigations if isinstance(m, dict)]

    assert any("Lipid Protection" in t or "Endothelial" in t for t in mitigation_titles)
    assert any("Hemodynamic" in t or "Vascular Counterbalance" in t for t in mitigation_titles)
    assert result["risk_band"] in {"MINIMAL", "LOW"}
    assert result["cumulative_risk_score"] <= 20


def test_elevated_testosterone_with_unmanaged_downstream_markers_flags_specific_end_effects():
    """
    Verify that elevated testosterone with unmanaged downstream markers (high BP, suppressed HDL, elevated LDL, high hematocrit)
    triggers specific end-effect biomarker warnings for lipid disruption, hypertensive strain, and viscosity.
    """
    cat = CatalogService()
    engine = InteractionEngine()

    testosterone = cat.get_compound("testosterone_cypionate")

    profile_unmanaged = {
        "labs": {
            "bio_testosterone": 1500.0,
            "testosterone_ng_dl": 1500.0,
            "blood_pressure": 145.0,
            "hdl_c_mg_dl": 28.0,
            "ldl_mg_dl": 160.0,
            "hematocrit_pct": 54.0,
            "estradiol_pg_ml": 65.0,
        }
    }

    result = engine.analyze_stack([testosterone], profile=profile_unmanaged)

    assert result["risk_band"] in {"MODERATE", "ELEVATED", "SEVERE"}
    assert result["cumulative_risk_score"] >= 35

    biomarker_warnings = result["breakdown"]["biomarker_warnings"]
    warning_titles = [w.get("title", "") for w in biomarker_warnings]

    assert any("Lipid" in t or "Atherogenic" in t for t in warning_titles)
    assert any("Hypertensive" in t or "Blood Pressure" in t for t in warning_titles)
    assert any("Viscosity" in t or "Hematocrit" in t for t in warning_titles)
