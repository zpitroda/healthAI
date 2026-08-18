import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.services.ingestion_queue import get_ingestion_queue, IngestionJobStatus


def test_submit_and_get_enrichment_job():
    client = TestClient(app)

    # Submit job
    response = client.post(
        "/api/enrichment/jobs",
        json={"compounds": ["telmisartan"], "auto_save_catalog": False},
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    job_id = data["job_id"]
    assert data["compounds"] == ["telmisartan"]
    assert data["status"] in (IngestionJobStatus.QUEUED, IngestionJobStatus.RUNNING, IngestionJobStatus.COMPLETED)

    # Fetch job status
    get_resp = client.get(f"/api/enrichment/jobs/{job_id}")
    assert get_resp.status_code == 200
    job_data = get_resp.json()
    assert job_data["job_id"] == job_id
    assert "logs" in job_data


def test_list_enrichment_jobs():
    client = TestClient(app)

    # Submit two jobs
    client.post("/api/enrichment/jobs", json={"compounds": ["aspirin"]})
    client.post("/api/enrichment/jobs", json={"compounds": ["caffeine"]})

    list_resp = client.get("/api/enrichment/jobs")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert "jobs" in data
    assert len(data["jobs"]) >= 2


def test_websocket_enrichment_stream():
    client = TestClient(app)

    # Connect to global WebSocket
    with client.websocket_connect("/ws/enrichment") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_json()
        assert data.get("event") == "pong"


def test_websocket_specific_job_stream():
    client = TestClient(app)

    # Create job first
    submit_resp = client.post("/api/enrichment/jobs", json={"compounds": ["theanine"]})
    job_id = submit_resp.json()["job_id"]

    with client.websocket_connect(f"/ws/enrichment/{job_id}") as websocket:
        data = websocket.receive_json()
        assert data.get("event") == "job_status"
        assert data.get("job", {}).get("job_id") == job_id
