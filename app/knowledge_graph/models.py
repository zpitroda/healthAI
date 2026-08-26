from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class BaseNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    node_id: str = Field(..., description="Unique node identifier")
    label: str = Field(default="", description="Human-readable node label")
    node_type: str = Field(..., description="Bio-ontology node class")
    category: Optional[str] = Field(default=None, description="Domain sub-category")
    description: Optional[str] = Field(default=None, description="Detailed biological summary")
    synonyms: List[str] = Field(default_factory=list, description="Synonyms and alternative aliases")
    external_ids: Dict[str, Any] = Field(default_factory=dict, description="Cross-database identifiers (e.g. UniProt, ChEMBL, PubChem, Reactome)")


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
    canonical_name: Optional[str] = Field(default=None, description="Standardized IUPAC or INN name")
    smiles: Optional[str] = Field(default=None, description="Canonical SMILES structure")
    inchikey: Optional[str] = Field(default=None, description="InChIKey standard hash")
    pubchem_cid: Optional[str] = Field(default=None, description="PubChem Compound ID")
    chembl_id: Optional[str] = Field(default=None, description="ChEMBL Molecule Accession ID")
    logP: Optional[float] = Field(default=None, description="Octanol-water partition coefficient")
    tpsa: Optional[float] = Field(default=None, description="Topological polar surface area in Å²")
    molecular_weight: Optional[float] = Field(default=None, gt=0, description="Molecular weight in g/mol")
    base_half_life: Optional[float] = Field(default=None, gt=0, description="Baseline elimination half-life in hours")
    bioavailability_pct: Optional[float] = Field(default=None, ge=0, le=100, description="Oral bioavailability percentage")
    volume_of_distribution: Optional[float] = Field(default=None, description="Apparent Vd in L/kg")
    protein_binding_pct: Optional[float] = Field(default=None, ge=0, le=100, description="Plasma protein binding percentage")
    renal_clearance_fraction: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Fraction eliminated unchanged by renal excretion (fe)")
    hepatic_clearance_fraction: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Fraction eliminated via hepatic metabolism (fh)")
    drug_class: Optional[str] = Field(default=None, description="Therapeutic drug class")
    is_narrow_therapeutic_index: bool = Field(default=False, description="Narrow therapeutic index flag")
    cyp_substrates: List[str] = Field(default_factory=list, description="CYP/UGT enzymes for which compound is a substrate")
    cyp_inhibitors: List[str] = Field(default_factory=list, description="CYP/UGT enzymes inhibited by compound")
    cyp_inducers: List[str] = Field(default_factory=list, description="CYP/UGT enzymes induced by compound")
    metabolites: List[str] = Field(default_factory=list, description="Active or notable downstream metabolites")


class EnzymeNode(BaseNode):
    node_type: str = "enzyme"
    enzyme_family: Optional[str] = Field(default=None, description="e.g. CYP450, UGT, Kinase, Esterase, Reductase, Lyase")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")
    gene_symbol: Optional[str] = Field(default=None, description="HGNC Gene Symbol or Microbial Gene identifier")
    subcellular_location: Optional[str] = Field(default=None, description="e.g. Endoplasmic Reticulum, Cytoplasm, Mitochondria, Intestinal Lumen")
    is_microbial: bool = Field(default=False, description="Flag indicating if enzyme is expressed by gut microbiota rather than human host")
    microbial_source: Optional[str] = Field(default=None, description="e.g. Gut Microbiota, Clostridium, Escherichia, Prevotella")


class ReceptorNode(BaseNode):
    node_type: str = "receptor"
    receptor_family: Optional[str] = Field(default=None, description="e.g. GPCR, Nuclear Receptor, Ligand-Gated Ion Channel, Tyrosine Kinase")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")
    gene_symbol: Optional[str] = Field(default=None, description="HGNC Gene Symbol")
    subcellular_location: Optional[str] = Field(default=None, description="e.g. Plasma Membrane, Nucleus, Cytosol")


class TransporterNode(BaseNode):
    node_type: str = "transporter"
    transporter_family: Optional[str] = Field(default=None, description="e.g. ABC (P-gp/BCRP/MRP2), SLC (OATP/OCT/OAT)")
    direction: Optional[str] = Field(default="efflux", description="efflux or influx/uptake")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")
    gene_symbol: Optional[str] = Field(default=None, description="HGNC Gene Symbol")


class IonChannelNode(BaseNode):
    node_type: str = "ion_channel"
    channel_type: Optional[str] = Field(default=None, description="e.g. Voltage-gated, Potassium (hERG), Calcium L-type, Sodium (Nav)")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")
    gene_symbol: Optional[str] = Field(default=None, description="HGNC Gene Symbol")


class CarrierProteinNode(BaseNode):
    node_type: str = "carrier_protein"
    protein_type: Optional[str] = Field(default="plasma_protein", description="e.g. Albumin, Alpha-1-acid glycoprotein, SHBG")
    uniprot_id: Optional[str] = Field(default=None, description="UniProt Accession ID")


