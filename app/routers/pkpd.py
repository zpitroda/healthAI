from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.schemas.pkpd import PKPDSimulationRequest, PKPDSimulationResponse, PKParameters, PDParameters
from app.services.catalog_service import CatalogService
from app.services.pkpd_engine import PKPDEngine
from app.services.pkpd_enricher import PKPDEnricher
from app.services.live_enrichment import LiveEnrichmentService

router = APIRouter(tags=["pkpd"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.post("/api/pkpd/simulate", response_model=PKPDSimulationResponse)
def simulate_pkpd(request: PKPDSimulationRequest) -> JSONResponse:
    """
    Simulates continuous time-concentration PK curves (Bateman 1-compartment, multi-dose steady state),
    computes DDI AUC ratios, and models sigmoidal Emax Hill pharmacodynamics.
    """
    service = CatalogService()
    compound = service.get_compound(request.compound_key)
    if not compound:
        # Create a transient compound profile
        compound = {
            "key": request.compound_key,
            "name": request.compound_key.replace("_", " ").title(),
            "half_life": "6 hours",
            "oral_bioavailability": "70%",
            "volume_of_distribution": "1.5 L/kg",
            "protein_binding": "80%",
            "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
            "transporters": {"substrates": [], "inhibitors": [], "inducers": []},
        }

    co_compounds_data: List[Dict[str, Any]] = []
    for co_key in request.co_administered_compounds:
        if co_key and co_key != request.compound_key:
            co_comp = service.get_compound(co_key)
            if co_comp:
                co_compounds_data.append(co_comp)

    result = PKPDEngine.simulate(compound, request, co_compounds_data=co_compounds_data)
    return JSONResponse(result.model_dump(), headers=NO_CACHE_HEADERS)


@router.get("/api/compounds/{compound_key}/pkpd")
def get_compound_pkpd(compound_key: str) -> JSONResponse:
    """Retrieve extracted quantitative PK and PD parameters for a compound."""
    service = CatalogService()
    compound = service.get_compound(compound_key)
    if not compound:
        raise HTTPException(status_code=404, detail="Compound not found in catalog.")

    pk_params = PKPDEngine.extract_pk_parameters(compound)
    pd_params = PKPDEngine.extract_pd_parameters(compound)

    return JSONResponse({
        "compound_key": compound["key"],
        "name": compound.get("name") or compound["key"],
        "pk": pk_params.model_dump(),
        "pd": pd_params.model_dump(),
    }, headers=NO_CACHE_HEADERS)


@router.post("/api/compounds/{compound_key}/enrich-full")
def enrich_compound_full(compound_key: str) -> JSONResponse:
    """
    Performs full multi-source structured enrichment (PubChem, ChEMBL Activity, UniProt, Reactome, OpenFDA)
    and saves the enriched quantitative PK/PD parameters to the SQLite database.
    """
    service = CatalogService()
    compound = service.get_compound(compound_key)
    if not compound:
        compound = {
            "key": compound_key.strip().lower().replace(" ", "_"),
            "name": compound_key.strip().title(),
            "canonical_name": compound_key.strip().title(),
        }

    # 1. Live Enrichment (OpenFDA + ChEMBL mechanisms + RxNorm ATC)
    live_service = LiveEnrichmentService()
    enriched = live_service.enrich_compound(compound)

    # 2. Structured PK/PD Enrichment (PubChem PUG-REST + ChEMBL quantitative affinities + USAN)
    pkpd_enricher = PKPDEnricher()
    enriched = pkpd_enricher.enrich_compound_pkpd(enriched)

    # Save to SQLite database
    saved = service.upsert_compound(enriched)
    return JSONResponse(saved, headers=NO_CACHE_HEADERS)
