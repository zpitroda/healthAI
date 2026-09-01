from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "healthAI"
    assert data["version"] == "2.0.0"


def test_search_compounds_api():
    response = client.get("/api/compounds/search", params={"q": "caff"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(c["key"] == "caffeine" for c in data)


def test_catalog_endpoints():
    # List catalog
    response = client.get("/catalog", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 5

    # Get single item
    response = client.get("/catalog/caffeine")
    assert response.status_code == 200
    assert response.json()["key"] == "caffeine"

    # Get non-existent item
    response = client.get("/catalog/non_existent_compound_123", params={"auto_enrich": False})
    assert response.status_code == 404

    # Upsert custom item
    new_compound = {
        "key": "test_compound_endpoint",
        "name": "Test Compound Endpoint",
        "drug_class": "nootropic",
        "mechanism": "Enhances cognitive test capability",
        "receptor_targets": [],
    }
    response = client.post("/catalog", json=new_compound)
    assert response.status_code == 200
    assert response.json()["key"] == "test_compound_endpoint"

    # Delete custom item
    response = client.delete("/catalog/test_compound_endpoint")
    assert response.status_code == 200
    assert response.json()["deleted"] == "test_compound_endpoint"

    # Delete non-existent item
    response = client.delete("/catalog/test_compound_endpoint")
    assert response.status_code == 404


def test_protocol_endpoint():
    payload = {
        "goals": ["strength", "focus"],
        "experience": "intermediate",
        "sex": "male",
        "age": 28,
        "weight_kg": 80.0,
        "height_cm": 180.0,
        "sleep_hours": 7.0,
        "labs": {
            "testosterone_ng_dl": 650.0,
            "hematocrit_pct": 46.0,
            "ldl_mg_dl": 95.0,
            "alt_u_l": 22.0,
        },
    }
    response = client.post("/protocol", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "stack" in data
    assert "summary" in data
    assert "cumulative_risk_score" in data
    assert any(c["compound"] == "Creatine" for c in data["stack"])


def test_interaction_matrix_api_endpoint():
    payload = {
        "stack": ["caffeine", "theanine", "berberine"],
        "blood_pressure": 120,
        "sleep_hours": 7.5,
        "labs": {
            "alt_u_l": 25,
            "hematocrit_pct": 46,
            "blood_pressure": 120,
        },
    }
    response = client.post("/api/interactions/matrix", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "cumulative_risk_score" in data
    assert "matrix" in data
    assert len(data["matrix"]) == 3
    assert len(data["matrix"][0]) == 3
    assert data["risk_band"] in {"MINIMAL", "LOW", "MODERATE", "ELEVATED", "SEVERE"}
    assert "breakdown" in data
    assert "cyp_conflicts" in data["breakdown"]
    assert "synergistic_benefits" in data["breakdown"]


def test_html_views_serve():
    for path in ["/", "/admin", "/graph", "/compound/caffeine"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


def test_favicon_and_manifest_endpoints():
    ico_res = client.get("/favicon.ico")
    assert ico_res.status_code == 200
    assert "image/x-icon" in ico_res.headers.get("content-type", "")

    svg_res = client.get("/favicon.svg")
    assert svg_res.status_code == 200
    assert "image/svg+xml" in svg_res.headers.get("content-type", "")

    manifest_res = client.get("/site.webmanifest")
    assert manifest_res.status_code == 200
    assert "manifest" in manifest_res.headers.get("content-type", "")

    # Verify /graph contains domain filter matrix buttons
    graph_html = client.get("/graph").text
    assert "data-filter=\"all\"" in graph_html
    assert "data-filter=\"pd\"" in graph_html
    assert "data-filter=\"pk\"" in graph_html
    assert "data-filter=\"outcomes\"" in graph_html
    assert "Pharmacodynamics (PD)" in graph_html
    assert "Pharmacokinetics (PK)" in graph_html
    assert "Biomarkers &amp; Outcomes" in graph_html or "Biomarkers & Outcomes" in graph_html


def test_graph_data_endpoint_enriched_tiers_and_path():
    # Test /graph-data with multi-compound stack
    response = client.get("/graph-data", params={"stack": ["caffeine", "theanine"]})
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0

    # Verify node tier enrichment
    first_node = data["nodes"][0]
    assert "tier" in first_node
    assert "tier_name" in first_node
    assert "degree" in first_node

    # Verify compound nodes have tier 0
    compound_nodes = [n for n in data["nodes"] if n["node_type"] == "compound"]
    assert len(compound_nodes) >= 2
    for cn in compound_nodes:
        assert cn["tier"] == 0
        assert cn["tier_name"] == "Compound"

    # Verify edge direction_class
    if data["edges"]:
        first_edge = data["edges"][0]
        assert "direction_class" in first_edge
        assert first_edge["direction_class"] in {"positive", "negative", "allosteric", "metabolic", "neutral"}

    # Test /graph-path endpoint
    caff_node = "caffeine"
    path_resp = client.get("/graph-path", params={"source": caff_node, "target": data["nodes"][-1]["id"], "stack": ["caffeine", "theanine"]})
    assert path_resp.status_code == 200
    path_data = path_resp.json()
    assert "path" in path_data
    assert "length" in path_data


def test_single_compound_graph_pk_pd_connectivity():
    # Test single compound graph for caffeine
    response = client.get("/graph-data", params={"stack": ["caffeine"], "depth": 5})
    assert response.status_code == 200
    data = response.json()
    nodes = data["nodes"]
    edges = data["edges"]

    # Verify both PK nodes (CYP1A2) and PD nodes (Adenosine Receptor, Pathways, Biomarkers) exist
    node_ids = [n["id"] for n in nodes]
    node_types = [n["node_type"] for n in nodes]
    pk_pd_classes = [n.get("pk_pd_class") for n in nodes]

    assert "caffeine" in node_ids
    assert any("CYP1A2" in nid for nid in node_ids), "CYP1A2 PK metabolism enzyme node should be connected"
    assert "PK" in pk_pd_classes, "PK class should be present on CYP enzyme nodes"
    assert "PD" in pk_pd_classes, "PD class should be present on receptor/pathway nodes"
    assert any("biomarker" in nt for nt in node_types), "Downstream biomarker nodes should be connected"
    assert any("phenotype" in nt for nt in node_types), "Downstream phenotype nodes should be connected"


