from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class BaseNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    node_id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Human-readable node label")
    node_type: str = Field(..., description="Bio-ontology node class")
    category: Optional[str] = Field(default=None, description="Domain sub-category")
    description: Optional[str] = Field(default=None, description="Detailed biological summary")


class MixtureNode(BaseNode):
    node_type: str = "mixture"
    standardization_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Standardized active content percentage of the botanical or mixture",
    )


class CompoundNode(BaseNode):
    node_type: str = "compound"
    smiles: Optional[str] = Field(default=None, description="Canonical SMILES structure")
    inchikey: Optional[str] = Field(default=None, description="InChIKey standard hash")
    logP: Optional[float] = Field(default=None, description="Octanol-water partition coefficient")
    tpsa: Optional[float] = Field(default=None, description="Topological polar surface area in Å²")
    molecular_weight: Optional[float] = Field(default=None, gt=0, description="Molecular weight in g/mol")
    base_half_life: Optional[float] = Field(default=None, gt=0, description="Baseline half-life in hours")
    bioavailability_pct: Optional[float] = Field(default=None, ge=0, le=100, description="Oral bioavailability percentage")
    volume_of_distribution: Optional[float] = Field(default=None, description="Apparent Vd in L/kg")
    protein_binding_pct: Optional[float] = Field(default=None, ge=0, le=100, description="Plasma protein binding percentage")
    drug_class: Optional[str] = Field(default=None, description="Therapeutic drug class")
    is_narrow_therapeutic_index: bool = Field(default=False, description="Narrow therapeutic index flag")


class EnzymeNode(BaseNode):
    node_type: str = "enzyme"
    enzyme_family: Optional[str] = Field(default=None, description="e.g. CYP450, UGT, Kinase, Esterase")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")


class ReceptorNode(BaseNode):
    node_type: str = "receptor"
    receptor_family: Optional[str] = Field(default=None, description="e.g. GPCR, Nuclear Receptor, Ligand-Gated Ion Channel")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")


class TransporterNode(BaseNode):
    node_type: str = "transporter"
    transporter_family: Optional[str] = Field(default=None, description="e.g. ABC, SLC, Efflux, Uptake")
    direction: Optional[str] = Field(default="efflux", description="efflux or influx/uptake")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")


class IonChannelNode(BaseNode):
    node_type: str = "ion_channel"
    channel_type: Optional[str] = Field(default=None, description="e.g. Voltage-gated, Potassium (hERG), Calcium L-type, Sodium")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")


class CarrierProteinNode(BaseNode):
    node_type: str = "carrier_protein"
    protein_type: Optional[str] = Field(default="plasma_protein", description="e.g. Albumin, Alpha-1-acid glycoprotein, SHBG")


class ReactionNode(BaseNode):
    node_type: str = "reaction"
    reaction_type: Optional[str] = Field(default=None, description="e.g. Phase I Oxidation, Phase II Glucuronidation, Cleavage, Reduction")


class SignalingPathwayNode(BaseNode):
    node_type: str = "signaling_pathway"
    pathway_database: Optional[str] = Field(default="Reactome", description="e.g. Reactome, KEGG, GO")
    pathway_id: Optional[str] = Field(default=None, description="External pathway identifier")


class PhysiologyNode(BaseNode):
    node_type: str = "physiology"
    organ_system: Optional[str] = Field(default=None, description="e.g. Hepatic, Renal, Cardiovascular, CNS, Endocrine, Autonomic")
    physiological_function: Optional[str] = Field(default=None, description="e.g. Vascular Tone, Glomerular Filtration, Bile Acid Clearance")


