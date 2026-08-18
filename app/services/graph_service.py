from __future__ import annotations

import math
import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from app.knowledge_graph.examples import build_testosterone_alopecia_graph
from app.knowledge_graph.graph import BiologicalGraph
from app.knowledge_graph.models import (
    BaseNode,
    BiomarkerNode,
    CompoundNode,
    EdgeData,
    EdgeType,
    EnzymeNode,
    IonChannelNode,
    PhenotypeNode,
    PhysiologyNode,
    ReactionNode,
    ReceptorNode,
    SignalingPathwayNode,
    TransporterNode,
)
from app.services.catalog_service import CatalogService


def normalize_stack_name(value: Any) -> str:
    """Normalize string token by lowercasing and replacing underscores/hyphens with spaces."""
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def canonicalize_match_token(value: Any) -> str:
    """Strip all non-alphanumeric characters for fuzzy synonym and key matching."""
    return "".join(ch for ch in normalize_stack_name(value) if ch.isalnum())


def parse_compound_spec(spec: Any) -> Dict[str, Any]:
    """Parse compound name/key and optional dose specification (e.g., 'clenbuterol:40ug', 'nebivolol:5mg', or structured dict)."""
    from app.services.dosing_service import get_default_compound_dose, parse_dose_string_or_spec

    if isinstance(spec, dict):
        key = str(spec.get("key") or spec.get("compound") or spec.get("name") or "").strip()
        dose = spec.get("dose") or spec.get("dose_val") or spec.get("dose_mg")
        unit = str(spec.get("unit") or spec.get("dose_unit") or "").strip().lower()

        if isinstance(dose, (int, float)) and float(dose) > 0:
            val = float(dose)
            if unit in ["ug", "mcg", "μg", "µg"]:
                dose_mg = val / 1000.0
                fmt_str = f"{val:g} μg"
            elif unit in ["g", "grams"]:
                dose_mg = val * 1000.0
                fmt_str = f"{val:g} g"
            elif unit in ["iu"]:
                dose_mg = val * 0.025
                fmt_str = f"{val:g} IU"
            else:
                dose_mg = val
                fmt_str = f"{val:g} mg"
            return {"key": key, "dose_mg": dose_mg, "dose_str": fmt_str}
        elif isinstance(dose, str) and dose.strip():
            return parse_compound_spec(f"{key}:{dose.strip()}")
        else:
            default_info = get_default_compound_dose(key)
            return {"key": key, "dose_mg": default_info["dose_mg"], "dose_str": default_info["dose_display"]}

    spec_str = str(spec or "").strip()
    if not spec_str:
        return {"key": "", "dose_mg": 10.0, "dose_str": "10 mg"}

    parsed = parse_dose_string_or_spec(spec_str)
    return {"key": parsed["key"], "dose_mg": parsed["dose_mg"], "dose_str": parsed["dose_display"]}



def resolve_stack_to_catalog_keys(stack: List[Any] | None, catalog_service: CatalogService | None = None) -> List[str]:
    """Map raw user input compound names/synonyms to canonical catalog keys directly in the database."""
    if not stack:
        return []

    service = catalog_service or CatalogService()
    resolved: List[str] = []

    for item in stack:
        parsed = parse_compound_spec(item)
        text = parsed["key"]
        if not text:
            continue

        try:
            compound = service.get_compound(text, auto_enrich=False)
        except TypeError:
            compound = service.get_compound(text)

        if compound and compound["key"] not in resolved:
            resolved.append(compound["key"])
        else:
            # Fallback search
            try:
                matches = service.search_compounds(text, limit=1, auto_enrich=False)
            except TypeError:
                matches = service.search_compounds(text, limit=1)
            if matches and matches[0]["key"] not in resolved:
                resolved.append(matches[0]["key"])

    return resolved


def classify_target_action(action: Any) -> tuple[EdgeType, float]:
    """Classify pharmacological action description into a standardized edge type and vector magnitude."""
    normalized = str(action or "").lower()
    if "antagonist" in normalized or "antagonizes" in normalized or "blocker" in normalized or "blocks" in normalized:
        return EdgeType.ANTAGONIZES, -1.0
    if "agonist" in normalized or "agonizes" in normalized or "activator" in normalized or "activates" in normalized or "antioxidant" in normalized or "scavenger" in normalized:
        return EdgeType.AGONIZES, 1.0
    if any(token in normalized for token in ["inhibitor", "inhibits", "inhibition", "suppresses"]):
        return EdgeType.INHIBITS_ENZYME, -0.8
    if any(token in normalized for token in ["substrate", "metabolized by", "converted by", "cleaved by"]):
        return EdgeType.SUBSTRATE_OF, 0.5
    if any(token in normalized for token in ["inducer", "induces", "induction"]):
        return EdgeType.INDUCES_ENZYME, 0.8
    if any(token in normalized for token in ["pam", "positive allosteric"]):
        return EdgeType.POSITIVE_ALLOSTERIC_MODULATOR, 0.8
    if any(token in normalized for token in ["nam", "negative allosteric"]):
        return EdgeType.NEGATIVE_ALLOSTERIC_MODULATOR, -0.8
    if any(token in normalized for token in ["modulator", "modulates", "supports", "cofactor"]):
        return EdgeType.MODULATES, 0.5
    return EdgeType.MODULATES, 0.5


