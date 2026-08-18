import math
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx
from pydantic import BaseModel, ConfigDict

from app.knowledge_graph.models import BaseNode, EdgeData, EdgeType


BIOMARKER_CLINICAL_CALIBRATION: Dict[str, Dict[str, Any]] = {
    "bio_heart_rate": {
        "baseline": 70.0,
        "unit": "bpm",
        "gain_up": 85.0,     # Max sympathoadrenal chronotropic surge (+85 bpm -> 155 bpm)
        "gain_down": 32.0,   # Physiological intrinsic bradycardia floor (-32 bpm -> 38 bpm)
        "safe_lower": 50.0,
        "safe_upper": 90.0,
        "label": "Resting Heart Rate",
        "onset_days": 0.05,
        "half_time_days": 0.5,
        "time_to_steady_state_weeks": 0.3,
        "kinetic_profile": "rapid_autonomic",
        "time_course_description": "Immediate autonomic chronotropic response (equilibrates within hours to 1-2 days)",
    },
    "bio_blood_pressure": {
        "baseline": 120.0,
        "unit": "mmHg",
        "gain_up": 55.0,     # Pressor hypertensive ceiling (+55 mmHg -> 175 mmHg)
        "gain_down": 40.0,   # Vasodilatory hypotensive floor (-40 mmHg -> 80 mmHg)
        "safe_lower": 90.0,
        "safe_upper": 120.0,
        "label": "Systolic Blood Pressure",
        "onset_days": 0.1,
        "half_time_days": 0.75,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "rapid_autonomic",
        "time_course_description": "Rapid vascular tone & autonomic reactivity (equilibrates within 2-4 days)",
    },
    "bio_potassium": {
        "baseline": 4.2,
        "unit": "mEq/L",
        "gain_up": 2.2,      # Hyperkalemia ceiling (+2.2 mEq/L -> 6.4 mEq/L)
        "gain_down": 1.5,    # Hypokalemia floor (-1.5 mEq/L -> 2.7 mEq/L)
        "safe_lower": 3.5,
        "safe_upper": 5.0,
        "label": "Serum Potassium",
        "onset_days": 0.25,
        "half_time_days": 1.0,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "renal_electrolyte",
        "time_course_description": "Renal distal tubular electrolyte excretion (equilibrates in 2-3 days)",
    },
    "bio_qtc": {
        "baseline": 410.0,
        "unit": "ms",
        "gain_up": 140.0,    # hERG blockade prolongation ceiling (+140 ms -> 550 ms)
        "gain_down": 60.0,   # QTc shortening floor (-60 ms -> 350 ms)
        "safe_lower": 360.0,
        "safe_upper": 440.0,
        "label": "Corrected QT Interval (QTc)",
        "onset_days": 0.05,
        "half_time_days": 0.25,
        "time_to_steady_state_weeks": 0.2,
        "kinetic_profile": "rapid_autonomic",
        "time_course_description": "Immediate electrophysiological ventricular repolarization shift",
    },
    "bio_glucose": {
        "baseline": 90.0,
        "unit": "mg/dL",
        "gain_up": 60.0,
        "gain_down": 45.0,
        "safe_lower": 70.0,
        "safe_upper": 100.0,
        "label": "Fasting Blood Glucose",
        "onset_days": 0.1,
        "half_time_days": 0.5,
        "time_to_steady_state_weeks": 0.3,
        "kinetic_profile": "metabolic_incretin",
        "time_course_description": "Pancreatic insulin secretion and peripheral glucose utilization",
    },
    "bio_blood_glucose": {
        "baseline": 90.0,
        "unit": "mg/dL",
        "gain_up": 60.0,
        "gain_down": 45.0,
        "safe_lower": 70.0,
        "safe_upper": 100.0,
        "label": "Fasting Blood Glucose",
        "onset_days": 0.1,
        "half_time_days": 0.5,
        "time_to_steady_state_weeks": 0.3,
        "kinetic_profile": "metabolic_incretin",
        "time_course_description": "Pancreatic insulin secretion and peripheral glucose utilization",
    },
    "bio_hba1c": {
        "baseline": 5.4,
        "unit": "%",
        "gain_up": 2.5,
        "gain_down": 1.8,
        "safe_lower": 4.0,
        "safe_upper": 5.7,
        "label": "Hemoglobin A1c (HbA1c)",
        "onset_days": 14.0,
        "half_time_days": 45.0,
        "time_to_steady_state_weeks": 12.0,
        "kinetic_profile": "erythropoietic_turnover",
        "time_course_description": "Glycated hemoglobin reflecting ~120-day erythrocyte lifespan (8-12 weeks to peak)",
    },
    "bio_bleeding_risk": {
        "baseline": 0.15,
        "unit": "index",
        "gain_up": 0.85,
        "gain_down": 0.15,
        "safe_lower": 0.0,
        "safe_upper": 0.35,
        "label": "Bleeding Tendency Index",
        "onset_days": 0.5,
        "half_time_days": 2.0,
        "time_to_steady_state_weeks": 0.8,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Platelet inhibition & clotting factor synthesis turnover",
    },
    "bio_estradiol": {
        "baseline": 25.0,
        "unit": "pg/mL",
        "gain_up": 189.5,    # Supraphysiological aromatization ceiling (+120 pg/mL -> 145 pg/mL on 70mg plain unesterified testosterone)
        "gain_down": 23.5,   # Near-total AI aromatase suicide blockade floor (-23.5 pg/mL -> 1.5 pg/mL)
        "safe_lower": 15.0,
        "safe_upper": 45.0,
        "label": "Serum Estradiol (E2)",
        "onset_days": 0.5,
        "half_time_days": 2.0,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Steroidogenic aromatization and clearance kinetics (3-7 days to equilibrium)",
    },
    "bio_hematocrit": {
        "baseline": 45.0,
        "unit": "%",
        "gain_up": 14.0,
        "gain_down": 10.0,
        "safe_lower": 38.5,
        "safe_upper": 50.0,
        "label": "Blood Hematocrit",
        "onset_days": 7.0,
        "half_time_days": 21.0,
        "time_to_steady_state_weeks": 8.0,
        "kinetic_profile": "erythropoietic_turnover",
        "time_course_description": "Erythropoiesis-driven bone marrow reticulocyte maturation & RBC lifespan (6-12 weeks to peak)",
    },
    "bio_hemoglobin": {
        "baseline": 15.2,
        "unit": "g/dL",
        "gain_up": 4.5,
        "gain_down": 3.5,
        "safe_lower": 13.5,
        "safe_upper": 17.5,
        "label": "Hemoglobin Concentration",
        "onset_days": 7.0,
        "half_time_days": 21.0,
        "time_to_steady_state_weeks": 8.0,
        "kinetic_profile": "erythropoietic_turnover",
        "time_course_description": "Erythropoietic hemoglobin synthesis turnover (6-12 weeks to peak)",
    },
    "bio_testosterone": {
        "baseline": 650.0,
        "unit": "ng/dL",
        "gain_up": 5190.0,   # Supraphysiological androgen ceiling (+5150 ng/dL -> 5800 ng/dL on 70mg pure unesterified testosterone)
        "gain_down": 550.0,
        "safe_lower": 300.0,
        "safe_upper": 1000.0,
        "label": "Total Serum Testosterone",
        "onset_days": 0.25,
        "half_time_days": 1.5,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Circulating androgen levels reflecting exogenous absorption and HPTA suppression",
    },
    "bio_dht": {
        "baseline": 45.0,
        "unit": "ng/dL",
        "gain_up": 85.0,
        "gain_down": 40.0,
        "safe_lower": 30.0,
        "safe_upper": 85.0,
        "label": "Serum Dihydrotestosterone (DHT)",
        "onset_days": 0.5,
        "half_time_days": 2.0,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "5-alpha reductase enzymatic conversion and clearance kinetics (3-7 days)",
    },
    "bio_luteinizing_hormone": {
        "baseline": 5.0,
        "unit": "IU/L",
        "gain_up": 12.0,
        "gain_down": 4.8,
        "safe_lower": 1.5,
        "safe_upper": 9.3,
        "label": "Luteinizing Hormone (LH)",
        "onset_days": 1.0,
        "half_time_days": 3.0,
        "time_to_steady_state_weeks": 1.5,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Pituitary gonadotropin negative feedback suppression (1-2 weeks)",
    },
    "bio_fsh": {
        "baseline": 4.5,
        "unit": "IU/L",
        "gain_up": 10.0,
        "gain_down": 4.2,
        "safe_lower": 1.4,
        "safe_upper": 12.4,
        "label": "Follicle-Stimulating Hormone (FSH)",
        "onset_days": 1.0,
        "half_time_days": 3.5,
        "time_to_steady_state_weeks": 1.5,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Pituitary gonadotropin negative feedback suppression (1-2 weeks)",
    },
    "bio_hdl_c": {
        "baseline": 55.0,
        "unit": "mg/dL",
        "gain_up": 25.0,
        "gain_down": 35.0,
        "safe_lower": 40.0,
        "safe_upper": 90.0,
        "label": "Serum HDL Cholesterol",
        "onset_days": 3.0,
        "half_time_days": 12.0,
        "time_to_steady_state_weeks": 4.0,
        "kinetic_profile": "hepatic_lipid_remodeling",
        "time_course_description": "Hepatic SR-B1 and reverse cholesterol transport remodeling (3-6 weeks to peak)",
    },
    "bio_ldl_c": {
        "baseline": 85.0,
        "unit": "mg/dL",
        "gain_up": 65.0,
        "gain_down": 45.0,
        "safe_lower": 50.0,
        "safe_upper": 100.0,
        "label": "Serum LDL Cholesterol",
        "onset_days": 3.0,
        "half_time_days": 14.0,
        "time_to_steady_state_weeks": 4.0,
        "kinetic_profile": "hepatic_lipid_remodeling",
        "time_course_description": "Hepatic LDL receptor expression and apolipoprotein clearance (3-6 weeks)",
    },
    "bio_triglycerides": {
        "baseline": 100.0,
        "unit": "mg/dL",
        "gain_up": 85.0,
        "gain_down": 55.0,
        "safe_lower": 40.0,
        "safe_upper": 150.0,
        "label": "Serum Triglycerides",
        "onset_days": 3.0,
        "half_time_days": 10.0,
        "time_to_steady_state_weeks": 3.0,
        "kinetic_profile": "hepatic_lipid_remodeling",
        "time_course_description": "Hepatic VLDL secretion and intravascular lipolysis remodeling (2-4 weeks)",
    },
    "bio_crp": {
        "baseline": 0.5,
        "unit": "mg/L",
        "gain_up": 6.5,
        "gain_down": 0.4,
        "safe_lower": 0.0,
        "safe_upper": 1.0,
        "label": "High-Sensitivity C-Reactive Protein (hs-CRP)",
        "onset_days": 0.5,
        "half_time_days": 1.5,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Hepatic acute phase reactant synthesis (1-3 days to peak)",
    },
    "bio_testosterone": {
        "baseline": 650.0,
        "unit": "ng/dL",
        "gain_up": 850.0,
        "gain_down": 450.0,
        "safe_lower": 300.0,
        "safe_upper": 1000.0,
        "label": "Serum Total Testosterone",
        "onset_days": 1.0,
        "half_time_days": 4.0,
        "time_to_steady_state_weeks": 2.0,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Exogenous androgen pool expansion and endocrine distribution (1-2 weeks)",
    },
    "bio_gsh_redox_ratio": {
        "baseline": 100.0,
        "unit": "ratio",
        "gain_up": 60.0,
        "gain_down": 45.0,
        "safe_lower": 80.0,
        "safe_upper": 160.0,
        "label": "Glutathione Redox Ratio (GSH:GSSG)",
        "onset_days": 0.5,
        "half_time_days": 2.0,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Intracellular glutathione redox buffering and Nrf2 transcription",
    },
    "bio_mda": {
        "baseline": 1.2,
        "unit": "μmol/L",
        "gain_up": 1.8,
        "gain_down": 0.6,
        "safe_lower": 0.5,
        "safe_upper": 1.8,
        "label": "Malondialdehyde (Lipid Peroxidation)",
        "onset_days": 1.0,
        "half_time_days": 3.0,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Polyunsaturated fatty acid lipid peroxidation byproduct",
    },
    # 1. Hepatobiliary Domain
    "bio_alt": {
        "baseline": 24.0,
        "unit": "U/L",
        "gain_up": 68.0,
        "gain_down": 14.0,
        "safe_lower": 10.0,
        "safe_upper": 45.0,
        "label": "Alanine Aminotransferase (ALT)",
        "onset_days": 1.0,
        "half_time_days": 3.0,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "hepatic_enzymatic",
        "time_course_description": "Hepatocellular enzyme leakage and hepatic clearance (3-7 days to peak)",
    },
    "bio_ast": {
        "baseline": 22.0,
        "unit": "U/L",
        "gain_up": 56.0,
        "gain_down": 12.0,
        "safe_lower": 10.0,
        "safe_upper": 40.0,
        "label": "Aspartate Aminotransferase (AST)",
        "onset_days": 1.0,
        "half_time_days": 2.5,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "hepatic_enzymatic",
        "time_course_description": "Cytosolic and mitochondrial AST release from metabolic strain (2-5 days)",
    },
    "bio_total_bilirubin": {
        "baseline": 0.6,
        "unit": "mg/dL",
        "gain_up": 1.8,
        "gain_down": 0.4,
        "safe_lower": 0.2,
        "safe_upper": 1.2,
        "label": "Total Serum Bilirubin",
        "onset_days": 1.5,
        "half_time_days": 4.0,
        "time_to_steady_state_weeks": 1.5,
        "kinetic_profile": "biliary_clearance",
        "time_course_description": "Hepatic UGT1A1 glucuronidation & canalicular biliary excretion",
    },
    "bio_ggt": {
        "baseline": 20.0,
        "unit": "U/L",
        "gain_up": 55.0,
        "gain_down": 10.0,
        "safe_lower": 9.0,
        "safe_upper": 48.0,
        "label": "Gamma-Glutamyl Transferase (GGT)",
        "onset_days": 2.0,
        "half_time_days": 7.0,
        "time_to_steady_state_weeks": 2.0,
        "kinetic_profile": "hepatic_enzymatic",
        "time_course_description": "Biliary ductal epithelium and hepatic microsomal enzyme induction",
    },
    "bio_alp": {
        "baseline": 65.0,
        "unit": "U/L",
        "gain_up": 75.0,
        "gain_down": 25.0,
        "safe_lower": 40.0,
        "safe_upper": 129.0,
        "label": "Alkaline Phosphatase (ALP)",
        "onset_days": 2.0,
        "half_time_days": 7.0,
        "time_to_steady_state_weeks": 2.0,
        "kinetic_profile": "biliary_clearance",
        "time_course_description": "Canalicular membrane transport and osteobiliary remodeling",
    },
    # 2. Renal Hemodynamics & Tubular Domain
    "bio_serum_creatinine": {
        "baseline": 0.95,
        "unit": "mg/dL",
        "gain_up": 1.15,
        "gain_down": 0.35,
        "safe_lower": 0.6,
        "safe_upper": 1.3,
        "label": "Serum Creatinine",
        "onset_days": 0.5,
        "half_time_days": 1.5,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "renal_filtration",
        "time_course_description": "Glomerular filtration rate dynamics and tubular secretion (1-3 days)",
    },
    "bio_egfr": {
        "baseline": 105.0,
        "unit": "mL/min/1.73m²",
        "gain_up": 15.0,
        "gain_down": 45.0,
        "safe_lower": 90.0,
        "safe_upper": 125.0,
        "label": "Estimated Glomerular Filtration Rate (eGFR)",
        "onset_days": 0.5,
        "half_time_days": 1.5,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "renal_filtration",
        "time_course_description": "Glomerular hydraulic pressure and nephron filtration kinetics",
    },
    "bio_bun": {
        "baseline": 14.0,
        "unit": "mg/dL",
        "gain_up": 22.0,
        "gain_down": 7.0,
        "safe_lower": 7.0,
        "safe_upper": 20.0,
        "label": "Blood Urea Nitrogen (BUN)",
        "onset_days": 0.5,
        "half_time_days": 1.5,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "renal_filtration",
        "time_course_description": "Renal tubular urea reabsorption and protein catabolic state",
    },
    "bio_cystatin_c": {
        "baseline": 0.80,
        "unit": "mg/L",
        "gain_up": 0.70,
        "gain_down": 0.30,
        "safe_lower": 0.50,
        "safe_upper": 1.05,
        "label": "Serum Cystatin C",
        "onset_days": 0.5,
        "half_time_days": 2.0,
        "time_to_steady_state_weeks": 0.8,
        "kinetic_profile": "renal_filtration",
        "time_course_description": "Endogenous nucleated cell production & pure glomerular filtration",
    },
    # 3. Oxidative Stress & Redox Domain
    "bio_gsh_redox_ratio": {
        "baseline": 100.0,
        "unit": "index",
        "gain_up": 25.0,
        "gain_down": 65.0,
        "safe_lower": 80.0,
        "safe_upper": 140.0,
        "label": "Glutathione Redox Index (GSH:GSSG)",
        "onset_days": 0.5,
        "half_time_days": 1.5,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "cellular_redox",
        "time_course_description": "Intracellular reduced glutathione reserve and antioxidant capacity",
    },
    "bio_mda": {
        "baseline": 1.8,
        "unit": "μmol/L",
        "gain_up": 4.2,
        "gain_down": 0.8,
        "safe_lower": 1.0,
        "safe_upper": 2.5,
        "label": "Serum Malondialdehyde (MDA / Lipid Peroxidation)",
        "onset_days": 1.0,
        "half_time_days": 3.0,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "cellular_redox",
        "time_course_description": "Reactive oxygen species attack on polyunsaturated membrane phospholipids",
    },
    # 4. Myocardial & Cardiovascular Domain
    "bio_nt_probnp": {
        "baseline": 45.0,
        "unit": "pg/mL",
        "gain_up": 180.0,
        "gain_down": 25.0,
        "safe_lower": 0.0,
        "safe_upper": 125.0,
        "label": "N-Terminal Pro-B-Type Natriuretic Peptide (NT-proBNP)",
        "onset_days": 0.5,
        "half_time_days": 2.0,
        "time_to_steady_state_weeks": 0.8,
        "kinetic_profile": "cardiovascular_hemodynamics",
        "time_course_description": "Myocardial stretch, ventricular wall tension and volume overload signaling",
    },
    "bio_qtc": {
        "baseline": 410.0,
        "unit": "ms",
        "gain_up": 65.0,
        "gain_down": 30.0,
        "safe_lower": 360.0,
        "safe_upper": 450.0,
        "label": "Corrected QT Interval (QTc)",
        "onset_days": 0.1,
        "half_time_days": 0.5,
        "time_to_steady_state_weeks": 0.2,
        "kinetic_profile": "cardiac_electrophysiology",
        "time_course_description": "Ventricular repolarization duration and hERG channel kinetics",
    },
    # 5. Lipid Domain Expansion
    "bio_apob": {
        "baseline": 75.0,
        "unit": "mg/dL",
        "gain_up": 55.0,
        "gain_down": 35.0,
        "safe_lower": 40.0,
        "safe_upper": 90.0,
        "label": "Apolipoprotein B (ApoB)",
        "onset_days": 3.0,
        "half_time_days": 14.0,
        "time_to_steady_state_weeks": 4.0,
        "kinetic_profile": "hepatic_lipid_remodeling",
        "time_course_description": "Circulating atherogenic particle number (VLDL, IDL, and LDL particle count)",
    },
    # 6. Hematology Domain Expansion
    "bio_blood_viscosity": {
        "baseline": 4.0,
        "unit": "cP",
        "gain_up": 2.8,
        "gain_down": 1.2,
        "safe_lower": 3.2,
        "safe_upper": 4.8,
        "label": "Whole Blood Viscosity Index",
        "onset_days": 5.0,
        "half_time_days": 18.0,
        "time_to_steady_state_weeks": 6.0,
        "kinetic_profile": "erythropoietic_turnover",
        "time_course_description": "Microvascular shear rate resistance and red cell concentration dynamics",
    },
    "bio_platelets": {
        "baseline": 240.0,
        "unit": "10^3/μL",
        "gain_up": 180.0,
        "gain_down": 140.0,
        "safe_lower": 150.0,
        "safe_upper": 450.0,
        "label": "Platelet Count",
        "onset_days": 2.0,
        "half_time_days": 6.0,
        "time_to_steady_state_weeks": 2.0,
        "kinetic_profile": "hematologic_thrombopoiesis",
        "time_course_description": "Megakaryocyte thrombopoiesis & peripheral platelet consumption",
    },
    # 7. Neuroendocrine & Hormonal Domain
    "bio_cortisol": {
        "baseline": 14.0,
        "unit": "μg/dL",
        "gain_up": 18.0,
        "gain_down": 9.0,
        "safe_lower": 6.0,
        "safe_upper": 20.0,
        "label": "Morning Serum Cortisol",
        "onset_days": 0.25,
        "half_time_days": 1.0,
        "time_to_steady_state_weeks": 0.5,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Hypothalamic-Pituitary-Adrenal (HPA) axis stress pulsatility",
    },
    "bio_prolactin": {
        "baseline": 9.0,
        "unit": "ng/mL",
        "gain_up": 28.0,
        "gain_down": 6.0,
        "safe_lower": 2.0,
        "safe_upper": 18.0,
        "label": "Serum Prolactin",
        "onset_days": 0.5,
        "half_time_days": 1.5,
        "time_to_steady_state_weeks": 0.8,
        "kinetic_profile": "direct_endocrine",
        "time_course_description": "Lactotroph dopamine D2 receptor disinhibition & progestogenic drive",
    },
    "bio_shbg": {
        "baseline": 35.0,
        "unit": "nmol/L",
        "gain_up": 45.0,
        "gain_down": 25.0,
        "safe_lower": 15.0,
        "safe_upper": 55.0,
        "label": "Sex Hormone-Binding Globulin (SHBG)",
        "onset_days": 2.0,
        "half_time_days": 7.0,
        "time_to_steady_state_weeks": 2.5,
        "kinetic_profile": "hepatic_protein_synthesis",
        "time_course_description": "Hepatic SHBG synthesis modulation by androgens, estrogens, and insulin",
    },
    # 8. Metabolic & Glycemic Domain
    "bio_fasting_insulin": {
        "baseline": 7.0,
        "unit": "μIU/mL",
        "gain_up": 22.0,
        "gain_down": 4.5,
        "safe_lower": 2.0,
        "safe_upper": 15.0,
        "label": "Fasting Serum Insulin",
        "onset_days": 0.5,
        "half_time_days": 2.0,
        "time_to_steady_state_weeks": 1.0,
        "kinetic_profile": "metabolic_incretin",
        "time_course_description": "Pancreatic beta-cell secretion and peripheral insulin sensitivity",
    },
    "bio_homa_ir": {
        "baseline": 1.5,
        "unit": "index",
        "gain_up": 4.5,
        "gain_down": 0.9,
        "safe_lower": 0.5,
        "safe_upper": 2.5,
        "label": "HOMA-IR (Insulin Resistance Index)",
        "onset_days": 1.0,
        "half_time_days": 3.5,
        "time_to_steady_state_weeks": 1.5,
        "kinetic_profile": "metabolic_incretin",
        "time_course_description": "Homeostatic Model Assessment of peripheral insulin resistance",
    },
    # 9. Neurochemical Domain
    "bio_dopamine_tone": {
        "baseline": 65.0,
        "unit": "index",
        "gain_up": 45.0,
        "gain_down": 35.0,
        "safe_lower": 40.0,
        "safe_upper": 90.0,
        "label": "Central Dopaminergic Tone Index",
        "onset_days": 0.1,
        "half_time_days": 0.5,
        "time_to_steady_state_weeks": 0.3,
        "kinetic_profile": "synaptic_neurotransmission",
        "time_course_description": "Synaptic monoamine transporter reuptake and mesolimbic neurotransmission",
    },
    "bio_serotonin_tone": {
        "baseline": 60.0,
        "unit": "index",
        "gain_up": 50.0,
        "gain_down": 30.0,
        "safe_lower": 40.0,
        "safe_upper": 85.0,
        "label": "Synaptic Serotonergic Tone Index",
        "onset_days": 0.1,
        "half_time_days": 0.5,
        "time_to_steady_state_weeks": 0.3,
        "kinetic_profile": "synaptic_neurotransmission",
        "time_course_description": "Synaptic SERT occupancy and prefrontal serotonergic receptor activation",
    },
    "bio_cns_arousal": {
        "baseline": 60.0,
        "unit": "index",
        "gain_up": 35.0,
        "gain_down": 45.0,
        "safe_lower": 40.0,
        "safe_upper": 80.0,
        "label": "Central CNS Arousal State",
        "onset_days": 0.05,
        "half_time_days": 0.25,
        "time_to_steady_state_weeks": 0.2,
        "kinetic_profile": "rapid_autonomic",
        "time_course_description": "Ascending reticular activating system arousal and cortical vigilance",
    },
}