class BiomarkerNode(BaseNode):
    node_type: str = "biomarker"
    safe_lower_bound: float = Field(default=0.0, description="Lower bound of clinically normal range")
    safe_upper_bound: float = Field(default=100.0, description="Upper bound of clinically normal range")
    unit: str = Field(default="standard", description="Unit of measurement for the biomarker")
    biomarker_panel: Optional[str] = Field(default=None, description="e.g. Hepatic Panel, Renal Panel, Lipid Panel, Vitals, CBC")
    onset_days: float = Field(default=1.0, description="Onset latency in days before observable biomarker shift")
    half_time_days: float = Field(default=3.0, description="Turnover half-life in days to reach 50% response")
    time_to_steady_state_weeks: float = Field(default=1.0, description="Time in weeks to reach steady-state equilibrium (~95%)")
    kinetic_profile: str = Field(default="direct_receptor", description="rapid_autonomic, renal_electrolyte, direct_endocrine, metabolic_glycemic, hepatic_injury, hepatic_lipid_remodeling, erythropoietic_turnover, renal_hemodynamic")


class PhenotypeNode(BaseNode):
    node_type: str = "phenotype"
    phenotype_category: Optional[str] = Field(default=None, description="therapeutic_benefit, adverse_effect, toxicity, or safety_endpoint")
    severity: Optional[str] = Field(default="moderate", description="none, mild, moderate, high, severe")


class EdgeType(str, Enum):
    CONTAINS = "CONTAINS"
    BINDS_TO_CARRIER = "BINDS_TO_CARRIER"
    EFFLUXED_BY = "EFFLUXED_BY"
    UPTAKE_BY = "UPTAKE_BY"
    REACTANT_IN = "REACTANT_IN"
    CATALYZES = "CATALYZES"
    YIELDS = "YIELDS"
    INHIBITS_ENZYME = "INHIBITS_ENZYME"
    INDUCES_ENZYME = "INDUCES_ENZYME"
    SUBSTRATE_OF = "SUBSTRATE_OF"
    AGONIZES = "AGONIZES"
    ANTAGONIZES = "ANTAGONIZES"
    POSITIVE_ALLOSTERIC_MODULATOR = "POSITIVE_ALLOSTERIC_MODULATOR"
    NEGATIVE_ALLOSTERIC_MODULATOR = "NEGATIVE_ALLOSTERIC_MODULATOR"
    MODULATES = "MODULATES"
    BLOCKS_CHANNEL = "BLOCKS_CHANNEL"
    OPENS_CHANNEL = "OPENS_CHANNEL"
    ACTIVATES_CASCADE = "ACTIVATES_CASCADE"
    INHIBITS_CASCADE = "INHIBITS_CASCADE"
    ACTIVATES_PATHWAY = "ACTIVATES_PATHWAY"
    INHIBITS_PATHWAY = "INHIBITS_PATHWAY"
    ALTERS_PHYSIOLOGY = "ALTERS_PHYSIOLOGY"
    MODIFIES_BIOMARKER = "MODIFIES_BIOMARKER"
    DRIVES_PHENOTYPE = "DRIVES_PHENOTYPE"
    MITIGATES_PHENOTYPE = "MITIGATES_PHENOTYPE"
    SYNERGIZES_WITH = "SYNERGIZES_WITH"
    CONTRAINDICATED_WITH = "CONTRAINDICATED_WITH"


class EdgeData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    affinity_ki: Optional[float] = Field(default=None, gt=0, description="Binding affinity Ki in nM or μM (lower is stronger)")
    inhibition_ic50: Optional[float] = Field(default=None, gt=0, description="Half maximal inhibitory concentration (IC50)")
    ec50: Optional[float] = Field(default=None, gt=0, description="Half maximal effective concentration (EC50)")
    inhibition_type: Optional[str] = Field(
        default=None,
        description="Mechanism of inhibition, e.g. competitive, mechanism_based (suicide), uncompetitive, allosteric",
    )
    vector_magnitude: float = Field(
        default=1.0,
        description="Directional magnitude of the biological effect",
    )
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score for this biological association")
    is_bridge: bool = Field(default=False, description="Whether this edge represents an inter-cascade cross-talk bridge")
    description: Optional[str] = Field(default=None, description="Clinical or biochemical description of the interaction")
    notes: Optional[str] = Field(default=None)
