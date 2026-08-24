from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from app.data.compounds import COMPOUND_LIBRARY

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
            {"target": "Carnitine Palmitoyltransferase (CPT1A / CPT2)", "action": "agonist", "family": "Enzyme / Fatty Acid Oxidation"}
        ],
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
    "nebivolol": {
        "name": "Nebivolol",
        "canonical_name": "Nebivolol (Bystolic)",
        "synonyms": ["bystolic", "nebivololhcl"],
        "drug_class": "Cardioselective Beta-1 Adrenergic Receptor Blocker / Nitric Oxide Vasodilator",
        "categories": ["Cardiovascular Support", "Beta Blocker", "Antihypertensive"],
        "molecular_weight": 405.44,
        "logp": 3.2,
        "oral_bioavailability": 0.12,
        "volume_of_distribution": 2.5,
        "protein_binding": 98.0,
        "half_life": "10-12 hours",
        "t_half_numeric": 12.0,
        "mechanism": "Highly selective beta-1 adrenergic receptor antagonist with endothelium-derived nitric oxide (NO)-mediated vasodilatory properties.",
        "receptor_targets": [
            {"target": "Beta-1 Adrenergic Receptor (ADRB1)", "action": "antagonist", "family": "GPCR", "affinity_ki": 2.0, "gene_symbol": "ADRB1"},
            {"target": "Beta-2 Adrenergic Receptor (ADRB2)", "action": "antagonist", "family": "GPCR", "affinity_ki": 30.0, "gene_symbol": "ADRB2"}
        ],
    },
    "caffeine": {
        "name": "Caffeine",
        "canonical_name": "Caffeine (1,3,7-Trimethylxanthine)",
        "synonyms": ["caffein", "137trimethylxanthine", "caffeineanhydrous"],
        "drug_class": "Central Nervous System Stimulant / Adenosine Antagonist",
        "categories": ["Dietary Supplement", "Nootropic", "Stimulant"],
        "molecular_weight": 194.19,
        "logp": -0.07,
        "oral_bioavailability": 0.99,
        "volume_of_distribution": 0.6,
        "protein_binding": 36.0,
        "half_life": "5 hours",
        "t_half_numeric": 5.0,
        "dosing": {
            "basis": "bodyweight",
            "unit": "mg/day",
            "mg_per_kg": {"threshold": 1, "common": 3, "heavy": 6}
        },
        "mechanism": "Non-selective competitive antagonist of adenosine A1 and A2A receptors, preventing fatigue signaling and elevating intracellular cAMP via phosphodiesterase inhibition.",
        "receptor_targets": [
            {"target": "A1 receptor", "action": "antagonist", "family": "GPCR", "gene_symbol": "ADORA1"},
            {"target": "Adenosine A2A Receptor (ADORA2A)", "action": "antagonist", "family": "GPCR", "gene_symbol": "ADORA2A"}
        ],
    },
    "creatine": {
        "name": "Creatine",
        "canonical_name": "Creatine Monohydrate",
        "synonyms": ["creatine", "creatinemonohydrate", "creapure"],
        "drug_class": "Dietary Supplement / Bioenergetic Amino Acid Derivative",
        "categories": ["Dietary Supplement", "Mitochondrial Support", "Ergogenic Aid"],
        "molecular_weight": 131.13,
        "logp": -1.5,
        "oral_bioavailability": 0.99,
        "volume_of_distribution": 0.8,
        "protein_binding": 0.0,
        "half_life": "3 hours",
        "t_half_numeric": 3.0,
        "dosing": {
            "basis": "bodyweight",
            "unit": "mg/day",
            "mg_per_kg": {"threshold": 10, "common": 20, "heavy": 50}
        },
        "mechanism": "Serves as substrate for creatine kinase to rapidly regenerate ATP from ADP during high-intensity cellular energy demands.",
        "receptor_targets": [
            {"target": "Creatine Kinase (CKMT1A / CKM)", "action": "substrate", "family": "Bioenergetics", "gene_symbol": "CKM"}
        ],
    },
    "methyldrostanolone": {
        "name": "Methyldrostanolone",
        "canonical_name": "Methyldrostanolone (Superdrol)",
        "canonical_key": "methyldrostanolone",
        "synonyms": ["superdrol", "methasterone", "17alphamethyldrostanolone"],
        "drug_class": "17-Alpha Alkylated Anabolic Steroid",
        "categories": ["Anabolic Steroid", "DHT Derivative", "Oral Anabolic"],
        "molecular_weight": 318.49,
        "logp": 3.9,
        "oral_bioavailability": 0.90,
        "volume_of_distribution": 1.2,
        "protein_binding": 90.0,
        "half_life": "8-12 hours",
        "t_half_numeric": 10.0,
        "mechanism": "Potent oral 17-alpha alkylated DHT derivative with powerful anabolic binding to the androgen receptor and minimal aromatization.",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 0.5, "gene_symbol": "AR"}
        ],
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
        "oral_bioavailability": 0.95,
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
        "oral_bioavailability": 0.95,
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
        "oral_bioavailability": 0.95,
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
        "oral_bioavailability": 0.95,
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
    compounds = [{"key": key, **value} for key, value in COMPOUND_LIBRARY.items()]
    for key, value in CORE_SUPPLEMENT_LIBRARY.items():
        compounds.append({"key": key, **value})
    for key, value in CORE_ESTER_LIBRARY.items():
        compounds.append({"key": key, **value})
    return compounds