TIMELINE_HORIZONS: Dict[str, Dict[str, Any]] = {
    "1_day": {
        "key": "1_day",
        "label": "1 Day (Acute)",
        "days": 1.0,
        "description": "Immediate acute response, autonomic chronotropics, and rapid vascular tone reactivity",
    },
    "3_days": {
        "key": "3_days",
        "label": "3 Days (Early Adaptation)",
        "days": 3.0,
        "description": "Autonomic equilibrium, renal electrolyte excretion, and acute-phase reactant shifts",
    },
    "1_week": {
        "key": "1_week",
        "label": "1 Week (Sub-acute Tone)",
        "days": 7.0,
        "description": "Sub-acute receptor adaptation, endocrine feedback loops, transaminases, and glycemic shifts",
    },
    "2_weeks": {
        "key": "2_weeks",
        "label": "2 Weeks (Endocrine Equilibrium)",
        "days": 14.0,
        "description": "HPTA axis equilibrium, transaminase peak, and initial hepatic lipid remodeling",
    },
    "1_month": {
        "key": "1_month",
        "label": "1 Month (4 Weeks / Lipid Remodeling)",
        "days": 28.0,
        "description": "Hepatic lipid receptor remodeling, SHBG equilibrium, and 4-week clinical bloodwork milestone",
    },
    "2_months": {
        "key": "2_months",
        "label": "2 Months (8 Weeks / Reticulocyte Turn)",
        "days": 56.0,
        "description": "Bone marrow reticulocyte maturation and cumulative erythropoietic response",
    },
    "3_months": {
        "key": "3_months",
        "label": "3 Months (12 Weeks / HbA1c & RBC Turn)",
        "days": 84.0,
        "description": "Full ~120-day erythrocyte turnover (peak HbA1c, hematocrit, and long-term equilibrium)",
    },
    "steady_state": {
        "key": "steady_state",
        "label": "Steady State (Full Equilibrium)",
        "days": None,
        "description": "Theoretical asymptotic steady-state biological equilibrium (~100% response)",
    },
}


