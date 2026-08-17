from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


def _normalize_name(name: str | None) -> str:
    return str(name or "").strip().lower().replace("-", "_").replace(" ", "_")


def _has_ontology_match(context: str, term: str) -> bool:
    """
    Checks if a pharmacological term or code matches in the ontology context.
    Short acronyms (<= 4 characters, e.g. 'arb', 'ace', 'maoi', 'ssri', 'doac', 'tca', 'nsaid', 'katp', 'dora')
    require word boundaries to avoid false substring collisions (e.g. 'narbivolol' or 'carbon' matching 'arb').
    """
    clean_term = term.strip().lower()
    if not clean_term:
        return False

    if len(clean_term) <= 4 and clean_term.isalpha():
        return bool(re.search(rf"\b{re.escape(clean_term)}\b", context))

    return clean_term in context


def _has_any_ontology_match(context: str, terms: List[str]) -> bool:
    return any(_has_ontology_match(context, term) for term in terms)


def _get_compound_pharmacology_tags(comp: Dict[str, Any]) -> str:
    """Aggregates all formal structural pharmacology tags (EPC, PE, MOA, ATC, targets, drug_class) without indication pollution."""
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
    """Aggregates all ontology tags including pharmacology, names, and synonyms (excluding free-text disease indications)."""
    pharm_text = _get_compound_pharmacology_tags(comp)
    parts = [
        pharm_text,
        str(comp.get("name", "")),
        str(comp.get("key", "")),
        str(comp.get("canonical_name", "")),
        " ".join(str(s) for s in comp.get("synonyms", [])),
    ]
    return " ".join(parts).lower()


def _is_potassium_sparing_or_raas(comp: Dict[str, Any]) -> tuple[bool, str]:
    """Identify if a compound retains potassium or acts as a RAAS / aldosterone antagonist."""
    all_context = _get_compound_ontology_tags(comp)

    if _has_any_ontology_match(all_context, ["sartan", "angiotensin 2 receptor blocker", "angiotensin ii receptor antagonist", "arb", "angiotensin receptor", "at1 receptor", "agtr1", "type-1 angiotensin", "c09ca", "c09c"]):
        return True, "Angiotensin II Receptor Blocker (ARB)"
    if _has_any_ontology_match(all_context, ["pril", "angiotensin-converting enzyme inhibitor", "ace inhibitor", "angiotensin-converting enzyme", "c09aa", "c09a"]):
        return True, "ACE Inhibitor"
    if _has_any_ontology_match(all_context, ["aldosterone antagonist", "mineralocorticoid receptor antagonist", "mineralocorticoid antagonist", "renone", "spironolactone", "eplerenone", "finerenone", "nr3c2", "c03da", "c03d"]):
        return True, "Aldosterone / Mineralocorticoid Receptor Antagonist"
    if _has_any_ontology_match(all_context, ["potassium-sparing", "potassium sparing", "triamterene", "amiloride", "enac inhibitor", "c03db"]):
        return True, "Potassium-Sparing Diuretic"
    if _has_any_ontology_match(all_context, ["potassium chloride", "potassium citrate", "potassium gluconate", "potassium supplement", "a12ba"]):
        return True, "Potassium Supplement"
    if _has_any_ontology_match(all_context, ["calcineurin inhibitor", "tacrolimus", "cyclosporine", "l04ad"]):
        return True, "Calcineurin Inhibitor"
    if _has_any_ontology_match(all_context, ["trimethoprim", "bactrim", "cotrimoxazole", "j01ea"]):
        return True, "Trimethoprim"
    if _has_any_ontology_match(all_context, ["direct renin inhibitor", "renin inhibitor", "aliskiren", "c09xa"]):
        return True, "Direct Renin Inhibitor"
    if _has_any_ontology_match(all_context, ["decreased renal potassium excretion"]):
        return True, "Potassium-Retaining Pharmacologic Agent"

    return False, ""


