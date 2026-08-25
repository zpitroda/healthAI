from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.copilot_agent import CopilotAgent
from app.services.stack_intent_engine import StackIntentEngine, SCRATCH_GOAL_BLUEPRINTS


@pytest.fixture
def client():
    return TestClient(app)


def test_scratch_goal_blueprints_taxonomy():
    """Verify all expected goals have valid blueprints with core compounds."""
    expected_goals = [
        "cognitive_focus",
        "longevity_autophagy",
        "cardiovascular_lipid",
        "anabolic_physique",
        "sleep_stress_recovery",
        "fat_loss_metabolic",
        "post_therapy_reset",
    ]
    for g in expected_goals:
        assert g in SCRATCH_GOAL_BLUEPRINTS
        bp = SCRATCH_GOAL_BLUEPRINTS[g]
        assert "title" in bp
        assert len(bp["core_compounds"]) >= 2
        for comp in bp["core_compounds"]:
            assert "key" in comp
            assert "name" in comp
            assert comp["base_dose"] > 0
            assert comp["timing"] in ("morning", "pre-workout", "midday", "bedtime", "evening")


def test_build_scratch_stack_proposal_cognitive():
    """Verify building a cognitive focus stack with standard preferences and biometrics."""
    biometrics = {
        "weight_kg": 85.0,
        "age": 32,
        "egfr": 95.0,
        "alt_u_l": 24.0,
        "blood_pressure": 120.0,
    }
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="cognitive_focus",
        biometrics=biometrics,
        preferences={"stimulant_level": "standard", "complexity": "standard"},
    )

    assert proposal["goal_id"] == "cognitive_focus"
    assert "Cognitive Focus" in proposal["goal_title"]
    assert len(proposal["compounds"]) >= 3

    keys = [c["key"] for c in proposal["compounds"]]
    assert "caffeine" in keys
    assert "l_theanine" in keys
    assert "bacopa" in keys

    # Verify action card diff format
    action_card = proposal["action_card"]
    assert action_card["action_card"] == "stack_diff"
    assert len(action_card["add"]) >= 3
    for item in action_card["add"]:
        assert "key" in item
        assert "dose" in item
        assert "timing" in item
        assert "route" in item


def test_build_scratch_stack_proposal_stim_free():
    """Verify stimulant-free preference removes caffeine and stimulants."""
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="cognitive_focus",
        preferences={"stimulant_level": "stim-free"},
    )
    keys = [c["key"] for c in proposal["compounds"]]
    assert "caffeine" not in keys
    assert "l_theanine" in keys


def test_build_scratch_stack_proposal_organ_protection():
    """Verify elevated BP/ALT automatically injects protective co-factors."""
    biometrics = {
        "weight_kg": 90.0,
        "blood_pressure": 142.0,
        "alt_u_l": 65.0,
        "egfr": 75.0,
    }
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="longevity_autophagy",
        biometrics=biometrics,
        preferences={"substance_style": "hybrid"},
    )
    keys = [c["key"] for c in proposal["compounds"]]
    assert "telmisartan" in keys  # Added for BP/renal protection
    assert "nac" in keys          # Added for elevated ALT support


def test_copilot_tool_build_stack_from_scratch():
    """Verify CopilotAgent executes build_stack_from_scratch tool."""
    tool_res = CopilotAgent.execute_tool(
        "build_stack_from_scratch",
        {
            "goal": "cardiovascular_lipid",
            "biometrics": {"weight_kg": 80.0, "blood_pressure": 130.0},
            "preferences": {"complexity": "standard"},
        },
    )
    assert isinstance(tool_res, dict)
    assert tool_res.get("goal_id") == "cardiovascular_lipid"
    assert len(tool_res.get("compounds", [])) >= 3
    assert "action_card" in tool_res