class ReactionNode(BaseNode):
    node_type: str = "reaction"
    reaction_type: Optional[str] = Field(default=None, description="e.g. Phase I Oxidation, Phase II Glucuronidation, Cleavage, Reduction, Hydrolysis")


class SignalingPathwayNode(BaseNode):
    node_type: str = "signaling_pathway"
    pathway_database: Optional[str] = Field(default="Reactome", description="e.g. Reactome, KEGG, GO, BioSystems")
    pathway_id: Optional[str] = Field(default=None, description="External pathway identifier (e.g. R-HSA-123456)")
    pathway_category: Optional[str] = Field(default=None, description="Functional category (e.g. Renin-Angiotensin, Vasodilation, Redox Homeostasis)")


class PhysiologyNode(BaseNode):
    node_type: str = "physiology"
    organ_system: Optional[str] = Field(default=None, description="e.g. Hepatic, Renal, Cardiovascular, CNS, Endocrine, Autonomic")
    physiological_function: Optional[str] = Field(default=None, description="e.g. Vascular Tone, Glomerular Filtration, Bile Acid Clearance, Lipolysis")
    tissue_specificity: Optional[str] = Field(default=None, description="Specific target tissue or cell type")


class BiomarkerNode(BaseNode):
    node_type: str = "biomarker"
    baseline: Optional[float] = Field(default=None, description="Physiological baseline reference value")
    safe_lower_bound: float = Field(default=0.0, description="Lower bound of clinically normal range")
    safe_upper_bound: float = Field(default=100.0, description="Upper bound of clinically normal range")
    gain_up: Optional[float] = Field(default=None, description="Maximum upward physiological ceiling shift")
    gain_down: Optional[float] = Field(default=None, description="Maximum downward physiological floor shift")
    unit: str = Field(default="standard", description="Unit of measurement for the biomarker")
    biomarker_panel: Optional[str] = Field(default=None, description="e.g. Hepatic Panel, Renal Panel, Lipid Panel, Vitals, CBC, Endocrine Panel")
    onset_days: float = Field(default=1.0, description="Onset latency in days before observable biomarker shift")
    half_time_days: float = Field(default=3.0, description="Turnover half-life in days to reach 50% response")
    time_to_steady_state_weeks: float = Field(default=1.0, description="Time in weeks to reach steady-state equilibrium (~95%)")
    kinetic_profile: str = Field(default="direct_receptor", description="rapid_autonomic, renal_electrolyte, direct_endocrine, metabolic_glycemic, hepatic_injury, hepatic_lipid_remodeling, erythropoietic_turnover, renal_hemodynamic")


class PhenotypeNode(BaseNode):
    node_type: str = "phenotype"
    phenotype_category: Optional[str] = Field(default=None, description="therapeutic_benefit, adverse_effect, toxicity, or safety_endpoint")
    severity: Optional[str] = Field(default="moderate", description="none, mild, moderate, high, severe")
    clinical_evidence_level: Optional[str] = Field(default="established", description="preclinical, clinical_trial, fda_label, consensus_guideline, observational")
    mesh_id: Optional[str] = Field(default=None, description="Medical Subject Headings (MeSH) / MedDRA identifier")


class CitationNode(BaseNode):
    node_type: str = "citation"
    pmid: Optional[str] = Field(default=None, description="PubMed ID")
    doi: Optional[str] = Field(default=None, description="Digital Object Identifier")
    title: str = Field(default="", description="Publication title")
    authors: List[str] = Field(default_factory=list, description="Author list")
    journal: Optional[str] = Field(default=None, description="Publishing journal name")
    pub_year: Optional[int] = Field(default=None, description="Publication year (for chronological indexing)")
    pub_date: Optional[str] = Field(default=None, description="ISO publication date (YYYY-MM-DD)")
    evidence_tier: str = Field(
        default="clinical_trial",
        description="Evidence grade: rct_landmark, meta_analysis, systematic_review, cohort, in_vivo, in_vitro, fda_label, guideline",
    )
    sample_size: Optional[int] = Field(default=None, description="Clinical trial or cohort participant count (N)")
    study_design: Optional[str] = Field(default=None, description="e.g. Double-blind RCT, Crossover, Observational Cohort, In Vitro Cell Culture")
    mesh_terms: List[str] = Field(default_factory=list, description="MeSH heading terms")
    key_findings: Optional[str] = Field(default=None, description="Structured summary of findings")
    conflict_count: int = Field(default=0, description="Count of conflicting/opposing studies identified")
    url: Optional[str] = Field(default=None, description="Direct URL to article (PubMed, DOI, or Europe PMC)")


