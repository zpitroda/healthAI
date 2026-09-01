from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["views"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.get("/")
def serve_index() -> FileResponse:
    """Serve the main Pharmacology Lab dashboard."""
    return FileResponse(STATIC_DIR / "index.html", headers=NO_CACHE_HEADERS)


@router.get("/admin")
def serve_admin() -> FileResponse:
    """Serve the Catalog Management & Ingestion Admin interface."""
    return FileResponse(STATIC_DIR / "admin.html", headers=NO_CACHE_HEADERS)


@router.get("/graph")
def serve_graph() -> FileResponse:
    """Serve the Interactive Biological Knowledge Graph view."""
    return FileResponse(STATIC_DIR / "graph.html", headers=NO_CACHE_HEADERS)


@router.get("/compound")
@router.get("/compound/{compound_key}")
def serve_compound_page(compound_key: str = "caffeine") -> FileResponse:
    """Serve the deep-dive profile page for an individual compound."""
    return FileResponse(STATIC_DIR / "compound.html", headers=NO_CACHE_HEADERS)


@router.get("/debug")
def serve_debug() -> FileResponse:
    """Serve the Interactive Debugging & Log Workbench interface."""
    return FileResponse(STATIC_DIR / "debug.html", headers=NO_CACHE_HEADERS)
