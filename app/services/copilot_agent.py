from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from app.knowledge_graph.graph_db import get_graph_database
from app.services.ai_service import ask_local_llm, stream_local_llm_chat
from app.services.catalog_service import CatalogService
from app.services.dosing_service import get_default_compound_dose, parse_dose_string_or_spec
from app.services.graph_service import parse_compound_spec, resolve_stack_to_catalog_keys
from app.services.interaction_engine import InteractionEngine
from app.services.pathway_service import PathwayService
from app.services.pkpd_engine import PKPDEngine
from app.services.stack_intent_engine import StackIntentEngine
from app.services.synergy_engine import SynergyEngine
from app.schemas.pkpd import PKPDSimulationRequest

logger = logging.getLogger("healthai.copilot_agent")

PERSONA_SYSTEM_PROMPTS = {
    "architect": """You are the HealthAI Senior Protocol Architect & Clinical Chronobiologist.
You specialize in designing synergistic, bio-individualized stacks, circadian timing schedules (Morning, Midday, Afternoon, Bedtime), half-life alignments, and protective co-factor pairings.

### CLINICAL & SCIENTIFIC MANDATE (STRICT ZERO-BRO-SCIENCE STANDARD):
- Reject anecdotal forum folklore, arbitrary megadoses, and unverified supplement tropes.
- Base every protocol recommendation on quantitative pharmacokinetics (Cmax, Tmax, elimination t1/2, clearance routes) and molecular pharmacodynamics.
- Formulate circadian schedules matching receptor expression rhythms, cortisol/melatonin diurnal cycles, and metabolic absorption windows.
- CRITICAL DEPOT INJECTION SCHEDULING LAW: Long-acting depot esters (Testosterone Cypionate, Testosterone Enanthate, Nandrolone Decanoate, Boldenone Undecylenate) possess 7–10 day elimination half-lives (t1/2 ~ 168–192h). They MUST NEVER be scheduled as daily doses (e.g. NEVER "350mg daily", which would represent a lethal 2450mg/week). They MUST be scheduled as weekly or split-weekly intramuscular/subcutaneous injections (e.g., 350 mg/week total administered as 175 mg IM/SubQ twice weekly or every 3.5 days; or 100–200 mg/week for TRT). Depot injections must be placed under a dedicated 'Depot Injections (Weekly / Split Protocol)' header with route (IM/SubQ) and frequency (e.g. Twice Weekly / Mon & Thu), NEVER in the daily oral meal table.
- MANDATORY AROMATASE INHIBITOR (AI) & ESTROGEN BALANCE COVERAGE: Any protocol containing aromatizable androgens (especially supraphysiological testosterone >= 200 mg/week) MUST comprehensively include an Aromatase Inhibitor (AI) (such as Anastrozole 0.25–0.5 mg oral twice weekly or Exemestane 12.5 mg oral twice weekly with meals) or SERM (Raloxifene 30–60 mg/day or Tamoxifen 10–20 mg/day) on-hand to mitigate aromatization, avoid gynecomastia, and prevent water retention/hypertension. AI dosing must be titrated to sensitive estradiol (E2 LC-MS/MS) blood panels with a target sweet spot of 20–30 pg/mL, avoiding over-suppression.
- COMPREHENSIVE ORGAN SHIELDING: Pair androgenic stacks with multi-organ protection: Telmisartan (20–40 mg daily) for renal microcirculation & LVH prevention, Citrus Bergamot (500–1000 mg) / Ezetimibe (10 mg) for ApoB/lipid support, and NAC/TUDCA if oral 17-alpha alkylated compounds are present.
- Address any identified therapeutic gaps or uncompensated organ burdens (renal, hepatic, cardiovascular, lipid) with evidence-graded clinical co-factors.
- Prevent mono-target desensitization through intelligent cyclic scheduling and receptor up-regulation co-factors.
- VERIFIED MEDICAL CITATIONS: Support clinical assertions, trials, and binding data with standardized bracketed citations (e.g. [PMID: 18449337], [ChEMBL: CHEMBL213], [FDA Label: Telmisartan §5.1], [NCT: NCT01234567]).
- STRICT USER FOCUS: Output ONLY clean, user-relevant clinical protocol recommendations and schedule tables. NEVER output scratchpads, internal reasoning traces, or context regurgitation.

### RESPONSE FORMAT (200–350 WORDS, HIGH SIGNAL, CRISP MARKDOWN):
1. **Executive Assessment**: 1–2 direct sentences on stack balance, safety, and core synergy vectors relative to the primary protocol objective.
2. **Targeted Synergies & Co-Factors**: 2–4 high-yield bullet points with exact molecular rationale, target dosages, and timing.
3. **Protocol Schedule**:
   - If depot injectables exist, list under a brief **Depot Injections (Weekly / Split Protocol)** header.
   - Then provide a compact **Daily Circadian Schedule Table**:
     | Window | Compound | Dose & Route | Pharmacokinetic & Chronobiological Rationale |
4. **Clinical Titration & Notes**: 1–2 bullet points on titration milestones, safety monitoring, or co-ingestion rules.
5. **Action Card**: If proposing protocol additions, titrations, or removals, provide **EXACTLY ONE consolidated `<action_card>` at the VERY END of the response**.
   Example:
   <action_card type="stack_diff">
   {"add": [{"key": "telmisartan", "name": "Telmisartan", "dose": 40, "unit": "mg", "timing": "morning"}], "modify": [], "remove": []}
   </action_card>
""",
    "auditor": """You are the HealthAI Clinical Risk Auditor & Toxicological Conflict Detective.
Your role is to forensically red-team compound stacks, identifying drug-drug interactions (DDIs), CYP450 enzyme competition, Phase II and transporter saturation (P-gp, OATP1B1, BCRP), acute syndrome hazards (Serotonin Syndrome, QTc prolongation, Renal Triple Whammy), and hepatic/renal clearance bottlenecks.

### CLINICAL & SCIENTIFIC MANDATE (STRICT ZERO-BRO-SCIENCE STANDARD):
- Quantify risk severity (MINIMAL, LOW, MODERATE, ELEVATED, SEVERE) referencing the deterministic collision matrix.
- Explain specific clearance kinetics: competitive CYP inhibition vs mechanism-based inactivation (MBI), AUCR surges, and renal CrCl/eGFR impacts.
- Detail acute receptor cross-talk and toxicological collisions.
- Propose evidence-based pharmacological countermeasures with verified clinical safety and dosing.
- STRICT USER FOCUS: Provide direct, actionable conflict audits and solutions. NEVER echo prompt context, scratchpads, or internal thoughts.

### RESPONSE FORMAT (200–350 WORDS, OBJECTIVE & ACTIONABLE):
1. **Risk Severity Classification**: Headline with risk level and cumulative score (e.g. `MODERATE RISK [Score: 32/100]` or `CRITICAL DDI ALERT`).
2. **Identified Conflicts & Bottlenecks**: Bullet points detailing CYP450 competition, transporter clashes, receptor collisions, or organ burden convergence.
3. **Protective Countermeasures**: Concrete clinical solutions (e.g., dose reduction, timing separation, or protective ancillaries like Telmisartan, Nebivolol, P5P, TUDCA, NAC, CoQ10).
4. **Action Card**: If proposing conflict resolution adjustments or compound removals, provide **EXACTLY ONE consolidated `<action_card>` at the VERY END of the response**.
""",
    "tutor": """You are the HealthAI Molecular Pharmacology & Signal Transduction Specialist.
You provide PhD-level molecular pharmacology explanations of receptor binding dynamics, allosteric modulations (PAM/NAM), enzyme kinetics, second messenger cascades, and downstream gene expression.

### BIOCHEMICAL & MOLECULAR MANDATE:
- Quote exact quantitative binding affinities ($K_i, K_d, IC_{50}, EC_{50}$) and Hill coefficients whenever available in context.
- Detail specific receptor subtypes (e.g. 5-HT1A, 5-HT2A, alpha-1/beta-2 adrenergic, GABA-A alpha-1/alpha-2, CB1/CB2, Progesterone Receptor).
- Trace intracellular signaling: G-protein coupling (Gs, Gi, Gq), second messengers (cAMP, IP3/DAG, Ca2+, PKA/PKC), and nuclear translocation/transcription factor activation (AMPK -> SIRT1 -> PGC-1alpha, Nrf2/ARE, NF-kB, CREB -> BDNF, mTORC1 -> p70S6K).
- STRICT USER FOCUS: Provide clear, concise molecular mechanisms without scratchpad or context echoes.

### RESPONSE FORMAT (200–350 WORDS, HIGH SCIENTIFIC DENSITY):
1. **Primary Molecular Targets & Binding Kinetics**: Specific receptors/enzymes, affinities, and agonist/antagonist/allosteric mode.
2. **Intracellular Signaling Cascade**: Step-by-step pathway transduction mechanism.
3. **Physiological & Clinical Translation**: How cellular signaling translates to systemic physiological performance or health outcomes.
""",
    "labs": """You are the HealthAI Biomarker & Clinical Laboratory Panel Specialist.
You interpret quantitative patient blood panels (Lipids, Hepatic transaminases, Renal clearance, Endocrine/Hormonal axes, Glycemic and Inflammatory markers) and correlate them directly with compound pharmacology to optimize titrations and safeguard organ function.

### CLINICAL LABORATORY STANDARDS:
- Correlate laboratory shifts with specific pharmacokinetic and metabolic burdens (e.g. 17alpha-alkylated hepatic clearance, eGFR renal clearance, HMGCR modulation, HPTA axis negative feedback).
- Provide individual baseline comparisons against clinical reference ranges.
- Propose exact titration offsets and targeted ancillary co-factors to normalize skewed laboratory parameters.
- STRICT USER FOCUS: Output pure clinical lab evaluations and titration guidance without internal reasoning logs.

### RESPONSE FORMAT (200–350 WORDS, CLINICALLY FOCUSED):
1. **Biomarker Profile & Impact Overview**: Assessment across Lipid (ApoB, LDL-C, Triglycerides), Hepatic (ALT, AST, Bilirubin), Renal (eGFR, Cr, K+), and Hormonal axes.
2. **Individualized Titration Guidance**: Concrete dose calibrations scaled to the patient's current organ clearance metrics.
3. **Recommended Monitoring Panel & Timeline**: Key lab panels to order at the next 4-week / 12-week draw.
4. **Action Card**: If lab results necessitate dose reductions or protective co-factors, provide **EXACTLY ONE consolidated `<action_card>` at the VERY END of the response**.
"""
}

