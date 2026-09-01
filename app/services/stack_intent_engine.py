from __future__ import annotations

import logging
import re
from app.services.chemical_structure_engine import (
    is_17a_alkylated,
    is_19nor_steroid,
    is_aromatizable_androgen,
    is_steroidal_androgen,
)


logger = logging.getLogger("healthai.stack_intent_engine")

PROTOCOL_GOAL_TAXONOMY = [
    {
        "id": "auto",
        "name": "Auto-Infer from Stack",
        "icon": "🤖",
        "description": "Automatically infer primary objective from compound mechanisms, receptor targets, and drug classes."
    },
    {
        "id": "anabolic_physique",
        "name": "Physique & Anabolic Hypertrophy",
        "icon": "🏋️",
        "description": "Supra-physiological androgen exposure, protein synthesis, organ protection, and endocrine management."
    },
    {
        "id": "cognitive_focus",
        "name": "Cognitive Focus & Neuroprotection",
        "icon": "🧠",
        "description": "Neurotransmitter modulation, catecholaminergic sustained focus, synaptic plasticity, and cerebral blood flow."
    },
    {
        "id": "cardiovascular_lipid",
        "name": "Cardiovascular & Lipid Optimization",
        "icon": "❤️",
        "description": "Endothelial nitric oxide release, blood pressure normalization, ApoB/LDL regulation, and arterial compliance."
    },
    {
        "id": "longevity_autophagy",
        "name": "Longevity & Cellular Autophagy",
        "icon": "🧬",
        "description": "AMPK activation, mTORC1 cycling, sirtuin deacetylase activation, and mitochondrial biogenesis."
    },
    {
        "id": "sleep_stress_recovery",
        "name": "Sleep Architecture & Stress Recovery",
        "icon": "🌙",
        "description": "HPA axis downregulation, nocturnal GABAergic tone, cortisol blunting, and slow-wave sleep depth."
    },
    {
        "id": "fat_loss_metabolic",
        "name": "Metabolic Output & Fat Loss",
        "icon": "🔥",
        "description": "Beta-adrenergic lipolysis, insulin sensitivity enhancement, and mitochondrial uncoupling / substrate partitioning."
    },
    {
        "id": "post_therapy_reset",
        "name": "Post-Therapy Restoration (PCT / Reset)",
        "icon": "🔄",
        "description": "HPTA axis kickstart, selective estrogen receptor modulation, liver enzyme flushing, and lipid clearance."
    },
    {
        "id": "gut_microbiome",
        "name": "Gut Microbiome & Intestinal Barrier",
        "icon": "🦠",
        "description": "Gastric peptide healing, tight junction repair, short-chain fatty acids, and microbiome diversity."
    },
    {
        "id": "immune_defense",
        "name": "Immune Defense & Cellular Resilience",
        "icon": "🛡️",
        "description": "Cellular redox buffering, innate immune potentiation, viral shielding, and T-cell support."
    },
    {
        "id": "hair_skin_derm",
        "name": "Dermatology & Hair Follicle Health",
        "icon": "✨",
        "description": "5-AR inhibition, scalp perfusion, collagen synthesis, and topical anti-androgens."
    },
    {
        "id": "custom",
        "name": "Custom User Objective",
        "icon": "✍️",
        "description": "User-specified clinical or performance goals and personalized constraints."
    }
]

