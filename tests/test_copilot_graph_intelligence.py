import pytest
from app.knowledge_graph.graph_db import get_graph_database
from app.services.copilot_agent import CopilotAgent


@pytest.fixture(autouse=True)
def setup_mock_graph_edges():
    gdb = get_graph_database()
    # Populate mock graph with test nodes and edges
    gdb._mock_nodes["testosterone"] = {"id": "testosterone", "label": "Testosterone", "node_type": "compound"}
    gdb._mock_nodes["exemestane"] = {"id": "exemestane", "label": "Exemestane", "node_type": "compound"}
    gdb._mock_nodes["anastrozole"] = {"id": "anastrozole", "label": "Anastrozole", "node_type": "compound"}
    gdb._mock_nodes["cyp19a1"] = {"id": "cyp19a1", "label": "Aromatase (CYP19A1)", "node_type": "enzyme"}
    gdb._mock_nodes["bio_heart_rate"] = {"id": "bio_heart_rate", "label": "Heart Rate", "node_type": "biomarker"}
    gdb._mock_nodes["caffeine"] = {"id": "caffeine", "label": "Caffeine", "node_type": "compound"}
    gdb._mock_nodes["adenosine_a2a"] = {"id": "adenosine_a2a", "label": "Adenosine A2A Receptor", "node_type": "receptor"}

    # Mock edges
    gdb._mock_edges.extend([
        {
            "source": "testosterone",
            "target": "exemestane",
            "edge_type": "LITERATURE_COOCCURRENCE",
            "confidence": 0.88,
            "cooccurrence_count": 34,
            "npmi_score": 0.55,
            "sample_pmids": ["15086884", "12086762"],
            "source_db": "PubMed_PMI",
            "description": "Co-administered for estrogen control in androgenic protocols",
        },
        {
            "source": "exemestane",
            "target": "cyp19a1",
            "edge_type": "INHIBITS_ENZYME",
            "confidence": 0.95,
            "description": "Irreversible suicide inhibition of aromatase",
        },
        {
            "source": "testosterone",
            "target": "cyp19a1",
            "edge_type": "SUBSTRATE_OF",
            "confidence": 0.99,
            "description": "Substrate for aromatization to estradiol",
        },
        {
            "source": "caffeine",
            "target": "adenosine_a2a",
            "edge_type": "ANTAGONIZES",
            "confidence": 0.92,
        },
        {
            "source": "adenosine_a2a",
            "target": "bio_heart_rate",
            "edge_type": "MODIFIES_BIOMARKER",
            "confidence": 0.85,
        }
    ])


def test_graphrag_literature_context():
    gdb = get_graph_database()
    context = gdb.get_graphrag_context(["testosterone", "exemestane"])
    
    assert len(context["literature_cooccurrences"]) >= 1
    assert "Literature Co-occurrences" in context["formatted_prompt_context"]
    assert "Exemestane" in context["formatted_prompt_context"] or "exemestane" in context["formatted_prompt_context"]


def test_find_candidate_pairings_tool():
    res = CopilotAgent.execute_tool("find_candidate_pairings", {
        "compound_key": "testosterone",
        "min_confidence": 0.5,
    })
    
    assert res["pairings_found"] >= 1
    pairings = res["top_pairings"]
    assert any(p["partner_key"] == "exemestane" for p in pairings)
    exem = next(p for p in pairings if p["partner_key"] == "exemestane")
    assert exem["cooccurrence_count"] == 34
    assert exem["npmi_score"] == 0.55


def test_query_compound_associations_tool():
    res = CopilotAgent.execute_tool("query_compound_associations", {
        "compound_a": "exemestane",
        "compound_b": "testosterone",
    })
    
    assert len(res["direct_associations"]) >= 1
    assert res["direct_associations"][0]["relationship"] == "LITERATURE_COOCCURRENCE"
    # Should detect shared CYP19A1 target
    assert len(res["shared_molecular_targets"]) >= 1
    assert any(t["target"] == "cyp19a1" for t in res["shared_molecular_targets"])


def test_trace_mechanism_pathway_tool():
    res = CopilotAgent.execute_tool("trace_mechanism_pathway", {
        "source_compound": "caffeine",
        "target_biomarker": "bio_heart_rate",
    })
    
    assert res["paths_found_count"] >= 1
    all_paths = " ".join(res["pathways"]).lower()
    assert "caffeine" in all_paths
    assert "adora" in all_paths or "adenosine" in all_paths
    assert "bio_heart_rate" in all_paths


def test_execute_read_only_cypher_tool_success_and_guardrails():
    # Valid read-only query
    res = CopilotAgent.execute_tool("execute_read_only_cypher", {
        "query": "MATCH (c:CompoundNode) RETURN c.id AS id LIMIT 5"
    })
    assert "error" not in res
    assert "records" in res

    # Blocked mutating query (CREATE)
    res_block1 = CopilotAgent.execute_tool("execute_read_only_cypher", {
        "query": "CREATE (n:BadNode {name: 'hacked'})"
    })
    assert "error" in res_block1
    assert "Security Violation" in res_block1["error"]

    # Blocked mutating query (DELETE)
    res_block2 = CopilotAgent.execute_tool("execute_read_only_cypher", {
        "query": "MATCH (n) DELETE n"
    })
    assert "error" in res_block2
    assert "Security Violation" in res_block2["error"]


def test_get_evidence_based_recommendations_with_literature_discovery():
    recs = CopilotAgent.get_evidence_based_recommendations(
        compounds=[{"key": "testosterone", "name": "Testosterone", "dose": 200, "unit": "mg"}],
        biometrics={"weight_kg": 80, "blood_pressure": 120},
    )
    
    # Should include Exemestane or Anastrozole in recommendations
    rec_keys = [r["key"] for r in recs]
    assert "exemestane" in rec_keys or "anastrozole" in rec_keys
