import pytest
from app.services.interaction_engine import InteractionEngine


def test_empty_stack_returns_zero_risk():
    engine = InteractionEngine()
    result = engine.analyze_stack([])
    assert result["cumulative_risk_score"] == 0
    assert result["risk_band"] == "MINIMAL"
    assert result["conflict_count"] == 0
    assert result["matrix"] == []


def test_caffeine_and_theanine_synergy_detected():
    engine = InteractionEngine()
    caffeine = {
        "key": "caffeine",
        "name": "Caffeine",
        "synergies": [{"partner": "theanine", "effect": "Cognitive Focus"}],
        "cyp_enzymes": {"substrates": ["CYP1A2"], "inhibitors": ["CYP1A2"], "inducers": []},
        "organ_burdens": {"cns_stimulant": "high", "cardiovascular": "moderate"},
    }
    theanine = {
        "key": "theanine",
        "name": "L-Theanine",
        "synergies": [],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"sedative": "low"},
    }

    result = engine.analyze_stack([caffeine, theanine])
    assert result["synergy_count"] >= 1
    assert result["cumulative_risk_score"] <= 15
    assert result["risk_band"] in {"MINIMAL", "LOW"}

    assert len(result["matrix"]) == 2
    assert len(result["matrix"][0]) == 2
    cell_01 = result["matrix"][0][1]
    cell_10 = result["matrix"][1][0]
    assert cell_01["severity"] == "SYNERGISTIC"
    assert cell_10["severity"] == "SYNERGISTIC"


def test_caffeine_and_yohimbine_dual_stimulant_high_risk_collision():
    from app.services.catalog_service import CatalogService
    cat = CatalogService()
    engine = InteractionEngine()
    caffeine = cat.get_compound("caffeine")
    yohimbine = cat.get_compound("yohimbine")

    result = engine.analyze_stack([caffeine, yohimbine])
    assert result["synergy_count"] == 0
    assert len(result["breakdown"]["synergistic_benefits"]) == 0
    assert len(result["breakdown"]["receptor_conflicts"]) >= 1
    assert result["matrix"][0][1]["severity"] == "HIGH_RISK"
    assert result["matrix"][1][0]["severity"] == "HIGH_RISK"
    assert result["matrix"][0][1]["title"] == "Dual Stimulant Sympathetic Hyper-Activation"
    assert result["matrix"][1][0]["title"] == "Dual Stimulant Sympathetic Hyper-Activation"


def test_cyp_collision_between_inhibitor_and_substrate():
    engine = InteractionEngine()
    inhibitor = {
        "key": "berberine",
        "name": "Berberine",
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": ["CYP3A4", "CYP2D6"], "inducers": []},
        "organ_burdens": {"hepatic": "moderate"},
    }
    substrate = {
        "key": "simvastatin",
        "name": "Simvastatin",
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "moderate"},
    }

    result = engine.analyze_stack([inhibitor, substrate])
    assert len(result["breakdown"]["cyp_conflicts"]) >= 1
    cyp_conflict = result["breakdown"]["cyp_conflicts"][0]
    assert "CYP3A4" in cyp_conflict["affected_targets"]
    assert cyp_conflict["severity"] == "HIGH_RISK"


def test_transporter_collision_detected():
    engine = InteractionEngine()
    verapamil = {
        "key": "verapamil",
        "name": "Verapamil",
        "transporters": {"substrates": ["P-gp"], "inhibitors": ["P-gp"], "inducers": []},
        "organ_burdens": {"cardiovascular": "high"},
    }
    digoxin = {
        "key": "digoxin",
        "name": "Digoxin",
        "transporters": {"substrates": ["P-gp"], "inhibitors": [], "inducers": []},
        "is_narrow_therapeutic_index": True,
        "organ_burdens": {"cardiovascular": "high"},
    }

    result = engine.analyze_stack([verapamil, digoxin])
    assert len(result["breakdown"]["transporter_conflicts"]) >= 1
    assert any("P-gp" in c["affected_targets"] for c in result["breakdown"]["transporter_conflicts"])


