from __future__ import annotations

import pytest
from app.services.catalog_service import CatalogService
from app.services.interaction_engine import InteractionEngine


@pytest.fixture
def catalog():
    return CatalogService()


@pytest.fixture
def engine():
    return InteractionEngine()


def test_clenbuterol_and_caffeine_dynamic_camp_overload_risk(catalog, engine):
    """Verify Clenbuterol (Beta-2 agonist) + Caffeine (Adenosine antagonist/PDE inhibitor) is flagged as high/severe risk."""
    clen = catalog.get_compound("clenbuterol")
    caff = catalog.get_compound("caffeine")
    assert clen is not None and caff is not None

    result = engine.analyze_stack([clen, caff])
    assert result["risk_band"] in {"HIGH", "ELEVATED", "SEVERE"}
    assert result["cumulative_risk_score"] >= 45

    # Check pairwise receptor conflict
    receptor_conflicts = result["breakdown"]["receptor_conflicts"]
    assert any("cAMP" in c["title"] or "Tachycardia" in c["title"] or "Sympath" in c["title"] for c in receptor_conflicts)

    # Check syndromic alerts
    syndrome_alerts = result["breakdown"]["syndrome_alerts"]
    assert any("Sympathomimetic" in s["title"] or "Cardiovascular Overload" in s["title"] or "Tachycardia" in s["title"] for s in syndrome_alerts)


def test_clenbuterol_and_yohimbine_sympathoadrenal_overdrive_risk(catalog, engine):
    """Verify Clenbuterol (Beta-2 agonist) + Yohimbine (Alpha-2 blocker) is flagged as severe risk."""
    clen = catalog.get_compound("clenbuterol")
    yoh = catalog.get_compound("yohimbine")
    assert clen is not None and yoh is not None

    result = engine.analyze_stack([clen, yoh])
    assert result["risk_band"] in {"HIGH", "ELEVATED", "SEVERE"}
    assert result["cumulative_risk_score"] >= 50

    # Check pairwise conflict
    receptor_conflicts = result["breakdown"]["receptor_conflicts"]
    assert any("Sympathoadrenal" in c["title"] or "Arrhythmogenic" in c["title"] or "Crisis" in c["title"] for c in receptor_conflicts)

    # Check syndrome alerts
    syndrome_alerts = result["breakdown"]["syndrome_alerts"]
    assert any("Sympathomimetic" in s["title"] or "Tachycardia" in s["title"] for s in syndrome_alerts)


def test_synthetic_unnamed_beta_agonist_and_xanthine_collision(engine):
    """Verify that completely synthetic uncataloged compounds with generic pharmacology trigger dynamic downstream risks with zero hardcoding."""
    synthetic_beta_agonist = {
        "key": "SYNTH_BETA2_AGONIST",
        "name": "Compound-Beta2-99",
        "drug_class": "Selective Beta-2 Adrenoreceptor Agonist",
        "mechanism": "Selective beta-2 adrenergic receptor agonist",
        "receptor_targets": [
            {"target": "Beta-2 adrenergic receptor", "action": "agonist", "family": "SINGLE PROTEIN"}
        ],
        "categories": ["R03AC - Selective beta-2-adrenoreceptor agonists"],
        "organ_burdens": {"cardiovascular": "high", "cns_stimulant": "moderate", "hepatic": "none", "renal": "none", "sedative": "none"},
    }

    synthetic_xanthine = {
        "key": "SYNTH_XANTHINE_01",
        "name": "Compound-Purine-X",
        "drug_class": "Xanthine Phosphodiesterase Inhibitor",
        "mechanism": "Non-selective adenosine receptor antagonist and phosphodiesterase inhibitor",
        "receptor_targets": [
            {"target": "Adenosine A1/A2A Receptor", "action": "antagonist", "family": "Purinergic"}
        ],
        "categories": ["R03DA - Xanthines"],
        "organ_burdens": {"cardiovascular": "moderate", "cns_stimulant": "high", "hepatic": "none", "renal": "none", "sedative": "none"},
    }

    result = engine.analyze_stack([synthetic_beta_agonist, synthetic_xanthine])
    assert result["risk_band"] in {"HIGH", "ELEVATED", "SEVERE"}
    assert result["cumulative_risk_score"] >= 30

    receptor_conflicts = result["breakdown"]["receptor_conflicts"]
    assert len(receptor_conflicts) > 0
    assert any("cAMP" in c["title"] or "Tachycardia" in c["title"] for c in receptor_conflicts)


