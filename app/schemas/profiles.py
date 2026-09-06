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
    hrv_rmssd_ms: Optional[float] = None

    # Hematology & Electrolytes
    potassium_meq_l: Optional[float] = None
    sodium_meq_l: Optional[float] = None
    magnesium_mg_dl: Optional[float] = None
    hematocrit_pct: Optional[float] = None
    platelets_k_ul: Optional[float] = None

    # Metabolic & Lipids
    fasting_glucose_mg_dl: Optional[float] = None
    fasting_insulin_u_iu_ml: Optional[float] = None
    homa_ir: Optional[float] = None
    metabolic_rate_kcal: Optional[float] = None
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
    free_t3_pg_ml: Optional[float] = None
    free_t4_ng_dl: Optional[float] = None
    shbg_nmol_l: Optional[float] = None
    igf1_ng_ml: Optional[float] = None
    sleep_hours: Optional[float] = None

    # Neurotrophic, Longevity & Inflammation
    bdnf_ng_ml: Optional[float] = None
    ngf_pg_ml: Optional[float] = None
    nad_plus_umol_l: Optional[float] = None
    hs_crp_mg_l: Optional[float] = None

    # Pharmacogenomics (PGx)
    cyp2d6_phenotype: Optional[str] = None
    cyp2c19_phenotype: Optional[str] = None
    cyp3a4_phenotype: Optional[str] = None
    slco1b1_genotype: Optional[str] = None
    comt_phenotype: Optional[str] = None


class UserProfile(BaseModel):
    """User profile containing biometric inputs, goals, active compound stack, and clinical bloodwork."""
    stack: List[Any] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    experience: str = "intermediate"
    sex: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    sleep_hours: Optional[float] = 7.0
    body_fat_pct: Optional[float] = None
    blood_pressure: Optional[float] = None
    hrv_rmssd_ms: Optional[float] = None
    metabolic_rate_kcal: Optional[float] = None
    labs: LabProfile = Field(default_factory=LabProfile)


class InteractionWorkbenchRequest(BaseModel):
    """Payload for evaluating multi-compound pharmacodynamic/pharmacokinetic collision matrix & cascades."""
    stack: List[Any] = Field(default_factory=list)
    labs: LabProfile = Field(default_factory=LabProfile)
    sleep_hours: Optional[float] = 7.5
    blood_pressure: Optional[float] = 120.0
    hrv_rmssd_ms: Optional[float] = None
    metabolic_rate_kcal: Optional[float] = None
    sex: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    body_fat_pct: Optional[float] = None
    timeline: Optional[str] = "steady_state"
    timeline_days: Optional[float] = None


class BMRCalculationRequest(BaseModel):
    weight_kg: float = Field(..., description="Body weight in kilograms", ge=20.0, le=350.0)
    height_cm: float = Field(..., description="Stature in centimeters", ge=100.0, le=250.0)
    age: int = Field(..., description="Age in years", ge=1, le=120)
    sex: str = Field(..., description="Biological sex ('male' or 'female')")
    body_fat_pct: Optional[float] = Field(None, description="Optional body fat percentage for Katch-McArdle lean mass calculation", ge=2.0, le=65.0)


class FreeTestosteroneCalculationRequest(BaseModel):
    total_t_ng_dl: float = Field(..., description="Serum total testosterone in ng/dL", ge=0.1, le=10000.0)
    shbg_nmol_l: float = Field(..., description="Serum SHBG in nmol/L", ge=1.0, le=300.0)
    albumin_g_dl: Optional[float] = Field(4.3, description="Serum albumin in g/dL (reference default: 4.3)", ge=1.0, le=6.5)