def test_serotonin_syndrome_detected():
    engine = InteractionEngine()
    fluoxetine = {
        "key": "fluoxetine",
        "name": "Fluoxetine",
        "drug_class": "SSRI antidepressant",
        "mechanism": "Selective serotonin reuptake inhibitor",
    }
    tramadol = {
        "key": "tramadol",
        "name": "Tramadol",
        "drug_class": "Opioid / Serotonin releaser",
        "mechanism": "Mu-opioid agonist and 5-HT reuptake inhibitor",
    }

    result = engine.analyze_stack([fluoxetine, tramadol])
    assert any("Serotonin" in s["syndrome"] for s in result["breakdown"]["syndrome_alerts"])
    assert result["cumulative_risk_score"] >= 25


def test_renal_triple_whammy_detected():
    engine = InteractionEngine()
    lisinopril = {"key": "lisinopril", "name": "Lisinopril", "drug_class": "ACE Inhibitor", "mechanism": "Inhibits ACE"}
    ibuprofen = {"key": "ibuprofen", "name": "Ibuprofen", "drug_class": "NSAID", "mechanism": "Inhibits COX-1 and COX-2"}
    furosemide = {"key": "furosemide", "name": "Furosemide", "drug_class": "Loop Diuretic", "mechanism": "Inhibits Na-K-2Cl cotransporter"}

    result = engine.analyze_stack([lisinopril, ibuprofen, furosemide])
    assert any("Triple Whammy" in s["syndrome"] for s in result["breakdown"]["syndrome_alerts"])
    assert result["risk_band"] in {"ELEVATED", "SEVERE"}


def test_comprehensive_biomarker_warnings():
    engine = InteractionEngine()
    telmisartan = {
        "key": "telmisartan",
        "name": "Telmisartan",
        "drug_class": "ARB",
        "organ_burdens": {"renal": "moderate", "cardiovascular": "high"},
    }

    profile = {
        "labs": {
            "potassium_meq_l": 5.4,
            "egfr": 42.0,
            "alt_u_l": 82.0,
            "blood_pressure": 150.0,
        }
    }

    result = engine.analyze_stack([telmisartan], profile=profile)
    warnings = result["breakdown"]["biomarker_warnings"]
    assert len(warnings) >= 2
    assert any("Potassium" in w["biomarker"] for w in warnings)
    assert any("eGFR" in w["biomarker"] for w in warnings)


def test_telmisartan_and_eplerenone_hyperkalemia_collision():
    engine = InteractionEngine()
    telmisartan = {
        "key": "telmisartan",
        "name": "Telmisartan",
        "drug_class": "Angiotensin II Receptor Blocker (ARB)",
        "mechanism": "Selectively antagonizes AT1 receptors",
    }
    eplerenone = {
        "key": "eplerenone",
        "name": "Eplerenone",
        "drug_class": "Mineralocorticoid / Aldosterone Receptor Antagonist",
        "mechanism": "Mineralocorticoid receptor antagonist",
    }

    result = engine.analyze_stack([telmisartan, eplerenone])
    assert result["risk_band"] in {"ELEVATED", "SEVERE"}
    assert len(result["breakdown"]["receptor_conflicts"]) >= 1
    conflict = result["breakdown"]["receptor_conflicts"][0]
    assert "Hyperkalemia" in conflict["title"]
    assert any("ELECTROLYTE_DISRUPTION" in t or "DOWNSTREAM_CASCADE" in t for t in conflict["conflict_types"])
    assert any("Hyperkalemia" in s["syndrome"] for s in result["breakdown"]["syndrome_alerts"])


def test_pde5_and_nitrate_severe_hypotension_collision():
    engine = InteractionEngine()
    tadalafil = {
        "key": "tadalafil",
        "name": "Tadalafil",
        "drug_class": "PDE5 Inhibitor",
        "mechanism": "Inhibits phosphodiesterase type 5",
    }
    nitroglycerin = {
        "key": "nitroglycerin",
        "name": "Nitroglycerin",
        "drug_class": "Nitrate vasodilator",
        "mechanism": "Nitric oxide donor / cGMP stimulator",
    }

    result = engine.analyze_stack([tadalafil, nitroglycerin])
    assert any(c["severity"] == "SEVERE_CONTRAINDICATION" for c in result["breakdown"]["receptor_conflicts"])
    assert any("Hypotension" in c["title"] for c in result["breakdown"]["receptor_conflicts"])


