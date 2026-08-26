from __future__ import annotations

import copy
import difflib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("healthai.catalog_service")

DEFAULT_CATALOG_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "healthai_catalog.db")


CORE_SUPPLEMENT_LIBRARY: Dict[str, Dict[str, Any]] = {
    "astaxanthin": {
        "name": "Astaxanthin",
        "canonical_name": "Astaxanthin",
        "synonyms": ["asta", "astareal", "astaxanthine"],
        "drug_class": "Dietary Supplement / Carotenoid Antioxidant",
        "categories": ["Dietary Supplement", "Antioxidant", "Carotenoid", "Mitochondrial Support"],
        "molecular_weight": 596.84,
        "logp": 6.8,
        "oral_bioavailability": 0.35,
        "volume_of_distribution": 2.5,
        "protein_binding": 85.0,
        "receptor_targets": [
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"},
            {"target": "Cellular Redox Homeostasis & Mitochondrial Bioenergetics", "action": "antioxidant", "family": "Redox Defense"}
        ],
    },
    "coq10": {
        "name": "Coenzyme Q10",
        "canonical_name": "Coenzyme Q10 (Ubiquinone / Ubiquinol)",
        "synonyms": ["ubiquinone", "ubiquinol", "coenzymeq10"],
        "drug_class": "Dietary Supplement / Mitochondrial Quinone",
        "categories": ["Dietary Supplement", "Antioxidant", "Mitochondrial Support"],
        "molecular_weight": 863.34,
        "logp": 10.5,
        "oral_bioavailability": 0.10,
        "volume_of_distribution": 3.0,
        "protein_binding": 90.0,
        "receptor_targets": [
            {"target": "Cellular Redox Homeostasis & Mitochondrial Bioenergetics", "action": "agonist", "family": "Mitochondrial Bioenergetics"}
        ],
    },
    "milk_thistle": {
        "name": "Milk Thistle",
        "canonical_name": "Milk Thistle (Silymarin / Silybin)",
        "synonyms": ["silymarin", "silybin", "silybum marianum", "siliphos"],
        "drug_class": "Dietary Supplement / Hepatoprotective Antioxidant",
        "categories": ["Dietary Supplement", "Antioxidant", "Hepatoprotective", "Herbal Extract"],
        "molecular_weight": 482.44,
        "logp": 1.7,
        "oral_bioavailability": 0.20,
        "volume_of_distribution": 1.2,
        "protein_binding": 75.0,
        "receptor_targets": [
            {"target": "Hepatic Parenchymal & Biliary Transport (BSEP / MRP2 / CYP)", "action": "supports", "family": "Hepatobiliary Support"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": ["CYP3A4", "CYP2C9"], "inducers": []},
    },
    "curcumin": {
        "name": "Curcumin",
        "canonical_name": "Curcumin (Turmeric Extract)",
        "synonyms": ["turmeric", "turmericextract", "curcuminoids", "theracurmin", "longvida"],
        "drug_class": "Dietary Supplement / Polyphenolic Antioxidant",
        "categories": ["Dietary Supplement", "Antioxidant", "Anti-Inflammatory", "Herbal Extract"],
        "molecular_weight": 368.38,
        "logp": 3.2,
        "oral_bioavailability": 0.05,
        "volume_of_distribution": 2.0,
        "protein_binding": 85.0,
        "receptor_targets": [
            {"target": "NF-κB & Pro-Inflammatory Cytokines (NFKB1 / PTGS2)", "action": "inhibitor", "family": "Inflammatory Signaling", "gene_symbol": "NFKB1"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
    },
    "citrus_bergamot": {
        "name": "Citrus Bergamot",
        "canonical_name": "Citrus Bergamot (Bergamonte / BPF)",
        "synonyms": ["bergamot", "bergamotextract", "bergamonte", "bpf"],
        "drug_class": "Dietary Supplement / Polyphenolic Flavonoid",
        "categories": ["Dietary Supplement", "Cardiovascular Support", "Lipid Management"],
        "molecular_weight": 580.53,
        "logp": 0.5,
        "oral_bioavailability": 0.25,
        "volume_of_distribution": 1.5,
        "protein_binding": 60.0,
        "receptor_targets": [
            {"target": "HMG-CoA Reductase (HMGCR)", "action": "inhibitor", "family": "Enzyme / Lipid"}
        ],
    },
    "alpha_lipoic_acid": {
        "name": "Alpha-Lipoic Acid",
        "canonical_name": "Alpha-Lipoic Acid (R-ALA / Thioctic Acid)",
        "synonyms": ["ala", "rala", "rlipoicacid", "thiocticacid"],
        "drug_class": "Dietary Supplement / Mitochondrial Co-Factor",
        "categories": ["Dietary Supplement", "Antioxidant", "Metabolic Support"],
        "molecular_weight": 206.33,
        "logp": 2.1,
        "oral_bioavailability": 0.30,
        "volume_of_distribution": 1.0,
        "protein_binding": 70.0,
        "receptor_targets": [
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
    },
    "taurine": {
        "name": "Taurine",
        "canonical_name": "Taurine (2-Aminoethanesulfonic Acid)",
        "synonyms": ["ltaurine"],
        "drug_class": "Dietary Supplement / Amino Sulfonic Acid",
        "categories": ["Dietary Supplement", "Osmolyte", "Cardiovascular Support"],
        "molecular_weight": 125.15,
        "logp": -1.3,
        "oral_bioavailability": 0.90,
        "volume_of_distribution": 0.8,
        "protein_binding": 0.0,
        "receptor_targets": [
            {"target": "GABA-A Receptor (GABRA1 / GABRA2)", "action": "agonist", "family": "Ion Channel / Neurotransmitter"}
        ],
    },
    "melatonin": {
        "name": "Melatonin",
        "canonical_name": "Melatonin",
        "synonyms": ["circadin"],
        "drug_class": "Dietary Supplement / Pineal Neurohormone",
        "categories": ["Dietary Supplement", "Sleep Support", "Antioxidant"],
        "molecular_weight": 232.28,
        "logp": 1.6,
        "oral_bioavailability": 0.15,
        "volume_of_distribution": 1.5,
        "protein_binding": 60.0,
        "receptor_targets": [
            {"target": "Melatonin Receptor (MTNR1A / MT1 / MT2)", "action": "agonist", "family": "GPCR / Circadian"}
        ],
    },
    "nac": {
        "name": "N-Acetyl Cysteine",
        "canonical_name": "N-Acetyl Cysteine (NAC)",
        "synonyms": ["nacetylcysteine", "acetylcysteine"],
        "drug_class": "Dietary Supplement / Glutathione Precursor",
        "categories": ["Dietary Supplement", "Antioxidant", "Glutathione Support"],
        "molecular_weight": 163.19,
        "logp": -0.6,
        "oral_bioavailability": 0.10,
        "volume_of_distribution": 0.6,
        "protein_binding": 50.0,
        "receptor_targets": [
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
    },
    "tudca": {
        "name": "Tauroursodeoxycholic Acid",
        "canonical_name": "Tauroursodeoxycholic Acid (TUDCA)",
        "synonyms": ["tauroursodeoxycholicacid", "tauroursodeoxycholate"],
        "drug_class": "Dietary Supplement / Hydrophilic Bile Acid",
        "categories": ["Dietary Supplement", "Hepatoprotective", "ER Stress Reducer"],
        "molecular_weight": 499.70,
        "logp": 1.2,
        "oral_bioavailability": 0.40,
        "volume_of_distribution": 0.8,
        "protein_binding": 70.0,
        "receptor_targets": [
            {"target": "Hepatic Parenchymal & Biliary Transport (BSEP / MRP2 / CYP)", "action": "supports", "family": "Hepatobiliary Support"}
        ],
    },
    "l_carnitine": {
        "name": "L-Carnitine",
        "canonical_name": "L-Carnitine (ALCAR)",
        "synonyms": ["alcar", "acetyllcarnitine", "carnitine", "lcarnitine", "lcarnitinetartrate"],
        "drug_class": "Dietary Supplement / Fatty Acid Shuttle",
        "categories": ["Dietary Supplement", "Mitochondrial Support"],
        "molecular_weight": 161.20,
        "logp": -3.1,
        "oral_bioavailability": 0.15,
        "volume_of_distribution": 0.7,
        "protein_binding": 0.0,
        "receptor_targets": [
            {"target": "Carnitine Palmitoyltransferase (CPT1A / CPT2)", "action": "agonist", "family": "Enzyme / Fatty Acid Oxidation"},
            {"target": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)", "action": "substrate", "family": "Gut Microbiota / Microbial Lyase", "is_microbial": True}
        ],
    },
    "allicin": {
        "name": "Allicin",
        "canonical_name": "Allicin (Garlic Extract / Allium sativum)",
        "synonyms": ["allicin", "garlic", "garlicextract", "alliumsativum", "agedgarlicextract", "diallylthiosulfinate"],
        "drug_class": "Dietary Supplement / Organosulfur Botanical / Microbial Lyase Inhibitor",
        "categories": ["Dietary Supplement", "Antioxidant", "Cardiovascular Support", "Gut Microbiome Modulator"],
        "molecular_weight": 162.27,
        "logp": 1.35,
        "oral_bioavailability": 0.80,
        "volume_of_distribution": 0.8,
        "protein_binding": 45.0,
        "receptor_targets": [
            {"target": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)", "action": "inhibitor", "family": "Gut Microbiota / Microbial Lyase", "inhibition_ic50": 0.05, "is_microbial": True},
            {"target": "HMG-CoA Reductase (HMGCR)", "action": "inhibitor", "family": "Enzyme / Lipid", "inhibition_ic50": 1.2},
            {"target": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)", "action": "agonist", "family": "Vascular Endothelium"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
        "cyp_enzymes": {"substrates": [], "inhibitors": ["CYP2E1"], "inducers": []},
    },
    "l_theanine": {
        "name": "L-Theanine",
        "canonical_name": "L-Theanine",
        "synonyms": ["theanine", "suntheanine"],
        "drug_class": "Dietary Supplement / Amino Acid",
        "categories": ["Dietary Supplement", "Nootropic", "Anxiolytic"],
        "molecular_weight": 174.20,
        "logp": -1.8,
        "oral_bioavailability": 0.95,
        "volume_of_distribution": 0.8,
        "protein_binding": 0.0,
        "receptor_targets": [
            {"target": "GABA-A Receptor (GABRA1 / GABRA2)", "action": "agonist", "family": "Ion Channel / Neurotransmitter"},
            {"target": "Glutamate Receptor (GRIN1 / NMDA)", "action": "antagonist", "family": "Ion Channel / Glutamate"}
        ],
    },
    "berberine": {
        "name": "Berberine",
        "canonical_name": "Berberine",
        "synonyms": ["berberinehcl"],
        "drug_class": "Dietary Supplement / Isoquinoline Alkaloid",
        "categories": ["Dietary Supplement", "Metabolic Support", "AMPK Activator"],
        "molecular_weight": 336.36,
        "logp": -1.5,
        "oral_bioavailability": 0.05,
        "volume_of_distribution": 2.5,
        "protein_binding": 50.0,
        "receptor_targets": [
            {"target": "AMP-Activated Protein Kinase (AMPK)", "action": "agonist", "family": "Enzyme / Energy Sensor"},
            {"target": "PCSK9", "action": "inhibitor", "family": "Enzyme / Lipid"}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": ["CYP3A4", "CYP2D6"], "inducers": []},
    },
    "omega_3": {
        "name": "Omega-3 Fatty Acids",
        "canonical_name": "Omega-3 Fatty Acids (EPA / DHA)",
        "synonyms": ["fishoil", "krilloil", "epadha", "epa", "dha"],
        "drug_class": "Dietary Supplement / Polyunsaturated Fatty Acid",
        "categories": ["Dietary Supplement", "Cardiovascular Support", "Anti-Inflammatory"],
        "molecular_weight": 302.45,
        "logp": 4.5,
        "oral_bioavailability": 0.80,
        "volume_of_distribution": 1.5,
        "protein_binding": 95.0,
        "receptor_targets": [
            {"target": "NF-κB & Pro-Inflammatory Cytokines (NFKB1 / PTGS2)", "action": "inhibitor", "family": "Inflammatory Signaling", "gene_symbol": "NFKB1"},
            {"target": "PPAR-alpha (PPARA)", "action": "agonist", "family": "Nuclear Receptor"}
        ],
    },
    "nac": {
        "name": "N-Acetylcysteine (NAC)",
        "canonical_name": "N-Acetylcysteine",
        "synonyms": ["nac", "nacetylcysteine", "acetylcysteine", "mucomyst"],
        "drug_class": "Antioxidant / Mucolytic / Glutathione Precursor",
        "categories": ["Dietary Supplement", "Antioxidant", "Hepatic Support", "Cytoprotective"],
        "molecular_weight": 163.19,
        "logp": -0.6,
        "oral_bioavailability": 0.10,
        "volume_of_distribution": 0.47,
        "protein_binding": 83.0,
        "mechanism": "Provides bioavailable L-cysteine substrate for rate-limiting glutathione (GSH) synthesis, scavenges reactive oxygen species (ROS), and activates Nrf2 cytoprotective pathway.",
        "receptor_targets": [
            {"target": "Glutathione Biosynthesis (GCLC / GCLM / SLC7A11)", "action": "substrate", "family": "Redox Defense", "gene_symbol": "GCLC"},
            {"target": "Nrf2 Cytoprotective Pathway (NFE2L2)", "action": "activator", "family": "Transcription Factor", "gene_symbol": "NFE2L2"},
            {"target": "Cellular Reactive Oxygen Species (ROS)", "action": "scavenger", "family": "Redox Defense"}
        ],
    },
    "astaxanthin": {
        "name": "Astaxanthin",
        "canonical_name": "Astaxanthin",
        "synonyms": ["astaxanthin", "asta"],
        "drug_class": "Dietary Supplement / Carotenoid Antioxidant",
        "categories": ["Dietary Supplement", "Antioxidant", "Endothelial Protection", "Mitochondrial Support"],
        "molecular_weight": 596.84,
        "logp": 8.0,
        "oral_bioavailability": 0.40,
        "volume_of_distribution": 2.0,
        "protein_binding": 95.0,
        "mechanism": "Transmembrane lipophilic antioxidant that quenches singlet oxygen and lipid peroxides across cellular membranes, protecting mitochondrial double membranes.",
        "receptor_targets": [
            {"target": "Cellular Redox Homeostasis & Lipid Peroxidation (MDA / ROS)", "action": "scavenger", "family": "Redox Defense"},
            {"target": "Nrf2 Cytoprotective Pathway (NFE2L2)", "action": "activator", "family": "Transcription Factor", "gene_symbol": "NFE2L2"}
        ],
    },
    "coq10": {
        "name": "Coenzyme Q10 (Ubiquinol)",
        "canonical_name": "Coenzyme Q10",
        "synonyms": ["coq10", "ubiquinol", "ubiquinone", "coenzymeq10"],
        "drug_class": "Dietary Supplement / Bioenergetic Antioxidant",
        "categories": ["Dietary Supplement", "Antioxidant", "Mitochondrial Bioenergetics", "Cardiovascular Support"],
        "molecular_weight": 863.34,
        "logp": 10.5,
        "oral_bioavailability": 0.06,
        "volume_of_distribution": 1.5,
        "protein_binding": 99.0,
        "mechanism": "Essential mitochondrial electron transport chain electron carrier and lipid-soluble antioxidant, protecting LDL particles and cellular membranes from oxidative damage.",
        "receptor_targets": [
            {"target": "Mitochondrial Electron Transport Complex I & III", "action": "cofactor", "family": "Mitochondrial Bioenergetics"},
            {"target": "Cellular Redox Homeostasis & Lipid Peroxidation (MDA / ROS)", "action": "antioxidant", "family": "Redox Defense"}
        ],
    },
    "curcumin": {
        "name": "Curcumin",
        "canonical_name": "Curcumin",
        "synonyms": ["curcumin", "turmeric", "turmericextract"],
        "drug_class": "Dietary Supplement / Polyphenolic Antioxidant",
        "categories": ["Dietary Supplement", "Antioxidant", "Anti-Inflammatory"],
        "molecular_weight": 368.38,
        "logp": 3.2,
        "oral_bioavailability": 0.01,
        "volume_of_distribution": 2.1,
        "protein_binding": 90.0,
        "receptor_targets": [
            {"target": "Nrf2 Cytoprotective Pathway (NFE2L2)", "action": "activator", "family": "Transcription Factor", "gene_symbol": "NFE2L2"},
            {"target": "NF-κB & Pro-Inflammatory Cytokines (NFKB1 / PTGS2)", "action": "inhibitor", "family": "Inflammatory Signaling", "gene_symbol": "NFKB1"}
        ],
    },
    "creatine": {
        "name": "Creatine",
        "canonical_name": "Creatine",
        "synonyms": ["creatine", "creatinemonohydrate"],
        "drug_class": "Dietary Supplement / Ergogenic Aid",
        "categories": ["Dietary Supplement", "Ergogenic Aid", "Muscle Support"],
        "molecular_weight": 131.13,
        "logp": -0.9,
        "oral_bioavailability": 0.99,
        "volume_of_distribution": 0.8,
        "protein_binding": 0.0,
        "dosing": {
            "unit": "mg/day",
            "basis": "bodyweight",
            "mg_per_kg": {"threshold": 10, "common": 20, "heavy": 30},
        },
        "reason": "Expands intramuscular phosphocreatine reserves to accelerate ATP resynthesis during high-intensity resistance training.",
        "receptor_targets": [
            {"target": "Skeletal Muscle ATP-PCr Phosphagen System (CKM / SLC6A8)", "action": "agonist", "family": "Phosphagen System"}
        ],
    },
    "caffeine": {
        "name": "Caffeine",
        "canonical_name": "Caffeine",
        "synonyms": ["caffeine", "caffeineanhydrous", "guarana"],
        "drug_class": "Dietary Supplement / CNS Psychostimulant",
        "categories": ["Dietary Supplement", "CNS Stimulant", "Adenosine Antagonist"],
        "molecular_weight": 194.19,
        "logp": -0.07,
        "oral_bioavailability": 0.99,
        "volume_of_distribution": 0.6,
        "protein_binding": 36.0,
        "dosing": {
            "unit": "mg/day",
            "basis": "bodyweight",
            "mg_per_kg": {"threshold": 1, "common": 3, "heavy": 6},
        },
        "reason": "Antagonizes central adenosine A1 and A2A receptors to suppress fatigue and enhance alertness.",
        "receptor_targets": [
            {"target": "A1 receptor", "action": "antagonist", "family": "GPCR / Adenosine"},
            {"target": "Adenosine Receptor (ADORA1 / ADORA2A)", "action": "antagonist", "family": "GPCR / Adenosine"}
        ],
        "cyp_enzymes": {"substrates": ["CYP1A2"], "inhibitors": ["CYP1A2"], "inducers": []},
    },
    "semaglutide": {
        "name": "Semaglutide",
        "canonical_name": "Semaglutide",
        "synonyms": ["semaglutide", "ozempic", "wegovy", "rybelsus"],
        "drug_class": "GLP-1 Receptor Agonist",
        "categories": ["Approved Drug", "GLP-1 Receptor Agonist", "Antidiabetic", "Anti-Obesity"],
        "molecular_weight": 4113.58,
        "logp": -1.2,
        "oral_bioavailability": 0.89,
        "volume_of_distribution": 12.5,
        "protein_binding": 99.0,
        "metadata": {
            "evidence_tier": "FDA_APPROVED_CLINICAL_DATA",
            "regulatory_status": "APPROVED_RX",
            "human_clinical_trials": True,
        },
        "receptor_targets": [
            {"target": "Glucagon-Like Peptide 1 Receptor (GLP1R)", "action": "agonist", "family": "GPCR Class B", "affinity_ki": 0.0005}
        ],
    },
    "retatrutide": {
        "name": "Retatrutide",
        "canonical_name": "Retatrutide",
        "synonyms": ["retatrutide", "ly3437943"],
        "drug_class": "Triple Incretin GIP / GLP-1 / Glucagon Receptor Agonist",
        "categories": ["Investigational Peptide", "GIP/GLP-1/Glucagon Tri-Agonist"],
        "molecular_weight": 4731.33,
        "logp": -1.5,
        "oral_bioavailability": 0.80,
        "volume_of_distribution": 10.5,
        "protein_binding": 99.0,
        "metadata": {
            "evidence_tier": "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION",
            "regulatory_status": "RESEARCH_CHEMICAL",
            "human_clinical_trials": True,
        },
        "receptor_targets": [
            {"target": "Gastric Inhibitory Polypeptide Receptor (GIPR)", "action": "agonist", "family": "GPCR Class B", "affinity_ki": 0.05},
            {"target": "Glucagon-Like Peptide 1 Receptor (GLP1R)", "action": "agonist", "family": "GPCR Class B", "affinity_ki": 0.77},
            {"target": "Glucagon Receptor (GCGR)", "action": "agonist", "family": "GPCR Class B", "affinity_ki": 0.58},
        ],
    },
    "nebivolol": {
        "name": "Nebivolol",
        "canonical_name": "Nebivolol (Bystolic)",
        "synonyms": ["bystolic", "nebilet", "nebivololum", "nebivololhcl"],
        "drug_class": "Third-Generation Beta-1 Selective Blocker (eNOS Vasodilating)",
        "categories": ["Cardiovascular Agent", "Beta Blocker", "Antihypertensive", "Vasodilator"],
        "molecular_weight": 405.44,
        "logp": 4.1,
        "oral_bioavailability": 0.12,
        "half_life": "10-12 hours (Extensive Metabolizers) / 19-30 hours (Poor Metabolizers)",
        "t_half_numeric": 12.0,
        "volume_of_distribution": 10.5,
        "protein_binding": 98.0,
        "mechanism": "Highly selective competitive beta-1 adrenergic receptor antagonist combined with d-enantiomer mediated endothelial nitric oxide synthase (eNOS / NOS3) activation and beta-3 adrenergic agonism, producing systemic peripheral vasodilation with minimal bronchoconstrictive or inotropic depression.",
        "receptor_targets": [
            {"target": "Beta-1 Adrenergic Receptor (ADRB1)", "action": "antagonist", "family": "GPCR / Adrenergic", "affinity_ki": 0.9, "gene_symbol": "ADRB1"},
            {"target": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)", "action": "activator", "family": "Endothelial Vasodilation", "gene_symbol": "NOS3"},
            {"target": "Beta-3 Adrenergic Receptor (ADRB3)", "action": "agonist", "family": "GPCR / Adrenergic", "affinity_ki": 25.0, "gene_symbol": "ADRB3"}
        ],
        "cyp_enzymes": {"substrates": ["CYP2D6", "CYP3A4"], "inhibitors": ["CYP2D6"], "inducers": []},
    },
    "quercetin": {
        "name": "Quercetin",
        "canonical_name": "Quercetin",
        "synonyms": ["quercetine", "quercetindihydrate", "isoquercetin", "bioflavonoid"],
        "drug_class": "Dietary Supplement / Polyphenolic Flavonoid",
        "categories": ["Dietary Supplement", "Antioxidant", "Anti-Inflammatory", "Flavonoid"],
        "molecular_weight": 302.24,
        "logp": 1.8,
        "oral_bioavailability": 0.05,
        "volume_of_distribution": 2.0,
        "protein_binding": 98.0,
        "receptor_targets": [
            {"target": "Catechol-O-Methyltransferase (COMT)", "action": "inhibitor", "family": "Enzyme / Catecholamine Metabolism", "gene_symbol": "COMT"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
    },
    "resveratrol": {
        "name": "Resveratrol",
        "canonical_name": "Resveratrol",
        "synonyms": ["transresveratrol", "stilbenoid"],
        "drug_class": "Dietary Supplement / Polyphenolic Stilbenoid",
        "categories": ["Dietary Supplement", "Antioxidant", "Sirtuin Activator"],
        "molecular_weight": 228.25,
        "logp": 3.1,
        "oral_bioavailability": 0.01,
        "volume_of_distribution": 1.8,
        "protein_binding": 95.0,
        "receptor_targets": [
            {"target": "Sirtuin 1 (SIRT1)", "action": "agonist", "family": "Deacetylase / Longevity"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
    },
    "rhodiola": {
        "name": "Rhodiola Rosea",
        "canonical_name": "Rhodiola Rosea",
        "synonyms": ["rhodiolarosea", "salidroside", "rosavin", "goldenroot"],
        "drug_class": "Dietary Supplement / Botanical Adaptogen",
        "categories": ["Dietary Supplement", "Adaptogen", "Nootropic", "Herbal Extract"],
        "molecular_weight": 300.30,
        "logp": 0.8,
        "oral_bioavailability": 0.30,
        "volume_of_distribution": 1.5,
        "protein_binding": 50.0,
        "receptor_targets": [
            {"target": "Monoamine Oxidase Subtype A & B (MAOA / MAOB)", "action": "inhibitor", "family": "Enzyme / Neurotransmitter", "gene_symbol": "MAOA"}
        ],
    },
    "bacopa": {
        "name": "Bacopa Monnieri",
        "canonical_name": "Bacopa Monnieri",
        "synonyms": ["bacopamonnieri", "brahmi", "bacosides"],
        "drug_class": "Dietary Supplement / Botanical Nootropic",
        "categories": ["Dietary Supplement", "Nootropic", "Adaptogen", "Herbal Extract"],
        "molecular_weight": 768.80,
        "logp": 1.2,
        "oral_bioavailability": 0.25,
        "volume_of_distribution": 1.2,
        "protein_binding": 60.0,
        "receptor_targets": [
            {"target": "Tryptophan Hydroxylase & Serotonin Biosynthesis (TPH2)", "action": "activator", "family": "Neurotransmitter Biosynthesis", "gene_symbol": "TPH2"}
        ],
    },
    "ginkgo_biloba": {
        "name": "Ginkgo Biloba",
        "canonical_name": "Ginkgo Biloba",
        "synonyms": ["ginkgo", "ginkgoextract", "egb761", "ginkgolides"],
        "drug_class": "Dietary Supplement / Botanical Vasodilator",
        "categories": ["Dietary Supplement", "Nootropic", "Vasodilator", "Herbal Extract"],
        "molecular_weight": 408.40,
        "logp": 1.5,
        "oral_bioavailability": 0.80,
        "volume_of_distribution": 1.4,
        "protein_binding": 50.0,
        "receptor_targets": [
            {"target": "Platelet-Activating Factor Receptor (PTAFR)", "action": "antagonist", "family": "GPCR / Hemostasis"},
            {"target": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)", "action": "activator", "family": "Endothelial Vasodilation"}
        ],
    },
    "panax_ginseng": {
        "name": "Panax Ginseng",
        "canonical_name": "Panax Ginseng",
        "synonyms": ["ginseng", "redginseng", "koreanginseng", "ginsenosides"],
        "drug_class": "Dietary Supplement / Botanical Adaptogen",
        "categories": ["Dietary Supplement", "Adaptogen", "Herbal Extract"],
        "molecular_weight": 800.00,
        "logp": 1.1,
        "oral_bioavailability": 0.10,
        "volume_of_distribution": 1.8,
        "protein_binding": 70.0,
        "receptor_targets": [
            {"target": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)", "action": "activator", "family": "Endothelial Vasodilation", "gene_symbol": "NOS3"}
        ],
    },
    "piperine": {
        "name": "Piperine",
        "canonical_name": "Piperine (Black Pepper Extract)",
        "synonyms": ["bioperine", "blackpepperextract", "pipernigrum"],
        "drug_class": "Dietary Supplement / Bioenhancer Alkaloid",
        "categories": ["Dietary Supplement", "Bioenhancer", "Alkaloid"],
        "molecular_weight": 285.34,
        "logp": 3.7,
        "oral_bioavailability": 0.90,
        "volume_of_distribution": 1.0,
        "protein_binding": 95.0,
        "receptor_targets": [
            {"target": "Transient Receptor Potential Vanilloid 1 (TRPV1)", "action": "agonist", "family": "Ion Channel", "gene_symbol": "TRPV1"},
            {"target": "P-glycoprotein / ABCB1 Efflux Transporter (ABCB1)", "action": "inhibitor", "family": "ABC Transporter", "gene_symbol": "ABCB1"},
            {"target": "UDP-Glucuronosyltransferase 1A1 (UGT1A1)", "action": "inhibitor", "family": "Phase II Conjugation", "gene_symbol": "UGT1A1"}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": ["CYP3A4", "CYP2C9"], "inducers": []},
        "transporters": {"substrates": ["P-gp"], "inhibitors": ["P-gp"], "inducers": []},
        "phase2_enzymes": {"substrates": [], "inhibitors": ["UGT1A1"], "inducers": []},
    },
    "sulforaphane": {
        "name": "Sulforaphane",
        "canonical_name": "Sulforaphane",
        "synonyms": ["broccolisproutextract", "glucoraphanin"],
        "drug_class": "Dietary Supplement / Isothiocyanate Nrf2 Inducer",
        "categories": ["Dietary Supplement", "Antioxidant", "Detoxification"],
        "molecular_weight": 177.29,
        "logp": 0.2,
        "oral_bioavailability": 0.80,
        "volume_of_distribution": 0.9,
        "protein_binding": 40.0,
        "receptor_targets": [
            {"target": "Nrf2 / Keap1 Cytoprotective & Phase II Detoxification Pathway (NFE2L2)", "action": "activator", "family": "Transcription Factor", "gene_symbol": "NFE2L2"}
        ],
    },
    "st_johns_wort": {
        "name": "St. John's Wort",
        "canonical_name": "St. John's Wort (Hypericum perforatum)",
        "synonyms": ["stjohnswort", "stjohnwort", "hypericum", "hypericumperforatum", "hyperforin", "hypericin"],
        "drug_class": "Dietary Supplement / Botanical PXR Inducer",
        "categories": ["Dietary Supplement", "Herbal Extract", "Antidepressant"],
        "molecular_weight": 536.70,
        "logp": 4.2,
        "oral_bioavailability": 0.20,
        "volume_of_distribution": 1.5,
        "protein_binding": 90.0,
        "receptor_targets": [
            {"target": "Pregnane X Receptor (PXR / NR1I2 / CYP3A4 Inducer)", "action": "inducer", "family": "Nuclear Receptor", "gene_symbol": "NR1I2"},
            {"target": "Sodium-Dependent Serotonin Transporter (SERT / SLC6A4)", "action": "inhibitor", "family": "Monoamine Transporter", "gene_symbol": "SLC6A4"}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4", "CYP2C9"], "inhibitors": [], "inducers": ["CYP3A4", "CYP2C9", "CYP2C19"]},
        "transporters": {"substrates": ["P-gp"], "inhibitors": [], "inducers": ["P-gp"]},
    },
    "saw_palmetto": {
        "name": "Saw Palmetto",
        "canonical_name": "Saw Palmetto (Serenoa repens)",
        "synonyms": ["sawpalmetto", "serenoarepens", "permixon"],
        "drug_class": "Dietary Supplement / Botanical 5-AR Inhibitor",
        "categories": ["Dietary Supplement", "Herbal Extract", "Prostate Support"],
        "molecular_weight": 280.00,
        "logp": 4.5,
        "oral_bioavailability": 0.40,
        "volume_of_distribution": 1.0,
        "protein_binding": 90.0,
        "receptor_targets": [
            {"target": "5-Alpha Reductase Subtype 1 & 2 (SRD5A1 / SRD5A2)", "action": "inhibitor", "family": "Steroid Biosynthesis", "gene_symbol": "SRD5A2"},
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "antagonist", "family": "Nuclear Receptor", "gene_symbol": "AR"}
        ],
    },
    "green_tea_extract": {
        "name": "Green Tea Extract (EGCG)",
        "canonical_name": "Green Tea Extract (Epigallocatechin Gallate)",
        "synonyms": ["greenteaextract", "greentea", "egcg", "epigallocatechingallate"],
        "drug_class": "Dietary Supplement / Botanical Polyphenol",
        "categories": ["Dietary Supplement", "Antioxidant", "Herbal Extract"],
        "molecular_weight": 458.37,
        "logp": 1.1,
        "oral_bioavailability": 0.05,
        "volume_of_distribution": 1.2,
        "protein_binding": 80.0,
        "receptor_targets": [
            {"target": "Catechol-O-Methyltransferase (COMT)", "action": "inhibitor", "family": "Enzyme / Catecholamine Metabolism", "gene_symbol": "COMT"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
    },
    "magnesium": {
        "name": "Magnesium Glycinate",
        "canonical_name": "Magnesium Glycinate",
        "synonyms": ["magnesiumglycinate", "magnesiumbisglycinate", "magnesiumcitrate", "magnesiumlthreonate", "magglycinate"],
        "drug_class": "Dietary Supplement / Essential Mineral",
        "categories": ["Dietary Supplement", "Essential Mineral", "Relaxant"],
        "molecular_weight": 172.46,
        "logp": -1.0,
        "oral_bioavailability": 0.40,
        "volume_of_distribution": 1.0,
        "protein_binding": 30.0,
        "receptor_targets": [
            {"target": "Multivalent Cation Gastrointestinal Chelation Site", "action": "chelator", "family": "Physicochemical Interaction"},
            {"target": "NMDA Receptor Ion Channel Voltage-Dependent Blockade (GRIN1 / GRIN2B)", "action": "antagonist", "family": "Ion Channel", "gene_symbol": "GRIN1"}
        ],
    },
    "zinc": {
        "name": "Zinc Picolinate",
        "canonical_name": "Zinc Picolinate",
        "synonyms": ["zincpicolinate", "zinccitrate", "zincgluconate", "optizinc"],
        "drug_class": "Dietary Supplement / Essential Mineral",
        "categories": ["Dietary Supplement", "Essential Mineral", "Immune Support"],
        "molecular_weight": 309.52,
        "logp": -0.5,
        "oral_bioavailability": 0.50,
        "volume_of_distribution": 1.0,
        "protein_binding": 90.0,
        "receptor_targets": [
            {"target": "Multivalent Cation Gastrointestinal Chelation Site", "action": "chelator", "family": "Physicochemical Interaction"}
        ],
    },
    "tart_cherry": {
        "name": "Tart Cherry Extract",
        "canonical_name": "Tart Cherry Extract (Montmorency)",
        "synonyms": ["tartcherry", "tartcherryextract", "montmorencycherry", "prunuscerasus"],
        "drug_class": "Dietary Supplement / Botanical Flavonoid",
        "categories": ["Dietary Supplement", "Antioxidant", "Herbal Extract"],
        "molecular_weight": 448.38,
        "logp": 0.8,
        "oral_bioavailability": 0.20,
        "volume_of_distribution": 1.2,
        "protein_binding": 70.0,
        "receptor_targets": [
            {"target": "Xanthine Dehydrogenase / Oxidase (XDH / XO)", "action": "inhibitor", "family": "Purine Metabolism", "gene_symbol": "XDH"},
            {"target": "NF-κB & Pro-Inflammatory Cytokines (NFKB1 / PTGS2)", "action": "inhibitor", "family": "Inflammatory Signaling"}
        ],
    },
    "alpha_gpc": {
        "name": "Alpha-GPC",
        "canonical_name": "Alpha-GPC (L-Alpha Glycerylphosphorylcholine / Choline Alfoscerate)",
        "synonyms": ["alphagpc", "alpha_gpc", "cholinealfoscerate", "lalphagpc", "gpc", "alfoscerate"],
        "drug_class": "Dietary Supplement / Cholinergic Nootropic",
        "categories": ["Dietary Supplement", "Nootropic", "Cognitive Support", "Cholinergic"],
        "molecular_weight": 257.22,
        "logp": -2.8,
        "oral_bioavailability": 0.85,
        "volume_of_distribution": 0.9,
        "protein_binding": 10.0,
        "mechanism": "Rapidly crosses the blood-brain barrier to deliver bioavailable free choline, accelerating central acetylcholine (ACh) neurotransmitter synthesis and supporting membrane phosphatidylcholine reserves.",
        "receptor_targets": [
            {"target": "Muscarinic Acetylcholine Receptor (CHRM1 / CHRM2)", "action": "agonist", "family": "GPCR / Cholinergic", "gene_symbol": "CHRM1"},
            {"target": "Neuronal Nicotinic Acetylcholine Receptor (CHRNA7 / CHRNB2)", "action": "agonist", "family": "Ion Channel / Cholinergic", "gene_symbol": "CHRNA7"}
        ],
    },
    "huperzine_a": {
        "name": "Huperzine A",
        "canonical_name": "Huperzine A (Huperzia serrata Extract)",
        "synonyms": ["huperzinea", "huperzine", "selagine", "huperziaserrata"],
        "drug_class": "Dietary Supplement / Acetylcholinesterase Inhibitor",
        "categories": ["Dietary Supplement", "Nootropic", "AChE Inhibitor", "Neuroprotective"],
        "molecular_weight": 242.32,
        "logp": 1.4,
        "oral_bioavailability": 0.95,
        "half_life": "10-14 hours",
        "t_half_numeric": 12.0,
        "volume_of_distribution": 2.5,
        "protein_binding": 40.0,
        "mechanism": "Potent, highly selective, reversible, and centrally active inhibitor of acetylcholinesterase (AChE), preventing acetylcholine hydrolysis and enhancing synaptic cholinergic neurotransmission.",
        "receptor_targets": [
            {"target": "Acetylcholinesterase (ACHE)", "action": "inhibitor", "family": "Enzyme / Cholinergic", "gene_symbol": "ACHE"},
            {"target": "Glutamate Receptor (GRIN1 / NMDA)", "action": "antagonist", "family": "Ion Channel / Glutamate", "gene_symbol": "GRIN1"}
        ],
    },
    "ashwagandha": {
        "name": "Ashwagandha",
        "canonical_name": "Ashwagandha (Withania somnifera / KSM-66 / Sensoril)",
        "synonyms": ["ashwagandha", "ksm66", "sensoril", "withaniasomnifera", "withanolides"],
        "drug_class": "Dietary Supplement / Botanical Adaptogen",
        "categories": ["Dietary Supplement", "Adaptogen", "Anxiolytic", "Endocrine Support"],
        "molecular_weight": 470.60,
        "logp": 2.3,
        "oral_bioavailability": 0.35,
        "volume_of_distribution": 1.8,
        "protein_binding": 65.0,
        "mechanism": "Withanolide glycosides modulate hypothalamic-pituitary-adrenal (HPA) axis feedback, reducing serum cortisol and activating central GABA-A receptor signaling.",
        "receptor_targets": [
            {"target": "GABA-A Receptor (GABRA1 / GABRA2)", "action": "agonist", "family": "Ion Channel / Neurotransmitter", "gene_symbol": "GABRA1"},
            {"target": "Glucocorticoid Receptor (GR / NR3C1 / Cortisol Regulation)", "action": "modulator", "family": "Nuclear Receptor", "gene_symbol": "NR3C1"}
        ],
    },
    "l_tyrosine": {
        "name": "L-Tyrosine",
        "canonical_name": "L-Tyrosine",
        "synonyms": ["ltyrosine", "tyrosine", "nalt", "nacetyltyrosine"],
        "drug_class": "Dietary Supplement / Catecholamine Amino Acid Precursor",
        "categories": ["Dietary Supplement", "Nootropic", "Neurotransmitter Precursor", "Focus"],
        "molecular_weight": 181.19,
        "logp": -2.3,
        "oral_bioavailability": 0.90,
        "volume_of_distribution": 0.8,
        "protein_binding": 15.0,
        "mechanism": "Rate-limiting substrate precursor for tyrosine hydroxylase (TH), driving dopamine, norepinephrine, and epinephrine synthesis under acute environmental and cognitive stress.",
        "receptor_targets": [
            {"target": "Tyrosine Hydroxylase & Catecholamine Synthesis (TH / SLC6A3)", "action": "substrate", "family": "Neurotransmitter Biosynthesis", "gene_symbol": "TH"}
        ],
    },
    "nmn": {
        "name": "Nicotinamide Mononucleotide (NMN)",
        "canonical_name": "Nicotinamide Mononucleotide",
        "synonyms": ["nmn", "nicotinamidemononucleotide", "beta_nmn"],
        "drug_class": "Dietary Supplement / NAD+ Precursor",
        "categories": ["Dietary Supplement", "Longevity", "NAD+ Booster", "Mitochondrial Support"],
        "molecular_weight": 334.22,
        "logp": -3.5,
        "oral_bioavailability": 0.65,
        "volume_of_distribution": 1.1,
        "protein_binding": 5.0,
        "mechanism": "Direct intracellular precursor to Nicotinamide Adenine Dinucleotide (NAD+), activating sirtuin deacylases (SIRT1, SIRT3) and promoting mitochondrial oxidative phosphorylation.",
        "receptor_targets": [
            {"target": "Sirtuin 1 (SIRT1)", "action": "activator", "family": "Deacetylase / Longevity", "gene_symbol": "SIRT1"},
            {"target": "Sirtuin 3 (SIRT3 / Mitochondrial)", "action": "activator", "family": "Deacetylase / Mitochondrial", "gene_symbol": "SIRT3"}
        ],
    },
    "apigenin": {
        "name": "Apigenin",
        "canonical_name": "Apigenin (Chamomile Extract)",
        "synonyms": ["apigenin", "chamomileextract", "flavone"],
        "drug_class": "Dietary Supplement / Flavonoid CD38 Inhibitor",
        "categories": ["Dietary Supplement", "Antioxidant", "Sleep Support", "Longevity"],
        "molecular_weight": 270.24,
        "logp": 2.6,
        "oral_bioavailability": 0.30,
        "volume_of_distribution": 1.5,
        "protein_binding": 90.0,
        "mechanism": "Positive allosteric modulator of central GABA-A benzodiazepine receptors that reduces sleep latency, alongside potent inhibition of the NADase CD38 enzyme to preserve cellular NAD+ pools.",
        "receptor_targets": [
            {"target": "GABA-A Receptor (GABRA1 / GABRA2)", "action": "agonist", "family": "Ion Channel / Neurotransmitter", "gene_symbol": "GABRA1"},
            {"target": "CD38 NAD+ Hydrolase (CD38)", "action": "inhibitor", "family": "Enzyme / NAD Metabolism", "gene_symbol": "CD38"}
        ],
    },
    "lions_mane": {
        "name": "Lion's Mane Mushroom",
        "canonical_name": "Lion's Mane (Hericium erinaceus)",
        "synonyms": ["lionsmane", "lion_s_mane", "hericiumerinaceus", "erinacines", "hericenones"],
        "drug_class": "Dietary Supplement / Botanical Neurotrophic",
        "categories": ["Dietary Supplement", "Nootropic", "Neuroprotective", "Mushroom Extract"],
        "molecular_weight": 450.00,
        "logp": 1.8,
        "oral_bioavailability": 0.40,
        "volume_of_distribution": 1.4,
        "protein_binding": 50.0,
        "mechanism": "Erinacines (mycelium) and hericenones (fruiting body) cross the blood-brain barrier to stimulate Nerve Growth Factor (NGF) and Brain-Derived Neurotrophic Factor (BDNF) synthesis.",
        "receptor_targets": [
            {"target": "Nerve Growth Factor & TrkA Signaling (NGF / NTRK1)", "action": "inducer", "family": "Neurotrophic Factor", "gene_symbol": "NGF"},
            {"target": "Brain-Derived Neurotrophic Factor (BDNF / NTRK2)", "action": "inducer", "family": "Neurotrophic Factor", "gene_symbol": "BDNF"}
        ],
    },
    "magnesium_l_threonate": {
        "name": "Magnesium L-Threonate",
        "canonical_name": "Magnesium L-Threonate (Magtein)",
        "synonyms": ["magnesiumlthreonate", "magtein", "mg_threonate"],
        "drug_class": "Dietary Supplement / BBB-Penetrating Magnesium Chelate",
        "categories": ["Dietary Supplement", "Nootropic", "Essential Mineral", "Synaptic Plasticity"],
        "molecular_weight": 294.50,
        "logp": -1.2,
        "oral_bioavailability": 0.70,
        "volume_of_distribution": 0.9,
        "protein_binding": 25.0,
        "mechanism": "Chelated magnesium form engineered to cross the blood-brain barrier, significantly raising cerebrospinal fluid magnesium concentrations and enhancing synaptic density and NMDA plasticity.",
        "receptor_targets": [
            {"target": "NMDA Receptor Ion Channel Voltage-Dependent Blockade (GRIN1 / GRIN2B)", "action": "antagonist", "family": "Ion Channel", "gene_symbol": "GRIN1"},
            {"target": "Multivalent Cation Gastrointestinal Chelation Site", "action": "chelator", "family": "Physicochemical Interaction"}
        ],
    },
    "tongkat_ali": {
        "name": "Tongkat Ali",
        "canonical_name": "Tongkat Ali (Eurycoma longifolia / Longjack)",
        "synonyms": ["tongkatali", "longjack", "eurycomalongifolia", "eurycomanone"],
        "drug_class": "Dietary Supplement / Botanical Endocrine Adaptogen",
        "categories": ["Dietary Supplement", "Endocrine Support", "Ergogenic", "Herbal Extract"],
        "molecular_weight": 408.40,
        "logp": 1.9,
        "oral_bioavailability": 0.30,
        "volume_of_distribution": 1.6,
        "protein_binding": 70.0,
        "mechanism": "Eurycomanone quassinoids release bound testosterone from sex hormone-binding globulin (SHBG) and stimulate luteinizing hormone (LH) pulsatility.",
        "receptor_targets": [
            {"target": "Sex Hormone-Binding Globulin (SHBG)", "action": "antagonist", "family": "Endocrine Binding Globulin", "gene_symbol": "SHBG"},
            {"target": "Hypothalamic-Pituitary-Gonadal Axis (HPG Axis / GnRH / LH)", "action": "agonist", "family": "Endocrine Axis"}
        ],
    },
    "noopept": {
        "name": "Noopept",
        "canonical_name": "Noopept (N-Phenylacetyl-L-prolylglycine Ethyl Ester)",
        "synonyms": ["noopept", "gvs111", "omberacetam"],
        "drug_class": "Synthetic Peptide Nootropic / AMPA Modulator",
        "categories": ["Nootropic", "Peptide", "Cognitive Support"],
        "molecular_weight": 318.37,
        "logp": 0.8,
        "oral_bioavailability": 0.99,
        "volume_of_distribution": 0.7,
        "protein_binding": 10.0,
        "mechanism": "Positively modulates central AMPA receptors and enhances hippocampal BDNF and NGF expression, improving synaptic consolidation and memory encoding.",
        "receptor_targets": [
            {"target": "AMPA Glutamate Receptor (GRIA1 / GRIA2)", "action": "agonist", "family": "Ion Channel / Glutamate", "gene_symbol": "GRIA1"},
            {"target": "Brain-Derived Neurotrophic Factor (BDNF / NTRK2)", "action": "inducer", "family": "Neurotrophic Factor", "gene_symbol": "BDNF"}
        ],
    },
    "bpc_157": {
        "name": "BPC-157",
        "canonical_name": "BPC-157 (Body Protection Compound-157 / Pentadecapeptide)",
        "synonyms": ["bpc157", "bpc_157", "bepecin", "pentadecapeptide"],
        "drug_class": "Cytoprotective Regenerative Peptide",
        "categories": ["Peptide", "Cytoprotective", "Tissue Repair", "Angiogenesis"],
        "molecular_weight": 1419.53,
        "logp": -2.1,
        "oral_bioavailability": 0.75,
        "volume_of_distribution": 0.5,
        "protein_binding": 20.0,
        "mechanism": "Accelerates tissue healing, tendon repair, and mucosal cytoprotection via upregulation of VEGF-driven angiogenesis, focal adhesion kinase (FAK), and eNOS nitric oxide generation.",
        "receptor_targets": [
            {"target": "Vascular Endothelial Growth Factor Receptor (KDR / VEGFR2)", "action": "inducer", "family": "Receptor Tyrosine Kinase", "gene_symbol": "KDR"},
            {"target": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)", "action": "activator", "family": "Endothelial Vasodilation", "gene_symbol": "NOS3"}
        ],
    },
    "tb_500": {
        "name": "TB-500",
        "canonical_name": "TB-500 (Thymosin Beta-4 Active Fragment LKKTETQ)",
        "synonyms": ["tb500", "tb_500", "thymosinbeta4", "tbeta4"],
        "drug_class": "Cytoprotective Regenerative Peptide",
        "categories": ["Peptide", "Cytoprotective", "Tissue Repair", "Actin Sequestration"],
        "molecular_weight": 4963.50,
        "logp": -2.8,
        "oral_bioavailability": 0.20,
        "volume_of_distribution": 0.6,
        "protein_binding": 30.0,
        "mechanism": "Actin-binding peptide that sequesters G-actin, promoting endothelial cell migration, microvascular angiogenesis, and suppression of inflammatory myofibroblast differentiation.",
        "receptor_targets": [
            {"target": "Actin Cytoskeleton Dynamics (ACTB / Cell Migration)", "action": "agonist", "family": "Cytoskeleton", "gene_symbol": "ACTB"}
        ],
    },
    "tirzepatide": {
        "name": "Tirzepatide",
        "canonical_name": "Tirzepatide (Mounjaro / Zepbound)",
        "synonyms": ["tirzepatide", "mounjaro", "zepbound", "ly3298176"],
        "drug_class": "Dual GIP / GLP-1 Receptor Agonist",
        "categories": ["Approved Drug", "Dual Incretin Agonist", "Antidiabetic", "Anti-Obesity"],
        "molecular_weight": 4813.45,
        "logp": -1.4,
        "oral_bioavailability": 0.80,
        "half_life": "5 days (120 hours)",
        "t_half_numeric": 120.0,
        "volume_of_distribution": 10.3,
        "protein_binding": 99.0,
        "mechanism": "Bi-functional agonist at both glucose-dependent insulinotropic polypeptide (GIP) and glucagon-like peptide-1 (GLP-1) receptors, synergistically suppressing appetite, delaying gastric emptying, and optimizing insulin secretion.",
        "receptor_targets": [
            {"target": "Gastric Inhibitory Polypeptide Receptor (GIPR)", "action": "agonist", "family": "GPCR Class B", "gene_symbol": "GIPR"},
            {"target": "Glucagon-Like Peptide 1 Receptor (GLP1R)", "action": "agonist", "family": "GPCR Class B", "gene_symbol": "GLP1R"}
        ],
    },
    "rapamycin": {
        "name": "Rapamycin",
        "canonical_name": "Rapamycin (Sirolimus)",
        "synonyms": ["sirolimus", "rapamune", "rapamycin"],
        "drug_class": "mTORC1 Inhibitor / Autophagy Inducer",
        "categories": ["Immunosuppressant", "Longevity", "mTOR Inhibitor", "Autophagy"],
        "molecular_weight": 914.17,
        "logp": 4.3,
        "oral_bioavailability": 0.15,
        "half_life": "62 hours",
        "t_half_numeric": 62.0,
        "volume_of_distribution": 12.0,
        "protein_binding": 92.0,
        "mechanism": "Binds FKBP12 to selectively inhibit the mammalian target of rapamycin complex 1 (mTORC1), triggering macroautophagy, reducing senescence-associated secretory phenotype (SASP), and extending lifespan.",
        "receptor_targets": [
            {"target": "Mechanistic Target of Rapamycin Complex 1 (mTOR / MTORC1)", "action": "inhibitor", "family": "Kinase / Longevity", "gene_symbol": "MTOR"},
            {"target": "FKBP12 Peptidyl-Prolyl Cis-Trans Isomerase (FKBP1A)", "action": "agonist", "family": "Immunophilin", "gene_symbol": "FKBP1A"}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": ["CYP3A4"], "inducers": []},
    },
}


CORE_ESTER_LIBRARY: Dict[str, Dict[str, Any]] = {
    "testosterone": {
        "name": "Testosterone",
        "canonical_name": "Testosterone Base",
        "synonyms": ["testosteronebase", "freetestosterone", "unesterifiedtestosterone"],
        "drug_class": "Androgen / Anabolic Steroid",
        "categories": ["Anabolic Steroid", "Hormone Replacement", "Androgen"],
        "molecular_weight": 288.42,
        "logp": 3.3,
        "oral_bioavailability": 0.05,
        "half_life": "10-100 minutes (unesterified IV/oral)",
        "t_half_numeric": 1.0,
        "volume_of_distribution": 1.0,
        "protein_binding": 98.0,
        "is_ester": False,
        "ester_name": None,
        "parent_compound_id": None,
        "ester_weight_factor": 1.0,
        "mechanism": "Binds to and activates nuclear androgen receptor (AR / NR3C4), inducing male secondary sexual characteristics, anabolic protein synthesis, and HPG axis feedback.",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 0.5, "gene_symbol": "AR"},
            {"target": "Estrogen Receptor Alpha (ESR1 / ER-alpha)", "action": "agonist (via aromatization)", "family": "Nuclear Receptor", "gene_symbol": "ESR1"},
            {"target": "5-Alpha Reductase Type 1 & 2 (SRD5A1 / SRD5A2)", "action": "substrate (to DHT)", "family": "Enzyme", "gene_symbol": "SRD5A2", "affinity_ki": 2500.0}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4", "CYP2C19"], "inhibitors": [], "inducers": []},
    },
    "testosterone_cypionate": {
        "name": "Testosterone Cypionate",
        "canonical_name": "Testosterone Cypionate",
        "synonyms": ["testc", "testcyp", "testosteronecypionate", "depotestosterone"],
        "drug_class": "Androgen / Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "Hormone Replacement", "Prodrug Depot"],
        "molecular_weight": 412.61,
        "logp": 6.3,
        "oral_bioavailability": 0.05,
        "half_life": "8 days (192 hours)",
        "t_half_numeric": 192.0,
        "absorption_rate_ka": 0.02,
        "volume_of_distribution": 1.0,
        "protein_binding": 98.0,
        "is_ester": True,
        "ester_name": "Cypionate",
        "parent_compound_id": "testosterone",
        "ester_weight_factor": 0.699,
        "mechanism": "Long-acting depot prodrug ester of testosterone. Hydrolyzed by endogenous esterases into free testosterone.",
    },
    "testosterone_enanthate": {
        "name": "Testosterone Enanthate",
        "canonical_name": "Testosterone Enanthate",
        "synonyms": ["teste", "testenan", "testosteroneenanthate", "delatestryl"],
        "drug_class": "Androgen / Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "Hormone Replacement", "Prodrug Depot"],
        "molecular_weight": 400.59,
        "logp": 6.0,
        "oral_bioavailability": 0.05,
        "half_life": "7 days (168 hours)",
        "t_half_numeric": 168.0,
        "absorption_rate_ka": 0.025,
        "volume_of_distribution": 1.0,
        "protein_binding": 98.0,
        "is_ester": True,
        "ester_name": "Enanthate",
        "parent_compound_id": "testosterone",
        "ester_weight_factor": 0.720,
        "mechanism": "Depot prodrug ester of testosterone. Hydrolyzed by esterases into free testosterone.",
    },
    "testosterone_propionate": {
        "name": "Testosterone Propionate",
        "canonical_name": "Testosterone Propionate",
        "synonyms": ["testp", "testprop", "testosteronepropionate", "testoviron"],
        "drug_class": "Androgen / Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "Hormone Replacement", "Short-Acting Ester"],
        "molecular_weight": 344.49,
        "logp": 4.9,
        "oral_bioavailability": 0.05,
        "half_life": "1.5 days (36 hours)",
        "t_half_numeric": 36.0,
        "absorption_rate_ka": 0.08,
        "volume_of_distribution": 1.0,
        "protein_binding": 98.0,
        "is_ester": True,
        "ester_name": "Propionate",
        "parent_compound_id": "testosterone",
        "ester_weight_factor": 0.837,
        "mechanism": "Short-acting prodrug ester of testosterone. Hydrolyzed rapidly into free testosterone.",
    },
    "testosterone_undecanoate": {
        "name": "Testosterone Undecanoate",
        "canonical_name": "Testosterone Undecanoate",
        "synonyms": ["testu", "testundec", "testosteroneundecanoate", "aveed", "nebido", "androdiol"],
        "drug_class": "Androgen / Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "Hormone Replacement", "Ultra Long-Acting Ester"],
        "molecular_weight": 456.70,
        "logp": 7.5,
        "oral_bioavailability": 0.07,
        "half_life": "21 days (504 hours)",
        "t_half_numeric": 504.0,
        "absorption_rate_ka": 0.008,
        "volume_of_distribution": 1.0,
        "protein_binding": 98.0,
        "is_ester": True,
        "ester_name": "Undecanoate",
        "parent_compound_id": "testosterone",
        "ester_weight_factor": 0.632,
        "mechanism": "Ultra long-acting prodrug ester of testosterone.",
    },
    "trenbolone": {
        "name": "Trenbolone",
        "canonical_name": "Trenbolone Base (19-Nor Trienolone)",
        "synonyms": ["trenbolonebase", "trenbase", "trienolone", "parabolanbase"],
        "drug_class": "19-Nor Anabolic-Androgenic Steroid",
        "categories": ["Anabolic Steroid", "19-Nor Derivative", "Non-Aromatizing Triene", "Research Chemical"],
        "smiles": "CC12CCC3C(=CCC4=C3CCC(=O)C4)C1CCC2O",
        "inchikey": "OKIZDXOPAGLMIA-UHFFFAOYSA-N",
        "molecular_weight": 270.37,
        "logp": 3.3,
        "oral_bioavailability": 0.03,
        "half_life": "6-12 hours (unesterified base)",
        "t_half_numeric": 8.0,
        "volume_of_distribution": 1.1,
        "volume_of_distribution_l_kg": 1.1,
        "protein_binding": 98.0,
        "protein_binding_pct": 98.0,
        "fraction_unbound": 0.02,
        "is_ester": False,
        "ester_name": None,
        "parent_compound_id": None,
        "ester_weight_factor": 1.0,
        "source_tier": "research_chemical_enrichment",
        "metadata": {
            "evidence_tier": "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION",
            "regulatory_status": "VETERINARY / RESEARCH_CHEMICAL",
            "human_clinical_trials": False,
            "data_sources": [
                "ChEMBL In Vitro Assays",
                "PubChem Compound Database",
                "Interspecies Allometric Scaling & QSPR PK Engine"
            ],
            "data_limitations": {
                "has_human_trials": False,
                "has_human_pk": False,
                "has_chronic_toxicity_studies": False,
                "has_cyp_metabolite_mapping": False,
                "known_limitations": [
                    "No FDA or EMA human clinical trials conducted for systemic human administration.",
                    "Pharmacokinetics derived from veterinary models and in vitro human receptor assays.",
                    "Long-term neurodegenerative and cardiovascular safety profiles uncharacterized in humans."
                ]
            }
        },
        "mechanism": "High-affinity binding to nuclear androgen receptor (AR / NR3C4, ~3-5x affinity of testosterone) and moderate progestogenic agonist activity (PGR / NR3C3). Non-aromatizable triene structure with strong anti-glucocorticoid and anabolic potency.",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 0.7, "gene_symbol": "AR"},
            {"target": "Progesterone Receptor (PGR / NR3C3)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 1.2, "gene_symbol": "PGR"},
            {"target": "Glucocorticoid Receptor (NR3C1)", "action": "antagonist", "family": "Nuclear Receptor", "gene_symbol": "NR3C1"}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
    },
    "trenbolone_acetate": {
        "name": "Trenbolone Acetate",
        "canonical_name": "Trenbolone Acetate",
        "synonyms": ["trenace", "trena", "finajet", "finaplix", "trenboloneacetate"],
        "drug_class": "19-Nor Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "19-Nor Derivative", "Short-Acting Depot Ester"],
        "molecular_weight": 312.41,
        "logp": 4.5,
        "oral_bioavailability": 0.03,
        "half_life": "1.5 days (36 hours)",
        "t_half_numeric": 36.0,
        "absorption_rate_ka": 0.08,
        "volume_of_distribution": 1.1,
        "protein_binding": 98.0,
        "is_ester": True,
        "ester_name": "Acetate",
        "parent_compound_id": "trenbolone",
        "ester_weight_factor": 0.865,
        "mechanism": "Short-acting intramuscular depot prodrug of trenbolone. Hydrolyzed by endogenous esterases into active trenbolone.",
    },
    "trenbolone_enanthate": {
        "name": "Trenbolone Enanthate",
        "canonical_name": "Trenbolone Enanthate",
        "synonyms": ["trene", "trenenanthate", "trenboloneenanthate"],
        "drug_class": "19-Nor Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "19-Nor Derivative", "Long-Acting Depot Ester"],
        "molecular_weight": 382.54,
        "logp": 6.1,
        "oral_bioavailability": 0.03,
        "half_life": "7-10 days (168 hours)",
        "t_half_numeric": 168.0,
        "absorption_rate_ka": 0.025,
        "volume_of_distribution": 1.1,
        "protein_binding": 98.0,
        "is_ester": True,
        "ester_name": "Enanthate",
        "parent_compound_id": "trenbolone",
        "ester_weight_factor": 0.706,
        "mechanism": "Long-acting intramuscular depot prodrug of trenbolone. Hydrolyzed by endogenous esterases into active trenbolone.",
    },
    "trenbolone_hexahydrophenylcarbonate": {
        "name": "Trenbolone Hexahydrobenzylcarbonate",
        "canonical_name": "Trenbolone Hexahydrobenzylcarbonate (Parabolan)",
        "synonyms": ["parabolan", "trenhex", "trenbolonecyclohexylmethylcarbonate"],
        "drug_class": "19-Nor Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "19-Nor Derivative", "Extended Depot Ester"],
        "molecular_weight": 410.55,
        "logp": 6.5,
        "oral_bioavailability": 0.03,
        "half_life": "14 days (336 hours)",
        "t_half_numeric": 336.0,
        "absorption_rate_ka": 0.012,
        "volume_of_distribution": 1.1,
        "protein_binding": 98.0,
        "is_ester": True,
        "ester_name": "Hexahydrobenzylcarbonate",
        "parent_compound_id": "trenbolone",
        "ester_weight_factor": 0.658,
        "mechanism": "Extended-release intramuscular depot prodrug of trenbolone.",
    },
    "nandrolone": {
        "name": "Nandrolone",
        "canonical_name": "Nandrolone (19-Nortestosterone Base)",
        "synonyms": ["nandrolonebase", "19nortestosterone"],
        "drug_class": "19-Nor Anabolic Steroid / Progestin",
        "categories": ["Anabolic Steroid", "19-Nor Derivative"],
        "molecular_weight": 274.40,
        "logp": 2.6,
        "is_ester": False,
        "ester_weight_factor": 1.0,
        "mechanism": "Binds and activates androgen receptor (AR) and progesterone receptor (PGR).",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 0.4},
            {"target": "Progesterone Receptor (PGR / NR3C3)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 2.5}
        ],
    },
    "nandrolone_decanoate": {
        "name": "Nandrolone Decanoate",
        "canonical_name": "Nandrolone Decanoate",
        "synonyms": ["deca", "durabolin", "decadurabolin", "nandrolonedecanoate"],
        "drug_class": "19-Nor Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "19-Nor Derivative", "Prodrug Depot"],
        "molecular_weight": 428.65,
        "logp": 6.8,
        "half_life": "12 days (288 hours)",
        "t_half_numeric": 288.0,
        "is_ester": True,
        "ester_name": "Decanoate",
        "parent_compound_id": "nandrolone",
        "ester_weight_factor": 0.640,
    },
    "drostanolone": {
        "name": "Drostanolone",
        "canonical_name": "Drostanolone Base",
        "synonyms": ["masteronbase", "dromostanolone"],
        "drug_class": "DHT-Derived Anabolic Steroid",
        "categories": ["Anabolic Steroid", "DHT Derivative"],
        "molecular_weight": 304.47,
        "logp": 3.8,
        "is_ester": False,
        "ester_weight_factor": 1.0,
        "mechanism": "Non-aromatizing DHT derivative. High binding affinity to androgen receptor and mild anti-estrogenic properties.",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 0.6}
        ],
    },
    "drostanolone_propionate": {
        "name": "Drostanolone Propionate",
        "canonical_name": "Drostanolone Propionate",
        "synonyms": ["masteron", "masteronpropionate", "drostanolonepropionate"],
        "drug_class": "DHT-Derived Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "DHT Derivative", "Short-Acting Ester"],
        "molecular_weight": 360.53,
        "logp": 5.2,
        "half_life": "1.5 days (36 hours)",
        "t_half_numeric": 36.0,
        "is_ester": True,
        "ester_name": "Propionate",
        "parent_compound_id": "drostanolone",
        "ester_weight_factor": 0.844,
    },
    "drostanolone_enanthate": {
        "name": "Drostanolone Enanthate",
        "canonical_name": "Drostanolone Enanthate",
        "synonyms": ["masteronenanthate", "drostanoloneenanthate"],
        "drug_class": "DHT-Derived Anabolic Steroid Ester",
        "categories": ["Anabolic Steroid", "DHT Derivative", "Long-Acting Ester"],
        "molecular_weight": 416.64,
        "logp": 6.3,
        "half_life": "7 days (168 hours)",
        "t_half_numeric": 168.0,
        "is_ester": True,
        "ester_name": "Enanthate",
        "parent_compound_id": "drostanolone",
        "ester_weight_factor": 0.730,
    },
    "estradiol": {
        "name": "Estradiol",
        "canonical_name": "Estradiol (17-Beta Estradiol)",
        "synonyms": ["e2", "17betaestradiol", "estradiolbase"],
        "drug_class": "Estrogen Hormone",
        "categories": ["Hormone", "Estrogen"],
        "molecular_weight": 272.38,
        "logp": 2.4,
        "is_ester": False,
        "ester_weight_factor": 1.0,
        "mechanism": "Primary female sex hormone. Binds ESR1 and ESR2 nuclear receptors.",
        "receptor_targets": [
            {"target": "Estrogen Receptor Alpha (ESR1)", "action": "agonist", "family": "Nuclear Receptor"},
            {"target": "Estrogen Receptor Beta (ESR2)", "action": "agonist", "family": "Nuclear Receptor"}
        ],
    },
    "estradiol_valerate": {
        "name": "Estradiol Valerate",
        "canonical_name": "Estradiol Valerate",
        "synonyms": ["progynova", "delestrogen", "estradiolvalerate"],
        "drug_class": "Estrogen Hormone Ester",
        "categories": ["Hormone", "Estrogen Ester", "Prodrug Depot"],
        "molecular_weight": 356.50,
        "logp": 5.1,
        "half_life": "4 days (96 hours)",
        "t_half_numeric": 96.0,
        "is_ester": True,
        "ester_name": "Valerate",
        "parent_compound_id": "estradiol",
        "ester_weight_factor": 0.764,
    }
}


def _get_default_compounds() -> List[Dict[str, Any]]:
    compounds = []
    for key, value in CORE_SUPPLEMENT_LIBRARY.items():
        compounds.append({"key": key, **value})
    for key, value in CORE_ESTER_LIBRARY.items():
        compounds.append({"key": key, **value})
    return compounds


CANONICAL_SYNONYM_MAP: Dict[str, str] = {
    "testosterone": "testosterone",
    "testosteronebase": "testosterone",
    "testc": "testosterone_cypionate",
    "testcyp": "testosterone_cypionate",
    "testosteronecypionate": "testosterone_cypionate",
    "depotestosterone": "testosterone_cypionate",
    "teste": "testosterone_enanthate",
    "testenan": "testosterone_enanthate",
    "testosteroneenanthate": "testosterone_enanthate",
    "delatestryl": "testosterone_enanthate",
    "testp": "testosterone_propionate",
    "testprop": "testosterone_propionate",
    "testosteronepropionate": "testosterone_propionate",
    "testu": "testosterone_undecanoate",
    "testundec": "testosterone_undecanoate",
    "testosteroneundecanoate": "testosterone_undecanoate",
    "nandrolone": "nandrolone",
    "nandrolonebase": "nandrolone",
    "deca": "nandrolone_decanoate",
    "durabolin": "nandrolone_decanoate",
    "decadurabolin": "nandrolone_decanoate",
    "nandrolonedecanoate": "nandrolone_decanoate",
    "trenbolone": "trenbolone",
    "tren": "trenbolone",
    "trenbase": "trenbolone",
    "trienolone": "trenbolone",
    "trenace": "trenbolone_acetate",
    "trena": "trenbolone_acetate",
    "trenboloneacetate": "trenbolone_acetate",
    "finajet": "trenbolone_acetate",
    "finaplix": "trenbolone_acetate",
    "trene": "trenbolone_enanthate",
    "trenenanthate": "trenbolone_enanthate",
    "trenboloneenanthate": "trenbolone_enanthate",
    "parabolan": "trenbolone_hexahydrophenylcarbonate",
    "trenhex": "trenbolone_hexahydrophenylcarbonate",
    "drostanolone": "drostanolone",
    "masteron": "drostanolone",
    "masteronpropionate": "drostanolone",
    "drostanolonepropionate": "drostanolone",
    "masteronenanthate": "drostanolone",
    "drostanoloneenanthate": "drostanolone",
    "dromostanolone": "drostanolone",

    "superdrol": "methyldrostanolone",
    "methasterone": "methyldrostanolone",
    "17amethyldrostanolone": "methyldrostanolone",
    "17alphamethyldrostanolone": "methyldrostanolone",
    "arimidex": "anastrozole",
    "femara": "letrozole",
    "aromasin": "exemestane",
    "proscar": "finasteride",
    "propecia": "finasteride",
    "avodart": "dutasteride",
    "micardis": "telmisartan",
    "inspra": "eplerenone",
    "cialis": "tadalafil",
    "viagra": "sildenafil",
    "levitra": "vardenafil",
    "valium": "diazepam",
    "xanax": "alprazolam",
    "accutane": "isotretinoin",
    "glucophage": "metformin",
    "jardiance": "empagliflozin",
    "farxiga": "dapagliflozin",
    "ozempic": "semaglutide",
    "wegovy": "semaglutide",
    "mounjaro": "tirzepatide",
    "zepbound": "tirzepatide",
    "bystolic": "nebivolol",
    "lopressor": "metoprolol",
    "tenormin": "atenolol",
    # Supplements & Nutraceuticals
    "astaxanthin": "astaxanthin",
    "asta": "astaxanthin",
    "astaxanthine": "astaxanthin",
    "astareal": "astaxanthin",
    "coq10": "coq10",
    "ubiquinol": "coq10",
    "ubiquinone": "coq10",
    "coenzymeq10": "coq10",
    "milkthistle": "milk_thistle",
    "silymarin": "milk_thistle",
    "silybin": "milk_thistle",
    "silybummarianum": "milk_thistle",
    "siliphos": "milk_thistle",
    "curcumin": "curcumin",
    "turmeric": "curcumin",
    "turmericextract": "curcumin",
    "curcuminoids": "curcumin",
    "theracurmin": "curcumin",
    "longvida": "curcumin",
    "citrusbergamot": "citrus_bergamot",
    "bergamot": "citrus_bergamot",
    "bergamotextract": "citrus_bergamot",
    "bergamonte": "citrus_bergamot",
    "bpf": "citrus_bergamot",
    "alphalipoicacid": "alpha_lipoic_acid",
    "ala": "alpha_lipoic_acid",
    "rala": "alpha_lipoic_acid",
    "rlipoicacid": "alpha_lipoic_acid",
    "thiocticacid": "alpha_lipoic_acid",
    "taurine": "taurine",
    "ltaurine": "taurine",
    "melatonin": "melatonin",
    "circadin": "melatonin",
    "nac": "nac",
    "nacetylcysteine": "nac",
    "acetylcysteine": "nac",
    "tudca": "tudca",
    "tauroursodeoxycholicacid": "tudca",
    "tauroursodeoxycholate": "tudca",
    "alcar": "l_carnitine",
    "acetyllcarnitine": "l_carnitine",
    "carnitine": "l_carnitine",
    "lcarnitine": "l_carnitine",
    "lcarnitinetartrate": "l_carnitine",
    "allicin": "allicin",
    "garlic": "allicin",
    "garlicextract": "allicin",
    "alliumsativum": "allicin",
    "agedgarlicextract": "allicin",
    "diallylthiosulfinate": "allicin",
    "ltheanine": "l_theanine",
    "theanine": "l_theanine",
    "suntheanine": "l_theanine",
    "berberine": "berberine",
    "berberinehcl": "berberine",
    "omega3": "omega_3",
    "fishoil": "omega_3",
    "krilloil": "omega_3",
    "epadha": "omega_3",
    "epa": "omega_3",
    "dha": "omega_3",
    "ashwagandha": "ashwagandha",
    "ksm66": "ashwagandha",
    "sensoril": "ashwagandha",
    "withaniasomnifera": "ashwagandha",
    "quercetin": "quercetin",
    "quercetine": "quercetin",
    "quercetindihydrate": "quercetin",
    "isoquercetin": "quercetin",
    "bioflavonoid": "quercetin",
    "resveratrol": "resveratrol",
    "transresveratrol": "resveratrol",
    "stilbenoid": "resveratrol",
    "rhodiola": "rhodiola",
    "rhodiolarosea": "rhodiola",
    "salidroside": "rhodiola",
    "rosavin": "rhodiola",
    "goldenroot": "rhodiola",
    "bacopa": "bacopa",
    "bacopamonnieri": "bacopa",
    "brahmi": "bacopa",
    "bacosides": "bacopa",
    "ginkgobiloba": "ginkgo_biloba",
    "ginkgo": "ginkgo_biloba",
    "ginkgoextract": "ginkgo_biloba",
    "egb761": "ginkgo_biloba",
    "ginkgolides": "ginkgo_biloba",
    "panaxginseng": "panax_ginseng",
    "ginseng": "panax_ginseng",
    "redginseng": "panax_ginseng",
    "koreanginseng": "panax_ginseng",
    "ginsenosides": "panax_ginseng",
    "piperine": "piperine",
    "bioperine": "piperine",
    "blackpepperextract": "piperine",
    "pipernigrum": "piperine",
    "sulforaphane": "sulforaphane",
    "broccolisproutextract": "sulforaphane",
    "glucoraphanin": "sulforaphane",
    "stjohnswort": "st_johns_wort",
    "stjohnwort": "st_johns_wort",
    "hypericum": "st_johns_wort",
    "hypericumperforatum": "st_johns_wort",
    "hyperforin": "st_johns_wort",
    "hypericin": "st_johns_wort",
    "sawpalmetto": "saw_palmetto",
    "serenoarepens": "saw_palmetto",
    "permixon": "saw_palmetto",
    "greenteaextract": "green_tea_extract",
    "greentea": "green_tea_extract",
    "egcg": "green_tea_extract",
    "epigallocatechingallate": "green_tea_extract",
    "magnesium": "magnesium",
    "magnesiumglycinate": "magnesium",
    "magnesiumbisglycinate": "magnesium",
    "magnesiumcitrate": "magnesium",
    "magnesiumlthreonate": "magnesium",
    "magglycinate": "magnesium",
    "zinc": "zinc",
    "zincpicolinate": "zinc",
    "zinccitrate": "zinc",
    "zincgluconate": "zinc",
    "optizinc": "zinc",
    "tartcherry": "tart_cherry",
    "tartcherryextract": "tart_cherry",
    "montmorencycherry": "tart_cherry",
    "prunuscerasus": "tart_cherry",
    # Peptides & Research Bioregulators
    "bpc157": "bpc_157",
    "bpc": "bpc_157",
    "bodyprotectioncompound157": "bpc_157",
    "pl14736": "bpc_157",
    "tb500": "tb_500",
    "thymosinbeta4": "tb_500",
    "tbeta4": "tb_500",
    "ghkcu": "ghk_cu",
    "copperpeptide": "ghk_cu",
    "glycylhistidyllysine": "ghk_cu",
    "kpv": "kpv",
    "ara290": "ara_290",
    "cibinetide": "ara_290",
    "ipamorelin": "ipamorelin",
    "ipam": "ipamorelin",
    "cjc1295": "cjc_1295",
    "cjc1295dac": "cjc_1295",
    "cjc1295nodac": "cjc_1295",
    "modgrf": "cjc_1295",
    "modgrf129": "cjc_1295",
    "sermorelin": "sermorelin",
    "geref": "sermorelin",
    "tesamorelin": "tesamorelin",
    "egrifta": "tesamorelin",
    "ghrp2": "ghrp_2",
    "pralmorelin": "ghrp_2",
    "ghrp6": "ghrp_6",
    "hexarelin": "hexarelin",
    "examorelin": "hexarelin",
    "aod9604": "aod_9604",
    "aod": "aod_9604",
    "semaglutide": "semaglutide",
    "ozempic": "semaglutide",
    "wegovy": "semaglutide",
    "rybelsus": "semaglutide",
    "tirzepatide": "tirzepatide",
    "mounjaro": "tirzepatide",
    "zepbound": "tirzepatide",
    "retatrutide": "retatrutide",
    "ly3437943": "retatrutide",
    "cagrilintide": "cagrilintide",
    "melanotanii": "melanotan_ii",
    "melanotan2": "melanotan_ii",
    "mt2": "melanotan_ii",
    "bremelanotide": "bremelanotide",
    "pt141": "bremelanotide",
    "vyleesi": "bremelanotide",
    "semax": "semax",
    "selank": "selank",
    "epithalon": "epithalon",
    "epitalon": "epithalon",
    "epithalone": "epithalon",
    "dsip": "dsip",
    "deltasleepinducingpeptide": "dsip",
    "oxytocin": "oxytocin",
    "pitocin": "oxytocin",
    "masteron": "drostanolone",
    "masteronpropionate": "drostanolone",
    "masteronenanthate": "drostanolone",
    "drostanolonepropionate": "drostanolone",
    "motsc": "mots_c",
    "mots": "mots_c",
    "ss31": "elamipretide",
    "elamipretide": "elamipretide",
    "bendavia": "elamipretide",
    "thymosinalpha1": "thymosin_alpha_1",
    "thymalfasin": "thymosin_alpha_1",
    "zadaxin": "thymosin_alpha_1",
    "talpha1": "thymosin_alpha_1",
    "kisspeptin10": "kisspeptin_10",
    "kisspeptin": "kisspeptin_10",
    "kp10": "kisspeptin_10",
    "desmopressin": "desmopressin",
    "ddavp": "desmopressin",
    "octreotide": "octreotide",
    "sandostatin": "octreotide",
    "leuprolide": "leuprolide",
    "lupron": "leuprolide",
    "leuprorelin": "leuprolide",
    "alphagpc": "alpha_gpc",
    "cholinealfoscerate": "alpha_gpc",
    "gpc": "alpha_gpc",
    "lalphagpc": "alpha_gpc",
    "huperzinea": "huperzine_a",
    "huperzine": "huperzine_a",
    "huperziaserrata": "huperzine_a",
    "ltyrosine": "l_tyrosine",
    "tyrosine": "l_tyrosine",
    "nalt": "l_tyrosine",
    "nacetyltyrosine": "l_tyrosine",
    "nmn": "nmn",
    "nicotinamidemononucleotide": "nmn",
    "betanmn": "nmn",
    "apigenin": "apigenin",
    "lionsmane": "lions_mane",
    "hericiumerinaceus": "lions_mane",
    "tongkatali": "tongkat_ali",
    "longjack": "tongkat_ali",
    "eurycomalongifolia": "tongkat_ali",
    "noopept": "noopept",
    "gvs111": "noopept",
    "omberacetam": "noopept",
    "rapamycin": "rapamycin",
    "sirolimus": "rapamycin",
    "rapamune": "rapamycin",
}



def _normalize_compound_name(name: str | None) -> str:
    cleaned = str(name or "").strip().lower()
    cleaned = re.sub(r"^(?:l-|d-|dl-|\(r\)-|\(s\)-|\(\+-\)-|\(±\)-)", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned)
    return cleaned


def _phonetic_key(s: str) -> str:
    """Simplifies phonetic ambiguities (e.g. c->s before e/i/y, ph->f, double consonants, unstressed vowels)."""
    s = str(s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]", "", s)
    s = re.sub(r"ph", "f", s)
    s = re.sub(r"c(?=[eiy])", "s", s)
    s = re.sub(r"c(?=[aou])", "k", s)
    s = re.sub(r"ck", "k", s)
    s = re.sub(r"q", "k", s)
    s = re.sub(r"x", "ks", s)
    s = re.sub(r"(.)\1+", r"\1", s)
    if len(s) > 1:
        first = s[0]
        rest = re.sub(r"[aeiouy]", "", s[1:])
        return first + rest
    return s


def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


_CATALOG_MEMORY_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
_CATALOG_ALL_COMPOUNDS: Dict[str, List[Dict[str, Any]]] = {}
_CATALOG_VARIANTS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
_INITIALIZED_DATABASES: Set[str] = set()


class CatalogService:
    def __init__(self, database_path: str | None = None):
        self._custom_database_path = database_path
        if self.database_path not in _INITIALIZED_DATABASES:
            self._ensure_database()
            self.sync_seed_compounds()
            _INITIALIZED_DATABASES.add(self.database_path)

    def sync_seed_compounds(self) -> None:
        with self._connect() as conn:
            existing_keys = {str(row["key"]).lower() for row in conn.execute("SELECT key FROM compounds").fetchall()}
        for compound in _get_default_compounds():
            k = str(compound.get("key") or compound.get("name")).lower()
            if k and k not in existing_keys:
                self.upsert_compound(compound)

    @property
    def database_path(self) -> str:
        if self._custom_database_path:
            return self._custom_database_path
        env_db = os.getenv("HEALTHAI_CATALOG_DB")
        if env_db:
            return env_db
        return DEFAULT_CATALOG_DB_PATH

    def _connect(self) -> sqlite3.Connection:
        db_dir = os.path.dirname(self.database_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_database(self) -> None:
        try:
            self._init_database_tables()
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            db_file = self.database_path
            logger.error(f"Malformed or corrupted SQLite database detected at {db_file}: {e}. Auto-recovering clean database...")
            try:
                import shutil
                if os.path.isfile(db_file):
                    shutil.move(db_file, f"{db_file}.corrupt_{int(time.time())}")
                for extra in [f"{db_file}-wal", f"{db_file}-shm", f"{db_file}-journal"]:
                    if os.path.isfile(extra):
                        try:
                            os.remove(extra)
                        except Exception:
                            pass
            except Exception:
                pass
            self._init_database_tables()

    def _init_database_tables(self) -> None:
        with self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA temp_store=MEMORY;")
            except Exception:
                pass
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compounds (

                    key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    canonical_name TEXT,
                    canonical_key TEXT,
                    inchikey TEXT,
                    smiles TEXT,
                    logp REAL,
                    tpsa REAL,
                    molecular_weight REAL,
                    pka REAL,
                    hbd INTEGER,
                    hba INTEGER,
                    rotatable_bonds INTEGER,
                    synonyms TEXT,
                    external_ids TEXT,
                    drug_class TEXT,
                    compound_class TEXT,
                    route_of_administration TEXT,
                    formulation TEXT,
                    mechanism TEXT,
                    receptor_targets TEXT,
                    transporters TEXT,
                    phase2_enzymes TEXT,
                    categories TEXT,
                    indications TEXT,
                    dosing TEXT,
                    reason TEXT,
                    citation TEXT,
                    contraindications TEXT,
                    side_effects TEXT,
                    interactions TEXT,
                    warnings TEXT,
                    boxed_warning TEXT,
                    is_narrow_therapeutic_index INTEGER DEFAULT 0,
                    dilirank_class TEXT,
                    half_life TEXT,
                    oral_bioavailability REAL,
                    t_max REAL,
                    volume_of_distribution REAL,
                    protein_binding REAL,
                    metabolism TEXT,
                    clearance REAL,
                    clearance_routes TEXT,
                    primary_effects TEXT,
                    cyp_enzymes TEXT,
                    organ_burdens TEXT,
                    synergies TEXT,
                    metadata TEXT,
                    evidence_level TEXT DEFAULT 'moderate',
                    risk_band TEXT DEFAULT 'low',
                    graph_tags TEXT,
                    t_half_numeric REAL,
                    bioavailability_f REAL,
                    volume_of_distribution_l_kg REAL,
                    clearance_l_h_kg REAL,
                    t_max_h REAL,
                    c_max_ng_ml REAL,
                    fraction_unbound REAL,
                    protein_binding_pct REAL,
                    absorption_rate_ka REAL,
                    renal_clearance_fraction REAL,
                    bcs_class TEXT,
                    mec_ng_ml REAL,
                    mtc_ng_ml REAL,
                    therapeutic_index REAL,
                    e_max REAL,
                    ec50_nm REAL,
                    ic50_nm REAL,
                    hill_coefficient REAL,
                    pathway_details TEXT,
                    source_tier TEXT DEFAULT 'seed',
                    last_enriched_at TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(compounds)").fetchall()}
            additions = {
                "canonical_name": "TEXT",
                "canonical_key": "TEXT",
                "inchikey": "TEXT",
                "smiles": "TEXT",
                "logp": "REAL",
                "tpsa": "REAL",
                "molecular_weight": "REAL",
                "pka": "REAL",
                "hbd": "INTEGER",
                "hba": "INTEGER",
                "rotatable_bonds": "INTEGER",
                "synonyms": "TEXT",
                "external_ids": "TEXT",
                "drug_class": "TEXT",
                "compound_class": "TEXT",
                "route_of_administration": "TEXT",
                "formulation": "TEXT",
                "mechanism": "TEXT",
                "receptor_targets": "TEXT",
                "transporters": "TEXT",
                "phase2_enzymes": "TEXT",
                "categories": "TEXT",
                "indications": "TEXT",
                "dosing": "TEXT",
                "reason": "TEXT",
                "citation": "TEXT",
                "contraindications": "TEXT",
                "side_effects": "TEXT",
                "interactions": "TEXT",
                "warnings": "TEXT",
                "boxed_warning": "TEXT",
                "is_narrow_therapeutic_index": "INTEGER DEFAULT 0",
                "dilirank_class": "TEXT",
                "half_life": "TEXT",
                "oral_bioavailability": "REAL",
                "t_max": "REAL",
                "volume_of_distribution": "REAL",
                "protein_binding": "REAL",
                "metabolism": "TEXT",
                "clearance": "REAL",
                "clearance_routes": "TEXT",
                "primary_effects": "TEXT",
                "cyp_enzymes": "TEXT",
                "organ_burdens": "TEXT",
                "synergies": "TEXT",
                "t_half_numeric": "REAL",
                "bioavailability_f": "REAL",
                "volume_of_distribution_l_kg": "REAL",
                "clearance_l_h_kg": "REAL",
                "t_max_h": "REAL",
                "c_max_ng_ml": "REAL",
                "fraction_unbound": "REAL",
                "protein_binding_pct": "REAL",
                "absorption_rate_ka": "REAL",
                "renal_clearance_fraction": "REAL",
                "bcs_class": "TEXT",
                "mec_ng_ml": "REAL",
                "mtc_ng_ml": "REAL",
                "therapeutic_index": "REAL",
                "e_max": "REAL",
                "ec50_nm": "REAL",
                "ic50_nm": "REAL",
                "hill_coefficient": "REAL",
                "pathway_details": "TEXT",
                "source_tier": "TEXT DEFAULT 'seed'",
                "last_enriched_at": "TEXT",
                "parent_compound_id": "TEXT",
                "is_ester": "INTEGER DEFAULT 0",
                "ester_name": "TEXT",
                "ester_weight_factor": "REAL DEFAULT 1.0",
            }
            for column_name, column_type in additions.items():
                if column_name not in existing_columns:
                    conn.execute(f"ALTER TABLE compounds ADD COLUMN {column_name} {column_type}")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_name ON compounds(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_canonical_name ON compounds(canonical_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_drug_class ON compounds(drug_class)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_mechanism ON compounds(mechanism)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_indications ON compounds(indications)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_inchikey ON compounds(inchikey)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_source_tier ON compounds(source_tier)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_parent_id ON compounds(parent_compound_id)")

            # Relational Citations, Clinical Trials, and Claims Tables
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS citations (
                    id TEXT PRIMARY KEY,
                    pmid TEXT,
                    doi TEXT,
                    title TEXT NOT NULL,
                    authors TEXT,
                    journal TEXT,
                    pub_year INTEGER,
                    pub_date TEXT,
                    evidence_tier TEXT DEFAULT 'clinical_trial',
                    sample_size INTEGER,
                    mesh_terms TEXT,
                    key_findings TEXT,
                    compound_key TEXT,
                    url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clinical_trials (
                    nct_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    phase TEXT,
                    status TEXT,
                    sponsor TEXT,
                    enrollment INTEGER,
                    conditions TEXT,
                    interventions TEXT,
                    primary_outcomes TEXT,
                    compound_key TEXT,
                    start_year INTEGER,
                    completion_year INTEGER,
                    url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_claims (
                    id TEXT PRIMARY KEY,
                    compound_key TEXT NOT NULL,
                    claim_type TEXT,
                    subject TEXT,
                    predicate TEXT,
                    object TEXT,
                    magnitude_value REAL,
                    magnitude_unit TEXT,
                    direction TEXT,
                    consensus_score REAL DEFAULT 1.0,
                    dispute_status TEXT DEFAULT 'consensus',
                    contradiction_index REAL DEFAULT 0.0,
                    discovery_year INTEGER,
                    last_validated_year INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS claim_citations (
                    claim_id TEXT,
                    citation_id TEXT,
                    relationship TEXT DEFAULT 'SUPPORTS',
                    confidence REAL DEFAULT 1.0,
                    extract_snippet TEXT,
                    PRIMARY KEY(claim_id, citation_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_compound ON citations(compound_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_pmid ON citations(pmid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_year ON citations(pub_year)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trials_compound ON clinical_trials(compound_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_compound ON evidence_claims(compound_key)")

    def _resolve_canonical_key(self, compound: Dict[str, Any]) -> str | None:
        candidates = [
            compound.get("canonical_key"),
            compound.get("inchikey"),
            compound.get("standard_inchi_key"),
            compound.get("inchi_key"),
            (compound.get("metadata") or {}).get("inchikey") if isinstance(compound.get("metadata"), dict) else None,
        ]
        for value in candidates:
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
        return None

    def _merge_duplicate_record(self, conn: sqlite3.Connection, compound: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
        canonical_key = row.get("canonical_key") or row.get("inchikey")
        if not canonical_key:
            return row

        existing = conn.execute(
            "SELECT key FROM compounds WHERE canonical_key = ? OR inchikey = ? LIMIT 1",
            (canonical_key, canonical_key),
        ).fetchone()
        if existing is None or existing["key"] == row["key"]:
            return row

        row["key"] = existing["key"]
        return row

    def deduplicate_database(self) -> int:
        """Finds and merges duplicate compound entries in the SQLite database by normalized name."""
        merged_count = 0
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM compounds").fetchall()
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for r in rows:
                row_dict = dict(r)
                norm_key = _normalize_compound_name(row_dict.get("name") or row_dict.get("key"))
                if norm_key:
                    grouped.setdefault(norm_key, []).append(row_dict)

            for norm_key, group_rows in grouped.items():
                if len(group_rows) < 2:
                    continue

                group_rows.sort(
                    key=lambda r: (
                        len(str(r.get("mechanism") or "")),
                        len(str(r.get("receptor_targets") or "")),
                        0 if str(r.get("key", "")).startswith("CHEMBL") else 1,
                    ),
                    reverse=True,
                )

                primary = group_rows[0]
                secondary_rows = group_rows[1:]

                for sec in secondary_rows:
                    if not primary.get("canonical_key") and sec.get("canonical_key"):
                        primary["canonical_key"] = sec["canonical_key"]
                    if not primary.get("inchikey") and sec.get("inchikey"):
                        primary["inchikey"] = sec["inchikey"]
                    if not primary.get("smiles") and sec.get("smiles"):
                        primary["smiles"] = sec["smiles"]

                    conn.execute("DELETE FROM compounds WHERE key = ?", (sec["key"],))
                    merged_count += 1

                conn.execute(
                    "UPDATE compounds SET canonical_key = ?, inchikey = ?, smiles = COALESCE(smiles, ?) WHERE key = ?",
                    (primary.get("canonical_key"), primary.get("inchikey"), primary.get("smiles"), primary["key"]),
                )

            conn.commit()
        return merged_count

    def reset_database(self) -> None:
        _INITIALIZED_DATABASES.discard(self.database_path)
        _CATALOG_ALL_COMPOUNDS.pop(self.database_path, None)
        _CATALOG_VARIANTS.pop(self.database_path, None)
        keys_to_del = [k for k in _CATALOG_MEMORY_CACHE if k[0] == self.database_path]
        for k in keys_to_del:
            _CATALOG_MEMORY_CACHE.pop(k, None)
        with self._connect() as conn:
            conn.execute("DROP TABLE IF EXISTS compounds")
        self._ensure_database()
        self.seed_default_compounds()
        _INITIALIZED_DATABASES.add(self.database_path)

    def seed_default_compounds(self) -> None:
        for compound in _get_default_compounds():
            self.upsert_compound(compound)

    def _serialize(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _deserialize(self, value: str | None, default: Any = None) -> Any:
        if value is None:
            return default if default is not None else []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else []

    def upsert_compound(self, compound: Dict[str, Any]) -> Dict[str, Any]:
        key = str(compound.get("key") or compound.get("name") or "compound").strip() or "compound"
        canonical_key = self._resolve_canonical_key(compound)
        if canonical_key:
            key = str(compound.get("key") or canonical_key).strip() or canonical_key

        row = {
            "key": key,
            "name": compound.get("name", key),
            "canonical_name": compound.get("canonical_name") or compound.get("name") or key,
            "canonical_key": canonical_key,
            "inchikey": canonical_key,
            "smiles": compound.get("smiles") or (compound.get("metadata", {}).get("chembl", {}) if isinstance(compound.get("metadata"), dict) else {}).get("smiles"),
            "logp": compound.get("logp") or compound.get("logP"),
            "tpsa": compound.get("tpsa"),
            "molecular_weight": compound.get("molecular_weight") or compound.get("mw"),
            "pka": compound.get("pka"),
            "hbd": compound.get("hbd"),
            "hba": compound.get("hba"),
            "rotatable_bonds": compound.get("rotatable_bonds"),
            "synonyms": self._serialize(compound.get("synonyms", [])),
            "external_ids": self._serialize(compound.get("external_ids", {})),
            "drug_class": compound.get("drug_class"),
            "compound_class": compound.get("compound_class"),
            "route_of_administration": compound.get("route_of_administration"),
            "formulation": compound.get("formulation"),
            "mechanism": compound.get("mechanism"),
            "receptor_targets": self._serialize(compound.get("receptor_targets", [])),
            "transporters": self._serialize(compound.get("transporters", {"substrates": [], "inhibitors": [], "inducers": []})),
            "phase2_enzymes": self._serialize(compound.get("phase2_enzymes", {"substrates": [], "inhibitors": [], "inducers": []})),
            "categories": self._serialize(compound.get("categories", [])),
            "indications": self._serialize(compound.get("indications", [])),
            "dosing": self._serialize(compound.get("dosing", {})),
            "reason": compound.get("reason"),
            "citation": compound.get("citation"),
            "contraindications": self._serialize(compound.get("contraindications", [])),
            "side_effects": self._serialize(compound.get("side_effects", [])),
            "interactions": self._serialize(compound.get("interactions", [])),
            "warnings": self._serialize(compound.get("warnings", [])),
            "boxed_warning": compound.get("boxed_warning"),
            "is_narrow_therapeutic_index": 1 if compound.get("is_narrow_therapeutic_index") else 0,
            "dilirank_class": compound.get("dilirank_class"),
            "half_life": compound.get("half_life"),
            "oral_bioavailability": compound.get("oral_bioavailability"),
            "t_max": compound.get("t_max"),
            "volume_of_distribution": compound.get("volume_of_distribution"),
            "protein_binding": compound.get("protein_binding"),
            "metabolism": compound.get("metabolism"),
            "clearance": compound.get("clearance"),
            "clearance_routes": compound.get("clearance_routes"),
            "primary_effects": self._serialize(compound.get("primary_effects", [])),
            "cyp_enzymes": self._serialize(compound.get("cyp_enzymes", {"substrates": [], "inhibitors": [], "inducers": []})),
            "organ_burdens": self._serialize(compound.get("organ_burdens", {})),
            "synergies": self._serialize(compound.get("synergies", [])),
            "metadata": self._serialize(compound.get("metadata", {})),
            "evidence_level": compound.get("evidence_level", "moderate"),
            "risk_band": compound.get("risk_band", "low"),
            "graph_tags": self._serialize(compound.get("graph_tags", [])),
            "t_half_numeric": compound.get("t_half_numeric"),
            "bioavailability_f": compound.get("bioavailability_f"),
            "volume_of_distribution_l_kg": compound.get("volume_of_distribution_l_kg"),
            "clearance_l_h_kg": compound.get("clearance_l_h_kg"),
            "t_max_h": compound.get("t_max_h"),
            "c_max_ng_ml": compound.get("c_max_ng_ml"),
            "fraction_unbound": compound.get("fraction_unbound"),
            "protein_binding_pct": compound.get("protein_binding_pct"),
            "absorption_rate_ka": compound.get("absorption_rate_ka"),
            "renal_clearance_fraction": compound.get("renal_clearance_fraction"),
            "bcs_class": compound.get("bcs_class"),
            "mec_ng_ml": compound.get("mec_ng_ml"),
            "mtc_ng_ml": compound.get("mtc_ng_ml"),
            "therapeutic_index": compound.get("therapeutic_index"),
            "e_max": compound.get("e_max"),
            "ec50_nm": compound.get("ec50_nm"),
            "ic50_nm": compound.get("ic50_nm"),
            "hill_coefficient": compound.get("hill_coefficient"),
            "pathway_details": self._serialize(compound.get("pathway_details", [])),
            "source_tier": compound.get("source_tier", "seed"),
            "last_enriched_at": compound.get("last_enriched_at"),
            "parent_compound_id": compound.get("parent_compound_id"),
            "is_ester": 1 if compound.get("is_ester") else 0,
            "ester_name": compound.get("ester_name"),
            "ester_weight_factor": float(compound.get("ester_weight_factor") if compound.get("ester_weight_factor") is not None else 1.0),
        }

        with self._connect() as conn:
            row = self._merge_duplicate_record(conn, compound, row)
            conn.execute(
                """
                INSERT INTO compounds (
                    key, name, canonical_name, canonical_key, inchikey, smiles, logp, tpsa,
                    molecular_weight, pka, hbd, hba, rotatable_bonds, synonyms, external_ids,
                    drug_class, compound_class, route_of_administration, formulation, mechanism,
                    receptor_targets, transporters, phase2_enzymes, categories, indications, dosing,
                    reason, citation, contraindications, side_effects, interactions, warnings,
                    boxed_warning, is_narrow_therapeutic_index, dilirank_class, half_life,
                    oral_bioavailability, t_max, volume_of_distribution, protein_binding,
                    metabolism, clearance, clearance_routes, primary_effects, cyp_enzymes,
                    organ_burdens, synergies, metadata, evidence_level, risk_band, graph_tags,
                    t_half_numeric, bioavailability_f, volume_of_distribution_l_kg, clearance_l_h_kg,
                    t_max_h, c_max_ng_ml, fraction_unbound, protein_binding_pct, absorption_rate_ka,
                    renal_clearance_fraction, bcs_class, mec_ng_ml, mtc_ng_ml, therapeutic_index,
                    e_max, ec50_nm, ic50_nm, hill_coefficient, pathway_details, source_tier,
                    last_enriched_at, parent_compound_id, is_ester, ester_name, ester_weight_factor, updated_at
                )
                VALUES (
                    :key, :name, :canonical_name, :canonical_key, :inchikey, :smiles, :logp, :tpsa,
                    :molecular_weight, :pka, :hbd, :hba, :rotatable_bonds, :synonyms, :external_ids,
                    :drug_class, :compound_class, :route_of_administration, :formulation, :mechanism,
                    :receptor_targets, :transporters, :phase2_enzymes, :categories, :indications, :dosing,
                    :reason, :citation, :contraindications, :side_effects, :interactions, :warnings,
                    :boxed_warning, :is_narrow_therapeutic_index, :dilirank_class, :half_life,
                    :oral_bioavailability, :t_max, :volume_of_distribution, :protein_binding,
                    :metabolism, :clearance, :clearance_routes, :primary_effects, :cyp_enzymes,
                    :organ_burdens, :synergies, :metadata, :evidence_level, :risk_band, :graph_tags,
                    :t_half_numeric, :bioavailability_f, :volume_of_distribution_l_kg, :clearance_l_h_kg,
                    :t_max_h, :c_max_ng_ml, :fraction_unbound, :protein_binding_pct, :absorption_rate_ka,
                    :renal_clearance_fraction, :bcs_class, :mec_ng_ml, :mtc_ng_ml, :therapeutic_index,
                    :e_max, :ec50_nm, :ic50_nm, :hill_coefficient, :pathway_details, :source_tier,
                    :last_enriched_at, :parent_compound_id, :is_ester, :ester_name, :ester_weight_factor, CURRENT_TIMESTAMP
                )
                ON CONFLICT(key) DO UPDATE SET
                    name = excluded.name,
                    canonical_name = excluded.canonical_name,
                    canonical_key = excluded.canonical_key,
                    inchikey = excluded.inchikey,
                    smiles = COALESCE(excluded.smiles, compounds.smiles),
                    logp = COALESCE(excluded.logp, compounds.logp),
                    tpsa = COALESCE(excluded.tpsa, compounds.tpsa),
                    molecular_weight = COALESCE(excluded.molecular_weight, compounds.molecular_weight),
                    pka = COALESCE(excluded.pka, compounds.pka),
                    hbd = COALESCE(excluded.hbd, compounds.hbd),
                    hba = COALESCE(excluded.hba, compounds.hba),
                    rotatable_bonds = COALESCE(excluded.rotatable_bonds, compounds.rotatable_bonds),
                    synonyms = excluded.synonyms,
                    external_ids = excluded.external_ids,
                    drug_class = excluded.drug_class,
                    compound_class = excluded.compound_class,
                    route_of_administration = excluded.route_of_administration,
                    formulation = excluded.formulation,
                    mechanism = excluded.mechanism,
                    receptor_targets = excluded.receptor_targets,
                    transporters = excluded.transporters,
                    phase2_enzymes = excluded.phase2_enzymes,
                    categories = excluded.categories,
                    indications = excluded.indications,
                    dosing = excluded.dosing,
                    reason = excluded.reason,
                    citation = excluded.citation,
                    contraindications = excluded.contraindications,
                    side_effects = excluded.side_effects,
                    interactions = excluded.interactions,
                    warnings = excluded.warnings,
                    boxed_warning = excluded.boxed_warning,
                    is_narrow_therapeutic_index = excluded.is_narrow_therapeutic_index,
                    dilirank_class = excluded.dilirank_class,
                    half_life = excluded.half_life,
                    oral_bioavailability = excluded.oral_bioavailability,
                    t_max = excluded.t_max,
                    volume_of_distribution = excluded.volume_of_distribution,
                    protein_binding = excluded.protein_binding,
                    metabolism = excluded.metabolism,
                    clearance = excluded.clearance,
                    clearance_routes = excluded.clearance_routes,
                    primary_effects = excluded.primary_effects,
                    cyp_enzymes = excluded.cyp_enzymes,
                    organ_burdens = excluded.organ_burdens,
                    synergies = excluded.synergies,
                    metadata = excluded.metadata,
                    evidence_level = excluded.evidence_level,
                    risk_band = excluded.risk_band,
                    graph_tags = excluded.graph_tags,
                    t_half_numeric = COALESCE(excluded.t_half_numeric, compounds.t_half_numeric),
                    bioavailability_f = COALESCE(excluded.bioavailability_f, compounds.bioavailability_f),
                    volume_of_distribution_l_kg = COALESCE(excluded.volume_of_distribution_l_kg, compounds.volume_of_distribution_l_kg),
                    clearance_l_h_kg = COALESCE(excluded.clearance_l_h_kg, compounds.clearance_l_h_kg),
                    t_max_h = COALESCE(excluded.t_max_h, compounds.t_max_h),
                    c_max_ng_ml = COALESCE(excluded.c_max_ng_ml, compounds.c_max_ng_ml),
                    fraction_unbound = COALESCE(excluded.fraction_unbound, compounds.fraction_unbound),
                    protein_binding_pct = COALESCE(excluded.protein_binding_pct, compounds.protein_binding_pct),
                    absorption_rate_ka = COALESCE(excluded.absorption_rate_ka, compounds.absorption_rate_ka),
                    renal_clearance_fraction = COALESCE(excluded.renal_clearance_fraction, compounds.renal_clearance_fraction),
                    bcs_class = COALESCE(excluded.bcs_class, compounds.bcs_class),
                    mec_ng_ml = COALESCE(excluded.mec_ng_ml, compounds.mec_ng_ml),
                    mtc_ng_ml = COALESCE(excluded.mtc_ng_ml, compounds.mtc_ng_ml),
                    therapeutic_index = COALESCE(excluded.therapeutic_index, compounds.therapeutic_index),
                    e_max = COALESCE(excluded.e_max, compounds.e_max),
                    ec50_nm = COALESCE(excluded.ec50_nm, compounds.ec50_nm),
                    ic50_nm = COALESCE(excluded.ic50_nm, compounds.ic50_nm),
                    hill_coefficient = COALESCE(excluded.hill_coefficient, compounds.hill_coefficient),
                    pathway_details = COALESCE(excluded.pathway_details, compounds.pathway_details),
                    source_tier = COALESCE(excluded.source_tier, compounds.source_tier),
                    last_enriched_at = COALESCE(excluded.last_enriched_at, compounds.last_enriched_at),
                    parent_compound_id = COALESCE(excluded.parent_compound_id, compounds.parent_compound_id),
                    is_ester = COALESCE(excluded.is_ester, compounds.is_ester),
                    ester_name = COALESCE(excluded.ester_name, compounds.ester_name),
                    ester_weight_factor = COALESCE(excluded.ester_weight_factor, compounds.ester_weight_factor),
                    updated_at = CURRENT_TIMESTAMP
                """,
                row,
            )
            conn.commit()

        # Invalidate path cache
        self._invalidate_path_cache()
        comp = self._row_to_compound(row)
        for alias in [comp.get("key"), comp.get("name"), comp.get("canonical_name"), comp.get("canonical_key"), comp.get("inchikey")] + list(comp.get("synonyms") or []):
            if alias:
                _CATALOG_MEMORY_CACHE[(self.database_path, _normalize_compound_name(alias))] = comp

        return copy.deepcopy(comp)

    def _invalidate_path_cache(self) -> None:
        _CATALOG_ALL_COMPOUNDS.pop(self.database_path, None)
        _CATALOG_VARIANTS.pop(self.database_path, None)

    def _warm_cache(self) -> List[Dict[str, Any]]:
        db_path = self.database_path
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM compounds ORDER BY name ASC").fetchall()
            variant_rows = conn.execute(
                "SELECT parent_compound_id, key, name, ester_name, molecular_weight, ester_weight_factor, t_half_numeric, half_life FROM compounds WHERE parent_compound_id IS NOT NULL AND parent_compound_id != ''"
            ).fetchall()

        variants_map: Dict[str, List[Dict[str, Any]]] = {}
        for vr in variant_rows:
            pid = vr["parent_compound_id"]
            if pid not in variants_map:
                variants_map[pid] = []
            variants_map[pid].append({
                "key": vr["key"],
                "name": vr["name"],
                "ester_name": vr["ester_name"],
                "molecular_weight": vr["molecular_weight"],
                "ester_weight_factor": float(vr["ester_weight_factor"]) if vr["ester_weight_factor"] is not None else 1.0,
                "t_half_numeric": vr["t_half_numeric"],
                "half_life": vr["half_life"],
            })
        _CATALOG_VARIANTS[db_path] = variants_map

        compounds_list: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()
        for r in rows:
            comp = self._row_to_compound(dict(r))
            k = comp.get("key")
            if k and k not in seen_keys:
                seen_keys.add(k)
                compounds_list.append(comp)

        # Pass 1: exact primary keys
        for comp in compounds_list:
            k = comp.get("key")
            if k:
                norm_k = _normalize_compound_name(k)
                _CATALOG_MEMORY_CACHE[(db_path, norm_k)] = comp
                _CATALOG_MEMORY_CACHE[(db_path, str(k).lower())] = comp

        # Pass 2: exact names and canonical names
        for comp in compounds_list:
            for alias in [comp.get("name"), comp.get("canonical_name")]:
                if alias:
                    norm_alias = _normalize_compound_name(alias)
                    existing = _CATALOG_MEMORY_CACHE.get((db_path, norm_alias))
                    if existing is None or _normalize_compound_name(existing.get("key")) != norm_alias:
                        if existing is None or len(str(comp.get("key") or "")) <= len(str(existing.get("key") or "")):
                            _CATALOG_MEMORY_CACHE[(db_path, norm_alias)] = comp

        # Pass 3: remaining aliases, synonyms, and identifiers
        for comp in compounds_list:
            for alias in [comp.get("canonical_key"), comp.get("inchikey")] + list(comp.get("synonyms") or []):
                if alias:
                    norm_alias = _normalize_compound_name(alias)
                    existing = _CATALOG_MEMORY_CACHE.get((db_path, norm_alias))
                    if existing is None:
                        _CATALOG_MEMORY_CACHE[(db_path, norm_alias)] = comp

        _CATALOG_ALL_COMPOUNDS[db_path] = compounds_list
        return compounds_list

    def get_compound(self, key: str, auto_enrich: bool = True) -> Dict[str, Any] | None:
        if not key:
            return None

        norm_query = _normalize_compound_name(key)
        cache_key = (self.database_path, norm_query)
        if cache_key in _CATALOG_MEMORY_CACHE:
            cached_val = _CATALOG_MEMORY_CACHE[cache_key]
            if cached_val is not None:
                return copy.deepcopy(cached_val)
            if not auto_enrich:
                return None

        # Resolve known synonym/brand aliases to canonical entity key
        if norm_query in CANONICAL_SYNONYM_MAP:
            canonical_key = CANONICAL_SYNONYM_MAP[norm_query]
            if canonical_key != key:
                canon_res = self.get_compound(canonical_key, auto_enrich=auto_enrich)
                if canon_res is not None:
                    _CATALOG_MEMORY_CACHE[cache_key] = canon_res
                    return copy.deepcopy(canon_res)
                if not auto_enrich:
                    _CATALOG_MEMORY_CACHE[cache_key] = None
                    return None

        # Warm memory cache if not yet loaded for this DB path
        if self.database_path not in _CATALOG_ALL_COMPOUNDS:
            self._warm_cache()
            if cache_key in _CATALOG_MEMORY_CACHE:
                cached_val = _CATALOG_MEMORY_CACHE[cache_key]
                if cached_val is not None:
                    return copy.deepcopy(cached_val)
                if not auto_enrich:
                    return None

        normalized_query = str(key).strip().lower().replace(" ", "_").replace("-", "_")

        with self._connect() as conn:
            row = conn.execute("SELECT * FROM compounds WHERE key = ?", (key,)).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(key) = LOWER(?) LIMIT 1",
                    (key.strip(),),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(key) = LOWER(?) LIMIT 1",
                    (normalized_query,),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(name) = LOWER(?) OR LOWER(canonical_name) = LOWER(?) LIMIT 1",
                    (key.strip(), key.strip()),
                ).fetchone()
            if row is None:
                # Exact InChIKey or canonical_key match
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(canonical_key) = LOWER(?) OR LOWER(inchikey) = LOWER(?) LIMIT 1",
                    (key.strip(), key.strip()),
                ).fetchone()
            if row is None:
                # Exact synonym match in JSON synonyms array
                clean_syn = key.strip().lower()
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(synonyms) LIKE ? LIMIT 1",
                    (f'%"{clean_syn}"%',),
                ).fetchone()
            if row is None:
                # Normalized alphanumeric match across keys, names, and all synonyms
                target_norm = _normalize_compound_name(key)
                all_rows = conn.execute("SELECT * FROM compounds").fetchall()
                for r in all_rows:
                    if _normalize_compound_name(r["key"]) == target_norm or _normalize_compound_name(r["name"]) == target_norm:
                        row = r
                        break
                    syns = self._deserialize(r["synonyms"], [])
                    for s in syns:
                        if _normalize_compound_name(str(s)) == target_norm:
                            row = r
                            break
                    if row is not None:
                        break

            if row is None:
                # Generalized fuzzy / phonetic near-miss matching (e.g. "alison" -> "allicin", "cypionat" -> "cypionate")
                target_norm = _normalize_compound_name(key)
                if len(target_norm) >= 3:
                    target_pk = _phonetic_key(target_norm)
                    all_candidates: List[str] = []
                    row_by_cand: Dict[str, Any] = {}
                    row_by_pk: Dict[str, Any] = {}
                    all_rows = conn.execute("SELECT * FROM compounds").fetchall()
                    for r in all_rows:
                        k_norm = _normalize_compound_name(r["key"])
                        n_norm = _normalize_compound_name(r["name"])
                        if k_norm:
                            all_candidates.append(k_norm)
                            row_by_cand[k_norm] = r
                            pk = _phonetic_key(k_norm)
                            if pk not in row_by_pk:
                                row_by_pk[pk] = r
                        if n_norm and n_norm != k_norm:
                            all_candidates.append(n_norm)
                            row_by_cand[n_norm] = r
                            pk = _phonetic_key(n_norm)
                            if pk not in row_by_pk:
                                row_by_pk[pk] = r
                        syns = self._deserialize(r["synonyms"], [])
                        for s in syns:
                            s_norm = _normalize_compound_name(str(s))
                            if s_norm:
                                if s_norm not in row_by_cand:
                                    all_candidates.append(s_norm)
                                    row_by_cand[s_norm] = r
                                pk = _phonetic_key(s_norm)
                                if pk not in row_by_pk:
                                    row_by_pk[pk] = r

                    # 1. Phonetic matching
                    if target_pk in row_by_pk:
                        row = row_by_pk[target_pk]

                    # 2. Levenshtein edit-distance matching (<=2 for len>=5, <=1 for len<5)
                    if row is None:
                        max_dist = 2 if len(target_norm) >= 5 else 1
                        best_cand = None
                        best_dist = max_dist + 1
                        for cand in all_candidates:
                            if abs(len(cand) - len(target_norm)) <= max_dist:
                                d = _levenshtein_distance(target_norm, cand)
                                if d < best_dist and d <= max_dist:
                                    best_dist = d
                                    best_cand = cand
                        if best_cand:
                            row = row_by_cand.get(best_cand)

                    # 3. SequenceMatcher close match fallback (high-confidence typos only)
                    if row is None:
                        matches = difflib.get_close_matches(target_norm, all_candidates, n=1, cutoff=0.80)
                        if matches:
                            row = row_by_cand.get(matches[0])

        if row is not None:
            comp = self._row_to_compound(dict(row))
            parent_id = comp.get("parent_compound_id")
            if parent_id and parent_id != comp.get("key"):
                parent_comp = self.get_compound(parent_id, auto_enrich=False)
                if parent_comp:
                    if not comp.get("receptor_targets"):
                        comp["receptor_targets"] = copy.deepcopy(parent_comp.get("receptor_targets", []))
                    if not comp.get("drug_class") or comp.get("drug_class") == "Dietary Supplement / Chemical Compound":
                        comp["drug_class"] = parent_comp.get("drug_class") or comp.get("drug_class")
                    if not comp.get("mechanism") or len(str(comp.get("mechanism"))) < 15:
                        comp["mechanism"] = parent_comp.get("mechanism") or comp.get("mechanism")
                    if not comp.get("pathway_details"):
                        comp["pathway_details"] = copy.deepcopy(parent_comp.get("pathway_details", []))
                    if not comp.get("cyp_enzymes") or not any(comp["cyp_enzymes"].values()):
                        comp["cyp_enzymes"] = copy.deepcopy(parent_comp.get("cyp_enzymes", {}))
                    if not comp.get("side_effects"):
                        comp["side_effects"] = copy.deepcopy(parent_comp.get("side_effects", []))
                    if not comp.get("contraindications"):
                        comp["contraindications"] = copy.deepcopy(parent_comp.get("contraindications", []))
                    if not comp.get("interactions"):
                        comp["interactions"] = copy.deepcopy(parent_comp.get("interactions", []))
                    
                    comp["parent_info"] = {
                        "parent_key": parent_comp.get("key"),
                        "parent_name": parent_comp.get("name"),
                        "parent_mw": parent_comp.get("molecular_weight"),
                    }
                    
                    if (comp.get("ester_weight_factor") == 1.0 or not comp.get("ester_weight_factor")) and parent_comp.get("molecular_weight") and comp.get("molecular_weight"):
                        try:
                            comp["ester_weight_factor"] = round(float(parent_comp["molecular_weight"]) / float(comp["molecular_weight"]), 3)
                        except (ValueError, ZeroDivisionError):
                            pass

            db_path = self.database_path
            variants_map = _CATALOG_VARIANTS.get(db_path)
            if variants_map is None:
                self._warm_cache()
                variants_map = _CATALOG_VARIANTS.get(db_path, {})
            if comp.get("key") and comp.get("key") in variants_map:
                comp["variants"] = copy.deepcopy(variants_map[comp["key"]])

            for alias in [comp.get("key"), comp.get("name"), comp.get("canonical_name"), comp.get("canonical_key"), comp.get("inchikey"), key] + list(comp.get("synonyms") or []):
                if alias:
                    _CATALOG_MEMORY_CACHE[(self.database_path, _normalize_compound_name(alias))] = comp
            return copy.deepcopy(comp)

        if not auto_enrich:
            _CATALOG_MEMORY_CACHE[cache_key] = None
            return None

        # Write-through lazy enrichment fallback
        try:
            from app.services.live_enrichment import LiveEnrichmentService
            enricher = LiveEnrichmentService()
            profile = enricher.fetch_compound_profile(key)
            if profile:
                return self.upsert_compound(profile)
        except Exception:
            pass
        _CATALOG_MEMORY_CACHE[cache_key] = None
        return None

    def find_by_synonym(self, key: str, auto_enrich: bool = False) -> Dict[str, Any] | None:
        """Resolves a compound by synonym, alias, key, or canonical name."""
        return self.get_compound(key, auto_enrich=auto_enrich)

    def find_compounds_by_target(self, target_name_or_keyword: str, action: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Dynamically finds all catalog compounds that interact with or modulate a target enzyme/receptor.
        Optionally filters by action mode (e.g. 'inhibitor', 'antagonist', 'agonist', 'substrate').
        """
        tgt_kw = str(target_name_or_keyword or "").strip().lower()
        act_kw = str(action or "").strip().lower() if action else ""
        if not tgt_kw:
            return []

        results: List[Dict[str, Any]] = []
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            all_rows = conn.execute("SELECT * FROM compounds").fetchall()
            for r in all_rows:
                comp = self._row_to_compound(dict(r))
                targets = comp.get("receptor_targets") or []
                matched = False
                for t in targets:
                    t_str = str(t.get("target") or t.get("name") or "").lower()
                    t_act = str(t.get("action") or "").lower()
                    t_fam = str(t.get("family") or "").lower()
                    if (tgt_kw in t_str or tgt_kw in t_fam or any(w in t_str for w in tgt_kw.split() if len(w) >= 4)):
                        if not act_kw or act_kw in t_act or (act_kw == "inhibitor" and any(w in t_act for w in ["inhibitor", "antagonist", "blocker", "inactivator"])):
                            matched = True
                            break
                if matched and comp.get("key") not in [res["key"] for res in results]:
                    results.append(comp)
        return results

    def canonicalize_and_merge_stack(self, stack: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Unifies and merges stack entries that refer to the same chemical compound under different names
        (e.g., Drostanolone and Masteron, Methyldrostanolone and Superdrol).
        Aggregates dosages cleanly into a single canonical entry.
        """
        if not stack:
            return []

        merged_by_canonical: Dict[str, Dict[str, Any]] = {}
        for item in stack:
            if not isinstance(item, dict):
                continue
            raw_key = str(item.get("key") or item.get("name") or "").strip()
            if not raw_key:
                continue

            try:
                comp = self.get_compound(raw_key, auto_enrich=False)
            except TypeError:
                comp = self.get_compound(raw_key)
            canonical_id = (comp.get("canonical_key") or comp.get("parent_compound_id") or comp.get("inchikey") or comp.get("key") or raw_key).lower() if comp else raw_key.lower()

            dose_val = item.get("dose") if item.get("dose") is not None else item.get("dose_mg")
            try:
                dose_mg = float(dose_val) if dose_val is not None else None
            except (ValueError, TypeError):
                dose_mg = None

            unit = str(item.get("unit") or "mg").strip()

            if canonical_id in merged_by_canonical:
                existing = merged_by_canonical[canonical_id]
                if dose_mg is not None:
                    if existing.get("dose_mg") is not None:
                        existing["dose_mg"] += dose_mg
                        existing["dose"] = existing["dose_mg"]
                    else:
                        existing["dose_mg"] = dose_mg
                        existing["dose"] = dose_mg
                if "synonyms_merged" not in existing:
                    existing["synonyms_merged"] = [existing.get("name") or existing.get("key")]
                existing["synonyms_merged"].append(item.get("name") or raw_key)
            else:
                if comp:
                    new_entry = dict(comp)
                    new_entry.update(item)
                    new_entry["key"] = comp.get("key") or raw_key
                    new_entry["canonical_key"] = comp.get("canonical_key") or comp.get("key")
                    new_entry["canonical_name"] = comp.get("canonical_name") or comp.get("name")
                    new_entry["name"] = comp.get("name") or item.get("name") or comp.get("canonical_name")
                    new_entry["drug_class"] = comp.get("drug_class") or item.get("drug_class")
                    new_entry["inchikey"] = comp.get("inchikey")
                else:
                    new_entry = dict(item)
                if dose_mg is not None:
                    new_entry["dose_mg"] = dose_mg
                raw_k_lower = raw_key.lower()
                is_inj_aas = any(w in raw_k_lower for w in ["testosterone", "trenbolone", "nandrolone", "drostanolone", "boldenone", "methenolone", "primobolan", "masteron", "deca", "equipoise", "sustanon", "cypionate", "enanthate", "propionate", "undecanoate"]) and not any(w in raw_k_lower for w in ["oxandrolone", "anavar", "stanozolol", "winstrol", "dianabol", "anadrol", "turinabol", "superdrol", "sarm", "rad140", "lgd", "ostarine"])
                is_inj_pep = any(w in raw_k_lower for w in ["semaglutide", "tirzepatide", "retatrutide", "liraglutide", "bpc-157", "bpc_157", "tb-500", "tb_500", "somatropin", "hgh", "ipamorelin", "cjc"])
                default_route = "intramuscular" if is_inj_aas else ("subcutaneous" if is_inj_pep else "oral")
                new_entry["route"] = str(item.get("route") or (comp.get("route") if comp else None) or (comp.get("default_route") if comp else None) or default_route).strip().lower()
                merged_by_canonical[canonical_id] = new_entry

        return list(merged_by_canonical.values())

    def enrich_compound_online(self, key_or_name: str) -> Dict[str, Any] | None:
        """Enriches a compound in the catalog with live OpenFDA, ChEMBL, and RxNorm metadata."""
        from app.services.live_enrichment import LiveEnrichmentService
        from datetime import datetime, timezone

        compound = self.get_compound(key_or_name, auto_enrich=False)
        enricher = LiveEnrichmentService()
        if compound is None:
            return enricher.enrich_and_cache(key_or_name, catalog_service=self)

        enriched = enricher.enrich_compound(compound)
        enriched["source_tier"] = "live_enrichment"
        enriched["last_enriched_at"] = datetime.now(timezone.utc).isoformat()
        return self.upsert_compound(enriched)

    def get_compounds_by_keys(self, keys: List[str]) -> Dict[str, Dict[str, Any]]:
        if not keys:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        for key in keys:
            compound = self.get_compound(key)
            if compound:
                results[compound["key"]] = compound
                if compound.get("name"):
                    results[compound["name"].lower()] = compound

        return results

    def get_variants(self, compound_key: str) -> List[Dict[str, Any]]:
        """Returns available formulation and depot ester variants for a compound."""
        if not compound_key:
            return []
        db_path = self.database_path
        variants_map = _CATALOG_VARIANTS.get(db_path)
        if variants_map is None:
            self._warm_cache()
            variants_map = _CATALOG_VARIANTS.get(db_path, {})
        norm_k = _normalize_compound_name(compound_key)
        if compound_key in variants_map:
            return copy.deepcopy(variants_map[compound_key])
        if norm_k in variants_map:
            return copy.deepcopy(variants_map[norm_k])
        comp = self.get_compound(compound_key, auto_enrich=False)
        if comp:
            k = comp.get("key")
            if k and k in variants_map:
                return copy.deepcopy(variants_map[k])
            parent_id = comp.get("parent_compound_id")
            if parent_id and parent_id in variants_map:
                return copy.deepcopy(variants_map[parent_id])
        return []

    def _enrich_ester_variant_metadata(self, compounds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not compounds:
            return compounds
        db_path = self.database_path
        variants_map = _CATALOG_VARIANTS.get(db_path)
        if variants_map is None:
            self._warm_cache()
            variants_map = _CATALOG_VARIANTS.get(db_path, {})
        for comp in compounds:
            comp_key = comp.get("key")
            if comp_key and comp_key in variants_map:
                comp["variants"] = copy.deepcopy(variants_map[comp_key])
        return compounds

    def search_compounds(self, query: str, limit: int = 20, auto_enrich: bool = False) -> List[Dict[str, Any]]:
        query_str = str(query or "").strip().lower()
        try:
            limit_int = int(limit) if limit is not None else 20
        except (ValueError, TypeError):
            limit_int = 20
        limit = limit_int
        all_compounds = _CATALOG_ALL_COMPOUNDS.get(self.database_path)
        if all_compounds is None:
            all_compounds = self._warm_cache()

        if not query_str:
            unique_compounds = [copy.deepcopy(c) for c in all_compounds[:limit]]
            return self._enrich_ester_variant_metadata(unique_compounds)

        norm_q = _normalize_compound_name(query_str)
        scored_matches: List[Tuple[int, str, Dict[str, Any]]] = []

        for comp in all_compounds:
            comp_key = str(comp.get("key") or "").lower()
            comp_name = str(comp.get("name") or "").lower()
            comp_canonical = str(comp.get("canonical_name") or "").lower()
            comp_class = str(comp.get("drug_class") or "").lower()
            comp_indications = str(comp.get("indications") or "").lower()
            syns = [str(s).lower() for s in (comp.get("synonyms") or [])]

            norm_k = _normalize_compound_name(comp_key)
            norm_n = _normalize_compound_name(comp_name)
            norm_syns = [_normalize_compound_name(s) for s in syns]

            score = 0
            # Exact match
            if comp_name == query_str or comp_key == query_str or norm_n == norm_q or norm_k == norm_q:
                score = 100
            elif any(s == query_str or ns == norm_q for s, ns in zip(syns, norm_syns)):
                score = 90
            # Prefix match
            elif comp_name.startswith(query_str) or norm_n.startswith(norm_q):
                score = 80
            elif comp_key.startswith(query_str) or norm_k.startswith(norm_q):
                score = 75
            elif any(s.startswith(query_str) or ns.startswith(norm_q) for s, ns in zip(syns, norm_syns)):
                score = 70
            # Word boundary or substring match
            elif f" {query_str}" in f" {comp_name}" or norm_q in norm_n:
                score = 60
            elif query_str in comp_key or norm_q in norm_k:
                score = 50
            elif any(query_str in s or norm_q in ns for s, ns in zip(syns, norm_syns)):
                score = 45
            elif query_str in comp_canonical:
                score = 40
            elif query_str in comp_class:
                score = 30
            elif query_str in comp_indications:
                score = 20

            if score > 0:
                scored_matches.append((score, comp_name, comp))

        if scored_matches:
            scored_matches.sort(key=lambda x: (-x[0], x[1]))
            matched_compounds = [copy.deepcopy(x[2]) for x in scored_matches[:limit]]
            return self._enrich_ester_variant_metadata(matched_compounds)

        # On-demand write-through lookup if search returned 0 matches
        if auto_enrich and len(query_str) >= 3:
            try:
                enriched = self.get_compound(query_str, auto_enrich=True)
                if enriched:
                    return self._enrich_ester_variant_metadata([copy.deepcopy(enriched)])
            except Exception:
                pass

        return []

    def query_compounds(self, limit: int = 20, offset: int = 0, search: Optional[str] = None) -> tuple[List[Dict[str, Any]], int]:
        page_size = max(limit, 1)
        start = max(offset, 0)

        with self._connect() as conn:
            base_query = "FROM compounds"
            params: List[Any] = []
            where_clauses: List[str] = []

            if search:
                tokens = [part.strip().lower() for part in str(search).split() if part.strip()]
                for token in tokens:
                    where_clauses.append(
                        "(LOWER(COALESCE(key, '') || ' ' || COALESCE(name, '') || ' ' || COALESCE(canonical_name, '') || ' ' || COALESCE(drug_class, '') || ' ' || COALESCE(compound_class, '') || ' ' || COALESCE(route_of_administration, '') || ' ' || COALESCE(mechanism, '') || ' ' || COALESCE(synonyms, '') || ' ' || COALESCE(indications, '') || ' ' || COALESCE(graph_tags, '')) LIKE ?)"
                    )
                    params.append(f"%{token}%")

            where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            count_query = f"SELECT COUNT(*) AS total {base_query}{where_str}"
            total_row = conn.execute(count_query, params).fetchone()
            total = int(total_row["total"]) if total_row else 0

            select_query = f"SELECT * {base_query}{where_str} ORDER BY name ASC LIMIT ? OFFSET ?"
            fetch_params = list(params) + [page_size, start]
            rows = conn.execute(select_query, fetch_params).fetchall()

        return [self._row_to_compound(dict(row)) for row in rows], total

    def delete_compound(self, key: str) -> bool:
        if not key:
            return False
        self._invalidate_path_cache()
        keys_to_del = [
            k
            for k in _CATALOG_MEMORY_CACHE
            if k[0] == self.database_path
            and (
                k[1] == _normalize_compound_name(key)
                or (
                    _CATALOG_MEMORY_CACHE[k] is not None
                    and _CATALOG_MEMORY_CACHE[k].get("key") == key
                )
            )
        ]
        for k in keys_to_del:
            _CATALOG_MEMORY_CACHE.pop(k, None)
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM compounds WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def list_compounds(self, limit: int | None = None, offset: int = 0) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if limit is not None:
                rows = conn.execute("SELECT * FROM compounds ORDER BY name ASC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM compounds ORDER BY name ASC").fetchall()

        return [self._row_to_compound(dict(row)) for row in rows]

    def _row_to_compound(self, row: Dict[str, Any]) -> Dict[str, Any]:
        compound = {
            "key": row["key"],
            "name": row["name"],
            "canonical_name": row.get("canonical_name") or row.get("name"),
            "canonical_key": row.get("canonical_key") or row.get("inchikey"),
            "inchikey": row.get("inchikey") or row.get("canonical_key"),
            "smiles": row.get("smiles"),
            "logp": row.get("logp"),
            "tpsa": row.get("tpsa"),
            "molecular_weight": row.get("molecular_weight"),
            "pka": row.get("pka"),
            "hbd": row.get("hbd"),
            "hba": row.get("hba"),
            "rotatable_bonds": row.get("rotatable_bonds"),
            "synonyms": self._deserialize(row.get("synonyms")),
            "external_ids": self._deserialize(row.get("external_ids"), default={}),
            "drug_class": row["drug_class"],
            "compound_class": row.get("compound_class"),
            "route_of_administration": row.get("route_of_administration"),
            "formulation": row.get("formulation"),
            "mechanism": row["mechanism"],
            "receptor_targets": self._deserialize(row.get("receptor_targets")),
            "transporters": self._deserialize(row.get("transporters"), default={"substrates": [], "inhibitors": [], "inducers": []}),
            "phase2_enzymes": self._deserialize(row.get("phase2_enzymes"), default={"substrates": [], "inhibitors": [], "inducers": []}),
            "categories": self._deserialize(row.get("categories")),
            "indications": self._deserialize(row.get("indications")),
            "dosing": self._deserialize(row.get("dosing"), default={}),
            "reason": row.get("reason"),
            "citation": row.get("citation"),
            "contraindications": self._deserialize(row.get("contraindications")),
            "side_effects": self._deserialize(row.get("side_effects")),
            "interactions": self._deserialize(row.get("interactions")),
            "warnings": self._deserialize(row.get("warnings")),
            "boxed_warning": row.get("boxed_warning"),
            "is_narrow_therapeutic_index": bool(row.get("is_narrow_therapeutic_index", 0)),
            "dilirank_class": row.get("dilirank_class"),
            "half_life": row.get("half_life"),
            "oral_bioavailability": row.get("oral_bioavailability"),
            "t_max": row.get("t_max"),
            "volume_of_distribution": row.get("volume_of_distribution"),
            "protein_binding": row.get("protein_binding"),
            "metabolism": row.get("metabolism"),
            "clearance": row.get("clearance"),
            "clearance_routes": row.get("clearance_routes"),
            "primary_effects": self._deserialize(row.get("primary_effects")),
            "cyp_enzymes": self._deserialize(row.get("cyp_enzymes"), default={"substrates": [], "inhibitors": [], "inducers": []}),
            "organ_burdens": self._deserialize(row.get("organ_burdens"), default={}),
            "synergies": self._deserialize(row.get("synergies"), default=[]),
            "metadata": self._deserialize(row.get("metadata"), default={}),
            "evidence_level": row.get("evidence_level", "moderate"),
            "risk_band": row.get("risk_band", "low"),
            "graph_tags": self._deserialize(row.get("graph_tags")),
            "t_half_numeric": row.get("t_half_numeric"),
            "bioavailability_f": row.get("bioavailability_f"),
            "volume_of_distribution_l_kg": row.get("volume_of_distribution_l_kg"),
            "clearance_l_h_kg": row.get("clearance_l_h_kg"),
            "t_max_h": row.get("t_max_h"),
            "c_max_ng_ml": row.get("c_max_ng_ml"),
            "fraction_unbound": row.get("fraction_unbound"),
            "protein_binding_pct": row.get("protein_binding_pct"),
            "absorption_rate_ka": row.get("absorption_rate_ka"),
            "renal_clearance_fraction": row.get("renal_clearance_fraction"),
            "bcs_class": row.get("bcs_class"),
            "mec_ng_ml": row.get("mec_ng_ml"),
            "mtc_ng_ml": row.get("mtc_ng_ml"),
            "therapeutic_index": row.get("therapeutic_index"),
            "e_max": row.get("e_max"),
            "ec50_nm": row.get("ec50_nm"),
            "ic50_nm": row.get("ic50_nm"),
            "hill_coefficient": row.get("hill_coefficient"),
            "pathway_details": self._deserialize(row.get("pathway_details"), default=[]),
            "source_tier": row.get("source_tier", "seed"),
            "last_enriched_at": row.get("last_enriched_at"),
            "parent_compound_id": row.get("parent_compound_id"),
            "is_ester": bool(row.get("is_ester", 0)),
            "ester_name": row.get("ester_name"),
            "ester_weight_factor": float(row.get("ester_weight_factor") if row.get("ester_weight_factor") is not None else 1.0),
        }

        # Overlay structured seed library definitions if available
        comp_k = compound.get("key")
        seed_item = CORE_SUPPLEMENT_LIBRARY.get(comp_k) or CORE_ESTER_LIBRARY.get(comp_k) if comp_k else None
        if seed_item:
            if seed_item.get("smiles") and not compound.get("smiles"):
                compound["smiles"] = seed_item["smiles"]
            if seed_item.get("source_tier") and (compound.get("source_tier") in ("seed", None, "") or seed_item.get("source_tier") == "research_chemical_enrichment"):
                compound["source_tier"] = seed_item["source_tier"]
            if seed_item.get("metadata"):
                cur_meta = dict(compound.get("metadata") or {})
                for mk, mv in seed_item["metadata"].items():
                    if mk not in cur_meta or cur_meta[mk] is None or cur_meta[mk] == "":
                        cur_meta[mk] = mv
                compound["metadata"] = cur_meta
            if seed_item.get("volume_of_distribution_l_kg") is not None and compound.get("volume_of_distribution_l_kg") is None:
                compound["volume_of_distribution_l_kg"] = seed_item["volume_of_distribution_l_kg"]
            if seed_item.get("fraction_unbound") is not None and compound.get("fraction_unbound") is None:
                compound["fraction_unbound"] = seed_item["fraction_unbound"]

        burdens = compound.get("organ_burdens") or {}
        if not burdens or all(v == "none" for v in burdens.values()):
            from app.services.pharmacology_enricher import PharmacologyEnricher
            compound = PharmacologyEnricher.enrich_compound(compound)

        from app.services.dosing_service import get_default_compound_dose
        dose_info = get_default_compound_dose(compound)
        compound["default_dose"] = dose_info
        compound["dose"] = dose_info["dose_val"]
        compound["unit"] = dose_info["dose_unit"]
        compound["dose_display"] = dose_info["dose_display"]

        return compound

    def add_citation(self, citation_dict: Dict[str, Any]) -> str:
        """Adds or updates a citation record in the catalog database."""
        cid = str(citation_dict.get("id") or (f"pmid_{citation_dict['pmid']}" if citation_dict.get("pmid") else f"cite_{time.time()}"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO citations (
                    id, pmid, doi, title, authors, journal, pub_year, pub_date,
                    evidence_tier, sample_size, mesh_terms, key_findings, compound_key, url
                ) VALUES (
                    :id, :pmid, :doi, :title, :authors, :journal, :pub_year, :pub_date,
                    :evidence_tier, :sample_size, :mesh_terms, :key_findings, :compound_key, :url
                )
                ON CONFLICT(id) DO UPDATE SET
                    pmid = excluded.pmid,
                    doi = excluded.doi,
                    title = excluded.title,
                    authors = excluded.authors,
                    journal = excluded.journal,
                    pub_year = excluded.pub_year,
                    pub_date = excluded.pub_date,
                    evidence_tier = excluded.evidence_tier,
                    sample_size = excluded.sample_size,
                    mesh_terms = excluded.mesh_terms,
                    key_findings = excluded.key_findings,
                    compound_key = excluded.compound_key,
                    url = excluded.url,
                    updated_at = CURRENT_TIMESTAMP
                """,
                {
                    "id": cid,
                    "pmid": citation_dict.get("pmid"),
                    "doi": citation_dict.get("doi"),
                    "title": citation_dict.get("title", ""),
                    "authors": json.dumps(citation_dict.get("authors", [])) if isinstance(citation_dict.get("authors"), list) else str(citation_dict.get("authors") or ""),
                    "journal": citation_dict.get("journal"),
                    "pub_year": citation_dict.get("pub_year"),
                    "pub_date": citation_dict.get("pub_date"),
                    "evidence_tier": citation_dict.get("evidence_tier", "clinical_trial"),
                    "sample_size": citation_dict.get("sample_size"),
                    "mesh_terms": json.dumps(citation_dict.get("mesh_terms", [])) if isinstance(citation_dict.get("mesh_terms"), list) else str(citation_dict.get("mesh_terms") or ""),
                    "key_findings": citation_dict.get("key_findings") or citation_dict.get("clinical_finding"),
                    "compound_key": citation_dict.get("compound_key"),
                    "url": citation_dict.get("url"),
                }
            )
        return cid

    def get_citations_for_compound(self, compound_key: str) -> List[Dict[str, Any]]:
        """Retrieves all peer-reviewed citations for a compound from the Citation Graph Database, SQLite, and PubMed."""
        ck = str(compound_key).strip().lower()
        results: List[Dict[str, Any]] = []
        seen_pmids: Set[str] = set()

        # 1. Query Citation Graph Database
        try:
            from app.knowledge_graph.graph_db import get_graph_database
            gdb = get_graph_database()
            graph_cites = gdb.get_citations_for_entity(ck, max_results=10)
            for gc in graph_cites:
                p = str(gc.get("pmid") or "")
                if p and p not in seen_pmids:
                    seen_pmids.add(p)
                    results.append(gc)
        except Exception as g_err:
            logger.debug("Graph DB citation retrieval notice: %s", g_err)

        # 2. Query SQLite catalog citations table
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM citations WHERE compound_key = ? ORDER BY pub_year DESC", (ck,)).fetchall()
                for r in rows:
                    item = dict(r)
                    p = str(item.get("pmid") or "")
                    if p and p not in seen_pmids:
                        seen_pmids.add(p)
                        item["authors"] = self._deserialize(item.get("authors"), default=[])
                        item["mesh_terms"] = self._deserialize(item.get("mesh_terms"), default=[])
                        results.append(item)
        except Exception:
            pass

        # 3. If empty, dynamically query PubMed and ingest into the Graph Database
        if not results:
            try:
                from app.services.pubmed_service import PubMedService
                p_svc = PubMedService()
                live_cites = p_svc.search_literature(ck, max_results=3)
                for lc in live_cites:
                    p = str(lc.get("pmid") or "")
                    if p and p not in seen_pmids:
                        seen_pmids.add(p)
                        results.append(lc)
            except Exception:
                pass

        results.sort(key=lambda x: (int(x.get("pub_year") or 0)), reverse=True)
        return results

    def get_clinical_trials_for_compound(self, compound_key: str) -> List[Dict[str, Any]]:
        """Retrieves clinical trial records for a compound."""
        ck = str(compound_key).strip().lower()
        try:
            from app.services.pubmed_service import PubMedService
            p_svc = PubMedService()
            return p_svc.get_clinical_trials_for_compound(ck)
        except Exception:
            return []

    def get_compound_evidence_dossier(self, compound_key: str) -> Dict[str, Any]:
        """
        Builds a comprehensive scientific evidence dossier for a compound, combining:
        - Structured peer-reviewed citations
        - Clinical trial registrations (NCT)
        - Chronological discovery timeline milestones
        - Known controversies and conflicting literature
        """
        ck = str(compound_key).strip().lower()
        compound = self.get_compound(ck, auto_enrich=False)
        citations = self.get_citations_for_compound(ck)
        trials = self.get_clinical_trials_for_compound(ck)

        try:
            from app.knowledge_graph.graph_db import get_graph_database
            gdb = get_graph_database()
            timeline = gdb.get_chronological_evidence_timeline(ck)
            claims = gdb.get_evidence_claims_for_entity(ck)
        except Exception:
            timeline = []
            claims = []

        try:
            from app.services.pubmed_service import PubMedService
            p_svc = PubMedService()
            conflicts = p_svc.detect_conflicts_for_compound(ck)
        except Exception:
            conflicts = []

        return {
            "compound_key": ck,
            "compound_name": (compound.get("name") or ck).title() if compound else ck.title(),
            "citation_count": len(citations),
            "citations": citations,
            "clinical_trials": trials,
            "chronological_timeline": timeline,
            "evidence_claims": claims,
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
        }
