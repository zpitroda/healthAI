from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import (
    catalog_router,
    graph_router,
    interactions_router,
    pkpd_router,
    protocols_router,
    views_router,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="HealthAI Pharmacology Lab & Protocol Engine",
    version="2.0.0",
    description="Individualized compound protocol optimization, pharmacokinetic conflict analysis, and biological network mapping.",
)

# Static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# API and View Routers
app.include_router(views_router)
app.include_router(catalog_router)
app.include_router(interactions_router)
app.include_router(graph_router)
app.include_router(protocols_router)
app.include_router(pkpd_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "healthAI", "version": "2.0.0"}
