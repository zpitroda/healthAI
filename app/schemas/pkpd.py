from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class QuantitativeTargetAffinity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_name: str = Field(..., description="Target protein name or symbol")
    target_chembl_id: Optional[str] = Field(default=None, description="Target ChEMBL identifier")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")
    gene_symbol: Optional[str] = Field(default=None, description="HGNC Gene Symbol")
    affinity_type: str = Field(default="IC50", description="Ki, IC50, EC50, or Kd")
    affinity_value_nm: float = Field(..., gt=0, description="Binding affinity in nanomolar (nM)")
    pchembl_value: Optional[float] = Field(default=None, description="-log10(molar activity)")
    action_type: str = Field(default="inhibitor", description="agonist, antagonist, inhibitor, PAM, NAM, blocker")
    confidence_score: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class PathwayAnnotation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pathway_id: str = Field(..., description="External pathway identifier e.g. R-HSA-112316")
    pathway_name: str = Field(..., description="Human-readable pathway title")
    database: str = Field(default="Reactome", description="Reactome, KEGG, or GO")
    category: Optional[str] = Field(default=None)


class PKParameters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    t_half_h: float = Field(..., gt=0, description="Elimination half-life in hours")
    bioavailability_f: float = Field(default=1.0, ge=0.0, le=1.0, description="Oral bioavailability fraction (0.0 - 1.0)")
    volume_of_distribution_l_kg: float = Field(..., gt=0, description="Apparent Vd in L/kg body weight")
    clearance_l_h_kg: Optional[float] = Field(default=None, gt=0, description="Total systemic clearance in L/h/kg")
    t_max_h: float = Field(default=2.0, gt=0, description="Time to maximum peak concentration in hours")
    c_max_reference_ng_ml: Optional[float] = Field(default=None, description="Reference Cmax at standard therapeutic dose (ng/mL)")
    fraction_unbound: float = Field(default=0.05, ge=0.0, le=1.0, description="Fraction of drug unbound in plasma fu (0.0 - 1.0)")
    protein_binding_pct: float = Field(default=95.0, ge=0.0, le=100.0, description="Plasma protein binding percentage")
    absorption_rate_ka: float = Field(default=1.0, gt=0, description="Absorption rate constant ka in 1/hours")
    renal_clearance_fraction: float = Field(default=0.2, ge=0.0, le=1.0, description="Fraction excreted unchanged via renal pathway fe")
    bcs_class: Optional[str] = Field(default="Class I", description="Biopharmaceutics Classification (Class I, II, III, IV)")
    pka: Optional[float] = Field(default=None, description="Acid/base ionization dissociation constant")

    # 2-Compartment Open Model Parameters
    number_of_compartments: int = Field(default=1, description="1-compartment or 2-compartment open model")
    v1_l_kg: Optional[float] = Field(default=None, description="Central compartment volume of distribution V1 (L/kg)")
    v2_l_kg: Optional[float] = Field(default=None, description="Peripheral compartment volume of distribution V2 (L/kg)")
    k12: Optional[float] = Field(default=None, description="Rate constant central -> peripheral (1/h)")
    k21: Optional[float] = Field(default=None, description="Rate constant peripheral -> central (1/h)")

    # Michaelis-Menten Non-Linear Elimination Kinetics
    is_saturable_elimination: bool = Field(default=False, description="Whether clearance exhibits Michaelis-Menten capacity-limited saturation")
    vmax_mg_h_kg: Optional[float] = Field(default=None, description="Maximum elimination rate Vmax (mg/h/kg)")
    km_ng_ml: Optional[float] = Field(default=None, description="Michaelis constant Km (ng/mL)")
    ki_ng_ml: Optional[float] = Field(default=None, description="Enzyme inhibition constant Ki (ng/mL)")