def parse_timeline_days(timeline: Optional[str | float | int] = None) -> Tuple[Optional[float], str, str]:
    """
    Parse a timeline spec (e.g. '1_day', '2_weeks', '1_month', 'steady_state', or numeric days)
    into (days_or_none, key, display_label).
    """
    if timeline is None:
        return None, "steady_state", "Steady State (Full Equilibrium)"

    if isinstance(timeline, (int, float)):
        d = float(timeline)
        if d <= 0 or d >= 365:
            return None, "steady_state", "Steady State (Full Equilibrium)"
        return d, f"{d:g}_days", f"{d:g} Day{'s' if d != 1 else ''}"

    t_str = str(timeline).strip().lower().replace("-", "_").replace(" ", "_")
    if t_str in TIMELINE_HORIZONS:
        meta = TIMELINE_HORIZONS[t_str]
        return meta["days"], meta["key"], meta["label"]

    if t_str in ["1d", "day_1", "1day"]:
        return 1.0, "1_day", "1 Day (Acute)"
    if t_str in ["3d", "day_3", "3days"]:
        return 3.0, "3_days", "3 Days (Early Adaptation)"
    if t_str in ["1w", "week_1", "1week", "7d", "7days"]:
        return 7.0, "1_week", "1 Week (Sub-acute Tone)"
    if t_str in ["2w", "week_2", "2weeks", "14d", "14days"]:
        return 14.0, "2_weeks", "2 Weeks (Endocrine Equilibrium)"
    if t_str in ["4w", "month_1", "1month", "28d", "30d", "month"]:
        return 28.0, "1_month", "1 Month (4 Weeks / Lipid Remodeling)"
    if t_str in ["8w", "month_2", "2months", "56d", "60d"]:
        return 56.0, "2_months", "2 Months (8 Weeks / Reticulocyte Turn)"
    if t_str in ["12w", "month_3", "3months", "84d", "90d"]:
        return 84.0, "3_months", "3 Months (12 Weeks / HbA1c & RBC Turn)"
    if t_str in ["full", "all", "equilibrium", "inf", "infinity"]:
        return None, "steady_state", "Steady State (Full Equilibrium)"

    try:
        val = float(t_str)
        if val > 0 and val < 365:
            return val, f"{val:g}_days", f"{val:g} Day{'s' if val != 1 else ''}"
    except ValueError:
        pass

    return None, "steady_state", "Steady State (Full Equilibrium)"