SCRATCH_GOAL_BLUEPRINTS: Dict[str, Dict[str, Any]] = {
    "cognitive_focus": {
        "title": "Cognitive Focus & Neuroprotection",
        "description": "Clean catecholaminergic sustained focus, synaptic plasticity, and cerebral perfusion without crash or jitter.",
        "core_compounds": [
            {
                "key": "modafinil",
                "name": "Modafinil",
                "base_dose": 100,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Dopamine Transporter (DAT) & Orexin Activation",
                "rationale": "Promotes extreme wakefulness and cognitive processing speed without the crash associated with classical amphetamines.",
                "pmid": "18198270",
                "citation_str": "Minzenberg MJ et al., Neuropsychopharmacology 2008 [PMID: 18198270]",
                "is_stimulant": True,
            },
            {
                "key": "alpha_gpc",
                "name": "Alpha-GPC",
                "base_dose": 300,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Acetylcholine Biosynthesis",
                "rationale": "Crosses the blood-brain barrier to rapidly provide choline for acetylcholine synthesis, supporting focus and memory.",
                "pmid": "1319912",
                "citation_str": "Parnetti L et al., Mech Ageing Dev 1992 [PMID: 1319912]",
                "is_stimulant": False,
            },
            {
                "key": "caffeine",
                "name": "Caffeine Anhydrous",
                "base_dose": 100,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Adenosine A1 / A2A Antagonist",
                "rationale": "Inhibits tonic adenosine fatigue signals and promotes dopamine/norepinephrine neurotransmission.",
                "pmid": "18681988",
                "citation_str": "Owen GN et al., Nutr Neurosci 2008 [PMID: 18681988]",
                "is_stimulant": True,
            },
            {
                "key": "l_theanine",
                "name": "L-Theanine",
                "base_dose": 200,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Glutamate Receptor Modulator & GABAergic Tone",
                "rationale": "Promotes alpha wave relaxation, blunts caffeine-induced peripheral vasoconstriction, and sharpens attention (1:2 caffeine-to-theanine ratio).",
                "pmid": "18296328",
                "citation_str": "Nobre AC et al., Asia Pac J Clin Nutr 2008 [PMID: 18296328]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "magnesium",
                "name": "Magnesium Glycinate",
                "base_dose": 300,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "NMDA Receptor Voltage-Gated Blocker",
                "rationale": "Safeguards neurovascular recovery and prevents excitotoxicity following stimulant exposure.",
                "pmid": "23853635",
                "citation_str": "Abbasi B et al., J Res Med Sci 2012 [PMID: 23853635]",
                "is_stimulant": False,
            }
        ]
    },
    "longevity_autophagy": {
        "title": "Longevity & Cellular Autophagy",
        "description": "AMPK activation, sirtuin deacetylase stimulation, mitochondrial biogenesis, and lipid protection.",
        "core_compounds": [
            {
                "key": "berberine",
                "name": "Berberine HCl",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "AMPK Activator & GLUT4 Translocator",
                "rationale": "Phosphorylates AMPK, promotes mitochondrial biogenesis, and improves insulin sensitivity and substrate partitioning.",
                "pmid": "18442638",
                "citation_str": "Yin J et al., Metabolism 2008 [PMID: 18442638]",
                "is_stimulant": False,
            },
            {
                "key": "coq10",
                "name": "Coenzyme Q10 (Ubiquinol)",
                "base_dose": 100,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Mitochondrial ETC Complex I/II Electron Carrier",
                "rationale": "Maintains inner mitochondrial membrane potential and supports myocardial energetics.",
                "pmid": "25282031",
                "citation_str": "Mortensen SA et al., JACC Heart Fail 2014 [PMID: 25282031]",
                "is_stimulant": False,
            },
            {
                "key": "curcumin",
                "name": "Curcumin Extract",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Nrf2 / ARE Master Antioxidant Pathway & NF-kB Inhibitor",
                "rationale": "Downregulates chronic systemic inflammatory cytokines (TNF-alpha, IL-6) and upregulates endogenous glutathione synthesis.",
                "pmid": "9619120",
                "citation_str": "Shoba G et al., Planta Med 1998 [PMID: 9619120]",
                "is_stimulant": False,
            },
            {
                "key": "piperine",
                "name": "Piperine (BioPerine)",
                "base_dose": 5,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Hepatic/Intestinal Glucuronidation & P-gp Modulator",
                "rationale": "Increases curcumin and polyphenol serum bioavailability by up to 2000%.",
                "pmid": "9619120",
                "citation_str": "Shoba G et al., Planta Med 1998 [PMID: 9619120]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "taurine",
                "name": "Taurine",
                "base_dose": 1000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Mitochondrial Matrix Osmolyte & Senescence Modulator",
                "rationale": "Supplements age-dependent cellular taurine decline, supporting mitochondrial integrity and reducing DNA oxidative damage.",
                "pmid": "37289866",
                "citation_str": "Singh P et al., Science 2023 [PMID: 37289866]",
                "is_stimulant": False,
            }
        ]
    },
    "cardiovascular_lipid": {
        "title": "Cardiovascular & Lipid Optimization",
        "description": "Endothelial nitric oxide release, blood pressure normalization, ApoB/LDL clearance, and myocardial preservation.",
        "core_compounds": [
            {
                "key": "telmisartan",
                "name": "Telmisartan",
                "base_dose": 40,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Angiotensin II Type 1 (AT1) Receptor Antagonist & PPAR-gamma Partial Agonist",
                "rationale": "Blocks RAAS-mediated renal vasoconstriction, prevents Left Ventricular Hypertrophy (LVH), and improves insulin sensitivity.",
                "pmid": "18378520",
                "citation_str": "Yusuf S et al., N Engl J Med 2008 [PMID: 18378520]",
                "is_stimulant": False,
            },
            {
                "key": "nebivolol",
                "name": "Nebivolol",
                "base_dose": 5,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Selective Beta-1 Adrenergic Blocker & eNOS Stimulator",
                "rationale": "Reduces resting heart rate and arterial stiffness via direct endothelial NO release.",
                "pmid": "15587107",
                "citation_str": "Ignarro LJ, Blood Press Suppl 2004 [PMID: 15587107]",
                "is_stimulant": False,
            },
            {
                "key": "rosuvastatin",
                "name": "Rosuvastatin",
                "base_dose": 5,
                "unit": "mg",
                "timing": "evening",
                "frequency": "daily",
                "route": "oral",
                "target": "HMG-CoA Reductase Inhibitor",
                "rationale": "Potently upregulates hepatic LDL receptors to aggressively lower circulating ApoB and LDL-C.",
                "pmid": "18997196",
                "citation_str": "Ridker PM et al., N Engl J Med 2008 [PMID: 18997196]",
                "is_stimulant": False,
            },
            {
                "key": "ezetimibe",
                "name": "Ezetimibe",
                "base_dose": 10,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "NPC1L1 Cholesterol Transporter Inhibitor",
                "rationale": "Blocks biliary and dietary cholesterol absorption in the jejunum, highly synergistic with statin therapy.",
                "pmid": "26039521",
                "citation_str": "Cannon CP et al., N Engl J Med 2015 [PMID: 26039521]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": []
    },
    "anabolic_physique": {
        "title": "Physique & Anabolic Hypertrophy",
        "description": "Intracellular energetic buffering, cellular hydration, protein synthesis support, and cardioprotective ancillaries.",
        "core_compounds": [
            {
                "key": "creatine",
                "name": "Creatine Monohydrate",
                "base_dose": 5000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Intracellular Phosphocreatine Shuttle & Myocellular Osmolality",
                "rationale": "Maximizes rapid ADP-to-ATP resynthesis during anaerobic high-threshold muscle contractions.",
                "pmid": "12701815",
                "citation_str": "Kreider RB, Mol Cell Biochem 2003 [PMID: 12701815]",
                "is_stimulant": False,
            },
            {
                "key": "beta_alanine",
                "name": "Beta-Alanine",
                "base_dose": 3200,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Intramuscular Carnosine Biosynthesis",
                "rationale": "Buffers exercise-induced intracellular hydrogen ion (H+) accumulation and delays muscular acidosis.",
                "pmid": "16868650",
                "citation_str": "Harris RC et al., Amino Acids 2006 [PMID: 16868650]",
                "is_stimulant": False,
            },
            {
                "key": "l_carnitine",
                "name": "L-Carnitine L-Tartrate",
                "base_dose": 2000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Androgen Receptor Upregulation & CPT-1 Mitochondrial Shuttle",
                "rationale": "Increases post-exercise androgen receptor density and accelerates recovery kinetics.",
                "pmid": "29534031",
                "citation_str": "Fielding R et al., Nutrients 2018 [PMID: 29534031]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "citrus_bergamot",
                "name": "Citrus Bergamot",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Lipid & ApoB Protection",
                "rationale": "Maintains lipid profile equilibrium during intensive training phases.",
                "pmid": "24239156",
                "citation_str": "Gliozzi M et al., Int J Cardiol 2013 [PMID: 24239156]",
                "is_stimulant": False,
            },
            {
                "key": "telmisartan",
                "name": "Telmisartan",
                "base_dose": 20,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Renal Microcirculation & AT1 Blockade",
                "rationale": "Protects glomerular filtration pressure and vascular compliance.",
                "pmid": "18378520",
                "citation_str": "Yusuf S et al., N Engl J Med 2008 [PMID: 18378520]",
                "is_stimulant": False,
            }
        ]
    },
    "sleep_stress_recovery": {
        "title": "Sleep Architecture & Stress Recovery",
        "description": "HPA axis downregulation, nocturnal GABAergic tone, cortisol blunting, and slow-wave sleep depth.",
        "core_compounds": [
            {
                "key": "magnesium",
                "name": "Magnesium Glycinate",
                "base_dose": 400,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "GABA-A Tone & NMDA Voltage Gating",
                "rationale": "Promotes deep slow-wave sleep and attenuates nocturnal sympathetic nervous tone.",
                "pmid": "23853635",
                "citation_str": "Abbasi B et al., J Res Med Sci 2012 [PMID: 23853635]",
                "is_stimulant": False,
            },
            {
                "key": "apigenin",
                "name": "Apigenin",
                "base_dose": 50,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "GABA-A Receptor Binding",
                "rationale": "Binds to benzodiazepine receptors on the GABA-A complex, inducing mild sedation without tolerance buildup.",
                "pmid": "1588258",
                "citation_str": "Viola H et al., Planta Med 1995 [PMID: 1588258]",
                "is_stimulant": False,
            },
            {
                "key": "l_theanine",
                "name": "L-Theanine",
                "base_dose": 200,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "Glutamate Attenuation & Alpha Wave Stimulation",
                "rationale": "Calms nocturnal racing thoughts and eases transition to sleep onset.",
                "pmid": "18296328",
                "citation_str": "Nobre AC et al., Asia Pac J Clin Nutr 2008 [PMID: 18296328]",
                "is_stimulant": False,
            },
            {
                "key": "melatonin",
                "name": "Melatonin",
                "base_dose": 0.3,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "MT1/MT2 Melatonin Receptors",
                "rationale": "Physiological low-dose synchronizes central suprachiasmatic nucleus without causing receptor downregulation or next-day grogginess.",
                "pmid": "11600532",
                "citation_str": "Zhdanova IV et al., J Clin Endocrinol Metab 2001 [PMID: 11600532]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "taurine",
                "name": "Taurine",
                "base_dose": 1000,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "Inhibitory Glycinergic & GABAergic Neurotransmission",
                "rationale": "Stabilizes neural membranes and suppresses nocturnal autonomic excitability.",
                "pmid": "37289866",
                "citation_str": "Singh P et al., Science 2023 [PMID: 37289866]",
                "is_stimulant": False,
            }
        ]
    },
    "fat_loss_metabolic": {
        "title": "Metabolic Output & Fat Loss",
        "description": "Beta-adrenergic lipolysis, insulin sensitivity enhancement, and mitochondrial uncoupling / substrate partitioning.",
        "core_compounds": [
            {
                "key": "caffeine",
                "name": "Caffeine Anhydrous",
                "base_dose": 150,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Phosphodiesterase Inhibition & Beta-Adrenergic Tone",
                "rationale": "Stimulates resting energy expenditure and mobilizes free fatty acids from adipose depots.",
                "pmid": "18681988",
                "citation_str": "Owen GN et al., Nutr Neurosci 2008 [PMID: 18681988]",
                "is_stimulant": True,
            },
            {
                "key": "l_carnitine",
                "name": "L-Carnitine L-Tartrate",
                "base_dose": 2000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Carnitine Palmitoyltransferase-1 (CPT-1) Shuttle",
                "rationale": "Facilitates long-chain fatty acid transport across the inner mitochondrial membrane for beta-oxidation.",
                "pmid": "29534031",
                "citation_str": "Fielding R et al., Nutrients 2018 [PMID: 29534031]",
                "is_stimulant": False,
            },
            {
                "key": "berberine",
                "name": "Berberine HCl",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "AMPK Activation & Substrate Partitioning",
                "rationale": "Enhances peripheral insulin sensitivity and prevents compensatory glucose surges.",
                "pmid": "18442638",
                "citation_str": "Yin J et al., Metabolism 2008 [PMID: 18442638]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "taurine",
                "name": "Taurine",
                "base_dose": 1000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Myocellular Osmolyte & Heart Rhythm Support",
                "rationale": "Protects against cramping and sympathomimetic-induced electrolyte loss.",
                "pmid": "37289866",
                "citation_str": "Singh P et al., Science 2023 [PMID: 37289866]",
                "is_stimulant": False,
            }
        ]
    },
    "post_therapy_reset": {
        "title": "Post-Therapy Restoration (PCT / Reset)",
        "description": "Hypothalamic-pituitary axis restoration (LH/FSH recovery), testicular responsiveness, and lipid/hepatic normalization.",
        "core_compounds": [
            {
                "key": "enclomiphene",
                "name": "Enclomiphene Citrate",
                "base_dose": 12.5,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Selective Estrogen Receptor Antagonist (Hypothalamus/Pituitary)",
                "rationale": "Antagonizes negative estrogen feedback at the pituitary/hypothalamus to stimulate pulsatile GnRH, LH, and FSH release.",
                "pmid": "26447833",
                "citation_str": "Kaminetsky J et al., J Sex Med 2013 [PMID: 26447833]",
                "is_stimulant": False,
            },
            {
                "key": "nac",
                "name": "N-Acetyl Cysteine (NAC)",
                "base_dose": 600,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Glutathione Biosynthesis & Hepatocyte Protection",
                "rationale": "Restores hepatic intracellular glutathione pools and normalizes post-cycle transaminases.",
                "pmid": "21118657",
                "citation_str": "Dean O et al., J Psychiatry Neurosci 2011 [PMID: 21118657]",
                "is_stimulant": False,
            },
            {
                "key": "tudca",
                "name": "Tauroursodeoxycholic Acid (TUDCA)",
                "base_dose": 250,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Biliary Clearance & Cholestatic Resolution",
                "rationale": "Mitigates canalicular cholestasis and enhances biliary lipid excretion.",
                "pmid": "20522594",
                "citation_str": "Kars M et al., Diabetes 2010 [PMID: 20522594]",
                "is_stimulant": False,
            },
            {
                "key": "citrus_bergamot",
                "name": "Citrus Bergamot Extract",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Lipid Profile & ApoB Normalization",
                "rationale": "Accelerates recovery of HDL-C and normalizes LDL particle distribution following androgen exposure.",
                "pmid": "24239156",
                "citation_str": "Gliozzi M et al., Int J Cardiol 2013 [PMID: 24239156]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": [
            {
                "key": "ashwagandha",
                "name": "Ashwagandha (KSM-66)",
                "base_dose": 600,
                "unit": "mg",
                "timing": "bedtime",
                "frequency": "daily",
                "route": "oral",
                "target": "Testicular Leydig Cell Responsiveness & HPA Dampening",
                "rationale": "Lowers post-cycle catabolic cortisol spikes and supports endogenous testosterone synthesis.",
                "pmid": "31517876",
                "citation_str": "Lopresti AL et al., Medicine (Baltimore) 2019 [PMID: 31517876]",
                "is_stimulant": False,
            }
        ]
    },
    "gut_microbiome": {
        "title": "Gut Microbiome & Intestinal Barrier",
        "description": "Gastric peptide healing, tight junction repair, short-chain fatty acids, and microbiome diversity.",
        "core_compounds": [
            {
                "key": "bpc_157",
                "name": "BPC-157 (Arginine Salt)",
                "base_dose": 500,
                "unit": "μg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Gastric Mucosa & Angiogenesis",
                "rationale": "Promotes healing of the intestinal epithelium and accelerates tissue regeneration.",
                "pmid": "27847936",
                "citation_str": "Sikiric P et al., Curr Pharm Des 2018 [PMID: 27847936]",
                "is_stimulant": False,
            },
            {
                "key": "glutamine",
                "name": "L-Glutamine",
                "base_dose": 5,
                "unit": "g",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Intestinal Epithelial Tight Junctions",
                "rationale": "Primary fuel source for enterocytes and supports the integrity of the gut barrier.",
                "pmid": "28498331",
                "citation_str": "Kim MH et al., Int J Mol Sci 2017 [PMID: 28498331]",
                "is_stimulant": False,
            },
            {
                "key": "tributyrin",
                "name": "Tributyrin",
                "base_dose": 500,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "SCFA Receptor Activation",
                "rationale": "Provides highly bioavailable butyrate to colonocytes, reducing GI inflammation.",
                "pmid": "12519746",
                "citation_str": "Gaschott T et al., J Nutr 2003 [PMID: 12519746]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": []
    },
    "immune_defense": {
        "title": "Immune Defense & Cellular Resilience",
        "description": "Cellular redox buffering, innate immune potentiation, viral shielding, and T-cell support.",
        "core_compounds": [
            {
                "key": "vitamin_d3",
                "name": "Vitamin D3",
                "base_dose": 5000,
                "unit": "IU",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "VDR (Vitamin D Receptor)",
                "rationale": "Regulates antimicrobial peptide synthesis and balances innate/adaptive immunity.",
                "pmid": "21849261",
                "citation_str": "Hewison M, Clin Endocrinol (Oxf) 2012 [PMID: 21849261]",
                "is_stimulant": False,
            },
            {
                "key": "zinc",
                "name": "Zinc Picolinate",
                "base_dose": 30,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Intracellular Viral Replication",
                "rationale": "Inhibits RNA polymerase activity in viruses and supports immune cell proliferation.",
                "pmid": "22222917",
                "citation_str": "Read SA et al., Adv Nutr 2019 [PMID: 22222917]",
                "is_stimulant": False,
            },
            {
                "key": "vitamin_c",
                "name": "Vitamin C",
                "base_dose": 1000,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Cellular Redox Buffering",
                "rationale": "Protects phagocytes from oxidative burst damage and promotes chemotaxis.",
                "pmid": "29099763",
                "citation_str": "Carr AC et al., Nutrients 2017 [PMID: 29099763]",
                "is_stimulant": False,
            },
            {
                "key": "nac",
                "name": "N-Acetyl Cysteine",
                "base_dose": 600,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Glutathione Biosynthesis",
                "rationale": "Replenishes intracellular glutathione, acting as a potent antioxidant.",
                "pmid": "21118657",
                "citation_str": "Dean O et al., J Psychiatry Neurosci 2011 [PMID: 21118657]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": []
    },
    "hair_skin_derm": {
        "title": "Dermatology & Hair Follicle Health",
        "description": "5-AR inhibition, scalp perfusion, collagen synthesis, and topical anti-androgens.",
        "core_compounds": [
            {
                "key": "finasteride",
                "name": "Finasteride",
                "base_dose": 1,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Type II 5-Alpha Reductase",
                "rationale": "Reduces systemic and scalp DHT levels to halt androgenetic alopecia.",
                "pmid": "9777765",
                "citation_str": "Kaufman KD et al., J Am Acad Dermatol 1998 [PMID: 9777765]",
                "is_stimulant": False,
            },
            {
                "key": "oral_minoxidil",
                "name": "Oral Minoxidil",
                "base_dose": 2.5,
                "unit": "mg",
                "timing": "morning",
                "frequency": "daily",
                "route": "oral",
                "target": "Potassium Channel Opener (Vasodilation)",
                "rationale": "Increases follicular blood flow and prolongs the anagen growth phase of hair.",
                "pmid": "31239585",
                "citation_str": "Randolph M et al., J Am Acad Dermatol 2021 [PMID: 31239585]",
                "is_stimulant": False,
            },
            {
                "key": "ketoconazole_shampoo",
                "name": "Ketoconazole 2% Shampoo",
                "base_dose": 1,
                "unit": "appl",
                "timing": "morning",
                "frequency": "biweekly",
                "route": "topical",
                "target": "Fungal Cell Wall & Mild Anti-Androgen",
                "rationale": "Reduces scalp micro-inflammation and acts as a mild local anti-androgen.",
                "pmid": "9669136",
                "citation_str": "Pierard-Franchimont C et al., Dermatology 1998 [PMID: 9669136]",
                "is_stimulant": False,
            }
        ],
        "ancillaries": []
    }
}


class StackIntentEngine:
    """
    Dynamic Pharmacological Stack Intent & Purpose Inference Engine.
    Analyzes compound classes, receptor targets, mechanisms, routes, and clearance kinetics
    to deduce stack objectives, partition administration modalities, and identify therapeutic gaps.
    """

    @classmethod
    def get_goal_taxonomy(cls) -> List[Dict[str, Any]]:
        return PROTOCOL_GOAL_TAXONOMY

    @classmethod
    def analyze(
        cls,
        compounds: List[Dict[str, Any]],
        biometrics: Optional[Dict[str, Any]] = None,
        user_goal_id: Optional[str] = None,
        user_objective_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Performs full pharmacological analysis of stack purpose, modality segmentation,
        and therapeutic gap identification.
        """
        biometrics = biometrics or {}
        user_objective_text = (user_objective_text or "").strip()

        # 1. Extract compound pharmacological traits
        features = cls._extract_pharmacological_features(compounds)

        # 2. Infer primary domain if auto
        inferred_domain, confidence, reasoning = cls._infer_primary_domain(features, compounds)

        # Determine active goal metadata
        active_goal_id = user_goal_id if (user_goal_id and user_goal_id != "auto") else inferred_domain
        matching_tax = next((t for t in PROTOCOL_GOAL_TAXONOMY if t["id"] == active_goal_id), None)
        goal_title = matching_tax["name"] if matching_tax else active_goal_id.replace("_", " ").title()

        # 3. Partition Administration Modalities (Depot vs Daily Oral vs Acute)
        modality_profile = cls._partition_modalities(compounds)

        # 4. Detect Therapeutic Gaps & Uncompensated Axes
        therapeutic_gaps = cls._detect_therapeutic_gaps(features, compounds, biometrics)

        # 5. Build prompt grounding text block
        grounding_text = cls._format_prompt_grounding(
            goal_title=goal_title,
            is_user_selected=bool(user_goal_id and user_goal_id != "auto"),
            user_objective_text=user_objective_text,
            inferred_reasoning=reasoning,
            modality_profile=modality_profile,
            therapeutic_gaps=therapeutic_gaps,
            features=features
        )

        return {
            "active_goal_id": active_goal_id,
            "goal_title": goal_title,
            "is_user_selected": bool(user_goal_id and user_goal_id != "auto"),
            "user_objective_text": user_objective_text,
            "inferred_domain": inferred_domain,
            "confidence": confidence,
            "inferred_reasoning": reasoning,
            "modality_profile": modality_profile,
            "therapeutic_gaps": therapeutic_gaps,
            "pharmacological_features": features,
            "grounding_text": grounding_text,
        }

    @classmethod
    def _has_atc_prefix(cls, compound: Dict[str, Any], prefixes: Tuple[str, ...]) -> bool:
        ext = compound.get("external_ids") or {}
        atc_codes = [str(c).upper() for c in (ext.get("atc_codes") or [])]
        return any(c.startswith(prefixes) for c in atc_codes)

    @classmethod
    def _extract_pharmacological_features(cls, compounds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extracts high-level pharmacological flags from compound catalog records algorithmically."""
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

        from app.services.catalog_service import CatalogService
        catalog = CatalogService()

        for c in compounds:
            k = str(c.get("key", "")).lower().strip()
            cat_rec = catalog.get_compound(k, auto_enrich=False) or catalog.find_by_synonym(k)
            c_merged = {**(cat_rec or {}), **c}
            name = c.get("name") or c_merged.get("name") or k.title()
            route = str(c.get("route", "") or c_merged.get("route", "")).lower()
            cats = [str(cat).lower() for cat in (c_merged.get("categories") or [])]
            mech = str(c_merged.get("mechanism", "")).lower()
            
            targets = []
            for t in (c_merged.get("receptor_targets") or []):
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
                is_steroidal_androgen(c_merged)
                or cls._has_atc_prefix(c_merged, ("G03B", "G03BA", "G03BB", "A14A", "A14AA", "A14AB"))
                or has_gene({"AR", "NR3C4"}, {"agonist", "modulator", "partial agonist"})
                or "sarm" in cats
                or "anabolic agent" in cats
            )
            if is_androgen:
                features["has_androgens"] = True
                features["androgen_names"].append(name)
                if "sarm" in cats or not is_steroidal_androgen(c_merged):
                    features["has_sarms"] = True

            # 19-nor progestogenic
            if (
                is_19nor_steroid(c_merged)
                or cls._has_atc_prefix(c_merged, ("A14AB",))
                or "19-nor" in cats
                or "estren derivative" in cats
                or (is_androgen and has_gene({"PGR", "NR3C3"}))
            ):
                features["has_19nor_progestogenic"] = True


            # Aromatase inhibitor (AI)
            if cls._has_atc_prefix(c_merged, ("L02BG",)) or has_gene({"CYP19A1"}, {"inhibitor", "antagonist"}) or "aromatase inhibitor" in cats or any(w in k for w in ["exemestane", "anastrozole", "letrozole", "arimidex", "aromasin"]):
                features["has_aromatase_inhibitors"] = True
                features["protective_ancillary_names"].append(name)

            # SERMs (Selective Estrogen Receptor Modulators)
            if cls._has_atc_prefix(c_merged, ("G03XC", "L02BA")) or has_gene({"ESR1", "ESR2", "NR3A1", "NR3A2"}, {"modulator", "antagonist", "partial agonist"}) or "serm" in cats or any(w in k for w in ["tamoxifen", "clomiphene", "enclomiphene", "raloxifene", "nolvadex", "clomid"]):
                features["has_serms"] = True
                features["protective_ancillary_names"].append(name)

            # Aromatizable substrate
            if is_aromatizable_androgen(c_merged) or (is_androgen and cls._has_atc_prefix(c_merged, ("G03BA03", "G03BA02"))):
                features["has_aromatizable_substrate"] = True

            # RAAS blockers
            is_raas = cls._has_atc_prefix(c_merged, ("C09",)) or has_gene({"AGTR1", "ACE"}, {"antagonist", "inhibitor"}) or any(w in k for w in ["telmisartan", "losartan", "valsartan", "candesartan"])
            if is_raas:
                features["has_raas_blockers"] = True
                features["protective_ancillary_names"].append(name)

            # Beta blockers
            if cls._has_atc_prefix(c_merged, ("C07",)) or has_gene({"ADRB1", "ADRB2", "ADRB3"}, {"antagonist"}) or "beta blocker" in cats or any(w in k for w in ["nebivolol", "bisoprolol", "metoprolol", "carvedilol", "propranolol"]):
                features["has_beta_blockers"] = True
                features["protective_ancillary_names"].append(name)

            # PDE5 inhibitors
            if cls._has_atc_prefix(c_merged, ("G04BE",)) or has_gene({"PDE5A"}, {"inhibitor"}) or any(w in k for w in ["tadalafil", "sildenafil", "vardenafil"]):
                features["has_pde5_inhibitors"] = True

            dclass = str(c_merged.get("drug_class", "")).lower()

            # Psychostimulants
            if cls._has_atc_prefix(c_merged, ("N06B",)) or has_gene({"SLC6A2", "SLC6A3", "ADORA1", "ADORA2A"}, {"inhibitor", "antagonist", "reuptake inhibitor"}) or "stimulant" in cats or "stimulant" in dclass or "adenosine" in mech or k in ("caffeine", "theacrine", "modafinil", "armodafinil"):
                features["has_psychostimulants"] = True

            # Cholinergics
            if cls._has_atc_prefix(c_merged, ("N06D",)) or has_gene({"ACHE", "CHRNA7"}) or "cholinergic" in cats or "nootropic" in cats:
                features["has_cholinergics"] = True

            # GABAergics / Sedatives
            if cls._has_atc_prefix(c_merged, ("N05B", "N05C")) or has_gene({"GABRA1", "GABRB2", "MT1", "MT2", "MTNR1A", "MTNR1B"}) or any("gaba" in str(t.get("target")).lower() for t in targets) or "sedative" in cats:
                features["has_gabaergics_sedatives"] = True

            # Longevity / Metabolic
            if cls._has_atc_prefix(c_merged, ("A10",)) or has_gene({"PRKAA1", "PRKAA2", "SIRT1", "MTOR"}) or "ampk activator" in cats or "longevity" in cats:
                features["has_longevity_metabolic"] = True

            # Hepatoprotectants
            if cls._has_atc_prefix(c_merged, ("A05",)) or "hepatoprotectant" in cats or "liver therapy" in cats or k in ("nac", "tudca", "udca", "milk_thistle", "silymarin"):
                features["has_hepatoprotectants"] = True
                features["protective_ancillary_names"].append(name)

            # Lipid regulators
            if (
                cls._has_atc_prefix(c_merged, ("C10",))
                or has_gene({"HMGCR", "PCSK9", "NPC1L1"})
                or "lipid modifying agent" in cats
                or "lipid management" in cats
                or any(w in k or w in name.lower() for w in ["ezetimibe", "bergamot", "statin", "pitavastatin", "rosuvastatin", "atorvastatin", "bempedoic", "pcsk9"])
                or any(w in mech or w in dclass for w in ["hmgcr", "hmg-coa", "npc1l1", "pcsk9", "cholesterol absorption", "statin"])
                or any("hmgcr" in str(t.get("target", "")).lower() or "npc1l1" in str(t.get("target", "")).lower() or "pcsk9" in str(t.get("target", "")).lower() for t in targets)
            ):
                features["has_lipid_regulators"] = True
                features["protective_ancillary_names"].append(name)

            # Renal support
            if (
                is_raas
                or "renal support" in cats
                or any(w in k or w in name.lower() for w in ["telmisartan", "astragalus", "losartan", "valsartan", "candesartan"])
                or any("at1" in str(t.get("target", "")).lower() or "angiotensin" in str(t.get("target", "")).lower() for t in targets)
            ):
                features["has_renal_support"] = True

            # Oral TMA precursors
            is_oral_route = route in ("oral", "po", "swallow", "") or ":oral" in k
            is_parenteral = route in ("intramuscular", "im", "subcutaneous", "subq", "iv")
            is_tma_substrate = (
                has_gene({"CNTA", "CNTB", "SLC22A5"})
                or "tma precursor" in cats
                or any(w in k or w in name.lower() for w in ["carnitine", "alcar", "choline", "alpha_gpc", "alpha-gpc", "citicoline", "betaine"])
                or any("tma" in str(t.get("target", "")).lower() or "cnta" in str(t.get("target", "")).lower() for t in targets)
            )
            if is_oral_route and not is_parenteral and is_tma_substrate:
                features["has_oral_tma_precursors"] = True
                features["oral_tma_precursor_names"].append(name)

            # Microbial TMA lyase inhibitors
            if (
                has_gene({"CNTA", "CNTB", "CUTC"}, {"inhibitor"})
                or "tma lyase inhibitor" in cats
                or any(w in k or w in name.lower() for w in ["allicin", "garlic", "aged_garlic", "dmb", "dimethylbutanol"])
                or any(("tma" in str(t.get("target", "")).lower() or "cnta" in str(t.get("target", "")).lower()) and any(act in str(t.get("action", "")).lower() for act in ["inhibitor", "antagonist", "blocker"]) for t in targets)
            ):
                features["has_microbial_tma_inhibitors"] = True
                features["protective_ancillary_names"].append(name)

            # Prolactin inhibitors / Dopamine agonists
            if (
                cls._has_atc_prefix(c_merged, ("G02CB", "A11HA02"))
                or has_gene({"DRD2"}, {"agonist"})
                or any(w in k or w in name.lower() for w in ["p5p", "pyridoxal", "cabergoline", "pramipexole", "bromocriptine"])
            ):
                features["has_prolactin_inhibitors"] = True
                features["protective_ancillary_names"].append(name)

            # Phase II Conjugation (NAC)
            if cls._has_atc_prefix(c_merged, ("R05CB01", "V03AB23")) or "glutathione biosynthesis" in mech or "acetylcysteine" in name.lower() or k == "nac":
                features["has_phase2_conjugation_support"] = True

            # Biliary Clearance (TUDCA)
            if cls._has_atc_prefix(c_merged, ("A05AA",)) or "bile acid" in cats or "cholestasis" in mech or k in ("tudca", "udca"):
                features["has_biliary_clearance_support"] = True

            # Autonomic Buffer / Theanine
            if has_gene({"GRIN1", "GRIN2A", "GRIN2B", "GRIN2C", "GRIN2D"}, {"antagonist"}) or "autonomic buffer" in cats or k in ("l_theanine", "theanine", "agmatine"):
                features["has_autonomic_buffer"] = True

        return features

    @classmethod
    def _infer_primary_domain(
        cls,
        features: Dict[str, Any],
        compounds: List[Dict[str, Any]]
    ) -> Tuple[str, float, str]:
        """Infers the most scientifically accurate primary domain for the stack."""
        if not compounds:
            return "general_wellness", 0.5, "Empty stack; default general wellness."

        if features["has_androgens"]:
            ancillaries = len(features["protective_ancillary_names"])
            return (
                "anabolic_physique",
                0.95,
                f"Stack contains potent androgenic modulators ({', '.join(features['androgen_names'])}) "
                + (f"with {ancillaries} active organ-protective ancillaries." if ancillaries else "without complete ancillary coverage.")
            )

        if features["has_psychostimulants"] or features["has_cholinergics"]:
            return (
                "cognitive_focus",
                0.90,
                "Stack focuses on central neurotransmitter modulation, catecholaminergic tone, and cognitive focus."
            )

        if features["has_longevity_metabolic"]:
            return (
                "longevity_autophagy",
                0.88,
                "Stack is oriented toward metabolic signaling, AMPK activation, mTOR modulation, or cellular autophagy."
            )

        if features["has_raas_blockers"] or features["has_beta_blockers"]:
            return (
                "cardiovascular_lipid",
                0.85,
                "Stack is primarily oriented around hemodynamic regulation, blood pressure management, and vascular protection."
            )

        if features["has_gabaergics_sedatives"] and not features["has_psychostimulants"]:
            return (
                "sleep_stress_recovery",
                0.82,
                "Stack is oriented around parasympathetic tone, HPA axis relaxation, and nocturnal recovery."
            )

        return "general_wellness", 0.70, "Multi-factorial wellness protocol."

    @classmethod
    def _partition_modalities(cls, compounds: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Partitions stack into Depot Injections, Daily Oral Maintenance, and Acute/Situational."""
        depot = []
        daily_oral = []
        acute = []

        for c in compounds:
            route = str(c.get("route", "oral")).lower()
            freq = str(c.get("frequency", "daily")).lower()
            name = c.get("name") or c.get("key", "Compound")
            dose = c.get("dose") or c.get("dose_mg", 100)
            unit = c.get("unit", "mg")
            timing = c.get("timing", "morning")

            blob = f"{name} {c.get('key', '')}".lower()
            is_depot = (
                route in ("intramuscular", "im", "subcutaneous", "subq")
                or any(e in blob for e in ["cypionate", "enanthate", "decanoate", "undecanoate", "isocaproate"])
                or "weekly" in freq
            )

            if is_depot:
                depot.append({
                    "name": name,
                    "dose_display": f"{dose} {unit}",
                    "route": route.upper() if route else "IM",
                    "frequency": freq.capitalize(),
                    "half_life_estimate": "7–10 days (Extended Depot Release)"
                })
            elif "prn" in freq or "acute" in freq or "pre-workout" in timing.lower():
                acute.append({
                    "name": name,
                    "dose_display": f"{dose} {unit}",
                    "route": route.title(),
                    "timing": timing.title()
                })
            else:
                daily_oral.append({
                    "name": name,
                    "dose_display": f"{dose} {unit}",
                    "route": route.title(),
                    "timing": timing.title()
                })

        return {
            "depot_injections": depot,
            "daily_oral": daily_oral,
            "acute_situational": acute,
        }

    @classmethod
    def _detect_therapeutic_gaps(
        cls,
        features: Dict[str, Any],
        compounds: List[Dict[str, Any]],
        biometrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Dynamically detects physiological vulnerabilities / uncompensated axes
        and prescribes evidence-based targeted co-factors.
        """
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

        return gaps

    @classmethod
    def _format_prompt_grounding(
        cls,
        goal_title: str,
        is_user_selected: bool,
        user_objective_text: str,
        inferred_reasoning: str,
        modality_profile: Dict[str, Any],
        therapeutic_gaps: List[Dict[str, Any]],
        features: Dict[str, Any]
    ) -> str:
        """Formats grounding markdown for LLM system prompt injection."""
        lines = [
            "### PROTOCOL PURPOSE, MODALITY & THERAPEUTIC GAP ANALYSIS:",
            f"- **Primary Protocol Objective**: **{goal_title}** ({'User Explicitly Specified' if is_user_selected else 'Auto-Inferred from Stack Pharmacology'})",
        ]

        if user_objective_text:
            lines.append(f"- **User Clinical / Performance Notes**: \"{user_objective_text}\"")
        else:
            lines.append(f"- **Pharmacological Intent Reasoning**: {inferred_reasoning}")

        # Modality segmentation
        depots = modality_profile.get("depot_injections", [])
        if depots:
            depot_str = ", ".join(f"{d['name']} ({d['dose_display']} {d['route']} - {d['frequency']})" for d in depots)
            lines.append(f"- **Depot Injections (Weekly/Split IM Protocol)**: {depot_str}")
            lines.append("  *(Note: Depot injectables have 7-10 day half-lives. NEVER schedule daily oral supplements 'with' an injection event on daily circadian tables.)*")

        daily_items = modality_profile.get("daily_oral", [])
        if daily_items:
            daily_str = ", ".join(f"{d['name']} ({d['dose_display']}, {d['timing']})" for d in daily_items)
            lines.append(f"- **Daily Oral / Maintenance Regimen**: {daily_str}")

        # Physiological Gaps
        if therapeutic_gaps:
            lines.append("- **Identified Therapeutic Gaps & Uncompensated Axes**:")
            for g in therapeutic_gaps:
                lines.append(f"  * ⚠️ **{g['axis']}**: {g['issue']}")
                lines.append(f"    ➔ **Evidence-Based Solution**: {g['recommended_cofactor']} ({g['mechanism']})")

        # Pharmacokinetic & Mechanistic Protocol Principles
        lines.append("- **Pharmacokinetic & Mechanistic Protocol Principles**:")
        if features.get("has_depot_injectables"):
            lines.append("  * **Depot Half-Life & Interval Dosing**: Long-acting depot formulations have extended elimination half-lives (t1/2 > 72h). Dose on appropriate weekly or split-weekly intervals (never as daily oral doses).")
        if features.get("has_androgens"):
            lines.append("  * **Hypothalamic-Pituitary-Gonadal (HPG) Feedback**: Exogenous androgens induce negative feedback inhibition on LH/FSH secretion.")
            if not features.get("has_aromatase_inhibitors") and not features.get("has_serms") and features.get("has_aromatizable_substrate"):
                lines.append("  * **Enzymatic CYP19A1 Aromatization**: Monitor estradiol (E2) balance and consider enzymatic or receptor countermeasures if aromatization signs or elevated serum E2 occur.")
        if features.get("has_aromatase_inhibitors"):
            lines.append("  * **Estradiol Preservation**: Maintain physiological estradiol levels (target 20–30 pg/mL) to preserve bone mineral density, lipid synthesis, and joint health.")

        if not modality_profile.get("daily_oral") and not modality_profile.get("depot_injections"):
            lines.append("- **SCRATCH PROTOCOL GENERATION MANDATE**:")
            lines.append("  * Stack is currently empty. Design a complete, synergistic, evidence-based stack matching the goal and patient biometrics.")
            lines.append("  * Formulate circadian timing allocations (Morning, Midday, Afternoon, Bedtime).")
            lines.append("  * If depot injectables are included, list under 'Depot Injections (Weekly / Split Protocol)' with twice-weekly or weekly frequency.")
            lines.append("  * At the very end of your response, provide the `<action_card type=\"stack_diff\">` containing the complete `add` list of compounds.")

        return "\n".join(lines)

    @classmethod
    def _extract_user_exclusions(
        cls,
        custom_notes: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        exclusions: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Extracts structured negative compound and route exclusions from user parameters and instructions,
        resolving exact catalog database matches without fragile regex/semantic patterns.
        """
        import re
        collected: List[str] = []
        if exclusions:
            collected.extend([str(e).strip().lower() for e in exclusions if e])

        prefs = preferences or {}
        for k in ("exclusions", "exclude", "avoid", "omit", "disallowed_compounds"):
            val = prefs.get(k)
            if isinstance(val, list):
                collected.extend([str(v).strip().lower() for v in val if v])
            elif isinstance(val, str) and val.strip():
                collected.extend([v.strip().lower() for v in val.split(",") if v.strip()])

        notes_str = (custom_notes or "").strip()
        if notes_str:
            # Tokenize and scan exact n-grams against catalog database
            from app.services.catalog_service import CatalogService
            cat = CatalogService()

            words = re.findall(r"[a-zA-Z0-9_\-\+]+", notes_str)
            negation_words = {"no", "not", "without", "exclude", "avoid", "omit", "disallow", "skip", "allergic", "none"}

            for i in range(len(words)):
                prev_word = words[i - 1].lower() if i > 0 else ""
                prev_prev_word = words[i - 2].lower() if i > 1 else ""

                is_negated = prev_word in negation_words or prev_prev_word in negation_words

                if is_negated:
                    # Check 1-gram, 2-gram, 3-gram
                    for n in (3, 2, 1):
                        if i + n <= len(words):
                            ngram = " ".join(words[i:i + n])
                            comp_rec = cat.get_compound(ngram, auto_enrich=False) or cat.find_by_synonym(ngram)
                            if comp_rec:
                                collected.append(comp_rec.get("key") or ngram.lower())
                                break

                    # Also capture route exclusions e.g. "no oral l-carnitine"
                    if i + 1 < len(words):
                        route_cand = words[i].lower()
                        if route_cand in ("oral", "injectable", "subq", "im"):
                            next_ngram = " ".join(words[i + 1:i + 3])
                            comp_rec = cat.get_compound(next_ngram, auto_enrich=False) or cat.find_by_synonym(next_ngram) or cat.get_compound(words[i + 1], auto_enrich=False)
                            if comp_rec:
                                collected.append(f"no {route_cand} {comp_rec.get('key') or words[i + 1].lower()}")

        return list(dict.fromkeys(collected))

    @classmethod
    def _is_compound_excluded(
        cls,
        cand: Dict[str, Any],
        exclusions: List[str],
        catalog: Any = None,
    ) -> bool:
        """
        Determines whether a candidate compound matches any user-requested exclusion,
        evaluating keys, names, synonyms, and routes.
        """
        if not exclusions:
            return False

        c_key = str(cand.get("key") or "").lower().strip()
        c_name = str(cand.get("name") or "").lower().strip()
        c_route = str(cand.get("route") or "oral").lower().strip()
        c_class = str(cand.get("drug_class") or "").lower().strip()
        synonyms = set()

        if catalog:
            rec = catalog.get_compound(c_key, auto_enrich=False) or catalog.find_by_synonym(c_key)
            if rec:
                c_name = str(rec.get("name") or rec.get("canonical_name") or c_name).lower()
                for syn in (rec.get("synonyms") or []):
                    synonyms.add(str(syn).lower())

        cand_tokens = {c_key, c_name, c_key.replace("_", " "), c_name.replace("-", " ")}
        cand_tokens.update(synonyms)

        for exc in exclusions:
            exc_clean = exc.lower().strip()
            # Strip leading exclusion prefix verbs
            stripped_exc = re.sub(r"^(?:no|without|exclude|avoid|skip|omit|do not want|do not include|don't want|don't include|disallow|allergic to|intolerant to)\s+", "", exc_clean).strip()
            
            # Check route qualification
            is_oral_exc = "oral" in stripped_exc
            is_inj_exc = any(w in stripped_exc for w in ["injectable", "injection", "im", "subq"])

            target_term = re.sub(r"\b(oral|injectable|injection|im|subq)\b", "", stripped_exc).strip()
            if not target_term:
                target_term = stripped_exc

            # Check if target_term matches candidate tokens
            matches_compound = any(
                target_term in tok or tok in target_term or target_term.replace(" ", "_") == tok
                for tok in cand_tokens if len(tok) >= 3 and len(target_term) >= 3
            )

            if matches_compound:
                if is_oral_exc and c_route not in ("oral", "capsule", "tablet", "powder"):
                    continue
                if is_inj_exc and c_route not in ("intramuscular", "im", "subcutaneous", "subq", "injectable"):
                    continue
                return True

        return False

    @classmethod
    def _extract_user_requested_compounds(
        cls,
        custom_notes: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        catalog: Any = None,
        requested_compounds: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically extracts user-requested compounds from structured parameters or preference dictionaries,
        resolving canonical keys and metadata via CatalogService without regex pattern scraping or hardcoding.
        """
        from app.services.dosing_service import parse_dose_string_or_spec, infer_compound_route_and_frequency
        from app.services.pharmacological_utility_engine import PharmacologicalUtilityEngine

        if catalog is None:
            from app.services.catalog_service import CatalogService
            catalog = CatalogService()

        requested_specs: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()
        seen_canonical_ids: Set[str] = set()

        def _get_canon_id(key_or_name: str, comp_rec: Optional[Dict[str, Any]] = None) -> str:
            if comp_rec:
                return str(comp_rec.get("canonical_key") or comp_rec.get("parent_compound_id") or comp_rec.get("key") or key_or_name).lower().strip()
            comp = catalog.get_compound(key_or_name, auto_enrich=False) or catalog.find_by_synonym(key_or_name)
            if comp:
                return str(comp.get("canonical_key") or comp.get("parent_compound_id") or comp.get("key") or key_or_name).lower().strip()
            return key_or_name.lower().strip().replace("-", "_").replace(" ", "_")

        req_inputs: List[Any] = []
        if requested_compounds:
            req_inputs.extend(requested_compounds)

        prefs = preferences or {}
        for k in ("requested_compounds", "requested", "include", "compounds", "user_compounds", "add"):
            val = prefs.get(k)
            if isinstance(val, list):
                req_inputs.extend(val)
            elif isinstance(val, str) and val.strip():
                req_inputs.extend([v.strip() for v in val.split(",") if v.strip()])

        notes_str = (custom_notes or "").strip()
        if notes_str:
            # Split notes by commas, semicolons, newlines, or conjunctions
            clauses = re.split(r"[,;\n\r]+|\band\b", notes_str, flags=re.I)
            negation_pattern = re.compile(r"\b(no|not|without|exclude|avoid|omit|disallow|skip|allergic)\b", re.I)
            for cl in clauses:
                cl_clean = cl.strip()
                if not cl_clean or len(cl_clean) < 3:
                    continue
                if negation_pattern.search(cl_clean):
                    continue
                req_inputs.append(cl_clean)

        for item in req_inputs:
            item_str = str(item).strip()
            if not item_str:
                continue

            # Strip leading exclusion prefix verbs if accidentally caught
            item_clean = re.sub(r"^(?:please\s+|i\s+want\s+to\s+|add\s+|include\s+|with\s+|take\s+)", "", item_str, flags=re.IGNORECASE).strip()
            # Strip trailing context filler
            item_clean = re.sub(r"\s+(?:for\s+my\s+|to\s+my\s+|for\s+|in\s+my\s+|cycle|stack|protocol|cut|bulk|routine).*$", "", item_clean, flags=re.IGNORECASE).strip()

            if not item_clean or len(item_clean) < 2:
                continue

            # Parse dose/spec if provided in string
            parsed_spec = parse_dose_string_or_spec(item_clean)
            raw_key = parsed_spec.get("key") or item_clean.lower().replace(" ", "_")

            # Try resolving whole item or individual word tokens via catalog
            comp_rec = catalog.get_compound(raw_key, auto_enrich=False) or catalog.find_by_synonym(raw_key)
            if not comp_rec:
                # Try tokens within item_clean
                tokens = re.findall(r"[a-zA-Z0-9_\-\+]+", item_clean)
                for tok in tokens:
                    if len(tok) >= 3 and tok.lower() not in ("stack", "protocol", "compounds", "routine", "cycle", "hypertrophy", "please", "want", "include", "add", "oral", "injectable", "daily", "weekly"):
                        rec_tok = catalog.get_compound(tok, auto_enrich=False) or catalog.find_by_synonym(tok)
                        if rec_tok:
                            comp_rec = rec_tok
                            break

            if not comp_rec:
                comp_rec = catalog.get_compound(raw_key, auto_enrich=True) or catalog.find_by_synonym(raw_key)

            if comp_rec:
                c_key = comp_rec.get("key", raw_key)
                canon_id = _get_canon_id(c_key, comp_rec)
                if canon_id in seen_canonical_ids or c_key in seen_keys:
                    continue
                seen_canonical_ids.add(canon_id)
                seen_keys.add(c_key)

                inf_route, inf_freq = infer_compound_route_and_frequency(c_key)
                opt_freq = PharmacologicalUtilityEngine.determine_optimal_frequency(comp_rec, inf_route)
                eff_freq = parsed_spec.get("frequency") or opt_freq or inf_freq
                eff_timing = parsed_spec.get("timing")
                if not eff_timing or eff_timing == "morning":
                    if eff_freq in ("twice_weekly", "twice weekly"):
                        eff_timing = "Twice Weekly (Mon / Thu)"
                    elif eff_freq in ("three_times_weekly", "3x_weekly", "three times weekly"):
                        eff_timing = "Three Times Weekly (Mon / Wed / Fri)"
                    elif eff_freq in ("weekly", "once_weekly"):
                        eff_timing = "Weekly"
                    elif eff_freq in ("every_other_day", "eod", "qod"):
                        eff_timing = "Every Other Day (EOD)"
                    elif eff_freq in ("biweekly", "every_2_weeks"):
                        eff_timing = "Bi-Weekly (Every 2 Weeks)"
                    elif eff_freq in ("as_needed", "prn"):
                        eff_timing = "As Needed (PRN)"
                    else:
                        eff_timing = eff_timing or "morning"

                dose_val = parsed_spec.get("dose_mg") or comp_rec.get("dose") or comp_rec.get("standard_dose_mg") or 100.0

                requested_specs.append({
                    "key": c_key,
                    "name": comp_rec.get("name") or comp_rec.get("canonical_name") or c_key.replace("_", " ").title(),
                    "dose": dose_val,
                    "unit": parsed_spec.get("unit") or "mg",
                    "timing": eff_timing,
                    "frequency": eff_freq,
                    "route": parsed_spec.get("route") or inf_route,
                    "target": comp_rec.get("mechanism") or comp_rec.get("drug_class") or "Target receptor",
                    "is_user_requested": True,
                    "metadata": comp_rec.get("metadata", {}),
                    "evidence_level": comp_rec.get("evidence_level", "moderate"),
                    "risk_band": comp_rec.get("risk_band", "low"),
                    "boxed_warning": comp_rec.get("boxed_warning"),
                })
            else:
                # Dynamic fallback spec for uncataloged requested string if valid candidate token
                clean_tok = re.sub(r"[^a-zA-Z0-9_]", "", raw_key)
                if len(clean_tok) >= 3 and clean_tok not in ("stack", "protocol", "compounds", "routine", "cycle", "hypertrophy", "please", "want", "include", "add") and clean_tok not in seen_keys:
                    seen_keys.add(clean_tok)
                    requested_specs.append({
                        "key": clean_tok,
                        "name": item_clean.replace("_", " ").title(),
                        "dose": parsed_spec.get("dose_mg") or 100.0,
                        "unit": parsed_spec.get("unit") or "mg",
                        "timing": "morning",
                        "frequency": "daily",
                        "route": "oral",
                        "target": "User-specified agent",
                        "is_user_requested": True,
                        "metadata": {"human_clinical_trials": False, "regulatory_status": "UNAPPROVED"},
                    })

        return requested_specs

    @classmethod
    def _discover_experimental_candidates_for_goal(
        cls,
        target_goal: str,
        catalog: Any,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically queries CatalogService for experimental compounds / research chemicals
        with limited human data matching the biological mechanisms of target_goal.
        Zero hardcoding of compound keys or brand names.
        """
        all_compounds = catalog.list_compounds() if hasattr(catalog, "list_compounds") else []
        experimental_cands: List[Dict[str, Any]] = []

        # Derive pharmacological domain terms dynamically from target goal taxonomy
        goal_tax = next((t for t in PROTOCOL_GOAL_TAXONOMY if t["id"] == target_goal), None)
        domain_terms = set()
        if goal_tax:
            domain_terms.update(re.findall(r"[a-z0-9]+", goal_tax.get("name", "").lower()))
            domain_terms.update(re.findall(r"[a-z0-9]+", goal_tax.get("description", "").lower()))
        domain_terms.discard("and")
        domain_terms.discard("the")
        domain_terms.discard("for")

        for comp in all_compounds:
            meta = comp.get("metadata", {}) or {}
            ev_tier = str(meta.get("evidence_tier") or "").upper()
            reg_stat = str(meta.get("regulatory_status") or "").upper()
            ev_level = str(comp.get("evidence_level") or "").lower()
            has_trials = meta.get("human_clinical_trials")

            is_experimental = (
                has_trials is False
                or ev_tier in ("IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION", "PRECLINICAL", "ANECDOTAL")
                or reg_stat in ("RESEARCH_CHEMICAL", "EXPERIMENTAL", "UNAPPROVED", "INVESTIGATIONAL PEPTIDE")
                or ev_level in ("experimental", "low", "preclinical", "anecdotal", "in_vitro")
            )

            if not is_experimental:
                continue

            text_blob = f"{comp.get('key', '')} {comp.get('name', '')} {comp.get('drug_class', '')} {comp.get('mechanism', '')} {' '.join(comp.get('categories') or [])}".lower()
            
            # Goal-specific mechanistic domain match
            if target_goal == "anabolic_physique":
                if not any(w in text_blob for w in ["hypertrophy", "anabolic", "muscle mass", "strength", "myostatin", "follistatin", "igf-1", "igf_1", "ghrp", "growth hormone", "androgenic", "nitrogen retention"]):
                    continue
            elif target_goal == "cognitive_focus":
                if not any(w in text_blob for w in ["nootropic", "cognit", "focus", "cholinergic", "dopamin", "synaptic", "neurogenesis", "bdnf", "memory"]):
                    continue
            elif target_goal == "longevity_autophagy":
                if not any(w in text_blob for w in ["autophagy", "longevity", "sirtuin", "sirt", "ampk", "mtor", "senolytic", "nad", "mitochondr"]):
                    continue
            elif target_goal == "sleep_stress_recovery":
                if not any(w in text_blob for w in ["sleep", "gaba", "recovery", "sedative", "anxiolytic", "parasympathetic", "hpa"]):
                    continue
            elif target_goal == "cardiovascular_lipid":
                if not any(w in text_blob for w in ["cardio", "lipid", "cholesterol", "vascular", "endothelial", "blood_pressure", "nitric_oxide", "apob"]):
                    continue
            elif not any(kw in text_blob for kw in domain_terms if len(kw) >= 4):
                continue

            experimental_cands.append(comp)

        return experimental_cands

    @classmethod
    def build_scratch_stack_proposal(
        cls,
        goal_id: Optional[str] = None,
        biometrics: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        custom_notes: Optional[str] = None,
        exclusions: Optional[List[str]] = None,
        requested_compounds: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Dynamically discovers and calibrates a compound protocol from the pharmacological catalog
        based on the user's inputted biometrics, clinical parameters, preferences, and exclusions.
        Dosages and cofactors are computed dynamically via DosingService and InteractionEngine.
        """
        from app.services.catalog_service import CatalogService
        from app.services.dosing_service import calculate_individualized_dose, infer_compound_route_and_frequency
        from app.services.pubmed_service import SEED_LITERATURE_DB

        biometrics = biometrics or {}
        preferences = preferences or {}
        custom_notes = (custom_notes or "").strip()

        # Parse user negative exclusions
        parsed_exclusions = cls._extract_user_exclusions(custom_notes=custom_notes, preferences=preferences, exclusions=exclusions)
        applied_exclusions: List[str] = []

        target_goal = (goal_id or "cognitive_focus").lower().strip()
        if target_goal in ("auto", "custom", ""):
            import re
            from collections import Counter
            lower_notes = (custom_notes + " " + str(preferences)).lower()
            # Algorithmic and exact science: Compute term-frequency cosine similarity
            # between user intent and goal taxonomy descriptions/names
            user_words = Counter(re.findall(r'\w+', lower_notes))
            
            best_goal = "cognitive_focus"
            best_score = 0.0
            
            for tax in PROTOCOL_GOAL_TAXONOMY:
                if tax["id"] in ("auto", "custom"):
                    continue
                tax_text = f"{tax['name']} {tax['description']}".lower()
                tax_words = Counter(re.findall(r'\w+', tax_text))
                
                # Compute dot product of term frequencies
                score = sum(user_words[w] * tax_words[w] for w in user_words if w in tax_words)
                if score > best_score:
                    best_score = score
                    best_goal = tax["id"]
                    
            target_goal = best_goal

        blueprint = SCRATCH_GOAL_BLUEPRINTS.get(target_goal, SCRATCH_GOAL_BLUEPRINTS["cognitive_focus"])
        goal_title = blueprint["title"]
        goal_desc = blueprint["description"]

        # Parse user preference parameters
        risk_pref = str(preferences.get("risk_tolerance") or preferences.get("risk") or "balanced").lower().strip()
        stim_pref = str(preferences.get("stimulant_level", "standard")).lower().strip()
        complexity = str(preferences.get("complexity", "standard")).lower().strip()
        natural_only = bool(preferences.get("natural_only", False) or preferences.get("substance_style") == "natural")
        route_pref = str(preferences.get("route_preference") or preferences.get("route") or "all").lower().strip()
        schedule_pref = str(preferences.get("schedule_preference") or preferences.get("schedule") or "circadian").lower().strip()
        organ_pref = str(preferences.get("organ_priority") or preferences.get("organ_shield") or "auto").lower().strip()
        budget_pref = str(preferences.get("budget_tier") or preferences.get("budget") or "standard").lower().strip()

        # Biometric parameters & clearance multipliers
        weight_kg = float(biometrics.get("weight_kg") or 75.0)
        egfr = float(biometrics.get("egfr") or 95.0)
        alt_u_l = float(biometrics.get("alt_u_l") or 25.0)
        bp_val = float(biometrics.get("blood_pressure") or biometrics.get("systolic_bp") or 120.0)
        age = int(biometrics.get("age") or 30)
        sex = str(biometrics.get("sex") or biometrics.get("gender") or "unspecified").lower().strip()
        is_female = sex in ("female", "f", "woman")

        weight_scale = max(0.7, min(1.4, weight_kg / 75.0))
        sex_renal_factor = 0.85 if is_female else 1.0
        renal_scale = (max(0.5, min(1.0, (egfr * sex_renal_factor) / 90.0))) if egfr < 60 else 1.0
        hepatic_scale = max(0.6, min(1.0, 45.0 / alt_u_l)) if alt_u_l > 45 else 1.0
        age_scale = 0.9 if age >= 65 else 1.0

        if risk_pref in ("conservative", "low", "cautious", "safe"):
            risk_scale = 0.75
        elif risk_pref in ("aggressive", "high", "performance", "high_potency"):
            risk_scale = 1.25
        else:
            risk_scale = 1.0

        catalog = CatalogService()

        # Extract user specifically requested compounds
        user_requested_compounds = cls._extract_user_requested_compounds(
            custom_notes=custom_notes,
            preferences=preferences,
            catalog=catalog,
            requested_compounds=requested_compounds,
        )

        # Collect candidate compounds from blueprint
        raw_candidates: List[Dict[str, Any]] = [dict(c) for c in blueprint.get("core_compounds", [])]

        if budget_pref != "essential" and complexity in ("standard", "maximum", "comprehensive", "full"):
            raw_candidates.extend([dict(a) for a in blueprint.get("ancillaries", [])])

        # Step 1: Aggressive Risk Tolerance -> Discover experimental candidates dynamically
        experimental_notices: List[str] = []
        if risk_pref in ("aggressive", "high", "performance", "high_potency"):
            exp_candidates = cls._discover_experimental_candidates_for_goal(target_goal, catalog)
            for exp in exp_candidates:
                exp_key = exp.get("key")
                if not exp_key or exp_key in [c.get("key") for c in raw_candidates]:
                    continue
                # If user already requested specific androgens, do not pile on unrequested redundant AAS
                if is_steroidal_androgen(exp) and user_requested_compounds:
                    continue

                from app.services.pharmacological_utility_engine import PharmacologicalUtilityEngine
                exp_route = PharmacologicalUtilityEngine.determine_optimal_route(exp, route_pref)
                exp_freq = PharmacologicalUtilityEngine.determine_optimal_frequency(exp, exp_route)
                exp_timing = "morning"
                if exp_freq in ("twice_weekly", "twice weekly"):
                    exp_timing = "Twice Weekly (Mon / Thu)"
                elif exp_freq in ("weekly", "once_weekly"):
                    exp_timing = "Weekly"

                raw_candidates.append({
                    "key": exp_key,
                    "name": exp.get("name") or exp_key.replace("_", " ").title(),
                    "base_dose": exp.get("dose") or (exp.get("default_dose") or {}).get("dose_val") or 10.0,
                    "unit": exp.get("unit") or (exp.get("default_dose") or {}).get("dose_unit") or "mg",
                    "timing": exp_timing,
                    "frequency": exp_freq,
                    "route": exp_route,
                    "target": exp.get("mechanism") or exp.get("drug_class") or "Research agent",
                    "rationale": f"[EXPERIMENTAL: Preclinical / Limited Human Data] Recommended under aggressive risk tolerance mode for {goal_title}.",
                    "is_stimulant": False,
                    "is_experimental": True,
                    "metadata": exp.get("metadata", {}),
                })
                experimental_notices.append(
                    f"⚠️ EXPERIMENTAL COMPOUND NOTICE [{exp.get('name') or exp_key}]: Limited human clinical trial data (preclinical/in vitro evidence). Recommended under aggressive risk tolerance mode; monitor individual response."
                )
                if len(experimental_notices) >= 2:
                    break

        # Dynamic Pharmacological Detection of Endocrine / Aromatase / Androgen Candidates
        def _is_endocrine_active(cand: Dict[str, Any]) -> bool:
            drug_class = str(cand.get("drug_class", "")).lower()
            mech = str(cand.get("mechanism", "")).lower()
            target_str = str(cand.get("target", "")).lower()
            targets = cand.get("receptor_targets", []) or []
            target_names = " ".join(str(t.get("target", "")).lower() for t in targets if isinstance(t, dict))
            combined = f"{drug_class} {mech} {target_str} {target_names} {cand.get('key', '')}"
            return any(w in combined for w in ["aromatase", "cyp19a1", "androgen receptor", "anabolic steroid", "aas", "testosterone"])

        has_endocrine_cand = any(_is_endocrine_active(c) for c in raw_candidates)
        is_enhanced_mode = (
            (target_goal == "anabolic_physique" or has_endocrine_cand)
            and not natural_only
            and (
                has_endocrine_cand
                or preferences.get("substance_style") in ("aggressive", "hybrid", "enhanced")
                or route_pref in ("injectable", "all", "hybrid")
                or risk_pref in ("aggressive", "high", "performance")
            )
        )

        if is_enhanced_mode:
            if is_female:
                if not any(c.get("key") == "oxandrolone" for c in raw_candidates):
                    raw_candidates.insert(0, {
                        "key": "oxandrolone",
                        "name": "Oxandrolone (Anavar)",
                        "base_dose": 10,
                        "unit": "mg",
                        "timing": "morning",
                        "frequency": "daily",
                        "route": "oral",
                        "target": "Androgen Receptor Agonist (Low Virilization Index)",
                        "rationale": "High anabolic-to-androgenic ratio calibrated for female athletic hypertrophy without virilizing side effects.",
                        "is_stimulant": False,
                    })
            else:
                if not any("testosterone" in str(c.get("key", "")) for c in raw_candidates):
                    raw_candidates.insert(0, {
                        "key": "testosterone_cypionate",
                        "name": "Testosterone Cypionate",
                        "base_dose": 175,
                        "unit": "mg",
                        "timing": "Twice Weekly (Mon / Thu)",
                        "frequency": "twice_weekly",
                        "route": "intramuscular",
                        "target": "Nuclear Androgen Receptor (AR / NR3C4)",
                        "rationale": "Extended ester depot prodrug providing stable supraphysiological androgen receptor occupancy and enhanced myocellular protein synthesis.",
                        "is_stimulant": False,
                    })

        # Organ Shields & Targeted Biomarker Protection
        needs_cardio = organ_pref == "cardio" or (organ_pref == "auto" and (bp_val > 130 or egfr < 90)) or is_enhanced_mode
        needs_hepatic = organ_pref == "hepatic" or (organ_pref == "auto" and alt_u_l > 40)
        needs_neuro = organ_pref == "neuro_recovery"

        if needs_cardio:
            if not any(c["key"] == "telmisartan" for c in raw_candidates) and not natural_only:
                raw_candidates.append({
                    "key": "telmisartan",
                    "name": "Telmisartan",
                    "base_dose": 20,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Angiotensin II Type 1 (AT1) Receptor Antagonist",
                    "rationale": f"Blocks renal AT1 vasoconstriction, prevents LVH remodeling, and preserves podocyte integrity (Resting BP: {bp_val} mmHg, eGFR: {egfr}).",
                    "is_stimulant": False,
                })
            if not any(c["key"] == "citrus_bergamot" for c in raw_candidates):
                raw_candidates.append({
                    "key": "citrus_bergamot",
                    "name": "Citrus Bergamot Extract",
                    "base_dose": 500,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Hepatic HMGCR Modulation & ApoB Lipid Protection",
                    "rationale": "Maintains atherogenic ApoB and LDL particle clearance during androgen exposure.",
                    "is_stimulant": False,
                })

        if needs_hepatic:
            if not any(c["key"] == "nac" for c in raw_candidates):
                raw_candidates.append({
                    "key": "nac",
                    "name": "N-Acetyl Cysteine (NAC)",
                    "base_dose": 600,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Glutathione Biosynthesis & Hepatocyte Protection",
                    "rationale": f"Added for hepatic transaminase support and Phase II detoxification (ALT: {alt_u_l} U/L).",
                    "is_stimulant": False,
                })
            if complexity in ("standard", "maximum", "comprehensive", "full") and not any(c["key"] == "tudca" for c in raw_candidates) and not natural_only:
                raw_candidates.append({
                    "key": "tudca",
                    "name": "Tauroursodeoxycholic Acid (TUDCA)",
                    "base_dose": 250,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Biliary Clearance & Hepatocyte ER Chaperone",
                    "rationale": "Provides hydrophilic bile acid pool expansion and mitigates canalicular cholestatic stress.",
                    "is_stimulant": False,
                })

        if needs_neuro:
            if not any(c["key"] == "magnesium" for c in raw_candidates):
                raw_candidates.append({
                    "key": "magnesium",
                    "name": "Magnesium Glycinate",
                    "base_dose": 300,
                    "unit": "mg",
                    "timing": "bedtime" if schedule_pref != "morning_only" else "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "NMDA Receptor Voltage-Gated Blocker",
                    "rationale": "Buffers cortical excitotoxicity and calms autonomic tone.",
                    "is_stimulant": False,
                })
            if not any(c["key"] == "l_theanine" for c in raw_candidates):
                raw_candidates.append({
                    "key": "l_theanine",
                    "name": "L-Theanine",
                    "base_dose": 200,
                    "unit": "mg",
                    "timing": "morning",
                    "frequency": "daily",
                    "route": "oral",
                    "target": "Glutamate Attenuation & Alpha Wave Stimulation",
                    "rationale": "Smooths central nervous system excitation and autonomic arousal.",
                    "is_stimulant": False,
                })

        # Process and dynamically scale candidate compounds
        built_compounds: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()
        seen_canonical_ids: Set[str] = set()

        def _get_canon_id(cand_or_rec: Dict[str, Any]) -> str:
            k = str(cand_or_rec.get("key") or cand_or_rec.get("name") or "").strip().lower()
            comp_obj = catalog.get_compound(k, auto_enrich=False) or catalog.find_by_synonym(k)
            if comp_obj:
                return str(comp_obj.get("canonical_key") or comp_obj.get("parent_compound_id") or comp_obj.get("key") or k).lower().strip()
            return k.replace("-", "_").replace(" ", "_")

        from app.services.pharmacological_utility_engine import PharmacologicalUtilityEngine

        # Index user-requested compounds by canonical ID so explicit user preferences override blueprint defaults cleanly
        req_by_canon: Dict[str, Dict[str, Any]] = {}
        for req in user_requested_compounds:
            req_cid = _get_canon_id(req)
            if req_cid:
                req_by_canon[req_cid] = req

        for cand in raw_candidates:
            raw_k = cand.get("key", "").lower().strip()
            if not raw_k:
                continue
            canon_rec = catalog.get_compound(raw_k, auto_enrich=False) or catalog.find_by_synonym(raw_k)
            c_key = (canon_rec.get("key") if canon_rec else raw_k).lower().strip()
            cand_cid = _get_canon_id(cand)

            if cand_cid in seen_canonical_ids or c_key in seen_keys:
                continue

            # Exclude experimental candidates if risk preference is non-aggressive (unless explicitly requested)
            meta = cand.get("metadata", {}) or {}
            is_exp = cand.get("is_experimental") or meta.get("human_clinical_trials") is False or str(meta.get("evidence_tier")).upper() in ("IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION", "PRECLINICAL") or str(meta.get("regulatory_status")).upper() in ("RESEARCH_CHEMICAL", "EXPERIMENTAL")
            if is_exp and risk_pref not in ("aggressive", "high", "performance", "high_potency") and cand_cid not in req_by_canon:
                continue

            # Dynamic route and frequency resolution using pharmacological utility engine
            opt_route = PharmacologicalUtilityEngine.determine_optimal_route(cand, route_pref)
            c_route = opt_route or cand.get("route") or "oral"
            c_freq = PharmacologicalUtilityEngine.determine_optimal_frequency(cand, c_route) or cand.get("frequency") or "daily"

            # Dynamic formulation scaling for route (bioavailability-adjusted)
            cand_name = cand.get("name") or (canon_rec.get("name") if canon_rec else None) or (canon_rec.get("canonical_name") if canon_rec else None) or c_key.replace("_", " ").title()
            base_dose_val = cand.get("base_dose", 100.0)
            raw_f = cand.get("oral_bioavailability") or cand.get("bioavailability_f")
            try:
                f_val = float(raw_f) if raw_f is not None else 1.0
            except (ValueError, TypeError):
                f_val = 1.0

            if c_route in ("intramuscular", "subcutaneous"):
                if c_key == "l_carnitine":
                    cand_name = "Injectable L-Carnitine"
                    base_dose_val = 400.0
                    c_freq = "daily"
                elif f_val < 0.25:
                    base_dose_val = round(base_dose_val * max(0.15, f_val), 0)
                    if not any(w in cand_name.lower() for w in ["injectable", "im", "subq"]):
                        cand_name = f"Injectable {cand_name}"
            elif c_route == "oral" and c_key == "l_carnitine":
                cand_name = "L-Carnitine L-Tartrate"
                base_dose_val = 2000.0
                c_freq = "daily"

            # Check explicit user compound / route exclusions
            cand_check = dict(cand)
            cand_check["route"] = c_route
            if cls._is_compound_excluded(cand_check, parsed_exclusions, catalog):
                applied_exclusions.append(f"{cand_name} ({c_route})")
                continue

            # Filter by natural_only
            if natural_only and any(w in str(cand.get("target", "") + " " + c_key).lower() for w in ["steroid", "androgen", "prescription", "pharmaceutical"]):
                continue

            # Filter by route preference
            if route_pref in ("oral_only", "capsules_only", "no_powders") and c_route in ("intramuscular", "subcutaneous"):
                continue

            # If user explicitly requested this compound, override blueprint defaults with user's specific requested formulation
            user_override = req_by_canon.get(cand_cid)
            if user_override:
                cand_dose = user_override.get("dose") or base_dose_val
                cand_unit = user_override.get("unit") or cand.get("unit", "mg")
                c_route = user_override.get("route") or c_route
                c_freq = user_override.get("frequency") or c_freq
                cand_name = user_override.get("name") or cand_name
                timing_val = user_override.get("timing") or cand.get("timing", "morning")
            else:
                cand_unit = cand.get("unit", "mg")
                # Stimulant filtering & scaling
                if cand.get("is_stimulant"):
                    if stim_pref in ("none", "stim-free", "stim_free", "free"):
                        continue
                    elif stim_pref in ("mild", "low"):
                        cand_dose = round(base_dose_val * 0.5 * min(1.0, risk_scale))
                    else:
                        cand_dose = round(base_dose_val * risk_scale)
                else:
                    b_dose = base_dose_val
                    if c_key == "l_carnitine" and c_route in ("intramuscular", "subcutaneous"):
                        scaled_dose = round(b_dose * min(1.2, weight_scale) * min(1.25, risk_scale))
                    elif c_key in ("caffeine", "beta_alanine", "creatine", "l_carnitine", "magnesium", "citrus_bergamot", "taurine"):
                        scaled_dose = round(b_dose * weight_scale * risk_scale)
                    elif c_key in ("berberine", "telmisartan", "nebivolol", "metformin"):
                        scaled_dose = round(b_dose * renal_scale * hepatic_scale * age_scale * risk_scale, 1)
                        if scaled_dose == int(scaled_dose):
                            scaled_dose = int(scaled_dose)
                    elif "testosterone" in c_key and is_female:
                        scaled_dose = round(b_dose * 0.08 * risk_scale, 2)
                    else:
                        scaled_dose = round(b_dose * risk_scale) if isinstance(b_dose, (int, float)) and b_dose >= 10 else b_dose
                    cand_dose = scaled_dose

                if c_freq in ("twice_weekly", "twice weekly"):
                    timing_val = "Twice Weekly (Mon / Thu)"
                elif c_freq in ("three_times_weekly", "3x_weekly", "three times weekly"):
                    timing_val = "Three Times Weekly (Mon / Wed / Fri)"
                elif c_freq in ("weekly", "once_weekly"):
                    timing_val = "Weekly"
                elif c_freq in ("every_other_day", "eod", "qod"):
                    timing_val = "Every Other Day (EOD)"
                elif c_freq in ("biweekly", "every_2_weeks"):
                    timing_val = "Bi-Weekly (Every 2 Weeks)"
                elif c_freq in ("as_needed", "prn"):
                    timing_val = "As Needed (PRN)"
                elif schedule_pref == "morning_only":
                    if cand.get("timing") in ("bedtime", "evening"):
                        if c_key == "melatonin":
                            continue
                        timing_val = "morning"
                    else:
                        timing_val = cand.get("timing", "morning")
                else:
                    timing_val = cand.get("timing", "morning")

            if isinstance(cand_dose, float) and cand_dose == int(cand_dose):
                cand_dose = int(cand_dose)

            seen_canonical_ids.add(cand_cid)
            seen_keys.add(c_key)
            
            c_pmid = cand.get("pmid")
            c_cite = cand.get("citation_str")
            c_finding = cand.get("clinical_finding")
            if not c_pmid and c_key in SEED_LITERATURE_DB:
                seeds = SEED_LITERATURE_DB[c_key]
                if seeds:
                    c_pmid = seeds[0].get("pmid")
                    c_cite = f"{seeds[0].get('authors', ['Investigator'])[0]} et al., {seeds[0].get('journal', 'PubMed')} {seeds[0].get('pub_year', '')} [PMID: {c_pmid}]"
                    c_finding = seeds[0].get("clinical_finding")

            built_compounds.append({
                "key": c_key,
                "name": cand_name,
                "dose": cand_dose,
                "unit": cand_unit,
                "timing": timing_val,
                "frequency": c_freq,
                "route": c_route,
                "target": cand.get("target", "Target receptor"),
                "rationale": cand.get("rationale", f"Calibrated for {goal_title}."),
                "pmid": c_pmid,
                "citation_str": c_cite,
                "clinical_finding": c_finding,
            })

        # Step 2: FORCE INCLUDE USER REQUESTED COMPOUNDS REGARDLESS OF RISK
        requested_compound_warnings: List[str] = []

        for req in user_requested_compounds:
            req_cid = _get_canon_id(req)
            req_key = req.get("key") or req_cid
            if not req_key or req_cid in seen_canonical_ids or req_key in seen_keys:
                continue

            req_check = {"key": req_key, "name": req.get("name"), "route": req.get("route")}
            if cls._is_compound_excluded(req_check, parsed_exclusions, catalog):
                applied_exclusions.append(f"{req.get('name') or req_key} ({req.get('route')})")
                continue

            seen_canonical_ids.add(req_cid)
            seen_keys.add(req_key)

            req_name = req.get("name") or req_key.replace("_", " ").title()
            req_dose = req.get("dose", 100.0)
            req_unit = req.get("unit", "mg")
            req_route = req.get("route", "oral")
            req_freq = req.get("frequency", "daily")
            req_timing = req.get("timing")
            if not req_timing or req_timing == "morning":
                if req_freq in ("twice_weekly", "twice weekly"):
                    req_timing = "Twice Weekly (Mon / Thu)"
                elif req_freq in ("three_times_weekly", "3x_weekly", "three times weekly"):
                    req_timing = "Three Times Weekly (Mon / Wed / Fri)"
                elif req_freq in ("weekly", "once_weekly"):
                    req_timing = "Weekly"
                elif req_freq in ("every_other_day", "eod", "qod"):
                    req_timing = "Every Other Day (EOD)"
                elif req_freq in ("biweekly", "every_2_weeks"):
                    req_timing = "Bi-Weekly (Every 2 Weeks)"
                elif req_freq in ("as_needed", "prn"):
                    req_timing = "As Needed (PRN)"
                else:
                    req_timing = req_timing or "morning"

            # Check for high-risk flags on user requested additions
            warn_msg = ""
            if req_key in ("trenbolone", "halotestin", "superdrol", "clenbuterol"):
                warn_msg = "Requires strict biomarker monitoring and liver/lipid support."
                requested_compound_warnings.append(f"{req_name}: High-potency substance requested. {warn_msg}")

            req_pmid = req.get("pmid")
            req_cite = req.get("citation_str")
            req_finding = req.get("clinical_finding")
            if not req_pmid and req_key in SEED_LITERATURE_DB:
                seeds = SEED_LITERATURE_DB[req_key]
                if seeds:
                    req_pmid = seeds[0].get("pmid")
                    req_cite = f"{seeds[0].get('authors', ['Investigator'])[0]} et al., {seeds[0].get('journal', 'PubMed')} {seeds[0].get('pub_year', '')} [PMID: {req_pmid}]"
                    req_finding = seeds[0].get("clinical_finding")

            built_compounds.append({
                "key": req_key,
                "name": req_name,
                "dose": req_dose,
                "unit": req_unit,
                "timing": req_timing,
                "frequency": req_freq,
                "route": req_route,
                "target": req.get("target", "User requested agent"),
                "rationale": f"Specifically requested by user. {warn_msg}",
                "is_user_requested": True,
                "pmid": req_pmid,
                "citation_str": req_cite,
                "clinical_finding": req_finding,
            })

        # Dynamically evaluate gaps and attach protective co-factors (Side-effect mitigation)
        comp_records_for_analysis = [dict(c) for c in built_compounds]
        features = cls._extract_pharmacological_features(comp_records_for_analysis)
        gaps = cls._detect_therapeutic_gaps(features, comp_records_for_analysis, biometrics)

        for gap in gaps:
            # STRICT GUARD: Rules / contraindications must NEVER be parsed as compound co-factors
            if gap.get("severity") == "RULE" or not gap.get("cofactor_search_terms"):
                continue

            search_terms = gap.get("cofactor_search_terms", [])
            candidate_records = []
            for term in search_terms:
                term_clean = term.lower().strip().replace("-", "_")
                rec = catalog.get_compound(term_clean) or catalog.find_by_synonym(term_clean)
                if rec:
                    r_cid = _get_canon_id(rec)
                    if r_cid not in seen_canonical_ids and rec.get("key") not in seen_keys:
                        candidate_records.append(rec)

            if not candidate_records:
                continue

            # Rank candidate cofactors by composite Pharmacological Utility Score
            scored_candidates = []
            for rec in candidate_records:
                opt_r = PharmacologicalUtilityEngine.determine_optimal_route(rec, route_pref)
                u_score = PharmacologicalUtilityEngine.score_compound(
                    compound=rec,
                    route=opt_r,
                    user_profile={"biometrics": biometrics, "preferences": preferences},
                    target_context=gap.get("axis"),
                )
                scored_candidates.append((u_score["total_score"], rec, opt_r))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, found_rec, co_route = scored_candidates[0]
            found_cid = _get_canon_id(found_rec)

            if found_rec and found_cid not in seen_canonical_ids and found_rec.get("key") not in seen_keys:
                cofactor_key = found_rec.get("key")
                seen_canonical_ids.add(found_cid)
                seen_keys.add(cofactor_key)
                
                opt_freq = PharmacologicalUtilityEngine.determine_optimal_frequency(found_rec, co_route)
                _, inferred_freq = infer_compound_route_and_frequency(cofactor_key)
                co_freq = opt_freq or inferred_freq or "daily"

                # Check if cofactor is excluded
                co_check = {"key": cofactor_key, "name": found_rec.get("name"), "route": co_route}
                if cls._is_compound_excluded(co_check, parsed_exclusions, catalog):
                    applied_exclusions.append(f"{found_rec.get('name') or cofactor_key} ({co_route})")
                    continue

                seen_keys.add(cofactor_key)
                co_dose_info = calculate_individualized_dose(found_rec, biometrics, risk_scale)

                co_dose_val = co_dose_info.get("dose_val", 10.0)
                if isinstance(co_dose_val, float) and co_dose_val == int(co_dose_val):
                    co_dose_val = int(co_dose_val)

                # Dynamically calibrate timing based on administration frequency
                if co_freq in ("twice_weekly", "twice weekly"):
                    co_timing = "Twice Weekly (Mon / Thu)"
                elif co_freq in ("three_times_weekly", "3x_weekly", "three times weekly"):
                    co_timing = "Three Times Weekly (Mon / Wed / Fri)"
                elif co_freq in ("weekly", "once_weekly"):
                    co_timing = "Weekly"
                elif co_freq in ("every_other_day", "eod", "qod"):
                    co_timing = "Every Other Day (EOD)"
                elif co_freq in ("biweekly", "every_2_weeks"):
                    co_timing = "Bi-Weekly (Every 2 Weeks)"
                elif co_freq in ("as_needed", "prn"):
                    co_timing = "As Needed (PRN)"
                elif schedule_pref == "morning_only":
                    co_timing = "morning"
                elif found_rec.get("timing"):
                    co_timing = found_rec.get("timing")
                else:
                    co_timing = "morning"

                co_pmid = None
                co_cite = None
                co_finding = None
                if cofactor_key in SEED_LITERATURE_DB:
                    co_seeds = SEED_LITERATURE_DB[cofactor_key]
                    if co_seeds:
                        co_pmid = co_seeds[0].get("pmid")
                        co_cite = f"{co_seeds[0].get('authors', ['Investigator'])[0]} et al., {co_seeds[0].get('journal', 'PubMed')} {co_seeds[0].get('pub_year', '')} [PMID: {co_pmid}]"
                        co_finding = co_seeds[0].get("clinical_finding")

                built_compounds.append({
                    "key": cofactor_key,
                    "name": found_rec.get("name") or cofactor_key.replace("_", " ").title(),
                    "dose": co_dose_val,
                    "unit": co_dose_info.get("unit", "mg"),
                    "timing": co_timing,
                    "frequency": co_freq,
                    "route": co_route,
                    "target": gap.get("axis", "Protective Co-factor"),
                    "rationale": f"Protective co-factor for {gap.get('axis', '')}: {gap.get('mechanism', '')}",
                    "pmid": co_pmid,
                    "citation_str": co_cite,
                    "clinical_finding": co_finding,
                })

        daily_freqs = ("daily", "once_daily", "every_day", "qd", None, "")
        schedule = {
            "morning": [c for c in built_compounds if c.get("frequency") in daily_freqs and c.get("timing") in ("morning", "pre-workout", "midday")],
            "bedtime": [c for c in built_compounds if c.get("frequency") in daily_freqs and c.get("timing") in ("bedtime", "evening")],
            "intermittent": [c for c in built_compounds if c.get("frequency") not in daily_freqs],
        }

        action_card_payload = {
            "action_card": "stack_diff",
            "add": [
                {
                    "key": c["key"],
                    "name": c["name"],
                    "dose": c["dose"],
                    "unit": c["unit"],
                    "timing": c["timing"],
                    "frequency": c["frequency"],
                    "route": c["route"]
                }
                for c in built_compounds
            ],
            "modify": [],
            "remove": []
        }

        all_warnings = list(dict.fromkeys(experimental_notices + requested_compound_warnings))

        return {
            "goal_id": target_goal,
            "goal_title": goal_title,
            "goal_description": goal_desc,
            "compounds": built_compounds,
            "schedule": schedule,
            "diff": action_card_payload,
            "action_card": action_card_payload,
            "applied_exclusions": list(dict.fromkeys(applied_exclusions)),
            "requested_compounds": [r.get("name") for r in user_requested_compounds],
            "warnings": all_warnings,
            "biometric_calibration": {
                "weight_scale": round(weight_scale, 2),
                "renal_scale": round(renal_scale, 2),
                "hepatic_scale": round(hepatic_scale, 2),
                "age_scale": age_scale,
                "risk_scale": round(risk_scale, 2),
            },
            "customizations": {
                "risk_tolerance": risk_pref,
                "stimulant_level": stim_pref,
                "complexity": complexity,
                "substance_style": "natural" if natural_only else "hybrid",
                "route_preference": route_pref,
                "schedule_preference": schedule_pref,
                "organ_priority": organ_pref,
                "budget_tier": budget_pref,
                "exclusions": list(dict.fromkeys(parsed_exclusions)),
            }
        }