def test_api_build_stack_from_scratch_endpoint(client):
    """Verify POST /api/ai/build-stack-from-scratch endpoint."""
    response = client.post(
        "/api/ai/build-stack-from-scratch",
        json={
            "goal": "anabolic_physique",
            "biometrics": {"weight_kg": 82.0, "age": 28, "blood_pressure": 120.0},
            "preferences": {"complexity": "standard", "stimulant_level": "standard"},
            "custom_instructions": "Focus on natural cellular hydration and carnosine buffering",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["goal_id"] == "anabolic_physique"
    assert len(data["compounds"]) >= 3
    assert "action_card" in data
    assert data["action_card"]["action_card"] == "stack_diff"


def test_copilot_system_context_empty_stack():
    """Verify build_system_context handles empty stack gracefully and provides scratch generation mandate."""
    ctx = CopilotAgent.build_system_context(
        persona="architect",
        stack=[],
        biometrics={"weight_kg": 75, "age": 30, "blood_pressure": 120},
        protocol_goal="cognitive_focus",
    )
    assert "### ACTIVE WORKBENCH STACK (0 compounds):" in ctx
    assert "No active compounds loaded in workbench." in ctx
    assert "SCRATCH PROTOCOL GENERATION MANDATE" in ctx
    assert "action_card" in ctx


def test_anabolic_physique_enhanced_scratch_stack_includes_ai_and_depot_schedule():
    """Verify enhanced testosterone protocol appropriately sets twice-weekly depot dosing and includes an AI."""
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="anabolic_physique",
        biometrics={"weight_kg": 85.0, "blood_pressure": 122.0, "alt_u_l": 26.0, "egfr": 95.0},
        preferences={"complexity": "comprehensive"},
        custom_notes="Include testosterone cypionate for hypertrophy cycle with full ancillary coverage",
    )
    keys = [c["key"] for c in proposal["compounds"]]
    assert "testosterone_cypionate" in keys
    assert "anastrozole" in keys or "exemestane" in keys
    assert "telmisartan" in keys

    # Verify testosterone cypionate is NOT scheduled daily, but twice-weekly/weekly IM
    test_cyp = next(c for c in proposal["compounds"] if c["key"] == "testosterone_cypionate")
    assert test_cyp["frequency"] in ("twice_weekly", "weekly")
    assert test_cyp["route"] in ("intramuscular", "subcutaneous")
    assert test_cyp["dose"] in (175, 350)

    # Verify AI has twice-weekly frequency and oral route
    ai_cand = next(c for c in proposal["compounds"] if c["key"] in ("anastrozole", "exemestane"))
    assert ai_cand["frequency"] in ("twice_weekly", "every_other_day", "daily")
    assert ai_cand["route"] == "oral"


def test_therapeutic_gap_detects_missing_ai_for_testosterone_stack():
    """Verify StackIntentEngine detects missing Aromatase Inhibitor when testosterone is in the stack."""
    compounds = [
        {"key": "testosterone_cypionate", "name": "Testosterone Cypionate", "dose_mg": 350.0, "frequency": "weekly", "route": "intramuscular"},
        {"key": "telmisartan", "name": "Telmisartan", "dose_mg": 40.0, "frequency": "daily", "route": "oral"},
    ]
    analysis = StackIntentEngine.analyze(
        compounds=compounds,
        biometrics={"weight_kg": 80.0},
        user_goal_id="anabolic_physique",
    )
    gaps = analysis.get("therapeutic_gaps", [])
    assert any("Aromatization" in g.get("axis", "") or "Estrogen" in g.get("axis", "") or "AI" in g.get("axis", "") for g in gaps)
    ai_gap = next(g for g in gaps if "Aromatization" in g.get("axis", "") or "Estrogen" in g.get("axis", ""))
    assert "Anastrozole" in ai_gap["recommended_cofactor"] or "Exemestane" in ai_gap["recommended_cofactor"]


def test_copilot_evidence_based_recommendations_suggests_ai_when_androgens_present():
    """Verify CopilotAgent.get_evidence_based_recommendations proposes Anastrozole/Exemestane when testosterone is active."""
    compounds = [
        {"key": "testosterone_cypionate", "name": "Testosterone Cypionate", "dose_mg": 350.0, "route": "intramuscular", "frequency": "weekly"}
    ]
    recs = CopilotAgent.get_evidence_based_recommendations(
        compounds=compounds,
        biometrics={"weight_kg": 80.0},
        protocol_goal="anabolic_physique",
    )
    rec_keys = [r["key"] for r in recs]
    assert "anastrozole" in rec_keys or "exemestane" in rec_keys
    assert "telmisartan" in rec_keys


def test_dosing_service_depot_androgen_route_and_frequency_defaults():
    """Verify dosing_service correctly defaults route to intramuscular and frequency to twice_weekly for depot esters."""
    from app.services.dosing_service import parse_dose_string_or_spec

    parsed = parse_dose_string_or_spec("testosterone_cypionate")
    assert parsed["route"] == "intramuscular"
    assert parsed["frequency"] == "twice_weekly"
    assert parsed["dose_mg"] > 0

    parsed_weekly = parse_dose_string_or_spec("testosterone_cypionate:350mg:weekly")
    assert parsed_weekly["route"] == "intramuscular"
    assert parsed_weekly["frequency"] == "weekly"
    assert parsed_weekly["dose_mg"] == 350.0
    assert parsed_weekly["effective_daily_dose_mg"] == 50.0


def test_build_scratch_stack_proposal_risk_tolerance_conservative_vs_aggressive():
    """Verify risk_tolerance scales dosages appropriately (conservative: 0.75x, aggressive: 1.25x)."""
    biometrics = {"weight_kg": 75.0, "age": 30, "blood_pressure": 120.0, "alt_u_l": 25.0, "egfr": 95.0}

    # Conservative stack
    conservative_prop = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="cognitive_focus",
        biometrics=biometrics,
        preferences={"risk_tolerance": "conservative", "complexity": "standard"},
    )
    assert conservative_prop["biometric_calibration"]["risk_scale"] == 0.75
    assert conservative_prop["customizations"]["risk_tolerance"] == "conservative"
    c_caf = next(c for c in conservative_prop["compounds"] if c["key"] == "caffeine")
    # Base dose for caffeine is 100mg -> 100 * 0.75 = 75mg
    assert c_caf["dose"] == 75

    # Aggressive stack
    aggressive_prop = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="cognitive_focus",
        biometrics=biometrics,
        preferences={"risk_tolerance": "aggressive", "complexity": "standard"},
    )
    assert aggressive_prop["biometric_calibration"]["risk_scale"] == 1.25
    assert aggressive_prop["customizations"]["risk_tolerance"] == "aggressive"
    a_caf = next(c for c in aggressive_prop["compounds"] if c["key"] == "caffeine")
    # Base dose for caffeine is 100mg -> 100 * 1.25 = 125mg
    assert a_caf["dose"] == 125


