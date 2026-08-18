from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.profiles import InteractionWorkbenchRequest
from app.services.catalog_service import CatalogService
from app.services.graph_service import parse_compound_spec
from app.services.interaction_engine import InteractionEngine

router = APIRouter(tags=["interactions"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.post("/api/interactions/matrix")
def evaluate_interaction_matrix(payload: InteractionWorkbenchRequest) -> JSONResponse:
    """Evaluate pairwise N x N interaction collision matrix and cumulative risk score for a stack."""
    service = CatalogService()
    engine = InteractionEngine()

    raw_compounds: List[Dict[str, Any]] = []
    for item in payload.stack:
        parsed = parse_compound_spec(item)
        key = parsed["key"]
        if not key:
            continue

        comp = service.get_compound(str(key))
        if comp:
            comp_copy = dict(comp)
            comp_copy["key"] = str(key)
            comp_copy["dose"] = item.get("dose") if isinstance(item, dict) and item.get("dose") is not None else parsed.get("dose_mg")
            comp_copy["unit"] = item.get("unit") if isinstance(item, dict) and item.get("unit") else "mg"
            comp_copy["dose_mg"] = parsed.get("dose_mg", 10.0)
            comp_copy["dose_str"] = parsed.get("dose_str", f"{comp_copy['dose_mg']:g} mg")
            if isinstance(item, dict):
                comp_copy["timing"] = item.get("timing", "morning")
                comp_copy["frequency"] = item.get("frequency", "daily")
            raw_compounds.append(comp_copy)
        elif key:
            raw_compounds.append({
                "key": str(key).strip().lower().replace(" ", "_"),
                "name": str(key).strip().title(),
                "drug_class": "custom compound",
                "mechanism": "Custom compound added in safety workbench.",
                "dose": item.get("dose") if isinstance(item, dict) and item.get("dose") is not None else parsed.get("dose_mg"),
                "unit": item.get("unit") if isinstance(item, dict) and item.get("unit") else "mg",
                "dose_mg": parsed.get("dose_mg", 10.0),
                "dose_str": parsed.get("dose_str", "10 mg"),
                "timing": item.get("timing", "morning") if isinstance(item, dict) else "morning",
                "frequency": item.get("frequency", "daily") if isinstance(item, dict) else "daily",
                "receptor_targets": [],
                "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
                "organ_burdens": {},
                "synergies": [],
                "evidence_level": "preliminary",
                "risk_band": "low",
            })

    profile_dict = payload.model_dump()
    result = engine.analyze_stack(raw_compounds, profile=profile_dict)
    return JSONResponse(result, headers=NO_CACHE_HEADERS)

