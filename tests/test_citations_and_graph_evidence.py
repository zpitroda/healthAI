import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.knowledge_graph.models import (
    CitationNode,
    ClinicalTrialNode,
    EvidenceClaimNode,
    CompoundNode,
    ReceptorNode,
    EdgeType,
    EdgeData,
)
from app.knowledge_graph.graph_db import get_graph_database
from app.services.graph_service import build_selected_compound_graph
from app.services.conflict_detector import ConflictDetector
from app.services.pubmed_service import PubMedService
from app.services.catalog_service import CatalogService
from app.services.copilot_agent import CopilotAgent

client = TestClient(app)


def test_citation_nodes_and_models():
    """Verify CitationNode, ClinicalTrialNode, and EvidenceClaimNode instantiation."""
    cite = CitationNode(
        node_id="pmid_18378520",
        pmid="18378520",
        doi="10.1056/NEJMoa0801317",
        title="Telmisartan, ramipril, or both in patients at high risk for vascular events (ONTARGET)",
        authors=["Yusuf S", "Teo KK", "Pogue J", "et al."],
        journal="N Engl J Med",
        pub_year=2008,
        pub_date="2008-04-10",
        evidence_tier="rct_landmark",
        sample_size=25620,
        key_findings="Demonstrates potent AT1 blockade and endothelial organ protection.",
        url="https://pubmed.ncbi.nlm.nih.gov/18378520/",
    )
    assert cite.node_type == "citation"
    assert cite.pmid == "18378520"
    assert cite.pub_year == 2008
    assert cite.sample_size == 25620

    trial = ClinicalTrialNode(
        node_id="trial_NCT00079287",
        nct_id="NCT00079287",
        title="Ongoing Telmisartan Alone and in Combination with Ramipril Global Endpoint Trial (ONTARGET)",
        phase="Phase III",
        status="COMPLETED",
        sponsor="Boehringer Ingelheim",
        enrollment=25620,
        conditions=["Cardiovascular Diseases", "Hypertension"],
        interventions=["Telmisartan 80mg", "Ramipril 10mg"],
        start_year=2001,
        completion_year=2008,
        url="https://clinicaltrials.gov/study/NCT00079287",
    )
    assert trial.node_type == "clinical_trial"
    assert trial.nct_id == "NCT00079287"
    assert trial.phase == "Phase III"

    claim = EvidenceClaimNode(
        node_id="claim_telmisartan_agtr1",
        claim_type="binding_affinity",
        subject_id="telmisartan",
        predicate="INHIBITS",
        object_id="agtr1",
        magnitude_value=3.7,
        magnitude_unit="nM",
        consensus_score=0.98,
        dispute_status="consensus",
        contradiction_index=0.02,
        discovery_year=1998,
        last_validated_year=2024,
    )
    assert claim.node_type == "evidence_claim"
    assert claim.magnitude_value == 3.7
    assert claim.consensus_score == 0.98


def test_graph_database_sync_and_timeline():
    """Verify Neo4j graph database synchronization and chronological evidence retrieval."""
    gdb = get_graph_database()
    bio_graph = build_selected_compound_graph(["telmisartan"])

    sync_res = gdb.sync_biological_graph(bio_graph)
    assert sync_res["nodes_synced"] > 0
    assert sync_res["edges_synced"] > 0

    # Test chronological timeline retrieval
    timeline = gdb.get_chronological_evidence_timeline("telmisartan")
    assert len(timeline) >= 1
    assert any(str(m.get("pmid")) == "18378520" for m in timeline)
    assert all("year" in m for m in timeline)

    # Test temporal snapshot
    snapshot_1990 = gdb.get_temporal_graph_snapshot(1990)
    assert isinstance(snapshot_1990["nodes"], list)

    snapshot_2026 = gdb.get_temporal_graph_snapshot(2026)
    assert snapshot_2026["edge_count"] >= sync_res["edges_synced"]


def test_conflict_detector_affinity_and_consensus():
    """Verify ConflictDetector variance calculations and consensus scoring."""
    # Low variance (consensus)
    low_var = [
        {"source": "Study A", "value": 3.5, "unit": "nM"},
        {"source": "Study B", "value": 4.1, "unit": "nM"},
    ]
    eval_low = ConflictDetector.evaluate_affinity_variance(low_var, "Ki")
    assert eval_low["has_conflict"] is False
    assert eval_low["dispute_status"] == "consensus"
    assert eval_low["consensus_score"] == 1.0

    # High variance (>10x fold difference)
    high_var = [
        {"source": "Assay In Vitro 1999", "value": 2.0, "unit": "nM"},
        {"source": "Assay Radioligand 2012", "value": 85.0, "unit": "nM"},
    ]
    eval_high = ConflictDetector.evaluate_affinity_variance(high_var, "Ki")
    assert eval_high["has_conflict"] is True
    assert eval_high["dispute_status"] == "debated"
    assert eval_high["fold_difference"] > 10.0
    assert eval_high["contradiction_index"] > 0.4

    # Clinical outcome consensus
    pos_studies = [{"title": "Benefit RCT", "evidence_tier": "Phase III Landmark RCT"}]
    opp_studies = [{"title": "Blunting Study", "evidence_tier": "In Vivo Cohort"}]
    c_eval = ConflictDetector.evaluate_clinical_outcome_consensus(pos_studies, opp_studies)
    assert c_eval["has_conflict"] is True
    assert c_eval["consensus_score"] > 0.5


