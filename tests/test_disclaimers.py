import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_disclaimer_api_endpoint(client):
    """Verify that /api/disclaimer returns complete, structured disclaimer data."""
    response = client.get("/api/disclaimer")
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "version" in data
    assert "sections" in data
    assert "medical_disclaimer" in data["sections"]
    assert "computational_scope" in data["sections"]
    assert "terms_and_liability" in data["sections"]
    assert "emergency_notice" in data["sections"]
    assert "emergency_contacts" in data
    assert "1-800-222-1222" in data["emergency_contacts"]["us_poison_control"]


def test_openapi_disclaimer_metadata(client):
    """Verify that OpenAPI schema includes terms of service, description disclaimers, and license."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    info = schema.get("info", {})
    assert "termsOfService" in info
    assert "MEDICAL & SCIENTIFIC RESEARCH NOTICE" in info.get("description", "")
    assert "License" in info.get("license", {}).get("name", "")


def test_protocol_endpoint_includes_disclaimer(client):
    """Verify that /protocol response contains disclaimer annotation."""
    payload = {
        "weight_kg": 75,
        "age": 30,
        "sex": "male",
        "goals": ["focus", "cognition"],
    }
    response = client.post("/protocol", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "disclaimer" in data
    assert "Not medical advice" in data["disclaimer"]


def test_interaction_matrix_endpoint_includes_disclaimer(client):
    """Verify that /api/interactions/matrix response contains disclaimer annotation."""
    payload = {
        "stack": ["caffeine 100mg", "l_theanine 200mg"],
        "age": 30,
        "weight_kg": 75,
    }
    response = client.post("/api/interactions/matrix", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "disclaimer" in data
    assert "Not medical advice" in data["disclaimer"]


def test_static_disclaimer_assets_served(client):
    """Verify that disclaimer.js and disclaimer.css are properly served as static assets."""
    resp_js = client.get("/static/js/disclaimer.js")
    assert resp_js.status_code == 200
    assert "HealthAIDisclaimer" in resp_js.text

    resp_css = client.get("/static/css/disclaimer.css")
    assert resp_css.status_code == 200
    assert ".global-disclaimer-footer" in resp_css.text


def test_html_pages_contain_disclaimer_assets(client):
    """Verify that core HTML pages reference disclaimer assets and topbar elements."""
    pages = ["/", "/compound?key=caffeine", "/graph", "/admin", "/debug"]
    for path in pages:
        res = client.get(path)
        assert res.status_code == 200
        assert "disclaimer.css" in res.text, f"disclaimer.css missing in {path}"
        assert "disclaimer.js" in res.text, f"disclaimer.js missing in {path}"
        assert "Disclaimer" in res.text, f"Disclaimer element missing in {path}"
