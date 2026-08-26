from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.catalog_service import CatalogService

router = APIRouter(tags=["catalog"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


_GLOBAL_CATALOG_SERVICE: Optional[CatalogService] = None


def get_catalog_service() -> CatalogService:
    global _GLOBAL_CATALOG_SERVICE
    if _GLOBAL_CATALOG_SERVICE is None:
        _GLOBAL_CATALOG_SERVICE = CatalogService()
    return _GLOBAL_CATALOG_SERVICE


@router.post("/api/compounds/batch")
def get_compounds_batch_api(
    payload: Dict[str, Any],
) -> JSONResponse:
    """Retrieve multiple compound pharmacology profiles in a single batch request."""
    keys = payload.get("keys", [])
    if isinstance(keys, str):
        keys = [k.strip() for k in keys.split(",") if k.strip()]
    service = get_catalog_service()
    results = service.get_compounds_by_keys(keys)
    return JSONResponse(results, headers=NO_CACHE_HEADERS)


@router.get("/api/compounds/search")
def search_compounds_api(
    q: str = Query(default=""),
    limit: int = Query(default=15, ge=1, le=100),
    auto_enrich: bool = Query(default=True),
) -> JSONResponse:
    """Typeahead search across compound keys, names, drug classes, and indications with on-demand fallback."""
    service = get_catalog_service()
    results = service.search_compounds(q, limit=limit, auto_enrich=auto_enrich)
    return JSONResponse(results, headers=NO_CACHE_HEADERS)


@router.get("/catalog")
def list_catalog(
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None),
) -> JSONResponse:
    """Paginated catalog list with optional multi-token keyword search."""
    service = get_catalog_service()
    compounds, total = service.query_compounds(limit=limit, offset=offset, search=search)
    return JSONResponse(
        {"items": compounds, "total": total, "limit": limit, "offset": offset},
        headers=NO_CACHE_HEADERS,
    )


@router.get("/catalog/{compound_key}")
def get_catalog_item(
    compound_key: str,
    auto_enrich: bool = Query(default=True),
) -> JSONResponse:
    """Retrieve full pharmacology profile for a compound by key or canonical name with write-through cache."""
    service = get_catalog_service()
    # Check if local hit first to set cache headers
    local_compound = service.get_compound(compound_key, auto_enrich=False)
    if local_compound is not None:
        headers = dict(NO_CACHE_HEADERS)
        headers["X-Cache-Status"] = "HIT"
        headers["X-Source-Tier"] = str(local_compound.get("source_tier") or "seed")
        return JSONResponse(local_compound, headers=headers)

    if not auto_enrich:
        raise HTTPException(status_code=404, detail="Compound not found.")

    compound = service.get_compound(compound_key, auto_enrich=True)
    if compound is None:
        raise HTTPException(status_code=404, detail="Compound not found.")

    headers = dict(NO_CACHE_HEADERS)
    headers["X-Cache-Status"] = "MISS_ENRICHED"
    headers["X-Source-Tier"] = str(compound.get("source_tier") or "live_enrichment")
    return JSONResponse(compound, headers=headers)


@router.post("/catalog/enrich-online/{compound_key}")
def enrich_catalog_item_online(compound_key: str) -> JSONResponse:
    """Enrich a compound using live OpenFDA, ChEMBL, and RxNorm APIs and write through to catalog."""
    service = get_catalog_service()
    enriched = service.enrich_compound_online(compound_key)
    if enriched is None:
        raise HTTPException(status_code=404, detail="Unable to enrich compound.")
    headers = dict(NO_CACHE_HEADERS)
    headers["X-Cache-Status"] = "WRITE_THROUGH_SAVED"
    headers["X-Source-Tier"] = str(enriched.get("source_tier") or "live_enrichment")
    return JSONResponse(enriched, headers=headers)


@router.post("/catalog")
def save_catalog_item(compound: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a compound pharmacology record."""
    if not compound.get("key"):
        raise HTTPException(status_code=400, detail="Compound key is required.")
    service = get_catalog_service()
    return service.upsert_compound(compound)


@router.delete("/catalog/{compound_key}")
def delete_catalog_item(compound_key: str) -> Dict[str, str]:
    """Delete a compound record from the active catalog."""
    service = get_catalog_service()
    deleted = service.delete_compound(compound_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Compound not found.")
    return {"deleted": compound_key}


@router.get("/catalog/{compound_key}/citations")
def get_compound_citations(compound_key: str) -> JSONResponse:
    """Retrieve structured peer-reviewed citations for a specific compound."""
    service = get_catalog_service()
    citations = service.get_citations_for_compound(compound_key)
    return JSONResponse(
        {"compound_key": compound_key, "count": len(citations), "citations": citations},
        headers=NO_CACHE_HEADERS,
    )


@router.get("/catalog/{compound_key}/trials")
def get_compound_trials(compound_key: str) -> JSONResponse:
    """Retrieve clinical trial registrations for a specific compound."""
    service = get_catalog_service()
    trials = service.get_clinical_trials_for_compound(compound_key)
    return JSONResponse(
        {"compound_key": compound_key, "count": len(trials), "trials": trials},
        headers=NO_CACHE_HEADERS,
    )


@router.get("/catalog/{compound_key}/evidence-dossier")
def get_compound_evidence_dossier_api(compound_key: str) -> JSONResponse:
    """Retrieve comprehensive scientific evidence dossier (citations, trials, milestones, and controversies)."""
    service = get_catalog_service()
    dossier = service.get_compound_evidence_dossier(compound_key)
    return JSONResponse(dossier, headers=NO_CACHE_HEADERS)


@router.post("/catalog/{compound_key}/citations")
def add_compound_citation(compound_key: str, payload: Dict[str, Any]) -> JSONResponse:
    """Add a structured citation record to a compound."""
    service = get_catalog_service()
    payload["compound_key"] = compound_key.strip().lower()
    cid = service.add_citation(payload)
    return JSONResponse({"id": cid, "status": "saved"}, headers=NO_CACHE_HEADERS)
