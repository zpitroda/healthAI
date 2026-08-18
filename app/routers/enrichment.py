from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.ingestion_queue import (
    IngestionJobQueue,
    get_ingestion_queue,
)

router = APIRouter(tags=["enrichment"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class SubmitEnrichmentJobRequest(BaseModel):
    compounds: List[str] = Field(
        ...,
        description="List of compound keys or names to enrich asynchronously from multi-source APIs",
        examples=[["telmisartan", "sildenafil", "exemestane"]],
    )
    auto_save_catalog: bool = Field(
        default=True,
        description="Whether to automatically write-through save enriched compound profiles into the SQLite catalog",
    )


@router.post("/api/enrichment/jobs")
async def submit_enrichment_job(request: SubmitEnrichmentJobRequest) -> JSONResponse:
    """Submit long-running multi-source enrichment query to background async worker queue."""
    if not request.compounds:
        raise HTTPException(status_code=400, detail="At least one compound key or name is required.")

    queue = get_ingestion_queue()
    try:
        job = queue.submit_job(
            compounds=request.compounds,
            auto_save_catalog=request.auto_save_catalog,
        )
        return JSONResponse(job.to_dict(), status_code=202, headers=NO_CACHE_HEADERS)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/enrichment/jobs/{job_id}")
async def get_enrichment_job(job_id: str) -> JSONResponse:
    """Retrieve status, progress, logs, and results for a specific enrichment job."""
    queue = get_ingestion_queue()
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Enrichment job '{job_id}' not found.")
    return JSONResponse(job.to_dict(), headers=NO_CACHE_HEADERS)


@router.get("/api/enrichment/jobs")
async def list_enrichment_jobs(limit: int = Query(default=20, ge=1, le=100)) -> JSONResponse:
    """List recent background enrichment jobs and their status."""
    queue = get_ingestion_queue()
    jobs = queue.list_jobs(limit=limit)
    return JSONResponse({"jobs": jobs, "total": len(jobs)}, headers=NO_CACHE_HEADERS)


@router.websocket("/ws/enrichment")
async def websocket_enrichment_stream(websocket: WebSocket) -> None:
    """Global WebSocket endpoint streaming real-time background job events & multi-source query logs."""
    queue = get_ingestion_queue()
    await queue.connect_websocket(websocket)
    try:
        while True:
            # Keep connection alive & listen for client ping or command
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        queue.disconnect_websocket(websocket)
    except Exception:
        queue.disconnect_websocket(websocket)


@router.websocket("/ws/enrichment/{job_id}")
async def websocket_job_stream(websocket: WebSocket, job_id: str) -> None:
    """Dedicated WebSocket endpoint streaming real-time progress for a specific job_id."""
    queue = get_ingestion_queue()
    await queue.connect_websocket(websocket, job_id=job_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"event": "pong", "job_id": job_id})
    except WebSocketDisconnect:
        queue.disconnect_websocket(websocket, job_id=job_id)
    except Exception:
        queue.disconnect_websocket(websocket, job_id=job_id)
