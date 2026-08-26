import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.protocol_agent import optimize_protocol

client = TestClient(app)

@pytest.fixture
def anyio_backend():
    return 'asyncio'

def test_ai_optimize_protocol_endpoint_validation():
    # Empty stack should return 400
    res = client.post("/api/ai/optimize-protocol", json={"stack": [], "biometrics": {}})
    assert res.status_code == 400

    # Stack with only nulls/empty strings should return 400
    res2 = client.post("/api/ai/optimize-protocol", json={"stack": [None, ""], "biometrics": {}})
    assert res2.status_code == 400

def test_ai_optimize_protocol_endpoint_success():
    mock_res = {
        "dosage_adjustments": [],
        "scheduling": [],
        "countermeasures": [],
        "summary_analysis": "All optimal."
    }
    with patch("app.routers.ai.optimize_protocol", new_callable=AsyncMock) as mock_opt:
        mock_opt.return_value = mock_res
        res = client.post("/api/ai/optimize-protocol", json={"stack": ["caffeine", "theanine"], "biometrics": {"age": 30}})
        assert res.status_code == 200
        assert res.json()["summary_analysis"] == "All optimal."
        mock_opt.assert_called_once_with(["caffeine", "theanine"], {"age": 30})

@pytest.mark.anyio
async def test_optimize_protocol_service():
    mock_ai_response = {
        "dosage_adjustments": [
            {
                "compound": "Telmisartan",
                "adjustment_reasoning": "eGFR preserved, standard titration",
                "recommended_dose_change": "Maintain standard 40mg"
            }
        ],
        "scheduling": [
            {
                "compound": "Telmisartan",
                "timing": "Morning",
                "reasoning": "24h half-life"
            }
        ],
        "countermeasures": [],
        "summary_analysis": "Safe balanced protocol."
    }

    with patch("app.services.protocol_agent.ask_local_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_ai_response
        
        result = await optimize_protocol(
            stack=["telmisartan"],
            biometrics={"age": 35, "weight_kg": 75, "egfr": 95}
        )
        
        assert result["summary_analysis"] == "Safe balanced protocol."
        assert len(result["dosage_adjustments"]) == 1
        assert result["dosage_adjustments"][0]["compound"] == "Telmisartan"


def test_qwen3_json_extractor_clean():
    from app.services.ai_service import _extract_json_from_llm_response

    # Standard clean JSON
    res = _extract_json_from_llm_response('{"status": "ok", "dose": 40}')
    assert res == {"status": "ok", "dose": 40}


def test_qwen3_json_extractor_with_think_tags():
    from app.services.ai_service import _extract_json_from_llm_response

    # Qwen3 output with <think>...</think> reasoning before JSON
    raw_output = """<think>
Evaluating patient eGFR of 95 mL/min and BP 120/80.
Telmisartan 40mg is appropriate.
</think>
{"dosage_adjustments": [{"compound": "Telmisartan", "dose": 40}], "summary": "Optimal"}"""

    res = _extract_json_from_llm_response(raw_output)
    assert res["summary"] == "Optimal"
    assert res["dosage_adjustments"][0]["compound"] == "Telmisartan"


def test_qwen3_json_extractor_with_markdown_fence():
    from app.services.ai_service import _extract_json_from_llm_response

    raw_output = """Here is the clinical protocol optimization:
```json
{
    "active_stack": ["telmisartan", "nebivolol"],
    "balanced": true
}
```
Protocol complete."""

    res = _extract_json_from_llm_response(raw_output)
    assert res["active_stack"] == ["telmisartan", "nebivolol"]
    assert res["balanced"] is True


@pytest.mark.anyio
async def test_qwen3_model_resolution():
    from app.services.ai_service import get_best_available_model, MODEL_PREFERENCES

    # Both qwen3.8:27b and qwen3.6:27b should be in priority tier
    assert "qwen3.8:27b" in MODEL_PREFERENCES[:4]
    assert "qwen3.6:27b" in MODEL_PREFERENCES[:4]

    # Explicit preference passed
    resolved_local = await get_best_available_model(preferred_model="qwen3.8:27b")
    assert "qwen" in resolved_local.lower()

    resolved_live = await get_best_available_model(preferred_model="qwen3.6:27b")
    assert "qwen" in resolved_live.lower()

