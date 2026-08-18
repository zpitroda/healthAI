import pytest
import os
import shutil
from fastapi.testclient import TestClient

from app.main import app
from app.knowledge_graph.graph_db import KuzuGraphDatabase, get_graph_database
from app.services.graph_service import build_selected_compound_graph


@pytest.fixture
def temp_kuzu_db(tmp_path):
    db_file = str(tmp_path / "test_kuzu.db")
    db = KuzuGraphDatabase(db_path=db_file)
    yield db
    # Cleanup after test
    try:
        db.conn = None
        db.db = None
        if os.path.exists(db_file):
            if os.path.isdir(db_file):
                shutil.rmtree(db_file)
            else:
                os.remove(db_file)
    except Exception:
        pass


def test_kuzu_database_initialization_and_cypher(temp_kuzu_db):
    db = temp_kuzu_db
    assert db.conn is not None

    # Test basic Cypher query execution
    res = db.execute_cypher("MATCH (c:CompoundNode) RETURN count(c) AS count")
    assert len(res) == 1
    assert "count" in res[0]


def test_sync_biological_graph_and_multi_hop_traversal(temp_kuzu_db):
    db = temp_kuzu_db

    # Build biological graph for telmisartan and sildenafil
    bio_graph = build_selected_compound_graph(["telmisartan", "sildenafil"])
    sync_res = db.sync_biological_graph(bio_graph)

    assert sync_res["nodes_synced"] > 0
    assert sync_res["edges_synced"] > 0

    # Query synced nodes via Cypher
    nodes = db.execute_cypher("MATCH (e:EntityNode) RETURN e.id AS id, e.label AS label, e.node_type AS node_type LIMIT 10")
    assert len(nodes) > 0

    # Test multi-hop traversal query
    traversals = db.multi_hop_traversal("telmisartan", max_hops=3)
    assert isinstance(traversals, list)


def test_graphrag_context_extraction(temp_kuzu_db):
    db = temp_kuzu_db

    bio_graph = build_selected_compound_graph(["telmisartan"])
    db.sync_biological_graph(bio_graph)

    # Extract GraphRAG context
    ctx = db.get_graphrag_context(["telmisartan"], max_hops=2)
    assert ctx["focused_ids"] == ["telmisartan"]
    assert "entities" in ctx
    assert "triples" in ctx
    assert "text_summary" in ctx
    assert "GraphRAG Biological Subgraph Context" in ctx["text_summary"]


def test_cypher_and_graphrag_api_endpoints():
    client = TestClient(app)

    # Test Cypher endpoint
    cypher_resp = client.post(
        "/api/graph/cypher",
        json={"query": "MATCH (e:EntityNode) RETURN e.id AS id, e.label AS label LIMIT 5"},
    )
    assert cypher_resp.status_code == 200
    c_data = cypher_resp.json()
    assert "query" in c_data
    assert "results" in c_data

    # Test GraphRAG context endpoint
    graphrag_resp = client.post(
        "/api/graph/graphrag-context",
        json={"entity_ids": ["telmisartan", "sildenafil"], "max_hops": 2},
    )
    assert graphrag_resp.status_code == 200
    g_data = graphrag_resp.json()
    assert "entities" in g_data
    assert "triples" in g_data
    assert "text_summary" in g_data
