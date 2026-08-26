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
    DistributionPercentiles,
    MetricDistribution,
    RoutePKParameters,
    MetaboliteProfile,
    TissuePartitionCoefficients,
    LysosomalTrappingInfo,
    CompoundDataLimitations,
    AllometricExtrapolation,
)


class PKPDEngine:
    """
    Continuous-Time Pharmacokinetics (PK) and Pharmacodynamics (PD) Simulation Engine.
    Implements:
    1. 1-Compartment & 2-Compartment Open Models (alpha-distribution & beta-elimination phases)
    2. Michaelis-Menten Non-Linear Capacity-Limited Elimination Kinetics
    3. Time-Resolved Dynamic DDI Collisions with continuous inhibitor concentration I(t)
    4. Multi-Dose Steady-State Accumulation Dynamics (Rac, PTF, Css,avg, AUC0-tau)
    5. Quantitative Drug-Drug Interaction (DDI) AUC Ratio (AUCR) and Cmax Surge Modeling
    6. Sigmoidal Emax Hill Pharmacodynamics & Dynamic Receptor Occupancy RO(t)
    7. Patient Biometric (Weight, eGFR, ALT/AST, Albumin) Clearance Scaling
    8. Therapeutic Window Safety Bounds (MEC, MTC, Therapeutic Index)
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
        is_steady_state = bool(request.steady_state)

        # Biometric patient characteristics (Track whether fields were specified or left unknown)
        is_sex_known = request.sex is not None and str(request.sex).strip() != ""
        is_age_known = request.age is not None
        is_weight_known = request.weight_kg is not None
        is_height_known = request.height_cm is not None

        sex = str(request.sex or "male").strip().lower()
        age = max(1, min(120, int(request.age if request.age is not None else 30)))
        weight_kg = max(20.0, float(request.weight_kg if request.weight_kg is not None else 70.0))
        height_cm = max(100.0, float(request.height_cm if request.height_cm is not None else 175.0))
        body_fat_pct = request.body_fat_pct

        # Base Coefficient of Variation (CV) for population distribution curves
        # Base PK CV = 25%, Base PD CV = 20%
        # If biometric parameters are unspecified/unknown, expand distribution uncertainty bands
        unknown_biometric_count = sum([not is_sex_known, not is_age_known, not is_weight_known, not is_height_known])
        cv_pk_scale = 0.25 + (unknown_biometric_count * 0.08)  # Up to 57% CV if all unknown
        cv_pd_scale = 0.20 + (unknown_biometric_count * 0.06)  # Up to 44% CV if all unknown

        # 1. Calculate Patient Biometrics (Lean Body Mass, Total Body Water, BMI, eGFR)
        height_m = height_cm / 100.0
        bmi = weight_kg / (height_m * height_m)

        if body_fat_pct is not None and body_fat_pct > 0:
            lbm_kg = weight_kg * (1.0 - (body_fat_pct / 100.0))
        else:
            # Boer equation for LBM
            if sex == "female":
                lbm_kg = (0.252 * weight_kg) + (0.473 * height_cm) - 48.3
            else:
                lbm_kg = (0.407 * weight_kg) + (0.267 * height_cm) - 19.2
        lbm_kg = max(15.0, min(weight_kg * 0.95, lbm_kg))

        # Watson equation for Total Body Water (TBW) in Liters
        if sex == "female":
            tbw_l = -2.097 + (0.1069 * height_cm) + (0.2466 * weight_kg)
        else:
            tbw_l = 2.447 - (0.09516 * age) + (0.1074 * height_cm) + (0.3362 * weight_kg)
        tbw_l = max(10.0, tbw_l)

        # Calculate eGFR if not specified (Cockcroft-Gault formula normalized)
        if request.egfr_ml_min is not None and float(request.egfr_ml_min) > 0:
            egfr = float(request.egfr_ml_min)
        else:
            # Default serum creatinine ~ 0.95 mg/dL
            cg_crcl = ((140.0 - age) * weight_kg) / (72.0 * 0.95)
            if sex == "female":
                cg_crcl *= 0.85
            egfr = max(15.0, min(150.0, cg_crcl))

        patient_biometrics = {
            "sex": sex if is_sex_known else "unspecified (default male)",
            "age_years": age if is_age_known else "unspecified (default 30)",
            "weight_kg": round(weight_kg, 1) if is_weight_known else "unspecified (default 70.0)",
            "height_cm": round(height_cm, 1) if is_height_known else "unspecified (default 175.0)",
            "bmi": round(bmi, 1),
            "lean_body_mass_kg": round(lbm_kg, 1),
            "total_body_water_l": round(tbw_l, 1),
            "egfr_ml_min": round(egfr, 1),
            "unknown_biometrics_count": unknown_biometric_count,
            "distribution_cv_multiplier": round(cv_pk_scale / 0.25, 2),
        }

        # 2. Resolve / Infer Core Quantitative PK Parameters
        pk = cls.extract_pk_parameters(compound)
        pd_params = cls.extract_pd_parameters(compound)

        logp = float(compound.get("logp") if compound.get("logp") is not None else 2.0)

        # Scale Volume of Distribution Vd based on lipophilicity vs hydrophilicity
        if logp > 3.0:
            # Lipophilic drug: distributes into fat mass as well as LBM
            v_d_total_l = max(0.5, pk.volume_of_distribution_l_kg * weight_kg)
        else:
            # Hydrophilic drug: distributes primarily into LBM / TBW
            standard_lbm_baseline = 55.0 if sex == "male" else 45.0
            lbm_scale_factor = lbm_kg / standard_lbm_baseline
            v_d_total_l = max(0.5, pk.volume_of_distribution_l_kg * 70.0 * lbm_scale_factor)

        # Base clearance scaling
        if pk.clearance_l_h_kg and pk.clearance_l_h_kg > 0:
            cl_base_l_h = pk.clearance_l_h_kg * weight_kg
        else:
            k_elim_base = math.log(2.0) / max(0.1, pk.t_half_h)
            cl_base_l_h = k_elim_base * v_d_total_l

        # Age-related clearance decline (approx 0.7% decline per year over age 40)
        age_decline_factor = max(0.6, 1.0 - (max(0, age - 40) * 0.007))

        fe = max(0.0, min(1.0, pk.renal_clearance_fraction))
        renal_factor = min(1.5, egfr / 100.0)

        alt = max(5.0, float(request.alt_u_l or 25.0))
        hepatic_factor = (0.6 if alt > 80 else (0.8 if alt > 45 else 1.0)) * age_decline_factor

        # Pharmacogenomics (PGx) intrinsic clearance scaling
        from app.services.pgx_engine import PGXEngine
        pgx_profile = {
            "cyp2d6_phenotype": request.cyp2d6_phenotype,
            "cyp2c19_phenotype": request.cyp2c19_phenotype,
            "cyp3a4_phenotype": request.cyp3a4_phenotype,
            "slco1b1_genotype": request.slco1b1_genotype,
            "comt_phenotype": request.comt_phenotype,
        }
        pgx_mult = PGXEngine.get_clearance_multiplier(compound, pgx_profile)
        hepatic_factor *= pgx_mult

        # Female CYP3A4 metabolic scaling adjustment (+15% intrinsic activity for female hepatic clearance)
        cyp_info = compound.get("cyp_enzymes") or {}
        cyp3a4_sub = any("CYP3A4" in str(s).upper() for s in (cyp_info.get("substrates") or [])) if isinstance(cyp_info, dict) else False
        if sex == "female" and cyp3a4_sub:
            hepatic_factor *= 1.15

        cl_renal = cl_base_l_h * fe * renal_factor
        cl_hepatic = cl_base_l_h * (1.0 - fe) * hepatic_factor
        cl_adjusted_l_h = max(0.01, cl_renal + cl_hepatic)

        # Patient Albumin scaling for free fraction fu
        albumin = max(1.5, min(6.0, float(request.serum_albumin_g_dl or 4.5)))
        fu_adjusted = max(0.001, min(1.0, pk.fraction_unbound * (4.5 / albumin)))

        # Static DDI AUCR and Cmax multipliers
        ddi_aucr, ddi_cmax_mult, interacting_enzymes = cls.calculate_ddi_shift(
            compound, co_compounds_data or []
        )

        from app.services.pkpd_enricher import PKPDEnricher
        route_calc = PKPDEnricher.calculate_route_pk_parameters(compound, route)

        f_route = route_calc["bioavailability_f"]
        k_a = route_calc["absorption_rate_ka"]
        first_pass_pct = route_calc["first_pass_hepatic_pct"]
        bypass_pct = route_calc["first_pass_bypass_pct"]
        metabolites_list = route_calc["metabolites"]

        # Compartments and Non-Linear Kinetics Configuration
        n_compartments = pk.number_of_compartments
        is_saturable = pk.is_saturable_elimination
        dynamic_ddi_active = len(co_compounds_data or []) > 0 and len(interacting_enzymes) > 0

        # Compartment Volumes and Micro-constants
        if n_compartments == 2:
            v1_total_l = max(0.2, (pk.v1_l_kg or (0.30 * pk.volume_of_distribution_l_kg)) * weight_kg)
            v2_total_l = max(0.3, (pk.v2_l_kg or (0.70 * pk.volume_of_distribution_l_kg)) * weight_kg)
            k12 = pk.k12 if pk.k12 is not None else 0.35
            k21 = pk.k21 if pk.k21 is not None else max(0.01, k12 * (v1_total_l / v2_total_l))
        else:
            v1_total_l = v_d_total_l
            v2_total_l = 0.0
            k12 = 0.0
            k21 = 0.0

        v_met_total_l = v1_total_l * 1.25
        k_el_met = max(0.02, math.log(2.0) / max(0.5, pk.t_half_h * 1.4))

        # Michaelis-Menten Parameters
        vmax_total_mg_h = (pk.vmax_mg_h_kg * weight_kg) if (is_saturable and pk.vmax_mg_h_kg) else 0.0
        km_ng_ml = pk.km_ng_ml or 5000.0

        # Build Inhibitor PK Profiles for Time-Resolved Dynamic DDI Collisions
        inhibitor_profiles = []
        if co_compounds_data:
            cyp_info = compound.get("cyp_enzymes") or {}
            substrates = [str(s).upper() for s in (cyp_info.get("substrates") or [])] if isinstance(cyp_info, dict) else []
            trans_info = compound.get("transporters") or {}
            trans_subs = [str(t).upper() for t in (trans_info.get("substrates") or [])] if isinstance(trans_info, dict) else []

            for other in co_compounds_data:
                if str(other.get("key")) == str(compound.get("key")):
                    continue
                other_pk = cls.extract_pk_parameters(other)
                other_cyp = other.get("cyp_enzymes") or {}
                other_trans = other.get("transporters") or {}

                is_inhibitor = False
                if isinstance(other_cyp, dict):
                    for inh in (other_cyp.get("inhibitors") or []):
                        if str(inh).upper() in substrates:
                            is_inhibitor = True
                            break
                if not is_inhibitor and isinstance(other_trans, dict):
                    for inh in (other_trans.get("inhibitors") or []):
                        if str(inh).upper() in trans_subs:
                            is_inhibitor = True
                            break

                if is_inhibitor:
                    inh_vd = max(1.0, other_pk.volume_of_distribution_l_kg * weight_kg)
                    inh_ke = max(0.001, math.log(2.0) / max(0.1, other_pk.t_half_h))
                    inh_ka = max(0.1, other_pk.absorption_rate_ka)
                    inh_f = max(0.05, min(1.0, other_pk.bioavailability_f))
                    inh_dose_mg = max(10.0, float(other.get("dose") or other.get("dose_mg") or 100.0))
                    inh_tau = max(1.0, float(other.get("dosing_interval_h") or 24.0))
                    inh_ki = other_pk.ki_ng_ml or 500.0

                    inhibitor_profiles.append({
                        "name": other.get("name") or other.get("key"),
                        "dose_factor": (inh_f * inh_dose_mg * 1000.0) / inh_vd,
                        "ka": inh_ka,
                        "ke": inh_ke,
                        "tau": inh_tau,
                        "ki": inh_ki,
                    })

        # PBPK Tissue Partitioning & Lysosomal Ion-Trapping Calculations
        kp_pbpk = cls.calculate_pbpk_tissue_partitions(compound, fu_adjusted, weight_kg)
        lyso_info = cls.calculate_lysosomal_trapping(compound)
        circadian_dose_time = float(request.circadian_dosing_time_h if request.circadian_dosing_time_h is not None else 8.0)
        enable_tolerance = bool(request.enable_receptor_tolerance)
        enable_pbpk = bool(request.enable_pbpk_tissues)

        # Pharmacodynamic parameters (Binding affinity, Hill coefficient, EC50)
        mw = float(compound.get("molecular_weight") or 350.0)
        primary_aff_nm = cls._get_primary_affinity_nm(pd_params)
        kd_ng_ml = (primary_aff_nm * mw) / 1000.0 if primary_aff_nm else 50.0
        ec50_ng_ml = (pd_params.ec50_nm * mw / 1000.0) if pd_params.ec50_nm else kd_ng_ml
        hill_gamma = max(0.5, pd_params.hill_coefficient)
        emax = max(10.0, pd_params.e_max)
        ec50_pow = math.pow(max(0.001, ec50_ng_ml), hill_gamma)

        mec = pd_params.mec_ng_ml or 10.0
        mtc = pd_params.mtc_ng_ml or 500.0
        if mtc <= mec:
            mtc = mec * 3.0

        ti = mtc / mec if mec > 0 else 3.0

        def get_inhibitor_conc(t: float) -> float:
            """Calculates instantaneous plasma concentration I(t) for co-administered inhibitors."""
            if not inhibitor_profiles:
                return 0.0
            total_i = 0.0
            for inh in inhibitor_profiles:
                t_mod = t % inh["tau"] if is_steady_state else t
                pre = inh["dose_factor"] * (inh["ka"] / max(0.01, inh["ka"] - inh["ke"]))
                if is_steady_state:
                    e_k = math.exp(-inh["ke"] * t_mod) / (1.0 - math.exp(-inh["ke"] * inh["tau"]))
                    e_a = math.exp(-inh["ka"] * t_mod) / (1.0 - math.exp(-inh["ka"] * inh["tau"]))
                    c_i = max(0.0, pre * (e_k - e_a))
                else:
                    c_i = max(0.0, pre * (math.exp(-inh["ke"] * t_mod) - math.exp(-inh["ka"] * t_mod)))
                total_i += c_i
            return total_i

        def get_instantaneous_clearance(t: float) -> float:
            """Calculates continuous time-dependent clearance CL(t) modulated by inhibitor I(t)."""
            i_t = get_inhibitor_conc(t)
            if i_t <= 0.0 or not inhibitor_profiles:
                return cl_adjusted_l_h

            primary_ki = inhibitor_profiles[0]["ki"]
            # Dynamic modulation: CL_int(t) = CL_0 / (1 + I(t) / Ki)
            mod_factor = 1.0 / (1.0 + (i_t / primary_ki))
            # Assume 75% metabolized via inhibited pathway
            cl_t = cl_adjusted_l_h * (0.25 + 0.75 * mod_factor)
            return max(0.005, cl_t)

        # 2. Coupled Biophysical ODE System for Continuous Simulation (RK4 Integrator)
        # State vector: y = [A_abs (mg), A_1 (mg), A_2 (mg), A_met (mg), E_rel (fraction 0-1), R_surf (fraction 0-1)]
        # y[0] = A_abs (depot absorption amount)
        # y[1] = A_1 (central compartment amount)
        # y[2] = A_2 (peripheral compartment amount)
        # y[3] = A_met (active metabolite amount)
        # y[4] = E_rel (active functional enzyme fraction E(t)/E0)
        # y[5] = R_surf (functional surface receptor density R_surf(t)/R0 reflecting tolerance)
        k_deg_enz = math.log(2.0) / 36.0  # 36 h enzyme de novo synthesis turnover half-life
        k_inact = 0.25
        k_i_app = 500.0
        k_recycle = 0.15
        k_internalize = 0.30

        def ode_derivatives(t: float, y: List[float]) -> List[float]:
            a_abs = max(0.0, y[0])
            a1 = max(0.0, y[1])
            a2 = max(0.0, y[2])
            a_met = max(0.0, y[3])
            e_rel = max(0.01, min(1.0, y[4]))
            r_surf = max(0.05, min(1.0, y[5]))

            c1_ng_ml = (a1 * 1000.0) / v1_total_l
            c_free_inst = c1_ng_ml * fu_adjusted

            # Circadian diurnal clearance variation (diurnal peak at 14:00 / 2 PM, trough at 02:00 / 2 AM)
            t_circ = (t + circadian_dose_time) % 24.0
            circ_mult = 1.0 + 0.15 * math.cos((2.0 * math.pi * (t_circ - 14.0)) / 24.0)

            # Elimination Rate (mg/h) modulated by active enzyme fraction and circadian rhythm
            cl_inst = get_instantaneous_clearance(t) * e_rel * circ_mult
            if is_saturable:
                # Michaelis-Menten: dC/dt = - Vmax * C / (Km + C)
                inhibition_mult = cl_inst / cl_adjusted_l_h
                elim_rate_mg_h = (vmax_total_mg_h * c1_ng_ml / (km_ng_ml + c1_ng_ml)) * inhibition_mult
            else:
                k10 = cl_inst / v1_total_l
                elim_rate_mg_h = k10 * a1

            da_abs_dt = -k_a * a_abs
            da1_dt = (k_a * a_abs) - elim_rate_mg_h - (k12 * a1) + (k21 * a2)
            da2_dt = (k12 * a1) - (k21 * a2) if n_compartments == 2 else 0.0
            da_met_dt = (0.45 * elim_rate_mg_h) - (k_el_met * a_met)

            # Enzyme Turnover & Mechanism-Based Inactivation (MBI) ODE
            # dE/dt = k_deg * (1 - E) - [k_inact * I(t) / (K_I + I(t))] * E
            i_t = get_inhibitor_conc(t)
            inact_term = (k_inact * i_t / (k_i_app + i_t)) if i_t > 0 else 0.0
            de_dt = (k_deg_enz * (1.0 - e_rel)) - (inact_term * e_rel)

            # Receptor Desensitization, Internalization & Tachyphylaxis ODE
            # dR_surf/dt = k_recycle * (1 - R_surf) - k_internalize * [C_free^gamma / (EC50^gamma + C_free^gamma)] * R_surf
            c_pow_inst = math.pow(max(0.0, c_free_inst), hill_gamma)
            occupancy_stimulus = c_pow_inst / (ec50_pow + c_pow_inst) if (ec50_pow + c_pow_inst) > 0 else 0.0
            dr_dt = (k_recycle * (1.0 - r_surf)) - (k_internalize * occupancy_stimulus * r_surf) if enable_tolerance else 0.0

            return [da_abs_dt, da1_dt, da2_dt, da_met_dt, de_dt, dr_dt]

        def rk4_step(t: float, y: List[float], dt: float) -> List[float]:
            k1 = ode_derivatives(t, y)
            y_k2 = [y[i] + 0.5 * dt * k1[i] for i in range(6)]
            k2 = ode_derivatives(t + 0.5 * dt, y_k2)
            y_k3 = [y[i] + 0.5 * dt * k2[i] for i in range(6)]
            k3 = ode_derivatives(t + 0.5 * dt, y_k3)
            y_k4 = [y[i] + dt * k3[i] for i in range(6)]
            k4 = ode_derivatives(t + dt, y_k4)

            return [
                max(0.0, y[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]))
                for i in range(6)
            ]

        # Multi-Dose / Steady-State Initialization
        fine_dt = 0.01  # 36 second numerical step for high precision
        ester_weight_factor = float(compound.get("ester_weight_factor") if compound.get("ester_weight_factor") is not None else 1.0)
        if ester_weight_factor <= 0 or ester_weight_factor > 1.0:
            ester_weight_factor = 1.0

        effective_active_dose_mg = dose_mg * ester_weight_factor
        init_dose_mg = effective_active_dose_mg * f_route
        first_pass_initial_met_mg = (effective_active_dose_mg * ((100.0 - bypass_pct) / 100.0) * 0.35) if route_calc["route_name"] in ["oral", "rectal"] else 0.0

        if compound.get("is_ester") or ester_weight_factor < 1.0 or compound.get("parent_compound_id"):
            patient_biometrics["ester_info"] = {
                "is_ester": bool(compound.get("is_ester", True)),
                "ester_name": compound.get("ester_name"),
                "parent_compound_id": compound.get("parent_compound_id"),
                "nominal_dose_mg": round(dose_mg, 2),
                "ester_weight_factor": round(ester_weight_factor, 3),
                "effective_active_dose_mg": round(effective_active_dose_mg, 2),
            }

        if route_calc["route_name"] == "intravenous":
            y_state = [0.0, init_dose_mg, 0.0, 0.0, 1.0, 1.0]
        else:
            y_state = [init_dose_mg, 0.0, 0.0, first_pass_initial_met_mg, 1.0, 1.0]

        if is_steady_state:
            # Run 12 dosing cycles to establish exact numerical steady-state
            cycles = 12
            for c in range(cycles):
                if c > 0:
                    if route_calc["route_name"] == "intravenous":
                        y_state[1] += init_dose_mg
                    else:
                        y_state[0] += init_dose_mg
                        y_state[3] += first_pass_initial_met_mg

                t_cycle = 0.0
                while t_cycle < tau:
                    step_dt = min(fine_dt, tau - t_cycle)
                    y_state = rk4_step(t_cycle, y_state, step_dt)
                    t_cycle += step_dt

            # Apply final dose for reported steady-state cycle
            if route_calc["route_name"] == "intravenous":
                y_state[1] += init_dose_mg
            else:
                y_state[0] += init_dose_mg
                y_state[3] += first_pass_initial_met_mg

        # 3. Simulate and Record Report Time Series
        steps = 120
        out_dt = duration / (steps - 1)
        time_series: List[TimePoint] = []
        time_in_window_count = 0
        time_in_toxic_count = 0
        time_subtherapeutic_count = 0

        cur_t = 0.0
        cur_y = list(y_state)

        for s in range(steps):
            target_t = s * out_dt

            while cur_t < (target_t - 1e-6):
                step_dt = min(fine_dt, target_t - cur_t)
                cur_y = rk4_step(cur_t, cur_y, step_dt)
                cur_t += step_dt

            c_p = (cur_y[1] * 1000.0) / v1_total_l
            c_tissue = (cur_y[2] * 1000.0) / v2_total_l if n_compartments == 2 else 0.0
            c_met = (cur_y[3] * 1000.0) / v_met_total_l
            e_act_pct = round(cur_y[4] * 100.0, 1)
            r_surf_pct = round(cur_y[5] * 100.0, 1)
            c_free = c_p * fu_adjusted

            cl_inst = get_instantaneous_clearance(target_t)
            i_conc = get_inhibitor_conc(target_t)

            ro = (c_free / (c_free + kd_ng_ml)) * 100.0 if (c_free + kd_ng_ml) > 0 else 0.0
            c_pow = math.pow(max(0.0, c_free), hill_gamma)
            ec50_pow = math.pow(max(0.001, ec50_ng_ml), hill_gamma)
            effect_raw = (emax * c_pow) / (ec50_pow + c_pow) if (ec50_pow + c_pow) > 0 else 0.0
            effect = effect_raw * cur_y[5] if enable_tolerance else effect_raw

            if c_p > mtc:
                time_in_toxic_count += 1
            elif c_p >= mec:
                time_in_window_count += 1
            else:
                time_subtherapeutic_count += 1

            # Inter-Individual Variability Distribution at time t (scaled CV if biometrics unknown)
            c_dist = cls._calculate_distribution_percentiles(c_p, cv=cv_pk_scale)
            eff_dist = cls._calculate_distribution_percentiles(effect, cv=cv_pd_scale, max_bound=100.0)

            # PBPK Tissue Concentrations
            c_brain = round(c_p * kp_pbpk.kp_brain, 2) if enable_pbpk else None
            c_liver = round(c_p * kp_pbpk.kp_liver, 2) if enable_pbpk else None
            c_kidney = round(c_p * kp_pbpk.kp_kidney, 2) if enable_pbpk else None
            c_muscle = round(c_p * kp_pbpk.kp_muscle, 2) if enable_pbpk else None
            c_adipose = round(c_p * kp_pbpk.kp_adipose, 2) if enable_pbpk else None

            time_series.append(
                TimePoint(
                    time_h=round(target_t, 2),
                    c_plasma_ng_ml=round(c_p, 2),
                    c_free_ng_ml=round(c_free, 2),
                    receptor_occupancy_pct=round(min(100.0, ro), 1),
                    effect_pct=round(min(100.0, effect), 1),
                    c_metabolite_ng_ml=round(c_met, 2),
                    c_tissue_ng_ml=round(c_tissue, 2) if n_compartments == 2 else None,
                    cl_instantaneous_l_h=round(cl_inst, 2),
                    inhibitor_conc_ng_ml=round(i_conc, 2) if inhibitor_profiles else None,
                    c_brain_ng_ml=c_brain,
                    c_liver_ng_ml=c_liver,
                    c_kidney_ng_ml=c_kidney,
                    c_muscle_ng_ml=c_muscle,
                    c_adipose_ng_ml=c_adipose,
                    active_enzyme_fraction_pct=e_act_pct,
                    surface_receptor_density_pct=r_surf_pct,
                    c_plasma_distribution=c_dist.percentiles,
                    effect_distribution=eff_dist.percentiles,
                )
            )

        # Calculate Summary Metrics
        c_max = max(p.c_plasma_ng_ml for p in time_series)
        t_max_ss = min(time_series, key=lambda p: (abs(p.c_plasma_ng_ml - c_max), p.time_h)).time_h

        tau_pts = [p for p in time_series if p.time_h <= tau + 1e-3]
        if not tau_pts:
            tau_pts = time_series

        c_min = tau_pts[-1].c_plasma_ng_ml
        auc_0_tau = sum(
            0.5 * (tau_pts[i].c_plasma_ng_ml + tau_pts[i + 1].c_plasma_ng_ml) * (tau_pts[i + 1].time_h - tau_pts[i].time_h)
            for i in range(len(tau_pts) - 1)
        )
        c_avg_ss = max(0.01, auc_0_tau / tau)
        ptf = ((c_max - c_min) / c_avg_ss) * 100.0 if is_steady_state else 0.0
        swing_ratio = round(c_max / max(0.001, c_min), 2) if is_steady_state and c_min > 0 else 1.0

        cl_effective_avg = (effective_active_dose_mg * f_route * 1000.0) / max(1.0, auc_0_tau)
        k_e_eff = max(0.0001, cl_effective_avg / v_d_total_l)
        t_half_effective_h = math.log(2.0) / k_e_eff

        if not is_steady_state:
            fluct_level = "STABLE"
            fluct_warning = None
        elif ptf >= 140.0 or swing_ratio >= 3.0:
            fluct_level = "VOLATILE"
            fluct_warning = (
                f"Severe steady-state peak-to-trough swing detected (PTF: {round(ptf, 1)}%, Cmax/Cmin: {swing_ratio}x). "
                f"Dosing interval tau={tau}h is wide relative to elimination t1/2 ({round(t_half_effective_h, 1)}h), "
                f"creating peak surges and deep trough crashes. Consider splitting total dosage into more frequent "
                f"administrations (e.g. twice-weekly, every-other-day, or daily) to stabilize circulating levels."
            )
        elif ptf >= 80.0 or swing_ratio >= 2.0:
            fluct_level = "HIGH"
            fluct_warning = (
                f"Significant steady-state peak-to-trough swing detected (PTF: {round(ptf, 1)}%, Cmax/Cmin: {swing_ratio}x). "
                f"Consider splitting the dose into higher frequency administrations to flatten peaks and elevate troughs."
            )
        elif ptf >= 50.0 or swing_ratio >= 1.5:
            fluct_level = "MODERATE"
            fluct_warning = f"Moderate steady-state fluctuation (PTF: {round(ptf, 1)}%, Cmax/Cmin: {swing_ratio}x)."
        else:
            fluct_level = "STABLE"
            fluct_warning = None

        rac = 1.0 / (1.0 - math.exp(-k_e_eff * tau)) if is_steady_state else 1.0

        pct_in_window = round((time_in_window_count / steps) * 100.0, 1)
        pct_toxic = round((time_in_toxic_count / steps) * 100.0, 1)
        pct_subtherapeutic = round((time_subtherapeutic_count / steps) * 100.0, 1)

        # Pharmacodynamic Hill Curve Points (0.001 to 1000x EC50)
        pd_conc_points: List[float] = []
        pd_effect_points: List[float] = []
        for p in range(40):
            exponent = -3.0 + (6.0 * (p / 39.0))
            conc_val = ec50_ng_ml * math.pow(10.0, exponent)
            cp = math.pow(conc_val, hill_gamma)
            eff_val = (emax * cp) / (ec50_pow + cp)
            pd_conc_points.append(round(conc_val, 3))
            pd_effect_points.append(round(eff_val, 2))

        # Overall Metric Distributions
        c_max_dist = cls._calculate_distribution_percentiles(c_max, cv=cv_pk_scale)
        c_avg_dist = cls._calculate_distribution_percentiles(c_avg_ss, cv=cv_pk_scale)
        auc_dist = cls._calculate_distribution_percentiles(auc_0_tau, cv=cv_pk_scale)
        clearance_dist = cls._calculate_distribution_percentiles(cl_effective_avg, cv=cv_pk_scale)
        half_life_dist = cls._calculate_distribution_percentiles(t_half_effective_h, cv=cv_pk_scale)

        parsed_mets = [MetaboliteProfile(**m) if isinstance(m, dict) else m for m in metabolites_list]

        from app.services.dosing_service import PreclinicalAllometricEngine
        limitations_dict = PreclinicalAllometricEngine.evaluate_compound_limitations(compound)
        data_limitations_obj = CompoundDataLimitations(
            has_human_trials=limitations_dict["has_human_trials"],
            has_human_pk=limitations_dict["has_human_pk"],
            has_chronic_toxicity_studies=limitations_dict["has_chronic_toxicity_studies"],
            has_cyp_metabolite_mapping=limitations_dict["has_cyp_metabolite_mapping"],
            known_limitations=limitations_dict["known_limitations"],
        )
        evidence_tier_val = str(limitations_dict.get("evidence_tier") or "regulatory_human_clinical").lower()
        human_data_present = limitations_dict["has_human_trials"]

        meta_dict = compound.get("metadata") or {}
        allometric_extrapolation_obj = None
        if not human_data_present:
            animal_dose = meta_dict.get("rodent_ed50_mg_kg") or meta_dict.get("preclinical_dose_mg_kg")
            if animal_dose is not None:
                allo_dict = PreclinicalAllometricEngine.calculate_hed(
                    animal_dose_mg_kg=float(animal_dose),
                    species=meta_dict.get("animal_species", "rat"),
                    human_weight_kg=weight_kg,
                )
                allometric_extrapolation_obj = AllometricExtrapolation(**allo_dict)

        return PKPDSimulationResponse(
            compound_key=request.compound_key,
            compound_name=comp_name,
            dose_mg=dose_mg,
            dosing_interval_h=tau,
            route=route_calc["route_name"],
            steady_state=is_steady_state,
            patient_biometrics=patient_biometrics,
            route_pk_details=RoutePKParameters(
                route_name=route_calc["route_name"],
                bioavailability_f=route_calc["bioavailability_f"],
                absorption_rate_ka=route_calc["absorption_rate_ka"],
                t_max_h=route_calc["t_max_h"],
                apparent_t_half_h=route_calc["apparent_t_half_h"],
                first_pass_hepatic_pct=route_calc["first_pass_hepatic_pct"],
                first_pass_bypass_pct=route_calc["first_pass_bypass_pct"],
                metabolites=parsed_mets,
            ),
            first_pass_metabolism_pct=route_calc["first_pass_hepatic_pct"],
            first_pass_bypass_pct=route_calc["first_pass_bypass_pct"],
            metabolites=parsed_mets,
            c_max_ng_ml=round(c_max, 2),
            t_max_h=round(t_max_ss, 2),
            c_min_trough_ng_ml=round(c_min, 2),
            c_avg_ss_ng_ml=round(c_avg_ss, 2),
            auc_0_tau_ng_h_ml=round(auc_0_tau, 2),
            accumulation_ratio=round(rac, 2),
            fluctuation_pct=round(ptf, 1),
            peak_to_trough_ratio=swing_ratio if is_steady_state else None,
            fluctuation_risk_level=fluct_level,
            fluctuation_warning=fluct_warning,
            elimination_half_life_effective_h=round(t_half_effective_h, 2),
            total_clearance_l_h=round(cl_effective_avg, 2),
            tissue_partition_coefficients=kp_pbpk,
            lysosomal_trapping=lyso_info,
            tachyphylaxis_tolerance_active=enable_tolerance,
            circadian_rhythm_active=True,
            c_max_distribution=c_max_dist,
            c_avg_distribution=c_avg_dist,
            auc_distribution=auc_dist,
            clearance_distribution=clearance_dist,
            half_life_distribution=half_life_dist,
            number_of_compartments=n_compartments,
            is_saturable_elimination=is_saturable,
            dynamic_ddi_active=dynamic_ddi_active,
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
            evidence_tier=evidence_tier_val,
            human_data_present=human_data_present,
            data_limitations=data_limitations_obj,
            allometric_extrapolation=allometric_extrapolation_obj,
        )

    @classmethod
    def calculate_pbpk_tissue_partitions(
        cls,
        compound: Dict[str, Any],
        fu_adjusted: float,
        weight_kg: float = 70.0,
    ) -> TissuePartitionCoefficients:
        """
        Rodgers-Rowland & Poulin-Theil biophysical tissue partition coefficient (Kp) model.
        Calculates equilibrium tissue:plasma concentration ratios based on:
        - Lipophilicity (LogP / octanol:water partition Po:w)
        - Ionization (pKa, acid/base fraction)
        - Plasma protein binding (unbound fraction fu)
        - Physiological lipid (neutral & phospholipids) and water composition of major tissues.
        """
        logp = float(compound.get("logp") if compound.get("logp") is not None else 2.0)
        pka = float(compound.get("pka") if compound.get("pka") is not None else 7.4)
        mw = float(compound.get("molecular_weight") if compound.get("molecular_weight") is not None else 350.0)
        fu = max(0.001, min(1.0, float(fu_adjusted)))

        p_ow = math.pow(10.0, max(-2.0, min(5.5, logp)))

        # Tissue physiological water and lipid volume fractions (Rodgers & Rowland 2006)
        tissue_comps = {
            "brain": {"w": 0.77, "nl": 0.051, "np": 0.040, "ap": 0.004},
            "liver": {"w": 0.70, "nl": 0.035, "np": 0.025, "ap": 0.003},
            "kidney": {"w": 0.76, "nl": 0.021, "np": 0.020, "ap": 0.003},
            "muscle": {"w": 0.76, "nl": 0.015, "np": 0.010, "ap": 0.001},
            "adipose": {"w": 0.15, "nl": 0.790, "np": 0.002, "ap": 0.0002},
        }
        w_plasma = 0.93

        kp_dict = {}
        for t_name, comp_data in tissue_comps.items():
            w_t = comp_data["w"]
            nl_t = comp_data["nl"]
            np_t = comp_data["np"]
            ap_t = comp_data["ap"]

            if t_name == "adipose":
                kp = fu * ((w_t / w_plasma) + (p_ow * nl_t / w_plasma) + ((0.3 * p_ow + 0.7) * np_t / w_plasma))
            else:
                base_part = (w_t / w_plasma) + (p_ow * nl_t / w_plasma) + ((0.3 * p_ow + 0.7) * np_t / w_plasma)
                if pka > 7.0:
                    ion_pair_factor = min(20.0, 1.0 + (pka - 7.0) * 1.5) * (ap_t / 0.003)
                    base_part += ion_pair_factor
                kp = fu * base_part

            # Brain Blood-Brain Barrier (BBB) permeability & P-gp / BCRP efflux transport correction
            if t_name == "brain":
                trans_info = compound.get("transporters") or {}
                trans_subs = [str(t).upper() for t in (trans_info.get("substrates") or [])] if isinstance(trans_info, dict) else []
                is_pgp_sub = any("P-GP" in s or "ABCB1" in s or "BCRP" in s or "ABCG2" in s for s in trans_subs)
                efflux_ratio = 3.5 if is_pgp_sub else (1.2 if mw > 450 else 1.0)
                tpsa = float(compound.get("tpsa") or 60.0)
                psa_factor = max(0.2, min(1.0, 1.2 - (tpsa / 140.0)))
                kp = (kp * psa_factor) / efflux_ratio

            kp_dict[t_name] = max(0.05, min(50.0, round(kp, 3)))

        return TissuePartitionCoefficients(
            kp_brain=kp_dict["brain"],
            kp_liver=kp_dict["liver"],
            kp_kidney=kp_dict["kidney"],
            kp_muscle=kp_dict["muscle"],
            kp_adipose=kp_dict["adipose"],
            method="Rodgers-Rowland / Poulin-Theil Biophysical Equation",
        )

    @classmethod
    def calculate_lysosomal_trapping(
        cls,
        compound: Dict[str, Any],
    ) -> LysosomalTrappingInfo:
        """
        Henderson-Hasselbalch biophysical calculation of lysosomal ion-trapping for basic xenobiotics.
        Lysosomal lumen pH ~ 4.8 vs Cytosolic pH ~ 7.2.
        R_lyso = (1 + 10^(pKa - 4.8)) / (1 + 10^(pKa - 7.2))
        """
        pka_val = compound.get("pka")
        logp = float(compound.get("logp") if compound.get("logp") is not None else 2.0)
        drug_class = str(compound.get("drug_class") or "").lower()

        if pka_val is not None:
            pka = float(pka_val)
        elif any(w in drug_class for w in ["amine", "antidepressant", "ssri", "snri", "tca", "opioid", "beta blocker", "amphetamine", "alkaloid"]):
            pka = 8.8
        else:
            pka = None

        if pka is not None and pka >= 6.5 and logp >= 1.0:
            ratio = (1.0 + math.pow(10.0, min(6.0, pka - 4.8))) / (1.0 + math.pow(10.0, min(6.0, pka - 7.2)))
            ratio_rounded = round(ratio, 2)
            is_lyso = ratio > 15.0
            v_lyso_fraction = 0.01
            f_cyto = 100.0 / (1.0 + v_lyso_fraction * (ratio - 1.0))
            f_cyto_pct = round(max(2.0, min(100.0, f_cyto)), 1)
        else:
            pka_clean = pka if pka is not None else None
            ratio_rounded = 1.0
            is_lyso = False
            f_cyto_pct = 100.0

        return LysosomalTrappingInfo(
            pka=pka,
            is_lysosomotropic=is_lyso,
            lysosomal_accumulation_ratio=ratio_rounded,
            cytosolic_free_fraction_pct=f_cyto_pct,
        )

    @classmethod
    def _calculate_distribution_percentiles(
        cls, median_val: float, cv: float = 0.25, max_bound: Optional[float] = None
    ) -> MetricDistribution:
        """
        Calculates log-normal probability distribution percentiles (p5, p25, p50, p75, p95)
        for inter-individual population variability modeling.
        Z-scores: p5 = -1.645, p25 = -0.6745, p50 = 0.0, p75 = +0.6745, p95 = +1.645
        """
        val = max(0.0001, float(median_val))
        sigma_log = math.sqrt(math.log(1.0 + cv * cv))
        mu_log = math.log(val)

        p5_val = math.exp(mu_log - (1.645 * sigma_log))
        p25_val = math.exp(mu_log - (0.6745 * sigma_log))
        p50_val = val
        p75_val = math.exp(mu_log + (0.6745 * sigma_log))
        p95_val = math.exp(mu_log + (1.645 * sigma_log))

        if max_bound is not None:
            p5_val = min(max_bound, p5_val)
            p25_val = min(max_bound, p25_val)
            p50_val = min(max_bound, p50_val)
            p75_val = min(max_bound, p75_val)
            p95_val = min(max_bound, p95_val)

        std_dev = val * cv
        return MetricDistribution(
            mean=round(val, 2),
            std_dev=round(std_dev, 2),
            percentiles=DistributionPercentiles(
                p5=round(p5_val, 2),
                p25=round(p25_val, 2),
                p50=round(p50_val, 2),
                p75=round(p75_val, 2),
                p95=round(p95_val, 2),
            ),
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

        phase2_info = substrate_compound.get("phase2_enzymes") or {}
        if not isinstance(phase2_info, dict):
            phase2_info = {}
        phase2_substrates = [str(p).upper() for p in phase2_info.get("substrates") or []]

        sub_text_lower = f"{substrate_compound.get('name', '')} {substrate_compound.get('key', '')} {substrate_compound.get('drug_class', '')}".lower()
        is_polyphenol = any(w in sub_text_lower for w in ["curcumin", "resveratrol", "quercetin", "polyphenol", "flavonoid", "astaxanthin", "coq10", "berberine"])

        if not substrates and not trans_substrates and not phase2_substrates and not is_polyphenol:
            return 1.0, 1.0, []

        # Fractional contribution of major enzymes (default equal split among substrates)
        n_subs = len(substrates)
        fm_map: Dict[str, float] = {sub: (0.75 / max(1, n_subs)) for sub in substrates}

        total_inhib_factor = 0.0
        interacting_enzymes = []

        for other in co_compounds:
            if str(other.get("key")) == str(substrate_compound.get("key")):
                continue

            other_text_lower = f"{other.get('name', '')} {other.get('key', '')} {other.get('drug_class', '')}".lower()
            is_piperine = any(w in other_text_lower for w in ["piperine", "bioperine", "black pepper"])
            is_st_john = any(w in other_text_lower for w in ["st john", "hypericum", "hyperforin"])

            # Special bioenhancer effect (Piperine boosts polyphenol / P-gp / UGT1A1 / CYP3A4 substrate AUC)
            if is_piperine and (is_polyphenol or "CYP3A4" in substrates or "P-GP" in trans_substrates or "UGT1A1" in phase2_substrates):
                total_inhib_factor += 0.65  # ~2.8x exposure multiplier
                interacting_enzymes.append(f"Intestinal P-gp & UGT1A1 Bioenhancement by {other.get('name') or 'Piperine'}")

            # Special PXR nuclear induction effect (St. John's Wort strongly induces CYP3A4, CYP2C9, P-gp)
            if is_st_john and ("CYP3A4" in substrates or "CYP2C9" in substrates or "P-GP" in trans_substrates):
                total_inhib_factor -= 0.60  # ~0.4x exposure reduction
                other_name = other.get('name') or "St. John's Wort"
                interacting_enzymes.append(f"Nuclear PXR Enzyme & P-gp Induction by {other_name}")

            other_cyp = other.get("cyp_enzymes") or {}
            if isinstance(other_cyp, dict):
                # Strong/moderate inhibitors
                for inh in other_cyp.get("inhibitors") or []:
                    inh_clean = str(inh).upper()
                    if inh_clean in substrates:
                        fm = fm_map.get(inh_clean, 0.4)
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

            # Phase II inhibitors (e.g. UGT1A1, UGT2B7)
            other_p2 = other.get("phase2_enzymes") or {}
            if isinstance(other_p2, dict):
                for p_inh in other_p2.get("inhibitors") or []:
                    p_clean = str(p_inh).upper()
                    if p_clean in phase2_substrates:
                        total_inhib_factor += 0.25
                        if p_clean not in interacting_enzymes:
                            interacting_enzymes.append(f"{p_clean} Glucuronidation Inhibition by {other.get('name') or other.get('key')}")

        aucr = 1.0 / max(0.15, 1.0 - total_inhib_factor)
        aucr = max(0.3, min(8.0, aucr))

        # Cmax increases with inhibition but dampened by absorption
        cmax_mult = math.sqrt(aucr) if aucr >= 1.0 else aucr

        return aucr, cmax_mult, interacting_enzymes

    @classmethod
    def extract_pk_parameters(cls, compound: Dict[str, Any]) -> PKParameters:
        """Extracts or rigorously estimates continuous numerical PK parameters from compound dictionary."""
        comp_key_lower = str(compound.get("key") or compound.get("name") or "").lower()

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

        # 2-Compartment Open Model Parameter Extraction & Benchmarking
        n_compartments = int(compound.get("number_of_compartments") or 1)
        v1_l_kg = compound.get("v1_l_kg")
        v2_l_kg = compound.get("v2_l_kg")
        k12_val = compound.get("k12")
        k21_val = compound.get("k21")

        if "amiodarone" in comp_key_lower:
            n_compartments = 2
            v1_l_kg = v1_l_kg or 1.5
            v2_l_kg = v2_l_kg or 60.0
            k12_val = k12_val or 0.15
            k21_val = k21_val or 0.005
            vd_val = max(vd_val, 61.5)
            th_val = max(th_val, 120.0)
        elif "diazepam" in comp_key_lower or "valium" in comp_key_lower:
            n_compartments = 2
            v1_l_kg = v1_l_kg or 0.4
            v2_l_kg = v2_l_kg or 0.8
            k12_val = k12_val or 0.50
            k21_val = k21_val or 0.20
            vd_val = max(vd_val, 1.2)
        elif "fentanyl" in comp_key_lower:
            n_compartments = 2
            v1_l_kg = v1_l_kg or 0.8
            v2_l_kg = v2_l_kg or 3.2
            k12_val = k12_val or 0.80
            k21_val = k21_val or 0.15
            vd_val = max(vd_val, 4.0)
        elif n_compartments == 2 or vd_val > 3.0 or (v1_l_kg is not None and v2_l_kg is not None):
            n_compartments = 2
            v1_l_kg = v1_l_kg or max(0.2, 0.30 * vd_val)
            v2_l_kg = v2_l_kg or max(0.5, 0.70 * vd_val)
            k12_val = k12_val or 0.35
            k21_val = k21_val or max(0.01, k12_val * (v1_l_kg / v2_l_kg))

        # Michaelis-Menten Non-Linear Elimination Parameter Extraction
        is_saturable = bool(compound.get("is_saturable_elimination", False))
        vmax_mg_h_kg = compound.get("vmax_mg_h_kg")
        km_ng_ml = compound.get("km_ng_ml")
        ki_ng_ml = compound.get("ki_ng_ml")

        if "phenytoin" in comp_key_lower or "dilantin" in comp_key_lower:
            is_saturable = True
            vmax_mg_h_kg = vmax_mg_h_kg or 0.30  # ~7.0 mg/kg/day
            km_ng_ml = km_ng_ml or 4000.0  # 4.0 mg/L
        elif "ethanol" in comp_key_lower or "alcohol" in comp_key_lower:
            is_saturable = True
            vmax_mg_h_kg = vmax_mg_h_kg or 100.0  # ~0.1 g/kg/h
            km_ng_ml = km_ng_ml or 100000.0  # 100.0 mg/L
        elif is_saturable or (vmax_mg_h_kg is not None and km_ng_ml is not None):
            is_saturable = True
            km_ng_ml = km_ng_ml or 5000.0
            if vmax_mg_h_kg is None:
                k_elim = math.log(2.0) / max(0.1, float(th_val))
                vmax_mg_h_kg = k_elim * vd_val * (km_ng_ml / 1000.0)

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
            number_of_compartments=n_compartments,
            v1_l_kg=v1_l_kg,
            v2_l_kg=v2_l_kg,
            k12=k12_val,
            k21=k21_val,
            is_saturable_elimination=is_saturable,
            vmax_mg_h_kg=vmax_mg_h_kg,
            km_ng_ml=km_ng_ml,
            ki_ng_ml=ki_ng_ml,
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

    @classmethod
    def calculate_circadian_receptor_occupancy(
        cls,
        compound: Dict[str, Any],
        dose_mg: float = 100.0,
        route: str = "oral",
        dosing_interval_h: float = 24.0,
        biometrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculates continuous circadian receptor occupancy RO(t) = Cu(t) / (Cu(t) + Kd) * 100%
        across 24-hour circadian windows:
        - T+2h: Morning Peak / Absorption (Cmax)
        - T+6h: Midday Sustained Plateau
        - T+10h: Afternoon Window
        - T+14h: Evening Window
        - T+18h: Bedtime Trough
        - T+24h: Pre-Dose Baseline
        """
        biometrics = biometrics or {}
        req = PKPDSimulationRequest(
            compound_key=compound.get("key", "compound"),
            dose_mg=dose_mg,
            dosing_interval_h=dosing_interval_h,
            simulation_duration_h=max(24.0, dosing_interval_h),
            route=route,
            steady_state=True,
            age=biometrics.get("age", 30),
            weight_kg=biometrics.get("weight_kg", 75.0),
            egfr=biometrics.get("egfr", 95.0),
            alt_u_l=biometrics.get("alt_u_l", 25.0),
            cyp2d6_phenotype=biometrics.get("cyp2d6_phenotype"),
            cyp2c19_phenotype=biometrics.get("cyp2c19_phenotype"),
            cyp3a4_phenotype=biometrics.get("cyp3a4_phenotype"),
            slco1b1_genotype=biometrics.get("slco1b1_genotype"),
            comt_phenotype=biometrics.get("comt_phenotype"),
        )
        sim = cls.simulate(compound, req)

        pd_params = cls.extract_pd_parameters(compound)
        pk_params = cls.extract_pk_parameters(compound)
        mw = float(compound.get("molecular_weight") or 300.0)
        fu = pk_params.fraction_unbound

        targets = pd_params.target_affinities
        if not targets:
            kd_nm = pd_params.ec50_nm or 25.0
            targets = [QuantitativeTargetAffinity(target_name="Primary Target", affinity_type="Kd", affinity_value_nm=kd_nm)]

        circadian_windows = [
            {"label": "Morning (T+2h Peak)", "time_h": 2.0},
            {"label": "Midday (T+6h Plateau)", "time_h": 6.0},
            {"label": "Afternoon (T+10h)", "time_h": 10.0},
            {"label": "Evening (T+14h)", "time_h": 14.0},
            {"label": "Bedtime (T+18h Trough)", "time_h": 18.0},
            {"label": "Next-Day (T+24h Pre-Dose)", "time_h": 24.0},
        ]

        target_results = []
        for tgt in targets[:4]:
            t_name = tgt.target_name
            kd_nm = max(0.01, float(tgt.affinity_value_nm))
            # Kd in ng/mL = (Kd_nM * MW) / 1000
            kd_ng_ml = (kd_nm * mw) / 1000.0

            window_occupancies = []
            for win in circadian_windows:
                t_h = win["time_h"]
                closest_pt = min(sim.time_series, key=lambda p: abs(p.time_h - t_h))
                c_free = closest_pt.c_free_ng_ml
                ro = (c_free / (c_free + kd_ng_ml) * 100.0) if (c_free + kd_ng_ml) > 0 else 0.0
                window_occupancies.append({
                    "window": win["label"],
                    "time_h": t_h,
                    "c_plasma_ng_ml": closest_pt.c_plasma_ng_ml,
                    "c_unbound_ng_ml": round(c_free, 2),
                    "receptor_occupancy_pct": round(min(100.0, max(0.0, ro)), 1),
                })

            target_results.append({
                "target_name": t_name,
                "affinity_nm": round(kd_nm, 2),
                "affinity_type": tgt.affinity_type,
                "action_type": tgt.action_type,
                "windows": window_occupancies,
                "peak_occupancy_pct": max(w["receptor_occupancy_pct"] for w in window_occupancies),
                "trough_occupancy_pct": min(w["receptor_occupancy_pct"] for w in window_occupancies),
            })

        return {
            "compound": sim.compound_name,
            "dose": f"{dose_mg} mg ({route})",
            "cmax_ng_ml": round(sim.c_max_ng_ml, 1),
            "effective_half_life_h": round(sim.elimination_half_life_effective_h, 1),
            "fraction_unbound_pct": round(fu * 100.0, 1),
            "targets": target_results,
        }
