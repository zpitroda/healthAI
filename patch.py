import re

with open("app/services/stack_intent_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

new_extract_func = """    @classmethod
    def _has_atc_prefix(cls, compound: Dict[str, Any], prefixes: Tuple[str, ...]) -> bool:
        ext = compound.get("external_ids") or {}
        atc_codes = [str(c).upper() for c in (ext.get("atc_codes") or [])]
        return any(c.startswith(prefixes) for c in atc_codes)

    @classmethod
    def _extract_pharmacological_features(cls, compounds: List[Dict[str, Any]]) -> Dict[str, Any]:
        \"\"\"Extracts high-level pharmacological flags from compound catalog records algorithmically.\"\"\"
        features = {
            "has_androgens": False,
            "has_19nor_progestogenic": False,
            "has_aromatase_inhibitors": False,
            "has_aromatizable_substrate": False,
            "has_sarms": False,
            "has_serms": False,
            "has_raas_blockers": False,
            "has_beta_blockers": False,
            "has_pde5_inhibitors": False,
            "has_psychostimulants": False,
            "has_cholinergics": False,
            "has_gabaergics_sedatives": False,
            "has_longevity_metabolic": False,
            "has_hepatoprotectants": False,
            "has_lipid_regulators": False,
            "has_renal_support": False,
            "has_depot_injectables": False,
            "has_oral_tma_precursors": False,
            "has_microbial_tma_inhibitors": False,
            "has_prolactin_inhibitors": False,
            "has_phase2_conjugation_support": False,
            "has_biliary_clearance_support": False,
            "has_autonomic_buffer": False,
            "androgen_names": [],
            "oral_tma_precursor_names": [],
            "protective_ancillary_names": [],
        }

        for c in compounds:
            k = str(c.get("key", "")).lower()
            name = c.get("name") or k.title()
            route = str(c.get("route", "")).lower()
            cats = [str(cat).lower() for cat in (c.get("categories") or [])]
            mech = str(c.get("mechanism", "")).lower()
            
            targets = []
            for t in (c.get("receptor_targets") or []):
                if isinstance(t, dict):
                    targets.append(t)
                else:
                    targets.append({"target": str(t)})
                    
            def has_gene(symbols, actions=None):
                for t in targets:
                    if str(t.get("gene_symbol")).upper() in symbols:
                        if actions is None or str(t.get("action")).lower() in actions:
                            return True
                return False

            # Depot injectable detection
            is_depot = (
                route in ("intramuscular", "im", "subcutaneous", "subq") 
                or "depot" in cats
            )
            if is_depot:
                features["has_depot_injectables"] = True

            # Androgen / AAS detection
            is_androgen = (
                is_steroidal_androgen(c)
                or cls._has_atc_prefix(c, ("G03B", "G03BA", "G03BB", "A14A", "A14AA", "A14AB"))
                or has_gene({"AR", "NR3C4"}, {"agonist", "modulator", "partial agonist"})
                or "sarm" in cats
                or "anabolic agent" in cats
            )
            if is_androgen:
                features["has_androgens"] = True
                features["androgen_names"].append(name)
                if "sarm" in cats or not is_steroidal_androgen(c):
                    features["has_sarms"] = True

            # 19-nor progestogenic
            if cls._has_atc_prefix(c, ("A14AB",)) or "19-nor" in cats or "estren derivative" in cats or (is_androgen and has_gene({"PGR", "NR3C3"})):
                features["has_19nor_progestogenic"] = True

            # Aromatase inhibitor (AI)
            if cls._has_atc_prefix(c, ("L02BG",)) or has_gene({"CYP19A1"}, {"inhibitor", "antagonist"}) or "aromatase inhibitor" in cats:
                features["has_aromatase_inhibitors"] = True
                features["protective_ancillary_names"].append(name)

            # SERMs (Selective Estrogen Receptor Modulators)
            if cls._has_atc_prefix(c, ("G03XC", "L02BA")) or has_gene({"ESR1", "ESR2", "NR3A1", "NR3A2"}, {"modulator", "antagonist", "partial agonist"}) or "serm" in cats:
                features["has_serms"] = True
                features["protective_ancillary_names"].append(name)

            # Aromatizable substrate
            if is_aromatizable_androgen(c) or (is_androgen and cls._has_atc_prefix(c, ("G03BA03", "G03BA02"))):
                features["has_aromatizable_substrate"] = True

            # RAAS blockers
            is_raas = cls._has_atc_prefix(c, ("C09",)) or has_gene({"AGTR1", "ACE"}, {"antagonist", "inhibitor"})
            if is_raas:
                features["has_raas_blockers"] = True
                features["protective_ancillary_names"].append(name)

            # Beta blockers
            if cls._has_atc_prefix(c, ("C07",)) or has_gene({"ADRB1", "ADRB2", "ADRB3"}, {"antagonist"}) or "beta blocker" in cats:
                features["has_beta_blockers"] = True
                features["protective_ancillary_names"].append(name)

            # PDE5 inhibitors
            if cls._has_atc_prefix(c, ("G04BE",)) or has_gene({"PDE5A"}, {"inhibitor"}):
                features["has_pde5_inhibitors"] = True

            # Psychostimulants
            if cls._has_atc_prefix(c, ("N06B",)) or has_gene({"SLC6A2", "SLC6A3", "ADORA1", "ADORA2A"}, {"inhibitor", "antagonist", "reuptake inhibitor"}) or "stimulant" in cats:
                features["has_psychostimulants"] = True

            # Cholinergics
            if cls._has_atc_prefix(c, ("N06D",)) or has_gene({"ACHE", "CHRNA7"}) or "cholinergic" in cats or "nootropic" in cats:
                features["has_cholinergics"] = True

            # GABAergics / Sedatives
            if cls._has_atc_prefix(c, ("N05B", "N05C")) or has_gene({"GABRA1", "GABRB2", "MT1", "MT2", "MTNR1A", "MTNR1B"}) or any("gaba" in str(t.get("target")).lower() for t in targets) or "sedative" in cats:
                features["has_gabaergics_sedatives"] = True

            # Longevity / Metabolic
            if cls._has_atc_prefix(c, ("A10",)) or has_gene({"PRKAA1", "PRKAA2", "SIRT1", "MTOR"}) or "ampk activator" in cats or "longevity" in cats:
                features["has_longevity_metabolic"] = True

            # Hepatoprotectants
            if cls._has_atc_prefix(c, ("A05",)) or "hepatoprotectant" in cats or "liver therapy" in cats:
                features["has_hepatoprotectants"] = True
                features["protective_ancillary_names"].append(name)

            # Lipid regulators
            if cls._has_atc_prefix(c, ("C10",)) or has_gene({"HMGCR", "PCSK9", "NPC1L1"}) or "lipid modifying agent" in cats:
                features["has_lipid_regulators"] = True
                features["protective_ancillary_names"].append(name)

            # Renal support
            if is_raas or "renal support" in cats:
                features["has_renal_support"] = True

            # Oral TMA precursors
            is_oral_route = route in ("oral", "po", "swallow", "") or ":oral" in k
            is_parenteral = route in ("intramuscular", "im", "subcutaneous", "subq", "iv")
            is_tma_substrate = has_gene({"CNTA", "SLC22A5"}) or "tma precursor" in cats
            if is_oral_route and not is_parenteral and is_tma_substrate:
                features["has_oral_tma_precursors"] = True
                features["oral_tma_precursor_names"].append(name)

            # Microbial TMA lyase inhibitors
            if has_gene({"CNTA", "CNTB", "CUTC"}, {"inhibitor"}) or "tma lyase inhibitor" in cats:
                features["has_microbial_tma_inhibitors"] = True
                features["protective_ancillary_names"].append(name)

            # Prolactin inhibitors / Dopamine agonists
            if cls._has_atc_prefix(c, ("G02CB", "A11HA02")) or has_gene({"DRD2"}, {"agonist"}):
                features["has_prolactin_inhibitors"] = True

            # Phase II Conjugation (NAC)
            if cls._has_atc_prefix(c, ("R05CB01", "V03AB23")) or "glutathione biosynthesis" in mech or "acetylcysteine" in name.lower() or k == "nac":
                features["has_phase2_conjugation_support"] = True

            # Biliary Clearance (TUDCA)
            if cls._has_atc_prefix(c, ("A05AA",)) or "bile acid" in cats or "cholestasis" in mech or k in ("tudca", "udca"):
                features["has_biliary_clearance_support"] = True

            # Autonomic Buffer / Theanine
            if has_gene({"GRIN1", "GRIN2A", "GRIN2B", "GRIN2C", "GRIN2D"}, {"antagonist"}) or "autonomic buffer" in cats or k in ("l_theanine", "theanine", "agmatine"):
                features["has_autonomic_buffer"] = True

        return features"""

new_gaps_func = """    @classmethod
    def _detect_therapeutic_gaps(
        cls,
        features: Dict[str, Any],
        compounds: List[Dict[str, Any]],
        biometrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        \"\"\"
        Dynamically detects physiological vulnerabilities / uncompensated axes
        and prescribes evidence-based targeted co-factors.
        \"\"\"
        gaps = []

        # 1. 19-Nor Progestogenic / Prolactin Elevation
        if features.get("has_19nor_progestogenic"):
            if not features.get("has_prolactin_inhibitors"):
                gaps.append({
                    "axis": "Endocrine / Prolactin Axis",
                    "severity": "HIGH",
                    "issue": "19-Nor androgen present with PR affinity and risk of hyperprolactinemia.",
                    "recommended_cofactor": "Pyridoxal-5-Phosphate (P-5-P) 100–200 mg/day (or Cabergoline 0.25mg if prolactin is elevated)",
                    "cofactor_search_terms": ["p5p", "pyridoxal_5_phosphate", "cabergoline"],
                    "mechanism": "Cofactor for AADC, elevating dopamine synthesis to tonically suppress pituitary lactotroph prolactin release."
                })

        # 2. AAS-Induced Atherogenic Dyslipidemia (SR-B1 suppression, HDL crash, ApoB elevation)
        if features.get("has_androgens") and not features.get("has_lipid_regulators"):
            gaps.append({
                "axis": "Cardiovascular / Lipid Profile",
                "severity": "HIGH",
                "issue": "Androgenic downregulation of hepatic SR-B1 crushes HDL and increases atherogenic ApoB particle count.",
                "recommended_cofactor": "Citrus Bergamot Extract (500–1000 mg/day)",
                "cofactor_search_terms": ["citrus_bergamot", "bergamot", "ezetimibe"],
                "mechanism": "Upregulates LDL receptor clearance and inhibits HMG-CoA reductase to maintain endothelial health."
            })

        # 3. AAS Renal Glomerular Strain / Elevated Vascular Resistance
        if features.get("has_androgens") and not features.get("has_renal_support"):
            gaps.append({
                "axis": "Renal Glomerular Microcirculation",
                "severity": "MODERATE",
                "issue": "Androgen receptor activation in renal tubules stimulates renin and increases glomerular filtration pressure.",
                "recommended_cofactor": "Telmisartan (20–40 mg/day) or Astragalus Root Extract",
                "cofactor_search_terms": ["telmisartan", "astragalus"],
                "mechanism": "Antagonizes AT1 receptors to dilate efferent renal arterioles and protect podocyte integrity."
            })

        # 4. AAS Hepatic Bile Acid & Phase II Conjugation Strain
        if features.get("has_androgens"):
            if features.get("has_phase2_conjugation_support") and not features.get("has_biliary_clearance_support"):
                gaps.append({
                    "axis": "Hepatobiliary / Cholestasis",
                    "severity": "MODERATE",
                    "issue": "NAC provides intracellular glutathione but does not resolve hydrophobic bile acid accumulation.",
                    "recommended_cofactor": "TUDCA (Tauroursodeoxycholic Acid) 250–500 mg/day",
                    "cofactor_search_terms": ["tudca", "tauroursodeoxycholic_acid", "udca"],
                    "mechanism": "Increases hydrophilic bile acid ratio, promotes biliary clearance, and mitigates canalicular cholestatic stress."
                })

        # 5. Aromatization & Estrogen (E2) Management
        if (features.get("has_androgens") or features.get("has_aromatizable_substrate")) and not features.get("has_aromatase_inhibitors") and not features.get("has_serms"):
            gaps.append({
                "axis": "Aromatization & Estrogen (E2) Management",
                "severity": "HIGH",
                "issue": "Aromatizable androgen present without active aromatase inhibition or estrogen receptor modulation. Risk of excessive CYP19A1 conversion to estradiol, gynecomastia, and fluid retention.",
                "recommended_cofactor": "Aromatase Inhibitor (Anastrozole 0.25–0.5 mg twice weekly or Exemestane 12.5 mg twice weekly) or SERM (Raloxifene 30–60 mg/day) as indicated by sensitive E2 blood panels.",
                "cofactor_search_terms": ["anastrozole", "exemestane", "letrozole", "raloxifene"],
                "mechanism": "Inhibits CYP19A1 aromatase to control serum estradiol (E2) in the healthy target window and prevent estrogenic side effects."
            })

        # 6. Aromatase Inhibitor Crash Protection
        if features.get("has_aromatase_inhibitors"):
            gaps.append({
                "axis": "Estrogen Balance (E2 Preservation)",
                "severity": "RULE",
                "issue": "Aromatase inhibitor is active; stacking additional secondary AIs risks severe hypoestrogenic crash.",
                "recommended_cofactor": "Do NOT add secondary aromatase inhibitors. Maintain target E2: 20–30 pg/mL.",
                "mechanism": "Preserves HDL synthesis, joint synovia, bone mineral density, and vascular compliance."
            })

        # 7. Psychostimulant Vasoconstriction & Sleep Hygiene
        if features.get("has_psychostimulants"):
            if not features.get("has_autonomic_buffer"):
                gaps.append({
                    "axis": "Autonomic / Psychostimulant Buffer",
                    "severity": "MODERATE",
                    "issue": "Central catecholamine drive induces peripheral alpha-1 vasoconstriction, elevated pulse, and sleep latency.",
                    "recommended_cofactor": "L-Theanine 100–200 mg (co-administered with stimulant) + strict 8–10h bedtime cutoff.",
                    "cofactor_search_terms": ["l_theanine", "theanine", "magnesium"],
                    "mechanism": "Antagonizes glutamate receptors and stimulates inhibitory GABA synthesis to smooth autonomic tone."
                })

        # 8. Female-Specific Androgen Sensitivity & Virilization Protection
        sex = str(biometrics.get("sex") or biometrics.get("gender") or "").lower().strip()
        if sex in ("female", "f", "woman") and features.get("has_androgens"):
            gaps.append({
                "axis": "Endocrine / Female Virilization Risk",
                "severity": "HIGH",
                "issue": "Exogenous androgenic exposure in female patient carries high risk of virilization (hyperandrogenism, voice deepening, clitoromegaly, hirsutism, and menstrual disruption).",
                "recommended_cofactor": "Titrate androgens to micro-doses (e.g. low-dose TRT 5–10 mg/week or Oxandrolone <= 5 mg/day) and monitor free androgen index / SHBG",
                "mechanism": "Female AR tissue sensitivity is significantly higher; avoid supra-physiological male dosing levels."
            })

        # 9. Gut Microbiota TMA/TMAO Axis (Oral L-Carnitine/Choline without Microbial Lyase Inhibition)
        if features.get("has_oral_tma_precursors") and not features.get("has_microbial_tma_inhibitors"):
            precursor_str = ", ".join(features.get("oral_tma_precursor_names") or ["Oral L-Carnitine/Choline"])
            gaps.append({
                "axis": "Gastrointestinal / Microbial TMAO Axis",
                "severity": "MODERATE",
                "issue": f"Oral TMA precursor active ({precursor_str}) without gut microbial TMA-lyase inhibition. Intestinal bacteria (CntA/CntB / yeaW/yeaX) cleave oral carnitine/choline to trimethylamine (TMA), oxidized by host hepatic FMO3 into atherogenic Trimethylamine N-Oxide (TMAO).",
                "recommended_cofactor": "Allicin (Garlic Extract / Allium sativum) 10–20 mg (or 600–1200 mg Aged Garlic Extract) daily with meals, or switch to parenteral (IM/SubQ) route to bypass intestinal microbiota.",
                "cofactor_search_terms": ["allicin", "garlic", "aged_garlic_extract", "garlic_extract"],
                "mechanism": "Inactivates bacterial CntA/CntB / CutC TMA-lyase enzymes, suppressing TMA and TMAO formation by >50% while preserving mitochondrial carnitine shuttle bioactivity."
            })

        return gaps"""

pattern1 = re.compile(r"    @classmethod\n    def _extract_pharmacological_features\(cls, compounds: List\[Dict\[str, Any\]\]\) -> Dict\[str, Any\]:.*?(?=    @classmethod\n    def _infer_primary_domain)", re.DOTALL)
text = pattern1.sub(new_extract_func + "\n\n", text)

pattern2 = re.compile(r"    @classmethod\n    def _detect_therapeutic_gaps\(\n        cls,\n        features: Dict\[str, Any\],\n        compounds: List\[Dict\[str, Any\]\],\n        biometrics: Dict\[str, Any\]\n    \) -> List\[Dict\[str, Any\]\]:.*?(?=    @classmethod\n    def _format_prompt_grounding)", re.DOTALL)
text = pattern2.sub(new_gaps_func + "\n\n", text)

with open("app/services/stack_intent_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
