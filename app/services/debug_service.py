import sys
import time
import logging
import asyncio
import traceback
import platform
import sqlite3
from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("healthai.debug_service")


class LogEntry:
    def __init__(self, record: logging.LogRecord, request_id: Optional[str] = None):
        self.timestamp = datetime.fromtimestamp(record.created).isoformat()
        self.created = record.created
        self.level = record.levelname
        self.logger_name = record.name
        self.message = record.getMessage()
        self.filename = record.filename
        self.lineno = record.lineno
        self.funcName = record.funcName
        self.request_id = request_id or getattr(record, "request_id", None)
        self.exc_info = None
        if record.exc_info:
            self.exc_info = "".join(traceback.format_exception(*record.exc_info))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "created": self.created,
            "level": self.level,
            "logger_name": self.logger_name,
            "message": self.message,
            "filename": self.filename,
            "lineno": self.lineno,
            "funcName": self.funcName,
            "request_id": self.request_id,
            "exc_info": self.exc_info,
        }


class RingBufferLogHandler(logging.Handler):
    """Thread-safe logging handler storing recent log records in a fixed-size ring buffer."""
    def __init__(self, max_capacity: int = 2000):
        super().__init__()
        self.max_capacity = max_capacity
        self._buffer: deque = deque(maxlen=max_capacity)
        self.broadcaster: Optional["WebSocketLogBroadcaster"] = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry(record)
            self._buffer.append(entry)
            if self.broadcaster:
                self.broadcaster.broadcast_log(entry.to_dict())
        except Exception:
            self.handleError(record)

    def get_logs(
        self,
        min_level: Optional[str] = None,
        logger_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        level_map = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        min_level_num = level_map.get((min_level or "").upper(), 0)

        results = []
        for entry in list(self._buffer):
            if min_level_num and level_map.get(entry.level, 0) < min_level_num:
                continue
            if logger_filter and logger_filter.lower() not in entry.logger_name.lower():
                continue
            if search_query:
                q = search_query.lower()
                if q not in entry.message.lower() and q not in entry.logger_name.lower():
                    continue
            results.append(entry.to_dict())

        return results[-limit:]

    def clear(self) -> None:
        self._buffer.clear()

    @property
    def count(self) -> int:
        return len(self._buffer)


class WebSocketLogBroadcaster:
    """Manages active WebSocket connections for streaming real-time log records."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def broadcast_log(self, log_dict: Dict[str, Any]):
        if not self.active_connections:
            return

        # Schedule message emission on current event loop if running
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                dead_sockets = []
                for ws in list(self.active_connections):
                    try:
                        asyncio.run_coroutine_threadsafe(ws.send_json({"type": "log", "data": log_dict}), loop)
                    except Exception:
                        dead_sockets.append(ws)
                for ws in dead_sockets:
                    self.disconnect(ws)
        except RuntimeError:
            pass


# Global singleton log handler and broadcaster
ring_buffer_handler = RingBufferLogHandler(max_capacity=2000)
log_broadcaster = WebSocketLogBroadcaster()
ring_buffer_handler.broadcaster = log_broadcaster


def setup_debug_logging():
    """Attaches ring_buffer_handler to the root logger and healthai loggers."""
    root_logger = logging.getLogger()
    if ring_buffer_handler not in root_logger.handlers:
        root_logger.addHandler(ring_buffer_handler)

    healthai_logger = logging.getLogger("healthai")
    healthai_logger.setLevel(logging.DEBUG)


class SystemDiagnostics:
    """Collects system health, memory usage, database statuses, and logger states."""
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        import os

        mem_info = {}
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_info = {
                "rss_mb": round(process.memory_info().rss / (1024 * 1024), 2),
                "vsz_mb": round(process.memory_info().vms / (1024 * 1024), 2),
                "cpu_percent": process.cpu_percent(interval=None),
            }
        except Exception:
            mem_info = {"notice": "psutil unavailable"}

        # SQLite status
        sqlite_status = "unknown"
        sqlite_compounds_count = 0
        try:
            from app.services.catalog_service import CatalogService
            cat = CatalogService()
            compounds = cat.list_compounds()
            sqlite_compounds_count = len(compounds)
            sqlite_status = "connected"
        except Exception as e:
            sqlite_status = f"error: {str(e)}"

        # Neo4j status
        neo4j_status = "disconnected (in-memory fallback)"
        try:
            from app.knowledge_graph.graph_db import Neo4jGraphDatabase
            g_db = Neo4jGraphDatabase()
            if getattr(g_db, "driver", None) or (hasattr(g_db, "is_connected") and g_db.is_connected()):
                neo4j_status = f"connected ({g_db.uri})"
        except Exception as e:
            neo4j_status = f"error: {str(e)}"

        return {
            "platform": platform.platform(),
            "python_version": sys.version,
            "timestamp": datetime.now().isoformat(),
            "memory": mem_info,
            "sqlite_status": sqlite_status,
            "sqlite_compounds_count": sqlite_compounds_count,
            "neo4j_status": neo4j_status,
            "total_logs_in_buffer": ring_buffer_handler.count,
        }

    @staticmethod
    def get_all_loggers() -> List[Dict[str, Any]]:
        loggers_info = []
        root = logging.getLogger()
        loggers_info.append({
            "name": "root",
            "level": logging.getLevelName(root.getEffectiveLevel()),
            "level_num": root.getEffectiveLevel(),
        })

        for name in sorted(logging.root.manager.loggerDict):
            logger_obj = logging.getLogger(name)
            loggers_info.append({
                "name": name,
                "level": logging.getLevelName(logger_obj.getEffectiveLevel()),
                "level_num": logger_obj.getEffectiveLevel(),
                "disabled": getattr(logger_obj, "disabled", False),
            })
        return loggers_info

    @staticmethod
    def set_logger_level(logger_name: str, level_name: str) -> bool:
        valid_levels = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
        level_val = valid_levels.get(level_name.upper())
        if level_val is None:
            return False

        target_logger = logging.getLogger(logger_name if logger_name != "root" else "")
        target_logger.setLevel(level_val)
        logger.info(f"Log level for logger '{logger_name}' set to {level_name.upper()}")
        return True


class DebugRunner:
    """Provides direct execution sandbox for internal pharmacology modules and tests."""
    @staticmethod
    def run_collision_test(stack: List[Dict[str, Any]]) -> Dict[str, Any]:
        from app.services.interaction_engine import InteractionEngine
        engine = InteractionEngine()
        start = time.perf_counter()
        result = engine.analyze_stack(stack)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"execution_time_ms": elapsed_ms, "result": result}

    @staticmethod
    def run_pkpd_simulation(compound_key: str, dose_mg: float = 100.0, duration_h: float = 24.0) -> Dict[str, Any]:
        from app.services.pkpd_engine import PKPDEngine
        engine = PKPDEngine()
        start = time.perf_counter()
        result = engine.simulate(compound_key=compound_key, dose_mg=dose_mg, duration_hours=duration_h)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"execution_time_ms": elapsed_ms, "result": result}

    @staticmethod
    def run_catalog_lookup(query: str) -> Dict[str, Any]:
        from app.services.catalog_service import CatalogService
        cat = CatalogService()
        start = time.perf_counter()
        results = cat.search_compounds(query)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"execution_time_ms": elapsed_ms, "query": query, "count": len(results), "results": results[:10]}

    @staticmethod
    def run_graph_query(cypher: str) -> Dict[str, Any]:
        from app.knowledge_graph.graph_db import Neo4jGraphDatabase
        g_db = Neo4jGraphDatabase()
        start = time.perf_counter()
        try:
            res = g_db.execute_cypher(cypher)
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            return {"execution_time_ms": elapsed_ms, "success": True, "results": res}
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            return {"execution_time_ms": elapsed_ms, "success": False, "error": str(e)}

    @staticmethod
    def run_code_snippet(code: str) -> Dict[str, Any]:
        """Runs arbitrary python snippet in controlled namespace for fast debugging."""
        start = time.perf_counter()
        local_scope = {}
        # Pre-import common services for convenience
        global_scope = {
            "logging": logging,
            "asyncio": asyncio,
            "sqlite3": sqlite3,
        }
        try:
            exec("from app.services.catalog_service import CatalogService\n"
                 "from app.services.interaction_engine import InteractionEngine\n"
                 "from app.services.pkpd_engine import PKPDEngine\n"
                 "from app.knowledge_graph.graph import BiologicalGraph\n"
                 "from app.services.copilot_agent import CopilotAgent\n"
                 + code, global_scope, local_scope)
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            # Filter non-serializable objects
            safe_results = {}
            for k, v in local_scope.items():
                if k.startswith("_"):
                    continue
                try:
                    import json
                    json.dumps(v)
                    safe_results[k] = v
                except Exception:
                    safe_results[k] = str(v)
            return {"execution_time_ms": elapsed_ms, "success": True, "outputs": safe_results}
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "execution_time_ms": elapsed_ms,
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