_DEFAULT_COMPOUND_MAP: Dict[str, Dict[str, Any]] = {}

def _get_default_compound_map() -> Dict[str, Dict[str, Any]]:
    global _DEFAULT_COMPOUND_MAP
    if not _DEFAULT_COMPOUND_MAP:
        for c in _get_default_compounds():
            k = str(c.get("key") or "").strip().lower()
            if k:
                _DEFAULT_COMPOUND_MAP[k] = c
    return _DEFAULT_COMPOUND_MAP


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
    "drostanolone": "drostanolone",
    "masteron": "drostanolone_propionate",
    "masteronpropionate": "drostanolone_propionate",
    "drostanolonepropionate": "drostanolone_propionate",
    "masteronenanthate": "drostanolone_enanthate",
    "drostanoloneenanthate": "drostanolone_enanthate",
    "dromostanolone": "drostanolone",

    "masteronenanthate": "drostanolone",
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
}



def _normalize_compound_name(name: str | None) -> str:
    cleaned = str(name or "").strip().lower()
    cleaned = re.sub(r"^(?:l-|d-|dl-|\(r\)-|\(s\)-|\(\+-\)-|\(±\)-)", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned)
    return cleaned


_CATALOG_MEMORY_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
SEED_VERSION = "v2025_03_01_v13"


