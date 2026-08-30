import pytest
import re
from unittest.mock import AsyncMock, patch

from app.services.copilot_agent import CopilotAgent, CopilotSourceCollector


def test_copilot_source_collector_literature_and_engines():
    collector = CopilotSourceCollector()
    collector.record_literature_citation(
        pmid="18378520",
        doi="10.1056/NEJMoa0801317",
        title="Telmisartan, ramipril, or both in patients at high risk for vascular events (ONTARGET)",
        journal="N Engl J Med",
        pub_year="2008",
        authors=["Yusuf S", "Teo KK", "et al."],
        clinical_finding="Demonstrated potent AT1 blockade.",
        compound_name="Telmisartan",
    )
    collector.record_clinical_trial("NCT01234567", title="Phase 3 Study of Cardiovascular Protection", phase="Phase 3", status="Completed")
    collector.record_database_registry("ChEMBL", "CHEMBL25", "ADRB2 target profile")
    collector.record_guideline("FDA", "FDA Structured Product Labeling: §5.1 Boxed Warning", "Official FDA Drug Prescribing Information")
    collector.record_engine("HealthAI Steady-State PK/PD Clearance & Fluctuation Engine", "1- & 2-compartment elimination kinetics")

    md = collector.format_sources_markdown()
    assert "### 📚 Sources & Scientific Evidence Base" in md
    assert "[PMID: 18378520]" in md
    assert "N Engl J Med (2008)" in md
    assert "[NCT: NCT01234567]" in md
    assert "[ChEMBL: CHEMBL25]" in md
    assert "FDA Structured Product Labeling" in md
    # Assert computational engines are omitted from the user-facing sources footer
    assert "Computational Pharmacology Models" not in md


def test_copilot_source_collector_append_before_action_card():
    collector = CopilotSourceCollector()
    collector.record_literature_citation(pmid="26039521", title="Allicin TMAO study")

    sample_text = """### Protocol Assessment
Recommended protocol for patient.

<action_card type="stack_diff">
{"add": [{"key": "allicin", "dose": 10, "unit": "mg"}]}
</action_card>"""

    result = collector.append_to_response(sample_text)
    assert "### 📚 Sources & Scientific Evidence Base" in result
    assert result.find("### 📚 Sources & Scientific Evidence Base") < result.find("<action_card")
    assert "[PMID: 26039521]" in result


def test_format_deterministic_protocol_markdown_includes_sources():
    proposal = {
        "goal_id": "cognitive_focus",
        "goal_title": "Cognitive Focus & Sustained Attention",
        "compounds": [
            {
                "name": "Caffeine",
                "dose": 100,
                "unit": "mg",
                "route": "oral",
                "timing": "morning",
                "frequency": "daily",
                "target": "Adenosine A1/A2A antagonist",
                "rationale": "Boosts vigilance",
                "pmid": "18088200",
                "citation_str": "PMID: 18088200 - Smith et al., 2008",
            }
        ],
    }

    md = CopilotAgent.format_deterministic_protocol_markdown(proposal, persona="architect")
    assert "### ⚡ HealthAI ARCHITECT Grounded Protocol: Cognitive Focus & Sustained Attention" in md
    assert "### 📚 Sources & Scientific Evidence Base" in md
    assert "[PMID: 18088200]" in md
    assert "Computational Pharmacology Models" not in md


def test_synthesize_deterministic_fallback_scenarios_include_sources():
    # Scenario 1: TMAO query
    tmao_text, _ = CopilotAgent.synthesize_deterministic_fallback_response(
        user_query="How to mitigate TMAO from l-carnitine?",
        persona="architect",
        stack_list=["l_carnitine"],
        biometrics={},
    )
    assert "### 📚 Sources & Scientific Evidence Base" in tmao_text
    assert "[PMID: 26039521]" in tmao_text
    assert "Computational Pharmacology Models" not in tmao_text

    # Scenario 2: Safety / Auditor query
    audit_text, _ = CopilotAgent.synthesize_deterministic_fallback_response(
        user_query="Is this stack safe from CYP conflicts?",
        persona="auditor",
        stack_list=["telmisartan", "caffeine"],
        biometrics={},
    )
    assert "### 📚 Sources & Scientific Evidence Base" in audit_text
    assert "[FDA Label]" in audit_text or "FDA" in audit_text

    # Scenario 3: Tutor query
    tutor_text, _ = CopilotAgent.synthesize_deterministic_fallback_response(
        user_query="Explain the mechanism of action and receptor affinity",
        persona="tutor",
        stack_list=["caffeine"],
        biometrics={},
    )
    assert "### 📚 Sources & Scientific Evidence Base" in tutor_text
    assert "[Reactome" in tutor_text or "Reactome" in tutor_text

    # Scenario 4: Labs query
    labs_text, _ = CopilotAgent.synthesize_deterministic_fallback_response(
        user_query="Interpret my blood test results",
        persona="labs",
        stack_list=[],
        biometrics={"egfr": 90, "alt_u_l": 22},
    )
    assert "### 📚 Sources & Scientific Evidence Base" in labs_text
    assert "Clinical Standards" in labs_text


def test_chat_copilot_turn_appends_sources():
    import asyncio

    async def mock_stream_chat(*args, **kwargs):
        yield {"type": "content", "data": "Analysis of the stack shows high synergy [PMID: 18378520]."}

    async def _test():
        with patch("app.services.copilot_agent.stream_local_llm_chat", side_effect=mock_stream_chat):
            result = await CopilotAgent.chat_copilot_turn(
                messages=[{"role": "user", "content": "How is telmisartan for organ protection?"}],
                persona="architect",
                stack=["telmisartan"],
                biometrics={"weight_kg": 75},
            )
            resp = result.get("response_text", "")
            assert "Analysis of the stack shows high synergy" in resp
            assert "### 📚 Sources & Scientific Evidence Base" in resp
            assert "[PMID: 18378520]" in resp

    asyncio.run(_test())


def test_stream_copilot_turn_emits_sources_delta():
    import asyncio

    async def mock_stream_chat(*args, **kwargs):
        yield {"type": "content", "data": "Executive Assessment: Synergistic schedule formulated [PMID: 18378520].\n\n<action_card type=\"stack_diff\">{\"add\": [{\"key\": \"telmisartan\", \"dose\": 40, \"unit\": \"mg\"}]}</action_card>"}

    async def _test():
        events = []
        with patch("app.services.copilot_agent.stream_local_llm_chat", side_effect=mock_stream_chat):
            async for evt in CopilotAgent.stream_copilot_turn(
                messages=[{"role": "user", "content": "Build me a protocol"}],
                persona="architect",
                stack=["telmisartan"],
                biometrics={},
            ):
                events.append(evt)

        deltas = [e["data"] for e in events if e.get("event") == "delta"]
        combined_delta = "".join(deltas)
        assert "Executive Assessment" in combined_delta
        assert "### 📚 Sources & Scientific Evidence Base" in combined_delta
        assert "[PMID: 18378520]" in combined_delta
        assert "Computational Pharmacology Models" not in combined_delta
        assert any(e.get("event") == "action_card" for e in events)

    asyncio.run(_test())
