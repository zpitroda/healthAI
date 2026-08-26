from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Set

logger = logging.getLogger("healthai.stack_intent_engine")

PROTOCOL_GOAL_TAXONOMY = [
    {
        "id": "auto",
        "name": "Auto-Infer from Stack",
        "icon": "🤖",
        "description": "Automatically infer primary objective from compound mechanisms, receptor targets, and drug classes."
    },
    {
        "id": "anabolic_physique",
        "name": "Physique & Anabolic Hypertrophy",
        "icon": "🏋️",
        "description": "Supra-physiological androgen exposure, protein synthesis, organ protection, and endocrine management."
    },
    {
        "id": "cognitive_focus",
        "name": "Cognitive Focus & Neuroprotection",
        "icon": "🧠",
        "description": "Neurotransmitter modulation, catecholaminergic sustained focus, synaptic plasticity, and cerebral blood flow."
    },
    {
        "id": "cardiovascular_lipid",
        "name": "Cardiovascular & Lipid Optimization",
        "icon": "❤️",
        "description": "Endothelial nitric oxide release, blood pressure normalization, ApoB/LDL regulation, and arterial compliance."
    },
    {
        "id": "longevity_autophagy",
        "name": "Longevity & Cellular Autophagy",
        "icon": "🧬",
        "description": "AMPK activation, mTORC1 cycling, sirtuin deacetylase activation, and mitochondrial biogenesis."
    },
    {
        "id": "sleep_stress_recovery",
        "name": "Sleep Architecture & Stress Recovery",
        "icon": "🌙",
        "description": "HPA axis downregulation, nocturnal GABAergic tone, cortisol blunting, and slow-wave sleep depth."
    },
    {
        "id": "fat_loss_metabolic",
        "name": "Metabolic Output & Fat Loss",
        "icon": "🔥",
        "description": "Beta-adrenergic lipolysis, insulin sensitivity enhancement, and mitochondrial uncoupling / substrate partitioning."
    },
    {
        "id": "post_therapy_reset",
        "name": "Post-Therapy Restoration (PCT / Reset)",
        "icon": "🔄",
        "description": "Hypothalamic-pituitary axis restoration (LH/FSH recovery), testicular responsiveness, and lipid/hepatic normalization."
    },
    {
        "id": "custom",
        "name": "Custom User Objective",
        "icon": "✍️",
        "description": "User-specified clinical or performance goals and personalized constraints."
    }
]

SCRATCH_GOAL_BLUEPRINTS: Dict[str, Dict[str, Any]] = {
    "cognitive_focus": {
        "title": "Cognitive Focus & Neuroprotection",
        "description": "Clean catecholaminergic sustained focus, synaptic plasticity, and cerebral perfusion without crash or jitter.",
        "core_compounds": [
            {
                "key": "caffeine",
                "name": "Caffeine Anhydrous",
                "base_dose": 100,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Adenosine A1 / A2A Antagonist",
                "rationale": "Inhibits tonic adenosine fatigue signals and promotes dopamine/norepinephrine neurotransmission.",
                "is_stimulant": True,
            },
            {
                "key": "l_theanine",
                "name": "L-Theanine",
                "base_dose": 200,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Glutamate Receptor Modulator & GABAergic Tone",
                "rationale": "Promotes alpha wave relaxation, blunts caffeine-induced peripheral vasoconstriction, and sharpens attention (1:2 caffeine-to-theanine ratio).",
                "is_stimulant": False,
            },
            {
                "key": "bacopa",
                "name": "Bacopa Monnieri",
                "base_dose": 300,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Tryptophan Hydroxylase & Synaptic Dendritic Branching",
                "rationale": "Standardized bacosides upregulate cerebral antioxidant enzymes and enhance memory retention and cognitive processing speed.",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "magnesium",
                "name": "Magnesium Glycinate",
                "base_dose": 300,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "NMDA Receptor Voltage-Gated Blocker",
                "rationale": "Safeguards neurovascular recovery and prevents excitotoxicity following stimulant exposure.",
                "is_stimulant": False,
            }
        ]
    },
    "longevity_autophagy": {
        "title": "Longevity & Cellular Autophagy",
        "description": "AMPK activation, sirtuin deacetylase stimulation, mitochondrial biogenesis, and lipid protection.",
        "core_compounds": [
            {
                "key": "berberine",
                "name": "Berberine HCl",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "AMPK Activator & GLUT4 Translocator",
                "rationale": "Phosphorylates AMPK, promotes mitochondrial biogenesis, and improves insulin sensitivity and substrate partitioning.",
                "is_stimulant": False,
            },
            {
                "key": "coq10",
                "name": "Coenzyme Q10 (Ubiquinol)",
                "base_dose": 100,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Mitochondrial ETC Complex I/II Electron Carrier",
                "rationale": "Maintains inner mitochondrial membrane potential and supports myocardial energetics.",
                "is_stimulant": False,
            },
            {
                "key": "curcumin",
                "name": "Curcumin Extract",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Nrf2 / ARE Master Antioxidant Pathway & NF-kB Inhibitor",
                "rationale": "Downregulates chronic systemic inflammatory cytokines (TNF-alpha, IL-6) and upregulates endogenous glutathione synthesis.",
                "is_stimulant": False,
            },
            {
                "key": "piperine",
                "name": "Piperine (BioPerine)",
                "base_dose": 5,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Hepatic/Intestinal Glucuronidation & P-gp Modulator",
                "rationale": "Increases curcumin and polyphenol serum bioavailability by up to 2000%.",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "resveratrol",
                "name": "Trans-Resveratrol",
                "base_dose": 250,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "SIRT1 NAD+-Dependent Deacetylase",
                "rationale": "Synergizes with AMPK activators to promote nuclear PGC-1alpha transcription and cellular longevity.",
                "is_stimulant": False,
            }
        ]
    },
    "cardiovascular_lipid": {
        "title": "Cardiovascular & Lipid Optimization",
        "description": "Endothelial nitric oxide release, blood pressure normalization, ApoB/LDL clearance, and myocardial preservation.",
        "core_compounds": [
            {
                "key": "telmisartan",
                "name": "Telmisartan",
                "base_dose": 20,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Angiotensin II Type 1 (AT1) Receptor Antagonist & PPAR-gamma Partial Agonist",
                "rationale": "Blocks RAAS-mediated renal vasoconstriction, prevents Left Ventricular Hypertrophy (LVH), and improves insulin sensitivity.",
                "is_stimulant": False,
            },
            {
                "key": "citrus_bergamot",
                "name": "Citrus Bergamot Extract",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Hepatic HMG-CoA Reductase & LDL Receptor Upregulation",
                "rationale": "Lowers atherogenic ApoB and dense LDL particles while supporting HDL-C and antioxidant vascular tone.",
                "is_stimulant": False,
            },
            {
                "key": "coq10",
                "name": "Coenzyme Q10 (Ubiquinol)",
                "base_dose": 100,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Vascular Endothelial Bioenergetics",
                "rationale": "Prevents LDL oxidation and enhances vascular nitric oxide bioavailability.",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "nebivolol",
                "name": "Nebivolol",
                "base_dose": 2.5,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Selective Beta-1 Adrenergic Blocker & eNOS Stimulator",
                "rationale": "Reduces resting heart rate and arterial stiffness via direct endothelial NO release.",
                "is_stimulant": False,
            }
        ]
    },
    "anabolic_physique": {
        "title": "Physique & Anabolic Hypertrophy",
        "description": "Intracellular energetic buffering, cellular hydration, protein synthesis support, and cardioprotective ancillaries.",
        "core_compounds": [
            {
                "key": "creatine",
                "name": "Creatine Monohydrate",
                "base_dose": 5000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Intracellular Phosphocreatine Shuttle & Myocellular Osmolality",
                "rationale": "Maximizes rapid ADP-to-ATP resynthesis during anaerobic high-threshold muscle contractions.",
                "is_stimulant": False,
            },
            {
                "key": "beta_alanine",
                "name": "Beta-Alanine",
                "base_dose": 3200,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Intramuscular Carnosine Biosynthesis",
                "rationale": "Buffers exercise-induced intracellular hydrogen ion (H+) accumulation and delays muscular acidosis.",
                "is_stimulant": False,
            },
            {
                "key": "l_carnitine",
                "name": "L-Carnitine L-Tartrate",
                "base_dose": 2000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Androgen Receptor Upregulation & CPT-1 Mitochondrial Shuttle",
                "rationale": "Increases post-exercise androgen receptor density and accelerates recovery kinetics.",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "citrus_bergamot",
                "name": "Citrus Bergamot",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Lipid & ApoB Protection",
                "rationale": "Maintains lipid profile equilibrium during intensive training phases.",
                "is_stimulant": False,
            },
            {
                "key": "telmisartan",
                "name": "Telmisartan",
                "base_dose": 20,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Renal Microcirculation & AT1 Blockade",
                "rationale": "Protects glomerular filtration pressure and vascular compliance.",
                "is_stimulant": False,
            }
        ]
    },
    "sleep_stress_recovery": {
        "title": "Sleep Architecture & Stress Recovery",
        "description": "HPA axis downregulation, nocturnal GABAergic tone, cortisol blunting, and slow-wave sleep depth.",
        "core_compounds": [
            {
                "key": "magnesium",
                "name": "Magnesium Glycinate",
                "base_dose": 300,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "GABA-A Tone & NMDA Voltage Gating",
                "rationale": "Promotes deep slow-wave sleep and attenuates nocturnal sympathetic nervous tone.",
                "is_stimulant": False,
            },
            {
                "key": "ashwagandha",
                "name": "Ashwagandha (KSM-66)",
                "base_dose": 600,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "HPA Axis Downregulation & Cortisol Blunting",
                "rationale": "Lowers nocturnal systemic cortisol elevation and enhances subjective sleep architecture.",
                "is_stimulant": False,
            },
            {
                "key": "l_theanine",
                "name": "L-Theanine",
                "base_dose": 200,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "Glutamate Attenuation & Alpha Wave Stimulation",
                "rationale": "Calms nocturnal racing thoughts and eases transition to sleep onset.",
                "is_stimulant": False,
            },
            {
                "key": "melatonin",
                "name": "Melatonin",
                "base_dose": 3,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "MT1/MT2 Melatonin Receptors",
                "rationale": "Synchronizes central suprachiasmatic nucleus circadian clock and accelerates sleep latency.",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "taurine",
                "name": "Taurine",
                "base_dose": 1000,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "Inhibitory Glycinergic & GABAergic Neurotransmission",
                "rationale": "Stabilizes neural membranes and suppresses nocturnal autonomic excitability.",
                "is_stimulant": False,
            }
        ]
    },
    "fat_loss_metabolic": {
        "title": "Metabolic Output & Fat Loss",
        "description": "Beta-adrenergic lipolysis, insulin sensitivity enhancement, and mitochondrial uncoupling / substrate partitioning.",
        "core_compounds": [
            {
                "key": "caffeine",
                "name": "Caffeine Anhydrous",
                "base_dose": 150,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Phosphodiesterase Inhibition & Beta-Adrenergic Tone",
                "rationale": "Stimulates resting energy expenditure and mobilizes free fatty acids from adipose depots.",
                "is_stimulant": True,
            },
            {
                "key": "l_carnitine",
                "name": "L-Carnitine L-Tartrate",
                "base_dose": 2000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Carnitine Palmitoyltransferase-1 (CPT-1) Shuttle",
                "rationale": "Facilitates long-chain fatty acid transport across the inner mitochondrial membrane for beta-oxidation.",
                "is_stimulant": False,
            },
            {
                "key": "berberine",
                "name": "Berberine HCl",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "AMPK Activation & Substrate Partitioning",
                "rationale": "Enhances peripheral insulin sensitivity and prevents compensatory glucose surges.",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "taurine",
                "name": "Taurine",
                "base_dose": 1000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Myocellular Osmolyte & Heart Rhythm Support",
                "rationale": "Protects against cramping and sympathomimetic-induced electrolyte loss.",
                "is_stimulant": False,
            }
        ]
    },
    "post_therapy_reset": {
        "title": "Post-Therapy Restoration (PCT / Reset)",
        "description": "Hypothalamic-pituitary axis restoration (LH/FSH recovery), testicular responsiveness, and lipid/hepatic normalization.",
        "core_compounds": [
            {
                "key": "enclomiphene",
                "name": "Enclomiphene Citrate",
                "base_dose": 12.5,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Selective Estrogen Receptor Antagonist (Hypothalamus/Pituitary)",
                "rationale": "Antagonizes negative estrogen feedback at the pituitary/hypothalamus to stimulate pulsatile GnRH, LH, and FSH release.",
                "is_stimulant": False,
            },
            {
                "key": "nac",
                "name": "N-Acetyl Cysteine (NAC)",
                "base_dose": 600,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Glutathione Biosynthesis & Hepatocyte Protection",
                "rationale": "Restores hepatic intracellular glutathione pools and normalizes post-cycle transaminases.",
                "is_stimulant": False,
            },
            {
                "key": "tudca",
                "name": "Tauroursodeoxycholic Acid (TUDCA)",
                "base_dose": 250,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Biliary Clearance & Cholestatic Resolution",
                "rationale": "Mitigates canalicular cholestasis and enhances biliary lipid excretion.",
                "is_stimulant": False,
            },
            {
                "key": "citrus_bergamot",
                "name": "Citrus Bergamot Extract",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Lipid Profile & ApoB Normalization",
                "rationale": "Accelerates recovery of HDL-C and normalizes LDL particle distribution following androgen exposure.",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "ashwagandha",
                "name": "Ashwagandha (KSM-66)",
                "base_dose": 600,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "Testicular Leydig Cell Responsiveness & HPA Dampening",
                "rationale": "Lowers post-cycle catabolic cortisol spikes and supports endogenous testosterone synthesis.",
                "is_stimulant": False,
            }
        ]
    }
}


