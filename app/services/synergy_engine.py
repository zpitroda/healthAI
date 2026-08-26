from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("healthai.synergy_engine")


class SynergyEngine:
    """
    Multi-Agent Quantitative Synergy & Polypharmacology Mapping Engine.
    Models multi-agent interactions using:
    1. Loewe Additivity Model (Combination Index CI):
       CI = sum(d_i / D_x,i)
       CI < 0.85 -> Synergistic
       0.85 <= CI <= 1.15 -> Additive
       CI > 1.15 -> Antagonistic
    2. Bliss Independence Model (Bliss Delta ΔE):
       E_bliss = 1 - prod(1 - E_i)
       ΔE = E_observed - E_bliss
       ΔE > +0.08 -> Synergistic
       -0.08 <= ΔE <= +0.08 -> Independent
       ΔE < -0.08 -> Antagonistic
    3. Multi-Agent Polypharmacology & Stack Domain Profiling:
       - Oncology stacks (dual pathway kinase/DNA damage/checkpoint blockade)
       - Antimicrobial stacks (sequential metabolic / cell wall + resistance enzyme blockade)
       - Longevity stacks (mTOR + AMPK + SIRT1 / senolytic autophagy convergence)
    """

    def calculate_loewe_combination_index(
        self,
        doses_mg: List[float],
        single_agent_ec50s_mg: List[float],
        hill_slopes: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Calculates Loewe Additivity Combination Index (CI) for multi-agent combinations."""
        if not doses_mg or not single_agent_ec50s_mg or len(doses_mg) != len(single_agent_ec50s_mg):
            return {"combination_index": 1.0, "classification": "Additive", "is_synergistic": False}

        hill_slopes = hill_slopes or [1.0] * len(doses_mg)

        # Calculate individual terms d_i / D_x,i
        terms = []
        for d, ec50 in zip(doses_mg, single_agent_ec50s_mg):
            terms.append(d / max(0.0001, ec50))

        ci = sum(terms)
        ci_rounded = round(ci, 3)

        if ci_rounded < 0.70:
            classification = "Strong Synergy"
            is_synergistic = True
        elif ci_rounded < 0.85:
            classification = "Moderate Synergy"
            is_synergistic = True
        elif ci_rounded <= 1.15:
            classification = "Loewe Additive"
            is_synergistic = False
        elif ci_rounded <= 1.45:
            classification = "Moderate Antagonism"
            is_synergistic = False
        else:
            classification = "Strong Antagonism"
            is_synergistic = False

        return {
            "combination_index": ci_rounded,
            "classification": classification,
            "is_synergistic": is_synergistic,
            "terms": [round(t, 4) for t in terms],
            "loewe_description": f"Loewe CI = {ci_rounded:.3f} ({classification}). Dose reduction factor: {round(1.0 / max(0.1, ci_rounded), 2)}x.",
        }

    def calculate_bliss_independence(
        self,
        single_effects: List[float],
        observed_combined_effect: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculates Bliss Independence expected effect and Bliss Delta (ΔE)."""
        if not single_effects:
            return {"expected_bliss_effect_pct": 0.0, "observed_effect_pct": 0.0, "bliss_delta_pct": 0.0, "bliss_delta": 0.0, "classification": "Independent", "is_synergistic": False}

        # Normalize fractional effects to [0.0, 1.0]
        norm_effects = [max(0.0, min(1.0, float(e))) for e in single_effects]

        prod = 1.0
        for e in norm_effects:
            prod *= (1.0 - e)

        e_bliss = 1.0 - prod

        if observed_combined_effect is None:
            # Estimate observed effect with synergy boost if multiple distinct mechanisms
            if len(norm_effects) >= 2 and all(e > 0.05 for e in norm_effects):
                observed_combined_effect = min(0.99, e_bliss + 0.12 * (1.0 - e_bliss))
            else:
                observed_combined_effect = e_bliss

        obs_norm = max(0.0, min(1.0, float(observed_combined_effect)))
        bliss_delta = obs_norm - e_bliss

        e_bliss_pct = round(e_bliss * 100.0, 1)
        obs_pct = round(obs_norm * 100.0, 1)
        delta_pct = round(bliss_delta * 100.0, 1)

        if delta_pct > 12.0:
            classification = "Strong Synergy"
            is_synergistic = True
        elif delta_pct > 5.0:
            classification = "Moderate Synergy"
            is_synergistic = True
        elif delta_pct >= -5.0:
            classification = "Bliss Independent"
            is_synergistic = False
        elif delta_pct >= -12.0:
            classification = "Moderate Antagonism"
            is_synergistic = False
        else:
            classification = "Strong Antagonism"
            is_synergistic = False

        return {
            "expected_bliss_effect_pct": e_bliss_pct,
            "observed_effect_pct": obs_pct,
            "bliss_delta_pct": delta_pct,
            "bliss_delta": round(bliss_delta, 4),
            "classification": classification,
            "is_synergistic": is_synergistic,
            "bliss_description": f"Bliss Model: Expected {e_bliss_pct}%, Observed {obs_pct}% (ΔE = {delta_pct:+.1f}%, {classification}).",
        }

    def evaluate_multi_agent_synergy(
        self,
        compounds: List[Dict[str, Any]],
        stack_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates full multi-compound synergy across Loewe Additivity and Bliss Independence models
        and maps polypharmacology target & pathway overlaps.
        """
        if not compounds:
            return {
                "polypharmacology_matrix": [],
                "synergy_summary": "No active compounds provided for synergy evaluation.",
                "loewe_model": {},
                "bliss_model": {},
            }

        # 1. Map target engagement & polypharmacology overlaps
        targets_by_compound: Dict[str, List[Dict[str, Any]]] = {}
        all_targets: Dict[str, List[str]] = {}

        for c in compounds:
            c_key = c.get("key") or c.get("name") or "unknown"
            c_label = c.get("name") or c.get("canonical_name") or c_key.title()
            tgt_list = c.get("receptor_targets") or []
            targets_by_compound[c_key] = tgt_list
            for t in tgt_list:
                t_name = t.get("target") if isinstance(t, dict) else str(t)
                if t_name:
                    all_targets.setdefault(t_name.lower(), []).append(c_label)

        # Detect target overlaps (shared targets engaged by >1 agent)
        shared_targets = {t_name: comps for t_name, comps in all_targets.items() if len(comps) > 1}

        # 2. Extract doses and single-agent fractional effects
        doses_mg = []
        ec50s_mg = []
        effects = []

        for c in compounds:
            c_dose = float(c.get("dose_mg") if c.get("dose_mg") is not None else c.get("dose", 10.0))
            doses_mg.append(c_dose)

            # Estimate EC50 reference dose based on compound class
            drug_class = str(c.get("drug_class") or "").lower()
            if "oncology" in drug_class or "kinase" in drug_class or "chemotherapy" in drug_class:
                ref_ec50 = 25.0
            elif "antibiotic" in drug_class or "antimicrobial" in drug_class:
                ref_ec50 = 250.0
            elif "longevity" in drug_class or "mtor" in drug_class or "ampk" in drug_class or "sirtuin" in drug_class:
                ref_ec50 = 100.0
            else:
                ref_ec50 = 20.0
            ec50s_mg.append(ref_ec50)

            # Single-agent fractional efficacy
            single_e = min(0.95, 0.40 + 0.20 * math.log10(max(1.0, c_dose / max(1.0, ref_ec50 * 0.1))))
            effects.append(single_e)

        # Determine observed combined effect with domain-specific synergy rules
        is_oncology = (stack_domain == "oncology") or any(
            any(w in str(c.get("drug_class") or "").lower() or w in str(c.get("mechanism") or "").lower() or w in str(c.get("name") or "").lower()
                for w in ["kinase", "tumor", "oncology", "chemo", "egfr", "braf", "her2", "checkpoint", "doxorubicin", "paclitaxel", "tamoxifen", "cisplatin", "osimertinib", "trametinib", "dabrafenib"])
            for c in compounds
        )
        is_antimicrobial = (stack_domain == "antimicrobial") or any(
            any(w in str(c.get("drug_class") or "").lower() or w in str(c.get("mechanism") or "").lower() or w in str(c.get("name") or "").lower()
                for w in ["antibiotic", "antimicrobial", "penicillin", "amoxicillin", "clavulan", "trimethoprim", "sulfamethoxazole", "bactericidal", "antifungal", "fluconazole"])
            for c in compounds
        )
        is_longevity = (stack_domain == "longevity") or any(
            any(w in str(c.get("drug_class") or "").lower() or w in str(c.get("mechanism") or "").lower() or w in str(c.get("name") or "").lower()
                for w in ["rapamycin", "metformin", "nmn", "resveratrol", "dasatinib", "quercetin", "sirtuin", "ampk", "mtor", "senolytic", "autophagy", "nad+"])
            for c in compounds
        )

        detected_stack_type = "general"
        synergy_boost = 0.05
        domain_note = ""

        if is_oncology and len(compounds) >= 2:
            detected_stack_type = "oncology"
            synergy_boost = 0.16
            domain_note = "Oncology Polypharmacology: Dual oncogenic kinase / DNA damage pathway inhibition drives synergistic tumor growth suppression."
        elif is_antimicrobial and len(compounds) >= 2:
            detected_stack_type = "antimicrobial"
            synergy_boost = 0.18
            domain_note = "Antimicrobial Synergy: Sequential metabolic enzyme blockade / cell wall degradation + resistance inhibitor (e.g. Beta-lactamase) produces synergistic pathogen eradication."
        elif is_longevity and len(compounds) >= 2:
            detected_stack_type = "longevity"
            synergy_boost = 0.14
            domain_note = "Longevity & Anti-Aging Stack: Convergence on AMPK activation, mTORC1 suppression, and SIRT1 deacetylase activation drives synergistic autophagy and cellular rejuvenation."

        # 2b. Literature evidence integration — adjust synergy_boost based on
        # LITERATURE_COOCCURRENCE and CURATED_ASSOCIATION edges in the graph
        literature_evidence: List[Dict[str, Any]] = []
        literature_boost = 0.0
        try:
            from app.knowledge_graph.graph_db import get_graph_database
            gdb = get_graph_database()
            compound_keys = [
                str(c.get("key") or c.get("name") or "").lower().replace(" ", "_")
                for c in compounds
            ]
            for i in range(len(compound_keys)):
                for j in range(i + 1, len(compound_keys)):
                    src, tgt = compound_keys[i], compound_keys[j]
                    if not src or not tgt:
                        continue
                    # Query both literature edge types between this pair
                    for edge in gdb._mock_edges:
                        edge_type = str(edge.get("edge_type", ""))
                        if edge_type not in ("LITERATURE_COOCCURRENCE", "CURATED_ASSOCIATION"):
                            continue
                        e_src = str(edge.get("source", ""))
                        e_tgt = str(edge.get("target", ""))
                        if (e_src == src and e_tgt == tgt) or (e_src == tgt and e_tgt == src):
                            conf = float(edge.get("confidence", 0.0))
                            literature_evidence.append({
                                "compound_a": src,
                                "compound_b": tgt,
                                "edge_type": edge_type,
                                "confidence": conf,
                                "source_db": edge.get("source_db", ""),
                                "cooccurrence_count": edge.get("cooccurrence_count"),
                                "npmi_score": edge.get("npmi_score"),
                                "description": edge.get("description", ""),
                            })
                            literature_boost = max(literature_boost, conf)

            # Scale: high-confidence literature evidence (conf >= 0.7) adds up to +0.10 synergy boost
            if literature_boost > 0 and len(compounds) >= 2:
                scaled_boost = min(0.10, literature_boost * 0.12)
                synergy_boost += scaled_boost
                if not domain_note:
                    domain_note = f"Literature-backed association: {len(literature_evidence)} evidence edge(s) found across curated databases and PubMed co-occurrence (max confidence: {literature_boost:.2f})."
                else:
                    domain_note += f" Literature reinforcement: {len(literature_evidence)} evidence edge(s), max confidence {literature_boost:.2f}."
                logger.debug(
                    "Literature synergy boost: +%.3f (from %d edges, max conf %.2f)",
                    scaled_boost, len(literature_evidence), literature_boost,
                )
        except Exception as e:
            logger.debug("Literature evidence lookup skipped: %s", e)

        prod_eff = 1.0
        for e in effects:
            prod_eff *= (1.0 - e)
        e_bliss_base = 1.0 - prod_eff
        obs_effect = min(0.99, e_bliss_base + synergy_boost) if len(compounds) >= 2 else e_bliss_base

        bliss_res = self.calculate_bliss_independence(effects, observed_combined_effect=obs_effect)

        # Calculate Loewe Additivity CI where D_X,i is single agent dose to reach E_observed
        loewe_single_doses_dx = [ec50 * (obs_effect / max(0.01, 1.0 - obs_effect)) for ec50 in ec50s_mg]
        loewe_res = self.calculate_loewe_combination_index(doses_mg, loewe_single_doses_dx)

        # 3. Evaluate Pairwise Synergy Matrix
        pairwise_matrix = []
        for i in range(len(compounds)):
            for j in range(i + 1, len(compounds)):
                c1, c2 = compounds[i], compounds[j]
                n1 = c1.get("name") or c1.get("key") or f"Agent {i+1}"
                n2 = c2.get("name") or c2.get("key") or f"Agent {j+1}"
                d1 = float(c1.get("dose_mg") if c1.get("dose_mg") is not None else c1.get("dose", 10.0))
                d2 = float(c2.get("dose_mg") if c2.get("dose_mg") is not None else c2.get("dose", 10.0))

                pair_e_bliss = 1.0 - (1.0 - effects[i]) * (1.0 - effects[j])
                pair_obs = min(0.98, pair_e_bliss + synergy_boost) if synergy_boost > 0 else pair_e_bliss
                pair_dx = [ec50s_mg[i] * (pair_obs / max(0.01, 1.0 - pair_obs)), ec50s_mg[j] * (pair_obs / max(0.01, 1.0 - pair_obs))]
                pair_loewe = self.calculate_loewe_combination_index([d1, d2], pair_dx)
                pair_bliss = self.calculate_bliss_independence([effects[i], effects[j]], observed_combined_effect=pair_obs)

                pairwise_matrix.append({
                    "compound_a": n1,
                    "compound_b": n2,
                    "loewe_combination_index": pair_loewe["combination_index"],
                    "loewe_classification": pair_loewe["classification"],
                    "bliss_delta_pct": pair_bliss["bliss_delta_pct"],
                    "bliss_classification": pair_bliss["classification"],
                    "is_synergistic": pair_loewe["is_synergistic"] or pair_bliss["is_synergistic"],
                    "mechanistic_basis": f"Polypharmacological convergence of {n1} and {n2}." if not domain_note else domain_note,
                })

        overall_synergy = loewe_res["is_synergistic"] or bliss_res["is_synergistic"]

        return {
            "stack_domain": stack_domain or detected_stack_type,
            "overall_synergistic": overall_synergy,
            "synergy_score_index": round((1.0 / max(0.2, loewe_res["combination_index"])) * (1.0 + max(0.0, bliss_res["bliss_delta"])), 2),
            "loewe_model": loewe_res,
            "bliss_model": bliss_res,
            "pairwise_synergy_matrix": pairwise_matrix,
            "polypharmacology_shared_targets": shared_targets,
            "shared_target_count": len(shared_targets),
            "domain_notes": domain_note or f"Evaluated synergy across {len(compounds)} compounds using Loewe Additivity and Bliss Independence models.",
            "literature_evidence": literature_evidence,
            "literature_evidence_count": len(literature_evidence),
            "literature_max_confidence": round(literature_boost, 3),
        }
