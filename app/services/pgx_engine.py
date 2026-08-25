from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("healthai.pgx_engine")

# CPIC / PharmGKB activity multipliers for hepatic intrinsic clearance (CL_int)
PGX_PHENOTYPE_MULTIPLIERS = {
    "cyp2d6": {
        "poor_metabolizer": 0.15,
        "pm": 0.15,
        "intermediate_metabolizer": 0.50,
        "im": 0.50,
        "normal_metabolizer": 1.00,
        "nm": 1.00,
        "extensive_metabolizer": 1.00,
        "em": 1.00,
        "rapid_metabolizer": 1.50,
        "rm": 1.50,
        "ultrarapid_metabolizer": 2.20,
        "um": 2.20,
    },
    "cyp2c19": {
        "poor_metabolizer": 0.20,
        "pm": 0.20,
        "intermediate_metabolizer": 0.60,
        "im": 0.60,
        "normal_metabolizer": 1.00,
        "nm": 1.00,
        "extensive_metabolizer": 1.00,
        "em": 1.00,
        "rapid_metabolizer": 1.40,
        "rm": 1.40,
        "ultrarapid_metabolizer": 2.00,
        "um": 2.00,
    },
    "cyp3a4": {
        "poor_metabolizer": 0.40,
        "pm": 0.40,
        "intermediate_metabolizer": 0.70,
        "im": 0.70,
        "normal_metabolizer": 1.00,
        "nm": 1.00,
        "hyper_inducer": 1.80,
    },
    "slco1b1": {
        "*1/*1": 1.00, # Normal hepatic OATP1B1 transporter uptake
        "*1/*5": 0.65, # Intermediate transporter uptake (approx 1.5x plasma AUC for statins)
        "*5/*5": 0.35, # Low transporter uptake (approx 2.5x plasma AUC, high myopathy risk)
        "poor_transporter": 0.35,
        "intermediate_transporter": 0.65,
        "normal_transporter": 1.00,
    },
    "comt": {
        "val_val": 1.50, # Fast catecholamine/dopamine breakdown (low baseline prefrontal dopamine)
        "val_met": 1.00, # Intermediate
        "met_met": 0.60, # Slow catecholamine breakdown (high baseline dopamine, sensitive to stimulant anxiety)
    }
}


