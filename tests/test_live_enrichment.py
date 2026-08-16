import pytest
from unittest.mock import patch, MagicMock
from app.services.live_enrichment import LiveEnrichmentService


def test_live_enrichment_service_instantiation():
    service = LiveEnrichmentService(timeout_seconds=2.0)
    assert service.timeout == 2.0
    assert service._cache == {}


def test_enrich_compound_merges_openfda_chembl_rxnorm():
    service = LiveEnrichmentService(timeout_seconds=2.0)

    # Mock openfda
    mock_openfda = {
        "pharm_class_epc": ["Mineralocorticoid Receptor Antagonist [EPC]"],
        "pharm_class_moa": ["Mineralocorticoid Receptor Antagonists [MoA]"],
        "pharm_class_pe": ["Decreased Renal Potassium Excretion [PE]"],
        "boxed_warning": "Warning: Hyperkalemia risk in renal impairment.",
        "warnings": ["Monitor serum potassium regularly."],
        "contraindications": ["Serum potassium > 5.5 mEq/L at initiation."],
        "drug_interactions": ["Avoid co-administration with strong CYP3A4 inhibitors and potassium supplements."],
        "atc_codes": ["C03DA04"],
    }

    # Mock chembl
    mock_chembl = {
        "chembl_id": "CHEMBL1095097",
        "mechanisms": [{"mechanism_of_action": "Mineralocorticoid receptor antagonist", "action_type": "ANTAGONIST"}],
        "receptor_targets": [{"target": "Mineralocorticoid receptor", "action": "antagonist", "family": "ChEMBL Mechanism"}],
    }

    # Mock rxnorm
    mock_rxnorm = ["Aldosterone antagonists"]

    with patch.object(service, "fetch_openfda", return_value=mock_openfda):
        with patch.object(service, "fetch_chembl", return_value=mock_chembl):
            with patch.object(service, "fetch_rxnorm_atc", return_value=mock_rxnorm):
                base_compound = {
                    "key": "synthetic_compound_x",
                    "name": "Synthetic Compound X",
                    "categories": ["cardiovascular"],
                }

                enriched = service.enrich_compound(base_compound)

                assert "Mineralocorticoid Receptor Antagonist [EPC]" in enriched["categories"]
                assert "Aldosterone antagonists" in enriched["categories"]
                assert any(t["target"] == "Mineralocorticoid receptor" for t in enriched["receptor_targets"])
                assert enriched["boxed_warning"] == "Warning: Hyperkalemia risk in renal impairment."
                assert len(enriched["warnings"]) >= 1
                assert len(enriched["contraindications"]) >= 1
                assert "online_enrichment" in enriched["metadata"]
