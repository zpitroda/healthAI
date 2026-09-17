from __future__ import annotations

from typing import Any, Dict, List, Optional
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
def get_compound_pkpd(compound_key: str, dose_mg: Optional[float] = None) -> JSONResponse:
    """Retrieve extracted quantitative PK and PD parameters for a compound with dose-dependent target occupancies."""
    service = CatalogService()
    compound = service.get_compound(compound_key)
    if not compound:
        raise HTTPException(status_code=404, detail="Compound not found in catalog.")

    pk_params = PKPDEngine.extract_pk_parameters(compound)
    pd_params = PKPDEngine.extract_pd_parameters(compound)

    # Compute target occupancies at requested or default dose
    if dose_mg is None or dose_mg <= 0:
        from app.services.dosing_service import get_default_compound_dose
        def_dose_info = get_default_compound_dose(compound)
        calc_dose = float(def_dose_info.get("dose_mg") or 100.0)
    else:
        calc_dose = dose_mg

    sim_req = PKPDSimulationRequest(
        compound_key=compound["key"],
        dose_mg=calc_dose,
        dosing_interval_h=24.0,
        simulation_duration_h=48.0,
        route="oral",
        steady_state=True,
    )
    sim_res = PKPDEngine.simulate(compound, sim_req)

    return JSONResponse({
        "compound_key": compound["key"],
        "name": compound.get("name") or compound["key"],
        "simulated_dose_mg": calc_dose,
        "pk": pk_params.model_dump(),
        "pd": pd_params.model_dump(),
        "target_occupancies": [to.model_dump() for to in sim_res.target_occupancies],
    }, headers=NO_CACHE_HEADERS)


@router.get("/api/compounds/{compound_key}/receptor-occupancy")
def get_compound_receptor_occupancy(
    compound_key: str,
    dose_mg: Optional[float] = None,
    route: str = "oral",
    dosing_interval_h: float = 24.0,
    steady_state: bool = True,
) -> JSONResponse:
    """
    Calculates dose-dependent target receptor saturation (occupancy %) across all molecular targets
    for a specific compound and dosing regimen.
    """
    service = CatalogService()
    compound = service.get_compound(compound_key)
    if not compound:
        raise HTTPException(status_code=404, detail=f"Compound '{compound_key}' not found in catalog.")

    if dose_mg is None or dose_mg <= 0:
        from app.services.dosing_service import get_default_compound_dose
        def_dose_info = get_default_compound_dose(compound)
        dose_mg = float(def_dose_info.get("dose_mg") or 100.0)

    req = PKPDSimulationRequest(
        compound_key=compound["key"],
        dose_mg=dose_mg,
        dosing_interval_h=dosing_interval_h,
        simulation_duration_h=max(48.0, dosing_interval_h * 2),
        route=route,
        steady_state=steady_state,
    )
    sim_res = PKPDEngine.simulate(compound, req)
    circadian = PKPDEngine.calculate_circadian_receptor_occupancy(
        compound=compound,
        dose_mg=dose_mg,
        route=route,
        dosing_interval_h=dosing_interval_h,
    )

    return JSONResponse({
        "compound_key": compound["key"],
        "compound_name": sim_res.compound_name,
        "dose_mg": dose_mg,
        "route": route,
        "dosing_interval_h": dosing_interval_h,
        "steady_state": steady_state,
        "c_max_ng_ml": sim_res.c_max_ng_ml,
        "c_avg_ss_ng_ml": sim_res.c_avg_ss_ng_ml,
        "c_min_trough_ng_ml": sim_res.c_min_trough_ng_ml,
        "target_occupancies": [to.model_dump() for to in sim_res.target_occupancies],
        "circadian_windows": circadian.get("targets", []),
    }, headers=NO_CACHE_HEADERS)


from datetime import datetime, timezone

@router.api_route("/api/compounds/{compound_key}/enrich-full", methods=["GET", "POST"])
def enrich_compound_full(compound_key: str, force: bool = False) -> JSONResponse:
    """
    Performs full multi-source structured enrichment (PubChem, ChEMBL Activity, UniProt, Reactome, OpenFDA)
    and saves the enriched quantitative PK/PD parameters to the SQLite database.
    """
    service = CatalogService()
    compound = service.get_compound(compound_key)
    if compound and compound.get("last_enriched_at") and not force:
        return JSONResponse(compound, headers=NO_CACHE_HEADERS)

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

    # Mark enrichment timestamp
    enriched["last_enriched_at"] = datetime.now(timezone.utc).isoformat()
    if enriched.get("source_tier") == "seed":
        enriched["source_tier"] = "live_enrichment"

    # Save to SQLite database
    saved = service.upsert_compound(enriched)
    return JSONResponse(saved, headers=NO_CACHE_HEADERS)