def _is_pde5_inhibitor(comp: Dict[str, Any]) -> bool:
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["phosphodiesterase 5 inhibitor", "phosphodiesterase type 5 inhibitor", "pde5", "pde-5", "g04be", "tadalafil", "sildenafil", "vardenafil", "avanafil"])


def _is_nitrate_donor(comp: Dict[str, Any]) -> bool:
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["organic nitrate", "nitrate vasodilator", "nitroglycerin", "isosorbide", "nitroprusside", "c01da", "nitric oxide donor"])


def _is_alpha1_blocker(comp: Dict[str, Any]) -> bool:
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["alpha-1 blocker", "alpha 1 blocker", "alpha-adrenoreceptor antagonist", "prazosin", "doxazosin", "terazosin", "tamsulosin", "alfuzosin", "c02ca", "g04ca", "adra1a"])


def _is_beta_blocker(comp: Dict[str, Any]) -> bool:
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["beta-adrenergic blocker", "beta blocker", "beta-blocker", "c07aa", "c07ab", "c07ag", "c07", "olol", "propranolol", "metoprolol", "atenolol", "bisoprolol", "carvedilol", "nebivolol", "adrb1", "adrb2"])


def _is_non_dhp_ccb_or_digoxin(comp: Dict[str, Any]) -> bool:
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["non-dihydropyridine", "calcium channel blocker (phenylalkylamine)", "calcium channel blocker (benzothiazepine)", "verapamil", "diltiazem", "digoxin", "c08db", "c08da", "c01aa", "cacna1c"])


def _is_potent_hypoglycemic(comp: Dict[str, Any]) -> tuple[bool, str, str]:
    """
    Returns (is_hypoglycemic, class_name, risk_potency_tier).
    - HIGH_POTENCY_SECRETAGOGUE: Exogenous insulins (A10A), sulfonylureas (A10BB), meglitinides (A10BX). High intrinsic risk of acute neuroglycopenia.
    - MODERATE_SENSITIZER: GLP-1 (A10BJ), SGLT2 (A10BK), DPP-4 (A10BH), Biguanides (A10BA), Berberine, TZDs (A10BG). Glucose-dependent action.
    - METABOLIC_MODULATOR: Androgens (G03B), Growth Hormone (H01A). Long-term nutrient partitioning and metabolic modulation.
    """
    pharm = _get_compound_pharmacology_tags(comp)

    # 1. High-Potency Hypoglycemic Secretagogues & Exogenous Insulins
    if _has_any_ontology_match(pharm, ["insulin agonist", "a10a", "insulin human", "insulin glargine", "insulin lispro", "insulin aspart", "insulin degludec", "insulin detemir"]):
        return True, "Exogenous Insulin Agonist", "HIGH_POTENCY_SECRETAGOGUE"
    if _has_any_ontology_match(pharm, ["sulfonylurea", "a10bb", "glimepiride", "glipizide", "glyburide", "gliclazide", "katp", "abcc8", "kcnj11"]):
        return True, "Sulfonylurea (KATP Blocker)", "HIGH_POTENCY_SECRETAGOGUE"
    if _has_any_ontology_match(pharm, ["meglitinide", "a10bx", "repaglinide", "nateglinide"]):
        return True, "Meglitinide Secretagogue", "HIGH_POTENCY_SECRETAGOGUE"

    # 2. Incretins, SGLT2, & Sensitizers
    if _has_any_ontology_match(pharm, ["glucagon-like peptide", "glp-1 receptor agonist", "glp1r", "a10bj", "semaglutide", "tirzepatide", "liraglutide", "dulaglutide"]):
        return True, "GLP-1 Receptor Agonist", "MODERATE_SENSITIZER"
    if _has_any_ontology_match(pharm, ["sglt2 inhibitor", "sodium-glucose cotransporter 2 inhibitor", "slc5a2", "a10bk", "empagliflozin", "dapagliflozin", "canagliflozin", "flozin"]):
        return True, "SGLT2 Inhibitor", "MODERATE_SENSITIZER"
    if _has_any_ontology_match(pharm, ["biguanide", "a10ba", "metformin", "berberine", "ampk activator"]):
        return True, "Biguanide / AMPK Activator", "MODERATE_SENSITIZER"
    if _has_any_ontology_match(pharm, ["dipeptidyl peptidase 4 inhibitor", "dpp-4 inhibitor", "a10bh", "sitagliptin", "linagliptin", "saxagliptin"]):
        return True, "DPP-4 Inhibitor", "MODERATE_SENSITIZER"
    if _has_any_ontology_match(pharm, ["thiazolidinedione", "a10bg", "pioglitazone"]):
        return True, "Thiazolidinedione (PPAR-gamma Agonist)", "MODERATE_SENSITIZER"
    if _has_any_ontology_match(pharm, ["decreased blood glucose"]):
        return True, "Glucose-Lowering Agent", "MODERATE_SENSITIZER"

    # 3. Hormonal Metabolic Modulators
    is_androgen = _has_any_ontology_match(pharm, ["androgen", "g03ba", "g03b", "androgen receptor agonist", "ar agonist"])
    is_gh = _has_any_ontology_match(pharm, ["somatropin", "growth hormone receptor agonist", "h01ac", "h01a", "ghr"])
    if is_androgen:
        return False, "Androgen (Mild Peripheral Insulin Sensitizer)", "METABOLIC_MODULATOR"
    if is_gh:
        return False, "Growth Hormone (Hepatic Lipolytic Modulator)", "METABOLIC_MODULATOR"

    return False, "", ""


