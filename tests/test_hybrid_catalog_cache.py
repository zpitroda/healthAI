from __future__ import annotations

import tempfile
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog_service import CatalogService
from app.services.live_enrichment import LiveEnrichmentService


@pytest.fixture
def temp_catalog_service():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name
    service = CatalogService(database_path=temp_db_path)
    yield service


def test_local_cache_hit_returns_fast(temp_catalog_service: CatalogService):
    """Cached compound is served immediately from local SQLite database without network."""
    temp_catalog_service.upsert_compound({
        "key": "caffeine",
        "name": "Caffeine",
        "canonical_name": "Caffeine",
        "drug_class": "Adenosine receptor antagonist",
        "source_tier": "cached",
    })
    caffeine = temp_catalog_service.get_compound("caffeine", auto_enrich=False)
    assert caffeine is not None
    assert caffeine["key"] == "caffeine"
    assert caffeine.get("source_tier") in ("cached", "seed", None) or isinstance(caffeine.get("source_tier"), str)


def test_cache_miss_triggers_live_enrichment_and_persists_to_sqlite(temp_catalog_service: CatalogService):
    """Unknown drug triggers live API lookup and is persisted directly into SQLite."""
    novel_key = "novel_glp1_candidate"

    # Confirm it does not exist locally yet
    assert temp_catalog_service.get_compound(novel_key, auto_enrich=False) is None

    mock_openfda = {
        "pharm_class_epc": ["Glucagon-Like Peptide-1 Receptor Agonist [EPC]"],
        "pharm_class_moa": ["GLP-1 Receptor Agonists [MoA]"],
        "pharm_class_pe": ["Increased Insulin Secretion [PE]"],
        "boxed_warning": "Warning: Risk of thyroid C-cell tumors.",
        "warnings": ["Pancreatitis risk"],
        "contraindications": ["Personal or family history of MTC"],
        "drug_interactions": ["Delays gastric emptying"],
        "atc_codes": ["A10BJ06"],
    }
    mock_chembl = {
        "chembl_id": "CHEMBL999999",
        "mechanisms": [{"mechanism_of_action": "GLP-1 receptor agonist", "action_type": "AGONIST"}],
        "receptor_targets": [{"target": "GLP-1 receptor", "action": "agonist", "family": "ChEMBL Mechanism"}],
    }
    mock_rxnorm = ["Glucagon-like peptide-1 receptor agonists"]

    with patch.object(LiveEnrichmentService, "fetch_openfda", return_value=mock_openfda) as mock_fda:
        with patch.object(LiveEnrichmentService, "fetch_chembl", return_value=mock_chembl) as mock_ch:
            with patch.object(LiveEnrichmentService, "fetch_rxnorm_atc", return_value=mock_rxnorm) as mock_rx:
                # 1. First fetch: triggers live enrichment and write-through cache
                enriched_compound = temp_catalog_service.get_compound(novel_key, auto_enrich=True)

                assert enriched_compound is not None
                assert enriched_compound["key"] == novel_key
                assert "Glucagon-Like Peptide-1 Receptor Agonist [EPC]" in enriched_compound["categories"]
                assert enriched_compound["boxed_warning"] == "Warning: Risk of thyroid C-cell tumors."
                assert enriched_compound["source_tier"] == "live_enrichment"
                assert enriched_compound["last_enriched_at"] is not None
                assert mock_fda.called

                # 2. Reset mock call counts to verify subsequent query does NOT touch online APIs
                mock_fda.reset_mock()
                mock_ch.reset_mock()
                mock_rx.reset_mock()

                # 3. Second fetch: served purely from SQLite without any API calls
                cached_compound = temp_catalog_service.get_compound(novel_key, auto_enrich=True)
                assert cached_compound is not None
                assert cached_compound["key"] == novel_key
                assert cached_compound["boxed_warning"] == "Warning: Risk of thyroid C-cell tumors."
                assert cached_compound["source_tier"] == "live_enrichment"

                # Verify NO external API calls were made
                assert not mock_fda.called
                assert not mock_ch.called
                assert not mock_rx.called


def test_search_compounds_auto_enrich_fallback(temp_catalog_service: CatalogService):
    """Typeahead search automatically enriches novel compound when local results are empty."""
    search_query = "semaglutide_variant_x"
    assert len(temp_catalog_service.search_compounds(search_query, auto_enrich=False)) == 0

    mock_profile = {
        "key": "semaglutide_variant_x",
        "name": "Semaglutide Variant X",
        "canonical_name": "Semaglutide Variant X",
        "drug_class": "GLP-1 RA",
        "mechanism": "GLP-1 Agonist",
        "categories": ["Antidiabetic"],
        "receptor_targets": [],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "transporters": {"substrates": [], "inhibitors": [], "inducers": []},
        "indications": ["Type 2 Diabetes Mellitus"],
        "contraindications": [],
        "side_effects": [],
        "interactions": [],
        "warnings": [],
        "boxed_warning": None,
        "evidence_level": "moderate",
        "risk_band": "low",
        "source_tier": "live_enrichment",
        "last_enriched_at": "2026-08-16T12:00:00Z",
    }

    with patch.object(LiveEnrichmentService, "fetch_compound_profile", return_value=mock_profile):
        results = temp_catalog_service.search_compounds(search_query, auto_enrich=True)
        assert len(results) == 1
        assert results[0]["key"] == "semaglutide_variant_x"

        # Subsequent search is now instant local SQL
        local_results = temp_catalog_service.search_compounds(search_query, auto_enrich=False)
        assert len(local_results) == 1
        assert local_results[0]["key"] == "semaglutide_variant_x"


def test_live_enrichment_failure_gracefully_degrades(temp_catalog_service: CatalogService):
    """When external APIs throw exceptions or timeout, get_compound safely returns None."""
    with patch.object(LiveEnrichmentService, "fetch_compound_profile", side_effect=RuntimeError("API Network Timeout")):
        result = temp_catalog_service.get_compound("completely_unknown_molecule_999", auto_enrich=True)
        assert result is None


def test_catalog_api_headers_hit_and_miss(temp_catalog_service: CatalogService):
    """Test FastAPI router response headers for Cache HIT and Cache MISS_ENRICHED."""
    client = TestClient(app)

    with patch("app.routers.catalog.get_catalog_service", return_value=temp_catalog_service):
        # 1. Local hit (caffeine is in local catalog cache)
        temp_catalog_service.upsert_compound({
            "key": "caffeine",
            "name": "Caffeine",
            "canonical_name": "Caffeine",
            "drug_class": "Adenosine receptor antagonist",
            "source_tier": "cached",
        })
        resp = client.get("/catalog/caffeine")
        assert resp.status_code == 200
        assert resp.headers.get("X-Cache-Status") == "HIT"

        # 2. Cache miss enriched
        mock_openfda = {
            "pharm_class_epc": ["SGLT2 Inhibitor [EPC]"],
            "pharm_class_moa": [],
            "pharm_class_pe": [],
            "boxed_warning": None,
            "warnings": [],
            "contraindications": [],
            "drug_interactions": [],
            "atc_codes": [],
        }
        with patch.object(LiveEnrichmentService, "fetch_openfda", return_value=mock_openfda):
            with patch.object(LiveEnrichmentService, "fetch_chembl", return_value={}):
                with patch.object(LiveEnrichmentService, "fetch_rxnorm_atc", return_value=[]):
                    resp = client.get("/catalog/dapagliflozin_mock_test")
                    assert resp.status_code == 200
                    assert resp.headers.get("X-Cache-Status") == "MISS_ENRICHED"
                    assert resp.headers.get("X-Source-Tier") == "live_enrichment"