def test_pubmed_service_citations_and_conflicts():
    """Verify PubMedService citation retrieval, polarity classification, and controversy detection."""
    svc = PubMedService()

    # Seed literature lookup
    telm_cites = svc.search_literature("telmisartan", max_results=2)
    assert len(telm_cites) >= 1
    assert any("ONTARGET" in c["title"] for c in telm_cites)

    # Polarity classification
    polarity_results = svc.search_literature_with_polarity("telmisartan", max_results=2)
    assert len(polarity_results) >= 1
    assert "inferred_polarity" in polarity_results[0]

    # Conflict detector for compound
    conflicts = svc.detect_conflicts_for_compound("antioxidants_hypertrophy")
    assert len(conflicts) >= 1
    assert conflicts[0]["dispute_status"] == "debated"
    assert "consensus_score" in conflicts[0]

    # Clinical trials lookup
    trials = svc.get_clinical_trials_for_compound("telmisartan")
    assert len(trials) >= 1
    assert trials[0]["nct_id"] == "NCT00079287"


def test_catalog_service_evidence_dossier():
    """Verify CatalogService citation methods and composite evidence dossier."""
    cat = CatalogService()

    # Add citation
    cid = cat.add_citation({
        "pmid": "99999999",
        "title": "Novel Test Investigation on Nebivolol",
        "journal": "J Cardiovasc Pharmacol",
        "pub_year": 2025,
        "compound_key": "nebivolol",
        "evidence_tier": "clinical_trial",
        "clinical_finding": "Vasodilation mediated through eNOS beta-3 stimulation.",
    })
    assert cid is not None

    # Get citations
    cites = cat.get_citations_for_compound("nebivolol")
    assert len(cites) >= 1
    assert any(str(c.get("pmid")) in ("99999999", "15587107", "15642700") for c in cites)

    # Compound evidence dossier
    dossier = cat.get_compound_evidence_dossier("telmisartan")
    assert dossier["compound_key"] == "telmisartan"
    assert dossier["citation_count"] >= 1
    assert len(dossier["citations"]) >= 1
    assert "clinical_trials" in dossier
    assert "chronological_timeline" in dossier


def test_rest_api_endpoints_evidence():
    """Verify REST API endpoints for evidence timeline, conflicts, snapshots, and dossiers."""
    # 1. Evidence timeline endpoint
    res_timeline = client.get("/api/graph/evidence-timeline/telmisartan")
    assert res_timeline.status_code == 200
    data_t = res_timeline.json()
    assert data_t["entity_id"] == "telmisartan"
    assert "timeline" in data_t

    # 2. Conflicts endpoint
    res_conflicts = client.get("/api/graph/conflicts?entity_ids=telmisartan")
    assert res_conflicts.status_code == 200
    data_c = res_conflicts.json()
    assert "disputed_edges" in data_c

    # 3. Temporal snapshot endpoint
    res_snapshot = client.get("/api/graph/temporal-snapshot?year=2024")
    assert res_snapshot.status_code == 200
    data_s = res_snapshot.json()
    assert data_s["as_of_year"] == 2024
    assert "nodes" in data_s

    # 4. Catalog citations endpoint
    res_cites = client.get("/catalog/telmisartan/citations")
    assert res_cites.status_code == 200
    data_cc = res_cites.json()
    assert data_cc["count"] >= 1

    # 5. Compound evidence dossier endpoint
    res_dossier = client.get("/catalog/telmisartan/evidence-dossier")
    assert res_dossier.status_code == 200
    data_d = res_dossier.json()
    assert data_d["compound_key"] == "telmisartan"
    assert data_d["citation_count"] >= 1


def test_copilot_agent_literature_tools():
    """Verify AI Copilot ReAct tool dispatching for literature and controversies."""
    # Tool: search_literature_and_conflicts
    res_conf = CopilotAgent.execute_tool("search_literature_and_conflicts", {"compound_name": "metformin_hypertrophy"})
    assert "conflict_count" in res_conf

    # Tool: get_temporal_evidence_timeline
    res_time = CopilotAgent.execute_tool("get_temporal_evidence_timeline", {"entity_id": "telmisartan"})
    assert res_time["entity_id"] == "telmisartan"
    assert "milestone_count" in res_time

    # Tool: get_citation_details
    res_cite = CopilotAgent.execute_tool("get_citation_details", {"pmid": "18378520"})
    assert res_cite.get("pmid") == "18378520"
    assert "ONTARGET" in res_cite.get("title", "")