def _is_anticholinergic_agent(comp: Dict[str, Any]) -> bool:
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["anticholinergic", "antimuscarinic", "muscarinic acetylcholine receptor antagonist", "diphenhydramine", "hydroxyzine", "amitriptyline", "nortriptyline", "oxybutynin", "tolterodine", "cyclobenzaprine", "scopolamine", "r06aa", "g04bd", "n06aa", "chrm1", "chrm2", "chrm3", "chrm4", "chrm5"])


def _is_direct_nephrotoxic(comp: Dict[str, Any]) -> bool:
    all_context = _get_compound_ontology_tags(comp)
    return _has_any_ontology_match(all_context, ["aminoglycoside", "gentamicin", "tobramycin", "amikacin", "vancomycin", "glycopeptide antibiotic", "cisplatin", "amphotericin", "tacrolimus", "cyclosporine", "nsaid", "non-steroidal anti-inflammatory drug", "m01ae", "m01ab", "m01a", "j01gb", "j01xa"])


def _is_qtc_prolonging_agent(comp: Dict[str, Any]) -> tuple[bool, str]:
    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["kcnh2", "herg", "delayed rectifier", "potassium voltage-gated", "antiarrhythmic", "c01b", "c01ba", "c01bb", "c01bc", "c01bd"]):
        return True, "Antiarrhythmic / hERG Channel Modulator"
    if _has_any_ontology_match(all_context, ["delayed cardiac repolarization", "prolonged qtc interval", "prolongation of the qt interval"]):
        return True, "QTc Prolonging Pharmacologic Agent"
    if _has_any_ontology_match(all_context, ["antipsychotic", "phenothiazine", "butyrophenone", "n05a", "haloperidol", "thioridazine", "ziprasidone", "quetiapine"]):
        return True, "Antipsychotic (hERG Affinity)"
    if _has_any_ontology_match(all_context, ["fluoroquinolone", "j01ma", "ciprofloxacin", "levofloxacin", "moxifloxacin"]):
        return True, "Fluoroquinolone (hERG Blocker)"
    if _has_any_ontology_match(all_context, ["macrolide", "j01fa", "erythromycin", "azithromycin", "clarithromycin"]):
        return True, "Macrolide (hERG Blocker)"
    if _has_any_ontology_match(all_context, ["5-ht3 receptor antagonist", "ondansetron", "granisetron", "a04aa"]):
        return True, "5-HT3 Receptor Antagonist"
    return False, ""


