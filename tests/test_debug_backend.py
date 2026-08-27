import logging
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.debug_service import ring_buffer_handler, setup_debug_logging, SystemDiagnostics

client = TestClient(app)


def test_setup_debug_logging_and_ring_buffer():
    setup_debug_logging()
    test_logger = logging.getLogger("healthai.test_logger")
    test_logger.setLevel(logging.DEBUG)

    ring_buffer_handler.clear()
    assert ring_buffer_handler.count == 0

    test_logger.info("Test info message")
    test_logger.warning("Test warning message")
    test_logger.error("Test error message")

    assert ring_buffer_handler.count == 3
    logs = ring_buffer_handler.get_logs()
    assert len(logs) == 3
    assert logs[0]["message"] == "Test info message"
    assert logs[1]["level"] == "WARNING"
    assert logs[2]["level"] == "ERROR"


def test_get_logs_api():
    ring_buffer_handler.clear()
    logger = logging.getLogger("healthai.api_test")
    logger.info("API log 1")
    logger.error("API log 2")

    response = client.get("/api/debug/logs")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert data["count"] >= 2

    response_filtered = client.get("/api/debug/logs?min_level=ERROR")
    assert response_filtered.status_code == 200
    filtered_data = response_filtered.json()
    assert all(log["level"] in ["ERROR", "CRITICAL"] for log in filtered_data["logs"])


def test_system_diagnostics_api():
    response = client.get("/api/debug/system")
    assert response.status_code == 200
    data = response.json()
    assert "platform" in data
    assert "python_version" in data
    assert "memory" in data
    assert "sqlite_status" in data


def test_loggers_list_and_level_change():
    response = client.get("/api/debug/loggers")
    assert response.status_code == 200
    loggers_data = response.json()
    assert "loggers" in loggers_data
    assert len(loggers_data["loggers"]) > 0

    # Change level for a test logger
    test_logger_name = "healthai.dynamic_test"
    set_level_res = client.post(
        "/api/debug/log-level",
        json={"logger_name": test_logger_name, "level_name": "WARNING"},
    )
    assert set_level_res.status_code == 200
    assert logging.getLogger(test_logger_name).level == logging.WARNING


def test_debug_eval_endpoints():
    # Test catalog eval
    cat_res = client.post(
        "/api/debug/eval",
        json={"eval_type": "catalog", "query": "caffeine"},
    )
    assert cat_res.status_code == 200
    assert cat_res.json()["success"] is True

    # Test collision eval
    col_res = client.post(
        "/api/debug/eval",
        json={
            "eval_type": "collision",
            "stack": [
                {"compound_key": "caffeine", "dose_mg": 200},
                {"compound_key": "l-theanine", "dose_mg": 200},
            ],
        },
    )
    assert col_res.status_code == 200
    assert col_res.json()["success"] is True

    # Test python snippet eval
    snip_res = client.post(
        "/api/debug/eval",
        json={
            "eval_type": "snippet",
            "code": "x = 10 + 20\nresult = x",
        },
    )
    assert snip_res.status_code == 200
    assert snip_res.json()["success"] is True
    assert snip_res.json()["data"]["result"] == 30


def test_websocket_logs_endpoint():
    with client.websocket_connect("/api/debug/ws/logs") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"
        assert isinstance(data["data"], list)


def test_debug_view_html():
    response = client.get("/debug")
    assert response.status_code == 200
    assert "healthAI // Debug & Logging" in response.text
