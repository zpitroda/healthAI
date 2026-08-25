import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import (
    catalog_router,
    enrichment_router,
    graph_router,
    interactions_router,
    pkpd_router,
    protocols_router,
    views_router,
)
from app.routers.ai import router as ai_router
from app.services.ai_service import preload_and_warmup_model

from fastapi.middleware.gzip import GZipMiddleware

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

async def _warmup_background_services():
    try:
        import asyncio
        from app.services.catalog_service import CatalogService
        from app.services.interaction_engine import InteractionEngine
        from app.services.pathway_service import PathwayService

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: (
                CatalogService()._warm_cache(),
                PathwayService(),
                InteractionEngine(),
            ),
        )
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up in-memory catalog, pathway caches, and AI model in background on launch
    asyncio.create_task(_warmup_background_services())
    asyncio.create_task(preload_and_warmup_model())
    yield

app = FastAPI(
    title="HealthAI Pharmacology Lab & Protocol Engine",
    version="2.0.0",
    description="Individualized compound protocol optimization, pharmacokinetic conflict analysis, and biological network mapping.",
    lifespan=lifespan,
)

# Static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# API and View Routers
app.include_router(views_router)
app.include_router(catalog_router)
app.include_router(enrichment_router)
app.include_router(interactions_router)
app.include_router(graph_router)
app.include_router(protocols_router)
app.include_router(pkpd_router)
app.include_router(ai_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "healthAI", "version": "2.0.0"}
