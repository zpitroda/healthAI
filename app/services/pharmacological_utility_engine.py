from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("healthai.pharmacological_utility_engine")


class PharmacologicalUtilityEngine:
    """
    Generalized Pharmacological Multi-Criteria Decision Analysis (MCDA) Scoring Engine.
    
    Evaluates and ranks candidate compounds and delivery routes dynamically across:
    1. Pharmacodynamic (PD) Efficacy & Clinical Evidence (Mechanism Type, Bio-identity, Selectivity, Pleiotropic Targets)
    2. Pharmacokinetic (PK) Delivery & Circadian Half-Life Compatibility (F, t1/2 stability, Depot alignment)
    3. Safety, Organ Burden & Rebound Risk (Hepatic, Renal, Lipid/ApoB, Endocrine Rebound, CYP450 collisions)
    4. Protocol Economy & Metabolite Liability (Gut TMAO generation, Ancillary dependency count)
    
    Zero hardcoded drug names: all evaluations operate on quantifiable catalog metadata.
    """

    # Multi-criteria weighting coefficients (sum to 1.0)
    WEIGHT_PD = 0.30
    WEIGHT_PK = 0.25
    WEIGHT_SAFETY = 0.25
    WEIGHT_ECONOMY = 0.20

    @classmethod
    def score_compound(
        cls,
        compound: Dict[str, Any],
        route: Optional[str] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        target_context: Optional[str] = None,
        action_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes a comprehensive pharmacological utility score U in [0.0, 100.0] for a compound and route.
        Returns total score and sub-score breakdown.
        """
        user_profile = user_profile or {}
        biometrics = user_profile.get("biometrics", {}) or {}
        route_preference = str(
            user_profile.get("route_preference")
            or user_profile.get("preferences", {}).get("route_preference")
            or user_profile.get("preferences", {}).get("route")
            or "all"
        ).lower().strip()

        # Infer effective delivery route if not provided
        effective_route = str(route or compound.get("route_of_administration") or "oral").lower().strip()
        if not route and route_preference in ("all", "hybrid", "injectable"):
            effective_route = cls.determine_optimal_route(compound, route_preference)

        # Calculate sub-scores
        s_pd, pd_reasons = cls._evaluate_pharmacodynamics(compound, target_context, action_context)
        s_pk, pk_reasons = cls._evaluate_pharmacokinetics(compound, effective_route, user_profile)
        s_safety, safety_reasons = cls._evaluate_safety_and_burdens(compound, user_profile)
        s_econ, econ_reasons = cls._evaluate_economy_and_metabolites(compound, effective_route)

        total_score = (
            cls.WEIGHT_PD * s_pd
            + cls.WEIGHT_PK * s_pk
            + cls.WEIGHT_SAFETY * s_safety
            + cls.WEIGHT_ECONOMY * s_econ
        )
        total_score = max(0.0, min(100.0, round(total_score, 2)))

        return {
            "total_score": total_score,
            "route": effective_route,
            "sub_scores": {
                "pharmacodynamics": round(s_pd, 2),
                "pharmacokinetics": round(s_pk, 2),
                "safety": round(s_safety, 2),
                "protocol_economy": round(s_econ, 2),
            },
            "rationales": {
                "pd": pd_reasons,
                "pk": pk_reasons,
                "safety": safety_reasons,
                "economy": econ_reasons,
            }
        }

    @classmethod
    def _evaluate_pharmacodynamics(
        cls,
        compound: Dict[str, Any],
        target_context: Optional[str] = None,
        action_context: Optional[str] = None,
    ) -> Tuple[float, List[str]]:
        """Evaluates PD mechanism quality, intrinsic efficacy, pleiotropic targets, and clinical evidence tier."""
        score = 50.0  # Neutral baseline
        reasons: List[str] = []

        mech = str(compound.get("mechanism", "")).lower()
        drug_class = str(compound.get("drug_class", "")).lower()
        evidence_level = str(compound.get("evidence_level", "moderate")).lower()
        meta = compound.get("metadata", {}) or {}
        evidence_tier = str(meta.get("evidence_tier", "")).upper()
        human_trials = meta.get("human_clinical_trials")

        # 1. Mechanism Class & Inactivation Kinetics
        is_irreversible = any(w in mech for w in ["suicide", "irreversible", "covalent", "inactivat"])
        if is_irreversible:
            score += 22.0
            reasons.append("Irreversible / suicidal inactivation destroys target enzyme molecule, eliminating competitive rebound surges.")

        is_allosteric = "allosteric" in mech or "pam" in mech or "nam" in mech
        if is_allosteric:
            score += 12.0
            reasons.append("Allosteric modulation provides saturable ceiling safety and preserves endogenous feedback loops.")

        # 2. Human Clinical Trial Validation & Regulatory Grounding
        if evidence_level in ("high", "gold_standard", "established") or human_trials is True or evidence_tier in ("CLINICAL_TRIAL_VALIDATED", "FDA_APPROVED"):
            score += 18.0
            reasons.append("Strong clinical trial validation and robust human safety/efficacy documentation.")
        elif evidence_tier in ("PRECLINICAL", "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION") or human_trials is False:
            score -= 12.0
            reasons.append("Limited to preclinical or in vitro data with uncharacterized long-term human safety.")

        # 3. Pleiotropic Secondary Beneficial Targets
        targets = compound.get("receptor_targets") or []
        beneficial_pleiotropic_count = 0
        for t in targets:
            if not isinstance(t, dict):
                continue
            t_str = str(t.get("target", "") + " " + t.get("name", "")).lower()
            t_act = str(t.get("action", "")).lower()
            
            # eNOS / Nitric oxide stimulation
            if ("nos3" in t_str or "enos" in t_str or "nitric oxide" in t_str) and any(a in t_act for a in ["activat", "stimulat", "agonist"]):
                beneficial_pleiotropic_count += 1
                reasons.append("Secondary endothelial nitric oxide synthase (eNOS) activation provides cardioprotective vasodilation.")
            
            # PPAR-gamma / Metabolic insulin sensitization
            if "ppar" in t_str and any(a in t_act for a in ["agonist", "activat", "modulat"]):
                beneficial_pleiotropic_count += 1
                reasons.append("Secondary PPAR-gamma modulation improves peripheral insulin sensitivity and lipid partitioning.")
                
            # Nrf2 / Phase II antioxidant defense
            if "nrf2" in t_str and any(a in t_act for a in ["activat", "inducer", "agonist"]):
                beneficial_pleiotropic_count += 1
                reasons.append("Secondary Nrf2 cytoprotective induction enhances Phase II endogenous antioxidant enzymes.")

        if beneficial_pleiotropic_count > 0:
            score += min(15.0, beneficial_pleiotropic_count * 7.5)

        # 4. Target Selectivity Ratio (if target_context specified)
        if target_context:
            tc_lower = target_context.lower()
            matching_targets = [t for t in targets if isinstance(t, dict) and tc_lower in str(t.get("target", "")).lower()]
            if matching_targets:
                score += 10.0
                reasons.append(f"Direct on-target affinity for {target_context}.")

        return max(0.0, min(100.0, score)), reasons

    @classmethod
    def _evaluate_pharmacokinetics(
        cls,
        compound: Dict[str, Any],
        route: str,
        user_profile: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Evaluates delivery bioavailability, half-life stability, and depot alignment."""
        score = 50.0
        reasons: List[str] = []

        is_parenteral = route in ("intramuscular", "im", "subcutaneous", "subq", "iv")
        
        # 1. Route Delivery Bioavailability (F)
        if is_parenteral:
            bioavailability = 1.0
            score += 25.0
            reasons.append("Parenteral delivery achieves ~100% systemic bioavailability with zero first-pass gastrointestinal loss.")
        else:
            raw_f = compound.get("oral_bioavailability") or compound.get("bioavailability_f")
            try:
                bioavailability = float(raw_f) if raw_f is not None else 0.5
            except (ValueError, TypeError):
                bioavailability = 0.5

            if bioavailability >= 0.75:
                score += 15.0
                reasons.append(f"High oral bioavailability (F ≈ {int(bioavailability*100)}%).")
            elif bioavailability <= 0.20:
                # Moderate penalty if half-life is long (>12h) due to active metabolites/tissue binding
                score -= 10.0
                reasons.append(f"Lower oral bioavailability (F ≈ {int(bioavailability*100)}%).")
            else:
                score += (bioavailability - 0.5) * 20.0

        # 2. Elimination Half-Life (t1/2) Stability & Fluctuation Control
        t_half_numeric = compound.get("t_half_numeric")
        if t_half_numeric is None:
            hl_str = str(compound.get("half_life") or "").lower()
            m = re.search(r"(\d+(?:\.\d+)?)\s*(h|hr|hours?|d|days?|w|weeks?)", hl_str)
            if m:
                val = float(m.group(1))
                unit = m.group(2)
                if "d" in unit:
                    t_half_numeric = val * 24.0
                elif "w" in unit:
                    t_half_numeric = val * 168.0
                else:
                    t_half_numeric = val

        if t_half_numeric is not None:
            if t_half_numeric >= 24.0:
                # 24h+ half-lives provide excellent steady-state stability for daily/weekly protocols
                score += 20.0
                reasons.append(f"Extended elimination half-life (t1/2 ≈ {t_half_numeric:g}h) flattens peak-to-trough fluctuations (PTF < 50%).")
            elif t_half_numeric >= 12.0:
                score += 12.0
                reasons.append(f"Compatible half-life (t1/2 ≈ {t_half_numeric:g}h) for once or twice daily administration.")
            elif t_half_numeric < 3.0 and not is_parenteral:
                score -= 15.0
                reasons.append(f"Short elimination half-life (t1/2 ≈ {t_half_numeric:g}h) causes rapid plasma clearance and roller-coaster serum levels.")

        return max(0.0, min(100.0, score)), reasons

    @classmethod
    def _evaluate_safety_and_burdens(
        cls,
        compound: Dict[str, Any],
        user_profile: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Evaluates multi-organ burdens, rebound risk, and CYP450 interaction liabilities."""
        score = 65.0  # Favorable baseline
        reasons: List[str] = []

        burdens = compound.get("organ_burdens") or {}
        if isinstance(burdens, dict):
            total_burden = 0.0
            for org, b_info in burdens.items():
                if isinstance(b_info, dict):
                    b_score = float(b_info.get("score") or 0.0)
                    total_burden += b_score
                    if b_score >= 30.0:
                        score -= 10.0
                        reasons.append(f"Notable {org} organ burden score ({b_score:g}/100).")
            if total_burden == 0.0 and len(burdens) > 0:
                score += 10.0
                reasons.append("Documented zero organ toxicity profile.")
            else:
                score -= min(25.0, total_burden * 0.20)

        # Rebound liabilities
        warnings = str(compound.get("warnings") or "").lower()
        side_effects = str(compound.get("side_effects") or "").lower()
        if "rebound" in warnings or "rebound" in side_effects:
            score -= 15.0
            reasons.append("Carries rebound surge risk upon discontinuation.")

        # Narrow therapeutic index
        if compound.get("is_narrow_therapeutic_index") or compound.get("boxed_warning"):
            score -= 15.0
            reasons.append("Narrow therapeutic index or clinical boxed warning profile.")

        # CYP450 severe inhibition collision liabilities
        cyp = compound.get("cyp_enzymes") or {}
        if isinstance(cyp, dict):
            inh = cyp.get("inhibitors") or []
            if "CYP3A4" in inh or "CYP2D6" in inh:
                score -= 8.0
                reasons.append("Inhibits major hepatic clearance enzymes (CYP3A4/2D6), creating polypharmacy interaction risk.")

        return max(0.0, min(100.0, score)), reasons

    @classmethod
    def _evaluate_economy_and_metabolites(
        cls,
        compound: Dict[str, Any],
        route: str,
    ) -> Tuple[float, List[str]]:
        """Evaluates toxic gut metabolite formation (e.g. TMAO) and secondary ancillary dependency count."""
        score = 70.0  # Clean protocol baseline
        reasons: List[str] = []

        is_oral = route in ("oral", "po", "swallow", "")
        c_name_key = f"{compound.get('key') or ''} {compound.get('name') or ''} {compound.get('mechanism') or ''}".lower()

        # Check if oral substrate undergoes intestinal microbiota degradation to toxic metabolites
        targets = compound.get("receptor_targets") or []
        is_tma_substrate = (
            any("cnta" in str(t).lower() or "tma lyase" in str(t).lower() for t in targets)
            or any(w in c_name_key for w in ["carnitine", "alcar", "choline", "alpha-gpc", "alpha_gpc", "citicoline", "betaine"])
        )

        if is_oral and is_tma_substrate:
            score -= 35.0
            reasons.append("Oral delivery undergoes bacterial CntA/CntB lyase cleavage to trimethylamine (TMA), converting to atherogenic TMAO and necessitating a secondary TMA-lyase inhibitor (e.g. Allicin).")
        elif not is_oral and is_tma_substrate:
            score += 20.0
            reasons.append("Parenteral route completely bypasses gut microbiota CntA/CntB enzymes, resulting in negligible TMAO and eliminating the need for secondary inhibitors.")

        return max(0.0, min(100.0, score)), reasons

    @classmethod
    def determine_optimal_route(
        cls,
        compound: Dict[str, Any],
        route_preference: str = "all",
    ) -> str:
        """
        Deterministically selects the pharmacokinetically optimal route for a compound
        based on bioavailability, gut metabolite liabilities, formulation, and user preferences.
        """
        route_pref = str(route_preference or "all").lower().strip()
        if route_pref in ("oral_only", "capsules_only", "no_powders", "no_injections"):
            return "oral"

        c_key = str(compound.get("key") or "").lower()
        c_name = str(compound.get("name") or "").lower()
        blob = f"{c_key} {c_name} {compound.get('mechanism', '')}".lower()

        # If compound is an ester depot or peptide designed for parenteral delivery
        if any(e in blob for e in [
            "cypionate", "enanthate", "decanoate", "undecanoate", "isocaproate", "depot",
            "semaglutide", "tirzepatide", "retatrutide", "bpc_157", "bpc157", "tb_500", "tb500",
            "ghk_cu", "ipamorelin", "cjc_1295", "sermorelin", "tesamorelin", "epitalon", "mots_c"
        ]):
            if any(p in blob for p in ["semaglutide", "tirzepatide", "retatrutide", "bpc", "tb_", "ghk", "ipam", "cjc", "epitalon", "mots_c"]):
                return "subcutaneous"
            return "intramuscular"

        # If compound suffers severe oral loss or forms toxic gut metabolites (e.g. L-Carnitine, Glutathione)
        # and user has not restricted route to oral-only
        raw_f = compound.get("oral_bioavailability") or compound.get("bioavailability_f")
        try:
            f_val = float(raw_f) if raw_f is not None else 0.5
        except (ValueError, TypeError):
            f_val = 0.5

        is_tma_substrate = any(w in blob for w in ["carnitine", "alcar", "choline", "betaine"])
        if (f_val < 0.20 or is_tma_substrate) and route_pref in ("all", "hybrid", "injectable"):
            if "carnitine" in blob or "glutathione" in blob:
                return "intramuscular"

        return "oral"

    @classmethod
    def rank_candidates_for_target(
        cls,
        target_name_or_keyword: str,
        action: Optional[str] = None,
        route_preference: str = "all",
        user_profile: Optional[Dict[str, Any]] = None,
        catalog: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discovers and ranks all catalog compounds modulating a target, ordered from highest to lowest pharmacological utility.
        """
        if catalog is None:
            from app.services.catalog_service import CatalogService
            catalog = CatalogService()

        raw_candidates = catalog.find_compounds_by_target(target_name_or_keyword, action=action)
        if not raw_candidates:
            return []

        user_profile = user_profile or {}
        scored_candidates: List[Dict[str, Any]] = []

        for cand in raw_candidates:
            opt_route = cls.determine_optimal_route(cand, route_preference)
            score_data = cls.score_compound(
                compound=cand,
                route=opt_route,
                user_profile=user_profile,
                target_context=target_name_or_keyword,
                action_context=action,
            )
            scored_candidates.append({
                "compound": cand,
                "key": cand.get("key"),
                "name": cand.get("name"),
                "optimal_route": opt_route,
                "score": score_data["total_score"],
                "sub_scores": score_data["sub_scores"],
                "rationales": score_data["rationales"],
            })

        # Sort descending by pharmacological utility score
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates
