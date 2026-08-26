import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, status

from app.schemas.debug import (
    LogFilterQuery,
    SetLogLevelRequest,
    DebugEvalRequest,
    DebugEvalResponse,
)
from app.services.debug_service import (
    ring_buffer_handler,
    log_broadcaster,
    SystemDiagnostics,
    DebugRunner,
)

router = APIRouter(prefix="/api/debug", tags=["debug"])
logger = logging.getLogger("healthai.router.debug")


@router.get("/logs")
def get_logs(
    min_level: Optional[str] = Query(None, description="Minimum log level: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
    logger_name: Optional[str] = Query(None, description="Logger name sub-string filter"),
    q: Optional[str] = Query(None, description="Search query string"),
    limit: int = Query(200, ge=1, le=2000),
) -> Dict[str, Any]:
    """Retrieve filtered log entries from the in-memory ring buffer."""
    logs = ring_buffer_handler.get_logs(
        min_level=min_level,
        logger_filter=logger_name,
        search_query=q,
        limit=limit,
    )
    return {
        "count": len(logs),
        "total_buffered": ring_buffer_handler.count,
        "logs": logs,
    }


@router.delete("/logs")
def clear_logs() -> Dict[str, Any]:
    """Clear all buffered log entries."""
    count_before = ring_buffer_handler.count
    ring_buffer_handler.clear()
    logger.info("Debug log buffer cleared manually via API.")
    return {"message": "Logs cleared successfully", "cleared_count": count_before}


@router.get("/system")
def get_system_diagnostics() -> Dict[str, Any]:
    """Get real-time system diagnostics, memory usage, and database connections."""
    return SystemDiagnostics.get_system_info()


@router.get("/loggers")
def get_all_loggers() -> Dict[str, Any]:
    """Get list of registered loggers and their effective log levels."""
    loggers = SystemDiagnostics.get_all_loggers()
    return {"count": len(loggers), "loggers": loggers}


@router.post("/log-level")
def set_logger_level(payload: SetLogLevelRequest) -> Dict[str, Any]:
    """Dynamically set the log level for a specific logger."""
    success = SystemDiagnostics.set_logger_level(payload.logger_name, payload.level_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid log level '{payload.level_name}'. Expected DEBUG, INFO, WARNING, ERROR, or CRITICAL.",
        )
    return {
        "message": f"Log level for '{payload.logger_name}' successfully set to {payload.level_name.upper()}",
        "logger_name": payload.logger_name,
        "new_level": payload.level_name.upper(),
    }


@router.post("/eval", response_model=DebugEvalResponse)
def evaluate_debug_payload(payload: DebugEvalRequest) -> DebugEvalResponse:
    """Execute interactive backend evaluations without test scripts."""
    try:
        if payload.eval_type == "collision":
            if not payload.stack:
                raise HTTPException(status_code=400, detail="Stack parameter is required for collision eval.")
            res = DebugRunner.run_collision_test(payload.stack)
            return DebugEvalResponse(
                success=True,
                execution_time_ms=res["execution_time_ms"],
                data=res["result"],
            )

        elif payload.eval_type == "pkpd":
            if not payload.compound_key:
                raise HTTPException(status_code=400, detail="compound_key parameter is required for PKPD eval.")
            res = DebugRunner.run_pkpd_simulation(
                payload.compound_key,
                dose_mg=payload.dose_mg or 100.0,
                duration_h=payload.duration_h or 24.0,
            )
            return DebugEvalResponse(
                success=True,
                execution_time_ms=res["execution_time_ms"],
                data=res["result"],
            )

        elif payload.eval_type == "catalog":
            if not payload.query:
                raise HTTPException(status_code=400, detail="query parameter is required for catalog search eval.")
            res = DebugRunner.run_catalog_lookup(payload.query)
            return DebugEvalResponse(
                success=True,
                execution_time_ms=res["execution_time_ms"],
                data=res,
            )

        elif payload.eval_type == "graph":
            if not payload.cypher:
                raise HTTPException(status_code=400, detail="cypher parameter is required for graph query eval.")
            res = DebugRunner.run_graph_query(payload.cypher)
            return DebugEvalResponse(
                success=res.get("success", False),
                execution_time_ms=res["execution_time_ms"],
                data=res.get("results"),
                error=res.get("error"),
            )

        elif payload.eval_type == "snippet":
            if not payload.code:
                raise HTTPException(status_code=400, detail="code parameter is required for Python snippet eval.")
            res = DebugRunner.run_code_snippet(payload.code)
            return DebugEvalResponse(
                success=res.get("success", False),
                execution_time_ms=res["execution_time_ms"],
                data=res.get("outputs"),
                error=res.get("error"),
                traceback=res.get("traceback"),
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown eval_type '{payload.eval_type}'. Expected collision, pkpd, catalog, graph, or snippet.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during debug evaluation: {e}", exc_info=True)
        return DebugEvalResponse(
            success=False,
            execution_time_ms=0.0,
            data=None,
            error=str(e),
        )


@router.websocket("/ws/logs")
async def websocket_logs_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming real-time log records."""
    await log_broadcaster.connect(websocket)
    try:
        # Stream initial snapshot of recent logs upon connection
        snapshot = ring_buffer_handler.get_logs(limit=50)
        await websocket.send_json({"type": "snapshot", "data": snapshot})

        while True:
            # Keep connection open and handle incoming ping/pong or client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        log_broadcaster.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket log client error: {e}")
        log_broadcaster.disconnect(websocket)
