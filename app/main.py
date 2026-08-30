import time
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
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
from app.routers.debug import router as debug_router
from app.services.ai_service import preload_and_warmup_model
from app.services.debug_service import setup_debug_logging

from fastapi.middleware.gzip import GZipMiddleware

logger = logging.getLogger("healthai.http")

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
    except Exception as e:
        import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize debug logging handler
    setup_debug_logging()
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

# Request trace & correlation ID middleware
@app.middleware("http")
async def debug_trace_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    start_time = time.perf_counter()

    response = None
    try:
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-MS"] = str(elapsed_ms)

        # Don't clutter debug logs with static asset requests
        if not request.url.path.startswith("/static"):
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms) [req:{request_id}]"
            )
        return response
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            f"{request.method} {request.url.path} FAILED: {exc} ({elapsed_ms}ms) [req:{request_id}]",
            exc_info=True,
        )
        raise exc

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
app.include_router(debug_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "healthAI", "version": "2.0.0"}
