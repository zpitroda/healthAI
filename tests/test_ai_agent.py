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
