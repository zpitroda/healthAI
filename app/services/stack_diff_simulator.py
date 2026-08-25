from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.action_card_validator import ActionCardValidator
from app.services.catalog_service import CatalogService
from app.services.graph_service import parse_compound_spec
from app.services.interaction_engine import InteractionEngine
from app.services.pkpd_engine import PKPDEngine
from app.services.synergy_engine import SynergyEngine
from app.schemas.pkpd import PKPDSimulationRequest

logger = logging.getLogger("healthai.stack_diff_simulator")


class StackDiffSimulator:
    """
    Virtual Stack Experiment & 'What-If' Simulation Engine.
    Evaluates comparative before-and-after deltas across:
    1. Cumulative Risk Score & Conflict Count
    2. CYP450 & Transporter Metabolic Load
    3. Organ System Burdens (Hepatic, Renal, Cardiovascular, Lipid, CNS)
    4. Quantitative Multi-Agent Synergy (Loewe CI & Bliss Model)
    5. Pharmacokinetic Steady-State Kinetics (Cmax, AUC, t1/2, Accumulation Ratio)
    """

    @classmethod
    def simulate_diff(
        cls,
        base_stack: List[Any],
        diff: Dict[str, Any],
        biometrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        catalog = CatalogService()
        interaction_engine = InteractionEngine()
        synergy_engine = SynergyEngine()
        biometrics = biometrics or {}

        # 1. Sanitize diff through ActionCardValidator
        sanitized_diff, guardrail_notes = ActionCardValidator.validate_and_sanitize_card(
            card_type="stack_diff",
            payload=diff,
            current_stack=base_stack,
            biometrics=biometrics,
        )

        additions = sanitized_diff.get("add", [])
        modifications = sanitized_diff.get("modify", [])
        removals = sanitized_diff.get("remove", [])

        # 2. Canonicalize Base Stack
        base_compounds = []
        for item in base_stack:
            if isinstance(item, dict):
                k = str(item.get("key") or item.get("name") or "").strip().lower()
                rec = dict(catalog.get_compound(k, auto_enrich=False) or {})
                rec.update(item)
                rec["key"] = k
                base_compounds.append(rec)
            else:
                spec = parse_compound_spec(str(item))
                k = spec.get("key", str(item)).lower()
                rec = dict(catalog.get_compound(k, auto_enrich=False) or {})
                rec.update(spec)
                rec["key"] = k
                base_compounds.append(rec)
        base_compounds = catalog.canonicalize_and_merge_stack(base_compounds)

        # 3. Canonicalize Projected Stack
        projected_compounds = ActionCardValidator._build_projected_stack(
            current_stack=base_stack,
            additions=additions,
            modifications=modifications,
            removals=removals,
            catalog=catalog,
        )
        projected_compounds = catalog.canonicalize_and_merge_stack(projected_compounds)

        # 4. Evaluate Before & After DDI & Collision Matrix
        eval_before = interaction_engine.analyze_stack(base_compounds, profile={"labs": biometrics}) if base_compounds else {}
        eval_after = interaction_engine.analyze_stack(projected_compounds, profile={"labs": biometrics}) if projected_compounds else {}

        risk_before = eval_before.get("cumulative_risk_score", 0)
        risk_after = eval_after.get("cumulative_risk_score", 0)
        risk_delta = risk_after - risk_before

        band_before = str(eval_before.get("risk_band", "minimal")).upper()
        band_after = str(eval_after.get("risk_band", "minimal")).upper()

        conflicts_before = eval_before.get("conflict_count", 0)
        conflicts_after = eval_after.get("conflict_count", 0)

        # Organ Burdens Delta
        breakdown_before = eval_before.get("breakdown", {})
        breakdown_after = eval_after.get("breakdown", {})
        organs_before = breakdown_before.get("organ_burdens", {})
        organs_after = breakdown_after.get("organ_burdens", {})

        organ_deltas = {}
        all_organ_keys = set(list(organs_before.keys()) + list(organs_after.keys()))
        for ok in all_organ_keys:
            score_b = organs_before.get(ok, {}).get("score", 0)
            score_a = organs_after.get(ok, {}).get("score", 0)
            organ_deltas[ok] = {
                "before_score": score_b,
                "after_score": score_a,
                "delta": score_a - score_b,
                "level_before": organs_before.get(ok, {}).get("level", "None"),
                "level_after": organs_after.get(ok, {}).get("level", "None"),
            }

        # 5. Evaluate Before & After Synergy
        syn_before = synergy_engine.evaluate_multi_agent_synergy(base_compounds) if len(base_compounds) >= 2 else {}
        syn_after = synergy_engine.evaluate_multi_agent_synergy(projected_compounds) if len(projected_compounds) >= 2 else {}

        loewe_desc_before = syn_before.get("loewe_model", {}).get("loewe_description", "N/A")
        loewe_desc_after = syn_after.get("loewe_model", {}).get("loewe_description", "N/A")

        # 6. Evaluate PK/PD of Changed Compounds
        pkpd_summaries = []
        for comp in additions + modifications:
            c_key = comp.get("key") or comp.get("name")
            dose = float(comp.get("dose") or comp.get("dose_mg") or 100.0)
            route = comp.get("route", "oral")
            full_record = catalog.get_compound(c_key, auto_enrich=False) or catalog.find_by_synonym(c_key) or comp

            try:
                tau_h = 24.0
                if comp.get("frequency") in ("twice weekly", "split"):
                    tau_h = 84.0
                elif "twice" in str(comp.get("timing", "")).lower() or "bid" in str(comp.get("frequency", "")).lower():
                    tau_h = 12.0

                req = PKPDSimulationRequest(
                    compound_key=c_key,
                    dose_mg=dose,
                    dosing_interval_h=tau_h,
                    simulation_duration_h=max(48.0, tau_h * 2),
                    route=route,
                    steady_state=True,
                    age=biometrics.get("age", 30),
                    weight_kg=biometrics.get("weight_kg", 75.0),
                    egfr=biometrics.get("egfr", 95.0),
                    alt_u_l=biometrics.get("alt_u_l", 25.0),
                )
                sim = PKPDEngine.simulate(full_record, req)
                pkpd_summaries.append({
                    "compound": sim.compound_name,
                    "dose": f"{dose} mg ({route})",
                    "cmax_ng_ml": round(sim.c_max_ng_ml, 1),
                    "tmax_h": round(sim.t_max_h, 1),
                    "effective_t12_h": round(sim.elimination_half_life_effective_h, 1),
                    "accumulation_ratio": round(sim.accumulation_ratio, 2),
                    "time_in_therapeutic_window_pct": round(sim.time_in_therapeutic_window_pct, 1),
                })
            except Exception as e:
                logger.debug("PK simulation error for %s: %s", c_key, e)

        # 7. Generate Clean Markdown Summary Table
        risk_sign = f"+{risk_delta}" if risk_delta > 0 else str(risk_delta)
        markdown_summary = [
            "### 🔬 WHAT-IF STACK DIFF SIMULATION REPORT",
            f"**Baseline Stack ({len(base_compounds)} compounds) ➔ Proposed Stack ({len(projected_compounds)} compounds)**\n",
            "| Parameter | Baseline | Proposed | Delta |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Cumulative Risk Score** | {risk_before}/100 ({band_before}) | {risk_after}/100 ({band_after}) | **{risk_sign} pts** |",
            f"| **Identified Conflicts** | {conflicts_before} | {conflicts_after} | {conflicts_after - conflicts_before:+.0f} |",
            f"| **Loewe Synergy CI** | {loewe_desc_before} | {loewe_desc_after} | - |",
        ]

        for ok, od in organ_deltas.items():
            if od["before_score"] > 0 or od["after_score"] > 0:
                markdown_summary.append(
                    f"| **{ok.capitalize()} Burden** | {od['level_before']} ({od['before_score']:.0f}) | {od['level_after']} ({od['after_score']:.0f}) | {od['delta']:+.1f} pts |"
                )

        if pkpd_summaries:
            markdown_summary.append("\n**Steady-State Pharmacokinetics of Proposed Compounds:**")
            for pk in pkpd_summaries:
                markdown_summary.append(
                    f"- **{pk['compound']}** [{pk['dose']}]: Cmax = {pk['cmax_ng_ml']} ng/mL, Tmax = {pk['tmax_h']}h, t1/2 = {pk['effective_t12_h']}h, Acc = {pk['accumulation_ratio']}x, Window Target = {pk['time_in_therapeutic_window_pct']}%"
                )

        if guardrail_notes:
            markdown_summary.append("\n**Guardrail & Harm-Reduction Verifications:**")
            for gn in guardrail_notes:
                markdown_summary.append(f"- {gn}")

        return {
            "baseline_count": len(base_compounds),
            "projected_count": len(projected_compounds),
            "risk_score_before": risk_before,
            "risk_score_after": risk_after,
            "risk_score_delta": risk_delta,
            "risk_band_before": band_before,
            "risk_band_after": band_after,
            "conflict_count_before": conflicts_before,
            "conflict_count_after": conflicts_after,
            "organ_deltas": organ_deltas,
            "loewe_synergy_before": loewe_desc_before,
            "loewe_synergy_after": loewe_desc_after,
            "pkpd_summaries": pkpd_summaries,
            "guardrail_notes": guardrail_notes,
            "sanitized_diff": sanitized_diff,
            "markdown_summary": "\n".join(markdown_summary),
        }
