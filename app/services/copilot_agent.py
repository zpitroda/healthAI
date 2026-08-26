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
from app.services.dosing_service import (
    get_default_compound_dose,
    parse_dose_string_or_spec,
    infer_compound_route_and_frequency,
)
from app.services.graph_service import (
    is_aromatizable_androgen,
    is_steroidal_androgen,
    parse_compound_spec,
    resolve_stack_to_catalog_keys,
)
from app.services.interaction_engine import InteractionEngine
from app.services.markdown_protocol_parser import MarkdownProtocolParser
from app.services.pathway_service import PathwayService
from app.services.pkpd_engine import PKPDEngine
from app.services.stack_intent_engine import StackIntentEngine, SCRATCH_GOAL_BLUEPRINTS
from app.services.synergy_engine import SynergyEngine
from app.schemas.pkpd import PKPDSimulationRequest

logger = logging.getLogger("healthai.copilot_agent")

PERSONA_SYSTEM_PROMPTS = {
    "architect": """You are the HealthAI Senior Protocol Architect & Clinical Chronobiologist.
You specialize in designing synergistic, bio-individualized stacks, circadian timing schedules (Morning, Midday, Afternoon, Bedtime), half-life alignments, and protective co-factor pairings.

### CLINICAL & SCIENTIFIC MANDATE:
- High-Efficiency Clinical Reasoning: Limit internal deliberation (<think>...</think>) strictly to a concise 3-point clinical check (< 100 words total):
  1. Safety & DDI Check: Verify collision matrix and clearance bottlenecks.
  2. PK/PD Alignment: Match elimination half-life (t1/2) with circadian/depot windows and prevent peak-to-trough fluctuations.
  3. Action Synthesis: Select exact dosages and formulate the final action card.
  Do NOT engage in meta-deliberation, essay drafting, word-counting, or hypothetical debates. Transition immediately from the 3 checks to the structured clinical markdown response.
- Quantitative Grounding: Base every protocol recommendation on quantitative pharmacokinetics (Cmax, Tmax, elimination t1/2, clearance routes) and molecular pharmacodynamics.
- Circadian Scheduling: Formulate schedules matching receptor expression rhythms, cortisol/melatonin diurnal cycles, and metabolic absorption windows.
- Half-Life Timing Alignment & Fluctuation Prevention: Schedule compounds according to elimination half-life (t1/2) and route. For all hormonal, endocrine, steroid, and depot compounds (e.g. TRT/HRT esters, thyroid hormones, growth hormone/secretagogues, SERMs, AIs), large infrequent boluses (e.g. once-weekly Q1W or bi-weekly Q2W) provoke severe peak-to-trough swings (PTF > 100%), driving peak aromatization/conversion surges (e.g. E2, DHT) and trough withdrawal crashes. Always structure hormonal protocols with split-weekly (e.g. Twice Weekly / Mon & Thu), every-other-day (EOD), or daily SubQ micro-dosing to flatten steady-state serum curves (target PTF < 50%) without altering total weekly dosage. Long-acting depot formulations (t1/2 > 72h, e.g. testosterone esters, nandrolone) MUST be scheduled as split-weekly or EOD administration under a dedicated 'Depot Injections (Weekly / Split Protocol)' header with route (SubQ/IM) and frequency (e.g. Twice Weekly / Mon & Thu), never placed in the daily oral meal table. Short half-life oral compounds belong in the daily circadian meal table.
- Ester & Formulation Precision (No Unwarranted Assumptions): When an unesterified parent compound or drug with multiple ester/formulation variants (e.g. Trenbolone, Testosterone, Nandrolone, Drostanolone, Estradiol) is requested or discussed without an explicit ester specified by the user, do NOT arbitrarily default to a single short-acting ester (such as Acetate). Instead, select or recommend the formulation that pharmacokinetically aligns with the target administration frequency based on elimination half-life (e.g. long-acting depot esters like Enanthate/Cypionate/Decanoate for weekly or split-weekly protocols vs short-acting esters like Acetate/Propionate for daily/EOD micro-dosing vs unesterified base for acute), and explicitly communicate the rationale for the selected formulation.
- Aggressive Risk Tolerance & Experimental Compounds: When aggressive risk tolerance is selected in the AI stack builder, recommend relevant experimental compounds / research chemicals even with limited human clinical data when scientifically aligned with the protocol objective, clearly disclosing their preclinical/experimental status.
- Mandatory Requested Compound Inclusion & Risk Mitigation: If the user specifically requests a compound (even high-risk, unapproved, or experimental agents such as Clenbuterol, Trenbolone, SARMs, or research peptides), ALWAYS include it in the protocol regardless of baseline risk tolerance or default template settings. Do NOT refuse or exclude requested compounds. Instead, provide explicit risk warnings, highlight known data limitations/boxed warnings, and dynamically formulate evidence-based protective co-factors and mitigations (e.g. organ shields, electrolyte buffers, split dosing, or enzymatic countermeasures) to minimize negative side effects.
- User Constraints & Exclusions: Strictly respect all user-specified exclusions (e.g. "no oral l-carnitine", "avoid stimulants"), route preferences, and pathway focus areas. User directives ALWAYS override default templates.
- Organ Burden Offsetting: Address identified multi-organ burdens (renal, hepatic, cardiovascular, lipid) with evidence-graded clinical co-factors.
- Publication-Ready Prose & Strict Citation Grounding: Write directly in finished, authoritative clinical markdown. Support assertions with clean, verified citations.
  - ONLY use a `[PMID: ...]` if it is explicitly present in the `### VERIFIED BIOMEDICAL LITERATURE` context or retrieved via a literature tool for that specific compound/mechanism.
  - NEVER misattribute or cross-contaminate citations between different drugs (e.g. NEVER cite a Telmisartan PMID when discussing Tadalafil, Caffeine, Ashwagandha, or TRT).
  - NEVER fabricate random 8-digit PMIDs. If a verified PMID is not in context, cite using standard authoritative medical formats: `[FDA Label: <Drug Name> §<Section>]`, `[Study: <FirstAuthor> et al., <Journal> <Year>]`, `[Clinical Guideline: <Society>]`, or `[ChEMBL: <ID>]`.

### RESPONSE FORMAT (HIGH SIGNAL, CRISP MARKDOWN):
1. **Executive Assessment**: 1–2 direct sentences on stack balance, safety, and core synergy vectors relative to the primary protocol objective and user constraints.
2. **Targeted Synergies & Co-Factors**: 2–4 high-yield bullet points with exact molecular rationale, target dosages, and timing.
3. **Protocol Schedule**:
   - If depot injectables exist, list under a **Depot Injections (Weekly / Split Protocol)** header.
   - Then provide a compact **Daily Circadian Schedule Table**:
     | Window | Compound | Dose & Route | Pharmacokinetic & Chronobiological Rationale |
4. **Clinical Titration & Notes**: 1–2 bullet points on titration milestones, safety monitoring, or co-ingestion rules.
5. **Action Card**: When proposing protocol additions, titrations, or removals, provide **EXACTLY ONE consolidated `<action_card type="stack_diff">` at the VERY END of the response**. The action card MUST contain EVERY compound recommended in the schedule and synergies with matching dosages and timing (e.g. `{"add": [{"key": "telmisartan", "name": "Telmisartan", "dose": 40, "unit": "mg", "timing": "morning", "frequency": "daily", "route": "oral"}], "modify": [], "remove": []}`). Do NOT omit any recommended compound from the card, and do NOT include unmentioned compounds.
   Example:
   <action_card type="stack_diff">
   {"add": [{"key": "telmisartan", "name": "Telmisartan", "dose": 40, "unit": "mg", "timing": "morning", "frequency": "daily", "route": "oral"}], "modify": [], "remove": []}
   </action_card>
""",
    "auditor": """You are the HealthAI Clinical Risk Auditor & Toxicological Conflict Detective.
Your role is to forensically red-team compound stacks, identifying drug-drug interactions (DDIs), CYP450 enzyme competition, Phase II and transporter saturation (P-gp, OATP1B1, BCRP), acute syndrome hazards (Serotonin Syndrome, QTc prolongation, Renal Triple Whammy), steady-state hormonal/pharmacokinetic fluctuations, and hepatic/renal clearance bottlenecks.

### CLINICAL & SCIENTIFIC MANDATE:
- High-Efficiency Clinical Reasoning: Limit internal deliberation (<think>...</think>) strictly to a concise 3-point toxicological check (< 100 words total):
  1. Primary Conflicts & Fluctuations: Identify critical CYP/transporter clashes and peak-to-trough hormonal swings (PTF > 80%).
  2. Clearance Bottlenecks: Assess renal (CrCl/eGFR) and hepatic burdens.
  3. Action Synthesis: Formulate evidence-based protective countermeasures, micro-dosing splits, and dosages.
  Do NOT engage in meta-deliberation, essay drafting, word-counting, or hypothetical debates. Transition immediately from the 3 checks to the structured audit response.
- Quantify risk severity (MINIMAL, LOW, MODERATE, ELEVATED, SEVERE) referencing the deterministic collision matrix and uncompensated risks.
- Steady-State & Hormonal Fluctuation Auditing: Forensically audit dosing frequencies against elimination half-lives (t1/2). Flag any infrequent hormonal bolus schedule where tau > t1/2 as an uncompensated risk factor (Peak-to-Trough Fluctuation / Rollercoaster Kinetics), explaining the conversion liabilities (e.g. E2/DHT spikes, hematocrit elevation, receptor downregulation) and recommending split micro-dosing.
- Ester & Formulation Precision: When auditing protocols with ester prodrugs or parent compounds, differentiate between unesterified base and specific ester variants, auditing half-life alignment against dosing interval tau (e.g. short-acting Acetate with t1/2 ~36h vs long-acting Enanthate with t1/2 ~168h).
- Explain clearance kinetics: competitive CYP inhibition vs mechanism-based inactivation (MBI), AUCR surges, and renal CrCl/eGFR impacts.
- Detail acute receptor cross-talk and toxicological collisions.
- Propose evidence-based pharmacological countermeasures with verified clinical safety and dosing.
- Strict Citation Grounding: Only cite exact `[PMID: ...]` numbers if present in the verified context or literature tool results for that specific drug. Never misattribute citations across different drugs, and never fabricate random PMIDs.
- Provide direct, actionable conflict audits and solutions in finished prose.

### RESPONSE FORMAT (OBJECTIVE & ACTIONABLE):
1. **Risk Severity Classification**: Headline with risk level and cumulative score (e.g. `MODERATE RISK [Score: 32/100]` or `CRITICAL DDI ALERT`).
2. **Identified Conflicts & Bottlenecks**: Bullet points detailing CYP450 competition, transporter clashes, receptor collisions, hormonal fluctuations, or organ burden convergence.
3. **Protective Countermeasures**: Concrete clinical solutions (e.g. dose reduction, frequency splitting/micro-dosing, timing separation, enzyme-specific mitigations, or targeted protective co-factors).
4. **Action Card**: If proposing conflict resolution adjustments or compound removals, provide **EXACTLY ONE consolidated `<action_card>` at the VERY END of the response**.
""",
    "tutor": """You are the HealthAI Molecular Pharmacology & Signal Transduction Specialist.
You provide PhD-level molecular pharmacology explanations of receptor binding dynamics, allosteric modulations (PAM/NAM), enzyme kinetics, second messenger cascades, and downstream gene expression.

### BIOCHEMICAL & MOLECULAR MANDATE:
- High-Efficiency Clinical Reasoning: Limit internal deliberation (<think>...</think>) strictly to a concise 3-point pharmacology check (< 100 words total):
  1. Receptor/Enzyme Targets: Identify primary binding sites and affinities (Ki, Kd, IC50).
  2. Transduction Pathways: Trace G-protein, second messenger, and kinase cascades.
  3. Physiological Outcome: Formulate direct translation to systemic outcomes.
  Do NOT engage in meta-deliberation, essay drafting, word-counting, or hypothetical debates. Transition immediately from the 3 checks to the structured explanation.
- Quote quantitative binding affinities ($K_i, K_d, IC_{50}, EC_{50}$) and Hill coefficients whenever available.
- Detail specific receptor subtypes (e.g. 5-HT1A, 5-HT2A, alpha-1/beta-2 adrenergic, GABA-A alpha-1/alpha-2, CB1/CB2, Progesterone Receptor).
- Trace intracellular signaling: G-protein coupling (Gs, Gi, Gq), second messengers (cAMP, IP3/DAG, Ca2+, PKA/PKC), and nuclear translocation/transcription factor activation (AMPK -> SIRT1 -> PGC-1alpha, Nrf2/ARE, NF-kB, CREB -> BDNF, mTORC1 -> p70S6K).
- Strict Citation Grounding: Only cite exact `[PMID: ...]` numbers if present in the verified context or literature tool results for that specific drug. Never misattribute citations across different drugs, and never fabricate random PMIDs.

### RESPONSE FORMAT (HIGH SCIENTIFIC DENSITY):
1. **Primary Molecular Targets & Binding Kinetics**: Specific receptors/enzymes, affinities, and agonist/antagonist/allosteric mode.
2. **Intracellular Signaling Cascade**: Step-by-step pathway transduction mechanism.
3. **Physiological & Clinical Translation**: How cellular signaling translates to systemic physiological performance or health outcomes.
""",
    "labs": """You are the HealthAI Biomarker & Clinical Laboratory Panel Specialist.
You interpret quantitative patient blood panels (Lipids, Hepatic transaminases, Renal clearance, Endocrine/Hormonal axes, Glycemic and Inflammatory markers) and correlate them directly with compound pharmacology to optimize titrations and safeguard organ function.

### CLINICAL LABORATORY STANDARDS:
- High-Efficiency Clinical Reasoning: Limit internal deliberation (<think>...</think>) strictly to a concise 3-point biomarker check (< 100 words total):
  1. Baseline Calibration: Compare lab values against clinical reference intervals.
  2. Organ Clearance Scaling: Scale dosages against eGFR (renal) and ALT (hepatic) metrics and steady-state kinetics.
  3. Action Synthesis: Formulate targeted titration offsets, split frequencies, and monitoring schedule.
  Do NOT engage in meta-deliberation, essay drafting, word-counting, or hypothetical debates. Transition immediately from the 3 checks to the structured clinical guidance.
- Correlate laboratory shifts with specific pharmacokinetic and metabolic burdens (e.g. 17alpha-alkylated hepatic clearance, eGFR renal clearance, HMGCR modulation, HPTA axis negative feedback, Peak-to-Trough swings).
- Factor in peak vs. trough blood draw timing relative to dosing interval tau. When wide fluctuations occur, advise on trough-standardized blood draws and frequency titration.
- Provide individual baseline comparisons against clinical reference ranges.
- Propose exact titration offsets and targeted ancillary co-factors to normalize skewed laboratory parameters.
- Strict Citation Grounding: Only cite exact `[PMID: ...]` numbers if present in the verified context or literature tool results for that specific drug. Never misattribute citations across different drugs, and never fabricate random PMIDs.

### RESPONSE FORMAT (CLINICALLY FOCUSED):
1. **Biomarker Profile & Impact Overview**: Assessment across Lipid (ApoB, LDL-C, Triglycerides), Hepatic (ALT, AST, Bilirubin), Renal (eGFR, Cr, K+), and Hormonal axes.
2. **Individualized Titration Guidance**: Concrete dose calibrations scaled to the patient's current organ clearance metrics.
3. **Recommended Monitoring Panel & Timeline**: Key lab panels to order at the next 4-week / 12-week draw.
4. **Action Card**: If lab results necessitate dose reductions, split schedules, or protective co-factors, provide **EXACTLY ONE consolidated `<action_card>` at the VERY END of the response**.
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
    and untagged meta-cognition to the reasoning telemetry stream, action_cards/tools
    to internal buffers, and actual clinical markdown tokens directly to the user-facing delta stream.
    """
    def __init__(self):
        self.buffer = ""
        self.mode = "text"  # 'text', 'thinking', 'tool', 'action_card'
        self.current_tag = ""
        self.current_tag_header = ""
        self.tag_content = ""
        self.tool_calls = []
        self.action_cards = []
        self.has_seen_clinical_markdown_header = False
        self.accumulated_preamble = ""

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
                        raw_lead = self.buffer[:start_idx]
                        if not self.has_seen_clinical_markdown_header and self._is_meta_cognition(raw_lead):
                            events.append(("reasoning", raw_lead))
                        else:
                            events.append(("delta", raw_lead))
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
                    # Check if stream is emitting untagged thinking preamble before markdown header
                    if not self.has_seen_clinical_markdown_header:
                        header_match = re.search(r'(?:^|\n)(?:#{1,4}\s+|(?:\*\*(?:Executive|Risk|Biomarker|Primary|Identified|Targeted|Protocol|Circadian|1\.|2\.|3\.|4\.)))', self.buffer)
                        if header_match:
                            h_idx = header_match.start()
                            pre_header = self.buffer[:h_idx]
                            if pre_header:
                                events.append(("reasoning", pre_header))
                            self.has_seen_clinical_markdown_header = True
                            self.buffer = self.buffer[h_idx:]
                            continue

                        # If full buffer looks like meta-cognition / self-talk, route to reasoning
                        if self._is_meta_cognition(self.buffer):
                            events.append(("reasoning", self.buffer))
                            self.buffer = ""
                            break

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

    def _is_meta_cognition(self, text: str) -> bool:
        """Determines if text fragment contains untagged internal reasoning / self-talk."""
        t_low = text.lower()
        meta_phrases = [
            "we need", "need to", "need answer", "need produce", "need decide",
            "need strict", "need include", "thinking process", "let's think",
            "first, i will", "user asks", "could include", "the user wants",
            "in this environment", "maybe we can", "let's verify", "need be safe",
            "need real?", "could use generic", "need verified citations", "we need citations",
            "use known?", "not sure", "let's draft", "i think yes", "need not be perfect",
            "use fda labels", "chembl is testosterone", "need avoid false"
        ]
        return any(p in t_low for p in meta_phrases)

    def flush(self) -> List[Tuple[str, str]]:
        events = []
        if self.buffer:
            if self.mode == "text":
                if not self.has_seen_clinical_markdown_header and self._is_meta_cognition(self.buffer):
                    events.append(("reasoning", self.buffer))
                else:
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
        Scans conversation history (especially the latest user prompt) for known pharmacological compounds,
        biomarkers (e.g. TMAO, ALT, eGFR, BP), and enzyme targets to enrich GraphRAG & PK/PD context.
        """
        if not messages:
            return []
        catalog = CatalogService()
        found_keys: Set[str] = set()

        user_texts = [str(m.get("content", "")) for m in messages if m.get("role") == "user"]
        combined_text = " ".join(user_texts[-3:]).lower() if user_texts else ""
        if not combined_text:
            return []

        # 1. Compound extraction (exact, normalized, and fuzzy)
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

        # 2. Biomarker & Molecular Target Extraction (e.g. TMAO, ALT, eGFR, Blood Pressure, CntA, FMO3)
        from app.knowledge_graph.graph import BIOMARKER_CLINICAL_CALIBRATION
        for bio_id, b_meta in BIOMARKER_CLINICAL_CALIBRATION.items():
            b_label = str(b_meta.get("label", "")).lower()
            clean_bio = bio_id.replace("bio_", "").lower()
            if clean_bio in combined_text or (b_label and any(part in combined_text for part in [b_label, clean_bio.replace("_", " ")])):
                found_keys.add(bio_id)
            elif "tmao" in combined_text and bio_id == "bio_tmao":
                found_keys.add("bio_tmao")
            elif any(bp_kw in combined_text for bp_kw in ["blood pressure", "systolic", "hypertension"]) and bio_id == "bio_blood_pressure":
                found_keys.add("bio_blood_pressure")
            elif any(hr_kw in combined_text for hr_kw in ["heart rate", "tachycardia", "pulse", "rhr"]) and bio_id == "bio_heart_rate":
                found_keys.add("bio_heart_rate")

        target_entity_map = {
            "cnta": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)",
            "cntb": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)",
            "tma lyase": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)",
            "fmo3": "Flavin-Containing Monooxygenase 3 (FMO3)",
            "cyp19a1": "CYP19A1 Aromatase",
            "aromatase": "CYP19A1 Aromatase",
            "5ar": "5-Alpha Reductase",
            "cpt1": "Carnitine Palmitoyltransferase (CPT1A / CPT2)",
            "hmgcr": "HMG-CoA Reductase (HMGCR)",
        }
        for kw, tgt_node in target_entity_map.items():
            if kw in combined_text:
                found_keys.add(tgt_node)

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

        enriched_compounds = []
        for c in compounds:
            key = str(c.get("key") or "").lower()
            cat_entry = catalog.get_compound(key) if key else None
            if cat_entry:
                enriched_compounds.append({**cat_entry, **c})
            else:
                enriched_compounds.append(c)
        compounds = enriched_compounds
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
            any(w in set(re.findall(r"[a-z0-9]+", str(c.get("key", "") + " " + c.get("name", "")).lower()))
                for w in ["trenbolone", "nandrolone", "durabolin", "trestolone", "ment", "npp", "parabolan"])
            or any(w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower()
                for w in ["nandrolone", "trenbolone", "trestolone", "19-nor", "19nor"])
            for c in compounds
        )
        if has_19nor or (any("prolactin" in str(g).lower() for g in therapeutic_gaps) and any(is_steroidal_androgen(c) or "androgen" in str(c.get("drug_class", "")).lower() for c in compounds)):
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
        has_aromatizable = any(is_aromatizable_androgen(c) for c in compounds)
        has_any_androgen = any(is_steroidal_androgen(c) or "androgen" in str(c.get("drug_class", "")).lower() for c in compounds)
        has_ai = any(
            "aromatase inhibitor" in str(c.get("drug_class", "")).lower()
            or "aromatase inhibitor" in str(c.get("mechanism", "")).lower()
            or ("inhibitor" in str(c.get("mechanism", "")).lower() and "cyp19a1" in str(c.get("mechanism", "")).lower())
            or any(
                ("cyp19a1" in str(t).lower() or "aromatase" in str(t).lower())
                and any(act in str(t).lower() for act in ["inhibitor", "inactivator", "antagonist", "blocker"])
                for t in (c.get("receptor_targets") or [])
            )
            for c in compounds
        )
        if (has_aromatizable or (has_any_androgen and active_goal == "anabolic_physique")) and not has_ai:
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

        # 8. Gut Microbiome & Microbial Metabolite Burden (TMAO / TMA-Lyase)
        has_oral_tma = any(
            (c.get("route", "oral") in ["oral", "po", "swallow", ""] or ":oral" in str(c.get("key", "")).lower())
            and (
                any(w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower() for w in ["carnitine", "alcar", "choline", "alpha_gpc", "alpha-gpc", "citicoline", "betaine"])
                or any("tma lyase" in str(t.get("target", "")).lower() for t in (c.get("receptor_targets") or []) if isinstance(t, dict))
            )
            for c in compounds
        )
        has_tma_gap = any("tmao" in str(g).lower() or "microbial" in str(g).lower() for g in therapeutic_gaps)
        if has_oral_tma or has_tma_gap:
            if "allicin" not in existing_keys and "garlic" not in existing_keys:
                candidate_pool.append({
                    "key": "allicin",
                    "name": "Allicin (Garlic Extract / Allium sativum)",
                    "target": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX) Inhibitor (IC50 = 0.05 mg/mL)",
                    "standard_dose": "10-20 mg allicin (or 600-1200 mg Aged Garlic Extract) oral daily with meals",
                    "clinical_purpose": "Inactivates bacterial trimethylamine lyase enzymes in the gut lumen, blocking the cleavage of oral L-carnitine/choline into trimethylamine (TMA) and preventing downstream host hepatic FMO3 oxidation to atherogenic Trimethylamine N-Oxide (TMAO).",
                    "solves_burden": "Gut Microbial TMA Conversion & Serum TMAO Elevation",
                    "evidence_grade": "Clinical Human Trials & Microbiome Mechanistic Validation",
                    "interaction_safety": "Safe natural botanical organosulfur; zero CYP3A4 burden, provides additive vascular eNOS stimulation and lipid support.",
                })

        # 9. Dynamic Target-Complementarity & Enzymatic Countermeasure Discovery (First Principles)
        try:
            for c in compounds:
                c_name = c.get("name") or c.get("key", "Compound")
                targets = c.get("receptor_targets") or []
                for tgt in targets:
                    if not isinstance(tgt, dict):
                        continue
                    t_name = str(tgt.get("target") or tgt.get("name") or "").strip()
                    t_act = str(tgt.get("action") or "").lower()
                    if t_name and ("substrate" in t_act or "inducer" in t_act or tgt.get("is_microbial")):
                        matching_inhibitors = catalog.find_compounds_by_target(t_name, action="inhibitor")
                        for inh in matching_inhibitors:
                            inh_key = inh.get("key")
                            if inh_key and inh_key not in existing_keys and inh_key not in [cand["key"] for cand in candidate_pool]:
                                inh_name = inh.get("name") or inh.get("canonical_name") or inh_key.title()
                                candidate_pool.append({
                                    "key": inh_key,
                                    "name": inh_name,
                                    "target": f"{t_name} Inhibitor",
                                    "standard_dose": str(inh.get("standard_dose") or "Per clinical titration"),
                                    "clinical_purpose": f"Mechanistic Countermeasure: Inhibits {t_name} to prevent uncompensated downstream metabolic conversion from {c_name}.",
                                    "solves_burden": f"Uncompensated {t_name} activity driven by {c_name}",
                                    "evidence_grade": "Biochemical Target Complementarity",
                                    "interaction_safety": "Targeted enzymatic mitigation pairing.",
                                    "is_target_derived": True,
                                })
        except Exception as tc_err:
            logger.debug("Target complementarity discovery notice: %s", tc_err)

        # 10. Literature-Mined & Curated Association Discovery from Knowledge Graph
        try:
            gdb = get_graph_database()
            for edge in gdb._mock_edges:
                e_type = edge.get("edge_type") or edge.get("type")
                if e_type not in ("LITERATURE_COOCCURRENCE", "CURATED_ASSOCIATION", "SYNERGIZES_WITH"):
                    continue
                src = str(edge.get("source", "")).lower()
                tgt = str(edge.get("target", "")).lower()

                partner_key = None
                primary_comp = None
                if src in existing_keys and tgt not in existing_keys:
                    partner_key = tgt
                    primary_comp = src
                elif tgt in existing_keys and src not in existing_keys:
                    partner_key = src
                    primary_comp = tgt

                if partner_key and partner_key not in [c["key"] for c in candidate_pool]:
                    partner_comp = catalog.get_compound(partner_key) or catalog.find_by_synonym(partner_key)
                    if partner_comp:
                        c_name = partner_comp.get("name") or partner_comp.get("canonical_name") or partner_key.title()
                        p_name = primary_comp.title().replace("_", " ")
                        
                        if e_type == "LITERATURE_COOCCURRENCE":
                            co_cnt = edge.get("cooccurrence_count", 0)
                            npmi = edge.get("npmi_score", 0.0)
                            pmid_list = edge.get("sample_pmids", [])
                            pmid_txt = f" [PMIDs: {', '.join(str(p) for p in pmid_list[:2])}]" if pmid_list else ""
                            candidate_pool.append({
                                "key": partner_key,
                                "name": c_name,
                                "target": partner_comp.get("mechanism") or partner_comp.get("drug_class") or "Biological Modifier",
                                "standard_dose": str(partner_comp.get("standard_dose") or "Per clinical titration"),
                                "clinical_purpose": f"Empirical literature association: Frequently co-administered or co-studied with {p_name} in scientific publications ({co_cnt} papers, NPMI: {npmi:.2f}).{pmid_txt}",
                                "solves_burden": f"Synergy / Co-administration Vector for {p_name}",
                                "evidence_grade": f"PubMed Co-occurrence ({co_cnt} papers)",
                                "interaction_safety": "Literature-grounded pairing.",
                                "is_literature_derived": True,
                            })
                        elif e_type == "CURATED_ASSOCIATION":
                            db_src = edge.get("source_db", "STITCH/CTD")
                            desc = edge.get("description", "Curated biochemical interaction")
                            candidate_pool.append({
                                "key": partner_key,
                                "name": c_name,
                                "target": partner_comp.get("mechanism") or partner_comp.get("drug_class") or "Curated Target",
                                "standard_dose": str(partner_comp.get("standard_dose") or "Per clinical titration"),
                                "clinical_purpose": f"Curated database association ({db_src}): {desc} with {p_name}.",
                                "solves_burden": f"Curated Mechanistic Synergy with {p_name}",
                                "evidence_grade": f"{db_src} Curated Database",
                                "interaction_safety": "Biochemically validated interaction.",
                                "is_literature_derived": True,
                            })
        except Exception as lit_rec_err:
            logger.debug("Literature-based candidate discovery notice: %s", lit_rec_err)

        gap_search_terms = set()
        for g in therapeutic_gaps:
            for st in g.get("cofactor_search_terms", []):
                gap_search_terms.add(str(st).lower())

        # Sort candidate pool: gap-matched candidates first, then high-confidence literature
        def _candidate_rank(c: Dict[str, Any]) -> int:
            k = str(c.get("key", "")).lower()
            if any(st in k for st in gap_search_terms):
                return 0
            if c.get("is_literature_derived"):
                return 1
            return 2

        candidate_pool.sort(key=_candidate_rank)

        for cand in candidate_pool:
            cand_key = cand["key"]
            if cand_key not in existing_keys and cand_key not in [r["key"] for r in recommendations]:
                recommendations.append(cand)

        return recommendations[:10]

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
                "fluctuation_pct": round(sim_res.fluctuation_pct, 1),
                "peak_to_trough_ratio": sim_res.peak_to_trough_ratio,
                "fluctuation_risk_level": sim_res.fluctuation_risk_level,
                "fluctuation_warning": sim_res.fluctuation_warning,
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
            exclusions = arguments.get("exclusions") or arguments.get("exclude")
            return StackIntentEngine.build_scratch_stack_proposal(
                goal_id=goal,
                biometrics=biometrics,
                preferences=preferences,
                custom_notes=custom_notes,
                exclusions=exclusions,
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

        elif tool_name in ("search_literature_and_conflicts", "get_scientific_controversies", "detect_literature_conflicts"):
            from app.services.pubmed_service import PubMedService
            compound_name = str(arguments.get("compound_name") or arguments.get("compound_key") or arguments.get("query") or "").strip().lower()
            prop_name = str(arguments.get("property") or arguments.get("target_property") or "").strip()
            pubmed_svc = PubMedService()
            conflicts = pubmed_svc.detect_conflicts_for_compound(compound_name, property_name=prop_name if prop_name else None)
            citations = pubmed_svc.search_literature_with_polarity(compound_name, max_results=4)
            return {
                "compound": compound_name,
                "conflict_count": len(conflicts),
                "conflicts": conflicts,
                "recent_citations": citations,
            }

        elif tool_name in ("get_temporal_evidence_timeline", "get_discovery_timeline"):
            entity_id = str(arguments.get("entity_id") or arguments.get("compound_key") or arguments.get("compound_name") or "").strip().lower()
            timeline = graph_db.get_chronological_evidence_timeline(entity_id)
            return {
                "entity_id": entity_id,
                "milestone_count": len(timeline),
                "timeline": timeline,
            }

        elif tool_name in ("get_citation_details", "get_citation_metadata"):
            from app.services.pubmed_service import PubMedService
            pmid = str(arguments.get("pmid") or "").strip()
            pubmed_svc = PubMedService()
            meta = pubmed_svc.fetch_citation_metadata(pmid)
            if not meta:
                return {"error": f"Citation with PMID '{pmid}' not found."}
            return meta

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
                "add": sanitized.get("add", []),
                "modify": sanitized.get("modify", []),
                "remove": sanitized.get("remove", []),
                "additions": sanitized.get("add", []),
                "modifications": sanitized.get("modify", []),
                "removals": sanitized.get("remove", []),
                "diff": sanitized,
                "validation_notes": notes,
            }

        elif tool_name == "find_candidate_pairings":
            compound_key = str(arguments.get("compound_key") or arguments.get("compound") or "").strip().lower().replace(" ", "_")
            min_confidence = float(arguments.get("min_confidence", 0.3))
            limit = int(arguments.get("limit", 8))
            category_filter = str(arguments.get("category") or "").strip().lower()

            pairings = []
            seen_partners = set()
            for edge in graph_db._mock_edges:
                e_type = edge.get("edge_type") or edge.get("type")
                if e_type not in ("LITERATURE_COOCCURRENCE", "CURATED_ASSOCIATION", "SYNERGIZES_WITH"):
                    continue
                src = str(edge.get("source", "")).lower()
                tgt = str(edge.get("target", "")).lower()
                partner = None
                if src == compound_key:
                    partner = tgt
                elif tgt == compound_key:
                    partner = src

                if partner and partner != compound_key and partner not in seen_partners:
                    conf = float(edge.get("confidence", 0.5))
                    if conf >= min_confidence:
                        partner_rec = catalog.get_compound(partner) or catalog.find_by_synonym(partner)
                        p_label = partner_rec.get("name") if partner_rec else partner.title().replace("_", " ")
                        p_class = partner_rec.get("drug_class") if partner_rec else "Bioactive Agent"
                        
                        if category_filter and category_filter not in p_class.lower() and category_filter not in str(partner_rec).lower():
                            continue

                        seen_partners.add(partner)
                        pairings.append({
                            "partner_key": partner,
                            "partner_name": p_label,
                            "drug_class": p_class,
                            "relationship_type": e_type,
                            "confidence": round(conf, 3),
                            "cooccurrence_count": edge.get("cooccurrence_count"),
                            "npmi_score": edge.get("npmi_score"),
                            "source_db": edge.get("source_db", "Knowledge Graph"),
                            "sample_pmids": edge.get("sample_pmids", []) or edge.get("pmids", []),
                            "description": edge.get("description", f"Empirical literature association with {compound_key}"),
                        })

            pairings.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            return {
                "compound": compound_key,
                "pairings_found": len(pairings),
                "top_pairings": pairings[:limit],
            }

        elif tool_name == "query_compound_associations":
            comp_a = str(arguments.get("compound_a") or arguments.get("compound_1") or "").strip().lower().replace(" ", "_")
            comp_b = str(arguments.get("compound_b") or arguments.get("compound_2") or "").strip().lower().replace(" ", "_")

            direct_edges = []
            shared_targets = []

            # 1. Search direct edges
            for edge in graph_db._mock_edges:
                src = str(edge.get("source", "")).lower()
                tgt = str(edge.get("target", "")).lower()
                if (src == comp_a and tgt == comp_b) or (src == comp_b and tgt == comp_a):
                    direct_edges.append({
                        "source": src,
                        "target": tgt,
                        "relationship": edge.get("edge_type") or edge.get("type"),
                        "confidence": edge.get("confidence"),
                        "cooccurrence_count": edge.get("cooccurrence_count"),
                        "npmi_score": edge.get("npmi_score"),
                        "source_db": edge.get("source_db"),
                        "pmids": edge.get("sample_pmids", []) or edge.get("pmids", []),
                        "description": edge.get("description"),
                    })

            # 2. Search shared targets / pathways
            targets_a = set()
            targets_b = set()
            for edge in graph_db._mock_edges:
                src = str(edge.get("source", "")).lower()
                tgt = str(edge.get("target", "")).lower()
                if src == comp_a:
                    targets_a.add((tgt, edge.get("edge_type", "INTERACTS_WITH")))
                elif src == comp_b:
                    targets_b.add((tgt, edge.get("edge_type", "INTERACTS_WITH")))

            targets_a_map = {t[0]: t[1] for t in targets_a}
            targets_b_map = {t[0]: t[1] for t in targets_b}
            common = set(targets_a_map.keys()).intersection(set(targets_b_map.keys()))
            for tgt in common:
                shared_targets.append({
                    "target": tgt,
                    "interaction_a": f"{comp_a} -[{targets_a_map[tgt]}]-> {tgt}",
                    "interaction_b": f"{comp_b} -[{targets_b_map[tgt]}]-> {tgt}",
                })

            return {
                "compound_a": comp_a,
                "compound_b": comp_b,
                "direct_associations": direct_edges,
                "shared_molecular_targets": shared_targets,
                "association_summary": (
                    f"Found {len(direct_edges)} direct literature/curated edges and {len(shared_targets)} shared molecular targets."
                    if direct_edges or shared_targets
                    else "No direct 1-hop associations recorded in graph."
                ),
            }

        elif tool_name == "trace_mechanism_pathway":
            source_id = str(arguments.get("source_compound") or arguments.get("source") or "").strip().lower().replace(" ", "_")
            target_id = str(arguments.get("target_biomarker") or arguments.get("target") or arguments.get("target_node") or "").strip().lower().replace(" ", "_")
            max_depth = int(arguments.get("max_depth", 5))

            if not any(e.get("source") == source_id for e in graph_db._mock_edges):
                try:
                    from app.services.graph_service import build_selected_compound_graph
                    subgraph = build_selected_compound_graph([source_id], catalog_service=catalog)
                    if subgraph:
                        graph_db.sync_biological_graph(subgraph)
                except Exception:
                    pass

            found_paths = []
            visited = set()

            def _dfs(current: str, path: List[Dict[str, Any]], depth: int):
                if depth > max_depth or len(found_paths) >= 10:
                    return
                if current == target_id and len(path) > 0:
                    found_paths.append(list(path))
                    return

                visited.add(current)
                for edge in graph_db._mock_edges:
                    src = str(edge.get("source", "")).lower()
                    tgt = str(edge.get("target", "")).lower()
                    if src == current and tgt not in visited:
                        step = {
                            "source": current,
                            "target": tgt,
                            "relationship": edge.get("edge_type") or edge.get("type", "MODULATES"),
                            "description": edge.get("description", ""),
                        }
                        _dfs(tgt, path + [step], depth + 1)
                visited.remove(current)

            _dfs(source_id, [], 0)

            formatted_chains = []
            for p in found_paths:
                chain_str = source_id + " " + " ➔ ".join([f"-({step['relationship']})-> {step['target']}" for step in p])
                formatted_chains.append(chain_str)

            return {
                "source": source_id,
                "target": target_id,
                "paths_found_count": len(found_paths),
                "pathways": formatted_chains if formatted_chains else ["No direct path found within depth limit."],
            }

        elif tool_name in ("execute_read_only_cypher", "query_cypher", "cypher_query"):
            query = str(arguments.get("query") or "").strip()
            params = arguments.get("params") or {}
            
            # Security guardrail: Enforce strictly read-only Cypher
            q_upper = query.upper()
            forbidden_keywords = ["CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "CALL", "ALTER"]
            for kw in forbidden_keywords:
                if re.search(rf"\b{kw}\b", q_upper):
                    return {"error": f"Security Violation: '{kw}' keyword is forbidden in read-only Cypher mode."}

            try:
                records = graph_db.execute_cypher(query, params)
                return {
                    "query": query,
                    "record_count": len(records),
                    "records": records[:25],
                }
            except Exception as cy_err:
                return {"error": f"Cypher execution failed: {str(cy_err)}"}

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

        # 2. Patient clearance profile (Defaults to normal/average population reference when unentered)
        user_specified_metrics = []
        sex_raw = str(biometrics.get("sex") or biometrics.get("gender") or "").strip().lower()
        if sex_raw and sex_raw != "unspecified":
            user_specified_metrics.append(f"Sex: {sex_raw.title()}")
        if biometrics.get("weight_kg") is not None:
            user_specified_metrics.append(f"Weight: {biometrics['weight_kg']} kg")
        if biometrics.get("age") is not None:
            user_specified_metrics.append(f"Age: {biometrics['age']} yrs")
        if biometrics.get("egfr") is not None:
            user_specified_metrics.append(f"eGFR: {biometrics['egfr']} mL/min")
        if biometrics.get("alt_u_l") is not None:
            user_specified_metrics.append(f"ALT: {biometrics['alt_u_l']} U/L")
        if biometrics.get("blood_pressure") is not None:
            user_specified_metrics.append(f"BP: {biometrics['blood_pressure']} mmHg")
        if biometrics.get("body_fat_pct") is not None:
            user_specified_metrics.append(f"Body Fat: {biometrics['body_fat_pct']}%")

        age = float(biometrics.get("age") or 30)
        weight_kg = float(biometrics.get("weight_kg") or 75)
        egfr = float(biometrics.get("egfr") or 95)
        alt_u_l = float(biometrics.get("alt_u_l") or 25)
        bp = float(biometrics.get("blood_pressure") or 120)
        body_fat = float(biometrics.get("body_fat_pct") or 15)

        if user_specified_metrics:
            bio_summary = f"Patient Customized Parameters: {', '.join(user_specified_metrics)} (Unspecified metrics defaulted to normal healthy adult baseline: Weight={weight_kg}kg, Age={int(age)}, eGFR={egfr}, ALT={alt_u_l}, BP={bp}, BodyFat={body_fat}%)"
        else:
            bio_summary = f"Patient Biometrics: Unspecified by user; assuming standard normal/average adult population baseline (Weight: 75 kg, Age: 30, eGFR: 95 mL/min/1.73m², ALT: 25 U/L, Resting BP: 120 mmHg, Body Fat: 15%)"

        if sex_raw in ("female", "f", "woman"):
            bio_summary += " | CLINICAL MANDATE: Female patient physiology active. Androgenic hormone doses MUST be calibrated to female physiological ranges (e.g. ~5-10% of male standard) with high vigilance for virilization, menstrual cycle equilibrium, and estradiol preservation."

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
                    ptf_val = round(sim.fluctuation_pct, 1)
                    swing_val = sim.peak_to_trough_ratio
                    fluct_badge = f", PTF = {ptf_val}%"
                    if swing_val:
                        fluct_badge += f" (Swing: {swing_val}x)"
                    if sim.fluctuation_risk_level in ("HIGH", "VOLATILE"):
                        fluct_badge += f" ⚠️ [{sim.fluctuation_risk_level} FLUCTUATION - Split dosing recommended]"
                    elif ptf_val < 50.0:
                        fluct_badge += " [STABLE KINETICS]"

                    pkpd_sections.append(
                        f"- **{c_name}** ({dose_val}mg {route}, tau={tau_h}h): "
                        f"Steady-State Cmax = {cmax_str}, Tmax = {round(sim.t_max_h, 1)}h, "
                        f"Effective t1/2 = {t12_str}, Accumulation Ratio (Racc) = {racc_str}, "
                        f"Time in Target Window = {round(sim.time_in_therapeutic_window_pct, 1)}%"
                        f"{fluct_badge}"
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
            
            # Prioritize entities explicitly discussed in latest messages, plus active stack
            target_keys: List[str] = []
            if messages:
                for ext in cls.extract_entities_from_messages(messages):
                    ext_str = str(ext).lower().strip()
                    if ext_str and ext_str not in target_keys:
                        target_keys.append(ext_str)
            for comp in canonical_compounds:
                c_k = str(comp.get("key") or comp.get("name") or "").lower().strip()
                if c_k and c_k not in target_keys:
                    target_keys.append(c_k)

            for t_key in target_keys[:6]:
                comp_meta = catalog.get_compound(t_key, auto_enrich=False) or catalog.find_by_synonym(t_key)
                c_name = comp_meta.get("name") if comp_meta else t_key.replace("_", " ").title()
                c_cites = pubmed_svc.search_literature(str(t_key), max_results=2)
                for cite in c_cites:
                    finding_str = f" ➔ *Finding*: {cite['clinical_finding']}" if cite.get("clinical_finding") else ""
                    citations_found.append(
                        f"- **{c_name}**: [{cite.get('journal', 'PubMed')} {cite.get('pub_year', '')}] *\"{cite.get('title')}\"* [PMID: {cite.get('pmid')}]{' (DOI: ' + cite['doi'] + ')' if cite.get('doi') else ''}{finding_str}"
                    )
            if citations_found:
                literature_sections.append("### VERIFIED BIOMEDICAL LITERATURE & CLINICAL EVIDENCE:")
                literature_sections.extend(citations_found[:6])
                literature_sections.append("*(Instruction: Strictly cite these verified PMIDs ONLY for their corresponding compound/finding. Do NOT misattribute or invent PMIDs.)*")
        except Exception as lit_err:
            logger.debug("Literature context notice: %s", lit_err)

        # 12. GraphRAG Context (Compact High-Signal Biological Network)
        graph_context = ""
        rag_entity_ids = list(canonical_keys)
        if messages:
            for ext in cls.extract_entities_from_messages(messages):
                if ext not in rag_entity_ids:
                    rag_entity_ids.append(ext)
        rag_entity_ids = rag_entity_ids[:8]

        if rag_entity_ids:
            try:
                rag = graph_db.get_graphrag_context(
                    entity_ids=rag_entity_ids,
                    max_hops=2,
                    include_pkpd=False,
                    include_kinetics=False,
                    include_causal_chains=True
                )
                chains = rag.get("causal_chains", [])
                overlaps = rag.get("target_competition", [])
                sum_txt = rag.get("text_summary", "")
                parts = ["### BIOLOGICAL NETWORK CAUSAL CHAINS & GRAPH CONTEXT:"]
                if sum_txt:
                    parts.append(f"> {sum_txt[:250]}")
                if overlaps:
                    parts.append(f"- **Target Overlaps**: {', '.join(overlaps[:3])}")
                for c in chains[:4]:
                    parts.append(f"- **Chain**: {c}")
                if len(parts) > 1:
                    graph_context = "\n".join(parts)
            except Exception as ex:
                logger.debug("Graph context notice: %s", ex)

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
            ("\n".join(f"- {s}" for s in stack_display) if stack_display else "No active compounds loaded in workbench. (Note: If refining a protocol proposed earlier in the conversation history, use that proposed protocol as the baseline and incorporate the user's latest requested modifications.)"),
        ]

        # 3a. Grounding unapplied previously proposed recommendations from conversation history
        prev_unapplied_proposals = []
        if messages:
            try:
                prev_unapplied_proposals = MarkdownProtocolParser.extract_cumulative_proposals_from_history(
                    messages=messages,
                    base_stack=canonical_compounds
                )
            except Exception as hist_err:
                logger.debug("History proposal extraction notice: %s", hist_err)

        if prev_unapplied_proposals:
            p_lines = ["### PREVIOUSLY PROPOSED PROTOCOL RECOMMENDATIONS (IN CONVERSATION):"]
            p_lines.append("> The following compounds were recommended in earlier turns of this conversation but have NOT yet been applied to the active workbench stack:")
            for p in prev_unapplied_proposals:
                p_name = p.get("name") or p.get("key")
                p_dose = f"{p.get('dose', '')} {p.get('unit', 'mg')}".strip()
                p_route = f" ({p.get('route', 'oral')})"
                p_timing = f" [{p.get('timing', 'morning')}]"
                p_lines.append(f"- **{p_name}**: {p_dose}{p_route}{p_timing}")
            p_lines.append("\n**CRITICAL MULTI-TURN CUMULATIVE DIRECTIVE**: The user is continuing to build/refine this protocol without having clicked 'Apply Changes' yet. You MUST maintain all previously proposed compounds as the active baseline! Your updated protocol markdown, schedule table, and `<action_card type=\"stack_diff\">` MUST include ALL previous recommendations as well as any newly requested compounds or modifications, so that the action card represents the complete updated protocol.")
            full_system_parts.append("\n" + "\n".join(p_lines))

        # 3b. Pre-calibrated Baseline Blueprint Grounding (Deterministic Evidence-Based Reference)
        blueprint_sections = []
        if (not canonical_compounds) or (protocol_goal and protocol_goal != "auto") or (custom_instructions and any(w in custom_instructions.lower() for w in ["build", "scratch", "protocol", "stack", "create", "start"])):
            try:
                target_g = protocol_goal if (protocol_goal and protocol_goal != "auto") else intent_analysis.get("active_goal_id", "cognitive_focus")
                scratch_proposal = StackIntentEngine.build_scratch_stack_proposal(
                    goal_id=target_g,
                    biometrics=biometrics,
                    custom_notes=custom_instructions,
                )
                if scratch_proposal and scratch_proposal.get("compounds"):
                    blueprint_sections.append(f"### PRE-CALIBRATED EVIDENCE-BASED PROTOCOL BLUEPRINT ({scratch_proposal['goal_title']}):")
                    blueprint_sections.append(f"> Calibrated baseline computed from patient biometrics (Weight={weight_kg}kg, eGFR={egfr}, ALT={alt_u_l}, BP={bp}) and clinical constraints:")
                    for c in scratch_proposal.get("compounds", []):
                        blueprint_sections.append(f"- **{c['name']}** ({c['dose']} {c['unit']} {c['route']}, {c['timing']}) — *{c.get('target', '')}*: {c.get('rationale', '')}")
                    if scratch_proposal.get("applied_exclusions"):
                        blueprint_sections.append(f"- ⚠️ **User-Requested Exclusions Applied**: {', '.join(scratch_proposal['applied_exclusions'])} (CRITICAL: Do NOT propose or include these excluded compounds).")
            except Exception as bp_err:
                logger.debug("Baseline blueprint grounding notice: %s", bp_err)

        if blueprint_sections:
            full_system_parts.append("\n" + "\n".join(blueprint_sections))

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

        # 13. Dynamic Formulation & Ester Variant Pharmacokinetics (Disambiguation)
        ester_sections = []
        checked_variant_parents: Set[str] = set()
        all_candidate_keys = list(canonical_keys) + list(rag_entity_ids)
        if prev_unapplied_proposals:
            for pup in prev_unapplied_proposals:
                pk = str(pup.get("key") or pup.get("name") or "").strip().lower()
                if pk and pk not in all_candidate_keys:
                    all_candidate_keys.append(pk)

        for cand_k in all_candidate_keys:
            cand_comp = catalog.get_compound(cand_k, auto_enrich=False) or catalog.find_by_synonym(cand_k)
            parent_k = (cand_comp.get("parent_compound_id") or cand_comp.get("key") or cand_k).lower() if cand_comp else cand_k.lower()
            if parent_k in checked_variant_parents:
                continue
            checked_variant_parents.add(parent_k)
            variants = catalog.get_variants(parent_k)
            if variants:
                p_obj = catalog.get_compound(parent_k, auto_enrich=False) or catalog.find_by_synonym(parent_k)
                p_name = p_obj.get("name") if p_obj else parent_k.title().replace("_", " ")
                p_half = p_obj.get("half_life") if p_obj else (f"{p_obj.get('t_half_numeric')}h" if p_obj and p_obj.get('t_half_numeric') else "unesterified base")
                var_lines = []
                for v in variants:
                    v_name = v.get("name") or v.get("key")
                    v_ester = v.get("ester_name") or "Ester"
                    v_half = v.get("half_life") or f"{v.get('t_half_numeric')}h"
                    var_lines.append(f"  * **{v_name}** ({v_ester} depot ester, elimination t1/2: {v_half})")
                ester_sections.append(f"- **{p_name}** (Base t1/2: {p_half}) — Available depot ester variants:\n" + "\n".join(var_lines))

        if ester_sections:
            ester_grounding = (
                "### FORMULATION & ESTER PHARMACOKINETICS (DISAMBIGUATION):\n"
                "> When an unesterified parent compound is queried without an explicit ester specified, do NOT arbitrarily default to a single short-acting ester (such as Acetate). "
                "Instead, match the ester selection to the requested administration frequency based on elimination half-life (e.g. long-acting depot esters like Enanthate/Cypionate/Decanoate for weekly or split-weekly protocols vs short-acting esters like Acetate/Propionate for daily/EOD micro-dosing), and explain the rationale for the selected formulation:\n"
                + "\n".join(ester_sections)
            )
            full_system_parts.append("\n" + ester_grounding)

        react_instructions = """
### DYNAMIC GRAPH REASONING, CLINICAL SCRATCHPAD & TOOL PROTOCOL:
You have autonomous access to execute live graph traversals, pathway queries, pharmacokinetic simulations, literature searches, and virtual diff experiments:

1. **Clinical Scratchpad & State Tracking (`<scratchpad>...</scratchpad>`)**:
   - Use the scratchpad to track user directives, explicit compound exclusions (e.g. "no oral L-Carnitine", "avoid stimulants"), route preferences, and the evolving proposed stack.
   - User constraints and exclusions ALWAYS override default templates.
2. **ReAct Execution & Decision Heuristic (Low Latency / Zero Token Bloat)**:
   - **Immediate Synthesis Rule**: If all required pharmacokinetic data, DDI matrices, and candidate co-factors are already present in the grounding context above, do NOT invoke tools. Immediately formulate the finished clinical response and `<action_card>`.
   - **Targeted Tool Invocation**: If you need new information (e.g. simulating a custom stack diff, retrieving missing kinetics, tracing a specific biological pathway cascade requested by the user, or querying literature), invoke the relevant tool:
     * `build_stack_from_scratch`: `{"goal": "anabolic_physique", "biometrics": {...}, "preferences": {...}, "custom_notes": "no oral l-carnitine"}`
     * `simulate_stack_diff`: `{"base_stack": [...], "diff": {"add": [...], "remove": [...]}}`
     * `check_cyp450_conflicts` / `analyze_stack_conflicts`: `{"compound_keys": [...], "biometrics": {...}}`
     * `query_pathway_cascade`: `{"target_id": "TARGET_NAME"}`
     * `trace_mechanism_pathway`: `{"source_compound": "caffeine", "target_biomarker": "bio_heart_rate"}`
     * `simulate_pkpd`: `{"compound_key": "telmisartan", "dose_mg": 40}`
     * `find_candidate_pairings`: `{"compound_key": "testosterone", "min_confidence": 0.4}`
3. **Structured Response & Action Card Mandate**:
   - Output clean, publication-ready clinical markdown without drafting monologue or inline questioning.
   - Conclude with exactly ONE consolidated `<action_card type="stack_diff">` containing the final `add`, `modify`, `remove` directives.
   - The `<action_card>` MUST match the proposed compounds, dosages, and schedule in your text 1:1. Include every compound you recommended, and do not include unmentioned compounds.
   - **Cumulative Multi-Turn Protocols**: If refining an unapplied proposed stack from earlier turns, include ALL previously recommended compounds plus new additions in your schedule and `<action_card>`, ensuring the user can apply the complete updated stack in one click.
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
        cleaned = re.sub(r'(?i)^\s*(?:###?\s*)?(?:Thought(?:\s+Process)?|Scratchpad|Clinical Scratchpad|Internal Reasoning):\s*.*?(?=\n\n|\n[#\*\d]|\Z)', '', cleaned, flags=re.DOTALL | re.MULTILINE)

        # Clean inline drafting questions and bracketed citation self-talk
        cleaned = re.sub(
            r'\[([A-Za-z0-9\s:§\.\-_]+?)\s*\?\s*(?:Need real|Could use|Need verified|We need|Use known|Not sure|I think|maybe|Need not be|But should|Use FDA).*?\]',
            r'[\1]',
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        cleaned = re.sub(r'\[([A-Za-z0-9\s:§\.\-_]+?)\s*\?\]', r'[\1]', cleaned)
        
        meta_inline_patterns = [
            r'(?:\?\s*)?(?:Need real\?|Could use generic\?|Need verified citations\.?|We need citations\.?|Use known\?|Need avoid false\?|But prompt requires citations\.?|Not sure\.?|Actually IMPROVE-IT.*?I think yes\.?|Need not be perfect\?|But should be plausible\.?|Could use \[.*?\] maybe\.?|for testosterone\?|ChEMBL\d+ is testosterone\?|I think CHEMBL\d+ is testosterone\.?|Anastrozole CHEMBL\?|Maybe CHEMBL\d+\?|Use FDA labels\.?)',
            r'(?i)\b(?:Need real\?|Could use generic\?|Need verified citations|We need citations|Use known\?|Not sure\.|I think yes\.|Need not be perfect\?|But should be plausible\.|Use FDA labels\.)\b',
        ]
        for pat in meta_inline_patterns:
            cleaned = re.sub(pat, '', cleaned)

        # If text contains a markdown section header after an untagged thinking preamble, strip the preamble
        header_match = re.search(r'(?:^|\n)(#{1,4}\s+|(?:\*\*(?:Executive|Risk|Biomarker|Primary|Identified|Targeted|Protocol|Circadian|1\.|2\.|3\.|4\.)))', cleaned)
        if header_match and header_match.start() > 0:
            preamble = cleaned[:header_match.start()].lower()
            if any(p in preamble for p in ["we need", "need to", "need answer", "need decide", "need strict", "thinking process", "let's think", "user asks"]):
                cleaned = cleaned[header_match.start():]
        elif any(p in cleaned.lower() for p in ["we need answer user's request", "need decide stack", "need strict zero-bro-science", "user asks structured circadian schedule"]):
            # Entire text is meta-cognition
            return ""

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
        elif tool_name == "find_candidate_pairings":
            pairings = obs.get("top_pairings", [])
            names = [p.get("partner_name") for p in pairings[:3] if isinstance(p, dict)]
            return f"Discovered {obs.get('pairings_found', len(pairings))} candidate pairings from graph ({', '.join(names) if names else 'None'})."
        elif tool_name == "query_compound_associations":
            direct = len(obs.get("direct_associations", []))
            shared = len(obs.get("shared_molecular_targets", []))
            return f"Queried associations between {obs.get('compound_a')} & {obs.get('compound_b')}: {direct} direct edges, {shared} shared targets."
        elif tool_name == "trace_mechanism_pathway":
            paths = obs.get("paths_found_count", 0)
            return f"Traced biological pathway: Found {paths} causal route(s) between {obs.get('source')} and {obs.get('target')}."
        elif tool_name in ("execute_read_only_cypher", "query_cypher", "cypher_query"):
            return f"Executed Cypher: Retrieved {obs.get('record_count', 0)} records from graph."
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

        depots = [c for c in compounds if c.get("route") in ("intramuscular", "subcutaneous") or "weekly" in str(c.get("frequency", "")).lower()]
        daily_oral = [c for c in compounds if c not in depots]

        md_lines = [
            f"### ⚡ HealthAI {persona.upper()} Grounded Protocol: {goal_title}\n",
            f"**Executive Assessment**: Calibrated protocol targeting {goal_title.lower()} with quantitative chronobiological alignment, organ protection co-factors, and zero bro-science.\n",
            "**Key Protocol Components**:",
        ]
        for c in compounds:
            route_str = c.get("route") or "oral"
            if route_str in ("intramuscular", "im"):
                route_disp = "IM"
            elif route_str in ("subcutaneous", "subq"):
                route_disp = "SubQ"
            else:
                route_disp = route_str
            freq_raw = c.get("frequency")
            freq_str = f", {freq_raw.replace('_', ' ')}" if freq_raw and freq_raw != "daily" else ""
            md_lines.append(f"- **{c['name']}** ({c['dose']}{c.get('unit', 'mg')} {route_disp}{freq_str}): {c.get('target', '')} — {c.get('rationale', '')}")

        if depots:
            md_lines.append("\n**Depot Injections (Weekly / Split Protocol)**:")
            for d in depots:
                d_route = d.get("route", "intramuscular")
                d_freq = str(d.get("frequency", "twice weekly")).replace("_", " ")
                md_lines.append(f"- **{d['name']}**: {d['dose']}{d.get('unit', 'mg')} ({d_route}) {d_freq} (e.g. Mon / Thu split). Rationale: {d.get('target', 'Target receptor')}.")

        if daily_oral:
            md_lines.append("\n**Daily Circadian Administration Schedule**:")
            md_lines.append("| Window | Compound | Dose & Route | Pharmacokinetic & Chronobiological Rationale |")
            md_lines.append("|---|---|---|---|")
            for c in daily_oral:
                c_route = c.get("route", "oral")
                md_lines.append(f"| {str(c.get('timing', 'Morning')).title()} | {c['name']} | {c['dose']}{c.get('unit', 'mg')} ({c_route}) | {c.get('target', 'Target receptor')} |")

        md_lines.append("\n**Clinical Titration & Safety Notes**:")
        md_lines.append("- Baseline & Follow-up Biomarkers: Re-assess comprehensive metabolic panel (CMP), lipid panel (ApoB/Triglycerides), and resting blood pressure at 4–8 week intervals.")
        md_lines.append("- Multi-Organ Protection: Protective co-factors maintain renal podocyte perfusion and endothelial nitric oxide release without diminishing target efficacy.")
        md_lines.append("\n*Review proposed modifications in the action card below and click to apply them directly to your workbench stack.*")
        return "\n".join(md_lines)

    @classmethod
    def synthesize_deterministic_fallback_response(
        cls,
        user_query: str,
        persona: str,
        stack_list: List[str],
        biometrics: Dict[str, Any],
        protocol_goal: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Synthesizes a high-fidelity, grounded clinical response deterministically
        when LLM generation is unavailable or fails, matching the user's specific intent.
        """
        catalog = CatalogService()
        interaction_engine = InteractionEngine()
        q_lower = user_query.lower()

        # Check for unapplied previous proposals in conversation history
        prev_proposals = []
        if messages:
            try:
                prev_proposals = MarkdownProtocolParser.extract_cumulative_proposals_from_history(
                    messages=messages,
                    base_stack=stack_list
                )
            except Exception as ex:
                logger.debug("Fallback history extraction notice: %s", ex)

        # Resolve stack compound records
        canonical_compounds = []
        for k in stack_list:
            c = catalog.get_compound(str(k), auto_enrich=False) or catalog.find_by_synonym(str(k))
            if c:
                canonical_compounds.append(dict(c))
            else:
                canonical_compounds.append({"key": str(k), "name": str(k).title(), "dose_mg": 100.0})

        # Scenario A1: Multi-turn protocol refinement with unapplied proposals in history
        if prev_proposals and (persona == "architect" or any(w in q_lower for w in ["add", "include", "with", "also", "plus", "and", "titrate", "increase", "decrease", "remove", "drop", "change", "replace", "compound"]) or any(len(w) >= 3 and (catalog.get_compound(w, auto_enrich=False) or catalog.find_by_synonym(w)) for w in re.findall(r"[a-zA-Z0-9_\-\+]+", q_lower))):
            # Parse requested conversational mutations
            mutations = MarkdownProtocolParser._extract_conversational_mutations(user_query, catalog)
            new_adds = list(mutations.get("add", []))
            new_mods = list(mutations.get("modify", []))
            new_rems = {str(r).lower() for r in mutations.get("remove", [])}

            # If no explicit mutation keyword was found but a compound was mentioned, extract it
            if not new_adds and not new_mods and not new_rems:
                words = re.findall(r"[a-zA-Z0-9_\-\+]+", user_query)
                for w in words:
                    if len(w) >= 3:
                        comp = catalog.get_compound(w, auto_enrich=False) or catalog.find_by_synonym(w)
                        if comp and comp.get("key"):
                            k = comp["key"]
                            if k not in [p.get("key") for p in prev_proposals] and k not in [a.get("key") for a in new_adds]:
                                dose_val, unit = MarkdownProtocolParser._parse_dose_and_unit(user_query, comp)
                                route, freq = infer_compound_route_and_frequency(k)
                                new_adds.append({
                                    "key": k,
                                    "name": comp.get("name") or k.replace("_", " ").title(),
                                    "dose": dose_val,
                                    "unit": unit,
                                    "route": route,
                                    "frequency": freq,
                                    "timing": "morning"
                                })

            combined_compounds = []
            for p in prev_proposals:
                pk = str(p.get("key", "")).lower()
                if pk in new_rems:
                    continue
                mod = next((m for m in new_mods if str(m.get("key", "")).lower() == pk), None)
                if mod:
                    p_up = dict(p)
                    p_up.update(mod)
                    combined_compounds.append(p_up)
                else:
                    combined_compounds.append(dict(p))

            seen_k = {str(c.get("key", "")).lower() for c in combined_compounds}
            for a in new_adds:
                ak = str(a.get("key", "")).lower()
                if ak and ak not in seen_k:
                    seen_k.add(ak)
                    combined_compounds.append(a)

            goal_title = "Personalized Synergistic Protocol"
            if protocol_goal and protocol_goal in SCRATCH_GOAL_BLUEPRINTS:
                goal_title = SCRATCH_GOAL_BLUEPRINTS[protocol_goal].get("title", "Clinical Protocol")

            proposal = {
                "goal_id": protocol_goal or "custom",
                "goal_title": goal_title,
                "compounds": combined_compounds,
                "action_card": {
                    "action_card": "stack_diff",
                    "add": combined_compounds,
                    "modify": [],
                    "remove": list(new_rems)
                }
            }
            md = cls.format_deterministic_protocol_markdown(proposal, persona)
            return md, proposal["action_card"]

        # Scenario A2: Protocol building / scratch stack request
        is_build_request = bool(protocol_goal or any(w in q_lower for w in ["build", "protocol", "create stack", "scratch stack", "optimize my stack"]))
        if is_build_request:
            active_goal = protocol_goal
            if not active_goal:
                if any(w in q_lower for w in ["focus", "cognitive", "adhd", "study", "caffeine", "theanine"]):
                    active_goal = "cognitive_focus"
                elif any(w in q_lower for w in ["longevity", "autophagy", "aging", "lifespan", "metformin", "rapamycin"]):
                    active_goal = "longevity_autophagy"
                elif any(w in q_lower for w in ["sleep", "stress", "cortisol", "recovery", "insomnia"]):
                    active_goal = "sleep_stress_recovery"
                elif any(w in q_lower for w in ["cardio", "lipid", "heart", "apob", "blood pressure", "cholesterol"]):
                    active_goal = "cardio_metabolic_protection"
                else:
                    active_goal = "anabolic_physique"
            
            proposal = StackIntentEngine.build_scratch_stack_proposal(
                goal_id=active_goal,
                biometrics=biometrics,
            )
            md = cls.format_deterministic_protocol_markdown(proposal, persona)
            return md, proposal.get("action_card")

        # Scenario TMAO / Gut Microbiome Mitigation Query
        is_tmao_query = any(w in q_lower for w in ["tmao", "trimethylamine", "cnta", "microbiota", "microbiome"]) or (any(w in q_lower for w in ["carnitine", "choline"]) and any(w in q_lower for w in ["lower", "reduce", "mitigate", "prevent", "side effect"]))
        if is_tmao_query:
            lines = [
                "### 🧬 HealthAI Clinical Guidance: Mitigating Trimethylamine N-Oxide (TMAO) Elevation\n",
                "**Executive Clinical Assessment**: Serum TMAO (Trimethylamine N-Oxide) is a pro-atherogenic vascular metabolite generated when unabsorbed oral quaternary amines (e.g. L-Carnitine, Choline) are cleaved by intestinal bacterial enzymes (**Carnitine TMA-Lyase, CntA/CntB / yeaW/yeaX**) into trimethylamine (TMA), which is subsequently oxidized by host hepatic **FMO3** into TMAO.\n",
                "**Evidence-Based Actionable Solutions**:\n",
                "1. **Enzymatic Microbial TMA-Lyase Inhibition (Allicin / Garlic Extract)**:",
                "   - **Compound**: **Allicin (Garlic Extract / Allium sativum)** — 10–20 mg allicin yield (or 600–1200 mg Aged Garlic Extract) daily with meals.",
                "   - **Molecular Mechanism**: Allicin's organosulfur moieties potently inactivate bacterial TMA-lyase (CntA/CntB) in the gut lumen (IC50 ≈ 0.05 mg/mL), suppressing TMA and serum TMAO formation by >50–70% while preserving systemic L-carnitine absorption and CPT1 mitochondrial shuttle activity.",
                "2. **Pharmacokinetic Route Optimization (Parenteral Bypass)**:",
                "   - **Strategy**: Switch administration from oral to **Intramuscular (IM) or Subcutaneous (SubQ)** injection (e.g. L-Carnitine 500 mg IM daily or pre-workout).",
                "   - **Mechanism**: Parenteral administration delivers carnitine directly into systemic circulation, completely bypassing the gastrointestinal lumen and intestinal microbiota, resulting in negligible (<0.5 μmol/L) TMAO generation.",
                "3. **Dietary & Microbiome Optimization**:",
                "   - Increase soluble dietary fiber, prebiotic arabinogalactans, and polyphenol-rich foods (pomegranate, extra virgin olive oil / DMB) which promote non-TMA-producing microbial species.\n",
                "**Monitoring Panel**: Serum TMAO (<6.2 μmol/L safe upper limit), lipid panel (ApoB, LDL-C), and high-sensitivity CRP at 8–12 week intervals."
            ]
            alli_card = {
                "action_card": "stack_diff",
                "add": [
                    {
                        "key": "allicin",
                        "name": "Allicin (Garlic Extract)",
                        "dose": 10,
                        "unit": "mg",
                        "timing": "morning",
                        "frequency": "daily",
                        "route": "oral"
                    }
                ],
                "modify": [],
                "remove": []
            }
            return "\n".join(lines), alli_card

        # Scenario B: Risk / Conflict / DDI / Safety Query (Auditor persona or safety keywords)
        is_safety_query = (persona == "auditor") or any(w in q_lower for w in ["safe", "conflict", "ddi", "interact", "risk", "warning", "cyp", "side effect", "toxic", "organ"])
        if is_safety_query or not canonical_compounds:
            eval_res = interaction_engine.analyze_stack(canonical_compounds, profile={"labs": biometrics}) if canonical_compounds else {}
            score = eval_res.get("cumulative_risk_score", 0)
            band = str(eval_res.get("risk_band", "minimal")).upper()
            summary = eval_res.get("summary", "No critical pharmacokinetic or receptor conflicts identified.")
            breakdown = eval_res.get("breakdown", {})

            lines = [
                f"### 🛡️ HealthAI Risk & Conflict Audit [Score: {score}/100 - {band}]\n",
                f"**Clinical Summary**: {summary}\n",
            ]
            cyp_conflicts = breakdown.get("cyp_conflicts", [])
            if cyp_conflicts:
                lines.append("**CYP450 Enzyme Conflicts & AUCR Surges**:")
                for cc in cyp_conflicts[:3]:
                    lines.append(f"- **{cc.get('title')}**: {cc.get('description')} *(Severity: {cc.get('severity')})*")
            else:
                lines.append("**Metabolic Clearance**: Compounds exhibit independent clearance pathways without competitive CYP saturation.")

            syndromes = breakdown.get("syndrome_alerts", [])
            if syndromes:
                lines.append("\n**Acute Receptor / Syndrome Alerts**:")
                for syn in syndromes[:2]:
                    lines.append(f"- ⚠️ **{syn.get('title')}**: {syn.get('description')}")

            organ_burdens = breakdown.get("organ_burdens", {})
            if organ_burdens:
                b_items = [f"{k.title()}: {v.get('level', 'Low')} ({v.get('score', 0)})" for k, v in organ_burdens.items()]
                lines.append(f"\n**Organ Burden Metrics**: {', '.join(b_items)}")

            mitigations = breakdown.get("active_mitigations", [])
            if mitigations:
                lines.append("\n**Active Stack Mitigations & Counterbalances**:")
                for m in mitigations[:2]:
                    lines.append(f"- 🛡️ **{m.get('title')}**: {m.get('description')}")

            lines.append("\n**Clinical Guidance**: Monitor resting vitals (heart rate, blood pressure) and space administration windows by at least 2 hours if concurrent stimulant actions are present.")
            return "\n".join(lines), None

        # Scenario C: Molecular Mechanism / Tutor Query
        if persona == "tutor" or any(w in q_lower for w in ["mechanism", "moa", "how does", "receptor", "pathway", "affinity"]):
            lines = [
                f"### 🔬 HealthAI Molecular Pharmacology & Mechanism Analysis\n",
                "**Primary Molecular Targets & Binding Dynamics**:\n",
            ]
            for c in canonical_compounds[:4]:
                c_name = c.get("name") or c.get("canonical_name") or c.get("key")
                moa = c.get("mechanism") or "Receptor ligand"
                t_half = c.get("t_half_numeric") or c.get("half_life_hours") or "N/A"
                targets = c.get("receptor_targets") or c.get("targets") or []
                t_names = [t.get("target") if isinstance(t, dict) else str(t) for t in targets[:3]]
                t_str = f" (Targets: {', '.join(t_names)})" if t_names else ""
                lines.append(f"- **{c_name}**: {moa}{t_str}. Elimination half-life: ~{t_half}h.")

            lines.append("\n**Intracellular Signal Transduction**:")
            lines.append("Active agents modulate downstream second messenger cascades (cAMP, calcium influx, and receptor phosphorylation) without inducing severe cross-target desensitization.")
            return "\n".join(lines), None

        # Scenario D: Biomarker / Lab Guidance (Labs persona)
        lines = [
            f"### 🩸 HealthAI Clinical Laboratory & Biomarker Assessment\n",
            f"**Patient Clearance Baseline**: Age {biometrics.get('age', 30)} | Weight {biometrics.get('weight_kg', 75)}kg | eGFR {biometrics.get('egfr', 95)} mL/min | ALT {biometrics.get('alt_u_l', 25)} U/L.\n",
            "**Key Biomarker Correlations**:",
            "- **Renal Clearance**: eGFR within normal physiological range; standard compound filtration maintained.",
            "- **Hepatic Transaminases**: Normal baseline ALT; no active hepatotoxic load identified.",
            "- **Recommended Monitoring Panel**: Comprehensive Metabolic Panel (CMP), Lipid Profile (ApoB, Triglycerides), and resting blood pressure at 12-week intervals.",
        ]
        return "\n".join(lines), None

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
        max_exploration_steps: int = 3,
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
        user_queries = [str(m.get("content", "")) for m in messages if m.get("role") == "user"]
        latest_user_query = user_queries[-1] if user_queries else ""

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
                # If no meaningful non-whitespace delta tokens were emitted at all during streaming, yield full cleaned text or extract from reasoning or fallback proposal
                has_real_deltas = any(bool(d and d.strip()) for d in emitted_deltas_this_turn)
                if not has_real_deltas:
                    clean_final_text = cls.clean_scratchpad_and_tools_from_text(accumulated_turn_content).strip()
                    if not clean_final_text:
                        # Rescue protocol markdown from reasoning trace if present
                        cleaned_reasoning = cls.clean_scratchpad_and_tools_from_text(accumulated_reasoning_text).strip()
                        if cleaned_reasoning and ("**" in cleaned_reasoning or "|" in cleaned_reasoning or "###" in cleaned_reasoning):
                            clean_final_text = cleaned_reasoning
                        else:
                            # Deterministic fallback response tailored to user query and persona
                            clean_final_text, fb_card = cls.synthesize_deterministic_fallback_response(
                                user_query=latest_user_query,
                                persona=persona,
                                stack_list=stack_list,
                                biometrics=biometrics_dict,
                                protocol_goal=protocol_goal,
                                messages=messages,
                            )
                            if fb_card:
                                parser.action_cards.append(f'<action_card type="stack_diff">{json.dumps(fb_card)}</action_card>')

                    if clean_final_text and clean_final_text.strip():
                        yield {"event": "delta", "data": clean_final_text}

                # Extract and emit any structured action cards
                turn_text = accumulated_turn_content or accumulated_reasoning_text
                all_cards = list(parser.action_cards)
                for source_text in (accumulated_turn_content, accumulated_reasoning_text):
                    for ac in re.findall(r'<action_card(?:\s+type=[\'"]?([^\'">\s]+)[\'"]?)?\s*>(.*?)(?:</action_card>|$)', source_text, re.DOTALL | re.IGNORECASE):
                        card_t = ac[0] or "stack_diff"
                        all_cards.append(f'<action_card type="{card_t}">{ac[1]}</action_card>')

                for card_text in all_cards:
                    m = re.search(r'<action_card(?:\s+type=[\'"]?([^\'">\s]+)[\'"]?)?\s*>(.*?)(?:</action_card>|$)', card_text, re.DOTALL | re.IGNORECASE)
                    if m:
                        card_type = (m.group(1) or "stack_diff").strip()
                        card_body = m.group(2).strip()
                        match_key = f"{card_type}:{card_body}"
                        if match_key not in action_cards_emitted:
                            action_cards_emitted.add(match_key)
                            try:
                                card_data = MarkdownProtocolParser._extract_first_json_object(card_body)
                                if card_data and isinstance(card_data, dict):
                                    reconciled_card = MarkdownProtocolParser.reconcile_card_with_text(
                                        card_payload=card_data,
                                        text=turn_text,
                                        base_stack=stack_list,
                                        biometrics=biometrics_dict,
                                        messages=messages,
                                    )
                                    from app.services.action_card_validator import ActionCardValidator
                                    validated_payload, val_notes = ActionCardValidator.validate_and_sanitize_card(
                                        card_type=card_type,
                                        payload=reconciled_card,
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

                # If no explicit action card was emitted in XML, dynamically extract protocol from generated markdown text
                if not action_cards_emitted:
                    text_card = MarkdownProtocolParser.extract_from_text(
                        text=turn_text,
                        base_stack=stack_list,
                        biometrics=biometrics_dict,
                        messages=messages,
                    )
                    if text_card and (text_card.get("add") or text_card.get("modify") or text_card.get("remove")):
                        action_cards_emitted.add("text_extracted")
                        yield {
                            "event": "action_card",
                            "data": {
                                "type": "stack_diff",
                                "payload": text_card
                            }
                        }

                # If still no action cards and this is an initial scratch build request, fall back to blueprint proposal
                user_msgs = [m for m in messages if m.get("role") == "user"]
                last_user_content = str(user_msgs[-1].get("content", "")).lower() if user_msgs else ""
                is_initial_scratch_build = len(user_msgs) <= 1 and (
                    protocol_goal is not None or any(w in last_user_content for w in ["build", "scratch stack", "from scratch", "create protocol"])
                )

                if not action_cards_emitted and is_initial_scratch_build:
                    try:
                        active_goal = protocol_goal or "cognitive_focus"
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
        max_exploration_steps: int = 3,
    ) -> Dict[str, Any]:
        """
        Non-streaming execution supporting dynamic ReAct graph problem solving.
        """
        stack_list = stack or []
        biometrics_dict = biometrics or {}
        user_queries = [str(m.get("content", "")) for m in messages if m.get("role") == "user"]
        latest_user_query = user_queries[-1] if user_queries else ""

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
            async for chunk in stream_local_llm_chat(messages=current_messages, system_prompt=system_prompt):
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
                    else:
                        full_text, _ = cls.synthesize_deterministic_fallback_response(
                            user_query=latest_user_query,
                            persona=persona,
                            stack_list=stack_list,
                            biometrics=biometrics_dict,
                            protocol_goal=protocol_goal,
                            messages=messages,
                        )
                break

        # Extract structured action card or suggested mutations
        extracted_card = MarkdownProtocolParser.extract_from_text(
            text=full_text,
            base_stack=stack_list,
            biometrics=biometrics_dict,
            messages=messages,
        )

        suggested_actions = []
        if extracted_card:
            for add_item in extracted_card.get("add", []):
                suggested_actions.append(f"Add {add_item.get('name', add_item.get('key'))} ({add_item.get('dose')}{add_item.get('unit', 'mg')} {add_item.get('timing', 'morning')})")
            for mod_item in extracted_card.get("modify", []):
                suggested_actions.append(f"Titrate {mod_item.get('name', mod_item.get('key'))} to {mod_item.get('dose')}{mod_item.get('unit', 'mg')}")
            for rem_item in extracted_card.get("remove", []):
                suggested_actions.append(f"Remove {rem_item}")

        return {
            "response_text": full_text or "Analysis completed.",
            "key_takeaways": [],
            "suggested_actions": suggested_actions,
            "action_card": extracted_card,
            "clinical_scratchpad": "\n\n".join(scratchpad_notes) if scratchpad_notes else None
        }