def test_synthetic_unnamed_beta_agonist_and_alpha2_blocker_collision(engine):
    """Verify that generic synthetic beta-agonist + alpha-2 blocker produces Sympathoadrenal Overdrive."""
    synthetic_beta_agonist = {
        "key": "SYNTH_BETA2_88",
        "name": "Beta2-Agonist-X",
        "drug_class": "Beta-Adrenergic Bronchodilator",
        "mechanism": "Beta-2 adrenergic receptor agonist",
        "receptor_targets": [
            {"target": "Beta-2 adrenergic receptor", "action": "agonist"}
        ],
        "organ_burdens": {"cardiovascular": "high", "cns_stimulant": "moderate"},
    }

    synthetic_alpha2_blocker = {
        "key": "SYNTH_ALPHA2_BLOCKER",
        "name": "Alpha2-Antagonist-Y",
        "drug_class": "Presynaptic Alpha-2 Blocker",
        "mechanism": "Alpha-2 adrenergic receptor antagonist",
        "receptor_targets": [
            {"target": "Alpha-2 adrenergic receptor", "action": "antagonist"}
        ],
        "organ_burdens": {"cardiovascular": "high", "cns_stimulant": "high"},
    }

    result = engine.analyze_stack([synthetic_beta_agonist, synthetic_alpha2_blocker])
    assert result["risk_band"] in {"HIGH", "ELEVATED", "SEVERE"}
    assert result["cumulative_risk_score"] >= 35

    receptor_conflicts = result["breakdown"]["receptor_conflicts"]
    assert any("Sympathoadrenal" in c["title"] or "Crisis" in c["title"] for c in receptor_conflicts)


def test_nebivolol_and_yohimbine_is_not_false_alarm_dual_stimulant(catalog, engine):
    """Verify Nebivolol (Beta-blocker) combined with Yohimbine is NOT flagged as a dual stimulant or severe risk."""
    neb = catalog.get_compound("nebivolol")
    yoh = catalog.get_compound("yohimbine")
    assert neb is not None and yoh is not None

    result = engine.analyze_stack([neb, yoh])
    assert result["risk_band"] in {"LOW", "MINIMAL"}
    assert result["cumulative_risk_score"] < 25

    # Should not have stimulant syndromes
    syndromes = result["breakdown"]["syndrome_alerts"]
    assert not any("Sympathomimetic" in s.get("syndrome", "") for s in syndromes)


def test_nebivolol_and_caffeine_is_not_dual_stimulant(catalog, engine):
    """Verify Nebivolol (Beta-blocker) combined with Caffeine is NOT flagged as a dual stimulant."""
    neb = catalog.get_compound("nebivolol")
    caff = catalog.get_compound("caffeine")
    assert neb is not None and caff is not None

    result = engine.analyze_stack([neb, caff])
    assert result["risk_band"] in {"LOW", "MINIMAL"}
    assert result["cumulative_risk_score"] < 25
    syndromes = result["breakdown"]["syndrome_alerts"]
    assert not any("Sympathomimetic" in s.get("syndrome", "") for s in syndromes)


def test_nebivolol_and_clenbuterol_is_opposing_antagonism_not_dual_stimulant(catalog, engine):
    """Verify Nebivolol (Beta-blocker) + Clenbuterol (Beta-agonist) is flagged as opposing antagonism, not dual stimulant."""
    neb = catalog.get_compound("nebivolol")
    clen = catalog.get_compound("clenbuterol")
    assert neb is not None and clen is not None

    result = engine.analyze_stack([neb, clen])
    # Opposing actions
    receptor_conflicts = result["breakdown"]["receptor_conflicts"]
    assert any("Opposing" in c.get("title", "") or "Antagonism" in c.get("title", "") for c in receptor_conflicts)
    syndromes = result["breakdown"]["syndrome_alerts"]
    assert not any("Sympathomimetic" in s.get("syndrome", "") for s in syndromes)

