from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("healthai.ingestion_queue")


class IngestionJobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionJob:
    """Dataclass representing an asynchronous multi-source compound enrichment job."""

    def __init__(
        self,
        job_id: str,
        compounds: List[str],
        auto_save_catalog: bool = True,
    ):
        self.job_id = job_id
        self.compounds = compounds
        self.auto_save_catalog = auto_save_catalog
        self.status = IngestionJobStatus.QUEUED
        self.progress_pct: float = 0.0
        self.current_step: str = "Job queued in background worker pool"
        self.logs: List[Dict[str, str]] = []
        self.results: Dict[str, Any] = {}
        self.failed_compounds: List[str] = []
        self.error_message: Optional[str] = None
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = datetime.now(timezone.utc).isoformat()

    def add_log(self, message: str, level: str = "INFO") -> Dict[str, str]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        self.logs.append(entry)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return entry

    def update_progress(self, progress_pct: float, step: str) -> None:
        self.progress_pct = max(0.0, min(100.0, round(progress_pct, 1)))
        self.current_step = step
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "compounds": self.compounds,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "current_step": self.current_step,
            "total_compounds": len(self.compounds),
            "completed_compounds": len(self.results),
            "failed_compounds": self.failed_compounds,
            "logs": self.logs,
            "results": self.results,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class IngestionJobQueue:
    """
    Async Ingestion Job Queue Manager & Worker Pool.
    Handles background execution of multi-source enrichment queries with real-time
    WebSocket event broadcasting.
    """

    _instance: Optional[IngestionJobQueue] = None

    def __new__(cls, num_workers: int = 3) -> IngestionJobQueue:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, num_workers: int = 3) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.num_workers = num_workers
        self.jobs: Dict[str, IngestionJob] = {}
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.workers: List[asyncio.Task] = []
        self.active_websockets: Set[WebSocket] = set()
        self.job_websockets: Dict[str, Set[WebSocket]] = {}
        self._running = False

    async def start_workers(self) -> None:
        """Start async worker pool tasks if not already running."""
        if self._running:
            return
        self._running = True
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker_loop(i))
            self.workers.append(task)
        logger.info("Started %d background ingestion queue workers.", self.num_workers)

    async def stop_workers(self) -> None:
        """Gracefully stop background worker pool."""
        self._running = False
        for worker in self.workers:
            worker.cancel()
        self.workers.clear()

    def submit_job(self, compounds: List[str], auto_save_catalog: bool = True) -> IngestionJob:
        """Submit a single or batch enrichment job to the async worker queue."""
        clean_compounds = list(dict.fromkeys(
            c.strip().lower() for c in compounds if isinstance(c, str) and c.strip()
        ))
        if not clean_compounds:
            raise ValueError("At least one compound key or name is required.")

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = IngestionJob(job_id=job_id, compounds=clean_compounds, auto_save_catalog=auto_save_catalog)
        job.add_log(f"Job {job_id} queued with {len(clean_compounds)} compound(s).")

        self.jobs[job_id] = job
        try:
            self.queue.put_nowait(job_id)
        except Exception as e:
            logger.error("Failed to enqueue job %s: %s", job_id, e)

        # Ensure workers are running
        try:
            loop = asyncio.get_running_loop()
            if not self._running:
                loop.create_task(self.start_workers())
        except RuntimeError:
            pass

        return job

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        return self.jobs.get(job_id)

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        sorted_jobs = sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in sorted_jobs[:limit]]

    # WebSocket Connection Registration
    async def connect_websocket(self, websocket: WebSocket, job_id: Optional[str] = None) -> None:
        await websocket.accept()
        self.active_websockets.add(websocket)
        if job_id:
            self.job_websockets.setdefault(job_id, set()).add(websocket)
            job = self.get_job(job_id)
            if job:
                await websocket.send_json({
                    "event": "job_status",
                    "job": job.to_dict()
                })

    def disconnect_websocket(self, websocket: WebSocket, job_id: Optional[str] = None) -> None:
        self.active_websockets.discard(websocket)
        if job_id and job_id in self.job_websockets:
            self.job_websockets[job_id].discard(websocket)

    async def broadcast_job_event(self, job: IngestionJob, event_type: str = "job_progress") -> None:
        """Broadcast real-time job progress or event to connected WebSockets."""
        payload = {
            "event": event_type,
            "job_id": job.job_id,
            "status": job.status,
            "progress_pct": job.progress_pct,
            "current_step": job.current_step,
            "completed_compounds": len(job.results),
            "total_compounds": len(job.compounds),
            "latest_log": job.logs[-1] if job.logs else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Send to specific job listeners and global listeners
        targets = set(self.active_websockets)
        if job.job_id in self.job_websockets:
            targets.update(self.job_websockets[job.job_id])

        disconnected = set()
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.add(ws)

        for ws in disconnected:
            self.disconnect_websocket(ws, job.job_id)

    async def _worker_loop(self, worker_id: int) -> None:
        """Background worker execution loop."""
        while self._running:
            try:
                job_id = await self.queue.get()
                job = self.jobs.get(job_id)
                if not job:
                    self.queue.task_done()
                    continue

                await self._process_job(job, worker_id)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker %d encountered error: %s", worker_id, e)
                await asyncio.sleep(0.5)

    async def _process_job(self, job: IngestionJob, worker_id: int) -> None:
        """Executes multi-source live enrichment queries for compounds in the job."""
        from app.services.catalog_service import CatalogService
        from app.services.live_enrichment import LiveEnrichmentService

        catalog_service = CatalogService()
        live_service = LiveEnrichmentService()

        job.status = IngestionJobStatus.RUNNING
        job.update_progress(0.0, f"Worker {worker_id} started processing job")
        job.add_log(f"Worker {worker_id} executing enrichment pipeline for {len(job.compounds)} compound(s).")
        await self.broadcast_job_event(job, "job_started")

        total = len(job.compounds)
        for idx, item in enumerate(job.compounds, start=1):
            step_msg = f"Enriching [{idx}/{total}]: {item}"
            job.update_progress((idx - 1) / total * 100.0, step_msg)
            job.add_log(f"Querying OpenFDA, ChEMBL, PubChem, and RxNorm for '{item}'...")
            await self.broadcast_job_event(job, "job_progress")

            try:
                # Execute blocking live enrichment in threadpool to keep event loop responsive
                loop = asyncio.get_running_loop()
                enriched = await loop.run_in_executor(
                    None,
                    lambda: live_service.fetch_compound_profile(item)
                )

                if enriched:
                    if job.auto_save_catalog:
                        # Write-through save into SQLite catalog
                        saved = await loop.run_in_executor(
                            None,
                            lambda: catalog_service.upsert_compound(enriched)
                        )
                        job.results[item] = saved
                    else:
                        job.results[item] = enriched

                    targets_count = len(enriched.get("receptor_targets", []))
                    job.add_log(f"Successfully enriched '{item}' ({targets_count} receptor targets, source: {enriched.get('source_tier')}).")
                else:
                    job.failed_compounds.append(item)
                    job.add_log(f"No online data found for '{item}'.", level="WARNING")

            except Exception as e:
                job.failed_compounds.append(item)
                job.add_log(f"Error enriching '{item}': {e}", level="ERROR")
                logger.exception("Failed to enrich compound %s in job %s", item, job.job_id)

            # Update progress after each compound
            progress = (idx / total) * 100.0
            job.update_progress(progress, f"Completed {idx}/{total}: {item}")
            await self.broadcast_job_event(job, "job_progress")

        if len(job.results) > 0:
            job.status = IngestionJobStatus.COMPLETED
            job.update_progress(100.0, f"Job completed ({len(job.results)} enriched, {len(job.failed_compounds)} failed)")
            job.add_log(f"Job completed successfully with {len(job.results)} enriched compounds.")
        else:
            job.status = IngestionJobStatus.FAILED
            job.error_message = "Enrichment failed for all requested compounds."
            job.update_progress(100.0, "Job failed: No compounds enriched")
            job.add_log("Job failed. Could not enrich any requested compounds.", level="ERROR")

        await self.broadcast_job_event(job, "job_completed")


# Singleton instance accessor
_QUEUE_INSTANCE: Optional[IngestionJobQueue] = None


def get_ingestion_queue() -> IngestionJobQueue:
    global _QUEUE_INSTANCE
    if _QUEUE_INSTANCE is None:
        _QUEUE_INSTANCE = IngestionJobQueue()
    return _QUEUE_INSTANCE
