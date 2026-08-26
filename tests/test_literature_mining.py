import pytest
from app.knowledge_graph.models import EdgeType, EdgeData
from app.knowledge_graph.graph_db import get_graph_database
from app.services.pubmed_service import PubMedService
from app.services.cooccurrence_miner import CooccurrenceMiner
from app.services.synergy_engine import SynergyEngine


def test_edge_types_and_model_fields():
    assert "LITERATURE_COOCCURRENCE" in [e.value for e in EdgeType]
    assert "CURATED_ASSOCIATION" in [e.value for e in EdgeType]

    edge = EdgeData(
        source_db="STITCH",
        cooccurrence_count=42,
        pmi_score=3.14,
        npmi_score=0.65,
        last_mined="2026-08-26T00:00:00Z",
    )
    assert edge.source_db == "STITCH"
    assert edge.cooccurrence_count == 42
    assert edge.pmi_score == 3.14
    assert edge.npmi_score == 0.65


def test_pubmed_service_count_results():
    ps = PubMedService(api_key="test_key")
    assert ps.api_key == "test_key"
    assert hasattr(ps, "count_results")

    # Empty query should return 0 without making network call
    assert ps.count_results("") == 0


def test_cooccurrence_miner_pmi_calculation():
    miner = CooccurrenceMiner(api_key="mock_key")
    miner._cache['"caffeine"[Title/Abstract]'] = 1000
    miner._cache['"theanine"[Title/Abstract]'] = 500
    miner._cache['"caffeine"[Title/Abstract] AND "theanine"[Title/Abstract]'] = 100

    # Total 30,000,000 papers
    # P(A) = 1000 / 3e7, P(B) = 500 / 3e7, P(AB) = 100 / 3e7
    # PMI = log2( (100 / 3e7) / ((1000/3e7) * (500/3e7)) ) = log2( 100 * 3e7 / (1000 * 500) ) = log2(6000) ~ 12.55
    res = miner.compute_pmi("caffeine", "theanine", total_papers=30000000)
    assert res["count_a"] == 1000
    assert res["count_b"] == 500
    assert res["count_ab"] == 100
    assert res["pmi"] > 12.0
    assert 0.0 <= res["npmi"] <= 1.0
    assert 0.0 <= res["confidence"] <= 1.0


def test_synergy_engine_literature_evidence_boost():
    gdb = get_graph_database()
    
    # Inject mock literature co-occurrence edge between exemestane and testosterone
    gdb._mock_edges.append({
        "source": "exemestane",
        "target": "testosterone",
        "edge_type": "LITERATURE_COOCCURRENCE",
        "confidence": 0.85,
        "source_db": "PubMed_PMI",
        "cooccurrence_count": 34,
        "npmi_score": 0.55,
        "description": "Exemestane and testosterone co-occurrence in aromatase inhibition literature",
    })

    se = SynergyEngine()
    stack = [
        {"key": "testosterone", "name": "Testosterone", "dose_mg": 100},
        {"key": "exemestane", "name": "Exemestane", "dose_mg": 12.5},
    ]
    result = se.evaluate_multi_agent_synergy(stack)
    
    assert result["literature_evidence_count"] >= 1
    assert result["literature_max_confidence"] >= 0.85
    assert "Literature" in result["domain_notes"]
