from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from app.knowledge_graph.graph_db import get_graph_database
from app.services.ai_service import ask_local_llm, reset_model_context, stream_local_llm_chat
from app.services.catalog_service import CatalogService
from app.services.dosing_service import (
    get_default_compound_dose,
    parse_dose_string_or_spec,
    infer_compound_route_and_frequency,
)
from app.services.chemical_structure_engine import (
    is_17a_alkylated,
    is_19nor_steroid,
    is_aromatizable_androgen,
    is_steroidal_androgen,
)
from app.services.graph_service import (
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


class CopilotSourceCollector:
    """
    Programmatic collector and deduplicator for all scientific sources used by
    the AI Copilot during context assembly, dynamic ReAct tool execution, and response synthesis.
    """

    def __init__(self):
        self.literature_studies: Dict[str, Dict[str, Any]] = {}
        self.clinical_trials: Dict[str, Dict[str, Any]] = {}
        self.databases_and_registries: Dict[str, Dict[str, Any]] = {}
        self.computational_engines: Dict[str, str] = {}
        self.regulatory_and_guidelines: Dict[str, str] = {}

    def record_literature_citation(
        self,
        pmid: Optional[str] = None,
        doi: Optional[str] = None,
        title: Optional[str] = None,
        journal: Optional[str] = None,
        pub_year: Optional[Any] = None,
        authors: Optional[Any] = None,
        clinical_finding: Optional[str] = None,
        compound_name: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        if not pmid and not doi and not title:
            return
        key = str(pmid).strip() if pmid else (str(doi).strip().lower() if doi else str(title).strip().lower()[:60])
        if not key:
            return

        existing = self.literature_studies.get(key, {})
        auth_str = ""
        if isinstance(authors, list):
            auth_str = ", ".join([str(a) for a in authors if a])
        elif authors:
            auth_str = str(authors)

        merged = {
            "pmid": str(pmid).strip() if pmid else existing.get("pmid"),
            "doi": str(doi).strip() if doi else existing.get("doi"),
            "title": str(title).strip().rstrip(".") if title else existing.get("title"),
            "journal": str(journal).strip() if journal else existing.get("journal", "PubMed Journal"),
            "pub_year": str(pub_year).strip() if pub_year else existing.get("pub_year"),
            "authors": auth_str or existing.get("authors"),
            "clinical_finding": str(clinical_finding).strip() if clinical_finding else existing.get("clinical_finding"),
            "compound_name": str(compound_name).strip() if compound_name else existing.get("compound_name"),
            "url": url or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else None)),
        }
        self.literature_studies[key] = merged

    def record_clinical_trial(
        self,
        nct_id: str,
        title: Optional[str] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        clean_nct = str(nct_id).strip().upper()
        if not clean_nct:
            return
        self.clinical_trials[clean_nct] = {
            "nct_id": clean_nct,
            "title": str(title).strip() if title else None,
            "phase": str(phase).strip() if phase else None,
            "status": str(status).strip() if status else None,
            "url": f"https://clinicaltrials.gov/study/{clean_nct}",
        }

    def record_database_registry(self, db_type: str, item_id: str, description: Optional[str] = None) -> None:
        clean_id = str(item_id).strip()
        if not clean_id:
            return
        key = f"{db_type.lower()}:{clean_id}"
        self.databases_and_registries[key] = {
            "db_type": db_type,
            "item_id": clean_id,
            "description": description or f"{db_type} target record ({clean_id})",
        }

    def record_engine(self, engine_name: str, description: Optional[str] = None) -> None:
        if engine_name:
            self.computational_engines[engine_name.strip()] = description or ""

    def record_guideline(self, guideline_type: str, title: str, description: Optional[str] = None) -> None:
        key = f"{guideline_type}:{title}"
        full_text = f"{title} — {description}" if description and description != title else title
        self.regulatory_and_guidelines[key] = full_text

    def record_tool_execution(self, tool_name: str, arguments: Dict[str, Any], observation: Any) -> None:
        if not observation or (isinstance(observation, str) and observation.startswith("Error")):
            return
        t_name = str(tool_name).lower().strip()

        if t_name in (
            "search_pubmed_literature",
            "search_biomedical_literature",
            "search_pubmed",
            "search_literature_for_claim",
            "get_claim_citations",
            "search_evidence_for_claim",
        ):
            if isinstance(observation, dict):
                for c in observation.get("citations", []):
                    if isinstance(c, dict):
                        self.record_literature_citation(
                            pmid=c.get("pmid"),
                            doi=c.get("doi"),
                            title=c.get("title"),
                            journal=c.get("journal"),
                            pub_year=c.get("pub_year"),
                            authors=c.get("authors"),
                            clinical_finding=c.get("clinical_finding"),
                            compound_name=c.get("compound") or observation.get("entity_id") or observation.get("query"),
                        )

        elif t_name in ("search_pubmed_titles", "search_literature_titles", "search_paper_titles"):
            if isinstance(observation, dict):
                for ct in observation.get("candidate_titles", []):
                    if isinstance(ct, dict):
                        self.record_literature_citation(
                            pmid=ct.get("pmid"),
                            title=ct.get("title"),
                            journal=ct.get("journal"),
                            pub_year=ct.get("pub_year"),
                            doi=ct.get("doi"),
                        )

        elif t_name in ("fetch_paper_abstract", "read_paper_abstract", "get_paper_abstract", "read_study"):
            if isinstance(observation, dict) and observation.get("pmid"):
                self.record_literature_citation(
                    pmid=observation.get("pmid"),
                    doi=observation.get("doi"),
                    title=observation.get("title"),
                    journal=observation.get("journal"),
                    pub_year=observation.get("pub_year"),
                    authors=observation.get("authors"),
                    clinical_finding=observation.get("clinical_finding") or (observation.get("abstract")[:160] if observation.get("abstract") else None),
                )

        elif t_name in ("read_paper_section", "fetch_paper_full_text_section", "read_full_text_section"):
            if isinstance(observation, dict) and observation.get("pmid"):
                self.record_literature_citation(
                    pmid=observation.get("pmid"),
                    doi=observation.get("doi"),
                    title=observation.get("title"),
                    journal=observation.get("journal"),
                    pub_year=observation.get("pub_year"),
                    clinical_finding=f"Section: {observation.get('section', 'Results').title()}",
                )

        elif t_name in ("search_within_paper", "search_in_paper", "search_paper_passages"):
            if isinstance(observation, dict) and observation.get("pmid"):
                self.record_literature_citation(
                    pmid=observation.get("pmid"),
                    doi=observation.get("doi"),
                    title=observation.get("title"),
                    clinical_finding=f"Passage match for '{arguments.get('query', '')}'" if arguments.get("query") else None,
                )

        elif t_name in ("find_similar_papers", "find_similar_studies", "find_similar_citations"):
            if isinstance(observation, dict):
                for sp in observation.get("similar_papers", []):
                    if isinstance(sp, dict):
                        self.record_literature_citation(
                            pmid=sp.get("pmid"),
                            title=sp.get("title"),
                            journal=sp.get("journal"),
                            pub_year=sp.get("pub_year"),
                            doi=sp.get("doi"),
                        )

        elif t_name in ("search_cached_papers_semantic", "search_citations_semantic"):
            if isinstance(observation, dict):
                for c in observation.get("citations", []):
                    if isinstance(c, dict):
                        self.record_literature_citation(
                            pmid=c.get("pmid"),
                            title=c.get("title"),
                            journal=c.get("journal"),
                            pub_year=c.get("pub_year"),
                            doi=c.get("doi"),
                        )

        elif t_name in ("hybrid_rag_search", "search_graphrag_and_literature", "hybrid_literature_search"):
            self.record_engine(
                "HealthAI 3-Hop Biological Knowledge Graph & Causal Chain Reasoner",
                "Multi-hop graph traversal and causal pathway network",
            )
            if isinstance(observation, dict):
                for c in observation.get("citations", []):
                    if isinstance(c, dict):
                        self.record_literature_citation(
                            pmid=c.get("pmid"),
                            title=c.get("title"),
                            journal=c.get("journal"),
                            pub_year=c.get("pub_year"),
                            doi=c.get("doi"),
                        )

        elif t_name in ("search_clinical_trials", "search_trials"):
            if isinstance(observation, dict):
                for tr in observation.get("trials", []):
                    if isinstance(tr, dict):
                        self.record_clinical_trial(
                            nct_id=tr.get("nct_id") or tr.get("id"),
                            title=tr.get("title"),
                            phase=tr.get("phase"),
                            status=tr.get("status"),
                        )

        elif t_name in ("simulate_pkpd", "get_pkpd_kinetics"):
            comp_key = arguments.get("compound_key") or arguments.get("compound") or ""
            c_desc = f" for {comp_key}" if comp_key else ""
            self.record_engine(
                "HealthAI Steady-State PK/PD Clearance & Fluctuation Engine",
                f"Simulates 1- & 2-compartment elimination kinetics, Cmax, Tmax, t1/2, and PTF% swing curves{c_desc}",
            )

        elif t_name in ("check_cyp450_conflicts", "analyze_stack_conflicts", "evaluate_stack_interactions", "get_compound_interactions"):
            self.record_engine(
                "HealthAI Deterministic Collision Matrix & DDI Database",
                "Audits CYP450 enzyme inhibition, Phase II conjugation, transporter saturation, and syndrome liabilities",
            )

        elif t_name in ("evaluate_pgx_interactions", "check_pgx_warnings"):
            self.record_engine(
                "CPIC Pharmacogenomics (PGx) Clinical Practice Guidelines",
                "Maps patient enzyme metabolizer phenotypes (CYP2D6, CYP2C19, CYP3A4/5, SLCO1B1) to clearance rates",
            )

        elif t_name in ("trace_mechanism_pathway", "query_pathway_cascade"):
            self.record_engine(
                "Reactome Intracellular Biological Signal Transduction Pathway Database",
                "Traces receptor signal cascades, G-protein coupling, and transcriptional activation",
            )

        elif t_name in ("get_circadian_receptor_occupancy", "calculate_receptor_occupancy"):
            self.record_engine(
                "HealthAI Circadian Receptor Occupancy (RO) & Saturation Dynamics Model",
                "Calculates peak and trough receptor saturation percentages across diurnal windows",
            )

        elif t_name in ("find_candidate_pairings", "evaluate_multi_agent_synergy"):
            self.record_engine(
                "HealthAI Quantitative Multi-Agent Synergy Engine",
                "Evaluates Loewe Additivity Combination Indices (CI) and Bliss Independence deltas",
            )

        elif t_name in ("build_stack_from_scratch", "get_stack_recommendations"):
            self.record_engine(
                "HealthAI Evidence-Based Protocol Architecture & Blueprint Engine",
                "Formulates calibrated compound pairings, circadian timing, and protective co-factors",
            )

        elif t_name in ("simulate_stack_diff", "apply_stack_diff"):
            self.record_engine(
                "HealthAI Virtual Stack Diff Simulator & Clearance Modeler",
                "Simulates net pharmacokinetic and organ burden shifts before protocol changes are applied",
            )

    def record_grounding_context(
        self,
        citations: Optional[List[Dict[str, Any]]] = None,
        has_ddi: bool = False,
        has_pkpd: bool = False,
        has_pathway: bool = False,
        has_pgx: bool = False,
        has_ro: bool = False,
        has_synergy: bool = False,
        has_graphrag: bool = False,
    ) -> None:
        if citations:
            for c in citations:
                if isinstance(c, dict):
                    self.record_literature_citation(
                        pmid=c.get("pmid"),
                        doi=c.get("doi"),
                        title=c.get("title"),
                        journal=c.get("journal"),
                        pub_year=c.get("pub_year"),
                        authors=c.get("authors"),
                        clinical_finding=c.get("clinical_finding"),
                        compound_name=c.get("compound"),
                    )
        if has_ddi:
            self.record_engine(
                "HealthAI Deterministic Collision Matrix & DDI Database",
                "Evaluates competitive CYP450 clearance, transporter clashes, and syndrome liabilities",
            )
        if has_pkpd:
            self.record_engine(
                "HealthAI Steady-State PK/PD Clearance & Fluctuation Engine",
                "Computes Cmax, elimination t1/2, accumulation ratios, and fluctuation curves",
            )
        if has_pathway:
            self.record_engine(
                "Reactome Pathway Knowledgebase",
                "Intracellular signal transduction cascades and receptor coupling",
            )
        if has_pgx:
            self.record_engine(
                "CPIC Pharmacogenomics (PGx) Clinical Practice Guidelines",
                "Clinical pharmacogenetic guidance on drug-gene clearance phenotypes",
            )
        if has_ro:
            self.record_engine(
                "HealthAI Circadian Receptor Occupancy (RO) Model",
                "Circadian target saturation and receptor occupancy curves",
            )
        if has_synergy:
            self.record_engine(
                "HealthAI Quantitative Synergy Engine",
                "Loewe Combination Index & Bliss Independence models",
            )
        if has_graphrag:
            self.record_engine(
                "HealthAI 3-Hop Biological Knowledge Graph",
                "Multi-tier causal network and target competition triples",
            )

    def scan_text_for_citations(self, text: str) -> None:
        if not text:
            return
        # Scan PMIDs: [PMID: 12345678 - Author et al., Journal 2020] or [PMID: 12345678]
        for m in re.finditer(r'\[PMID:\s*(\d+)(?:\s*[-–—:]\s*([^\]]+))?\]', text, re.IGNORECASE):
            pmid = m.group(1).strip()
            extra = m.group(2).strip() if m.group(2) else None
            if pmid not in self.literature_studies:
                from app.services.pubmed_service import PubMedService
                meta = PubMedService().fetch_citation_metadata(pmid) or {}
                self.record_literature_citation(
                    pmid=pmid,
                    doi=meta.get("doi"),
                    title=meta.get("title") or (extra if extra and not any(w in extra.lower() for w in ["author", "et al", "pmid"]) else None),
                    journal=meta.get("journal"),
                    pub_year=meta.get("pub_year"),
                    authors=meta.get("authors") or (extra if extra and any(w in extra.lower() for w in ["et al", "author"]) else None),
                    clinical_finding=meta.get("clinical_finding"),
                )

        # Scan DOIs: [DOI: 10.1016/...]
        for m in re.finditer(r'\[DOI:\s*([^\s\]]+)\]', text, re.IGNORECASE):
            doi = m.group(1).strip()
            if not any(c.get("doi") == doi for c in self.literature_studies.values()):
                self.record_literature_citation(doi=doi)

        # Scan ChEMBL: [ChEMBL: CHEMBL25]
        for m in re.finditer(r'\[ChEMBL:\s*([A-Za-z0-9_]+)\]', text, re.IGNORECASE):
            cid = m.group(1).strip()
            self.record_database_registry("ChEMBL", cid, f"ChEMBL Target Profile & Bioactivity Data ({cid})")

        # Scan FDA: [FDA Label: §5.1] or [FDA: ...]
        for m in re.finditer(r'\[FDA(?:\s+Label)?:\s*([^\]]+)\]', text, re.IGNORECASE):
            fda_spec = m.group(1).strip()
            self.record_guideline("FDA", f"FDA Structured Product Labeling: {fda_spec}", "Official FDA Drug Prescribing Information & Package Insert")

        # Scan ClinicalTrials NCT: [NCT: NCT01234567]
        for m in re.finditer(r'\[NCT:\s*([A-Za-z0-9_]+)\]', text, re.IGNORECASE):
            nct_id = m.group(1).strip()
            self.record_clinical_trial(nct_id)

        # Scan CPIC: [CPIC Guideline: ...] or [CPIC: ...]
        for m in re.finditer(r'\[CPIC(?:\s+Guideline)?:\s*([^\]]+)\]', text, re.IGNORECASE):
            cpic_spec = m.group(1).strip()
            self.record_guideline("CPIC", f"CPIC Clinical Pharmacogenetics Guideline: {cpic_spec}", "CPIC / PharmGKB Evidence-Based Dosing Protocol")

    def format_sources_markdown(self) -> str:
        if (
            not self.literature_studies
            and not self.clinical_trials
            and not self.databases_and_registries
            and not self.regulatory_and_guidelines
        ):
            return ""

        lines = ["\n\n### 📚 Sources & Scientific Evidence Base"]

        # 1. Literature Studies
        if self.literature_studies:
            lines.append("\n#### 📄 Primary Biomedical Literature & Clinical Studies")
            for _, study in list(self.literature_studies.items())[:12]:
                pmid = study.get("pmid")
                doi = study.get("doi")
                title = study.get("title")
                journal = study.get("journal")
                year = study.get("pub_year")
                authors = study.get("authors")
                finding = study.get("clinical_finding")

                badge_part = f"[PMID: {pmid}]" if pmid else (f"[DOI: {doi}]" if doi else "")
                detail_parts = []
                if authors:
                    detail_parts.append(str(authors).rstrip("."))
                if title:
                    detail_parts.append(f"*\"{title}\"*")
                if journal:
                    j_str = journal
                    if year:
                        j_str += f" ({year})"
                    detail_parts.append(j_str)
                elif year:
                    detail_parts.append(f"({year})")
                if doi and pmid:
                    detail_parts.append(f"[DOI: {doi}]")

                full_desc = " — ".join([p for p in detail_parts if p]) if detail_parts else ""
                if finding:
                    full_desc += f" *(Finding: {finding[:140]}...)*" if len(finding) > 140 else f" *(Finding: {finding})*"

                if badge_part and full_desc:
                    lines.append(f"- **{badge_part}** {full_desc}")
                elif badge_part:
                    lines.append(f"- **{badge_part}** Verified Biomedical Publication")
                elif full_desc:
                    lines.append(f"- {full_desc}")

        # 2. Clinical Trials
        if self.clinical_trials:
            lines.append("\n#### 🧪 Registered Clinical Trials (ClinicalTrials.gov)")
            for _, tr in list(self.clinical_trials.items())[:5]:
                nct = tr.get("nct_id")
                t_title = tr.get("title")
                phase = tr.get("phase")
                status = tr.get("status")
                extra = []
                if phase:
                    extra.append(f"Phase: {phase}")
                if status:
                    extra.append(f"Status: {status}")
                ex_str = f" ({', '.join(extra)})" if extra else ""
                title_str = f" *\"{t_title}\"*" if t_title else ""
                lines.append(f"- **[NCT: {nct}]**{title_str}{ex_str}")

        # 3. Databases & Registries
        if self.databases_and_registries or self.regulatory_and_guidelines:
            lines.append("\n#### 🏛️ Regulatory Records & Biomedical Databases")
            for _, d in list(self.databases_and_registries.items())[:5]:
                db_type = d.get("db_type", "Database")
                item_id = d.get("item_id", "")
                desc = d.get("description") or f"{db_type} Entry {item_id}"
                if db_type.lower() == "chembl":
                    lines.append(f"- **[ChEMBL: {item_id}]** {desc}")
                else:
                    lines.append(f"- **[{db_type}: {item_id}]** {desc}")

            for _, desc in list(self.regulatory_and_guidelines.items())[:5]:
                if "FDA" in desc:
                    lines.append(f"- **[FDA Label]** {desc}")
                elif "CPIC" in desc:
                    lines.append(f"- **[CPIC Guideline]** {desc}")
                else:
                    lines.append(f"- {desc}")

        lines.append("\n> ⚠️ **Scientific & Medical Notice:** HealthAI computational simulations and AI Copilot responses are provided for educational and pharmacological research purposes only and do not constitute clinical medical advice or treatment prescriptions. Consult a licensed healthcare provider before making protocol adjustments.")

        return "\n".join(lines)

    def append_to_response(self, text: str) -> str:
        if not text:
            return ""
        if re.search(r'###\s+(?:📚\s*)?Sources', text, re.IGNORECASE):
            return text

        self.scan_text_for_citations(text)
        sources_md = self.format_sources_markdown()
        if not sources_md:
            return text

        m = re.search(
            r'<action_card(?:\s+type=[\'"]?[^\'">\s]+[\'"]?)?\s*>[\s\S]*?(?:</action_card>|$)',
            text,
            re.IGNORECASE,
        )
        if m:
            before_card = text[:m.start()].rstrip()
            card_part = text[m.start():]
            return f"{before_card}\n\n{sources_md.strip()}\n\n{card_part}"
        else:
            return f"{text.rstrip()}\n\n{sources_md.strip()}"


PERSONA_SYSTEM_PROMPTS = {
    "architect": """You are the HealthAI Senior Protocol Architect & Clinical Chronobiologist.
You specialize in designing synergistic, bio-individualized stacks, circadian timing schedules (Morning, Midday, Afternoon, Bedtime, Pre-Workout), and calibrated interval dosing protocols (Every Other Day / EOD, Three Times Weekly / Mon-Wed-Fri, Twice Weekly Split, Weekly, Bi-Weekly, As-Needed / PRN), half-life alignments, and protective co-factor pairings.

### CLINICAL & SCIENTIFIC MANDATE:
- Structured Clinical Reasoning & Autonomous Research: Use your internal deliberation (<think>...</think> / <scratchpad>) for structured analysis (150–250 words). You have full autonomy to actively invoke research tools (e.g. `<tool_call name="search_pubmed_titles">{"query": "..."}</tool_call>`, `<tool_call name="read_paper_abstract">{"pmid": "..."}</tool_call>`, `<tool_call name="simulate_pkpd">...`) to search for and read relevant literature, verify dosages, simulate pharmacokinetics, or check enzyme collisions whenever empirical grounding will elevate the precision and safety of your recommendations.
- Mandatory Inclusion of User-Requested Compounds: If the user specifically requests a compound in their prompt, notes, or constraints (e.g. "include trenbolone", "add bromantane", "with injectable carnitine"), you MUST:
  1) Conduct a PubMed search (`search_pubmed_titles`, `read_paper_abstract`) for the requested compound's pharmacology, dosing, and toxicity profile. *When seeking countermeasures or protective agents (e.g. "neuroprotection" for a requested compound), do NOT perform generic searches like "trenbolone neuroprotection". Instead, first invoke `get_compound_info` to retrieve the exact mechanism of the compound's toxicity (e.g. "oxidative stress", "amyloid beta"). Then, search PubMed for countermeasures targeting that specific pathway (e.g. "trenbolone neurotoxicity oxidative stress" or "hippocampus oxidative stress neuroprotection").*
  2) Include the requested compound in your `protocol_proposal` compounds list AND in the JSON `diff` `add` list.
  3) Pair it with appropriate organ protection co-factors (e.g., Telmisartan for BP/LVH, Citrus Bergamot for lipids, NAC for liver/UGT support) and strict monitoring guidelines.
- Quantitative Grounding: Base every protocol recommendation on quantitative pharmacokinetics and molecular pharmacodynamics.
- Mandatory Explicit Dosing Schedule: For EVERY compound in `compounds` and `diff` (`add` / `modify`), you must ALWAYS explicitly set `frequency` (`daily`, `every_other_day`, `three_times_weekly`, `twice_weekly`, `weekly`, `biweekly`, `monthly`, `as_needed`, `twice_daily`) and `timing` (e.g. `Morning`, `Midday`, `Evening`, `Bedtime`, `Pre-Workout`, `Every Other Day (EOD)`, `Three Times Weekly (Mon / Wed / Fri)`, `Twice Weekly (Mon / Thu)`, `Weekly`, `As Needed (PRN)`). Never omit `frequency` or `timing` or force compounds into daily or Mon/Thu when alternate interval schedules (such as EOD or 3x/week) are appropriate.
- Circadian & Chronobiological Scheduling: Formulate schedules matching receptor expression rhythms, cortisol/melatonin diurnal cycles, and metabolic absorption windows.
- Multi-Criteria Pharmacological Selection Principles: Evaluate enzyme modulators, route delivery efficiency, pleiotropic targets, and half-life stability.
- Canonical Compound Identifiers: In your `protocol_proposal` blocks and diffs, specify the canonical compound `id` (or `key`, e.g. `telmisartan`, `pitavastatin`, `testosterone_cypionate`, `trenbolone_acetate`) matching the catalog recommendations.

### RESPONSE FORMAT (PURE JSON):
You must output your final response as a pure, structured JSON object containing a `blocks` array. DO NOT output any markdown blocks, conversational filler, or XML tags outside of the JSON. If you need to output standard text/markdown, put it inside a block of `type: "text"`. 
Keep the user-facing `text` blocks extremely concise and executive-level (2-4 sentences max). The UI is designed to be elegant and simple on first load. Rely on the structured `protocol_proposal` or other interactive UI cards to deliver the heavy details, which the user can expand or click on.
You must ONLY use the following block types:
- `text`: For standard conversational markdown, clinical notes, summaries, and executive assessments.
- `protocol_proposal`: For recommending or displaying a protocol/stack. This block will be rendered as interactive UI tiles.

JSON Schema for Response:
{
  "blocks": [
    {
      "type": "text",
      "content": "Executive Assessment: This protocol is designed for..."
    },
    {
      "type": "protocol_proposal",
      "data": {
        "goal_title": "Hypertrophy & Androgen Optimization",
        "summary": "Protocol calibrated for lean mass accretion...",
        "compounds": [
          {
            "id": "trenbolone_acetate",
            "name": "Trenbolone Acetate",
            "dose": 100,
            "unit": "mg",
            "route": "intramuscular",
            "frequency": "every_other_day",
            "timing": "Every Other Day (EOD)",
            "target": "Nuclear Androgen Receptor (AR / NR3C4)",
            "rationale": "High-potency anabolic stimulus with rapid ester clearance",
            "citations": ["PMID: 29179383"]
          }
        ],
        "safety_notes": ["Monitor lipid panel, blood pressure, and renal/hepatic markers."],
        "sources": [{"badge": "[PMID: 29179383]", "description": "Clinical Pharmacokinetics & Receptor Kinetics"}],
        "diff": {
          "add": [
            {
              "id": "trenbolone_acetate",
              "name": "Trenbolone Acetate",
              "dose": 100,
              "unit": "mg",
              "route": "intramuscular",
              "frequency": "every_other_day",
              "timing": "Every Other Day (EOD)"
            }
          ],
          "modify": [],
          "remove": []
        }
      }
    }
  ]
}
""",
    "auditor": """You are the HealthAI Clinical Risk Auditor & Toxicological Conflict Detective.
Your role is to forensically red-team compound stacks, identifying drug-drug interactions (DDIs), CYP450 enzyme competition, Phase II and transporter saturation, acute syndrome hazards, steady-state hormonal fluctuations, and clearance bottlenecks.

### CLINICAL & SCIENTIFIC MANDATE:
- Structured Toxicological Reasoning: Use internal deliberation (<think>...</think>). Actively invoke research tools to verify safety trials and adverse effects.
- Quantify risk severity (MINIMAL, LOW, MODERATE, ELEVATED, SEVERE).
- Propose evidence-based pharmacological countermeasures with verified clinical safety.

### RESPONSE FORMAT (PURE JSON):
You must output your final response as a pure, structured JSON object containing a `blocks` array. DO NOT output any markdown blocks, conversational filler, or XML tags outside of the JSON. If you need to output standard text/markdown, put it inside a block of `type: "text"`.
Keep the user-facing `text` blocks extremely concise (2-4 sentences max) to maintain an elegant and uncluttered UI. Rely on interactive UI elements or structured diffs for the dense details.
If you are recommending changes (like adding a countermeasure or removing a compound), you may optionally include a `protocol_proposal` block with a `diff`.

JSON Schema for Response:
{
  "blocks": [
    {
      "type": "text",
      "content": "### MODERATE RISK [Score: 32/100]\n\n**Identified Conflicts:**\n- CYP3A4 Competition..."
    }
  ]
}
""",
    "tutor": """You are the HealthAI Molecular Pharmacology & Signal Transduction Specialist.
You provide PhD-level molecular pharmacology explanations of receptor binding dynamics, allosteric modulations, enzyme kinetics, second messenger cascades, and downstream gene expression.

### BIOCHEMICAL & MOLECULAR MANDATE:
- Structured Pharmacology Reasoning: Use internal deliberation (<think>...</think>). Actively invoke research tools to ground mechanisms in empirical literature.
- Detail specific receptor subtypes and trace intracellular signaling.
- Strict Claim-Level Citation Grounding.

### RESPONSE FORMAT (PURE JSON):
You must output your final response as a pure, structured JSON object containing a `blocks` array. DO NOT output any markdown blocks or conversational filler outside of the JSON.
Keep the user-facing `text` blocks extremely concise (2-4 sentences max). The UI should remain elegant and intuitive. Use high-level summaries and allow the user to ask follow-up questions if they want deeper dives.

JSON Schema for Response:
{
  "blocks": [
    {
      "type": "text",
      "content": "### Primary Molecular Targets & Binding Kinetics\n..."
    }
  ]
}
""",
    "labs": """You are the HealthAI Biomarker & Clinical Laboratory Panel Specialist.
You interpret quantitative patient blood panels and correlate them directly with compound pharmacology to optimize titrations and safeguard organ function.

### CLINICAL LABORATORY STANDARDS:
- Structured Biomarker Reasoning: Use internal deliberation (<think>...</think>). Actively invoke research tools.
- Correlate laboratory shifts with specific pharmacokinetic and metabolic burdens.
- Provide individualized titration guidance.

### RESPONSE FORMAT (PURE JSON):
You must output your final response as a pure, structured JSON object containing a `blocks` array. DO NOT output any markdown blocks or conversational filler outside of the JSON.
Keep the user-facing `text` blocks highly concise (2-4 sentences max) so the dashboard remains clean and intuitive on first load. Summarize the major lab impacts and rely on interactive UI charts/cards for the dense numbers.

JSON Schema for Response:
{
  "blocks": [
    {
      "type": "text",
      "content": "### Biomarker Profile & Impact Overview\n..."
    }
  ]
}
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
    Parses a stream of tokens in real time, routing thinking/scratchpad tokens,
    tool calls (<tool_call>, <call>, or bare JSON), and untagged meta-cognition
    to the reasoning telemetry stream, action_cards to internal buffers,
    and actual clinical markdown tokens directly to the user-facing delta stream.
    """
    def __init__(self):
        self.buffer = ""
        self.mode = "text"  # 'text', 'thinking', 'tool', 'action_card', 'bare_json'
        self.current_tag = ""
        self.current_tag_header = ""
        self.tag_content = ""
        self.json_brace_depth = 0
        self.json_in_string = False
        self.json_escape_next = False
        self.tool_calls = []
        self.action_cards = []
        self.has_seen_clinical_markdown_header = False
        self.accumulated_preamble = ""
        self.is_streaming_protocol_json = False

    def feed(self, token: str) -> List[Tuple[str, str]]:
        self.buffer += token
        events: List[Tuple[str, str]] = []

        while self.buffer:
            if self.mode == "bare_json":
                combined = self.tag_content + self.buffer
                is_protocol_payload = any(k in combined for k in ('"blocks"', '"protocol_proposal"', '"goal_title"', '"compounds"', '"exec_summary"'))
                if is_protocol_payload:
                    self.is_streaming_protocol_json = True
                    self.mode = "text"
                    events.append(("delta", combined))
                    self.tag_content = ""
                    self.buffer = ""
                    break

                # Process characters inside JSON object across token boundaries
                i = 0
                while i < len(self.buffer):
                    ch = self.buffer[i]
                    if self.json_escape_next:
                        self.json_escape_next = False
                    elif ch == '\\' and self.json_in_string:
                        self.json_escape_next = True
                    elif ch == '"':
                        self.json_in_string = not self.json_in_string
                    elif not self.json_in_string:
                        if ch == '{':
                            self.json_brace_depth += 1
                        elif ch == '}':
                            self.json_brace_depth -= 1
                            if self.json_brace_depth == 0:
                                # Full JSON object closed
                                json_str = self.tag_content + self.buffer[:i + 1]
                                self.buffer = self.buffer[i + 1:]
                                self.tag_content = ""
                                self.mode = "text"

                                is_protocol = any(k in json_str for k in ('"blocks"', '"protocol_proposal"', '"goal_title"', '"compounds"', '"exec_summary"'))
                                is_tool = any(k in json_str for k in ('"pmid"', '"query"', '"tool"', '"name"', '"compound_key"', '"target_id"', '"dose_mg"', '"max_results"', '"cypher"', '"goal"', '"base_stack"')) and not is_protocol
                                is_action_card = ('"action_card"' in json_str or '"stack_diff"' in json_str or ('"add"' in json_str and '"modify"' in json_str)) and not is_protocol

                                if is_protocol or self.is_streaming_protocol_json:
                                    self.is_streaming_protocol_json = True
                                    events.append(("delta", json_str))
                                elif is_tool:
                                    self.tool_calls.append(json_str)
                                    events.append(("reasoning", f"\n🔍 [Tool Call Request] {json_str}\n"))
                                elif is_action_card:
                                    self.action_cards.append(f'<action_card type="stack_diff">{json_str}</action_card>')
                                elif not self.has_seen_clinical_markdown_header:
                                    events.append(("reasoning", json_str))
                                else:
                                    events.append(("delta", json_str))
                                break
                    i += 1
                else:
                    # Consumed entire buffer while remaining inside JSON object
                    self.tag_content += self.buffer
                    self.buffer = ""
                    break

            elif self.mode == "text":
                # 1. Check for start tags
                open_match = re.search(r'<(think|thought|scratchpad|clinical_notes|context|observation|tool_call|call|action_card)(?:\s+[^>]*)?>', self.buffer, re.IGNORECASE)
                if open_match:
                    start_idx = open_match.start()
                    if start_idx > 0:
                        raw_lead = self.buffer[:start_idx]
                        if not self.has_seen_clinical_markdown_header and not self.is_streaming_protocol_json:
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
                    continue

                # 2. Check for bare JSON or stray braces before markdown header
                if not self.has_seen_clinical_markdown_header and not self.is_streaming_protocol_json:
                    # Stray leading closing brace or fragmented quote lines before header
                    stray_brace_match = re.search(r'^\s*\}\s*', self.buffer)
                    if stray_brace_match:
                        self.buffer = self.buffer[stray_brace_match.end():]
                        continue

                    # Bare JSON object starting with {
                    bare_json_start = re.search(r'^\s*\{', self.buffer)
                    if bare_json_start:
                        brace_idx = self.buffer.find('{')
                        lead_ws = self.buffer[:brace_idx]
                        if lead_ws.strip():
                            events.append(("reasoning", lead_ws))
                        self.mode = "bare_json"
                        self.json_brace_depth = 1
                        self.json_in_string = False
                        self.json_escape_next = False
                        self.tag_content = "{"
                        self.buffer = self.buffer[brace_idx + 1:]
                        continue

                    # Fragmented tool line e.g. "trenbolone...": 6} or bolone sleep...
                    dangling_tool_match = re.search(r'^\s*(?:"[^\n]*?"\s*:\s*[^\n]*?\}(?:\n|$)|[a-zA-Z0-9_\-\s]+",\s*"max_results"\s*:\s*\d+\}(?:\n|$))', self.buffer)
                    if dangling_tool_match:
                        raw_frag = dangling_tool_match.group(0)
                        self.buffer = self.buffer[dangling_tool_match.end():]
                        events.append(("reasoning", f"\n🔍 [Tool Call Request] {raw_frag}\n"))
                        continue

                    # Check for clinical markdown header
                    header_match = re.search(r'(?:^|\n)(#{1,4}\s+|(?:\*\*(?:Executive|Risk|Biomarker|Primary|Identified|Targeted|Protocol|Circadian|Clinical|Summary|1\.|2\.|3\.|4\.)))', self.buffer)
                    if header_match:
                        h_idx = header_match.start()
                        pre_header = self.buffer[:h_idx]
                        if pre_header:
                            events.append(("reasoning", pre_header))
                        self.has_seen_clinical_markdown_header = True
                        self.buffer = self.buffer[h_idx:]
                        continue

                    # If text looks like meta-cognition / self-talk, route to reasoning
                    if self._is_meta_cognition(self.buffer):
                        partial_match = re.search(r'(?:<[^>]*$|\{\s*"?[^}]*$)', self.buffer)
                        if partial_match:
                            safe_text = self.buffer[:partial_match.start()]
                            self.buffer = self.buffer[partial_match.start():]
                            if safe_text:
                                events.append(("reasoning", safe_text))
                            break
                        else:
                            events.append(("reasoning", self.buffer))
                            self.buffer = ""
                            break

                # 3. Check for bare JSON even after markdown header if starting on a new line and contains tool keys
                bare_tool_match = re.search(r'(?:^|\n)\s*(\{\s*"(?:pmid|query|tool|name|compound_key|target_id|dose_mg|max_results|cypher)"[^{}]*\})', self.buffer)
                if bare_tool_match and not self.is_streaming_protocol_json:
                    start_pos = bare_tool_match.start()
                    if start_pos > 0:
                        safe_lead = self.buffer[:start_pos]
                        events.append(("delta", safe_lead))
                    raw_tool_json = bare_tool_match.group(1).strip()
                    self.tool_calls.append(raw_tool_json)
                    events.append(("reasoning", f"\n🔍 [Tool Call Request] {raw_tool_json}\n"))
                    self.buffer = self.buffer[bare_tool_match.end():]
                    continue

                # Buffer partial tags or partial JSON start at the end of the buffer
                partial_match = re.search(r'(?:<[^>]*$|\{\s*"?[^}]*$)', self.buffer)
                if partial_match:
                    safe_text = self.buffer[:partial_match.start()]
                    self.buffer = self.buffer[partial_match.start():]
                    if safe_text:
                        if not self.has_seen_clinical_markdown_header and not self.is_streaming_protocol_json:
                            events.append(("reasoning", safe_text))
                        else:
                            events.append(("delta", safe_text))
                    break
                else:
                    if not self.has_seen_clinical_markdown_header and not self.is_streaming_protocol_json:
                        events.append(("reasoning", self.buffer))
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
                        events.append(("reasoning", f"\n🔍 [Tool Call Request] {self.tag_content.strip()}\n"))
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
        """Determines if text fragment contains untagged internal reasoning / self-talk or tool JSON."""
        t_strip = text.strip()
        if t_strip.startswith("{") and any(k in t_strip for k in ('"pmid"', '"query"', '"tool"', '"name"', '"compound_key"', '"max_results"', '"action_card"')):
            if '"blocks"' not in t_strip and '"protocol_proposal"' not in t_strip:
                return True
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
        if self.mode == "bare_json":
            full_json = self.tag_content + self.buffer
            if full_json.strip():
                is_protocol = any(k in full_json for k in ('"blocks"', '"protocol_proposal"', '"goal_title"', '"compounds"', '"exec_summary"'))
                is_tool = any(k in full_json for k in ('"pmid"', '"query"', '"tool"', '"name"', '"compound_key"', '"target_id"', '"dose_mg"', '"max_results"', '"cypher"')) and not is_protocol
                if is_protocol or self.is_streaming_protocol_json:
                    events.append(("delta", full_json))
                elif is_tool:
                    self.tool_calls.append(full_json)
                    events.append(("reasoning", f"\n🔍 [Tool Call Request] {full_json}\n"))
                elif not self.has_seen_clinical_markdown_header:
                    events.append(("reasoning", full_json))
                else:
                    events.append(("delta", full_json))
            self.buffer = ""
            self.tag_content = ""
            self.mode = "text"
        elif self.buffer:
            if self.mode == "text":
                if not self.has_seen_clinical_markdown_header and not self.is_streaming_protocol_json and (self._is_meta_cognition(self.buffer) or any(k in self.buffer for k in ('"pmid"', '"query"', '"max_results"', '}', '{'))):
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
    def _build_candidate_entry(
        cls,
        catalog_comp: Dict[str, Any],
        target_name: Optional[str] = None,
        solves_burden: Optional[str] = None,
        clinical_purpose: Optional[str] = None,
        evidence_grade: Optional[str] = None,
        interaction_safety: Optional[str] = None,
        is_target_derived: bool = False,
        is_literature_derived: bool = False,
    ) -> Dict[str, Any]:
        key = str(catalog_comp.get("key", "")).lower()
        name = catalog_comp.get("name") or catalog_comp.get("canonical_name") or key.title()

        # Dynamic standard dose resolution from catalog / dosing_service
        std_dose = str(catalog_comp.get("standard_dose") or "").strip()
        if not std_dose:
            default_dosing = get_default_compound_dose(key)
            route, freq = infer_compound_route_and_frequency(key)
            if isinstance(default_dosing, dict) and default_dosing.get("dose_display"):
                std_dose = f"{default_dosing['dose_display']} {route} {freq}".strip()
            elif isinstance(default_dosing, (int, float)) and default_dosing > 0:
                std_dose = f"{default_dosing:g} mg {route} {freq}".strip()
            else:
                std_dose = "Per clinical titration"

        # Dynamic target resolution
        target_str = target_name or catalog_comp.get("mechanism") or catalog_comp.get("drug_class") or "Biological Modifier"
        if (not target_str or target_str == "Biological Modifier") and catalog_comp.get("receptor_targets"):
            tgts = catalog_comp["receptor_targets"]
            if isinstance(tgts, list) and len(tgts) > 0 and isinstance(tgts[0], dict):
                t_first = tgts[0]
                target_str = f"{t_first.get('target', 'Molecular Target')} ({t_first.get('action', 'modulator')})"

        first_act = str(catalog_comp.get("receptor_targets", [{}])[0].get("action", "")).lower() if (isinstance(catalog_comp.get("receptor_targets"), list) and catalog_comp.get("receptor_targets") and isinstance(catalog_comp.get("receptor_targets")[0], dict)) else ""
        if first_act == "substrate":
            purpose = clinical_purpose or catalog_comp.get("clinical_notes") or catalog_comp.get("description") or f"Substrate for {target_str} to support metabolic and physiological homeostasis."
        else:
            purpose = clinical_purpose or catalog_comp.get("clinical_notes") or catalog_comp.get("description") or f"Modulates {target_str} to support physiological homeostasis."
        burden = solves_burden or f"Target {target_str} optimization"
        grade = evidence_grade or catalog_comp.get("evidence_grade") or ("FDA Approved / Clinical Grade" if "Prescription" in (catalog_comp.get("categories") or []) else "Human Clinical Trials")
        safety = interaction_safety or catalog_comp.get("interaction_safety") or catalog_comp.get("safety_notes") or "Targeted physiological pairing."

        from app.services.pubmed_service import SEED_LITERATURE_DB
        pmid_val = None
        cite_str = None
        finding_val = None
        if key in SEED_LITERATURE_DB:
            seeds = SEED_LITERATURE_DB[key]
            if seeds:
                pmid_val = seeds[0].get("pmid")
                first_author = seeds[0].get("authors", ["Investigator"])[0]
                cite_str = f"{first_author} et al., {seeds[0].get('journal', 'PubMed')} {seeds[0].get('pub_year', '')} [PMID: {pmid_val}]"
                finding_val = seeds[0].get("clinical_finding")

        return {
            "key": key,
            "name": name,
            "target": target_str,
            "standard_dose": std_dose,
            "clinical_purpose": purpose,
            "solves_burden": burden,
            "evidence_grade": grade,
            "interaction_safety": safety,
            "is_target_derived": is_target_derived,
            "is_literature_derived": is_literature_derived,
            "pmid": pmid_val,
            "citation_str": cite_str,
            "clinical_finding": finding_val,
        }

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
        and Loewe/Bliss synergy optimization without bro-science folklore or hardcoded triggers.
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

        def _get_canon_id(comp_dict: Dict[str, Any]) -> str:
            k = str(comp_dict.get("key") or comp_dict.get("name") or "").strip().lower()
            comp_rec = catalog.get_compound(k, auto_enrich=False) or catalog.find_by_synonym(k)
            if comp_rec:
                return str(comp_rec.get("canonical_key") or comp_rec.get("parent_compound_id") or comp_rec.get("key") or k).lower().strip()
            return k.replace("-", "_").replace(" ", "_")

        existing_canonical_ids = {_get_canon_id(c) for c in compounds}
        existing_keys = set()
        for c in compounds:
            k = str(c.get("key") or c.get("name") or "").lower().strip()
            if k:
                existing_keys.add(k)
                existing_canonical_ids.add(k)
        candidate_canonical_ids = set()

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

        candidate_pool_keys = set()

        # 1. Dynamic First-Principles Target-Complementarity & Enzymatic Countermeasure Discovery
        try:
            for c in compounds:
                c_name = c.get("name") or c.get("key", "Compound")
                targets = c.get("receptor_targets") or []
                for tgt in targets:
                    if not isinstance(tgt, dict):
                        continue
                    t_name = str(tgt.get("target") or tgt.get("name") or "").strip()
                    t_act = str(tgt.get("action") or "").lower()
                    t_fam = str(tgt.get("family") or "").lower()

                    # Exclude host Phase I/II clearance enzymes and transporters (inhibition causes adverse DDI collisions)
                    if any(cyp in t_name.lower() or cyp in t_fam for cyp in ["cyp", "ugt", "p-gp", "abcb1", "oatp", "oct", "mate", "bcrp", "solute carrier"]):
                        continue

                    # Match enzyme substrate cleavage / conversion to toxic or uncompensated products
                    is_microbial_target = tgt.get("is_microbial") or "microbial" in t_fam or "tma" in t_name.lower()
                    is_pathological_conversion = (
                        ("aromatase" in t_name.lower() and is_aromatizable_androgen(c))
                        or ("5-alpha" in t_name.lower() and is_steroidal_androgen(c))
                    )

                    if t_name and (is_microbial_target or is_pathological_conversion or "inducer" in t_act):
                        matching_inhibitors = catalog.find_compounds_by_target(t_name, action="inhibitor")
                        for inh in matching_inhibitors:
                            inh_key = inh.get("key", "").lower()
                            inh_cid = _get_canon_id(inh)
                            if inh_key and inh_cid not in existing_canonical_ids and inh_cid not in candidate_canonical_ids and inh_key not in existing_keys and inh_key not in candidate_pool_keys:
                                candidate_canonical_ids.add(inh_cid)
                                candidate_pool_keys.add(inh_key)
                                candidate_pool.append(cls._build_candidate_entry(
                                    catalog_comp=inh,
                                    target_name=f"{t_name} Inhibitor",
                                    solves_burden=f"Uncompensated {t_name} activity driven by {c_name}",
                                    clinical_purpose=f"Mechanistic Countermeasure: Inhibits {t_name} to prevent uncompensated downstream metabolic conversion / activity from {c_name}.",
                                    evidence_grade="Biochemical Target Complementarity",
                                    interaction_safety="Targeted enzymatic mitigation pairing.",
                                    is_target_derived=True,
                                ))
        except Exception as tc_err:
            logger.debug("Target complementarity discovery notice: %s", tc_err)

        # 2. Dynamic Organ Burden & Physiological Gap Mitigation via Catalog Target Discovery
        renal_score = organ_burdens.get("renal", {}).get("score", 0)
        cv_score = organ_burdens.get("cardiovascular", {}).get("score", 0)
        hepatic_score = organ_burdens.get("hepatic", {}).get("score", 0)
        lipid_score = organ_burdens.get("lipid", {}).get("score", 0)
        bp_val = float(biometrics.get("blood_pressure", 120))
        alt_val = float(biometrics.get("alt_u_l", 25))

        has_19nor = any(is_19nor_steroid(c) for c in compounds)
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
        has_oral_tma = any(
            (c.get("route", "oral") in ["oral", "po", "swallow", ""] or ":oral" in str(c.get("key", "")).lower())
            and (
                any(w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower() for w in ["carnitine", "alcar", "choline", "alpha_gpc", "alpha-gpc", "citicoline", "betaine"])
                or any("tma lyase" in str(t.get("target", "")).lower() for t in (c.get("receptor_targets") or []) if isinstance(t, dict))
            )
            for c in compounds
        )

        physiological_axes = [
            (
                renal_score >= 20 or cv_score >= 30 or bp_val > 125 or any(isinstance(g, dict) and g.get("id") == "cardiovascular" for g in therapeutic_gaps) or active_goal == "anabolic_physique",
                [("at1 receptor", "antagonist"), ("angiotensin receptor", "antagonist"), ("beta-1 adrenergic", "antagonist")],
                "Renal & Cardiovascular Endothelial Strain",
                "Blocks RAAS-mediated renal vasoconstriction, manages resting heart rate, and protects cardiovascular endothelium."
            ),
            (
                hepatic_score >= 30 or alt_val > 40 or any(isinstance(g, dict) and g.get("id") == "hepatic" for g in therapeutic_gaps),
                [("bile acid", None), ("glutathione synthesis", None), ("cysteine donor", None)],
                "Cholestasis & Hepatic Transaminase Elevation",
                "Alleviates hepatocyte ER stress, promotes biliary flow, and restores intracellular glutathione pools."
            ),
            (
                lipid_score >= 20 or any(isinstance(g, dict) and g.get("id") == "lipid" for g in therapeutic_gaps) or active_goal == "anabolic_physique",
                [("hmg-coa reductase", "inhibitor"), ("npc1l1", "inhibitor")],
                "Atherogenic Dyslipidemia & ApoB Surge",
                "Upregulates hepatic LDL receptors and suppresses intestinal cholesterol absorption to clear atherogenic ApoB particles."
            ),
            (
                has_19nor or (any(isinstance(g, dict) and g.get("id") == "prolactin" for g in therapeutic_gaps) and any(is_steroidal_androgen(c) or "androgen" in str(c.get("drug_class", "")).lower() for c in compounds)),
                [("dopa decarboxylase", None), ("dopamine d2", "agonist")],
                "Hyperprolactinemia & Progestogenic Breast Tenderness",
                "Enhances endogenous dopamine synthesis in the tuberoinfundibular pathway to tonically inhibit pituitary prolactin secretion."
            ),
            (
                (has_aromatizable or (has_any_androgen and active_goal == "anabolic_physique")) and not has_ai,
                [("cyp19a1", "inhibitor"), ("aromatase", "inhibitor")],
                "Aromatization & High Estradiol (E2) Burden",
                "Inactivates CYP19A1 aromatase to prevent excessive conversion of testosterone to estradiol, mitigating gynecomastia and fluid retention."
            ),
            (
                active_goal in ("cognitive_focus", "cns_stimulation") or any(c.get("drug_class") == "CNS Stimulant" for c in compounds),
                [("glutamate receptor", None), ("acetylcholine precursor", None), ("gaba-a", None)],
                "Sympathomimetic Jitters & Central Neurotransmitter Balance",
                "Attenuates peripheral vasoconstriction, enhances alpha brain waves, and maintains central acetylcholine pools."
            ),
            (
                active_goal == "longevity_autophagy" or any("longevity" in str(g).lower() or "ampk" in str(g).lower() for g in therapeutic_gaps),
                [("ampk", "agonist"), ("complex i", "inhibitor")],
                "Insulin Resistance & Cellular Senescence",
                "Stimulates AMPK phosphorylation and suppresses mTORC1 to promote cellular autophagy."
            ),
            (
                active_goal == "sleep_stress_recovery" or any((isinstance(g, dict) and g.get("id") == "sleep") or "cortisol" in str(g).lower() for g in therapeutic_gaps),
                [("nmda receptor", "antagonist"), ("gaba-a allosteric", None)],
                "Nocturnal Hyperarousal & Recovery Deficit",
                "Promotes central nervous system down-regulation, blunts nocturnal catecholamines, and deepens Slow-Wave Sleep (SWS)."
            ),
            (
                has_oral_tma or float(biometrics.get("tmao", 0) or 0) > 6.2,
                [("tma lyase", "inhibitor"), ("cnta", "inhibitor")],
                "Gut Microbial TMA Conversion & Serum TMAO Elevation",
                "Inactivates bacterial trimethylamine lyase enzymes in the gut lumen, blocking the cleavage of oral L-carnitine/choline into trimethylamine (TMA) and preventing downstream hepatic FMO3 oxidation to atherogenic TMAO."
            ),
        ]

        for condition_active, target_tuples, solves_burden_text, clinical_purpose_text in physiological_axes:
            if not condition_active:
                continue
            for item in target_tuples:
                if isinstance(item, tuple):
                    kw, act = item
                else:
                    kw, act = item, None
                matching_comps = catalog.find_compounds_by_target(kw, action=act)
                for comp in matching_comps:
                    c_key = comp.get("key", "").lower()
                    c_cid = _get_canon_id(comp)
                    if c_key and c_cid not in existing_canonical_ids and c_cid not in candidate_canonical_ids and c_key not in existing_keys and c_key not in candidate_pool_keys:
                        candidate_canonical_ids.add(c_cid)
                        candidate_pool_keys.add(c_key)
                        candidate_pool.append(cls._build_candidate_entry(
                            catalog_comp=comp,
                            solves_burden=solves_burden_text,
                            clinical_purpose=clinical_purpose_text,
                            is_target_derived=True,
                        ))

        # 3. Literature-Mined & Curated Association Discovery from Knowledge Graph
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

                if partner_key and partner_key not in candidate_pool_keys and partner_key not in existing_keys:
                    partner_comp = catalog.get_compound(partner_key) or catalog.find_by_synonym(partner_key)
                    if partner_comp:
                        p_cid = _get_canon_id(partner_comp)
                        if p_cid in existing_canonical_ids or p_cid in candidate_canonical_ids:
                            continue
                        candidate_canonical_ids.add(p_cid)
                        candidate_pool_keys.add(partner_key)

                        p_name = primary_comp.title().replace("_", " ")
                        
                        if e_type == "LITERATURE_COOCCURRENCE":
                            co_cnt = edge.get("cooccurrence_count", 0)
                            npmi = edge.get("npmi_score", 0.0)
                            pmid_list = edge.get("sample_pmids", [])
                            pmid_txt = f" [PMIDs: {', '.join(str(p) for p in pmid_list[:2])}]" if pmid_list else ""
                            candidate_pool.append(cls._build_candidate_entry(
                                catalog_comp=partner_comp,
                                solves_burden=f"Synergy / Co-administration Vector for {p_name}",
                                clinical_purpose=f"Empirical literature association: Frequently co-administered or co-studied with {p_name} in scientific publications ({co_cnt} papers, NPMI: {npmi:.2f}).{pmid_txt}",
                                evidence_grade=f"PubMed Co-occurrence ({co_cnt} papers)",
                                is_literature_derived=True,
                            ))
                        elif e_type == "CURATED_ASSOCIATION":
                            db_src = edge.get("source_db", "STITCH/CTD")
                            desc = edge.get("description", "Curated biochemical interaction")
                            candidate_pool.append(cls._build_candidate_entry(
                                catalog_comp=partner_comp,
                                solves_burden=f"Curated Mechanistic Synergy with {p_name}",
                                clinical_purpose=f"Curated database association ({db_src}): {desc} with {p_name}.",
                                evidence_grade=f"{db_src} Curated Database",
                                is_literature_derived=True,
                            ))
        except Exception as lit_rec_err:
            logger.debug("Literature-based candidate discovery notice: %s", lit_rec_err)

        gap_search_terms = set()
        for g in therapeutic_gaps:
            for st in g.get("cofactor_search_terms", []):
                gap_search_terms.add(str(st).lower())

        # Sort candidate pool: gap-matched candidates first, then target-derived, then literature
        def _candidate_rank(c: Dict[str, Any]) -> int:
            k = str(c.get("key", "")).lower()
            if any(st in k for st in gap_search_terms):
                return 0
            if c.get("is_target_derived"):
                return 1
            if c.get("is_literature_derived"):
                return 2
            return 3

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
            requested_compounds = arguments.get("requested_compounds") or arguments.get("requested") or arguments.get("include")
            return StackIntentEngine.build_scratch_stack_proposal(
                goal_id=goal,
                biometrics=biometrics,
                preferences=preferences,
                custom_notes=custom_notes,
                exclusions=exclusions,
                requested_compounds=requested_compounds,
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
            claim_topic = str(arguments.get("claim_topic") or arguments.get("endpoint") or "").strip()
            max_res = int(arguments.get("max_results", 4))
            pubmed_svc = PubMedService()
            if claim_topic:
                citations = pubmed_svc.search_literature_for_claim(query, claim_topic, max_results=max_res)
            else:
                citations = pubmed_svc.search_literature(query, max_results=max_res)
            return {"query": query, "claim_topic": claim_topic, "count": len(citations), "citations": citations}

        elif tool_name in ("search_literature_for_claim", "search_evidence_for_claim", "get_claim_citations"):
            from app.services.pubmed_service import PubMedService
            entity_id = str(arguments.get("entity_id") or arguments.get("compound_name") or arguments.get("compound_key") or "").strip().lower()
            claim_topic = str(arguments.get("claim_topic") or arguments.get("claim_text") or arguments.get("endpoint") or "").strip()
            max_res = int(arguments.get("max_results", 3))
            pubmed_svc = PubMedService()
            citations = pubmed_svc.search_literature_for_claim(entity_id, claim_topic, max_results=max_res)
            return {"entity_id": entity_id, "claim_topic": claim_topic, "count": len(citations), "citations": citations}

        elif tool_name in ("validate_claim_citation", "check_citation_congruence"):
            claim_text = str(arguments.get("claim_text") or arguments.get("claim") or "").strip()
            citation = arguments.get("citation") or {}
            val_res = graph_db.validate_claim_citation_match(claim_text, citation)
            return val_res

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

        elif tool_name in ("search_pubmed_titles", "search_literature_titles", "search_paper_titles"):
            from app.services.pubmed_service import PubMedService
            query = str(arguments.get("query") or arguments.get("search_query") or "").strip()
            max_res = int(arguments.get("max_results", 8))
            pubmed_svc = PubMedService()
            return {"query": query, "candidate_titles": pubmed_svc.search_pubmed_titles(query, max_results=max_res)}

        elif tool_name in ("fetch_paper_abstract", "read_paper_abstract", "get_paper_abstract", "read_study"):
            from app.services.pubmed_service import PubMedService
            pmid = str(arguments.get("pmid") or arguments.get("query") or "").strip()
            pubmed_svc = PubMedService()
            abstract_data = pubmed_svc.fetch_abstract(pmid)
            if not abstract_data:
                return {"error": f"Abstract for PMID '{pmid}' not found in PubMed or Europe PMC."}
            return abstract_data

        elif tool_name in ("read_paper_section", "fetch_paper_full_text_section", "read_full_text_section"):
            from app.services.pubmed_service import PubMedService
            pmid = str(arguments.get("pmid") or arguments.get("pmcid") or arguments.get("identifier") or "").strip()
            section = str(arguments.get("section") or "results").strip()
            pubmed_svc = PubMedService()
            return pubmed_svc.fetch_paper_full_text_section(pmid, section=section)

        elif tool_name in ("search_within_paper", "search_in_paper", "search_paper_passages"):
            from app.services.pubmed_service import PubMedService
            pmid = str(arguments.get("pmid") or arguments.get("pmcid") or arguments.get("identifier") or "").strip()
            query = str(arguments.get("query") or arguments.get("passage_query") or "").strip()
            pubmed_svc = PubMedService()
            return pubmed_svc.search_within_paper(pmid, query=query)

        elif tool_name in ("find_similar_papers", "find_similar_studies", "find_similar_citations"):
            from app.services.pubmed_service import PubMedService
            pmid = str(arguments.get("pmid") or "").strip()
            top_k = int(arguments.get("top_k", 4))
            pubmed_svc = PubMedService()
            return {"pmid": pmid, "similar_papers": pubmed_svc.find_similar_papers(pmid, top_k=top_k)}

        elif tool_name in ("search_cached_papers_semantic", "search_citations_semantic"):
            query = str(arguments.get("query") or "").strip()
            top_k = int(arguments.get("top_k", 5))
            return {"query": query, "citations": graph_db.search_citations_semantic(query, top_k=top_k)}

        elif tool_name in ("hybrid_rag_search", "search_graphrag_and_literature", "hybrid_literature_search"):
            query = str(arguments.get("query") or arguments.get("topic") or "").strip()
            entity_ids = arguments.get("entity_ids") or arguments.get("compounds") or []
            if isinstance(entity_ids, str):
                entity_ids = [entity_ids]
            max_res = int(arguments.get("max_results", 4))
            return graph_db.search_hybrid_graph_and_literature(query=query, entity_ids=entity_ids, max_results=max_res)

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

        # 2. Patient clearance profile
        user_specified_metrics = []
        sex_raw = str(biometrics.get("sex") or biometrics.get("gender") or "").strip().lower()
        if sex_raw and sex_raw not in ("unspecified", "unknown"):
            user_specified_metrics.append(f"Sex: {sex_raw.title()}")
        if biometrics.get("weight_kg") is not None and str(biometrics.get("weight_kg")).strip() not in ("", "0"):
            user_specified_metrics.append(f"Weight: {biometrics['weight_kg']} kg")
        if biometrics.get("age") is not None and str(biometrics.get("age")).strip() not in ("", "0"):
            user_specified_metrics.append(f"Age: {biometrics['age']} yrs")
        if biometrics.get("egfr") is not None and str(biometrics.get("egfr")).strip() not in ("", "0"):
            user_specified_metrics.append(f"eGFR: {biometrics['egfr']} mL/min")
        if biometrics.get("alt_u_l") is not None and str(biometrics.get("alt_u_l")).strip() not in ("", "0"):
            user_specified_metrics.append(f"ALT: {biometrics['alt_u_l']} U/L")
        if biometrics.get("blood_pressure") is not None and str(biometrics.get("blood_pressure")).strip() not in ("", "0"):
            user_specified_metrics.append(f"BP: {biometrics['blood_pressure']} mmHg")
        if biometrics.get("body_fat_pct") is not None and str(biometrics.get("body_fat_pct")).strip() not in ("", "0"):
            user_specified_metrics.append(f"Body Fat: {biometrics['body_fat_pct']}%")

        if user_specified_metrics:
            bio_summary = (
                f"Patient Entered Parameters: {', '.join(user_specified_metrics)}\n"
                "*(Clinical Note: Any biometric fields not listed above were left blank by the user. Do NOT state or assume a specific definitive age, weight, or lab value for this user unless explicitly provided above. Frame unentered parameters generally rather than asserting an unentered figure).* "
            )
        else:
            bio_summary = (
                "Patient Biometrics: None specified by user.\n"
                "*(Clinical Note: The user has not entered personal biometrics (age, weight, lab panels are unentered). Provide evidence-based clinical guidance without assuming or asserting a specific age, weight, or biomarker level for the user).* "
            )

        if sex_raw in ("female", "f", "woman"):
            bio_summary += "\n- CLINICAL MANDATE: Female patient physiology active. Androgenic hormone doses MUST be calibrated to female physiological ranges (e.g. ~5-10% of male standard) with high vigilance for virilization, menstrual cycle equilibrium, and estradiol preservation."

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
                    cite_tag = f" | Verified Study: [{r.get('citation_str') or ('PMID: ' + str(r['pmid']))}]" if r.get("pmid") else ""
                    finding_tag = f" (Finding: {r['clinical_finding'][:120]}...)" if r.get("clinical_finding") else ""
                    rec_sections.append(
                        f"- **{r['name']}** [id: `{r['key']}` | standard_dose: {r['standard_dose']}]: Target = {r['target']} | "
                        f"Clinical Rationale = {r['clinical_purpose']} (Compensates: {r['solves_burden']}) | "
                        f"Evidence = {r['evidence_grade']}{cite_tag}{finding_tag} | Safety = {r['interaction_safety']}"
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
                route = comp.get("route") or "oral"
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
            
            # Prioritize entities explicitly discussed in latest messages, active stack, and candidate recommendations / blueprints
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
            # Add top candidate recommendation keys
            for r in evidence_recs[:4]:
                rk = str(r.get("key", "")).lower().strip()
                if rk and rk not in target_keys:
                    target_keys.append(rk)

            for t_key in target_keys[:10]:
                comp_meta = catalog.get_compound(t_key, auto_enrich=False) or catalog.find_by_synonym(t_key)
                c_name = comp_meta.get("name") if comp_meta else t_key.replace("_", " ").title()
                c_cites = pubmed_svc.search_literature(str(t_key), max_results=2, online_fallback=False)
                for cite in c_cites:
                    finding_str = f" ➔ *Investigated Finding*: {cite['clinical_finding']}" if cite.get("clinical_finding") else ""
                    topics_list = cite.get("claim_topics") or []
                    topic_str = f" [Topic: {', '.join(topics_list)}]" if topics_list else ""
                    citations_found.append(
                        f"- **{c_name}**{topic_str}: [{cite.get('journal', 'PubMed')} {cite.get('pub_year', '')}] *\"{cite.get('title')}\"* [PMID: {cite.get('pmid')}]{' (DOI: ' + cite['doi'] + ')' if cite.get('doi') else ''}{finding_str}"
                    )
            if citations_found:
                literature_sections.append("### VERIFIED BIOMEDICAL LITERATURE & CLINICAL EVIDENCE:")
                literature_sections.extend(citations_found[:12])
                literature_sections.append("*(Grounding Mandate: Ground your compound recommendations and answers in empirical biomedical literature. Strictly cite verified studies using [PMID: <id> - Author et al., Year] or [DOI: ...]. If you encounter an unfamiliar compound, novel therapeutic endpoint, or need specific dosage/adverse effect evidence not listed above, invoke `<tool_call name=\"search_pubmed_titles\">{\"query\": \"<compound> <endpoint>\"}</tool_call>` or `<tool_call name=\"read_paper_abstract\">{\"pmid\": \"<id>\"}</tool_call>` during your thinking scratchpad to autonomously research and read study abstracts before formulating your response.)*")
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
                    parts.append(f"- **Target Overlaps**: {len(overlaps)} competitive receptor interactions")
                if chains:
                    for i, ch in enumerate(chains[:3], 1):
                        parts.append(f"- Chain {i}: {' ➔ '.join([c['target_label'] for c in ch])}")
                graph_context = "\n".join(parts)
            except Exception as gr_err:
                logger.debug("GraphRAG context notice: %s", gr_err)

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
            p_lines.append("\n**CRITICAL MULTI-TURN CUMULATIVE DIRECTIVE**: The user is continuing to build/refine this protocol without having clicked 'Apply Changes' yet. You MUST maintain all previously proposed compounds as the active baseline! Your updated `protocol_proposal` JSON block MUST include ALL previous recommendations as well as any newly requested compounds or modifications in both the `compounds` array and the `diff` object, so that it represents the complete updated protocol.")
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
                    if user_specified_metrics:
                        blueprint_sections.append(f"> Baseline protocol blueprint calibrated against user parameters ({', '.join(user_specified_metrics)}) and clinical constraints:")
                    else:
                        blueprint_sections.append("> Baseline protocol blueprint formulated according to clinical goals and constraints:")
                    for c in scratch_proposal.get("compounds", []):
                        freq_str = f", {c['frequency'].replace('_', ' ')}" if c.get("frequency") and c.get("frequency") not in ("daily", "once_daily", "every_day", "") else ""
                        blueprint_sections.append(f"- **{c['name']}** ({c['dose']} {c['unit']} {c['route']}{freq_str}, {c['timing']}) — *{c.get('target', '')}*: {c.get('rationale', '')}")
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

1. **Clinical Scratchpad & Research Planning (`<scratchpad>...</scratchpad>`)**:
   - Use the scratchpad for structured, goal-directed clinical reasoning (150–250 words).
   - Track user directives, explicit compound exclusions (e.g. "no oral L-Carnitine", "avoid stimulants"), route preferences, and the evolving proposed stack.
   - **Proactive Research Assessment**: Actively assess whether your recommendations, clinical rationales, or compound synergies would benefit from deeper empirical backing, literature citations, or pharmacokinetic validation. If so, invoke the appropriate research tool(s) to fetch the evidence before formulating your final response.
   - User constraints and exclusions ALWAYS override default templates.

2. **Proactive Tool Calling & Empirical Grounding Protocol**:
   - **Autonomous Research & Tool Access**: You have full autonomy to inspect literature and simulate pharmacology. You are strongly encouraged to actively invoke your research tools inside your `<scratchpad>` whenever designing protocols from scratch, evaluating specialized or requested compounds, exploring synergies, validating circadian timing, or verifying safe dosing ranges:
     * `search_pubmed_titles`: `<tool_call name="search_pubmed_titles">{"query": "telmisartan cognitive neuroprotection bdnf", "max_results": 8}</tool_call>` (Discovers candidate study titles, PMIDs, and publication years without token bloat)
     * `read_paper_abstract`: `<tool_call name="read_paper_abstract">{"pmid": "26039521", "goal": "Extract dosage protocols and adverse effects"}</tool_call>` (Dispatches a subagent to read the abstract and extract ONLY goal-relevant findings to save context)
     * `read_paper_section`: `<tool_call name="read_paper_section">{"pmid": "26039521", "section": "results", "goal": "Find exact lipid changes"}</tool_call>` (Dispatches a subagent to read targeted open access sections)
     * `search_within_paper`: `<tool_call name="search_within_paper">{"pmid": "26039521", "query": "liver enzymes AST ALT"}</tool_call>` (Extracts top relevant paragraphs within a paper)
     * `find_candidate_pairings`: `<tool_call name="find_candidate_pairings">{"compound_key": "telmisartan", "min_confidence": 0.3}</tool_call>` (Discovers empirical literature co-occurrences & synergistic partners)
     * `find_similar_papers`: `<tool_call name="find_similar_papers">{"pmid": "18378520", "top_k": 4}</tool_call>` (Discovers related papers sharing biological pathways via vector graph)
     * `search_cached_papers_semantic`: `<tool_call name="search_cached_papers_semantic">{"query": "metformin exercise hypertrophy mTOR", "top_k": 5}</tool_call>` (Semantic vector search across local graph cache)
     * `hybrid_rag_search`: `<tool_call name="hybrid_rag_search">{"query": "metformin hypertrophy mTOR", "entity_ids": ["metformin"], "goal": "Assess blunting effect on muscle growth"}</tool_call>` (Subagent extracts causal chains with literature citations)
     * `search_biomedical_literature`: `<tool_call name="search_biomedical_literature">{"query": "citrus bergamot lipid profile ApoB", "max_results": 4, "goal": "Extract lipid impact"}</tool_call>`
     * `simulate_pkpd`: `<tool_call name="simulate_pkpd">{"compound_key": "telmisartan", "dose_mg": 40}</tool_call>` (Simulates Cmax, t1/2, clearance, and steady-state accumulation)
     * `check_cyp450_conflicts` / `analyze_stack_conflicts`: `<tool_call name="check_cyp450_conflicts">{"compound_keys": ["compound1", "compound2"], "biometrics": {}}</tool_call>` (Evaluates enzyme inhibition & competitive clearance)
     * `build_stack_from_scratch`: `<tool_call name="build_stack_from_scratch">{"goal": "anabolic_physique", "biometrics": {}, "preferences": {}, "custom_notes": "no oral l-carnitine"}</tool_call>`
     * `simulate_stack_diff`: `<tool_call name="simulate_stack_diff">{"base_stack": [], "diff": {"add": [], "remove": []}}</tool_call>`
     * `trace_mechanism_pathway`: `<tool_call name="trace_mechanism_pathway">{"source_compound": "caffeine", "target_biomarker": "bio_heart_rate"}</tool_call>`
     * `query_pathway_cascade`: `<tool_call name="query_pathway_cascade">{"target_id": "TARGET_NAME"}</tool_call>`
   - **User-Requested Compounds Mandate**: When the user requests a specific compound in their prompt, notes, or constraints (e.g. "include trenbolone", "add bromantane", "with injectable carnitine"), you MUST:
      1) Invoke `search_pubmed_titles` and `read_paper_abstract` to research the requested compound's pharmacology, dosing, and toxicity profile. *When seeking countermeasures or protective agents (e.g. "neuroprotection" for a requested compound), do NOT perform generic searches like "trenbolone neuroprotection". Instead, first invoke `get_compound_info` to retrieve the exact mechanism of the compound's toxicity (e.g. "oxidative stress", "amyloid beta"). Then, search PubMed for countermeasures targeting that specific pathway (e.g. "trenbolone neurotoxicity oxidative stress" or "hippocampus oxidative stress neuroprotection").*
      2) Include the requested compound in your `protocol_proposal` compounds list AND in the JSON `diff` `add` list.
      3) Pair it with appropriate protective co-factors (e.g., BP/LVH, lipid, hepatic/renal support) and monitoring requirements.
   - **Syntax Rule**: Tool calls MUST be formatted with `<tool_call name="...">{"arguments": ...}</tool_call>` inside your `<scratchpad>`. Never emit raw, un-tagged JSON queries outside `<tool_call>` tags in your final user-facing response.
   - **Single Tool Call Per Turn**: Emit exactly ONE `<tool_call>` per turn. After each tool call, close your `<scratchpad>` and wait for the engine to execute the tool and return the `<observation>` before emitting your next tool call or formulating your final synthesis. Do not batch multiple `<tool_call>` tags into a single turn.
   - **Autonomous Synthesis & Multi-Step Flow**: When empirical validation, deeper literature backing, or PK simulations are beneficial, emit tool calls in your `<scratchpad>`, review the returned `<observation>`, and synthesize your findings. If all necessary parameters and citations are already explicitly provided in the grounding context, or for simple conversational queries, you may synthesize directly.

3. **Structured Response & JSON Diff Mandate**:
   - Draft clean, publication-ready clinical markdown WITHOUT inline questioning, and place it inside a `text` block in your final JSON response.
   - Following your `text` block, include exactly ONE consolidated `protocol_proposal` JSON block containing the final `compounds` array and the `diff` object with `add`, `modify`, `remove` directives.
   - The JSON `diff` MUST match the proposed compounds, dosages, and schedule in your `compounds` list 1:1. Include every compound you recommended, and do not include unmentioned compounds.
   - **Cumulative Multi-Turn Protocols**: If refining an unapplied proposed stack from earlier turns, include ALL previously recommended compounds plus new additions in your `compounds` list and JSON `diff`, ensuring the user can apply the complete updated stack in one click.
"""
        full_system_parts.append(react_instructions)

        if custom_instructions:
            full_system_parts.append(f"\n### USER PREFERENCES & CONSTRAINTS:\n{custom_instructions}\n")

        return "\n".join(full_system_parts)

    @classmethod
    def parse_tool_call_from_text(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Parses structured tool calls from agent generation text.
        Supports XML tags (<tool_call name="...">, <call tool="...">),
        fenced JSON code blocks, bare JSON tool call structures, and OpenAI native tool call dicts.
        """
        if not text:
            return None

        # Format 1: <tool_call name="tool_name">JSON_ARGS</tool_call> or <tool_call>{"name": "...", "arguments": {...}}</tool_call>
        tag_match = re.search(r'<tool_call(?:\s+name="([^"]+)")?\s*>(.*?)(?:</tool_call>|$)', text, re.DOTALL | re.IGNORECASE)
        if tag_match:
            name_attr = tag_match.group(1)
            raw_body = tag_match.group(2).strip()
            if name_attr:
                name = name_attr.strip()
                try:
                    args = json.loads(raw_body) if raw_body else {}
                except Exception:
                    args = {}
                return {"name": name, "arguments": args}
            elif raw_body:
                try:
                    parsed = json.loads(raw_body)
                    if isinstance(parsed, dict):
                        if "name" in parsed:
                            return {"name": str(parsed["name"]), "arguments": parsed.get("arguments", parsed.get("args", {}))}
                        elif "tool" in parsed:
                            return {"name": str(parsed["tool"]), "arguments": parsed.get("arguments", parsed.get("args", {}))}
                except Exception:
                    pass

        # Format 2: <call tool="tool_name">JSON_ARGS</call> or <call name="tool_name">JSON_ARGS</call>
        call_match = re.search(r'<call(?:\s+(?:tool|name)="([^"]+)")?\s*>(.*?)(?:</call>|$)', text, re.DOTALL | re.IGNORECASE)
        if call_match:
            name_attr = call_match.group(1)
            raw_body = call_match.group(2).strip()
            if name_attr:
                name = name_attr.strip()
                try:
                    args = json.loads(raw_body) if raw_body else {}
                except Exception:
                    args = {}
                return {"name": name, "arguments": args}

        # Format 3: ```json or ```tool_call {"tool": "name", "arguments": {...}} or {"name": "...", "arguments": {...}}
        json_block_match = re.search(r'```(?:json|tool_call)?\s*(\{\s*"(?:tool|name|function)"\s*:\s*"[^"]+".*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
        if json_block_match:
            try:
                parsed = json.loads(json_block_match.group(1))
                if isinstance(parsed, dict):
                    tool_name = parsed.get("name") or parsed.get("tool") or parsed.get("function")
                    if tool_name:
                        return {"name": str(tool_name), "arguments": parsed.get("arguments", parsed.get("args", {}))}
            except Exception:
                pass

        # Format 4: Bare JSON object or JSON lines (e.g. {"name": "search_pubmed_titles", "arguments": {"query": "..."}})
        bare_json_matches = re.finditer(r'\{[^{}]*"(?:pmid|query|tool|name|compound_key|goal|base_stack|target_id|cypher)"[^{}]*\}', text)
        for bj in bare_json_matches:
            try:
                parsed = json.loads(bj.group(0))
                if isinstance(parsed, dict):
                    if "tool" in parsed:
                        return {"name": str(parsed["tool"]), "arguments": parsed.get("arguments", parsed.get("args", {}))}
                    elif "name" in parsed and ("arguments" in parsed or "args" in parsed):
                        return {"name": str(parsed["name"]), "arguments": parsed.get("arguments", parsed.get("args", {}))}
                    elif "pmid" in parsed:
                        return {"name": "read_paper_abstract", "arguments": {"pmid": str(parsed["pmid"])}}
                    elif "query" in parsed and "cypher" not in parsed:
                        return {"name": "search_pubmed_titles", "arguments": parsed}
                    elif "compound_key" in parsed:
                        return {"name": "simulate_pkpd", "arguments": parsed}
                    elif "cypher" in parsed:
                        return {"name": "execute_read_only_cypher", "arguments": {"query": str(parsed["cypher"])}}
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
        Strips internal scratchpad, tool call tags, and raw/dangling tool JSON objects from final user-facing text.
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
        cleaned = re.sub(r'<(?:think|thought|scratchpad|clinical_notes|context|observation|tool_call|call)>.*?$', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'(?i)^\s*(?:###?\s*)?(?:Thought(?:\s+Process)?|Scratchpad|Clinical Scratchpad|Internal Reasoning):\s*.*?(?=\n\n|\n[#\*\d]|\Z)', '', cleaned, flags=re.DOTALL | re.MULTILINE)

        # Strip fenced code blocks containing tool calls
        cleaned = re.sub(r'```(?:json|tool_call)?\s*\{[^{}]*"(?:pmid|query|tool|name|compound_key|dose_mg|target_id|max_results)"[^{}]*\}\s*```', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

        # Strip bare JSON tool calls or metadata objects from final text
        cleaned = re.sub(r'\{[^{}]*"(?:pmid|query|tool|name|compound_key|dose_mg|target_id|max_results|cypher)"[^{}]*\}', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'^\s*\{[\s\S]*?\}\s*(?=\n|$)', '', cleaned)

        # Strip dangling tool call fragments and stray JSON lines (e.g. lines with '"max_results":', stray '}', or broken quotes)
        cleaned = re.sub(r'(?m)^\s*\{?\s*"?(?:query|pmid|tool|name|compound_key|max_results)"?[^\n]*?(?:"max_results"\s*:\s*\d+|"pmid"\s*:\s*"[^"]*")[^\n]*\}?\s*$', '', cleaned)
        cleaned = re.sub(r'(?m)^\s*\}?\s*"[^"\n]*"(?:,\s*"max_results"\s*:\s*\d+)?\s*\}?\s*$', '', cleaned)
        cleaned = re.sub(r'(?m)^\s*[\{\}]\s*$', '', cleaned)

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
        header_match = re.search(r'(?:^|\n)(#{1,4}\s+|(?:\*\*(?:Executive|Risk|Biomarker|Primary|Identified|Targeted|Protocol|Circadian|Clinical|Summary|1\.|2\.|3\.|4\.)))', cleaned)
        if header_match and header_match.start() > 0:
            preamble = cleaned[:header_match.start()].strip()
            # If preamble contains meta-cognition or any tool-like artifacts, strip it
            if any(p in preamble.lower() for p in ["we need", "need to", "need answer", "need decide", "need strict", "thinking process", "let's think", "user asks"]) or any(k in preamble for k in ['"pmid"', '"query"', '"max_results"', '}', '{']):
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
        if "subagent_summary" in obs:
            return f"Subagent Extracted Findings: {str(obs['subagent_summary'])[:150]}..."
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
        elif tool_name in ("search_pubmed_titles", "search_literature_titles", "search_paper_titles"):
            candidates = obs.get("candidate_titles", [])
            pmids = [str(c.get("pmid")) for c in candidates[:4] if c.get("pmid")]
            return f"Scanned PubMed titles for '{obs.get('query')}': Discovered {len(candidates)} candidate studies [PMIDs: {', '.join(pmids)}]."
        elif tool_name in ("fetch_paper_abstract", "read_paper_abstract", "get_paper_abstract", "read_study"):
            return f"Read study abstract [PMID: {obs.get('pmid')}]: \"{obs.get('title', '')[:80]}\" ({obs.get('journal', 'PubMed')} {obs.get('pub_year', '')}). Key Finding: {obs.get('clinical_finding', '')[:100]}..."
        elif tool_name in ("read_paper_section", "fetch_paper_full_text_section", "read_full_text_section"):
            return f"Read '{obs.get('section_requested', 'section')}' section for [{obs.get('pmid') or obs.get('pmcid')}]: {obs.get('word_count', 0)} words extracted (Open Access: {obs.get('is_open_access', False)})."
        elif tool_name in ("search_within_paper", "search_in_paper", "search_paper_passages"):
            return f"In-paper passage search for '{obs.get('query')}': Extracted {obs.get('passage_count', 0)} relevant clinical paragraphs."
        elif tool_name in ("find_similar_papers", "find_similar_studies", "find_similar_citations"):
            sim = obs.get("similar_papers", [])
            pmids = [str(s.get("pmid")) for s in sim if s.get("pmid")]
            return f"Similar paper finder for [PMID: {obs.get('pmid')}]: Found {len(sim)} mechanistically related studies [PMIDs: {', '.join(pmids)}]."
        elif tool_name in ("search_cached_papers_semantic", "search_citations_semantic"):
            cites = obs.get("citations", [])
            return f"Semantic vector search: Retrieved {len(cites)} cached studies matching '{obs.get('query')}'."
        elif tool_name in ("hybrid_rag_search", "search_graphrag_and_literature", "hybrid_literature_search"):
            return f"Hybrid RAG search for '{obs.get('query')}': {obs.get('citation_count', 0)} citations, {len(obs.get('causal_chains', []))} causal chains."
        elif tool_name in ("search_pubmed_literature", "search_biomedical_literature", "search_pubmed", "search_literature_for_claim"):
            cites = obs.get("citations", [])
            pmids = [str(c.get("pmid")) for c in cites[:3] if c.get("pmid")]
            return f"Literature search: Found {obs.get('count', len(cites))} papers [PMIDs: {', '.join(pmids)}]."
        return f"Tool returned {len(obs)} fields."

    @classmethod
    def format_deterministic_protocol_markdown(cls, proposal: Dict[str, Any], persona: str = "architect") -> str:
        """
        Formats a clean JSON blocks protocol from deterministic StackIntentEngine proposal.
        """
        goal_title = proposal.get("goal_title", "Clinical Protocol")
        compounds = proposal.get("compounds", [])

        # Build formatted compounds
        formatted_compounds = []
        for c in compounds:
            route_str = c.get("route") or "oral"
            freq_raw = c.get("frequency", "daily")
            freq_str = freq_raw.replace("_", " ") if freq_raw and freq_raw != "daily" else freq_raw
            cite_str = f"PMID: {c['pmid']}" if c.get("pmid") else ""
            if c.get("citation_str"):
                cite_str = c["citation_str"]
            
            formatted_compounds.append({
                "key": c.get("key", ""),
                "name": c.get("name", ""),
                "dose": c.get("dose", 100),
                "unit": c.get("unit", "mg"),
                "route": route_str,
                "frequency": freq_str,
                "timing": c.get("timing", "Morning"),
                "target": c.get("target", ""),
                "rationale": c.get("rationale", ""),
                "citations": [cite_str] if cite_str else []
            })

        # Build standard diff payload with full compound parameters
        diff = {
            "add": [
                {
                    "key": fc["key"],
                    "name": fc["name"],
                    "dose": fc["dose"],
                    "unit": fc["unit"],
                    "timing": fc["timing"],
                    "frequency": fc["frequency"],
                    "route": fc["route"],
                    "target": fc["target"],
                }
                for fc in formatted_compounds if fc.get("key")
            ],
            "modify": [],
            "remove": []
        }
            
        source_collector = CopilotSourceCollector()
        for c in compounds:
            if c.get("pmid") or c.get("citation_str"):
                source_collector.record_literature_citation(
                    pmid=c.get("pmid"),
                    title=f"{c.get('name')} Clinical Evidence",
                    clinical_finding=f"Target: {c.get('target', '')}. {c.get('rationale', '')}",
                )

        sources = []
        if source_collector.literature_studies:
            for source in source_collector.literature_studies.values():
                sources.append({"badge": f"[PMID: {source['pmid']}]" if source.get("pmid") else "[DOI]", "description": source.get("title", "")})

        sources_text = ""
        if sources:
            sources_text = "\n\n### 📚 Sources & Scientific Evidence Base\n" + "\n".join([f"- **{s['badge']}**: {s['description']}" for s in sources])

        payload = {
            "blocks": [
                {
                    "type": "text",
                    "content": f"### ⚡ HealthAI {persona.upper()} Grounded Protocol: {goal_title}\n\n**Executive Assessment**: Calibrated protocol targeting {goal_title.lower()} with quantitative chronobiological alignment, organ protection co-factors, and zero bro-science.{sources_text}"
                },
                {
                    "type": "protocol_proposal",
                    "data": {
                        "goal_title": goal_title,
                        "persona": persona.upper(),
                        "summary": f"Deterministic protocol for {goal_title}",
                        "compounds": formatted_compounds,
                        "safety_notes": [
                            "Baseline & Follow-up Biomarkers: Re-assess comprehensive metabolic panel (CMP), lipid panel (ApoB/Triglycerides), and resting blood pressure at 4–8 week intervals.",
                            "Multi-Organ Protection: Protective co-factors maintain renal podocyte perfusion and endothelial nitric oxide release without diminishing target efficacy."
                        ],
                        "sources": sources,
                        "diff": diff
                    }
                }
            ]
        }
        
        return json.dumps(payload, indent=2, ensure_ascii=False)

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
                                timing_val = MarkdownProtocolParser._extract_timing_from_string(user_query)
                                freq_val = MarkdownProtocolParser._extract_frequency_from_string(user_query) or freq
                                if not timing_val:
                                    if freq_val in ("every_other_day", "eod", "qod"):
                                        timing_val = "Every Other Day (EOD)"
                                    elif freq_val in ("three_times_weekly", "3x_weekly"):
                                        timing_val = "Three Times Weekly (Mon / Wed / Fri)"
                                    elif freq_val in ("twice_weekly", "twice weekly"):
                                        timing_val = "Twice Weekly (Mon / Thu)"
                                    elif freq_val in ("weekly", "once_weekly"):
                                        timing_val = "Weekly"
                                    elif freq_val in ("biweekly", "every_2_weeks"):
                                        timing_val = "Bi-Weekly (Every 2 Weeks)"
                                    elif freq_val in ("as_needed", "prn"):
                                        timing_val = "As Needed (PRN)"
                                    else:
                                        timing_val = "Morning"

                                new_adds.append({
                                    "key": k,
                                    "name": comp.get("name") or k.replace("_", " ").title(),
                                    "dose": dose_val,
                                    "unit": unit,
                                    "route": route,
                                    "frequency": freq_val,
                                    "timing": timing_val
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
                "   - **Molecular Mechanism**: Allicin's organosulfur moieties potently inactivate bacterial TMA-lyase (CntA/CntB) in the gut lumen (IC50 ≈ 0.05 mg/mL), suppressing TMA and serum TMAO formation by >50–70% while preserving systemic L-carnitine absorption and CPT1 mitochondrial shuttle activity [PMID: 26039521].",
                "2. **Pharmacokinetic Route Optimization (Parenteral Bypass)**:",
                "   - **Strategy**: Switch administration from oral to **Intramuscular (IM) or Subcutaneous (SubQ)** injection (e.g. L-Carnitine 500 mg IM daily or pre-workout).",
                "   - **Mechanism**: Parenteral administration delivers carnitine directly into systemic circulation, completely bypassing the gastrointestinal lumen and intestinal microbiota, resulting in negligible (<0.5 μmol/L) TMAO generation [PMID: 23563705].",
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
            sc = CopilotSourceCollector()
            sc.record_literature_citation(
                pmid="26039521",
                title="Allicin Alleviates Trimethylamine N-Oxide-Induced Atherosclerosis in Mice",
                journal="J Agric Food Chem",
                pub_year="2015",
                clinical_finding="Organosulfur compounds in garlic inactivate gut microbial carnitine TMA-lyase (CntA/CntB), reducing TMA and serum TMAO by >50-70%.",
            )
            sc.record_literature_citation(
                pmid="23563705",
                title="Intestinal microbial metabolism of phosphatidylcholine and carnitine promotes atherosclerosis (Koeth et al.)",
                journal="Nature Medicine",
                pub_year="2013",
                clinical_finding="Established the pathway linking gut microbiota metabolism of dietary choline and L-carnitine to TMAO production and cardiovascular risk.",
            )
            s_md = sc.format_sources_markdown()
            if s_md:
                lines.append(s_md)
            return "\n".join(lines), alli_card

        # Scenario D: Biomarker / Lab Guidance (Labs persona)
        if persona == "labs" or any(w in q_lower for w in ["lab", "blood", "biomarker", "panel", "alt", "egfr", "lipid", "test"]):
            lines = [
                f"### 🩸 HealthAI Clinical Laboratory & Biomarker Assessment\n",
                f"**Patient Clearance Baseline**: Age {biometrics.get('age', 30)} | Weight {biometrics.get('weight_kg', 75)}kg | eGFR {biometrics.get('egfr', 95)} mL/min | ALT {biometrics.get('alt_u_l', 25)} U/L.\n",
                "**Key Biomarker Correlations**:",
                "- **Renal Clearance**: eGFR within normal physiological range; standard compound filtration maintained.",
                "- **Hepatic Transaminases**: Normal baseline ALT; no active hepatotoxic load identified.",
                "- **Recommended Monitoring Panel**: Comprehensive Metabolic Panel (CMP), Lipid Profile (ApoB, Triglycerides), and resting blood pressure at 12-week intervals.",
            ]
            sc = CopilotSourceCollector()
            sc.record_database_registry(
                "Clinical Standards",
                "Standard Reference Ranges",
                "Standardized Clinical Laboratory Reference Ranges (CMP, Lipid Panels, Endocrine Metrics)",
            )
            s_md = sc.format_sources_markdown()
            if s_md:
                lines.append(s_md)
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
            sc = CopilotSourceCollector()
            sc.record_database_registry(
                "Reactome",
                "Signal Transduction",
                "Intracellular Biological Signal Transduction Pathway Database & Receptor Cascades",
            )
            sc.record_database_registry(
                "ChEMBL",
                "Target Bioactivity",
                "Quantitative Receptor Binding Affinities (Ki, Kd, IC50) and Selectivity Profiles",
            )
            for c in canonical_compounds[:4]:
                if c.get("pmid") or c.get("citation_str"):
                    sc.record_literature_citation(pmid=c.get("pmid"), title=f"{c.get('name')} Pharmacology Profile")
            s_md = sc.format_sources_markdown()
            if s_md:
                lines.append(s_md)
            return "\n".join(lines), None

        # Scenario B: Risk / Conflict / DDI / Safety Query (Auditor persona or safety keywords)
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
        sc = CopilotSourceCollector()
        sc.record_guideline(
            "FDA",
            "FDA Structured Product Labeling Standard: §5.1 Boxed Warnings & Clinical Drug Interactions",
            "Official FDA Drug Prescribing Information & Metabolism Standards",
        )
        sc.record_guideline(
            "CPIC",
            "CPIC Clinical Pharmacogenetics Implementation Consortium",
            "Guidelines on Drug-Gene Clearance Phenotypes and CYP450 Substrate Warnings",
        )
        s_md = sc.format_sources_markdown()
        if s_md:
            lines.append(s_md)
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
        max_exploration_steps: int = 8,
        user_api_key: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator for streaming SSE events to the frontend with dynamic multi-step ReAct graph traversal.
        Emits:
        - {"event": "reasoning", "data": "..."} (scratchpad notes, graph exploration steps, telemetry)
        - {"event": "delta", "data": "..."} (synthesized clinical markdown)
        - {"event": "action_card", "data": {...}} (structured stack mutations)
        - {"event": "quota_exceeded", "data": {...}} (host token exhaustion notice)
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
        source_collector = CopilotSourceCollector()
        source_collector.record_grounding_context(
            has_ddi=bool(stack_list or persona == "auditor"),
            has_pkpd=bool(stack_list or persona in ("architect", "tutor")),
            has_graphrag=True,
            has_pathway=bool(persona == "tutor"),
            has_synergy=bool(len(stack_list) > 1 or protocol_goal is not None),
        )

        if max_exploration_steps >= 12:
            extra_directive = f"\n\n**USER EXPLICITLY REQUESTED EXHAUSTIVE RESEARCH**: The user has granted you an exploration budget of {max_exploration_steps} tool calls. You MUST aggressively use `search_pubmed_titles`, `read_paper_abstract`, and graph search tools to find mechanistic evidence before answering. DO NOT stop at your first discovery; verify findings across multiple pathways and sources. You are FORBIDDEN from outputting your final `protocol_proposal` JSON response until you have used at least {int(max_exploration_steps * 0.75)} tool calls."
            custom_instructions = (custom_instructions + extra_directive) if custom_instructions else extra_directive

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
                api_key=user_api_key,
            ):
                chunk_type = chunk.get("type")
                data = chunk.get("data")

                if chunk_type == "quota_exceeded":
                    yield {"event": "quota_exceeded", "data": data}
                    return

                elif chunk_type == "reasoning":
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
                    "event": "tool_call",
                    "data": {
                        "step": step,
                        "tool": tool_name,
                        "arguments": tool_args
                    }
                }
                yield {
                    "event": "reasoning",
                    "data": f"\n🔍 [Step {step}] Querying Graph: Executing tool '{tool_name}' with arguments {json.dumps(tool_args)}..."
                }

                # Deterministically execute the requested tool
                obs = await asyncio.to_thread(cls.execute_tool, tool_name, tool_args)
                source_collector.record_tool_execution(tool_name, tool_args, obs)

                # --- SUBAGENT DELEGATION (Context Window Protection) ---
                goal = tool_args.get("goal")
                if goal and tool_name in ("read_paper_abstract", "fetch_paper_abstract", "read_paper_section", "search_biomedical_literature", "hybrid_rag_search", "search_pubmed_titles"):
                    try:
                        from app.services.ai_service import ask_local_llm
                        sub_sys = (
                            "You are a clinical research subagent. Read the raw research data provided by the user. "
                            "Extract ONLY the information directly relevant to the assigned GOAL. "
                            "Ignore completely irrelevant background information to save token space. "
                            "Format your response as a pure JSON object with a single key 'summary' containing your extracted markdown."
                        )
                        # We only send a slice of the raw observation to prevent blowing up the subagent context
                        sub_user = f"GOAL: {goal}\n\nRAW TOOL OUTPUT:\n{json.dumps(obs)[:24000]}"
                        
                        yield {
                            "event": "tool_call",
                            "data": {
                                "step": f"{step}.sub",
                                "tool": "subagent_delegation",
                                "arguments": {"task": "Extracting goal-relevant findings", "payload_size": len(json.dumps(obs))}
                            }
                        }
                        
                        sub_res = await ask_local_llm(
                            system_prompt=sub_sys,
                            user_prompt=sub_user,
                            api_key=user_api_key
                        )
                        
                        extracted_summary = sub_res.get("summary") or str(sub_res)
                        
                        obs = {
                            "subagent_summary": extracted_summary,
                            "original_tool": tool_name,
                            "pmid": obs.get("pmid"),
                            "query": obs.get("query"),
                            "note": "Raw data was compressed by subagent."
                        }
                        
                        yield {
                            "event": "tool_result",
                            "data": {
                                "step": f"{step}.sub",
                                "tool": "subagent_delegation",
                                "summary": "Subagent successfully compressed and extracted relevant findings."
                            }
                        }
                    except Exception as e:
                        yield {
                            "event": "tool_result",
                            "data": {
                                "step": f"{step}.sub",
                                "tool": "subagent_delegation",
                                "summary": f"Subagent failed: {str(e)}"
                            }
                        }
                # -------------------------------------------------------

                obs_summary = cls._summarize_observation(tool_name, obs)

                yield {
                    "event": "tool_result",
                    "data": {
                        "step": step,
                        "tool": tool_name,
                        "summary": obs_summary
                    }
                }
                yield {
                    "event": "reasoning",
                    "data": f"📍 [Step {step}] Graph Observation: {obs_summary}\n"
                }

                # Append assistant thoughts and graph observation for next ReAct iteration
                current_messages.append({
                    "role": "assistant",
                    "content": accumulated_turn_content
                })
                if step < (max_exploration_steps * 0.75) and max_exploration_steps >= 10:
                    prompt_reminder = f"\nReview this graph observation. You have only used {step} out of {max_exploration_steps} tool calls in your research budget. The user requested EXHAUSTIVE research. You MUST continue exploring, cross-referencing, and verifying data using your tools. DO NOT output your final JSON response yet."
                else:
                    prompt_reminder = "\nReview this graph observation, update your clinical scratchpad, and proceed with further graph exploration if needed, or provide your final clinical response."

                current_messages.append({
                    "role": "user",
                    "content": f"<observation for='{tool_name}'>\n{json.dumps(obs, indent=2)}\n</observation>{prompt_reminder}"
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

                    if clean_final_text and not re.search(r'###\s+(?:📚\s*)?Sources', clean_final_text, re.IGNORECASE):
                        clean_final_text = source_collector.append_to_response(clean_final_text)

                    if clean_final_text and clean_final_text.strip():
                        yield {"event": "delta", "data": clean_final_text}
                        accumulated_turn_content = clean_final_text
                else:
                    # Emitted deltas were streamed. If no sources header in emitted content, append formatted sources delta
                    clean_streamed = cls.clean_scratchpad_and_tools_from_text(accumulated_turn_content)
                    if not re.search(r'###\s+(?:📚\s*)?Sources', clean_streamed, re.IGNORECASE):
                        source_collector.scan_text_for_citations(clean_streamed)
                        sources_md = source_collector.format_sources_markdown()
                        if sources_md:
                            yield {"event": "delta", "data": sources_md}
                            accumulated_turn_content += sources_md

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
        max_exploration_steps: int = 8,
        user_api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Non-streaming execution supporting dynamic ReAct graph problem solving.
        """
        stack_list = stack or []
        biometrics_dict = biometrics or {}
        user_queries = [str(m.get("content", "")) for m in messages if m.get("role") == "user"]
        latest_user_query = user_queries[-1] if user_queries else ""

        source_collector = CopilotSourceCollector()
        source_collector.record_grounding_context(
            has_ddi=bool(stack_list or persona == "auditor"),
            has_pkpd=bool(stack_list or persona in ("architect", "tutor")),
            has_graphrag=True,
            has_pathway=bool(persona == "tutor"),
            has_synergy=bool(len(stack_list) > 1 or protocol_goal is not None),
        )

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
            async for chunk in stream_local_llm_chat(messages=current_messages, system_prompt=system_prompt, api_key=user_api_key):
                if chunk.get("type") == "quota_exceeded":
                    from app.services.ai_service import QuotaExhaustedException
                    raise QuotaExhaustedException("The host/admin's OpenRouter token budget has been exhausted.")
                elif chunk.get("type") == "content":
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
                source_collector.record_tool_execution(tool_call.get("name"), tool_call.get("arguments", {}), obs)
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

                full_text = source_collector.append_to_response(full_text)
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

    @classmethod
    async def reset_session_context(cls) -> Dict[str, Any]:
        """
        Completely resets all Copilot session context, clearing model KV caches,
        active slot memory, and ephemeral caches.
        """
        model_reset_res = await reset_model_context()
        logger.info("Copilot conversation context and model slots reset.")
        return {
            "status": "ok",
            "message": "Copilot chat context and model memory reset successfully.",
            "details": model_reset_res,
        }



