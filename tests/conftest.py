import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def isolate_catalog_db_env():
    """Ensure HEALTHAI_CATALOG_DB environment variable and in-memory caches are isolated per test."""
    from app.services.catalog_service import _CATALOG_MEMORY_CACHE, _CATALOG_ALL_COMPOUNDS, CatalogService
    from app.services.pathway_service import _PATHWAY_METADATA_CACHE, _PATHWAY_CASCADE_CACHE
    import json
    import os
    
    _CATALOG_MEMORY_CACHE.clear()
    _CATALOG_ALL_COMPOUNDS.clear()
    _PATHWAY_METADATA_CACHE.clear()
    _PATHWAY_CASCADE_CACHE.clear()
    original_db = os.environ.get("HEALTHAI_CATALOG_DB")
    
    # Load test fixtures into the test database
    db_path = os.environ.get("HEALTHAI_CATALOG_DB", "healthai_catalog_test.db")
    svc = CatalogService(db_path)
    try:
        with open('tests/fixtures/test_seed_compounds.json', 'r') as f:
            seeds = json.load(f)
            for s in seeds:
                svc.upsert_compound(s)
    except Exception as e:
        pass
        
    yield
    
    _CATALOG_MEMORY_CACHE.clear()
    _CATALOG_ALL_COMPOUNDS.clear()
    _PATHWAY_METADATA_CACHE.clear()
    _PATHWAY_CASCADE_CACHE.clear()
    if original_db is not None:
        os.environ["HEALTHAI_CATALOG_DB"] = original_db
    else:
        os.environ.pop("HEALTHAI_CATALOG_DB", None)



