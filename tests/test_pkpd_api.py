from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_pkpd_simulate():
    payload = {
        "compound_key": "telmisartan",
        "dose_mg": 40.0,
        "dosing_interval_h": 24.0,
        "simulation_duration_h": 48.0,
        "steady_state": True,
        "co_administered_compounds": ["ketoconazole"],
    }
    response = client.post("/api/pkpd/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "c_max_ng_ml" in data
    assert "time_series" in data
    assert len(data["time_series"]) > 0
    assert data["compound_key"] == "telmisartan"


def test_api_get_compound_pkpd():
    response = client.get("/api/compounds/telmisartan/pkpd")
    assert response.status_code == 200
    data = response.json()
    assert "pk" in data
    assert "pd" in data
    assert data["pk"]["t_half_h"] == 24.0
    assert data["pk"]["bioavailability_f"] == 0.5


def test_api_enrich_compound_full():
    from unittest.mock import patch
    from app.services.live_enrichment import LiveEnrichmentService

    mock_fda = {"pharm_class_epc": ["Angiotensin 2 Receptor Antagonist [EPC]"]}
    mock_chembl = {"chembl_id": "CHEMBL1082", "mechanisms": []}
    mock_rx = ["Angiotensin II Receptor Antagonists"]

    with patch.object(LiveEnrichmentService, "fetch_openfda", return_value=mock_fda):
        with patch.object(LiveEnrichmentService, "fetch_chembl", return_value=mock_chembl):
            with patch.object(LiveEnrichmentService, "fetch_rxnorm_atc", return_value=mock_rx):
                response = client.post("/api/compounds/telmisartan/enrich-full")
                assert response.status_code == 200
                data = response.json()
                assert data["key"] == "telmisartan"
                assert data.get("t_half_numeric") == 24.0
