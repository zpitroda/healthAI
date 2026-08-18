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


class PKPDSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    compound_key: str = Field(..., description="Compound identifier in catalog")
    dose_mg: float = Field(default=100.0, gt=0, description="Administered single dose in milligrams")
    dosing_interval_h: float = Field(default=24.0, gt=0, description="Dosing interval tau in hours (e.g. 8, 12, 24)")
    simulation_duration_h: float = Field(default=48.0, gt=0, le=168.0, description="Simulation time span in hours")
    route: str = Field(default="oral", description="oral or iv")
    weight_kg: float = Field(default=70.0, gt=0, description="Patient body weight in kg")
    steady_state: bool = Field(default=True, description="Whether to simulate steady-state multiple dosing vs single dose")
    co_administered_compounds: List[str] = Field(default_factory=list, description="Other active compound keys in stack to model DDI PK shifts")
    egfr_ml_min: Optional[float] = Field(default=95.0, description="Patient eGFR for renal clearance scaling")
    alt_u_l: Optional[float] = Field(default=25.0, description="Patient ALT for hepatic clearance scaling")
    serum_albumin_g_dl: Optional[float] = Field(default=4.5, description="Patient serum albumin for protein binding scaling")


class TimePoint(BaseModel):
    time_h: float
    c_plasma_ng_ml: float
    c_free_ng_ml: float
    receptor_occupancy_pct: float
    effect_pct: float


class OpenTargetsData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    approved_symbol: str = Field(..., description="HGNC Approved Symbol")
    approved_name: str = Field(..., description="Approved Protein Title")
    uniprot_id: Optional[str] = Field(default=None)
    tractability: List[Dict[str, Any]] = Field(default_factory=list, description="Modality tractability assessments (Small Molecule, Antibody)")
    associated_diseases: List[Dict[str, Any]] = Field(default_factory=list, description="Associated diseases and genetic evidence scores")
    target_disease_summary: Optional[str] = Field(default=None)


class FAERSSurveillanceData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    drug_name: str = Field(..., description="Medicinal Product Name")
    total_reports: int = Field(default=0, description="Total post-marketing FAERS report count")
    top_adverse_events: List[Dict[str, Any]] = Field(default_factory=list, description="Top MedDRA adverse reactions with reporting ratios")
    disproportionality_signals: List[Dict[str, Any]] = Field(default_factory=list, description="Disproportionality signals (PRR > 2.0)")
    surveillance_summary: Optional[str] = Field(default=None)


class AlphaFoldStructureData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uniprot_id: str = Field(..., description="UniProt Accession ID")
    gene_symbol: Optional[str] = Field(default=None)
    alphafold_id: str = Field(..., description="AlphaFold Model ID e.g. AF-P00533-F1")
    mean_plddt: float = Field(default=90.0, description="Mean pLDDT structure confidence score")
    structure_url: Optional[str] = Field(default=None, description="PDB structure download URL")
    pdb_ids: List[str] = Field(default_factory=list, description="RCSB PDB entry identifiers")
    binding_site_residues: List[str] = Field(default_factory=list, description="Key active site residue positions")
    mutation_impacts: List[Dict[str, Any]] = Field(default_factory=list, description="Binding site residue mutations impacting drug affinity")
    structure_summary: Optional[str] = Field(default=None)


class SynergyEvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stack_domain: str = Field(default="general", description="oncology, antimicrobial, longevity, or general")
    overall_synergistic: bool = Field(default=False)
    synergy_score_index: float = Field(default=1.0)
    loewe_model: Dict[str, Any] = Field(default_factory=dict, description="Loewe Additivity Combination Index (CI)")
    bliss_model: Dict[str, Any] = Field(default_factory=dict, description="Bliss Independence expected vs observed effect and Bliss Delta")
    pairwise_synergy_matrix: List[Dict[str, Any]] = Field(default_factory=list)
    polypharmacology_shared_targets: Dict[str, Any] = Field(default_factory=dict)
    shared_target_count: int = Field(default=0)
    domain_notes: Optional[str] = Field(default=None)


class PKPDSimulationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    compound_key: str
    compound_name: str
    dose_mg: float
    dosing_interval_h: float
    route: str
    steady_state: bool

    # Dynamic PK Metrics
    c_max_ng_ml: float
    t_max_h: float
    c_min_trough_ng_ml: float
    c_avg_ss_ng_ml: float
    auc_0_tau_ng_h_ml: float
    accumulation_ratio: float
    fluctuation_pct: float
    elimination_half_life_effective_h: float
    total_clearance_l_h: float

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