class PDParameters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mec_ng_ml: Optional[float] = Field(default=None, gt=0, description="Minimal Effective Concentration (MEC) in ng/mL")
    mtc_ng_ml: Optional[float] = Field(default=None, gt=0, description="Maximum Tolerated Concentration (MTC) in ng/mL")
    therapeutic_index: Optional[float] = Field(default=None, gt=0, description="Therapeutic Index (MTC / MEC)")
    e_max: float = Field(default=100.0, description="Maximal biological response efficacy percentage")
    ec50_nm: Optional[float] = Field(default=None, gt=0, description="Half-maximal effective concentration in nM")
    ic50_nm: Optional[float] = Field(default=None, gt=0, description="Half-maximal inhibitory concentration in nM")
    hill_coefficient: float = Field(default=1.0, gt=0, description="Sigmoidal Hill slope factor gamma")
    target_affinities: List[QuantitativeTargetAffinity] = Field(default_factory=list)
    pathways: List[PathwayAnnotation] = Field(default_factory=list)


class MetaboliteProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Metabolite name or identifier")
    chembl_id: Optional[str] = Field(default=None, description="ChEMBL molecule ID if available")
    inchikey: Optional[str] = Field(default=None, description="InChIKey identifier")
    smiles: Optional[str] = Field(default=None, description="SMILES structure")
    conversion_enzyme: Optional[str] = Field(default=None, description="Metabolizing enzyme (e.g. CYP3A4, UGT1A1, Esterase)")
    is_active: bool = Field(default=False, description="Whether the metabolite possesses pharmacological activity")
    activity_type: Optional[str] = Field(default=None, description="Active, inactive, toxic, or prodrug activation")
    relative_exposure_pct: float = Field(default=10.0, ge=0.0, description="Estimated relative systemic AUC exposure percentage compared to parent")


class RoutePKParameters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    route_name: str = Field(..., description="Administration route (oral, sublingual, subcutaneous, intramuscular, transdermal, intravenous, inhalation, intranasal, rectal)")
    bioavailability_f: float = Field(default=1.0, ge=0.0, le=1.0, description="Route-specific fraction absorbed into systemic circulation F")
    absorption_rate_ka: float = Field(default=1.0, gt=0.0, description="Route-specific absorption rate constant ka (1/h)")
    t_max_h: float = Field(default=2.0, gt=0.0, description="Time to maximum peak plasma concentration Tmax in hours")
    apparent_t_half_h: Optional[float] = Field(default=None, description="Apparent elimination half-life for depot/sustained delivery (flip-flop kinetics)")
    first_pass_hepatic_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage of absorbed drug cleared via first-pass hepatic extraction")
    first_pass_bypass_pct: float = Field(default=100.0, ge=0.0, le=100.0, description="Percentage bypassing first-pass portal transit")
    metabolites: List[MetaboliteProfile] = Field(default_factory=list, description="Metabolites formed post-administration")


class PKPDSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    compound_key: str = Field(..., description="Compound identifier in catalog")
    dose_mg: float = Field(default=100.0, gt=0, description="Administered single dose in milligrams")
    dosing_interval_h: float = Field(default=24.0, gt=0, description="Dosing interval tau in hours (e.g. 8, 12, 24, 168)")
    simulation_duration_h: float = Field(default=48.0, gt=0, le=336.0, description="Simulation time span in hours")
    route: str = Field(default="oral", description="Administration route: oral, sublingual, subcutaneous, intramuscular, transdermal, intravenous, inhalation, intranasal, rectal")
    sex: Optional[str] = Field(default=None, description="Patient sex ('male' or 'female')")
    age: Optional[int] = Field(default=None, ge=1, le=120, description="Patient age in years")
    weight_kg: Optional[float] = Field(default=None, gt=0, description="Patient body weight in kg")
    height_cm: Optional[float] = Field(default=None, gt=0, description="Patient height in cm")
    body_fat_pct: Optional[float] = Field(default=None, ge=1.0, le=80.0, description="Patient body fat percentage")
    steady_state: bool = Field(default=True, description="Whether to simulate steady-state multiple dosing vs single dose")
    co_administered_compounds: List[str] = Field(default_factory=list, description="Other active compound keys in stack to model DDI PK shifts")
    egfr_ml_min: Optional[float] = Field(default=None, description="Patient eGFR for renal clearance scaling (auto-calculated from age/sex/weight/creatinine if None)")
    alt_u_l: Optional[float] = Field(default=25.0, description="Patient ALT for hepatic clearance scaling")
    serum_albumin_g_dl: Optional[float] = Field(default=4.5, description="Patient serum albumin for protein binding scaling")