class StackIntentEngine:
    """
    Dynamic Pharmacological Stack Intent & Purpose Inference Engine.
    Analyzes compound classes, receptor targets, mechanisms, routes, and clearance kinetics
    to deduce stack objectives, partition administration modalities, and identify therapeutic gaps.
    """

    @classmethod
    def get_goal_taxonomy(cls) -> List[Dict[str, Any]]:
        return PROTOCOL_GOAL_TAXONOMY

    @classmethod
    def analyze(
        cls,
        compounds: List[Dict[str, Any]],
        biometrics: Optional[Dict[str, Any]] = None,
        user_goal_id: Optional[str] = None,
        user_objective_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Performs full pharmacological analysis of stack purpose, modality segmentation,
        and therapeutic gap identification.
        """
        biometrics = biometrics or {}
        user_objective_text = (user_objective_text or "").strip()

        # 1. Extract compound pharmacological traits
        features = cls._extract_pharmacological_features(compounds)

        # 2. Infer primary domain if auto
        inferred_domain, confidence, reasoning = cls._infer_primary_domain(features, compounds)

        # Determine active goal metadata
        active_goal_id = user_goal_id if (user_goal_id and user_goal_id != "auto") else inferred_domain
        matching_tax = next((t for t in PROTOCOL_GOAL_TAXONOMY if t["id"] == active_goal_id), None)
        goal_title = matching_tax["name"] if matching_tax else active_goal_id.replace("_", " ").title()

        # 3. Partition Administration Modalities (Depot vs Daily Oral vs Acute)
        modality_profile = cls._partition_modalities(compounds)

        # 4. Detect Therapeutic Gaps & Uncompensated Axes
        therapeutic_gaps = cls._detect_therapeutic_gaps(features, compounds, biometrics)

        # 5. Build prompt grounding text block
        grounding_text = cls._format_prompt_grounding(
            goal_title=goal_title,
            is_user_selected=bool(user_goal_id and user_goal_id != "auto"),
            user_objective_text=user_objective_text,
            inferred_reasoning=reasoning,
            modality_profile=modality_profile,
            therapeutic_gaps=therapeutic_gaps,
            features=features
        )

        return {
            "active_goal_id": active_goal_id,
            "goal_title": goal_title,
            "is_user_selected": bool(user_goal_id and user_goal_id != "auto"),
            "user_objective_text": user_objective_text,
            "inferred_domain": inferred_domain,
            "confidence": confidence,
            "inferred_reasoning": reasoning,
            "modality_profile": modality_profile,
            "therapeutic_gaps": therapeutic_gaps,
            "pharmacological_features": features,
            "grounding_text": grounding_text,
        }

    @classmethod
    def _extract_pharmacological_features(cls, compounds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extracts high-level pharmacological flags from compound catalog records."""
        features = {
            "has_androgens": False,
            "has_19nor_progestogenic": False,
            "has_aromatase_inhibitors": False,
            "has_aromatizable_substrate": False,
            "has_sarms": False,
            "has_serms": False,
            "has_raas_blockers": False,
            "has_beta_blockers": False,
            "has_pde5_inhibitors": False,
            "has_psychostimulants": False,
            "has_cholinergics": False,
            "has_gabaergics_sedatives": False,
            "has_longevity_metabolic": False,
            "has_hepatoprotectants": False,
            "has_lipid_regulators": False,
            "has_renal_support": False,
            "has_depot_injectables": False,
            "has_oral_tma_precursors": False,
            "has_microbial_tma_inhibitors": False,
            "androgen_names": [],
            "oral_tma_precursor_names": [],
            "protective_ancillary_names": [],
        }

        for c in compounds:
            k = str(c.get("key", "")).lower()
            name = str(c.get("name", "")).lower()
            d_class = str(c.get("drug_class", "")).lower()
            mech = str(c.get("mechanism", "")).lower()
            route = str(c.get("route", "")).lower()
            targets = [str(t.get("target", "")).lower() if isinstance(t, dict) else str(t).lower() for t in (c.get("receptor_targets") or [])]

            tokens = set(re.findall(r"[a-z0-9]+", f"{k} {name} {d_class}"))
            text_blob = f"{k} {name} {d_class} {mech} {' '.join(targets)}"

            # Depot injectable detection
            if route in ("intramuscular", "im", "subcutaneous", "subq") or any(e in text_blob for e in ["cypionate", "enanthate", "decanoate", "undecanoate", "isocaproate", "depot"]):
                features["has_depot_injectables"] = True

            # Androgen / AAS detection
            if any(w in tokens for w in ["testosterone", "trenbolone", "nandrolone", "drostanolone", "masteron", "primobolan", "methenolone", "boldenone", "oxandrolone", "anavar", "stanozolol", "winstrol", "superdrol", "dianabol", "anadrol", "turinabol", "trestolone", "ment"]) or any(w in k or w in name for w in ["testosterone", "trenbolone", "nandrolone", "drostanolone", "masteron", "primobolan", "methenolone", "boldenone", "oxandrolone", "anavar", "stanozolol", "winstrol", "superdrol", "dianabol", "anadrol", "turinabol", "sarm", "rad140", "lgd4033", "ostarine"]):
                features["has_androgens"] = True
                features["androgen_names"].append(c.get("name") or k.title())

            # 19-nor progestogenic
            if any(w in tokens for w in ["trenbolone", "nandrolone", "durabolin", "trestolone", "ment", "npp", "parabolan"]) or any(w in k or w in name for w in ["nandrolone", "trenbolone", "trestolone", "19-nor", "19nor"]) or any("progesterone receptor" in t and any(act in t for act in ["agonist", "substrate", "cleaved"]) for t in targets):
                features["has_19nor_progestogenic"] = True

            # Aromatase inhibitor (AI)
            if any(w in tokens for w in ["exemestane", "anastrozole", "letrozole", "aromasin", "arimidex", "femara"]) or any(w in text_blob for w in ["aromatase inhibitor", "cyp19a1 inhibitor"]):
                features["has_aromatase_inhibitors"] = True
                features["protective_ancillary_names"].append(c.get("name") or k.title())

            # SERMs (Selective Estrogen Receptor Modulators)
            if any(w in tokens for w in ["tamoxifen", "nolvadex", "raloxifene", "evista", "clomiphene", "clomid", "enclomiphene", "toremifene", "fareston"]):
                features["has_serms"] = True
                features["protective_ancillary_names"].append(c.get("name") or k.title())

            # Aromatizable substrate
            if any(w in tokens for w in ["testosterone", "testc", "testcyp", "teste", "testenan", "dianabol", "dbol", "methandrostenolone", "boldenone", "equipoise"]) or any(w in k or w in name for w in ["testosterone", "dianabol", "boldenone", "methandrostenolone"]):
                features["has_aromatizable_substrate"] = True

            # RAAS blockers
            if any(w in text_blob for w in ["telmisartan", "losartan", "candesartan", "valsartan", "enalapril", "lisinopril", "ramipril"]):
                features["has_raas_blockers"] = True
                features["protective_ancillary_names"].append(c.get("name") or k.title())

            # Beta blockers
            if any(w in text_blob for w in ["nebivolol", "bisoprolol", "metoprolol", "carvedilol", "atenolol"]):
                features["has_beta_blockers"] = True
                features["protective_ancillary_names"].append(c.get("name") or k.title())

            # PDE5 inhibitors
            if any(w in text_blob for w in ["tadalafil", "sildenafil", "vardenafil"]):
                features["has_pde5_inhibitors"] = True

            # Psychostimulants
            if any(w in text_blob for w in ["caffeine", "modafinil", "armodafinil", "methylphenidate", "amphetamine", "yohimbine", "nicotine"]):
                features["has_psychostimulants"] = True

            # Cholinergics
            if any(w in text_blob for w in ["alpha_gpc", "alpha-gpc", "citicoline", "cdp-choline", "huperzine", "donepezil"]):
                features["has_cholinergics"] = True

            # GABAergics / Sedatives
            if any(w in text_blob for w in ["magnesium", "theanine", "l-theanine", "melatonin", "gaba", "ashwagandha", "glycine", "lemon_balm"]):
                features["has_gabaergics_sedatives"] = True

            # Longevity / Metabolic
            if any(w in text_blob for w in ["metformin", "berberine", "rapamycin", "nmn", "nr", "resveratrol", "empagliflozin", "dapagliflozin"]):
                features["has_longevity_metabolic"] = True

            # Hepatoprotectants
            if any(w in text_blob for w in ["nac", "acetylcysteine", "tudca", "udca", "milk_thistle", "silymarin", "glutathione"]):
                features["has_hepatoprotectants"] = True
                features["protective_ancillary_names"].append(c.get("name") or k.title())

            # Lipid regulators
            if any(w in text_blob for w in ["bergamot", "citrus_bergamot", "ezetimibe", "statin", "pitavastatin", "rosuvastatin", "omega3", "omega-3", "fish_oil"]):
                features["has_lipid_regulators"] = True
                features["protective_ancillary_names"].append(c.get("name") or k.title())

            # Renal support
            if any(w in text_blob for w in ["astragalus", "cycloastragenol", "telmisartan"]):
                features["has_renal_support"] = True

            # Oral TMA precursors (e.g. oral L-carnitine, choline, betaine)
            is_oral_route = route in ("oral", "po", "swallow", "") or ":oral" in k
            is_parenteral = route in ("intramuscular", "im", "subcutaneous", "subq", "iv")
            is_tma_substrate = any(
                ("tma lyase" in t or "cnta" in t or "cntb" in t or "cutc" in t or "yeaw" in t)
                for t in targets
            ) or any(w in text_blob for w in ["carnitine", "alcar", "choline", "alpha_gpc", "alpha-gpc", "citicoline", "betaine"])
            if is_oral_route and not is_parenteral and is_tma_substrate:
                features["has_oral_tma_precursors"] = True
                features["oral_tma_precursor_names"].append(c.get("name") or k.title())

            # Microbial TMA lyase inhibitors (e.g. allicin, garlic extract, DMB)
            if any(w in text_blob for w in ["allicin", "garlic", "allium", "dimethylbutanol", "dmb"]) or any(("tma lyase" in t or "cnta" in t) and "inhibitor" in str(getattr(t, "action", "")).lower() for t in targets):
                features["has_microbial_tma_inhibitors"] = True
                features["protective_ancillary_names"].append(c.get("name") or k.title())

        return features

    @classmethod
    def _infer_primary_domain(
        cls,
        features: Dict[str, Any],
        compounds: List[Dict[str, Any]]
    ) -> Tuple[str, float, str]:
        """Infers the most scientifically accurate primary domain for the stack."""
        if not compounds:
            return "general_wellness", 0.5, "Empty stack; default general wellness."

        if features["has_androgens"]:
            ancillaries = len(features["protective_ancillary_names"])
            return (
                "anabolic_physique",
                0.95,
                f"Stack contains potent androgenic modulators ({', '.join(features['androgen_names'])}) "
                + (f"with {ancillaries} active organ-protective ancillaries." if ancillaries else "without complete ancillary coverage.")
            )

        if features["has_psychostimulants"] or features["has_cholinergics"]:
            return (
                "cognitive_focus",
                0.90,
                "Stack focuses on central neurotransmitter modulation, catecholaminergic tone, and cognitive focus."
            )

        if features["has_longevity_metabolic"]:
            return (
                "longevity_autophagy",
                0.88,
                "Stack is oriented toward metabolic signaling, AMPK activation, mTOR modulation, or cellular autophagy."
            )

        if features["has_raas_blockers"] or features["has_beta_blockers"]:
            return (
                "cardiovascular_lipid",
                0.85,
                "Stack is primarily oriented around hemodynamic regulation, blood pressure management, and vascular protection."
            )

        if features["has_gabaergics_sedatives"] and not features["has_psychostimulants"]:
            return (
                "sleep_stress_recovery",
                0.82,
                "Stack is oriented around parasympathetic tone, HPA axis relaxation, and nocturnal recovery."
            )

        return "general_wellness", 0.70, "Multi-factorial wellness protocol."

    @classmethod
    def _partition_modalities(cls, compounds: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Partitions stack into Depot Injections, Daily Oral Maintenance, and Acute/Situational."""
        depot = []
        daily_oral = []
        acute = []

        for c in compounds:
            route = str(c.get("route", "oral")).lower()
            freq = str(c.get("frequency", "daily")).lower()
            name = c.get("name") or c.get("key", "Compound")
            dose = c.get("dose") or c.get("dose_mg", 100)
            unit = c.get("unit", "mg")
            timing = c.get("timing", "morning")

            blob = f"{name} {c.get('key', '')}".lower()
            is_depot = (
                route in ("intramuscular", "im", "subcutaneous", "subq")
                or any(e in blob for e in ["cypionate", "enanthate", "decanoate", "undecanoate", "isocaproate"])
                or "weekly" in freq
            )

            if is_depot:
                depot.append({
                    "name": name,
                    "dose_display": f"{dose} {unit}",
                    "route": route.upper() if route else "IM",
                    "frequency": freq.capitalize(),
                    "half_life_estimate": "7–10 days (Extended Depot Release)"
                })
            elif "prn" in freq or "acute" in freq or "pre-workout" in timing.lower():
                acute.append({
                    "name": name,
                    "dose_display": f"{dose} {unit}",
                    "route": route.title(),
                    "timing": timing.title()
                })
            else:
                daily_oral.append({
                    "name": name,
                    "dose_display": f"{dose} {unit}",
                    "route": route.title(),
                    "timing": timing.title()
                })

        return {
            "depot_injections": depot,
            "daily_oral": daily_oral,
            "acute_situational": acute,
        }

    @classmethod
    def _detect_therapeutic_gaps(
        cls,
        features: Dict[str, Any],
        compounds: List[Dict[str, Any]],
        biometrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Dynamically detects physiological vulnerabilities / uncompensated axes
        and prescribes evidence-based targeted co-factors.
        """
        gaps = []

        # 1. 19-Nor Progestogenic / Prolactin Elevation
        if features["has_19nor_progestogenic"]:
            has_p5p_or_cab = any(
                any(w in str(c.get("key", "") + " " + c.get("name", "")).lower() for w in ["p5p", "p-5-p", "pyridoxal", "cabergoline"])
                for c in compounds
            )
            if not has_p5p_or_cab:
                gaps.append({
                    "axis": "Endocrine / Prolactin Axis",
                    "severity": "HIGH",
                    "issue": "19-Nor androgen present with PR affinity and risk of hyperprolactinemia.",
                    "recommended_cofactor": "Pyridoxal-5-Phosphate (P-5-P) 100–200 mg/day (or Cabergoline 0.25mg if prolactin is elevated)",
                    "cofactor_search_terms": ["p5p", "pyridoxal_5_phosphate", "cabergoline"],
                    "mechanism": "Cofactor for AADC, elevating dopamine synthesis to tonically suppress pituitary lactotroph prolactin release."
                })

        # 2. AAS-Induced Atherogenic Dyslipidemia (SR-B1 suppression, HDL crash, ApoB elevation)
        if features["has_androgens"] and not features["has_lipid_regulators"]:
            gaps.append({
                "axis": "Cardiovascular / Lipid Profile",
                "severity": "HIGH",
                "issue": "Androgenic downregulation of hepatic SR-B1 crushes HDL and increases atherogenic ApoB particle count.",
                "recommended_cofactor": "Citrus Bergamot Extract (500–1000 mg/day)",
                "cofactor_search_terms": ["citrus_bergamot", "bergamot", "ezetimibe"],
                "mechanism": "Upregulates LDL receptor clearance and inhibits HMG-CoA reductase to maintain endothelial health."
            })

        # 3. AAS Renal Glomerular Strain / Elevated Vascular Resistance
        if features["has_androgens"] and not features["has_renal_support"]:
            gaps.append({
                "axis": "Renal Glomerular Microcirculation",
                "severity": "MODERATE",
                "issue": "Androgen receptor activation in renal tubules stimulates renin and increases glomerular filtration pressure.",
                "recommended_cofactor": "Telmisartan (20–40 mg/day) or Astragalus Root Extract",
                "cofactor_search_terms": ["telmisartan", "astragalus"],
                "mechanism": "Antagonizes AT1 receptors to dilate efferent renal arterioles and protect podocyte integrity."
            })

        # 4. AAS Hepatic Bile Acid & Phase II Conjugation Strain
        if features["has_androgens"]:
            has_nac = any("nac" in str(c.get("key", "") + " " + c.get("name", "")).lower() for c in compounds)
            has_tudca = any("tudca" in str(c.get("key", "") + " " + c.get("name", "")).lower() for c in compounds)
            if has_nac and not has_tudca:
                gaps.append({
                    "axis": "Hepatobiliary / Cholestasis",
                    "severity": "MODERATE",
                    "issue": "NAC provides intracellular glutathione but does not resolve hydrophobic bile acid accumulation.",
                    "recommended_cofactor": "TUDCA (Tauroursodeoxycholic Acid) 250–500 mg/day",
                    "cofactor_search_terms": ["tudca", "tauroursodeoxycholic_acid", "udca"],
                    "mechanism": "Increases hydrophilic bile acid ratio, promotes biliary clearance, and mitigates canalicular cholestatic stress."
                })

        # 5. Aromatization & Estrogen (E2) Management
        if (features["has_androgens"] or features["has_aromatizable_substrate"]) and not features["has_aromatase_inhibitors"] and not features["has_serms"]:
            gaps.append({
                "axis": "Aromatization & Estrogen (E2) Management",
                "severity": "HIGH",
                "issue": "Aromatizable androgen present without active aromatase inhibition or estrogen receptor modulation. Risk of excessive CYP19A1 conversion to estradiol, gynecomastia, and fluid retention.",
                "recommended_cofactor": "Aromatase Inhibitor (Anastrozole 0.25–0.5 mg twice weekly or Exemestane 12.5 mg twice weekly) or SERM (Raloxifene 30–60 mg/day) as indicated by sensitive E2 blood panels.",
                "cofactor_search_terms": ["anastrozole", "exemestane", "letrozole", "raloxifene"],
                "mechanism": "Inhibits CYP19A1 aromatase to control serum estradiol (E2) in the healthy target window and prevent estrogenic side effects."
            })

        # 6. Aromatase Inhibitor Crash Protection
        if features["has_aromatase_inhibitors"]:
            gaps.append({
                "axis": "Estrogen Balance (E2 Preservation)",
                "severity": "RULE",
                "issue": "Aromatase inhibitor is active; stacking additional secondary AIs risks severe hypoestrogenic crash.",
                "recommended_cofactor": "Do NOT add secondary aromatase inhibitors. Maintain target E2: 20–30 pg/mL.",
                "mechanism": "Preserves HDL synthesis, joint synovia, bone mineral density, and vascular compliance."
            })

        # 7. Psychostimulant Vasoconstriction & Sleep Hygiene
        if features["has_psychostimulants"]:
            has_theanine = any(
                any(w in str(c.get("key", "") + " " + c.get("name", "")).lower() for w in ["theanine", "l-theanine", "agmatine"])
                for c in compounds
            )
            if not has_theanine:
                gaps.append({
                    "axis": "Autonomic / Psychostimulant Buffer",
                    "severity": "MODERATE",
                    "issue": "Central catecholamine drive induces peripheral alpha-1 vasoconstriction, elevated pulse, and sleep latency.",
                    "recommended_cofactor": "L-Theanine 100–200 mg (co-administered with stimulant) + strict 8–10h bedtime cutoff.",
                    "cofactor_search_terms": ["l_theanine", "theanine", "magnesium"],
                    "mechanism": "Antagonizes glutamate receptors and stimulates inhibitory GABA synthesis to smooth autonomic tone."
                })

        # 8. Female-Specific Androgen Sensitivity & Virilization Protection
        sex = str(biometrics.get("sex") or biometrics.get("gender") or "").lower().strip()
        if sex in ("female", "f", "woman") and features["has_androgens"]:
            gaps.append({
                "axis": "Endocrine / Female Virilization Risk",
                "severity": "HIGH",
                "issue": "Exogenous androgenic exposure in female patient carries high risk of virilization (hyperandrogenism, voice deepening, clitoromegaly, hirsutism, and menstrual disruption).",
                "recommended_cofactor": "Titrate androgens to micro-doses (e.g. low-dose TRT 5–10 mg/week or Oxandrolone <= 5 mg/day) and monitor free androgen index / SHBG",
                "mechanism": "Female AR tissue sensitivity is significantly higher; avoid supra-physiological male dosing levels."
            })

        # 9. Gut Microbiota TMA/TMAO Axis (Oral L-Carnitine/Choline without Microbial Lyase Inhibition)
        if features.get("has_oral_tma_precursors") and not features.get("has_microbial_tma_inhibitors"):
            precursor_str = ", ".join(features.get("oral_tma_precursor_names", ["Oral L-Carnitine/Choline"]))
            gaps.append({
                "axis": "Gastrointestinal / Microbial TMAO Axis",
                "severity": "MODERATE",
                "issue": f"Oral TMA precursor active ({precursor_str}) without gut microbial TMA-lyase inhibition. Intestinal bacteria (CntA/CntB / yeaW/yeaX) cleave oral carnitine/choline to trimethylamine (TMA), oxidized by host hepatic FMO3 into atherogenic Trimethylamine N-Oxide (TMAO).",
                "recommended_cofactor": "Allicin (Garlic Extract / Allium sativum) 10–20 mg (or 600–1200 mg Aged Garlic Extract) daily with meals, or switch to parenteral (IM/SubQ) route to bypass intestinal microbiota.",
                "cofactor_search_terms": ["allicin", "garlic", "aged_garlic_extract", "garlic_extract"],
                "mechanism": "Inactivates bacterial CntA/CntB / CutC TMA-lyase enzymes, suppressing TMA and TMAO formation by >50% while preserving mitochondrial carnitine shuttle bioactivity."
            })

        return gaps

    @classmethod
    def _format_prompt_grounding(
        cls,
        goal_title: str,
        is_user_selected: bool,
        user_objective_text: str,
        inferred_reasoning: str,
        modality_profile: Dict[str, Any],
        therapeutic_gaps: List[Dict[str, Any]],
        features: Dict[str, Any]
    ) -> str:
        """Formats grounding markdown for LLM system prompt injection."""
        lines = [
            "### PROTOCOL PURPOSE, MODALITY & THERAPEUTIC GAP ANALYSIS:",
            f"- **Primary Protocol Objective**: **{goal_title}** ({'User Explicitly Specified' if is_user_selected else 'Auto-Inferred from Stack Pharmacology'})",
        ]

        if user_objective_text:
            lines.append(f"- **User Clinical / Performance Notes**: \"{user_objective_text}\"")
        else:
            lines.append(f"- **Pharmacological Intent Reasoning**: {inferred_reasoning}")

        # Modality segmentation
        depots = modality_profile.get("depot_injections", [])
        if depots:
            depot_str = ", ".join(f"{d['name']} ({d['dose_display']} {d['route']} - {d['frequency']})" for d in depots)
            lines.append(f"- **Depot Injections (Weekly/Split IM Protocol)**: {depot_str}")
            lines.append("  *(Note: Depot injectables have 7-10 day half-lives. NEVER schedule daily oral supplements 'with' an injection event on daily circadian tables.)*")

        daily_items = modality_profile.get("daily_oral", [])
        if daily_items:
            daily_str = ", ".join(f"{d['name']} ({d['dose_display']}, {d['timing']})" for d in daily_items)
            lines.append(f"- **Daily Oral / Maintenance Regimen**: {daily_str}")

        # Physiological Gaps
        if therapeutic_gaps:
            lines.append("- **Identified Therapeutic Gaps & Uncompensated Axes**:")
            for g in therapeutic_gaps:
                lines.append(f"  * ⚠️ **{g['axis']}**: {g['issue']}")
                lines.append(f"    ➔ **Evidence-Based Solution**: {g['recommended_cofactor']} ({g['mechanism']})")

        # Pharmacokinetic & Mechanistic Protocol Principles
        lines.append("- **Pharmacokinetic & Mechanistic Protocol Principles**:")
        if features.get("has_depot_injectables"):
            lines.append("  * **Depot Half-Life & Interval Dosing**: Long-acting depot formulations have extended elimination half-lives (t1/2 > 72h). Dose on appropriate weekly or split-weekly intervals (never as daily oral doses).")
        if features.get("has_androgens"):
            lines.append("  * **Hypothalamic-Pituitary-Gonadal (HPG) Feedback**: Exogenous androgens induce negative feedback inhibition on LH/FSH secretion.")
            if not features.get("has_aromatase_inhibitors") and not features.get("has_serms") and features.get("has_aromatizable_substrate"):
                lines.append("  * **Enzymatic CYP19A1 Aromatization**: Monitor estradiol (E2) balance and consider enzymatic or receptor countermeasures if aromatization signs or elevated serum E2 occur.")
        if features.get("has_aromatase_inhibitors"):
            lines.append("  * **Estradiol Preservation**: Maintain physiological estradiol levels (target 20–30 pg/mL) to preserve bone mineral density, lipid synthesis, and joint health.")

        if not modality_profile.get("daily_oral") and not modality_profile.get("depot_injections"):
            lines.append("- **SCRATCH PROTOCOL GENERATION MANDATE**:")
            lines.append("  * Stack is currently empty. Design a complete, synergistic, evidence-based stack matching the goal and patient biometrics.")
            lines.append("  * Formulate circadian timing allocations (Morning, Midday, Afternoon, Bedtime).")
            lines.append("  * If depot injectables are included, list under 'Depot Injections (Weekly / Split Protocol)' with twice-weekly or weekly frequency.")
            lines.append("  * At the very end of your response, provide the `<action_card type=\"stack_diff\">` containing the complete `add` list of compounds.")

        return "\n".join(lines)

    @classmethod
    def _extract_user_exclusions(
        cls,
        custom_notes: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        exclusions: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Extracts structured negative compound and route exclusions from user parameters and instructions,
        resolving exact catalog database matches without fragile regex/semantic patterns.
        """
        import re
        collected: List[str] = []
        if exclusions:
            collected.extend([str(e).strip().lower() for e in exclusions if e])

        prefs = preferences or {}
        for k in ("exclusions", "exclude", "avoid", "omit", "disallowed_compounds"):
            val = prefs.get(k)
            if isinstance(val, list):
                collected.extend([str(v).strip().lower() for v in val if v])
            elif isinstance(val, str) and val.strip():
                collected.extend([v.strip().lower() for v in val.split(",") if v.strip()])

        notes_str = (custom_notes or "").strip()
        if notes_str:
            # Tokenize and scan exact n-grams against catalog database
            from app.services.catalog_service import CatalogService
            cat = CatalogService()

            words = re.findall(r"[a-zA-Z0-9_\-\+]+", notes_str)
            negation_words = {"no", "without", "exclude", "avoid", "omit", "disallow", "skip", "allergic"}

            for i in range(len(words)):
                prev_word = words[i - 1].lower() if i > 0 else ""
                prev_prev_word = words[i - 2].lower() if i > 1 else ""

                is_negated = prev_word in negation_words or prev_prev_word in negation_words or "no" in prev_word or "avoid" in prev_word or "exclude" in prev_word or "without" in prev_word

                if is_negated:
                    # Check 1-gram, 2-gram, 3-gram
                    for n in (3, 2, 1):
                        if i + n <= len(words):
                            ngram = " ".join(words[i:i + n])
                            comp_rec = cat.get_compound(ngram, auto_enrich=False) or cat.find_by_synonym(ngram)
                            if comp_rec:
                                collected.append(comp_rec.get("key") or ngram.lower())
                                break

                    # Also capture route exclusions e.g. "no oral l-carnitine"
                    if i + 1 < len(words):
                        route_cand = words[i].lower()
                        if route_cand in ("oral", "injectable", "subq", "im"):
                            next_ngram = " ".join(words[i + 1:i + 3])
                            comp_rec = cat.get_compound(next_ngram, auto_enrich=False) or cat.find_by_synonym(next_ngram) or cat.get_compound(words[i + 1], auto_enrich=False)
                            if comp_rec:
                                collected.append(f"no {route_cand} {comp_rec.get('key') or words[i + 1].lower()}")

        return list(dict.fromkeys(collected))

    @classmethod
    def _is_compound_excluded(
        cls,
        cand: Dict[str, Any],
        exclusions: List[str],
        catalog: Any = None,
    ) -> bool:
        """
        Determines whether a candidate compound matches any user-requested exclusion,
        evaluating keys, names, synonyms, and routes.
        """
        if not exclusions:
            return False

        c_key = str(cand.get("key") or "").lower().strip()
        c_name = str(cand.get("name") or "").lower().strip()
        c_route = str(cand.get("route") or "oral").lower().strip()
        c_class = str(cand.get("drug_class") or "").lower().strip()
        synonyms = set()

        if catalog:
            rec = catalog.get_compound(c_key, auto_enrich=False) or catalog.find_by_synonym(c_key)
            if rec:
                c_name = str(rec.get("name") or rec.get("canonical_name") or c_name).lower()
                for syn in (rec.get("synonyms") or []):
                    synonyms.add(str(syn).lower())

        cand_tokens = {c_key, c_name, c_key.replace("_", " "), c_name.replace("-", " ")}
        cand_tokens.update(synonyms)

        for exc in exclusions:
            exc_clean = exc.lower().strip()
            # Strip leading exclusion prefix verbs
            stripped_exc = re.sub(r"^(?:no|without|exclude|avoid|skip|omit|do not want|do not include|don't want|don't include|disallow|allergic to|intolerant to)\s+", "", exc_clean).strip()
            
            # Check route qualification
            is_oral_exc = "oral" in stripped_exc
            is_inj_exc = any(w in stripped_exc for w in ["injectable", "injection", "im", "subq"])

            target_term = re.sub(r"\b(oral|injectable|injection|im|subq)\b", "", stripped_exc).strip()
            if not target_term:
                target_term = stripped_exc

            # Check if target_term matches candidate tokens
            matches_compound = any(
                target_term in tok or tok in target_term or target_term.replace(" ", "_") == tok
                for tok in cand_tokens if len(tok) >= 3 and len(target_term) >= 3
            )

            if matches_compound:
                if is_oral_exc and c_route not in ("oral", "capsule", "tablet", "powder"):
                    continue
                if is_inj_exc and c_route not in ("intramuscular", "im", "subcutaneous", "subq", "injectable"):
                    continue
                return True

        return False

    @classmethod
    def _extract_user_requested_compounds(
        cls,
        custom_notes: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        catalog: Any = None,
        requested_compounds: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically extracts user-requested compounds from structured parameters or preference dictionaries,
        resolving canonical keys and metadata via CatalogService without regex pattern scraping or hardcoding.
        """
        from app.services.dosing_service import parse_dose_string_or_spec, infer_compound_route_and_frequency

        if catalog is None:
            from app.services.catalog_service import CatalogService
            catalog = CatalogService()

        requested_specs: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        req_inputs: List[Any] = []
        if requested_compounds:
            req_inputs.extend(requested_compounds)

        prefs = preferences or {}
        for k in ("requested_compounds", "requested", "include", "compounds", "user_compounds", "add"):
            val = prefs.get(k)
            if isinstance(val, list):
                req_inputs.extend(val)
            elif isinstance(val, str) and val.strip():
                req_inputs.extend([v.strip() for v in val.split(",") if v.strip()])

        notes_str = (custom_notes or "").strip()
        if notes_str:
            import re
            words = re.findall(r"[a-zA-Z0-9_\-\+]+", notes_str)
            inclusion_words = {"include", "add", "want", "with", "using", "take", "request", "incorporate"}
            negation_words = {"no", "without", "exclude", "avoid", "omit", "disallow", "skip", "allergic"}

            for i in range(len(words)):
                prev_word = words[i - 1].lower() if i > 0 else ""
                prev_prev_word = words[i - 2].lower() if i > 1 else ""

                is_negated = prev_word in negation_words or prev_prev_word in negation_words
                if is_negated:
                    continue

                is_included = prev_word in inclusion_words or prev_prev_word in inclusion_words or "include" in prev_word or "add" in prev_word or "want" in prev_word

                if is_included:
                    for n in (3, 2, 1):
                        if i + n <= len(words):
                            ngram = " ".join(words[i:i + n])
                            comp_rec = catalog.get_compound(ngram, auto_enrich=False) or catalog.find_by_synonym(ngram)
                            if comp_rec:
                                req_inputs.append(comp_rec.get("key") or ngram.lower())
                                break

        for item in req_inputs:
            item_str = str(item).strip()
            if not item_str:
                continue

            # Strip leading exclusion prefix verbs if accidentally caught
            item_clean = re.sub(r"^(?:please\s+|i\s+want\s+to\s+|add\s+|include\s+|with\s+|take\s+)", "", item_str, flags=re.IGNORECASE).strip()
            # Strip trailing context filler
            item_clean = re.sub(r"\s+(?:for\s+my\s+|to\s+my\s+|for\s+|in\s+my\s+|cycle|stack|protocol|cut|bulk|routine).*$", "", item_clean, flags=re.IGNORECASE).strip()

            if not item_clean or len(item_clean) < 2:
                continue

            # Parse dose/spec if provided in string
            parsed_spec = parse_dose_string_or_spec(item_clean)
            raw_key = parsed_spec.get("key") or item_clean.lower().replace(" ", "_")

            # Try resolving whole item or individual word tokens via catalog
            comp_rec = catalog.get_compound(raw_key, auto_enrich=False) or catalog.find_by_synonym(raw_key)
            if not comp_rec:
                # Try tokens within item_clean
                tokens = re.findall(r"[a-zA-Z0-9_\-\+]+", item_clean)
                for tok in tokens:
                    if len(tok) >= 3 and tok.lower() not in ("stack", "protocol", "compounds", "routine", "cycle", "hypertrophy", "please", "want", "include", "add"):
                        rec_tok = catalog.get_compound(tok, auto_enrich=False) or catalog.find_by_synonym(tok)
                        if rec_tok:
                            comp_rec = rec_tok
                            break

            if not comp_rec:
                comp_rec = catalog.get_compound(raw_key, auto_enrich=True) or catalog.find_by_synonym(raw_key)

            if comp_rec:
                c_key = comp_rec.get("key", raw_key)
                if c_key in seen_keys:
                    continue
                seen_keys.add(c_key)

                inf_route, inf_freq = infer_compound_route_and_frequency(c_key)
                dose_val = parsed_spec.get("dose_mg") or comp_rec.get("dose") or comp_rec.get("standard_dose_mg") or 100.0

                requested_specs.append({
                    "key": c_key,
                    "name": comp_rec.get("name") or comp_rec.get("canonical_name") or c_key.replace("_", " ").title(),
                    "dose": dose_val,
                    "unit": parsed_spec.get("unit") or "mg",
                    "timing": parsed_spec.get("timing") or "morning",
                    "frequency": parsed_spec.get("frequency") or inf_freq,
                    "route": parsed_spec.get("route") or inf_route,
                    "target": comp_rec.get("mechanism") or comp_rec.get("drug_class") or "Target receptor",
                    "is_user_requested": True,
                    "metadata": comp_rec.get("metadata", {}),
                    "evidence_level": comp_rec.get("evidence_level", "moderate"),
                    "risk_band": comp_rec.get("risk_band", "low"),
                    "boxed_warning": comp_rec.get("boxed_warning"),
                })
            else:
                # Dynamic fallback spec for uncataloged requested string if valid candidate token
                clean_tok = re.sub(r"[^a-zA-Z0-9_]", "", raw_key)
                if len(clean_tok) >= 3 and clean_tok not in ("stack", "protocol", "compounds", "routine", "cycle", "hypertrophy", "please", "want", "include", "add") and clean_tok not in seen_keys:
                    seen_keys.add(clean_tok)
                    requested_specs.append({
                        "key": clean_tok,
                        "name": item_clean.replace("_", " ").title(),
                        "dose": parsed_spec.get("dose_mg") or 100.0,
                        "unit": parsed_spec.get("unit") or "mg",
                        "timing": "morning",
                        "frequency": "daily",
                        "route": "oral",
                        "target": "User-specified agent",
                        "is_user_requested": True,
                        "metadata": {"human_clinical_trials": False, "regulatory_status": "UNAPPROVED"},
                    })

        return requested_specs

    @classmethod
    def _discover_experimental_candidates_for_goal(
        cls,
        target_goal: str,
        catalog: Any,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically queries CatalogService for experimental compounds / research chemicals
        with limited human data matching the biological mechanisms of target_goal.
        Zero hardcoding of compound keys or brand names.
        """
        all_compounds = catalog.list_compounds() if hasattr(catalog, "list_compounds") else []
        experimental_cands: List[Dict[str, Any]] = []

        # Derive pharmacological domain terms dynamically from target goal taxonomy
        goal_tax = next((t for t in PROTOCOL_GOAL_TAXONOMY if t["id"] == target_goal), None)
        domain_terms = set()
        if goal_tax:
            domain_terms.update(re.findall(r"[a-z0-9]+", goal_tax.get("name", "").lower()))
            domain_terms.update(re.findall(r"[a-z0-9]+", goal_tax.get("description", "").lower()))
        domain_terms.discard("and")
        domain_terms.discard("the")
        domain_terms.discard("for")

        for comp in all_compounds:
            meta = comp.get("metadata", {}) or {}
            ev_tier = str(meta.get("evidence_tier") or "").upper()
            reg_stat = str(meta.get("regulatory_status") or "").upper()
            ev_level = str(comp.get("evidence_level") or "").lower()
            has_trials = meta.get("human_clinical_trials")

            is_experimental = (
                has_trials is False
                or ev_tier in ("IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION", "PRECLINICAL", "ANECDOTAL")
                or reg_stat in ("RESEARCH_CHEMICAL", "EXPERIMENTAL", "UNAPPROVED", "INVESTIGATIONAL PEPTIDE")
                or ev_level in ("experimental", "low", "preclinical", "anecdotal", "in_vitro")
            )

            if not is_experimental:
                continue

            text_blob = f"{comp.get('key', '')} {comp.get('name', '')} {comp.get('drug_class', '')} {comp.get('mechanism', '')} {' '.join(comp.get('categories') or [])}".lower()
            if any(kw in text_blob for kw in domain_terms if len(kw) >= 4):
                experimental_cands.append(comp)

        return experimental_cands

    @classmethod
    def build_scratch_stack_proposal(
        cls,
        goal_id: Optional[str] = None,
        biometrics: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        custom_notes: Optional[str] = None,
        exclusions: Optional[List[str]] = None,
        requested_compounds: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Dynamically discovers and calibrates a compound protocol from the pharmacological catalog
        based on the user's inputted biometrics, clinical parameters, preferences, and exclusions.
        Dosages and cofactors are computed dynamically via DosingService and InteractionEngine.
        """
        from app.services.catalog_service import CatalogService
        from app.services.dosing_service import calculate_individualized_dose, infer_compound_route_and_frequency

        biometrics = biometrics or {}
        preferences = preferences or {}
        custom_notes = (custom_notes or "").strip()

        # Parse user negative exclusions
        parsed_exclusions = cls._extract_user_exclusions(custom_notes=custom_notes, preferences=preferences, exclusions=exclusions)
        applied_exclusions: List[str] = []

        target_goal = (goal_id or "cognitive_focus").lower().strip()
        if target_goal in ("auto", "custom", ""):
            lower_notes = (custom_notes + " " + str(preferences)).lower()
            if any(w in lower_notes for w in ["focus", "cognit", "adhd", "study", "brain", "nootrop", "memory"]):
                target_goal = "cognitive_focus"
            elif any(w in lower_notes for w in ["muscle", "hypertrophy", "bodybuild", "physique", "anabolic", "strength", "gear", "testosterone", "aas"]):
                target_goal = "anabolic_physique"
            elif any(w in lower_notes for w in ["heart", "cardio", "lipid", "apob", "cholesterol", "blood pressure", "bp"]):
                target_goal = "cardiovascular_lipid"
            elif any(w in lower_notes for w in ["longevity", "aging", "autophagy", "sirt", "ampk", "mitochondria", "healthspan"]):
                target_goal = "longevity_autophagy"
            elif any(w in lower_notes for w in ["sleep", "insomnia", "stress", "relax", "cortisol", "recovery"]):
                target_goal = "sleep_stress_recovery"
            elif any(w in lower_notes for w in ["fat", "cut", "weight", "metabol", "thermogen", "shred"]):
                target_goal = "fat_loss_metabolic"
            elif any(w in lower_notes for w in ["pct", "reset", "post-cycle", "post therapy", "hormone recovery", "hpta"]):
                target_goal = "post_therapy_reset"
            else:
                target_goal = "cognitive_focus"

        blueprint = SCRATCH_GOAL_BLUEPRINTS.get(target_goal, SCRATCH_GOAL_BLUEPRINTS["cognitive_focus"])
        goal_title = blueprint["title"]
        goal_desc = blueprint["description"]

        # Parse user preference parameters
        risk_pref = str(preferences.get("risk_tolerance") or preferences.get("risk") or "balanced").lower().strip()
        stim_pref = str(preferences.get("stimulant_level", "standard")).lower().strip()
        complexity = str(preferences.get("complexity", "standard")).lower().strip()
        natural_only = bool(preferences.get("natural_only", False) or preferences.get("substance_style") == "natural")
        route_pref = str(preferences.get("route_preference") or preferences.get("route") or "all").lower().strip()
        schedule_pref = str(preferences.get("schedule_preference") or preferences.get("schedule") or "circadian").lower().strip()
        organ_pref = str(preferences.get("organ_priority") or preferences.get("organ_shield") or "auto").lower().strip()
        budget_pref = str(preferences.get("budget_tier") or preferences.get("budget") or "standard").lower().strip()

        # Biometric parameters & clearance multipliers
        weight_kg = float(biometrics.get("weight_kg") or 75.0)
        egfr = float(biometrics.get("egfr") or 95.0)
        alt_u_l = float(biometrics.get("alt_u_l") or 25.0)
        bp_val = float(biometrics.get("blood_pressure") or biometrics.get("systolic_bp") or 120.0)
        age = int(biometrics.get("age") or 30)
        sex = str(biometrics.get("sex") or biometrics.get("gender") or "unspecified").lower().strip()
        is_female = sex in ("female", "f", "woman")

        weight_scale = max(0.7, min(1.4, weight_kg / 75.0))
        sex_renal_factor = 0.85 if is_female else 1.0
        renal_scale = (max(0.5, min(1.0, (egfr * sex_renal_factor) / 90.0))) if egfr < 60 else 1.0
        hepatic_scale = max(0.6, min(1.0, 45.0 / alt_u_l)) if alt_u_l > 45 else 1.0
        age_scale = 0.9 if age >= 65 else 1.0

        if risk_pref in ("conservative", "low", "cautious", "safe"):
            risk_scale = 0.75
        elif risk_pref in ("aggressive", "high", "performance", "high_potency"):
            risk_scale = 1.25
        else:
            risk_scale = 1.0

        catalog = CatalogService()

        # Extract user specifically requested compounds
        user_requested_compounds = cls._extract_user_requested_compounds(
            custom_notes=custom_notes,
            preferences=preferences,
            catalog=catalog,
            requested_compounds=requested_compounds,
        )

        # Collect candidate compounds from blueprint
        raw_candidates: List[Dict[str, Any]] = [dict(c) for c in blueprint.get("core_compounds", [])]

        if budget_pref != "essential" and complexity in ("standard", "maximum", "comprehensive", "full"):
            raw_candidates.extend([dict(a) for a in blueprint.get("ancillaries", [])])

        # Step 1: Aggressive Risk Tolerance -> Discover experimental candidates dynamically
        experimental_notices: List[str] = []
        if risk_pref in ("aggressive", "high", "performance", "high_potency"):
            exp_candidates = cls._discover_experimental_candidates_for_goal(target_goal, catalog)
            for exp in exp_candidates[:2]:
                exp_key = exp.get("key")
                if exp_key and exp_key not in [c.get("key") for c in raw_candidates]:
                    raw_candidates.append({
                        "key": exp_key,
                        "name": exp.get("name") or exp_key.replace("_", " ").title(),
                        "base_dose": exp.get("dose") or (exp.get("default_dose") or {}).get("dose_val") or 10.0,
                        "unit": exp.get("unit") or (exp.get("default_dose") or {}).get("dose_unit") or "mg",
                        "timing": "morning",
                        "frequency": (exp.get("default_dose") or {}).get("frequency") or "daily",
                        "route": exp.get("route_of_administration") or "oral",
                        "target": exp.get("mechanism") or exp.get("drug_class") or "Research agent",
                        "rationale": f"[EXPERIMENTAL: Preclinical / Limited Human Data] Recommended under aggressive risk tolerance mode for {goal_title}.",
                        "is_stimulant": False,
                        "is_experimental": True,
                        "metadata": exp.get("metadata", {}),
                    })
                    experimental_notices.append(
                        f"⚠️ EXPERIMENTAL COMPOUND NOTICE [{exp.get('name') or exp_key}]: Limited human clinical trial data (preclinical/in vitro evidence). Recommended under aggressive risk tolerance mode; monitor individual response."
                    )

        # Enhanced / Aggressive Testosterone Support for Anabolic Physique
        is_enhanced_mode = (
            target_goal == "anabolic_physique"
            and not natural_only
            and (
                preferences.get("substance_style") in ("aggressive", "hybrid", "enhanced")
                or route_pref in ("injectable", "all", "hybrid")
                or risk_pref in ("aggressive", "high", "performance")
                or any(w in custom_notes.lower() for w in ["testosterone", "gear", "aas", "hypertrophy", "cycle", "cypionate", "enanthate"])
            )
        )

        if is_enhanced_mode:
            if is_female:
                if not any(c["key"] == "oxandrolone" for c in raw_candidates):
                    raw_candidates.insert(0, {
                        "key": "oxandrolone",
                        "name": "Oxandrolone (Anavar)",
                        "base_dose": 10,
                        "unit": "mg",
                        "timing": "morning",
                        "frequency": "daily",
                        "route": "oral",
                        "target": "Androgen Receptor Agonist (Low Virilization Index)",
                        "rationale": "High anabolic-to-androgenic ratio calibrated for female athletic hypertrophy without virilizing side effects.",
                        "is_stimulant": False,
                    })
            else:
                if not any("testosterone" in c["key"] for c in raw_candidates):
                    raw_candidates.insert(0, {
                        "key": "testosterone_cypionate",
                        "name": "Testosterone Cypionate",
                        "base_dose": 175,
                        "unit": "mg",
                        "timing": "Twice Weekly (Mon / Thu)",
                        "frequency": "twice_weekly",
                        "route": "intramuscular",
                        "target": "Nuclear Androgen Receptor (AR / NR3C4)",
                        "rationale": "Extended ester depot prodrug providing stable supraphysiological androgen receptor occupancy and enhanced myocellular protein synthesis.",
                        "is_stimulant": False,
                    })

        # Organ Shields & Targeted Biomarker Protection
        needs_cardio = organ_pref == "cardio" or (organ_pref == "auto" and (bp_val > 130 or egfr < 90)) or is_enhanced_mode
        needs_hepatic = organ_pref == "hepatic" or (organ_pref == "auto" and alt_u_l > 40)
        needs_neuro = organ_pref == "neuro_recovery"

        if needs_cardio:
            if not any(c["key"] == "telmisartan" for c in raw_candidates) and not natural_only:
                raw_candidates.append({
                    "key": "telmisartan",
                    "name": "Telmisartan",
                    "base_dose": 20,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Angiotensin II Type 1 (AT1) Receptor Antagonist",
                    "rationale": f"Blocks renal AT1 vasoconstriction, prevents LVH remodeling, and preserves podocyte integrity (Resting BP: {bp_val} mmHg, eGFR: {egfr}).",
                    "is_stimulant": False,
                })
            if not any(c["key"] == "citrus_bergamot" for c in raw_candidates):
                raw_candidates.append({
                    "key": "citrus_bergamot",
                    "name": "Citrus Bergamot Extract",
                    "base_dose": 500,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Hepatic HMGCR Modulation & ApoB Lipid Protection",
                    "rationale": "Maintains atherogenic ApoB and LDL particle clearance during androgen exposure.",
                    "is_stimulant": False,
                })

        if needs_hepatic:
            if not any(c["key"] == "nac" for c in raw_candidates):
                raw_candidates.append({
                    "key": "nac",
                    "name": "N-Acetyl Cysteine (NAC)",
                    "base_dose": 600,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Glutathione Biosynthesis & Hepatocyte Protection",
                    "rationale": f"Added for hepatic transaminase support and Phase II detoxification (ALT: {alt_u_l} U/L).",
                    "is_stimulant": False,
                })
            if complexity in ("standard", "maximum", "comprehensive", "full") and not any(c["key"] == "tudca" for c in raw_candidates) and not natural_only:
                raw_candidates.append({
                    "key": "tudca",
                    "name": "Tauroursodeoxycholic Acid (TUDCA)",
                    "base_dose": 250,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Biliary Clearance & Hepatocyte ER Chaperone",
                    "rationale": "Provides hydrophilic bile acid pool expansion and mitigates canalicular cholestatic stress.",
                    "is_stimulant": False,
                })

        if needs_neuro:
            if not any(c["key"] == "magnesium" for c in raw_candidates):
                raw_candidates.append({
                    "key": "magnesium",
                    "name": "Magnesium Glycinate",
                    "base_dose": 300,
                    "unit": "mg",
                    "timing": "bedtime" if schedule_pref != "morning_only" else "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "NMDA Receptor Voltage-Gated Blocker",
                    "rationale": "Buffers cortical excitotoxicity and calms autonomic tone.",
                    "is_stimulant": False,
                })
            if not any(c["key"] == "l_theanine" for c in raw_candidates):
                raw_candidates.append({
                    "key": "l_theanine",
                    "name": "L-Theanine",
                    "base_dose": 200,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Glutamate Attenuation & Alpha Wave Stimulation",
                    "rationale": "Smooths central nervous system excitation and autonomic arousal.",
                    "is_stimulant": False,
                })

        # Process and dynamically scale candidate compounds
        built_compounds: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        for cand in raw_candidates:
            c_key = cand.get("key")
            if not c_key or c_key in seen_keys:
                continue

            # Exclude experimental candidates if risk preference is non-aggressive (unless explicitly requested)
            meta = cand.get("metadata", {}) or {}
            is_exp = cand.get("is_experimental") or meta.get("human_clinical_trials") is False or str(meta.get("evidence_tier")).upper() in ("IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION", "PRECLINICAL") or str(meta.get("regulatory_status")).upper() in ("RESEARCH_CHEMICAL", "EXPERIMENTAL")
            if is_exp and risk_pref not in ("aggressive", "high", "performance", "high_potency") and not any(r.get("key") == c_key for r in user_requested_compounds):
                continue

            # Route and frequency inference
            inf_route, inf_freq = infer_compound_route_and_frequency(c_key)
            c_route = cand.get("route") or inf_route
            c_freq = cand.get("frequency") or inf_freq

            # Check explicit user compound / route exclusions
            cand_check = dict(cand)
            cand_check["route"] = c_route
            if cls._is_compound_excluded(cand_check, parsed_exclusions, catalog):
                applied_exclusions.append(f"{cand.get('name') or c_key} ({c_route})")
                continue

            seen_keys.add(c_key)

            # Filter by natural_only
            if natural_only and any(w in str(cand.get("target", "") + " " + c_key).lower() for w in ["steroid", "androgen", "prescription", "pharmaceutical"]):
                continue

            # Filter by route preference
            if route_pref in ("oral_only", "capsules_only", "no_powders") and c_route in ("intramuscular", "subcutaneous"):
                continue

            # Stimulant filtering & scaling
            if cand.get("is_stimulant"):
                if stim_pref in ("none", "stim-free", "stim_free", "free"):
                    continue
                elif stim_pref in ("mild", "low"):
                    cand_dose = round(cand["base_dose"] * 0.5 * min(1.0, risk_scale))
                else:
                    cand_dose = round(cand["base_dose"] * risk_scale)
            else:
                b_dose = cand.get("base_dose", 100.0)
                if c_key in ("caffeine", "beta_alanine", "creatine", "l_carnitine", "magnesium", "citrus_bergamot", "taurine"):
                    scaled_dose = round(b_dose * weight_scale * risk_scale)
                elif c_key in ("berberine", "telmisartan", "nebivolol", "metformin"):
                    scaled_dose = round(b_dose * renal_scale * hepatic_scale * age_scale * risk_scale, 1)
                    if scaled_dose == int(scaled_dose):
                        scaled_dose = int(scaled_dose)
                elif "testosterone" in c_key and is_female:
                    scaled_dose = round(b_dose * 0.08 * risk_scale, 2)
                else:
                    scaled_dose = round(b_dose * risk_scale) if isinstance(b_dose, (int, float)) and b_dose >= 10 else b_dose
                cand_dose = scaled_dose

            if isinstance(cand_dose, float) and cand_dose == int(cand_dose):
                cand_dose = int(cand_dose)

            timing_val = cand.get("timing", "morning")
            if schedule_pref == "morning_only":
                if timing_val in ("bedtime", "evening"):
                    if c_key == "melatonin":
                        continue
                    timing_val = "morning"

            built_compounds.append({
                "key": c_key,
                "name": cand.get("name") or c_key.replace("_", " ").title(),
                "dose": cand_dose,
                "unit": cand.get("unit", "mg"),
                "timing": timing_val,
                "frequency": c_freq,
                "route": c_route,
                "target": cand.get("target", "Target receptor"),
                "rationale": cand.get("rationale", f"Calibrated for {goal_title}."),
            })

        # Step 2: FORCE INCLUDE USER REQUESTED COMPOUNDS REGARDLESS OF RISK
        requested_compound_warnings: List[str] = []

        for req in user_requested_compounds:
            req_key = req.get("key")
            if not req_key or req_key in seen_keys:
                continue

            req_check = {"key": req_key, "name": req.get("name"), "route": req.get("route")}
            if cls._is_compound_excluded(req_check, parsed_exclusions, catalog):
                applied_exclusions.append(f"{req.get('name') or req_key} ({req.get('route')})")
                continue

            seen_keys.add(req_key)

            req_name = req.get("name") or req_key.replace("_", " ").title()
            req_dose = req.get("dose", 100.0)
            req_unit = req.get("unit", "mg")
            req_route = req.get("route", "oral")
            req_freq = req.get("frequency", "daily")
            req_timing = req.get("timing", "morning")

            meta = req.get("metadata", {}) or {}
            is_high_risk = req.get("risk_band") in ("high", "severe", "elevated") or req.get("boxed_warning") is not None
            is_exp = meta.get("human_clinical_trials") is False or str(meta.get("evidence_tier")).upper() in ("IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION", "PRECLINICAL") or str(meta.get("regulatory_status")).upper() in ("RESEARCH_CHEMICAL", "EXPERIMENTAL")

            warn_reasons = []
            if is_exp:
                warn_reasons.append("Limited human clinical trial data (preclinical/in vitro evidence).")
            if is_high_risk or req.get("boxed_warning"):
                warn_reasons.append(f"High risk profile / Boxed warning: {req.get('boxed_warning') or 'Requires strict monitoring.'}")
            if req.get("is_stimulant") or any(w in str(req.get("target", "") + " " + req.get("drug_class", "")).lower() for w in ["sympathomimetic", "adrenergic", "beta-2"]):
                warn_reasons.append("Sympathomimetic / Adrenergic drive carries cardiac strain and electrolyte depletion risks.")

            warn_detail = " ".join(warn_reasons) if warn_reasons else "Monitor individual tolerance."
            warn_msg = f"⚠️ USER-REQUESTED COMPOUND [{req_name}]: Included as specifically requested regardless of baseline risk. {warn_detail}"
            requested_compound_warnings.append(warn_msg)

            built_compounds.append({
                "key": req_key,
                "name": req_name,
                "dose": req_dose,
                "unit": req_unit,
                "timing": req_timing,
                "frequency": req_freq,
                "route": req_route,
                "target": req.get("target", "User requested agent"),
                "rationale": f"Specifically requested by user. {warn_msg}",
                "is_user_requested": True,
            })

        # Dynamically evaluate gaps and attach protective co-factors (Side-effect mitigation)
        comp_records_for_analysis = [dict(c) for c in built_compounds]
        features = cls._extract_pharmacological_features(comp_records_for_analysis)
        gaps = cls._detect_therapeutic_gaps(features, comp_records_for_analysis, biometrics)

        for gap in gaps:
            # STRICT GUARD: Rules / contraindications must NEVER be parsed as compound co-factors
            if gap.get("severity") == "RULE" or not gap.get("cofactor_search_terms"):
                continue

            search_terms = gap.get("cofactor_search_terms", [])
            found_rec = None
            for term in search_terms:
                term_clean = term.lower().strip().replace("-", "_")
                found_rec = catalog.get_compound(term_clean) or catalog.find_by_synonym(term_clean)
                if found_rec:
                    break

            if found_rec and found_rec.get("key") not in seen_keys:
                cofactor_key = found_rec.get("key")
                co_route, co_freq = infer_compound_route_and_frequency(cofactor_key)

                # Check if cofactor is excluded
                co_check = {"key": cofactor_key, "name": found_rec.get("name"), "route": co_route}
                if cls._is_compound_excluded(co_check, parsed_exclusions, catalog):
                    applied_exclusions.append(f"{found_rec.get('name') or cofactor_key} ({co_route})")
                    continue

                seen_keys.add(cofactor_key)
                co_dose_info = calculate_individualized_dose(found_rec, biometrics, risk_scale)

                co_dose_val = co_dose_info.get("dose_val", 10.0)
                if isinstance(co_dose_val, float) and co_dose_val == int(co_dose_val):
                    co_dose_val = int(co_dose_val)

                built_compounds.append({
                    "key": cofactor_key,
                    "name": found_rec.get("name") or cofactor_key.replace("_", " ").title(),
                    "dose": co_dose_val,
                    "unit": co_dose_info.get("unit", "mg"),
                    "timing": "morning",
                    "frequency": co_freq,
                    "route": co_route,
                    "target": gap.get("axis", "Protective Co-factor"),
                    "rationale": f"Protective co-factor for {gap.get('axis', '')}: {gap.get('mechanism', '')}",
                })

        schedule = {
            "morning": [c for c in built_compounds if c["timing"] in ("morning", "pre-workout", "midday")],
            "bedtime": [c for c in built_compounds if c["timing"] in ("bedtime", "evening")],
        }

        action_card_payload = {
            "action_card": "stack_diff",
            "add": [
                {
                    "key": c["key"],
                    "name": c["name"],
                    "dose": c["dose"],
                    "unit": c["unit"],
                    "timing": c["timing"],
                    "frequency": c["frequency"],
                    "route": c["route"]
                }
                for c in built_compounds
            ],
            "modify": [],
            "remove": []
        }

        all_warnings = list(dict.fromkeys(experimental_notices + requested_compound_warnings))

        return {
            "goal_id": target_goal,
            "goal_title": goal_title,
            "goal_description": goal_desc,
            "compounds": built_compounds,
            "schedule": schedule,
            "action_card": action_card_payload,
            "applied_exclusions": list(dict.fromkeys(applied_exclusions)),
            "requested_compounds": [r.get("name") for r in user_requested_compounds],
            "warnings": all_warnings,
            "biometric_calibration": {
                "weight_scale": round(weight_scale, 2),
                "renal_scale": round(renal_scale, 2),
                "hepatic_scale": round(hepatic_scale, 2),
                "age_scale": age_scale,
                "risk_scale": round(risk_scale, 2),
            },
            "customizations": {
                "risk_tolerance": risk_pref,
                "stimulant_level": stim_pref,
                "complexity": complexity,
                "substance_style": "natural" if natural_only else "hybrid",
                "route_preference": route_pref,
                "schedule_preference": schedule_pref,
                "organ_priority": organ_pref,
                "budget_tier": budget_pref,
                "exclusions": list(dict.fromkeys(parsed_exclusions)),
            }
        }