@pytest.fixture(autouse=True)
def disable_external_network_io(monkeypatch):
    """
    Globally intercepts external biomedical network requests (UniProt, Reactome, Open Targets,
    OpenFDA, ChEMBL, PubChem, RxNorm) to guarantee 100% offline, deterministic, sub-millisecond execution.
    FastAPI TestClient requests (host == 'testserver') pass through unimpeded.
    """
    import httpx

    orig_send = httpx.Client.send

    def mock_send(self, request, *args, **kwargs):
        host = request.url.host.lower() if request.url.host else ""
        url_str = str(request.url).lower()

        # Pass through internal TestClient / localhost calls
        if host in ("testserver", "localhost", "127.0.0.1") or "testserver" in url_str:
            return orig_send(self, request, *args, **kwargs)

        # Mock OpenFDA
        if "api.fda.gov" in host:
            if "event.json" in url_str:
                return httpx.Response(200, json={
                    "results": [
                        {"term": "HEADACHE", "count": 3500},
                        {"term": "FLUSHING", "count": 2200},
                        {"term": "DIZZINESS", "count": 1800},
                        {"term": "HYPOTENSION", "count": 1200},
                    ]
                })
            return httpx.Response(200, json={
                "results": [{
                    "openfda": {
                        "pharm_class_epc": ["Cardiovascular Agent [EPC]"],
                        "pharm_class_moa": ["Vasodilator [MoA]"],
                        "pharm_class_pe": ["Decreased Blood Pressure [PE]"],
                        "atc_codes": ["C09CA07"],
                        "route": ["oral"],
                    },
                    "boxed_warning": None,
                    "warnings": ["Monitor blood pressure regularly."],
                    "contraindications": ["Hypersensitivity"],
                    "drug_interactions": ["Avoid potassium supplements."],
                }]
            })

        # Mock UniProt Search
        if "rest.uniprot.org" in host or "uniprot.org" in host:
            if "ghsr" in url_str or "q92847" in url_str:
                return httpx.Response(200, json={
                    "results": [{
                        "primaryAccession": "Q92847",
                        "proteinDescription": {
                            "recommendedName": {"fullName": {"value": "Growth Hormone Secretagogue Receptor"}}
                        }
                    }]
                })
            elif "ghrhr" in url_str or "q02643" in url_str:
                return httpx.Response(200, json={
                    "results": [{
                        "primaryAccession": "Q02643",
                        "proteinDescription": {
                            "recommendedName": {"fullName": {"value": "Growth Hormone-Releasing Hormone Receptor"}}
                        }
                    }]
                })
            return httpx.Response(200, json={"results": []})


        # Mock Ensembl
        if "rest.ensembl.org" in host or "ensembl.org" in host:
            return httpx.Response(200, json=[{"id": "ENSG00000146648"}])

        # Mock Reactome
        if "reactome.org" in host:
            return httpx.Response(200, json=[
                {"stId": "R-HSA-177929", "displayName": "Signaling by EGFR", "hasDiagram": True, "speciesName": "Homo sapiens"},
                {"stId": "R-HSA-5683057", "displayName": "MAPK family signaling cascades", "hasDiagram": True, "speciesName": "Homo sapiens"}
            ])

        # Mock AlphaFold API
        if "alphafold.ebi.ac.uk" in host:
            return httpx.Response(200, json=[{
                "entryId": "AF-P00533-F1",
                "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v4.pdb",
                "globalMetricValue": 92.4,
                "uniprotSequence": "MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEVVLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALAVLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSDFLSNMSMDFQNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGCTGPRESDCLVCRKFRDEATC"
            }])

        # Mock ChEMBL Molecule / Mechanism / Activity search
        if "ebi.ac.uk" in host:
            if "mechanism" in url_str:
                return httpx.Response(200, json={
                    "mechanisms": [{
                        "mechanism_of_action": "Angiotensin II receptor antagonist",
                        "action_type": "ANTAGONIST",
                        "target_name": "Angiotensin II Receptor Type 1",
                        "target_chembl_id": "CHEMBL1824"
                    }]
                })
            elif "target" in url_str:
                return httpx.Response(200, json={
                    "target_components": [{
                        "accession": "P30556",
                        "target_component_synonyms": [{"syn_type": "GENE_SYMBOL", "component_synonym": "AGTR1"}]
                    }]
                })
            elif "activity" in url_str:
                return httpx.Response(200, json={
                    "activities": [{
                        "target_pref_name": "Angiotensin II Receptor Type 1",
                        "target_chembl_id": "CHEMBL1824",
                        "standard_type": "Ki",
                        "standard_value": "12.0",
                        "standard_units": "nM"
                    }]
                })
            else:
                return httpx.Response(200, json={
                    "molecules": [{
                        "molecule_chembl_id": "CHEMBL1059",
                        "pref_name": "Telmisartan",
                        "max_phase": 4,
                        "molecule_synonyms": []
                    }]
                })

        # Mock PubChem
        if "pubchem.ncbi.nlm.nih.gov" in host or "ncbi.nlm.nih.gov" in host:
            if "property" in url_str:
                return httpx.Response(200, json={
                    "PropertyTable": {
                        "Properties": [{
                            "CID": 65999,
                            "MolecularWeight": 514.62,
                            "CanonicalSMILES": "CCCC1=NC2=C(N1CC3=CC=C(C=C3)C4=CC=CC=C4C(=O)O)C=C(C=C2)C5=NC6=CC=CC=C6N5C",
                            "InChIKey": "RMMXLENWDFGHAA-UHFFFAOYSA-N",
                            "XLogP": 3.2,
                            "TPSA": 72.8,
                        }]
                    }
                })
            elif "synonyms" in url_str:
                return httpx.Response(200, json={
                    "InformationList": {"Information": [{"Synonym": ["Telmisartan", "Micardis", "Pritor"]}]}
                })
            else:
                return httpx.Response(200, json={"Record": {"Section": []}})

        # Mock RxNorm
        if "rxnav.nlm.nih.gov" in host or "nlm.nih.gov" in host:
            if "rxcui.json" in url_str:
                return httpx.Response(200, json={"idGroup": {"rxnormId": ["316049"]}})
            elif "byrxcui.json" in url_str:
                return httpx.Response(200, json={
                    "rxclassDrugInfoList": {
                        "rxclassDrugInfo": [{
                            "rxclassMinConceptItem": {
                                "className": "Angiotensin II Receptor Antagonists [EPC]"
                            }
                        }]
                    }
                })

        # Mock Open Targets GraphQL
        if "opentargets.org" in host or "opentargets" in url_str:
            return httpx.Response(200, json={
                "data": {
                    "search": {
                        "hits": [{"id": "ENSG00000146648", "name": "Epidermal Growth Factor Receptor", "symbol": "EGFR"}]
                    },
                    "target": {
                        "id": "ENSG00000146648",
                        "approvedSymbol": "EGFR",
                        "approvedName": "Epidermal Growth Factor Receptor",
                        "tractability": [
                            {"label": "Small Molecule Tractable (Clinical Precedent)", "modality": "SM", "value": True},
                            {"label": "Antibody Modality", "modality": "AB", "value": True}
                        ],
                        "associatedDiseases": {
                            "rows": [
                                {"disease": {"id": "EFO_0000616", "name": "Neoplasm"}, "score": 0.95},
                                {"disease": {"id": "EFO_0000384", "name": "Colorectal Neoplasm"}, "score": 0.88}
                            ]
                        },
                        "phenotypes": {
                            "rows": [
                                {"phenotypeHPO": {"id": "HP_0002664", "name": "Neoplasm"}}
                            ]
                        }
                    }
                }
            })

        # Default fast 200 response
        return httpx.Response(200, json={})

    orig_async_send = httpx.AsyncClient.send

    async def mock_async_send(self, request, *args, **kwargs):
        host = request.url.host.lower() if request.url.host else ""
        url_str = str(request.url).lower()
        port = request.url.port

        # Fast mock for local LLM servers on port 8080 and 11434
        if port in (8080, 11434) or ":8080" in url_str or ":11434" in url_str:
            if "models" in url_str:
                return httpx.Response(200, json={"data": [{"id": "qwen2.5-7b-instruct"}]})
            if "chat/completions" in url_str:
                req_body = getattr(request, "_content", b"") or b""
                is_streaming = b'"stream": true' in req_body.lower() or b'"stream":true' in req_body.lower()
                if is_streaming:
                    sse_body = (
                        b'data: {"choices":[{"delta":{"content":"Deterministic offline AI response."}}]}\n\n'
                        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                        b'data: [DONE]\n\n'
                    )
                    return httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})
                else:
                    return httpx.Response(200, json={
                        "id": "mock-cmpl-1",
                        "choices": [
                            {"message": {"role": "assistant", "content": "{\"response\": \"Deterministic offline response\", \"primary_goal\": \"general_optimization\", \"sub_goals\": []}"}, "finish_reason": "stop"}
                        ]
                    })
            return httpx.Response(200, json={})

        if host in ("testserver", "localhost", "127.0.0.1") or "testserver" in url_str:
            return await orig_async_send(self, request, *args, **kwargs)

        return mock_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", mock_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", mock_async_send)



