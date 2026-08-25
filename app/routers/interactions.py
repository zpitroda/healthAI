from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.profiles import InteractionWorkbenchRequest
from app.services.catalog_service import CatalogService
from app.services.graph_service import parse_compound_spec
from app.services.interaction_engine import InteractionEngine
from app.services.pharmacology_enricher import PharmacologyEnricher

router = APIRouter(tags=["interactions"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

_GLOBAL_INTERACTION_ENGINE: Optional[InteractionEngine] = None
_GLOBAL_CATALOG_SERVICE: Optional[CatalogService] = None


def get_interaction_engine() -> InteractionEngine:
    global _GLOBAL_INTERACTION_ENGINE
    if _GLOBAL_INTERACTION_ENGINE is None:
        _GLOBAL_INTERACTION_ENGINE = InteractionEngine()
    return _GLOBAL_INTERACTION_ENGINE


def get_catalog_service() -> CatalogService:
    global _GLOBAL_CATALOG_SERVICE
    if _GLOBAL_CATALOG_SERVICE is None:
        _GLOBAL_CATALOG_SERVICE = CatalogService()
    return _GLOBAL_CATALOG_SERVICE


@router.post("/api/interactions/matrix")
def evaluate_interaction_matrix(payload: InteractionWorkbenchRequest) -> JSONResponse:
    """Evaluate pairwise N x N interaction collision matrix and cumulative risk score for a stack."""
    service = get_catalog_service()
    engine = get_interaction_engine()

    raw_compounds: List[Dict[str, Any]] = []
    for item in payload.stack:
        parsed = parse_compound_spec(item)
        key = parsed["key"]
        if not key:
            continue

        comp = service.get_compound(str(key), auto_enrich=False)
        if comp:
            comp_copy = dict(comp)
            comp_copy["key"] = str(key)
            comp_copy["dose"] = item.get("dose") if isinstance(item, dict) and item.get("dose") is not None else parsed.get("dose_val", parsed.get("dose_mg"))
            comp_copy["unit"] = item.get("unit") if isinstance(item, dict) and item.get("unit") else parsed.get("dose_unit", "mg")
            comp_copy["dose_mg"] = parsed.get("dose_mg", 10.0)
            comp_copy["dose_str"] = parsed.get("dose_str", f"{comp_copy['dose_mg']:g} mg")
            comp_copy["frequency"] = parsed.get("frequency", "daily")
            comp_copy["frequency_multiplier"] = parsed.get("frequency_multiplier", 1.0)
            comp_copy["effective_daily_dose_mg"] = parsed.get("effective_daily_dose_mg", comp_copy["dose_mg"])
            comp_copy["effective_daily_display"] = parsed.get("effective_daily_display", f"{comp_copy['dose_mg']:g} mg/day")
            comp_copy["route"] = str(item.get("route") if isinstance(item, dict) and item.get("route") else parsed.get("route", comp.get("route") or "oral")).strip().lower()
            if isinstance(item, dict):
                comp_copy["timing"] = item.get("timing", "morning")
                if item.get("frequency"):
                    comp_copy["frequency"] = item.get("frequency")
            raw_compounds.append(comp_copy)
        elif key:
            clean_key = str(key).strip().lower().replace(" ", "_")
            display_name = str(item.get("name") if isinstance(item, dict) and item.get("name") else key).replace("_", " ").title()
            enriched = PharmacologyEnricher.enrich_compound({"key": clean_key, "name": display_name})
            raw_compounds.append({
                "key": clean_key,
                "name": enriched.get("name") or display_name,
                "drug_class": enriched.get("drug_class", "custom compound"),
                "mechanism": enriched.get("mechanism", "Custom compound added in safety workbench."),
                "dose": item.get("dose") if isinstance(item, dict) and item.get("dose") is not None else parsed.get("dose_val", parsed.get("dose_mg")),
                "unit": item.get("unit") if isinstance(item, dict) and item.get("unit") else parsed.get("dose_unit", "mg"),
                "dose_mg": parsed.get("dose_mg", 10.0),
                "dose_str": parsed.get("dose_str", "10 mg"),
                "frequency": parsed.get("frequency", "daily"),
                "frequency_multiplier": parsed.get("frequency_multiplier", 1.0),
                "effective_daily_dose_mg": parsed.get("effective_daily_dose_mg", parsed.get("dose_mg", 10.0)),
                "effective_daily_display": parsed.get("effective_daily_display", "10 mg/day"),
                "route": str(item.get("route") if isinstance(item, dict) and item.get("route") else parsed.get("route", "oral")).strip().lower(),
                "timing": item.get("timing", "morning") if isinstance(item, dict) else "morning",
                "receptor_targets": enriched.get("receptor_targets", []),
                "cyp_enzymes": enriched.get("cyp_enzymes", {"substrates": [], "inhibitors": [], "inducers": []}),
                "transporters": enriched.get("transporters", {"substrates": [], "inhibitors": [], "inducers": []}),
                "phase2_enzymes": enriched.get("phase2_enzymes", {"substrates": [], "inhibitors": [], "inducers": []}),
                "organ_burdens": enriched.get("organ_burdens", {}),
                "synergies": enriched.get("synergies", []),
                "evidence_level": "moderate",
                "risk_band": "low",
            })

    profile_dict = payload.model_dump()
    result = engine.analyze_stack(raw_compounds, profile=profile_dict)
    return JSONResponse(result, headers=NO_CACHE_HEADERS)


@router.post("/api/synergy/evaluate")
def evaluate_synergy(payload: InteractionWorkbenchRequest) -> JSONResponse:
    """Evaluate multi-agent Loewe Additivity vs Bliss Independence models and polypharmacology mapping."""
    service = get_catalog_service()
    from app.services.synergy_engine import SynergyEngine

    raw_compounds: List[Dict[str, Any]] = []
    for item in payload.stack:
        parsed = parse_compound_spec(item)
        key = parsed["key"]
        if not key:
            continue

        comp = service.get_compound(str(key), auto_enrich=False)
        if comp:
            comp_copy = dict(comp)
            comp_copy["key"] = str(key)
            comp_copy["dose_mg"] = parsed.get("dose_mg", 10.0)
            raw_compounds.append(comp_copy)
        elif key:
            clean_key = str(key).strip().lower().replace(" ", "_")
            display_name = str(item.get("name") if isinstance(item, dict) and item.get("name") else key).replace("_", " ").title()
            enriched = PharmacologyEnricher.enrich_compound({"key": clean_key, "name": display_name})
            raw_compounds.append({
                "key": clean_key,
                "name": display_name,
                "dose_mg": parsed.get("dose_mg", 10.0),
                "receptor_targets": enriched.get("receptor_targets", []),
            })

    engine = SynergyEngine()
    result = engine.evaluate_multi_agent_synergy(raw_compounds)
    return JSONResponse(result, headers=NO_CACHE_HEADERS)
