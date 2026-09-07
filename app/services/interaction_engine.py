from __future__ import annotations

import math
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.catalog_service import CatalogService
from app.services.chemical_structure_engine import is_17a_alkylated, is_19nor_steroid
from app.knowledge_graph.graph import get_demographic_calibrated_reference_range

# Clinical within-subject biological variation (CV_w) baselines per EFLM / Westgard biological variation specifications
BIOMARKER_BIOLOGICAL_CV_MAP: Dict[str, float] = {
    # Tight homeostatic parameters (low biological CV)
    "bio_blood_pressure": 0.06,
    "bio_systolic_blood_pressure": 0.06,
    "bio_diastolic_blood_pressure": 0.06,
    "bio_serum_potassium": 0.05,
    "bio_potassium": 0.05,
    "bio_serum_sodium": 0.03,
    "bio_sodium": 0.03,
    "bio_serum_calcium": 0.04,
    "bio_hematocrit": 0.05,
    "bio_hemoglobin": 0.05,
    "bio_platelets": 0.08,
    "bio_egfr": 0.08,
    "bio_serum_creatinine": 0.08,
    "bio_cystatin_c": 0.08,
    "bio_blood_glucose": 0.07,
    "bio_fasting_glucose": 0.07,
    "bio_hba1c": 0.05,
    "bio_resting_heart_rate": 0.07,
    "bio_heart_rate": 0.07,
    # Moderate variability
    "bio_hdl_c": 0.10,
    "bio_hdl": 0.10,
    "bio_ldl_c": 0.10,
    "bio_ldl": 0.10,
    "bio_apob": 0.10,
    "bio_total_cholesterol": 0.09,
    "bio_triglycerides": 0.16,
    "bio_alt": 0.15,
    "bio_ast": 0.15,
    "bio_ggt": 0.16,
    "bio_alp": 0.10,
    "bio_total_bilirubin": 0.18,
    "bio_gsh_redox_ratio": 0.14,
    "bio_mda": 0.15,
    "bio_tsh": 0.14,
    "bio_free_t3": 0.12,
    "bio_free_t4": 0.10,
    # Pulsatile endocrine & inflammatory
    "bio_estradiol": 0.18,
    "bio_estrone": 0.18,
    "bio_dht": 0.18,
    "bio_dihydrotestosterone": 0.18,
    "bio_testosterone": 0.18,
    "bio_free_testosterone": 0.20,
    "bio_prolactin": 0.18,
    "bio_cortisol": 0.22,
    "bio_luteinizing_hormone": 0.20,
    "bio_lh": 0.20,
    "bio_follicle_stimulating_hormone": 0.18,
    "bio_fsh": 0.18,
    "bio_shbg": 0.14,
    "bio_crp": 0.22,
    "bio_hs_crp": 0.22,
    "bio_tmao": 0.20,
    "bio_qtc": 0.04,
    # Metabolic, Wearable & Neurotrophic
    "bio_metabolic_rate": 0.05,
    "bio_bmr": 0.05,
    "bio_fasting_insulin": 0.18,
    "bio_homa_ir": 0.18,
    "bio_bdnf": 0.15,
    "bio_ngf": 0.15,
    "bio_acetylcholine": 0.14,
    "bio_synaptic_plasticity": 0.12,
    "bio_igf1": 0.14,
    "bio_nad_plus": 0.16,
    "bio_sirtuin_activity": 0.14,
    "bio_hrv": 0.15,
}
DEFAULT_BIOMARKER_CV: float = 0.12



class ActionType(str, Enum):
    AGONIST = "agonist"
    ANTAGONIST = "antagonist"
    INVERSE_AGONIST = "inverse_agonist"
    INHIBITOR = "inhibitor"
    PAM = "pam"  # Positive Allosteric Modulator
    NAM = "nam"  # Negative Allosteric Modulator
    SUBSTRATE = "substrate"
    INDUCER = "inducer"
    MODULATOR = "modulator"
    ENHANCER = "enhancer"
    COFACTOR = "cofactor"
    OTHER = "other"


def normalize_action(action: Any) -> ActionType:
    """Deterministically normalizes target pharmacological actions into structured ActionType enums."""
    if action is None:
        return ActionType.OTHER
    if isinstance(action, ActionType):
        return action

    a_str = str(action).strip().lower()
    if not a_str:
        return ActionType.OTHER

    # 1. Antagonists & Blockers (checked before agonist to eliminate substring overlaps)
    if any(k in a_str for k in ["antagonist", "blocker", "inverse antagonist"]):
        return ActionType.ANTAGONIST
    if "inverse" in a_str and "agonist" in a_str:
        return ActionType.INVERSE_AGONIST

    # 2. Agonists & Activators
    if any(k in a_str for k in ["agonist", "activator", "stimulator", "opener"]):
        return ActionType.AGONIST

    # 3. Inhibitors & Suppressors
    if any(k in a_str for k in ["inhibitor", "inhibition", "suppressor"]):
        return ActionType.INHIBITOR

    # 4. Allosteric Modulators
    if "positive allosteric" in a_str or a_str == "pam":
        return ActionType.PAM
    if "negative allosteric" in a_str or a_str == "nam":
        return ActionType.NAM

    # 5. Metabolism / PK / Enzyme Enhancers / Co-factors
    if "substrate" in a_str:
        return ActionType.SUBSTRATE
    if "inducer" in a_str or "induction" in a_str:
        return ActionType.INDUCER
    if "enhancer" in a_str or "enhancement" in a_str:
        return ActionType.ENHANCER
    if "cofactor" in a_str or "co-factor" in a_str:
        return ActionType.COFACTOR
    if "modulator" in a_str:
        return ActionType.MODULATOR

    return ActionType.OTHER


_TARGET_GENE_SYNONYMS: Dict[str, str] = {
    # Adrenergic
    "adrb1": "ADRB1", "beta-1": "ADRB1", "beta 1": "ADRB1", "p08588": "ADRB1",
    "adrb2": "ADRB2", "beta-2": "ADRB2", "beta 2": "ADRB2", "p07550": "ADRB2",
    "adra1a": "ADRA1A", "alpha-1a": "ADRA1A", "alpha-1": "ADRA1A", "p35348": "ADRA1A",
    "adra2a": "ADRA2A", "alpha-2a": "ADRA2A", "alpha-2": "ADRA2A", "p08913": "ADRA2A",
    "adra2b": "ADRA2B", "alpha-2b": "ADRA2B", "p18089": "ADRA2B",
    "adra2c": "ADRA2C", "alpha-2c": "ADRA2C", "p18825": "ADRA2C",
    # Purinergic / Adenosine
    "adora1": "ADORA1", "adenosine a1": "ADORA1", "p30542": "ADORA1",
    "adora2a": "ADORA2A", "adenosine a2a": "ADORA2A", "p29274": "ADORA2A",
    "pde5a": "PDE5A", "pde5": "PDE5A", "phosphodiesterase 5": "PDE5A",
    "pde4": "PDE4", "pde3": "PDE3", "phosphodiesterase": "PDE_NONSPECIFIC",
    # Renin-Angiotensin-Aldosterone & Renal
    "agtr1": "AGTR1", "angiotensin ii type-1": "AGTR1", "at1": "AGTR1", "p30556": "AGTR1",
    "ace": "ACE", "angiotensin-converting enzyme": "ACE", "p12821": "ACE",
    "nr3c2": "NR3C2", "mineralocorticoid receptor": "NR3C2", "aldosterone receptor": "NR3C2", "p08235": "NR3C2",
    "scnn1a": "ENAC", "enac": "ENAC", "epithelial sodium channel": "ENAC",
    "ren": "RENIN", "renin": "RENIN",
    # Cardiac Electrophysiology & Calcium
    "kcnh2": "KCNH2", "herg": "KCNH2", "delayed rectifier": "KCNH2", "q12809": "KCNH2",
    "cacna1c": "CACNA1C", "cav1.2": "CACNA1C", "l-type calcium": "CACNA1C", "q13936": "CACNA1C",
    "atp1a1": "ATP1A1", "sodium-potassium-transporting atpase": "ATP1A1", "p05023": "ATP1A1",
    # Serotonergic & Neurotransmitters
    "slc6a4": "SLC6A4", "sert": "SLC6A4", "serotonin transporter": "SLC6A4", "p31645": "SLC6A4",
    "htr1a": "HTR1A", "5-ht1a": "HTR1A", "p08908": "HTR1A",
    "htr1b": "HTR1B", "5-ht1b": "HTR1B", "p28222": "HTR1B",
    "htr1d": "HTR1D", "5-ht1d": "HTR1D", "p28221": "HTR1D",
    "htr2a": "HTR2A", "5-ht2a": "HTR2A", "p28223": "HTR2A",
    "maoa": "MAOA", "monoamine oxidase a": "MAOA", "p21397": "MAOA",
    "maob": "MAOB", "monoamine oxidase b": "MAOB", "p27338": "MAOB",
    # Cholinergic
    "chrm1": "CHRM1", "muscarinic acetylcholine receptor m1": "CHRM1",
    "chrm2": "CHRM2", "muscarinic acetylcholine receptor m2": "CHRM2",
    "chrm3": "CHRM3", "muscarinic acetylcholine receptor m3": "CHRM3",
    "chrm": "CHRM", "muscarinic": "CHRM",
    # Sedative / Opioid
    "oprm1": "OPRM1", "mu-type opioid receptor": "OPRM1", "p35372": "OPRM1",
    "gabra1": "GABRA1", "gaba-a": "GABRA1", "p14867": "GABRA1",
    "hcrtr1": "HCRTR1", "orexin receptor": "HCRTR1",
    # Metabolic & Endocrine
    "insr": "INSR", "insulin receptor": "INSR", "p06213": "INSR",
    "abcc8": "ABCC8", "sur1": "ABCC8", "katp": "ABCC8", "q09428": "ABCC8",
    "glp1r": "GLP1R", "glucagon-like peptide 1 receptor": "GLP1R", "p43220": "GLP1R",
    "slc5a2": "SLC5A2", "sglt2": "SLC5A2", "p31639": "SLC5A2",
    "pparg": "PPARG", "peroxisome proliferator-activated receptor gamma": "PPARG", "p37231": "PPARG",
    "ar": "AR", "androgen receptor": "AR", "p10275": "AR",
    "ghr": "GHR", "growth hormone receptor": "GHR", "p10912": "GHR",
    # Hemostasis & Coagulation
    "f10": "F10", "coagulation factor x": "F10", "p00742": "F10",
    "f2": "F2", "thrombin": "F2", "p00734": "F2",
    "vkorc1": "VKORC1", "vitamin k epoxide reductase": "VKORC1", "q9bq51": "VKORC1",
    "p2ry12": "P2RY12", "p2y12": "P2RY12", "q9h244": "P2RY12",
    "ptgs1": "PTGS1", "cox-1": "PTGS1", "cyclooxygenase-1": "PTGS1", "p23219": "PTGS1",
    "ptgs2": "PTGS2", "cox-2": "PTGS2", "cyclooxygenase-2": "PTGS2", "p35354": "PTGS2",
    # Nootropics, Neurotrophins & Research Chemicals
    "gria1": "GRIA1", "gria2": "GRIA1", "ampa": "GRIA1", "ampa receptor": "GRIA1", "ampakine": "GRIA1", "p42261": "GRIA1",
    "grin1": "GRIN1", "grin2a": "GRIN1", "grin2b": "GRIN1", "nmda": "GRIN1", "nmda receptor": "GRIN1", "q05586": "GRIN1",
    "ntrk2": "NTRK2", "trkb": "NTRK2", "bdnf receptor": "NTRK2", "q16620": "NTRK2",
    "ntrk1": "NTRK1", "trka": "NTRK1", "ngf receptor": "NTRK1", "p04629": "NTRK1",
    "met": "MET", "hgf receptor": "MET", "c-met": "MET", "p08581": "MET",
    "slc6a3": "SLC6A3", "dat": "SLC6A3", "dopamine transporter": "SLC6A3", "q01959": "SLC6A3",
    "slc6a2": "SLC6A2", "net": "SLC6A2", "norepinephrine transporter": "SLC6A2", "p23975": "SLC6A2",
    "th": "TH", "tyrosine hydroxylase": "TH", "p07101": "TH",
    "chrna7": "CHRNA7", "alpha-7 nachr": "CHRNA7", "alpha7 nachr": "CHRNA7", "p36544": "CHRNA7",
    "sigmar1": "SIGMAR1", "sigma-1": "SIGMAR1", "sigma-1 receptor": "SIGMAR1", "q99720": "SIGMAR1",
    "gabbr1": "GABBR1", "gabbr2": "GABBR1", "gaba-b": "GABBR1", "gaba-b receptor": "GABBR1", "q92540": "GABBR1",
    "slc5a7": "SLC5A7", "hacu": "SLC5A7", "choline transporter": "SLC5A7", "q9gzv3": "SLC5A7",
    "ghsr": "GHSR", "ghrelin receptor": "GHSR", "growth hormone secretagogue receptor": "GHSR", "q92847": "GHSR",
    "pgr": "PGR", "progesterone receptor": "PGR", "p06401": "PGR",
    "nr3c1": "NR3C1", "glucocorticoid receptor": "NR3C1", "p04150": "NR3C1",
    "esr1": "ESR1", "estrogen receptor alpha": "ESR1", "er-alpha": "ESR1", "p03372": "ESR1",
    "esr2": "ESR2", "estrogen receptor beta": "ESR2", "er-beta": "ESR2", "q92731": "ESR2",
    "thra": "THRA", "thyroid hormone receptor alpha": "THRA", "nr1a1": "THRA", "p10827": "THRA",
    "thrb": "THRB", "thyroid hormone receptor beta": "THRB", "nr1a2": "THRB", "p10828": "THRB",
    "cyp19a1": "CYP19A1", "aromatase": "CYP19A1", "p11511": "CYP19A1",
    "srd5a1": "SRD5A1", "srd5a2": "SRD5A2", "5-alpha reductase": "SRD5A2",
    "shbg": "SHBG", "sex hormone-binding globulin": "SHBG", "p04278": "SHBG",
    "lhcgr": "LHCGR", "luteinizing hormone receptor": "LHCGR", "lh receptor": "LHCGR",
    "fshr": "FSHR", "follicle stimulating hormone receptor": "FSHR",
    "tshr": "TSHR", "thyrotropin receptor": "TSHR", "thyroid stimulating hormone receptor": "TSHR",
    # Immunology, Cytokines & Checkpoints
    "tnf": "TNF", "tumor necrosis factor": "TNF", "tnf-alpha": "TNF", "p01375": "TNF",
    "pdcd1": "PDCD1", "pd-1": "PDCD1", "programmed cell death protein 1": "PDCD1", "q15116": "PDCD1",
    "cd274": "CD274", "pd-l1": "CD274", "q9nzq7": "CD274",
    "ctla4": "CTLA4", "ctla-4": "CTLA4", "p16410": "CTLA4",
    "ms4a1": "MS4A1", "cd20": "MS4A1", "p11836": "MS4A1",
    "il6r": "IL6R", "interleukin-6 receptor": "IL6R", "p08887": "IL6R",
    "il6": "IL6", "interleukin-6": "IL6", "p05231": "IL6",
    "il1b": "IL1B", "interleukin-1 beta": "IL1B", "p01584": "IL1B",
    "il17a": "IL17A", "interleukin-17a": "IL17A", "q16552": "IL17A",
    "il23a": "IL23A", "interleukin-23": "IL23A", "q9npf7": "IL23A",
    "jak1": "JAK1", "janus kinase 1": "JAK1", "p23458": "JAK1",
    "jak2": "JAK2", "janus kinase 2": "JAK2", "o60674": "JAK2",
    "jak3": "JAK3", "janus kinase 3": "JAK3", "p52333": "JAK3",
    "ppp3ca": "PPP3CA", "calcineurin": "PPP3CA", "q08209": "PPP3CA",
    "mtor": "MTOR", "mammalian target of rapamycin": "MTOR", "p42345": "MTOR",
}


def _normalize_name(name: str | None) -> str:
    return str(name or "").strip().lower().replace("-", "_").replace(" ", "_")


def _get_atc_prefixes(comp: Dict[str, Any]) -> Set[str]:
    """Extracts a set of all uppercase ATC codes and their hierarchical prefixes."""
    prefixes: Set[str] = set()
    raw_codes: List[str] = []

    ext = comp.get("external_ids") or {}
    if isinstance(ext, dict):
        raw_codes.extend(ext.get("atc_codes") or [])

    for cat in comp.get("categories", []):
        cat_str = str(cat).strip()
        # ATC pattern: e.g. R03AC02, R03AC, C07AB12
        match = re.match(r"^([A-Z][0-9]{2}[A-Z]?[A-Z]?[0-9]*)", cat_str, re.IGNORECASE)
        if match:
            raw_codes.append(match.group(1))

    meta = comp.get("metadata") or {}
    online = meta.get("online_enrichment") if isinstance(meta, dict) else {}
    if isinstance(online, dict):
        raw_codes.extend(online.get("atc_classes") or [])

    for c in raw_codes:
        clean = re.sub(r"[^A-Z0-9]", "", str(c).upper())
        if clean:
            for length in range(1, len(clean) + 1):
                prefixes.add(clean[:length])

    return prefixes


_PATHWAY_SERVICE_SINGLETON = None


def _get_pathway_service():
    global _PATHWAY_SERVICE_SINGLETON
    if _PATHWAY_SERVICE_SINGLETON is None:
        from app.services.pathway_service import PathwayService
        _PATHWAY_SERVICE_SINGLETON = PathwayService()
    return _PATHWAY_SERVICE_SINGLETON


def _get_target_gene_actions(comp: Dict[str, Any]) -> Dict[str, Set[ActionType]]:
    """Standardizes compound receptor targets into a {GeneSymbol: {ActionType}} dictionary."""
    gene_map: Dict[str, Set[ActionType]] = {}
    for r in comp.get("receptor_targets", []):
        if not isinstance(r, dict):
            continue

        target_name = str(r.get("target", "")).strip().lower()
        target_id = str(r.get("target_id", "")).strip().lower()
        accessions = str(r.get("accessions", "")).strip().lower()
        action = normalize_action(r.get("action"))

        # Resolve to standard gene symbol
        matched_gene: Optional[str] = None
        for syn, sym in _TARGET_GENE_SYNONYMS.items():
            if len(syn) <= 3:
                if re.search(r"\b" + re.escape(syn) + r"\b", target_name) or syn == target_id or syn == accessions:
                    matched_gene = sym
                    break
            else:
                if syn in target_name or syn == target_id or syn in accessions:
                    matched_gene = sym
                    break

        if not matched_gene and target_name:
            try:
                meta = _get_pathway_service().resolve_target_metadata(target_name, allow_online=False)
                if meta.get("symbol") and meta["symbol"] != "UNKNOWN":
                    matched_gene = meta["symbol"]
            except Exception:
                pass

        if matched_gene:
            if matched_gene not in gene_map:
                gene_map[matched_gene] = set()
            gene_map[matched_gene].add(action)

    return gene_map


def _get_epc_classes(comp: Dict[str, Any]) -> Set[str]:
    """Returns normalized uppercase FDA Established Pharmacologic Classes (EPC)."""
    epcs: Set[str] = set()
    meta = comp.get("metadata") or {}
    online = meta.get("online_enrichment") if isinstance(meta, dict) else {}
    if isinstance(online, dict):
        for e in online.get("pharm_class_epc", []):
            epcs.add(str(e).upper().replace(" ", "_").replace("-", "_"))
    for c in comp.get("categories", []):
        epcs.add(str(c).upper().replace(" ", "_").replace("-", "_"))
    return epcs


def _get_usan_stem(comp: Dict[str, Any]) -> str:
    """Returns standardized lowercase USAN stem."""
    stem = str(comp.get("usan_stem") or "").strip().lower()
    if not stem:
        meta = comp.get("metadata") or {}
        chembl = meta.get("chembl") if isinstance(meta, dict) else {}
        if isinstance(chembl, dict):
            stem = str(chembl.get("usan_stem") or "").strip().lower()
    return stem


def _has_ontology_match(context: str, term: str) -> bool:
    """Exact word-token and multi-word phrase matching without regex."""
    clean_term = term.strip().lower()
    if not clean_term or not context:
        return False
    if clean_term == context:
        return True
    words = context.split()
    if " " not in clean_term:
        return clean_term in words
    term_words = clean_term.split()
    t_len = len(term_words)
    for i in range(len(words) - t_len + 1):
        if words[i:i + t_len] == term_words:
            return True
    return False


def _has_any_ontology_match(context: str, terms: List[str]) -> bool:
    return any(_has_ontology_match(context, term) for term in terms)


def _get_compound_pharmacology_tags(comp: Dict[str, Any]) -> str:
    meta = comp.get("metadata") or {}
    online = meta.get("online_enrichment") if isinstance(meta, dict) else {}
    ext = comp.get("external_ids") or {}

    parts = [
        str(comp.get("drug_class", "")),
        str(comp.get("compound_class", "")),
        str(comp.get("mechanism", "")),
        " ".join(str(c) for c in comp.get("categories", [])),
        " ".join(str(a) for a in ext.get("atc_codes", [])),
        str(comp.get("usan_stem", "")),
        str(meta.get("usan_definition", "") if isinstance(meta, dict) else ""),
    ]

    if isinstance(online, dict):
        parts.extend([
            " ".join(str(x) for x in online.get("pharm_class_epc", [])),
            " ".join(str(x) for x in online.get("pharm_class_moa", [])),
            " ".join(str(x) for x in online.get("pharm_class_pe", [])),
            " ".join(str(x) for x in online.get("atc_classes", [])),
        ])

    for r in comp.get("receptor_targets", []):
        if isinstance(r, dict):
            parts.append(str(r.get("target", "")))
            parts.append(str(r.get("family", "")))
            parts.append(str(r.get("action", "")))

    return " ".join(parts).lower()


def _get_compound_ontology_tags(comp: Dict[str, Any]) -> str:
    pharm_text = _get_compound_pharmacology_tags(comp)
    parts = [
        pharm_text,
        str(comp.get("name", "")),
        str(comp.get("key", "")),
        str(comp.get("canonical_name", "")),
        str(comp.get("drug_class", "")),
        str(comp.get("mechanism", "")),
        str(comp.get("category", "")),
        str(comp.get("description", "")),
        " ".join(str(s) for s in comp.get("categories", [])),
        " ".join(str(s) for s in comp.get("synonyms", [])),
    ]
    return " ".join(parts).lower()



def _is_potassium_sparing_or_raas(comp: Dict[str, Any]) -> tuple[bool, str]:
    """Identify if a compound retains potassium or acts as a RAAS / aldosterone antagonist."""
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)
    all_context = _get_compound_ontology_tags(comp)

    # 1. ARBs (Angiotensin II Receptor Blockers)
    if ActionType.ANTAGONIST in targets.get("AGTR1", set()) or bool(atc & {"C09CA", "C09C"}) or usan.endswith("sartan") or _has_any_ontology_match(all_context, ["sartan", "angiotensin 2 receptor blocker", "angiotensin ii receptor antagonist", "arb", "agtr1"]):
        return True, "Angiotensin II Receptor Blocker (ARB)"

    # 2. ACE Inhibitors
    if ActionType.INHIBITOR in targets.get("ACE", set()) or bool(atc & {"C09AA", "C09A"}) or usan.endswith("pril") or _has_any_ontology_match(all_context, ["pril", "angiotensin-converting enzyme inhibitor", "ace inhibitor"]):
        return True, "ACE Inhibitor"

    # 3. Mineralocorticoid / Aldosterone Antagonists (MRA)
    if ActionType.ANTAGONIST in targets.get("NR3C2", set()) or bool(atc & {"C03DA", "C03D"}) or usan.endswith("renone") or _has_any_ontology_match(all_context, ["aldosterone antagonist", "mineralocorticoid receptor antagonist", "mineralocorticoid antagonist", "spironolactone", "eplerenone", "finerenone"]):
        return True, "Aldosterone / Mineralocorticoid Receptor Antagonist"

    # 4. Potassium-Sparing Diuretics
    if ActionType.INHIBITOR in targets.get("ENAC", set()) or bool(atc & {"C03DB"}) or _has_any_ontology_match(all_context, ["potassium-sparing", "potassium sparing", "triamterene", "amiloride"]):
        return True, "Potassium-Sparing Diuretic"

    # 5. Potassium Supplements
    if bool(atc & {"A12BA"}) or _has_any_ontology_match(all_context, ["potassium chloride", "potassium citrate", "potassium supplement"]):
        return True, "Potassium Supplement"

    # 6. Calcineurin Inhibitors
    if bool(atc & {"L04AD"}) or _has_any_ontology_match(all_context, ["calcineurin inhibitor", "tacrolimus", "cyclosporine"]):
        return True, "Calcineurin Inhibitor"

    # 7. Trimethoprim
    if bool(atc & {"J01EA"}) or _has_any_ontology_match(all_context, ["trimethoprim", "bactrim", "cotrimoxazole"]):
        return True, "Trimethoprim"

    # 8. Direct Renin Inhibitors (e.g. Aliskiren)
    if not _is_beta_blocker(comp):
        if (ActionType.INHIBITOR in targets.get("RENIN", set()) and bool(atc & {"C09XA"})) or bool(atc & {"C09XA"}) or usan.endswith("kiren") or _has_any_ontology_match(all_context, ["direct renin inhibitor", "aliskiren"]):
            return True, "Direct Renin Inhibitor"

    if _has_any_ontology_match(all_context, ["decreased renal potassium excretion"]):
        return True, "Potassium-Retaining Pharmacologic Agent"

    return False, ""


def _is_pde5_inhibitor(comp: Dict[str, Any]) -> bool:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)
    if ActionType.INHIBITOR in targets.get("PDE5A", set()) or bool(atc & {"G04BE"}) or usan.endswith("afil"):
        return True
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["phosphodiesterase 5 inhibitor", "phosphodiesterase type 5 inhibitor", "pde5", "pde-5", "tadalafil", "sildenafil", "vardenafil", "avanafil"])


def _is_nitrate_donor(comp: Dict[str, Any]) -> bool:
    atc = _get_atc_prefixes(comp)
    if bool(atc & {"C01DA"}):
        return True
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["organic nitrate", "nitrate vasodilator", "nitroglycerin", "isosorbide", "nitroprusside", "nitric oxide donor"])


def _is_alpha1_blocker(comp: Dict[str, Any]) -> bool:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)
    if ActionType.ANTAGONIST in targets.get("ADRA1A", set()) or bool(atc & {"C02CA", "G04CA"}) or usan.endswith("azosin") or usan.endswith("ulosin"):
        return True
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["alpha-1 blocker", "alpha 1 blocker", "alpha-adrenoreceptor antagonist", "prazosin", "doxazosin", "terazosin", "tamsulosin", "alfuzosin"])


def _is_beta_blocker(comp: Dict[str, Any]) -> bool:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)
    if ActionType.ANTAGONIST in (targets.get("ADRB1", set()) | targets.get("ADRB2", set())):
        return True
    if bool(atc & {"C07AA", "C07AB", "C07AG", "C07A", "C07"}) or (usan.endswith("lol") and not usan.endswith("terol")):
        return True
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["beta-adrenergic blocker", "beta blocker", "beta-blocker", "propranolol", "metoprolol", "atenolol", "bisoprolol", "carvedilol", "nebivolol"])


def _is_non_dhp_ccb_or_digoxin(comp: Dict[str, Any]) -> bool:
    atc = _get_atc_prefixes(comp)
    if bool(atc & {"C08DB", "C08DA", "C01AA"}):
        return True
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["non-dihydropyridine", "verapamil", "diltiazem", "digoxin"])


def _is_potent_hypoglycemic(comp: Dict[str, Any]) -> tuple[bool, str, str]:
    """
    Returns (is_hypoglycemic, class_name, risk_potency_tier).
    - HIGH_POTENCY_SECRETAGOGUE: Exogenous insulins (A10A), sulfonylureas (A10BB), meglitinides (A10BX). High intrinsic risk of acute neuroglycopenia.
    - MODERATE_SENSITIZER: GLP-1 (A10BJ), SGLT2 (A10BK), DPP-4 (A10BH), Biguanides (A10BA), Berberine, TZDs (A10BG). Glucose-dependent action.
    - METABOLIC_MODULATOR: Androgens (G03B), Growth Hormone (H01A). Long-term nutrient partitioning and metabolic modulation.
    """
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    pharm = _get_compound_pharmacology_tags(comp)

    # 1. High-Potency Hypoglycemic Secretagogues & Exogenous Insulins
    if ActionType.AGONIST in targets.get("INSR", set()) or bool(atc & {"A10A"}) or _has_any_ontology_match(pharm, ["insulin agonist", "insulin human", "insulin glargine", "insulin lispro", "insulin aspart", "insulin degludec", "insulin detemir"]):
        return True, "Exogenous Insulin Agonist", "HIGH_POTENCY_SECRETAGOGUE"
    if ActionType.INHIBITOR in targets.get("ABCC8", set()) or bool(atc & {"A10BB"}) or _has_any_ontology_match(pharm, ["sulfonylurea", "glimepiride", "glipizide", "glyburide", "gliclazide", "katp", "abcc8", "kcnj11"]):
        return True, "Sulfonylurea (KATP Blocker)", "HIGH_POTENCY_SECRETAGOGUE"
    if bool(atc & {"A10BX"}) or _has_any_ontology_match(pharm, ["meglitinide", "repaglinide", "nateglinide"]):
        return True, "Meglitinide Secretagogue", "HIGH_POTENCY_SECRETAGOGUE"

    # 2. Incretins, SGLT2, & Sensitizers
    if ActionType.AGONIST in targets.get("GLP1R", set()) or bool(atc & {"A10BJ"}) or _has_any_ontology_match(pharm, ["glucagon-like peptide", "glp-1 receptor agonist", "glp1r", "semaglutide", "tirzepatide", "liraglutide", "dulaglutide"]):
        return True, "GLP-1 Receptor Agonist", "MODERATE_SENSITIZER"
    if ActionType.INHIBITOR in targets.get("SLC5A2", set()) or bool(atc & {"A10BK"}) or _has_any_ontology_match(pharm, ["sglt2 inhibitor", "sodium-glucose cotransporter 2 inhibitor", "slc5a2", "empagliflozin", "dapagliflozin", "canagliflozin", "flozin"]):
        return True, "SGLT2 Inhibitor", "MODERATE_SENSITIZER"
    if bool(atc & {"A10BA"}) or _has_any_ontology_match(pharm, ["biguanide", "metformin", "berberine", "ampk activator"]):
        return True, "Biguanide / AMPK Activator", "MODERATE_SENSITIZER"
    if bool(atc & {"A10BH"}) or _has_any_ontology_match(pharm, ["dipeptidyl peptidase 4 inhibitor", "dpp-4 inhibitor", "sitagliptin", "linagliptin", "saxagliptin"]):
        return True, "DPP-4 Inhibitor", "MODERATE_SENSITIZER"
    if ActionType.AGONIST in targets.get("PPARG", set()) or bool(atc & {"A10BG"}) or _has_any_ontology_match(pharm, ["thiazolidinedione", "pioglitazone"]):
        return True, "Thiazolidinedione (PPAR-gamma Agonist)", "MODERATE_SENSITIZER"
    if _has_any_ontology_match(pharm, ["decreased blood glucose"]):
        return True, "Glucose-Lowering Agent", "MODERATE_SENSITIZER"

    # 3. Hormonal Metabolic Modulators
    if ActionType.AGONIST in targets.get("AR", set()) or bool(atc & {"G03BA", "G03B"}) or _has_any_ontology_match(pharm, ["androgen", "androgen receptor agonist", "ar agonist"]):
        return False, "Androgen (Mild Peripheral Insulin Sensitizer)", "METABOLIC_MODULATOR"
    if ActionType.AGONIST in targets.get("GHR", set()) or bool(atc & {"H01AC", "H01A"}) or _has_any_ontology_match(pharm, ["somatropin", "growth hormone receptor agonist", "ghr"]):
        return False, "Growth Hormone (Hepatic Lipolytic Modulator)", "METABOLIC_MODULATOR"

    return False, "", ""


def _is_anticholinergic_agent(comp: Dict[str, Any]) -> bool:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    chrm_actions = targets.get("CHRM1", set()) | targets.get("CHRM2", set()) | targets.get("CHRM3", set()) | targets.get("CHRM", set())
    if ActionType.ANTAGONIST in chrm_actions or bool(atc & {"R06AA", "G04BD", "N06AA"}):
        return True
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["anticholinergic", "antimuscarinic", "muscarinic acetylcholine receptor antagonist", "diphenhydramine", "hydroxyzine", "amitriptyline", "nortriptyline", "oxybutynin", "tolterodine", "cyclobenzaprine", "scopolamine"])


def _is_direct_nephrotoxic(comp: Dict[str, Any]) -> bool:
    atc = _get_atc_prefixes(comp)
    if bool(atc & {"M01AE", "M01AB", "M01A", "J01GB", "J01XA"}):
        return True
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["aminoglycoside", "gentamicin", "tobramycin", "amikacin", "vancomycin", "glycopeptide antibiotic", "cisplatin", "amphotericin", "tacrolimus", "cyclosporine", "nsaid", "non-steroidal anti-inflammatory drug"])


def _is_qtc_prolonging_agent(comp: Dict[str, Any]) -> tuple[bool, str]:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    if ActionType.INHIBITOR in targets.get("KCNH2", set()) or ActionType.ANTAGONIST in targets.get("KCNH2", set()) or bool(atc & {"C01B", "C01BA", "C01BB", "C01BC", "C01BD"}):
        return True, "Antiarrhythmic / hERG Channel Modulator"
    if bool(atc & {"N05A"}):
        return True, "Antipsychotic (hERG Affinity)"
    if bool(atc & {"J01MA"}):
        return True, "Fluoroquinolone (hERG Blocker)"
    if bool(atc & {"J01FA"}):
        return True, "Macrolide (hERG Blocker)"
    if bool(atc & {"A04AA"}):
        return True, "5-HT3 Receptor Antagonist"

    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["kcnh2", "herg", "delayed rectifier", "potassium voltage-gated", "delayed cardiac repolarization", "prolonged qtc interval", "prolongation of the qt interval"]):
        return True, "QTc Prolonging Pharmacologic Agent"
    return False, ""


