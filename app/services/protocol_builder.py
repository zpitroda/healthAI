from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.services.catalog_service import CatalogService
from app.services.interaction_engine import InteractionEngine


def _get_catalog_service() -> CatalogService:
    return CatalogService()


def _dose_for_compound(compound: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    dosing = compound.get("dosing", {}) or {}
    unit = dosing.get("unit", "mg/day")
    basis = dosing.get("basis", "fixed")
    mg_per_kg = dosing.get("mg_per_kg", {}) or {}
    weight_kg = profile.get("weight_kg") or 70

    sex = str(profile.get("sex") or "male").lower()
    age = int(profile.get("age") or 30)
    height_cm = float(profile.get("height_cm") or 175.0)

    # Adjust dose recommendations for sex and age variations where applicable
    sex_scaling = 0.88 if sex == "female" else 1.0
    age_scaling = 0.90 if age > 65 else 1.0
    combined_biometric_scale = sex_scaling * age_scaling

    if basis == "bodyweight" and mg_per_kg:
        threshold = mg_per_kg.get("threshold", 0)
        common = mg_per_kg.get("common", 0)
        heavy = mg_per_kg.get("heavy", 0)

        threshold_dose = round(threshold * weight_kg * combined_biometric_scale)
        common_dose = round(common * weight_kg * combined_biometric_scale)
        heavy_dose = round(heavy * weight_kg * combined_biometric_scale)
        return {
            "unit": unit,
            "dosage_range": {
                "threshold": threshold_dose,
                "common": common_dose,
                "heavy": heavy_dose,
            },
            "recommended_dose": common_dose,
            "basis": basis,
        }

    threshold = mg_per_kg.get("threshold", 0)
    common = mg_per_kg.get("common", 0)
    heavy = mg_per_kg.get("heavy", 0)
    if common == 0 and dosing.get("common"):
        common = dosing.get("common")
    return {
        "unit": unit,
        "dosage_range": {"threshold": threshold, "common": common, "heavy": heavy},
        "recommended_dose": common or 100,
        "basis": basis,
    }


def build_recommendation(compound_key: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    service = _get_catalog_service()
    compound = service.get_compound(compound_key)
    if compound is None:
        normalized = compound_key.strip().lower().replace(" ", "_")
        compound = service.get_compound(normalized)

    if compound is None:
        return {
            "compound": compound_key,
            "key": compound_key,
            "drug_class": "unknown",
            "mechanism": "Compound was not found in the catalog.",
            "receptor_targets": [],
            "dose": {"unit": "mg/day", "dosage_range": {"threshold": 0, "common": 0, "heavy": 0}, "recommended_dose": 0, "basis": "fixed"},
            "dose_mg": 0,
            "unit": "mg/day",
            "reason": "This item is not in the active catalog and should be reviewed manually before use.",
            "citation": "N/A",
            "contraindications": [],
            "side_effects": [],
            "interactions": [],
            "evidence_level": "unknown",
            "risk_band": "unknown",
            "graph_tags": [],
            "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
            "organ_burdens": {},
            "synergies": [],
        }

    dosing = _dose_for_compound(compound, profile)

    return {
        "compound": compound["name"],
        "key": compound.get("key"),
        "drug_class": compound.get("drug_class"),
        "mechanism": compound.get("mechanism"),
        "receptor_targets": compound.get("receptor_targets", []),
        "transporters": compound.get("transporters", {}),
        "phase2_enzymes": compound.get("phase2_enzymes", {}),
        "smiles": compound.get("smiles"),
        "logp": compound.get("logp"),
        "tpsa": compound.get("tpsa"),
        "half_life": compound.get("half_life"),
        "oral_bioavailability": compound.get("oral_bioavailability"),
        "dose": dosing,
        "dose_mg": dosing["recommended_dose"],
        "unit": dosing["unit"],
        "reason": compound.get("reason"),
        "citation": compound.get("citation"),
        "contraindications": compound.get("contraindications", []),
        "side_effects": compound.get("side_effects", []),
        "interactions": compound.get("interactions", []),
        "warnings": compound.get("warnings", []),
        "boxed_warning": compound.get("boxed_warning"),
        "is_narrow_therapeutic_index": bool(compound.get("is_narrow_therapeutic_index")),
        "evidence_level": compound.get("evidence_level", "moderate"),
        "risk_band": compound.get("risk_band", "low"),
        "graph_tags": compound.get("graph_tags", []),
        "cyp_enzymes": compound.get("cyp_enzymes", {"substrates": [], "inhibitors": [], "inducers": []}),
        "organ_burdens": compound.get("organ_burdens", {}),
        "synergies": compound.get("synergies", []),
    }


def _normalize_stack(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_stack = profile.get("stack") or []
    if isinstance(raw_stack, str):
        raw_stack = [raw_stack]

    normalized: List[Dict[str, Any]] = []
    for item in raw_stack:
        if item is None:
            continue

        if isinstance(item, dict):
            compound_name = str(item.get("compound") or item.get("name") or item.get("key") or "").strip().lower()
            if not compound_name:
                continue
            normalized.append(
                {
                    "compound": compound_name,
                    "dose": item.get("dose"),
                    "unit": item.get("unit") or "mg",
                    "frequency": item.get("frequency") or "daily",
                    "timing": item.get("timing") or "with food",
                    "notes": item.get("notes"),
                }
            )
            continue

        compound_name = str(item).strip().lower()
        if compound_name:
            normalized.append({
                "compound": compound_name,
                "dose": None,
                "unit": "mg",
                "frequency": "daily",
                "timing": "with food",
                "notes": None,
            })

    return normalized


def _current_stack_issues(profile: Dict[str, Any], stack: List[str]) -> List[str]:
    issues: List[str] = []
    labs = profile.get("labs", {}) or {}
    counts = Counter(stack)

    for key, count in sorted(counts.items()):
        if count > 1:
            issues.append(f"Duplicate compound detected: {key} appears {count} times in the current stack.")

    if "caffeine" in stack and len(stack) > 1:
        issues.append("Multiple stimulant exposures may increase CNS and cardiovascular load beyond the intended effect.")

    hematocrit = labs.get("hematocrit_pct") or 0
    ldl = labs.get("ldl_mg_dl") or 0
    alt = labs.get("alt_u_l") or 0
    if hematocrit > 50 or ldl > 150 or alt > 70:
        issues.append("Biomarker pattern suggests oxidative or metabolic stress; recovery and mitochondrial support should be reviewed.")

    sleep = profile.get("sleep_hours") if profile.get("sleep_hours") is not None else 7.0
    if sleep < 6:
        issues.append("Sleep is below the threshold for resilient stimulant tolerance and recovery.")

    bp = profile.get("blood_pressure") or labs.get("blood_pressure") or 0
    if any(key in {"caffeine", "ephedra", "synephrine", "yohimbine"} for key in set(stack)) and bp > 120:
        issues.append("Elevated blood pressure with stimulant exposure warrants caution and a lower stimulant load.")

    return issues


def _current_stack_interactions(profile: Dict[str, Any], stack: List[str]) -> List[str]:
    service = _get_catalog_service()
    interactions: List[str] = []
    seen = set()

    for key in stack:
        compound = service.get_compound(key)
        if not compound:
            continue
        for interaction in compound.get("interactions", []):
            if interaction not in seen:
                interactions.append(interaction)
                seen.add(interaction)

    if "caffeine" in stack:
        msg = "Caffeine can worsen sleep quality and raise cardiovascular stress when repeated or dosed late in the day."
        if msg not in seen:
            interactions.append(msg)
            seen.add(msg)

    stack_raw = profile.get("stack", [])
    if any(isinstance(entry, dict) and entry.get("frequency") == "daily" for entry in stack_raw):
        msg = "Daily dosing is a relevant schedule signal; repeated daily stimulant exposure may increase sleep disruption and cardiovascular strain."
        if msg not in seen:
            interactions.append(msg)
            seen.add(msg)

    if len(stack) > 1:
        msg = "Multiple compounds in the current stack warrant a review for overlapping pharmacology and additive stress signals."
        if msg not in seen:
            interactions.append(msg)
            seen.add(msg)

    return interactions


def calculate_protocol(profile: Dict[str, Any]) -> Dict[str, Any]:
    service = _get_catalog_service()
    interaction_engine = InteractionEngine()

    stack_entries = _normalize_stack(profile)
    if stack_entries:
        stack_keys = [entry["compound"] for entry in stack_entries]
        recommendations = [build_recommendation(key, profile) for key in stack_keys if key]
        for index, entry in enumerate(stack_entries):
            if index < len(recommendations):
                recommendation = recommendations[index]
                recommendation["user_entry"] = {
                    "compound": entry["compound"],
                    "dose": entry.get("dose"),
                    "unit": entry.get("unit"),
                    "frequency": entry.get("frequency"),
                    "timing": entry.get("timing"),
                }

        issues = _current_stack_issues(profile, stack_keys)
        interactions = _current_stack_interactions(profile, stack_keys)

        if any(isinstance(entry, dict) and entry.get("timing") in {"before bed", "late evening"} for entry in profile.get("stack", [])):
            msg = "Compounds taken before bed or late in the evening may impair sleep and amplify stimulant-related stress."
            if msg not in interactions:
                interactions.append(msg)

        # Run comprehensive Interaction Collision Engine
        raw_compounds = []
        for key in stack_keys:
            c = service.get_compound(key)
            if c:
                raw_compounds.append(c)
            else:
                raw_compounds.append({"key": key, "name": key.title(), "mechanism": "User added custom compound."})

        interaction_results = interaction_engine.analyze_stack(raw_compounds, profile)

        # Append engine conflicts to interactions list
        for conflict in interaction_results["breakdown"]["cyp_conflicts"] + interaction_results["breakdown"]["receptor_conflicts"]:
            if conflict["description"] not in interactions:
                interactions.append(conflict["description"])

        contraindications = list(issues)
        summary = (
            "This review is based on the user’s current stack and biomarkers, with emphasis on duplicate exposures, stimulant burden, oxidative stress, and overlapping pharmacology."
        )

        return {
            "summary": summary,
            "stack": recommendations,
            "issues": issues,
            "interactions": interactions,
            "contraindications": contraindications,
            "cumulative_risk_score": interaction_results["cumulative_risk_score"],
            "risk_band": interaction_results["risk_band"],
            "matrix": interaction_results["matrix"],
            "breakdown": interaction_results["breakdown"],
            "conflict_count": interaction_results["conflict_count"],
            "synergy_count": interaction_results["synergy_count"],
        }

    goals = {goal.lower().strip() for goal in profile.get("goals", [])}
    labs = profile.get("labs", {}) or {}
    contraindications: List[str] = []

    hematocrit = labs.get("hematocrit_pct") or 0
    ldl = labs.get("ldl_mg_dl") or 0
    alt = labs.get("alt_u_l") or 0
    sleep = profile.get("sleep_hours") if profile.get("sleep_hours") is not None else 7.0

    if hematocrit > 52:
        contraindications.append("High hematocrit may increase cardiovascular risk with erythropoietic compounds.")
    if ldl > 190:
        contraindications.append("Very high LDL suggests cardiovascular contraindication for certain performance compounds.")
    if alt > 80:
        contraindications.append("Elevated ALT suggests hepatic stress and warrants caution with liver-metabolized compounds.")
    if sleep < 6:
        contraindications.append("Insufficient sleep lowers tolerance and may increase stimulant-related adverse effects.")

    protocol_order = [
        "creatine" if ("strength" in goals or "muscle" in goals) else None,
        "caffeine" if ("focus" in goals or "cognition" in goals or "productivity" in goals) else None,
        "l_carnitine" if ("fat loss" in goals or "weight" in goals) else None,
        "ashwagandha" if ("stress" in goals or "recovery" in goals) else None,
        "beta_alanine" if ("endurance" in goals or "power" in goals) else None,
        "omega_3" if ("general health" in goals or "recovery" in goals or "cardio" in goals) else None,
    ]

    selected_keys = [item for item in protocol_order if item is not None]
    if not selected_keys:
        selected_keys = ["creatine", "caffeine"]

    recommendations = []
    raw_compounds = []
    for key in selected_keys:
        comp = service.get_compound(key)
        if comp:
            rec = build_recommendation(key, profile)
            recommendations.append(rec)
            raw_compounds.append(comp)

    interaction_results = interaction_engine.analyze_stack(raw_compounds, profile)

    summary = (
        "This stack is assembled from a structured pharmacology map, with dosing anchored to bodyweight where appropriate and safety metadata captured by class, receptor, interaction, and contraindication tags."
    )

    return {
        "summary": summary,
        "stack": recommendations,
        "contraindications": contraindications,
        "issues": [],
        "interactions": [c["description"] for c in interaction_results["breakdown"]["cyp_conflicts"] + interaction_results["breakdown"]["receptor_conflicts"]],
        "cumulative_risk_score": interaction_results["cumulative_risk_score"],
        "risk_band": interaction_results["risk_band"],
        "matrix": interaction_results["matrix"],
        "breakdown": interaction_results["breakdown"],
        "conflict_count": interaction_results["conflict_count"],
        "synergy_count": interaction_results["synergy_count"],
    }
