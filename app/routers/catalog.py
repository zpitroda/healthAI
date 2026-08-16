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


def get_catalog_service() -> CatalogService:
    return CatalogService()


@router.get("/api/compounds/search")
def search_compounds_api(
    q: str = Query(default=""),
    limit: int = Query(default=15, ge=1, le=100),
) -> JSONResponse:
    """Typeahead search across compound keys, names, drug classes, and indications."""
    service = get_catalog_service()
    results = service.search_compounds(q, limit=limit)
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
def get_catalog_item(compound_key: str) -> JSONResponse:
    """Retrieve full pharmacology profile for a compound by key or canonical name."""
    service = get_catalog_service()
    compound = service.get_compound(compound_key)
    if compound is None:
        raise HTTPException(status_code=404, detail="Compound not found.")
    return JSONResponse(compound, headers=NO_CACHE_HEADERS)


@router.post("/catalog/enrich-online/{compound_key}")
def enrich_catalog_item_online(compound_key: str) -> Dict[str, Any]:
    """Enrich a compound using live OpenFDA, ChEMBL, and RxNorm APIs."""
    service = get_catalog_service()
    enriched = service.enrich_compound_online(compound_key)
    if enriched is None:
        raise HTTPException(status_code=404, detail="Unable to enrich compound.")
    return enriched


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
    existing = service.get_compound(compound_key)
    if existing is None:
        raise HTTPException(status_code=404, detail="Compound not found.")
    service.delete_compound(compound_key)
    return {"deleted": compound_key}
