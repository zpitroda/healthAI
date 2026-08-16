from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from app.schemas.profiles import UserProfile
from app.services.protocol_builder import calculate_protocol

router = APIRouter(tags=["protocols"])


@router.post("/protocol")
def build_protocol(profile: UserProfile) -> Dict[str, Any]:
    """Calculate individualized compound, supplement, and ancillary recommendations based on user biometrics and goals."""
    payload = profile.model_dump()
    return calculate_protocol(payload)
