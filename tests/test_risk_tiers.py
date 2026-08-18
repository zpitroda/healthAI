import pytest
from app.services.interaction_engine import InteractionEngine


def test_telmisartan_and_eplerenone_is_critical_severe_risk():
    """Verify that dual RAAS / aldosterone blockade triggers Critical / Severe risk for hyperkalemia."""
    engine = InteractionEngine()
    telmisartan = {
        "key": "telmisartan",
        "name": "Telmisartan",
        "drug_class": "Angiotensin II Receptor Blocker",
        "external_ids": {"atc_codes": ["C09CA07"]},
    }
    eplerenone = {
        "key": "eplerenone",
        "name": "Eplerenone",
        "drug_class": "Aldosterone Antagonist",
        "external_ids": {"atc_codes": ["C03DA04"]},
    }

    result = engine.analyze_stack([telmisartan, eplerenone])
    assert result["risk_band"] in {"SEVERE", "ELEVATED"}
    assert result["cumulative_risk_score"] >= 50
    assert any("Hyperkalemia" in c["title"] for c in result["breakdown"]["receptor_conflicts"])


def test_testosterone_and_hgh_is_not_false_alarm_hypoglycemia():
    """Verify that TRT + Growth Hormone does NOT get falsely marked as high-risk hypoglycemia."""
    engine = InteractionEngine()
    testosterone = {
        "key": "testosterone",
        "name": "Testosterone",
        "drug_class": "Androgen",
        "indications": ["hypogonadism", "insulin resistance"],
        "external_ids": {"atc_codes": ["G03BA03"]},
    }
    hgh = {
        "key": "somatropin",
        "name": "Somatropin",
        "drug_class": "Growth Hormone Receptor Agonist",
        "indications": ["growth failure", "diabetes mellitus"],
        "external_ids": {"atc_codes": ["H01AC01"]},
    }

    result = engine.analyze_stack([testosterone, hgh])
    assert result["risk_band"] in {"MINIMAL", "LOW"}
    assert result["cumulative_risk_score"] <= 25
    # Should NOT have any severe hypoglycemia conflicts or syndrome alerts
    assert not any("Hypoglycemia" in c["title"] for c in result["breakdown"]["receptor_conflicts"])
    assert not any("Hypoglycemia" in s["title"] for s in result["breakdown"]["syndrome_alerts"])
    # Should recognize beneficial / anabolic synergy
    assert any("Synergy" in s["title"] or "Somatotropic" in s["title"] for s in result["breakdown"]["synergistic_benefits"])


def test_exogenous_insulin_and_sulfonylurea_is_critical_hypoglycemia():
    """Verify that dual secretagogues/insulins are accurately classified as Critical Hypoglycemia."""
    engine = InteractionEngine()
    insulin = {
        "key": "insulin_glargine",
        "name": "Insulin Glargine",
        "drug_class": "Exogenous Insulin Agonist",
        "external_ids": {"atc_codes": ["A10AE04"]},
    }
    glimepiride = {
        "key": "glimepiride",
        "name": "Glimepiride",
        "drug_class": "Sulfonylurea",
        "external_ids": {"atc_codes": ["A10BB12"]},
    }

    result = engine.analyze_stack([insulin, glimepiride])
    assert result["risk_band"] in {"SEVERE", "ELEVATED"}
    assert result["cumulative_risk_score"] >= 40
    assert any("Hypoglycemia" in c["title"] for c in result["breakdown"]["receptor_conflicts"])
    assert any("Hypoglycemia" in s["title"] for s in result["breakdown"]["syndrome_alerts"])


def test_metformin_and_sglt2_is_moderate_low_risk_glycemic_optimization():
    """Verify that dual non-secretagogue sensitizers are categorized as Moderate/Low rather than Critical."""
    engine = InteractionEngine()
    metformin = {
        "key": "metformin",
        "name": "Metformin",
        "drug_class": "Biguanide",
        "external_ids": {"atc_codes": ["A10BA02"]},
    }
    empagliflozin = {
        "key": "empagliflozin",
        "name": "Empagliflozin",
        "drug_class": "SGLT2 Inhibitor",
        "external_ids": {"atc_codes": ["A10BK03"]},
    }

    result = engine.analyze_stack([metformin, empagliflozin])
    assert result["risk_band"] in {"MODERATE", "LOW", "MINIMAL"}
    assert result["cumulative_risk_score"] <= 30
    assert not any("Collapse" in s["title"] for s in result["breakdown"]["syndrome_alerts"])


def test_telmisartan_and_nebivolol_is_synergistic_not_hyperkalemia():
    """Verify that Telmisartan (ARB) + Nebivolol (Beta-Blocker) does not falsely trigger hyperkalemia."""
    engine = InteractionEngine()
    telmisartan = {
        "key": "telmisartan",
        "name": "Telmisartan",
        "drug_class": "Angiotensin II Receptor Blocker",
        "external_ids": {"atc_codes": ["C09CA07"]},
    }
    nebivolol = {
        "key": "nebivolol",
        "name": "Nebivolol",
        "drug_class": "Beta-Adrenergic Blocker",
        "synonyms": ["narbivolol", "hypoloc", "bystolic"],
        "external_ids": {"atc_codes": ["C07AB12"]},
    }

    result = engine.analyze_stack([telmisartan, nebivolol])
    # Must NOT have hyperkalemia conflict
    assert not any("Hyperkalemia" in c["title"] for c in result["breakdown"]["receptor_conflicts"])
    assert not any("Hyperkalemia" in s["title"] for s in result["breakdown"]["syndrome_alerts"])
    # Must recognize complementary RAAS + Beta-blocker synergy
    assert any("Synergy" in s["title"] or "Antihypertensive" in s["title"] for s in result["breakdown"]["synergistic_benefits"])
    assert result["conflict_count"] == 0
    assert result["synergy_count"] >= 1