def test_build_scratch_stack_proposal_schedule_preference_morning_only():
    """Verify schedule_preference='morning_only' adjusts timings and excludes pure sleep agents like melatonin."""
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="sleep_stress_recovery",
        biometrics={"weight_kg": 75.0},
        preferences={"schedule_preference": "morning_only", "complexity": "standard"},
    )
    assert proposal["customizations"]["schedule_preference"] == "morning_only"
    # Melatonin is bedtime-specific and should be filtered from morning-only schedules
    keys = [c["key"] for c in proposal["compounds"]]
    assert "melatonin" not in keys
    assert "magnesium" in keys
    # Magnesium timing should be shifted to morning
    mag = next(c for c in proposal["compounds"] if c["key"] == "magnesium")
    assert mag["timing"] == "morning"
    assert len(proposal["schedule"]["morning"]) > 0


def test_build_scratch_stack_proposal_organ_priorities_and_budget_tier():
    """Verify explicit organ_priority flags inject targeted organ shields, and essential budget tier trims tertiary co-factors."""
    # Hepatic priority
    hep_prop = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="cognitive_focus",
        biometrics={"weight_kg": 75.0, "alt_u_l": 20.0},  # Normal ALT, but hepatic priority explicitly selected
        preferences={"organ_priority": "hepatic", "complexity": "standard"},
    )
    hep_keys = [c["key"] for c in hep_prop["compounds"]]
    assert "nac" in hep_keys

    # Budget essential tier on longevity stack
    budget_prop = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="longevity_autophagy",
        biometrics={"weight_kg": 75.0},
        preferences={"budget_tier": "essential", "complexity": "standard"},
    )
    b_keys = [c["key"] for c in budget_prop["compounds"]]
    assert "berberine" in b_keys
    assert "coq10" in b_keys
    # Non-essential enhancers like piperine/resveratrol should be omitted in essential budget tier
    assert "resveratrol" not in b_keys