def _is_antithrombotic_or_anticoagulant(comp: Dict[str, Any]) -> tuple[bool, str]:
    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["direct oral anticoagulant", "doac", "factor xa inhibitor", "b01af", "apixaban", "rivaroxaban", "edoxaban"]):
        return True, "Factor Xa Inhibitor (DOAC)"
    if _has_any_ontology_match(all_context, ["direct thrombin inhibitor", "b01ae", "dabigatran", "argatroban", "bivalirudin"]):
        return True, "Direct Thrombin Inhibitor"
    if _has_any_ontology_match(all_context, ["vitamin k antagonist", "coumarin", "b01aa", "warfarin"]):
        return True, "Vitamin K Antagonist (Warfarin)"
    if _has_any_ontology_match(all_context, ["heparin", "low molecular weight heparin", "lmwh", "b01ab", "enoxaparin", "fondaparinux"]):
        return True, "Heparin / LMWH"
    if _has_any_ontology_match(all_context, ["platelet aggregation inhibitor", "p2y12", "b01ac", "clopidogrel", "ticagrelor", "prasugrel", "aspirin", "acetylsalicylic acid"]):
        return True, "Platelet Antiaggregant"
    if _has_any_ontology_match(all_context, ["non-steroidal anti-inflammatory drug", "nsaid", "m01a", "m01ae", "ibuprofen", "naproxen", "ketorolac", "indomethacin"]):
        return True, "NSAID (COX-1 Platelet Suppressor)"
    if _has_any_ontology_match(all_context, ["selective serotonin reuptake inhibitor", "ssri", "n06ab"]):
        return True, "SSRI (Platelet Serotonin Depletor)"
    if _has_any_ontology_match(all_context, ["inhibition of blood coagulation", "decreased platelet aggregation"]):
        return True, "Hemostasis-Impairing Agent"
    return False, ""


def _is_serotonergic_agent(comp: Dict[str, Any]) -> tuple[bool, str]:
    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["monoamine oxidase inhibitor", "maoi", "n06af", "n06ag", "phenelzine", "tranylcypromine", "selegiline", "moclobemide", "linezolid", "methylene blue"]):
        return True, "Monoamine Oxidase Inhibitor (MAOI)"
    if _has_any_ontology_match(all_context, ["selective serotonin reuptake inhibitor", "ssri", "n06ab"]):
        return True, "Selective Serotonin Reuptake Inhibitor (SSRI)"
    if _has_any_ontology_match(all_context, ["serotonin-norepinephrine reuptake inhibitor", "snri", "n06ax", "venlafaxine", "duloxetine", "desvenlafaxine"]):
        return True, "Serotonin-Norepinephrine Reuptake Inhibitor (SNRI)"
    if _has_any_ontology_match(all_context, ["tricyclic antidepressant", "tca", "n06aa", "amitriptyline", "clomipramine", "imipramine"]):
        return True, "Tricyclic Antidepressant (TCA)"
    if _has_any_ontology_match(all_context, ["triptan", "5-ht1b/1d agonist", "n02cc", "sumatriptan", "zolmitriptan", "rizatriptan"]):
        return True, "5-HT1 Receptor Agonist (Triptan)"
    if _has_any_ontology_match(all_context, ["tramadol", "meperidine", "methadone", "fentanyl", "dextromethorphan", "st. john's wort", "hypericum", "slc6a4"]):
        return True, "Serotonin-Releasing / Reuptake Modulating Agent"
    return False, ""


