import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_service import is_quota_exceeded_error, QuotaExhaustedException

client = TestClient(app)


def test_is_quota_exceeded_error_detection():
    # HTTP 402 Payment Required
    assert is_quota_exceeded_error(402, "") is True
    assert is_quota_exceeded_error(402, "Payment Required") is True

    # Quota / Credit text keywords
    assert is_quota_exceeded_error(400, "User has insufficient credits") is True
    assert is_quota_exceeded_error(429, "You have exceeded your current quota, please check your plan and billing details.") is True
    assert is_quota_exceeded_error(403, "Out of credits. Please purchase more tokens.") is True
    assert is_quota_exceeded_error(401, "insufficient_quota") is True
    assert is_quota_exceeded_error(500, "Token budget exhausted for account") is True

    # Unrelated errors
    assert is_quota_exceeded_error(200, "OK") is False
    assert is_quota_exceeded_error(404, "Model not found") is False
    assert is_quota_exceeded_error(500, "Internal server error") is False


def test_validate_api_key_empty():
    res = client.post("/api/ai/validate-key", json={"api_key": "   "})
    assert res.status_code == 400


def test_validate_api_key_valid():
    mock_res = AsyncMock()
    mock_res.status_code = 200
    mock_res.json = lambda: {"data": [{"id": "qwen/qwen3.8-27b"}, {"id": "openai/gpt-4o"}]}

    with patch("httpx.AsyncClient.get", return_value=mock_res):
        res = client.post("/api/ai/validate-key", json={"api_key": "sk-or-v1-testkey123"})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["status"] == "valid"
        assert data["models_count"] == 2


def test_validate_api_key_quota_exceeded():
    mock_res = AsyncMock()
    mock_res.status_code = 402
    mock_res.text = "Account has run out of credits"

    with patch("httpx.AsyncClient.get", return_value=mock_res):
        res = client.post("/api/ai/validate-key", json={"api_key": "sk-or-v1-emptykey"})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert data["status"] == "quota_exceeded"


def test_copilot_chat_with_custom_key_header():
    mock_turn = {
        "text": "Protocol designed with custom key.",
        "action_card": None,
        "suggested_actions": []
    }
    with patch("app.services.copilot_agent.CopilotAgent.chat_copilot_turn", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = mock_turn
        res = client.post(
            "/api/ai/chat",
            headers={"X-User-API-Key": "sk-or-v1-my-custom-key"},
            json={
                "messages": [{"role": "user", "content": "Optimize my stack"}],
                "stack": ["caffeine"],
            }
        )
        assert res.status_code == 200
        mock_agent.assert_called_once()
        _, kwargs = mock_agent.call_args
        assert kwargs.get("user_api_key") == "sk-or-v1-my-custom-key"


def test_copilot_chat_quota_exhausted_returns_402():
    with patch("app.services.copilot_agent.CopilotAgent.chat_copilot_turn", side_effect=QuotaExhaustedException("Admin token budget exhausted")):
        res = client.post(
            "/api/ai/chat",
            json={
                "messages": [{"role": "user", "content": "Optimize my stack"}],
            }
        )
        assert res.status_code == 402
        assert "token budget exhausted" in res.json()["detail"].lower()


def test_copilot_stream_quota_exhausted_event():
    async def mock_stream_turn(*args, **kwargs):
        yield {"event": "quota_exceeded", "data": {"message": "Admin OpenRouter token budget has been exhausted.", "code": "QUOTA_EXHAUSTED"}}

    with patch("app.services.copilot_agent.CopilotAgent.stream_copilot_turn", side_effect=mock_stream_turn):
        res = client.post(
            "/api/ai/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Help me build a stack"}],
            }
        )
        assert res.status_code == 200
        content = res.text
        assert "event: quota_exceeded" in content
        assert "QUOTA_EXHAUSTED" in content
