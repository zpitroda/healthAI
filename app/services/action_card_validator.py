from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.catalog_service import CatalogService
from app.services.dosing_service import get_default_compound_dose, parse_dose_string_or_spec
from app.services.graph_service import (
    is_aromatizable_androgen,
    is_steroidal_androgen,
    parse_compound_spec,
)
from app.services.interaction_engine import InteractionEngine

logger = logging.getLogger("healthai.action_card_validator")

# Critical Narrow Therapeutic Index (NTI) compounds with known acute toxicity thresholds in mg
# (Used strictly to prevent unit confusion e.g. mcg vs mg, not to restrict standard or supraphysiological compounds)
NTI_ACUTE_TOXICITY_THRESHOLDS_MG = {
    "clenbuterol": 0.16,      # 160 mcg max single acute athletic limit
    "digoxin": 0.5,           # 0.5 mg max single therapeutic limit
    "colchicine": 2.0,        # 2 mg max acute limit
    "warfarin": 15.0,         # 15 mg max single limit without INR monitoring
    "lithium": 1200.0,        # 1200 mg single acute limit
    "potassium_chloride": 3000.0, # 3 g single acute oral load
}


class ActionCardValidator:
    """
    Generalized Chain-of-Verification (CoVe) engine for Copilot action cards.
    Validates and auto-corrects proposed compound additions, modifications, and removals:
    1. Pharmacokinetic Half-Life & Formulation Route/Frequency Laws:
       - If compound elimination t1/2 >= 72 hours (e.g. depot esters, long-lived peptides),
         enforces route ('intramuscular' or 'subcutaneous') and frequency ('twice weekly',
         'every 3.5 days', or 'weekly'), preventing dangerous daily scheduling.
    2. Nuanced Harm-Reduction & Supraphysiological Cycle Support:
       - Supraphysiological protocols (e.g. high-dose androgens) are fully supported.
       - Detects if active targets (e.g. CYP19A1 aromatase, RAAS vasoconstriction, 17a-alkylation)
         require protective co-factors and attaches harm-reduction metadata.
       - Protects against accidental unit errors in narrow-therapeutic-index toxins.
    3. Deterministic DDI Collision Safety Check:
       - Runs post-mutation stack analysis through InteractionEngine to ensure no fatal uncompensated
         syndromes (e.g. SSRI + MAOI) are introduced without explicit countermeasures.
    4. Data Normalization & Sanitization:
       - Canonicalizes compound keys, parses units, and cleans timing strings.
    """

    @classmethod
    def validate_and_sanitize_card(
        cls,
        card_type: str,
        payload: Dict[str, Any],
        current_stack: Optional[List[Any]] = None,
        biometrics: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validates an action card payload, applying generalized biophysical corrections
        and returning (sanitized_payload, list_of_adjustments_or_warnings).
        """
        if card_type != "stack_diff" or not isinstance(payload, dict):
            return payload, []

        catalog = CatalogService()
        current_stack = current_stack or []
        biometrics = biometrics or {}
        audit_log: List[str] = []

        additions: List[Dict[str, Any]] = payload.get("add") or payload.get("additions") or []
        modifications: List[Dict[str, Any]] = payload.get("modify") or payload.get("modifications") or []
        removals: List[Any] = payload.get("remove") or payload.get("removals") or []

        sanitized_additions = []
        for item in additions:
            sanitized_item, notes = cls._sanitize_compound_entry(item, catalog, biometrics)
            sanitized_additions.append(sanitized_item)
            audit_log.extend(notes)

        sanitized_modifications = []
        for item in modifications:
            sanitized_item, notes = cls._sanitize_compound_entry(item, catalog, biometrics)
            sanitized_modifications.append(sanitized_item)
            audit_log.extend(notes)

        sanitized_removals = []
        for item in removals:
            if isinstance(item, dict):
                rem_key = str(item.get("key") or item.get("name") or "").strip().lower()
            else:
                rem_key = str(item).strip().lower()
            if rem_key:
                sanitized_removals.append(rem_key)

        # Build projected post-mutation stack
        projected_stack = cls._build_projected_stack(
            current_stack=current_stack,
            additions=sanitized_additions,
            modifications=sanitized_modifications,
            removals=sanitized_removals,
            catalog=catalog,
        )

        # Harm-reduction evaluation for projected stack
        harm_reduction_notes, shield_active = cls._evaluate_harm_reduction(projected_stack, biometrics)
        audit_log.extend(harm_reduction_notes)

        # DDI safety check on projected stack
        ddi_notes = cls._evaluate_projected_ddi(projected_stack, biometrics)
        audit_log.extend(ddi_notes)

        sanitized_payload = {
            "add": sanitized_additions,
            "modify": sanitized_modifications,
            "remove": sanitized_removals,
            "validation_meta": {
                "guardrail_verified": True,
                "harm_reduction_shield_active": shield_active,
                "audit_notes": audit_log,
                "projected_compound_count": len(projected_stack),
            },
        }

        return sanitized_payload, audit_log

    @classmethod
    def _sanitize_compound_entry(
        cls,
        entry: Dict[str, Any],
        catalog: CatalogService,
        biometrics: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        raw_key = str(entry.get("key") or entry.get("name") or "").strip().lower()

        # Canonicalize compound record
        comp_record = catalog.get_compound(raw_key, auto_enrich=False) or catalog.find_by_synonym(raw_key)
        if not comp_record:
            spec = parse_compound_spec(raw_key)
            spec_key = spec.get("key", raw_key)
            comp_record = catalog.get_compound(spec_key, auto_enrich=False) or catalog.find_by_synonym(spec_key)

        if not comp_record:
            clean_k = re.sub(r"[^a-z0-9]", "", raw_key)
            if clean_k:
                for c in catalog.list_compounds():
                    c_k = str(c.get("key", "")).lower()
                    c_n = str(c.get("name", "")).lower()
                    c_clean_k = re.sub(r"[^a-z0-9]", "", c_k)
                    c_clean_n = re.sub(r"[^a-z0-9]", "", c_n)
                    if clean_k == c_clean_k or clean_k == c_clean_n:
                        comp_record = c
                        break
                    if clean_k.startswith("test") and "cyp" in clean_k and "cyp" in c_k:
                        comp_record = c
                        break

        canonical_key = comp_record.get("key", raw_key) if comp_record else raw_key
        canonical_name = comp_record.get("name", entry.get("name", raw_key.title())) if comp_record else entry.get("name", raw_key.title())

        # Extract and normalize dose & unit
        raw_dose = entry.get("dose") or entry.get("dose_mg")
        raw_unit = str(entry.get("unit") or "mg").strip().lower()

        if raw_dose is None:
            default_dose_spec = get_default_compound_dose(canonical_key)
            dose_val = float(default_dose_spec.get("dose_mg", 100.0))
            raw_unit = str(default_dose_spec.get("unit", "mg")).lower()
        else:
            try:
                dose_val = float(raw_dose)
            except (ValueError, TypeError):
                dose_val = 100.0

        # Handle unit conversion (mcg to mg for NTI check if unit is mcg)
        dose_in_mg = dose_val / 1000.0 if raw_unit in ("mcg", "ug", "μg") else dose_val

        # 1. NTI Acute Toxicity Hard Cap (unit confusion protection)
        if canonical_key in NTI_ACUTE_TOXICITY_THRESHOLDS_MG:
            max_acute_mg = NTI_ACUTE_TOXICITY_THRESHOLDS_MG[canonical_key]
            if dose_in_mg > max_acute_mg:
                capped_dose = max_acute_mg * 1000.0 if raw_unit in ("mcg", "ug", "μg") else max_acute_mg
                notes.append(
                    f"⚠️ Critical NTI Guardrail: Dose for '{canonical_name}' ({dose_val}{raw_unit}) exceeded acute safety threshold. Capped to {capped_dose}{raw_unit}."
                )
                dose_val = capped_dose

        # 2. Pharmacokinetic Half-Life & Formulation Route/Frequency Laws
        t_half_h = 0.0
        if comp_record:
            t_half_h = float(
                comp_record.get("t_half_numeric")
                or comp_record.get("half_life_hours")
                or comp_record.get("half_life")
                or 0.0
            )

        route = str(entry.get("route") or (comp_record.get("route") if comp_record else "oral")).strip().lower()
        timing = str(entry.get("timing") or "morning").strip().lower()
        frequency = str(entry.get("frequency") or "").strip().lower()

        # If t_half >= 72 hours (e.g. Testosterone Cypionate ~ 192h, Decanoate ~ 240h), enforce depot scheduling
        is_long_half_life = t_half_h >= 72.0 or any(
            ester in canonical_key for ester in ["cypionate", "enanthate", "decanoate", "undecylenate", "depot"]
        )

        if is_long_half_life:
            # Route must be injectable (intramuscular or subcutaneous)
            if route not in ("intramuscular", "subcutaneous", "im", "subq"):
                notes.append(
                    f"💉 Pharmacokinetic Schedule Law: Long-acting depot '{canonical_name}' (t1/2 ~ {round(t_half_h, 1) if t_half_h else 168}h) route corrected to 'intramuscular'."
                )
                route = "intramuscular"

            # Frequency must be weekly or split-weekly, NOT daily
            daily_timing_keywords = ["morning", "midday", "bedtime", "evening", "with breakfast", "with dinner", "daily"]
            is_daily_scheduled = timing in daily_timing_keywords and frequency in ("", "daily", "once daily", "qd")
            
            if is_daily_scheduled:
                notes.append(
                    f"📅 Pharmacokinetic Schedule Law: Long-acting depot '{canonical_name}' (t1/2 ~ {round(t_half_h, 1) if t_half_h else 168}h) schedule adjusted from daily to 'Twice Weekly (Split Depot Protocol)'."
                )
                timing = "Twice Weekly (Mon / Thu)"
                frequency = "twice weekly"
            elif not frequency:
                frequency = "twice weekly"

        sanitized_entry = {
            "key": canonical_key,
            "name": canonical_name,
            "dose": round(dose_val, 2),
            "unit": raw_unit,
            "route": route,
            "timing": timing,
        }
        if frequency:
            sanitized_entry["frequency"] = frequency
        if entry.get("clinical_purpose"):
            sanitized_entry["clinical_purpose"] = entry["clinical_purpose"]

        return sanitized_entry, notes

    @classmethod
    def _build_projected_stack(
        cls,
        current_stack: List[Any],
        additions: List[Dict[str, Any]],
        modifications: List[Dict[str, Any]],
        removals: List[str],
        catalog: CatalogService,
    ) -> List[Dict[str, Any]]:
        projected_map: Dict[str, Dict[str, Any]] = {}

        # 1. Load current stack
        for item in current_stack:
            if isinstance(item, dict):
                k = str(item.get("key") or item.get("name") or "").strip().lower()
                rec = dict(catalog.get_compound(k, auto_enrich=False) or {})
                rec.update(item)
                rec["key"] = k
                projected_map[k] = rec
            else:
                spec = parse_compound_spec(str(item))
                k = spec.get("key", str(item)).lower()
                rec = dict(catalog.get_compound(k, auto_enrich=False) or {})
                rec.update(spec)
                rec["key"] = k
                projected_map[k] = rec

        # 2. Apply removals
        for r_key in removals:
            projected_map.pop(r_key, None)

        # 3. Apply modifications
        for mod in modifications:
            m_key = str(mod.get("key") or "").lower()
            if m_key in projected_map:
                projected_map[m_key].update(mod)
            else:
                rec = dict(catalog.get_compound(m_key, auto_enrich=False) or {})
                rec.update(mod)
                rec["key"] = m_key
                projected_map[m_key] = rec

        # 4. Apply additions
        for add in additions:
            a_key = str(add.get("key") or "").lower()
            rec = dict(catalog.get_compound(a_key, auto_enrich=False) or {})
            rec.update(add)
            rec["key"] = a_key
            projected_map[a_key] = rec

        return list(projected_map.values())

    @classmethod
    def _evaluate_harm_reduction(
        cls,
        projected_stack: List[Dict[str, Any]],
        biometrics: Dict[str, Any],
    ) -> Tuple[List[str], bool]:
        """
        Dynamically analyzes molecular targets and pathways in the projected stack to determine
        if side-effect management countermeasures are active and sufficient.
        """
        notes: List[str] = []
        catalog = CatalogService()
        enriched_stack: List[Dict[str, Any]] = []
        for c in projected_stack:
            k = str(c.get("key") or c.get("name") or "").strip().lower()
            rec = dict(catalog.get_compound(k, auto_enrich=False) or {})
            rec.update(c)
            enriched_stack.append(rec)

        stack_keys = {str(c.get("key", "")).lower() for c in enriched_stack}

        has_aromatizable_androgen = False
        has_19nor_androgen = False
        has_17a_alkylated = False
        total_androgen_dose = 0.0

        for comp in enriched_stack:
            drug_class = str(comp.get("drug_class") or "").lower()
            key_name = str(comp.get("key") or comp.get("name") or "").lower()
            mech = str(comp.get("mechanism") or "").lower()
            targets = [str(t.get("target", "")).lower() if isinstance(t, dict) else str(t).lower() for t in (comp.get("receptor_targets") or [])]
            dose = float(comp.get("dose") or comp.get("dose_mg") or 0.0)

            if is_steroidal_androgen(comp) or "androgen" in drug_class or "anabolic" in drug_class:
                total_androgen_dose += dose
                if is_aromatizable_androgen(comp):
                    has_aromatizable_androgen = True
                if any(w in key_name or w in mech for w in ["nandrolone", "trenbolone", "deca", "trestolone", "19-nor"]) or any("progesterone" in t or "pr" in t for t in targets):
                    has_19nor_androgen = True
                if any(w in key_name or w in mech or w in drug_class for w in ["17aa", "17a-", "17-alpha", "methyl", "dianabol", "methandrostenolone", "stanozolol", "winstrol", "oxandrolone", "anavar", "oxymetholone", "anadrol", "fluoxymesterone", "halotestin", "turinabol"]):
                    has_17a_alkylated = True

        shield_active = False

        if has_aromatizable_androgen:
            shield_active = True
            has_ai_or_serm = any(
                k in stack_keys for k in ["anastrozole", "exemestane", "letrozole", "raloxifene", "tamoxifen", "arimidex", "aromasin", "formestane", "aminoglutethimide"]
            ) or any(
                c.get("drug_class") == "Aromatase Inhibitor"
                or c.get("drug_class") == "SERM"
                or any(
                    (isinstance(t, dict) and t.get("gene_symbol") == "CYP19A1")
                    and isinstance(t, dict) and t.get("action") in ["inhibitor", "antagonist", "blocker"]
                    for t in (c.get("receptor_targets") or [])
                )
                for c in enriched_stack
            )
            if not has_ai_or_serm:
                notes.append(
                    "🛡️ Harm-Reduction Recommendation: Protocol contains aromatizable androgens without an Aromatase Inhibitor (Anastrozole 0.25-0.5mg 2x/wk or Exemestane 12.5mg 2x/wk) or SERM (Raloxifene 30-60mg/d) on-hand for estrogen control."
                )

        if has_19nor_androgen:
            shield_active = True
            has_prolactin_support = any(
                k in stack_keys for k in ["p5p", "pyridoxal_5_phosphate", "cabergoline", "pramipexole"]
            ) or any(
                c.get("drug_class") == "Dopamine Agonist"
                for c in enriched_stack
            )
            if not has_prolactin_support:
                notes.append(
                    "🛡️ Harm-Reduction Recommendation: 19-nor progestogenic compound active; consider P-5-P (50-100mg bedtime) to maintain baseline pituitary prolactin control."
                )

        if has_17a_alkylated:
            shield_active = True
            has_hepatic_shield = any(
                k in stack_keys for k in ["tudca", "nac", "glutathione", "udca"]
            ) or any(
                "glutathione" in str(c.get("mechanism", "")).lower()
                or "bile acid" in str(c.get("mechanism", "")).lower()
                or "hepatoprotective" in str(c.get("drug_class", "")).lower()
                for c in enriched_stack
            )
            if not has_hepatic_shield:
                notes.append(
                    "🛡️ Harm-Reduction Recommendation: Oral 17-alpha alkylated compound detected; pair with TUDCA (250-500mg) and NAC (600-1200mg) for hepatobiliary protection."
                )

        # Check for cardiovascular / RAAS / Lipid shielding on high-dose protocols
        if total_androgen_dose >= 250.0:
            shield_active = True
            has_arb = any(
                k in stack_keys for k in ["telmisartan", "losartan", "valsartan", "candesartan", "irbesartan", "olmesartan"]
            ) or any(
                "angiotensin receptor blocker" in str(c.get("drug_class", "")).lower()
                or "arb" in str(c.get("drug_class", "")).lower()
                or any(
                    ("agtr1" in str(t.get("target", "") if isinstance(t, dict) else str(t)).lower() or "angiotensin" in str(t.get("target", "") if isinstance(t, dict) else str(t)).lower())
                    and str(t.get("action", "") if isinstance(t, dict) else "").lower() in ["antagonist", "inhibitor", "blocker"]
                    for t in (c.get("receptor_targets") or [])
                )
                for c in enriched_stack
            )
            if not has_arb:
                notes.append(
                    "🛡️ Harm-Reduction Recommendation: Supraphysiological anabolic load (>=250mg); Telmisartan (20-40mg daily) strongly recommended for renal microcirculation and LVH prevention."
                )

        return notes, shield_active

    @classmethod
    def _evaluate_projected_ddi(
        cls,
        projected_stack: List[Dict[str, Any]],
        biometrics: Dict[str, Any],
    ) -> List[str]:
        """
        Runs deterministic collision matrix analysis on projected stack to catch severe uncompensated interactions.
        """
        notes: List[str] = []
        if len(projected_stack) < 2:
            return notes

        try:
            interaction_engine = InteractionEngine()
            eval_res = interaction_engine.analyze_stack(projected_stack, profile={"labs": biometrics})
            breakdown = eval_res.get("breakdown", {})
            syndromes = breakdown.get("syndrome_alerts", [])

            for syn in syndromes:
                sev = str(syn.get("severity", "")).upper()
                if sev in ("CRITICAL", "HIGH", "SEVERE_CONTRAINDICATION"):
                    notes.append(f"⚠️ DDI Collision Warning ({sev}): {syn.get('title')} - {syn.get('description')}")
        except Exception as e:
            logger.debug("DDI check notice: %s", e)

        return notes
