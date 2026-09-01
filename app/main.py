import time
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
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
    description="""
# HealthAI // Next-Generation Clinical Pharmacology & Network Biology Platform

> ⚠️ **IMPORTANT MEDICAL & SCIENTIFIC RESEARCH NOTICE:**
> HealthAI is an experimental computational pharmacology simulation, continuous biophysical PBPK modeling, and educational network analysis platform.
> **HealthAI is NOT a licensed medical device and does NOT provide medical advice, clinical diagnoses, or treatment prescriptions.**
> All pharmacokinetic projections, collision matrices, receptor occupancy simulations, and AI Copilot outputs are mathematical approximations intended for research and educational purposes only. Always consult a qualified, licensed healthcare provider before initiating, modifying, or discontinuing any medication, peptide, or supplement protocol.

---
### Capabilities & Endpoints
- **Interactive Collision Matrix**: CYP450, Phase II, transporter saturation, and emergent syndrome alerts.
- **Autonomous AI Copilot**: Multi-persona reasoning drawer (Architect, Auditor, Tutor, Labs) with real-time SSE streaming.
- **6-Tier Knowledge Graph**: Molecular targets, cascades, organ physiology, biomarkers, and clinical outcomes.
- **Continuous PBPK & ODE Engine**: 1- and 2-compartment open models with Rodgers-Rowland tissue partitioning.
    """,
    terms_of_service="/api/disclaimer",
    contact={
        "name": "HealthAI Research & Safety Team",
        "url": "http://127.0.0.1:8000/",
    },
    license_info={
        "name": "MIT License with Medical Research Disclaimer",
        "url": "https://opensource.org/licenses/MIT",
    },
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
        exc_name = exc.__class__.__name__
        if exc_name in ("EndOfStream", "ClientDisconnect", "CancelledError"):
            logger.info(
                f"{request.method} {request.url.path} client disconnected ({elapsed_ms}ms) [req:{request_id}]"
            )
            return Response(status_code=499)
        logger.error(
            f"{request.method} {request.url.path} FAILED: {exc} ({elapsed_ms}ms) [req:{request_id}]",
            exc_info=True,
        )
        raise exc

# Static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon_ico():
    return FileResponse(STATIC_DIR / "favicon.ico", media_type="image/x-icon")

@app.get("/favicon.svg", include_in_schema=False)
async def get_favicon_svg():
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

@app.get("/site.webmanifest", include_in_schema=False)
async def get_webmanifest():
    return FileResponse(STATIC_DIR / "site.webmanifest", media_type="application/manifest+json")

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
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "healthAI", "version": "2.0.0"}


@app.get("/api/disclaimer", tags=["system"])
async def get_disclaimer() -> dict[str, Any]:
    """
    Official HealthAI Medical, Scientific Research, and Legal Disclaimers.
    """
    return {
        "title": "HealthAI Medical & Scientific Research Disclaimer",
        "version": "1.0.0",
        "last_updated": "2026-08-31",
        "summary": "HealthAI is an in silico computational pharmacology simulation, biophysical PBPK modeling, and educational network analysis platform. It does NOT provide medical advice, clinical diagnoses, or treatment prescriptions.",
        "sections": {
            "medical_disclaimer": (
                "HealthAI is designed solely for scientific research, educational modeling, and mechanistic pharmacology analysis. "
                "The software, its simulated pharmacokinetic curves, collision matrices, circadian schedules, and AI Copilot outputs "
                "do not constitute medical advice or clinical diagnoses. Always consult a qualified, licensed healthcare provider "
                "before starting, stopping, or altering any pharmaceutical or supplement protocol."
            ),
            "computational_scope": (
                "All simulations (including 1- and 2-compartment open models, Rodgers-Rowland tissue partition coefficients, and receptor occupancy curves) "
                "are continuous mathematical approximations derived from published literature and population parameters. In vivo human biological responses "
                "may vary significantly due to genetics, organ perfusion, gastrointestinal factors, and individual health states."
            ),
            "terms_and_liability": (
                "This platform is provided 'AS IS' without warranties of any kind. Under no circumstances shall the authors, contributors, "
                "or maintainers be held liable for any clinical decisions, direct or indirect damages, adverse events, or injuries arising from "
                "the use or misuse of information provided by this software."
            ),
            "emergency_notice": (
                "If you or someone in your care is experiencing a medical emergency, acute toxicity symptoms, chest pain, or severe adverse reactions, "
                "immediately call your local emergency services (911 in US/Canada, 999 in UK, 112 in EU) or go to the nearest emergency department."
            ),
        },
        "emergency_contacts": {
            "us_poison_control": "1-800-222-1222",
            "uk_nhs_non_emergency": "111",
            "uk_emergency": "999",
            "eu_emergency": "112",
            "us_emergency": "911",
        },
    }
