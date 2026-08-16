from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class LabProfile(BaseModel):
    """Comprehensive clinical biomarker laboratory profile for safety, contraindication & cascade modelling."""
    # Hepatic Panel
    alt_u_l: Optional[float] = None
    ast_u_l: Optional[float] = None
    total_bilirubin_mg_dl: Optional[float] = None
    serum_albumin_g_dl: Optional[float] = None

    # Renal Panel
    egfr: Optional[float] = None
    creatinine_mg_dl: Optional[float] = None
    bun_mg_dl: Optional[float] = None

    # Cardiovascular & Vitals
    blood_pressure: Optional[float] = None
    heart_rate: Optional[float] = None
    qtc_ms: Optional[float] = None

    # Hematology & Electrolytes
    potassium_meq_l: Optional[float] = None
    sodium_meq_l: Optional[float] = None
    magnesium_mg_dl: Optional[float] = None
    hematocrit_pct: Optional[float] = None
    platelets_k_ul: Optional[float] = None

    # Metabolic & Lipids
    fasting_glucose_mg_dl: Optional[float] = None
    hba1c_pct: Optional[float] = None
    ldl_mg_dl: Optional[float] = None
    hdl_mg_dl: Optional[float] = None
    triglycerides_mg_dl: Optional[float] = None
    apob_mg_dl: Optional[float] = None

    # Endocrine & Recovery
    testosterone_ng_dl: Optional[float] = None
    free_testosterone_pg_ml: Optional[float] = None
    estradiol_pg_ml: Optional[float] = None
    cortisol_ug_dl: Optional[float] = None
    tsh_miu_l: Optional[float] = None
    sleep_hours: Optional[float] = None


class UserProfile(BaseModel):
    """User profile containing biometric inputs, goals, active compound stack, and clinical bloodwork."""
    stack: List[Any] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    experience: str = "intermediate"
    sex: str = "male"
    age: int = 30
    weight_kg: float = 70.0
    height_cm: float = 175.0
    sleep_hours: float = 7.0
    body_fat_pct: Optional[float] = None
    blood_pressure: Optional[float] = None
    labs: LabProfile = Field(default_factory=LabProfile)


class InteractionWorkbenchRequest(BaseModel):
    """Payload for evaluating multi-compound pharmacodynamic/pharmacokinetic collision matrix & cascades."""
    stack: List[Any] = Field(default_factory=list)
    labs: LabProfile = Field(default_factory=LabProfile)
    sleep_hours: float = 7.5
    blood_pressure: float = 120.0
    weight_kg: float = 75.0