def _is_cns_sedative_or_opioid(comp: Dict[str, Any]) -> tuple[bool, str]:
    all_context = _get_compound_ontology_tags(comp)
    if _has_any_ontology_match(all_context, ["opioid receptor agonist", "opioid", "n02a", "morphine", "oxycodone", "fentanyl", "hydromorphone", "buprenorphine", "methadone", "codeine", "oprm1"]):
        return True, "Opioid Agonist"
    if _has_any_ontology_match(all_context, ["benzodiazepine", "n05ba", "n05cd", "diazepam", "alprazolam", "lorazepam", "clonazepam", "midazolam", "gabra1"]):
        return True, "Benzodiazepine (GABA-A PAM)"
    if _has_any_ontology_match(all_context, ["z-drug", "gaba-a receptor positive allosteric modulator", "n05cf", "zolpidem", "zopiclone", "eszopiclone"]):
        return True, "Non-Benzodiazepine Hypnotic (Z-Drug)"
    if _has_any_ontology_match(all_context, ["barbiturate", "n03aa", "phenobarbital"]):
        return True, "Barbiturate"
    if _has_any_ontology_match(all_context, ["dual orexin receptor antagonist", "dora", "n05cm", "suvorexant", "lemborexant"]):
        return True, "Orexin Receptor Antagonist"
    if _has_any_ontology_match(all_context, ["first-generation antihistamine", "h1 inverse agonist", "r06aa", "r06ab", "diphenhydramine", "hydroxyzine", "promethazine", "doxylamine"]):
        return True, "Sedating Antihistamine (H1/Muscarinic Blocker)"
    return False, ""


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
        compounds: List[Dict[str, Any]],
        profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            }

        profile_data = profile or {}
        labs = profile_data.get("labs", {}) or {}

        # Clinical Laboratory & Vital Sign Inputs
        sleep_hours = profile_data.get("sleep_hours") if profile_data.get("sleep_hours") is not None else labs.get("sleep_hours", 7.5)
        blood_pressure = profile_data.get("blood_pressure") or labs.get("blood_pressure") or 120
        heart_rate = labs.get("heart_rate") or profile_data.get("heart_rate") or 72
        qtc_ms = labs.get("qtc_ms") or 410

        # Renal Panel
        egfr = labs.get("egfr") if labs.get("egfr") is not None else 95.0
        creatinine_mg_dl = labs.get("creatinine_mg_dl") if labs.get("creatinine_mg_dl") is not None else 0.95
        bun_mg_dl = labs.get("bun_mg_dl") if labs.get("bun_mg_dl") is not None else 14.0

        # Hepatic Panel
        alt_u_l = labs.get("alt_u_l") if labs.get("alt_u_l") is not None else 25.0
        ast_u_l = labs.get("ast_u_l") if labs.get("ast_u_l") is not None else 22.0
        total_bilirubin = labs.get("total_bilirubin_mg_dl") if labs.get("total_bilirubin_mg_dl") is not None else 0.8
        serum_albumin = labs.get("serum_albumin_g_dl") if labs.get("serum_albumin_g_dl") is not None else 4.5

        # Electrolytes & Hematology
        potassium_meq_l = labs.get("potassium_meq_l") if labs.get("potassium_meq_l") is not None else 4.2
        sodium_meq_l = labs.get("sodium_meq_l") if labs.get("sodium_meq_l") is not None else 140.0
        magnesium_mg_dl = labs.get("magnesium_mg_dl") if labs.get("magnesium_mg_dl") is not None else 2.1
        hematocrit_pct = labs.get("hematocrit_pct") if labs.get("hematocrit_pct") is not None else 45.0
        platelets_k_ul = labs.get("platelets_k_ul") if labs.get("platelets_k_ul") is not None else 250.0

        # Lipids & Glycemia
        ldl_mg_dl = labs.get("ldl_mg_dl") if labs.get("ldl_mg_dl") is not None else 100.0
        hba1c_pct = labs.get("hba1c_pct") if labs.get("hba1c_pct") is not None else 5.2

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

        # Accumulate individual organ burdens
        for comp in compounds:
            burdens = comp.get("organ_burdens", {}) or {}
            for organ, weight in [
                ("hepatic", {"low": 8, "moderate": 18, "high": 35}),
                ("renal", {"low": 6, "moderate": 15, "high": 30}),
                ("cardiovascular", {"low": 8, "moderate": 20, "high": 40}),
                ("cns_stimulant", {"low": 10, "moderate": 22, "high": 45}),
                ("sedative", {"low": 6, "moderate": 16, "high": 32}),
            ]:
                val = str(burdens.get(organ, "none")).lower()
                organ_scores[organ] += weight.get(val, 0)

            # Narrow therapeutic index adds baseline vigilance
            if comp.get("is_narrow_therapeutic_index"):
                total_risk_points += 10.0

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
            syndrome_alerts.append(syn)
            total_risk_points += syn["severity_score"]

        # Dynamic Biomarker Vector Convergence Evaluator (from Knowledge Graph cascade simulation)
        vector_alerts = self._evaluate_biomarker_vector_convergence(compounds, labs)
        for valert in vector_alerts:
            if not any(valert.get("syndrome") == s.get("syndrome") or valert.get("title") == s.get("title") for s in syndrome_alerts):
                syndrome_alerts.append(valert)
                total_risk_points += valert["severity_score"]

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
            total_risk_points += 18.0

        # 2. Renal Impairment & Reduced GFR
        if egfr < 60 or creatinine_mg_dl > 1.3:
            renal_compounds = [c.get("name") for c in compounds if "renal" in str(c.get("clearance_routes", "")).lower() or c.get("organ_burdens", {}).get("renal") in {"moderate", "high"}]
            warning = {
                "biomarker": "eGFR / Renal Function",
                "value": f"eGFR {egfr} mL/min/1.73m², Cr {creatinine_mg_dl} mg/dL",
                "severity": "HIGH_RISK" if egfr < 45 else "MODERATE_RISK",
                "title": "Reduced Glomerular Filtration & Renal Clearance",
                "description": f"Baseline eGFR of {egfr} mL/min impairs clearance of renally eliminated compounds ({', '.join(renal_compounds[:3]) or 'stack entries'}), risking cumulative toxicity.",
                "clinical_recommendation": "Calculate CrCl and adjust dosing according to renal titration guidelines. Monitor serum creatinine and BUN.",
            }
            biomarker_warnings.append(warning)
            total_risk_points += 22.0

        # 3. Potassium & Electrolyte Dysregulation
        if potassium_meq_l > 5.0 and any(c.get("drug_class") and any(dc in c.get("drug_class").lower() for dc in ["arb", "ace inhibitor", "angiotensin", "potassium"]) for c in compounds):
            warning = {
                "biomarker": "Serum Potassium (K+)",
                "value": f"{potassium_meq_l} mEq/L (Hyperkalemia Risk)",
                "severity": "HIGH_RISK",
                "title": "Hyperkalemia Collision with Renin-Angiotensin Blockade",
                "description": f"Serum potassium at {potassium_meq_l} mEq/L with active RAAS inhibitors increases cardiac electrophysiological risk and arrhythmia.",
                "clinical_recommendation": "Avoid potassium supplementation, restrict dietary potassium boluses, and monitor ECG and renal function.",
            }
            biomarker_warnings.append(warning)
            total_risk_points += 20.0

        # 4. Sympathetic Hypertensive Strain
        if blood_pressure > 130 and (organ_scores["cns_stimulant"] > 15 or organ_scores["cardiovascular"] > 25):
            warning = {
                "biomarker": "Blood Pressure",
                "value": f"{blood_pressure} mmHg",
                "severity": "HIGH_RISK" if blood_pressure > 140 else "MODERATE_RISK",
                "title": "Sympathetic Hypertensive Overload",
                "description": f"Elevated baseline BP ({blood_pressure} mmHg) combined with active stimulant or cardiovascular load accelerates arterial wall shear stress and tachycardia risk.",
                "clinical_recommendation": "Offset stimulant timing, introduce vasodilators / L-Theanine, and monitor twice-daily resting BP.",
            }
            biomarker_warnings.append(warning)
            total_risk_points += 18.0

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
            total_risk_points += 12.0

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
            total_risk_points += 8.0

        # Cumulative Score (0-100 bounded)
        cumulative_score = min(100, round(total_risk_points + (organ_scores["cardiovascular"] * 0.15) + (organ_scores["cns_stimulant"] * 0.15)))

        has_severe = any(s.get("severity") == "SEVERE_CONTRAINDICATION" for s in syndrome_alerts) or any(
            any(c.get("severity") == "SEVERE_CONTRAINDICATION" for c in row if not c.get("is_self")) for row in matrix
        )

        if has_severe or cumulative_score > 75:
            risk_band = "SEVERE"
        elif cumulative_score > 45 or any(c.get("severity") == "HIGH_RISK" for c in receptor_conflicts + cyp_conflicts + transporter_conflicts + phase2_conflicts):
            risk_band = "ELEVATED"
        elif cumulative_score > 25:
            risk_band = "MODERATE"
        elif cumulative_score > 10:
            risk_band = "LOW"
        else:
            risk_band = "MINIMAL"

        conflict_count = (
            len(cyp_conflicts)
            + len(transporter_conflicts)
            + len(phase2_conflicts)
            + len([c for c in receptor_conflicts if c.get("severity") in {"HIGH_RISK", "SEVERE_CONTRAINDICATION", "MODERATE_RISK"}])
            + len([s for s in syndrome_alerts if s.get("severity") in {"HIGH_RISK", "SEVERE_CONTRAINDICATION"}])
        )
        synergy_count = len(synergistic_benefits)

        if conflict_count == 0 and synergy_count > 0:
            summary = f"Optimal stack synergy detected with {synergy_count} positive pharmacological pairing(s) and clean metabolic compatibility."
        elif conflict_count > 0:
            summary = f"Detected {conflict_count} interaction conflict(s) across metabolism, transporters, and organ pathways with a {risk_band.lower()} risk profile ({cumulative_score}/100)."
        else:
            summary = f"Clean pharmacological compatibility with standard clinical monitoring recommended. Overall risk is {risk_band.lower()} ({cumulative_score}/100)."

        return {
            "matrix": matrix,
            "compounds": [
                {
                    "key": _normalize_name(c.get("key") or c.get("name")),
                    "name": c.get("name") or c.get("key"),
                    "drug_class": c.get("drug_class"),
                    "risk_band": c.get("risk_band", "low"),
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
            },
            "conflict_count": conflict_count,
            "synergy_count": synergy_count,
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
        for syn in comp_a.get("synergies", []):
            if isinstance(syn, dict) and _normalize_name(syn.get("partner")) in {key_b, name_b.lower()}:
                syn_item = syn
                break
        if not syn_item:
            for syn in comp_b.get("synergies", []):
                if isinstance(syn, dict) and _normalize_name(syn.get("partner")) in {key_a, name_a.lower()}:
                    syn_item = syn
                    break

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

        # 2. CYP450 Collisions
        cyp_a = comp_a.get("cyp_enzymes", {}) or {}
        cyp_b = comp_b.get("cyp_enzymes", {}) or {}
        sub_a = set(cyp_a.get("substrates", []))
        inh_a = set(cyp_a.get("inhibitors", []))
        sub_b = set(cyp_b.get("substrates", []))
        inh_b = set(cyp_b.get("inhibitors", []))

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
        t_sub_a = set(trans_a.get("substrates", []))
        t_inh_a = set(trans_a.get("inhibitors", []))
        t_sub_b = set(trans_b.get("substrates", []))
        t_inh_b = set(trans_b.get("inhibitors", []))

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
                "severity": "HIGH_RISK" if "P-gp" in trans_overlap or "OATP1B1" in trans_overlap else "MODERATE_RISK",
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
        p2_sub_a = set(p2_a.get("substrates", []))
        p2_inh_a = set(p2_a.get("inhibitors", []))
        p2_sub_b = set(p2_b.get("substrates", []))
        p2_inh_b = set(p2_b.get("inhibitors", []))

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
                alt_ups = {c: v for c, v in contribs.items() if v >= 0.2}
                if "alt" in b_id.lower() and len(alt_ups) >= 2:
                    net_alt = sum(alt_ups.values())
                    alt_val = labs.get("alt_u_l") if labs.get("alt_u_l") is not None else 25.0
                    is_severe = net_alt >= 0.6 or alt_val > 50.0
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
        except Exception:
            pass

        return biomarker_alerts
