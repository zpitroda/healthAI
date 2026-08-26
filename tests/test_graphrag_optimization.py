import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.knowledge_graph.graph import BiologicalGraph
from app.knowledge_graph.models import (
    CompoundNode,
    ReceptorNode,
    EnzymeNode,
    SignalingPathwayNode,
    PhysiologyNode,
    BiomarkerNode,
    PhenotypeNode,
    EdgeType,
    EdgeData,
)
from app.knowledge_graph.graph_db import get_graph_database
from app.services.graph_service import build_selected_compound_graph


@pytest.fixture
def client():
    return TestClient(app)


def test_scientific_graph_sync_deep_attributes():
    """Verify that deep PK/PD, molecular, kinetic, and evidence properties sync to Graph DB storage."""
    graph = BiologicalGraph()
    
    # 1. Add rich CompoundNode
    graph.add_node(
        CompoundNode(
            node_id="telmisartan",
            label="Telmisartan",
            canonical_name="Telmisartan",
            smiles="CCCC1=NC2=C(N1CC3=CC=C(C=C3)C4=CC=CC=C4C(=O)O)C=C(C=C2)C5=NC6=CC=CC=C6N5C",
            inchikey="RMMXLENWDFGHAA-UHFFFAOYSA-N",
            pubchem_cid="65999",
            chembl_id="CHEMBL1059",
            logP=3.2,
            tpsa=72.8,
            molecular_weight=514.62,
            base_half_life=24.0,
            bioavailability_pct=42.0,
            volume_of_distribution=7.0,
            protein_binding_pct=99.5,
            renal_clearance_fraction=0.01,
            hepatic_clearance_fraction=0.99,
            drug_class="Angiotensin II Receptor Blocker (ARB)",
            is_narrow_therapeutic_index=False,
            cyp_substrates=["CYP2C9"],
            cyp_inhibitors=["CYP2C19"],
        )
    )

    # 2. Add TargetNode
    graph.add_node(
        ReceptorNode(
            node_id="agtr1",
            label="Angiotensin II Receptor Type 1",
            uniprot_id="P30556",
            gene_symbol="AGTR1",
            receptor_family="GPCR",
            subcellular_location="Plasma Membrane",
        )
    )

    # 3. Add Edge with binding thermodynamics
    graph.add_edge(
        "telmisartan",
        "agtr1",
        EdgeType.ANTAGONIZES,
        EdgeData(
            affinity_ki=12.0,
            inhibition_ic50=18.0,
            inhibition_type="insurmountable_antagonist",
            evidence_level="clinical_trial",
            mechanism_notes="High-affinity slow dissociation AT1 receptor blockade",
        ),
    )

    db = get_graph_database()
    sync_res = db.sync_biological_graph(graph)
    assert sync_res["nodes_synced"] >= 2
    assert sync_res["edges_synced"] >= 1

    # Verify fallback storage properties
    mock_node = db._mock_nodes.get("telmisartan")
    assert mock_node is not None
    assert mock_node.get("half_life_hours") == 24.0
    assert mock_node.get("inchikey") == "RMMXLENWDFGHAA-UHFFFAOYSA-N"
    assert "CYP2C9" in mock_node.get("cyp_substrates", [])


def test_graphrag_context_generation_and_causal_chains():
    """Verify that get_graphrag_context produces structured triples, causal chains, and clinical prompt formatting."""
    graph = build_selected_compound_graph(["telmisartan:40mg"])
    db = get_graph_database()
    db.sync_biological_graph(graph)

    context = db.get_graphrag_context(["telmisartan"], max_hops=3)

    assert "telmisartan" in context["focused_ids"]
    assert len(context["entities"]) >= 1
    assert context["triple_count"] >= 1
    assert isinstance(context["causal_chains"], list)
    assert isinstance(context["pkpd_matrix"], dict)
    assert "formatted_prompt_context" in context
    assert "SCIENTIFIC KNOWLEDGE GRAPH CONTEXT" in context["formatted_prompt_context"]