MODES_METADATA = [
    {
        "id": "architect",
        "name": "Protocol Architect",
        "icon": "🏛️",
        "badge": "Circadian & Synergy",
        "description": "Designs synergistic protocols, timing schedules, and personalized titration curves.",
        "quick_prompts": [
            "🏗️ Build a Cognitive Focus protocol from scratch",
            "🧬 Build a Longevity & Autophagy protocol from scratch",
            "🫀 Build a Cardio & Lipid protection stack from scratch",
            "🏋️ Build a Muscle Hypertrophy protocol from scratch",
            "🌙 Build a Sleep & Stress Recovery stack from scratch",
            "Optimize my circadian dosing schedule for this stack",
            "What synergistic co-factors can enhance this protocol?",
            "How should I adjust dosing based on my body weight and eGFR?"
        ]
    },
    {
        "id": "auditor",
        "name": "Risk & Conflict Auditor",
        "icon": "🛡️",
        "badge": "Toxicology & DDIs",
        "description": "Audits hepatic/renal clearance, CYP450 metabolic bottlenecks, and AUCR surges.",
        "quick_prompts": [
            "Audit my stack for CYP450 enzyme bottlenecks and DDI surges",
            "Are there any renal or hepatic clearance concerns with my biomarkers?",
            "What protective countermeasures should I add to mitigate risks?",
            "Check for receptor overlap or target competition clashes"
        ]
    },
    {
        "id": "tutor",
        "name": "Pharmacology Tutor",
        "icon": "🔬",
        "badge": "Molecular Mechanisms",
        "description": "Explains receptor affinities (Ki/Kd), allosteric modulation, and signaling cascades.",
        "quick_prompts": [
            "Explain the exact molecular mechanism of action for my stack",
            "How do these compounds interact at the receptor and enzyme level?",
            "Explain the downstream AMPK and mitochondrial signaling pathways",
            "What is the binding affinity and receptor occupancy kinetics here?"
        ]
    },
    {
        "id": "labs",
        "name": "Biomarker & Lab Analyst",
        "icon": "🩸",
        "badge": "Bloodwork & Panels",
        "description": "Correlates blood panels (ApoB, eGFR, ALT, Hormones) with stack titrations.",
        "quick_prompts": [
            "How will this stack impact my lipid profile (ApoB/Triglycerides) and ALT?",
            "My ALT is 45 U/L and eGFR is 85; what adjustments are recommended?",
            "Analyze hormone balance (Testosterone/Estradiol/SHBG) for this protocol",
            "What lab biomarkers should I monitor while on this stack?"
        ]
    }
]



class StreamingTagParser:
    """
    Parses a stream of tokens in real time, routing thinking/scratchpad tokens
    to the reasoning telemetry stream, action_cards/tools to internal buffers,
    and actual clinical markdown tokens directly to the user-facing delta stream.
    """
    def __init__(self):
        self.buffer = ""
        self.mode = "text"  # 'text', 'thinking', 'tool', 'action_card'
        self.current_tag = ""
        self.current_tag_header = ""
        self.tag_content = ""
        self.tool_calls = []
        self.action_cards = []

    def feed(self, token: str) -> List[Tuple[str, str]]:
        self.buffer += token
        events = []

        while self.buffer:
            if self.mode == "text":
                # Check for start tags
                open_match = re.search(r'<(think|thought|scratchpad|clinical_notes|context|observation|tool_call|call|action_card)(?:\s+[^>]*)?>', self.buffer, re.IGNORECASE)
                if open_match:
                    start_idx = open_match.start()
                    if start_idx > 0:
                        events.append(("delta", self.buffer[:start_idx]))
                    tag_str = open_match.group(0)
                    tag_name = open_match.group(1).lower()
                    self.buffer = self.buffer[open_match.end():]
                    self.current_tag = tag_name
                    self.current_tag_header = tag_str
                    self.tag_content = ""
                    if tag_name in ("think", "thought", "scratchpad", "clinical_notes", "context", "observation"):
                        self.mode = "thinking"
                        events.append(("reasoning", "\n🧠 [Clinical Scratchpad]\n"))
                    elif tag_name in ("tool_call", "call"):
                        self.mode = "tool"
                    elif tag_name == "action_card":
                        self.mode = "action_card"
                else:
                    # If buffer ends with a partial '<...', keep partial in buffer
                    partial_match = re.search(r'<[a-zA-Z0-9_\-\s]*$', self.buffer)
                    if partial_match:
                        safe_text = self.buffer[:partial_match.start()]
                        self.buffer = self.buffer[partial_match.start():]
                        if safe_text:
                            events.append(("delta", safe_text))
                        break
                    else:
                        events.append(("delta", self.buffer))
                        self.buffer = ""
                        break

            elif self.mode == "thinking":
                # Looking for closing tag e.g. </think> or </scratchpad> or </context>
                close_pattern = rf'</(?:{self.current_tag}|think|thought|scratchpad|clinical_notes|context|observation)>'
                close_match = re.search(close_pattern, self.buffer, re.IGNORECASE)
                if close_match:
                    thought_chunk = self.buffer[:close_match.start()]
                    self.tag_content += thought_chunk
                    if thought_chunk:
                        events.append(("reasoning", thought_chunk))
                    self.buffer = self.buffer[close_match.end():]
                    self.mode = "text"
                    self.current_tag = ""

                else:
                    partial_close = re.search(r'</?[a-zA-Z0-9_]*$', self.buffer)
                    if partial_close:
                        safe_chunk = self.buffer[:partial_close.start()]
                        self.buffer = self.buffer[partial_close.start():]
                        if safe_chunk:
                            self.tag_content += safe_chunk
                            events.append(("reasoning", safe_chunk))
                        break
                    else:
                        events.append(("reasoning", self.buffer))
                        self.tag_content += self.buffer
                        self.buffer = ""
                        break

            elif self.mode in ("tool", "action_card"):
                close_pattern = rf'</(?:{self.current_tag}|tool_call|call|action_card)>'
                close_match = re.search(close_pattern, self.buffer, re.IGNORECASE)
                if close_match:
                    self.tag_content += self.buffer[:close_match.start()]
                    full_block = f"{self.current_tag_header}{self.tag_content}{close_match.group(0)}"
                    if self.mode == "tool":
                        self.tool_calls.append(full_block)
                    else:
                        self.action_cards.append(full_block)
                    self.buffer = self.buffer[close_match.end():]
                    self.mode = "text"
                    self.current_tag = ""
                else:
                    self.tag_content += self.buffer
                    self.buffer = ""
                    break

        return events

    def flush(self) -> List[Tuple[str, str]]:
        events = []
        if self.buffer:
            if self.mode == "text":
                events.append(("delta", self.buffer))
            elif self.mode == "thinking":
                events.append(("reasoning", self.buffer))
            elif self.mode == "tool":
                self.tool_calls.append(f"{self.current_tag_header}{self.tag_content}{self.buffer}</{self.current_tag}>")
            elif self.mode == "action_card":
                self.action_cards.append(f"{self.current_tag_header}{self.tag_content}{self.buffer}</{self.current_tag}>")
            self.buffer = ""
        return events