def _is_antithrombotic_or_anticoagulant(comp: Dict[str, Any]) -> tuple[bool, str]:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    epc = _get_epc_classes(comp)
    all_context = _get_compound_ontology_tags(comp)

    # 1. Factor Xa Inhibitors (DOACs)
    if ActionType.INHIBITOR in targets.get("F10", set()) or bool(atc & {"B01AF"}) or any("FACTOR_XA" in e for e in epc) or _has_any_ontology_match(all_context, ["direct oral anticoagulant", "doac", "factor xa inhibitor", "apixaban", "rivaroxaban", "edoxaban"]):
        return True, "Factor Xa Inhibitor (DOAC)"

    # 2. Direct Thrombin Inhibitors
    if ActionType.INHIBITOR in targets.get("F2", set()) or bool(atc & {"B01AE"}) or any("DIRECT_THROMBIN" in e for e in epc) or _has_any_ontology_match(all_context, ["direct thrombin inhibitor", "dabigatran", "argatroban", "bivalirudin"]):
        return True, "Direct Thrombin Inhibitor"

    # 3. Vitamin K Antagonists
    if ActionType.INHIBITOR in targets.get("VKORC1", set()) or bool(atc & {"B01AA"}) or any("VITAMIN_K_ANTAGONIST" in e for e in epc) or _has_any_ontology_match(all_context, ["vitamin k antagonist", "coumarin", "warfarin"]):
        return True, "Vitamin K Antagonist (Warfarin)"

    # 4. Heparins / LMWH
    if bool(atc & {"B01AB"}) or any("HEPARIN" in e for e in epc) or _has_any_ontology_match(all_context, ["heparin", "low molecular weight heparin", "lmwh", "enoxaparin", "fondaparinux"]):
        return True, "Heparin / LMWH"

    # 5. Platelet Antiaggregants
    if ActionType.ANTAGONIST in targets.get("P2RY12", set()) or ActionType.INHIBITOR in targets.get("PTGS1", set()) or bool(atc & {"B01AC"}) or any("PLATELET_AGGREGATION_INHIBITOR" in e or "P2Y12" in e for e in epc) or _has_any_ontology_match(all_context, ["platelet aggregation inhibitor", "p2y12", "clopidogrel", "ticagrelor", "prasugrel", "aspirin", "acetylsalicylic acid"]):
        return True, "Platelet Antiaggregant"

    # 6. NSAIDs
    if bool(atc & {"M01A", "M01AE"}) or any("NONSTEROIDAL_ANTI_INFLAMMATORY" in e or "NSAID" in e for e in epc) or _has_any_ontology_match(all_context, ["non-steroidal anti-inflammatory drug", "nsaid", "ibuprofen", "naproxen", "ketorolac", "indomethacin"]):
        return True, "NSAID (COX-1 Platelet Suppressor)"

    # 7. SSRIs
    if ActionType.INHIBITOR in targets.get("SLC6A4", set()) or bool(atc & {"N06AB"}) or any("SEROTONIN_REUPTAKE_INHIBITOR" in e for e in epc) or _has_any_ontology_match(all_context, ["selective serotonin reuptake inhibitor", "ssri"]):
        return True, "SSRI (Platelet Serotonin Depletor)"

    if _has_any_ontology_match(all_context, ["inhibition of blood coagulation", "decreased platelet aggregation"]):
        return True, "Hemostasis-Impairing Agent"

    # 8. Fibrinolytic & Thrombolytic Enzymes
    if _has_any_ontology_match(all_context, ["nattokinase", "lumbrokinase", "serrapeptase", "subtilisin", "fibrinolytic enzyme", "thrombolytic enzyme", "fibrinolysis"]):
        return True, "Fibrinolytic Enzyme"

    return False, ""


def _is_serotonergic_agent(comp: Dict[str, Any]) -> tuple[bool, str]:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    epc = _get_epc_classes(comp)
    all_context = _get_compound_ontology_tags(comp)

    # 1. MAOIs
    if ActionType.INHIBITOR in (targets.get("MAOA", set()) | targets.get("MAOB", set())) or bool(atc & {"N06AF", "N06AG"}) or any("MONOAMINE_OXIDASE_INHIBITOR" in e for e in epc) or _has_any_ontology_match(all_context, ["monoamine oxidase inhibitor", "maoi", "phenelzine", "tranylcypromine", "selegiline", "moclobemide", "linezolid", "methylene blue"]):
        return True, "Monoamine Oxidase Inhibitor (MAOI)"

    # 2. SSRIs
    if ActionType.INHIBITOR in targets.get("SLC6A4", set()) or bool(atc & {"N06AB"}) or any("SEROTONIN_REUPTAKE_INHIBITOR" in e for e in epc) or _has_any_ontology_match(all_context, ["selective serotonin reuptake inhibitor", "ssri", "fluoxetine", "sertraline", "paroxetine", "citalopram", "escitalopram"]):
        return True, "Selective Serotonin Reuptake Inhibitor (SSRI)"

    # 3. SNRIs
    if bool(atc & {"N06AX"}) or any("SEROTONIN_NOREPINEPHRINE_REUPTAKE_INHIBITOR" in e for e in epc) or _has_any_ontology_match(all_context, ["serotonin-norepinephrine reuptake inhibitor", "snri", "venlafaxine", "duloxetine", "desvenlafaxine"]):
        return True, "Serotonin-Norepinephrine Reuptake Inhibitor (SNRI)"

    # 4. TCAs
    if bool(atc & {"N06AA"}) or any("TRICYCLIC_ANTIDEPRESSANT" in e for e in epc) or _has_any_ontology_match(all_context, ["tricyclic antidepressant", "tca", "amitriptyline", "clomipramine", "imipramine"]):
        return True, "Tricyclic Antidepressant (TCA)"

    # 5. Triptans (5-HT1B/1D agonists)
    if ActionType.AGONIST in (targets.get("HTR1B", set()) | targets.get("HTR1D", set())) or bool(atc & {"N02CC"}) or any("TRIPTAN" in e for e in epc) or _has_any_ontology_match(all_context, ["triptan", "5-ht1b/1d agonist", "sumatriptan", "zolmitriptan", "rizatriptan"]):
        return True, "5-HT1 Receptor Agonist (Triptan)"

    # 6. Modulators / Releasers
    if _has_any_ontology_match(all_context, ["tramadol", "meperidine", "methadone", "fentanyl", "dextromethorphan", "st. john's wort", "hypericum", "slc6a4", "5-ht reuptake inhibitor", "serotonin releaser"]):
        return True, "Serotonin-Releasing / Reuptake Modulating Agent"

    return False, ""


def _is_cns_sedative_or_opioid(comp: Dict[str, Any]) -> tuple[bool, str]:
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    epc = _get_epc_classes(comp)
    all_context = _get_compound_ontology_tags(comp)

    # 1. Opioids
    if ActionType.AGONIST in targets.get("OPRM1", set()) or bool(atc & {"N02A"}) or any("OPIOID" in e for e in epc) or _has_any_ontology_match(all_context, ["opioid receptor agonist", "mu-opioid", "morphine", "oxycodone", "fentanyl", "hydromorphone", "buprenorphine", "methadone", "codeine"]):
        return True, "Opioid Agonist"

    # 2. Benzodiazepines
    if ActionType.PAM in targets.get("GABRA1", set()) or bool(atc & {"N05BA", "N05CD"}) or any("BENZODIAZEPINE" in e for e in epc) or _has_any_ontology_match(all_context, ["benzodiazepine", "diazepam", "alprazolam", "lorazepam", "clonazepam", "midazolam"]):
        return True, "Benzodiazepine (GABA-A PAM)"

    # 3. Z-Drugs
    if bool(atc & {"N05CF"}) or any("GABA_A_RECEPTOR_POSITIVE_ALLOSTERIC_MODULATOR" in e for e in epc) or _has_any_ontology_match(all_context, ["z-drug", "gaba-a receptor positive allosteric modulator", "zolpidem", "zopiclone", "eszopiclone"]):
        return True, "Non-Benzodiazepine Hypnotic (Z-Drug)"

    # 4. Barbiturates
    if bool(atc & {"N03AA"}) or any("BARBITURATE" in e for e in epc) or _has_any_ontology_match(all_context, ["barbiturate", "phenobarbital"]):
        return True, "Barbiturate"

    # 5. Orexin Antagonists
    if ActionType.ANTAGONIST in targets.get("HCRTR1", set()) or bool(atc & {"N05CM"}) or any("OREXIN_RECEPTOR_ANTAGONIST" in e for e in epc) or _has_any_ontology_match(all_context, ["dual orexin receptor antagonist", "dora", "suvorexant", "lemborexant"]):
        return True, "Orexin Receptor Antagonist"

    # 6. Sedating Antihistamines
    if bool(atc & {"R06AA", "R06AB"}) or _has_any_ontology_match(all_context, ["first-generation antihistamine", "h1 inverse agonist", "diphenhydramine", "hydroxyzine", "promethazine", "doxylamine"]):
        return True, "Sedating Antihistamine (H1/Muscarinic Blocker)"

    if _has_any_ontology_match(all_context, ["opioid receptor agonist", "benzodiazepine", "z-drug", "barbiturate", "dual orexin receptor antagonist"]):
        return True, "CNS Sedative"

    return False, ""


def _is_beta_agonist(comp: Dict[str, Any]) -> tuple[bool, str]:
    """Identify if a compound is a Beta-1 / Beta-2 adrenergic receptor agonist or sympathomimetic bronchodilator."""
    if _is_beta_blocker(comp):
        return False, ""

    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)

    if ActionType.AGONIST in (targets.get("ADRB1", set()) | targets.get("ADRB2", set())):
        return True, "Beta-Adrenergic Receptor Agonist"
    if bool(atc & {"R03AC", "R03CC", "R03A", "R03C", "C01CA"}) or usan.endswith("terol"):
        return True, "Beta-Adrenergic Receptor Agonist"

    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["beta-2 adrenergic receptor agonist", "beta-2 agonist", "beta-1 agonist", "beta-adrenergic agonist", "adrb2 agonist", "adrb1 agonist"]):
        return True, "Beta-Adrenergic Receptor Agonist"

    return False, ""


def _is_alpha2_antagonist(comp: Dict[str, Any]) -> tuple[bool, str]:
    """Identify if a compound is an Alpha-2 adrenergic receptor antagonist (presynaptic autoreceptor blocker)."""
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    if ActionType.ANTAGONIST in (targets.get("ADRA2A", set()) | targets.get("ADRA2B", set()) | targets.get("ADRA2C", set())):
        return True, "Alpha-2 Adrenergic Antagonist (Presynaptic Autoreceptor Blocker)"
    if bool(atc & {"C02CA"}):
        return True, "Alpha-2 Adrenergic Antagonist (Presynaptic Autoreceptor Blocker)"

    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["alpha-2 adrenergic receptor antagonist", "alpha-2 antagonist", "alpha 2 blocker", "adra2a antagonist", "adra2", "yohimbine", "rauwolscine", "idazoxan", "atipamezole"]):
        return True, "Alpha-2 Adrenergic Antagonist (Presynaptic Autoreceptor Blocker)"
    return False, ""


def _is_adenosine_antagonist_or_pde_inhibitor(comp: Dict[str, Any]) -> tuple[bool, str]:
    """Identify if a compound is an Adenosine A1/A2A antagonist or non-selective phosphodiesterase inhibitor."""
    if _is_pde5_inhibitor(comp):
        return False, ""

    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)
    if ActionType.ANTAGONIST in (targets.get("ADORA1", set()) | targets.get("ADORA2A", set())) or ActionType.INHIBITOR in targets.get("PDE_NONSPECIFIC", set()):
        return True, "Adenosine Antagonist / Phosphodiesterase Inhibitor"
    if bool(atc & {"R03DA", "N06BC"}) or usan.endswith("phylline"):
        return True, "Adenosine Antagonist / Phosphodiesterase Inhibitor"

    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["adenosine receptor antagonist", "adenosine a1", "adenosine a2a", "methylxanthine", "caffeine", "theophylline", "aminophylline", "enprofylline", "xanthine phosphodiesterase"]):
        return True, "Adenosine Antagonist / Phosphodiesterase Inhibitor"
    return False, ""


def _is_sympathomimetic_stimulant(comp: Dict[str, Any]) -> tuple[bool, str]:
    """Identify if a compound is a direct or indirect sympathomimetic or psychostimulant."""
    if _is_beta_blocker(comp):
        return False, ""

    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)
    if bool(atc & {"N06BA", "R01BA"}) or usan.endswith("fedrine") or usan.endswith("phrine") or usan.endswith("fetamine") or usan.endswith("phenidate"):
        return True, "Sympathomimetic Stimulant"

    burdens = comp.get("organ_burdens", {}) or {}
    if str(burdens.get("cns_stimulant", "none")).lower() in {"moderate", "high"}:
        return True, "CNS Stimulant"

    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["sympathomimetic", "ephedrine", "pseudoephedrine", "synephrine", "phenylephrine", "amphetamine", "dextroamphetamine", "methylphenidate", "modafinil", "armodafinil", "phentermine"]):
        return True, "Sympathomimetic Stimulant"
    return False, ""


def _is_hormonal_or_endocrine_agent(comp: Dict[str, Any]) -> tuple[bool, str, str]:
    """
    Generalized, non-hardcoded classification of hormonal, endocrine, and steroidogenic agents.
    Returns: (is_hormonal, category_description, primary_axis)
    """
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    usan = _get_usan_stem(comp)
    all_context = _get_compound_ontology_tags(comp)

    is_botanical = any(w in str(comp.get("drug_class", "")).lower() for w in ["botanical", "adaptogen", "herbal", "dietary supplement"])
    d_class = str(comp.get("drug_class", "")).lower()
    is_non_endocrine_small_mol = any(w in d_class for w in [
        "sglt", "transporter", "biguanide", "diuretic", "statin", "antioxidant", "nsaid",
        "pde5", "pde-5", "phosphodiesterase", "vasodilator", "erectile dysfunction", "xanthine"
    ])

    # 1. Sex Steroids / HPG Axis
    if not is_botanical and not is_non_endocrine_small_mol and bool({"AR", "ESR1", "ESR2", "PGR", "CYP19A1", "SRD5A1", "SRD5A2", "SHBG", "LHCGR", "FSHR", "GNRHR"} & set(targets.keys())):
        return True, "Sex Hormone / HPG Axis Modulator", "HPG Endocrine Axis"
    if bool(atc & {"G03", "G03A", "G03B", "G03C", "G03D", "G03E", "G03F", "G03G", "G03H", "G03X", "L02", "L02A", "L02B"}):
        return True, "Sex Hormone / Endocrine Therapy", "HPG Endocrine Axis"

    # 2. Pituitary, Hypothalamic & Somatotropic (GH / IGF-1) Axis
    if not is_botanical and not is_non_endocrine_small_mol and bool({"GHR", "GHSR", "PRLR", "OXTR", "AVPR1A", "AVPR1B", "AVPR2", "CRHR1", "CRHR2", "MC2R"} & set(targets.keys())):
        return True, "Pituitary / Somatotropic Modulator", "Pituitary-Somatotropic Axis"
    if bool(atc & {"H01", "H01A", "H01B", "H01C", "H01AC"}):
        return True, "Pituitary / Hypothalamic Hormone", "Pituitary-Hypothalamic Axis"

    # 3. Thyroid Axis (HPT)
    if not is_botanical and not is_non_endocrine_small_mol and bool({"THRA", "THRB", "TSHR", "TRHR"} & set(targets.keys())):
        return True, "Thyroid Hormone / HPT Modulator", "Thyroid (HPT) Axis"
    if bool(atc & {"H03", "H03A", "H03B", "H03C"}):
        return True, "Thyroid Hormone Formulation", "Thyroid (HPT) Axis"

    # 4. Adrenal & Corticosteroid Axis (HPA / Mineralocorticoid)
    if not is_botanical and not is_non_endocrine_small_mol and (ActionType.AGONIST in targets.get("NR3C1", set()) or bool(atc & {"H02", "H02A", "H02B", "H02C"})):
        return True, "Corticosteroid / Adrenal Steroid", "Adrenal (HPA) Axis"

    # 5. Incretin / Metabolic Hormones
    if not is_botanical and not is_non_endocrine_small_mol and bool({"GLP1R", "GIPR", "GCGR", "INSR", "IGF1R"} & set(targets.keys())):
        return True, "Incretin / Metabolic Peptide Hormone", "Metabolic Endocrine Axis"
    if bool(atc & {"A10A", "A10BJ"}):
        return True, "Incretin / Insulin Mimetic", "Metabolic Endocrine Axis"

    # 6. USAN Stems
    if usan and any(usan.endswith(s) or usan.startswith(s) for s in [
        "ster", "olone", "asteride", "relin", "tropin", "gest", "andr", "estr", "stan", "bol", "dronate", "tide"
    ]):
        return True, "Endocrine / Peptide Hormone Derivative", "Endocrine System"

    # 7. Pharmacology / Drug Class / Category Ontologies
    if not is_botanical and not is_non_endocrine_small_mol:
        core_context = " ".join([
            str(comp.get("drug_class", "")),
            str(comp.get("compound_class", "")),
            " ".join(str(c) for c in comp.get("categories", [])),
            str(comp.get("name", "")),
            str(comp.get("canonical_name", "")),
        ]).lower()
        if any(re.search(rf"\b{re.escape(w)}\b", core_context) for w in ["pde5", "phosphodiesterase", "vasodilator", "erectile dysfunction"]):
            return False, "", ""
        endocrine_keywords = [
            "hormone replacement", "hormone therapy", "anabolic steroid", "androgenic steroid",
            "androgen", "estrogen", "progestin", "progestogen", "corticosteroid", "glucocorticoid",
            "thyroid hormone", "growth hormone", "gonadotropin", "serm", "sarm", "aromatase inhibitor",
            "somatropin", "growth hormone secretagogue", "antiandrogen", "antiestrogen", "neurosteroid",
            "testosterone", "estradiol", "nandrolone", "oxandrolone", "drostanolone", "trenbolone",
            "boldenone", "stanozolol", "dhea", "pregnenolone", "liothyronine", "levothyroxine"
        ]
        if _has_any_ontology_match(core_context, endocrine_keywords):
            if "reductase inhibitor" in core_context and "testosterone" in core_context and not any(k in core_context for k in ["anabolic", "androgen replacement", "testosterone cypionate", "testosterone enanthate", "testosterone propionate"]):
                return False, "", ""
            return True, "Endocrine / Hormonal Compound", "Endocrine System"

    return False, "", ""


def _is_immunosuppressive_agent(comp: Dict[str, Any]) -> tuple[bool, str]:
    """
    Deterministically identifies if a compound is an immunosuppressive, immunomodulatory,
    or targeted biologic agent (e.g. anti-TNF, anti-IL, checkpoint inhibitor, calcineurin inhibitor,
    mTOR inhibitor, systemic corticosteroid) based on ATC codes, EPC classes, molecular targets,
    and USAN stems.
    """
    targets = _get_target_gene_actions(comp)
    atc = _get_atc_prefixes(comp)
    epc = _get_epc_classes(comp)
    all_context = _get_compound_ontology_tags(comp)

    # 1. WHO ATC Hierarchy: L04 (Immunosuppressants), H02AB (Corticosteroids for systemic use)
    if any(a.startswith("L04") for a in atc):
        return True, "Immunosuppressant (ATC L04)"
    if any(a.startswith("H02AB") for a in atc):
        return True, "Systemic Corticosteroid"

    # 2. FDA Established Pharmacologic Classes (EPC)
    for e in epc:
        e_upper = e.upper()
        if "IMMUNOSUPPRESSIVE" in e_upper or "IMMUNOSUPPRESSANT" in e_upper:
            return True, "Immunosuppressive Agent (EPC)"
        if "TUMOR_NECROSIS_FACTOR" in e_upper or "TNF_BLOCKER" in e_upper:
            return True, "Tumor Necrosis Factor (TNF) Inhibitor"
        if "INTERLEUKIN" in e_upper:
            return True, "Interleukin Inhibitor"
        if "JANUS_KINASE" in e_upper or "JAK" in e_upper:
            return True, "Janus Kinase (JAK) Inhibitor"
        if "CALCINEURIN" in e_upper:
            return True, "Calcineurin Inhibitor"
        if "CD20" in e_upper:
            return True, "CD20-Directed Monoclonal Antibody"
        if "PROGRAMMED_DEATH" in e_upper or "PD-1" in e_upper or "PD-L1" in e_upper:
            return True, "Immune Checkpoint Inhibitor (PD-1/PD-L1)"
        if "CTLA-4" in e_upper:
            return True, "Immune Checkpoint Inhibitor (CTLA-4)"

    # 3. Specific Target genes: TNF, IL6R, IL6, IL1B, IL17A, IL23A, IL12B, MS4A1 (CD20), CTLA4, PDCD1, CD274, JAK1, JAK2, JAK3, PPP3CA (Calcineurin)
    immuno_targets = {
        "TNF": "TNF-alpha Inhibitor",
        "IL6R": "IL-6 Receptor Antagonist",
        "IL6": "IL-6 Inhibitor",
        "IL1B": "IL-1 beta Antagonist",
        "IL17A": "IL-17A Inhibitor",
        "IL23A": "IL-23 Inhibitor",
        "IL12B": "IL-12/23 Inhibitor",
        "MS4A1": "CD20 Cytolytic Monoclonal Antibody",
        "CTLA4": "CTLA-4 Checkpoint Modulator",
        "PDCD1": "PD-1 Immune Checkpoint Inhibitor",
        "CD274": "PD-L1 Immune Checkpoint Inhibitor",
        "JAK1": "JAK Kinase Inhibitor",
        "JAK2": "JAK Kinase Inhibitor",
        "JAK3": "JAK Kinase Inhibitor",
        "PPP3CA": "Calcineurin Inhibitor",
        "MTOR": "mTOR Inhibitor",
    }
    for gene, label in immuno_targets.items():
        if gene in targets:
            return True, label

    # 4. USAN Stems
    usan = _get_usan_stem(comp)
    if usan:
        if usan.endswith("limus"):
            return True, "Immunosuppressive Macrolide / Calcineurin Inhibitor"
        if usan.endswith("cept"):
            return True, "Receptor-Fc Fusion Protein / Biologic Modulator"

    # 5. Contextual ontology matches
    if _has_any_ontology_match(all_context, [
        "immunosuppressant", "immunosuppressive", "calcineurin inhibitor", "tnf blocker",
        "tumor necrosis factor alpha inhibitor", "interleukin-6 receptor antagonist",
        "anti-tnf", "cd20-directed", "janus kinase inhibitor", "jak inhibitor",
        "checkpoint inhibitor", "pd-1 inhibitor", "pd-l1 inhibitor", "ctla-4 inhibitor",
        "mycophenolate", "tacrolimus", "cyclosporine", "sirolimus", "everolimus", "azathioprine", "methotrexate"
    ]):
        return True, "Immunomodulatory / Immunosuppressive Agent"

    return False, ""


def _extract_dosing_interval_h(comp: Dict[str, Any]) -> tuple[float, str]:
    """
    Deterministically extracts or infers dosing interval tau in hours and human-readable frequency.
    """
    if comp.get("dosing_interval_h") is not None:
        try:
            val = float(comp["dosing_interval_h"])
            if val > 0:
                return val, f"tau={val:g}h"
        except (ValueError, TypeError):
            pass

    freq_str = str(comp.get("frequency") or comp.get("timing") or comp.get("schedule") or comp.get("dose_str") or "").strip().lower()

    if any(k in freq_str for k in ["twice daily", "bid", "2x/day", "q12h", "morning and evening", "morning & evening"]):
        return 12.0, "twice daily (q12h)"
    if any(k in freq_str for k in ["every 8 hours", "tid", "3x/day", "q8h"]):
        return 8.0, "every 8 hours (tid)"
    if any(k in freq_str for k in ["every 6 hours", "qid", "4x/day", "q6h"]):
        return 6.0, "every 6 hours (qid)"
    if any(k in freq_str for k in ["every other day", "eod", "q48h", "q2d", "alternate day"]):
        return 48.0, "every other day (EOD / q48h)"
    if any(k in freq_str for k in ["every 3 days", "q3d", "q72h"]):
        return 72.0, "every 3 days (q72h)"
    if any(k in freq_str for k in ["twice weekly", "biw", "2x/week", "2x weekly", "split", "mon & thu", "mon/thu", "tue/fri", "mon and thu"]):
        return 84.0, "twice weekly (BIW / split protocol)"
    if any(k in freq_str for k in ["every 10 days", "q10d"]):
        return 240.0, "every 10 days (q240h)"
    if any(k in freq_str for k in ["every 2 weeks", "every 14 days", "biweekly", "q2w", "q14d", "bi-weekly", "fortnightly"]):
        return 336.0, "every 2 weeks (Q2W / q336h)"
    if any(k in freq_str for k in ["weekly", "q1w", "once weekly", "1x/week", "1x weekly", "q7d", "q168h"]):
        return 168.0, "once weekly (Q1W / q168h)"
    if any(k in freq_str for k in ["monthly", "every 4 weeks", "q4w", "q28d", "q30d"]):
        return 672.0, "monthly (Q4W / q672h)"

    # Regex search for q<N>h or q<N>d
    m_h = re.search(r"\bq(\d+)h\b", freq_str)
    if m_h:
        return float(m_h.group(1)), f"every {m_h.group(1)} hours"
    m_d = re.search(r"\bq(\d+)d\b", freq_str)
    if m_d:
        d_val = float(m_d.group(1))
        return d_val * 24.0, f"every {d_val:g} days"

    # Route-based defaults for depot injections vs oral
    route = str(comp.get("route", "oral")).strip().lower()
    if route in ("im", "subq", "intramuscular", "subcutaneous", "depot"):
        # If depot/ester mentioned but unspecified, standard once-weekly default
        return 168.0, "weekly depot (default 168h)"

    return 24.0, "daily (q24h)"