def test_beta_blocker_and_non_dhp_ccb_bradycardia_collision():
    engine = InteractionEngine()
    metoprolol = {
        "key": "metoprolol",
        "name": "Metoprolol",
        "drug_class": "Beta-1 Adrenergic Receptor Blocker",
        "mechanism": "Beta-1 blocker",
    }
    verapamil = {
        "key": "verapamil",
        "name": "Verapamil",
        "drug_class": "Non-Dihydropyridine Calcium Channel Blocker",
        "mechanism": "L-type calcium channel blocker",
    }

    result = engine.analyze_stack([metoprolol, verapamil])
    assert any("Bradycardia" in c["title"] or "AV Nodal" in c["title"] for c in result["breakdown"]["receptor_conflicts"])
    assert result["risk_band"] in {"MODERATE", "ELEVATED", "SEVERE"}


def test_hormonal_fluctuation_uncompensated_risk_detected():
    """Verify that an infrequently dosed hormonal compound triggers an uncompensated fluctuation risk factor."""
    engine = InteractionEngine()
    testosterone_enanthate_biweekly = {
        "key": "testosterone_enanthate",
        "name": "Testosterone Enanthate",
        "drug_class": "Anabolic Steroid / Androgen Ester",
        "categories": ["Androgen", "Hormone Replacement"],
        "t_half_numeric": 108.0,  # 4.5 days
        "frequency": "every 2 weeks",
        "dose_mg": 250.0,
        "route": "im",
        "receptor_targets": [
            {"target": "Androgen Receptor", "action": "agonist", "gene_symbol": "AR"}
        ],
    }

    result = engine.analyze_stack([testosterone_enanthate_biweekly])
    uncomp = result["breakdown"]["uncompensated_risks"]
    assert any("Fluctuation" in r.get("title", "") for r in uncomp)
    fluct_risk = next(r for r in uncomp if "Fluctuation" in r.get("title", ""))
    assert fluct_risk["severity"] in ("HIGH_RISK", "MODERATE_RISK")
    assert "micro-doses" in fluct_risk["clinical_recommendation"].lower() or "twice-weekly" in fluct_risk["clinical_recommendation"].lower()


def test_split_dosing_mitigation_resolves_fluctuation_risk():
    """Verify that splitting a hormonal dose into twice-weekly removes the risk and registers an active mitigation."""
    engine = InteractionEngine()
    testosterone_enanthate_split = {
        "key": "testosterone_enanthate",
        "name": "Testosterone Enanthate",
        "drug_class": "Anabolic Steroid / Androgen Ester",
        "categories": ["Androgen", "Hormone Replacement"],
        "t_half_numeric": 108.0,  # 4.5 days
        "frequency": "twice weekly",
        "dose_mg": 60.0,
        "route": "subq",
        "receptor_targets": [
            {"target": "Androgen Receptor", "action": "agonist", "gene_symbol": "AR"}
        ],
    }

    result = engine.analyze_stack([testosterone_enanthate_split])
    uncomp = result["breakdown"]["uncompensated_risks"]
    assert not any("Fluctuation" in r.get("title", "") for r in uncomp)
    mitigations = result["breakdown"]["active_mitigations"]
    assert any("Stable Endocrine Micro-Dosing" in m.get("title", "") for m in mitigations)


def test_non_hormonal_compound_does_not_falsely_trigger_endocrine_fluctuation():
    """Verify that a non-hormonal supplement does not falsely trigger endocrine fluctuation alerts."""
    engine = InteractionEngine()
    theanine = {
        "key": "l_theanine",
        "name": "L-Theanine",
        "drug_class": "Amino Acid Dietary Supplement",
        "t_half_numeric": 3.0,
        "frequency": "daily",
        "dose_mg": 200.0,
    }

    result = engine.analyze_stack([theanine])
    uncomp = result["breakdown"]["uncompensated_risks"]
    assert not any("Fluctuation" in r.get("title", "") for r in uncomp)