class DistributionPercentiles(BaseModel):
    p5: float = Field(..., description="5th percentile value")
    p25: float = Field(..., description="25th percentile value")
    p50: float = Field(..., description="50th percentile (median) value")
    p75: float = Field(..., description="75th percentile value")
    p95: float = Field(..., description="95th percentile value")


class TimePoint(BaseModel):
    time_h: float
    c_plasma_ng_ml: float
    c_free_ng_ml: float
    receptor_occupancy_pct: float
    effect_pct: float
    c_metabolite_ng_ml: Optional[float] = Field(default=None, description="Primary active/major metabolite plasma concentration (ng/mL)")
    c_tissue_ng_ml: Optional[float] = Field(default=None, description="Peripheral compartment concentration for 2-compartment open models")
    cl_instantaneous_l_h: Optional[float] = Field(default=None, description="Instantaneous dynamic clearance at time t (L/h)")
    inhibitor_conc_ng_ml: Optional[float] = Field(default=None, description="Continuous inhibitor concentration I(t) modulating clearance")
    # Distribution curve percentiles for concentration at time t
    c_plasma_distribution: Optional[DistributionPercentiles] = Field(default=None, description="Population probability distribution percentiles for C(t)")
    effect_distribution: Optional[DistributionPercentiles] = Field(default=None, description="Population probability distribution percentiles for Effect E(t)")


class MetricDistribution(BaseModel):
    mean: float
    std_dev: float
    percentiles: DistributionPercentiles


class PKPDSimulationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    compound_key: str
    compound_name: str
    dose_mg: float
    dosing_interval_h: float
    route: str
    steady_state: bool

    # Patient Biometric Context Used
    patient_biometrics: Dict[str, Any] = Field(default_factory=dict, description="Resolved biometric scaling inputs (sex, age, weight, height, BMI, LBM, TBW)")

    # Route PK & First-Pass Characteristics
    route_pk_details: Optional[RoutePKParameters] = Field(default=None, description="Route-specific biopharmaceutical absorption parameters")
    first_pass_metabolism_pct: float = Field(default=0.0, description="First-pass hepatic extraction percentage")
    first_pass_bypass_pct: float = Field(default=100.0, description="Portal bypass percentage")
    metabolites: List[MetaboliteProfile] = Field(default_factory=list, description="Primary active and major metabolites")

    # Dynamic PK Metrics (Median / Central Estimate)
    c_max_ng_ml: float
    t_max_h: float
    c_min_trough_ng_ml: float
    c_avg_ss_ng_ml: float
    auc_0_tau_ng_h_ml: float
    accumulation_ratio: float
    fluctuation_pct: float
    elimination_half_life_effective_h: float
    total_clearance_l_h: float

    # Population Inter-Individual Variability Distribution Curves
    c_max_distribution: MetricDistribution = Field(..., description="Population distribution curve for Cmax")
    c_avg_distribution: MetricDistribution = Field(..., description="Population distribution curve for Cavg")
    auc_distribution: MetricDistribution = Field(..., description="Population distribution curve for AUC0-tau")
    clearance_distribution: MetricDistribution = Field(..., description="Population distribution curve for total clearance")
    half_life_distribution: MetricDistribution = Field(..., description="Population distribution curve for elimination half-life")

    # Model & DDI Classifications
    number_of_compartments: int = Field(default=1, description="1 or 2 compartment model used")
    is_saturable_elimination: bool = Field(default=False, description="Whether non-linear Michaelis-Menten kinetics applied")
    dynamic_ddi_active: bool = Field(default=False, description="Whether continuous time-resolved DDI clearance modulation was active")

    # DDI & Safety Metrics
    ddi_auc_ratio: float
    ddi_cmax_multiplier: float
    ddi_interacting_enzymes: List[str]
    mec_ng_ml: Optional[float]
    mtc_ng_ml: Optional[float]
    therapeutic_index: Optional[float]
    time_in_therapeutic_window_pct: float
    time_in_toxic_zone_pct: float
    time_subtherapeutic_pct: float

    # Curve Points
    time_series: List[TimePoint]

    # Pharmacodynamic Hill Curve Points for Visualization
    pd_curve_concentrations: List[float]
    pd_curve_effects: List[float]
