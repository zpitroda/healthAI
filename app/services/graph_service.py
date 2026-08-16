from __future__ import annotations

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


def resolve_stack_to_catalog_keys(stack: List[Any] | None, catalog_service: CatalogService | None = None) -> List[str]:
    """Map raw user input compound names/synonyms to canonical catalog keys directly in the database."""
    if not stack:
        return []

    service = catalog_service or CatalogService()
    resolved: List[str] = []

    for item in stack:
        if isinstance(item, dict):
            candidate = item.get("compound") or item.get("key") or item.get("name")
        else:
            candidate = item

        text = str(candidate or "").strip()
        if not text:
            continue

        compound = service.get_compound(text)
        if compound and compound["key"] not in resolved:
            resolved.append(compound["key"])
        else:
            # Fallback search
            matches = service.search_compounds(text, limit=1)
            if matches and matches[0]["key"] not in resolved:
                resolved.append(matches[0]["key"])

    return resolved


def classify_target_action(action: Any) -> tuple[EdgeType, float]:
    """Classify pharmacological action description into a standardized edge type and vector magnitude."""
    normalized = str(action or "").lower()
    if "antagonist" in normalized or "antagonizes" in normalized or "blocker" in normalized or "blocks" in normalized:
        return EdgeType.ANTAGONIZES, -1.0
    if "agonist" in normalized or "agonizes" in normalized or "activator" in normalized or "activates" in normalized:
        return EdgeType.AGONIZES, 1.0
    if any(token in normalized for token in ["inhibitor", "inhibits", "inhibition", "suppresses"]):
        return EdgeType.INHIBITS_ENZYME, -0.8
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
            {"id": "pheno_sympathetic_activation", "label": "Sympathoadrenal Arousal, Lipolysis & Elevated Heart Rate", "cat": "therapeutic_benefit", "sev": "moderate", "mag": -0.85},
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
                "target_node_pattern": r"(?:pathway_beta_adrenergic|phys_sa_av_nodal_conduction)",
                "edge_type": EdgeType.ACTIVATES_PATHWAY,
                "vector_magnitude": -0.85,
                "description": "Surge in synaptic norepinephrine activates downstream cardiac beta-adrenergic inotropic/chronotropic signaling",
            },
        ],
    },
    {
        "target_pattern": r"(?:adenosine|a1|a2a)",
        "target_name": "Adenosine A1/A2A Receptor",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_adenosine_signaling",
            "label": "Adenosine / Adenylyl Cyclase Signaling",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_central_arousal",
            "label": "Central Catecholaminergic Tone & Autonomic Arousal",
            "organ": "Central Nervous System",
        },
        "biomarkers": [
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.6},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.5},
        ],
        "phenotypes": [
            {"id": "pheno_vigilance", "label": "Heightened Cognitive Vigilance & Reaction Time", "cat": "therapeutic_benefit", "sev": "moderate", "mag": 0.8},
            {"id": "pheno_insomnia", "label": "Sleep Onset Latency Increase & Sleep Fragmentation", "cat": "adverse_effect", "sev": "moderate", "mag": 0.7},
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
            {"id": "bio_resting_hr", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.4},
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
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.6},
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
            "label": "Hepatic LDL Receptor Upregulation & Sterol Homeostasis",
            "organ": "Hepatic",
        },
        "biomarkers": [
            {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50, "upper": 100, "mag": -0.85},
            {"id": "bio_alt", "label": "Alanine Aminotransferase (ALT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10, "upper": 45, "mag": 0.25},
        ],
        "phenotypes": [
            {"id": "pheno_athero_regression", "label": "Atherosclerotic Plaque Stabilization & Major Adverse Event Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.95},
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
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": -0.5},
        ],
        "phenotypes": [
            {"id": "pheno_hyperemia", "label": "Enhanced Endothelial Vasodilation & Skeletal Muscle Perfusion", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
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
            {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": -0.75},
            {"id": "bio_egfr", "label": "Glomerular Filtration Rate (eGFR)", "unit": "mL/min/1.73m²", "panel": "Renal Panel", "lower": 60, "upper": 120, "mag": -0.35},
        ],
        "phenotypes": [
            {"id": "pheno_antiinflammatory", "label": "Rapid Analgesia & Systemic Inflammation Suppression", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
            {"id": "pheno_renal_strain", "label": "Afferent Renal Vasoconstriction & Fluid Retention Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.65},
        ],
    },
    {
        "target_pattern": r"(?:5-alpha|reductase|dht|androgen)",
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
            {"id": "bio_dht", "label": "Serum Dihydrotestosterone (DHT)", "unit": "ng/dL", "panel": "Endocrine Panel", "lower": 30, "upper": 85, "mag": -0.8},
        ],
        "phenotypes": [
            {"id": "pheno_alopecia_halt", "label": "Arrest of Androgen-Driven Hair Follicle Miniaturization", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
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
        "target_pattern": r"(?:adrb1|adrb2|beta-1|beta-2|beta-adrenergic)",
        "target_name": "Beta-1 & Beta-2 Adrenergic Receptors (ADRB1/2)",
        "node_type": "receptor",
        "pathway": {
            "id": "pathway_beta_adrenergic",
            "label": "Beta-Adrenergic Gs/cAMP/PKA Positive Inotropic Cascade",
            "db": "Reactome",
        },
        "physiology": {
            "id": "phys_sa_av_nodal_conduction",
            "label": "Sinoatrial & Atrioventricular Nodal Automaticity & Conduction",
            "organ": "Cardiovascular",
        },
        "biomarkers": [
            {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.75},
            {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.5},
        ],
        "phenotypes": [
            {"id": "pheno_bradycardia_block", "label": "Symptomatic Bradycardia & High-Grade AV Nodal Block", "cat": "toxicity", "sev": "high", "mag": -0.8},
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
            {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70, "upper": 100, "mag": 0.8},
        ],
        "phenotypes": [
            {"id": "pheno_hypoglycemia_crisis", "label": "Severe Neuroglycopenic Hypoglycemia & Cognitive Collapse", "cat": "toxicity", "sev": "severe", "mag": -0.9},
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
            {"id": "bio_cns_arousal", "label": "Central Respiratory & Arousal Index", "unit": "index", "panel": "Neurologic Index", "lower": 50, "upper": 100, "mag": 0.85},
        ],
        "phenotypes": [
            {"id": "pheno_respiratory_arrest", "label": "Fatal Respiratory Depression, Hypoventilation & Coma", "cat": "toxicity", "sev": "severe", "mag": -0.95},
        ],
    },
]


def _normalize_target_node_id(raw_name: str) -> str:
    """Normalize target receptor and enzyme names to standard clinical IDs for multi-compound graph cross-talk."""
    cleaned = str(raw_name or "").strip()
    lower = cleaned.lower()
    if re.search(r"\b(?:beta-1|adrb1)\b", lower) or "beta-1 adrenergic" in lower:
        return "Beta-1 Adrenergic Receptor (ADRB1)"
    if re.search(r"\b(?:beta-2|adrb2)\b", lower) or "beta-2 adrenergic" in lower:
        return "Beta-2 Adrenergic Receptor (ADRB2)"
    if re.search(r"\b(?:alpha-2a|adra2a)\b", lower) or "alpha-2a adrenergic" in lower:
        return "Alpha-2A Adrenergic Receptor (ADRA2A)"
    if re.search(r"\b(?:alpha-2b|adra2b)\b", lower) or "alpha-2b adrenergic" in lower:
        return "Alpha-2B Adrenergic Receptor (ADRA2B)"
    if re.search(r"\b(?:alpha-2c|adra2c)\b", lower) or "alpha-2c adrenergic" in lower:
        return "Alpha-2C Adrenergic Receptor (ADRA2C)"
    if re.search(r"\b(?:alpha-1a|adra1a)\b", lower) or "alpha-1a adrenergic" in lower:
        return "Alpha-1A Adrenergic Receptor (ADRA1A)"
    if re.search(r"\b(?:at1|agtr1)\b", lower) or "type-1 angiotensin" in lower or "angiotensin ii type-1" in lower:
        return "Angiotensin II Type-1 Receptor (AGTR1)"
    if re.search(r"\b(?:nr3c2|mineralocorticoid)\b", lower) or "mineralocorticoid receptor" in lower or "aldosterone receptor" in lower:
        return "Mineralocorticoid Receptor (NR3C2)"
    if re.search(r"\b(?:kcnh2|herg)\b", lower) or "voltage-gated potassium channel" in lower:
        return "Voltage-Gated Potassium Channel (hERG / KCNH2)"
    if re.search(r"\b(?:glp1r|glp-1)\b", lower) or "glucagon-like peptide 1" in lower:
        return "GLP-1 Receptor (GLP1R)"
    if re.search(r"\b(?:pde5|pde5a)\b", lower) or "phosphodiesterase 5" in lower:
        return "Phosphodiesterase 5A (PDE5)"
    if re.search(r"\b(?:sert|slc6a4)\b", lower) or "serotonin transporter" in lower:
        return "Serotonin Transporter (SERT / SLC6A4)"
    if re.search(r"\b(?:dat|slc6a3)\b", lower) or "dopamine transporter" in lower:
        return "Dopamine Transporter (DAT / SLC6A3)"
    if re.search(r"\b(?:gabra1|gaba-a|gaba_a)\b", lower) or "gamma-aminobutyric" in lower:
        return "GABA-A Receptor (GABRA1)"
    if re.search(r"\b(?:oprm1|mu-opioid)\b", lower) or "mu-type opioid receptor" in lower:
        return "Mu-Opioid Receptor (OPRM1)"
    if re.search(r"\b(?:htr1a|5-ht1a)\b", lower) or "5-hydroxytryptamine receptor 1a" in lower:
        return "5-HT1A Receptor (HTR1A)"
    if re.search(r"\b(?:ar|nr3c4)\b", lower) or "androgen receptor" in lower:
        return "Androgen Receptor (AR / NR3C4)"
    return cleaned


def build_selected_compound_graph(stack: List[str], catalog_service: CatalogService | None = None) -> BiologicalGraph:
    """
    Builds a multi-tier dynamic biological cascade graph for the selected stack:
    Tier 1: Compound Nodes (with ADMET properties)
    Tier 2: Molecular Target Nodes (Receptors, Enzymes, Transporters)
    Tier 3: Intracellular Signaling Pathway Nodes (Reactome)
    Tier 4: Organ & Physiological Function Nodes (with dynamic cross-talk bridges)
    Tier 5: Clinical Laboratory Biomarker Nodes
    Tier 6: Clinical Phenotype & Safety Outcome Nodes
    """
    service = catalog_service or CatalogService()
    resolved_stack = list(dict.fromkeys(item for item in resolve_stack_to_catalog_keys(stack, service) if item))

    if not resolved_stack:
        return build_testosterone_alopecia_graph()

    graph = BiologicalGraph()

    for compound_key in resolved_stack:
        compound = service.get_compound(compound_key)
        if compound is None:
            graph.add_node(
                CompoundNode(
                    node_id=compound_key,
                    label=compound_key.title(),
                )
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
            )
        )

        receptor_targets = compound.get("receptor_targets") or []
        mechanism_text = str(compound.get("mechanism") or "").lower()

        # Connect Targets & Multi-Tier Cascades
        for receptor in receptor_targets:
            if not isinstance(receptor, dict):
                continue
            target_raw = str(receptor.get("target") or receptor.get("name") or "unknown_target").strip()
            if not target_raw:
                continue

            target_id = target_raw
            target_label = target_raw
            edge_type, vector_magnitude = classify_target_action(receptor.get("action"))

            # Add Target Node
            graph.add_node(
                ReceptorNode(
                    node_id=target_id,
                    label=target_label,
                    receptor_family=receptor.get("family") or "Molecular Target",
                )
            )

            # Edge 1: Compound -> Target
            graph.add_edge(
                compound_id,
                target_id,
                edge_type=edge_type,
                edge_data=EdgeData(
                    affinity_ki=receptor.get("affinity_ki"),
                    inhibition_ic50=receptor.get("inhibition_ic50"),
                    vector_magnitude=vector_magnitude,
                ),
            )

            # Check Canonical Cascade Mapping
            target_lower = target_id.lower()
            for cascade in CANONICAL_TARGET_CASCADES:
                if re.search(cascade["target_pattern"], target_lower) or (not receptor_targets and re.search(cascade["target_pattern"], mechanism_text)):
                    p_info = cascade["pathway"]
                    phys_info = cascade["physiology"]

                    # Add Pathway Node
                    graph.add_node(
                        SignalingPathwayNode(
                            node_id=p_info["id"],
                            label=p_info["label"],
                            pathway_database=p_info["db"],
                        )
                    )

                    # Edge 2: Target -> Pathway
                    graph.add_edge(
                        target_id,
                        p_info["id"],
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
                        p_info["id"],
                        phys_info["id"],
                        edge_type=EdgeType.ALTERS_PHYSIOLOGY,
                        edge_data=EdgeData(vector_magnitude=1.0),
                    )

                    # Add Biomarkers & Edges
                    for b_info in cascade.get("biomarkers", []):
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
                        b_mag = float(b_info.get("mag", 1.0))
                        graph.add_edge(
                            phys_info["id"],
                            b_info["id"],
                            edge_type=EdgeType.MODIFIES_BIOMARKER,
                            edge_data=EdgeData(vector_magnitude=b_mag),
                        )

                    # Add Phenotypes & Edges
                    for pheno in cascade.get("phenotypes", []):
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
                    break

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
            for node in list(graph.graph.nodes()):
                if node == phys_id:
                    continue
                node_label = str(graph.graph.nodes[node].get("label", node)).lower()
                node_id_lower = str(node).lower()
                if re.search(pattern, node_label) or re.search(pattern, node_id_lower):
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

    start_nodes = [item for item in raw_items if item in graph.graph]
    if not start_nodes and normalized_stack:
        start_nodes = [item for item in normalized_stack if item in graph.graph]

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