class CatalogService:
    def __init__(self, database_path: str | None = None):
        self._custom_database_path = database_path
        self._ensure_database()
        with self._connect() as conn:
            v = conn.execute("SELECT value FROM _db_metadata WHERE key = 'seed_version'").fetchone()
            current_v = v[0] if v else None
            count = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
        if current_v != SEED_VERSION or count < 10:
            self.sync_seed_compounds()
            with self._connect() as conn:
                conn.execute("INSERT OR REPLACE INTO _db_metadata (key, value) VALUES ('seed_version', ?)", (SEED_VERSION,))
                conn.commit()

    def sync_seed_compounds(self) -> None:
        with self._connect() as conn:
            existing_keys = {str(row["key"]).lower() for row in conn.execute("SELECT key FROM compounds").fetchall()}
        for compound in _get_default_compounds():
            k = str(compound.get("key") or compound.get("name")).lower()
            if k and k not in existing_keys:
                self.upsert_compound(compound)

    def refresh_seed_compounds(self) -> None:
        """Force re-sync seed compounds into database."""
        for compound in _get_default_compounds():
            k = compound.get("key") or compound.get("name")
            if k:
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
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL;")
            connection.execute("PRAGMA synchronous=NORMAL;")
            connection.execute("PRAGMA temp_store=MEMORY;")
            connection.execute("PRAGMA cache_size=-64000;")
        except sqlite3.DatabaseError:
            pass
        return connection

    def _ensure_database(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS _db_metadata (key TEXT PRIMARY KEY, value TEXT)")
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
        db_path = self.database_path
        keys_to_del = [k for k in _CATALOG_MEMORY_CACHE if k[0] == db_path]
        for k in keys_to_del:
            _CATALOG_MEMORY_CACHE.pop(k, None)
        with self._connect() as conn:
            conn.execute("DROP TABLE IF EXISTS compounds")
        self._ensure_database()
        self.seed_default_compounds()

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

        # Invalidate memory cache for updated record
        for alias in [row.get("key"), row.get("name"), row.get("canonical_name")]:
            if alias:
                _CATALOG_MEMORY_CACHE.pop((self.database_path, _normalize_compound_name(alias)), None)

        try:
            return self.get_compound(row["key"], auto_enrich=False)
        except TypeError:
            return self.get_compound(row["key"])

    def get_compound(self, key: str, auto_enrich: bool = True) -> Dict[str, Any] | None:
        if not key:
            return None

        norm_query = _normalize_compound_name(key)
        cache_key = (self.database_path, norm_query)
        if cache_key in _CATALOG_MEMORY_CACHE:
            return copy.deepcopy(_CATALOG_MEMORY_CACHE[cache_key])

        # Resolve known synonym/brand aliases to canonical entity key
        if norm_query in CANONICAL_SYNONYM_MAP:
            canonical_key = CANONICAL_SYNONYM_MAP[norm_query]
            if canonical_key != key:
                canon_res = self.get_compound(canonical_key, auto_enrich=auto_enrich)
                if canon_res:
                    _CATALOG_MEMORY_CACHE[cache_key] = canon_res
                    return copy.deepcopy(canon_res)

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

            for alias in [comp.get("key"), comp.get("name"), comp.get("canonical_name"), comp.get("canonical_key"), comp.get("inchikey"), key] + list(comp.get("synonyms") or []):
                if alias:
                    _CATALOG_MEMORY_CACHE[(self.database_path, _normalize_compound_name(alias))] = comp
            return copy.deepcopy(comp)

        if not auto_enrich:
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

        return None

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
            canonical_id = (comp.get("canonical_key") or comp.get("inchikey") or comp.get("key") or raw_key).lower() if comp else raw_key.lower()

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
                    new_entry["dose"] = dose_mg
                raw_k_lower = raw_key.lower()
                is_test_raw = "testosterone" in raw_k_lower and not any(w in raw_k_lower for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd", "ostarine", "s-4", "yk-11"])
                new_entry["route"] = str(item.get("route") or (comp.get("route") if comp else None) or (comp.get("default_route") if comp else None) or ("intramuscular" if is_test_raw else "oral")).strip().lower()
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

    def _enrich_ester_variant_metadata(self, compounds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not compounds:
            return compounds
        keys = [comp.get("key") for comp in compounds if comp.get("key")]
        if not keys:
            return compounds

        placeholders = ",".join("?" for _ in keys)
        with self._connect() as conn:
            variant_rows = conn.execute(
                f"SELECT key, name, ester_name, molecular_weight, ester_weight_factor, t_half_numeric, half_life, parent_compound_id FROM compounds WHERE parent_compound_id IN ({placeholders})",
                keys,
            ).fetchall()

            variants_by_parent: Dict[str, List[Dict[str, Any]]] = {}
            for r in variant_rows:
                parent_id = r["parent_compound_id"]
                if parent_id:
                    variants_by_parent.setdefault(parent_id, []).append({
                        "key": r["key"],
                        "name": r["name"],
                        "ester_name": r["ester_name"],
                        "molecular_weight": r["molecular_weight"],
                        "ester_weight_factor": float(r["ester_weight_factor"]) if r["ester_weight_factor"] is not None else 1.0,
                        "t_half_numeric": r["t_half_numeric"],
                        "half_life": r["half_life"],
                    })

            for comp in compounds:
                comp_key = comp.get("key")
                if comp_key and comp_key in variants_by_parent:
                    comp["variants"] = variants_by_parent[comp_key]
        return compounds

    def search_compounds(self, query: str, limit: int = 20, auto_enrich: bool = True) -> List[Dict[str, Any]]:
        query_str = str(query or "").strip().lower()
        if not query_str:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM compounds ORDER BY name ASC").fetchall()
            unique_compounds: List[Dict[str, Any]] = []
            seen_names: Set[str] = set()
            for row in rows:
                c = self._row_to_compound(dict(row))
                norm_name = str(c.get("name") or c.get("key") or "").strip().lower()
                if norm_name and norm_name not in seen_names:
                    seen_names.add(norm_name)
                    unique_compounds.append(c)
                    if len(unique_compounds) >= limit:
                        break
            return self._enrich_ester_variant_metadata(unique_compounds)

        with self._connect() as conn:
            pattern = f"%{query_str}%"
            rows = conn.execute(
                """
                SELECT * FROM compounds 
                WHERE LOWER(key) LIKE ? 
                   OR LOWER(name) LIKE ? 
                   OR LOWER(canonical_name) LIKE ? 
                   OR LOWER(drug_class) LIKE ?
                   OR LOWER(indications) LIKE ?
                   OR LOWER(synonyms) LIKE ?
                ORDER BY 
                  CASE 
                    WHEN LOWER(name) = LOWER(?) THEN 0
                    WHEN LOWER(name) LIKE ? THEN 1
                    WHEN LOWER(key) LIKE ? THEN 2
                    ELSE 3
                  END,
                  name ASC
                """,
                (pattern, pattern, pattern, pattern, pattern, pattern, query_str, f"{query_str}%", f"{query_str}%"),
            ).fetchall()

        unique_compounds = []
        seen_names = set()
        for row in rows:
            c = self._row_to_compound(dict(row))
            norm_name = str(c.get("name") or c.get("key") or "").strip().lower()
            if norm_name and norm_name not in seen_names:
                seen_names.add(norm_name)
                unique_compounds.append(c)
                if len(unique_compounds) >= limit:
                    break

        if unique_compounds:
            return self._enrich_ester_variant_metadata(unique_compounds)

        # On-demand write-through lookup if search returned 0 matches
        if auto_enrich and len(query_str) >= 3:
            try:
                enriched = self.get_compound(query_str, auto_enrich=True)
                if enriched:
                    return self._enrich_ester_variant_metadata([enriched])
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
        keys_to_del = [k for k in _CATALOG_MEMORY_CACHE if k[0] == self.database_path and (k[1] == _normalize_compound_name(key) or _CATALOG_MEMORY_CACHE[k].get("key") == key)]
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

        def_map = _get_default_compound_map()
        comp_key = str(compound.get("key") or "").lower()
        canon_k = str(compound.get("canonical_key") or "").lower()
        name_k = str(compound.get("name") or "").lower()
        seed = def_map.get(comp_key) or def_map.get(canon_k) or def_map.get(name_k)
        if not seed:
            for k, v in def_map.items():
                if len(k) >= 4 and (k in name_k or k in comp_key or k in canon_k):
                    seed = v
                    break
        if seed:
            if seed.get("protein_binding") is not None:
                compound["protein_binding"] = seed["protein_binding"]
            if seed.get("oral_bioavailability") is not None:
                compound["oral_bioavailability"] = seed["oral_bioavailability"]
            if seed.get("volume_of_distribution") is not None:
                compound["volume_of_distribution"] = seed["volume_of_distribution"]
            if seed.get("receptor_targets") and (not compound.get("receptor_targets") or compound.get("receptor_targets") == []):
                compound["receptor_targets"] = seed["receptor_targets"]
            if seed.get("dosing") and (not compound.get("dosing") or compound.get("dosing") == {}):
                compound["dosing"] = seed["dosing"]
            if seed.get("cyp_enzymes") and (not compound.get("cyp_enzymes") or not any(compound["cyp_enzymes"].values())):
                compound["cyp_enzymes"] = seed["cyp_enzymes"]
            if seed.get("organ_burdens") and (not compound.get("organ_burdens") or compound.get("organ_burdens") == {}):
                compound["organ_burdens"] = seed["organ_burdens"]
            if seed.get("metadata"):
                cur_m = compound.get("metadata") or {}
                if isinstance(cur_m, dict):
                    for mk, mv in seed["metadata"].items():
                        cur_m[mk] = mv
                    compound["metadata"] = cur_m

        burdens = compound.get("organ_burdens") or {}
        if not burdens or all(v == "none" for v in burdens.values()):
            from app.services.pharmacology_enricher import PharmacologyEnricher
            compound = PharmacologyEnricher.enrich_compound(compound)

        if seed:
            if seed.get("protein_binding") is not None:
                compound["protein_binding"] = seed["protein_binding"]
            if seed.get("oral_bioavailability") is not None:
                compound["oral_bioavailability"] = seed["oral_bioavailability"]
            if seed.get("volume_of_distribution") is not None:
                compound["volume_of_distribution"] = seed["volume_of_distribution"]

        from app.services.dosing_service import get_default_compound_dose
        dose_info = get_default_compound_dose(compound)
        compound["default_dose"] = dose_info
        compound["dose"] = dose_info["dose_val"]
        compound["unit"] = dose_info["dose_unit"]
        compound["dose_display"] = dose_info["dose_display"]

        meta = compound.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        if compound.get("is_approved") or compound.get("key") in {"semaglutide", "tirzepatide", "desmopressin", "octreotide", "leuprolide"}:
            meta["evidence_tier"] = "FDA_APPROVED_CLINICAL_DATA"
            meta["regulatory_status"] = "APPROVED_RX"
            meta["human_clinical_trials"] = True
        elif compound.get("key") == "retatrutide":
            meta["human_clinical_trials"] = True
        compound["metadata"] = meta

        for alias in [compound.get("key"), compound.get("name"), compound.get("canonical_name"), compound.get("canonical_key"), compound.get("inchikey")] + list(compound.get("synonyms") or []):
            if alias:
                _CATALOG_MEMORY_CACHE[(self.database_path, _normalize_compound_name(alias))] = compound

        return compound