# CANONICAL TARGET-TO-DOWNSTREAM-CASCADE MAPPER
# Maps molecular targets to intracellular signaling pathways, physiology, biomarkers, and clinical phenotypes
CANONICAL_TARGET_CASCADES: List[Dict[str, Any]] = [
    {
        "target_pattern": r"(?:adra2|alpha-2|alpha_2|yohimbine|clonidine|guanfacine)",
        "target_name": "Alpha-2 Adrenergic Receptor (ADRA2A/2B/2C)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_adra2_autoreceptor",
            "label": "Presynaptic Gi/o Autoreceptor Exocytosis Regulation",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_norepinephrine_release",
            "label": "Presynaptic Norepinephrine Exocytosis & Sympathetic Noradrenergic Outflow",
            "organ": "Autonomic / Cardiovascular",
        },
        "biomarkers": [
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.7},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": -0.6},
        ],
        "phenotypes": [
            {"id": "pheno_sympathetic_activation", "label": "Sympathoadrenal Arousal, Lipolysis & Chronotropic Stimulation", "cat": "therapeutic_benefit", "sev": "moderate", "mag": -0.85},
            {"id": "pheno_tachycardia", "label": "Resting Tachycardia & Sympathetic Vasoconstriction", "cat": "adverse_effect", "sev": "moderate", "mag": -0.75},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:beta-1|beta-2|adrb1|adrb2|beta-adrenergic)",
                "edge_type": EdgeType.AGONIZES,
                "vector_magnitude": -0.85,
                "description": "Presynaptic Alpha-2 blockade triggers norepinephrine exocytosis, which endogenous agonist binds post-junctional Beta-1/Beta-2 Adrenergic Receptors",
            },
            {
                "target_node_pattern": r"(?:pathway_beta1_adrenergic|pathway_beta2_adrenergic|phys_sa_av_nodal_conduction)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": -0.85,
                "description": "Surge in synaptic norepinephrine activates downstream cardiac beta-adrenergic inotropic/chronotropic signaling",
            },
        ],
    },
    {
        "target_pattern": r"(?:adenosine|\ba1\b|\ba2a\b|adora1|adora2a)",
        "target_name": "Adenosine A1/A2A Receptor",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_adenosine_signaling",
            "label": "Adenosine / Adenylyl Cyclase Signaling",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_central_arousal",
            "label": "Purinergic Somnolence & Autonomic Brake",
            "organ": "Central Nervous System",
        },
        "biomarkers": [
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.6},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": -0.5},
        ],
        "phenotypes": [
            {"id": "pheno_vigilance", "label": "Heightened Cognitive Vigilance & Reaction Time", "cat": "therapeutic_benefit", "sev": "moderate", "mag": -0.8},
            {"id": "pheno_insomnia", "label": "Sleep Onset Latency Increase & Sleep Fragmentation", "cat": "adverse_effect", "sev": "moderate", "mag": -0.7},
            {"id": "pheno_tachycardia", "label": "Resting Tachycardia & Sympathetic Chronotropy", "cat": "adverse_effect", "sev": "moderate", "mag": -0.65},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:dopamine|dat|net|vmat|pathway_monoamine_reuptake|phys_mesolimbic_tone)",
                "edge_type": EdgeType.MODULATES,
                "vector_magnitude": -0.7,
                "description": "Adenosine receptor antagonism removes tonic purinergic inhibition, facilitating central catecholaminergic and dopaminergic neurotransmission",
            }
        ],
    },
    {
        "target_pattern": r"(?:atp-pcr|phosphagen|skeletal muscle)",
        "target_name": "Skeletal Muscle ATP-PCr System",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_phosphagen_resynthesis",
            "label": "Mitochondrial Creatine Kinase / Phosphagen Regeneration",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_muscle_bioenergetics",
            "label": "Intracellular High-Energy Phosphate Resynthesis",
            "organ": "Skeletal Muscle",
        },
        "biomarkers": [
            {"id": "bio_pcr_stores", "label": "Intramuscular Phosphocreatine Concentration", "unit": "mmol/kg dw", "panel": "Muscle Panel", "lower": 100, "upper": 150, "mag": 0.85},
            {"id": "bio_serum_creatinine", "label": "Serum Creatinine Lab Artifact", "unit": "mg/dL", "panel": "Renal Panel", "lower": 0.6, "upper": 1.2, "mag": 0.2},
        ],
        "phenotypes": [
            {"id": "pheno_power_output", "label": "Enhanced Anaerobic Peak Power & Repeated Sprint Capacity", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
            {"id": "pheno_lean_mass", "label": "Accelerated Resistance Training Lean Mass Adaptation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.8},
        ],
    },
    {
        "target_pattern": r"(?:gaba|gaba_a|benzodiazepine)",
        "target_name": "GABA-A Receptor Complex",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_gabaergic_transmission",
            "label": "GABA-A Receptor Activation & Chloride Influx",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_neural_inhibition",
            "label": "Central Synaptic Hyperpolarization & Cortical Inhibition",
            "organ": "Central Nervous System",
        },
        "biomarkers": [
            {"id": "bio_cortisol", "label": "Serum Cortisol Concentration", "unit": "μg/dL", "panel": "Endocrine Panel", "lower": 6.0, "upper": 18.0, "mag": -0.6},
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.4},
        ],
        "phenotypes": [
            {"id": "pheno_anxiolysis", "label": "Rapid Anxiolysis & Somatic Stress Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            {"id": "pheno_sedation", "label": "Central Sedation & Sleep Consolidation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.8},
        ],
    },
    {
        "target_pattern": r"(?:angiotensin|at1|agtr1|ace|renin|sartan)",
        "target_name": "Angiotensin II Type-1 (AT1) Receptor / ACE",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_raas_signaling",
            "label": "Renin-Angiotensin-Aldosterone System (RAAS) Cascade",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_arteriolar_tone",
            "label": "Systemic Vascular Resistance & Glomerular Hemodynamics",
            "organ": "Cardiovascular / Renal",
        },
        "biomarkers": [
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.7},
            {"id": "bio_potassium", "label": "Serum Potassium (K+)", "unit": "mEq/L", "panel": "Electrolytes", "lower": 3.5, "upper": 5.0, "mag": -0.4},
        ],
        "phenotypes": [
            {"id": "pheno_bp_control", "label": "Cardiovascular Risk Reduction & Blood Pressure Normalization", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.9},
            {"id": "pheno_nephroprotection", "label": "Renal Glomerular Protection & Reduced Microalbuminuria", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.8},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:mineralocorticoid|aldosterone|nr3c2|pathway_aldosterone_mr|phys_renal_k_sparing)",
                "edge_type": EdgeType.MODULATES,
                "vector_magnitude": 0.8,
                "description": "AT1 receptor signaling drives adrenal secretion of Aldosterone to activate Mineralocorticoid Receptors",
            }
        ],
    },
    {
        "target_pattern": r"(?:mineralocorticoid|aldosterone|nr3c2|eplerenone|spironolactone)",
        "target_name": "Mineralocorticoid Receptor (Aldosterone Receptor / NR3C2)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_aldosterone_mr",
            "label": "Aldosterone-Regulated Renal Sodium/Potassium Transport",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_renal_k_sparing",
            "label": "Distal Nephron Potassium Sparing & Natriuresis",
            "organ": "Renal / Cardiovascular",
        },
        "biomarkers": [
            {"id": "bio_potassium", "label": "Serum Potassium (K+)", "unit": "mEq/L", "panel": "Electrolytes", "lower": 3.5, "upper": 5.0, "mag": -0.5},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.15},
        ],
        "phenotypes": [
            {"id": "pheno_hyperkalemia_risk", "label": "Severe Hyperkalemia Risk & Cardiac Conduction Vulnerability", "cat": "toxicity", "sev": "severe", "mag": -0.85},
            {"id": "pheno_aldosterone_blockade", "label": "Aldosterone Breakthrough Suppression & Antifibrotic Cardioprotection", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.8},
        ],
    },
    {
        "target_pattern": r"(?:hmg-coa|statin|cholesterol)",
        "target_name": "HMG-CoA Reductase",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_mevalonate",
            "label": "Mevalonate / Hepatic Cholesterol Biosynthesis Pathway",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_ldl_clearance",
            "label": "Hepatic Cholesterol Biosynthesis & Sterol Homeostasis",
            "organ": "Hepatic",
        },
        "biomarkers": [
            {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50, "upper": 100, "mag": 0.85},
            {"id": "bio_alt", "label": "Alanine Aminotransferase (ALT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10, "upper": 45, "mag": -0.25},
        ],
        "phenotypes": [
            {"id": "pheno_athero_regression", "label": "Atherosclerotic Plaque Stabilization & Major Adverse Event Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.95},
        ],
    },
    {
        "target_pattern": r"(?:dopamine|dat|net|vmat)",
        "target_name": "Dopamine / Norepinephrine Transporter (DAT/NET)",
        "node_type": "transporter",
        "pathway": {
            "id": "pathway_monoamine_reuptake",
            "label": "Synaptic Monoamine Transport & Neurotransmission",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_mesolimbic_tone",
            "label": "Prefrontal Dopaminergic Signaling & Psychomotor Motivation",
            "organ": "Central Nervous System",
        },
        "biomarkers": [
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.6},
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.65},
        ],
        "phenotypes": [
            {"id": "pheno_executive_function", "label": "Enhanced Working Memory, Attentional Focus & Motivation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
            {"id": "pheno_tachycardia", "label": "Resting Tachycardia & Sympathetic Vasoconstriction", "cat": "adverse_effect", "sev": "moderate", "mag": 0.6},
        ],
    },
    {
        "target_pattern": r"(?:serotonin|sert|5-ht)",
        "target_name": "Serotonin Transporter (SERT / SLC6A4)",
        "node_type": "transporter",
        "pathway": {
            "id": "pathway_serotonergic_signaling",
            "label": "Synaptic Serotonin Signaling & Reuptake Inhibition",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_limbic_neurotransmission",
            "label": "Limbic Emotional Regulation & Platelet 5-HT Storage",
            "organ": "Central Nervous System / Hematologic",
        },
        "biomarkers": [
            {"id": "bio_cortisol", "label": "Serum Cortisol Concentration", "unit": "μg/dL", "panel": "Endocrine Panel", "lower": 6.0, "upper": 18.0, "mag": -0.4},
        ],
        "phenotypes": [
            {"id": "pheno_mood_stabilization", "label": "Affective Stabilization & Depressive Symptom Remission", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            {"id": "pheno_serotonin_toxicity", "label": "Serotonergic Autonomic Toxicity at High Doses", "cat": "toxicity", "sev": "severe", "mag": 0.7},
        ],
    },
    {
        "target_pattern": r"(?:pde5|phosphodiesterase 5)",
        "target_name": "Phosphodiesterase 5A (PDE5)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_cgmp_no",
            "label": "Nitric Oxide / cGMP Signal Transduction Pathway",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_smooth_muscle_relaxation",
            "label": "Vascular Smooth Muscle Relaxation & Endothelial Perfusion",
            "organ": "Cardiovascular",
        },
        "biomarkers": [
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.5},
        ],
        "phenotypes": [
            {"id": "pheno_hyperemia", "label": "Enhanced Endothelial Vasodilation & Skeletal Muscle Perfusion", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.9},
        ],
    },
    {
        "target_pattern": r"(?:cox-1|cox-2|cyclooxygenase|prostaglandin)",
        "target_name": "Cyclooxygenase 1 & 2 (COX-1/2)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_eicosanoid",
            "label": "Arachidonic Acid / Eicosanoid Biosynthesis Cascade",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_inflammatory_cascade",
            "label": "Pro-Inflammatory Prostaglandin Synthesis & Renal Hemodynamics",
            "organ": "Immune / Renal",
        },
        "biomarkers": [
            {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": 0.75},
            {"id": "bio_egfr", "label": "Glomerular Filtration Rate (eGFR)", "unit": "mL/min/1.73m²", "panel": "Renal Panel", "lower": 60, "upper": 120, "mag": 0.35},
        ],
        "phenotypes": [
            {"id": "pheno_antiinflammatory", "label": "Rapid Analgesia & Systemic Inflammation Suppression", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.9},
            {"id": "pheno_renal_strain", "label": "Afferent Renal Vasoconstriction & Fluid Retention Risk", "cat": "adverse_effect", "sev": "moderate", "mag": -0.65},
        ],
    },
    {
        "target_pattern": r"(?:glutathione synthesis|glutathione|gsh|gssg|cystine-glutamate|system xc-|slc7a11|nrf2|nfe2l2|glutamate-cysteine ligase|gclc|gclm|antioxidant defense)",
        "target_name": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_glutathione_biosynthesis_and_redox",
            "label": "Glutathione Biosynthesis, System xc- Cystine Transport & Nrf2 Redox Defense (R-HSA-3299685)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_glutathione_redox_tone",
            "label": "Intracellular Glutathione Synthesis, ROS Scavenging & Endothelial Cytoprotection",
            "organ": "Systemic / Hepatic",
        },
        "biomarkers": [
            {"id": "bio_gsh_redox_ratio", "label": "Glutathione Redox Index (GSH:GSSG)", "unit": "index", "panel": "Redox Panel", "lower": 80.0, "upper": 120.0, "mag": 0.85},
            {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": -0.75},
            {"id": "bio_mda", "label": "Serum Malondialdehyde (MDA / Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 1.0, "upper": 2.5, "mag": -0.80},
            {"id": "bio_alt", "label": "Alanine Aminotransferase (ALT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10.0, "upper": 45.0, "mag": -0.35},
        ],
        "phenotypes": [
            {"id": "pheno_glutathione_cytoprotection", "label": "Enhanced Hepatocellular Glutathione Pool, Free Radical Scavenging & Cytoprotection", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            {"id": "pheno_antiinflammatory", "label": "Systemic hs-CRP & Inflammatory Cascade Attenuation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
        ],
    },
    {
        "target_pattern": r"(?:5-alpha|srd5a|5-ar|5ar|dihydrotestosterone synthase)",
        "target_name": "5-Alpha Reductase Subtype 1 & 2",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_androgen_metabolism",
            "label": "Steroid 5-Alpha Reduction & Androgenic Transactivation",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_follicle_signaling",
            "label": "Scalp Dermal Papilla Androgenic Signaling",
            "organ": "Integumentary",
        },
        "biomarkers": [
            {"id": "bio_dht", "label": "Serum Dihydrotestosterone (DHT)", "unit": "ng/dL", "panel": "Endocrine Panel", "lower": 30, "upper": 85, "mag": 0.8},
        ],
        "phenotypes": [
            {"id": "pheno_alopecia_halt", "label": "Arrest of Androgen-Driven Hair Follicle Miniaturization", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.85},
        ],
    },
    {
        "target_pattern": r"(?:kcnh2|herg|potassium voltage-gated|ik_r|delayed rectifier)",
        "target_name": "Voltage-Gated Potassium Channel (hERG / KCNH2 / IKr)",
        "node_type": "ion_channel",
        "pathway": {
            "id": "pathway_cardiac_repolarization",
            "label": "Cardiac Ventricular Action Potential Phase 3 Repolarization",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_ventricular_refractoriness",
            "label": "Ventricular Myocardial Action Potential Duration & Refractoriness",
            "organ": "Cardiovascular",
        },
        "biomarkers": [
            {"id": "bio_qtc", "label": "Corrected QT Interval (QTc)", "unit": "ms", "panel": "Electrophysiology", "lower": 350, "upper": 440, "mag": -0.75},
        ],
        "phenotypes": [
            {"id": "pheno_torsades_risk", "label": "Torsades de Pointes & Fatal Ventricular Arrhythmia Risk", "cat": "toxicity", "sev": "severe", "mag": -0.9},
        ],
    },
    {
        "target_pattern": r"(?:adrb1|beta-1|beta_1)",
        "target_name": "Beta-1 Adrenergic Receptor (ADRB1)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_beta1_adrenergic",
            "label": "Beta-1 Adrenergic Gs/cAMP/PKA Cardiac Chronotropic & Inotropic Cascade",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_sa_av_nodal_conduction",
            "label": "Sinoatrial & Atrioventricular Nodal Automaticity & Conduction",
            "organ": "Cardiovascular",
        },
        "biomarkers": [
            # β1-AR modulates cardiac chronotropy at rest — blockade reduces HR by ~15-20bpm max
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.55},
            # β1-AR modulates cardiac inotropy → modest BP effect
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.35},
        ],
        "phenotypes": [
            {"id": "pheno_bradycardia_block", "label": "Symptomatic Bradycardia & High-Grade AV Nodal Block", "cat": "toxicity", "sev": "high", "mag": -0.8},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:pathway_calcium_influx|phys_myocardial_contractility)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.55,
                "description": "Beta-1 adrenergic Gs/cAMP/PKA signaling stimulates calcium influx and myocardial contractility",
            },
        ],
    },
    {
        "target_pattern": r"(?:adrb2|beta-2|beta_2|beta-adrenergic)",
        "target_name": "Beta-2 Adrenergic Receptor (ADRB2)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_beta2_adrenergic",
            "label": "Beta-2 Adrenergic Gs/cAMP Sympathoadrenal Activation Cascade",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_sympathoadrenal_drive",
            "label": "Sympathoadrenal Catecholaminergic Drive & Peripheral Beta-2 Vasodilation",
            "organ": "Cardiovascular / Metabolic",
        },
        "biomarkers": [
            # β2-AR agonism at high doses causes massive tachycardia (reflex + direct cAMP)
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.85},
            # β2-AR agonism → vasodilation acutely, but high-dose systemic cAMP surge raises BP
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.55},
            # β2 agonism drives hypokalemia via Na+/K+-ATPase stimulation
            {"id": "bio_potassium", "label": "Serum Potassium", "unit": "mEq/L", "panel": "Metabolic", "lower": 3.5, "upper": 5.0, "mag": -0.7},
        ],
        "phenotypes": [
            {"id": "pheno_sympathetic_activation", "label": "Sympathoadrenal Arousal, Lipolysis & Elevated Heart Rate", "cat": "therapeutic_benefit", "sev": "moderate", "mag": 0.8},
            {"id": "pheno_tachycardia", "label": "Resting Tachycardia & Sympathetic Vasoconstriction", "cat": "adverse_effect", "sev": "moderate", "mag": 0.85},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:pathway_beta1_adrenergic|phys_sa_av_nodal_conduction)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.65,
                "description": "Beta-2 sympathoadrenal cAMP surge cross-activates cardiac β1 chronotropic pathway via circulating catecholamines and reflex tachycardia",
            },
        ],
    },
    {
        "target_pattern": r"(?:cacna1c|voltage-gated calcium|l-type calcium|calcium channel)",
        "target_name": "L-Type Voltage-Gated Calcium Channel (CACNA1C)",
        "node_type": "ion_channel",
        "pathway": {
            "id": "pathway_calcium_influx",
            "label": "Depolarization-Induced Calcium Influx & Excitation-Contraction Coupling",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_myocardial_contractility",
            "label": "Myocardial Inotropy & Peripheral Arteriolar Resistance",
            "organ": "Cardiovascular",
        },
        "biomarkers": [
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.65},
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.5},
        ],
        "phenotypes": [
            {"id": "pheno_vasodilatory_hypotension", "label": "Arteriolar Vasodilation & Blood Pressure Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.85},
        ],
    },
    {
        "target_pattern": r"(?:thrombin|f2|factor xa|f10|p2y12|ptgs1|platelet|anticoagulant|antiplatelet)",
        "target_name": "Coagulation Cascade (Thrombin / Factor Xa / Platelet P2Y12)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_hemostatic_clotting",
            "label": "Prothrombinase Complex Activation & Platelet Cross-Linking",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_microvascular_hemostasis",
            "label": "Fibrin Mesh Polymerization & Primary/Secondary Hemostasis",
            "organ": "Hematologic",
        },
        "biomarkers": [
            {"id": "bio_bleeding_risk", "label": "Bleeding Tendency / Clotting Impairment", "unit": "risk_index", "panel": "Coagulation Panel", "lower": 0.0, "upper": 1.0, "mag": -0.8},
        ],
        "phenotypes": [
            {"id": "pheno_major_hemorrhage", "label": "Major Gastrointestinal & Intracranial Hemorrhage Risk", "cat": "toxicity", "sev": "severe", "mag": -0.9},
        ],
    },
    {
        "target_pattern": r"(?:chrm1|chrm2|chrm3|muscarinic|antimuscarinic|anticholinergic)",
        "target_name": "Muscarinic Acetylcholine Receptors (CHRM1-5)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_muscarinic_signaling",
            "label": "Postsynaptic Muscarinic Cholinergic Signal Transduction",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_central_cholinergic_transmission",
            "label": "Central Memory Encoding, Autonomic Secretions & Parasympathetic Tone",
            "organ": "Central Nervous System / Autonomic",
        },
        "biomarkers": [
            {"id": "bio_acetylcholine_cns", "label": "Central Cholinergic Neurotransmission Index", "unit": "index", "panel": "Neurologic Index", "lower": 50, "upper": 100, "mag": 0.8},
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.4},
        ],
        "phenotypes": [
            {"id": "pheno_anticholinergic_delirium", "label": "Acute Anticholinergic Delirium & Memory Impairment", "cat": "toxicity", "sev": "severe", "mag": -0.85},
        ],
    },
    {
        "target_pattern": r"(?:glp1r|glp-1|slc5a2|sglt2|kcnj11|sulfonylurea|insulin)",
        "target_name": "Glucose Regulatory Machinery (GLP1R / SGLT2 / KATP / Insulin)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_glucose_homeostasis",
            "label": "Incretin Receptor Signaling & Renal Tubular Glucose Reclamation",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_glycemic_control",
            "label": "Insulin-Mediated Glucose Uptake & Renal Glycosuria Control",
            "organ": "Endocrine / Renal",
        },
        "biomarkers": [
            {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70, "upper": 100, "mag": -0.8},
        ],
        "phenotypes": [
            {"id": "pheno_hypoglycemia_crisis", "label": "Severe Neuroglycopenic Hypoglycemia & Cognitive Collapse", "cat": "toxicity", "sev": "severe", "mag": 0.9},
        ],
    },
    {
        "target_pattern": r"(?:oprm1|mu-opioid|opioid|orexin|hcortr|histamine h1|hrh1)",
        "target_name": "Central Depressant Receptors (Mu-Opioid / GABA-A / H1 / Orexin)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_brainstem_ventilatory_drive",
            "label": "Medullary Chemosensory Ventilatory Pacemaker & Cortical Arousal",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_respiratory_control",
            "label": "Central Respiratory Drive & Vigilance Maintenance",
            "organ": "Central Nervous System",
        },
        "biomarkers": [
            {"id": "bio_cns_arousal", "label": "Central Respiratory & Arousal Index", "unit": "index", "panel": "Neurologic Index", "lower": 50, "upper": 100, "mag": -0.85},
        ],
        "phenotypes": [
            {"id": "pheno_respiratory_arrest", "label": "Fatal Respiratory Depression, Hypoventilation & Coma", "cat": "toxicity", "sev": "severe", "mag": 0.95},
        ],
    },
    {
        "target_pattern": r"(?:ppar|pparg|ppara|ppard|peroxisome proliferator)",
        "target_name": "Peroxisome Proliferator-Activated Receptor (PPAR-γ/α/δ)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_ppar_signaling",
            "label": "PPAR-Mediated Gene Transcription & Lipid/Glucose Regulation",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_insulin_sensitization",
            "label": "Adipose Tissue Lipid Storage & Peripheral GLUT4 Glucose Uptake",
            "organ": "Endocrine / Metabolic",
        },
        "biomarkers": [
            {"id": "bio_hba1c", "label": "Hemoglobin A1c (HbA1c)", "unit": "%", "panel": "Glycemic Panel", "lower": 4.0, "upper": 5.6, "mag": -0.8},
            {"id": "bio_triglycerides", "label": "Serum Triglycerides", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40, "upper": 150, "mag": -0.7},
            {"id": "bio_adiponectin", "label": "Serum Adiponectin Level", "unit": "μg/mL", "panel": "Endocrine Panel", "lower": 5.0, "upper": 30.0, "mag": 0.85},
        ],
        "phenotypes": [
            {"id": "pheno_glycemic_control", "label": "Peripheral Insulin Sensitization & Glycemic Normalization", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
            {"id": "pheno_fluid_retention_weight", "label": "Renal Sodium Retention & Subcutaneous Weight Gain Risk", "cat": "adverse_effect", "sev": "moderate", "mag": -0.6},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:phys_glycemic_control|pathway_glucose_homeostasis|bio_glucose)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.85,
                "description": "PPAR-gamma activation enhances systemic insulin sensitivity and downstream glucose homeostasis",
            }
        ],
    },
    {
        "target_pattern": r"(?:sglt2|slc5a2|dapagliflozin|empagliflozin|canagliflozin)",
        "target_name": "Sodium-Glucose Cotransporter 2 (SGLT2 / SLC5A2)",
        "node_type": "transporter",
        "pathway": {
            "id": "pathway_sglt2_inhibition",
            "label": "Renal Proximal Tubule Sodium-Glucose Transport Inhibition",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_renal_glycosuria",
            "label": "Glomerular Hyperfiltration Suppression & Osmotic Natriuresis",
            "organ": "Renal / Cardiovascular",
        },
        "biomarkers": [
            {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70, "upper": 100, "mag": -0.85},
            {"id": "bio_egfr", "label": "Glomerular Filtration Rate (eGFR)", "unit": "mL/min/1.73m²", "panel": "Renal Panel", "lower": 60, "upper": 120, "mag": 0.6},
        ],
        "phenotypes": [
            {"id": "pheno_cardiorenal_protection", "label": "Cardiorenal Protection & Glycemic Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
        ],
    },
    {
        "target_pattern": r"(?:aromatase|cyp19a1|estrogen synthase)",
        "target_name": "Aromatase (CYP19A1)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_aromatization",
            "label": "Steroid Aromatization & 17-Beta Estradiol Biosynthesis",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_estrogenic_tone",
            "label": "Estrogenic Endocrine Axis & Secondary Sexual Characteristics",
            "organ": "Endocrine / Reproductive",
        },
        "biomarkers": [
            {"id": "bio_estradiol", "label": "Serum Estradiol (E2)", "unit": "pg/mL", "panel": "Endocrine Panel", "lower": 15.0, "upper": 45.0, "mag": 1.0},
            {"id": "bio_hdl_c", "label": "Serum HDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 90.0, "mag": 0.45},
            {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50.0, "upper": 100.0, "mag": -0.40},
            {"id": "bio_triglycerides", "label": "Serum Triglycerides", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 150.0, "mag": 0.25},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.45},
        ],
        "phenotypes": [
            {"id": "pheno_gynecomastia_risk", "label": "Glandular Gynecomastia & Estrogenic Breast Tissue Proliferation Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.8},
            {"id": "pheno_fluid_retention", "label": "Estrogen-Mediated Renal Sodium & Subcutaneous Fluid Retention", "cat": "adverse_effect", "sev": "moderate", "mag": 0.75},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:esr1|esr2|er-alpha|er-beta|estrogen receptor|pathway_er_transactivation)",
                "edge_type": EdgeType.AGONIZES,
                "vector_magnitude": 0.85,
                "description": "Aromatase catalyzes conversion of circulating C19 androgens into 17-beta estradiol, which potently binds and transactivates nuclear Estrogen Receptors (ER-alpha/ER-beta)",
            },
            {
                "target_node_pattern": r"(?:pathway_raas_signaling|phys_arteriolar_tone|angiotensin|aldosterone|phys_renal_k_sparing)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.5,
                "description": "Estradiol upregulates hepatic angiotensinogen synthesis and increases renal tubular sodium/water retention, feeding into the RAAS vascular tone cascade",
            },
        ],
    },
    {
        "target_pattern": r"(?:esr1|esr2|er-alpha|er-beta|estrogen receptor|estradiol receptor)",
        "target_name": "Estrogen Receptor Alpha & Beta (ESR1/ESR2)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_er_transactivation",
            "label": "Nuclear Estrogen Receptor Transactivation & Gene Expression",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_estrogenic_signaling",
            "label": "Estrogenic Cellular Signaling & Tissue Proliferation",
            "organ": "Endocrine / Reproductive",
        },
        "biomarkers": [
            {"id": "bio_estradiol", "label": "Serum Estradiol (E2)", "unit": "pg/mL", "panel": "Endocrine Panel", "lower": 15.0, "upper": 45.0, "mag": 0.8},
            {"id": "bio_hdl_c", "label": "Serum HDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 90.0, "mag": 0.4},
            {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50.0, "upper": 100.0, "mag": -0.35},
            {"id": "bio_triglycerides", "label": "Serum Triglycerides", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 150.0, "mag": 0.20},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.4},
        ],
        "phenotypes": [
            {"id": "pheno_gynecomastia_risk", "label": "Glandular Gynecomastia & Estrogenic Breast Tissue Proliferation Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.85},
            {"id": "pheno_fluid_retention", "label": "Estrogen-Mediated Renal Sodium & Subcutaneous Fluid Retention", "cat": "adverse_effect", "sev": "moderate", "mag": 0.75},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:pathway_raas_signaling|phys_arteriolar_tone|mineralocorticoid|phys_renal_k_sparing)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.5,
                "description": "Nuclear ER signaling transactivates renal sodium transport and hepatic renin substrate pathways",
            },
        ],
    },
    {
        "target_pattern": r"(?:erythropoietin|erythropoiesis|\bepo\b|red blood cell)",
        "target_name": "Renal Erythropoietin (EPO) Signaling",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_erythropoiesis",
            "label": "Renal Erythropoietin Synthesis & Bone Marrow Erythropoiesis",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_red_cell_mass",
            "label": "Red Blood Cell Accrual & Oxygen-Carrying Capacity",
            "organ": "Hematologic / Renal",
        },
        "biomarkers": [
            {"id": "bio_hematocrit", "label": "Blood Hematocrit", "unit": "%", "panel": "Hematology Panel", "lower": 38.5, "upper": 50.0, "mag": 0.85},
            {"id": "bio_hemoglobin", "label": "Hemoglobin Concentration", "unit": "g/dL", "panel": "Hematology Panel", "lower": 13.5, "upper": 17.5, "mag": 0.8},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.35},
        ],
        "phenotypes": [
            {"id": "pheno_erythrocytosis_hyperviscosity", "label": "Secondary Polycythemia, Elevated Hematocrit & Hyperviscosity Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.85},
        ],
    },
    {
        "target_pattern": r"(?:circulating.*testosterone|exogenous testosterone|testosterone replacement|serum testosterone pool)",
        "target_name": "Circulating Serum Testosterone Pool",
        "node_type": "target",
        "pathway": {
            "id": "pathway_testosterone_homeostasis",
            "label": "Systemic Circulating Androgen Homeostasis & Bioavailability",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_systemic_androgen_pool",
            "label": "Circulating Bioavailable Androgen Concentration",
            "organ": "Endocrine / Systemic",
        },
        "biomarkers": [
            {"id": "bio_testosterone", "label": "Total Serum Testosterone", "unit": "ng/dL", "panel": "Endocrine Panel", "lower": 300, "upper": 1000, "mag": 1.0},
        ],
        "phenotypes": [
            {"id": "pheno_androgen_replacement", "label": "Androgen Optimization & Hypogonadal Resolution", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:cyp19a1|aromatase|pathway_estrogen_biosynthesis|phys_estrogenic_tone|bio_estradiol)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.75,
                "description": "Circulating testosterone supplies substrate for peripheral CYP19A1 aromatization into 17β-estradiol",
            },
        ],
    },
    {
        "target_pattern": r"(?:cyp19a1|aromatase|estrogen synthase|anastrozole|letrozole|exemestane)",
        "target_name": "Aromatase (CYP19A1)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_aromatization",
            "label": "Cytochrome P450 Aromatase Estrogen Biosynthesis (R-HSA-211859)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_estrogenic_tone",
            "label": "Endogenous 17β-Estradiol Synthesis & Endothelial Preservation",
            "organ": "Endocrine / Systemic",
        },
        "biomarkers": [
            {"id": "bio_estradiol", "label": "Serum Estradiol (E2)", "unit": "pg/mL", "panel": "Endocrine Panel", "lower": 15.0, "upper": 45.0, "mag": 0.95},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.35},
            {"id": "bio_hdl_c", "label": "Serum HDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 90.0, "mag": 0.35},
        ],
        "phenotypes": [
            {"id": "pheno_estrogen_optimization", "label": "Physiological Estradiol & Joint/Vascular Protection", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            {"id": "pheno_gynecomastia_risk", "label": "Mammary Gland Estrogenic Proliferation & Gynecomastia Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.65},
            {"id": "pheno_hypoestrogenemia", "label": "Hypoestrogenic Joint Arthralgia & Atherogenic Dyslipidemia", "cat": "toxicity", "sev": "high", "mag": -0.85},
        ],
    },
    {
        "target_pattern": r"(?:hypothalamic-pituitary-gonadal|hpg|gnrh|gonadotropin|lh/fsh)",
        "target_name": "Hypothalamic-Pituitary-Gonadal (HPG) Axis",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_hpg_feedback",
            "label": "Hypothalamic GnRH Pulsatility & Pituitary Gonadotropin Secretion",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_gonadotropin_release",
            "label": "Pituitary LH/FSH Secretion & Endogenous Steroidogenesis",
            "organ": "Endocrine / Reproductive",
        },
        "biomarkers": [
            {"id": "bio_luteinizing_hormone", "label": "Luteinizing Hormone (LH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.5, "upper": 9.3, "mag": 0.85},
            {"id": "bio_fsh", "label": "Follicle-Stimulating Hormone (FSH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.4, "upper": 12.4, "mag": 0.8},
            {"id": "bio_testosterone", "label": "Total Serum Testosterone", "unit": "ng/dL", "panel": "Endocrine Panel", "lower": 300, "upper": 1000, "mag": 0.95},
        ],
        "phenotypes": [
            {"id": "pheno_hpg_axis_suppression", "label": "Endogenous HPG Axis Suppression & Secondary Hypogonadism", "cat": "toxicity", "sev": "high", "mag": -0.9},
        ],
    },
    {
        "target_pattern": r"(?:androgen|nr3c4|\bar\b|testosterone receptor)",
        "target_name": "Androgen Receptor (AR / NR3C4)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_androgen_transactivation",
            "label": "Nuclear Androgen Receptor Transactivation & Protein Synthesis",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_anabolic_trophism",
            "label": "Skeletal Muscle Myofibrillar Protein Accrual & Virilization",
            "organ": "Musculoskeletal / Endocrine",
        },
        "biomarkers": [
            {"id": "bio_luteinizing_hormone", "label": "Luteinizing Hormone (LH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.5, "upper": 9.3, "mag": -0.85},
            {"id": "bio_fsh", "label": "Follicle-Stimulating Hormone (FSH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.4, "upper": 12.4, "mag": -0.85},
            {"id": "bio_hematocrit", "label": "Blood Hematocrit", "unit": "%", "panel": "Hematology Panel", "lower": 38.5, "upper": 50.0, "mag": 0.6},
            {"id": "bio_hdl_c", "label": "Serum HDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 90.0, "mag": -0.65},
            {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50.0, "upper": 100.0, "mag": 0.55},
            {"id": "bio_triglycerides", "label": "Serum Triglycerides", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 150.0, "mag": 0.35},
        ],
        "phenotypes": [
            {"id": "pheno_muscle_hypertrophy", "label": "Enhanced Anabolic Muscle Mass & Bone Mineral Density", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
            {"id": "pheno_androgenic_alopecia", "label": "Follicular Miniaturization & Prostatic Hypertrophy Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.7},
        ],
        "bridges": [
            {
                "target_node_pattern": r"(?:at1|agtr1|angiotensin|pathway_raas_signaling|phys_arteriolar_tone)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.55,
                "description": "Androgen Receptor transactivation stimulates hepatic Angiotensinogen synthesis, activating downstream Angiotensin II / RAAS vasoconstrictor signaling",
            },
            {
                "target_node_pattern": r"(?:pathway_erythropoiesis|phys_red_cell_mass|bio_hematocrit|erythropoietin)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": 0.75,
                "description": "Renal Androgen Receptor activation stimulates renal Erythropoietin (EPO) secretion and bone marrow erythropoiesis",
            },
            {
                "target_node_pattern": r"(?:pathway_hpg_feedback|phys_gonadotropin_release|bio_luteinizing_hormone)",
                "edge_type": EdgeType.INHIBITS_PATHWAY,
                "vector_magnitude": -0.9,
                "description": "Elevated circulating androgens exert negative feedback at hypothalamic GnRH and pituitary gonadotrophs, suppressing LH and FSH secretion",
            },
        ],
    },
    {
        "target_pattern": r"(?:thyroid hormone receptor|thra|thrb|nr1a1|nr1a2|liothyronine|levothyroxine|\bt3\b|\bt4\b)",
        "target_name": "Thyroid Hormone Receptor Alpha & Beta (THRA/THRB / NR1A1/NR1A2)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_thyroid_hormone_signaling",
            "label": "Thyroid Hormone Receptor Transactivation & Basal Metabolic Uncoupling (R-HSA-9010553)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_metabolic_rate_thyroid",
            "label": "Basal Caloric Expenditure & Pituitary TSH Negative Feedback",
            "organ": "Endocrine / Metabolic",
        },
        "biomarkers": [
            {"id": "bio_tsh", "label": "Thyroid-Stimulating Hormone (TSH)", "unit": "mIU/L", "panel": "Endocrine Panel", "lower": 0.4, "upper": 4.0, "mag": -0.85},
            {"id": "bio_free_t3", "label": "Free Triiodothyronine (FT3)", "unit": "pg/mL", "panel": "Endocrine Panel", "lower": 2.3, "upper": 4.2, "mag": 0.85},
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.50},
        ],
        "phenotypes": [
            {"id": "pheno_hypermetabolism", "label": "Elevated Basal Metabolic Rate & Lipolysis", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            {"id": "pheno_tsh_suppression", "label": "Iatrogenic Pituitary TSH Shutdown & Secondary Hypothyroidism Risk", "cat": "toxicity", "sev": "high", "mag": -0.85},
        ],
    },
    {
        "target_pattern": r"(?:progesterone receptor|pgr\b|nr3c3|19-nor|nandrolone|trenbolone)",
        "target_name": "Progesterone Receptor (PGR / NR3C3)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_progesterone_signaling",
            "label": "Progesterone Receptor Transactivation & Pituitary Lactotroph Signaling",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_progestogenic_tone",
            "label": "Pituitary Prolactin Secretion & Mammary Gland Responsiveness",
            "organ": "Endocrine / Pituitary",
        },
        "biomarkers": [
            {"id": "bio_prolactin", "label": "Serum Prolactin", "unit": "ng/mL", "panel": "Endocrine Panel", "lower": 2.0, "upper": 18.0, "mag": 0.85},
            {"id": "bio_luteinizing_hormone", "label": "Luteinizing Hormone (LH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.5, "upper": 9.3, "mag": -0.75},
        ],
        "phenotypes": [
            {"id": "pheno_hyperprolactinemia", "label": "Progestogenic Hyperprolactinemia & Galactorrhea Risk", "cat": "toxicity", "sev": "high", "mag": 0.85},
        ],
    },
    {
        "target_pattern": r"(?:adra1|alpha-1|alpha_1|prazosin|tamsulosin|terazosin)",
        "target_name": "Alpha-1 Adrenergic Receptor (ADRA1A/1B/1D)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_alpha1_vasoconstriction",
            "label": "Gq/11 PLC-IP3/DAG Calcium Mobilization Cascade",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_vascular_tone",
            "label": "Arteriolar Smooth Muscle Tone & Prostatic Urethral Resistance",
            "organ": "Cardiovascular / Genitourinary",
        },
        "biomarkers": [
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.75},
        ],
        "phenotypes": [
            {"id": "pheno_antihypertensive", "label": "Smooth Muscle Relaxation & Blood Pressure Normalization", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.85},
            {"id": "pheno_orthostatic_hypotension", "label": "Postural Orthostatic Hypotension & Reflex Tachycardia", "cat": "adverse_effect", "sev": "moderate", "mag": -0.7},
        ],
    },
    {
        "target_pattern": r"(?:htr1a|htr2a|htr2c|5-ht1a|5-ht2a|5-ht2c)",
        "target_name": "Serotonin Receptors (5-HT1A/2A/2C)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_5ht_gpcr_signaling",
            "label": "Corticolimbic Serotonergic GPCR Signal Transduction",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_cortical_5ht_modulation",
            "label": "Prefrontal Neurotransmission & Limbic Affective Modulation",
            "organ": "Central Nervous System",
        },
        "biomarkers": [
            {"id": "bio_acetylcholine_cns", "label": "Central Neurotransmission Index", "unit": "index", "panel": "Neurologic Index", "lower": 50, "upper": 100, "mag": 0.7},
        ],
        "phenotypes": [
            {"id": "pheno_mood_stabilization", "label": "Affective Stabilization & Anxiolytic Modulation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
        ],
    },
    {
        "target_pattern": r"(?:nr3c1|glucocorticoid|cortisol receptor|dexamethasone|prednisone)",
        "target_name": "Glucocorticoid Receptor (GR / NR3C1)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_glucocorticoid_transactivation",
            "label": "Nuclear Glucocorticoid Response Transactivation & NF-kB Suppression",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_immunosuppression",
            "label": "Systemic Leukocyte Suppression & Hepatic Gluconeogenesis",
            "organ": "Immune / Endocrine",
        },
        "biomarkers": [
            {"id": "bio_acth", "label": "Adrenocorticotropic Hormone (ACTH)", "unit": "pg/mL", "panel": "Endocrine Panel", "lower": 7.2, "upper": 63.3, "mag": -0.85},
            {"id": "bio_cortisol", "label": "Serum Cortisol Concentration", "unit": "μg/dL", "panel": "Endocrine Panel", "lower": 6.0, "upper": 18.0, "mag": -0.85},
            {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": -0.8},
            {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70, "upper": 100, "mag": 0.7},
        ],
        "phenotypes": [
            {"id": "pheno_antiinflammatory", "label": "Potent Systemic Anti-Inflammatory Action", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.95},
            {"id": "pheno_hpa_suppression", "label": "Iatrogenic Cushingoid Features & HPA Axis Suppression", "cat": "toxicity", "sev": "high", "mag": -0.8},
        ],
    },
    {
        "target_pattern": r"(?:hepatic metabolic clearance|hepatobiliary system|cyp450 clearance|phase i/ii clearance|hepatocyte integrity)",
        "target_name": "Hepatic Metabolic Clearance & Hepatobiliary System",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_hepatic_metabolic_oxidations",
            "label": "Biological Oxidations & Phase I/II Xenobiotic Clearance (R-HSA-211859)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_hepatic_metabolic_load",
            "label": "Hepatocellular Metabolic Clearance & Canalicular Bile Transport",
            "organ": "Hepatic / Gastrointestinal",
        },
        "biomarkers": [
            {"id": "bio_alt", "label": "Alanine Aminotransferase (ALT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10.0, "upper": 45.0, "mag": 0.55},
            {"id": "bio_ast", "label": "Aspartate Aminotransferase (AST)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10.0, "upper": 40.0, "mag": 0.50},
            {"id": "bio_total_bilirubin", "label": "Total Serum Bilirubin", "unit": "mg/dL", "panel": "Hepatic Panel", "lower": 0.2, "upper": 1.2, "mag": 0.40},
            {"id": "bio_ggt", "label": "Gamma-Glutamyl Transferase (GGT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 9.0, "upper": 48.0, "mag": 0.45},
            {"id": "bio_alp", "label": "Alkaline Phosphatase (ALP)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 40.0, "upper": 129.0, "mag": 0.35},
        ],
        "phenotypes": [
            {"id": "pheno_hepatotoxicity_risk", "label": "Hepatocellular Stress, Transaminitis & Metabolic Overload", "cat": "adverse_effect", "sev": "high", "mag": 0.85},
            {"id": "pheno_cholestasis_risk", "label": "Canalicular Transporter Congestion & Biliary Strain Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.70},
        ],
    },
    {
        "target_pattern": r"(?:glomerular filtration|renal tubular transport|nephron clearance|renal hemodynamic stress)",
        "target_name": "Glomerular Filtration & Renal Tubular Transport",
        "node_type": "transporter",
        "pathway": {
            "id": "pathway_renal_tubular_transport",
            "label": "Glomerular Filtration & Tubular Secretion Dynamics (R-HSA-216083)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_renal_hemodynamic_stress",
            "label": "Glomerular Hydraulic Perfusion & Tubular Clearance Load",
            "organ": "Renal / Excretory",
        },
        "biomarkers": [
            {"id": "bio_serum_creatinine", "label": "Serum Creatinine", "unit": "mg/dL", "panel": "Renal Panel", "lower": 0.6, "upper": 1.3, "mag": 0.60},
            {"id": "bio_egfr", "label": "Estimated Glomerular Filtration Rate (eGFR)", "unit": "mL/min/1.73m²", "panel": "Renal Panel", "lower": 90.0, "upper": 125.0, "mag": -0.60},
            {"id": "bio_bun", "label": "Blood Urea Nitrogen (BUN)", "unit": "mg/dL", "panel": "Renal Panel", "lower": 7.0, "upper": 20.0, "mag": 0.50},
            {"id": "bio_cystatin_c", "label": "Serum Cystatin C", "unit": "mg/L", "panel": "Renal Panel", "lower": 0.5, "upper": 1.05, "mag": 0.55},
        ],
        "phenotypes": [
            {"id": "pheno_acute_kidney_injury_risk", "label": "Renal Hemodynamic Strain & Tubular Secretory Congestion", "cat": "adverse_effect", "sev": "high", "mag": 0.85},
            {"id": "pheno_nephroprotection", "label": "Glomerular Hyperfiltration Mitigation & Long-Term Renal Preservation", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.80},
        ],
    },
    {
        "target_pattern": r"(?:renal cytoprotection|glomerular perfusion|nephroprotection|renal protection|tubular protection)",
        "target_name": "Renal Tubular Cytoprotection & Glomerular Perfusion (NAC / ARB / ALA)",
        "node_type": "transporter",
        "pathway": {
            "id": "pathway_renal_cytoprotection",
            "label": "Glomerular Filtration Dynamics & Tubular Cytoprotection (R-HSA-216083)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_renal_protection_dynamics",
            "label": "Renal Perfusion Preservation & Tubular Antioxidant Defense",
            "organ": "Renal / Excretory",
        },
        "biomarkers": [
            {"id": "bio_egfr", "label": "Estimated Glomerular Filtration Rate (eGFR)", "unit": "mL/min/1.73m²", "panel": "Renal Panel", "lower": 90.0, "upper": 125.0, "mag": 0.60},
            {"id": "bio_serum_creatinine", "label": "Serum Creatinine", "unit": "mg/dL", "panel": "Renal Panel", "lower": 0.6, "upper": 1.3, "mag": -0.60},
            {"id": "bio_bun", "label": "Blood Urea Nitrogen (BUN)", "unit": "mg/dL", "panel": "Renal Panel", "lower": 7.0, "upper": 20.0, "mag": -0.50},
            {"id": "bio_cystatin_c", "label": "Serum Cystatin C", "unit": "mg/L", "panel": "Renal Panel", "lower": 0.5, "upper": 1.05, "mag": -0.55},
        ],
        "phenotypes": [
            {"id": "pheno_nephroprotection", "label": "Glomerular Perfusion Preservation & Tubular Cytoprotection", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
        ],
    },
    {
        "target_pattern": r"(?:cellular redox homeostasis|ros detoxification|oxidative stress|mitochondrial bioenergetics)",
        "target_name": "Cellular Redox Homeostasis & Mitochondrial Bioenergetics",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_ros_detoxification",
            "label": "Detoxification of Reactive Oxygen Species & Nrf2-ARE Signaling (R-HSA-3299685)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_oxidative_stress_redox_tone",
            "label": "Systemic Redox Homeostasis & Mitochondrial Respiratory Coupling",
            "organ": "Systemic / Mitochondrial",
        },
        "biomarkers": [
            {"id": "bio_gsh_redox_ratio", "label": "Glutathione Redox Index (GSH:GSSG)", "unit": "index", "panel": "Redox Panel", "lower": 80.0, "upper": 120.0, "mag": -0.85},
            {"id": "bio_mda", "label": "Serum Malondialdehyde (MDA / Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 1.0, "upper": 2.5, "mag": 0.80},
            {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": 0.70},
        ],
        "phenotypes": [
            {"id": "pheno_oxidative_stress_mitochondrial_strain", "label": "Systemic Oxidative Stress, Lipid Peroxidation & Mitochondrial Strain", "cat": "adverse_effect", "sev": "moderate", "mag": 0.85},
        ],
    },
    {
        "target_pattern": r"(?:slc6a3|drd2|dopamine transporter|dopamine receptor|dat\b)",
        "target_name": "Dopamine Transporter & Receptors (SLC6A3 / DRD2)",
        "node_type": "transporter",
        "pathway": {
            "id": "pathway_dopaminergic_neurotransmission",
            "label": "Mesocorticolimbic Dopaminergic Neurotransmission (R-HSA-112316)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_mesolimbic_dopamine_tone",
            "label": "Prefrontal Executive Focus & Mesolimbic Motivational Tone",
            "organ": "Central Nervous System",
        },
        "biomarkers": [
            {"id": "bio_dopamine_tone", "label": "Central Dopaminergic Tone Index", "unit": "index", "panel": "Neurologic Index", "lower": 40.0, "upper": 90.0, "mag": 0.85},
            {"id": "bio_prolactin", "label": "Serum Prolactin", "unit": "ng/mL", "panel": "Endocrine Panel", "lower": 2.0, "upper": 18.0, "mag": -0.75},
            {"id": "bio_cns_arousal", "label": "Central CNS Arousal State", "unit": "index", "panel": "Neurologic Index", "lower": 40.0, "upper": 80.0, "mag": 0.70},
        ],
        "phenotypes": [
            {"id": "pheno_executive_function", "label": "Enhanced Executive Focus & Dopaminergic Vigilance", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            {"id": "pheno_hyperprolactinemia", "label": "Dopamine Disinhibition Hyperprolactinemia & Galactorrhea Risk", "cat": "adverse_effect", "sev": "moderate", "mag": -0.80},
        ],
    },
    {
        "target_pattern": r"(?:pde5|pde-5|phosphodiesterase 5|tadalafil|sildenafil|vardenafil)",
        "target_name": "Phosphodiesterase 5A (PDE5)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_cgmp_pde5_signaling",
            "label": "Nitric Oxide / cGMP Signaling & PDE5 Breakdown (R-HSA-111469)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_vascular_smooth_muscle_relaxation",
            "label": "Vascular Endothelial Nitric Oxide & Smooth Muscle Relaxation",
            "organ": "Cardiovascular / Endothelial",
        },
        "biomarkers": [
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.45},
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.15},
        ],
        "phenotypes": [
            {"id": "pheno_endothelial_vasodilation", "label": "cGMP-Mediated Arteriolar Vasodilation & Endothelial Flow Enhancement", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            {"id": "pheno_hypotension_risk", "label": "Additive Hypotension & Syncope Vulnerability", "cat": "adverse_effect", "sev": "moderate", "mag": 0.65},
        ],
    },
    {
        "target_pattern": r"(?:astaxanthin|carotenoid free radical|nfe2l2|asta\b)",
        "target_name": "Lipophilic Carotenoid Free Radical Scavenging & Nrf2 Activation (Astaxanthin)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_nrf2_antioxidant_response",
            "label": "Nrf2-ARE Redox Signaling & Membrane Singlet Oxygen Quenching (R-HSA-3299685)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_carotenoid_membrane_antioxidant",
            "label": "Cellular Membrane Bilayer Stabilization & ROS Neutralization",
            "organ": "Systemic / Cellular Bilayer",
        },
        "biomarkers": [
            {"id": "bio_mda", "label": "Serum Malondialdehyde (MDA / Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 1.0, "upper": 2.5, "mag": -0.85},
            {"id": "bio_gsh_redox_ratio", "label": "Glutathione Redox Index (GSH:GSSG)", "unit": "index", "panel": "Redox Panel", "lower": 80.0, "upper": 120.0, "mag": 0.80},
            {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": -0.75},
        ],
        "phenotypes": [
            {"id": "pheno_lipid_peroxidation_inhibition", "label": "Inhibition of Membrane Lipid Peroxidation & Singlet Oxygen Cytoprotection", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            {"id": "pheno_antiinflammatory", "label": "Systemic hs-CRP & Inflammatory Cascade Attenuation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
        ],
    },
    {
        "target_pattern": r"(?:mitochondrial ubiquinone|coq10|ubiquinol|ubiquinone|coq2)",
        "target_name": "Mitochondrial Ubiquinone Electron Transport & Bioenergetics (CoQ10 / Ubiquinol)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_mitochondrial_electron_transport",
            "label": "Mitochondrial Respiratory Electron Transport & ATP Synthesis (R-HSA-163200)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_mitochondrial_bioenergetics",
            "label": "Myocardial & Intracellular Bioenergetic Coupling",
            "organ": "Cardiovascular / Mitochondrial",
        },
        "biomarkers": [
            {"id": "bio_gsh_redox_ratio", "label": "Glutathione Redox Index (GSH:GSSG)", "unit": "index", "panel": "Redox Panel", "lower": 80.0, "upper": 120.0, "mag": 0.75},
            {"id": "bio_mda", "label": "Serum Malondialdehyde (MDA / Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 1.0, "upper": 2.5, "mag": -0.70},
            {"id": "bio_nt_probnp", "label": "N-Terminal Pro-B-Type Natriuretic Peptide (NT-proBNP)", "unit": "pg/mL", "panel": "Cardiovascular Panel", "lower": 0.0, "upper": 125.0, "mag": -0.40},
        ],
        "phenotypes": [
            {"id": "pheno_mitochondrial_atp_enhancement", "label": "Mitochondrial ATP Regeneration & Myocardial Redox Defense", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
        ],
    },
    {
        "target_pattern": r"(?:silymarin|milk thistle|silybin|hepatocellular silymarin|polr1a)",
        "target_name": "Hepatocellular Silymarin Membrane Stabilization & Protein Synthesis (Milk Thistle)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_hepatocellular_regeneration",
            "label": "RNA Polymerase I Transcription & Hepatocyte Regeneration (R-HSA-8877330)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_hepatocyte_membrane_preservation",
            "label": "Hepatocyte Plasma Membrane Stabilization & Free Radical Defense",
            "organ": "Hepatic Parenchymal",
        },
        "biomarkers": [
            {"id": "bio_alt", "label": "Alanine Aminotransferase (ALT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10.0, "upper": 45.0, "mag": -0.70},
            {"id": "bio_ast", "label": "Aspartate Aminotransferase (AST)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10.0, "upper": 40.0, "mag": -0.65},
            {"id": "bio_ggt", "label": "Gamma-Glutamyl Transferase (GGT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 9.0, "upper": 48.0, "mag": -0.55},
            {"id": "bio_mda", "label": "Serum Malondialdehyde (MDA / Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 1.0, "upper": 2.5, "mag": -0.60},
        ],
        "phenotypes": [
            {"id": "pheno_hepatoprotection", "label": "Hepatocellular Membrane Stabilization & Transaminase Protection", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
        ],
    },
    {
        "target_pattern": r"(?:curcumin|nfkb1|nf-kb suppression|polyphenolic nf-kb)",
        "target_name": "Polyphenolic NF-κB & Inflammatory Cytokine Suppression (Curcumin)",
        "node_type": "enzyme",
        "pathway": {
            "id": "pathway_nfkb_inflammatory_signaling",
            "label": "NF-kB RelA/p50 Complex Translocation & Pro-Inflammatory Cytokine Gene Regulation (R-HSA-446203)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_systemic_inflammatory_tone",
            "label": "Systemic Endothelial & Synovial Inflammatory Cascades",
            "organ": "Systemic Endothelial / Immune",
        },
        "biomarkers": [
            {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": 0.85},
            {"id": "bio_mda", "label": "Serum Malondialdehyde (MDA / Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 1.0, "upper": 2.5, "mag": 0.65},
        ],
        "phenotypes": [
            {"id": "pheno_antiinflammatory", "label": "Systemic hs-CRP & Inflammatory Cytokine Attenuation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
        ],
    },
    {
        "target_pattern": r"(?:canalicular bile salt|bsep|abcb11|gpbar1|tgr5|tudca|bile acid export)",
        "target_name": "Canalicular Bile Salt Export & Hepatoprotection (TUDCA / BSEP / ABCB11)",
        "node_type": "transporter",
        "pathway": {
            "id": "pathway_canalicular_bile_secretion",
            "label": "Bile Salt Export Pump (BSEP) Canalicular Transport & ER Stress Mitigation (R-HSA-194068)",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_canalicular_biliary_flow",
            "label": "Canalicular Biliary Clearance & Hepatoprotective Flow Dynamics",
            "organ": "Hepatic / Biliary",
        },
        "biomarkers": [
            {"id": "bio_total_bilirubin", "label": "Total Serum Bilirubin", "unit": "mg/dL", "panel": "Hepatic Panel", "lower": 0.2, "upper": 1.2, "mag": -0.75},
            {"id": "bio_alt", "label": "Alanine Aminotransferase (ALT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10.0, "upper": 45.0, "mag": -0.65},
            {"id": "bio_ast", "label": "Aspartate Aminotransferase (AST)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10.0, "upper": 40.0, "mag": -0.60},
            {"id": "bio_ggt", "label": "Gamma-Glutamyl Transferase (GGT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 9.0, "upper": 48.0, "mag": -0.70},
            {"id": "bio_alp", "label": "Alkaline Phosphatase (ALP)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 40.0, "upper": 129.0, "mag": -0.55},
        ],
        "phenotypes": [
            {"id": "pheno_cholestasis_mitigation", "label": "Relief of Canalicular Bile Stasis, Hepatocellular Membrane Protection & ER Stress Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            {"id": "pheno_hepatoprotection", "label": "Transaminase Normalization & Parenchymal Hepatoprotection", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
        ],
    },
]


# -----------------------------------------------------------------------------
# Deterministic Biomedical Target Ontology Registry (UniProt / HGNC / ChEMBL)
# Zero regex heuristics: indexed by UniProt Accession, HGNC Gene Symbol, and ChEMBL ID
# -----------------------------------------------------------------------------

TARGET_REGISTRY: List[Dict[str, Any]] = [
    {
        "gene_symbol": "GABRA1",
        "uniprot_ids": ["P14867"],
        "chembl_target_ids": ["CHEMBL2094111", "CHEMBL2111394"],
        "canonical_name": "Gamma-Aminobutyric Acid Type A Receptor Subunit Alpha-1 (GABRA1)",
        "aliases": ["gabra1", "gaba-a", "gaba a receptor", "gaba_a", "gaba-a receptor complex", "gaba receptor"],
    },
    {
        "gene_symbol": "CYP19A1",
        "uniprot_ids": ["P11511"],
        "chembl_target_ids": ["CHEMBL1978"],
        "canonical_name": "Aromatase (CYP19A1)",
        "aliases": ["aromatase", "cyp19a1", "estrogen synthase", "cytochrome p450 19a1"],
    },
    {
        "gene_symbol": "AR",
        "uniprot_ids": ["P10275"],
        "chembl_target_ids": ["CHEMBL1871"],
        "canonical_name": "Androgen Receptor (AR / NR3C4)",
        "aliases": ["androgen receptor", "ar", "nr3c4", "dihydrotestosterone receptor"],
    },
    {
        "gene_symbol": "TESTOSTERONE_POOL",
        "uniprot_ids": [],
        "chembl_target_ids": [],
        "canonical_name": "Circulating Serum Testosterone Pool",
        "aliases": ["circulating serum testosterone pool", "circulating testosterone pool", "exogenous testosterone pool", "serum testosterone pool", "circulating testosterone"],
    },
    {
        "gene_symbol": "ESR1",
        "uniprot_ids": ["P03372"],
        "chembl_target_ids": ["CHEMBL206"],
        "canonical_name": "Estrogen Receptor Alpha (ESR1 / ER-Alpha)",
        "aliases": ["estrogen receptor alpha", "esr1", "er-alpha", "eralpha"],
    },
    {
        "gene_symbol": "ESR2",
        "uniprot_ids": ["Q92731"],
        "chembl_target_ids": ["CHEMBL242"],
        "canonical_name": "Estrogen Receptor Beta (ESR2 / ER-Beta)",
        "aliases": ["estrogen receptor beta", "esr2", "er-beta", "erbeta"],
    },
    {
        "gene_symbol": "PGR",
        "uniprot_ids": ["P06401"],
        "chembl_target_ids": ["CHEMBL240"],
        "canonical_name": "Progesterone Receptor (PGR)",
        "aliases": ["progesterone receptor", "pgr", "nr3c3", "progestin receptor"],
    },
    {
        "gene_symbol": "TH",
        "uniprot_ids": ["P07101"],
        "chembl_target_ids": ["CHEMBL3525"],
        "canonical_name": "Tyrosine Hydroxylase (TH)",
        "aliases": ["tyrosine hydroxylase", "th", "tyrosine 3-monooxygenase"],
    },
    {
        "gene_symbol": "SRD5A1",
        "uniprot_ids": ["P18405", "P31213"],
        "chembl_target_ids": ["CHEMBL1782", "CHEMBL1783"],
        "canonical_name": "5-Alpha Reductase Subtype 1 & 2",
        "aliases": ["5-alpha reductase", "srd5a1", "srd5a2", "steroid 5-alpha reductase", "5ar"],
    },
    {
        "gene_symbol": "EPO",
        "uniprot_ids": ["P01588", "P19235"],
        "chembl_target_ids": ["CHEMBL3714088"],
        "canonical_name": "Renal Erythropoietin (EPO) Signaling",
        "aliases": ["erythropoietin", "epo", "erythropoietin receptor", "epor"],
    },
    {
        "gene_symbol": "SHBG",
        "uniprot_ids": ["P04278"],
        "chembl_target_ids": ["CHEMBL2530"],
        "canonical_name": "Sex Hormone-Binding Globulin (SHBG)",
        "aliases": ["shbg", "sex hormone binding globulin", "sex hormone-binding globulin"],
    },
    {
        "gene_symbol": "ADRB1",
        "uniprot_ids": ["P08588"],
        "chembl_target_ids": ["CHEMBL213"],
        "canonical_name": "Beta-1 Adrenergic Receptor (ADRB1)",
        "aliases": ["beta-1 adrenergic", "beta 1 adrenergic", "adrb1", "beta-1 receptor"],
    },
    {
        "gene_symbol": "ADRB2",
        "uniprot_ids": ["P07550"],
        "chembl_target_ids": ["CHEMBL210"],
        "canonical_name": "Beta-2 Adrenergic Receptor (ADRB2)",
        "aliases": ["beta-2 adrenergic", "beta 2 adrenergic", "adrb2", "beta-2 receptor"],
    },
    {
        "gene_symbol": "ADRA2A",
        "uniprot_ids": ["P08913"],
        "chembl_target_ids": ["CHEMBL241"],
        "canonical_name": "Alpha-2A Adrenergic Receptor (ADRA2A)",
        "aliases": ["alpha-2a adrenergic", "alpha 2a adrenergic", "adra2a", "alpha-2a receptor"],
    },
    {
        "gene_symbol": "ADRA2B",
        "uniprot_ids": ["P18089"],
        "chembl_target_ids": ["CHEMBL243"],
        "canonical_name": "Alpha-2B Adrenergic Receptor (ADRA2B)",
        "aliases": ["alpha-2b adrenergic", "alpha 2b adrenergic", "adra2b"],
    },
    {
        "gene_symbol": "ADRA2C",
        "uniprot_ids": ["P18825"],
        "chembl_target_ids": ["CHEMBL244"],
        "canonical_name": "Alpha-2C Adrenergic Receptor (ADRA2C)",
        "aliases": ["alpha-2c adrenergic", "alpha 2c adrenergic", "adra2c"],
    },
    {
        "gene_symbol": "ADRA1A",
        "uniprot_ids": ["P35348"],
        "chembl_target_ids": ["CHEMBL225"],
        "canonical_name": "Alpha-1A Adrenergic Receptor (ADRA1A)",
        "aliases": ["alpha-1a adrenergic", "alpha 1a adrenergic", "adra1a"],
    },
    {
        "gene_symbol": "AGTR1",
        "uniprot_ids": ["P30556"],
        "chembl_target_ids": ["CHEMBL228"],
        "canonical_name": "Angiotensin II Type-1 Receptor (AGTR1)",
        "aliases": [
            "angiotensin ii type-1",
            "type-1 angiotensin ii receptor",
            "type-1 angiotensin ii receptor a",
            "type-1 angiotensin ii receptor b",
            "type 1 angiotensin ii receptor",
            "type-1 angiotensin",
            "at1 receptor",
            "agtr1",
            "angiotensin receptor",
            "angiotensin ii receptor",
        ],
    },
    {
        "gene_symbol": "AGT",
        "uniprot_ids": ["P01019"],
        "chembl_target_ids": ["CHEMBL2835"],
        "canonical_name": "Angiotensinogen (AGT / Hepatic RAAS Precursor)",
        "aliases": [
            "angiotensinogen",
            "hepatic angiotensinogen",
            "hepatic angiotensinogen / raas cascade",
            "agt",
            "raas precursor",
            "raas",
        ],
    },
    {
        "gene_symbol": "PPARG",
        "uniprot_ids": ["P37231"],
        "chembl_target_ids": ["CHEMBL235"],
        "canonical_name": "Peroxisome Proliferator-Activated Receptor Gamma (PPARG)",
        "aliases": ["pparg", "ppar-gamma", "ppargamma", "peroxisome proliferator-activated receptor gamma"],
    },
    {
        "gene_symbol": "NR3C2",
        "uniprot_ids": ["P08235"],
        "chembl_target_ids": ["CHEMBL2034"],
        "canonical_name": "Mineralocorticoid Receptor (NR3C2)",
        "aliases": ["mineralocorticoid receptor", "aldosterone receptor", "nr3c2"],
    },
    {
        "gene_symbol": "KCNH2",
        "uniprot_ids": ["Q12809"],
        "chembl_target_ids": ["CHEMBL240"],
        "canonical_name": "Voltage-Gated Potassium Channel (hERG / KCNH2)",
        "aliases": ["herg", "kcnh2", "potassium voltage-gated channel subfamily h member 2"],
    },
    {
        "gene_symbol": "GLP1R",
        "uniprot_ids": ["P43220"],
        "chembl_target_ids": ["CHEMBL1784"],
        "canonical_name": "GLP-1 Receptor (GLP1R)",
        "aliases": ["glp-1 receptor", "glp1r", "glucagon-like peptide 1 receptor"],
    },
    {
        "gene_symbol": "PDE5A",
        "uniprot_ids": ["O76074"],
        "chembl_target_ids": ["CHEMBL1827", "CHEMBL1824"],
        "canonical_name": "Phosphodiesterase 5A (PDE5)",
        "aliases": ["pde5", "pde5a", "phosphodiesterase 5a", "cgmp-specific 3',5'-cyclic phosphodiesterase"],
    },
    {
        "gene_symbol": "SLC6A4",
        "uniprot_ids": ["P31645"],
        "chembl_target_ids": ["CHEMBL228"],
        "canonical_name": "Serotonin Transporter (SERT / SLC6A4)",
        "aliases": ["sert", "slc6a4", "serotonin transporter", "sodium-dependent serotonin transporter"],
    },
    {
        "gene_symbol": "SLC6A3",
        "uniprot_ids": ["Q01959"],
        "chembl_target_ids": ["CHEMBL238"],
        "canonical_name": "Dopamine Transporter (DAT / SLC6A3)",
        "aliases": ["dat", "slc6a3", "dopamine transporter", "sodium-dependent dopamine transporter"],
    },
    {
        "gene_symbol": "GABRA1",
        "uniprot_ids": ["P14867"],
        "chembl_target_ids": ["CHEMBL2094112"],
        "canonical_name": "GABA-A Receptor (GABRA1)",
        "aliases": ["gaba-a", "gabra1", "gaba a", "gamma-aminobutyric acid receptor subunit alpha-1"],
    },
    {
        "gene_symbol": "OPRM1",
        "uniprot_ids": ["P35372"],
        "chembl_target_ids": ["CHEMBL233"],
        "canonical_name": "Mu-Opioid Receptor (OPRM1)",
        "aliases": ["mu-opioid", "oprm1", "mu opioid receptor", "morphine receptor"],
    },
    {
        "gene_symbol": "HTR1A",
        "uniprot_ids": ["P08908"],
        "chembl_target_ids": ["CHEMBL214"],
        "canonical_name": "5-HT1A Receptor (HTR1A)",
        "aliases": ["5-ht1a", "htr1a", "5-hydroxytryptamine receptor 1a", "serotonin 1a receptor"],
    },
    {
        "gene_symbol": "ADORA1",
        "uniprot_ids": ["P30542", "P29274"],
        "chembl_target_ids": ["CHEMBL226", "CHEMBL251"],
        "canonical_name": "Adenosine A1/A2A Receptor",
        "aliases": ["a1 receptor", "a2a receptor", "adenosine a1", "adenosine a2a", "adora1", "adora2a", "adenosine receptor", "a1", "a2a"],
    },
    {
        "gene_symbol": "SLC5A2",
        "uniprot_ids": ["P31639"],
        "chembl_target_ids": ["CHEMBL1963778"],
        "canonical_name": "Sodium-Glucose Cotransporter 2 (SGLT2 / SLC5A2)",
        "aliases": ["sglt2", "slc5a2", "sodium/glucose cotransporter 2"],
    },
    {
        "gene_symbol": "SLC7A11",
        "uniprot_ids": ["Q16478", "P48506", "P48507", "Q16236"],
        "chembl_target_ids": ["CHEMBL3714090"],
        "canonical_name": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)",
        "aliases": [
            "glutathione synthesis system",
            "cystine-glutamate antiporter (system xc-)",
            "system xc-",
            "slc7a11",
            "gclc",
            "gclm",
            "nrf2",
            "nfe2l2",
            "glutathione biosynthesis",
            "glutathione",
            "antioxidant defense",
        ],
    },
    {
        "gene_symbol": "NFE2L2",
        "uniprot_ids": ["Q16236"],
        "chembl_target_ids": [],
        "canonical_name": "Nuclear Factor Erythroid 2-Related Factor 2 (Nrf2 / NFE2L2)",
        "aliases": ["nrf2", "nfe2l2", "astaxanthin", "carotenoid free radical"],
    },
    {
        "gene_symbol": "COQ2",
        "uniprot_ids": ["Q96H96"],
        "chembl_target_ids": [],
        "canonical_name": "Mitochondrial Ubiquinone Electron Transport & Bioenergetics (CoQ10 / Ubiquinol)",
        "aliases": ["coq2", "coq10", "ubiquinol", "ubiquinone", "coenzyme q10"],
    },
    {
        "gene_symbol": "POLR1A",
        "uniprot_ids": ["O95602"],
        "chembl_target_ids": [],
        "canonical_name": "RNA Polymerase I Subunit A (POLR1A / Silymarin)",
        "aliases": ["polr1a", "silymarin", "silybin", "milk thistle"],
    },
    {
        "gene_symbol": "NFKB1",
        "uniprot_ids": ["P19838"],
        "chembl_target_ids": [],
        "canonical_name": "Nuclear Factor NF-kappa-B p50 Subunit (NFKB1)",
        "aliases": ["nfkb1", "nf-kb", "curcumin", "nfkb"],
    },
    {
        "gene_symbol": "GPBAR1",
        "uniprot_ids": ["Q8TDU6"],
        "chembl_target_ids": ["CHEMBL5075"],
        "canonical_name": "G-Protein Coupled Bile Acid Receptor 1 (TGR5 / GPBAR1)",
        "aliases": ["tgr5", "gpbar1", "tudca", "bile acid receptor"],
    },
    {
        "gene_symbol": "ABCB11",
        "uniprot_ids": ["O95342"],
        "chembl_target_ids": [],
        "canonical_name": "Bile Salt Export Pump (BSEP / ABCB11)",
        "aliases": ["bsep", "abcb11", "biliary transport"],
    },
    {
        "gene_symbol": "PRKAA1",
        "uniprot_ids": ["Q13131"],
        "chembl_target_ids": ["CHEMBL2148"],
        "canonical_name": "AMP-Activated Protein Kinase (AMPK / PRKAA1)",
        "aliases": ["ampk", "prkaa1", "amp-activated protein kinase"],
    },
    {
        "gene_symbol": "MTNR1A",
        "uniprot_ids": ["P48039"],
        "chembl_target_ids": ["CHEMBL237"],
        "canonical_name": "Melatonin Receptor 1A (MT1 / MTNR1A)",
        "aliases": ["mt1", "mtnr1a", "melatonin receptor 1a"],
    },
    {
        "gene_symbol": "MTNR1B",
        "uniprot_ids": ["P49286"],
        "chembl_target_ids": ["CHEMBL238"],
        "canonical_name": "Melatonin Receptor 1B (MT2 / MTNR1B)",
        "aliases": ["mt2", "mtnr1b", "melatonin receptor 1b"],
    },
]

# Build high-speed O(1) identifier index
TARGET_LOOKUP_INDEX: Dict[str, Dict[str, Any]] = {}
for _target_entry in TARGET_REGISTRY:
    for _uid in _target_entry.get("uniprot_ids", []):
        TARGET_LOOKUP_INDEX[_uid.lower()] = _target_entry
    for _cid in _target_entry.get("chembl_target_ids", []):
        TARGET_LOOKUP_INDEX[_cid.lower()] = _target_entry
    TARGET_LOOKUP_INDEX[_target_entry["gene_symbol"].lower()] = _target_entry
    for _alias in _target_entry.get("aliases", []):
        TARGET_LOOKUP_INDEX[canonicalize_match_token(_alias)] = _target_entry


CASCADE_EXACT_GENE_SYMBOLS: Dict[str, List[str]] = {
    "Alpha-2 Adrenergic Receptor (ADRA2A/2B/2C)": ["ADRA2A", "ADRA2B", "ADRA2C"],
    "Adenosine A1/A2A Receptor": ["ADORA1", "ADORA2A"],
    "Skeletal Muscle ATP-PCr System": ["CKMT2", "CKM"],
    "GABA-A Receptor Complex": ["GABRA1"],
    "Angiotensin II Type-1 (AT1) Receptor / ACE": ["AGTR1", "ACE", "AGT"],
    "Mineralocorticoid Receptor (Aldosterone Receptor / NR3C2)": ["NR3C2"],
    "HMG-CoA Reductase": ["HMGCR", "PRKAA1"],
    "Dopamine / Norepinephrine Transporter (DAT/NET)": ["SLC6A3", "SLC6A2", "DRD2", "TH"],
    "Serotonin Transporter (SERT / SLC6A4)": ["SLC6A4"],
    "Aromatase (CYP19A1)": ["CYP19A1"],
    "5-Alpha Reductase Subtype 1 & 2": ["SRD5A1", "SRD5A2"],
    "Androgen Receptor (AR / NR3C4)": ["AR"],
    "Glucocorticoid Receptor (GR / NR3C1)": ["NR3C1"],
    "Beta-1 Adrenergic Receptor (ADRB1)": ["ADRB1"],
    "Beta-2 Adrenergic Receptor (ADRB2)": ["ADRB2"],
    "L-Type Voltage-Gated Calcium Channel (CACNA1C)": ["CACNA1C"],
    "Coagulation Cascade (Thrombin / Factor Xa / Platelet P2Y12)": ["F2", "F10", "P2RY12"],
    "Muscarinic Acetylcholine Receptors (CHRM1-5)": ["CHRM1", "CHRM2", "CHRM3", "CHRM4", "CHRM5"],
    "Cyclooxygenase 1 & 2 (COX-1/2)": ["PTGS1", "PTGS2"],
    "Mu-Opioid Receptor (OPRM1)": ["OPRM1"],
    "Peroxisome Proliferator-Activated Receptor (PPAR-γ/α/δ)": ["PPARG", "PPARA", "PPARD"],
    "Sodium-Glucose Cotransporter 2 (SGLT2 / SLC5A2)": ["SLC5A2"],
    "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)": ["SLC7A11", "GCLC", "GCLM", "GPX1", "SOD1", "SOD2", "CAT"],
    "Voltage-Gated Potassium Channel (hERG / KCNH2 / IKr)": ["KCNH2"],
    "Phosphodiesterase 5A (PDE5)": ["PDE5A"],
    "Lipophilic Carotenoid Free Radical Scavenging & Nrf2 Activation (Astaxanthin)": ["NFE2L2"],
    "Mitochondrial Ubiquinone Electron Transport & Bioenergetics (CoQ10 / Ubiquinol)": ["COQ2"],
    "Hepatocellular Silymarin Membrane Stabilization & Protein Synthesis (Milk Thistle)": ["POLR1A"],
    "Polyphenolic NF-κB & Inflammatory Cytokine Suppression (Curcumin)": ["NFKB1", "PTGS2"],
    "Canalicular Bile Salt Export & Hepatoprotection (TUDCA / BSEP / ABCB11)": ["ABCB11", "GPBAR1"],
    "Hepatic Metabolic Clearance & Hepatobiliary System": ["CYP3A4", "CYP2D6", "CYP1A2", "CYP2C9"],
    "Glomerular Filtration & Renal Tubular Transport": ["SLC22A2", "SLC22A6", "SLC22A8"],
    "Cellular Redox Homeostasis & Mitochondrial Bioenergetics": ["NOX1", "NOX2", "NOX4", "CYP2E1", "MAOA", "MAOB"],
}

# Build high-speed exact O(1) identifier index for Target Cascades (Zero regexes)
EXACT_CASCADE_LOOKUP: Dict[str, Dict[str, Any]] = {}
for _cascade in CANONICAL_TARGET_CASCADES:
    _t_name = _cascade.get("target_name", "")
    if _t_name:
        EXACT_CASCADE_LOOKUP[_t_name.lower()] = _cascade
        EXACT_CASCADE_LOOKUP[canonicalize_match_token(_t_name)] = _cascade

    # Map gene symbols and their exact UniProt/ChEMBL identifiers to this cascade
    _genes = CASCADE_EXACT_GENE_SYMBOLS.get(_t_name, [])
    for _gene in _genes:
        EXACT_CASCADE_LOOKUP[_gene.lower()] = _cascade
        # Find all registry entries matching this gene symbol
        for _reg in TARGET_REGISTRY:
            if _reg.get("gene_symbol", "").upper() == _gene.upper():
                for _uid in _reg.get("uniprot_ids", []):
                    EXACT_CASCADE_LOOKUP[_uid.lower()] = _cascade
                for _cid in _reg.get("chembl_target_ids", []):
                    EXACT_CASCADE_LOOKUP[_cid.lower()] = _cascade
                for _alias in _reg.get("aliases", []):
                    EXACT_CASCADE_LOOKUP[_alias.lower()] = _cascade
                    EXACT_CASCADE_LOOKUP[canonicalize_match_token(_alias)] = _cascade

    # Index explicit identifiers if defined
    for _key in _cascade.get("exact_identifiers", []):
        EXACT_CASCADE_LOOKUP[_key.lower()] = _cascade
        EXACT_CASCADE_LOOKUP[canonicalize_match_token(_key)] = _cascade


def get_exact_target_cascade_blueprint(
    target_name: str,
    gene_symbol: Optional[str] = None,
    uniprot_id: Optional[str] = None,
    chembl_target_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Zero-regex exact O(1) lookup of downstream signaling pathway, physiology, and biomarker cascade blueprints.
    Matches deterministically on UniProt Accession, HGNC Gene Symbol, ChEMBL Target ID, or Canonical Target Name.
    """
    candidates = [
        uniprot_id,
        chembl_target_id,
        gene_symbol,
        target_name,
    ]
    for cand in candidates:
        if not cand:
            continue
        c_str = str(cand).strip().lower()
        if c_str in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[c_str]
        c_tok = canonicalize_match_token(cand)
        if c_tok in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[c_tok]

    # Check via TARGET_LOOKUP_INDEX canonical normalization
    norm_name = _normalize_target_node_id(target_name, chembl_target_id, uniprot_id)
    if norm_name:
        if norm_name.lower() in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[norm_name.lower()]
        norm_tok = canonicalize_match_token(norm_name)
        if norm_tok in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[norm_tok]

    return None


def _normalize_target_node_id(
    raw_name: str,
    target_id: Optional[str] = None,
    accessions: Optional[str] = None,
) -> str:
    """
    Normalize molecular target to standard clinical node label using O(1) biomedical ontology indexing:
    1. UniProt Accession ID (e.g., P11511 -> Aromatase)
    2. ChEMBL Target ID (e.g., CHEMBL1978 -> Aromatase)
    3. HGNC Gene Symbol (e.g., CYP19A1 -> Aromatase)
    4. Exact Canonical Token Index
    """
    # 1. Check UniProt Accession
    if accessions:
        acc_tokens = str(accessions).replace(";", " ").replace(",", " ").split()
        for token in acc_tokens:
            entry = TARGET_LOOKUP_INDEX.get(token.lower())
            if entry:
                return entry["canonical_name"]

    # 2. Check ChEMBL Target ID
    if target_id:
        entry = TARGET_LOOKUP_INDEX.get(str(target_id).strip().lower())
        if entry:
            return entry["canonical_name"]

    # 3. Check HGNC / Exact Alias Token
    clean_token = canonicalize_match_token(raw_name)
    if clean_token in TARGET_LOOKUP_INDEX:
        return TARGET_LOOKUP_INDEX[clean_token]["canonical_name"]

    # 4. Partial substring key lookup across registered standard targets
    for key, entry in TARGET_LOOKUP_INDEX.items():
        if len(key) >= 3 and (key in clean_token or (len(clean_token) >= 4 and clean_token in key)):
            return entry["canonical_name"]

    cleaned = str(raw_name or "").strip()
    return cleaned


from app.services.dosing_service import CLINICAL_REFERENCE_DOSES_MG, get_default_compound_dose

DEFAULT_THERAPEUTIC_DOSES_MG: Dict[str, float] = CLINICAL_REFERENCE_DOSES_MG


def is_steroidal_androgen(compound: Dict[str, Any]) -> bool:
    """Determine if a compound is a steroidal androgen from its drug class, mechanism, or structure."""
    drug_class = str(compound.get("drug_class") or "").lower()
    mech = str(compound.get("mechanism") or "").lower()
    cats = [str(c).lower() for c in (compound.get("categories") or [])]
    all_text = f"{drug_class} {mech} {' '.join(cats)}"
    
    if any(k in all_text for k in ["aromatase inhibitor", "glucocorticoid", "mineralocorticoid", "corticosteroid", "estrogen receptor modulator", "serm"]):
        return False
    if any(k in all_text for k in ["androgen", "anabolic", "androstan"]):
        if any(k in all_text for k in ["non-steroidal", "sarm", "selective androgen receptor", "antiandrogen", "androgen receptor antagonist"]):
            return False
        return True
    return False


def is_aromatizable_androgen(compound: Dict[str, Any]) -> bool:
    """
    Determine if a compound is chemically capable of being aromatized to estradiol by CYP19A1.
    CYP19A1 requires a steroidal C19-methyl Delta-4-3-one or 3-hydroxy-Delta-5 sterol A-ring structure
    (e.g., testosterone, androstenedione, boldenone, DHEA).
    
    Non-aromatizable compounds include:
    1. Non-steroidal AR agonists (SARMs: RAD140, LGD-4033, Ostarine, etc.)
    2. 5-Alpha reduced / Androstane DHT derivatives (Drostanolone, Oxandrolone, Stanozolol, Methenolone, Mesterolone)
    3. Highly conjugated / modified non-aromatizable 19-nor trienes (Trenbolone)
    """
    if not is_steroidal_androgen(compound):
        return False
    
    drug_class = str(compound.get("drug_class") or "").lower()
    mech = str(compound.get("mechanism") or "").lower()
    smiles = str(compound.get("smiles") or "")
    
    # 1. Check chemical classification / ATC taxonomy
    if "androstan" in drug_class or "dht" in drug_class or "dihydrotestosterone" in drug_class:
        return False
    if "androstan" in mech or "dht derivative" in mech:
        return False
    
    # 2. Check SMILES structural features for delta-4-3-one steroid ring
    if smiles:
        # Check for conjugated triene (e.g. trenbolone)
        if "C=CC3=C" in smiles or bool(re.search(r"=C\d*C=C\d*C=C", smiles)):
            return False
        # Check for delta-4-3-one enone (e.g., C4=CC(=O)CCC)
        has_delta4_enone = bool(re.search(r"(=CC\(=O\)|C\(=O\)C=C|C=C\d*C\(=O\)|C\(=O\)CCC\d*=C)", smiles, re.IGNORECASE))
        if not has_delta4_enone:
            return False
            
    return True


def is_5alpha_reductase_substrate(compound: Dict[str, Any]) -> bool:
    """
    Determine if a compound is a substrate for 5-Alpha Reductase (SRD5A1/2).
    5AR reduces the 4,5-double bond of Delta-4-3-keto steroids into 5-alpha reduced metabolites.
    5-alpha reduced androstanes, 19-nor trienes, and non-steroidal SARMs cannot undergo 5-alpha reduction.
    """
    if not is_steroidal_androgen(compound):
        return False
    drug_class = str(compound.get("drug_class") or "").lower()
    if "androstan" in drug_class or "dht" in drug_class or "dihydrotestosterone" in drug_class:
        return False
    return is_aromatizable_androgen(compound)


def build_selected_compound_graph(stack: List[Any], catalog_service: CatalogService | None = None) -> BiologicalGraph:
    """
    Builds a multi-tier dynamic biological cascade graph for the selected stack:
    Tier 1: Compound Nodes (with ADMET properties and specific dose)
    Tier 2: Molecular Target Nodes (Receptors, Enzymes, Transporters)
    Tier 3: Intracellular Signaling Pathway Nodes (Reactome)
    Tier 4: Organ & Physiological Function Nodes (with dynamic cross-talk bridges)
    Tier 5: Clinical Laboratory Biomarker Nodes
    Tier 6: Clinical Phenotype & Safety Outcome Nodes
    """
    service = catalog_service or CatalogService()
    
    # 1. Parse and standardize compound specifications
    parsed_items: List[Dict[str, Any]] = []
    for item in (stack or []):
        parsed = parse_compound_spec(item)
        if parsed.get("key"):
            parsed_items.append(parsed)

    # 2. Canonicalize and merge duplicate compounds/synonyms with dose aggregation
    merged_stack = service.canonicalize_and_merge_stack(parsed_items)

    if not merged_stack:
        return build_testosterone_alopecia_graph()

    # Pre-fetch stack compounds to evaluate stack-level endocrine context
    stack_compounds: List[Dict[str, Any]] = []
    for item in merged_stack:
        c_obj = service.get_compound(item.get("key") or "")
        if c_obj:
            stack_compounds.append(c_obj)

    has_bioidentical_test_in_stack = any(
        ("testosterone" in str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
         and not any(w in str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
                     for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd", "ostarine", "s-4", "yk-11"]))
        or "hcg" in str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
        for c in stack_compounds
    )

    graph = BiologicalGraph()

    for compound_entry in merged_stack:
        compound_key = compound_entry.get("key") or "compound"
        compound = service.get_compound(compound_key)

        dose_mg = float(compound_entry.get("dose_mg") if compound_entry.get("dose_mg") is not None else compound_entry.get("dose", 10.0))
        dose_str = str(compound_entry.get("dose_str") or (f"{dose_mg:g} mg" if dose_mg >= 1.0 else f"{dose_mg * 1000.0:g} μg"))

        if compound is None:
            graph.add_node(
                CompoundNode(
                    node_id=compound_key,
                    label=compound_key.title(),
                ),
                dose_mg=dose_mg,
                dose_str=dose_str,
            )
            continue

        compound_id = str(compound.get("key") or compound_key)
        compound_label = str(compound.get("name") or compound_id)

        # 1. Add Compound Node
        graph.add_node(
            CompoundNode(
                node_id=compound_id,
                label=compound_label,
                smiles=compound.get("smiles"),
                inchikey=compound.get("inchikey"),
                logP=compound.get("logp"),
                tpsa=compound.get("tpsa"),
                molecular_weight=compound.get("molecular_weight"),
                base_half_life=float(re.search(r"(\d+)", str(compound.get("half_life") or "")).group(1)) if re.search(r"(\d+)", str(compound.get("half_life") or "")) else None,
                drug_class=compound.get("drug_class"),
                is_narrow_therapeutic_index=bool(compound.get("is_narrow_therapeutic_index")),
            ),
            dose_mg=dose_mg,
            dose_str=dose_str,
            molecular_weight=compound.get("molecular_weight"),
            oral_bioavailability=compound.get("oral_bioavailability") or compound.get("bioavailability_f"),
            volume_of_distribution=compound.get("volume_of_distribution") or compound.get("volume_of_distribution_l_kg"),
            protein_binding=compound.get("protein_binding") or compound.get("protein_binding_pct"),
        )

        receptor_targets = list(compound.get("receptor_targets") or [])
        mechanism_text = str(compound.get("mechanism") or "").lower()
        c_name_lower = str(compound.get("canonical_name") or compound.get("name") or compound_key).lower()
        drug_class_lower = str(compound.get("drug_class") or "").lower()

        # Connect exogenous bioidentical testosterone to circulating hormone pool (while excluding synthetic derivatives)
        is_bioidentical_test = "testosterone" in c_name_lower and not any(w in c_name_lower for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd"])
        if is_bioidentical_test:
            if dose_mg <= 10.0:
                exo_efficacy = 0.62 * (max(0.1, dose_mg) / 10.0)
            else:
                exo_efficacy = 0.62 + 0.015 * (dose_mg - 10.0)
            
            existing_pool = next((t for t in receptor_targets if "circulating" in str(t.get("target", "")).lower() or "serum testosterone pool" in str(t.get("target", "")).lower()), None)
            if existing_pool:
                existing_pool["intrinsic_efficacy"] = exo_efficacy
                existing_pool["pre_computed_stress"] = True
            else:
                receptor_targets.insert(0, {
                    "target": "Circulating Serum Testosterone Pool",
                    "action": "agonist",
                    "family": "Endocrine Pool",
                    "affinity_ki": 1.0,
                    "intrinsic_efficacy": exo_efficacy,
                    "pre_computed_stress": True,
                })

            exo_arom_eff = 0.20 * (max(0.1, dose_mg) / 10.0) if dose_mg <= 10.0 else min(0.48, 0.20 + 0.0025 * (dose_mg - 10.0))
            existing_arom = next((t for t in receptor_targets if "aromatase" in str(t.get("target", "")).lower() or "cyp19a1" in str(t.get("target", "")).lower()), None)
            if existing_arom:
                existing_arom["intrinsic_efficacy"] = exo_arom_eff
                existing_arom["pre_computed_stress"] = True
            else:
                receptor_targets.append({
                    "target": "Aromatase (CYP19A1)",
                    "action": "substrate",
                    "family": "Steroidogenesis",
                    "affinity_ki": 1.0,
                    "intrinsic_efficacy": exo_arom_eff,
                    "pre_computed_stress": True,
                })

        # Aromatase Inhibitor (Anastrozole, Letrozole, Exemestane)
        is_ai = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["aromatase inhibitor", "anastrozole", "letrozole", "exemestane"])
        if is_ai and not any("aromatase" in str(t.get("target", "")).lower() for t in receptor_targets):
            ai_eff = -min(0.95, 0.50 + 0.15 * math.log10(max(1.0, dose_mg)))
            receptor_targets.append({
                "target": "Aromatase (CYP19A1)",
                "action": "inhibitor",
                "family": "Enzyme",
                "intrinsic_efficacy": ai_eff,
                "pre_computed_stress": True,
            })

        is_androgen = (is_steroidal_androgen(compound) or ("androgen" in drug_class_lower and "antagonist" not in drug_class_lower and "inhibitor" not in drug_class_lower) or "sarm" in drug_class_lower) and not is_ai
        is_arom = is_aromatizable_androgen(compound) if is_androgen else True
        is_5ar = is_5alpha_reductase_substrate(compound) if is_androgen else True

        # Endocrine negative feedback: Synthetic androgens / SARMs without bioidentical testosterone base shut down HPG axis
        if is_androgen and not is_bioidentical_test:
            if not any("androgen receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
                receptor_targets.append({
                    "target": "Androgen Receptor (AR / NR3C4)",
                    "action": "agonist",
                    "family": "Nuclear Receptor",
                    "affinity_ki": 1.0,
                    "intrinsic_efficacy": 0.85,
                    "pre_computed_stress": True,
                })
            if not has_bioidentical_test_in_stack:
                if not any("hypothalamic-pituitary-gonadal" in str(t.get("target", "")).lower() for t in receptor_targets):
                    receptor_targets.append({
                        "target": "Hypothalamic-Pituitary-Gonadal (HPG) Axis",
                        "action": "inhibitor",
                        "family": "Endocrine Axis",
                        "intrinsic_efficacy": -0.92,
                        "pre_computed_stress": True,
                    })

        # 19-nor progestogenic stimulation (Trenbolone, Nandrolone)
        is_19nor = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["19-nor", "nandrolone", "trenbolone", "nortestosterone", "progest"])
        if is_19nor and not any("progesterone receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Progesterone Receptor (PGR / NR3C3)",
                "action": "agonist",
                "family": "Nuclear Receptor",
                "intrinsic_efficacy": 0.85,
                "pre_computed_stress": True,
            })

        # Dopamine Agonist prolactin suppression (Cabergoline, Pramipexole)
        is_d2_agonist = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["cabergoline", "pramipexole", "bromocriptine", "dopamine agonist"])
        if is_d2_agonist and not any("dopamine" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Dopamine Transporter & Receptors (SLC6A3 / DRD2)",
                "action": "agonist",
                "family": "GPCR",
                "intrinsic_efficacy": 0.90,
                "pre_computed_stress": True,
            })

        # Exogenous Thyroid (T3 / Liothyronine, T4 / Levothyroxine)
        is_thyroid = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["liothyronine", "levothyroxine", "thyroid hormone", "triiodothyronine", "t3", "t4"]) and not any(w in c_name_lower for w in ["ashwagandha", "iodine", "selenium", "tyrosine"])
        if is_thyroid and not any("thyroid hormone receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Thyroid Hormone Receptor Alpha & Beta (THRA/THRB / NR1A1/NR1A2)",
                "action": "agonist",
                "family": "Nuclear Receptor",
                "intrinsic_efficacy": 0.85,
                "pre_computed_stress": True,
            })

        # Exogenous Glucocorticoids (Prednisone, Dexamethasone, Hydrocortisone)
        is_glucocorticoid = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["prednisone", "dexamethasone", "hydrocortisone", "methylprednisolone", "budesonide", "corticosteroid", "glucocorticoid"])
        if is_glucocorticoid and not any("glucocorticoid receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Glucocorticoid Receptor (GR / NR3C1)",
                "action": "agonist",
                "family": "Nuclear Receptor",
                "intrinsic_efficacy": 0.85,
                "pre_computed_stress": True,
            })

        # Dynamic First-Principles Organ Stress & Clearance Pathway Synthesis
        cyp_info = compound.get("cyp_enzymes") or {}
        transporter_info = compound.get("transporters") or {}
        phase2_info = compound.get("phase2_enzymes") or {}
        clearance_routes = str(compound.get("clearance_routes") or "").lower()
        logp_val = float(compound.get("logp") or 0.0)
        warnings_text = str(compound.get("warnings") or "").lower()
        is_17aa = any(w in c_name_lower for w in ["methyl", "stanozolol", "superdrol", "anadrol", "oxymetholone", "halotestin", "fluoxymesterone", "dianabol", "methandrostenolone", "turinabol", "winstrol"])

        # 1. Dynamic Hepatic Metabolic Clearance & Hepatobiliary Stress
        # Routine hepatic metabolism is normal physiology — NOT hepatotoxicity.
        # Only structurally hepatotoxic features should drive meaningful transaminase elevation.
        has_hep_clearance = (
            bool(cyp_info.get("substrates"))
            or bool(cyp_info.get("inhibitors"))
            or bool(phase2_info.get("substrates"))
            or "hepatic" in clearance_routes
            or "liver" in clearance_routes
            or is_steroidal_androgen(compound)
            or logp_val >= 3.2
        )
        if has_hep_clearance and not any("hepatic metabolic clearance" in str(t.get("target", "")).lower() for t in receptor_targets):
            # Tiered hepatotoxicity scoring based on structural features
            hep_risk_score = 0.0

            # 17-alpha-alkylated orals (methyltestosterone, stanozolol, superdrol) — genuinely hepatotoxic
            if is_17aa:
                hep_risk_score += 0.50
            # Known hepatotoxicity warnings
            if any(w in warnings_text for w in ["hepatotox", "liver damage", "liver injury", "cholestatic", "jaundice", "liver failure"]):
                hep_risk_score += 0.35
            # CYP inhibitors (competitive inhibition increases reactive metabolite accumulation)
            if bool(cyp_info.get("inhibitors")):
                hep_risk_score += 0.08
            # Very high lipophilicity (logP > 5) increases hepatic accumulation
            if logp_val >= 5.0:
                hep_risk_score += 0.06
            elif logp_val >= 3.5:
                hep_risk_score += 0.02
            # Injectable steroids (non-17aa) — mild hepatic load
            if is_steroidal_androgen(compound) and not is_17aa:
                hep_risk_score += 0.04
            # Routine CYP substrate metabolism — background noise
            if bool(cyp_info.get("substrates")) and hep_risk_score < 0.05:
                hep_risk_score += 0.02

            # Dose scaling: only amplify for genuinely hepatotoxic compounds
            dose_factor = 1.0 + 0.15 * math.log10(max(1.0, dose_mg)) if hep_risk_score >= 0.10 else 1.0
            hep_efficacy = min(0.85, hep_risk_score * dose_factor)

            # Only add target if there's a meaningful hepatic signal
            if hep_efficacy >= 0.01:
                receptor_targets.append({
                    "target": "Hepatic Metabolic Clearance & Hepatobiliary System",
                    "action": "substrate",
                    "family": "Xenobiotic Clearance",
                    "intrinsic_efficacy": hep_efficacy,
                    "pre_computed_stress": True,
                })

        # 2. Dynamic Renal Filtration & Tubular Hemodynamic Stress
        # Distinguish nephroprotective agents (ARBs, aldosterone antagonists, SGLT2i) from nephrotoxic ones
        is_nephroprotective = any(w in drug_class_lower for w in ["arb", "angiotensin", "sartan", "sglt2", "aldosterone antagonist", "mineralocorticoid"])
        is_nephroprotective = is_nephroprotective or any(w in mechanism_text for w in ["angiotensin", "aldosterone", "sglt2", "mineralocorticoid receptor"])
        is_nephrotoxic = any(w in drug_class_lower for w in ["nsaid", "aminoglycoside", "cisplatin", "contrast"])
        is_nephrotoxic = is_nephrotoxic or any(w in warnings_text for w in ["nephrotox", "kidney damage", "renal failure", "renal impairment"])

        has_ren_involvement = (
            "renal" in clearance_routes
            or "kidney" in clearance_routes
            or any(t in str(transporter_info).upper() for t in ["OAT", "OCT", "P-GP", "ABCB1", "SLC22"])
            or is_nephroprotective
            or is_nephrotoxic
            or any(w in mechanism_text for w in ["raas", "cox-1", "cox-2"])
        )
        if has_ren_involvement and not any("glomerular filtration" in str(t.get("target", "")).lower() for t in receptor_targets):
            if is_nephroprotective:
                # ARBs, SGLT2i, MRAs are nephroprotective — they reduce GFR stress long-term
                # Short-term they may transiently raise creatinine (hemodynamic effect), but this is mild
                ren_efficacy = 0.04 + 0.02 * math.log10(max(1.0, dose_mg))
            elif is_nephrotoxic:
                # Genuinely nephrotoxic agents
                ren_efficacy = min(0.70, 0.25 + 0.15 * math.log10(max(1.0, dose_mg)))
            else:
                # Routine renal clearance — background noise
                ren_efficacy = 0.02

            if ren_efficacy >= 0.01:
                receptor_targets.append({
                    "target": "Glomerular Filtration & Renal Tubular Transport",
                    "action": "substrate",
                    "family": "Renal Elimination",
                    "intrinsic_efficacy": ren_efficacy,
                    "pre_computed_stress": True,
                })

        # 3. Dynamic Cellular Redox & Mitochondrial Stress
        is_blocker = any(w in drug_class_lower for w in ["blocker", "antagonist", "inhibitor"])
        comp_class_lower = str(compound.get("compound_class") or "").lower()
        is_antioxidant = any(
            w in drug_class_lower or w in mechanism_text or w in comp_class_lower or w in c_name_lower
            for w in [
                "antioxidant",
                "glutathione",
                "scavenger",
                "n-acetylcysteine",
                "acetylcysteine",
                "tudca",
                "mucolytic",
                "reductant",
                "neutralizing reactive oxygen",
                "protects against oxidative",
                "radical scavenger",
                "lipoic acid",
                "coq10",
                "ubiquinone",
                "ubiquinol",
                "tocopherol",
                "ascorbic",
            ]
        )
        has_redox_stress = (
            not is_blocker
            and not is_antioxidant
            and (
                is_17aa
                or ("beta" in drug_class_lower and "agonist" in drug_class_lower)
                or any(w in drug_class_lower for w in ["sympathomimetic", "xanthine", "stimulant", "mitochondrial uncoupler", "quinone", "17alpha-alkylated", "17a-alkylated"])
                or any(w in mechanism_text for w in ["beta-1 agonist", "beta-2 agonist", "camp surge", "uncoupl", "generates reactive oxygen", "mitochondrial uncoupling", "induces ros", "oxidative phosphorylation uncoupling", "lipid peroxidation"])
            )
        )
        if has_redox_stress and not any("cellular redox" in str(t.get("target", "")).lower() for t in receptor_targets):
            ox_efficacy = min(0.65, (0.25 if is_17aa else 0.15) + 0.10 * math.log10(max(1.0, dose_mg)))
            receptor_targets.append({
                "target": "Cellular Redox Homeostasis & Mitochondrial Bioenergetics",
                "action": "stimulator",
                "family": "Redox Homeostasis",
                "intrinsic_efficacy": ox_efficacy,
                "pre_computed_stress": True,
            })
        elif is_antioxidant and not any("glutathione" in str(t.get("target", "")).lower() or "cystine" in str(t.get("target", "")).lower() or "antioxidant defense" in str(t.get("target", "")).lower() for t in receptor_targets):
            antiox_efficacy = min(0.85, 0.35 + 0.15 * math.log10(max(1.0, dose_mg)))
            receptor_targets.append({
                "target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)",
                "action": "agonist",
                "family": "Antioxidant Defense",
                "intrinsic_efficacy": antiox_efficacy,
            })

        # Connect Targets & Multi-Tier Cascades
        for receptor in receptor_targets:
            if not isinstance(receptor, dict):
                continue
            target_raw = str(receptor.get("target") or receptor.get("name") or "unknown_target").strip()
            if not target_raw:
                continue

            target_raw_lower = target_raw.lower()
            action_lower = str(receptor.get("action") or "").lower()

            # Filter out aromatase substrate edges for chemically non-aromatizable compounds
            if is_androgen and not is_arom:
                if any(w in target_raw_lower for w in ["aromatase", "cyp19", "cyp19a1", "estrogen receptor", "esr1", "esr2"]) and any(act in action_lower for act in ["substrate", "agonist", "stimulator", "cleaved"]):
                    continue

            # Filter out 5AR substrate edges for DHT derivatives and non-5AR substrates
            if is_androgen and not is_5ar:
                if any(w in target_raw_lower for w in ["5-alpha reductase", "srd5a", "5ar"]) and any(act in action_lower for act in ["substrate", "agonist"]):
                    continue

            target_id = _normalize_target_node_id(
                raw_name=target_raw,
                target_id=receptor.get("target_id"),
                accessions=receptor.get("accessions") or receptor.get("uniprot_id"),
            )
            target_label = target_id
            edge_type, vector_magnitude = classify_target_action(receptor.get("action"))

            # If androgen/exogenous hormone connects to HPG Axis, ensure it exerts negative feedback suppression
            if any(w in target_raw_lower or w in target_id.lower() for w in ["hpg", "hypothalamic-pituitary-gonadal", "gnrh"]) and is_androgen:
                edge_type = EdgeType.INHIBITS_PATHWAY
                vector_magnitude = -0.9

            affinity_ki_raw = receptor.get("affinity_ki")
            inhibition_ic50_raw = receptor.get("inhibition_ic50")
            ec50_raw = receptor.get("ec50")

            affinity_ki: Optional[float] = None
            if affinity_ki_raw is not None:
                try:
                    val = float(affinity_ki_raw)
                    if val > 0.0:
                        affinity_ki = val
                except (ValueError, TypeError):
                    pass

            inhibition_ic50: Optional[float] = None
            if inhibition_ic50_raw is not None:
                try:
                    val = float(inhibition_ic50_raw)
                    if val > 0.0:
                        inhibition_ic50 = val
                except (ValueError, TypeError):
                    pass

            ec50: Optional[float] = None
            if ec50_raw is not None:
                try:
                    val = float(ec50_raw)
                    if val > 0.0:
                        ec50 = val
                except (ValueError, TypeError):
                    pass

            if receptor.get("intrinsic_efficacy") is not None:
                vector_magnitude = float(receptor["intrinsic_efficacy"])

            # Check Canonical Cascade Mapping & Target Node Type (Zero-Regex Exact Biological Matching)
            matched_cascade = get_exact_target_cascade_blueprint(
                target_name=target_id,
                gene_symbol=receptor.get("gene_symbol"),
                uniprot_id=receptor.get("uniprot_id") or receptor.get("accessions"),
                chembl_target_id=receptor.get("chembl_target_id") or receptor.get("target_id"),
            )
            if matched_cascade is None and target_raw != target_id:
                matched_cascade = get_exact_target_cascade_blueprint(
                    target_name=target_raw,
                    gene_symbol=receptor.get("gene_symbol"),
                    uniprot_id=receptor.get("uniprot_id") or receptor.get("accessions"),
                    chembl_target_id=receptor.get("chembl_target_id") or receptor.get("target_id"),
                )

            cascade_node_type = str(matched_cascade.get("node_type", "")).lower() if matched_cascade else ""
            target_fam = str(receptor.get("family") or "").lower()
            target_lower = target_id.lower()

            # Instantiate accurate biological node type (Enzyme, Transporter, Ion Channel, or Receptor)
            if (
                cascade_node_type == "enzyme"
                or any(w in target_lower or w in target_fam for w in ["enzyme", "synthase", "reductase", "aromatase", "cyp", "cox", "pde", "kinase", "esterase", "oxygenase", "dehydrogenase"])
            ):
                target_node = EnzymeNode(
                    node_id=target_id,
                    label=target_label,
                    enzyme_family=receptor.get("family") or "Enzyme",
                )
            elif (
                cascade_node_type == "transporter"
                or any(w in target_lower or w in target_fam for w in ["transporter", "sert", "dat", "net", "vmat", "p-gp", "oat", "oct", "mrp", "bcrp", "slc", "abc"])
            ):
                target_node = TransporterNode(
                    node_id=target_id,
                    label=target_label,
                    transporter_family=receptor.get("family") or "Membrane Transporter",
                )
            elif (
                cascade_node_type == "ion_channel"
                or any(w in target_lower or w in target_fam for w in ["channel", "herg", "kcnh2", "cav", "nav"])
            ):
                target_node = IonChannelNode(
                    node_id=target_id,
                    label=target_label,
                    channel_type=receptor.get("family") or "Ion Channel",
                )
            else:
                target_node = ReceptorNode(
                    node_id=target_id,
                    label=target_label,
                    receptor_family=receptor.get("family") or "Molecular Target",
                )

            graph.add_node(target_node)

            # Edge 1: Compound -> Target
            is_pre_computed_stress = bool(receptor.get("pre_computed_stress"))
            graph.add_edge(
                compound_id,
                target_id,
                edge_type=edge_type,
                edge_data=EdgeData(
                    affinity_ki=affinity_ki,
                    inhibition_ic50=inhibition_ic50,
                    vector_magnitude=vector_magnitude,
                ),
                dose_mg=dose_mg,
                dose_str=dose_str,
                pre_computed_stress=is_pre_computed_stress,
            )

            # Check Dynamic Pathway Service (Reactome + Open Targets + SQLite Cache)
            from app.services.pathway_service import PathwayService
            pathway_service = PathwayService(db_path=getattr(service, "db_path", None))
            dyn_cascade = pathway_service.get_dynamic_target_cascade(target_id, {"label": target_label, "name": target_raw})

            # Check Canonical Cascade Mapping
            if matched_cascade:
                p_info = matched_cascade["pathway"]
                phys_info = matched_cascade["physiology"]
                p_id = p_info["id"]
                reactome_pws = dyn_cascade.get("raw_pathways", [])
                p_label = f"{p_info['label']} ({reactome_pws[0]['pathway_name']})" if reactome_pws else p_info["label"]

                # Add Primary Pathway Node
                graph.add_node(
                    SignalingPathwayNode(
                        node_id=p_id,
                        label=p_label,
                        pathway_database="Reactome" if reactome_pws else p_info["db"],
                    )
                )

                # Edge 2: Target -> Pathway
                graph.add_edge(
                    target_id,
                    p_id,
                    edge_type=EdgeType.ACTIVATES_PATHWAY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )

                # Add dynamic Reactome pathway node if available
                if reactome_pws and reactome_pws[0].get("pathway_id"):
                    clean_tgt = re.sub(r"[^a-z0-9_]", "_", str(target_id).lower()).strip("_")
                    r_id = f"{reactome_pws[0]['pathway_id']}_{clean_tgt}"
                    graph.add_node(
                        SignalingPathwayNode(
                            node_id=r_id,
                            label=f"{reactome_pws[0].get('pathway_name') or r_id} ({target_label})",
                            pathway_database="Reactome",
                        )
                    )
                    graph.add_edge(
                        target_id,
                        r_id,
                        edge_type=EdgeType.ACTIVATES_PATHWAY,
                        edge_data=EdgeData(vector_magnitude=1.0),
                    )

                # Add Physiology Node
                graph.add_node(
                    PhysiologyNode(
                        node_id=phys_info["id"],
                        label=phys_info["label"],
                        organ_system=phys_info["organ"],
                    )
                )

                # Edge 3: Pathway -> Physiology
                graph.add_edge(
                    p_id,
                    phys_info["id"],
                    edge_type=EdgeType.ALTERS_PHYSIOLOGY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )

                # Add Biomarkers & Edges
                for b_info in matched_cascade.get("biomarkers", []):
                    graph.add_node(
                        BiomarkerNode(
                            node_id=b_info["id"],
                            label=b_info["label"],
                            unit=b_info["unit"],
                            biomarker_panel=b_info["panel"],
                            safe_lower_bound=b_info["lower"],
                            safe_upper_bound=b_info["upper"],
                            onset_days=float(b_info.get("onset_days", 1.0)),
                            half_time_days=float(b_info.get("half_time_days", 3.0)),
                            time_to_steady_state_weeks=float(b_info.get("time_to_steady_state_weeks", 1.0)),
                            kinetic_profile=str(b_info.get("kinetic_profile", "direct_receptor")),
                        )
                    )
                    b_mag = float(b_info.get("mag", 1.0))
                    graph.add_edge(
                        phys_info["id"],
                        b_info["id"],
                        edge_type=EdgeType.MODIFIES_BIOMARKER,
                        edge_data=EdgeData(vector_magnitude=b_mag),
                    )

                # Add Phenotypes & Edges
                for pheno in matched_cascade.get("phenotypes", []):
                    graph.add_node(
                        PhenotypeNode(
                            node_id=pheno["id"],
                            label=pheno["label"],
                            phenotype_category=pheno["cat"],
                            severity=pheno["sev"],
                        )
                    )
                    pheno_mag = float(pheno.get("mag", 1.0))
                    graph.add_edge(
                        phys_info["id"],
                        pheno["id"],
                        edge_type=EdgeType.DRIVES_PHENOTYPE if pheno_mag > 0 else EdgeType.MITIGATES_PHENOTYPE,
                        edge_data=EdgeData(vector_magnitude=pheno_mag),
                    )

            # Universal Dynamic Target Cascade Fallback for unmapped targets from Reactome & Open Targets
            if not matched_cascade:
                p_dyn = dyn_cascade.get("pathway", {})
                phys_dyn = dyn_cascade.get("physiology", {})

                pathway_id = p_dyn.get("id", f"pathway_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}")
                p_dyn_label = p_dyn.get("label", "")
                pathway_label = f"{target_label} Transduction Cascade ({p_dyn_label})" if p_dyn_label else f"{target_label} Transduction Cascade"
                phys_id = phys_dyn.get("id", f"phys_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}")
                phys_dyn_label = phys_dyn.get("label", "")
                phys_label = f"{target_label} Downstream Physiological Function ({phys_dyn_label})" if phys_dyn_label else f"{target_label} Downstream Physiological Function"

                graph.add_node(
                    SignalingPathwayNode(
                        node_id=pathway_id,
                        label=pathway_label,
                        pathway_database="Reactome",
                    )
                )
                graph.add_edge(
                    target_id,
                    pathway_id,
                    edge_type=EdgeType.ACTIVATES_PATHWAY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )
                graph.add_node(
                    PhysiologyNode(
                        node_id=phys_id,
                        label=phys_label,
                        organ_system="Systemic",
                    )
                )
                graph.add_edge(
                    pathway_id,
                    phys_id,
                    edge_type=EdgeType.ALTERS_PHYSIOLOGY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )

                # Dynamic biomarkers from Open Targets / Reactome
                if dyn_cascade.get("biomarkers"):
                    for b_info in dyn_cascade.get("biomarkers", []):
                        graph.add_node(
                            BiomarkerNode(
                                node_id=b_info["id"],
                                label=b_info["label"],
                                unit=b_info["unit"],
                                biomarker_panel=b_info["panel"],
                                safe_lower_bound=b_info["lower"],
                                safe_upper_bound=b_info["upper"],
                            )
                        )
                        graph.add_edge(
                            phys_id,
                            b_info["id"],
                            edge_type=EdgeType.MODIFIES_BIOMARKER,
                            edge_data=EdgeData(vector_magnitude=float(b_info.get("mag", 0.75))),
                        )
                else:
                    bio_id = f"bio_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}_activity"
                    graph.add_node(
                        BiomarkerNode(
                            node_id=bio_id,
                            label=f"{target_label} Functional Index",
                            unit="index",
                            biomarker_panel="Functional Panel",
                            safe_lower_bound=0.0,
                            safe_upper_bound=100.0,
                        )
                    )
                    graph.add_edge(
                        phys_id,
                        bio_id,
                        edge_type=EdgeType.MODIFIES_BIOMARKER,
                        edge_data=EdgeData(vector_magnitude=0.75),
                    )

                # Dynamic phenotypes from Open Targets
                if dyn_cascade.get("phenotypes"):
                    for ph_info in dyn_cascade.get("phenotypes", []):
                        graph.add_node(
                            PhenotypeNode(
                                node_id=ph_info["id"],
                                label=ph_info["label"],
                                phenotype_category=ph_info.get("cat", "adverse_effect"),
                                severity=ph_info.get("sev", "moderate"),
                            )
                        )
                        graph.add_edge(
                            phys_id,
                            ph_info["id"],
                            edge_type=EdgeType.DRIVES_PHENOTYPE,
                            edge_data=EdgeData(vector_magnitude=float(ph_info.get("mag", 0.75))),
                        )
                else:
                    pheno_id = f"pheno_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}_modulation"
                    graph.add_node(
                        PhenotypeNode(
                            node_id=pheno_id,
                            label=f"{target_label} Downstream Outcome",
                            phenotype_category="therapeutic_benefit",
                            severity="moderate",
                        )
                    )
                    graph.add_edge(
                        phys_id,
                        pheno_id,
                        edge_type=EdgeType.DRIVES_PHENOTYPE,
                        edge_data=EdgeData(vector_magnitude=0.75),
                    )

        # Connect Pharmacokinetic CYP450 Metabolism Enzymes
        cyp_info = compound.get("cyp_enzymes") or {}
        if isinstance(cyp_info, dict):
            for sub in cyp_info.get("substrates") or []:
                enz_id = str(sub).strip().upper()
                if enz_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=enz_id,
                            label=f"{enz_id} (Substrate)",
                            enzyme_family="CYP450 Metabolism",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        enz_id,
                        edge_type=EdgeType.SUBSTRATE_OF,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} is metabolized as a substrate of {enz_id}",
                        ),
                    )
            for inh in cyp_info.get("inhibitors") or []:
                enz_id = str(inh).strip().upper()
                if enz_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=enz_id,
                            label=f"{enz_id} (Inhibitor)",
                            enzyme_family="CYP450 Metabolism",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        enz_id,
                        edge_type=EdgeType.INHIBITS_ENZYME,
                        edge_data=EdgeData(
                            vector_magnitude=-1.0,
                            description=f"{compound_label} inhibits enzymatic clearance activity of {enz_id}",
                        ),
                    )
            for ind in cyp_info.get("inducers") or []:
                enz_id = str(ind).strip().upper()
                if enz_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=enz_id,
                            label=f"{enz_id} (Inducer)",
                            enzyme_family="CYP450 Metabolism",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        enz_id,
                        edge_type=EdgeType.INDUCES_ENZYME,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} induces expression of {enz_id}",
                        ),
                    )

        # Connect Pharmacokinetic Membrane Transporters
        transporter_info = compound.get("transporters") or {}
        if isinstance(transporter_info, dict):
            for sub in transporter_info.get("substrates") or []:
                t_id = str(sub).strip().upper()
                if t_id:
                    graph.add_node(
                        TransporterNode(
                            node_id=t_id,
                            label=f"{t_id} (Substrate)",
                            transporter_family="Membrane Transporter",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        t_id,
                        edge_type=EdgeType.EFFLUXED_BY,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} is transported as a substrate by {t_id}",
                        ),
                    )
            for inh in transporter_info.get("inhibitors") or []:
                t_id = str(inh).strip().upper()
                if t_id:
                    graph.add_node(
                        TransporterNode(
                            node_id=t_id,
                            label=f"{t_id} (Inhibitor)",
                            transporter_family="Membrane Transporter",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        t_id,
                        edge_type=EdgeType.INHIBITS_CASCADE,
                        edge_data=EdgeData(
                            vector_magnitude=-1.0,
                            description=f"{compound_label} inhibits transport via {t_id}",
                        ),
                    )

        # Connect Phase II Conjugation Enzymes
        phase2_info = compound.get("phase2_enzymes") or {}
        if isinstance(phase2_info, dict):
            for sub in phase2_info.get("substrates") or []:
                p2_id = str(sub).strip().upper()
                if p2_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=p2_id,
                            label=f"{p2_id} (Phase II)",
                            enzyme_family="Phase II Conjugation",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        p2_id,
                        edge_type=EdgeType.SUBSTRATE_OF,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} undergoes Phase II conjugation via {p2_id}",
                        ),
                    )

    # Phase 2: Dynamic Biological Cross-Talk Bridges
    # Connects upstream physiological neurotransmitters/hormones to downstream target receptors when applicable
    for cascade in CANONICAL_TARGET_CASCADES:
        phys_id = cascade["physiology"]["id"]
        if phys_id not in graph.graph:
            continue
        for bridge in cascade.get("bridges", []):
            pattern = bridge["target_node_pattern"]
            edge_type = bridge.get("edge_type", EdgeType.MODULATES)
            vec_mag = float(bridge.get("vector_magnitude", 1.0))
            desc = bridge.get("description", "")
            
            matching_nodes = []
            for node in list(graph.graph.nodes()):
                if node == phys_id:
                    continue
                node_label = str(graph.graph.nodes[node].get("label", node)).lower()
                node_id_lower = str(node).lower()
                if re.search(pattern, node_label) or re.search(pattern, node_id_lower):
                    nt = str(graph.graph.nodes[node].get("node_type", "")).lower()
                    if nt in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
                        tier_rank = 1
                    elif nt == "signaling_pathway":
                        tier_rank = 2
                    elif nt == "physiology":
                        tier_rank = 3
                    else:
                        tier_rank = 4
                    matching_nodes.append((tier_rank, node))

            if matching_nodes:
                matching_nodes.sort(key=lambda x: x[0])
                best_tier = matching_nodes[0][0]
                for rank, node in matching_nodes:
                    if rank == best_tier:
                        if not graph.graph.has_edge(phys_id, node):
                            graph.add_edge(
                                phys_id,
                                node,
                                edge_type=edge_type,
                                edge_data=EdgeData(
                                    vector_magnitude=vec_mag,
                                    description=desc,
                                    is_bridge=True,
                                ),
                            )

    if graph.graph.number_of_nodes() == 0:
        return build_testosterone_alopecia_graph()

    return graph


def filter_graph_by_stack(graph: BiologicalGraph, stack: List[Any] | None, max_depth: int = 5) -> BiologicalGraph:
    """Filter the biological knowledge graph to the cascade subgraph connected to selected compounds."""
    if not stack:
        return graph

    raw_items = [
        str(i.get("compound") or i.get("key") or i.get("name") if isinstance(i, dict) else i).strip().lower()
        for i in stack
        if i
    ]
    normalized_stack = list(dict.fromkeys(item for item in resolve_stack_to_catalog_keys(stack) if item))

    start_nodes = list(dict.fromkeys(
        [item for item in raw_items if item in graph.graph] +
        [item for item in normalized_stack if item in graph.graph]
    ))

    if not start_nodes:
        fallback = BiologicalGraph()
        items_to_add = sorted(set(raw_items or normalized_stack))
        for item in items_to_add:
            fallback.graph.add_node(
                item,
                node_id=item,
                label=item.title(),
                node_type="compound",
            )
        return fallback

    visited = set()
    depth_map = {node_id: 0 for node_id in start_nodes}
    frontier = deque(start_nodes)

    while frontier:
        current = frontier.popleft()
        if current in visited:
            continue
        visited.add(current)

        current_depth = depth_map.get(current, 0)
        if current_depth >= max_depth:
            continue

        for neighbor in list(graph.graph.successors(current)) + list(graph.graph.predecessors(current)):
            if neighbor not in visited:
                depth_map[neighbor] = current_depth + 1
                frontier.append(neighbor)

    filtered = BiologicalGraph()
    filtered.graph.add_nodes_from((node, graph.graph.nodes[node].copy()) for node in visited)
    filtered.graph.add_edges_from(
        (source, target, graph.graph.edges[source, target].copy())
        for source, target in graph.graph.edges
        if source in visited and target in visited
    )

    for item in sorted(start_nodes):
        if item not in filtered.graph.nodes:
            filtered.graph.add_node(
                item,
                node_id=item,
                label=item.title(),
                node_type="compound",
            )

    return filtered


def compute_target_combined_effects(
    graph: BiologicalGraph,
    custom_doses: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Computes combined pharmacodynamic receptor activation, fractional occupancy,
    and competitive displacement for all molecular targets (receptors, enzymes,
    ion channels, transporters) with incoming compound/ligand connections.
    Takes into account actual free molar biophase concentrations derived from dose (mg)
    and target binding affinities (Ki / IC50 in nM).
    """
    results: Dict[str, Dict[str, Any]] = {}
    custom_doses = custom_doses or {}

    target_types = {
        "receptor",
        "enzyme",
        "transporter",
        "ion_channel",
        "carrier_protein",
        "target",
    }

    for node_id, node_attrs in graph.graph.nodes(data=True):
        nt = str(node_attrs.get("node_type", "")).lower()
        if nt not in target_types and not any(t in node_id.lower() for t in ["receptor", "channel", "cyp", "transporter", "enzyme", "cox", "pde", "sert", "dat"]):
            continue

        # Find incoming compound edges
        incoming_compounds = []
        for pred in graph.graph.predecessors(node_id):
            pred_attrs = graph.graph.nodes[pred]
            pred_type = str(pred_attrs.get("node_type", "")).lower()
            if pred_type != "compound" and graph.graph.in_degree(pred) > 0:
                if pred_type not in ["compound", "mixture", "selected"]:
                    continue

            edge_data = graph.graph.edges[pred, node_id]
            edge_type = str(edge_data.get("edge_type", "MODULATES")).upper()
            mag = float(edge_data.get("vector_magnitude", 1.0))
            ki = edge_data.get("affinity_ki")
            ic50 = edge_data.get("inhibition_ic50")
            ec50 = edge_data.get("ec50")
            pred_label = pred_attrs.get("label", pred)

            # Determine action classification & intrinsic efficacy
            is_pam = "POSITIVE_ALLOSTERIC" in edge_type or "PAM" in edge_type
            is_nam = "NEGATIVE_ALLOSTERIC" in edge_type or "NAM" in edge_type
            is_antagonist = any(k in edge_type for k in ["ANTAGONIZ", "BLOCK"])
            is_inhibitor = not is_antagonist and any(k in edge_type for k in ["INHIBIT"])
            is_substrate = "SUBSTRATE" in edge_type
            is_agonist = not is_antagonist and not is_inhibitor and not is_substrate and any(k in edge_type for k in ["AGONIZ", "ACTIVAT", "OPEN", "INDUCE"])

            if is_pam:
                action_name = "Positive Allosteric Modulator (PAM)"
                efficacy = 0.8
                is_allosteric = True
            elif is_nam:
                action_name = "Negative Allosteric Modulator (NAM)"
                efficacy = -0.8
                is_allosteric = True
            elif is_antagonist:
                action_name = "Receptor Antagonist (Blocker)"
                efficacy = -1.0
                is_allosteric = False
            elif is_inhibitor:
                action_name = "Enzymatic / Functional Inhibitor"
                efficacy = -0.85
                is_allosteric = False
            elif is_substrate:
                action_name = "Enzymatic Substrate"
                efficacy = float(mag) if mag is not None and mag > 0 else 0.95
                is_allosteric = False
            elif is_agonist:
                action_name = "Receptor Agonist (Activator)"
                efficacy = 1.0 if mag >= 0.8 else (0.6 if mag > 0 else 1.0)
                is_allosteric = False
            else:
                action_name = "Allosteric / Functional Modulator"
                efficacy = mag
                is_allosteric = False

            # Resolve Dose (mg) & Dose Display
            dose_mg = custom_doses.get(pred) or custom_doses.get(pred.lower()) or custom_doses.get(canonicalize_match_token(pred))
            if dose_mg is None:
                dose_mg = edge_data.get("dose_mg") or pred_attrs.get("dose_mg") or DEFAULT_THERAPEUTIC_DOSES_MG.get(pred.lower()) or DEFAULT_THERAPEUTIC_DOSES_MG.get(canonicalize_match_token(pred)) or DEFAULT_THERAPEUTIC_DOSES_MG.get(canonicalize_match_token(pred_label)) or 10.0

            if dose_mg >= 1.0:
                dose_val = round(dose_mg, 2)
                dose_unit = "mg"
                dose_display = f"{dose_mg:g} mg"
            else:
                dose_val = round(dose_mg * 1000.0, 2)
                dose_unit = "μg"
                dose_display = f"{dose_mg * 1000.0:g} μg"

            # Pharmacokinetic free biophase concentration estimation (in nM) directly from node ADMET properties
            def _parse_num(v: Any, default: float) -> float:
                if v is None:
                    return default
                if isinstance(v, (int, float)):
                    return float(v)
                v_str = str(v).replace("%", "").strip()
                matches = re.findall(r"(\d+(?:\.\d+)?)", v_str)
                if matches:
                    nums = [float(x) for x in matches]
                    return sum(nums) / len(nums)
                return default

            mw = _parse_num(pred_attrs.get("molecular_weight"), 300.0)
            
            raw_f = pred_attrs.get("oral_bioavailability") or pred_attrs.get("bioavailability_f") or pred_attrs.get("bioavailability_pct")
            if raw_f is not None:
                f_val = _parse_num(raw_f, 80.0)
                f_bio = f_val if f_val <= 1.0 else f_val / 100.0
            else:
                f_bio = 0.80

            vd_lkg = _parse_num(pred_attrs.get("volume_of_distribution") or pred_attrs.get("volume_of_distribution_l_kg"), 2.5)

            raw_pb = pred_attrs.get("protein_binding") or pred_attrs.get("protein_binding_pct")
            if raw_pb is not None:
                pb_val = _parse_num(raw_pb, 60.0)
                pb_pct = pb_val if pb_val > 1.0 else pb_val * 100.0
            else:
                pb_pct = 60.0

            # Effective bioavailable fraction in tissue biophases (accounting for rapid albumin dissociation and cellular uptake)
            fu = max(0.005, min(1.0, 1.0 - (pb_pct / 100.0)))
            fu_eff = max(fu, min(1.0, 1.0 - (pb_pct / 100.0) * 0.98))
            c_free_nm = (dose_mg * f_bio * fu_eff * 1e6) / (vd_lkg * 70.0 * mw)

            # Calculate Biophysical Receptor Binding Drive W_i = [L_free] / K_i
            affinity_val = ki or ic50 or ec50
            if affinity_val and float(affinity_val) > 0:
                potency_weight = max(0.0001, c_free_nm / float(affinity_val))
            else:
                potency_weight = max(0.05, abs(mag) * (dose_mg / 10.0))

            incoming_compounds.append({
                "compound_id": pred,
                "compound_label": pred_label,
                "action": action_name,
                "edge_type": edge_type,
                "raw_vector": mag,
                "intrinsic_efficacy": efficacy,
                "affinity_ki": float(ki) if ki else None,
                "inhibition_ic50": float(ic50) if ic50 else None,
                "ec50": float(ec50) if ec50 else None,
                "dose_mg": round(dose_mg, 4),
                "dose_val": dose_val,
                "dose_unit": dose_unit,
                "dose_display": dose_display,
                "c_free_nm": round(c_free_nm, 3),
                "potency_weight": round(potency_weight, 4),
                "is_allosteric": is_allosteric,
                "is_pam": is_pam,
                "is_nam": is_nam,
                "is_antagonist": is_antagonist or is_inhibitor,
                "is_agonist": is_agonist,
            })

        if not incoming_compounds:
            continue

        target_label = node_attrs.get("label", node_id)
        total_potency = sum(c["potency_weight"] for c in incoming_compounds)

        # Total receptor saturation theta: W_total / (1.0 + W_total)
        receptor_saturation_pct = round((total_potency / (1.0 + total_potency)) * 100.0, 1)
        unoccupied_reserve_pct = round(max(0.0, 100.0 - receptor_saturation_pct), 1)

        # Compute fractional occupancy & individual effects
        for c in incoming_compounds:
            c["fractional_occupancy_pct"] = round((c["potency_weight"] / max(total_potency, 0.0001)) * 100.0, 1)
            c["absolute_saturation_pct"] = round((c["potency_weight"] / (1.0 + total_potency)) * 100.0, 1)
            c["individual_effect_pct"] = round(c["intrinsic_efficacy"] * 100.0, 1)

        # Calculate Net Combined Activation Score (-1.0 to +1.0) scaled by Absolute Receptor Saturation
        orthosteric_compounds = [c for c in incoming_compounds if not c["is_allosteric"]]
        allosteric_pams = [c for c in incoming_compounds if c["is_pam"]]
        allosteric_nams = [c for c in incoming_compounds if c["is_nam"]]

        ortho_total = sum(c["potency_weight"] for c in orthosteric_compounds)
        if orthosteric_compounds:
            ortho_net = sum(
                c["intrinsic_efficacy"] * c["potency_weight"]
                for c in orthosteric_compounds
            ) / (1.0 + ortho_total)
        else:
            ortho_net = 0.0

        # Apply allosteric modulators (ternary complex model)
        pam_multiplier = 1.0 + sum(
            c["intrinsic_efficacy"] * (c["potency_weight"] / (1.0 + c["potency_weight"]))
            for c in allosteric_pams
        )
        nam_multiplier = max(
            0.05,
            1.0 - sum(abs(c["intrinsic_efficacy"]) * (c["potency_weight"] / (1.0 + c["potency_weight"])) for c in allosteric_nams)
        )

        if orthosteric_compounds:
            net_score = ortho_net * pam_multiplier * nam_multiplier
        else:
            pam_score = sum(c["intrinsic_efficacy"] * (c["potency_weight"] / (1.0 + c["potency_weight"])) for c in allosteric_pams)
            nam_score = sum(c["intrinsic_efficacy"] * (c["potency_weight"] / (1.0 + c["potency_weight"])) for c in allosteric_nams)
            net_score = pam_score + nam_score

        net_score = max(-1.0, min(1.0, net_score))
        net_pct = round(net_score * 100.0, 1)

        has_agonists = any(c["is_agonist"] for c in incoming_compounds)
        has_antagonists = any(c["is_antagonist"] for c in incoming_compounds)
        has_opposing = has_agonists and has_antagonists
        has_synergistic = len([c for c in incoming_compounds if c["is_agonist"]]) > 1 or (has_agonists and bool(allosteric_pams))

        # Dominant compound
        dominant = max(incoming_compounds, key=lambda x: x["potency_weight"])

        # Determine receptor state classification
        if len(incoming_compounds) == 1:
            c0 = incoming_compounds[0]
            if c0["intrinsic_efficacy"] > 0.2:
                state_str = "Monotherapy Agonism / Activation"
            elif c0["intrinsic_efficacy"] < -0.2:
                state_str = "Monotherapy Blockade / Inhibition"
            else:
                state_str = "Monotherapy Modulation"
        elif has_opposing:
            if net_score > 0.15:
                state_str = "Competitive Attenuation (Agonist Dominant)"
            elif net_score < -0.15:
                state_str = "Competitive Blockade (Antagonist Dominant)"
            else:
                state_str = "Competitive Equilibrium / Balanced Antagonism"
        elif has_synergistic:
            if allosteric_pams:
                state_str = "Allosteric Potentiation / Synergistic Agonism"
            else:
                state_str = "Additive / Synergistic Agonism"
        elif net_score > 0.15:
            state_str = "Net Receptor Activation (Stimulated)"
        elif net_score < -0.15:
            state_str = "Net Receptor Blockade (Inhibited)"
        else:
            state_str = "Basal Equilibrium Tone"

        # Generate clinical pharmacological explanation
        if len(incoming_compounds) == 1:
            c0 = incoming_compounds[0]
            summary_text = (
                f"{c0['compound_label']} ({c0['dose_display']}) occupies {c0['absolute_saturation_pct']}% of {target_label}, "
                f"yielding an estimated {net_pct:+.1f}% functional signal modulation with {unoccupied_reserve_pct}% baseline reserve remaining."
            )
        elif has_opposing:
            agonists = [f"{c['compound_label']} ({c['dose_display']})" for c in incoming_compounds if c["is_agonist"]]
            antagonists = [f"{c['compound_label']} ({c['dose_display']})" for c in incoming_compounds if c["is_antagonist"]]
            summary_text = (
                f"Receptor Competition: {', '.join(agonists)} (Agonist) and {', '.join(antagonists)} (Antagonist) "
                f"compete for {receptor_saturation_pct}% total receptor saturation at {target_label}. {dominant['compound_label']} commands "
                f"{dominant['fractional_occupancy_pct']}% of occupied sites ({dominant['absolute_saturation_pct']}% absolute saturation), yielding a net activation of {net_pct:+.1f}%."
            )
        elif has_synergistic:
            comp_names = [f"{c['compound_label']} ({c['dose_display']})" for c in incoming_compounds]
            summary_text = (
                f"Synergistic Convergence: {', '.join(comp_names)} saturate {receptor_saturation_pct}% of {target_label}, "
                f"driving a unified net receptor activation of {net_pct:+.1f}%."
            )
        else:
            comp_names = [f"{c['compound_label']} ({c['dose_display']} • {c['absolute_saturation_pct']}% sat)" for c in incoming_compounds]
            summary_text = (
                f"Multi-Ligand Engagement: {', '.join(comp_names)} bind {target_label} ({receptor_saturation_pct}% saturation) with net activation of {net_pct:+.1f}%."
            )

        # Compute Dynamic Receptor Regulation (Desensitization / Downregulation / Upregulation)
        # Agonist occupancy drives homologous desensitization (GRK / beta-arrestin / internalization)
        # Antagonist occupancy drives compensatory target upregulation (Bmax increase)
        ago_occupancy = sum(c["absolute_saturation_pct"] for c in incoming_compounds if c["is_agonist"]) / 100.0
        ant_occupancy = sum(c["absolute_saturation_pct"] for c in incoming_compounds if c["is_antagonist"]) / 100.0

        is_gpcr = any(x in target_label.lower() for x in ["adrenergic", "receptor", "adrb", "adra", "at1", "5-ht", "dopamine", "opioid", "cannabinoid", "gaba", "muscarinic"])
        kappa_desens = 0.65 if is_gpcr else 0.25
        kappa_up = 0.25 if is_gpcr else 0.15

        rho_down = 1.0 / (1.0 + kappa_desens * (ago_occupancy ** 2))
        rho_up = 1.0 + kappa_up * ant_occupancy
        regulation_multiplier = round(rho_down * rho_up, 3)

        if ago_occupancy >= 0.50 and rho_down < 0.88:
            regulation_state = "Downregulated / Desensitized (Tachyphylaxis Risk)"
        elif ant_occupancy >= 0.50 and rho_up > 1.10:
            regulation_state = "Upregulated / Supersensitized (Rebound Sensitivity Risk)"
        else:
            regulation_state = "Homeostatic / Normal Receptor Density"

        results[node_id] = {
            "target_id": node_id,
            "target_label": target_label,
            "target_type": nt,
            "ligand_count": len(incoming_compounds),
            "has_multiple_ligands": len(incoming_compounds) > 1,
            "has_opposing_effects": has_opposing,
            "has_synergistic_effects": has_synergistic,
            "receptor_saturation_pct": receptor_saturation_pct,
            "unoccupied_reserve_pct": unoccupied_reserve_pct,
            "net_activation_score": round(net_score, 3),
            "net_activation": round(net_score, 3),
            "net_activation_pct": net_pct,
            "receptor_state": state_str,
            "dominant_compound": dominant["compound_label"],
            "regulation_state": regulation_state,
            "regulation_multiplier": regulation_multiplier,
            "compounds": incoming_compounds,
            "pharmacological_summary": summary_text,
        }

    return results

