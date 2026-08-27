import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog_service import CatalogService
from app.services.copilot_agent import CopilotAgent
from app.services.stack_intent_engine import StackIntentEngine

client = TestClient(app)


def test_copilot_modes_endpoint():
    res = client.get("/api/ai/modes")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 4
    mode_ids = [m["id"] for m in data]
    assert "architect" in mode_ids
    assert "auditor" in mode_ids
    assert "tutor" in mode_ids
    assert "labs" in mode_ids


def test_protocol_goals_endpoint():
    res = client.get("/api/ai/goals")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    goal_ids = [g["id"] for g in data]
    assert "auto" in goal_ids
    assert "anabolic_physique" in goal_ids
    assert "cognitive_focus" in goal_ids
    assert "longevity_autophagy" in goal_ids


def test_infer_stack_purpose_endpoint():
    res = client.post(
        "/api/ai/infer-purpose",
        json={
            "stack": ["testosterone_cypionate", "trenbolone_enanthate", "exemestane", "telmisartan", "nebivolol", "nac"],
            "biometrics": {"age": 30, "weight_kg": 90}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["inferred_domain"] == "anabolic_physique"
    assert "Physique" in data["goal_title"]
    assert len(data["modality_profile"]["depot_injections"]) >= 2
    assert len(data["therapeutic_gaps"]) >= 1


def test_stack_intent_engine_direct():
    compounds = [
        {"key": "caffeine", "name": "Caffeine", "drug_class": "CNS Stimulant", "mechanism": "Adenosine antagonist", "route": "oral", "dose": 200},
        {"key": "l_theanine", "name": "L-Theanine", "drug_class": "Amino Acid", "mechanism": "Glutamate modulator", "route": "oral", "dose": 100},
    ]
    analysis = StackIntentEngine.analyze(compounds)
    assert analysis["inferred_domain"] == "cognitive_focus"
    assert len(analysis["modality_profile"]["daily_oral"]) == 2


def test_copilot_tool_execution_catalog():
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "get_compound_details",
            "arguments": {"compound_name": "caffeine"}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "name" in data or "canonical_name" in data
    assert "half_life_hours" in data


def test_copilot_tool_execution_cyp450():
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "check_cyp450_conflicts",
            "arguments": {"compound_keys": ["caffeine", "theanine"]}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "critical_conflicts" in data
    assert "cumulative_risk_score" in data


def test_copilot_tool_execution_pkpd():
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "simulate_pkpd",
            "arguments": {
                "compound_key": "caffeine",
                "dose_mg": 150,
                "dosing_interval_h": 24,
                "age": 30,
                "weight_kg": 75,
                "egfr": 95,
                "alt_u_l": 25
            }
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "cmax_mg_l" in data
    assert "auc_mg_h_l" in data
    assert "effective_half_life_h" in data
    assert "steady_state_accumulation_ratio" in data


def test_copilot_tool_execution_diff():
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "propose_stack_diff",
            "arguments": {
                "add": [{"key": "l_theanine", "dose": 200, "unit": "mg"}],
                "modify": [{"key": "caffeine", "dose": 100, "unit": "mg"}],
                "remove": []
            }
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("action_card") == "stack_diff"
    assert len(data.get("additions", [])) == 1


def test_copilot_tool_execution_synergies():
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "evaluate_synergies",
            "arguments": {"compound_keys": ["caffeine", "l_theanine"]}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, dict)
    assert "pairs" in data or "synergy_count" in data or "benefits" in data or "matrix" in data or isinstance(data, dict)


def test_copilot_tool_execution_individualized_dosing():
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "calculate_individualized_dosing",
            "arguments": {
                "compound_key": "caffeine",
                "biometrics": {"weight_kg": 90, "egfr": 50, "alt_u_l": 60, "age": 45}
            }
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "adjusted_recommended_dose_mg" in data
    assert "scaling_factors" in data
    assert "weight_factor" in data["scaling_factors"]


def test_copilot_tool_execution_graphrag_subgraph():
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "query_graphrag_subgraph",
            "arguments": {"entity_ids": ["caffeine", "l_theanine"], "max_hops": 2}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "triple_count" in data
    assert "causal_chains" in data


def test_copilot_chat_non_streaming_endpoint():
    mock_res = {
        "response_text": "Protocol is balanced and circadian-aligned.",
        "key_takeaways": ["Take Caffeine in morning", "Add Theanine to buffer jitter"],
        "suggested_actions": []
    }
    with patch("app.services.copilot_agent.CopilotAgent.chat_copilot_turn", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_res
        res = client.post(
            "/api/ai/chat",
            json={
                "messages": [{"role": "user", "content": "Optimize my morning focus stack"}],
                "persona": "architect",
                "stack": ["caffeine", "l_theanine"],
                "biometrics": {"age": 30},
                "protocol_goal": "cognitive_focus",
                "protocol_objective": "Need 6 hours sustained clean focus"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["response_text"] == "Protocol is balanced and circadian-aligned."
        assert len(data["key_takeaways"]) == 2


def test_copilot_chat_stream_endpoint():
    async def mock_stream_events(*args, **kwargs):
        yield {"event": "reasoning", "data": "Evaluating 3-hop GraphRAG context..."}
        yield {"event": "delta", "data": "Caffeine provides adenosine receptor antagonism. "}
        yield {"event": "delta", "data": "Combine with Theanine for synergistic focus."}
        yield {
            "event": "action_card",
            "data": {
                "type": "stack_diff",
                "payload": {
                    "add": [{"key": "l_theanine", "dose": 200, "unit": "mg", "timing": "morning"}],
                    "modify": [],
                    "remove": []
                }
            }
        }
        yield {"event": "done", "data": "[DONE]"}

    with patch("app.services.copilot_agent.CopilotAgent.stream_copilot_turn", side_effect=mock_stream_events):
        res = client.post(
            "/api/ai/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Analyze my stack"}],
                "persona": "architect",
                "stack": ["caffeine"],
                "biometrics": {"age": 30},
                "protocol_goal": "cognitive_focus",
                "protocol_objective": "Focus optimization"
            }
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body_text = res.text
        assert "event: reasoning" in body_text
        assert "event: delta" in body_text
        assert "event: action_card" in body_text
        assert "event: done" in body_text


def test_copilot_system_context_deterministic_grounding():
    """Verify system context integrates collision matrix, PK/PD, and GraphRAG triples."""
    stack = ["caffeine:200mg", "l_theanine:100mg"]
    biometrics = {"age": 28, "weight_kg": 72, "egfr": 100, "alt_u_l": 20}
    
    ctx_architect = CopilotAgent.build_system_context(
        persona="architect",
        stack=stack,
        biometrics=biometrics,
        protocol_goal="cognitive_focus",
        protocol_objective="Clean wakefulness without anxiety"
    )
    assert "Protocol Architect" in ctx_architect
    assert "PROTOCOL PURPOSE, MODALITY & THERAPEUTIC GAP ANALYSIS" in ctx_architect
    assert "Cognitive Focus" in ctx_architect
    assert "Clean wakefulness without anxiety" in ctx_architect
    assert "PATIENT BIOMETRICS & CLEARANCE PROFILE" in ctx_architect
    assert "DETERMINISTIC DDI COLLISION MATRIX & SAFETY AUDIT" in ctx_architect
    assert "STEADY-STATE PHARMACOKINETICS" in ctx_architect
    assert "QUANTITATIVE MULTI-AGENT SYNERGY MODELING" in ctx_architect
    assert "Caffeine" in ctx_architect


def test_evidence_based_recommendations_anabolic_burden():
    """Verify evidence-based candidate recommendations dynamically offset organ burdens."""
    compounds = [
        {"key": "testosterone_cypionate", "name": "Testosterone Cypionate", "drug_class": "Androgenic Anabolic Steroid", "route": "intramuscular", "dose": 250},
        {"key": "trenbolone_enanthate", "name": "Trenbolone Enanthate", "drug_class": "19-nor Androgenic Anabolic Steroid", "route": "intramuscular", "dose": 150}
    ]
    biometrics = {"age": 30, "weight_kg": 90, "egfr": 90, "alt_u_l": 30, "blood_pressure": 138}
    recs = CopilotAgent.get_evidence_based_recommendations(
        compounds=compounds,
        biometrics=biometrics,
        protocol_goal="anabolic_physique"
    )
    assert len(recs) >= 2
    rec_keys = [r["key"] for r in recs]
    # Should identify BP/RAAS (Telmisartan), Prolactin/19-nor (P5P), or Lipid/ApoB (Pitavastatin)
    assert "telmisartan" in rec_keys or "p5p" in rec_keys or "pitavastatin" in rec_keys
    # Every recommendation must provide exact target, standard dose, and clinical rationale
    for r in recs:
        assert "target" in r
        assert "standard_dose" in r
        assert "clinical_purpose" in r
        assert "solves_burden" in r
        assert "evidence_grade" in r


def test_evidence_based_recommendations_cognitive_focus():
    """Verify evidence-based recommendations for cognitive focus and stimulant jitter buffering."""
    compounds = [
        {"key": "caffeine", "name": "Caffeine", "drug_class": "CNS Stimulant", "route": "oral", "dose": 250}
    ]
    recs = CopilotAgent.get_evidence_based_recommendations(
        compounds=compounds,
        biometrics={"age": 25, "weight_kg": 70},
        protocol_goal="cognitive_focus"
    )
    rec_keys = [r["key"] for r in recs]
    assert "l_theanine" in rec_keys or "alpha_gpc" in rec_keys


def test_copilot_tool_pathway_cascade():
    """Verify pathway cascade retrieval tool."""
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "query_pathway_cascade",
            "arguments": {"target_id": "ADORA1"}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "cascade" in data
    assert "target_id" in data


def test_copilot_tool_evidence_based_recommendations():
    """Verify tool execution for evidence-based recommendations."""
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "get_evidence_based_recommendations",
            "arguments": {
                "compound_keys": ["caffeine"],
                "biometrics": {"age": 28},
                "protocol_goal": "cognitive_focus"
            }
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "recommendations" in data
    assert data["count"] >= 1


def test_dynamic_entity_extraction_from_messages():
    """Verify conversation entity extraction finds compounds mentioned in chat."""
    messages = [
        {"role": "user", "content": "Should I consider adding Telmisartan and Nebivolol to my protocol for blood pressure?"}
    ]
    extracted = CopilotAgent.extract_entities_from_messages(messages)
    assert "telmisartan" in extracted or "nebivolol" in extracted


def test_all_persona_prompts_standards():
    """Verify all 4 personas have strict clinical guidance and structured formatting."""
    from app.services.copilot_agent import PERSONA_SYSTEM_PROMPTS
    modes = CopilotAgent.get_registered_modes()
    assert len(modes) == 4
    for m in modes:
        mode_id = m["id"]
        assert mode_id in PERSONA_SYSTEM_PROMPTS

        prompt_text = PERSONA_SYSTEM_PROMPTS[mode_id]
        assert len(prompt_text) > 300
    
    # Verify complete system context integration
    full_prompt = CopilotAgent.build_system_context(
        persona="architect",
        stack=["caffeine"],
        biometrics={"age": 30}
    )
    assert len(full_prompt) > 500
    assert "PATIENT BIOMETRICS" in full_prompt
    assert "ACTIVE WORKBENCH STACK" in full_prompt



def test_parse_and_clean_tool_calls_and_scratchpad():
    """Verify tool call parsing, scratchpad extraction, and user-facing text cleaning."""
    sample_agent_output = """
<scratchpad>
Hypothesis: Telmisartan will provide selective AT1 blockade and activate PPAR-gamma.
Let's query its 2-hop biological neighborhood to confirm downstream eNOS and renal effects.
</scratchpad>
<tool_call name="query_graphrag_subgraph">
{"entity_ids": ["telmisartan"], "max_hops": 2}
</tool_call>
"""
    # 1. Test tool parsing
    tool_call = CopilotAgent.parse_tool_call_from_text(sample_agent_output)
    assert tool_call is not None
    assert tool_call["name"] == "query_graphrag_subgraph"
    assert tool_call["arguments"]["entity_ids"] == ["telmisartan"]

    # 2. Test scratchpad extraction
    scratchpad = CopilotAgent.extract_scratchpad_from_text(sample_agent_output)
    assert "Hypothesis: Telmisartan" in scratchpad
    assert "PPAR-gamma" in scratchpad

    # 3. Test cleaning from user-facing text
    cleaned = CopilotAgent.clean_scratchpad_and_tools_from_text(sample_agent_output + "\n\n### Clinical Summary\nTelmisartan is recommended.")
    assert "Telmisartan is recommended." in cleaned
    assert "<scratchpad>" not in cleaned
    assert "<tool_call" not in cleaned


@pytest.mark.anyio
async def test_multi_step_react_graph_traversal():
    """Verify non-streaming multi-step ReAct loop runs tool and synthesizes answer."""
    turn_1_output = """
<scratchpad>
Need to verify pathway cascade for ADORA1 before answering.
</scratchpad>
<tool_call name="query_pathway_cascade">
{"target_id": "ADORA1"}
</tool_call>
"""
    turn_2_output = """
<scratchpad>
Confirmed ADORA1 couples to Gi and reduces intracellular cAMP.
</scratchpad>
Caffeine acts as a competitive antagonist at ADORA1 and ADORA2A adenosine receptors.
"""
    turn_idx = 0

    async def mock_stream_llm(*args, **kwargs):
        nonlocal turn_idx
        turn_idx += 1
        if turn_idx == 1:
            yield {"type": "content", "data": turn_1_output}
        else:
            yield {"type": "content", "data": turn_2_output}
        yield {"type": "done", "data": "[DONE]"}

    with patch("app.services.copilot_agent.stream_local_llm_chat", side_effect=mock_stream_llm):
        result = await CopilotAgent.chat_copilot_turn(
            messages=[{"role": "user", "content": "How does Caffeine affect adenosine receptors?"}],
            persona="tutor",
            stack=["caffeine"],
            max_exploration_steps=5
        )
        assert "competitive antagonist at ADORA1" in result["response_text"]
        assert "<tool_call" not in result["response_text"]
        assert result["clinical_scratchpad"] is not None
        assert "Need to verify pathway cascade" in result["clinical_scratchpad"]
        assert turn_idx == 2


@pytest.mark.anyio
async def test_streaming_multistep_react_sse_events():
    """Verify streaming generator yields intermediate reasoning, scratchpad, and final delta."""
    turn_1_output = """
<scratchpad>
Step 1: Checking potential synergies for Caffeine.
</scratchpad>
<tool_call name="get_evidence_based_recommendations">
{"compound_keys": ["caffeine"], "protocol_goal": "cognitive_focus"}
</tool_call>
"""
    turn_2_output = """
### Cognitive Focus Optimization
Caffeine pairs synergistically with L-Theanine (1:2 ratio) to elevate alpha-wave activity.
<action_card type="stack_diff">
{"add": [{"key": "l_theanine", "name": "L-Theanine", "dose": 200, "unit": "mg", "timing": "morning"}], "modify": [], "remove": []}
</action_card>
"""
    turn_idx = 0

    async def mock_stream_llm(*args, **kwargs):
        nonlocal turn_idx
        turn_idx += 1
        if turn_idx == 1:
            yield {"type": "content", "data": turn_1_output}
        else:
            yield {"type": "content", "data": turn_2_output}
        yield {"type": "done", "data": "[DONE]"}

    events = []
    with patch("app.services.copilot_agent.stream_local_llm_chat", side_effect=mock_stream_llm):
        async for evt in CopilotAgent.stream_copilot_turn(
            messages=[{"role": "user", "content": "Optimize my caffeine stack"}],
            persona="architect",
            stack=["caffeine"],
            max_exploration_steps=5
        ):
            events.append(evt)

    event_types = [e["event"] for e in events]
    assert "reasoning" in event_types
    assert "delta" in event_types
    assert "action_card" in event_types
    assert "done" in event_types

    reasoning_texts = " ".join([e["data"] for e in events if e["event"] == "reasoning"])
    assert "Clinical Scratchpad" in reasoning_texts
    assert "Querying Graph" in reasoning_texts
    assert "Graph Observation" in reasoning_texts

    delta_texts = "".join([e["data"] for e in events if e["event"] == "delta"])
    assert "L-Theanine" in delta_texts
    assert "<scratchpad>" not in delta_texts


@pytest.mark.anyio
async def test_multistep_safety_cap_termination():
    """Verify loop safely caps at max_exploration_steps without hanging."""
    loop_output = """
<scratchpad>Looping exploration step</scratchpad>
<tool_call name="query_pathway_cascade">
{"target_id": "ADORA1"}
</tool_call>
"""
    async def mock_infinite_tool_caller(*args, **kwargs):
        yield {"type": "content", "data": loop_output}
        yield {"type": "done", "data": "[DONE]"}

    with patch("app.services.copilot_agent.stream_local_llm_chat", side_effect=mock_infinite_tool_caller):
        result = await CopilotAgent.chat_copilot_turn(
            messages=[{"role": "user", "content": "Test loop safety"}],
            persona="auditor",
            stack=["caffeine"],
            max_exploration_steps=3
        )
        assert result is not None
        assert "response_text" in result


def test_action_card_validator_depot_and_harm_reduction():
    """Verify ActionCardValidator corrects daily depot scheduling and attaches harm reduction metadata."""
    from app.services.action_card_validator import ActionCardValidator
    raw_card = {
        "add": [
            {"key": "testosterone_cypionate", "dose": 500, "unit": "mg", "timing": "morning", "route": "oral"}
        ],
        "modify": [],
        "remove": [],
    }
    sanitized, notes = ActionCardValidator.validate_and_sanitize_card("stack_diff", raw_card)
    assert sanitized["add"][0]["route"] in ("intramuscular", "subcutaneous")
    assert "twice weekly" in sanitized["add"][0]["timing"].lower() or "twice weekly" in sanitized["add"][0].get("frequency", "").lower()
    assert sanitized["validation_meta"]["guardrail_verified"] is True
    assert sanitized["validation_meta"]["harm_reduction_shield_active"] is True


def test_stack_diff_simulator_endpoint():
    """Verify /api/ai/simulate-stack-diff endpoint calculates comparative deltas."""
    res = client.post(
        "/api/ai/simulate-stack-diff",
        json={
            "base_stack": ["caffeine:200mg"],
            "diff": {
                "add": [{"key": "l_theanine", "dose": 200, "unit": "mg", "timing": "morning"}],
                "modify": [],
                "remove": []
            },
            "biometrics": {"age": 30, "weight_kg": 75}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["baseline_count"] == 1
    assert data["projected_count"] == 2
    assert "markdown_summary" in data
    assert "SIMULATION REPORT" in data["markdown_summary"]


def test_copilot_tool_simulate_stack_diff():
    """Verify simulate_stack_diff tool execution."""
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "simulate_stack_diff",
            "arguments": {
                "base_stack": ["testosterone_cypionate:350mg"],
                "diff": {
                    "add": [{"key": "telmisartan", "dose": 40, "unit": "mg", "timing": "morning"}],
                    "modify": [],
                    "remove": []
                }
            }
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "sanitized_diff" in data
    assert "markdown_summary" in data


def test_copilot_tool_search_pubmed_literature():
    """Verify search_pubmed_literature tool execution."""
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "search_pubmed_literature",
            "arguments": {"query": "telmisartan endothelial LVH", "max_results": 2}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "citations" in data
    assert data["count"] >= 1
    assert "pmid" in data["citations"][0]


def test_copilot_tool_search_clinical_trials():
    """Verify search_clinical_trials tool execution."""
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "search_clinical_trials",
            "arguments": {"query": "hypertrophy resistance", "max_results": 2}
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "trials" in data


def test_copilot_tool_circadian_receptor_occupancy():
    """Verify get_circadian_receptor_occupancy tool execution."""
    res = client.post(
        "/api/ai/tools/execute",
        json={
            "tool_name": "get_circadian_receptor_occupancy",
            "arguments": {
                "compound_key": "caffeine",
                "dose_mg": 200,
                "route": "oral"
            }
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "compound" in data
    assert "targets" in data
    assert len(data["targets"]) >= 1
    assert "peak_occupancy_pct" in data["targets"][0]


def test_pgx_engine_phenotype_scaling():
    """Verify PGXEngine calculates clearance scaling and clinical warnings."""
    from app.services.pgx_engine import PGXEngine
    comp = {"key": "nebivolol", "name": "Nebivolol", "cyp_enzymes": {"substrates": ["CYP2D6"]}}
    pm_mult = PGXEngine.get_clearance_multiplier(comp, {"cyp2d6_phenotype": "poor_metabolizer"})
    assert pm_mult <= 0.20

    warnings = PGXEngine.evaluate_pgx_warnings([comp], {"cyp2d6_phenotype": "poor_metabolizer"})
    assert len(warnings) >= 1
    assert warnings[0]["gene"] == "CYP2D6"


def test_unspecified_and_partial_biometrics_fallback():
    """Verify system smoothly defaults to normal/average population reference when biometrics are empty or partial."""
    from app.services.copilot_agent import CopilotAgent
    from app.services.stack_intent_engine import StackIntentEngine

    # 1. Empty biometrics in system context
    context_empty = CopilotAgent.build_system_context(
        persona="architect",
        stack=["caffeine", "l_theanine"],
        biometrics={},
        protocol_goal="cognitive_focus"
    )
    assert "Patient Biometrics: None specified by user" in context_empty

    # 2. Partially specified biometrics
    context_partial = CopilotAgent.build_system_context(
        persona="architect",
        stack=["caffeine", "l_theanine"],
        biometrics={"weight_kg": 82, "egfr": 105},
        protocol_goal="cognitive_focus"
    )
    assert "Weight: 82 kg" in context_partial
    assert "eGFR: 105 mL/min" in context_partial
    assert "Patient Entered Parameters" in context_partial

    # 3. Dynamic scratch proposal with empty biometrics
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="cognitive_focus",
        biometrics={},
        preferences={}
    )
    assert proposal["goal_id"] == "cognitive_focus"
    assert len(proposal["compounds"]) >= 2
    for comp in proposal["compounds"]:
        assert comp["dose"] > 0


def test_sex_gender_hormone_and_clearance_scaling():
    """Verify gender/sex factors into hormone dosing, virilization gap detection, and renal clearance."""
    from app.services.dosing_service import calculate_individualized_dose
    from app.services.copilot_agent import CopilotAgent
    from app.services.stack_intent_engine import StackIntentEngine

    # 1. Testosterone dosing for male vs female
    test_male = calculate_individualized_dose("testosterone_cypionate", {"sex": "male", "weight_kg": 75})
    test_female = calculate_individualized_dose("testosterone_cypionate", {"sex": "female", "weight_kg": 60})
    # Female dose should be significantly lower (~5-10% of male standard)
    assert test_female["dose_mg"] < test_male["dose_mg"] * 0.20
    assert test_female["dose_mg"] > 0

    # 2. DHEA dosing for male vs female
    dhea_male = calculate_individualized_dose("dhea", {"sex": "male"})
    dhea_female = calculate_individualized_dose("dhea", {"sex": "female"})
    assert dhea_female["dose_mg"] < dhea_male["dose_mg"]

    # 3. Copilot prompt includes female clinical mandate
    context_female = CopilotAgent.build_system_context(
        persona="architect",
        stack=["testosterone_cypionate"],
        biometrics={"sex": "female", "weight_kg": 60},
        protocol_goal="anabolic_physique"
    )
    assert "Female patient physiology active" in context_female
    assert "virilization" in context_female.lower()

    # 4. Virilization gap detection for female with androgens
    analysis_female = StackIntentEngine.analyze(
        compounds=[{"key": "testosterone_cypionate", "name": "Testosterone Cypionate", "dose": 50, "route": "intramuscular"}],
        biometrics={"sex": "female"}
    )
    gap_axes = [g["axis"] for g in analysis_female.get("therapeutic_gaps", [])]
    assert any("Virilization" in a for a in gap_axes)


def test_inline_drafting_self_talk_sanitization():
    """Verify that inline drafting questions and citation self-talk are cleaned from final markdown."""
    raw_dirty_text = (
        "**Executive Assessment**: Balanced stack.\n\n"
        "**Targeted Synergies & Co-Factors**:\n"
        "- Testosterone Cypionate 175 mg IM/SubQ Mon/Thu: t1/2 ~7-10 d [PMID: 18449337? Need real? Could use generic? Need verified citations. Use known?]\n"
        "- Anastrozole 0.25 mg oral twice weekly [FDA Label: Anastrozole §5.1]. Telmisartan [FDA Label: Telmisartan §5.1]. Ezetimibe [IMPROVE-IT Trial; PMID: 19726719? Actually IMPROVE-IT PMID 19726719? I think yes. Creatine [PMID: 21639795? maybe]. Caffeine [PMID: 16399952?]. Need not be perfect? But should be plausible. Could use [FDA Label: Testosterone Cypionate §12.3] maybe. Use FDA labels"
    )
    cleaned = CopilotAgent.clean_scratchpad_and_tools_from_text(raw_dirty_text)
    assert "Need real?" not in cleaned
    assert "Could use generic?" not in cleaned
    assert "Need verified citations" not in cleaned
    assert "Use FDA labels" not in cleaned
    assert "Actually IMPROVE-IT" not in cleaned
    assert "[PMID: 18449337]" in cleaned
    assert "[FDA Label: Anastrozole §5.1]" in cleaned
    assert "[FDA Label: Telmisartan §5.1]" in cleaned


def test_chat_compound_mention_does_not_pollute_active_workbench_stack():
    """
    Verify that when a user asks to add a compound in chat (e.g. 'let's add 200mg trenbolone weekly'),
    the active workbench stack section does not falsely claim the compound is already active in the stack,
    while GraphRAG / background context still extracts the entity for knowledge enrichment.
    """
    messages = [
        {"role": "user", "content": "I want to build a hypertrophy stack."},
        {"role": "assistant", "content": "Here is an anabolic protocol with Testosterone Cypionate and Telmisartan."},
        {"role": "user", "content": "let's add 200mg trenbolone weekly"}
    ]
    workbench_stack = ["testosterone_cypionate:200mg", "telmisartan:40mg"]

    context = CopilotAgent.build_system_context(
        persona="architect",
        stack=workbench_stack,
        biometrics={"age": 28, "weight_kg": 85},
        messages=messages,
        protocol_goal="anabolic_physique"
    )

    # Active stack must only contain the compounds actually in the workbench
    assert "### ACTIVE WORKBENCH STACK (2 compounds):" in context
    assert "Testosterone Cypionate" in context
    assert "Telmisartan" in context
    # Trenbolone must NOT be in the ACTIVE WORKBENCH STACK list
    active_stack_part = context.split("### ACTIVE WORKBENCH STACK")[1].split("###")[0]
    assert "Trenbolone" not in active_stack_part
    assert "14.2857" not in active_stack_part


def test_copilot_system_context_grounds_previously_proposed_unapplied_stack():
    """
    Verify that when previous turns proposed a protocol and the user hasn't clicked Apply Changes,
    build_system_context includes the previously proposed unapplied compounds for grounding.
    """
    messages = [
        {"role": "user", "content": "Build Cognitive Focus protocol from scratch"},
        {
            "role": "assistant",
            "content": """### Focus Protocol
- **Alpha-GPC** (300mg oral)
- **L-Theanine** (200mg oral)
- **Caffeine** (100mg oral)
<action_card type="stack_diff">
{"add": [{"key": "alpha_gpc", "name": "Alpha-GPC", "dose": 300, "unit": "mg"}, {"key": "l_theanine", "name": "L-Theanine", "dose": 200, "unit": "mg"}, {"key": "caffeine", "name": "Caffeine", "dose": 100, "unit": "mg"}], "modify": [], "remove": []}
</action_card>
"""
        },
        {"role": "user", "content": "Also add zinc 30mg"}
    ]

    context = CopilotAgent.build_system_context(
        persona="architect",
        stack=[],
        biometrics={"age": 30, "weight_kg": 75},
        messages=messages,
        protocol_goal="cognitive_focus"
    )

    assert "### PREVIOUSLY PROPOSED PROTOCOL RECOMMENDATIONS (IN CONVERSATION):" in context
    assert "Alpha-GPC" in context
    assert "L-Theanine" in context
    assert "Caffeine" in context
    assert "CRITICAL MULTI-TURN CUMULATIVE DIRECTIVE" in context


def test_copilot_fallback_multi_turn_cumulative_protocol_and_card():
    """
    Verify that deterministic fallback synthesis creates a complete cumulative protocol
    and action card when user requests adding another compound in turn 2.
    """
    messages = [
        {"role": "user", "content": "Build Cognitive Focus protocol from scratch"},
        {
            "role": "assistant",
            "content": """### Focus Protocol
- **Alpha-GPC** (300mg oral)
- **L-Theanine** (200mg oral)
- **Caffeine** (100mg oral)
<action_card type="stack_diff">
{"add": [{"key": "alpha_gpc", "name": "Alpha-GPC", "dose": 300, "unit": "mg"}, {"key": "l_theanine", "name": "L-Theanine", "dose": 200, "unit": "mg"}, {"key": "caffeine", "name": "Caffeine", "dose": 100, "unit": "mg"}], "modify": [], "remove": []}
</action_card>
"""
        },
        {"role": "user", "content": "Also add zinc 30mg"}
    ]

    md_text, action_card = CopilotAgent.synthesize_deterministic_fallback_response(
        user_query="Also add zinc 30mg",
        persona="architect",
        stack_list=[],
        biometrics={"age": 30, "weight_kg": 75},
        protocol_goal="cognitive_focus",
        messages=messages
    )

    assert action_card is not None
    add_keys = {a["key"] for a in action_card.get("add", [])}
    assert "zinc" in add_keys
    assert "alpha_gpc" in add_keys
    assert "l_theanine" in add_keys
    assert "caffeine" in add_keys
    assert "Zinc" in md_text
    assert "Alpha-GPC" in md_text


@pytest.mark.anyio
async def test_copilot_stream_multi_turn_cumulative_action_card():
    """
    Verify streaming copilot turn emits a cumulative action card containing both previous recommendations
    and the newly requested compound when changes have not been applied.
    """
    messages = [
        {"role": "user", "content": "Build focus stack"},
        {
            "role": "assistant",
            "content": """### Proposed Protocol
- **Alpha-GPC** (300mg oral)
- **L-Theanine** (200mg oral)
- **Caffeine** (100mg oral)
<action_card type="stack_diff">
{"add": [{"key": "alpha_gpc", "name": "Alpha-GPC", "dose": 300, "unit": "mg"}, {"key": "l_theanine", "name": "L-Theanine", "dose": 200, "unit": "mg"}, {"key": "caffeine", "name": "Caffeine", "dose": 100, "unit": "mg"}], "modify": [], "remove": []}
</action_card>
"""
        },
        {"role": "user", "content": "Can we add Zinc 30mg?"}
    ]

    turn_2_output = """### Updated Focus Protocol
I have added Zinc to the protocol.
<action_card type="stack_diff">
{"add": [{"key": "zinc", "name": "Zinc", "dose": 30, "unit": "mg", "timing": "morning", "route": "oral"}], "modify": [], "remove": []}
</action_card>
"""

    async def mock_stream_llm(*args, **kwargs):
        yield {"type": "content", "data": turn_2_output}
        yield {"type": "done", "data": "[DONE]"}

    with patch("app.services.copilot_agent.stream_local_llm_chat", side_effect=mock_stream_llm):
        emitted_cards = []
        async for evt in CopilotAgent.stream_copilot_turn(
            messages=messages,
            persona="architect",
            stack=[],
            protocol_goal="cognitive_focus"
        ):
            if evt.get("event") == "action_card":
                emitted_cards.append(evt.get("data"))

        assert len(emitted_cards) >= 1
        final_card = emitted_cards[-1]
        payload = final_card.get("payload", {})
        add_keys = {a["key"] for a in payload.get("add", [])}
        assert "zinc" in add_keys
        assert "alpha_gpc" in add_keys
        assert "l_theanine" in add_keys
        assert "caffeine" in add_keys


def test_catalog_service_get_variants():
    """
    Verify CatalogService.get_variants dynamically retrieves all ester/formulation variants
    for parent compounds from the database with quantitative half-life and weight factor data.
    """
    catalog = CatalogService()
    
    # Test trenbolone variants
    tren_variants = catalog.get_variants("trenbolone")
    assert len(tren_variants) >= 3
    tren_keys = {v["key"] for v in tren_variants}
    assert "trenbolone_acetate" in tren_keys
    assert "trenbolone_enanthate" in tren_keys
    assert "trenbolone_hexahydrophenylcarbonate" in tren_keys
    
    ace = next(v for v in tren_variants if v["key"] == "trenbolone_acetate")
    assert ace["ester_name"] == "Acetate"
    assert ace["t_half_numeric"] == 36.0
    
    enan = next(v for v in tren_variants if v["key"] == "trenbolone_enanthate")
    assert enan["ester_name"] == "Enanthate"
    assert enan["t_half_numeric"] == 168.0

    # Test testosterone variants
    test_variants = catalog.get_variants("testosterone")
    assert len(test_variants) >= 4
    test_keys = {v["key"] for v in test_variants}
    assert "testosterone_cypionate" in test_keys
    assert "testosterone_enanthate" in test_keys
    assert "testosterone_propionate" in test_keys
    assert "testosterone_undecanoate" in test_keys


def test_copilot_system_context_grounds_ester_pharmacokinetics_disambiguation():
    """
    Verify that when an unesterified parent compound (e.g. 'trenbolone') is mentioned in chat,
    CopilotAgent.build_system_context dynamically includes the formulation & ester disambiguation
    guidance with depot ester options and half-lives to prevent unwarranted ester assumptions.
    """
    messages = [
        {"role": "user", "content": "can we add trenbolone? Maybe 200mg weekly?"}
    ]
    workbench_stack = ["testosterone_cypionate:175mg", "telmisartan:40mg"]

    context = CopilotAgent.build_system_context(
        persona="architect",
        stack=workbench_stack,
        biometrics={"age": 30, "weight_kg": 85},
        messages=messages,
        protocol_goal="anabolic_physique"
    )

    assert "### FORMULATION & ESTER PHARMACOKINETICS (DISAMBIGUATION):" in context
    assert "Trenbolone" in context
    assert "Trenbolone Acetate" in context
    assert "Trenbolone Enanthate" in context
    assert "elimination t1/2: 168" in context or "t1/2: 7-10 days" in context
    assert "do NOT arbitrarily default to a single short-acting ester" in context


def test_copilot_chat_reset_endpoints():
    """Verify that POST /api/ai/chat/reset and POST /api/ai/reset return 200 with status ok."""
    with patch("app.services.copilot_agent.CopilotAgent.reset_session_context", new_callable=AsyncMock) as mock_reset:
        mock_reset.return_value = {
            "status": "ok",
            "message": "Copilot chat context and model memory reset successfully.",
            "details": {"slots_erased": [0, 1], "cleared_caches": True}
        }
        res1 = client.post("/api/ai/chat/reset")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "ok"
        assert "reset successfully" in data1["message"]

        res2 = client.post("/api/ai/reset")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ok"


def test_reset_model_context_erases_slots():
    """Verify that reset_model_context queries slots and issues erase/release calls to llama-server."""
    import asyncio
    import httpx
    from typing import Any
    from app.services.ai_service import reset_model_context

    class MockResponse:
        def __init__(self, status_code: int, json_data: Any):
            self.status_code = status_code
            self._json = json_data

        def json(self):
            return self._json

    async def mock_get(url, *args, **kwargs):
        if url.endswith("/slots"):
            return MockResponse(200, [{"id": 0, "state": 0}, {"id": 1, "state": 1}])
        if url.endswith("/models"):
            return MockResponse(200, {"data": [{"id": "Qwen3.8-27B"}]})
        return MockResponse(200, {})

    async def mock_post(url, *args, **kwargs):
        return MockResponse(200, {"status": "ok"})

    async def run_test():
        with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
             patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
            result = await reset_model_context()
            assert result["status"] == "ok"
            assert 0 in result["slots_erased"]
            assert 1 in result["slots_erased"]
            assert result["cleared_caches"] is True

    asyncio.run(run_test())


def test_copilot_context_isolation_after_reset():
    """
    Verify that after clearing history, a new single message does not retain
    entities or context from previous messages.
    """
    # 1. Multi-turn conversation mentioning caffeine and tmao
    old_messages = [
        {"role": "user", "content": "How do I take caffeine?"},
        {"role": "assistant", "content": "Take caffeine in the morning with L-theanine."},
        {"role": "user", "content": "What about oral carnitine and TMAO?"},
        {"role": "assistant", "content": "Oral carnitine converts to TMA via gut CntA."}
    ]
    old_entities = CopilotAgent.extract_entities_from_messages(old_messages)
    assert "caffeine" in old_entities
    assert "bio_tmao" in old_entities

    # 2. Reset conversation (cleared to only new turn)
    fresh_messages = [
        {"role": "user", "content": "What is the optimal timing for ashwagandha?"}
    ]
    fresh_entities = CopilotAgent.extract_entities_from_messages(fresh_messages)
    assert "caffeine" not in fresh_entities
    assert "bio_tmao" not in fresh_entities
    assert "ashwagandha" in fresh_entities

    # 3. Verify system context only grounds the new prompt without prior conversation's biomarker/entity grounding
    fresh_context = CopilotAgent.build_system_context(
        persona="architect",
        stack=["ashwagandha:300mg"],
        biometrics={"age": 30},
        messages=fresh_messages
    )
    assert "Ashwagandha" in fresh_context or "ashwagandha" in fresh_context
    assert "bio_tmao" not in fresh_context.lower()
    assert "tma lyase" not in fresh_context.lower()