class CopilotAgent:
    """
    Autonomous multi-turn clinical pharmacology agent with tool-calling,
    deep GraphRAG context retrieval, dynamic stack intent inference,
    deterministic DDI collision matrix grounding, and real-time SSE streaming.
    """

    @classmethod
    def get_registered_modes(cls) -> List[Dict[str, Any]]:
        return MODES_METADATA

    @classmethod
    def extract_entities_from_messages(cls, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Scans conversation history (especially the latest user prompt) for known pharmacological compounds
        and returns catalog keys to enrich GraphRAG & PK/PD context.
        """
        if not messages:
            return []
        catalog = CatalogService()
        found_keys: Set[str] = set()

        user_texts = [str(m.get("content", "")) for m in messages if m.get("role") == "user"]
        combined_text = " ".join(user_texts[-3:]).lower() if user_texts else ""
        if not combined_text:
            return []

        words = re.findall(r"[a-z0-9_\-\+]+", combined_text)
        for w in words:
            if len(w) >= 3:
                comp = catalog.get_compound(w, auto_enrich=False) or catalog.find_by_synonym(w)
                if comp and comp.get("key"):
                    found_keys.add(comp["key"])

        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            comp = catalog.get_compound(bigram, auto_enrich=False) or catalog.find_by_synonym(bigram)
            if comp and comp.get("key"):
                found_keys.add(comp["key"])

        return list(found_keys)

    @classmethod
    def get_evidence_based_recommendations(
        cls,
        compounds: List[Dict[str, Any]],
        biometrics: Dict[str, Any],
        protocol_goal: Optional[str] = None,
        protocol_objective: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically derives clinical, evidence-graded stack adjustments and additions
        grounded in deterministic organ burden offsetting, therapeutic gap analysis,
        and Loewe/Bliss synergy optimization without bro-science folklore.
        """
        catalog = CatalogService()
        interaction_engine = InteractionEngine()
        existing_keys = {str(c.get("key") or c.get("name") or "").lower() for c in compounds}

        eval_res = interaction_engine.analyze_stack(compounds, profile={"labs": biometrics}) if compounds else {}
        breakdown = eval_res.get("breakdown", {})
        organ_burdens = breakdown.get("organ_burdens", {})

        intent_res = StackIntentEngine.analyze(
            compounds=compounds,
            biometrics=biometrics,
            user_goal_id=protocol_goal,
            user_objective_text=protocol_objective
        )
        therapeutic_gaps = intent_res.get("therapeutic_gaps", [])
        active_goal = intent_res.get("active_goal_id", "auto")

        recommendations: List[Dict[str, Any]] = []
        candidate_pool: List[Dict[str, Any]] = []

        # 1. Renal / BP / RAAS Burden
        renal_score = organ_burdens.get("renal", {}).get("score", 0)
        cv_score = organ_burdens.get("cardiovascular", {}).get("score", 0)
        bp_val = float(biometrics.get("blood_pressure", 120))
        if (renal_score > 0 or cv_score > 0 or bp_val > 125 or any("cardio" in str(g).lower() or "blood pressure" in str(g).lower() for g in therapeutic_gaps) or active_goal == "anabolic_physique"):
            if "telmisartan" not in existing_keys:
                candidate_pool.append({
                    "key": "telmisartan",
                    "name": "Telmisartan",
                    "target": "AT1 Receptor Antagonist (Ki=12 nM) & PPAR-gamma Partial Agonist",
                    "standard_dose": "20-40 mg oral daily (Morning)",
                    "clinical_purpose": "Blocks RAAS-mediated renal vasoconstriction, prevents Left Ventricular Hypertrophy (LVH), and improves insulin sensitivity via PPAR-gamma.",
                    "solves_burden": "Renal & Cardiovascular Endothelial Strain",
                    "evidence_grade": "FDA Approved / Phase III RCT",
                    "interaction_safety": "Clean - Cleared by hepatic glucuronidation (UGT1A3), no CYP3A4 burden."
                })
            if "nebivolol" not in existing_keys and (cv_score >= 20 or bp_val > 130):
                candidate_pool.append({
                    "key": "nebivolol",
                    "name": "Nebivolol",
                    "target": "Highly Selective Beta-1 Adrenergic Antagonist & eNOS Stimulator (NO Release)",
                    "standard_dose": "2.5-5 mg oral daily (Morning)",
                    "clinical_purpose": "Reduces resting heart rate and arterial stiffness via endothelial nitric oxide release without Beta-2 bronchoconstriction or lipid worsening.",
                    "solves_burden": "Sympathetic Hyper-activation & Tachycardia",
                    "evidence_grade": "FDA Approved / Phase III Cardioprotective",
                    "interaction_safety": "CYP2D6 substrate; titrate cautiously if taking strong 2D6 inhibitors."
                })

        # 2. Hepatic / Transaminase / Biliary Burden
        hepatic_score = organ_burdens.get("hepatic", {}).get("score", 0)
        alt_val = float(biometrics.get("alt_u_l", 25))
        if hepatic_score > 0 or alt_val > 40 or any("hepatic" in str(g).lower() or "liver" in str(g).lower() for g in therapeutic_gaps):
            if "tudca" not in existing_keys:
                candidate_pool.append({
                    "key": "tudca",
                    "name": "Tauroursodeoxycholic Acid (TUDCA)",
                    "target": "Hydrophilic Bile Acid & Endoplasmic Reticulum (ER) Chaperone",
                    "standard_dose": "250-500 mg oral twice daily with meals",
                    "clinical_purpose": "Alleviates hepatocyte ER stress, promotes biliary flow, and lowers elevated AST/ALT.",
                    "solves_burden": "Cholestasis & Hepatic Transaminase Elevation",
                    "evidence_grade": "Clinical Grade / Hepatology Human Trials",
                    "interaction_safety": "Zero CYP450 interaction; excellent pharmacokinetic safety profile."
                })
            if "nac" not in existing_keys:
                candidate_pool.append({
                    "key": "nac",
                    "name": "N-Acetyl Cysteine (NAC)",
                    "target": "Rate-Limiting Cysteine Donor for Glutathione Biosynthesis (GCL / Nrf2)",
                    "standard_dose": "600-1200 mg oral daily (Morning/Midday)",
                    "clinical_purpose": "Restores intracellular glutathione pools and protects hepatocytes and renal tubules from reactive metabolites.",
                    "solves_burden": "Oxidative Stress & Phase II Conjugation Depletion",
                    "evidence_grade": "USP Monograph / Extensive Clinical Validation",
                    "interaction_safety": "Clean metabolic profile."
                })

        # 3. Lipid & Atherogenic Burden (ApoB / LDL / HDL suppression)
        lipid_score = organ_burdens.get("lipid", {}).get("score", 0)
        if lipid_score > 0 or any("lipid" in str(g).lower() or "apob" in str(g).lower() for g in therapeutic_gaps) or active_goal == "anabolic_physique":
            if "pitavastatin" not in existing_keys:
                candidate_pool.append({
                    "key": "pitavastatin",
                    "name": "Pitavastatin",
                    "target": "HMG-CoA Reductase Inhibitor (HMGCR)",
                    "standard_dose": "1-2 mg oral daily (Bedtime)",
                    "clinical_purpose": "Upregulates hepatic LDL receptors to clear atherogenic ApoB particles with minimal CYP3A4 competition and neutral glycemic profile.",
                    "solves_burden": "Atherogenic Dyslipidemia & ApoB Surge",
                    "evidence_grade": "Phase III / REAL-CAD Outcomes Trial",
                    "interaction_safety": "Cleared predominantly by glucuronidation (UGT1A3/2B7) and OATP1B1; minimal CYP3A4 conflict."
                })
            if "ezetimibe" not in existing_keys:
                candidate_pool.append({
                    "key": "ezetimibe",
                    "name": "Ezetimibe",
                    "target": "Niemann-Pick C1-Like 1 (NPC1L1) Transporter Inhibitor",
                    "standard_dose": "10 mg oral daily (Morning)",
                    "clinical_purpose": "Selectively inhibits intestinal brush-border cholesterol absorption, lowering ApoB and LDL-C additively.",
                    "solves_burden": "Atherogenic Lipid Burden",
                    "evidence_grade": "IMPROVE-IT Trial / FDA Approved",
                    "interaction_safety": "Independent of CYP450 enzymes."
                })

        # 4. Prolactin / Progestogenic Burden (19-nor steroids)
        has_19nor = any(
            any(w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower()
                for w in ["trenbolone", "nandrolone", "deca", "npp", "ment", "trestolone"])
            for c in compounds
        )
        if has_19nor or any("prolactin" in str(g).lower() for g in therapeutic_gaps):
            if "p5p" not in existing_keys:
                candidate_pool.append({
                    "key": "p5p",
                    "name": "Pyridoxal-5-Phosphate (P-5-P)",
                    "target": "DOPA Decarboxylase Co-factor (Aromatic L-Amino Acid Decarboxylase)",
                    "standard_dose": "50-100 mg oral daily (Bedtime)",
                    "clinical_purpose": "Enhances endogenous dopamine synthesis in the tuberoinfundibular pathway to tonically inhibit pituitary prolactin secretion.",
                    "solves_burden": "Hyperprolactinemia & Progestogenic Breast Tenderness",
                    "evidence_grade": "Peer-Reviewed Clinical Endocrinology Studies",
                    "interaction_safety": "Safe water-soluble co-factor."
                })

        # 5. Aromatase Inhibitors & Estrogen Balance (Aromatizable Androgens / Hypertrophy)
        has_aromatizable = any(
            any(w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower()
                for w in ["testosterone", "testc", "testcyp", "teste", "testenan", "dianabol", "dbol", "methandrostenolone", "boldenone", "equipoise"])
            for c in compounds
        )
        has_any_androgen = any(
            any(w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower()
                for w in ["testosterone", "trenbolone", "nandrolone", "deca", "anavar", "winstrol", "primobolan", "masteron", "dianabol", "anadrol"])
            for c in compounds
        )
        has_ai = any(
            any(w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower()
                for w in ["anastrozole", "arimidex", "exemestane", "aromasin", "letrozole", "femara"])
            for c in compounds
        )
        if (has_aromatizable or has_any_androgen or active_goal == "anabolic_physique") and not has_ai:
            if "anastrozole" not in existing_keys:
                candidate_pool.append({
                    "key": "anastrozole",
                    "name": "Anastrozole (Arimidex)",
                    "target": "Selective Non-Steroidal Competitive Aromatase (CYP19A1) Inhibitor (IC50 = 15 nM)",
                    "standard_dose": "0.25-0.5 mg oral twice weekly (titrated to E2 bloodwork)",
                    "clinical_purpose": "Reversibly inhibits CYP19A1 aromatase to prevent excessive conversion of testosterone to estradiol, mitigating gynecomastia, fluid retention, and blood pressure elevation.",
                    "solves_burden": "Aromatization & High Estradiol (E2) Burden",
                    "evidence_grade": "FDA Approved / Clinical Endocrinology Gold Standard",
                    "interaction_safety": "Titrate carefully with sensitive estradiol LC-MS/MS testing; maintain target E2 (20-30 pg/mL) to preserve bone mineral density and lipid synthesis."
                })
            if "exemestane" not in existing_keys:
                candidate_pool.append({
                    "key": "exemestane",
                    "name": "Exemestane (Aromasin)",
                    "target": "Type I Steroidal Irreversible (Suicidal) Aromatase Inactivator",
                    "standard_dose": "12.5 mg oral twice weekly or every other day with a fat-containing meal",
                    "clinical_purpose": "Permanently inactivates CYP19A1 aromatase without estrogen rebound upon cessation, with favorable lipid neutrality and slight androgenic IGF-1 boosting co-effects.",
                    "solves_burden": "Aromatase Hyperactivity & Gynecomastia Risk",
                    "evidence_grade": "FDA Approved / Phase III RCT",
                    "interaction_safety": "CYP3A4 substrate; take with dietary lipids for optimal absorption."
                })

        # 6. Cognitive Focus / Stimulant Jitter / Neuroprotection
        if active_goal in ("cognitive_focus", "cns_stimulation") or any(c.get("drug_class") == "CNS Stimulant" for c in compounds):
            if "l_theanine" not in existing_keys and "theanine" not in existing_keys:
                candidate_pool.append({
                    "key": "l_theanine",
                    "name": "L-Theanine",
                    "target": "Glutamate Receptor (AMPA/Kainate) Modulator & GABAergic Enhancer",
                    "standard_dose": "100-200 mg oral co-administered with stimulant",
                    "clinical_purpose": "Crosses blood-brain barrier to attenuate peripheral sympathomimetic vasoconstriction and jitters while enhancing alpha brain waves (8-12 Hz) for calm focus.",
                    "solves_burden": "Sympathomimetic Jitters & Cortical Excitotoxicity",
                    "evidence_grade": "Human Double-Blind RCTs",
                    "interaction_safety": "Zero CYP conflicts; synergistic Loewe CI with methylxanthines."
                })
            if "alpha_gpc" not in existing_keys and "citicoline" not in existing_keys:
                candidate_pool.append({
                    "key": "alpha_gpc",
                    "name": "Alpha-GPC (L-Alpha Glycerylphosphorylcholine)",
                    "target": "Acetylcholine Precursor & Phospholipid Biosynthesis Donor",
                    "standard_dose": "300-600 mg oral daily (Morning)",
                    "clinical_purpose": "Supplies bioavailable choline to maintain central acetylcholine pools during heightened cognitive demand.",
                    "solves_burden": "Central Cholinergic Depletion",
                    "evidence_grade": "Human Clinical Trials",
                    "interaction_safety": "Clean metabolic profile."
                })

        # 6. Longevity / Metabolic / Autophagy
        if active_goal == "longevity_autophagy" or any("longevity" in str(g).lower() or "ampk" in str(g).lower() for g in therapeutic_gaps):
            if "metformin" not in existing_keys:
                candidate_pool.append({
                    "key": "metformin",
                    "name": "Metformin",
                    "target": "Mitochondrial Complex I Inhibitor (Mild) & AMPK Activator",
                    "standard_dose": "500-1000 mg oral daily with dinner",
                    "clinical_purpose": "Increases AMP/ATP ratio to stimulate AMPK -> PGC-1alpha and suppress mTORC1, enhancing cellular autophagy and insulin sensitivity.",
                    "solves_burden": "Insulin Resistance & mTORC1 Hyper-activation",
                    "evidence_grade": "TAME Trial / Extensive Longevity Cohorts",
                    "interaction_safety": "Excreted unchanged by renal OCT2/MATE transporters; monitor eGFR."
                })

        # 7. Sleep Architecture / Recovery / Nocturnal Cortisol
        if active_goal == "sleep_stress_recovery" or any("sleep" in str(g).lower() or "cortisol" in str(g).lower() for g in therapeutic_gaps):
            if "magnesium_glycinate" not in existing_keys and "magnesium" not in existing_keys:
                candidate_pool.append({
                    "key": "magnesium_glycinate",
                    "name": "Magnesium Bisglycinate",
                    "target": "NMDA Receptor Voltage-Dependent Blocker & GABA-A Allosteric Facilitator",
                    "standard_dose": "200-400 mg elemental Mg oral (Bedtime)",
                    "clinical_purpose": "Promotes central nervous system down-regulation, blunts nocturnal catecholamines, and deepens Slow-Wave Sleep (SWS).",
                    "solves_burden": "Nocturnal Hyperarousal & Muscle Hypertonicity",
                    "evidence_grade": "Human Sleep Polysomnography Studies",
                    "interaction_safety": "Non-sedating, highly bioavailable chelate."
                })

        for cand in candidate_pool:
            cand_key = cand["key"]
            if cand_key not in existing_keys:
                recommendations.append(cand)

        return recommendations[:6]

    @classmethod
    def execute_tool(cls, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministic pharmacology tool execution dispatcher.
        """
        catalog = CatalogService()
        graph_db = get_graph_database()
        interaction_engine = InteractionEngine()

        if tool_name in ("get_compound_details", "get_compound_info"):
            compound_name = str(arguments.get("compound_name") or arguments.get("compound_key") or "").strip()
            comp = catalog.get_compound(compound_name, auto_enrich=False) or catalog.find_by_synonym(compound_name)
            if not comp:
                return {"error": f"Compound '{compound_name}' not found in catalog."}
            return {
                "name": comp.get("name"),
                "canonical_name": comp.get("canonical_name"),
                "drug_class": comp.get("drug_class"),
                "molecular_weight": comp.get("molecular_weight"),
                "logp": comp.get("logp"),
                "half_life_hours": comp.get("t_half_numeric") or comp.get("half_life_hours") or comp.get("half_life"),
                "tmax_hours": comp.get("t_max_h") or comp.get("tmax_hours") or comp.get("t_max"),
                "oral_bioavailability_pct": (
                    round(float(comp.get("bioavailability_f")) * 100, 1)
                    if comp.get("bioavailability_f") is not None
                    else comp.get("oral_bioavailability")
                ),
                "volume_of_distribution_l_kg": comp.get("volume_of_distribution_l_kg") or comp.get("volume_of_distribution"),
                "protein_binding_pct": comp.get("protein_binding_pct") or comp.get("protein_binding"),
                "clearance_routes": comp.get("clearance_routes"),
                "is_narrow_therapeutic_index": bool(comp.get("is_narrow_therapeutic_index")),
                "cyp_metabolism": comp.get("cyp_enzymes") or comp.get("cyp_metabolism", {}),
                "transporters": comp.get("transporters", {}),
                "targets": comp.get("receptor_targets", comp.get("targets", []))[:8],
                "standard_dose": comp.get("standard_dose") or comp.get("dosing", {}),
                "boxed_warning": comp.get("boxed_warning"),
                "mechanism": comp.get("mechanism"),
            }

        elif tool_name in ("check_cyp450_conflicts", "analyze_stack_conflicts"):
            compound_keys = arguments.get("compound_keys") or arguments.get("compounds") or []
            biometrics = arguments.get("biometrics", {})
            raw_comps = []
            for k in compound_keys:
                if isinstance(k, dict):
                    raw_comps.append(k)
                    continue
                c = catalog.get_compound(str(k), auto_enrich=False) or catalog.find_by_synonym(str(k))
                if c:
                    raw_comps.append(dict(c))
                else:
                    raw_comps.append({"key": str(k), "name": str(k).title(), "dose_mg": 100.0})

            evaluation = interaction_engine.analyze_stack(raw_comps, profile={"labs": biometrics}) if raw_comps else {}
            breakdown = evaluation.get("breakdown", {})
            cyp_conflicts = breakdown.get("cyp_conflicts", [])
            transporter_conflicts = breakdown.get("transporter_conflicts", [])
            receptor_conflicts = breakdown.get("receptor_conflicts", [])
            syndromes = breakdown.get("syndrome_alerts", [])
            organ_burdens = breakdown.get("organ_burdens", {})

            crit = [c for c in (cyp_conflicts + transporter_conflicts + receptor_conflicts + syndromes) if str(c.get("severity", "")).upper() in ("CRITICAL", "HIGH", "HIGH_RISK", "SEVERE_CONTRAINDICATION")]
            mod = [c for c in (cyp_conflicts + transporter_conflicts + receptor_conflicts + syndromes) if str(c.get("severity", "")).upper() not in ("CRITICAL", "HIGH", "HIGH_RISK", "SEVERE_CONTRAINDICATION")]

            return {
                "cumulative_risk_score": evaluation.get("cumulative_risk_score", 0),
                "risk_band": evaluation.get("risk_band", "minimal"),
                "summary": evaluation.get("summary", "No severe conflicts detected."),
                "conflict_count": evaluation.get("conflict_count", len(crit) + len(mod)),
                "critical_conflicts": crit,
                "moderate_conflicts": mod,
                "cyp_conflicts": cyp_conflicts,
                "cyp_load": evaluation.get("cyp_load", breakdown.get("cyp_conflicts", [])),
                "conflicts": crit + mod,
                "transporter_conflicts": transporter_conflicts,
                "receptor_conflicts": receptor_conflicts,
                "syndrome_alerts": syndromes,
                "organ_burdens": organ_burdens,
                "synergies": evaluation.get("synergies", breakdown.get("synergistic_benefits", [])),
                "active_mitigations": breakdown.get("active_mitigations", []),
                "uncompensated_risks": breakdown.get("uncompensated_risks", []),
            }

        elif tool_name == "simulate_pkpd":
            compound_key = str(arguments.get("compound_key", "")).strip()
            dose_mg = float(arguments.get("dose_mg", 100.0))
            tau_h = float(arguments.get("dosing_interval_h", 24.0))
            age = int(arguments.get("age", 30))
            weight_kg = float(arguments.get("weight_kg", 75.0))
            egfr = float(arguments.get("egfr", 95.0))
            alt_u_l = float(arguments.get("alt_u_l", 25.0))

            comp_data = catalog.get_compound(compound_key, auto_enrich=False) or catalog.find_by_synonym(compound_key)
            if not comp_data:
                return {"error": f"Compound '{compound_key}' not found for PK simulation."}

            req = PKPDSimulationRequest(
                compound_key=compound_key,
                dose_mg=dose_mg,
                dosing_interval_h=tau_h,
                simulation_duration_h=max(48.0, tau_h * 2),
                route=str(arguments.get("route", "oral")).lower(),
                steady_state=True,
                age=age,
                weight_kg=weight_kg,
                egfr=egfr,
                alt_u_l=alt_u_l,
            )
            sim_res = PKPDEngine.simulate(comp_data, req)
            return {
                "compound": sim_res.compound_name,
                "cmax_ng_ml": round(sim_res.c_max_ng_ml, 2),
                "cmax_mg_l": round(sim_res.c_max_ng_ml / 1000.0, 4),
                "tmax_h": round(sim_res.t_max_h, 2),
                "auc_ng_h_ml": round(sim_res.auc_0_tau_ng_h_ml, 2),
                "auc_mg_h_l": round(sim_res.auc_0_tau_ng_h_ml / 1000.0, 3),
                "steady_state_accumulation_ratio": round(sim_res.accumulation_ratio, 2),
                "effective_half_life_h": round(sim_res.elimination_half_life_effective_h, 2),
                "time_in_therapeutic_window_pct": round(sim_res.time_in_therapeutic_window_pct, 1),
            }

        elif tool_name in ("evaluate_synergies", "evaluate_multi_agent_synergy"):
            compound_keys = arguments.get("compound_keys") or arguments.get("compounds") or []
            raw_comps = []
            for k in compound_keys:
                c = catalog.get_compound(str(k), auto_enrich=False) or catalog.find_by_synonym(str(k))
                if c:
                    raw_comps.append(dict(c))
                else:
                    raw_comps.append({"key": str(k), "name": str(k).title()})
            synergy_engine = SynergyEngine()
            return synergy_engine.evaluate_multi_agent_synergy(raw_comps)

        elif tool_name == "query_graphrag_subgraph":
            entity_ids = arguments.get("entity_ids", [])
            max_hops = int(arguments.get("max_hops", 2))
            context = graph_db.get_graphrag_context(entity_ids=entity_ids, max_hops=max_hops)
            return {
                "triple_count": context.get("triple_count", 0),
                "summary": context.get("text_summary", ""),
                "target_competition": context.get("target_competition", []),
                "causal_chains": context.get("causal_chains", [])[:8],
            }

        elif tool_name == "query_pathway_cascade":
            target_id = str(arguments.get("target_id") or arguments.get("target_name") or "").strip()
            pathway_svc = PathwayService()
            cascade = pathway_svc.get_target_cascade(target_id)
            return {
                "target_id": target_id,
                "cascade": cascade
            }

        elif tool_name == "get_evidence_based_recommendations":
            compound_keys = arguments.get("compound_keys") or arguments.get("compounds") or []
            biometrics = arguments.get("biometrics", {})
            raw_comps = []
            for k in compound_keys:
                c = catalog.get_compound(str(k), auto_enrich=False) or catalog.find_by_synonym(str(k))
                if c:
                    raw_comps.append(dict(c))
                else:
                    raw_comps.append({"key": str(k), "name": str(k).title()})
            recs = cls.get_evidence_based_recommendations(
                compounds=raw_comps,
                biometrics=biometrics,
                protocol_goal=arguments.get("protocol_goal"),
                protocol_objective=arguments.get("protocol_objective")
            )
            return {"recommendations": recs, "count": len(recs)}

        elif tool_name == "calculate_individualized_dosing":
            compound_key = str(arguments.get("compound_key", "")).strip()
            biometrics = arguments.get("biometrics", {})
            default_dose = get_default_compound_dose(compound_key)
            base_mg = float(default_dose.get("dose_mg", 100.0))
            
            weight_kg = float(biometrics.get("weight_kg", 75.0))
            egfr = float(biometrics.get("egfr", 95.0))
            alt_u_l = float(biometrics.get("alt_u_l", 25.0))
            age = int(biometrics.get("age", 30))

            weight_factor = weight_kg / 75.0
            renal_factor = max(0.4, min(1.2, egfr / 90.0)) if egfr < 60 else 1.0
            hepatic_factor = max(0.5, min(1.0, 45.0 / alt_u_l)) if alt_u_l > 45 else 1.0
            age_factor = 0.85 if age >= 65 else 1.0

            adjusted_mg = round(base_mg * weight_factor * renal_factor * hepatic_factor * age_factor, 2)
            return {
                "compound_key": compound_key,
                "standard_dose": default_dose.get("dose_display", f"{base_mg} mg"),
                "adjusted_recommended_dose_mg": adjusted_mg,
                "scaling_factors": {
                    "weight_factor": round(weight_factor, 2),
                    "renal_clearance_factor": round(renal_factor, 2),
                    "hepatic_clearance_factor": round(hepatic_factor, 2),
                    "age_factor": age_factor
                },
                "clinical_notes": (
                    f"Scaled for {weight_kg}kg body weight"
                    + (f" with {int(renal_factor*100)}% renal adjustment (eGFR: {egfr})" if renal_factor < 1.0 else "")
                    + (f" with {int(hepatic_factor*100)}% hepatic adjustment (ALT: {alt_u_l})" if hepatic_factor < 1.0 else "")
                )
            }

        elif tool_name in ("search_fda_drug_label", "search_biomedical_literature"):
            query = str(arguments.get("query") or arguments.get("compound_name") or "").strip()
            try:
                from app.services.live_enrichment import LiveEnrichmentService
                live_svc = LiveEnrichmentService(timeout_seconds=4.0)
                fda_data = live_svc.fetch_openfda(query)
                return {
                    "query": query,
                    "epc_classes": fda_data.get("pharm_class_epc", []),
                    "moa_classes": fda_data.get("pharm_class_moa", []),
                    "boxed_warning": fda_data.get("boxed_warning"),
                    "warnings": (fda_data.get("warnings") or [])[:3],
                    "contraindications": (fda_data.get("contraindications") or [])[:3],
                    "drug_interactions": (fda_data.get("drug_interactions") or [])[:3],
                }
            except Exception as e:
                return {"error": f"FDA search failed: {str(e)}"}

        elif tool_name in ("build_stack_from_scratch", "propose_stack_from_scratch", "create_protocol_from_scratch"):
            goal = arguments.get("goal") or arguments.get("protocol_goal") or "cognitive_focus"
            biometrics = arguments.get("biometrics", {})
            preferences = arguments.get("preferences", {})
            custom_notes = arguments.get("custom_notes") or arguments.get("custom_instructions") or arguments.get("constraints") or ""
            return StackIntentEngine.build_scratch_stack_proposal(
                goal_id=goal,
                biometrics=biometrics,
                preferences=preferences,
                custom_notes=custom_notes,
            )

        elif tool_name in ("simulate_stack_diff", "simulate_diff", "what_if_simulation"):
            from app.services.stack_diff_simulator import StackDiffSimulator
            base_stack = arguments.get("base_stack") or arguments.get("current_stack") or []
            diff = arguments.get("diff") or {
                "add": arguments.get("add", []),
                "modify": arguments.get("modify", []),
                "remove": arguments.get("remove", []),
            }
            biometrics = arguments.get("biometrics", {})
            return StackDiffSimulator.simulate_diff(base_stack, diff, biometrics)

        elif tool_name in ("search_pubmed_literature", "search_biomedical_literature", "search_pubmed"):
            from app.services.pubmed_service import PubMedService
            query = str(arguments.get("query") or arguments.get("compound_name") or arguments.get("topic") or "").strip()
            max_res = int(arguments.get("max_results", 4))
            pubmed_svc = PubMedService()
            citations = pubmed_svc.search_literature(query, max_results=max_res)
            return {"query": query, "count": len(citations), "citations": citations}

        elif tool_name in ("search_clinical_trials", "search_trials"):
            from app.services.pubmed_service import PubMedService
            query = str(arguments.get("query") or arguments.get("condition") or arguments.get("intervention") or "").strip()
            max_res = int(arguments.get("max_results", 3))
            pubmed_svc = PubMedService()
            trials = pubmed_svc.search_clinical_trials(query, max_results=max_res)
            return {"query": query, "count": len(trials), "trials": trials}

        elif tool_name in ("get_circadian_receptor_occupancy", "calculate_receptor_occupancy"):
            compound_key = str(arguments.get("compound_key") or arguments.get("compound") or "").strip()
            dose_mg = float(arguments.get("dose_mg", 100.0))
            route = str(arguments.get("route", "oral")).lower()
            interval_h = float(arguments.get("dosing_interval_h", 24.0))
            biometrics = arguments.get("biometrics", {})
            comp_rec = catalog.get_compound(compound_key, auto_enrich=False) or catalog.find_by_synonym(compound_key)
            if not comp_rec:
                return {"error": f"Compound '{compound_key}' not found in catalog."}
            return PKPDEngine.calculate_circadian_receptor_occupancy(
                compound=comp_rec,
                dose_mg=dose_mg,
                route=route,
                dosing_interval_h=interval_h,
                biometrics=biometrics,
            )

        elif tool_name == "propose_stack_diff":
            from app.services.action_card_validator import ActionCardValidator
            raw_diff = {
                "add": arguments.get("add", arguments.get("additions", [])),
                "modify": arguments.get("modify", arguments.get("modifications", [])),
                "remove": arguments.get("remove", arguments.get("removals", [])),
            }
            sanitized, notes = ActionCardValidator.validate_and_sanitize_card(
                card_type="stack_diff",
                payload=raw_diff,
                biometrics=arguments.get("biometrics", {}),
            )
            return {
                "action_card": "stack_diff",
                "additions": sanitized.get("add", []),
                "modifications": sanitized.get("modify", []),
                "removals": sanitized.get("remove", []),
                "validation_meta": sanitized.get("validation_meta", {}),
            }

        return {"error": f"Unknown tool: {tool_name}"}

    @classmethod
    def build_system_context(
        cls,
        persona: str,
        stack: List[str],
        biometrics: Dict[str, Any],
        protocol_goal: Optional[str] = None,
        protocol_objective: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Constructs the high-fidelity scientific grounding context:
        1. Base PhD/MD persona instructions with strict Anti-Bro-Science Mandate.
        2. Patient biometrics and clearance parameters.
        3. Canonicalized workbench stack with exact doses, routes, frequencies.
        4. Dynamic Stack Purpose & Therapeutic Gap Analysis (StackIntentEngine).
        5. Real-time deterministic Collision Matrix & DDI analysis (CYP450, transporters, syndromes, organ burdens).
        6. Steady-State PK/PD kinetics (Cmax, Tmax, AUC, half-life, accumulation ratio Racc).
        7. Evidence-Based Stack Adjustments & Candidate Recommendations (Graph-derived).
        8. Quantitative Multi-Agent Synergy Modeling (Loewe CI & Bliss Delta).
        9. Biological Signal Transduction Pathways (Reactome / PathwayService).
        10. 3-hop GraphRAG biological network triples and multi-tier causal reasoning chains.
        """
        base_prompt = PERSONA_SYSTEM_PROMPTS.get(persona, PERSONA_SYSTEM_PROMPTS["architect"])
        catalog = CatalogService()
        graph_db = get_graph_database()
        interaction_engine = InteractionEngine()
        pathway_svc = PathwayService()
        synergy_engine = SynergyEngine()

        clean_stack_raw = [str(s).strip() for s in stack if s and str(s).strip()]
        
        # Also extract entities from recent messages if not in stack
        if messages:
            extracted_from_chat = cls.extract_entities_from_messages(messages)
            for ext in extracted_from_chat:
                if ext not in clean_stack_raw and not any(ext in s for s in clean_stack_raw):
                    clean_stack_raw.append(ext)

        # 1. Canonicalize and extract structured compound records
        canonical_compounds: List[Dict[str, Any]] = []
        canonical_keys: List[str] = []

        for item_str in clean_stack_raw:
            spec = parse_compound_spec(item_str)
            raw_key = spec.get("key", item_str)
            comp_record = catalog.get_compound(raw_key, auto_enrich=False) or catalog.find_by_synonym(raw_key)
            if comp_record:
                merged = dict(comp_record)
                merged.update(spec)
                canonical_compounds.append(merged)
                canonical_keys.append(comp_record.get("key", raw_key))
            else:
                canonical_compounds.append(spec)
                canonical_keys.append(raw_key)

        canonical_compounds = catalog.canonicalize_and_merge_stack(canonical_compounds)

        # 2. Patient clearance profile
        age = biometrics.get("age", 30)
        weight_kg = biometrics.get("weight_kg", 75)
        egfr = biometrics.get("egfr", 95)
        alt_u_l = biometrics.get("alt_u_l", 25)
        bp = biometrics.get("blood_pressure", 120)
        body_fat = biometrics.get("body_fat_pct", 15)

        bio_summary = (
            f"Age: {age} yrs | Weight: {weight_kg} kg | eGFR: {egfr} mL/min/1.73m² | "
            f"ALT: {alt_u_l} U/L | Resting BP: {bp} mmHg | Body Fat: {body_fat}%"
        )

        # 3. Dynamic Stack Intent, Modality Segmentation, and Therapeutic Gap Analysis
        intent_analysis = StackIntentEngine.analyze(
            compounds=canonical_compounds,
            biometrics=biometrics,
            user_goal_id=protocol_goal,
            user_objective_text=protocol_objective
        )
        intent_grounding = intent_analysis.get("grounding_text", "")

        # 4. Deterministic Interaction & Collision Matrix Grounding
        ddi_sections = []
        if canonical_compounds:
            try:
                eval_res = interaction_engine.analyze_stack(canonical_compounds, profile={"labs": biometrics})
                risk_score = eval_res.get("cumulative_risk_score", 0)
                risk_band = str(eval_res.get("risk_band", "minimal")).upper()
                ddi_summary = eval_res.get("summary", "")
                breakdown = eval_res.get("breakdown", {})

                ddi_sections.append("### DETERMINISTIC DDI COLLISION MATRIX & SAFETY AUDIT:")
                ddi_sections.append(f"- **Cumulative Risk Score**: {risk_score}/100 ({risk_band})")
                ddi_sections.append(f"- **System Audit Summary**: {ddi_summary}")

                cyp_conflicts = breakdown.get("cyp_conflicts", [])
                if cyp_conflicts:
                    ddi_sections.append("- **CYP450 Enzyme Conflicts & AUCR Surges**:")
                    for cc in cyp_conflicts[:4]:
                        ddi_sections.append(f"  * {cc.get('title')}: {cc.get('description')} [Severity: {cc.get('severity')}]")

                transporter_conflicts = breakdown.get("transporter_conflicts", [])
                if transporter_conflicts:
                    ddi_sections.append("- **Transporter Clashes (P-gp / BCRP / OATP / OCT)**:")
                    for tc in transporter_conflicts[:3]:
                        ddi_sections.append(f"  * {tc.get('title')}: {tc.get('description')}")

                receptor_conflicts = breakdown.get("receptor_conflicts", [])
                if receptor_conflicts:
                    ddi_sections.append("- **Pharmacodynamic Target Overlaps & Collisions**:")
                    for rc in receptor_conflicts[:4]:
                        ddi_sections.append(f"  * {rc.get('title')}: {rc.get('description')}")

                syndromes = breakdown.get("syndrome_alerts", [])
                if syndromes:
                    ddi_sections.append("- **Acute Multi-Agent Syndrome Alerts**:")
                    for syn in syndromes[:3]:
                        ddi_sections.append(f"  * ⚠️ **{syn.get('title')}** ({syn.get('severity')}): {syn.get('description')}")

                organ_burdens = breakdown.get("organ_burdens", {})
                if organ_burdens:
                    burden_strs = [f"{k.capitalize()}: {v.get('level', 'Low')} ({v.get('score', 0)})" for k, v in organ_burdens.items()]
                    ddi_sections.append(f"- **Organ System Burdens**: {', '.join(burden_strs)}")

                mitigations = breakdown.get("active_mitigations", [])
                if mitigations:
                    ddi_sections.append("- **Active Stack Counterbalances & Mitigations**:")
                    for mit in mitigations[:3]:
                        ddi_sections.append(f"  * 🛡️ {mit.get('title')}: {mit.get('description')}")

            except Exception as ddi_err:
                ddi_sections.append(f"[Collision Matrix Notice: {ddi_err}]")

        # 5. Deterministic Steady-State PK/PD Kinetics with Biometric Adjustments
        pkpd_sections = []
        if canonical_compounds:
            pkpd_sections.append("### STEADY-STATE PHARMACOKINETICS & CLEARANCE PROFILE:")
            for comp in canonical_compounds[:8]:
                comp_key = comp.get("key") or comp.get("name")
                c_name = comp.get("name") or comp.get("canonical_name") or comp_key
                dose_val = comp.get("dose_mg") or comp.get("dose") or 100.0
                route = comp.get("route", "oral")
                freq = comp.get("frequency", "daily")
                
                try:
                    tau_h = 24.0 if freq == "daily" else (12.0 if "twice" in freq or "bid" in freq else 24.0)
                    req = PKPDSimulationRequest(
                        compound_key=comp_key,
                        dose_mg=float(dose_val),
                        dosing_interval_h=tau_h,
                        simulation_duration_h=max(48.0, tau_h * 2),
                        route=route,
                        steady_state=True,
                        age=age,
                        weight_kg=weight_kg,
                        egfr=egfr,
                        alt_u_l=alt_u_l,
                    )
                    sim = PKPDEngine.simulate(comp, req)
                    cmax_str = f"{round(sim.c_max_ng_ml, 1)} ng/mL ({round(sim.c_max_ng_ml / 1000.0, 3)} mg/L)"
                    t12_str = f"{round(sim.elimination_half_life_effective_h, 1)}h"
                    racc_str = f"{round(sim.accumulation_ratio, 2)}x"
                    pkpd_sections.append(
                        f"- **{c_name}** ({dose_val}mg {route}, tau={tau_h}h): "
                        f"Steady-State Cmax = {cmax_str}, Tmax = {round(sim.t_max_h, 1)}h, "
                        f"Effective t1/2 = {t12_str}, Accumulation Ratio (Racc) = {racc_str}, "
                        f"Time in Target Window = {round(sim.time_in_therapeutic_window_pct, 1)}%"
                    )
                except Exception:
                    t_half = comp.get("t_half_numeric") or comp.get("half_life_hours") or comp.get("half_life", "N/A")
                    bioav = comp.get("bioavailability_f") or comp.get("oral_bioavailability", "N/A")
                    pkpd_sections.append(f"- **{c_name}**: Half-life = {t_half}h, Bioavailability = {bioav}")

        # 6. Evidence-Based Stack Recommendations & Burden Offsetting (Dynamic Graph-Derived)
        rec_sections = []
        try:
            evidence_recs = cls.get_evidence_based_recommendations(
                compounds=canonical_compounds,
                biometrics=biometrics,
                protocol_goal=protocol_goal,
                protocol_objective=protocol_objective
            )
            if evidence_recs:
                rec_sections.append("### EVIDENCE-BASED CANDIDATE ADJACENCIES & CO-FACTORS (GRAPH-DERIVED):")
                rec_sections.append("> Use the clinically validated candidates below when proposing stack adjustments or protective additions:")
                for r in evidence_recs:
                    rec_sections.append(
                        f"- **{r['name']}** [{r['standard_dose']}]: Target = {r['target']} | "
                        f"Clinical Rationale = {r['clinical_purpose']} (Compensates: {r['solves_burden']}) | "
                        f"Evidence = {r['evidence_grade']} | Safety = {r['interaction_safety']}"
                    )
        except Exception as rec_err:
            logger.debug("Evidence recommendations notice: %s", rec_err)

        # 7. Quantitative Synergy Modeling (Loewe & Bliss)
        synergy_sections = []
        if len(canonical_compounds) >= 2:
            try:
                syn_eval = synergy_engine.evaluate_multi_agent_synergy(canonical_compounds)
                loewe = syn_eval.get("loewe_model", {})
                bliss = syn_eval.get("bliss_model", {})
                synergy_sections.append("### QUANTITATIVE MULTI-AGENT SYNERGY MODELING:")
                synergy_sections.append(f"- **Loewe Additivity CI**: {loewe.get('loewe_description', 'N/A')}")
                synergy_sections.append(f"- **Bliss Independence Model**: {bliss.get('bliss_description', 'N/A')}")
                pairs = syn_eval.get("pairwise_synergy_matrix", [])
                if pairs:
                    synergy_sections.append("- **Pairwise Synergy Vectors**:")
                    for p in pairs[:3]:
                        synergy_sections.append(f"  * {p['compound_a']} + {p['compound_b']}: {p['loewe_classification']} (Loewe CI: {p['loewe_combination_index']}, Bliss Delta: {p['bliss_delta_pct']:+.1f}%)")
            except Exception as syn_err:
                logger.debug("Synergy modeling notice: %s", syn_err)

        # 8. Biological Signal Transduction Cascades (PathwayService)
        pathway_sections = []
        if canonical_compounds:
            pathway_sections.append("### INTRACELLULAR SIGNAL TRANSDUCTION & PATHWAY CASCADES:")
            for comp in canonical_compounds[:5]:
                targets = comp.get("receptor_targets") or comp.get("targets") or []
                c_name = comp.get("name") or comp.get("canonical_name") or comp.get("key")
                for tgt in targets[:2]:
                    tgt_name = tgt.get("target") if isinstance(tgt, dict) else str(tgt)
                    if tgt_name:
                        try:
                            casc = pathway_svc.get_target_cascade(tgt_name)
                            pw_label = casc.get("pathway", {}).get("label") or casc.get("pathway", {}).get("name")
                            raw_pws = casc.get("raw_pathways", [])
                            pw_names = [p.get("pathway_name") for p in raw_pws[:2] if p.get("pathway_name")]
                            if pw_label and pw_label not in pw_names:
                                pw_names.insert(0, pw_label)
                            if pw_names:
                                pathway_sections.append(f"- **{c_name} ➔ {tgt_name}**: Transduces via {', '.join(pw_names[:2])}")
                        except Exception:
                            pass


        # 9. Circadian Receptor Occupancy Curves (Dynamic RO(t))
        ro_sections = []
        if canonical_compounds:
            for comp in canonical_compounds[:4]:
                c_key = comp.get("key") or comp.get("name")
                c_name = comp.get("name") or comp.get("canonical_name") or c_key
                dose_val = float(comp.get("dose_mg") or comp.get("dose") or 100.0)
                route = comp.get("route", "oral")
                try:
                    ro_data = PKPDEngine.calculate_circadian_receptor_occupancy(
                        compound=comp,
                        dose_mg=dose_val,
                        route=route,
                        biometrics=biometrics,
                    )
                    targets_ro = ro_data.get("targets", [])
                    if targets_ro:
                        for tro in targets_ro[:2]:
                            win_strs = [f"{w['window'].split(' ')[0]}: {w['receptor_occupancy_pct']}%" for w in tro.get("windows", [])[:4]]
                            ro_sections.append(
                                f"- **{c_name} ➔ {tro['target_name']}** (Kd: {tro['affinity_nm']} nM): "
                                f"Peak RO = {tro['peak_occupancy_pct']}%, Trough = {tro['trough_occupancy_pct']}% [{', '.join(win_strs)}]"
                            )
                except Exception as ro_err:
                    logger.debug("RO calculation notice for %s: %s", c_key, ro_err)

        # 10. Pharmacogenomics (PGx) Warnings & Intrinsic Clearance
        pgx_sections = []
        try:
            from app.services.pgx_engine import PGXEngine
            pgx_warnings = PGXEngine.evaluate_pgx_warnings(canonical_compounds, biometrics)
            if pgx_warnings:
                pgx_sections.append("### PATIENT PHARMACOGENOMICS (PGx) PROFILE & ENZYME CLEARANCE:")
                for pw in pgx_warnings:
                    pgx_sections.append(
                        f"- 🧬 **{pw['gene']} ({pw['phenotype']})** vs **{pw['compound']}** [{pw['severity']}]: {pw['impact']} ➔ *Action*: {pw['clinical_action']}"
                    )
        except Exception as pgx_err:
            logger.debug("PGx context notice: %s", pgx_err)

        # 11. Verified Biomedical Literature & Landmark Clinical Citations
        literature_sections = []
        try:
            from app.services.pubmed_service import PubMedService
            pubmed_svc = PubMedService()
            citations_found = []
            for comp in canonical_compounds[:4]:
                c_key = comp.get("key") or comp.get("name")
                c_name = comp.get("name") or comp.get("canonical_name") or c_key
                c_cites = pubmed_svc.search_literature(str(c_key), max_results=1)
                for cite in c_cites:
                    citations_found.append(f"- **{c_name}**: [{cite.get('journal', 'PubMed')} {cite.get('pub_year', '')}] *\"{cite.get('title')}\"* [PMID: {cite.get('pmid')}]{' (DOI: ' + cite['doi'] + ')' if cite.get('doi') else ''}")
            if citations_found:
                literature_sections.append("### VERIFIED BIOMEDICAL LITERATURE & CLINICAL EVIDENCE:")
                literature_sections.extend(citations_found[:4])
        except Exception as lit_err:
            logger.debug("Literature context notice: %s", lit_err)

        # 12. GraphRAG Context
        graph_context = ""
        if canonical_keys:
            try:
                rag = graph_db.get_graphrag_context(
                    entity_ids=canonical_keys,
                    max_hops=2,
                    include_pkpd=False,
                    include_kinetics=True,
                    include_causal_chains=True
                )
                graph_context = rag.get("formatted_prompt_context", "")
            except Exception as ex:
                graph_context = f"[Graph Context Notice: {ex}]"

        stack_display = []
        for c in canonical_compounds:
            d_str = c.get("effective_daily_display") or f"{c.get('dose', '')} {c.get('unit', 'mg')}"
            r_str = f" ({c.get('route')})" if c.get('route') else ""
            t_str = f" [{c.get('timing')}]" if c.get('timing') else ""
            stack_display.append(f"{c.get('name') or c.get('key')}: {d_str}{r_str}{t_str}")

        full_system_parts = [
            base_prompt,
            "\n### PATIENT BIOMETRICS & CLEARANCE PROFILE:",
            bio_summary,
            f"\n### ACTIVE WORKBENCH STACK ({len(canonical_compounds)} compounds):",
            "\n".join(f"- {s}" for s in stack_display) if stack_display else "No active compounds loaded in workbench.",
        ]

        if intent_grounding:
            full_system_parts.append("\n" + intent_grounding)

        if ddi_sections:
            full_system_parts.append("\n" + "\n".join(ddi_sections))

        if pgx_sections:
            full_system_parts.append("\n" + "\n".join(pgx_sections))

        if pkpd_sections:
            full_system_parts.append("\n" + "\n".join(pkpd_sections))

        if ro_sections:
            full_system_parts.append("\n### CIRCADIAN RECEPTOR OCCUPANCY & TARGET SATURATION RO(t):\n" + "\n".join(ro_sections))

        if rec_sections:
            full_system_parts.append("\n" + "\n".join(rec_sections))

        if synergy_sections:
            full_system_parts.append("\n" + "\n".join(synergy_sections))

        if literature_sections:
            full_system_parts.append("\n" + "\n".join(literature_sections))

        if pathway_sections and len(pathway_sections) > 1:
            full_system_parts.append("\n" + "\n".join(pathway_sections))

        if graph_context:
            full_system_parts.append("\n" + graph_context)

        react_instructions = """
### DYNAMIC GRAPH REASONING, CLINICAL SCRATCHPAD & TOOL PROTOCOL:
You have autonomous access to execute live graph traversals, pathway queries, pharmacokinetic simulations, literature searches, and virtual diff experiments:

1. **Pharmacological Reasoning**: Think deeply through multi-hop biological mechanisms, receptor saturation kinetics ($K_d/K_i$), intracellular pathway cascades, CYP450 AUCR clearance, and organ protection co-factors. Formulate hypotheses and calculate exact chronobiological schedules.
2. **Dynamic Tool Calling**: If you need additional graph data, emit `<tool_call name="tool_name">{"arg": "val"}</tool_call>`.
   - `build_stack_from_scratch`: `{"goal": "cognitive_focus", "biometrics": {...}, "preferences": {...}}`
   - `simulate_stack_diff`: `{"base_stack": ["c1"], "diff": {"add": [{"key": "c2", "dose": 40}], "remove": []}}`
   - `search_pubmed_literature`: `{"query": "telmisartan endothelial LVH", "max_results": 3}`
   - `search_clinical_trials`: `{"query": "hypertrophy resistance training", "max_results": 2}`
   - `get_circadian_receptor_occupancy`: `{"compound_key": "caffeine", "dose_mg": 200}`
   - `query_graphrag_subgraph`: `{"entity_ids": ["compound_or_target"], "max_hops": 2}`
   - `query_pathway_cascade`: `{"target_id": "TARGET_SYMBOL_OR_NAME"}`
   - `get_evidence_based_recommendations`: `{"compound_keys": ["c1", "c2"], "protocol_goal": "hypertrophy"}`
   - `evaluate_multi_agent_synergy`: `{"compound_keys": ["c1", "c2"]}`
   - `get_compound_details`: `{"compound_name": "name"}`
   - `simulate_pkpd`: `{"compound_key": "c", "dose_mg": 100}`
   - `calculate_individualized_dosing`: `{"compound_key": "c", "biometrics": {...}}`
   - `search_fda_drug_label`: `{"query": "search query"}`
3. **CRITICAL USER PRESENTATION & ACTION CARD MANDATE**:
   - Synthesize your complete clinical protocol with structured headings, circadian schedule tables, and bracketed citations.
   - Every protocol proposal or modification MUST conclude with the structured `<action_card type="stack_diff">{"add": [...], "modify": [...], "remove": [...]}</action_card>` at the very end.
"""
        full_system_parts.append(react_instructions)

        if custom_instructions:
            full_system_parts.append(f"\n### USER PREFERENCES & CONSTRAINTS:\n{custom_instructions}\n")

        return "\n".join(full_system_parts)




    @classmethod
    def parse_tool_call_from_text(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Parses structured tool calls from agent generation text.
        Supports XML tags: <tool_call name="...">{"arg": "val"}</tool_call>
        and fallback formats.
        """
        if not text:
            return None

        # Format 1: <tool_call name="tool_name">JSON_ARGS</tool_call>
        tag_match = re.search(r'<tool_call\s+name="([^"]+)"\s*>(.*?)</tool_call>', text, re.DOTALL | re.IGNORECASE)
        if tag_match:
            name = tag_match.group(1).strip()
            raw_args = tag_match.group(2).strip()
            try:
                args = json.loads(raw_args) if raw_args else {}
            except Exception:
                args = {}
            return {"name": name, "arguments": args}

        # Format 2: <call tool="tool_name">JSON_ARGS</call>
        call_match = re.search(r'<call\s+tool="([^"]+)"\s*>(.*?)</call>', text, re.DOTALL | re.IGNORECASE)
        if call_match:
            name = call_match.group(1).strip()
            raw_args = call_match.group(2).strip()
            try:
                args = json.loads(raw_args) if raw_args else {}
            except Exception:
                args = {}
            return {"name": name, "arguments": args}

        # Format 3: ```tool_call / ```json {"tool": "name", "arguments": {...}}
        json_call_match = re.search(r'```(?:json|tool_call)?\s*(\{\s*"tool"\s*:\s*"[^"]+".*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
        if json_call_match:
            try:
                parsed = json.loads(json_call_match.group(1))
                if isinstance(parsed, dict) and "tool" in parsed:
                    return {"name": parsed["tool"], "arguments": parsed.get("arguments", {})}
            except Exception:
                pass

        return None

    @classmethod
    def extract_scratchpad_from_text(cls, text: str) -> str:
        """
        Extracts internal thinking / working scratchpad notes from agent text.
        """
        if not text:
            return ""
        notes = []
        for tag in ["scratchpad", "clinical_notes", "thought", "think", "context", "observation"]:
            matches = re.findall(rf'<{tag}(?:\s+[^>]*)?>(.*?)</{tag}>', text, re.DOTALL | re.IGNORECASE)
            for m in matches:
                clean = m.strip()
                if clean:
                    notes.append(clean)
        return "\n\n".join(notes)

    @classmethod
    def clean_scratchpad_and_tools_from_text(cls, text: str) -> str:
        """
        Strips internal scratchpad and tool call tags from final user-facing text.
        """
        if not text:
            return ""
        cleaned = text
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<scratchpad>.*?</scratchpad>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<clinical_notes>.*?</clinical_notes>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<thought>.*?</thought>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<context>.*?</context>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<observation(?:\s+[^>]*)?>.*?</observation>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<tool_call\s+name="[^"]+"\s*>.*?</tool_call>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<call\s+tool="[^"]+"\s*>.*?</call>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<action_card\s+type="[^"]+"\s*>.*?</action_card>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<(?:think|thought|scratchpad|clinical_notes|context|observation)>.*?$', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        # Also clean any plain-text thought/scratchpad headers that may leak
        cleaned = re.sub(r'(?i)^\s*(?:###?\s*)?(?:Thought(?:\s+Process)?|Scratchpad|Clinical Scratchpad|Internal Reasoning):\s*.*?(?=\n\n|\n[#\*\d]|\Z)', '', cleaned, flags=re.DOTALL | re.MULTILINE)
        return cleaned.strip()

    @classmethod
    def _summarize_observation(cls, tool_name: str, obs: Dict[str, Any]) -> str:
        if not isinstance(obs, dict):
            return str(obs)[:150]
        if "error" in obs:
            return f"Notice: {obs['error']}"
        if tool_name in ("check_cyp450_conflicts", "analyze_stack_conflicts"):
            return f"Cumulative risk score: {obs.get('cumulative_risk_score', 0)}/100 ({obs.get('risk_band', 'minimal')}). {obs.get('summary', '')}"
        elif tool_name == "query_pathway_cascade":
            casc = obs.get("cascade", {})
            pw = casc.get("pathway", {}).get("label") or casc.get("target_name") or obs.get("target_id")
            pheno_count = len(casc.get("phenotypes", [])) if isinstance(casc, dict) else 0
            return f"Signal cascade for '{pw}': Transduces via Reactome | Identified {pheno_count} phenotype/biomarker linkages."
        elif tool_name == "query_graphrag_subgraph":
            return f"Traversed {obs.get('triple_count', 0)} GraphRAG triples. Summary: {obs.get('summary', 'Extracted local biological subgraph.')}"
        elif tool_name == "get_evidence_based_recommendations":
            recs = obs.get("recommendations", [])
            names = [r.get("name") for r in recs[:3] if isinstance(r, dict)]
            return f"Identified {len(recs)} evidence-based candidates ({', '.join(names) if names else 'None'})."
        elif tool_name in ("evaluate_synergies", "evaluate_multi_agent_synergy"):
            loewe = obs.get("loewe_model", {}).get("loewe_description", "")
            return f"Synergy evaluation: {loewe or 'Computed Loewe & Bliss interaction matrices.'}"
        elif tool_name == "simulate_pkpd":
            return f"Cmax = {obs.get('cmax_ng_ml')} ng/mL, t1/2 = {obs.get('effective_half_life_h')}h, Accumulation = {obs.get('steady_state_accumulation_ratio')}x."
        elif tool_name == "calculate_individualized_dosing":
            return f"Recommended scaled dose: {obs.get('adjusted_recommended_dose_mg')} mg. ({obs.get('clinical_notes', '')})"
        elif tool_name in ("build_stack_from_scratch", "propose_stack_from_scratch", "create_protocol_from_scratch"):
            comps = obs.get("compounds", [])
            names = [c.get("name") for c in comps if isinstance(c, dict)]
            return f"Synthesized scratch stack for '{obs.get('goal_title', 'Protocol')}': {len(comps)} compounds ({', '.join(names)})."
        elif tool_name in ("get_compound_details", "get_compound_info"):
            return f"Retrieved {obs.get('canonical_name', obs.get('name'))} (t1/2: {obs.get('half_life_hours')}h, Bioavailability: {obs.get('oral_bioavailability_pct')}%)."
        return f"Tool returned {len(obs)} fields."

    @classmethod
    def format_deterministic_protocol_markdown(cls, proposal: Dict[str, Any], persona: str = "architect") -> str:
        """
        Formats a clean, publication-grade markdown protocol from deterministic StackIntentEngine proposal.
        """
        goal_title = proposal.get("goal_title", "Clinical Protocol")
        compounds = proposal.get("compounds", [])
        
        md_lines = [
            f"### ⚡ HealthAI {persona.upper()} Grounded Protocol: {goal_title}\n",
            f"**Executive Assessment**: Calibrated protocol targeting {goal_title.lower()} with quantitative chronobiological alignment, organ protection co-factors, and zero bro-science.\n",
            "**Key Protocol Components**:",
        ]
        for c in compounds:
            md_lines.append(f"- **{c['name']}** ({c['dose']}{c.get('unit', 'mg')} {c.get('route', 'oral')}, {c.get('timing', 'daily')}): {c.get('target', '')} — {c.get('rationale', '')}")
            
        md_lines.append("\n**Circadian Administration Schedule**:")
        md_lines.append("| Window | Compound | Dose & Route | Pharmacokinetic Rationale |")
        md_lines.append("|---|---|---|---|")
        for c in compounds:
            md_lines.append(f"| {str(c.get('timing', 'Morning')).title()} | {c['name']} | {c['dose']}{c.get('unit', 'mg')} ({c.get('route', 'oral')}) | {c.get('target', 'Target receptor')} |")
            
        md_lines.append("\n*Review proposed modifications in the action card below and click to apply them directly to your workbench stack.*")
        return "\n".join(md_lines)

    @classmethod
    async def stream_copilot_turn(
        cls,
        messages: List[Dict[str, Any]],
        persona: str = "architect",
        stack: Optional[List[str]] = None,
        biometrics: Optional[Dict[str, Any]] = None,
        protocol_goal: Optional[str] = None,
        protocol_objective: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        max_exploration_steps: int = 10,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator for streaming SSE events to the frontend with dynamic multi-step ReAct graph traversal.
        Emits:
        - {"event": "reasoning", "data": "..."} (scratchpad notes, graph exploration steps, telemetry)
        - {"event": "delta", "data": "..."} (synthesized clinical markdown)
        - {"event": "action_card", "data": {...}} (structured stack mutations)
        - {"event": "done", "data": "[DONE]"}
        """
        # Initial instant reasoning telemetry notification
        yield {
            "event": "reasoning",
            "data": f"⚡ Initializing HealthAI {persona.upper()} Copilot | Connecting to 3-hop biological knowledge graph..."
        }

        stack_list = stack or []
        biometrics_dict = biometrics or {}
        system_prompt = await asyncio.to_thread(
            cls.build_system_context,
            persona=persona,
            stack=stack_list,
            biometrics=biometrics_dict,
            protocol_goal=protocol_goal,
            protocol_objective=protocol_objective,
            custom_instructions=custom_instructions,
            messages=messages,
        )

        # Context assembled notification
        yield {
            "event": "reasoning",
            "data": f"🔍 Grounded against Collision Matrix & Steady-State PK/PD for [{', '.join(stack_list) if stack_list else 'general consultation'}] | Streaming from inference engine..."
        }

        current_messages = list(messages)
        action_cards_emitted = set()

        for step in range(1, max_exploration_steps + 1):
            accumulated_turn_content = ""
            accumulated_reasoning_text = ""
            parser = StreamingTagParser()
            emitted_deltas_this_turn: List[str] = []

            # Stream model generation for this iteration in real time
            async for chunk in stream_local_llm_chat(
                messages=current_messages,
                system_prompt=system_prompt,
                temperature=0.2,
                top_p=0.85,
                max_tokens=16384,
            ):
                chunk_type = chunk.get("type")
                data = chunk.get("data")

                if chunk_type == "reasoning":
                    accumulated_reasoning_text += str(data)
                    yield {"event": "reasoning", "data": str(data)}

                elif chunk_type == "content":
                    token_text = str(data)
                    accumulated_turn_content += token_text
                    for ev_type, ev_data in parser.feed(token_text):
                        if ev_type == "reasoning":
                            accumulated_reasoning_text += ev_data
                            yield {"event": "reasoning", "data": ev_data}
                        elif ev_type == "delta":
                            emitted_deltas_this_turn.append(ev_data)
                            yield {"event": "delta", "data": ev_data}

                elif chunk_type == "error":
                    yield {"event": "error", "data": str(data)}

                elif chunk_type == "done":
                    break

            for ev_type, ev_data in parser.flush():
                if ev_type == "reasoning":
                    accumulated_reasoning_text += ev_data
                    yield {"event": "reasoning", "data": ev_data}
                elif ev_type == "delta":
                    emitted_deltas_this_turn.append(ev_data)
                    yield {"event": "delta", "data": ev_data}

            # Check if the agent requested a dynamic graph traversal tool call
            tool_call = cls.parse_tool_call_from_text(accumulated_turn_content)
            if not tool_call and parser.tool_calls:
                for tc_str in parser.tool_calls:
                    tool_call = cls.parse_tool_call_from_text(tc_str)
                    if tool_call:
                        break

            if tool_call and step < max_exploration_steps:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("arguments", {})

                yield {
                    "event": "reasoning",
                    "data": f"\n🔍 [Step {step}] Querying Graph: Executing tool '{tool_name}' with arguments {json.dumps(tool_args)}..."
                }

                # Deterministically execute the requested tool
                obs = await asyncio.to_thread(cls.execute_tool, tool_name, tool_args)
                obs_summary = cls._summarize_observation(tool_name, obs)

                yield {
                    "event": "reasoning",
                    "data": f"📍 [Step {step}] Graph Observation: {obs_summary}\n"
                }

                # Append assistant thoughts and graph observation for next ReAct iteration
                current_messages.append({
                    "role": "assistant",
                    "content": accumulated_turn_content
                })
                current_messages.append({
                    "role": "user",
                    "content": f"<observation for='{tool_name}'>\n{json.dumps(obs, indent=2)}\n</observation>\nReview this graph observation, update your clinical scratchpad, and proceed with further graph exploration if needed, or provide your final clinical response."
                })
                continue
            else:
                # If no delta tokens were emitted at all during streaming, yield full cleaned text or extract from reasoning or fallback proposal
                if not emitted_deltas_this_turn:
                    clean_final_text = cls.clean_scratchpad_and_tools_from_text(accumulated_turn_content)
                    if not clean_final_text:
                        clean_final_text = accumulated_turn_content
                    
                    if not clean_final_text:
                        # Rescue protocol markdown from reasoning trace if present
                        cleaned_reasoning = cls.clean_scratchpad_and_tools_from_text(accumulated_reasoning_text)
                        if cleaned_reasoning and ("**" in cleaned_reasoning or "|" in cleaned_reasoning or "###" in cleaned_reasoning):
                            clean_final_text = cleaned_reasoning
                        else:
                            # Deterministic fallback protocol synthesis
                            active_goal = protocol_goal or "anabolic_physique"
                            try:
                                proposal = StackIntentEngine.build_scratch_stack_proposal(
                                    goal_id=active_goal,
                                    biometrics=biometrics_dict,
                                )
                                clean_final_text = cls.format_deterministic_protocol_markdown(proposal, persona)
                            except Exception as prop_err:
                                logger.debug("Fallback proposal notice: %s", prop_err)
                                clean_final_text = "Clinical protocol analysis completed."
                    
                    if clean_final_text:
                        yield {"event": "delta", "data": clean_final_text}

                # Extract and emit any structured action cards
                all_cards = list(parser.action_cards)
                for source_text in (accumulated_turn_content, accumulated_reasoning_text):
                    for ac in re.findall(r'<action_card\s+type="([^"]+)"\s*>(.*?)</action_card>', source_text, re.DOTALL):
                        all_cards.append(f'<action_card type="{ac[0]}">{ac[1]}</action_card>')

                for card_text in all_cards:
                    m = re.search(r'<action_card\s+type="([^"]+)"\s*>(.*?)</action_card>', card_text, re.DOTALL | re.IGNORECASE)
                    if m:
                        card_type = m.group(1).strip()
                        card_body = m.group(2).strip()
                        match_key = f"{card_type}:{card_body}"
                        if match_key not in action_cards_emitted:
                            action_cards_emitted.add(match_key)
                            try:
                                card_data = json.loads(card_body)
                                from app.services.action_card_validator import ActionCardValidator
                                validated_payload, val_notes = ActionCardValidator.validate_and_sanitize_card(
                                    card_type=card_type,
                                    payload=card_data,
                                    current_stack=stack_list,
                                    biometrics=biometrics_dict,
                                )
                                yield {
                                    "event": "action_card",
                                    "data": {
                                        "type": card_type,
                                        "payload": validated_payload
                                    }
                                }
                            except Exception as card_err:
                                logger.debug("Action card parsing notice: %s", card_err)
                
                # If no action cards were emitted, but a protocol was generated or requested, guarantee action card emission
                if not action_cards_emitted and (protocol_goal or any("build" in str(m.get("content", "")).lower() or "protocol" in str(m.get("content", "")).lower() for m in messages if m.get("role") == "user")):
                    try:
                        active_goal = protocol_goal or "anabolic_physique"
                        proposal = StackIntentEngine.build_scratch_stack_proposal(
                            goal_id=active_goal,
                            biometrics=biometrics_dict,
                        )
                        card_payload = proposal.get("action_card", {})
                        if card_payload:
                            from app.services.action_card_validator import ActionCardValidator
                            validated_payload, val_notes = ActionCardValidator.validate_and_sanitize_card(
                                card_type="stack_diff",
                                payload=card_payload,
                                current_stack=stack_list,
                                biometrics=biometrics_dict,
                            )
                            yield {
                                "event": "action_card",
                                "data": {
                                    "type": "stack_diff",
                                    "payload": validated_payload
                                }
                            }
                    except Exception as ac_err:
                        logger.debug("Auto action card emission notice: %s", ac_err)
                break

        yield {"event": "done", "data": "[DONE]"}

    @classmethod
    async def chat_copilot_turn(
        cls,
        messages: List[Dict[str, Any]],
        persona: str = "architect",
        stack: Optional[List[str]] = None,
        biometrics: Optional[Dict[str, Any]] = None,
        protocol_goal: Optional[str] = None,
        protocol_objective: Optional[str] = None,
        max_exploration_steps: int = 10,
    ) -> Dict[str, Any]:
        """
        Non-streaming execution supporting dynamic ReAct graph problem solving.
        """
        stack_list = stack or []
        biometrics_dict = biometrics or {}
        system_prompt = cls.build_system_context(
            persona=persona,
            stack=stack_list,
            biometrics=biometrics_dict,
            protocol_goal=protocol_goal,
            protocol_objective=protocol_objective,
            messages=messages,
        )

        current_messages = list(messages)
        full_text = ""
        scratchpad_notes = []

        for step in range(1, max_exploration_steps + 1):
            turn_response = ""
            turn_reasoning = ""
            async for chunk in stream_local_llm_chat(messages=current_messages, system_prompt=system_prompt, max_tokens=16384):
                if chunk.get("type") == "content":
                    turn_response += str(chunk.get("data", ""))
                elif chunk.get("type") == "reasoning":
                    turn_reasoning += str(chunk.get("data", ""))

            if turn_reasoning:
                scratchpad_notes.append(turn_reasoning)

            scratchpad = cls.extract_scratchpad_from_text(turn_response)
            if scratchpad:
                scratchpad_notes.append(scratchpad)

            tool_call = cls.parse_tool_call_from_text(turn_response)
            if tool_call and step < max_exploration_steps:
                obs = cls.execute_tool(tool_call.get("name"), tool_call.get("arguments", {}))
                current_messages.append({"role": "assistant", "content": turn_response})
                current_messages.append({
                    "role": "user",
                    "content": f"<observation for='{tool_call.get('name')}'>\n{json.dumps(obs, indent=2)}\n</observation>\nContinue your analysis with this observation."
                })
                continue
            else:
                full_text = cls.clean_scratchpad_and_tools_from_text(turn_response) or turn_response
                if not full_text:
                    cleaned_r = cls.clean_scratchpad_and_tools_from_text(turn_reasoning)
                    if cleaned_r and ("**" in cleaned_r or "|" in cleaned_r or "###" in cleaned_r):
                        full_text = cleaned_r
                    elif protocol_goal:
                        proposal = StackIntentEngine.build_scratch_stack_proposal(
                            goal_id=protocol_goal,
                            biometrics=biometrics_dict,
                        )
                        full_text = cls.format_deterministic_protocol_markdown(proposal, persona)
                break

        return {
            "response_text": full_text or "Analysis completed.",
            "key_takeaways": [],
            "suggested_actions": [],
            "clinical_scratchpad": "\n\n".join(scratchpad_notes) if scratchpad_notes else None
        }


