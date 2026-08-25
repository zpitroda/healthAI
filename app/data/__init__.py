"""
HealthAI Data Module
--------------------
Handles compound library definitions, database initialization, and catalog storage.
All compounds and biological pathways are dynamically ingested and stored in SQLite.
"""
from __future__ import annotations

from typing import Any, Dict

# Dynamic library dictionary for in-memory caching and backward compatibility
COMPOUND_LIBRARY: Dict[str, Any] = {}

__all__ = ["COMPOUND_LIBRARY"]
