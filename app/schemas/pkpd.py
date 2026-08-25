from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class EvidenceTier(str, Enum):
    REGULATORY_HUMAN_CLINICAL = "regulatory_human_clinical"
    EXPLORATORY_HUMAN_PILOT = "exploratory_human_pilot"
    ANIMAL_IN_VIVO = "animal_in_vivo"
    IN_VITRO_ASSAY = "in_vitro_assay"
    IN_SILICO_QSAR = "in_silico_qsar"
    COMMUNITY_REPORTED = "community_reported"
    IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION = "in_vitro_and_allometric_extrapolation"


class CompoundDataLimitations(BaseModel):
    model_config = ConfigDict(extra="ignore")

    has_human_trials: bool = Field(default=False, description="Whether compound has completed FDA/EMA human clinical trials")
    has_human_pk: bool = Field(default=False, description="Whether human pharmacokinetic parameters (Tmax, Cmax, Vd, Cl) are clinically validated")
    has_chronic_toxicity_studies: bool = Field(default=False, description="Whether long-term human or GLP toxicology data exists")
    has_cyp_metabolite_mapping: bool = Field(default=False, description="Whether hepatic/renal metabolic degradation pathways are fully mapped")
    known_limitations: List[str] = Field(default_factory=list, description="Explicit disclosures detailing data gaps and uncharacterized safety bounds")


class AllometricExtrapolation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    animal_species: str = Field(default="rat", description="Preclinical model species (mouse, rat, guinea_pig, dog, monkey)")
    animal_dose_mg_kg: float = Field(..., description="Experimental preclinical animal dose in mg/kg")
    km_animal: float = Field(default=6.0, description="Species-specific Body Surface Area normalization factor Km")
    km_human: float = Field(default=37.0, description="Standard human Body Surface Area normalization factor Km (37)")
    hed_mg_kg: float = Field(..., description="Calculated raw Human Equivalent Dose in mg/kg (no arbitrary buffer)")
    human_weight_kg: float = Field(default=70.0, description="Human subject body weight in kg")
    total_human_dose_mg: float = Field(..., description="Calculated total human dose in mg for specified body weight")
    calculation_method: str = Field(default="FDA Reagan-Shaw Body Surface Area Allometric Scaling", description="Mathematical formula specification")
    is_human_validated: bool = Field(default=False, description="Flag denoting whether this dose is validated in human clinical trials")


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
    circadian_dosing_time_h: Optional[float] = Field(default=8.0, ge=0.0, le=24.0, description="Hour of day for administration (0-24, default 8.0 = 8 AM)")
    enable_pbpk_tissues: bool = Field(default=True, description="Enable Rodgers-Rowland whole-body PBPK tissue partitioning")
    enable_receptor_tolerance: bool = Field(default=True, description="Enable dynamic receptor desensitization and internalization ODE")
    cyp2d6_phenotype: Optional[str] = Field(default=None, description="Patient CYP2D6 metabolizer phenotype (e.g. poor_metabolizer, ultrarapid_metabolizer)")
    cyp2c19_phenotype: Optional[str] = Field(default=None, description="Patient CYP2C19 metabolizer phenotype")
    cyp3a4_phenotype: Optional[str] = Field(default=None, description="Patient CYP3A4 activity status")
    slco1b1_genotype: Optional[str] = Field(default=None, description="Patient SLCO1B1 genotype (e.g. *1/*5, *5/*5)")
    comt_phenotype: Optional[str] = Field(default=None, description="Patient COMT Val158Met phenotype (val_val, met_met)")


class TissuePartitionCoefficients(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kp_brain: float = Field(default=1.0, description="Brain-to-plasma partition coefficient Kp,brain (adjusted for BBB permeability & efflux)")
    kp_liver: float = Field(default=1.0, description="Liver-to-plasma partition coefficient Kp,liver")
    kp_kidney: float = Field(default=1.0, description="Kidney-to-plasma partition coefficient Kp,kidney")
    kp_muscle: float = Field(default=1.0, description="Muscle/lean tissue partition coefficient Kp,muscle")
    kp_adipose: float = Field(default=1.0, description="Adipose/fat tissue partition coefficient Kp,adipose")
    method: str = Field(default="Rodgers-Rowland / Poulin-Theil Biophysical Equation")


class LysosomalTrappingInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pka: Optional[float] = Field(default=None, description="Compound basic pKa")
    is_lysosomotropic: bool = Field(default=False, description="Whether compound exhibits significant lysosomal ion-trapping")
    lysosomal_accumulation_ratio: float = Field(default=1.0, description="Lysosome-to-cytosol accumulation ratio R_lyso via Henderson-Hasselbalch")
    cytosolic_free_fraction_pct: float = Field(default=100.0, description="Percentage of intracellular drug residing freely in cytosol for target engagement")


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
    # PBPK Tissue Concentrations (ng/mL or ng/g)
    c_brain_ng_ml: Optional[float] = Field(default=None, description="Brain interstitial/tissue concentration (ng/mL)")
    c_liver_ng_ml: Optional[float] = Field(default=None, description="Liver hepatocyte tissue concentration (ng/mL)")
    c_kidney_ng_ml: Optional[float] = Field(default=None, description="Kidney tissue concentration (ng/mL)")
    c_muscle_ng_ml: Optional[float] = Field(default=None, description="Muscle lean tissue concentration (ng/mL)")
    c_adipose_ng_ml: Optional[float] = Field(default=None, description="Adipose fat tissue concentration (ng/mL)")
    # Biophysical State Variables
    active_enzyme_fraction_pct: Optional[float] = Field(default=None, description="Relative functional enzyme activity E(t)/E0 (%)")
    surface_receptor_density_pct: Optional[float] = Field(default=None, description="Relative surface receptor density R_surf(t)/R0 (%) reflecting tolerance")
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

    # PBPK Tissue Partitioning & Lysosomal Trapping
    tissue_partition_coefficients: Optional[TissuePartitionCoefficients] = Field(default=None, description="Rodgers-Rowland PBPK tissue partition coefficients Kp")
    lysosomal_trapping: Optional[LysosomalTrappingInfo] = Field(default=None, description="Henderson-Hasselbalch lysosomal ion-trapping profile")
    tachyphylaxis_tolerance_active: bool = Field(default=False, description="Whether receptor desensitization and tolerance ODE was simulated")
    circadian_rhythm_active: bool = Field(default=False, description="Whether diurnal circadian clearance oscillation was simulated")

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

    # Evidence Tier & Preclinical Data Disclosures
    evidence_tier: Optional[str] = Field(default="regulatory_human_clinical", description="Empirical evidence tier (clinical, pilot, animal, in vitro, allometric)")
    human_data_present: bool = Field(default=True, description="Whether human clinical trial data exists")
    data_limitations: Optional[CompoundDataLimitations] = Field(default=None, description="Explicit disclosures of uncharacterized parameters and data gaps")
    allometric_extrapolation: Optional[AllometricExtrapolation] = Field(default=None, description="Preclinical-to-human allometric scaling parameters if extrapolated")
