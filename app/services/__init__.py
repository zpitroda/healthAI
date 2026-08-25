"""
HealthAI Services Package
-------------------------
Exposes core computational pharmacology, biophysical PK/PD, biological knowledge graph,
and clinical AI reasoning services.
"""
from __future__ import annotations

from .catalog_service import CatalogService
from .copilot_agent import CopilotAgent
from .dosing_service import get_default_compound_dose, parse_dose_string_or_spec
from .graph_service import build_selected_compound_graph, filter_graph_by_stack
from .ingestion_queue import get_ingestion_queue
from .interaction_engine import InteractionEngine
from .live_enrichment import LiveEnrichmentService
from .pathway_service import PathwayService
from .pharmacology_enricher import PharmacologyEnricher
from .pkpd_engine import PKPDEngine
from .pkpd_enricher import PKPDEnricher
from .protocol_agent import optimize_protocol
from .protocol_builder import calculate_protocol
from .redox_enricher import RedoxEnricher
from .stack_intent_engine import StackIntentEngine
from .synergy_engine import SynergyEngine

__all__ = [
    "CatalogService",
    "CopilotAgent",
    "get_default_compound_dose",
    "parse_dose_string_or_spec",
    "build_selected_compound_graph",
    "filter_graph_by_stack",
    "get_ingestion_queue",
    "InteractionEngine",
    "LiveEnrichmentService",
    "PathwayService",
    "PharmacologyEnricher",
    "PKPDEngine",
    "PKPDEnricher",
    "optimize_protocol",
    "calculate_protocol",
    "RedoxEnricher",
    "StackIntentEngine",
    "SynergyEngine",
]
