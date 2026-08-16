COMPOUND_LIBRARY = {
    "creatine": {
        "name": "Creatine",
        "canonical_name": "Creatine",
        "drug_class": "ergogenic metabolite",
        "compound_class": "amino acid derivative",
        "mechanism": "Increases phosphocreatine availability and supports ATP regeneration during high-intensity effort.",
        "receptor_targets": [
            {"target": "ATP-PCr system", "action": "supports energetics", "family": "metabolism"},
            {"target": "skeletal muscle", "action": "increases intracellular water and phosphagen capacity", "family": "muscle"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "low", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [
            {
                "partner": "beta_alanine",
                "effect": "Dual intracellular buffering & ATP regeneration",
                "description": "Simultaneous phosphagen reserve elevation and intramuscular carnosine acid buffering for sustained anaerobic work."
            },
            {
                "partner": "caffeine",
                "effect": "Neuromuscular performance enhancement",
                "description": "Combined central motor unit recruitment and intracellular phosphocreatine availability."
            }
        ],
        "categories": ["strength", "muscle", "performance"],
        "indications": ["strength", "muscle", "power"],
        "dosing": {
            "unit": "mg/day",
            "basis": "bodyweight",
            "mg_per_kg": {"threshold": 15, "common": 20, "heavy": 25},
            "notes": "Typical maintenance dosing is ~3-5 g/day; bodyweight scaling adjusts for total muscle mass."
        },
        "reason": "Creatine monohydrate increases phosphocreatine availability and supports repeated high-intensity performance, strength, and lean-mass adaptations.",
        "citation": "Kreider RB, et al. ISSN exercise & sport nutrition review: research & recommendations. J Int Soc Sports Nutr. 2017.",
        "contraindications": [
            "Avoid if severe renal insufficiency is present or eGFR is severely reduced.",
            "Maintain adequate hydration in thermogenic environments."
        ],
        "side_effects": [
            "Intracellular water retention",
            "Transient GI discomfort at high single bolus doses"
        ],
        "interactions": [
            "May slightly increase serum creatinine lab values without reducing actual glomerular filtration rate",
            "Caution with concurrent nephrotoxic agents"
        ],
        "evidence_level": "strong",
        "risk_band": "low",
        "graph_tags": ["metabolism", "muscle", "hydration", "renal"]
    },
    "caffeine": {
        "name": "Caffeine",
        "canonical_name": "Caffeine",
        "drug_class": "adenosine receptor antagonist",
        "compound_class": "methylxanthine",
        "mechanism": "Non-selective competitive antagonist of adenosine A1 and A2A receptors, elevating central alertness and catecholaminergic tone.",
        "receptor_targets": [
            {"target": "A1 receptor", "action": "antagonist", "family": "adenosine"},
            {"target": "A2A receptor", "action": "antagonist", "family": "adenosine"},
            {"target": "dopamine signaling", "action": "modulator", "family": "neuromodulation"},
            {"target": "phosphodiesterase", "action": "inhibitor", "family": "enzyme"}
        ],
        "cyp_enzymes": {"substrates": ["CYP1A2"], "inhibitors": ["CYP1A2"], "inducers": []},
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "moderate", "cns_stimulant": "high", "sedative": "none"},
        "synergies": [
            {
                "partner": "theanine",
                "effect": "Smooth attentional focus without jitters",
                "description": "L-Theanine crosses the blood-brain barrier to promote alpha brainwave activity and antagonize caffeine-induced peripheral vasoconstriction and anxiety."
            },
            {
                "partner": "alpha_gpc",
                "effect": "Enhanced cholinergic neuro-transmission",
                "description": "Adenosine antagonism combined with acetylcholine synthesis precursor for sustained cognitive vigilance."
            }
        ],
        "categories": ["focus", "cognition", "productivity", "performance"],
        "indications": ["focus", "cognition", "productivity"],
        "dosing": {
            "unit": "mg/kg",
            "basis": "bodyweight",
            "mg_per_kg": {"threshold": 2.5, "common": 3.0, "heavy": 5.0},
            "notes": "Many users achieve optimal ergogenic effects at ~3 mg/kg; doses above 5 mg/kg heighten cardiovascular strain and autonomic arousal."
        },
        "reason": "Caffeine acutely improves alertness and vigilance by adenosine receptor antagonism, increasing attention and reaction time performance.",
        "citation": "McLellan TM, et al. A review of caffeine's effects on cognitive, physical and occupational performance. Neurosci Biobehav Rev. 2016.",
        "contraindications": [
            "Avoid in uncontrolled hypertension or cardiac arrhythmias.",
            "Avoid within 8 hours of desired sleep onset.",
            "Caution with CYP1A2 inhibitors which dramatically prolong clearance."
        ],
        "side_effects": [
            "Tachycardia & elevated blood pressure",
            "Sleep onset latency increase",
            "Anxiety or psychomotor agitation at high doses"
        ],
        "interactions": [
            "CYP1A2 inhibitors (fluvoxamine, ciprofloxacin) dramatically slow caffeine clearance",
            "Synergistic stimulant cardiovascular strain with sympathomimetics (ephedrine, yohimbine)"
        ],
        "evidence_level": "strong",
        "risk_band": "moderate",
        "graph_tags": ["adenosine", "CNS", "sleep", "cardiovascular", "CYP1A2"]
    },
    "theanine": {
        "name": "L-Theanine",
        "canonical_name": "L-Theanine",
        "drug_class": "glutamate analog & neuromodulator",
        "compound_class": "amino acid analog",
        "mechanism": "Binds glutamate receptors with low affinity and stimulates GABA and dopamine synthesis, promoting relaxed cognitive focus.",
        "receptor_targets": [
            {"target": "GABA_A receptor", "action": "modulator", "family": "GABA"},
            {"target": "NMDA receptor", "action": "antagonist", "family": "glutamate"},
            {"target": "AMPA receptor", "action": "modulator", "family": "glutamate"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "low"},
        "synergies": [
            {
                "partner": "caffeine",
                "effect": "Cognitive synergy with reduced autonomic side effects",
                "description": "Counteracts caffeine-induced peripheral vasoconstriction, blood pressure spikes, and anxiety while synergizing on working memory and attention."
            }
        ],
        "categories": ["focus", "cognition", "stress", "sleep"],
        "indications": ["focus", "stress", "sleep"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 200, "heavy": 400},
            "notes": "Commonly dosed at a 1:1 or 2:1 ratio relative to caffeine (e.g. 200 mg Theanine to 100-200 mg Caffeine)."
        },
        "reason": "L-Theanine promotes calm focus, elevates alpha brain wave patterns, and mitigates stimulant-induced sympathetic overactivation.",
        "citation": "Giesbrecht T, et al. The combination of L-theanine and caffeine improves cognitive performance and increases subjective alertness. Nutr Neurosci. 2010.",
        "contraindications": [
            "Use caution with strong central antihypertensive agents due to mild vasorelaxant effects."
        ],
        "side_effects": [
            "Mild relaxation / slight drowsiness at very high doses"
        ],
        "interactions": [
            "Synergistic with caffeine and stimulants",
            "May potentiate mild sedative effects of GABAergic supplements"
        ],
        "evidence_level": "strong",
        "risk_band": "low",
        "graph_tags": ["neurotransmission", "GABA", "glutamate", "calm", "focus"]
    },
    "l_theanine": {
        "name": "L-Theanine",
        "canonical_name": "L-Theanine",
        "drug_class": "glutamate analog & neuromodulator",
        "compound_class": "amino acid analog",
        "mechanism": "Binds glutamate receptors with low affinity and stimulates GABA and dopamine synthesis, promoting relaxed cognitive focus.",
        "receptor_targets": [
            {"target": "GABA_A receptor", "action": "modulator", "family": "GABA"},
            {"target": "NMDA receptor", "action": "antagonist", "family": "glutamate"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "low"},
        "synergies": [
            {
                "partner": "caffeine",
                "effect": "Cognitive synergy",
                "description": "Counteracts stimulant jitteriness while enhancing visual attention."
            }
        ],
        "categories": ["focus", "cognition", "stress", "sleep"],
        "indications": ["focus", "stress", "sleep"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 200, "heavy": 400},
            "notes": "Commonly paired with caffeine at 100-200 mg."
        },
        "reason": "L-Theanine promotes calm alertness and alpha-wave generation.",
        "citation": "Giesbrecht T, et al. Nutr Neurosci. 2010.",
        "contraindications": [],
        "side_effects": [],
        "interactions": ["Synergizes with caffeine"],
        "evidence_level": "strong",
        "risk_band": "low",
        "graph_tags": ["neurotransmission", "focus"]
    },
    "berberine": {
        "name": "Berberine",
        "canonical_name": "Berberine",
        "drug_class": "AMPK activator & CYP inhibitor",
        "compound_class": "isoquinoline alkaloid",
        "mechanism": "Activates AMP-activated protein kinase (AMPK), promotes glucose transporter GLUT4 translocation, and strongly inhibits CYP3A4, CYP2D6, and CYP2C9 enzymes.",
        "receptor_targets": [
            {"target": "AMPK", "action": "agonist", "family": "metabolic kinase"},
            {"target": "CYP3A4", "action": "inhibitor", "family": "cytochrome P450"},
            {"target": "CYP2D6", "action": "inhibitor", "family": "cytochrome P450"},
            {"target": "CYP2C9", "action": "inhibitor", "family": "cytochrome P450"},
            {"target": "PCSK9", "action": "inhibitor", "family": "lipid regulation"}
        ],
        "cyp_enzymes": {
            "substrates": ["CYP3A4", "CYP2D6"],
            "inhibitors": ["CYP3A4", "CYP2D6", "CYP2C9"],
            "inducers": []
        },
        "organ_burdens": {"hepatic": "moderate", "renal": "low", "cardiovascular": "low", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [
            {
                "partner": "omega_3",
                "effect": "Complementary lipid and insulin sensitivity support",
                "description": "Berberine enhances hepatic LDL receptor expression via PCSK9 inhibition while Omega-3 reduces triglyceride synthesis."
            }
        ],
        "categories": ["metabolism", "fat loss", "cardiovascular", "longevity"],
        "indications": ["metabolism", "glucose", "lipids"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 1000, "heavy": 1500},
            "notes": "Usually split into 500 mg doses 2-3 times daily before meals to avoid acute GI distress."
        },
        "reason": "Potent AMPK activator for glycemic and lipid management, with significant pharmacokinetic drug-drug interaction considerations.",
        "citation": "Yin J, et al. Efficacy of berberine in patients with type 2 diabetes mellitus. Metabolism. 2008.",
        "contraindications": [
            "Strong caution when co-administered with drugs metabolized by CYP3A4, CYP2D6, or CYP2C9 (e.g. statins, ARBs, macrolides).",
            "Avoid in pregnancy and breastfeeding."
        ],
        "side_effects": [
            "GI cramping and diarrhea",
            "Altered pharmacokinetics of co-administered medications"
        ],
        "interactions": [
            "Potent CYP3A4 & CYP2D6 inhibition elevates serum concentrations of co-administered substrates",
            "Additive hypoglycemic potential with prescription antidiabetic agents"
        ],
        "evidence_level": "strong",
        "risk_band": "moderate",
        "graph_tags": ["metabolism", "AMPK", "CYP3A4", "CYP2D6", "glucose", "lipids"]
    },
    "telmisartan": {
        "name": "Telmisartan",
        "canonical_name": "Telmisartan",
        "drug_class": "angiotensin II receptor blocker & PPAR-gamma modulator",
        "compound_class": "biphenyl tetrazole",
        "mechanism": "Selectively antagonizes angiotensin II type 1 (AT1) receptors and acts as a partial agonist of PPAR-gamma, conferring metabolic and cardiovascular protection.",
        "receptor_targets": [
            {"target": "Type-1 angiotensin II receptor", "action": "antagonist", "family": "angiotensin"},
            {"target": "PPAR-gamma", "action": "agonist", "family": "nuclear receptor"},
            {"target": "TGF-beta signaling", "action": "inhibitor", "family": "fibrosis"}
        ],
        "cyp_enzymes": {
            "substrates": ["CYP2C9", "UGT1A3"],
            "inhibitors": [],
            "inducers": []
        },
        "organ_burdens": {"hepatic": "low", "renal": "moderate", "cardiovascular": "low", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [
            {
                "partner": "omega_3",
                "effect": "Cardiovascular endothelial resilience",
                "description": "Combined renin-angiotensin blockade and anti-inflammatory eicosanoid modulation."
            }
        ],
        "categories": ["cardio", "metabolism", "longevity"],
        "indications": ["hypertension", "cardiovascular", "nephroprotection"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 40, "heavy": 80},
            "notes": "Standard clinical dosing is 20-80 mg once daily."
        },
        "reason": "Provides blood pressure control, left ventricular hypertrophy regression, and insulin-sensitizing PPAR-gamma activation.",
        "citation": "Yusuf S, et al. Telmisartan, ramipril, or both in patients at high risk for vascular events. N Engl J Med. 2008.",
        "contraindications": [
            "Severe bilateral renal artery stenosis",
            "Concurrent ACE inhibitor therapy (dual RAS blockade)",
            "Hyperkalemia"
        ],
        "side_effects": [
            "Hypotension / dizziness",
            "Hyperkalemia in susceptible individuals"
        ],
        "interactions": [
            "Potassium-sparing diuretics or high potassium intake may trigger hyperkalemia",
            "CYP2C9 inhibitors may increase systemic exposure"
        ],
        "evidence_level": "strong",
        "risk_band": "moderate",
        "graph_tags": ["cardiovascular", "AT1", "PPAR-gamma", "blood_pressure", "kidney"]
    },
    "l_carnitine": {
        "name": "L-Carnitine",
        "canonical_name": "L-Carnitine",
        "drug_class": "fatty acid transporter cofactor",
        "compound_class": "quaternary ammonium",
        "mechanism": "Facilitates long-chain fatty acid transport into mitochondria for beta-oxidation and energy metabolism.",
        "receptor_targets": [
            {"target": "mitochondrial fatty acid transport", "action": "supports", "family": "metabolism"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [],
        "categories": ["fat loss", "metabolism"],
        "indications": ["fat loss", "weight"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 2000, "heavy": 3000},
            "notes": "Often used in 1-3 g/day ranges, but effects are modest and highly individual."
        },
        "reason": "L-carnitine supports mitochondrial fatty acid transport, which may modestly improve exercise metabolism.",
        "citation": "Pooyandjoo M, et al. Obes Rev. 2016.",
        "contraindications": [
            "Use cautiously in seizure disorders or with medications that alter mitochondrial metabolism."
        ],
        "side_effects": [
            "GI upset",
            "Fishy body odor at very high unabsorbed oral doses"
        ],
        "interactions": [
            "Limited adverse interaction profile"
        ],
        "evidence_level": "moderate",
        "risk_band": "low",
        "graph_tags": ["metabolism", "mitochondria", "fatty acids"]
    },
    "omega_3": {
        "name": "Omega-3",
        "canonical_name": "Omega-3",
        "drug_class": "essential fatty acid",
        "compound_class": "polyunsaturated fatty acid",
        "mechanism": "Provides EPA/DHA to support cell membrane fluidity, anti-inflammatory resolvin/protectin production, and triglyceride reduction.",
        "receptor_targets": [
            {"target": "eicosanoid pathways", "action": "modulates", "family": "inflammation"},
            {"target": "cell membranes", "action": "structural support", "family": "lipid signaling"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [
            {
                "partner": "berberine",
                "effect": "Comprehensive lipid particle optimization",
                "description": "Reduces triglyceride synthesis while berberine clears apoB/LDL particles."
            }
        ],
        "categories": ["general health", "recovery", "cardiovascular"],
        "indications": ["general health", "recovery", "cardio"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 1500, "heavy": 3000},
            "notes": "EPA/DHA dosing is standardized by total daily omega-3 active content."
        },
        "reason": "Omega-3 fatty acids support inflammatory balance and cardiovascular resilience.",
        "citation": "AbuMweis SS, et al. J Hum Hypertens. 2018.",
        "contraindications": [
            "Use with caution in active bleeding disorders or concurrent high-dose anticoagulant therapy."
        ],
        "side_effects": [
            "Fishy aftertaste",
            "Mild dyspepsia"
        ],
        "interactions": [
            "Potential additive antiplatelet effect with NSAIDs or anticoagulants at >3g/day"
        ],
        "evidence_level": "moderate",
        "risk_band": "low",
        "graph_tags": ["inflammation", "lipids", "cardiovascular"]
    },
    "beta_alanine": {
        "name": "Beta-Alanine",
        "canonical_name": "Beta-Alanine",
        "drug_class": "histidine-derived buffering agent",
        "compound_class": "beta-amino acid",
        "mechanism": "Rate-limiting precursor for intramuscular carnosine synthesis, buffering cellular hydrogen ion accumulation during high-intensity glycolytic exercise.",
        "receptor_targets": [
            {"target": "carnosine buffering", "action": "increases substrate availability", "family": "muscle buffering"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [
            {
                "partner": "creatine",
                "effect": "Anaerobic endurance and power synergy",
                "description": "Phosphocreatine recharge combined with intracellular proton buffering."
            }
        ],
        "categories": ["strength", "endurance", "performance"],
        "indications": ["strength", "endurance", "power"],
        "dosing": {
            "unit": "mg/kg",
            "basis": "bodyweight",
            "mg_per_kg": {"threshold": 40, "common": 60, "heavy": 80},
            "notes": "Doses are frequently split across the day (e.g. 1.6 g doses) to avoid transient paresthesia."
        },
        "reason": "Beta-alanine raises carnosine stores and improves high-intensity exercise capacity.",
        "citation": "Trexler ET, et al. J Int Soc Sports Nutr. 2015.",
        "contraindications": [],
        "side_effects": [
            "Transient paresthesia (harmless skin tingling mediated by MrgprD receptors)"
        ],
        "interactions": [],
        "evidence_level": "strong",
        "risk_band": "low",
        "graph_tags": ["muscle", "acid buffering", "performance"]
    },
    "ashwagandha": {
        "name": "Ashwagandha",
        "canonical_name": "Ashwagandha",
        "drug_class": "adaptogen & HPA modulator",
        "compound_class": "withanolide glycoside",
        "mechanism": "Modulates hypothalamic-pituitary-adrenal (HPA) axis cortisol secretion, enhances GABAergic tone, and exerts moderate CYP3A4 modulation.",
        "receptor_targets": [
            {"target": "HPA axis", "action": "modulates", "family": "stress"},
            {"target": "GABA_A receptor", "action": "modulator", "family": "neuroendocrine"},
            {"target": "CYP3A4", "action": "inhibitor", "family": "cytochrome P450"}
        ],
        "cyp_enzymes": {
            "substrates": ["CYP3A4"],
            "inhibitors": ["CYP3A4"],
            "inducers": []
        },
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "moderate"},
        "synergies": [
            {
                "partner": "magnesium_glycinate",
                "effect": "Deep sleep and neuro-somatic recovery",
                "description": "GABAergic sensitization coupled with NMDA receptor regulation."
            }
        ],
        "categories": ["stress", "recovery", "sleep"],
        "indications": ["stress", "recovery", "focus"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 300, "heavy": 600},
            "notes": "Clinical trials typically use 300-600 mg of standardized high-concentration extract (e.g. KSM-66 or Sensoril)."
        },
        "reason": "Ashwagandha significantly lowers perceived stress and circulating cortisol while supporting physical recovery.",
        "citation": "Chandrasekhar K, et al. Indian J Psychol Med. 2012.",
        "contraindications": [
            "Use cautiously in active autoimmune conditions or untreated hyperthyroidism."
        ],
        "side_effects": [
            "Mild drowsiness",
            "Occasional GI discomfort"
        ],
        "interactions": [
            "Additive sedative effects with central nervous system depressants",
            "Mild CYP3A4 inhibition"
        ],
        "evidence_level": "moderate",
        "risk_band": "low",
        "graph_tags": ["stress", "HPA-axis", "recovery", "sleep", "cortisol"]
    },
    "alpha_gpc": {
        "name": "Alpha-GPC",
        "canonical_name": "Alpha-GPC",
        "drug_class": "cholinergic precursor",
        "compound_class": "glycerophospholipid",
        "mechanism": "Directly delivers choline across the blood-brain barrier to synthesize acetylcholine and phosphatidylcholine membrane structures.",
        "receptor_targets": [
            {"target": "nicotinic acetylcholine receptor", "action": "agonist", "family": "cholinergic"},
            {"target": "muscarinic acetylcholine receptor", "action": "agonist", "family": "cholinergic"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "low", "cns_stimulant": "low", "sedative": "none"},
        "synergies": [
            {
                "partner": "caffeine",
                "effect": "Acetylcholine & catecholamine synergy",
                "description": "Optimizes neuromuscular power output and cognitive task switching."
            }
        ],
        "categories": ["focus", "cognition", "performance"],
        "indications": ["focus", "cognition", "power"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 300, "heavy": 600},
            "notes": "Dosed at 300-600 mg 45-60 minutes prior to mental or physical demand."
        },
        "reason": "Increases central acetylcholine availability, supporting cognitive processing speed and power output.",
        "citation": "Bellar D, et al. J Int Soc Sports Nutr. 2015.",
        "contraindications": [],
        "side_effects": ["Headaches if excess choline accumulates"],
        "interactions": ["Synergizes with anticholinesterases and stimulants"],
        "evidence_level": "moderate",
        "risk_band": "low",
        "graph_tags": ["acetylcholine", "cognition", "focus", "nootropic"]
    },
    "nac": {
        "name": "N-Acetylcysteine (NAC)",
        "canonical_name": "N-Acetylcysteine",
        "drug_class": "glutathione precursor & mucolytic",
        "compound_class": "cysteine derivative",
        "mechanism": "Provides bioavailable L-cysteine for intracellular glutathione (GSH) synthesis, neutralizing reactive oxygen species and supporting hepatic phase II conjugation.",
        "receptor_targets": [
            {"target": "glutathione synthesis system", "action": "supports", "family": "antioxidant"},
            {"target": "cystine-glutamate antiporter (system xc-)", "action": "agonist", "family": "glutamate regulation"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [
            {
                "partner": "tudca",
                "effect": "Comprehensive hepatobiliary protection",
                "description": "NAC elevates intracellular glutathione while TUDCA protects bile acid flow and endoplasmic reticulum homeostasis."
            }
        ],
        "categories": ["recovery", "general health", "longevity"],
        "indications": ["liver support", "antioxidant", "recovery"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 600, "heavy": 1200},
            "notes": "Commonly taken as 600 mg 1-2 times daily on an empty stomach."
        },
        "reason": "Replenishes intracellular glutathione to protect hepatocytes and mitigate oxidative stress from intense training or xenobiotics.",
        "citation": "Mokhtari V, et al. Cell J. 2017.",
        "contraindications": ["Active peptic ulcer disease"],
        "side_effects": ["Sulfur burps", "Mild nausea if taken without water"],
        "interactions": ["Caution when combined with nitroglycerin due to potentiation of vasodilation"],
        "evidence_level": "strong",
        "risk_band": "low",
        "graph_tags": ["glutathione", "liver", "antioxidant", "detoxification"]
    },
    "tudca": {
        "name": "TUDCA",
        "canonical_name": "TUDCA",
        "drug_class": "hydrophilic bile acid & chaperone",
        "compound_class": "tauroursodeoxycholic acid",
        "mechanism": "Mitigates endoplasmic reticulum (ER) stress, prevents hepatocyte apoptosis from hydrophobic bile salts, and promotes healthy biliary clearance.",
        "receptor_targets": [
            {"target": "TGR5 bile acid receptor", "action": "agonist", "family": "nuclear/membrane receptor"},
            {"target": "endoplasmic reticulum stress response", "action": "inhibitor", "family": "proteostasis"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": [], "inducers": []},
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "synergies": [
            {
                "partner": "nac",
                "effect": "Synergistic hepatoprotection",
                "description": "Combines glutathione antioxidant defense with bile acid cytoprotection."
            }
        ],
        "categories": ["recovery", "general health", "longevity"],
        "indications": ["liver support", "bile flow", "ER stress"],
        "dosing": {
            "unit": "mg/day",
            "basis": "fixed",
            "mg_per_kg": {"threshold": 0, "common": 500, "heavy": 1000},
            "notes": "Usually dosed at 250-500 mg twice daily with meals."
        },
        "reason": "Protects liver tissue from hydrophobic bile acid toxicity and alleviates endoplasmic reticulum stress.",
        "citation": "Vang S, et al. J Clin Transl Res. 2018.",
        "contraindications": ["Complete biliary obstruction"],
        "side_effects": ["Mild diarrhea at high dosages"],
        "interactions": ["Do not consume concurrently with ethanol as it may aggravate acute liver injury"],
        "evidence_level": "strong",
        "risk_band": "low",
        "graph_tags": ["liver", "bile", "ER stress", "hepatoprotection"]
    },
    "yohimbine": {
        "name": "Yohimbine",
        "canonical_name": "Yohimbine",
        "drug_class": "alpha-2 adrenergic antagonist & stimulant",
        "compound_class": "indole alkaloid",
        "mechanism": "Selectively antagonizes presynaptic alpha-2 adrenergic receptors, disinhibiting norepinephrine release and amplifying lipolysis and autonomic sympathetic tone.",
        "receptor_targets": [
            {"target": "alpha-2A adrenergic receptor", "action": "antagonist", "family": "adrenergic"},
            {"target": "alpha-2B adrenergic receptor", "action": "antagonist", "family": "adrenergic"},
            {"target": "5-HT1A receptor", "action": "modulator", "family": "serotonergic"}
        ],
        "cyp_enzymes": {
            "substrates": ["CYP2D6", "CYP3A4"],
            "inhibitors": [],
            "inducers": []
        },
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "high", "cns_stimulant": "high", "sedative": "none"},
        "synergies": [
            {
                "partner": "caffeine",
                "effect": "High-risk synergistic stimulant load",
                "description": "Concurrent phosphodiesterase/adenosine blockade and presynaptic alpha-2 disinhibition dramatically multiplies norepinephrine and cardiovascular burden."
            }
        ],
        "categories": ["fat loss", "performance"],
        "indications": ["fat loss", "lipolysis"],
        "dosing": {
            "unit": "mg/kg",
            "basis": "bodyweight",
            "mg_per_kg": {"threshold": 0.1, "common": 0.2, "heavy": 0.25},
            "notes": "Narrow therapeutic window; must be dosed in a fasted state due to insulin-mediated suppression of alpha-2 antagonism."
        },
        "reason": "Acutely blocks alpha-2 adrenergic receptors to facilitate stubborn adipose tissue lipolysis.",
        "citation": "Ostojic SM. Yohimbine: the effects on body composition and exercise performance in soccer players. Res Sports Med. 2006.",
        "contraindications": [
            "Uncontrolled hypertension, anxiety disorders, panic history, or cardiac arrhythmias.",
            "Avoid in combination with MAO inhibitors or multiple stimulants."
        ],
        "side_effects": [
            "Severe anxiety / panic",
            "Marked hypertension and tachycardia",
            "Cold sweats and tremors"
        ],
        "interactions": [
            "Severe cardiovascular collision with caffeine and other central stimulants",
            "CYP2D6 poor metabolizers experience drastically elevated circulating levels"
        ],
        "evidence_level": "moderate",
        "risk_band": "high",
        "graph_tags": ["adrenergic", "stimulant", "cardiovascular", "lipolysis", "CYP2D6"]
    }
}