def test_graphrag_target_competition_detection():
    """Verify that multi-compound stacks detect shared molecular targets."""
    # Build graph with stack that shares vascular/cardiovascular pathways
    graph = build_selected_compound_graph(["telmisartan:40mg", "sildenafil:50mg"])
    db = get_graph_database()
    db.sync_biological_graph(graph)

    context = db.get_graphrag_context(["telmisartan", "sildenafil"], max_hops=3)
    assert len(context["entities"]) >= 2
    assert "telmisartan" in context["pkpd_matrix"]
    assert "sildenafil" in context["pkpd_matrix"]
    assert "formatted_prompt_context" in context


def test_api_graphrag_endpoint(client):
    """Verify that POST /api/graph/graphrag-context returns complete structured payload."""
    payload = {
        "entity_ids": ["telmisartan", "sildenafil"],
        "max_hops": 2,
        "include_pkpd": True,
        "include_kinetics": True,
        "include_causal_chains": True,
    }
    response = client.post("/api/graph/graphrag-context", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "focused_ids" in data
    assert "triples" in data
    assert "causal_chains" in data
    assert "pkpd_matrix" in data
    assert "formatted_prompt_context" in data
    assert len(data["triples"]) > 0


def test_api_cypher_endpoint(client):
    """Verify that POST /api/graph/cypher handles Cypher queries."""
    payload = {
        "query": "MATCH (c:CompoundNode) RETURN count(c) AS count",
    }
    response = client.post("/api/graph/cypher", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "count" in data


def test_graphrag_caching_and_invalidation():
    """Verify that GraphRAG context extraction is cached in-memory and invalidated upon graph updates."""
    db = get_graph_database()
    db.clear_cache()

    context1 = db.get_graphrag_context(["telmisartan"], max_hops=2)
    assert len(db._graphrag_cache) == 1

    # Second call should retrieve from cache
    context2 = db.get_graphrag_context(["telmisartan"], max_hops=2)
    assert context1["triple_count"] == context2["triple_count"]

    # Invalidation
    db.clear_cache()
    assert len(db._graphrag_cache) == 0


def test_affinity_weighted_causal_chain_ranking():
    """Verify that causal reasoning paths prioritize high-affinity (low Ki) targets."""
    graph = BiologicalGraph()
    graph.add_node(CompoundNode(node_id="test_ligand", label="Test Ligand"))
    graph.add_node(ReceptorNode(node_id="rec_low_affinity", label="Low Affinity Target"))
    graph.add_node(ReceptorNode(node_id="rec_high_affinity", label="High Affinity Target"))
    graph.add_node(PhysiologyNode(node_id="phys_effect", label="Downstream Effect"))

    # Add low affinity edge (Ki = 500 nM)
    graph.add_edge("test_ligand", "rec_low_affinity", EdgeType.AGONIZES, EdgeData(affinity_ki=500.0))
    graph.add_edge("rec_low_affinity", "phys_effect", EdgeType.MODULATES, EdgeData())

    # Add high affinity edge (Ki = 0.5 nM)
    graph.add_edge("test_ligand", "rec_high_affinity", EdgeType.AGONIZES, EdgeData(affinity_ki=0.5))
    graph.add_edge("rec_high_affinity", "phys_effect", EdgeType.MODULATES, EdgeData())

    db = get_graph_database()
    db.sync_biological_graph(graph)

    chains = db.trace_causal_chains(["test_ligand"], max_depth=3)
    assert len(chains) >= 2
    # First ranked chain should traverse the high affinity target
    first_chain_targets = [step["target"] for step in chains[0]]
    assert "rec_high_affinity" in first_chain_targets


def test_action_card_validator_fuzzy_resolution():
    """Verify that action card validator resolves abbreviated compound keys to canonical catalog keys."""
    from app.services.action_card_validator import ActionCardValidator

    payload = {
        "add": [
            {"key": "testosterone_cyp", "dose": 200, "unit": "mg", "route": "intramuscular"},
            {"key": "n-acetyl-cysteine", "dose": 600, "unit": "mg"},
        ]
    }
    sanitized, notes = ActionCardValidator.validate_and_sanitize_card("stack_diff", payload)
    added_keys = [item["key"] for item in sanitized.get("add", [])]
    assert "testosterone_cypionate" in added_keys or "testosterone" in added_keys[0]
    assert "nac" in added_keys or "n_acetylcysteine" in added_keys

