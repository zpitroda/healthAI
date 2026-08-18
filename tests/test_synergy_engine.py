import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.synergy_engine import SynergyEngine

client = TestClient(app)


def test_loewe_additivity_combination_index_calculation():
    engine = SynergyEngine()

    # Synergy case: lower dose produces response (CI < 1.0)
    res_syn = engine.calculate_loewe_combination_index(doses_mg=[10.0, 15.0], single_agent_ec50s_mg=[30.0, 45.0])
    assert res_syn["combination_index"] < 0.85
    assert res_syn["is_synergistic"] is True
    assert "Synergy" in res_syn["classification"]

    # Additive case: CI approx 1.0
    res_add = engine.calculate_loewe_combination_index(doses_mg=[15.0, 22.5], single_agent_ec50s_mg=[30.0, 45.0])
    assert 0.85 <= res_add["combination_index"] <= 1.15
    assert res_add["is_synergistic"] is False

    # Antagonistic case: CI > 1.15
    res_ant = engine.calculate_loewe_combination_index(doses_mg=[30.0, 45.0], single_agent_ec50s_mg=[30.0, 45.0])
    assert res_ant["combination_index"] > 1.15
    assert res_ant["is_synergistic"] is False


def test_bliss_independence_model_calculation():
    engine = SynergyEngine()

    # Single effects E_A = 0.50, E_B = 0.40 -> E_bliss = 1 - (0.5 * 0.6) = 0.70 (70%)
    res_bliss = engine.calculate_bliss_independence(single_effects=[0.50, 0.40], observed_combined_effect=0.85)
    assert res_bliss["expected_bliss_effect_pct"] == 70.0
    assert res_bliss["observed_effect_pct"] == 85.0
    assert res_bliss["bliss_delta_pct"] == 15.0
    assert res_bliss["is_synergistic"] is True
    assert "Synergy" in res_bliss["classification"]


def test_oncology_multi_agent_stack_synergy():
    engine = SynergyEngine()

    oncology_stack = [
        {
            "key": "doxorubicin",
            "name": "Doxorubicin",
            "dose_mg": 20.0,
            "drug_class": "Oncology Chemotherapy / Topoisomerase II Inhibitor",
            "receptor_targets": [{"target": "Topoisomerase II", "action": "inhibitor"}],
        },
        {
            "key": "paclitaxel",
            "name": "Paclitaxel",
            "dose_mg": 30.0,
            "drug_class": "Oncology Antineoplastic / Microtubule Stabilizer",
            "receptor_targets": [{"target": "Beta-Tubulin", "action": "inhibitor"}],
        },
    ]

    res = engine.evaluate_multi_agent_synergy(oncology_stack, stack_domain="oncology")
    assert res["stack_domain"] == "oncology"
    assert res["overall_synergistic"] is True
    assert res["loewe_model"]["is_synergistic"] is True
    assert res["bliss_model"]["is_synergistic"] is True
    assert "Oncology" in res["domain_notes"]


def test_antimicrobial_multi_agent_stack_synergy():
    engine = SynergyEngine()

    antimicrobial_stack = [
        {
            "key": "amoxicillin",
            "name": "Amoxicillin",
            "dose_mg": 500.0,
            "drug_class": "Beta-lactam Antibiotic",
            "receptor_targets": [{"target": "Penicillin-Binding Protein", "action": "inhibitor"}],
        },
        {
            "key": "clavulanic_acid",
            "name": "Clavulanate",
            "dose_mg": 125.0,
            "drug_class": "Beta-Lactamase Inhibitor Antimicrobial",
            "receptor_targets": [{"target": "Beta-Lactamase Enzyme", "action": "inhibitor"}],
        },
    ]

    res = engine.evaluate_multi_agent_synergy(antimicrobial_stack, stack_domain="antimicrobial")
    assert res["stack_domain"] == "antimicrobial"
    assert res["overall_synergistic"] is True
    assert "Antimicrobial" in res["domain_notes"]


def test_longevity_multi_agent_stack_synergy():
    engine = SynergyEngine()

    longevity_stack = [
        {
            "key": "rapamycin",
            "name": "Rapamycin (Sirolimus)",
            "dose_mg": 5.0,
            "drug_class": "mTORC1 Inhibitor Longevity Agent",
            "receptor_targets": [{"target": "mTORC1", "action": "inhibitor"}],
        },
        {
            "key": "metformin",
            "name": "Metformin",
            "dose_mg": 500.0,
            "drug_class": "AMPK Activator Longevity Agent",
            "receptor_targets": [{"target": "AMPK", "action": "agonist"}],
        },
    ]

    res = engine.evaluate_multi_agent_synergy(longevity_stack, stack_domain="longevity")
    assert res["stack_domain"] == "longevity"
    assert res["overall_synergistic"] is True
    assert "Longevity" in res["domain_notes"]


def test_api_synergy_evaluate_endpoint():
    payload = {
        "stack": ["rapamycin:5mg", "metformin:500mg"],
        "goals": ["longevity", "autophagy"],
    }
    response = client.post("/api/synergy/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "stack_domain" in data
    assert "overall_synergistic" in data
    assert "loewe_model" in data
    assert "bliss_model" in data
    assert "pairwise_synergy_matrix" in data
    assert len(data["pairwise_synergy_matrix"]) >= 1
