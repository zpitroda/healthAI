import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.live_enrichment import LiveEnrichmentService

client = TestClient(app)


def test_open_targets_connector_tractability_and_genetics():
    service = LiveEnrichmentService()

    # Test EGFR Open Targets query
    ot_egfr = service.fetch_open_targets("EGFR", gene_symbol="EGFR", uniprot_id="P00533")
    assert ot_egfr is not None
    assert "approved_symbol" in ot_egfr
    assert ot_egfr["approved_symbol"].upper() == "EGFR"
    assert len(ot_egfr["tractability"]) >= 1
    assert len(ot_egfr["associated_diseases"]) >= 1
    assert "overall_score" in ot_egfr["associated_diseases"][0]
    assert "genetic_evidence_score" in ot_egfr["associated_diseases"][0]


def test_fda_faers_adverse_event_signal_detection():
    service = LiveEnrichmentService()

    # Test Sildenafil FAERS query
    faers_data = service.fetch_fda_faers("sildenafil")
    assert faers_data is not None
    assert faers_data["drug_name"].lower() == "sildenafil"
    assert faers_data["total_reports"] > 0
    assert len(faers_data["top_adverse_events"]) >= 1
    first_event = faers_data["top_adverse_events"][0]
    assert "reaction" in first_event
    assert "count" in first_event
    assert "prr" in first_event
    assert "surveillance_summary" in faers_data


def test_alphafold_pdb_structure_and_mutation_impacts():
    service = LiveEnrichmentService()

    # Test EGFR AlphaFold / PDB structure and mutation impacts
    af_data = service.fetch_alphafold_pdb(uniprot_id="P00533", gene_symbol="EGFR", target_name="Epidermal Growth Factor Receptor")
    assert af_data is not None
    assert af_data["gene_symbol"] == "EGFR"
    assert af_data["mean_plddt"] > 70.0
    assert len(af_data["binding_site_residues"]) >= 4
    assert len(af_data["mutation_impacts"]) >= 1

    # Verify gatekeeper mutation Thr790Met (T790M)
    t790m = next((m for m in af_data["mutation_impacts"] if "790" in m.get("mutation", "")), None)
    assert t790m is not None
    assert t790m["affinity_shift_factor"] > 1.0
    assert "STERIC_HINDRANCE" in t790m["impact_type"]


def test_graph_data_endpoint_contains_biomedical_connector_nodes():
    response = client.get("/graph-data?stack=sildenafil,telmisartan")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data

    nodes = data["nodes"]
    compound_nodes = [n for n in nodes if n.get("node_type") == "compound"]
    target_nodes = [n for n in nodes if n.get("node_type") in ("receptor", "enzyme", "transporter", "ion_channel")]

    # Check FAERS surveillance data on compound nodes
    for cn in compound_nodes:
        if cn.get("faers_surveillance"):
            assert "total_reports" in cn["faers_surveillance"]

    # Check Open Targets and AlphaFold structure on target nodes
    for tn in target_nodes:
        if tn.get("open_targets"):
            assert "tractability" in tn["open_targets"]
            assert "associated_diseases" in tn["open_targets"]
        if tn.get("alphafold_structure"):
            assert "alphafold_id" in tn["alphafold_structure"]
            assert "binding_site_residues" in tn["alphafold_structure"]