class BiologicalGraph:
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_node(self, node: BaseNode | Dict[str, Any], **kwargs: Any) -> None:
        if isinstance(node, BaseNode):
            payload = node.model_dump()
            payload.update(kwargs)
            self.graph.add_node(node.node_id, **payload)
        elif isinstance(node, dict):
            payload = dict(node)
            payload.update(kwargs)
            node_id = str(payload.get("node_id") or payload.get("id") or "unknown_node")
            self.graph.add_node(node_id, **payload)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType | str,
        edge_data: EdgeData | Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        type_str = edge_type.value if isinstance(edge_type, EdgeType) else str(edge_type)
        payload = {"edge_type": type_str}

        if edge_data is not None:
            if isinstance(edge_data, EdgeData):
                payload.update(edge_data.model_dump(exclude_none=True))
            elif isinstance(edge_data, dict):
                payload.update(edge_data)

        payload.update(kwargs)
        if "vector_magnitude" not in payload:
            payload["vector_magnitude"] = 1.0

        self.graph.add_edge(source_id, target_id, **payload)

    def get_node(self, node_id: str) -> Dict[str, Any]:
        return self.graph.nodes[node_id]

    def neighbors(self, node_id: str) -> List[str]:
        return list(self.graph.successors(node_id))

    def predecessors(self, node_id: str) -> List[str]:
        return list(self.graph.predecessors(node_id))

    def path_exists(self, source_id: str, target_id: str) -> bool:
        return nx.has_path(self.graph, source_id, target_id)

    def subgraph_from_node(self, node_id: str, max_depth: int = 2) -> "BiologicalGraph":
        if node_id not in self.graph:
            raise KeyError(f"Node '{node_id}' does not exist in the graph.")

        visited = {node_id}
        frontier = [node_id]
        depth_map = {node_id: 0}

        for _ in range(max_depth):
            next_frontier = []
            for current in frontier:
                for neighbor in self.graph.successors(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        depth_map[neighbor] = depth_map[current] + 1
                        next_frontier.append(neighbor)
                for predecessor in self.graph.predecessors(current):
                    if predecessor not in visited:
                        visited.add(predecessor)
                        depth_map[predecessor] = depth_map[current] + 1
                        next_frontier.append(predecessor)
            frontier = next_frontier
            if not frontier:
                break

        subgraph = BiologicalGraph()
        subgraph.graph.add_nodes_from((node, self.graph.nodes[node].copy()) for node in visited)
        subgraph.graph.add_edges_from(
            (source, target, self.graph.edges[source, target].copy())
            for source, target in self.graph.edges
            if source in visited and target in visited
        )

        return subgraph

    def propagate_cascade(
        self,
        start_node_ids: List[str] | str,
        max_depth: int = 5,
        affinity_decay: bool = True,
        combined_effects: Optional[Dict[str, Any]] = None,
        timeline: Optional[str | float | int] = None,
        timeline_days: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Dynamically traverses directed cascade paths starting from input compounds/ligands,
        multiplying signed directional vectors along paths (Sign(path) = ∏ sign(edge)),
        and computing predicted biomarker shifts, pathway activations, and phenotype probabilities.
        When combined_effects are provided, signal magnitude downstream of targets is calibrated
        to the target's exact dose-dependent receptor saturation and net activation (E_net).
        When timeline or timeline_days is specified (e.g. 1 day, 2 weeks, 1 month, steady state),
        calculates dynamic kinetic outcomes according to onset latency (t_onset) and turnover half-time (t_1/2).
        """
        effective_days, timeline_key, timeline_label = parse_timeline_days(
            timeline_days if timeline_days is not None else timeline
        )

        starts = [start_node_ids] if isinstance(start_node_ids, str) else list(start_node_ids)
        valid_starts: List[str] = []
        for raw_s in starts:
            s = (raw_s.get("key") or raw_s.get("name") or "") if isinstance(raw_s, dict) else str(raw_s).split(":")[0].strip()
            if not s:
                continue
            if s in self.graph:
                if s not in valid_starts:
                    valid_starts.append(s)
            else:
                # Resolve by label or case-insensitive ID match
                for n, d in self.graph.nodes(data=True):
                    if (
                        str(n).lower() == str(s).lower()
                        or str(d.get("label", "")).lower() == str(s).lower()
                        or str(d.get("canonical_key", "")).lower() == str(s).lower()
                    ):
                        if n not in valid_starts:
                            valid_starts.append(n)

        if not valid_starts:
            return {
                "activated_pathways": [],
                "biomarker_shifts": [],
                "phenotypes": [],
                "cascade_traces": [],
                "timeline": timeline_key,
                "timeline_days": effective_days,
                "timeline_label": timeline_label,
                "summary": "No active knowledge graph nodes found for the requested entities.",
            }

        biomarker_impacts: Dict[str, float] = {}
        pathway_impacts: Dict[str, float] = {}
        phenotype_impacts: Dict[str, float] = {}
        biomarker_contributions: Dict[str, Dict[str, float]] = {}
        biomarker_path_signals: Dict[str, Dict[str, List[float]]] = {}
        pathway_path_signals: Dict[str, Dict[str, List[float]]] = {}
        phenotype_path_signals: Dict[str, Dict[str, List[float]]] = {}
        traces: List[Dict[str, Any]] = []

        for start in valid_starts:
            stack: List[Tuple[str, List[str], float, List[Dict[str, Any]]]] = [(start, [start], 1.0, [])]

            while stack:
                curr, path, cum_mag, edge_trail = stack.pop()
                curr_data = self.graph.nodes[curr]
                curr_type = curr_data.get("node_type", "")

                if curr_type == "signaling_pathway":
                    pathway_path_signals.setdefault(curr, {}).setdefault(start, []).append(cum_mag)
                elif curr_type == "biomarker":
                    biomarker_path_signals.setdefault(curr, {}).setdefault(start, []).append(cum_mag)
                elif curr_type == "phenotype":
                    phenotype_path_signals.setdefault(curr, {}).setdefault(start, []).append(cum_mag)

                    traces.append({
                        "origin": start,
                        "origin_label": self.graph.nodes[start].get("label", start),
                        "endpoint": curr,
                        "endpoint_label": curr_data.get("label", curr),
                        "endpoint_type": curr_type,
                        "net_vector": round(cum_mag, 3),
                        "path": path,
                        "path_labels": [self.graph.nodes[p].get("label", p) for p in path],
                        "edge_types": [e.get("edge_type") for e in edge_trail],
                    })

                if len(path) > max_depth:
                    continue

                for succ in self.graph.successors(curr):
                    if succ in path:
                        continue

                    edge_attrs = self.graph.edges[curr, succ]
                    edge_mag = float(edge_attrs.get("vector_magnitude", 1.0))
                    edge_type = str(edge_attrs.get("edge_type", ""))

                    sign_mult = -1.0 if any(t in edge_type for t in ["INHIBIT", "ANTAGONIZ", "BLOCK", "REPRESS", "MITIGAT"]) else 1.0

                    succ_data = self.graph.nodes[succ]
                    succ_label = succ_data.get("label", succ)

                    if combined_effects and (succ in combined_effects or succ_label in combined_effects) and not edge_attrs.get("pre_computed_stress"):
                        c_target = combined_effects.get(succ) or combined_effects.get(succ_label)
                        matched_c = next((item for item in c_target.get("compounds", []) if str(item.get("compound_id", "")).lower() == start.lower() or str(item.get("compound_label", "")).lower() == start.lower()), None)
                        if matched_c:
                            abs_sat = float(matched_c.get("absolute_saturation_pct", 0.0)) / 100.0
                            eff = float(matched_c.get("intrinsic_efficacy", 1.0 if sign_mult > 0 else -1.0))
                            reg_mult = float(c_target.get("regulation_multiplier", 1.0))
                            next_mag = abs_sat * eff * reg_mult
                        else:
                            # Dynamic Upstream Cascade Bottlenecking & Potentiation at Receptors / Enzymes
                            target_net = float(c_target.get("net_activation_score", 0.0))
                            if target_net < -0.05:
                                # Target receptor/enzyme is in a blocked/inhibited state: bottleneck upstream signal
                                blockade_pass_through = max(0.05, 1.0 + target_net)
                                next_mag = cum_mag * (edge_mag if sign_mult > 0 else -abs(edge_mag)) * blockade_pass_through
                            elif target_net > 0.05:
                                # Target receptor/enzyme is in a stimulated state: amplify upstream throughput
                                potentiation = 1.0 + min(0.5, target_net * 0.5)
                                next_mag = cum_mag * (edge_mag if sign_mult > 0 else -abs(edge_mag)) * potentiation
                            else:
                                next_mag = cum_mag * (edge_mag if sign_mult > 0 else -abs(edge_mag))
                    else:
                        next_mag = cum_mag * (edge_mag if sign_mult > 0 else -abs(edge_mag))

                    if affinity_decay and "affinity_ki" in edge_attrs and not (combined_effects and (succ in combined_effects or succ_label in combined_effects)):
                        ki = float(edge_attrs["affinity_ki"])
                        next_mag *= max(0.2, min(1.0, 1.0 / (1.0 + (ki / 10.0))))

                    stack.append((succ, list(path) + [succ], next_mag, list(edge_trail) + [edge_attrs]))

        def _aggregate_compound_paths(paths: List[float]) -> float:
            if not paths:
                return 0.0
            pos = [p for p in paths if p > 0]
            neg = [p for p in paths if p < 0]
            m_pos = (max(pos) + 0.15 * sum(p for p in pos if p != max(pos))) if pos else 0.0
            m_neg = (min(neg) + 0.15 * sum(p for p in neg if p != min(neg))) if neg else 0.0
            return max(-1.0, min(1.0, m_pos + m_neg))

        # Compute Biomarker Impacts with Bounded Per-Compound Aggregation
        biomarker_impacts: Dict[str, float] = {}
        biomarker_contributions: Dict[str, Dict[str, float]] = {}
        for bio_id, start_map in biomarker_path_signals.items():
            biomarker_contributions[bio_id] = {}
            for c_id, p_list in start_map.items():
                biomarker_contributions[bio_id][c_id] = _aggregate_compound_paths(p_list)
            biomarker_impacts[bio_id] = max(-1.0, min(1.0, sum(biomarker_contributions[bio_id].values())))

        formatted_biomarkers = []
        for bio_id, net_mag in sorted(biomarker_impacts.items(), key=lambda x: abs(x[1]), reverse=True):
            bio_data = self.graph.nodes[bio_id]
            calib = BIOMARKER_CLINICAL_CALIBRATION.get(bio_id)
            if calib:
                baseline, unit = float(calib["baseline"]), str(calib["unit"])
                gain = float(calib["gain_up"] if net_mag >= 0 else calib["gain_down"])
                safe_lower, safe_upper = float(calib["safe_lower"]), float(calib["safe_upper"])
            else:
                safe_lower, safe_upper = float(bio_data.get("safe_lower_bound", 50.0)), float(bio_data.get("safe_upper_bound", 100.0))
                baseline, unit = round((safe_lower + safe_upper) / 2.0, 1), str(bio_data.get("unit", "units"))
                gain = max(1.0, (safe_upper - safe_lower) * 0.5)

            c_dict = biomarker_contributions.get(bio_id, {})
            has_positive_driver = any(m > 0 for m in c_dict.values())
            c_shares = []
            for c_id, c_mag in c_dict.items():
                if calib:
                    if c_mag >= 0:
                        c_gain = float(calib["gain_up"])
                    else:
                        c_gain = float(calib["gain_up"] if has_positive_driver else calib["gain_down"])
                else:
                    c_gain = gain
                c_delta = round(c_mag * c_gain, 1 if baseline >= 10 else 2)
                c_shares.append({"compound_id": c_id, "compound_label": self.graph.nodes[c_id].get("label", c_id), "contribution_mag": round(c_mag, 3), "estimated_delta": c_delta, "formatted_delta": f"{'+' if c_delta > 0 else ''}{c_delta} {unit}"})

            if c_shares:
                delta_val = round(sum(c["estimated_delta"] for c in c_shares), 1 if baseline >= 10 else 2)
            else:
                delta_val = round(net_mag * gain, 1 if baseline >= 10 else 2)

            # Cap maximum biomarker drop so circulating values cannot fall below biological 0.0 floor
            if delta_val < -baseline:
                delta_val = -baseline

            ss_delta = delta_val
            ss_est_val = round(baseline + ss_delta, 1 if baseline >= 10 else 2)
            ss_pct_change = round((ss_delta / baseline) * 100.0, 1) if baseline != 0 else 0.0

            onset_days = float(calib.get("onset_days", bio_data.get("onset_days", 1.0))) if calib else float(bio_data.get("onset_days", 1.0))
            half_time_days = float(calib.get("half_time_days", bio_data.get("half_time_days", 3.0))) if calib else float(bio_data.get("half_time_days", 3.0))
            steady_state_weeks = float(calib.get("time_to_steady_state_weeks", bio_data.get("time_to_steady_state_weeks", 1.0))) if calib else float(bio_data.get("time_to_steady_state_weeks", 1.0))
            profile = str(calib.get("kinetic_profile", bio_data.get("kinetic_profile", "direct_receptor"))) if calib else str(bio_data.get("kinetic_profile", "direct_receptor"))
            time_desc = str(calib.get("time_course_description")) if (calib and calib.get("time_course_description")) else f"Reaches 50% shift in ~{half_time_days} days and steady state in ~{steady_state_weeks} weeks."

            # Calculate kinetic progress fraction at requested timeline
            if effective_days is not None:
                t_days = float(effective_days)
                if t_days < onset_days:
                    kinetic_frac = 0.0
                else:
                    kinetic_frac = 1.0 - math.exp(-math.log(2.0) * (t_days - onset_days) / max(0.1, half_time_days))
                kinetic_frac = max(0.0, min(1.0, kinetic_frac))
                curr_delta = round(ss_delta * kinetic_frac, 1 if baseline >= 10 else 2)
                curr_est_val = round(baseline + curr_delta, 1 if baseline >= 10 else 2)
                curr_pct_change = round((curr_delta / baseline) * 100.0, 1) if baseline != 0 else 0.0
                progress_pct = round(kinetic_frac * 100.0, 1)

                # Scale compound contribution shares by timeline fraction
                timeline_c_shares = []
                for c in c_shares:
                    c_pt_delta = round(c["estimated_delta"] * kinetic_frac, 1 if baseline >= 10 else 2)
                    timeline_c_shares.append({
                        "compound_id": c["compound_id"],
                        "compound_label": c["compound_label"],
                        "contribution_mag": round(c["contribution_mag"] * kinetic_frac, 3),
                        "steady_state_delta": c["estimated_delta"],
                        "estimated_delta": c_pt_delta,
                        "formatted_delta": f"{'+' if c_pt_delta > 0 else ''}{c_pt_delta} {unit}",
                    })
            else:
                kinetic_frac = 1.0
                curr_delta = ss_delta
                curr_est_val = ss_est_val
                curr_pct_change = ss_pct_change
                progress_pct = 100.0
                timeline_c_shares = c_shares

            # Compute discrete dynamic time course progression points
            time_course = []
            milestone_days = [0.5, 1.0, 3.0, 7.0, 14.0, 28.0, 56.0, 84.0]
            for day in milestone_days:
                if day <= max(84.0, steady_state_weeks * 7.0 + 14.0):
                    if day < onset_days:
                        frac = 0.0
                    else:
                        frac = 1.0 - math.exp(-math.log(2.0) * (day - onset_days) / max(0.1, half_time_days))
                    frac = max(0.0, min(1.0, frac))
                    pt_delta = round(ss_delta * frac, 1 if baseline >= 10 else 2)
                    pt_val = round(baseline + pt_delta, 1 if baseline >= 10 else 2)
                    time_course.append({
                        "day": day,
                        "week": round(day / 7.0, 1),
                        "progress_pct": round(frac * 100.0, 1),
                        "estimated_value": pt_val,
                        "delta": pt_delta,
                    })

            formatted_biomarkers.append({
                "biomarker_id": bio_id,
                "label": bio_data.get("label", bio_id),
                "name": bio_data.get("label", bio_id),
                "net_shift": round(net_mag * kinetic_frac, 3),
                "steady_state_net_shift": round(net_mag, 3),
                "direction": "INCREASE" if (curr_delta > 0.05 or (net_mag * kinetic_frac) >= 0.01) else ("DECREASE" if (curr_delta < -0.05 or (net_mag * kinetic_frac) <= -0.01) else "NEUTRAL"),
                "arrow": "↑" if (curr_delta > 0.05 or (net_mag * kinetic_frac) >= 0.01) else ("↓" if (curr_delta < -0.05 or (net_mag * kinetic_frac) <= -0.01) else "→"),
                "unit": unit,
                "baseline_value": baseline,
                "estimated_value": curr_est_val,
                "estimated_delta": curr_delta,
                "estimated_pct_change": curr_pct_change,
                "steady_state_delta": ss_delta,
                "steady_state_value": ss_est_val,
                "steady_state_pct_change": ss_pct_change,
                "kinetic_progress_pct": progress_pct,
                "formatted_change": f"{'+' if curr_delta > 0 else ''}{curr_delta} {unit} ({'+' if curr_pct_change > 0 else ''}{curr_pct_change}%)",
                "formatted_display": f"{baseline} → {curr_est_val} {unit} ({'+' if curr_delta > 0 else ''}{curr_delta} {unit})",
                "biomarker_panel": bio_data.get("biomarker_panel", "General"),
                "safe_range": f"{safe_lower} - {safe_upper}",
                "safe_lower": safe_lower,
                "safe_upper": safe_upper,
                "in_safe_range": safe_lower <= curr_est_val <= safe_upper,
                "onset_days": onset_days,
                "half_time_days": half_time_days,
                "time_to_steady_state_weeks": steady_state_weeks,
                "kinetic_profile": profile,
                "time_course_description": time_desc,
                "time_progression_curve": time_course,
                "compound_contributions": timeline_c_shares,
            })

        # Compute Pathway Impacts with Bounded Per-Compound Aggregation
        pathway_impacts: Dict[str, float] = {}
        for path_id, start_map in pathway_path_signals.items():
            pathway_impacts[path_id] = max(-1.0, min(1.0, sum(_aggregate_compound_paths(p_list) for p_list in start_map.values())))

        pathway_kinetic_frac = 1.0
        if effective_days is not None:
            pathway_kinetic_frac = min(1.0, max(0.1, 1.0 - math.exp(-float(effective_days) / 1.5)))

        formatted_pathways = []
        for path_id, net_mag in sorted(pathway_impacts.items(), key=lambda x: abs(x[1]), reverse=True):
            pdata = self.graph.nodes[path_id]
            curr_act = round(net_mag * pathway_kinetic_frac, 3)
            formatted_pathways.append({
                "pathway_id": path_id,
                "label": pdata.get("label", path_id),
                "name": pdata.get("label", path_id),
                "net_activation": curr_act,
                "steady_state_activation": round(net_mag, 3),
                "status": "UPREGULATED" if curr_act > 0.03 else ("DOWNREGULATED" if curr_act < -0.03 else "MODULATED"),
                "database": pdata.get("pathway_database", "Reactome"),
            })

        # Compute Phenotype Impacts with Bounded Per-Compound Aggregation
        phenotype_impacts: Dict[str, float] = {}
        phenotype_contributions: Dict[str, Dict[str, float]] = {}
        for pheno_id, start_map in phenotype_path_signals.items():
            phenotype_contributions[pheno_id] = {}
            for c_id, p_list in start_map.items():
                phenotype_contributions[pheno_id][c_id] = _aggregate_compound_paths(p_list)
            phenotype_impacts[pheno_id] = max(-1.0, min(1.0, sum(phenotype_contributions[pheno_id].values())))

        pheno_kinetic_frac = 1.0
        if effective_days is not None:
            pheno_kinetic_frac = min(1.0, max(0.05, 1.0 - math.exp(-math.log(2.0) * float(effective_days) / 7.0)))

        formatted_phenotypes = []
        for pheno_id, net_mag in sorted(phenotype_impacts.items(), key=lambda x: abs(x[1]), reverse=True):
            pdata = self.graph.nodes[pheno_id]
            curr_pheno_mag = net_mag * pheno_kinetic_frac
            risk_pct = round(curr_pheno_mag * 100.0, 1)
            ss_risk_pct = round(net_mag * 100.0, 1)
            risk_status = "HIGH_RISK" if curr_pheno_mag > 0.4 else ("MODERATE_RISK" if curr_pheno_mag > 0.15 else ("MILD_RISK" if curr_pheno_mag > 0.03 else ("SUPPRESSED" if curr_pheno_mag < -0.15 else ("MILD_SUPPRESSION" if curr_pheno_mag < -0.03 else "NEUTRAL"))))
            c_shares = []
            for c_id, c_mag in phenotype_contributions.get(pheno_id, {}).items():
                c_risk = round(c_mag * pheno_kinetic_frac * 100.0, 1)
                c_shares.append({
                    "compound_id": c_id,
                    "compound_label": self.graph.nodes[c_id].get("label", c_id),
                    "contribution_mag": round(c_mag * pheno_kinetic_frac, 3),
                    "risk_delta_pct": c_risk,
                    "formatted_risk": f"{'+' if c_risk > 0 else ''}{c_risk}%",
                })
            formatted_phenotypes.append({
                "phenotype_id": pheno_id,
                "label": pdata.get("label", pheno_id),
                "name": pdata.get("label", pheno_id),
                "net_score": round(curr_pheno_mag, 3),
                "steady_state_score": round(net_mag, 3),
                "risk_delta_pct": risk_pct,
                "steady_state_risk_pct": ss_risk_pct,
                "risk_status": risk_status,
                "risk_badge": "High Elevation" if risk_status == "HIGH_RISK" else ("Moderate Elevation" if risk_status == "MODERATE_RISK" else ("Mild Elevation" if risk_status == "MILD_RISK" else ("Strong Suppression" if risk_status == "SUPPRESSED" else ("Mild Suppression" if risk_status == "MILD_SUPPRESSION" else "Neutral / Basal")))),
                "formatted_risk": f"{'+' if risk_pct > 0 else ''}{risk_pct}%",
                "category": pdata.get("phenotype_category", "clinical_outcome"),
                "severity": pdata.get("severity", "moderate"),
                "description": pdata.get("description", ""),
                "compound_contributions": c_shares,
            })

        timeline_summary_suffix = f" at {timeline_label} timeline horizon." if effective_days is not None else " at steady-state equilibrium."

        return {
            "activated_pathways": formatted_pathways,
            "biomarker_shifts": formatted_biomarkers,
            "phenotypes": formatted_phenotypes,
            "cascade_traces": traces[:25],
            "timeline": timeline_key,
            "timeline_days": effective_days,
            "timeline_label": timeline_label,
            "summary": f"Cascade simulation across {len(valid_starts)} origin entity(ies) mapped {len(formatted_pathways)} intracellular pathway(s), {len(formatted_biomarkers)} clinical biomarker shift(s), and {len(formatted_phenotypes)} downstream phenotype outcome(s){timeline_summary_suffix}"
        }

    def summarize(self) -> Dict[str, Any]:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": sorted({data.get("node_type", "unknown") for _, data in self.graph.nodes(data=True)}),
        }
