from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.pkpd import (
    PKParameters,
    PDParameters,
    PKPDSimulationRequest,
    PKPDSimulationResponse,
    TimePoint,
    QuantitativeTargetAffinity,
    PathwayAnnotation,
)


class PKPDEngine:
    """
    Continuous-Time Pharmacokinetics (PK) and Pharmacodynamics (PD) Simulation Engine.
    Implements:
    1. 1-Compartment Bateman Oral & IV Bolus Absorption Models
    2. Multi-Dose Steady-State Accumulation Dynamics (Rac, PTF, Css,avg, AUC0-tau)
    3. Quantitative Drug-Drug Interaction (DDI) AUC Ratio (AUCR) and Cmax Surge Modeling
    4. Sigmoidal Emax Hill Pharmacodynamics & Dynamic Receptor Occupancy RO(t)
    5. Patient Biometric (Weight, eGFR, ALT/AST, Albumin) Clearance Scaling
    6. Therapeutic Window Safety Bounds (MEC, MTC, Therapeutic Index)
    """

    @classmethod
    def simulate(
        cls,
        compound: Dict[str, Any],
        request: PKPDSimulationRequest,
        co_compounds_data: Optional[List[Dict[str, Any]]] = None,
    ) -> PKPDSimulationResponse:
        comp_name = str(compound.get("name") or compound.get("canonical_name") or request.compound_key).strip().title()
        route = request.route.lower()
        dose_mg = max(0.1, float(request.dose_mg))
        tau = max(1.0, float(request.dosing_interval_h))
        duration = max(tau, min(168.0, float(request.simulation_duration_h)))
        weight_kg = max(20.0, float(request.weight_kg))
        is_steady_state = bool(request.steady_state)

        # 1. Resolve / Infer Core Quantitative PK Parameters
        pk = cls.extract_pk_parameters(compound)
        pd_params = cls.extract_pd_parameters(compound)

        # 2. Scale Volume of Distribution and Clearance to Patient
        v_d_total_l = max(1.0, pk.volume_of_distribution_l_kg * weight_kg)
        
        # Base clearance
        if pk.clearance_l_h_kg and pk.clearance_l_h_kg > 0:
            cl_base_l_h = pk.clearance_l_h_kg * weight_kg
        else:
            k_elim_base = math.log(2.0) / max(0.1, pk.t_half_h)
            cl_base_l_h = k_elim_base * v_d_total_l

        # Patient renal & hepatic scaling
        fe = max(0.0, min(1.0, pk.renal_clearance_fraction))
        egfr = max(10.0, float(request.egfr_ml_min or 95.0))
        renal_factor = min(1.5, egfr / 100.0)

        alt = max(5.0, float(request.alt_u_l or 25.0))
        hepatic_factor = 0.6 if alt > 80 else (0.8 if alt > 45 else 1.0)

        cl_renal = cl_base_l_h * fe * renal_factor
        cl_hepatic = cl_base_l_h * (1.0 - fe) * hepatic_factor
        cl_adjusted_l_h = max(0.01, cl_renal + cl_hepatic)

        # 3. Dynamic Drug-Drug Interaction (DDI) AUCR Calculation
        ddi_aucr, ddi_cmax_mult, interacting_enzymes = cls.calculate_ddi_shift(
            compound, co_compounds_data or []
        )

        # Effective clearance & elimination rate constant under DDI
        cl_effective_l_h = cl_adjusted_l_h / ddi_aucr
        k_e = max(0.0001, cl_effective_l_h / v_d_total_l)
        t_half_effective_h = math.log(2.0) / k_e

        # Bioavailability and absorption rate
        f_oral = 1.0 if route == "iv" else max(0.05, min(1.0, pk.bioavailability_f))
        k_a = 50.0 if route == "iv" else max(0.05, pk.absorption_rate_ka)

        # Prevent numerical singularity if k_a == k_e
        if abs(k_a - k_e) < 1e-4:
            k_a += 0.01

        # Patient Albumin scaling for free fraction fu
        albumin = max(1.5, min(6.0, float(request.serum_albumin_g_dl or 4.5)))
        fu_adjusted = max(0.001, min(1.0, pk.fraction_unbound * (4.5 / albumin)))

        # 4. Compute Steady-State Accumulation Metrics
        rac = 1.0 / (1.0 - math.exp(-k_e * tau)) if is_steady_state else 1.0
        auc_0_tau = (f_oral * dose_mg * 1000.0) / cl_effective_l_h
        c_avg_ss = auc_0_tau / tau

        # Tmax calculation
        if route == "iv":
            t_max_ss = 0.0
        elif is_steady_state:
            numerator = k_a * (1.0 - math.exp(-k_e * tau))
            denominator = k_e * (1.0 - math.exp(-k_a * tau))
            if numerator > 0 and denominator > 0 and (k_a - k_e) != 0:
                t_max_ss = math.log(numerator / denominator) / (k_a - k_e)
                t_max_ss = max(0.05, min(tau, t_max_ss))
            else:
                t_max_ss = max(0.1, pk.t_max_h)
        else:
            t_max_ss = math.log(k_a / k_e) / (k_a - k_e) if k_a > k_e else pk.t_max_h

        # Dose coefficient in ng/mL: Dose(mg) * 1000 / Vd(L)
        dose_factor = (f_oral * dose_mg * 1000.0) / v_d_total_l

        def calc_conc(t: float) -> float:
            if t < 0:
                return 0.0
            if is_steady_state:
                t_mod = t % tau
                if route == "iv":
                    c = dose_factor * (math.exp(-k_e * t_mod) / (1.0 - math.exp(-k_e * tau)))
                else:
                    pre = dose_factor * (k_a / (k_a - k_e))
                    e_k = math.exp(-k_e * t_mod) / (1.0 - math.exp(-k_e * tau))
                    e_a = math.exp(-k_a * t_mod) / (1.0 - math.exp(-k_a * tau))
                    c = pre * (e_k - e_a)
                return max(0.0, c)
            else:
                if route == "iv":
                    return max(0.0, dose_factor * math.exp(-k_e * t))
                else:
                    pre = dose_factor * (k_a / (k_a - k_e))
                    return max(0.0, pre * (math.exp(-k_e * t) - math.exp(-k_a * t)))

        c_max = calc_conc(t_max_ss) * ddi_cmax_mult
        c_min = calc_conc(tau) if is_steady_state else calc_conc(duration)
        ptf = ((c_max - c_min) / max(0.001, c_avg_ss)) * 100.0 if is_steady_state else 0.0

        # Molecular Weight for molar conversions
        mw = float(compound.get("molecular_weight") or 350.0)
        
        # Primary binding affinity for receptor occupancy Kd in ng/mL
        primary_aff_nm = cls._get_primary_affinity_nm(pd_params)
        kd_ng_ml = (primary_aff_nm * mw) / 1000.0 if primary_aff_nm else 50.0

        ec50_ng_ml = (pd_params.ec50_nm * mw / 1000.0) if pd_params.ec50_nm else kd_ng_ml
        hill_gamma = max(0.5, pd_params.hill_coefficient)
        emax = max(10.0, pd_params.e_max)

        # 5. Generate Continuous Time-Series Curve (100 Points)
        steps = 120
        dt = duration / (steps - 1)
        time_series: List[TimePoint] = []

        mec = pd_params.mec_ng_ml or (c_max * 0.25 if c_max > 0 else 10.0)
        mtc = pd_params.mtc_ng_ml or (c_max * 2.5 if c_max > 0 else 500.0)
        if mtc <= mec:
            mtc = mec * 3.0

        ti = mtc / mec if mec > 0 else 3.0

        time_in_window_count = 0
        time_in_toxic_count = 0
        time_subtherapeutic_count = 0

        for s in range(steps):
            t_curr = round(s * dt, 2)
            c_p = calc_conc(t_curr)
            c_free = c_p * fu_adjusted

            # Receptor Occupancy %: RO = Cfree / (Cfree + Kd) * 100
            ro = (c_free / (c_free + kd_ng_ml)) * 100.0 if (c_free + kd_ng_ml) > 0 else 0.0
            
            # Sigmoidal Emax Hill Model
            c_pow = math.pow(max(0.0, c_free), hill_gamma)
            ec50_pow = math.pow(max(0.001, ec50_ng_ml), hill_gamma)
            effect = (emax * c_pow) / (ec50_pow + c_pow) if (ec50_pow + c_pow) > 0 else 0.0

            if c_p > mtc:
                time_in_toxic_count += 1
            elif c_p >= mec:
                time_in_window_count += 1
            else:
                time_subtherapeutic_count += 1

            time_series.append(
                TimePoint(
                    time_h=t_curr,
                    c_plasma_ng_ml=round(c_p, 2),
                    c_free_ng_ml=round(c_free, 2),
                    receptor_occupancy_pct=round(min(100.0, ro), 1),
                    effect_pct=round(min(100.0, effect), 1),
                )
            )

        pct_in_window = round((time_in_window_count / steps) * 100.0, 1)
        pct_toxic = round((time_in_toxic_count / steps) * 100.0, 1)
        pct_subtherapeutic = round((time_subtherapeutic_count / steps) * 100.0, 1)

        # 6. Generate Pharmacodynamic Hill Curve Points (0.001 to 1000x EC50)
        pd_conc_points: List[float] = []
        pd_effect_points: List[float] = []
        for p in range(40):
            exponent = -3.0 + (6.0 * (p / 39.0))
            conc_val = ec50_ng_ml * math.pow(10.0, exponent)
            cp = math.pow(conc_val, hill_gamma)
            eff_val = (emax * cp) / (ec50_pow + cp)
            pd_conc_points.append(round(conc_val, 4))
            pd_effect_points.append(round(eff_val, 2))

        return PKPDSimulationResponse(
            compound_key=str(compound.get("key") or request.compound_key),
            compound_name=comp_name,
            dose_mg=dose_mg,
            dosing_interval_h=tau,
            route=route,
            steady_state=is_steady_state,
            c_max_ng_ml=round(c_max, 2),
            t_max_h=round(t_max_ss, 2),
            c_min_trough_ng_ml=round(c_min, 2),
            c_avg_ss_ng_ml=round(c_avg_ss, 2),
            auc_0_tau_ng_h_ml=round(auc_0_tau, 2),
            accumulation_ratio=round(rac, 2),
            fluctuation_pct=round(ptf, 1),
            elimination_half_life_effective_h=round(t_half_effective_h, 2),
            total_clearance_l_h=round(cl_effective_l_h, 2),
            ddi_auc_ratio=round(ddi_aucr, 2),
            ddi_cmax_multiplier=round(ddi_cmax_mult, 2),
            ddi_interacting_enzymes=interacting_enzymes,
            mec_ng_ml=round(mec, 2),
            mtc_ng_ml=round(mtc, 2),
            therapeutic_index=round(ti, 2),
            time_in_therapeutic_window_pct=pct_in_window,
            time_in_toxic_zone_pct=pct_toxic,
            time_subtherapeutic_pct=pct_subtherapeutic,
            time_series=time_series,
            pd_curve_concentrations=pd_conc_points,
            pd_curve_effects=pd_effect_points,
        )

    @classmethod
    def calculate_ddi_shift(
        cls,
        substrate_compound: Dict[str, Any],
        co_compounds: List[Dict[str, Any]],
    ) -> Tuple[float, float, List[str]]:
        """
        Calculates the quantitative Area Under the Curve Ratio (AUCR) and Cmax multiplier
        resulting from competitive CYP and transporter inhibition or induction.
        AUCR = 1 / [ (1 - sum(fm)) + sum( fm / (1 + [I]/Ki) ) ]
        """
        if not co_compounds:
            return 1.0, 1.0, []

        cyp_info = substrate_compound.get("cyp_enzymes") or {}
        if not isinstance(cyp_info, dict):
            cyp_info = {}
        substrates = [str(s).upper() for s in cyp_info.get("substrates") or []]

        trans_info = substrate_compound.get("transporters") or {}
        if not isinstance(trans_info, dict):
            trans_info = {}
        trans_substrates = [str(t).upper() for t in trans_info.get("substrates") or []]

        if not substrates and not trans_substrates:
            return 1.0, 1.0, []

        # Fractional contribution of major enzymes (default equal split among substrates)
        n_subs = len(substrates)
        fm_map: Dict[str, float] = {sub: (0.75 / max(1, n_subs)) for sub in substrates}

        total_inhib_factor = 0.0
        interacting_enzymes = []

        for other in co_compounds:
            if str(other.get("key")) == str(substrate_compound.get("key")):
                continue

            other_cyp = other.get("cyp_enzymes") or {}
            if isinstance(other_cyp, dict):
                # Strong/moderate inhibitors
                for inh in other_cyp.get("inhibitors") or []:
                    inh_clean = str(inh).upper()
                    if inh_clean in substrates:
                        fm = fm_map.get(inh_clean, 0.4)
                        # Assume clinical I/Ki ratio of 3.0 for strong/moderate catalog inhibitors
                        i_over_ki = 3.0
                        total_inhib_factor += fm * (1.0 - (1.0 / (1.0 + i_over_ki)))
                        if inh_clean not in interacting_enzymes:
                            interacting_enzymes.append(f"{inh_clean} Inhibition by {other.get('name') or other.get('key')}")

                # Inducers
                for ind in other_cyp.get("inducers") or []:
                    ind_clean = str(ind).upper()
                    if ind_clean in substrates:
                        fm = fm_map.get(ind_clean, 0.4)
                        total_inhib_factor -= fm * 0.6  # Speeds clearance
                        if ind_clean not in interacting_enzymes:
                            interacting_enzymes.append(f"{ind_clean} Induction by {other.get('name') or other.get('key')}")

            # Transporter inhibitors (e.g. P-gp, OATP1B1, BCRP)
            other_trans = other.get("transporters") or {}
            if isinstance(other_trans, dict):
                for t_inh in other_trans.get("inhibitors") or []:
                    t_clean = str(t_inh).upper()
                    if t_clean in trans_substrates:
                        total_inhib_factor += 0.25  # Reduces efflux clearance
                        if t_clean not in interacting_enzymes:
                            interacting_enzymes.append(f"{t_clean} Efflux Inhibition by {other.get('name') or other.get('key')}")

        aucr = 1.0 / max(0.15, 1.0 - total_inhib_factor)
        aucr = max(0.3, min(8.0, aucr))

        # Cmax increases with inhibition but dampened by absorption
        cmax_mult = math.sqrt(aucr) if aucr >= 1.0 else aucr

        return aucr, cmax_mult, interacting_enzymes

    @classmethod
    def extract_pk_parameters(cls, compound: Dict[str, Any]) -> PKParameters:
        """Extracts or rigorously estimates continuous numerical PK parameters from compound dictionary."""
        # Half life
        th_val = compound.get("t_half_numeric")
        if th_val is None or th_val <= 0:
            th_str = str(compound.get("half_life") or "")
            th_val = cls._parse_hours_from_string(th_str, default=6.0)

        # Bioavailability
        f_val = compound.get("bioavailability_f")
        if f_val is None or f_val <= 0:
            bio_raw = compound.get("oral_bioavailability") or compound.get("bioavailability_pct")
            if bio_raw is not None:
                try:
                    num = float(str(bio_raw).replace("%", "").split("-")[0].strip())
                    f_val = min(1.0, max(0.01, num / 100.0 if num > 1.0 else num))
                except ValueError:
                    f_val = 0.7
            else:
                f_val = 0.7

        # Volume of distribution
        vd_val = compound.get("volume_of_distribution_l_kg")
        if vd_val is None or vd_val <= 0:
            vd_raw = compound.get("volume_of_distribution")
            vd_val = cls._parse_vd_from_string(vd_raw, default=1.5)

        # Protein binding / fraction unbound
        fu_val = compound.get("fraction_unbound")
        ppb_val = compound.get("protein_binding_pct")
        if fu_val is None or fu_val <= 0:
            pb_raw = compound.get("protein_binding")
            if pb_raw is not None:
                try:
                    num = float(str(pb_raw).replace("%", "").split("-")[0].strip())
                    ppb_val = min(99.9, max(0.0, num if num > 1.0 else num * 100.0))
                    fu_val = max(0.001, (100.0 - ppb_val) / 100.0)
                except ValueError:
                    ppb_val = 80.0
                    fu_val = 0.20
            else:
                ppb_val = 80.0
                fu_val = 0.20

        # Absorption rate ka and Tmax
        tmax_val = compound.get("t_max_h") or 2.0
        ka_val = compound.get("absorption_rate_ka")
        if ka_val is None or ka_val <= 0:
            # Ka estimated from Tmax: approx 2.5 / Tmax
            ka_val = max(0.2, min(5.0, 2.5 / max(0.5, float(tmax_val))))

        # Renal clearance fraction
        fe_val = compound.get("renal_clearance_fraction")
        if fe_val is None:
            cr_routes = str(compound.get("clearance_routes") or "").lower()
            if "renal (100%)" in cr_routes or "renal (80%)" in cr_routes:
                fe_val = 0.85
            elif "renal" in cr_routes and ("hepatic" in cr_routes or "biliary" in cr_routes):
                fe_val = 0.35
            elif "hepatic" in cr_routes or "biliary" in cr_routes:
                fe_val = 0.05
            else:
                fe_val = 0.30

        # BCS class estimation
        logp = float(compound.get("logp") if compound.get("logp") is not None else 2.0)
        tpsa = float(compound.get("tpsa") if compound.get("tpsa") is not None else 60.0)
        bcs = compound.get("bcs_class")
        if not bcs:
            if logp < 3.0 and tpsa < 100.0:
                bcs = "Class I (High Sol, High Perm)"
            elif logp >= 3.0 and tpsa < 100.0:
                bcs = "Class II (Low Sol, High Perm)"
            elif logp < 3.0 and tpsa >= 100.0:
                bcs = "Class III (High Sol, Low Perm)"
            else:
                bcs = "Class IV (Low Sol, Low Perm)"

        return PKParameters(
            t_half_h=max(0.1, float(th_val)),
            bioavailability_f=max(0.01, min(1.0, float(f_val))),
            volume_of_distribution_l_kg=max(0.05, float(vd_val)),
            clearance_l_h_kg=compound.get("clearance_l_h_kg"),
            t_max_h=max(0.1, float(tmax_val)),
            fraction_unbound=max(0.001, min(1.0, float(fu_val))),
            protein_binding_pct=max(0.0, min(99.9, float(ppb_val or 80.0))),
            absorption_rate_ka=max(0.1, float(ka_val)),
            renal_clearance_fraction=max(0.0, min(1.0, float(fe_val))),
            bcs_class=bcs,
            pka=compound.get("pka"),
        )

    @classmethod
    def extract_pd_parameters(cls, compound: Dict[str, Any]) -> PDParameters:
        """Extracts quantitative PD parameters, target affinities, and Reactome pathways."""
        mec = compound.get("mec_ng_ml")
        mtc = compound.get("mtc_ng_ml")
        ti = compound.get("therapeutic_index")
        if ti and not mtc and mec:
            mtc = mec * ti

        affinities: List[QuantitativeTargetAffinity] = []
        raw_targets = compound.get("receptor_targets") or []
        if isinstance(raw_targets, list):
            for t in raw_targets:
                if isinstance(t, dict):
                    t_name = str(t.get("target") or t.get("name") or "Target")
                    raw_val = t.get("affinity_ki") or t.get("inhibition_ic50") or t.get("ec50")
                    try:
                        aff_val = float(raw_val) if (raw_val is not None and float(raw_val) > 0.0) else 10.0
                    except (ValueError, TypeError):
                        aff_val = 10.0
                    aff_type = "Ki" if t.get("affinity_ki") else ("IC50" if t.get("inhibition_ic50") else "EC50")
                    affinities.append(
                        QuantitativeTargetAffinity(
                            target_name=t_name,
                            target_chembl_id=t.get("target_id") or t.get("target_chembl_id"),
                            uniprot_id=t.get("accessions") or t.get("uniprot_id"),
                            affinity_type=aff_type,
                            affinity_value_nm=aff_val,
                            action_type=str(t.get("action") or "modulator"),
                        )
                    )

        pathways: List[PathwayAnnotation] = []
        raw_paths = compound.get("pathway_details") or []
        if isinstance(raw_paths, list):
            for p in raw_paths:
                if isinstance(p, dict):
                    pathways.append(
                        PathwayAnnotation(
                            pathway_id=str(p.get("id") or p.get("pathway_id")),
                            pathway_name=str(p.get("name") or p.get("pathway_name")),
                            database=str(p.get("database") or "Reactome"),
                        )
                    )

        primary_aff = affinities[0].affinity_value_nm if affinities else 25.0

        return PDParameters(
            mec_ng_ml=float(mec) if mec else None,
            mtc_ng_ml=float(mtc) if mtc else None,
            therapeutic_index=float(ti) if ti else (mtc / mec if mtc and mec else None),
            e_max=float(compound.get("e_max") or 100.0),
            ec50_nm=float(compound.get("ec50_nm") or primary_aff),
            ic50_nm=float(compound.get("ic50_nm") or primary_aff),
            hill_coefficient=float(compound.get("hill_coefficient") or 1.0),
            target_affinities=affinities,
            pathways=pathways,
        )

    @staticmethod
    def _get_primary_affinity_nm(pd_params: PDParameters) -> float:
        if pd_params.target_affinities:
            return pd_params.target_affinities[0].affinity_value_nm
        if pd_params.ec50_nm:
            return pd_params.ec50_nm
        if pd_params.ic50_nm:
            return pd_params.ic50_nm
        return 20.0

    @staticmethod
    def _parse_hours_from_string(text: str, default: float = 6.0) -> float:
        if not text:
            return default
        clean = text.lower().replace("hours", "").replace("hour", "").replace("hrs", "").replace("hr", "").replace("h", "")
        parts = clean.split("-")
        try:
            nums = [float(p.strip()) for p in parts if p.strip()]
            return sum(nums) / len(nums) if nums else default
        except ValueError:
            return default

    @staticmethod
    def _parse_vd_from_string(value: Any, default: float = 1.5) -> float:
        if value is None:
            return default
        text = str(value).lower().replace("l/kg", "").replace("liters", "").replace("l", "")
        try:
            num = float(text.split("-")[0].strip())
            # If absolute liters given (e.g. 380 L), convert to L/kg for standard 70kg human
            if num > 20.0:
                return round(num / 70.0, 2)
            return max(0.05, num)
        except ValueError:
            return default
