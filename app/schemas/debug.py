from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class LogFilterQuery(BaseModel):
    min_level: Optional[str] = Field(default=None, description="Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    logger_name: Optional[str] = Field(default=None, description="Sub-string filter for logger name")
    search_query: Optional[str] = Field(default=None, description="Sub-string search query across log messages")
    limit: int = Field(default=200, ge=1, le=2000, description="Max number of log entries to retrieve")


class SetLogLevelRequest(BaseModel):
    logger_name: str = Field(..., description="Logger name to modify (or 'root')")
    level_name: str = Field(..., description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")


class DebugEvalRequest(BaseModel):
    eval_type: str = Field(..., description="Type of evaluation: 'collision', 'pkpd', 'catalog', 'graph', 'snippet'")
    stack: Optional[List[Dict[str, Any]]] = Field(default=None, description="Compound stack for collision matrix eval")
    compound_key: Optional[str] = Field(default=None, description="Target compound key for PKPD eval")
    dose_mg: Optional[float] = Field(default=100.0, description="Dose in mg for PKPD eval")
    duration_h: Optional[float] = Field(default=24.0, description="Duration in hours for PKPD eval")
    query: Optional[str] = Field(default=None, description="Search query string for catalog lookup")
    cypher: Optional[str] = Field(default=None, description="Cypher query for Graph database eval")
    code: Optional[str] = Field(default=None, description="Python code snippet for sandbox eval")


class DebugEvalResponse(BaseModel):
    success: bool = True
    execution_time_ms: float
    data: Any
    error: Optional[str] = None
    traceback: Optional[str] = None
