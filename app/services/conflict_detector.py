from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("healthai.conflict_detector")


class ConflictDetector:
    """
    Biomedical Conflict & Literature Consensus Analysis Engine.
    Detects divergent findings across pharmacological literature, evaluates binding affinity variances,
    computes quantitative contradiction indices, and scores consensus agreement ratios.
    """

    @classmethod
    def evaluate_affinity_variance(
        cls,
        reported_values: List[Dict[str, Any]],
        parameter_name: str = "Ki",
    ) -> Dict[str, Any]:
        """
        Analyzes variance among reported binding affinities (Ki, IC50, EC50) across multiple studies/assays.
        Flags high discrepancy (>10x fold difference) as an active scientific debate.
        """
        valid_records = [
            r for r in reported_values
            if isinstance(r.get("value"), (int, float)) and float(r.get("value")) > 0
        ]
        if len(valid_records) <= 1:
            return {
                "has_conflict": False,
                "dispute_status": "consensus",
                "consensus_score": 1.0,
                "contradiction_index": 0.0,
                "sample_count": len(valid_records),
                "summary": "Single source or unanimous measurement.",
            }

        numeric_vals = [float(r["value"]) for r in valid_records]
        min_val = min(numeric_vals)
        max_val = max(numeric_vals)
        fold_diff = max_val / max(0.0001, min_val)

        # Log10 variance
        log_diff = math.log10(max(1.0, fold_diff))
        contradiction_index = min(1.0, max(0.0, log_diff / 3.0))

        if fold_diff >= 10.0:
            status = "debated"
            consensus_score = max(0.2, round(1.0 - contradiction_index, 2))
            summary = (
                f"Significant variance in reported {parameter_name}: {min_val:g} to {max_val:g} nM "
                f"({fold_diff:.1f}x fold difference across {len(valid_records)} published assays)."
            )
        elif fold_diff >= 3.0:
            status = "mild_variance"
            consensus_score = round(1.0 - (contradiction_index * 0.5), 2)
            summary = f"Moderate assay variability in {parameter_name} ({fold_diff:.1f}x spread across {len(valid_records)} studies)."
        else:
            status = "consensus"
            consensus_score = 1.0
            contradiction_index = 0.0
            summary = f"High consistency in reported {parameter_name} ({fold_diff:.1f}x concordance)."

        return {
            "has_conflict": fold_diff >= 3.0,
            "dispute_status": status,
            "consensus_score": consensus_score,
            "contradiction_index": round(contradiction_index, 3),
            "fold_difference": round(fold_diff, 2),
            "min_value": min_val,
            "max_value": max_val,
            "sample_count": len(valid_records),
            "summary": summary,
            "studies": valid_records,
        }

    @classmethod
    def evaluate_clinical_outcome_consensus(
        cls,
        positive_studies: List[Dict[str, Any]],
        opposing_studies: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculates consensus score and contradiction index for opposing clinical efficacy
        or safety claims (e.g. adaptation blunting vs protection).
        Weights Phase III RCTs > Cohorts > In Vivo > In Vitro.
        """
        def _tier_weight(study: Dict[str, Any]) -> float:
            tier = str(study.get("evidence_tier") or study.get("tier") or "").lower()
            if "rct" in tier or "meta" in tier or "phase iii" in tier:
                return 3.0
            if "cohort" in tier or "human" in tier or "phase ii" in tier:
                return 2.0
            if "in_vivo" in tier or "animal" in tier:
                return 1.2
            return 0.8

        pos_weight = sum(_tier_weight(s) for s in positive_studies)
        opp_weight = sum(_tier_weight(s) for s in opposing_studies)
        total_weight = pos_weight + opp_weight

        if total_weight == 0:
            return {
                "has_conflict": False,
                "dispute_status": "consensus",
                "consensus_score": 1.0,
                "contradiction_index": 0.0,
                "summary": "No conflicting studies identified.",
            }

        pos_ratio = pos_weight / total_weight
        opp_ratio = opp_weight / total_weight
        consensus_score = round(max(pos_ratio, opp_ratio), 2)
        contradiction_index = round(min(pos_ratio, opp_ratio) * 2.0, 2)

        if contradiction_index >= 0.6:
            status = "debated"
            summary = (
                f"Active scientific debate: {len(positive_studies)} positive study/trials vs "
                f"{len(opposing_studies)} opposing/refuting reports (Consensus: {consensus_score*100:.0f}%)."
            )
        elif contradiction_index >= 0.2:
            status = "mild_variance"
            summary = (
                f"Predominant consensus ({consensus_score*100:.0f}%) with {len(opposing_studies)} "
                f"divergent or context-dependent study observations."
            )
        else:
            status = "consensus"
            summary = f"Strong scientific consensus ({consensus_score*100:.0f}% agreement)."

        return {
            "has_conflict": contradiction_index >= 0.2,
            "dispute_status": status,
            "consensus_score": consensus_score,
            "contradiction_index": contradiction_index,
            "positive_count": len(positive_studies),
            "opposing_count": len(opposing_studies),
            "summary": summary,
        }