class PGXEngine:
    """
    Pharmacogenomics (PGx) and Clinical Genetics Engine.
    Models inter-individual genetic variability across Phase I/II enzymes and transporters.
    """

    @classmethod
    def get_clearance_multiplier(
        cls,
        compound: Dict[str, Any],
        pgx_profile: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculates net hepatic/transporter clearance scaling factor based on the compound's
        primary CYP enzymes and the patient's PGx phenotype.
        """
        if not pgx_profile:
            return 1.0

        cyp_info = compound.get("cyp_enzymes") or compound.get("cyp_metabolism") or {}
        substrates = []
        if isinstance(cyp_info, dict):
            substrates = [str(s).upper() for s in (cyp_info.get("substrates") or [])]
        elif isinstance(cyp_info, list):
            substrates = [str(s).upper() for s in cyp_info]

        total_multiplier = 1.0
        weights_sum = 0.0

        # Check CYP2D6
        if any("2D6" in s for s in substrates):
            cyp2d6_pheno = str(pgx_profile.get("cyp2d6_phenotype") or pgx_profile.get("cyp2d6") or "").strip().lower()
            mult = PGX_PHENOTYPE_MULTIPLIERS["cyp2d6"].get(cyp2d6_pheno, 1.0)
            total_multiplier += mult
            weights_sum += 1.0

        # Check CYP2C19
        if any("2C19" in s for s in substrates):
            cyp2c19_pheno = str(pgx_profile.get("cyp2c19_phenotype") or pgx_profile.get("cyp2c19") or "").strip().lower()
            mult = PGX_PHENOTYPE_MULTIPLIERS["cyp2c19"].get(cyp2c19_pheno, 1.0)
            total_multiplier += mult
            weights_sum += 1.0

        # Check CYP3A4
        if any("3A4" in s for s in substrates):
            cyp3a4_pheno = str(pgx_profile.get("cyp3a4_phenotype") or pgx_profile.get("cyp3a4") or "").strip().lower()
            mult = PGX_PHENOTYPE_MULTIPLIERS["cyp3a4"].get(cyp3a4_pheno, 1.0)
            total_multiplier += mult
            weights_sum += 1.0

        if weights_sum > 0:
            return max(0.1, round((total_multiplier - 1.0) / weights_sum, 2))

        return 1.0

    @classmethod
    def evaluate_pgx_warnings(
        cls,
        compounds: List[Dict[str, Any]],
        pgx_profile: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Identifies specific clinical PGx clashes and dose calibrations.
        """
        warnings: List[Dict[str, Any]] = []
        if not pgx_profile or not compounds:
            return warnings

        cyp2d6 = str(pgx_profile.get("cyp2d6_phenotype") or pgx_profile.get("cyp2d6") or "").strip().lower()
        cyp2c19 = str(pgx_profile.get("cyp2c19_phenotype") or pgx_profile.get("cyp2c19") or "").strip().lower()
        slco1b1 = str(pgx_profile.get("slco1b1_genotype") or pgx_profile.get("slco1b1") or "").strip().lower()
        comt = str(pgx_profile.get("comt_phenotype") or pgx_profile.get("comt") or "").strip().lower()

        for comp in compounds:
            c_name = comp.get("name") or comp.get("canonical_name") or comp.get("key", "Compound")
            c_key = str(comp.get("key") or "").lower()
            cyp_info = comp.get("cyp_enzymes") or {}
            subs = [str(s).upper() for s in (cyp_info.get("substrates") or [])] if isinstance(cyp_info, dict) else []

            # 1. CYP2D6 Poor Metabolizer (e.g. Nebivolol, Propranolol, Fluoxetine, Dextromethorphan)
            if cyp2d6 in ("poor_metabolizer", "pm") and (any("2D6" in s for s in subs) or c_key in ("nebivolol", "propranolol", "fluoxetine", "atomoxetine")):
                warnings.append({
                    "gene": "CYP2D6",
                    "phenotype": "Poor Metabolizer (PM)",
                    "compound": c_name,
                    "severity": "HIGH",
                    "impact": f"Markedly reduced CYP2D6 clearance (~75-85% reduction); plasma AUC will surge significantly higher than standard population.",
                    "clinical_action": "Reduce initial starting dose by 50% and titrate slowly under resting heart rate / blood pressure monitoring.",
                })

            # 2. CYP2D6 Ultra-Rapid Metabolizer (Prodrug failure / rapid clearance)
            elif cyp2d6 in ("ultrarapid_metabolizer", "um") and any("2D6" in s for s in subs):
                warnings.append({
                    "gene": "CYP2D6",
                    "phenotype": "Ultra-Rapid Metabolizer (UM)",
                    "compound": c_name,
                    "severity": "MODERATE",
                    "impact": f"Accelerated hepatic clearance of {c_name}; standard doses may lead to sub-therapeutic plasma concentrations.",
                    "clinical_action": "Consider dosage increase or alternative non-CYP2D6 cleared agent.",
                })

            # 3. CYP2C19 Poor Metabolizer (e.g. Diazepam, Omeprazole, Citalopram)
            if cyp2c19 in ("poor_metabolizer", "pm") and (any("2C19" in s for s in subs) or c_key in ("diazepam", "citalopram", "escitalopram", "omeprazole")):
                warnings.append({
                    "gene": "CYP2C19",
                    "phenotype": "Poor Metabolizer (PM)",
                    "compound": c_name,
                    "severity": "HIGH",
                    "impact": f"Diminished CYP2C19 clearance capacity; prolonged half-life and elevated systemic exposure.",
                    "clinical_action": "Reduce dose by 25-50% and extend dosing interval.",
                })

            # 4. SLCO1B1 *5 Transporter Polymorphism (Statin Myopathy Risk)
            if slco1b1 in ("*5/*5", "*1/*5", "poor_transporter") and ("statin" in str(comp.get("drug_class", "")).lower() or c_key in ("atorvastatin", "simvastatin", "rosuvastatin", "pitavastatin")):
                warnings.append({
                    "gene": "SLCO1B1",
                    "phenotype": f"OATP1B1 Transporter Deficiency ({slco1b1})",
                    "compound": c_name,
                    "severity": "HIGH" if slco1b1 == "*5/*5" else "MODERATE",
                    "impact": "Impaired hepatic OATP1B1 uptake leads to circulating statin plasma accumulation and heightened statin-induced myopathy risk.",
                    "clinical_action": "Use low-dose Pitavastatin (1mg) or Ezetimibe (10mg) with CoQ10 (100-200mg) support.",
                })

            # 5. COMT Met/Met (Slow Catecholamine Breakdown & Stimulant Excitability)
            if comt in ("met_met", "slow") and ("stimulant" in str(comp.get("drug_class", "")).lower() or c_key in ("caffeine", "modafinil", "ephedrine", "yohimbine")):
                warnings.append({
                    "gene": "COMT (Val158Met)",
                    "phenotype": "Met/Met (Low Enzymatic Activity)",
                    "compound": c_name,
                    "severity": "MODERATE",
                    "impact": "Slow enzymatic degradation of prefrontal dopamine and norepinephrine; heightened susceptibility to stimulant jitters, tachycardia, and anxiety.",
                    "clinical_action": "Pair stimulants with higher ratio L-Theanine (2:1 Theanine:Caffeine) or reduce stimulant dose.",
                })

        return warnings
