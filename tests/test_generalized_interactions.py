import pytest
from app.services.interaction_engine import InteractionEngine


def test_zero_drug_name_epc_collision_hyperkalemia():
    """Verify that two novel compounds with synthetic names trigger hyperkalemia collision purely via FDA EPC classes."""
    engine = InteractionEngine()

    novel_compound_a = {
        "key": "nc_alpha_99",
        "name": "NC-Alpha-99",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Angiotensin 2 Receptor Blocker [EPC]"],
                "pharm_class_moa": ["Angiotensin 2 Receptor Antagonists [MoA]"],
            }
        },
    }

    novel_compound_b = {
        "key": "nc_beta_101",
        "name": "NC-Beta-101",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Mineralocorticoid Receptor Antagonist [EPC]"],
                "pharm_class_moa": ["Mineralocorticoid Receptor Antagonists [MoA]"],
            }
        },
    }

    result = engine.analyze_stack([novel_compound_a, novel_compound_b])
    assert result["risk_band"] in {"ELEVATED", "SEVERE"}
    assert len(result["breakdown"]["receptor_conflicts"]) >= 1
    conflict = result["breakdown"]["receptor_conflicts"][0]
    assert "Hyperkalemia" in conflict["title"]
    assert any("ELECTROLYTE_DISRUPTION" in t or "DOWNSTREAM_CASCADE" in t for t in conflict["conflict_types"])


def test_zero_drug_name_atc_collision_vasodilatory_shock():
    """Verify that novel compounds with only ATC codes (PDE5i G04BE + Nitrate C01DA) trigger severe contraindication."""
    engine = InteractionEngine()

    novel_pde5i = {
        "key": "novel_vaso_1",
        "name": "Novel Vasodilator A",
        "external_ids": {"atc_codes": ["G04BE08"]},
        "categories": ["G04BE - Drugs used in erectile dysfunction"],
    }

    novel_nitrate = {
        "key": "novel_vaso_2",
        "name": "Novel Vasodilator B",
        "external_ids": {"atc_codes": ["C01DA14"]},
        "categories": ["C01DA - Organic nitrates"],
    }

    result = engine.analyze_stack([novel_pde5i, novel_nitrate])
    assert any(c["severity"] == "SEVERE_CONTRAINDICATION" for c in result["breakdown"]["receptor_conflicts"])
    assert any("Vasodilatory Shock" in c["title"] or "Hypotension" in c["title"] for c in result["breakdown"]["receptor_conflicts"])


def test_zero_drug_name_physiologic_effect_pe_collision():
    """Verify that compounds with FDA Physiologic Effect 'Decreased Renal Potassium Excretion [PE]' trigger collision."""
    engine = InteractionEngine()

    comp_1 = {
        "key": "pe_agent_1",
        "name": "PE Research Agent 1",
        "metadata": {
            "online_enrichment": {
                "pharm_class_pe": ["Decreased Renal Potassium Excretion [PE]"],
            }
        },
    }

    comp_2 = {
        "key": "pe_agent_2",
        "name": "PE Research Agent 2",
        "metadata": {
            "online_enrichment": {
                "pharm_class_pe": ["Decreased Renal Potassium Excretion [PE]"],
            }
        },
    }

    result = engine.analyze_stack([comp_1, comp_2])
    assert len(result["breakdown"]["receptor_conflicts"]) >= 1
    assert "Hyperkalemia" in result["breakdown"]["receptor_conflicts"][0]["title"]