class ClinicalTrialNode(BaseNode):
    node_type: str = "clinical_trial"
    nct_id: str = Field(..., description="ClinicalTrials.gov identifier (e.g. NCT01234567)")
    title: str = Field(default="", description="Brief trial title")
    phase: Optional[str] = Field(default="Phase II/III", description="Phase I, II, III, IV, or Not Applicable")
    status: Optional[str] = Field(default="COMPLETED", description="COMPLETED, RECRUITING, ACTIVE_NOT_RECRUITING, TERMINATED, WITHDRAWN")
    sponsor: Optional[str] = Field(default=None, description="Primary sponsor organization or lead investigator")
    enrollment: Optional[int] = Field(default=None, description="Target or actual patient enrollment")
    conditions: List[str] = Field(default_factory=list, description="Target pathological conditions")
    interventions: List[str] = Field(default_factory=list, description="Compounds, drugs, or modalities tested")
    primary_outcomes: List[str] = Field(default_factory=list, description="Primary trial endpoint measurements")
    start_year: Optional[int] = Field(default=None, description="Trial initiation year")
    completion_year: Optional[int] = Field(default=None, description="Trial completion year")
    url: Optional[str] = Field(default=None, description="Direct link to study record on ClinicalTrials.gov")


class EvidenceClaimNode(BaseNode):
    node_type: str = "evidence_claim"
    claim_type: str = Field(
        default="pharmacological_effect",
        description="Type: binding_affinity, clearance_mechanism, drug_interaction, synergy, biomarker_shift, adverse_hazard, therapeutic_benefit",
    )
    subject_id: str = Field(..., description="Subject entity identifier (e.g. compound key)")
    predicate: str = Field(..., description="Relationship predicate (e.g. INHIBITS, AGONIZES, SYNERGIZES_WITH)")
    object_id: str = Field(..., description="Object entity identifier (e.g. target, enzyme, outcome)")
    magnitude_value: Optional[float] = Field(default=None, description="Quantitative magnitude (e.g. Ki in nM, AUCR ratio, delta %)")
    magnitude_unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g. nM, %, fold-change)")
    direction: Optional[str] = Field(default="neutral", description="increases, decreases, blocks, activates, neutral")
    consensus_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Literature consensus agreement ratio (1.0 = full consensus, <0.5 = contested)")
    dispute_status: str = Field(default="consensus", description="consensus, debated, refuted, context_dependent")
    contradiction_index: float = Field(default=0.0, ge=0.0, le=1.0, description="Divergence metric among published studies (0.0 = none, 1.0 = complete conflict)")
    discovery_year: Optional[int] = Field(default=None, description="Year this claim was first reported in literature")
    last_validated_year: Optional[int] = Field(default=None, description="Most recent study validating this claim")
    conflicting_pmids: List[str] = Field(default_factory=list, description="PMIDs reporting contradictory or incompatible findings")


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
    LITERATURE_COOCCURRENCE = "LITERATURE_COOCCURRENCE"
    CURATED_ASSOCIATION = "CURATED_ASSOCIATION"
    # Provenance, Temporal & Conflict Relationship Types
    SUPPORTED_BY = "SUPPORTED_BY"
    CONTRADICTED_BY = "CONTRADICTED_BY"
    TESTED_IN = "TESTED_IN"
    SUPERSEDES = "SUPERSEDES"
    CORROBORATES = "CORROBORATES"
    EVOLVED_TO = "EVOLVED_TO"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    DISPUTES = "DISPUTES"


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
    evidence_level: Optional[str] = Field(default="in_vitro", description="in_vitro, in_vivo, clinical_trial, meta_analysis, label_boxed, guideline")
    pmids: List[str] = Field(default_factory=list, description="PubMed identifiers validating the interaction")
    citations: List[Dict[str, Any]] = Field(default_factory=list, description="Structured citation references with PMIDs, DOIs, titles, years")
    discovery_year: Optional[int] = Field(default=None, description="Earliest published study year demonstrating this interaction")
    latest_study_year: Optional[int] = Field(default=None, description="Most recent study year validating or updating this interaction")
    conflict_flag: bool = Field(default=False, description="Whether there are conflicting or disputed findings in literature for this edge")
    consensus_score: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Consensus ratio among published studies (1.0 = unanimous agreement)")
    contradiction_index: Optional[float] = Field(default=0.0, ge=0.0, le=1.0, description="Contradiction magnitude metric (0.0 = none, 1.0 = diametric conflict)")
    conflicting_pmids: List[str] = Field(default_factory=list, description="PMIDs of studies reporting contradictory or conflicting data")
    divergence_rationale: Optional[str] = Field(default=None, description="Scientific explanation of why conflicting data exists")
    is_bridge: bool = Field(default=False, description="Whether this edge represents an inter-cascade cross-talk bridge")
    description: Optional[str] = Field(default=None, description="Clinical or biochemical description of the interaction")
    mechanism_notes: Optional[str] = Field(default=None, description="Biophysical explanation of the mechanism")
    notes: Optional[str] = Field(default=None)
    source_db: Optional[str] = Field(default=None, description="Source database for curated edges (STITCH, CTD, DrugBank, PubMed_PMI, ChEMBL)")
    cooccurrence_count: Optional[int] = Field(default=None, ge=0, description="Number of PubMed papers co-mentioning both entities")
    pmi_score: Optional[float] = Field(default=None, description="Pointwise Mutual Information score from literature co-occurrence")
    npmi_score: Optional[float] = Field(default=None, ge=-1.0, le=1.0, description="Normalized PMI score (-1 to +1)")
    last_mined: Optional[str] = Field(default=None, description="ISO timestamp of when this edge was last mined/updated")
