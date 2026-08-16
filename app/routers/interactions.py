from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.profiles import InteractionWorkbenchRequest
from app.services.catalog_service import CatalogService
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
        if isinstance(item, dict):
            key = item.get("key") or item.get("compound") or item.get("name")
        else:
            key = str(item)

        comp = service.get_compound(str(key))
        if comp:
            raw_compounds.append(comp)
        elif key:
            raw_compounds.append({
                "key": str(key).strip().lower().replace(" ", "_"),
                "name": str(key).strip().title(),
                "drug_class": "custom compound",
                "mechanism": "Custom compound added in safety workbench.",
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