class InteractionEngine:
    """
    Advanced Multi-Pathway Clinical Pharmacology Interaction Engine.
    Evaluates:
    1. Pharmacokinetics (PK):
       - CYP450 enzyme collisions (Strong/Moderate/Weak, MBI suicide inactivation, PXR induction)
       - Transporter collisions (P-gp/ABCB1, BCRP/ABCG2, OATP1B1/3, OCT1/2, OAT1/3)
       - Phase II Glucuronidation collisions (UGT1A1, UGT2B7)
       - High Plasma Protein Binding Displacement (fu surges)
       - Physicochemical Chelation (Multivalent cations + fluoroquinolones/tetracyclines)
    2. Pharmacodynamics (PD) & Multi-Agent Syndrome Classifiers:
       - Serotonin Syndrome Overload
       - QTc Prolongation & Torsades de Pointes (TdP) Risk
       - CNS & Respiratory Depression
       - Renal 'Triple Whammy' (ACEi/ARB + NSAID + Diuretic)
       - Synergistic Hemorrhagic Bleeding Risk
       - Sympathomimetic Hypertensive Crisis
       - Additive Anticholinergic Burden
    3. Comprehensive Biomarker & Laboratory Interplay:
       - 20+ laboratory markers (eGFR, Cr, ALT, AST, Bili, Albumin, K+, Na+, QTc, BP, HR, Lipids, etc.)
    4. N x N Collision Matrix & Cumulative Risk Score (0-100).
    """

    def analyze_stack(
        self,
        compounds: List[Dict[str, Any]] | Dict[str, Any],
        profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if isinstance(compounds, dict):
            profile = compounds
            compounds = profile.get("compounds") or profile.get("stack") or []

        if not compounds:
            return {
                "matrix": [],
                "compounds": [],
                "cumulative_risk_score": 0,
                "risk_band": "MINIMAL",
                "summary": "No compounds currently in stack. Add compounds to evaluate pharmacodynamics, pharmacokinetics, and interaction safety.",
                "breakdown": {
                    "cyp_conflicts": [],
                    "transporter_conflicts": [],
                    "phase2_conflicts": [],
                    "receptor_conflicts": [],
                    "syndrome_alerts": [],
                    "organ_burdens": {
                        "hepatic": {"score": 0, "level": "None"},
                        "renal": {"score": 0, "level": "None"},
                        "cardiovascular": {"score": 0, "level": "None"},
                        "cns_stimulant": {"score": 0, "level": "None"},
                        "sedative": {"score": 0, "level": "None"},
                    },
                    "synergistic_benefits": [],
                    "biomarker_warnings": [],
                },
                "conflict_count": 0,
                "synergy_count": 0,
                "full_stack_balance": {
                    "health_index": 100,
                    "status": "EMPTY",
                    "status_label": "No Active Compounds",
                    "axes": [],
                    "active_mitigations": [],
                    "uncompensated_risks": [],
                    "dose_recommendations": [],
                    "cascade_biomarker_shifts": [],
                    "target_combined_effects": {},
                },
            }

        profile_data = profile or {}
        labs = profile_data.get("labs", {}) or {}

        def _get_val(primary_key: str, default: float, alt_keys: Optional[List[str]] = None) -> float:
            keys = [primary_key] + (alt_keys or [])
            for k in keys:
                v = profile_data.get(k)
                if v is not None:
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        pass
                v_lab = labs.get(k)
                if v_lab is not None:
                    try:
                        return float(v_lab)
                    except (ValueError, TypeError):
                        pass
            return float(default)

        # Clinical Laboratory & Vital Sign Inputs
        sleep_hours = _get_val("sleep_hours", 7.5)
        blood_pressure = _get_val("blood_pressure", 120.0)
        heart_rate = _get_val("heart_rate", 72.0)
        qtc_ms = _get_val("qtc_ms", 410.0)

        # Renal Panel
        egfr = _get_val("egfr", 95.0)
        creatinine_mg_dl = _get_val("creatinine_mg_dl", 0.95)
        bun_mg_dl = _get_val("bun_mg_dl", 14.0)

        # Hepatic Panel
        alt_u_l = _get_val("alt_u_l", 25.0)
        ast_u_l = _get_val("ast_u_l", 22.0)
        total_bilirubin = _get_val("total_bilirubin_mg_dl", 0.8, ["total_bilirubin"])
        serum_albumin = _get_val("serum_albumin_g_dl", 4.5, ["serum_albumin"])

        # Electrolytes & Hematology
        potassium_meq_l = _get_val("potassium_meq_l", 4.2, ["potassium"])
        sodium_meq_l = _get_val("sodium_meq_l", 140.0, ["sodium"])
        magnesium_mg_dl = _get_val("magnesium_mg_dl", 2.1, ["magnesium"])
        hematocrit_pct = _get_val("hematocrit_pct", 45.0, ["hematocrit"])
        platelets_k_ul = _get_val("platelets_k_ul", 250.0, ["platelets"])

        # Lipids & Glycemia
        ldl_mg_dl = _get_val("ldl_mg_dl", 100.0, ["ldl_c_mg_dl", "ldl"])
        hba1c_pct = _get_val("hba1c_pct", 5.2, ["hba1c"])

        # Wearables, Autonomic, Metabolic & Neurotrophic Inputs
        hrv_rmssd_ms = _get_val("hrv_rmssd_ms", 45.0, ["hrv"])
        metabolic_rate_kcal = _get_val("metabolic_rate_kcal", 1750.0, ["bmr", "metabolic_rate"])
        fasting_insulin_u_iu_ml = _get_val("fasting_insulin_u_iu_ml", 6.0, ["fasting_insulin", "insulin"])
        homa_ir = _get_val("homa_ir", 1.2)
        free_t3_pg_ml = _get_val("free_t3_pg_ml", 3.2, ["free_t3"])
        free_t4_ng_dl = _get_val("free_t4_ng_dl", 1.3, ["free_t4"])
        shbg_nmol_l = _get_val("shbg_nmol_l", 32.0, ["shbg"])
        bdnf_ng_ml = _get_val("bdnf_ng_ml", 25.0, ["bdnf"])
        igf1_ng_ml = _get_val("igf1_ng_ml", 190.0, ["igf1"])
        nad_plus_umol_l = _get_val("nad_plus_umol_l", 30.0, ["nad_plus", "nad"])
        hs_crp_mg_l = _get_val("hs_crp_mg_l", 0.8, ["hs_crp", "crp"])

        # ---------------------------------------------------------
        # 0. CANONICAL ENTITY RESOLUTION & DOSE AGGREGATION
        # ---------------------------------------------------------
        cat_service = CatalogService()
        compounds = cat_service.canonicalize_and_merge_stack(compounds)

        # ---------------------------------------------------------
        # 1. UNIFIED GRAPH CASCADE & COMBINED EFFECTS SIMULATION
        # ---------------------------------------------------------
        from app.services.graph_service import (
            build_selected_compound_graph,
            compute_target_combined_effects,
            resolve_stack_to_catalog_keys,
            parse_compound_spec,
            canonicalize_match_token,
        )

        timeline = profile_data.get("timeline")
        timeline_days = profile_data.get("timeline_days")

        stack_specs: List[Any] = []
        custom_doses: Dict[str, Any] = {}
        for c in compounds:
            k = str(c.get("key") or c.get("name") or "").strip()
            if not k:
                continue
            dose_val = c.get("dose") if c.get("dose") is not None else c.get("dose_mg")
            unit_val = str(c.get("unit") or "mg").strip()
            freq_val = str(c.get("frequency") or c.get("dosing_frequency") or "daily").strip()
            route_val = str(c.get("route") or c.get("route_of_administration") or c.get("default_route") or ("intramuscular" if "testosterone" in k.lower() and not any(w in k.lower() for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd", "ostarine", "s-4", "yk-11"]) else "oral")).strip().lower()
            if dose_val is not None:
                spec_dict = {
                    "key": k,
                    "dose": dose_val,
                    "unit": unit_val,
                    "frequency": freq_val,
                    "route": route_val,
                }
                stack_specs.append(spec_dict)
                parsed = parse_compound_spec(spec_dict)
                custom_doses[k.lower()] = parsed
                custom_doses[canonicalize_match_token(k)] = parsed
            else:
                stack_specs.append({"key": k, "frequency": freq_val, "route": route_val})

        graph = build_selected_compound_graph(stack_specs)
        combined_effects = compute_target_combined_effects(graph, custom_doses=custom_doses)
        resolved_keys = resolve_stack_to_catalog_keys(stack_specs)
        cascade_results = graph.propagate_cascade(
            resolved_keys or stack_specs,
            combined_effects=combined_effects,
            timeline=timeline,
            timeline_days=timeline_days,
            profile_data=profile_data,
        )

        # ---------------------------------------------------------
        # 2. HOLISTIC FULL STACK BALANCE EVALUATION
        # ---------------------------------------------------------
        full_stack_balance = self._evaluate_full_stack_balance(
            compounds=compounds,
            profile_data=profile_data,
            cascade_results=cascade_results,
            combined_effects=combined_effects,
            graph=graph,
        )

        active_mitigations = full_stack_balance.get("active_mitigations", [])
        uncompensated_risks = full_stack_balance.get("uncompensated_risks", [])

        n = len(compounds)
        matrix: List[List[Dict[str, Any]]] = []
        cyp_conflicts: List[Dict[str, Any]] = []
        transporter_conflicts: List[Dict[str, Any]] = []
        phase2_conflicts: List[Dict[str, Any]] = []
        receptor_conflicts: List[Dict[str, Any]] = []
        syndrome_alerts: List[Dict[str, Any]] = []
        synergistic_benefits: List[Dict[str, Any]] = []
        biomarker_warnings: List[Dict[str, Any]] = []

        total_risk_points = 0.0

        # Organ burden accumulator
        organ_scores = {
            "hepatic": 0.0,
            "renal": 0.0,
            "cardiovascular": 0.0,
            "cns_stimulant": 0.0,
            "sedative": 0.0,
        }

        # Accumulate individual organ burdens with route-dependent portal bypass scaling
        for comp in compounds:
            burdens = comp.get("organ_burdens", {}) or {}
            c_route = str(comp.get("route") or "oral").strip().lower()
            bypasses_first_pass = c_route in ["sublingual", "subcutaneous", "intramuscular", "transdermal", "intravenous", "inhalation"]

            for organ, weight in [
                ("hepatic", {"low": 8, "moderate": 18, "high": 35}),
                ("renal", {"low": 6, "moderate": 15, "high": 30}),
                ("cardiovascular", {"low": 8, "moderate": 20, "high": 40}),
                ("cns_stimulant", {"low": 10, "moderate": 22, "high": 45}),
                ("sedative", {"low": 6, "moderate": 16, "high": 32}),
            ]:
                b_raw = burdens.get(organ, "none")
                val = b_raw.get("level", "none").lower() if isinstance(b_raw, dict) else str(b_raw).lower()
                base_w = weight.get(val, 0)
                # First-pass portal bypass discounts hepatic strain from oral transit
                if organ == "hepatic" and bypasses_first_pass:
                    base_w = base_w * 0.50
                organ_scores[organ] += base_w

            if comp.get("is_narrow_therapeutic_index"):
                total_risk_points += 10.0

        # Discount cardiovascular organ burden for bioidentical testosterone when downstream end-effects (BP & lipids) are managed
        has_cv_mitigation = any(m.get("benefited_axis") in {"Blood Pressure", "Lipid Profile / Cardioprotective"} for m in active_mitigations)
        is_normotensive = blood_pressure <= 128
        hdl_raw = labs.get("hdl_c_mg_dl") if labs.get("hdl_c_mg_dl") is not None else labs.get("hdl")
        try:
            hdl_val_check = float(hdl_raw) if hdl_raw is not None else None
        except (ValueError, TypeError):
            hdl_val_check = None
        is_normolipidemic = hdl_val_check is None or hdl_val_check >= 40.0

        if (has_cv_mitigation or (is_normotensive and is_normolipidemic)):
            for comp in compounds:
                c_name = str(comp.get("canonical_name") or comp.get("name") or comp.get("key") or "").lower()
                d_class = str(comp.get("drug_class") or "").lower()
                is_bioidentical_test = ("testosterone" in c_name or "androgen" in d_class) and not any(w in c_name for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "sarm", "rad140", "lgd"])
                if is_bioidentical_test:
                    organ_scores["cardiovascular"] = max(0.0, organ_scores["cardiovascular"] - 30.0)

        # Evaluate pairwise collisions (N x N)
        for i in range(n):
            row: List[Dict[str, Any]] = []
            comp_a = compounds[i]
            key_a = _normalize_name(comp_a.get("key") or comp_a.get("name"))
            name_a = comp_a.get("name") or key_a

            for j in range(n):
                comp_b = compounds[j]
                key_b = _normalize_name(comp_b.get("key") or comp_b.get("name"))
                name_b = comp_b.get("name") or key_b

                if i == j:
                    row.append({
                        "source_key": key_a,
                        "source_name": name_a,
                        "target_key": key_b,
                        "target_name": name_b,
                        "is_self": True,
                        "severity": "SELF",
                        "severity_score": 0,
                        "conflict_types": [],
                        "title": f"{name_a} Monotherapy Profile",
                        "description": comp_a.get("mechanism") or comp_a.get("reason") or "Standard catalog pharmacological profile.",
                        "affected_targets": [r.get("target") for r in comp_a.get("receptor_targets", []) if isinstance(r, dict)],
                        "clinical_recommendation": f"Follow clinical dosage and routine monitoring for {name_a}.",
                        "evidence_level": comp_a.get("evidence_level", "moderate"),
                    })
                    continue

                cell_result = self._evaluate_pair(comp_a, comp_b, profile_data)

                # Check if this pair participates in an active stack-level mitigation for a RELEVANT axis
                matched_mitigation = next(
                    (
                        m for m in active_mitigations
                        if any(key_a in p.lower() or name_a.lower() in p.lower() for p in m.get("participating_compounds", []))
                        and any(key_b in p.lower() or name_b.lower() in p.lower() for p in m.get("participating_compounds", []))
                    ),
                    None,
                )

                if matched_mitigation:
                    mit_axis = str(matched_mitigation.get("benefited_axis", "")).lower()
                    conflict_types = cell_result.get("conflict_types", [])
                    is_relevant = False
                    if "blood pressure" in mit_axis and any(t in conflict_types for t in ["CARDIOVASCULAR", "HYPERTENSION", "VASOCONSTRICTION"]):
                        is_relevant = True
                    elif "lipid" in mit_axis and any(t in conflict_types for t in ["LIPID", "ATHEROGENIC"]):
                        is_relevant = True
                    elif "inflammation" in mit_axis and any(t in conflict_types for t in ["INFLAMMATION", "NFKB"]):
                        is_relevant = True
                    
                    if is_relevant:
                        cell_result["is_mitigated_by_stack"] = True
                        cell_result["mitigation_summary"] = matched_mitigation["description"]

                row.append(cell_result)

                if i < j:
                    if cell_result["severity"] in {"HIGH_RISK", "SEVERE_CONTRAINDICATION", "MODERATE_RISK"}:
                        if "CYP450" in cell_result["conflict_types"]:
                            cyp_conflicts.append(cell_result)
                        if "TRANSPORTER" in cell_result["conflict_types"]:
                            transporter_conflicts.append(cell_result)
                        if "PHASE_II" in cell_result["conflict_types"]:
                            phase2_conflicts.append(cell_result)
                        if any(t in cell_result["conflict_types"] for t in ["PHARMACODYNAMIC", "ORGAN_BURDEN", "CHELATION", "PROTEIN_BINDING", "DOWNSTREAM_CASCADE", "ELECTROLYTE_DISRUPTION"]):
                            receptor_conflicts.append(cell_result)
                        total_risk_points += cell_result["severity_score"]
                    elif cell_result["severity"] == "SYNERGISTIC":
                        synergistic_benefits.append(cell_result)
                        total_risk_points = max(0.0, total_risk_points - 5.0)

            matrix.append(row)

        # Multi-Compound Syndromic Evaluator
        syndromes = self._evaluate_multi_compound_syndromes(compounds, labs)
        for syn in syndromes:
            is_syn_mitigated = False
            syn_title = str(syn.get("title", "")).lower()
            syn_name = str(syn.get("syndrome", "")).lower()
            if "potassium" in syn_title or "potassium" in syn_name:
                # Potassium retention is only mitigated if a potassium-wasting agent (thiazide/loop diuretic) is present
                has_k_wasting = any(any(w in str(c.get("drug_class", "")).lower() or w in str(c.get("name", "")).lower() for w in ["furosemide", "hydrochlorothiazide", "thiazide", "torsemide", "loop diuretic"]) for c in compounds)
                if has_k_wasting:
                    is_syn_mitigated = True
            elif "blood pressure" in syn_title or "hypertensive" in syn_title or "hypotension" in syn_title:
                bp_axis = next((a for a in full_stack_balance.get("axes", []) if a.get("biomarker_id") == "bio_blood_pressure"), None)
                if bp_axis and (bp_axis.get("status") == "BALANCED_NORMOTENSIVE"):
                    is_syn_mitigated = True

            if is_syn_mitigated:
                syn["is_mitigated"] = True
                syn["mitigation_summary"] = "Counterbalanced by full stack physiological equilibrium."
            else:
                total_risk_points += syn["severity_score"]

            syndrome_alerts.append(syn)

        # Dynamic Biomarker Vector Convergence Evaluator
        vector_alerts = self._evaluate_biomarker_vector_convergence(compounds, labs)
        for valert in vector_alerts:
            # Check if this alert was successfully counterbalanced by full stack balance
            is_mitigated = False
            if "blood pressure" in str(valert.get("title", "")).lower() or "hypertensive" in str(valert.get("title", "")).lower():
                bp_axis = next((a for a in full_stack_balance.get("axes", []) if a.get("biomarker_id") == "bio_blood_pressure"), None)
                if bp_axis and (bp_axis.get("status") == "BALANCED_NORMOTENSIVE" or bp_axis.get("in_safe_range")):
                    is_mitigated = True
            elif "potassium" in str(valert.get("title", "")).lower():
                k_axis = next((a for a in full_stack_balance.get("axes", []) if a.get("biomarker_id") in {"bio_serum_potassium", "bio_potassium"}), None)
                if k_axis and k_axis.get("in_safe_range"):
                    is_mitigated = True

            valert["is_mitigated"] = is_mitigated
            if not is_mitigated:
                if not any(valert.get("syndrome") == s.get("syndrome") or valert.get("title") == s.get("title") for s in syndrome_alerts):
                    syndrome_alerts.append(valert)
                    total_risk_points += valert["severity_score"]

        # Add uncompensated risk alerts from holistic full-stack analysis
        for ur in uncompensated_risks:
            biomarker_warnings.append({
                "biomarker": ur.get("axis", "Physiological Axis"),
                "value": ur.get("title"),
                "severity": ur.get("severity", "HIGH_RISK"),
                "title": ur.get("title"),
                "description": ur.get("description"),
                "clinical_recommendation": ur.get("clinical_recommendation"),
            })

        # Laboratory & Biomarker Interplay Triggers
        # 1. Hepatic Clearance Strain
        if (alt_u_l > 50 or ast_u_l > 50 or total_bilirubin > 1.5) and organ_scores["hepatic"] > 15:
            warning = {
                "biomarker": "Hepatic Transaminases (ALT/AST)",
                "value": f"ALT {alt_u_l} U/L, AST {ast_u_l} U/L",
                "severity": "HIGH_RISK" if (alt_u_l > 75 or ast_u_l > 75) else "MODERATE_RISK",
                "title": "Hepatic Metabolic Strain & Clearance Impairment",
                "description": f"Elevated transaminases (ALT {alt_u_l} U/L) combined with multiple hepatically metabolized compounds impairs Phase I/II clearance and elevates hepatotoxicity risk.",
                "clinical_recommendation": "Dose reduce hepatic substrates, introduce liver support (NAC / TUDCA), and repeat hepatic panel in 4 weeks.",
            }
            biomarker_warnings.append(warning)

        # 2. Renal Impairment & Reduced GFR
        if egfr < 60 or creatinine_mg_dl > 1.3:
            renal_compounds = [
                str(c.get("name") or c.get("canonical_name") or c.get("key") or "").strip()
                for c in compounds 
                if "renal" in str(c.get("clearance_routes", "")).lower() 
                or (isinstance(c.get("organ_burdens", {}).get("renal"), dict) and c.get("organ_burdens", {}).get("renal", {}).get("level", "").lower() in {"moderate", "high", "severe"})
                or str(c.get("organ_burdens", {}).get("renal", "")).lower() in {"moderate", "high", "severe"}
            ]
            renal_compounds = [rc for rc in renal_compounds if rc]
            warning = {
                "biomarker": "eGFR / Renal Function",
                "value": f"eGFR {egfr} mL/min/1.73m², Cr {creatinine_mg_dl} mg/dL",
                "severity": "HIGH_RISK" if egfr < 45 else "MODERATE_RISK",
                "title": "Reduced Glomerular Filtration & Renal Clearance",
                "description": f"Baseline eGFR of {egfr} mL/min impairs clearance of renally eliminated compounds ({', '.join(renal_compounds[:3]) or 'stack entries'}), risking cumulative toxicity.",
                "clinical_recommendation": "Calculate CrCl and adjust dosing according to renal titration guidelines. Monitor serum creatinine and BUN.",
            }
            biomarker_warnings.append(warning)

        # 3. Potassium & Electrolyte Dysregulation
        if potassium_meq_l > 5.0 and any(_is_potassium_sparing_or_raas(c)[0] or (c.get("drug_class") and any(dc in c.get("drug_class").lower() for dc in ["arb", "ace inhibitor", "angiotensin", "potassium", "aldosterone", "mineralocorticoid", "cardiovascular"])) for c in compounds):
            warning = {
                "biomarker": "Serum Potassium (K+)",
                "value": f"{potassium_meq_l} mEq/L (Hyperkalemia Risk)",
                "severity": "HIGH_RISK",
                "title": "Hyperkalemia Collision with Renin-Angiotensin Blockade",
                "description": f"Serum potassium at {potassium_meq_l} mEq/L with active RAAS inhibitors increases cardiac electrophysiological risk and arrhythmia.",
                "clinical_recommendation": "Avoid potassium supplementation, restrict dietary potassium boluses, and monitor ECG and renal function.",
            }
            biomarker_warnings.append(warning)

        # 4. Sympathetic Hypertensive Strain (only if not mitigated by stack)
        bp_axis_check = next((a for a in full_stack_balance.get("axes", []) if a.get("biomarker_id") == "bio_blood_pressure"), None)
        if blood_pressure > 130 and (organ_scores["cns_stimulant"] > 15 or organ_scores["cardiovascular"] > 25) and (not bp_axis_check or bp_axis_check.get("status") != "BALANCED_NORMOTENSIVE"):
            warning = {
                "biomarker": "Blood Pressure",
                "value": f"{blood_pressure} mmHg",
                "severity": "HIGH_RISK" if blood_pressure > 140 else "MODERATE_RISK",
                "title": "Sympathetic Hypertensive Overload",
                "description": f"Elevated baseline BP ({blood_pressure} mmHg) combined with active stimulant or cardiovascular load accelerates arterial wall shear stress and tachycardia risk.",
                "clinical_recommendation": "Offset stimulant timing, introduce vasodilators / L-Theanine, and monitor twice-daily resting BP.",
            }
            biomarker_warnings.append(warning)

        # 5. Sleep Deprivation & Stimulant Resilience
        if sleep_hours < 6.0 and organ_scores["cns_stimulant"] > 10:
            warning = {
                "biomarker": "Sleep Duration",
                "value": f"{sleep_hours} hrs/night",
                "severity": "MODERATE_RISK",
                "title": "Adenosine Buildup & Stimulant Tolerance Escalation",
                "description": f"Chronic sleep restriction ({sleep_hours} hrs) causes compensatory central adenosine upregulation, predisposing to crash fatigue, anxiety, and HPA axis exhaustion.",
                "clinical_recommendation": "Strict cutoff for stimulants 8-10 hours prior to bedtime. Prioritize sleep extension.",
            }
            biomarker_warnings.append(warning)

        # 6. Elevated Viscosity & Hematocrit
        if hematocrit_pct > 50.0:
            warning = {
                "biomarker": "Hematocrit",
                "value": f"{hematocrit_pct}%",
                "severity": "MODERATE_RISK",
                "title": "Elevated Blood Viscosity",
                "description": f"Hematocrit at {hematocrit_pct}% elevates peripheral vascular resistance and thrombotic risk.",
                "clinical_recommendation": "Maintain strict 3-4L daily fluid intake with balanced electrolytes.",
            }
            biomarker_warnings.append(warning)

        # 7. Atherogenic Lipid Disruption
        hdl_raw = labs.get("hdl_c_mg_dl") if labs.get("hdl_c_mg_dl") is not None else labs.get("hdl")
        ldl_raw = labs.get("ldl_mg_dl") if labs.get("ldl_mg_dl") is not None else labs.get("ldl_c_mg_dl")
        try:
            hdl_val = float(hdl_raw) if hdl_raw is not None else None
        except (ValueError, TypeError):
            hdl_val = None
        try:
            ldl_val = float(ldl_raw) if ldl_raw is not None else None
        except (ValueError, TypeError):
            ldl_val = None

        if (hdl_val is not None and hdl_val < 35.0) or (ldl_val is not None and ldl_val > 135.0):
            has_lipid_mitigation = any("Lipid" in m.get("title", "") for m in active_mitigations)
            if not has_lipid_mitigation:
                warning = {
                    "biomarker": "Lipid Panel (HDL / LDL)",
                    "value": f"HDL {hdl_val if hdl_val is not None else 'N/A'} mg/dL, LDL {ldl_val if ldl_val is not None else 'N/A'} mg/dL",
                    "severity": "HIGH_RISK" if ((hdl_val is not None and hdl_val < 28) or (ldl_val is not None and ldl_val > 160)) else "MODERATE_RISK",
                    "title": "Atherogenic Lipid Disruption & Cardio-Metabolic Strain",
                    "description": f"Uncompensated atherogenic lipid shift (HDL {hdl_val if hdl_val is not None else 'N/A'} mg/dL, LDL {ldl_val if ldl_val is not None else 'N/A'} mg/dL) elevates cardiovascular endothelial risk.",
                    "clinical_recommendation": "Incorporate lipid protection (Pitavastatin 2 mg daily or Ezetimibe) and optimize dietary fats.",
                }
                biomarker_warnings.append(warning)

        # 8. Hypermetabolic Thyrotoxic & Sympathomimetic Strain
        if (free_t3_pg_ml > 4.2 or any("thyroid" in str(c.get("drug_class", "")).lower() or "t3" in str(c.get("key", "")).lower() for c in compounds)) and (heart_rate > 85.0 or organ_scores["cardiovascular"] > 20):
            warning = {
                "biomarker": "Free T3 / Metabolic Rate / Heart Rate",
                "value": f"Free T3 {free_t3_pg_ml} pg/mL, HR {heart_rate} bpm",
                "severity": "HIGH_RISK" if (free_t3_pg_ml > 5.0 or heart_rate > 95.0) else "MODERATE_RISK",
                "title": "Hypermetabolic Thyrotoxic & Sympathomimetic Strain",
                "description": f"Elevated Free T3 ({free_t3_pg_ml} pg/mL) coupled with cardiovascular/stimulant load accelerates metabolic rate, oxygen consumption, and chronotropic demand ({heart_rate} bpm).",
                "clinical_recommendation": "Titrate down thermogenic / thyroid doses. Monitor resting heart rate and ECG.",
            }
            biomarker_warnings.append(warning)

        # 9. Vagal Tone Depletion / Low Heart Rate Variability (HRV)
        if hrv_rmssd_ms < 25.0 and (organ_scores["cns_stimulant"] > 10 or heart_rate > 80.0):
            warning = {
                "biomarker": "Heart Rate Variability (HRV RMSSD)",
                "value": f"{hrv_rmssd_ms} ms (Low Parasympathetic Tone)",
                "severity": "MODERATE_RISK",
                "title": "Vagal Tone Withdrawal & Autonomic Sympathetic Overdrive",
                "description": f"Resting HRV RMSSD at {hrv_rmssd_ms} ms under active CNS stimulant load indicates suppressed vagal tone and elevated autonomic strain.",
                "clinical_recommendation": "Integrate parasympathetic adaptogens (L-Theanine, Ashwagandha, Magnesium Glycinate) and establish daytime stimulant cutoffs.",
            }
            biomarker_warnings.append(warning)

        # 10. Insulin Resistance & Hyperinsulinemic Strain
        if homa_ir > 2.5 or fasting_insulin_u_iu_ml > 12.0:
            warning = {
                "biomarker": "Fasting Insulin / HOMA-IR",
                "value": f"Insulin {fasting_insulin_u_iu_ml} uIU/mL, HOMA-IR {homa_ir}",
                "severity": "HIGH_RISK" if homa_ir > 3.5 else "MODERATE_RISK",
                "title": "Peripheral Insulin Resistance & Hyperinsulinemic Strain",
                "description": f"Fasting insulin ({fasting_insulin_u_iu_ml} uIU/mL) and HOMA-IR ({homa_ir}) indicate compromised insulin sensitivity and metabolic strain.",
                "clinical_recommendation": "Incorporate insulin sensitizers (Metformin, Berberine, Inositol), optimize carbohydrate distribution, and monitor fasting glucose.",
            }
            biomarker_warnings.append(warning)

        # 11. Systemic Chronic Inflammation (hs-CRP)
        if hs_crp_mg_l > 3.0:
            warning = {
                "biomarker": "High-Sensitivity C-Reactive Protein (hs-CRP)",
                "value": f"{hs_crp_mg_l} mg/L",
                "severity": "HIGH_RISK" if hs_crp_mg_l > 5.0 else "MODERATE_RISK",
                "title": "Systemic Micro-Vascular Inflammation (Elevated hs-CRP)",
                "description": f"Serum hs-CRP of {hs_crp_mg_l} mg/L indicates active vascular inflammation, amplifying endothelial shear damage and atherogenic progression.",
                "clinical_recommendation": "Incorporate anti-inflammatory support (Curcumin with piperine, Omega-3 fatty acids 2-4g/day) and identify inflammatory drivers.",
            }
            biomarker_warnings.append(warning)

        # ---------------------------------------------------------
        # FIRST-PRINCIPLES MULTI-DOMAIN DE-DUPLICATED RISK ENGINE
        # ---------------------------------------------------------
        # Domain mapping partitions distinct physiological systems to eliminate multi-counting
        domain_items: Dict[str, List[float]] = {
            "metabolic": [],
            "cardiovascular": [],
            "renal_electrolyte": [],
            "hepatic": [],
            "neuro_autonomic": [],
            "endocrine_hemostatic": [],
        }

        for c in (cyp_conflicts + transporter_conflicts + phase2_conflicts):
            if not c.get("is_mitigated_by_stack"):
                domain_items["metabolic"].append(float(c.get("severity_score", 15.0)))

        for c in receptor_conflicts:
            if not c.get("is_mitigated_by_stack"):
                ctypes = c.get("conflict_types", [])
                score_val = float(c.get("severity_score", 20.0))
                if any(t in ctypes for t in ["ELECTROLYTE_DISRUPTION", "RENAL"]):
                    domain_items["renal_electrolyte"].append(score_val)
                elif any(t in ctypes for t in ["CNS_STIMULANT", "SEDATION", "SEROTONIN"]):
                    domain_items["neuro_autonomic"].append(score_val)
                else:
                    domain_items["cardiovascular"].append(score_val)

        for s in syndrome_alerts:
            if not s.get("is_mitigated"):
                stitle = str(s.get("title", "")).lower()
                s_score = float(s.get("severity_score", 25.0))
                if "potassium" in stitle or "electrolyte" in stitle or "renal" in stitle:
                    domain_items["renal_electrolyte"].append(s_score)
                elif "serotonin" in stitle or "sedation" in stitle or "stimulant" in stitle or "hrv" in stitle or "vagal" in stitle:
                    domain_items["neuro_autonomic"].append(s_score)
                elif "hepatic" in stitle or "liver" in stitle:
                    domain_items["hepatic"].append(s_score)
                elif "metabolic" in stitle or "thyroid" in stitle or "insulin" in stitle:
                    domain_items["metabolic"].append(s_score)
                else:
                    domain_items["cardiovascular"].append(s_score)

        for bw in biomarker_warnings:
            b_score = 22.0 if bw.get("severity") == "HIGH_RISK" else 14.0
            btitle = str(bw.get("title", "")).lower()
            if "hepatic" in btitle or "alt" in btitle or "transaminase" in btitle:
                domain_items["hepatic"].append(b_score)
            elif "renal" in btitle or "egfr" in btitle or "creatinine" in btitle or "potassium" in btitle:
                domain_items["renal_electrolyte"].append(b_score)
            elif "blood pressure" in btitle or "hypertensive" in btitle or "heart" in btitle:
                domain_items["cardiovascular"].append(b_score)
            elif "sleep" in btitle or "stimulant" in btitle or "adenosine" in btitle or "vagal" in btitle or "hrv" in btitle:
                domain_items["neuro_autonomic"].append(b_score)
            elif "metabolic" in btitle or "insulin" in btitle or "thyrotoxic" in btitle or "bmr" in btitle:
                domain_items["metabolic"].append(b_score)
            else:
                domain_items["endocrine_hemostatic"].append(b_score)

        # Intra-domain non-redundant score calculation: S_domain = S_max + 0.25 * sum(S_other)
        domain_scores: Dict[str, float] = {}
        for dname, scores in domain_items.items():
            if not scores:
                domain_scores[dname] = 0.0
            else:
                s_max = max(scores)
                s_other = sum(s for s in scores if s != s_max)
                domain_scores[dname] = s_max + (0.25 * s_other)

        # Apply domain organ burden weighting
        if organ_scores["cardiovascular"] > 25:
            domain_scores["cardiovascular"] += (organ_scores["cardiovascular"] - 25) * 0.15
        if organ_scores["cns_stimulant"] > 20:
            domain_scores["neuro_autonomic"] += (organ_scores["cns_stimulant"] - 20) * 0.15
        if organ_scores["hepatic"] > 25:
            domain_scores["hepatic"] += (organ_scores["hepatic"] - 25) * 0.15
        if organ_scores["renal"] > 25:
            domain_scores["renal_electrolyte"] += (organ_scores["renal"] - 25) * 0.15

        # Subtract active mitigation credits
        total_mitigation_reduction = sum(float(m.get("risk_reduction_points", 0.0)) for m in active_mitigations)
        raw_domain_sum = max(0.0, sum(domain_scores.values()) - total_mitigation_reduction)

        # Multi-domain asymptotic hazard integration: R = 100 * (1 - exp(-raw_sum / 60.0))
        if raw_domain_sum == 0.0 or (n <= 1 and not any(domain_scores.values())):
            cumulative_score = 0
        else:
            asymptotic_val = 100.0 * (1.0 - math.exp(-raw_domain_sum / 60.0))
            cumulative_score = min(100, round(asymptotic_val))

        # Filter unmitigated conflicts
        unmitigated_cyp = [c for c in cyp_conflicts if not c.get("is_mitigated_by_stack")]
        unmitigated_transporter = [c for c in transporter_conflicts if not c.get("is_mitigated_by_stack")]
        unmitigated_phase2 = [c for c in phase2_conflicts if not c.get("is_mitigated_by_stack")]
        unmitigated_receptor = [c for c in receptor_conflicts if c.get("severity") in {"HIGH_RISK", "SEVERE_CONTRAINDICATION", "MODERATE_RISK"} and not c.get("is_mitigated_by_stack")]
        unmitigated_syndromes = [s for s in syndrome_alerts if s.get("severity") in {"HIGH_RISK", "SEVERE_CONTRAINDICATION"} and not s.get("is_mitigated")]

        conflict_count = (
            len(unmitigated_cyp)
            + len(unmitigated_transporter)
            + len(unmitigated_phase2)
            + len(unmitigated_receptor)
            + len(unmitigated_syndromes)
            + len(uncompensated_risks)
        )
        synergy_count = len(synergistic_benefits) + len(active_mitigations)

        has_severe_unmitigated = any(s.get("severity") == "SEVERE_CONTRAINDICATION" and not s.get("is_mitigated") for s in syndrome_alerts) or any(
            any(c.get("severity") == "SEVERE_CONTRAINDICATION" and not c.get("is_mitigated_by_stack") for c in row if not c.get("is_self")) for row in matrix
        )

        has_high_unmitigated = any(
            c.get("severity") == "HIGH_RISK" and not c.get("is_mitigated_by_stack")
            for c in (receptor_conflicts + cyp_conflicts + transporter_conflicts + phase2_conflicts)
        ) or any(s.get("severity") == "HIGH_RISK" and not s.get("is_mitigated") for s in syndrome_alerts)

        if len(active_mitigations) > 0 and len(uncompensated_risks) == 0 and conflict_count == 0:
            cumulative_score = min(cumulative_score, 18)

        if has_severe_unmitigated:
            cumulative_score = max(76, cumulative_score)
            risk_band = "SEVERE"
        elif cumulative_score > 75:
            risk_band = "SEVERE"
        elif has_high_unmitigated:
            cumulative_score = max(46, cumulative_score)
            risk_band = "ELEVATED"
        elif cumulative_score > 45:
            risk_band = "ELEVATED"
        elif cumulative_score > 25:
            risk_band = "MODERATE"
        elif cumulative_score > 10:
            risk_band = "LOW"
        else:
            risk_band = "MINIMAL"

        if len(active_mitigations) > 0 and len(uncompensated_risks) == 0 and conflict_count <= len(active_mitigations):
            summary = f"Holistic Stack Equilibrium: Detected {len(active_mitigations)} active protective counterbalance(s) with clean dose compensation ({cumulative_score}/100 cumulative risk)."
        elif conflict_count == 0 and synergy_count > 0:
            summary = f"Optimal stack synergy detected with {synergy_count} positive pharmacological pairing(s) and clean metabolic compatibility."
        elif conflict_count > 0:
            summary = f"Detected {conflict_count} interaction conflict(s) across metabolism, transporters, and organ pathways with a {risk_band.lower()} risk profile ({cumulative_score}/100)."
        else:
            summary = f"Clean pharmacological compatibility with standard clinical monitoring recommended. Overall risk is {risk_band.lower()} ({cumulative_score}/100)."

        from app.services.synergy_engine import SynergyEngine
        synergy_analysis = SynergyEngine().evaluate_multi_agent_synergy(compounds)

        return {
            "matrix": matrix,
            "synergy_analysis": synergy_analysis,
            "compounds": [
                {
                    "key": _normalize_name(c.get("key") or c.get("name")),
                    "name": c.get("name") or c.get("key"),
                    "drug_class": c.get("drug_class"),
                    "risk_band": c.get("risk_band", "low"),
                    "dose": c.get("dose"),
                    "unit": c.get("unit", "mg"),
                    "dose_mg": c.get("dose_mg"),
                    "dose_str": c.get("dose_str"),
                    "timing": c.get("timing", "morning"),
                    "frequency": c.get("frequency", "daily"),
                    "is_narrow_therapeutic_index": bool(c.get("is_narrow_therapeutic_index")),
                }
                for c in compounds
            ],
            "cumulative_risk_score": cumulative_score,
            "risk_band": risk_band,
            "summary": summary,
            "breakdown": {
                "cyp_conflicts": cyp_conflicts,
                "transporter_conflicts": transporter_conflicts,
                "phase2_conflicts": phase2_conflicts,
                "receptor_conflicts": receptor_conflicts,
                "syndrome_alerts": syndrome_alerts,
                "organ_burdens": {
                    organ: {
                        "score": round(score, 1),
                        "level": "High" if score >= 35 else ("Moderate" if score >= 18 else ("Low" if score > 0 else "None")),
                    }
                    for organ, score in organ_scores.items()
                },
                "synergistic_benefits": synergistic_benefits,
                "biomarker_warnings": biomarker_warnings,
                "active_mitigations": active_mitigations,
                "uncompensated_risks": uncompensated_risks,
            },
            "conflict_count": conflict_count,
            "synergy_count": synergy_count,
            "synergies": synergistic_benefits,
            "full_stack_balance": full_stack_balance,
        }

    def _evaluate_full_stack_balance(
        self,
        compounds: List[Dict[str, Any]],
        profile_data: Dict[str, Any],
        cascade_results: Dict[str, Any],
        combined_effects: Dict[str, Any],
        graph: Any,
    ) -> Dict[str, Any]:
        """
        Evaluates the stack as a unified holistic pharmacological network across all physiological axes.
        Calculates dose-dependent balance, identifies active therapeutic counterbalances/mitigations,
        and flags uncompensated monotherapies or compounding strains.
        """
        axes: List[Dict[str, Any]] = []
        active_mitigations: List[Dict[str, Any]] = []
        uncompensated_risks: List[Dict[str, Any]] = []
        dose_recommendations: List[Dict[str, Any]] = []

        labs = profile_data.get("labs", {}) or {}
        shifts_by_id = {b.get("biomarker_id"): b for b in cascade_results.get("biomarker_shifts", [])}
        processed_bio_ids: Set[str] = set()

        def _to_float(v: Any, default: float = 0.0) -> float:
            if v is None:
                return float(default)
            try:
                return float(v)
            except (ValueError, TypeError):
                return float(default)

        # 1. ESTRADIOL (E2) / ENDOCRINE AXIS
        e2_shift = shifts_by_id.get("bio_estradiol")
        if e2_shift:
            processed_bio_ids.add("bio_estradiol")
            def_base, def_low, def_up = 28.0, 15.0, 50.0
            cal_base, cal_low, cal_up, e2_adjustments = get_demographic_calibrated_reference_range(
                "bio_estradiol", profile_data, def_base, def_low, def_up
            )
            baseline = _to_float(e2_shift.get("baseline_value"), cal_base)
            est_val = _to_float(e2_shift.get("estimated_value"), baseline)
            delta = _to_float(e2_shift.get("estimated_delta"), 0.0)
            unit = str(e2_shift.get("unit", "pg/mL"))
            safe_lower = _to_float(e2_shift.get("safe_lower"), cal_low)
            safe_upper = _to_float(e2_shift.get("safe_upper"), cal_up)

            contributions = e2_shift.get("compound_contributions") or e2_shift.get("contributions") or []
            has_ai = (
                any(c.get("contribution_mag", 0) < -0.05 for c in contributions)
                or any("aromatase" in str(k).lower() and float(v.get("net_activation_score", 0)) < -0.05 for k, v in combined_effects.items())
                or any(any("aromatase" in str(r.get("target", "")).lower() and "inhibitor" in str(r.get("action", "")).lower() for r in comp.get("receptor_targets", [])) for comp in compounds)
                or any("aromatase" in str(comp.get("drug_class", "")).lower() or "ai" in str(comp.get("drug_class", "")).lower() for comp in compounds)
            )
            has_androgen = (
                any(c.get("contribution_mag", 0) > 0.05 for c in contributions)
                or any(any("aromatase" in str(r.get("target", "")).lower() and "substrate" in str(r.get("action", "")).lower() for r in comp.get("receptor_targets", [])) for comp in compounds)
                or any("androgen" in str(comp.get("drug_class", "")).lower() or "testosterone" in str(comp.get("key", "")).lower() for comp in compounds)
            )

            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            participating_labels = [c.get("compound_label") for c in contributions] or [c.get("name") for c in compounds if c.get("name")]

            if has_ai and has_androgen and safe_lower <= est_val <= safe_upper:
                status = "BALANCED_TARGET"
                status_label = f"Optimal Target E2 ({est_val} {unit})"
                status_color = "#10b981"
                mitigation = {
                    "title": "Aromatase Control & Estrogenic Balance",
                    "description": (
                        f"Co-administration of Aromatase Inhibitor with Aromatizable Androgen successfully "
                        f"balances 17-beta estradiol conversion into target range ({est_val} {unit}, target {safe_lower}-{safe_upper} {unit}), "
                        f"preventing hyperestrogenic fluid retention/gynecomastia while protecting against monotherapy E2 crash."
                    ),
                    "participating_compounds": participating_labels,
                    "benefited_axis": "Estradiol (E2)",
                    "risk_reduction_points": 25.0,
                }
                active_mitigations.append(mitigation)
            elif has_ai and has_androgen and safe_upper < est_val <= (safe_upper + 5.0):
                status = "PARTIAL_COUNTERBALANCE_ELEVATED"
                status_label = f"Sub-Target Aromatase Control ({est_val} {unit})"
                status_color = "#f59e0b"
            elif has_ai and (est_val < safe_lower or not has_androgen):
                status = "HYPOESTROGENIC_CRASH"
                status_label = f"Crashed E2 Risk ({est_val} {unit})"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Estradiol (E2)",
                    "severity": "HIGH_RISK",
                    "title": "Uncompensated Aromatase Inhibition (E2 Crash)",
                    "description": f"Aromatase inhibition without sufficient androgen substrate crashes serum estradiol to {est_val} {unit}, risking arthralgia, osteopenia, mood depression, and dyslipidemia.",
                    "clinical_recommendation": "Titrate aromatase inhibitor dose downward or eliminate in the absence of elevated aromatizable androgen substrate.",
                })
                dose_recommendations.append({
                    "compound": next((c.get("compound_label") for c in contributions if c.get("contribution_mag", 0) < 0), "Aromatase Inhibitor"),
                    "action": "Reduce Dose / Taper",
                    "reason": f"Elevate serum estradiol from {est_val} {unit} back into healthy {safe_lower}-{safe_upper} {unit} range.",
                })
            elif has_androgen and est_val > safe_upper:
                status = "HYPERESTROGENIC_ELEVATION"
                status_label = f"Supraphysiological E2 ({est_val} {unit})"
                status_color = "#f59e0b"
                uncompensated_risks.append({
                    "axis": "Estradiol (E2)",
                    "severity": "MODERATE_RISK",
                    "title": "Supraphysiological Aromatization (Elevated E2)",
                    "description": f"Elevated androgen load drives estradiol to {est_val} {unit}, increasing risk of fluid retention, blood pressure elevation, and gynecomastia.",
                    "clinical_recommendation": "Monitor serum E2 and consider low-dose aromatase inhibitor titration if symptomatic.",
                })
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Physiological E2 ({est_val} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Estradiol (E2) Axis",
                "biomarker_id": "bio_estradiol",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "biometric_modifiers_applied": e2_adjustments,
            })

        # 2. BLOOD PRESSURE & CARDIOVASCULAR AXIS
        bp_shift = shifts_by_id.get("bio_blood_pressure") or shifts_by_id.get("bio_systolic_blood_pressure")
        if bp_shift:
            processed_bio_ids.add(bp_shift.get("biomarker_id"))
            def_base, def_low, def_up = 120.0, 90.0, 128.0
            cal_base, cal_low, cal_up, bp_adjustments = get_demographic_calibrated_reference_range(
                "bio_blood_pressure", profile_data, def_base, def_low, def_up
            )
            baseline = float(bp_shift.get("baseline_value", labs.get("blood_pressure") or cal_base))
            est_val = float(bp_shift.get("estimated_value", baseline))
            delta = float(bp_shift.get("estimated_delta", 0.0))
            unit = str(bp_shift.get("unit", "mmHg"))
            safe_lower = float(bp_shift.get("safe_lower") or cal_low)
            safe_upper = max(cal_up, float(bp_shift.get("safe_upper") or cal_up))

            contributions = bp_shift.get("compound_contributions") or bp_shift.get("contributions") or []
            hypertensive_comps = [c for c in contributions if c.get("contribution_mag", 0) > 0.05]
            antihypertensive_comps = [c for c in contributions if c.get("contribution_mag", 0) < -0.05]

            has_hypertensive = bool(hypertensive_comps)
            if not has_hypertensive:
                for comp in compounds:
                    d_class = str(comp.get("drug_class", "")).lower()
                    c_key = str(comp.get("key", "")).lower()
                    if "androgen" in d_class or "testosterone" in c_key or "stimulant" in d_class:
                        has_hypertensive = True
                        break
                    for r in comp.get("receptor_targets", []):
                        if any(w in str(r.get("target", "")).lower() for w in ["androgen", "erythropoietin", "ephedrine", "adra1"]):
                            has_hypertensive = True
                            break
                    if has_hypertensive:
                        break

            has_antihypertensive = bool(antihypertensive_comps)
            if not has_antihypertensive:
                for comp in compounds:
                    if _is_sympathomimetic_stimulant(comp)[0] or _is_adenosine_antagonist_or_pde_inhibitor(comp)[0] or _is_alpha2_antagonist(comp)[0]:
                        continue
                    d_class = str(comp.get("drug_class", "")).lower()

                    if any(w in d_class for w in ["arb", "angiotensin", "sartan", "beta-blocker", "antihypertensive", "calcium channel blocker", "ace inhibitor"]):
                        has_antihypertensive = True
                        break
                    for r in comp.get("receptor_targets", []):
                        t_name = str(r.get("target", "")).lower()
                        act = str(r.get("action", "")).lower()
                        if any(w in t_name for w in ["angiotensin", "agtr1", "mineralocorticoid"]):
                            if any(a in act for a in ["antagonist", "block", "inhib"]):
                                has_antihypertensive = True
                                break
                        elif "adrb1" in t_name and any(a in act for a in ["antagonist", "block"]):
                                has_antihypertensive = True
                                break
                        elif "adra2a" in t_name and any(a in act for a in ["agonist", "activat"]):
                                has_antihypertensive = True
                                break
                    if has_antihypertensive:
                        break

            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            participating_labels = [c.get("compound_label") for c in contributions] or [c.get("name") for c in compounds if c.get("name")]

            genuine_antihypertensive = any(
                _is_potassium_sparing_or_raas(c)[0] or _is_beta_blocker(c)
                or any(w in str(c.get("drug_class", "")).lower() or w in str(c.get("key", "")).lower() for w in ["arb", "ace inhibitor", "beta-blocker", "calcium channel blocker", "telmisartan", "nebivolol", "amlodipine"])
                for c in compounds
            )
            genuine_hypertensive = any(
                "androgen" in str(c.get("drug_class", "")).lower() or "anabolic" in str(c.get("drug_class", "")).lower()
                or "testosterone" in str(c.get("key", "")).lower()
                or _is_sympathomimetic_stimulant(c)[0]
                or _is_alpha2_antagonist(c)[0]
                for c in compounds
            )

            if has_hypertensive and has_antihypertensive and genuine_antihypertensive and genuine_hypertensive and 90.0 <= est_val <= 128.0:
                status = "BALANCED_NORMOTENSIVE"
                status_label = f"Normotensive Equilibrium ({est_val} {unit})"
                status_color = "#10b981"

                mitigation = {
                    "title": "Hemodynamic & Vascular Counterbalance",
                    "description": (
                        f"Antihypertensive / RAAS blockade counteracts androgenic and sympathetic vasoconstrictive pressure, "
                        f"maintaining stable normotensive resting blood pressure ({est_val} {unit}, target 115-125 {unit})."
                    ),
                    "participating_compounds": participating_labels,
                    "benefited_axis": "Blood Pressure",
                    "risk_reduction_points": 20.0,
                }
                active_mitigations.append(mitigation)
            elif est_val >= 135.0 and len(hypertensive_comps) >= 2:
                status = "HYPERTENSIVE_STRAIN"
                status_label = f"Vascular Shear Stress ({est_val} {unit})"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Blood Pressure",
                    "severity": "HIGH_RISK",
                    "title": "Compounded Hypertensive Overload",
                    "description": f"Multiple concurrent vasoconstrictive and adrenergic agents elevate resting blood pressure to {est_val} {unit}, accelerating endothelial strain.",
                    "clinical_recommendation": "Introduce RAAS blockade (Telmisartan) or vasodilatory support, and monitor daily BP.",
                })
            elif est_val >= 135.0 and any(c.get("drug_class") and any(w in str(c.get("drug_class")).lower() for w in ["arb", "sartan", "angiotensin"]) for c in compounds):
                status = "HYPERTENSIVE_STRAIN"
                status_label = f"Vascular Shear Stress ({est_val} {unit})"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Blood Pressure",
                    "severity": "HIGH_RISK",
                    "title": "Breakthrough Hypertensive Strain",
                    "description": f"Despite co-administered antihypertensive support, resting blood pressure remains elevated at {est_val} {unit}, exceeding the safe upper bound ({safe_upper} {unit}).",
                    "clinical_recommendation": "Titrate RAAS blockade (e.g. increase Telmisartan dose) or reduce vasoconstrictive/androgen load, and monitor daily BP.",
                })
            elif est_val < 85.0 and len(antihypertensive_comps) >= 2:
                status = "HYPOTENSIVE_RISK"
                status_label = f"Hypotension Vulnerability ({est_val} {unit})"
                status_color = "#f59e0b"
                uncompensated_risks.append({
                    "axis": "Blood Pressure",
                    "severity": "MODERATE_RISK",
                    "title": "Additive Blood Pressure Depletion",
                    "description": f"Concurrent vasodilators depress blood pressure to {est_val} {unit}, risking lightheadedness and orthostatic hypotension.",
                    "clinical_recommendation": "Titrate antihypertensive dose downward to maintain MAP > 70 mmHg.",
                })
            elif est_val > 128.0:
                if has_hypertensive and has_antihypertensive:
                    status = "PARTIAL_COUNTERBALANCE_ELEVATED"
                    status_label = f"Sub-Target Attenuation ({est_val} {unit})"
                    status_color = "#f59e0b"
                else:
                    status = "ELEVATED_VASCULAR_TONE"
                    status_label = f"Elevated Vascular Tone ({est_val} {unit})"
                    status_color = "#f59e0b"
            else:
                status = "NORMAL_NORMOTENSIVE"
                status_label = f"Normotensive Baseline ({est_val} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Blood Pressure & Vascular Axis",
                "biomarker_id": bp_shift.get("biomarker_id", "bio_blood_pressure"),
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "biometric_modifiers_applied": bp_adjustments,
            })

        # 3. ANDROGEN / 5AR-DHT AXIS
        dht_shift = shifts_by_id.get("bio_dht") or shifts_by_id.get("bio_dihydrotestosterone")
        if dht_shift:
            processed_bio_ids.add(dht_shift.get("biomarker_id"))
            processed_bio_ids.add("bio_dht")
            processed_bio_ids.add("bio_dihydrotestosterone")
            cal_base_dht, cal_low_dht, cal_up_dht, dht_adjustments = get_demographic_calibrated_reference_range(
                "bio_dht", profile_data, 45.0, 30.0, 85.0
            )
            baseline = float(dht_shift.get("baseline_value", cal_base_dht))
            est_val = float(dht_shift.get("estimated_value", baseline))
            delta = float(dht_shift.get("estimated_delta", 0.0))
            unit = str(dht_shift.get("unit", "ng/dL"))
            safe_lower = float(dht_shift.get("safe_lower", cal_low_dht))
            safe_upper = float(dht_shift.get("safe_upper", cal_up_dht))

            contributions = dht_shift.get("compound_contributions") or dht_shift.get("contributions") or []
            has_5ari = any(c.get("contribution_mag", 0) < -0.05 for c in contributions) or any(
                any("5-alpha" in str(r.get("target", "")).lower() and "inhibitor" in str(r.get("action", "")).lower() for r in comp.get("receptor_targets", [])) for comp in compounds
            )
            has_androgen = any(c.get("contribution_mag", 0) > 0.05 for c in contributions) or any(
                any("5-alpha" in str(r.get("target", "")).lower() and "substrate" in str(r.get("action", "")).lower() for r in comp.get("receptor_targets", [])) for comp in compounds
            )

            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            participating_dht_comps = [c.get("name") or c.get("key") for c in compounds if any(w in str(c.get("drug_class", "")).lower() or w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower() for w in ["androgen", "5-alpha", "finasteride", "dutasteride", "testosterone"])]

            if has_androgen and has_5ari and safe_lower <= est_val <= safe_upper:
                status = "BALANCED_TARGET"
                status_label = f"Controlled 5AR Conversion ({est_val} {unit})"
                status_color = "#10b981"
                active_mitigations.append({
                    "title": "5-Alpha Reductase & DHT Attenuation",
                    "description": (
                        f"5-alpha reductase inhibitor co-administration (Finasteride/Dutasteride) safely prevents supra-physiological "
                        f"DHT conversion ({est_val} {unit}, target {safe_lower:g}-{safe_upper:g} {unit}), mitigating androgenic alopecia and benign prostatic hyperplasia."
                    ),
                    "participating_compounds": participating_dht_comps,
                    "benefited_axis": "Dihydrotestosterone (DHT) / 5AR",
                    "risk_reduction_points": 20.0,
                })
            elif est_val > safe_upper:
                status = "ELEVATED_DHT"
                status_label = f"Elevated DHT Load ({est_val} {unit})"
                status_color = "#f59e0b"
            elif est_val < safe_lower * 0.5:
                status = "SUPPRESSED_DHT"
                status_label = f"Suppressed DHT ({est_val} {unit})"
                status_color = "#60a5fa"
            else:
                status = "NORMAL_RANGE"
                status_label = f"Baseline DHT ({est_val} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Androgen & 5AR-DHT Axis",
                "biomarker_id": dht_shift.get("biomarker_id", "bio_dht"),
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "biometric_modifiers_applied": dht_adjustments,
            })

        # 4. AUTONOMIC & CHRONOTROPIC AXIS
        hr_shift = shifts_by_id.get("bio_resting_heart_rate") or shifts_by_id.get("bio_heart_rate")
        if hr_shift:
            processed_bio_ids.add(hr_shift.get("biomarker_id"))
            processed_bio_ids.add("bio_resting_heart_rate")
            processed_bio_ids.add("bio_heart_rate")
            cal_base_hr, cal_low_hr, cal_up_hr, hr_adjustments = get_demographic_calibrated_reference_range(
                "bio_resting_heart_rate", profile_data, labs.get("heart_rate") or 72.0, 60.0, 85.0
            )
            baseline = _to_float(hr_shift.get("baseline_value"), cal_base_hr)
            est_val = _to_float(hr_shift.get("estimated_value"), baseline)
            delta = _to_float(hr_shift.get("estimated_delta"), 0.0)
            unit = str(hr_shift.get("unit", "bpm"))
            safe_lower = _to_float(hr_shift.get("safe_lower"), cal_low_hr)
            safe_upper = _to_float(hr_shift.get("safe_upper"), cal_up_hr)

            contributions = hr_shift.get("compound_contributions") or hr_shift.get("contributions") or []
            has_stim = any(c.get("contribution_mag", 0) > 0.05 for c in contributions)
            has_calm = any(c.get("contribution_mag", 0) < -0.05 for c in contributions)

            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            participating_hr_comps = [c.get("name") or c.get("key") for c in compounds if any(w in str(c.get("drug_class", "")).lower() or w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower() for w in ["stimulant", "caffeine", "theanine", "ashwagandha", "beta blocker", "nebivolol", "propranolol"])]

            if has_stim and has_calm and safe_lower <= est_val <= safe_upper:
                status = "BALANCED_AUTONOMIC"
                status_label = f"Autonomic Balance ({est_val} {unit})"
                status_color = "#10b981"
                active_mitigations.append({
                    "title": "Autonomic Buffering & Chronotropic Stability",
                    "description": (
                        f"Sympathetic overdrive from CNS stimulants is actively cushioned by GABAergic/anxiolytic or cardioselective beta-blocker co-administration "
                        f"(e.g., L-Theanine or Nebivolol), maintaining healthy resting heart rate ({est_val} {unit}, target {safe_lower:g}-{safe_upper:g} {unit})."
                    ),
                    "participating_compounds": participating_hr_comps,
                    "benefited_axis": "Resting Heart Rate / Chronotropic",
                    "risk_reduction_points": 15.0,
                })
            elif est_val > 90.0:
                status = "TACHYCARDIA_RISK"
                status_label = f"Elevated Heart Rate ({est_val} {unit})"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Resting Heart Rate",
                    "severity": "HIGH_RISK",
                    "title": "Uncompensated Tachycardia & Inotropic Load",
                    "description": f"Stimulant load drives resting heart rate to {est_val} {unit} without sufficient autonomic buffering.",
                    "clinical_recommendation": "Reduce stimulant dosage, avoid stacking sympathomimetics, and incorporate L-Theanine (200 mg) or cardioselective beta-blockade.",
                })
            elif est_val > safe_upper:
                status = "SYMPATHETIC_DOMINANCE"
                status_label = f"Borderline Heart Rate ({est_val} {unit})"
                status_color = "#f59e0b"
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Resting Heart Rate ({est_val} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Autonomic & Chronotropic Axis",
                "biomarker_id": "bio_resting_heart_rate",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "biometric_modifiers_applied": hr_adjustments,
            })

        # 5. RENAL & POTASSIUM AXIS
        k_shift = shifts_by_id.get("bio_serum_potassium") or shifts_by_id.get("bio_potassium")
        if k_shift:
            processed_bio_ids.add(k_shift.get("biomarker_id"))
            processed_bio_ids.add("bio_serum_potassium")
            processed_bio_ids.add("bio_potassium")
            cal_base_k, cal_low_k, cal_up_k, k_adjustments = get_demographic_calibrated_reference_range(
                "bio_serum_potassium", profile_data, labs.get("potassium_meq_l") or 4.2, 3.5, 5.0
            )
            baseline = _to_float(k_shift.get("baseline_value"), cal_base_k)
            est_val = _to_float(k_shift.get("estimated_value"), baseline)
            delta = _to_float(k_shift.get("estimated_delta"), 0.0)
            unit = str(k_shift.get("unit", "mEq/L"))
            safe_lower = _to_float(k_shift.get("safe_lower"), cal_low_k)
            safe_upper = _to_float(k_shift.get("safe_upper"), cal_up_k)

            contributions = k_shift.get("contributions") or []
            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            status = "EUVOLEMIC_NORMAL" if safe_lower <= est_val <= safe_upper else ("HYPERKALEMIA_RISK" if est_val > safe_upper else "HYPOKALEMIA_RISK")
            status_color = "#10b981" if safe_lower <= est_val <= safe_upper else "#ef4444"

            axes.append({
                "name": "Electrolyte & Potassium Axis",
                "biomarker_id": k_shift.get("biomarker_id", "bio_serum_potassium"),
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": f"Serum K+ ({est_val} {unit})",
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "biometric_modifiers_applied": k_adjustments,
            })

        # 6. SYSTEMIC OXIDATIVE STRESS & REDOX AXIS
        gsh_shift = shifts_by_id.get("bio_gsh_redox_ratio")
        mda_shift = shifts_by_id.get("bio_mda")
        if True:  # Always include Systemic Oxidative Stress & Redox Axis in Full Stack Equilibrium
            primary_redox = gsh_shift or mda_shift or {}
            bio_id = primary_redox.get("biomarker_id", "bio_gsh_redox_ratio")
            processed_bio_ids.add("bio_gsh_redox_ratio")
            processed_bio_ids.add("bio_mda")

            is_gsh = bio_id == "bio_gsh_redox_ratio"
            baseline = _to_float(primary_redox.get("baseline_value"), labs.get("gsh_redox_ratio") or (100.0 if is_gsh else 1.2))
            est_val = _to_float(primary_redox.get("estimated_value"), baseline)
            delta = _to_float(primary_redox.get("estimated_delta"), 0.0)
            unit = str(primary_redox.get("unit", "ratio" if is_gsh else "μmol/L"))
            safe_lower = _to_float(primary_redox.get("safe_lower"), 80.0 if is_gsh else 0.5)
            safe_upper = _to_float(primary_redox.get("safe_upper"), 160.0 if is_gsh else 1.8)
            
            contributions = primary_redox.get("compound_contributions") or primary_redox.get("contributions") or []
            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            is_gsh = bio_id == "bio_gsh_redox_ratio"
            pos_contribs = [c for c in contributions if (c.get("contribution_mag", 0) > 0.03 if is_gsh else c.get("contribution_mag", 0) < -0.03)]
            neg_contribs = [c for c in contributions if (c.get("contribution_mag", 0) < -0.03 if is_gsh else c.get("contribution_mag", 0) > 0.03)]
            in_safe = (est_val >= safe_lower) if is_gsh else (safe_lower <= est_val <= safe_upper)

            if pos_contribs and neg_contribs and in_safe:
                status = "BALANCED_TARGET"
                status_label = f"Redox Homeostasis ({est_val} {unit})"
                status_color = "#10b981"
                participating_labels = [c.get("compound_label") for c in contributions if abs(c.get("contribution_mag", 0)) > 0.02]
                active_mitigations.append({
                    "title": "Oxidative Stress & Redox Protection",
                    "description": (
                        f"Co-administration of antioxidant / cytoprotective support successfully neutralizes xenobiotic and metabolic reactive oxygen species, "
                        f"preserving intracellular glutathione reserves (GSH:GSSG ratio {est_val} {unit}) and suppressing lipid peroxidation."
                    ),
                    "participating_compounds": participating_labels,
                    "benefited_axis": "Systemic Redox / Glutathione",
                    "risk_reduction_points": 20.0,
                })
            elif (is_gsh and est_val < safe_lower) or (not is_gsh and est_val > safe_upper):
                status = "OXIDATIVE_STRAIN"
                status_label = f"Elevated Oxidative Stress ({est_val} {unit})"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Oxidative Stress",
                    "severity": "HIGH_RISK",
                    "title": "Uncompensated Oxidative Stress & Lipid Peroxidation",
                    "description": f"Pro-oxidant compound metabolism overwhelms intracellular redox capacity, shifting {primary_redox.get('label', bio_id)} to {est_val} {unit}.",
                    "clinical_recommendation": "Introduce potent antioxidant cytoprotection (e.g. Astaxanthin, NAC, CoQ10) to mitigate lipid peroxidation and restore GSH reserves.",
                })
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Optimal Redox Balance ({est_val} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Systemic Oxidative Stress & Redox Axis",
                "biomarker_id": bio_id,
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": in_safe,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "panel": "Redox Panel",
            })

        # 7. SYSTEMIC INFLAMMATION & HS-CRP AXIS
        crp_shift = shifts_by_id.get("bio_crp")
        if crp_shift:
            processed_bio_ids.add("bio_crp")
            baseline = _to_float(crp_shift.get("baseline_value"), labs.get("crp_mg_l") or 0.5)
            est_val = _to_float(crp_shift.get("estimated_value"), baseline)
            delta = _to_float(crp_shift.get("estimated_delta"), 0.0)
            unit = str(crp_shift.get("unit", "mg/L"))
            safe_lower = _to_float(crp_shift.get("safe_lower"), 0.0)
            safe_upper = _to_float(crp_shift.get("safe_upper"), 1.0)

            contributions = crp_shift.get("compound_contributions") or crp_shift.get("contributions") or []
            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            pro_inf = [c for c in contributions if c.get("contribution_mag", 0) > 0.03]
            anti_inf = [c for c in contributions if c.get("contribution_mag", 0) < -0.03]
            in_safe = safe_lower <= est_val <= safe_upper

            if pro_inf and anti_inf and in_safe:
                status = "BALANCED_TARGET"
                status_label = f"Controlled hs-CRP ({est_val} {unit})"
                status_color = "#10b981"
                participating_labels = [c.get("compound_label") for c in contributions if abs(c.get("contribution_mag", 0)) > 0.02]
                active_mitigations.append({
                    "title": "Systemic Inflammation & Endothelial Protection",
                    "description": (
                        f"Anti-inflammatory co-administration attenuates pro-inflammatory signaling and NF-kB transactivation, "
                        f"maintaining low cardiovascular risk hs-CRP ({est_val} {unit}, target < 1.0 {unit})."
                    ),
                    "participating_compounds": participating_labels,
                    "benefited_axis": "hs-CRP / Inflammation",
                    "risk_reduction_points": 15.0,
                })
            elif est_val > 3.0:
                status = "HIGH_INFLAMMATORY_RISK"
                status_label = f"Elevated hs-CRP ({est_val} {unit})"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Inflammation (hs-CRP)",
                    "severity": "HIGH_RISK",
                    "title": "Marked Inflammatory Activation (hs-CRP > 3.0 mg/L)",
                    "description": f"Stack triggers acute phase hepatic inflammation, driving hs-CRP to {est_val} {unit}, conferring high cardiovascular risk.",
                    "clinical_recommendation": "Incorporate anti-inflammatory agents (Curcumin, Omega-3, Astaxanthin) and address underlying systemic stressors.",
                })
            elif est_val > safe_upper:
                status = "MODERATE_INFLAMMATION"
                status_label = f"Sub-Optimal hs-CRP ({est_val} {unit})"
                status_color = "#f59e0b"
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Low Inflammatory Tone ({est_val} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Systemic Inflammation & hs-CRP Axis",
                "biomarker_id": "bio_crp",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": in_safe,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "panel": "Inflammatory Panel",
            })

        # 8. LIPID & ATHEROGENIC RISK AXIS
        hdl_shift = shifts_by_id.get("bio_hdl_c") or shifts_by_id.get("bio_hdl")
        ldl_shift = shifts_by_id.get("bio_ldl_c") or shifts_by_id.get("bio_ldl")
        apob_shift = shifts_by_id.get("bio_apob")

        if hdl_shift or ldl_shift or apob_shift or "hdl_c_mg_dl" in labs or "ldl_mg_dl" in labs or "apob_mg_dl" in labs:
            primary_lipid = hdl_shift or ldl_shift or apob_shift
            bio_id = primary_lipid.get("biomarker_id") if primary_lipid else "bio_hdl_c"
            processed_bio_ids.add(bio_id)
            if bio_id == "bio_hdl_c":
                processed_bio_ids.add("bio_hdl")
            elif bio_id == "bio_ldl_c":
                processed_bio_ids.add("bio_ldl")

            cal_base_hdl, cal_low_hdl, cal_up_hdl, hdl_adj = get_demographic_calibrated_reference_range(
                "bio_hdl_c", profile_data, 50.0, 40.0, 125.0
            )
            cal_base_ldl, cal_low_ldl, cal_up_ldl, ldl_adj = get_demographic_calibrated_reference_range(
                "bio_ldl_c", profile_data, 95.0, 50.0, 100.0
            )
            lipid_adjustments = list(dict.fromkeys(hdl_adj + ldl_adj))

            hdl_base = labs.get("hdl_c_mg_dl") if labs.get("hdl_c_mg_dl") is not None else (labs.get("hdl") or cal_base_hdl)
            hdl_val = _to_float(hdl_base, hdl_shift.get("estimated_value") if hdl_shift else cal_base_hdl)
            ldl_base = labs.get("ldl_mg_dl") if labs.get("ldl_mg_dl") is not None else (labs.get("ldl_c_mg_dl") or labs.get("ldl") or cal_base_ldl)
            ldl_val = _to_float(ldl_base, ldl_shift.get("estimated_value") if ldl_shift else cal_base_ldl)

            has_lipid_protective = any(
                any(w in str(comp.get("drug_class", "")).lower() or w in str(comp.get("name", "")).lower() or w in str(comp.get("key", "")).lower()
                    for w in ["statin", "pitavastatin", "atorvastatin", "rosuvastatin", "ezetimibe", "pcsk9", "bempedoic", "niacin", "bergamot", "lipid-lowering", "hmg-coa"])
                for comp in compounds
            )
            has_androgen_load = any(
                "androgen" in str(comp.get("drug_class", "")).lower() or "testosterone" in str(comp.get("key", "")).lower() or "anabolic" in str(comp.get("drug_class", "")).lower()
                for comp in compounds
            )

            participating_lipid_comps = [
                c.get("name") or c.get("key") for c in compounds
                if any(w in str(c.get("drug_class", "")).lower() or w in str(c.get("key", "")).lower() or w in str(c.get("name", "")).lower()
                       for w in ["statin", "pitavastatin", "atorvastatin", "rosuvastatin", "ezetimibe", "pcsk9", "lipid", "androgen", "testosterone"])
            ]

            # Require true multi-agent lipid coverage: must have a lipid-modulating compound co-administered to claim a counterbalance!
            if has_lipid_protective and (has_androgen_load or hdl_val >= cal_low_hdl):
                status = "BALANCED_NORMLIPIDEMIC"
                status_label = f"Normolipidemic Equilibrium (HDL {hdl_val}, LDL {ldl_val} mg/dL)"
                status_color = "#10b981"
                active_mitigations.append({
                    "title": "Lipid Protection & Endothelial Counterbalance",
                    "description": (
                        f"Co-administration of lipid-modulating therapy (e.g. Statin/Ezetimibe) "
                        f"effectively counterbalances androgenic lipolytic shift, maintaining cardioprotective HDL-C ({hdl_val} mg/dL) "
                        f"and controlling atherogenic LDL-C ({ldl_val} mg/dL)."
                    ),
                    "participating_compounds": participating_lipid_comps,
                    "benefited_axis": "Lipid Profile / Cardioprotective",
                    "risk_reduction_points": 20.0,
                })
            elif hdl_val < cal_low_hdl or ldl_val >= 135.0:
                if has_lipid_protective:
                    status = "PARTIAL_LIPID_ATTENUATION"
                    status_label = f"Sub-Target Lipid Shift (HDL {hdl_val}, LDL {ldl_val} mg/dL)"
                    status_color = "#f59e0b"
                    uncompensated_risks.append({
                        "axis": "Lipid Panel (HDL / LDL)",
                        "severity": "MODERATE_RISK",
                        "title": "Sub-Optimal Lipid Attenuation",
                        "description": f"Despite lipid-modulating therapy, HDL-C remains suppressed ({hdl_val} mg/dL) or LDL-C remains elevated ({ldl_val} mg/dL).",
                        "clinical_recommendation": "Titrate statin therapy (e.g., adjust Pitavastatin or add Ezetimibe) and monitor lipid panel in 6 weeks.",
                    })
                else:
                    status = "ATHEROGENIC_LIPID_SHIFT"
                    status_label = f"Atherogenic Lipid Shift (HDL {hdl_val}, LDL {ldl_val} mg/dL)"
                    status_color = "#ef4444"
                    uncompensated_risks.append({
                        "axis": "Lipid Panel (HDL / LDL)",
                        "severity": "HIGH_RISK" if (hdl_val < 28.0 or ldl_val >= 160.0) else "MODERATE_RISK",
                        "title": "Uncompensated Atherogenic Lipid Shift",
                        "description": f"Androgen load depresses cardioprotective HDL-C to {hdl_val} mg/dL and/or elevates LDL-C to {ldl_val} mg/dL without co-administered lipid-protective coverage.",
                        "clinical_recommendation": "Incorporate endothelial and lipid protection (e.g., Pitavastatin 2 mg daily or Ezetimibe) and re-check lipid panel in 6-8 weeks.",
                    })
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Normolipidemic Baseline (HDL {hdl_val}, LDL {ldl_val} mg/dL)"
                status_color = "#34d399"

            axes.append({
                "name": "Lipid & Atherogenic Risk Axis",
                "biomarker_id": bio_id,
                "baseline": hdl_val,
                "estimated_value": hdl_val,
                "unit": "mg/dL",
                "safe_range": f"HDL > {cal_low_hdl:g} mg/dL, LDL < 100 mg/dL",
                "safe_lower": cal_low_hdl,
                "safe_upper": 125.0,
                "in_safe_range": hdl_val >= cal_low_hdl and ldl_val <= 125.0,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"HDL {hdl_val} / LDL {ldl_val} mg/dL",
                "compounds_breakdown": [],
                "biometric_modifiers_applied": lipid_adjustments,
                "panel": "Lipid Panel",
            })

        # 9. SERUM TOTAL TESTOSTERONE / ENDOCRINE AXIS
        testo_shift = shifts_by_id.get("bio_testosterone")
        if testo_shift or (labs.get("bio_testosterone") is not None) or (labs.get("testosterone_ng_dl") is not None):
            processed_bio_ids.add("bio_testosterone")
            cal_base_t, cal_low_t, cal_up_t, t_adjustments = get_demographic_calibrated_reference_range(
                "bio_testosterone", profile_data, 550.0, 300.0, 1000.0
            )
            raw_testo = testo_shift.get("baseline_value") if testo_shift else None
            if raw_testo is None:
                raw_testo = labs.get("testosterone_ng_dl") or labs.get("bio_testosterone") or cal_base_t
            baseline = _to_float(raw_testo, cal_base_t)
            est_val = _to_float(testo_shift.get("estimated_value"), baseline) if testo_shift else baseline
            unit = "ng/dL"
            safe_lower = cal_low_t
            safe_upper = cal_up_t

            raw_sex = profile_data.get("sex") if profile_data else None
            is_female_pt = str(raw_sex).lower().strip() in ["female", "f", "woman"] if raw_sex else False

            if est_val > safe_upper:
                if is_female_pt:
                    status = "ELEVATED_ANDROGEN"
                    status_label = f"Elevated Serum Testosterone ({est_val} {unit})"
                    status_color = "#f59e0b"
                else:
                    status = "OPTIMIZED_ANABOLIC"
                    status_label = f"Optimized Anabolic Pool ({est_val} {unit})"
                    status_color = "#38bdf8"
            elif est_val < safe_lower:
                status = "SUPPRESSED_TESTOSTERONE"
                status_label = f"Suppressed Serum Testosterone ({est_val} {unit})"
                status_color = "#ef4444"
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Physiological Serum Testosterone ({est_val} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Serum Total Testosterone Axis",
                "biomarker_id": "bio_testosterone",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{est_val} {unit}",
                "compounds_breakdown": [],
                "biometric_modifiers_applied": t_adjustments,
                "panel": "Endocrine Panel",
            })

        # 10. FREE TESTOSTERONE (VERMEULEN SOLVER) AXIS
        free_t_shift = shifts_by_id.get("bio_free_testosterone")
        has_shbg_or_t = (
            labs.get("shbg_nmol_l") is not None
            or labs.get("shbg") is not None
            or labs.get("testosterone_ng_dl") is not None
            or labs.get("bio_testosterone") is not None
            or testo_shift is not None
            or free_t_shift is not None
        )
        if free_t_shift or has_shbg_or_t:
            processed_bio_ids.add("bio_free_testosterone")
            from app.services.dosing_service import calculate_free_testosterone
            cal_base_ft, cal_low_ft, cal_up_ft, ft_adjustments = get_demographic_calibrated_reference_range(
                "bio_free_testosterone", profile_data, 120.0, 50.0, 210.0
            )
            raw_total_t = labs.get("testosterone_ng_dl") or labs.get("bio_testosterone") or (testo_shift.get("estimated_value") if testo_shift else None) or 550.0
            raw_shbg = labs.get("shbg_nmol_l") or labs.get("shbg") or 32.0
            raw_alb = labs.get("serum_albumin_g_dl") or labs.get("serum_albumin") or 4.3
            try:
                tot_t_val = float(raw_total_t)
                shbg_val = float(raw_shbg)
                alb_val = float(raw_alb)
                sol = calculate_free_testosterone(tot_t_val, shbg_val, alb_val)
                calculated_ft = float(sol.get("free_testosterone_pg_ml", cal_base_ft))
            except Exception:
                calculated_ft = cal_base_ft

            baseline = _to_float(free_t_shift.get("baseline_value"), calculated_ft) if free_t_shift else calculated_ft
            est_val = _to_float(free_t_shift.get("estimated_value"), baseline) if free_t_shift else baseline
            unit = "pg/mL"
            safe_lower = cal_low_ft
            safe_upper = cal_up_ft

            raw_sex = profile_data.get("sex") if profile_data else None
            is_female_pt = str(raw_sex).lower().strip() in ["female", "f", "woman"] if raw_sex else False

            if est_val > safe_upper:
                status = "ELEVATED_FREE_ANDROGEN" if is_female_pt else "HIGH_BIOAVAILABLE_ANDROGEN"
                status_label = f"Elevated Free Testosterone ({est_val} {unit})"
                status_color = "#f59e0b" if is_female_pt else "#38bdf8"
            elif est_val < safe_lower:
                status = "LOW_FREE_TESTOSTERONE"
                status_label = f"Suboptimal Free Testosterone ({est_val} {unit})"
                status_color = "#ef4444"
                if raw_shbg and float(raw_shbg) > 55.0:
                    uncompensated_risks.append({
                        "axis": "Free Testosterone",
                        "severity": "MODERATE_RISK",
                        "title": f"SHBG Sequestration of Free Androgen ({est_val} {unit})",
                        "description": f"Elevated SHBG ({raw_shbg} nmol/L) binds circulating testosterone with high affinity (K_d = 1.0 nM), lowering biologically active free testosterone ({est_val} {unit}, target {safe_lower}-{safe_upper} {unit}).",
                        "clinical_recommendation": "Evaluate Boron (6-10 mg daily), Tongkat Ali, or optimizing insulin/caloric intake to modulate hepatic SHBG expression.",
                    })
            else:
                status = "OPTIMAL_BIOAVAILABLE"
                status_label = f"Optimal Free Testosterone ({est_val} {unit})"
                status_color = "#10b981"

            # Check Free T / Estradiol balance if E2 is available
            e2_val = None
            if e2_shift:
                e2_val = _to_float(e2_shift.get("estimated_value"))
            elif labs.get("estradiol_pg_ml") is not None:
                e2_val = _to_float(labs.get("estradiol_pg_ml"))
            if e2_val is not None and not is_female_pt:
                if e2_val < 12.0 and est_val > 100.0:
                    uncompensated_risks.append({
                        "axis": "Androgen / Estrogen Ratio",
                        "severity": "HIGH_RISK",
                        "title": "Severe Hypoestrogenemia with High Free Androgen",
                        "description": f"Free Testosterone is elevated or robust ({est_val} {unit}) while Estradiol is excessively suppressed ({e2_val} pg/mL). This creates neurovascular, articular, and endothelial vulnerability.",
                        "clinical_recommendation": "Reduce aromatase inhibitor dosage immediately. Target serum E2 between 20-35 pg/mL.",
                    })

            axes.append({
                "name": "Free Testosterone (Vermeulen Solver) Axis",
                "biomarker_id": "bio_free_testosterone",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{est_val} {unit}",
                "compounds_breakdown": [],
                "biometric_modifiers_applied": ft_adjustments,
                "panel": "Endocrine Panel",
            })

        # 11. BASAL METABOLIC RATE (BMR) & ENERGY EXPENDITURE AXIS
        bmr_shift = shifts_by_id.get("bio_metabolic_rate") or shifts_by_id.get("bio_bmr")
        has_bmr_profile = (
            profile_data.get("metabolic_rate_kcal") is not None
            or labs.get("metabolic_rate_kcal") is not None
            or profile_data.get("weight_kg") is not None
            or bmr_shift is not None
        )
        if bmr_shift or has_bmr_profile:
            processed_bio_ids.add("bio_metabolic_rate")
            processed_bio_ids.add("bio_bmr")
            from app.services.dosing_service import calculate_basal_metabolic_rate
            bmr_sol = calculate_basal_metabolic_rate(profile_data)
            cal_base_bmr = float(bmr_sol.get("bmr_kcal_day", 1750.0))
            cal_low_bmr = float(bmr_sol.get("safe_range_lower", round(cal_base_bmr * 0.82, 0)))
            cal_up_bmr = float(bmr_sol.get("safe_range_upper", round(cal_base_bmr * 1.18, 0)))

            baseline = _to_float(bmr_shift.get("baseline_value"), cal_base_bmr) if bmr_shift else cal_base_bmr
            est_val = _to_float(bmr_shift.get("estimated_value"), baseline) if bmr_shift else baseline
            unit = "kcal/day"
            safe_lower = cal_low_bmr
            safe_upper = cal_up_bmr

            delta_pct = ((est_val - baseline) / baseline * 100.0) if baseline > 0 else 0.0

            if delta_pct > 25.0:
                status = "HYPERMETABOLIC_SURGE"
                status_label = f"Hypermetabolic Surge ({est_val} {unit}, +{round(delta_pct, 1)}%)"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Metabolic Energy Expenditure",
                    "severity": "HIGH_RISK",
                    "title": f"Hypermetabolic Thyrotoxic / Adrenergic Strain (+{round(delta_pct, 1)}% BMR)",
                    "description": f"Dynamic cascade projects a marked acceleration in energy expenditure to {est_val} kcal/day (+{round(delta_pct, 1)}% over baseline). Excess metabolic turnover induces resting tachycardia, hyperthermia, and protein catabolism.",
                    "clinical_recommendation": "Calibrate caloric intake, monitor resting heart rate and core temperature, and avoid concurrent high-potency beta-2 agonists and exogenous thyroid hormones.",
                })
            elif delta_pct < -20.0:
                status = "HYPOMETABOLIC_SUPPRESSION"
                status_label = f"Hypometabolic Crash ({est_val} {unit}, {round(delta_pct, 1)}%)"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Metabolic Energy Expenditure",
                    "severity": "MODERATE_RISK",
                    "title": f"Hypometabolic Suppression ({round(delta_pct, 1)}% BMR)",
                    "description": f"Metabolic expenditure projected to drop by {abs(round(delta_pct, 1))}% ({est_val} kcal/day), indicating significant metabolic slowdown or down-regulated sympathetic tone.",
                    "clinical_recommendation": "Evaluate thyroid panel (TSH, Free T3) and optimize mitochondrial cofactors.",
                })
            elif delta_pct > 5.0:
                status = "THERMOGENIC_ELEVATION"
                status_label = f"Thermogenic Activation ({est_val} {unit}, +{round(delta_pct, 1)}%)"
                status_color = "#38bdf8"
            else:
                status = "EUMETABOLIC_HOMEOSTASIS"
                status_label = f"Homeostatic BMR ({est_val} {unit})"
                status_color = "#10b981"

            axes.append({
                "name": "Basal Metabolic Rate (BMR) Axis",
                "biomarker_id": "bio_metabolic_rate",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{round(est_val - baseline, 1):+g} {unit}",
                "compounds_breakdown": [],
                "biometric_modifiers_applied": [f"Formula: {bmr_sol.get('formula_used', 'Mifflin-St Jeor')} (TDEE: {bmr_sol.get('tdee_moderately_active')} kcal/day)"],
                "panel": "Metabolic Panel",
            })

        # 12. AUTONOMIC VAGAL TONE & HEART RATE VARIABILITY (HRV) AXIS
        hrv_shift = shifts_by_id.get("bio_hrv")
        has_hrv_profile = (
            profile_data.get("hrv_rmssd_ms") is not None
            or labs.get("hrv_rmssd_ms") is not None
            or labs.get("hrv") is not None
            or hrv_shift is not None
        )
        if hrv_shift or has_hrv_profile:
            processed_bio_ids.add("bio_hrv")
            cal_base_hrv, cal_low_hrv, cal_up_hrv, hrv_adjustments = get_demographic_calibrated_reference_range(
                "bio_hrv", profile_data, 45.0, 25.0, 85.0
            )
            raw_hrv = labs.get("hrv_rmssd_ms") or labs.get("hrv") or profile_data.get("hrv_rmssd_ms") or cal_base_hrv
            baseline = _to_float(hrv_shift.get("baseline_value") if hrv_shift else None, _to_float(raw_hrv, cal_base_hrv))
            est_val = _to_float(hrv_shift.get("estimated_value"), baseline) if hrv_shift else baseline
            unit = "ms"
            safe_lower = cal_low_hrv
            safe_upper = cal_up_hrv

            contributions = (hrv_shift.get("compound_contributions") or hrv_shift.get("contributions") or []) if hrv_shift else []
            pos_contribs = [c for c in contributions if c.get("contribution_mag", 0) > 0.03]
            neg_contribs = [c for c in contributions if c.get("contribution_mag", 0) < -0.03]

            if est_val < 25.0:
                status = "VAGAL_WITHDRAWAL"
                status_label = f"Vagal Tone Withdrawal ({est_val} {unit})"
                status_color = "#ef4444"
                uncompensated_risks.append({
                    "axis": "Autonomic Vagal Tone",
                    "severity": "HIGH_RISK",
                    "title": f"Vagal Withdrawal & Sympathetic Dominance (HRV {est_val} ms)",
                    "description": f"HRV RMSSD depressed to {est_val} ms. Parasympathetic vagal suppression limits systemic recovery, accelerates central allostatic load, and predisposes to cardiovascular strain.",
                    "clinical_recommendation": "Integrate parasympathomimetic or GABAergic counterbalances (L-Theanine 200 mg, Ashwagandha KSM-66, Magnesium Glycinate 300 mg) and time stimulants strictly in morning hours.",
                })
            elif pos_contribs and neg_contribs and safe_lower <= est_val <= safe_upper:
                status = "BALANCED_AUTONOMIC"
                status_label = f"Balanced Autonomic Tone ({est_val} {unit})"
                status_color = "#10b981"
                mitigation = {
                    "title": "Autonomic Vagal Tone Counterbalance",
                    "description": f"Parasympathetic adaptogenic / calming agents effectively buffer stimulant-induced vagal withdrawal, maintaining HRV within physiological targets ({est_val} {unit}).",
                    "participating_compounds": [c.get("compound_label") for c in contributions if abs(c.get("contribution_mag", 0)) > 0.03],
                    "benefited_axis": "Autonomic Vagal Tone (HRV)",
                    "risk_reduction_points": 12.0,
                }
                active_mitigations.append(mitigation)
            elif est_val >= safe_lower:
                status = "ROBUST_VAGAL_TONE"
                status_label = f"Robust Parasympathetic Tone ({est_val} {unit})"
                status_color = "#10b981"
            else:
                status = "MODERATE_HRV_DEPRESSION"
                status_label = f"Depressed HRV ({est_val} {unit})"
                status_color = "#f59e0b"

            axes.append({
                "name": "Autonomic Vagal Tone & HRV Axis",
                "biomarker_id": "bio_hrv",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{round(est_val - baseline, 1):+g} {unit}",
                "compounds_breakdown": [],
                "biometric_modifiers_applied": hrv_adjustments,
                "panel": "Wearables & Autonomic Panel",
            })

        # 13. NEUROTROPHIC & SYNAPTIC PLASTICITY (BDNF) AXIS
        bdnf_shift = shifts_by_id.get("bio_bdnf")
        has_bdnf_profile = (
            labs.get("bdnf_ng_ml") is not None
            or labs.get("bdnf") is not None
            or bdnf_shift is not None
        )
        if bdnf_shift or has_bdnf_profile:
            processed_bio_ids.add("bio_bdnf")
            cal_base_bdnf, cal_low_bdnf, cal_up_bdnf, bdnf_adjustments = get_demographic_calibrated_reference_range(
                "bio_bdnf", profile_data, 25.0, 15.0, 45.0
            )
            raw_bdnf = labs.get("bdnf_ng_ml") or labs.get("bdnf") or cal_base_bdnf
            baseline = _to_float(bdnf_shift.get("baseline_value") if bdnf_shift else None, _to_float(raw_bdnf, cal_base_bdnf))
            est_val = _to_float(bdnf_shift.get("estimated_value"), baseline) if bdnf_shift else baseline
            unit = "ng/mL"
            safe_lower = cal_low_bdnf
            safe_upper = cal_up_bdnf

            contributions = (bdnf_shift.get("compound_contributions") or bdnf_shift.get("contributions") or []) if bdnf_shift else []
            pos_contribs = [c for c in contributions if c.get("contribution_mag", 0) > 0.03]

            if len(pos_contribs) >= 2:
                status = "NEUROTROPHIC_SYNERGY"
                status_label = f"Neurotrophic BDNF Synergy ({est_val} {unit})"
                status_color = "#38bdf8"
                active_mitigations.append({
                    "title": "Neurotrophic BDNF Synergy & Synaptic Plasticity",
                    "description": f"Co-activation of TrkB / neurotrophin cascades by {', '.join([c.get('compound_label') for c in pos_contribs])} cooperatively elevates BDNF to {est_val} {unit} (+{round(est_val - baseline, 1)} {unit}), enhancing hippocampal LTP and synaptic resilience.",
                    "participating_compounds": [c.get("compound_label") for c in pos_contribs],
                    "benefited_axis": "Neurotrophic & Synaptic Plasticity (BDNF)",
                    "risk_reduction_points": 10.0,
                })
            elif est_val > baseline:
                status = "ENHANCED_NEUROTROPHIN"
                status_label = f"Enhanced BDNF Expression ({est_val} {unit})"
                status_color = "#10b981"
            elif est_val < safe_lower:
                status = "DEPLETED_NEUROTROPHIN"
                status_label = f"Suppressed BDNF ({est_val} {unit})"
                status_color = "#ef4444"
            else:
                status = "PHYSIOLOGICAL_BASELINE"
                status_label = f"Baseline BDNF ({est_val} {unit})"
                status_color = "#10b981"

            axes.append({
                "name": "Neurotrophic & Synaptic Plasticity (BDNF) Axis",
                "biomarker_id": "bio_bdnf",
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= est_val <= safe_upper,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{round(est_val - baseline, 1):+g} {unit}",
                "compounds_breakdown": [],
                "biometric_modifiers_applied": bdnf_adjustments,
                "panel": "Neurotrophic Panel",
            })

        # 14. HEPATIC TRANSAMINASES & HEPATOBILIARY AXIS (ALT / AST / DILI)
        alt_shift = shifts_by_id.get("bio_alt")
        ast_shift = shifts_by_id.get("bio_ast")
        bili_shift = shifts_by_id.get("bio_total_bilirubin")
        alp_shift = shifts_by_id.get("bio_alp")

        has_hepatic_profile = (
            alt_shift is not None
            or ast_shift is not None
            or labs.get("alt_u_l") is not None
            or labs.get("alt") is not None
            or any(is_17a_alkylated(c) or "hepatic" in str(c.get("drug_class", "")).lower() for c in compounds)
        )

        if has_hepatic_profile:
            processed_bio_ids.add("bio_alt")

            is_female_pt = str(profile_data.get("sex", "")).lower().strip() in ["female", "f", "woman"] if profile_data else False
            def_base_alt = 19.0 if is_female_pt else 26.0
            def_up_alt = 25.0 if is_female_pt else 33.0
            def_base_ast = 19.0 if is_female_pt else 24.0
            def_up_ast = 30.0 if is_female_pt else 35.0

            cal_base_alt, cal_low_alt, cal_up_alt, alt_adjustments = get_demographic_calibrated_reference_range(
                "bio_alt", profile_data, def_base_alt, 8.0 if is_female_pt else 10.0, def_up_alt
            )
            cal_base_ast, cal_low_ast, cal_up_ast, ast_adjustments = get_demographic_calibrated_reference_range(
                "bio_ast", profile_data, def_base_ast, 8.0 if is_female_pt else 10.0, def_up_ast
            )

            raw_alt_base = labs.get("alt_u_l") or labs.get("alt") or (alt_shift.get("baseline_value") if alt_shift else None) or cal_base_alt
            baseline_alt = _to_float(raw_alt_base, cal_base_alt)
            est_alt = _to_float(alt_shift.get("estimated_value") if alt_shift else None, baseline_alt)
            delta_alt = _to_float(alt_shift.get("estimated_delta") if alt_shift else None, round(est_alt - baseline_alt, 1))
            unit = str(alt_shift.get("unit") if alt_shift else "U/L")

            raw_ast_base = labs.get("ast_u_l") or labs.get("ast") or (ast_shift.get("baseline_value") if ast_shift else None) or cal_base_ast
            baseline_ast = _to_float(raw_ast_base, cal_base_ast)
            est_ast = _to_float(ast_shift.get("estimated_value") if ast_shift else None, baseline_ast)

            raw_bili = labs.get("total_bilirubin_mg_dl") or labs.get("total_bilirubin") or (bili_shift.get("estimated_value") if bili_shift else None) or 0.8
            est_bili = _to_float(raw_bili, 0.8)

            raw_alp = labs.get("alp_u_l") or labs.get("alp") or (alp_shift.get("estimated_value") if alp_shift else None) or 65.0
            est_alp = _to_float(raw_alp, 65.0)

            uln_alt = 25.0 if is_female_pt else 33.0
            uln_ast = 30.0 if is_female_pt else 35.0
            uln_bili = 1.2
            uln_alp = 120.0
            action_threshold_alt = 35.0 if is_female_pt else 45.0

            # 1. CIOMS R-ratio (Pattern of Liver Injury)
            r_ratio = (max(1.0, est_alt) / uln_alt) / (max(1.0, est_alp) / uln_alp)
            if r_ratio >= 5.0:
                pattern = "Hepatocellular (Cytolytic ALT Leakage Dominant)"
            elif r_ratio > 2.0:
                pattern = "Mixed (Hepatocellular Injury with Canalicular Cholestasis)"
            else:
                pattern = "Cholestatic (Biliary Canalicular Excretory Dominant)"

            # 2. De Ritis Ratio (AST / ALT) - Pharmacology / Toxicology Framework
            de_ritis = est_ast / max(1.0, est_alt)
            if de_ritis < 1.0:
                de_ritis_type = "Toxic Xenobiotic / Metabolic Hepatocellular Profile (ALT > AST)"
            elif de_ritis >= 2.0:
                de_ritis_type = "Marked Mitochondrial / Alcoholic / Ischemic Necrosis Strain (AST >> ALT)"
            else:
                de_ritis_type = "Balanced Transaminase Profile (AST ≈ ALT)"

            # 3. Hy's Law Assessment (FDA DILI Gold Standard)
            hys_law_triggered = (est_alt >= (3.0 * uln_alt)) and (est_bili >= (2.0 * uln_bili)) and (est_alp < (2.0 * uln_alp))

            contributions = (alt_shift.get("compound_contributions") or alt_shift.get("contributions") or []) if alt_shift else []
            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            # Identify genuine hepatotoxic xenobiotics and hepatoprotective cofactors
            hepatotoxic_comps = [
                c for c in compounds
                if is_17a_alkylated(c)
                or any(w in str(c.get("name", "")).lower() or w in str(c.get("key", "")).lower() for w in ["stanozolol", "oxandrolone", "methandrostenolone", "dianabol", "anadrol", "oxymetholone", "halotestin", "fluoxymesterone", "superdrol", "epistane", "acetaminophen", "paracetamol"])
                or any("hepatotox" in str(w).lower() for w in (c.get("warnings") or []))
                or any(cs.get("delta", 0) > 5.0 for cs in comp_shares if cs.get("compound_id") == c.get("key"))
            ]

            hepatoprotective_comps = [
                c for c in compounds
                if any(w in str(c.get("name", "")).lower() or w in str(c.get("key", "")).lower() for w in ["tudca", "tauroursodeoxycholic", "udca", "ursodiol", "nac", "acetylcysteine", "silymarin", "milk thistle", "glutathione", "phosphatidylcholine"])
                or any(cs.get("delta", 0) < -2.0 for cs in comp_shares if cs.get("compound_id") == c.get("key"))
            ]

            has_hepatotoxin = bool(hepatotoxic_comps)
            has_hepatoprotectant = bool(hepatoprotective_comps)

            if hys_law_triggered:
                status = "HYS_LAW_CRITICAL_DILI"
                status_label = f"CRITICAL: Hy's Law DILI Alert (ALT {est_alt} {unit}, Bili {est_bili} mg/dL)"
                status_color = "#dc2626"
                uncompensated_risks.append({
                    "axis": "Hepatic Transaminases (Hy's Law DILI)",
                    "severity": "CRITICAL_RISK",
                    "title": f"Hy's Law Severe Hepatotoxicity (ALT {est_alt} U/L, Bilirubin {est_bili} mg/dL)",
                    "description": (
                        f"Stack triggers FDA Hy's Law criteria: ALT ≥ 3x ULN ({est_alt} U/L, ULN {uln_alt} U/L) combined with "
                        f"Total Bilirubin ≥ 2x ULN ({est_bili} mg/dL, ULN {uln_bili} mg/dL) without primary biliary obstruction. "
                        f"Clinical literature associates this profile with ~10% risk of acute liver failure."
                    ),
                    "clinical_recommendation": "Immediately discontinue hepatotoxic agents. Re-check complete liver panel (ALT, AST, Bilirubin, INR, Albumin) and institute urgent clinical supervision.",
                })
            elif has_hepatotoxin and has_hepatoprotectant and est_alt <= action_threshold_alt:
                status = "BALANCED_HEPATIC"
                status_label = f"Protected Hepatobiliary Equilibrium (ALT {est_alt} {unit})"
                status_color = "#10b981"
                mitigation = {
                    "title": "Hepatobiliary Cytoprotection & Transaminase Counterbalance",
                    "description": (
                        f"Co-administration of hydrophilic bile acid (TUDCA) and/or glutathione precursor (NAC) "
                        f"effectively counterbalances 17α-alkylated steroid / xenobiotic hepatotoxicity, stabilizing canalicular transport "
                        f"and keeping ALT within physiological targets ({est_alt} {unit}, target {cal_low_alt:g}–{cal_up_alt:g} {unit})."
                    ),
                    "participating_compounds": [c.get("name") or c.get("key") for c in (hepatotoxic_comps + hepatoprotective_comps)],
                    "benefited_axis": "Hepatic Transaminases (ALT / AST)",
                    "risk_reduction_points": 25.0,
                }
                active_mitigations.append(mitigation)
            elif has_hepatotoxin and has_hepatoprotectant and est_alt > action_threshold_alt:
                status = "PARTIAL_HEPATIC_ATTENUATION"
                status_label = f"Sub-Target Transaminase Protection (ALT {est_alt} {unit})"
                status_color = "#f59e0b"
                uncompensated_risks.append({
                    "axis": "Hepatic Transaminases (ALT / AST)",
                    "severity": "MODERATE_RISK",
                    "title": f"Sub-Target Hepatic Protection (ALT {est_alt} U/L)",
                    "description": (
                        f"Despite co-administered hepatoprotective support, projected ALT remains elevated at {est_alt} {unit}, "
                        f"exceeding the clinical action threshold ({action_threshold_alt} {unit})."
                    ),
                    "clinical_recommendation": "Titrate TUDCA upward (500–1000 mg/day), reduce oral hepatotoxic compound dosage or cycle length, and monitor weekly liver panels.",
                })
            elif has_hepatotoxin and not has_hepatoprotectant:
                status = "UNCOMPENSATED_HEPATOTOXIC_STRAIN"
                status_label = f"Uncompensated Hepatocellular Strain (ALT {est_alt} {unit})"
                status_color = "#ef4444"
                is_severe_dili = est_alt >= (2.0 * uln_alt)
                uncompensated_risks.append({
                    "axis": "Hepatic Transaminases (ALT / AST)",
                    "severity": "HIGH_RISK" if is_severe_dili else "MODERATE_RISK",
                    "title": f"Uncompensated Hepatotoxicity ({', '.join([c.get('name', 'Hepatotoxin') for c in hepatotoxic_comps])})",
                    "description": (
                        f"Administration of 17α-alkylated oral androgen or hepatotoxic xenobiotic drives alanine aminotransferase "
                        f"to {est_alt} {unit} (baseline {baseline_alt} {unit}) without concurrent cytoprotective coverage. "
                        f"DILI pattern: {pattern}."
                    ),
                    "clinical_recommendation": "Incorporate TUDCA (250–500 mg daily) and NAC (600–1200 mg daily) to preserve canalicular transport and replenish hepatocyte glutathione reserves.",
                })
            elif est_alt > action_threshold_alt:
                status = "ELEVATED_TRANSAMINASES"
                status_label = f"Elevated Transaminases (ALT {est_alt} {unit})"
                status_color = "#f59e0b"
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Physiological ALT ({est_alt} {unit})"
                status_color = "#34d399"

            axes.append({
                "name": "Hepatic Transaminases & Hepatobiliary Axis",
                "biomarker_id": "bio_alt",
                "target_tissue": "Hepatic Parenchyma & Biliary Canaliculi (Liver)",
                "baseline": baseline_alt,
                "estimated_value": est_alt,
                "unit": unit,
                "safe_range": f"{cal_low_alt:g} - {cal_up_alt:g} {unit}",
                "safe_lower": cal_low_alt,
                "safe_upper": cal_up_alt,
                "action_threshold": action_threshold_alt,
                "in_safe_range": cal_low_alt <= est_alt <= action_threshold_alt,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta_alt > 0 else ''}{delta_alt} {unit} (AST: {est_ast} U/L)",
                "compounds_breakdown": comp_shares,
                "biometric_modifiers_applied": alt_adjustments + ([f"DILI Pattern: {pattern}"] if est_alt > cal_up_alt else []),
                "cioms_r_ratio": round(r_ratio, 2),
                "dili_pattern": pattern,
                "de_ritis_ratio": round(de_ritis, 2),
                "de_ritis_classification": de_ritis_type,
                "hys_law_triggered": hys_law_triggered,
                "panel": "Hepatic Panel",
            })

        # 8. ALL OTHER AFFECTED BIOMARKERS FROM DYNAMIC GRAPH CASCADE
        for b in cascade_results.get("biomarker_shifts", []):
            bio_id = str(b.get("biomarker_id") or "")
            if not bio_id or bio_id in processed_bio_ids:
                continue

            baseline = _to_float(b.get("baseline_value"), 0.0)
            est_val = _to_float(b.get("estimated_value"), baseline)
            delta = _to_float(b.get("estimated_delta"), 0.0)
            unit = str(b.get("unit") or "")
            safe_lower = _to_float(b.get("safe_lower"), baseline * 0.8 if baseline > 0 else -100.0)
            safe_upper = _to_float(b.get("safe_upper"), baseline * 1.2 if baseline > 0 else 100.0)
            in_safe = bool(b.get("in_safe_range", safe_lower <= est_val <= safe_upper))
            label = str(b.get("label") or b.get("name") or bio_id.replace("bio_", "").replace("_", " ").title())
            panel = str(b.get("biomarker_panel") or "General Panel")

            contributions = b.get("compound_contributions") or b.get("contributions") or []
            comp_shares = [
                {
                    "compound_id": c.get("compound_id"),
                    "compound_label": c.get("compound_label"),
                    "delta": c.get("estimated_delta", 0.0),
                    "formatted_delta": c.get("formatted_delta", f"{c.get('estimated_delta', 0.0):+g} {unit}"),
                    "direction": "UP" if c.get("contribution_mag", 0) > 0 else "DOWN",
                }
                for c in contributions
            ]

            pos_contribs = [c for c in contributions if c.get("contribution_mag", 0) > 0.03]
            neg_contribs = [c for c in contributions if c.get("contribution_mag", 0) < -0.03]

            if pos_contribs and neg_contribs and in_safe:
                status = "BALANCED_TARGET"
                status_label = f"Balanced {label} ({est_val} {unit})"
                status_color = "#10b981"
                participating_labels = [c.get("compound_label") for c in contributions if abs(c.get("contribution_mag", 0)) > 0.03]
                if len(participating_labels) >= 2:
                    active_mitigations.append({
                        "title": f"{label} Equilibrium & Counterbalance",
                        "description": (
                            f"Multi-agent interaction stabilizes {label} within physiological target bounds "
                            f"({est_val} {unit}, target {safe_lower}-{safe_upper} {unit})."
                        ),
                        "participating_compounds": participating_labels,
                        "benefited_axis": label,
                        "risk_reduction_points": 15.0,
                    })
            elif not in_safe and est_val > safe_upper:
                is_severe = est_val > (safe_upper * 1.35)
                status = "ELEVATED_RISK" if is_severe else "MODERATE_ELEVATION"
                status_label = f"Elevated {label} ({est_val} {unit})"
                status_color = "#ef4444" if is_severe else "#f59e0b"
                if is_severe and bio_id in {"bio_tmao", "bio_qtc", "bio_hematocrit", "bio_alt", "bio_ast", "bio_serum_creatinine", "bio_blood_glucose", "bio_prolactin", "bio_free_t3"}:
                    rec_text = "Incorporate microbial TMA-lyase inhibitor (e.g. Allicin 10-20 mg or Aged Garlic Extract) or switch to parenteral route (IM) to bypass gut microbiota." if bio_id == "bio_tmao" else f"Monitor {label} and adjust dosage or add counterbalancing support if necessary."
                    uncompensated_risks.append({
                        "axis": label,
                        "severity": "HIGH_RISK",
                        "title": f"Elevated {label} ({est_val} {unit})",
                        "description": f"Compound pharmacological action shifts {label} beyond the safe upper bound ({safe_upper} {unit}) to {est_val} {unit}.",
                        "clinical_recommendation": rec_text,
                    })
            elif not in_safe and est_val < safe_lower:
                is_severe = est_val < (safe_lower * 0.65)
                status = "SUPPRESSED_RISK" if is_severe else "MODERATE_SUPPRESSION"
                status_label = f"Suppressed {label} ({est_val} {unit})"
                status_color = "#ef4444" if is_severe else "#f59e0b"
                if is_severe and bio_id in {"bio_blood_glucose", "bio_egfr", "bio_platelets", "bio_hdl_c", "bio_testosterone", "bio_estradiol", "bio_luteinizing_hormone", "bio_tsh", "bio_acth"}:
                    uncompensated_risks.append({
                        "axis": label,
                        "severity": "HIGH_RISK",
                        "title": f"Suppressed {label} ({est_val} {unit})",
                        "description": f"Compound pharmacological action depresses {label} below the safe lower bound ({safe_lower} {unit}) to {est_val} {unit}.",
                        "clinical_recommendation": f"Monitor {label} and review stack components suppressing this axis.",
                    })
            else:
                status = "NORMAL_PHYSIOLOGICAL"
                status_label = f"Normal {label} ({est_val} {unit})"
                status_color = "#34d399"

            axis_name = label if "axis" in label.lower() else f"{label} Axis"
            axes.append({
                "name": axis_name,
                "biomarker_id": bio_id,
                "target_tissue": b.get("target_tissue", "Systemic Circulation & Peripheral Tissues"),
                "biometric_modifiers_applied": b.get("biometric_modifiers_applied", []),
                "baseline": baseline,
                "estimated_value": est_val,
                "unit": unit,
                "safe_range": f"{safe_lower} - {safe_upper} {unit}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": in_safe,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "net_delta_str": f"{'+' if delta > 0 else ''}{delta} {unit}",
                "compounds_breakdown": comp_shares,
                "panel": panel,
            })
            processed_bio_ids.add(bio_id)

        # 4. Steady-State Pharmacokinetic & Hormonal Fluctuation Evaluation
        for comp in compounds:
            is_hormonal, hormone_type, primary_axis = _is_hormonal_or_endocrine_agent(comp)
            if not is_hormonal:
                continue

            comp_name = str(comp.get("name") or comp.get("canonical_name") or comp.get("key") or "Hormonal Compound").strip().title()
            tau_h, freq_desc = _extract_dosing_interval_h(comp)

            # Determine effective elimination half-life
            t_half = None
            for th_key in ["t_half_numeric", "half_life_hours", "half_life_h", "apparent_t_half_h", "t_half"]:
                if comp.get(th_key) is not None:
                    try:
                        th_val = float(str(comp[th_key]).replace("h", "").replace("hours", "").strip())
                        if th_val > 0:
                            t_half = th_val
                            break
                    except (ValueError, TypeError):
                        pass

            if t_half is None:
                try:
                    from app.services.pkpd_engine import PKPDEngine
                    pk_params = PKPDEngine.extract_pk_parameters(comp)
                    t_half = pk_params.t_half_h
                except Exception:
                    route = str(comp.get("route", "oral")).lower()
                    if route in ("im", "subq", "depot"):
                        t_half = 120.0  # standard depot default ~5 days
                    else:
                        t_half = 24.0

            t_half = max(0.5, float(t_half or 24.0))
            k_e = math.log(2.0) / t_half
            tau_t_half_ratio = tau_h / t_half

            # Steady-state multi-dose peak-to-trough fluctuation (PTF) and swing ratio
            # Swing ratio = Cmax / Cmin = e^(ke * tau) = 2^(tau / t1/2)
            # PTF = (Cmax - Cmin) / Cavg * 100 = ke * tau * 100 = ln(2) * (tau / t1/2) * 100
            swing_ratio = round(math.exp(k_e * tau_h), 2)
            ptf = round(k_e * tau_h * 100.0, 1)

            # Check if fluctuation is significant
            if tau_t_half_ratio >= 1.0 or ptf >= 70.0 or swing_ratio >= 2.0:
                is_volatile = tau_t_half_ratio >= 1.4 or ptf >= 120.0 or swing_ratio >= 2.8
                severity = "HIGH_RISK" if is_volatile else "MODERATE_RISK"

                # Determine recommended split frequency
                if tau_h >= 168.0:
                    rec_freq = "Twice Weekly (BIW / Mon & Thu) or Every Other Day (EOD / SubQ)"
                    split_action = "Split Weekly Depot to Twice-Weekly (BIW) or EOD"
                elif tau_h >= 72.0:
                    rec_freq = "Daily or Every Other Day (EOD)"
                    split_action = "Split Dosing to EOD or Daily"
                else:
                    rec_freq = "Split into BID (Twice Daily) or Sustained-Release Delivery"
                    split_action = "Split into Twice-Daily (BID) Dosing"

                uncompensated_risks.append({
                    "axis": primary_axis or "Endocrine & Hormonal Stability",
                    "severity": severity,
                    "title": f"Significant Steady-State Hormonal Fluctuation ({comp_name})",
                    "description": (
                        f"Dosing interval of {freq_desc} (tau={tau_h:g}h) relative to elimination half-life "
                        f"(t1/2={t_half:g}h, ratio {tau_t_half_ratio:.2f}) produces wide steady-state peak-to-trough "
                        f"swings (PTF: ~{ptf}%, swing ratio: ~{swing_ratio}x). In {hormone_type.lower()} pathways, "
                        f"large peak surges drive excess aromatization/downstream conversions and receptor downregulation, "
                        f"while deep trough crashes provoke symptom recurrence and axis instability."
                    ),
                    "clinical_recommendation": (
                        f"Split administration of {comp_name} into more frequent micro-doses ({rec_freq}) "
                        f"to flatten steady-state serum fluctuations (target PTF < 50%) while preserving identical "
                        f"cumulative weekly exposure (AUC)."
                    ),
                })
                dose_recommendations.append({
                    "compound": comp_name,
                    "action": split_action,
                    "reason": f"Flatten peak-to-trough rollercoaster swings (PTF: {ptf}% -> <50%) and preserve steady-state hormonal equilibrium.",
                })

            elif (tau_t_half_ratio <= 0.85 or ptf <= 60.0) and tau_h < 168.0:
                # Stable micro-dosed regimen with demonstrated low peak-to-trough fluctuation
                active_mitigations.append({
                    "title": f"Stable Endocrine Micro-Dosing ({comp_name})",
                    "description": (
                        f"Frequent split-dosing schedule ({freq_desc}, tau={tau_h:g}h vs t1/2={t_half:g}h) "
                        f"maintains tight steady-state peak-to-trough equilibrium (PTF: ~{ptf}%, swing ratio: ~{swing_ratio}x), "
                        f"blunting supraphysiological peak surges and preventing trough withdrawal crashes."
                    ),
                    "participating_compounds": [comp_name],
                    "benefited_axis": primary_axis or "Endocrine & Hormonal Stability",
                    "risk_reduction_points": 15.0,
                })

        # Calculate Overall Health Index & Equilibrium Status
        num_mitigations = len(active_mitigations)
        num_uncompensated = len(uncompensated_risks)

        # Calculate Biometric Uncertainty Scale
        is_sex_known = profile_data.get("sex") is not None if profile_data else False
        is_age_known = profile_data.get("age") is not None if profile_data else False
        is_weight_known = profile_data.get("weight_kg") is not None if profile_data else False
        is_height_known = profile_data.get("height_cm") is not None if profile_data else False
        unknown_biometrics_count = sum([not is_sex_known, not is_age_known, not is_weight_known, not is_height_known])

        # Patient BMI
        weight_val = float(profile_data.get("weight_kg")) if (profile_data and profile_data.get("weight_kg")) else None
        height_val = float(profile_data.get("height_cm")) if (profile_data and profile_data.get("height_cm")) else None
        patient_bmi = round(weight_val / max(0.5, (height_val / 100.0) ** 2), 1) if (weight_val and height_val) else None

        # Demographic Uncertainty Scale: each unknown demographic factor adds 5% relative variance to biological CV
        cv_multiplier = 1.0 + (unknown_biometrics_count * 0.05)

        # Tag Priority Tiers, Percent Shifts, and Distribution Curves for each Axis
        for a in axes:
            status = str(a.get("status", ""))
            status_color = str(a.get("status_color", ""))
            in_safe = bool(a.get("in_safe_range", True))
            baseline = float(a.get("baseline", 0.0))
            est_val = float(a.get("estimated_value", baseline))
            pct_shift = (abs(est_val - baseline) / max(abs(baseline), 1e-4) * 100.0) if baseline != 0 else (abs(est_val) * 100.0)
            a["percent_shift"] = round(pct_shift, 2)

            # Determine biomarker-specific biological CV
            bio_id = str(a.get("biomarker_id") or "")
            base_cv = BIOMARKER_BIOLOGICAL_CV_MAP.get(bio_id, DEFAULT_BIOMARKER_CV)
            effective_cv = base_cv * cv_multiplier

            # Identify if lab bloodwork is user-calibrated
            is_lab_calibrated = bool(
                labs and (
                    bio_id in labs
                    or bio_id.replace("bio_", "") in labs
                    or any(k in str(labs).lower() for k in [bio_id.lower(), bio_id.replace("bio_", "").lower()])
                )
            )
            a["is_lab_calibrated"] = is_lab_calibrated
            if is_lab_calibrated:
                # Direct user bloodwork reduces population prior uncertainty
                effective_cv = max(0.02, effective_cv * 0.85)

            # Compute log-normal probability distribution percentiles (p5, p25, p50, p75, p95)
            v = max(0.0001, est_val)
            sigma_log = math.sqrt(math.log(1.0 + effective_cv * effective_cv))
            mu_log = math.log(v)
            p5 = round(math.exp(mu_log - 1.645 * sigma_log), 2 if v < 10 else 1)
            p25 = round(math.exp(mu_log - 0.6745 * sigma_log), 2 if v < 10 else 1)
            p50 = round(v, 2 if v < 10 else 1)
            p75 = round(math.exp(mu_log + 0.6745 * sigma_log), 2 if v < 10 else 1)
            p95 = round(math.exp(mu_log + 1.645 * sigma_log), 2 if v < 10 else 1)

            mean_val = round(v * math.sqrt(1.0 + effective_cv * effective_cv), 2 if v < 10 else 1)
            std_dev = round(mean_val * effective_cv, 2 if v < 10 else 1)

            unit_str = str(a.get("unit") or "")
            a["distribution"] = {
                "p5": p5,
                "p25": p25,
                "p50": p50,
                "p75": p75,
                "p95": p95,
                "mean": mean_val,
                "std_dev": std_dev,
                "cv": round(effective_cv, 3),
                "p5_p95_range_str": f"{p5} - {p95} {unit_str}".strip(),
            }
            a["p5_p95_range_str"] = f"{p5} - {p95} {unit_str}".strip()

            # Tail risk assessment
            safe_up = a.get("safe_upper")
            safe_low = a.get("safe_lower")
            tail_elevation = bool(safe_up is not None and p95 > safe_up)
            tail_suppression = bool(safe_low is not None and p5 < safe_low)
            a["tail_elevation_risk"] = tail_elevation
            a["tail_suppression_risk"] = tail_suppression
            a["has_tail_alert"] = tail_elevation or tail_suppression

            # Priority Tier Classification:
            # Tier 1 (Critical Strain): Out of range with high severity or dangerous status
            # Tier 2 (Moderate Alert / Tail Risk): Moderate elevation/suppression, or out-of-range, or significant tail breach on sensitive axis
            # Tier 3 (Counterbalanced): Genuine multi-agent protective counterbalances
            # Tier 4 (Active Shift / Anabolic Optimization): In-range active shifts or intentional supraphysiological targets
            # Tier 5 (Baseline Stable): Untouched normal baseline axes
            is_counterbalanced_status = any(k in status for k in ["BALANCED", "NORMOTENSIVE", "EUCHRONIC", "PARTIAL_COUNTERBALANCE"])
            has_multiple_comps = len(a.get("compounds_breakdown", [])) >= 2
            is_active_mitigation_axis = any(
                str(m.get("benefited_axis", "")).lower() in str(a.get("name", "")).lower()
                or str(a.get("name", "")).lower() in str(m.get("benefited_axis", "")).lower()
                for m in active_mitigations
            )

            if status_color == "#ef4444" or (not in_safe and any(k in status for k in ["CRASH", "STRAIN", "HYPERKALEMIA", "ELEVATED_RISK", "SUPPRESSED_RISK"])):
                a["priority_tier"] = 1
                a["priority_label"] = "Critical Strain"
            elif status_color == "#f59e0b" or not in_safe or any(k in status for k in ["ELEVATED", "SUPPRESSED", "HYPOTENSIVE", "MODERATE", "BRADYCARDIA", "HYPOKALEMIA"]):
                a["priority_tier"] = 2
                a["priority_label"] = "Moderate Alert"
            elif (is_counterbalanced_status or is_active_mitigation_axis) and (has_multiple_comps or is_active_mitigation_axis):
                a["priority_tier"] = 3
                if tail_elevation or tail_suppression:
                    a["priority_label"] = "Counterbalanced (Tail Alert)"
                else:
                    a["priority_label"] = "Counterbalanced"
            elif abs(est_val - baseline) > 1e-3 or len(a.get("compounds_breakdown", [])) > 0 or status == "OPTIMIZED_ANABOLIC":
                a["priority_tier"] = 4
                a["priority_label"] = "Active Shift"
            else:
                a["priority_tier"] = 5
                a["priority_label"] = "Baseline Stable"

        # Deterministic clinical sorting:
        # Tier 1 (Critical Out-of-Range) -> Tier 2 (Moderate Alert) -> Tier 3 (Counterbalanced) -> Tier 4 (Active Shift) -> Tier 5 (Baseline)
        axes.sort(key=lambda x: (
            x.get("priority_tier", 5),
            -x.get("percent_shift", 0.0),
            x.get("name", "")
        ))

        all_in_safe = all(a.get("in_safe_range", True) or a.get("status") == "OPTIMIZED_ANABOLIC" for a in axes)

        if num_uncompensated == 0 and num_mitigations > 0 and all_in_safe:
            overall_status = "OPTIMAL_EQUILIBRIUM"
            status_label = "Optimal Physiological Equilibrium"
            health_index = 95
        elif num_mitigations > 0 and all_in_safe:
            overall_status = "COUNTERBALANCED"
            status_label = "Therapeutic Counterbalance Active"
            health_index = 88
        elif num_uncompensated > 0:
            overall_status = "UNCOMPENSATED_STRAIN"
            status_label = "Uncompensated Axis Disruption"
            health_index = max(20, 70 - (num_uncompensated * 18))
        elif all_in_safe:
            overall_status = "PHYSIOLOGICAL_BASELINE"
            status_label = "Normal Physiological Baseline"
            health_index = 85
        else:
            overall_status = "MODERATE_DEVIATION"
            status_label = "Moderate Axis Deviation"
            health_index = 72

        return {
            "health_index": health_index,
            "status": overall_status,
            "status_label": status_label,
            "timeline": cascade_results.get("timeline", "steady_state"),
            "timeline_days": cascade_results.get("timeline_days"),
            "timeline_label": cascade_results.get("timeline_label", "Steady State (Full Equilibrium)"),
            "patient_biometrics": {
                "sex": profile_data.get("sex") if profile_data else None,
                "age": profile_data.get("age") if profile_data else None,
                "weight_kg": profile_data.get("weight_kg") if profile_data else None,
                "height_cm": profile_data.get("height_cm") if profile_data else None,
                "body_fat_pct": profile_data.get("body_fat_pct") if profile_data else None,
                "bmi": patient_bmi,
                "unknown_biometrics_count": unknown_biometrics_count,
                "cv_uncertainty_scale": round(cv_multiplier, 2),
            },
            "axes": axes,
            "active_mitigations": active_mitigations,
            "uncompensated_risks": uncompensated_risks,
            "dose_recommendations": dose_recommendations,
            "cascade_biomarker_shifts": cascade_results.get("biomarker_shifts", []),
            "target_combined_effects": combined_effects,
        }


    def _evaluate_pair(
        self,
        comp_a: Dict[str, Any],
        comp_b: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        key_a = _normalize_name(comp_a.get("key") or comp_a.get("name"))
        name_a = comp_a.get("name") or key_a
        key_b = _normalize_name(comp_b.get("key") or comp_b.get("name"))
        name_b = comp_b.get("name") or key_b

        # 1. Documented Synergies (Check bidirectional synergy pairing)
        syn_item = None
        targets_b = {
            key_b,
            name_b.lower(),
            str(comp_b.get("key", "")).lower(),
            str(comp_b.get("canonical_key", "")).lower(),
            str(comp_b.get("name", "")).lower(),
            _normalize_name(key_b),
            _normalize_name(name_b),
        }
        if any(t in targets_b for t in ["theanine", "l_theanine", "l-theanine"]):
            targets_b.update({"theanine", "l_theanine", "l-theanine", "suntheanine"})

        targets_a = {
            key_a,
            name_a.lower(),
            str(comp_a.get("key", "")).lower(),
            str(comp_a.get("canonical_key", "")).lower(),
            str(comp_a.get("name", "")).lower(),
            _normalize_name(key_a),
            _normalize_name(name_a),
        }
        if any(t in targets_a for t in ["theanine", "l_theanine", "l-theanine"]):
            targets_a.update({"theanine", "l_theanine", "l-theanine", "suntheanine"})

        for syn in comp_a.get("synergies", []):
            if isinstance(syn, dict):
                p = str(syn.get("partner", "")).lower()
                if p in targets_b or _normalize_name(p) in targets_b:
                    syn_item = syn
                    break
        if not syn_item:
            for syn in comp_b.get("synergies", []):
                if isinstance(syn, dict):
                    p = str(syn.get("partner", "")).lower()
                    if p in targets_a or _normalize_name(p) in targets_a:
                        syn_item = syn
                        break
            is_tudca = any(w in key_a or w in name_a.lower() for w in ["tudca", "tauroursodeoxycholic"]) or any(w in key_b or w in name_b.lower() for w in ["tudca", "tauroursodeoxycholic"])
            is_oral_aas = is_17a_alkylated(comp_a) or is_17a_alkylated(comp_b)

            if is_tudca and is_oral_aas:
                syn_item = {
                    "partner": name_b if any(w in name_a.lower() for w in ["tudca", "tauroursodeoxycholic"]) else name_a,
                    "effect": "Hepatobiliary Cytoprotection & Cholestasis Prevention",
                    "description": "TUDCA hydrophilic bile acid conjugation prevents canalicular cholestasis and membrane injury induced by 17α-alkylated oral androgens.",
                }

        if syn_item:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "SYNERGISTIC",
                "severity_score": -5,
                "conflict_types": ["SYNERGY"],
                "title": f"Synergistic Mechanism: {syn_item.get('effect', 'Positive Pairing')}",
                "description": syn_item.get("description") or f"{name_a} and {name_b} provide mutually reinforcing physiological benefits.",
                "affected_targets": [r.get("target") for r in comp_a.get("receptor_targets", []) + comp_b.get("receptor_targets", []) if isinstance(r, dict)],
                "clinical_recommendation": "Standardized clinical dosage recommended for both compounds.",
                "evidence_level": "strong",
            }

        # 1b. Specific Herb-Drug & Supplement Interaction Rule Engines
        tags_a = _get_compound_ontology_tags(comp_a)
        tags_b = _get_compound_ontology_tags(comp_b)

        # Piperine Bioenhancer Effect
        is_pip_a = _has_any_ontology_match(tags_a, ["piperine", "bioperine", "black pepper"])
        is_pip_b = _has_any_ontology_match(tags_b, ["piperine", "bioperine", "black pepper"])
        if is_pip_a or is_pip_b:
            pip_name = name_a if is_pip_a else name_b
            sub_comp = comp_b if is_pip_a else comp_a
            sub_name = name_b if is_pip_a else name_a
            sub_tags = tags_b if is_pip_a else tags_a

            is_polyphenol = _has_any_ontology_match(sub_tags, ["curcumin", "turmeric", "resveratrol", "quercetin", "polyphenol", "flavonoid", "coq10", "berberine"])
            is_sensitive_drug = sub_comp.get("is_narrow_therapeutic_index") or _has_any_ontology_match(sub_tags, ["statin", "tacrolimus", "cyclosporine", "digoxin", "warfarin", "theophylline"])

            if is_polyphenol:
                sub_comp = dict(sub_comp)
                if not sub_comp.get("is_high_first_pass"):
                    sub_comp["is_high_first_pass"] = True
                if not sub_comp.get("bioavailability_f") and sub_comp.get("oral_bioavailability"):
                    sub_comp["bioavailability_f"] = sub_comp.get("oral_bioavailability")
                sub_p2 = dict(sub_comp.get("phase2_enzymes") or {})
                sub_p2_subs = [str(x).upper() for x in sub_p2.get("substrates", [])]
                if "UGT1A1" not in sub_p2_subs:
                    sub_p2["substrates"] = list(sub_p2.get("substrates", [])) + ["UGT1A1"]
                    sub_comp["phase2_enzymes"] = sub_p2

            from app.services.pkpd_engine import PKPDEngine
            aucr_val, cmax_mult, _ = PKPDEngine.calculate_ddi_shift(sub_comp, [comp_a if is_pip_a else comp_b])

            if is_polyphenol and not is_sensitive_drug:
                return {
                    "source_key": key_a,
                    "source_name": name_a,
                    "target_key": key_b,
                    "target_name": name_b,
                    "is_self": False,
                    "severity": "SYNERGISTIC",
                    "severity_score": -5,
                    "conflict_types": ["SYNERGY", "BIOAVAILABILITY_ENHANCEMENT"],
                    "title": f"Botanical Bioavailability Synergy ({pip_name} + {sub_name})",
                    "description": (
                        f"{pip_name} inhibits intestinal P-glycoprotein (ABCB1) efflux and UGT1A1 glucuronidation, "
                        f"dramatically overcoming the intestinal first-pass metabolism bottleneck for {sub_name} "
                        f"(estimated +{int(round((aucr_val - 1.0) * 100))}% AUC bioavailability surge, {round(aucr_val, 1)}x exposure)."
                    ),
                    "affected_targets": ["P-glycoprotein / ABCB1", "UDP-Glucuronosyltransferase 1A1 (UGT1A1)", "CYP3A4"],
                    "clinical_recommendation": f"Co-administration with {pip_name} optimizes clinical oral absorption of {sub_name}.",
                    "evidence_level": "strong",
                    "ddi_auc_ratio": round(aucr_val, 2),
                    "ddi_cmax_multiplier": round(cmax_mult, 2),
                }
            elif is_sensitive_drug:
                return {
                    "source_key": key_a,
                    "source_name": name_a,
                    "target_key": key_b,
                    "target_name": name_b,
                    "is_self": False,
                    "severity": "HIGH_RISK",
                    "severity_score": 25,
                    "conflict_types": ["TRANSPORTER", "CYP450", "PHASE_II"],
                    "title": f"Bioenhancer Drug Toxicity Surge ({pip_name} + {sub_name})",
                    "description": (
                        f"{pip_name} inhibits P-gp efflux, CYP3A4, and UGT1A1 clearance, elevating systemic exposure of {sub_name} "
                        f"({round(aucr_val, 1)}x AUC surge) and predisposing to narrow-therapeutic-index toxicity."
                    ),
                    "affected_targets": ["P-glycoprotein / ABCB1", "CYP3A4", "UGT1A1"],
                    "clinical_recommendation": f"Monitor {sub_name} serum levels closely or separate dosing from {pip_name}.",
                    "evidence_level": "strong",
                    "ddi_auc_ratio": round(aucr_val, 2),
                    "ddi_cmax_multiplier": round(cmax_mult, 2),
                }

        # St. John's Wort PXR Nuclear Receptor Enzyme Induction
        is_sjw_a = _has_any_ontology_match(tags_a, ["st john", "st. john", "hypericum", "hyperforin"])
        is_sjw_b = _has_any_ontology_match(tags_b, ["st john", "st. john", "hypericum", "hyperforin"])
        if is_sjw_a or is_sjw_b:
            sjw_name = name_a if is_sjw_a else name_b
            sub_comp = comp_b if is_sjw_a else comp_a
            sub_name = name_b if is_sjw_a else name_a
            sub_tags = tags_b if is_sjw_a else tags_a

            cyp_sub = sub_comp.get("cyp_enzymes", {}) or {}
            trans_sub = sub_comp.get("transporters", {}) or {}
            is_cyp_p_gp_sub = any(e in ["CYP3A4", "CYP2C9", "CYP2C19"] for e in (cyp_sub.get("substrates") or [])) or "P-GP" in [t.upper() for t in (trans_sub.get("substrates") or [])] or _has_any_ontology_match(sub_tags, ["contraceptive", "statin", "cyclosporine", "tacrolimus", "digoxin", "warfarin", "antiretroviral", "protease inhibitor"])

            if is_cyp_p_gp_sub:
                from app.services.pkpd_engine import PKPDEngine
                aucr_val, cmax_mult, _ = PKPDEngine.calculate_ddi_shift(sub_comp, [comp_a if is_sjw_a else comp_b])
                return {
                    "source_key": key_a,
                    "source_name": name_a,
                    "target_key": key_b,
                    "target_name": name_b,
                    "is_self": False,
                    "severity": "HIGH_RISK",
                    "severity_score": 30,
                    "conflict_types": ["CYP450", "TRANSPORTER", "ENZYME_INDUCTION"],
                    "title": f"Nuclear PXR Enzyme & P-gp Induction ({sjw_name} + {sub_name})",
                    "description": (
                        f"{sjw_name} (Hyperforin) activates Pregnane X Receptor (PXR), powerfully inducing hepatic and intestinal "
                        f"expression of CYP3A4, CYP2C9, and P-gp. This accelerates clearance of {sub_name}, causing a dramatic drop "
                        f"in systemic exposure ({round(aucr_val, 2)}x AUC drop, ~50-70% reduction) and risking therapeutic failure or breakthrough."
                    ),
                    "affected_targets": ["Pregnane X Receptor (PXR / NR1I2)", "CYP3A4", "CYP2C9", "P-glycoprotein / ABCB1"],
                    "clinical_recommendation": f"Avoid concurrent use. Discontinue {sjw_name} or select alternative therapy not cleared via CYP3A4/P-gp.",
                    "evidence_level": "strong",
                    "ddi_auc_ratio": round(aucr_val, 2),
                    "ddi_cmax_multiplier": round(cmax_mult, 2),
                }

        # Gut Microbiota TMA/TMAO Mitigation (Oral L-Carnitine/Choline + Allicin/Garlic Extract/DMB)
        is_tma_prec_a = _has_any_ontology_match(tags_a, ["carnitine", "alcar", "acetylcarnitine", "choline", "alpha-gpc", "citicoline", "betaine"]) or any("tma lyase" in str(r.get("target", "")).lower() and "substrate" in str(r.get("action", "")).lower() for r in comp_a.get("receptor_targets", []) if isinstance(r, dict))
        is_tma_prec_b = _has_any_ontology_match(tags_b, ["carnitine", "alcar", "acetylcarnitine", "choline", "alpha-gpc", "citicoline", "betaine"]) or any("tma lyase" in str(r.get("target", "")).lower() and "substrate" in str(r.get("action", "")).lower() for r in comp_b.get("receptor_targets", []) if isinstance(r, dict))
        is_tma_inh_a = _has_any_ontology_match(tags_a, ["allicin", "garlic", "allium", "diallyl thiosulfinate", "dimethylbutanol", "dmb"]) or any("tma lyase" in str(r.get("target", "")).lower() and "inhibitor" in str(r.get("action", "")).lower() for r in comp_a.get("receptor_targets", []) if isinstance(r, dict))
        is_tma_inh_b = _has_any_ontology_match(tags_b, ["allicin", "garlic", "allium", "diallyl thiosulfinate", "dimethylbutanol", "dmb"]) or any("tma lyase" in str(r.get("target", "")).lower() and "inhibitor" in str(r.get("action", "")).lower() for r in comp_b.get("receptor_targets", []) if isinstance(r, dict))

        if (is_tma_prec_a and is_tma_inh_b) or (is_tma_prec_b and is_tma_inh_a):
            prec_name = name_a if is_tma_prec_a else name_b
            inh_name = name_b if is_tma_prec_a else name_a
            prec_comp = comp_a if is_tma_prec_a else comp_b
            prec_route = str(prec_comp.get("route") or "oral").lower()
            is_oral = prec_route in ["oral", "po", "swallow"]

            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "SYNERGISTIC",
                "severity_score": -6,
                "conflict_types": ["SYNERGY", "GUT_MICROBIOME_MITIGATION"],
                "title": f"Gut Microbiota TMAO Mitigation ({inh_name} + {prec_name})",
                "description": (
                    f"{inh_name} potently inhibits gut bacterial trimethylamine lyase (CntA/CntB / yeaW/yeaX), "
                    f"blocking the intestinal microbial cleavage of oral {prec_name} into trimethylamine (TMA) and preventing "
                    f"downstream host hepatic FMO3 oxidation to atherogenic Trimethylamine N-Oxide (TMAO)."
                    if is_oral else
                    f"{prec_name} is administered via parenteral {prec_route.upper()} route, already bypassing intestinal microbiota; "
                    f"{inh_name} provides supplementary cardiovascular endothelial protection."
                ),
                "affected_targets": [
                    "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)",
                    "Flavin-Containing Monooxygenase 3 (FMO3)",
                    "Endothelial Nitric Oxide Synthase (eNOS / NOS3)",
                ],
                "clinical_recommendation": f"Co-administration of {inh_name} with oral {prec_name} effectively counterbalances potential TMAO generation while preserving mitochondrial metabolic benefits.",
                "evidence_level": "strong",
            }

        # Multivalent Cation Gastrointestinal Chelation Collision
        is_mineral_a = _has_any_ontology_match(tags_a, ["magnesium", "zinc", "calcium", "iron", "aluminum", "multivalent cation"])
        is_mineral_b = _has_any_ontology_match(tags_b, ["magnesium", "zinc", "calcium", "iron", "aluminum", "multivalent cation"])
        is_chelatable_a = _has_any_ontology_match(tags_a, ["fluoroquinolone", "ciprofloxacin", "levofloxacin", "moxifloxacin", "tetracycline", "doxycycline", "minocycline", "bisphosphonate", "alendronate"])
        is_chelatable_b = _has_any_ontology_match(tags_b, ["fluoroquinolone", "ciprofloxacin", "levofloxacin", "moxifloxacin", "tetracycline", "doxycycline", "minocycline", "bisphosphonate", "alendronate"])

        if (is_mineral_a and is_chelatable_b) or (is_mineral_b and is_chelatable_a):
            min_name = name_a if is_mineral_a else name_b
            drug_name = name_b if is_mineral_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 28,
                "conflict_types": ["CHELATION", "PHYSICOCHEMICAL"],
                "title": f"Gastrointestinal Multivalent Cation Chelation ({min_name} + {drug_name})",
                "description": (
                    f"Multivalent cations in {min_name} form insoluble non-absorbable chelate complexes with {drug_name} "
                    f"in the gastrointestinal lumen, reducing antibiotic/drug oral absorption by 70-90% and causing treatment failure."
                ),
                "affected_targets": ["Gastrointestinal Intestinal Absorption Site", "Chelation Complex"],
                "clinical_recommendation": f"Separate oral administration of {min_name} and {drug_name} by at least 2 hours before or 4 hours after.",
                "evidence_level": "strong",
            }

        # Botanical COMT Inhibition Catecholamine Synergy
        targets_a = _get_target_gene_actions(comp_a)
        targets_b = _get_target_gene_actions(comp_b)
        atc_a = _get_atc_prefixes(comp_a)
        atc_b = _get_atc_prefixes(comp_b)

        is_comt_a = ActionType.INHIBITOR in targets_a.get("COMT", set()) or _has_any_ontology_match(tags_a, ["egcg", "green tea", "quercetin", "comt inhibitor"])
        is_comt_b = ActionType.INHIBITOR in targets_b.get("COMT", set()) or _has_any_ontology_match(tags_b, ["egcg", "green tea", "quercetin", "comt inhibitor"])
        is_catechol_a = (
            bool(ActionType.AGONIST in (targets_a.get("ADRA1A", set()) | targets_a.get("ADRB1", set()) | targets_a.get("DRD1", set()) | targets_a.get("DRD2", set())))
            or bool(ActionType.INHIBITOR in (targets_a.get("SLC6A2", set()) | targets_a.get("SLC6A3", set()) | targets_a.get("ADORA1", set()) | targets_a.get("ADORA2A", set())))
            or bool(atc_a & {"N06B", "N06BA", "N06BC"})
            or _has_any_ontology_match(tags_a, ["caffeine", "tyrosine", "ephedrine", "dopamine", "levodopa", "l-dopa", "amphetamine", "synephrine"])
        )
        is_catechol_b = (
            bool(ActionType.AGONIST in (targets_b.get("ADRA1A", set()) | targets_b.get("ADRB1", set()) | targets_b.get("DRD1", set()) | targets_b.get("DRD2", set())))
            or bool(ActionType.INHIBITOR in (targets_b.get("SLC6A2", set()) | targets_b.get("SLC6A3", set()) | targets_b.get("ADORA1", set()) | targets_b.get("ADORA2A", set())))
            or bool(atc_b & {"N06B", "N06BA", "N06BC"})
            or _has_any_ontology_match(tags_b, ["caffeine", "tyrosine", "ephedrine", "dopamine", "levodopa", "l-dopa", "amphetamine", "synephrine"])
        )

        if (is_comt_a and is_catechol_b) or (is_comt_b and is_catechol_a):
            comt_name = name_a if is_comt_a else name_b
            cat_name = name_b if is_comt_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "SYNERGISTIC",
                "severity_score": -5,
                "conflict_types": ["SYNERGY", "CATECHOLAMINE_POTENTIATION"],
                "title": f"COMT Inhibition & Catecholamine Synergy ({comt_name} + {cat_name})",
                "description": (
                    f"{comt_name} inhibits Catechol-O-Methyltransferase (COMT), slowing enzymatic degradation of {cat_name} "
                    f"and prolonging synaptic dopamine/norepinephrine signaling and cognitive focus."
                ),
                "affected_targets": ["Catechol-O-Methyltransferase (COMT)", "Dopamine / Norepinephrine Synaptic Half-Life"],
                "clinical_recommendation": f"Standardized pairing. Monitor for excessive sympathetic stimulation at high doses.",
                "evidence_level": "strong",
            }

        # 5-Alpha Reductase Dual Inhibition Synergy
        is_5ar_a = ActionType.INHIBITOR in (targets_a.get("SRD5A1", set()) | targets_a.get("SRD5A2", set())) or bool(atc_a & {"G04CB"}) or _has_any_ontology_match(tags_a, ["saw palmetto", "serenoa", "permixon", "finasteride", "dutasteride", "5-alpha reductase inhibitor"])
        is_5ar_b = ActionType.INHIBITOR in (targets_b.get("SRD5A1", set()) | targets_b.get("SRD5A2", set())) or bool(atc_b & {"G04CB"}) or _has_any_ontology_match(tags_b, ["saw palmetto", "serenoa", "permixon", "finasteride", "dutasteride", "5-alpha reductase inhibitor"])

        if is_5ar_a and is_5ar_b and key_a != key_b:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "SYNERGISTIC",
                "severity_score": -5,
                "conflict_types": ["SYNERGY", "DUAL_5AR_INHIBITION"],
                "title": f"Additive 5-Alpha Reductase Inhibition ({name_a} + {name_b})",
                "description": f"Co-administration of {name_a} and {name_b} provides additive 5-alpha reductase enzyme suppression, reducing follicular DHT conversion.",
                "affected_targets": ["5-Alpha Reductase Subtype 1 & 2 (SRD5A1 / SRD5A2)"],
                "clinical_recommendation": "Monitor for androgenic/DHT suppression symptoms.",
                "evidence_level": "strong",
            }

        def _extract_enzyme_set(items, keys=("enzyme", "transporter", "name", "cyp", "gene")):
            res = set()
            for x in items or []:
                raw = None
                if isinstance(x, dict):
                    for k in keys:
                        v = x.get(k)
                        if v:
                            raw = str(v).strip()
                            break
                elif x:
                    raw = str(x).strip()
                if raw:
                    upper_raw = raw.upper()
                    if upper_raw in ("P-GP", "P-GLYCOPROTEIN", "PGP", "ABCB1"):
                        res.add("P-gp")
                    else:
                        res.add(upper_raw)
            return res

        # 2. CYP450 Collisions
        cyp_a = comp_a.get("cyp_enzymes", {}) or {}
        cyp_b = comp_b.get("cyp_enzymes", {}) or {}
        sub_a = _extract_enzyme_set(cyp_a.get("substrates", []))
        inh_a = _extract_enzyme_set(cyp_a.get("inhibitors", []))
        sub_b = _extract_enzyme_set(cyp_b.get("substrates", []))
        inh_b = _extract_enzyme_set(cyp_b.get("inhibitors", []))

        overlap_a_inh_b_sub = inh_a.intersection(sub_b)
        overlap_b_inh_a_sub = inh_b.intersection(sub_a)
        cyp_collisions = overlap_a_inh_b_sub.union(overlap_b_inh_a_sub)

        if cyp_collisions:
            from app.services.pkpd_engine import PKPDEngine
            aucr_b, cmax_m_b, _ = PKPDEngine.calculate_ddi_shift(comp_b, [comp_a])
            aucr_a, cmax_m_a, _ = PKPDEngine.calculate_ddi_shift(comp_a, [comp_b])
            max_aucr = max(aucr_a, aucr_b)
            max_cmax_m = max(cmax_m_a, cmax_m_b)

            details = []
            if overlap_a_inh_b_sub:
                pct_surge = int(round((aucr_b - 1.0) * 100))
                details.append(f"{name_a} inhibits {', '.join(sorted(overlap_a_inh_b_sub))}, the primary clearance pathway for {name_b}, causing an estimated +{pct_surge}% AUC surge ({round(aucr_b, 1)}x exposure).")
            if overlap_b_inh_a_sub:
                pct_surge = int(round((aucr_a - 1.0) * 100))
                details.append(f"{name_b} inhibits {', '.join(sorted(overlap_b_inh_a_sub))}, delaying {name_a} clearance (+{pct_surge}% AUC surge).")

            is_high_risk = any(e in {"CYP3A4", "CYP2D6", "CYP2C9"} for e in cyp_collisions) or comp_a.get("is_narrow_therapeutic_index") or comp_b.get("is_narrow_therapeutic_index")
            severity = "HIGH_RISK" if is_high_risk else "MODERATE_RISK"
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": severity,
                "severity_score": 25 if severity == "HIGH_RISK" else 15,
                "conflict_types": ["CYP450"],
                "title": f"CYP450 Enzyme Collision ({', '.join(sorted(cyp_collisions))})",
                "description": " ".join(details),
                "affected_targets": list(cyp_collisions),
                "clinical_recommendation": "Dose reduce the substrate compound or separate administration times by at least 4 hours.",
                "evidence_level": "strong",
                "ddi_auc_ratio": round(max_aucr, 2),
                "ddi_cmax_multiplier": round(max_cmax_m, 2),
            }

        # 3. Transporter Collisions (P-gp, OATP1B1, BCRP, OCT2, OAT1/3)
        trans_a = comp_a.get("transporters", {}) or {}
        trans_b = comp_b.get("transporters", {}) or {}
        t_sub_a = _extract_enzyme_set(trans_a.get("substrates", []))
        t_inh_a = _extract_enzyme_set(trans_a.get("inhibitors", []))
        t_sub_b = _extract_enzyme_set(trans_b.get("substrates", []))
        t_inh_b = _extract_enzyme_set(trans_b.get("inhibitors", []))

        trans_overlap = (t_inh_a.intersection(t_sub_b)).union(t_inh_b.intersection(t_sub_a))
        if trans_overlap:
            from app.services.pkpd_engine import PKPDEngine
            aucr_b, cmax_m_b, _ = PKPDEngine.calculate_ddi_shift(comp_b, [comp_a])
            aucr_a, cmax_m_a, _ = PKPDEngine.calculate_ddi_shift(comp_a, [comp_b])
            max_aucr = max(aucr_a, aucr_b)
            max_cmax_m = max(cmax_m_a, cmax_m_b)

            trans_names = ", ".join(sorted(trans_overlap))
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK" if ("P-GP" in trans_overlap or "OATP1B1" in trans_overlap or "P-gp" in trans_overlap) else "MODERATE_RISK",
                "severity_score": 22,
                "conflict_types": ["TRANSPORTER"],
                "title": f"Drug Transporter Collision ({trans_names})",
                "description": f"Transporter inhibition at {trans_names} alters intestinal efflux, tissue uptake, or renal secretion between {name_a} and {name_b} ({round(max_aucr, 1)}x exposure multiplier).",
                "affected_targets": list(trans_overlap),
                "clinical_recommendation": "Monitor for altered bioavailability and tissue exposure.",
                "evidence_level": "strong",
                "ddi_auc_ratio": round(max_aucr, 2),
                "ddi_cmax_multiplier": round(max_cmax_m, 2),
            }

        # 4. Phase II Glucuronidation Collisions (UGTs)
        p2_a = comp_a.get("phase2_enzymes", {}) or {}
        p2_b = comp_b.get("phase2_enzymes", {}) or {}
        p2_sub_a = _extract_enzyme_set(p2_a.get("substrates", []))
        p2_inh_a = _extract_enzyme_set(p2_a.get("inhibitors", []))
        p2_sub_b = _extract_enzyme_set(p2_b.get("substrates", []))
        p2_inh_b = _extract_enzyme_set(p2_b.get("inhibitors", []))

        p2_overlap = (p2_inh_a.intersection(p2_sub_b)).union(p2_inh_b.intersection(p2_sub_a))
        if p2_overlap:
            p2_names = ", ".join(sorted(p2_overlap))
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 20,
                "conflict_types": ["PHASE_II"],
                "title": f"Phase II Glucuronidation Blockade ({p2_names})",
                "description": f"Inhibition of {p2_names} blocks conjugation clearance, dramatically increasing circulating substrate levels.",
                "affected_targets": list(p2_overlap),
                "clinical_recommendation": "Dose reduce the glucuronidated substrate and monitor for systemic toxicity.",
                "evidence_level": "strong",
            }

        # 5. Pharmacodynamic CNS Stimulant & Sedative Collisions
        burdens_a = comp_a.get("organ_burdens", {}) or {}
        burdens_b = comp_b.get("organ_burdens", {}) or {}

        # 5a. Dynamic Sympathoadrenal & Adrenergic Cascades
        is_beta_a, class_beta_a = _is_beta_agonist(comp_a)
        is_beta_b, class_beta_b = _is_beta_agonist(comp_b)
        is_a2_a, class_a2_a = _is_alpha2_antagonist(comp_a)
        is_a2_b, class_a2_b = _is_alpha2_antagonist(comp_b)
        is_ade_a, class_ade_a = _is_adenosine_antagonist_or_pde_inhibitor(comp_a)
        is_ade_b, class_ade_b = _is_adenosine_antagonist_or_pde_inhibitor(comp_b)
        is_symp_a, class_symp_a = _is_sympathomimetic_stimulant(comp_a)
        is_symp_b, class_symp_b = _is_sympathomimetic_stimulant(comp_b)

        # Case 1: Beta-Agonist + Alpha-2 Antagonist (e.g. Clenbuterol + Yohimbine)
        if (is_beta_a and is_a2_b) or (is_beta_b and is_a2_a):
            beta_name = name_a if is_beta_a else name_b
            a2_name = name_b if is_beta_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 35,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": f"Sympathoadrenal Overdrive & Arrhythmogenic Crisis ({beta_name} + {a2_name})",
                "description": (
                    f"Co-administration of {beta_name} (Beta-Adrenergic Agonist) and {a2_name} (Presynaptic Alpha-2 Blocker) "
                    f"produces severe convergent sympathoadrenal hyper-activation. Alpha-2 blockade triggers uncontrolled "
                    f"synaptic norepinephrine exocytosis that floods post-junctional receptors while the beta-agonist directly "
                    f"stimulates cardiac beta-1/beta-2 pathways, escalating tachycardia, palpitations, severe hypertensive spikes, "
                    f"and life-threatening ventricular arrhythmia risk."
                ),
                "affected_targets": ["Beta-2 Adrenergic Receptor", "Beta-1 Adrenergic Receptor", "Alpha-2 Adrenergic Autoreceptor", "SA/AV Nodal Conduction"],
                "clinical_recommendation": "Avoid concurrent combination. Do not combine beta-2 agonists with alpha-2 blockers. Monitor continuous ECG, heart rate, and blood pressure.",
                "evidence_level": "strong",
            }

        # Case 2: Beta-Agonist + Adenosine Antagonist / PDE Inhibitor (e.g. Clenbuterol + Caffeine / Theophylline)
        if (is_beta_a and is_ade_b) or (is_beta_b and is_ade_a):
            beta_name = name_a if is_beta_a else name_b
            ade_name = name_b if is_beta_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 30,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": f"Synergistic Intracellular cAMP Overload & Tachycardia ({beta_name} + {ade_name})",
                "description": (
                    f"Combining {beta_name} (Beta-Adrenergic Gs Agonist) with {ade_name} (Adenosine Antagonist / PDE Inhibitor) "
                    f"causes multiplicative intracellular cyclic AMP (cAMP) accumulation in cardiac myocytes and peripheral vasculature. "
                    f"Direct adenylyl cyclase stimulation coupled with removal of purinergic inhibition and reduced cAMP degradation "
                    f"triggers excessive positive inotropy/chronotropy, severe resting tachycardia, tremor, cardiac oxygen demand mismatch, and hypokalemia."
                ),
                "affected_targets": ["Adenylyl Cyclase / cAMP Signaling", "Adenosine A1/A2A Receptors", "Beta-2/Beta-1 Adrenergic Receptors", "Myocardial Contractility"],
                "clinical_recommendation": "Strictly avoid high-dose concurrent use. Separate administration by at least 6-8 hours, monitor resting heart rate, and maintain serum potassium and hydration.",
                "evidence_level": "strong",
            }

        # Case 3: Beta-Agonist + Sympathomimetic Stimulant (e.g. Clenbuterol + Ephedrine / Amphetamine)
        if (is_beta_a and is_symp_b) or (is_beta_b and is_symp_a):
            beta_name = name_a if is_beta_a else name_b
            symp_name = name_b if is_beta_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 32,
                "conflict_types": ["PHARMACODYNAMIC", "ORGAN_BURDEN", "DOWNSTREAM_CASCADE"],
                "title": f"Dual Adrenergic Sympathetic Hyper-Stimulation ({beta_name} + {symp_name})",
                "description": (
                    f"Co-administration of {beta_name} and {symp_name} compounds direct post-junctional beta-receptor stimulation "
                    f"with central/peripheral monoaminergic outflow, significantly increasing arterial wall shear stress, "
                    f"resting tachycardia, and myocardial strain."
                ),
                "affected_targets": ["Beta-Adrenergic Receptors", "Monoamine Transporters", "Cardiovascular Tone"],
                "clinical_recommendation": "Avoid simultaneous use. Dose reduce both agents and monitor resting heart rate and blood pressure twice daily.",
                "evidence_level": "strong",
            }

        # Case 4: Alpha-2 Antagonist + Adenosine Antagonist / Sympathomimetic (e.g. Yohimbine + Caffeine)
        if (is_a2_a and (is_ade_b or is_symp_b)) or (is_a2_b and (is_ade_a or is_symp_a)):
            a2_name = name_a if is_a2_a else name_b
            other_name = name_b if is_a2_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 26,
                "conflict_types": ["PHARMACODYNAMIC", "ORGAN_BURDEN"],
                "title": "Dual Stimulant Sympathetic Hyper-Activation",
                "description": (
                    f"Co-administration of {a2_name} (Presynaptic Alpha-2 Blocker) and {other_name} produces additive catecholaminergic "
                    f"outflow and central purinergic disinhibition, escalating resting tachycardia, acute anxiety, and hypertensive risk."
                ),
                "affected_targets": ["Alpha-2 Adrenergic Receptors", "Adenosine Receptors", "Cardiovascular Tone"],
                "clinical_recommendation": "Avoid simultaneous intake. Separate administration or reduce doses.",
                "evidence_level": "strong",
            }

        # Case 5: Dual Beta-Agonists
        if is_beta_a and is_beta_b:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 30,
                "conflict_types": ["PHARMACODYNAMIC", "ORGAN_BURDEN"],
                "title": f"Dual Beta-Adrenergic Agonist Overload ({name_a} + {name_b})",
                "description": (
                    f"Co-administration of redundant Beta-Adrenergic agonists ({name_a} and {name_b}) produces additive "
                    f"cardiovascular inotropic load, increasing risk of tachyarrhythmias and receptor desensitization."
                ),
                "affected_targets": ["Beta-1/Beta-2 Adrenergic Receptors"],
                "clinical_recommendation": "Eliminate redundant beta-agonist therapy.",
                "evidence_level": "strong",
            }

        # Case 6: Beta-Blocker + Beta-Agonist (Competitive Pharmacodynamic Antagonism)
        is_bb_a = _is_beta_blocker(comp_a)
        is_bb_b = _is_beta_blocker(comp_b)
        if (is_bb_a and is_beta_b) or (is_bb_b and is_beta_a):
            bb_name = name_a if is_bb_a else name_b
            ba_name = name_b if is_bb_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "MODERATE_RISK",
                "severity_score": 15,
                "conflict_types": ["PHARMACODYNAMIC", "ANTAGONISM"],
                "title": f"Opposing Beta-Adrenergic Antagonism ({bb_name} + {ba_name})",
                "description": (
                    f"Concomitant use of {bb_name} (Beta-Adrenergic Blocker) and {ba_name} (Beta-Adrenergic Agonist) "
                    f"results in mutual competitive antagonism at adrenergic receptors. {bb_name} blunts the stimulatory/bronchodilatory "
                    f"efficacy of {ba_name}, while {ba_name} counteracts the rate-control and cardioprotective effects of {bb_name}."
                ),
                "affected_targets": ["Beta-1 Adrenergic Receptor", "Beta-2 Adrenergic Receptor"],
                "clinical_recommendation": "Avoid concurrent combination of beta-blockers with beta-agonists unless specifically co-managed with close vitals monitoring.",
                "evidence_level": "strong",
            }

        # 5b. General Organ Burden Stimulant & Sedative Collisions
        stim_a = str(burdens_a.get("cns_stimulant", "none")).lower()
        stim_b = str(burdens_b.get("cns_stimulant", "none")).lower()
        if stim_a in {"moderate", "high"} and stim_b in {"moderate", "high"}:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK" if (stim_a == "high" or stim_b == "high") else "MODERATE_RISK",
                "severity_score": 22,
                "conflict_types": ["PHARMACODYNAMIC", "ORGAN_BURDEN"],
                "title": "Dual Stimulant Sympathetic Hyper-Activation",
                "description": f"Co-administration of {name_a} and {name_b} produces additive catecholaminergic stimulation, escalating tachycardia, insomnia, and hypertensive risk.",
                "affected_targets": ["Adrenergic Receptors", "Adenosine Receptors", "Cardiovascular Tone"],
                "clinical_recommendation": "Avoid simultaneous intake. Separate by 6+ hours or reduce dosages.",
                "evidence_level": "strong",
            }

        sed_a = str(burdens_a.get("sedative", "none")).lower()
        sed_b = str(burdens_b.get("sedative", "none")).lower()
        if sed_a in {"moderate", "high"} and sed_b in {"moderate", "high"}:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "MODERATE_RISK",
                "severity_score": 14,
                "conflict_types": ["PHARMACODYNAMIC"],
                "title": "Additive CNS Sedative & Inhibitory Synergy",
                "description": f"Both {name_a} and {name_b} elevate central GABAergic or inhibitory tone, causing excessive daytime somnolence and psychomotor slowing.",
                "affected_targets": ["GABA_A Receptors", "HPA Axis"],
                "clinical_recommendation": "Restrict administration strictly to evening or pre-bedtime schedules.",
                "evidence_level": "moderate",
            }

        # 6. Downstream Pharmacodynamic & Biomarker Cascade Collisions
        # 6a. Hyperkalemia & Dual RAAS / Aldosterone Blockade
        is_k_a, class_k_a = _is_potassium_sparing_or_raas(comp_a)
        is_k_b, class_k_b = _is_potassium_sparing_or_raas(comp_b)
        if is_k_a and is_k_b:
            labs_data = (profile.get("labs", {}) or {}) if profile else {}
            potassium = labs_data.get("potassium_meq_l") if labs_data.get("potassium_meq_l") is not None else 4.2
            egfr = labs_data.get("egfr") if labs_data.get("egfr") is not None else 90.0
            is_contraindicated = (potassium is not None and potassium >= 4.8) or (egfr is not None and egfr < 60.0)
            severity = "SEVERE_CONTRAINDICATION" if is_contraindicated else "HIGH_RISK"
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": severity,
                "severity_score": 45 if is_contraindicated else 30,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE", "ELECTROLYTE_DISRUPTION"],
                "title": f"Dual RAAS & Aldosterone Blockade: Severe Hyperkalemia Risk ({class_k_a} + {class_k_b})",
                "description": (
                    f"Co-administration of {name_a} ({class_k_a}) and {name_b} ({class_k_b}) exerts additive suppression on renal "
                    f"potassium excretion in the distal nephron and collecting ducts. This dual blockade significantly increases "
                    f"the risk of dangerous hyperkalemia (K+ > 5.5 mEq/L), cardiac conduction slowing, bradycardia, and fatal arrhythmias."
                ),
                "affected_targets": [class_k_a, class_k_b, "Renal Distal Potassium Excretion", "Cardiac Membrane Potential"],
                "clinical_recommendation": (
                    "Avoid dual RAAS/Aldosterone blockade without mandatory weekly serum potassium (K+) and renal (eGFR/Creatinine) "
                    "monitoring. Strictly avoid potassium supplements, potassium-sparing diuretics, and potassium-rich salt substitutes."
                ),
                "evidence_level": "strong",
            }

        # 6b. Profound Vasodilatory Shock & Severe Hypotension
        is_pde5_a, is_pde5_b = _is_pde5_inhibitor(comp_a), _is_pde5_inhibitor(comp_b)
        is_nitrate_a, is_nitrate_b = _is_nitrate_donor(comp_a), _is_nitrate_donor(comp_b)
        is_alpha_a, is_alpha_b = _is_alpha1_blocker(comp_a), _is_alpha1_blocker(comp_b)

        if (is_pde5_a and is_nitrate_b) or (is_pde5_b and is_nitrate_a):
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "SEVERE_CONTRAINDICATION",
                "severity_score": 75,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": "Severe Vasodilatory Shock & Fatal Hypotension (PDE5 Inhibitor + Nitrate)",
                "description": (
                    f"Combining {name_a} and {name_b} causes synergistic accumulation of cyclic GMP (cGMP) in vascular smooth muscle, "
                    f"triggering profound, refractory systemic vasodilation, critical coronary hypoperfusion, and fatal cardiovascular collapse."
                ),
                "affected_targets": ["cGMP Signaling Pathway", "Phosphodiesterase 5A", "Vascular Endothelial Tone"],
                "clinical_recommendation": "Strict contraindication. Do not co-administer nitrates with PDE5 inhibitors within 24-48 hours.",
                "evidence_level": "strong",
            }

        if (is_pde5_a and is_alpha_b) or (is_pde5_b and is_alpha_a):
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 25,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": "Additive Vasodilation & Symptomatic Orthostatic Hypotension (PDE5i + Alpha-1 Blocker)",
                "description": (
                    f"Co-administration of {name_a} and {name_b} produces additive arteriolar and venular vasodilation, "
                    f"predisposing to acute orthostatic dizziness, syncope, and compensatory reflex tachycardia."
                ),
                "affected_targets": ["Alpha-1 Adrenergic Receptors", "Phosphodiesterase 5A", "Systemic Vascular Resistance"],
                "clinical_recommendation": "Separate dosing times by at least 4-6 hours and initiate at lowest therapeutic dosages with BP monitoring.",
                "evidence_level": "strong",
            }

        # 6c. Additive Negative Inotropy/Chronotropy & Heart Block (Beta-Blocker + Non-DHP CCB / Digoxin)
        is_bb_a, is_bb_b = _is_beta_blocker(comp_a), _is_beta_blocker(comp_b)
        is_nondhp_a, is_nondhp_b = _is_non_dhp_ccb_or_digoxin(comp_a), _is_non_dhp_ccb_or_digoxin(comp_b)

        if (is_bb_a and is_nondhp_b) or (is_bb_b and is_nondhp_a):
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 30,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": "Additive Negative Inotropic/Chronotropic AV Nodal Conduction Block",
                "description": (
                    f"Concomitant use of {name_a} and {name_b} synergistically depresses SA and AV nodal electrical conduction, "
                    f"substantially increasing the risk of profound sinus bradycardia, complete heart block, and worsening heart failure."
                ),
                "affected_targets": ["Beta-1 Adrenergic Receptors", "L-Type Calcium Channels (Cav1.2)", "Cardiac Conduction System"],
                "clinical_recommendation": "Avoid concurrent combination or monitor resting heart rate, ECG PR-interval, and blood pressure closely.",
                "evidence_level": "strong",
            }

        # 6d. Glycemic Interplay & Hypoglycemia Cascades
        is_hypo_a, class_hypo_a, tier_hypo_a = _is_potent_hypoglycemic(comp_a)
        is_hypo_b, class_hypo_b, tier_hypo_b = _is_potent_hypoglycemic(comp_b)

        # Case 1: Dual Potent Secretagogues / Incretins
        if is_hypo_a and is_hypo_b:
            is_both_secretagogues = (tier_hypo_a == "HIGH_POTENCY_SECRETAGOGUE" and tier_hypo_b == "HIGH_POTENCY_SECRETAGOGUE")
            has_secretagogue = (tier_hypo_a == "HIGH_POTENCY_SECRETAGOGUE" or tier_hypo_b == "HIGH_POTENCY_SECRETAGOGUE")

            if has_secretagogue:
                return {
                    "source_key": key_a,
                    "source_name": name_a,
                    "target_key": key_b,
                    "target_name": name_b,
                    "is_self": False,
                    "severity": "SEVERE_CONTRAINDICATION" if is_both_secretagogues else "HIGH_RISK",
                    "severity_score": 40 if is_both_secretagogues else 25,
                    "risk_tier": "CRITICAL" if is_both_secretagogues else "HIGH",
                    "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                    "title": f"Synergistic Severe Hypoglycemia Risk ({name_a} + {name_b})",
                    "description": f"Concurrent administration of {name_a} ({class_hypo_a}) and {name_b} ({class_hypo_b}) compounds glucose disposal and suppresses hepatic gluconeogenesis, risking acute neuroglycopenic collapse.",
                    "affected_targets": ["Insulin Receptor", "KATP Channels", "Hepatic Glucose Output"],
                    "clinical_recommendation": "Frequent blood glucose self-monitoring and proactive dose reduction of secretagogues/insulin. Keep emergency glucagon / fast carbohydrates accessible.",
                    "evidence_level": "strong",
                }
            else:
                return {
                    "source_key": key_a,
                    "source_name": name_a,
                    "target_key": key_b,
                    "target_name": name_b,
                    "is_self": False,
                    "severity": "MODERATE_RISK",
                    "severity_score": 10,
                    "risk_tier": "MODERATE",
                    "conflict_types": ["PHARMACODYNAMIC"],
                    "title": f"Additive Non-Hypoglycemic Glycemic Optimization ({name_a} + {name_b})",
                    "description": f"Concomitant use of {name_a} and {name_b} provides additive insulin sensitization and glucose excretion with low intrinsic risk of severe hypoglycemia.",
                    "affected_targets": ["AMPK", "SGLT2 / GLP-1 Pathways"],
                    "clinical_recommendation": "Routine fasting blood glucose and HbA1c monitoring. Maintain adequate hydration.",
                    "evidence_level": "moderate",
                }

        # Case 2: Potent Secretagogue + Beta-Blocker (Hypoglycemia Masking)
        if (is_hypo_a and tier_hypo_a == "HIGH_POTENCY_SECRETAGOGUE" and is_bb_b) or (is_hypo_b and tier_hypo_b == "HIGH_POTENCY_SECRETAGOGUE" and is_bb_a):
            hypo_name = name_a if is_hypo_a else name_b
            bb_name = name_b if is_hypo_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 24,
                "risk_tier": "HIGH",
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": f"Hypoglycemia Warning Masking Cascade ({hypo_name} + {bb_name})",
                "description": f"{bb_name} (Beta-Blocker) blunts classic sympathoadrenal warning symptoms (tremors, palpitations, diaphoresis) of {hypo_name}-induced hypoglycemia.",
                "affected_targets": ["Beta-2 Adrenergic Receptors", "Hepatic Glycogenolysis"],
                "clinical_recommendation": "Use cardioselective beta-blockers where possible and rely on non-adrenergic symptoms (hunger, sweating, dizziness) or continuous glucose monitors.",
                "evidence_level": "strong",
            }

        # Case 3: Androgen + Growth Hormone (TRT + HGH) Hormonal Metabolic Synergy
        if (tier_hypo_a == "METABOLIC_MODULATOR" and tier_hypo_b == "METABOLIC_MODULATOR") and (
            ("Androgen" in class_hypo_a and "Growth Hormone" in class_hypo_b) or ("Growth Hormone" in class_hypo_a and "Androgen" in class_hypo_b)
        ):
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "SYNERGISTIC",
                "severity_score": 0,
                "risk_tier": "LOW",
                "conflict_types": ["METABOLIC_SYNERGY"],
                "title": f"Dual Somatotropic & Anabolic Axis Synergy ({name_a} + {name_b})",
                "description": f"Co-administration of {name_a} and {name_b} exerts complementary tissue-remodeling, lipolytic, and protein-synthetic effects. At therapeutic replacement doses, net glycemic impact is minimal and balanced by peripheral insulin sensitization vs mild hepatic counter-regulation.",
                "affected_targets": ["Androgen Receptor", "Growth Hormone Receptor (GHR)", "IGF-1 Axis"],
                "clinical_recommendation": "Monitor baseline and annual fasting glucose, HbA1c, hematocrit, and lipid panel. At supraphysiologic doses, monitor for insulin resistance.",
                "evidence_level": "strong",
            }

        # Case 4: ARB / ACEi + Beta-Blocker (Complementary Hemodynamic & Cardioprotective Synergy)
        is_raas_a = is_k_a and ("ARB" in class_k_a or "ACE Inhibitor" in class_k_a)
        is_raas_b = is_k_b and ("ARB" in class_k_b or "ACE Inhibitor" in class_k_b)
        if (is_raas_a and is_bb_b) or (is_raas_b and is_bb_a):
            raas_name = name_a if is_raas_a else name_b
            bb_name = name_b if is_raas_a else name_a
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "SYNERGISTIC",
                "severity_score": 0,
                "risk_tier": "LOW",
                "conflict_types": ["HEMODYNAMIC_SYNERGY"],
                "title": f"Complementary RAAS & Beta-Adrenergic Antihypertensive Synergy ({raas_name} + {bb_name})",
                "description": f"Co-administration of {raas_name} (reducing systemic vascular resistance / afterload) and {bb_name} (suppressing sympathetic chronotropy and renin release) represents a standard guideline-directed regimen with complementary cardioprotective profiles.",
                "affected_targets": ["Angiotensin AT1 / ACE Pathways", "Beta-1 Adrenergic Receptor", "Systemic Blood Pressure"],
                "clinical_recommendation": "Standard clinical combination. Routinely monitor resting blood pressure and heart rate during initial titration.",
                "evidence_level": "strong",
            }

        # 6e. Additive Anticholinergic Toxicity & Delirium
        is_anti_a = _is_anticholinergic_agent(comp_a)
        is_anti_b = _is_anticholinergic_agent(comp_b)
        if is_anti_a and is_anti_b:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 26,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": "Additive Central & Peripheral Anticholinergic Toxicity",
                "description": (
                    f"Co-administration of {name_a} and {name_b} creates compounded muscarinic receptor antagonism, "
                    f"elevating the risk of central confusion, memory impairment, delirium, acute urinary retention, and blurred vision."
                ),
                "affected_targets": ["Muscarinic Acetylcholine Receptors (M1-M5)", "Parasympathetic Tone"],
                "clinical_recommendation": "Avoid multi-agent anticholinergic stacking, especially in older adults or cognitive optimization protocols.",
                "evidence_level": "strong",
            }

        # 6f. Additive Direct Nephrotoxicity
        is_nephro_a = _is_direct_nephrotoxic(comp_a)
        is_nephro_b = _is_direct_nephrotoxic(comp_b)
        if is_nephro_a and is_nephro_b:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 28,
                "conflict_types": ["PHARMACODYNAMIC", "DOWNSTREAM_CASCADE"],
                "title": "Synergistic Renal Tubular & Glomerular Nephrotoxicity",
                "description": (
                    f"Combination of direct nephrotoxic agents ({name_a} and {name_b}) creates additive renal tubular "
                    f"shear stress and interstitial inflammation, accelerating renal functional decline."
                ),
                "affected_targets": ["Renal Proximal Tubules", "Glomerular Filtration Barrier"],
                "clinical_recommendation": "Monitor baseline serum creatinine, BUN, and eGFR. Maintain aggressive hydration.",
                "evidence_level": "strong",
            }

        # 6g. Additive Immunomodulatory & Opportunistic Infection Hazard
        is_immuno_a, cls_a = _is_immunosuppressive_agent(comp_a)
        is_immuno_b, cls_b = _is_immunosuppressive_agent(comp_b)
        if is_immuno_a and is_immuno_b:
            return {
                "source_key": key_a,
                "source_name": name_a,
                "target_key": key_b,
                "target_name": name_b,
                "is_self": False,
                "severity": "HIGH_RISK",
                "severity_score": 26,
                "conflict_types": ["PHARMACODYNAMIC", "IMMUNOMODULATORY_COLLISION", "DOWNSTREAM_CASCADE"],
                "title": "Compounded Immunosuppression & Opportunistic Infection Hazard",
                "description": (
                    f"Co-administration of two potent immunomodulatory agents ({name_a} [{cls_a}] and {name_b} [{cls_b}]) "
                    f"induces profound additive immune suppression, substantially elevating the risk of opportunistic infections "
                    f"(fungal, mycobacterial, viral reactivation e.g., HSV/VZV/CMV) and cytopenias."
                ),
                "affected_targets": ["Immune Surveillance", "Lymphocyte Proliferation / Signaling Cascade"],
                "clinical_recommendation": (
                    "Avoid dual biologic or unprotocolized immunosuppressive stacking. If clinically necessary, "
                    "maintain strict infectious disease vigilance, baseline latent TB screening, and routine complete blood count monitoring."
                ),
                "evidence_level": "strong",
            }

        return {
            "source_key": key_a,
            "source_name": name_a,
            "target_key": key_b,
            "target_name": name_b,
            "is_self": False,
            "severity": "NEUTRAL",
            "severity_score": 0,
            "conflict_types": [],
            "title": "Compatible Pharmacology",
            "description": f"No adverse pharmacodynamic antagonism or significant CYP/transporter collisions identified between {name_a} and {name_b}.",
            "affected_targets": [],
            "clinical_recommendation": "Compatible for concurrent use within standard therapeutic dose ranges.",
            "evidence_level": "moderate",
        }

    def _evaluate_multi_compound_syndromes(
        self,
        compounds: List[Dict[str, Any]],
        labs: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Identifies multi-compound systemic toxicity syndromes across 2+ agents."""
        syndromes: List[Dict[str, Any]] = []
        labs_dict = labs or {}

        all_text = " ".join([
            f"{c.get('name', '')} {c.get('mechanism', '')} {c.get('drug_class', '')} {c.get('categories', '')}"
            for c in compounds
        ]).lower()

        # 1. Hyperkalemia & Potassium Retention Cascade
        k_agents = []
        for c in compounds:
            is_k, class_k = _is_potassium_sparing_or_raas(c)
            if is_k:
                k_agents.append(f"{c.get('name')} ({class_k})")

        if len(k_agents) >= 2:
            potassium = labs_dict.get("potassium_meq_l") if labs_dict.get("potassium_meq_l") is not None else 4.2
            egfr = labs_dict.get("egfr") if labs_dict.get("egfr") is not None else 90.0
            is_severe = len(k_agents) >= 3 or (potassium is not None and potassium >= 4.8) or (egfr is not None and egfr < 60.0)
            syndromes.append({
                "syndrome": "Hyperkalemia & Potassium Retention Cascade",
                "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                "severity_score": 50 if is_severe else 30,
                "title": "Multi-Agent Renin-Angiotensin / Potassium Accumulation",
                "description": (
                    f"Stack contains multiple agents that promote renal potassium retention ({', '.join(k_agents)}). "
                    f"This dual/triple suppression of renal aldosterone-mediated potassium excretion dramatically elevates "
                    f"hyperkalemia risk, predisposing to dangerous cardiac conduction abnormalities."
                ),
                "clinical_recommendation": (
                    "Obtain baseline serum potassium (K+) and eGFR/Creatinine. Eliminate redundant potassium-retaining agents "
                    "and avoid potassium-containing supplements or salt substitutes."
                ),
            })

        # 2. Serotonin Syndrome Classifier
        serotonergic_agents = []
        for c in compounds:
            is_sero, s_class = _is_serotonergic_agent(c)
            if is_sero:
                serotonergic_agents.append(f"{c.get('name')} ({s_class})")

        if len(serotonergic_agents) >= 2:
            syndromes.append({
                "syndrome": "Serotonin Syndrome Risk",
                "severity": "SEVERE_CONTRAINDICATION" if len(serotonergic_agents) >= 3 else "HIGH_RISK",
                "severity_score": 65 if len(serotonergic_agents) >= 3 else 35,
                "title": "Serotonergic Hyper-Activation / Serotonin Toxicity",
                "description": f"Stack contains multiple serotonergic agents ({', '.join(serotonergic_agents)}), predisposing to hyperthermia, tremor, clonus, and autonomic instability.",
                "clinical_recommendation": "Avoid concurrent multi-agent serotonergic stacking. Discontinue redundant 5-HT elevating agents.",
            })

        # 3. QTc Prolongation & Torsades de Pointes
        qtc_prolonging = []
        for c in compounds:
            is_qtc, q_class = _is_qtc_prolonging_agent(c)
            if is_qtc:
                qtc_prolonging.append(f"{c.get('name')} ({q_class})")

        qtc_val = labs_dict.get("qtc_ms") if labs_dict.get("qtc_ms") is not None else 410
        k_val = labs_dict.get("potassium_meq_l") if labs_dict.get("potassium_meq_l") is not None else 4.2
        if len(qtc_prolonging) >= 2 or (len(qtc_prolonging) >= 1 and ((qtc_val is not None and qtc_val > 450) or (k_val is not None and k_val < 3.6))):
            syndromes.append({
                "syndrome": "QTc Prolongation / Torsades de Pointes",
                "severity": "HIGH_RISK",
                "severity_score": 40,
                "title": "Additive Cardiac hERG (IKr) Channel Blockade",
                "description": f"Concurrent use of QTc-prolonging agents ({', '.join(qtc_prolonging)}) delays ventricular repolarization, escalating risk of ventricular arrhythmias.",
                "clinical_recommendation": "Obtain baseline 12-lead ECG and maintain serum potassium >4.0 mEq/L and magnesium >2.0 mg/dL.",
            })

        # 4. Renal 'Triple Whammy'
        has_raas = any(_is_potassium_sparing_or_raas(c)[0] for c in compounds)
        has_nsaid = any(any(t in _get_compound_ontology_tags(c) for t in ["nsaid", "non-steroidal anti-inflammatory", "m01a", "m01ae", "m01ab", "cyclooxygenase inhibitor", "cox inhibitor"]) for c in compounds)
        has_diuretic = any("diuretic" in _get_compound_ontology_tags(c) or "c03" in _get_compound_ontology_tags(c) for c in compounds)

        if has_raas and has_nsaid and has_diuretic:
            syndromes.append({
                "syndrome": "Renal Triple Whammy",
                "severity": "SEVERE_CONTRAINDICATION",
                "severity_score": 75,
                "title": "Renal 'Triple Whammy' Acute Kidney Injury Cascade",
                "description": "Combination of RAAS blockade (efferent arteriole vasodilation) + NSAID (afferent arteriole constriction) + Diuretic (volume depletion) severely compromises GFR, precipitating acute renal failure.",
                "clinical_recommendation": "Avoid NSAID co-administration with ACEi/ARB and Diuretic. Use paracetamol/acetaminophen for analgesia.",
            })

        # 5. Multi-Agent Hemorrhage / Bleeding Cascade
        bleeding_agents = []
        for c in compounds:
            is_b, b_class = _is_antithrombotic_or_anticoagulant(c)
            if is_b:
                bleeding_agents.append(f"{c.get('name')} ({b_class})")

        if len(bleeding_agents) >= 2:
            syndromes.append({
                "syndrome": "Additive Hemorrhagic Risk",
                "severity": "HIGH_RISK",
                "severity_score": 25,
                "title": "Synergistic Coagulation & Platelet Inhibition",
                "description": f"Multiple antiplatelet/anticoagulant agents ({', '.join(bleeding_agents)}) exponentially amplify mucosal and internal bleeding risk.",
                "clinical_recommendation": "Add gastroprotection (PPI) if clinically indicated and monitor complete blood count / signs of bleeding.",
            })

        # 6. Profound Vasodilatory Hypotension & Reflex Tachycardia Syndrome
        vaso_agents = []
        for c in compounds:
            if _is_pde5_inhibitor(c) or _is_nitrate_donor(c) or _is_alpha1_blocker(c):
                vaso_agents.append(c.get("name"))

        if len(vaso_agents) >= 2:
            syndromes.append({
                "syndrome": "Profound Vasodilatory Hypotension Syndrome",
                "severity": "HIGH_RISK",
                "severity_score": 30,
                "title": "Additive Vascular Smooth Muscle Relaxation & Severe Hypotension",
                "description": f"Stack contains multiple vasodilatory agents ({', '.join(vaso_agents)}), predisposing to acute orthostatic syncope, dizziness, and reflex tachycardia.",
                "clinical_recommendation": "Avoid concurrent multi-vasodilator stacking. Separate administration times and monitor standing BP.",
            })

        # 7. Additive Bradycardia & AV Conduction Block Syndrome
        brady_agents = []
        for c in compounds:
            if _is_beta_blocker(c) or _is_non_dhp_ccb_or_digoxin(c):
                brady_agents.append(c.get("name"))

        if len(brady_agents) >= 2:
            syndromes.append({
                "syndrome": "Additive Bradycardia & AV Conduction Block",
                "severity": "HIGH_RISK",
                "severity_score": 32,
                "title": "Synergistic Negative Chronotropic / Inotropic Conduction Slowing",
                "description": f"Stack combines multiple AV nodal depressants ({', '.join(brady_agents)}), compounding bradycardia risk and predisposing to high-grade AV block.",
                "clinical_recommendation": "Obtain baseline resting ECG and monitor daily resting heart rate and blood pressure.",
            })

        # 8. Additive Central Anticholinergic Cognitive Burden Syndrome
        ach_agents = [c.get("name") for c in compounds if _is_anticholinergic_agent(c)]
        if len(ach_agents) >= 2:
            syndromes.append({
                "syndrome": "High Anticholinergic Cognitive Burden",
                "severity": "HIGH_RISK",
                "severity_score": 28,
                "title": "Additive Antimuscarinic Neurotoxicity & Delirium Risk",
                "description": f"Stack combines multiple anticholinergic agents ({', '.join(ach_agents)}), exceeding safe Anticholinergic Cognitive Burden (ACB) thresholds.",
                "clinical_recommendation": "Substitute anticholinergic agents with non-antimuscarinic alternatives.",
            })

        # 9. Additive CNS & Respiratory Depression Syndrome
        cns_agents = []
        for c in compounds:
            is_cns, c_class = _is_cns_sedative_or_opioid(c)
            if is_cns:
                cns_agents.append(f"{c.get('name')} ({c_class})")
        if len(cns_agents) >= 2:
            has_opioid = any("Opioid" in a for a in cns_agents)
            has_benzo_gaba = any("Benzodiazepine" in a or "Z-Drug" in a or "Barbiturate" in a for a in cns_agents)
            is_critical = has_opioid and has_benzo_gaba
            syndromes.append({
                "syndrome": "Central Nervous System & Respiratory Depression",
                "severity": "SEVERE_CONTRAINDICATION" if is_critical else "HIGH_RISK",
                "severity_score": 50 if is_critical else 30,
                "title": "Compounded GABAergic & Opioidergic Respiratory Depression",
                "description": f"Stack contains multiple CNS depressants ({', '.join(cns_agents)}), risking catastrophic hypoventilation, hypercapnia, and sedation.",
                "clinical_recommendation": "Avoid concurrent opioid + sedative stacking. Provide take-home naloxone if clinically mandated.",
            })

        # 10. Synergistic Hypoglycemia Classifier
        high_potency_hypo = []
        moderate_hypo = []
        for c in compounds:
            is_h, h_class, h_tier = _is_potent_hypoglycemic(c)
            if is_h:
                if h_tier == "HIGH_POTENCY_SECRETAGOGUE":
                    high_potency_hypo.append(f"{c.get('name')} ({h_class})")
                else:
                    moderate_hypo.append(f"{c.get('name')} ({h_class})")

        if len(high_potency_hypo) >= 2 or (len(high_potency_hypo) >= 1 and len(moderate_hypo) >= 1):
            all_hypo_agents = high_potency_hypo + moderate_hypo
            is_severe = len(high_potency_hypo) >= 2
            syndromes.append({
                "syndrome": "Synergistic Hypoglycemia Crisis",
                "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                "severity_score": 40 if is_severe else 24,
                "risk_tier": "CRITICAL" if is_severe else "HIGH",
                "title": "Dual Insulin / Incretin / Secretagogue Hypoglycemia Crisis",
                "description": f"Concurrent potent glucose-lowering agents ({', '.join(all_hypo_agents)}) synergistically lower serum glucose.",
                "clinical_recommendation": "Frequent blood glucose self-monitoring and proactive dose reduction of secretagogues/insulin.",
            })

        # 11. Synergistic Sympathomimetic & Adrenergic Cardiovascular Toxicity
        symp_agents = []
        for c in compounds:
            is_b, b_class = _is_beta_agonist(c)
            is_a2, a2_class = _is_alpha2_antagonist(c)
            is_ade, ade_class = _is_adenosine_antagonist_or_pde_inhibitor(c)
            is_s, s_class = _is_sympathomimetic_stimulant(c)
            if is_b:
                symp_agents.append(f"{c.get('name')} ({b_class})")
            elif is_a2:
                symp_agents.append(f"{c.get('name')} ({a2_class})")
            elif is_ade:
                symp_agents.append(f"{c.get('name')} ({ade_class})")
            elif is_s:
                symp_agents.append(f"{c.get('name')} ({s_class})")

        if len(symp_agents) >= 2:
            hr_val = labs_dict.get("heart_rate") if labs_dict.get("heart_rate") is not None else 72.0
            bp_val = labs_dict.get("blood_pressure") if labs_dict.get("blood_pressure") is not None else 120.0
            is_critical = len(symp_agents) >= 3 or (hr_val is not None and hr_val >= 85.0) or (bp_val is not None and bp_val >= 135.0)
            syndromes.append({
                "syndrome": "Sympathomimetic Cardiovascular Toxicity Risk",
                "severity": "SEVERE_CONTRAINDICATION" if is_critical else "HIGH_RISK",
                "severity_score": 50 if is_critical else 32,
                "title": "Multi-Agent Sympathomimetic & Adrenergic Cardiovascular Overload",
                "description": (
                    f"Stack combines multiple sympathomimetic, adrenergic agonist, or xanthine stimulant agents ({', '.join(symp_agents)}). "
                    f"This multi-pathway sympathetic hyper-stimulation compounds intracellular cAMP accumulation, positive chronotropy, "
                    f"and arterial vasoconstriction, exponentially increasing resting tachycardia, hypertensive crisis, and arrhythmia risk."
                ),
                "clinical_recommendation": (
                    "Avoid multi-stimulant / beta-agonist stacking. Monitor resting heart rate, blood pressure, and ECG. "
                    "Ensure adequate hydration and electrolyte balance (potassium and magnesium)."
                ),
            })

        # 12. Hypoestrogenemia & HPG Axis Shutdown without Testosterone Base
        def _is_effective_testosterone_base(c: Dict[str, Any]) -> bool:
            c_name = str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
            if "hcg" in c_name:
                return True
            is_test = "testosterone" in c_name and not any(w in c_name for w in [
                "trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol",
                "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd", "ostarine", "s-4", "yk-11"
            ])
            if not is_test:
                return False
            # Check route of administration
            c_route = str(c.get("route") or c.get("route_of_administration") or "").lower().strip()
            # If explicit oral route without 17a-alkylation, oral testosterone undergoes ~97% first-pass clearance
            if c_route in ["oral", "po", "swallow"]:
                eff_mg = float(c.get("effective_daily_dose_mg") or c.get("dose_mg") or c.get("dose") or 0.0)
                return (eff_mg * 0.03) >= 10.0
            # Parenteral / transdermal or default unstated route is bioavailable
            return True

        has_bioidentical_test = any(_is_effective_testosterone_base(c) for c in compounds)
        non_test_androgens = []
        for c in compounds:
            c_name = str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
            d_class = str(c.get("drug_class") or "").lower()
            is_androgen = "androgen" in d_class or "anabolic" in d_class or "sarm" in d_class or any(w in c_name for w in ["drostanolone", "masteron", "primobolan", "methenolone", "oxandrolone", "anavar", "stanozolol", "winstrol", "trenbolone", "superdrol", "rad140", "lgd4033", "ostarine"])
            is_test = "testosterone" in c_name and not any(w in c_name for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd"])
            if is_androgen and not is_test:
                non_test_androgens.append(c.get("name") or c.get("key"))

        if non_test_androgens and not has_bioidentical_test:
            syndromes.append({
                "syndrome": "Hypoestrogenemia & HPG Axis Shutdown",
                "severity": "HIGH_RISK",
                "severity_score": 45,
                "risk_tier": "HIGH",
                "title": "Crashed Testosterone & Estrogen (AAS/SARM without Testosterone Base)",
                "description": (
                    f"Stack contains non-testosterone androgen/SARM compounds ({', '.join(non_test_androgens)}) without a bioidentical testosterone base or aromatizable estrogen source. "
                    f"Exogenous AR stimulation halts hypothalamic GnRH and pituitary LH/FSH secretion, shutting down endogenous testicular steroidogenesis. "
                    f"Because non-aromatizing androgens cannot be converted into 17β-estradiol by aromatase (CYP19A1), circulating estradiol crashes (<10 pg/mL), "
                    f"triggering severe arthralgia, loss of endothelial and cardiovascular protection, severe atherogenic lipid worsening (profound HDL suppression), and mood/neurocognitive collapse."
                ),
                "clinical_recommendation": (
                    "Incorporate a bioidentical testosterone base (e.g., TRT 100-150 mg/week) or hCG to restore circulating testosterone substrate "
                    "and maintain neuroprotective and joint-protective physiological estradiol levels (20-40 pg/mL)."
                ),
            })

        # 13. Progestogenic Hyperprolactinemia Risk (19-nor without Dopamine Agonist)
        nor19_agents = [
            c.get("name") or c.get("key")
            for c in compounds
            if is_19nor_steroid(c)
        ]

        has_d2_agonist = any(
            any(w in str(c.get("name", "")).lower() or w in str(c.get("mechanism", "")).lower()
                for w in ["cabergoline", "pramipexole", "bromocriptine", "dopamine agonist"])
            for c in compounds
        )
        if nor19_agents and not has_d2_agonist:
            syndromes.append({
                "syndrome": "Progestogenic Hyperprolactinemia Risk",
                "severity": "HIGH_RISK",
                "severity_score": 30,
                "risk_tier": "HIGH",
                "title": "19-Nor Progestogenic Prolactin Surge",
                "description": (
                    f"Stack contains 19-nor progestogenic androgens ({', '.join(nor19_agents)}) without a dopamine D2 receptor agonist. "
                    f"19-Nor compounds transactivate progesterone receptors in the anterior pituitary gland, stimulating lactotroph prolactin secretion and predisposing to hyperprolactinemia, galactorrhea, and prolonged HPG axis suppression."
                ),
                "clinical_recommendation": (
                    "Monitor serum prolactin. Consider co-administration of a dopamine D2 agonist (Cabergoline 0.25-0.5 mg/week or Pramipexole) if prolactin exceeds 18 ng/mL."
                ),
            })

        # 14. Iatrogenic Thyroid Suppression
        thyroid_agents = [
            c.get("name") or c.get("key")
            for c in compounds
            if any(w in str(c.get("name", "")).lower() or w in str(c.get("mechanism", "")).lower() or w in str(c.get("drug_class", "")).lower()
                   for w in ["liothyronine", "levothyroxine", "thyroid hormone", "triiodothyronine", "t3", "t4"])
            and not any(w in str(c.get("name", "")).lower() for w in ["ashwagandha", "iodine", "selenium", "tyrosine"])
        ]
        if thyroid_agents:
            syndromes.append({
                "syndrome": "Thyroid Axis Shutdown Risk",
                "severity": "MODERATE_RISK",
                "severity_score": 20,
                "risk_tier": "MODERATE",
                "title": "Exogenous Thyroid Hormone TSH Suppression",
                "description": f"Exogenous thyroid hormone administration ({', '.join(thyroid_agents)}) suppresses pituitary TSH secretion and shuts down endogenous thyroid follicular synthesis.",
                "clinical_recommendation": "Monitor baseline and on-cycle TSH, Free T3, and Free T4. Taper gradually upon cessation to avoid rebound fatigue.",
            })

        return syndromes

    def _evaluate_biomarker_vector_convergence(
        self,
        compounds: List[Dict[str, Any]],
        labs: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Dynamically calculates multi-compound biomarker vector convergence across the biological cascade graph.
        Zero hardcoded drug names: Computes net vector sums across all active compounds.
        """
        biomarker_alerts: List[Dict[str, Any]] = []
        if len(compounds) < 2:
            return biomarker_alerts

        try:
            from app.services.graph_service import build_selected_compound_graph

            stack_keys = [str(c.get("key") or c.get("name") or "") for c in compounds if c]
            graph = build_selected_compound_graph(stack_keys)
            start_nodes = [n for n in graph.graph.nodes() if graph.graph.nodes[n].get("node_type") == "compound"]

            if not start_nodes:
                return biomarker_alerts

            # Measure directional contributions per origin compound
            compound_biomarker_vectors: Dict[str, Dict[str, float]] = {}
            for start in start_nodes:
                c_res = graph.propagate_cascade([start])
                for b in c_res.get("biomarker_shifts", []):
                    b_id = b.get("biomarker_id", "")
                    shift = float(b.get("net_shift", 0.0))
                    if abs(shift) > 0.05:
                        if b_id not in compound_biomarker_vectors:
                            compound_biomarker_vectors[b_id] = {}
                        compound_biomarker_vectors[b_id][start] = shift

            for b_id, contribs in compound_biomarker_vectors.items():
                b_data = graph.graph.nodes.get(b_id, {})
                label = b_data.get("label", b_id)

                # 1. Potassium retention convergence (at least 2 compounds pushing K+ up)
                k_ups = {c: v for c, v in contribs.items() if v >= 0.2}
                if "potassium" in b_id.lower() and len(k_ups) >= 2:
                    net_k = sum(k_ups.values())
                    potassium_val = labs.get("potassium_meq_l") if labs.get("potassium_meq_l") is not None else 4.2
                    egfr_val = labs.get("egfr") if labs.get("egfr") is not None else 90.0
                    is_severe = net_k >= 0.8 or potassium_val >= 4.8 or egfr_val < 60.0
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in k_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Hyperkalemia Multiplier",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                        "severity_score": 45 if is_severe else 28,
                        "title": f"Dynamic Cascade Convergence: Potassium Retention ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation identified multiple compounds ({', '.join(agent_names)}) "
                            f"converging to increase {label} (net vector: +{round(net_k, 2)}). "
                            f"This compounded renal retention increases arrhythmia and cardiac conduction vulnerability."
                        ),
                        "clinical_recommendation": "Mandatory serum potassium and renal panel monitoring. Restrict dietary potassium boluses.",
                    })

                # 2. QTc interval prolongation convergence (at least 2 compounds pushing QTc up)
                qtc_ups = {c: v for c, v in contribs.items() if v >= 0.25}
                if "qtc" in b_id.lower() and len(qtc_ups) >= 2:
                    net_qtc = sum(qtc_ups.values())
                    qtc_val = labs.get("qtc_ms") if labs.get("qtc_ms") is not None else 420.0
                    is_severe = net_qtc >= 0.8 or qtc_val >= 480.0
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in qtc_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: QTc Prolongation & TdP Risk",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                        "severity_score": 45 if is_severe else 30,
                        "title": f"Dynamic Cascade Convergence: Delayed Ventricular Repolarization ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"inhibiting delayed rectifier potassium channels and prolonging {label} (net vector: +{round(net_qtc, 2)}). "
                            f"This compounded electrophysiologic delay significantly elevates the risk of Torsades de Pointes and fatal arrhythmias."
                        ),
                        "clinical_recommendation": "Obtain baseline 12-lead ECG. Monitor serum electrolytes (K+ >= 4.0, Mg2+ >= 2.0) and avoid multi-hERG inhibitor stacking.",
                    })

                # 3. Blood Pressure reduction convergence (at least 2 compounds pushing BP down)
                bp_downs = {c: v for c, v in contribs.items() if v <= -0.3}
                if "blood_pressure" in b_id.lower() and len(bp_downs) >= 2:
                    net_bp = sum(bp_downs.values())
                    bp_val = labs.get("blood_pressure") if labs.get("blood_pressure") is not None else 120.0
                    is_high_risk = bp_val < 100.0 or len(bp_downs) >= 3
                    has_synergy = any(
                        "HEMODYNAMIC_SYNERGY" in s.get("conflict_types", []) or "Antihypertensive" in s.get("title", "")
                        for s in synergistic_benefits
                    )
                    if is_high_risk or not has_synergy:
                        agent_names = [graph.graph.nodes[c].get("label", c) for c in bp_downs.keys()]
                        biomarker_alerts.append({
                            "syndrome": "Biomarker Cascade: Additive Antihypertensive Response",
                            "severity": "HIGH_RISK" if is_high_risk else "MODERATE_RISK",
                            "severity_score": 24 if is_high_risk else 6,
                            "risk_tier": "HIGH" if is_high_risk else "MODERATE",
                            "title": f"Dynamic Cascade Convergence: Additive Blood Pressure Reduction ({', '.join(agent_names)})",
                            "description": (
                                f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                                f"cooperatively lowering {label} (net vector: {round(net_bp, 2)}). "
                                + ("Caution for symptomatic orthostatic hypotension given low baseline blood pressure." if is_high_risk else "Standard additive therapeutic blood pressure reduction.")
                            ),
                            "clinical_recommendation": "Routinely monitor sitting and standing blood pressure during dose titration.",
                        })

                # 3b. Blood Pressure elevation convergence (at least 2 compounds pushing BP up)
                bp_ups = {c: v for c, v in contribs.items() if v >= 0.25}
                if "blood_pressure" in b_id.lower() and len(bp_ups) >= 2:
                    net_bp_up = sum(bp_ups.values())
                    bp_val = labs.get("blood_pressure") if labs.get("blood_pressure") is not None else 120.0
                    is_high_bp = net_bp_up >= 0.8 or bp_val >= 135.0
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in bp_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Additive Hypertensive Strain",
                        "severity": "HIGH_RISK",
                        "severity_score": 30 if is_high_bp else 20,
                        "risk_tier": "HIGH",
                        "title": f"Dynamic Cascade Convergence: Hypertensive Vascular Strain ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"converging to elevate {label} (net vector: +{round(net_bp_up, 2)}). "
                            f"Compounded sympathomimetic vasoconstriction and inotropic pressure elevate arterial wall shear stress and afterload."
                        ),
                        "clinical_recommendation": "Monitor resting blood pressure morning and evening. Avoid concurrent stimulant / vasoconstrictor stacking.",
                    })

                # 4. Heart Rate / Chronotropy reduction convergence (at least 2 compounds pushing HR down)
                hr_downs = {c: v for c, v in contribs.items() if v <= -0.3}
                if "heart_rate" in b_id.lower() and len(hr_downs) >= 2:
                    net_hr = sum(hr_downs.values())
                    is_high_risk = len(hr_downs) >= 3
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in hr_downs.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Additive Bradycardia",
                        "severity": "HIGH_RISK" if is_high_risk else "MODERATE_RISK",
                        "severity_score": 24 if is_high_risk else 6,
                        "risk_tier": "HIGH" if is_high_risk else "MODERATE",
                        "title": f"Dynamic Cascade Convergence: Negative Chronotropic Slowing ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple agents ({', '.join(agent_names)}) "
                            f"depressing {label} (net vector: {round(net_hr, 2)}), compounding bradycardia and AV block risk."
                        ),
                        "clinical_recommendation": "Check baseline resting ECG and monitor daily resting heart rate.",
                    })

                # 4b. Heart Rate / Chronotropy elevation convergence (at least 2 compounds pushing HR up)
                hr_ups = {c: v for c, v in contribs.items() if v >= 0.25}
                if "heart_rate" in b_id.lower() and len(hr_ups) >= 2:
                    net_hr_up = sum(hr_ups.values())
                    hr_val = labs.get("heart_rate") if labs.get("heart_rate") is not None else 72.0
                    is_severe_hr = net_hr_up >= 0.8 or hr_val >= 85.0
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in hr_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Tachycardia & Inotropic Overdrive",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe_hr else "HIGH_RISK",
                        "severity_score": 42 if is_severe_hr else 28,
                        "risk_tier": "CRITICAL" if is_severe_hr else "HIGH",
                        "title": f"Dynamic Cascade Convergence: Resting Tachycardia & Inotropic Strain ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"converging to increase {label} (net vector: +{round(net_hr_up, 2)}). "
                            f"Dual sympathetic inotropic and chronotropic stimulation accelerates myocardial oxygen consumption and elevates tachyarrhythmia risk."
                        ),
                        "clinical_recommendation": "Obtain baseline resting ECG and monitor daily resting heart rate. Avoid multi-agent adrenergic / chronotropic stacking.",
                    })

                # 5. Bleeding / Hemostasis impairment convergence (at least 2 compounds increasing bleeding risk)
                bleed_ups = {c: v for c, v in contribs.items() if v >= 0.25}
                if ("bleed" in b_id.lower() or "clot" in b_id.lower()) and len(bleed_ups) >= 2:
                    net_bleed = sum(bleed_ups.values())
                    platelets_val = labs.get("platelets_k_ul") if labs.get("platelets_k_ul") is not None else 250.0
                    is_severe = net_bleed >= 0.8 or platelets_val < 100.0
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in bleed_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Compounded Hemorrhagic Risk",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                        "severity_score": 40 if is_severe else 28,
                        "title": f"Dynamic Cascade Convergence: Impaired Hemostasis & Bleeding ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation identified multiple compounds ({', '.join(agent_names)}) "
                            f"converging to elevate {label} (net vector: +{round(net_bleed, 2)}). "
                            f"Dual antiplatelet or anticoagulant cascades significantly elevate major gastrointestinal and intracranial bleeding."
                        ),
                        "clinical_recommendation": "Prescribe gastroprotection (PPI) when indicated, avoid unmonitored NSAID/anticoagulant co-use, and monitor CBC/hemoglobin.",
                    })

                # 6. Serotonergic hyperactivity convergence (at least 2 compounds increasing synaptic serotonin)
                sero_ups = {c: v for c, v in contribs.items() if v >= 0.3}
                if "serotonin" in b_id.lower() and len(sero_ups) >= 2:
                    net_sero = sum(sero_ups.values())
                    is_severe = net_sero >= 0.8
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in sero_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Serotonin Toxicity Risk",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                        "severity_score": 45 if is_severe else 30,
                        "title": f"Dynamic Cascade Convergence: Synaptic Serotonergic Overload ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation identified multiple agents ({', '.join(agent_names)}) "
                            f"compounding {label} (net vector: +{round(net_sero, 2)}). "
                            f"Additive central 5-HT accumulation risks severe serotonin toxicity (Hunter Criteria: hyperreflexia, clonus, autonomic instability, hyperthermia)."
                        ),
                        "clinical_recommendation": "Avoid concurrent multi-serotonergic combinations (e.g. MAOI + SSRI/SNRI/TCA). Allow mandatory 2-5 week washout.",
                    })

                # 7. Anticholinergic cognitive burden convergence (at least 2 compounds suppressing muscarinic tone)
                ach_downs = {c: v for c, v in contribs.items() if v <= -0.3}
                if "acetylcholine" in b_id.lower() and len(ach_downs) >= 2:
                    net_ach = sum(ach_downs.values())
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in ach_downs.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Anticholinergic Delirium Risk",
                        "severity": "HIGH_RISK",
                        "severity_score": 28,
                        "title": f"Dynamic Cascade Convergence: Central Cholinergic Blockade ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"suppressing {label} (net vector: {round(net_ach, 2)}). "
                            f"Additive muscarinic blockade drives cumulative cognitive impairment, acute delirium, memory fragmentation, and severe xerostomia/urinary retention."
                        ),
                        "clinical_recommendation": "Minimize total Anticholinergic Cognitive Burden (ACB score). Substitute with non-anticholinergic alternatives.",
                    })

                # 8. Hypoglycemia crisis convergence (at least 2 compounds lowering blood glucose)
                glu_downs = {c: v for c, v in contribs.items() if v <= -0.3}
                if "glucose" in b_id.lower() and len(glu_downs) >= 2:
                    net_glu = sum(glu_downs.values())
                    glucose_val = labs.get("fasting_glucose_mg_dl") if labs.get("fasting_glucose_mg_dl") is not None else 95.0
                    is_severe = abs(net_glu) >= 0.8 or glucose_val < 70.0
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in glu_downs.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Synergistic Hypoglycemia",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                        "severity_score": 40 if is_severe else 26,
                        "title": f"Dynamic Cascade Convergence: Additive Glycemic Drop ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"synergistically depressing {label} (net vector: {round(net_glu, 2)}). "
                            f"Dual secretagogue/incretin/insulin actions precipitate neuroglycopenic hypoglycemia, confusion, and seizure risk."
                        ),
                        "clinical_recommendation": "Frequent blood glucose self-monitoring and proactive dose reduction of secretagogues/insulin.",
                    })

                # 9. Renal hemodynamic strain convergence (at least 2 compounds reducing eGFR)
                egfr_downs = {c: v for c, v in contribs.items() if v <= -0.25}
                if "egfr" in b_id.lower() and len(egfr_downs) >= 2:
                    net_egfr = sum(egfr_downs.values())
                    egfr_val = labs.get("egfr") if labs.get("egfr") is not None else 90.0
                    is_severe = abs(net_egfr) >= 0.7 or egfr_val < 60.0
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in egfr_downs.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Renal Hemodynamic Strain",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                        "severity_score": 42 if is_severe else 28,
                        "title": f"Dynamic Cascade Convergence: Glomerular Hemodynamic Compromise ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"compromising {label} (net vector: {round(net_egfr, 2)}). "
                            f"Combining afferent vasoconstrictors with efferent vasodilators or hypovolemic diuretics threatens acute tubular necrosis."
                        ),
                        "clinical_recommendation": "Avoid Triple Whammy stacking. Ensure euvolemia and monitor serum creatinine and BUN weekly.",
                    })

                # 10. Central nervous system & respiratory depression convergence
                cns_downs = {c: v for c, v in contribs.items() if v <= -0.3}
                if ("cns_arousal" in b_id.lower() or "respiratory" in b_id.lower()) and len(cns_downs) >= 2:
                    net_cns = sum(cns_downs.values())
                    is_severe = abs(net_cns) >= 0.8
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in cns_downs.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Central & Respiratory Depression",
                        "severity": "SEVERE_CONTRAINDICATION" if is_severe else "HIGH_RISK",
                        "severity_score": 50 if is_severe else 32,
                        "title": f"Dynamic Cascade Convergence: CNS & Respiratory Depression ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple central depressants ({', '.join(agent_names)}) "
                            f"depressing {label} (net vector: {round(net_cns, 2)}). "
                            f"Compounded GABAergic and opioidergic depression risks catastrophic hypoventilation, hypercapnia, and respiratory arrest."
                        ),
                        "clinical_recommendation": "Strictly avoid concurrent opioid + benzodiazepine/sedative stacking without continuous SpO2/respiratory monitoring.",
                    })

                # 11. Hepatic transaminitis strain convergence
                alt_ups = {c: v for c, v in contribs.items() if v >= 0.4}
                if "alt" in b_id.lower() and len(alt_ups) >= 2:
                    net_alt = sum(alt_ups.values())
                    alt_val = labs.get("alt_u_l") if labs.get("alt_u_l") is not None else 25.0
                    has_hep_warning = any(
                        c.get("organ_burdens", {}).get("hepatic") in {"high", "severe"}
                        or "hepatotox" in str(c.get("warnings", "")).lower()
                        or "17-alpha" in str(c.get("mechanism", "")).lower()
                        for c in compounds
                    )
                    has_cyp_conflict = any("CYP450" in c.get("conflict_types", []) for c in receptor_conflicts + cyp_conflicts)
                    is_severe = (net_alt >= 1.5) or (alt_val > 50.0 and net_alt >= 0.8) or (has_hep_warning and net_alt >= 0.8) or (has_cyp_conflict and net_alt >= 0.8)
                    if is_severe:
                        agent_names = [graph.graph.nodes[c].get("label", c) for c in alt_ups.keys()]
                        biomarker_alerts.append({
                            "syndrome": "Biomarker Cascade: Hepatic Transaminitis Strain",
                            "severity": "HIGH_RISK",
                            "severity_score": 26,
                            "title": f"Dynamic Cascade Convergence: Additive Hepatocellular Strain ({', '.join(agent_names)})",
                            "description": (
                                f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                                f"elevating {label} (net vector: +{round(net_alt, 2)}). "
                                f"Additive hepatic metabolic and reactive metabolite strain increases transaminitis and DILI vulnerability."
                            ),
                            "clinical_recommendation": "Monitor baseline and 4-week liver function panels (ALT, AST, Total Bilirubin). Consider hepatoprotective co-factors.",
                        })

                # 12. Oxidative Stress & Redox Strain convergence
                ox_downs = {c: v for c, v in contribs.items() if v <= -0.25}
                if "gsh_redox_ratio" in b_id.lower() and len(ox_downs) >= 2:
                    net_ox = sum(ox_downs.values())
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in ox_downs.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Systemic Oxidative & Mitochondrial Strain",
                        "severity": "HIGH_RISK",
                        "severity_score": 24,
                        "title": f"Dynamic Cascade Convergence: Cellular Redox Depletion ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"depleting {label} (net vector: {round(net_ox, 2)}). "
                            f"Concurrent mitochondrial uncoupling, catecholaminergic autoxidation, and Phase I reactive species generation deplete reduced glutathione reserves."
                        ),
                        "clinical_recommendation": "Consider antioxidant support (N-Acetylcysteine, Alpha-Lipoic Acid, CoQ10) and monitor inflammatory markers.",
                    })

                # 13. QTc Prolongation & Cardiac Electrophysiology Strain convergence
                qtc_ups = {c: v for c, v in contribs.items() if v >= 0.25}
                if "qtc" in b_id.lower() and len(qtc_ups) >= 2:
                    net_qtc = sum(qtc_ups.values())
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in qtc_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Additive QTc Prolongation",
                        "severity": "SEVERE_CONTRAINDICATION" if net_qtc >= 0.7 else "HIGH_RISK",
                        "severity_score": 45 if net_qtc >= 0.7 else 30,
                        "title": f"Dynamic Cascade Convergence: Additive QTc Interval Prolongation ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation identified multiple compounds ({', '.join(agent_names)}) "
                            f"lengthening {label} (net vector: +{round(net_qtc, 2)}). "
                            f"Dual hERG channel blockade prolongs ventricular repolarization, escalating Torsades de Pointes and ventricular arrhythmia risk."
                        ),
                        "clinical_recommendation": "Obtain baseline 12-lead ECG, monitor QTc intervals, and maintain serum potassium and magnesium at upper-normal targets.",
                    })

                # 14. Basal Metabolic Rate Acceleration Convergence
                bmr_ups = {c: v for c, v in contribs.items() if v >= 0.2}
                if any(k in b_id.lower() for k in ["metabolic_rate", "bmr"]) and len(bmr_ups) >= 2:
                    net_bmr = sum(bmr_ups.values())
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in bmr_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Hypermetabolic Acceleration",
                        "severity": "HIGH_RISK" if net_bmr >= 0.8 else "MODERATE_RISK",
                        "severity_score": 28 if net_bmr >= 0.8 else 18,
                        "title": f"Dynamic Cascade Convergence: Hypermetabolic Energy Expenditure ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"converging to accelerate {label} (net vector: +{round(net_bmr, 2)}). "
                            f"Dual activation of thyroid and sympathomimetic beta-adrenergic cascades markedly increases cellular thermogenesis, resting heart rate, and caloric turnover."
                        ),
                        "clinical_recommendation": "Monitor resting heart rate, core body temperature, and caloric intake. Avoid stacking potent thermogenics with thyroid agonists.",
                    })

                # 15. Vagal Tone / HRV Suppression Convergence
                hrv_downs = {c: v for c, v in contribs.items() if v <= -0.2}
                if "hrv" in b_id.lower() and len(hrv_downs) >= 2:
                    net_hrv = sum(hrv_downs.values())
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in hrv_downs.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Autonomic Vagal Tone Withdrawal",
                        "severity": "HIGH_RISK" if net_hrv <= -0.6 else "MODERATE_RISK",
                        "severity_score": 26 if net_hrv <= -0.6 else 16,
                        "title": f"Dynamic Cascade Convergence: Vagal HRV Withdrawal ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation detected multiple compounds ({', '.join(agent_names)}) "
                            f"depressing {label} (net vector: {round(net_hrv, 2)}). "
                            f"Compound sympathomimetic stimulation suppresses parasympathetic vagal activity, accelerating autonomic allostatic load."
                        ),
                        "clinical_recommendation": "Integrate vagal-supportive adaptogens (L-Theanine, Ashwagandha, Magnesium) and limit late-day CNS stimulant dosing.",
                    })

                # 16. Neurotrophic & Synaptic Plasticity Convergence
                bdnf_ups = {c: v for c, v in contribs.items() if v >= 0.2}
                if "bdnf" in b_id.lower() and len(bdnf_ups) >= 2:
                    net_bdnf = sum(bdnf_ups.values())
                    agent_names = [graph.graph.nodes[c].get("label", c) for c in bdnf_ups.keys()]
                    biomarker_alerts.append({
                        "syndrome": "Biomarker Cascade: Neurotrophic Synergy",
                        "severity": "SYNERGISTIC_BENEFIT",
                        "severity_score": 0,
                        "title": f"Dynamic Cascade Convergence: Neurotrophic BDNF Synergy ({', '.join(agent_names)})",
                        "description": (
                            f"Biological cascade simulation identified multiple compounds ({', '.join(agent_names)}) "
                            f"converging to elevate {label} (net vector: +{round(net_bdnf, 2)}). "
                            f"Co-activation of TrkB and neurotrophin cascades supports synaptic plasticity and neuronal resilience."
                        ),
                        "clinical_recommendation": "Maintain adequate sleep and choline availability to support synaptic remodeling.",
                    })
        except Exception:
            pass

        return biomarker_alerts
