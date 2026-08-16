import pytest
from app.services.interaction_engine import InteractionEngine


def test_synthetic_qtc_prolongation_detection():
    """Verify zero-hardcoding detection of QTc prolongation via FDA EPC and target annotations."""
    engine = InteractionEngine()

    synth_hERG_a = {
        "key": "synth_mol_qt_1",
        "name": "Synthetic Molecule QT-1",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Antiarrhythmic [EPC]"],
            }
        },
        "receptor_targets": [{"target": "KCNH2", "action": "antagonist"}],
    }

    synth_hERG_b = {
        "key": "synth_mol_qt_2",
        "name": "Synthetic Molecule QT-2",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Fluoroquinolone [EPC]"],
            }
        },
        "receptor_targets": [{"target": "Voltage-Gated Potassium Channel (hERG / KCNH2)", "action": "inhibitor"}],
    }

    result = engine.analyze_stack([synth_hERG_a, synth_hERG_b])
    syndromes = [s["syndrome"] for s in result["breakdown"]["syndrome_alerts"]]
    assert any("QTc Prolongation" in s for s in syndromes)


def test_synthetic_bleeding_diathesis_detection():
    """Verify zero-hardcoding detection of hemorrhagic risk via FDA EPC classes."""
    engine = InteractionEngine()

    synth_anticoag = {
        "key": "synth_factor_xa",
        "name": "Synthetic Factor Xa Blocker",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Factor Xa Inhibitor [EPC]"],
            }
        },
    }

    synth_antiplatelet = {
        "key": "synth_p2y12",
        "name": "Synthetic P2Y12 Inhibitor",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Platelet Aggregation Inhibitor [EPC]"],
            }
        },
    }

    result = engine.analyze_stack([synth_anticoag, synth_antiplatelet])
    syndromes = [s["syndrome"] for s in result["breakdown"]["syndrome_alerts"]]
    assert any("Additive Hemorrhagic Risk" in s or "Hemorrhagic" in s for s in syndromes)


def test_synthetic_anticholinergic_delirium_detection():
    """Verify zero-hardcoding detection of anticholinergic burden via FDA EPC / ATC."""
    engine = InteractionEngine()

    synth_antimuscarinic_1 = {
        "key": "synth_ach_1",
        "name": "Synthetic Antimuscarinic Agent A",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Muscarinic Acetylcholine Receptor Antagonist [EPC]"],
            }
        },
    }

    synth_antimuscarinic_2 = {
        "key": "synth_ach_2",
        "name": "Synthetic Antimuscarinic Agent B",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Anticholinergic [EPC]"],
            }
        },
    }

    result = engine.analyze_stack([synth_antimuscarinic_1, synth_antimuscarinic_2])
    syndromes = [s["syndrome"] for s in result["breakdown"]["syndrome_alerts"]]
    assert any("Anticholinergic" in s for s in syndromes)


def test_synthetic_serotonin_toxicity_detection():
    """Verify zero-hardcoding detection of serotonin toxicity via formal ontology classes."""
    engine = InteractionEngine()

    synth_ssri = {
        "key": "synth_5ht_reuptake",
        "name": "Synthetic 5-HT Reuptake Blocker",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Selective Serotonin Reuptake Inhibitor [EPC]"],
            }
        },
    }

    synth_maoi = {
        "key": "synth_mao_inhibitor",
        "name": "Synthetic MAO Enzyme Blocker",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Monoamine Oxidase Inhibitor [EPC]"],
            }
        },
    }

    result = engine.analyze_stack([synth_ssri, synth_maoi])
    syndromes = [s["syndrome"] for s in result["breakdown"]["syndrome_alerts"]]
    assert any("Serotonin Syndrome" in s for s in syndromes)


def test_synthetic_cns_and_respiratory_depression_detection():
    """Verify zero-hardcoding detection of respiratory depression via Opioid + Benzodiazepine EPC."""
    engine = InteractionEngine()

    synth_opioid = {
        "key": "synth_mu_agonist",
        "name": "Synthetic Mu Agonist",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Opioid Receptor Agonist [EPC]"],
            }
        },
    }

    synth_benzo = {
        "key": "synth_gaba_pam",
        "name": "Synthetic GABA PAM",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Benzodiazepine [EPC]"],
            }
        },
    }

    result = engine.analyze_stack([synth_opioid, synth_benzo])
    assert result["risk_band"] in {"SEVERE", "ELEVATED"}
    syndromes = [s["syndrome"] for s in result["breakdown"]["syndrome_alerts"]]
    assert any("Respiratory Depression" in s for s in syndromes)


def test_synthetic_synergistic_hypoglycemia_detection():
    """Verify zero-hardcoding detection of hypoglycemia via formal antidiabetic EPC classes."""
    engine = InteractionEngine()

    synth_secretagogue = {
        "key": "synth_katp_blocker",
        "name": "Synthetic KATP Channel Blocker",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Sulfonylurea [EPC]"],
            }
        },
    }

    synth_incretin = {
        "key": "synth_glp1_agonist",
        "name": "Synthetic Incretin Mimetic",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["GLP-1 Receptor Agonist [EPC]"],
            }
        },
    }

    result = engine.analyze_stack([synth_secretagogue, synth_incretin])
    syndromes = [s["syndrome"] for s in result["breakdown"]["syndrome_alerts"]]
    assert any("Hypoglycemia" in s for s in syndromes)


def test_synthetic_renal_triple_whammy_detection():
    """Verify zero-hardcoding detection of renal triple whammy via RAAS + NSAID + Diuretic EPC/ATC."""
    engine = InteractionEngine()

    synth_arb = {
        "key": "synth_raas_blocker",
        "name": "Synthetic AT1 Antagonist",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Angiotensin 2 Receptor Blocker [EPC]"],
            }
        },
    }

    synth_nsaid = {
        "key": "synth_cox_inhibitor",
        "name": "Synthetic COX Inhibitor",
        "metadata": {
            "online_enrichment": {
                "pharm_class_epc": ["Non-Steroidal Anti-Inflammatory Drug [EPC]"],
            }
        },
    }

    synth_diuretic = {
        "key": "synth_loop_diuretic",
        "name": "Synthetic Loop Natriuretic",
        "categories": ["C03 - Diuretics"],
        "drug_class": "Diuretic",
    }

    result = engine.analyze_stack([synth_arb, synth_nsaid, synth_diuretic])
    syndromes = [s["syndrome"] for s in result["breakdown"]["syndrome_alerts"]]
    assert any("Triple Whammy" in s for s in syndromes)
