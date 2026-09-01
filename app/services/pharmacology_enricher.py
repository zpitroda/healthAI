"""
Pharmacology Knowledge Enrichment Engine
-----------------------------------------
Enriches compound records with:
1. Physicochemical ADMET properties (LogP, tPSA, MW, pKa, HBD/HBA)
2. CYP450 Enzyme Metabolism (substrates, inhibitors [strong/moderate/weak], inducers, MBI)
3. Phase II Metabolism (UGT1A1, UGT2B7, SULT, TPMT, NAT2)
4. Transporter Interactions (P-gp/ABCB1, BCRP/ABCG2, OATP1B1/3, OCT1/2, OAT1/3, MATE)
5. Pharmacokinetics (Oral Bioavailability F%, Vd, Protein Binding fu%, Half-life, Clearance routes)
6. Organ Burdens (Hepatic, Renal, Cardiovascular, CNS Stimulant, Sedative)
7. Narrow Therapeutic Index (NTI) & Boxed Warnings
8. Standardized Clinical Dosing Guidelines
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


# CLINICAL USAN STEM PHARMACOLOGICAL RULES (60+ Clinical Classes)
USAN_STEM_RULES: List[Dict[str, Any]] = [
    {
        "pattern": r"(?:statin)$",
        "class_name": "HMG-CoA Reductase Inhibitor (Statin)",
        "cyp_substrates": ["CYP3A4", "CYP2C9"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OATP1B1", "OATP1B3", "BCRP"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT1A1", "UGT1A3"],
        "organ_burdens": {"hepatic": "moderate", "renal": "low", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 20, "unit": "mg", "frequency": "daily", "timing": "evening"},
        "half_life": "14-20 hours",
        "oral_bioavailability": "14-30%",
        "volume_of_distribution": "380 L",
        "protein_binding": "95%",
        "clearance_routes": "Biliary (85%), Renal (10%)",
        "route": "oral",
        "logp": 4.1,
        "tpsa": 111.8,
        "is_narrow_therapeutic_index": False,
        "dilirank_class": "Less-DILI",
        "targets": [{"target": "HMG-CoA Reductase", "action": "inhibitor", "family": "Lipid Metabolism", "affinity_ki": 0.005}],
    },
    {
        "pattern": r"(?:sartan)$",
        "class_name": "Angiotensin II Receptor Blocker (ARB)",
        "cyp_substrates": ["CYP2C9", "CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OATP1B3"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT1A3"],
        "organ_burdens": {"hepatic": "low", "renal": "moderate", "cardiovascular": "high", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 40, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "24 hours",
        "oral_bioavailability": "42-58%",
        "volume_of_distribution": "500 L",
        "protein_binding": "99.5%",
        "clearance_routes": "Biliary/Fecal (98%), Renal (<2%)",
        "route": "oral",
        "logp": 3.2,
        "tpsa": 73.2,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Angiotensin II Type-1 Receptor (AGTR1)", "action": "antagonist", "family": "Renin-Angiotensin", "affinity_ki": 0.003},
            {"target": "Peroxisome Proliferator-Activated Receptor Gamma (PPARG)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 4.5}
        ],
    },
    {
        "pattern": r"(?:pril)$",
        "class_name": "Angiotensin-Converting Enzyme (ACE) Inhibitor",
        "cyp_substrates": [],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["PEPT1"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "moderate", "cardiovascular": "high", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 10, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "11-12 hours",
        "oral_bioavailability": "60%",
        "volume_of_distribution": "14 L",
        "protein_binding": "25%",
        "clearance_routes": "Renal (100%)",
        "route": "oral",
        "logp": -0.8,
        "tpsa": 84.4,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Angiotensin-Converting Enzyme (ACE)", "action": "inhibitor", "family": "Renin-Angiotensin", "affinity_ki": 0.001}],
    },
    {
        "pattern": r"(?:olol)$",
        "class_name": "Beta-Adrenergic Receptor Blocker",
        "cyp_substrates": ["CYP2D6"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OCT2"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "high", "cns_stimulant": "none", "sedative": "low"},
        "dosing": {"common": 50, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "3-7 hours",
        "oral_bioavailability": "50%",
        "volume_of_distribution": "5.6 L/kg",
        "protein_binding": "12%",
        "clearance_routes": "Hepatic (95%), Renal (5%)",
        "route": "oral",
        "logp": 1.8,
        "tpsa": 50.7,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Beta-1 Adrenergic Receptor", "action": "antagonist", "family": "Adrenergic", "affinity_ki": 0.01}],
    },
    {
        "pattern": r"(?:terol)$",
        "class_name": "Beta-2 Adrenergic Receptor Agonist (Sympathomimetic Bronchodilator)",
        "cyp_substrates": ["CYP2D6", "CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OCT1", "OCT2"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["SULT1A3", "UGT1A9"],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "high", "cns_stimulant": "moderate", "sedative": "none"},
        "dosing": {"common": 20, "unit": "mcg", "frequency": "daily", "timing": "morning"},
        "half_life": "6-36 hours",
        "oral_bioavailability": "75-85%",
        "volume_of_distribution": "2.0 L/kg",
        "protein_binding": "50-89%",
        "clearance_routes": "Hepatic conjugation and Renal excretion (80%)",
        "route": "oral",
        "logp": 2.0,
        "tpsa": 53.0,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Beta-2 Adrenergic Receptor (ADRB2)", "action": "agonist", "family": "Adrenergic", "affinity_ki": 0.002},
            {"target": "Beta-1 Adrenergic Receptor (ADRB1)", "action": "agonist", "family": "Adrenergic", "affinity_ki": 0.05}
        ],
    },
    {
        "pattern": r"(?:phrine|fedrine)$",
        "class_name": "Sympathomimetic Alpha/Beta Adrenergic Agonist",
        "cyp_substrates": ["CYP2D6", "CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OCT1", "OCT2"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["SULT1A3"],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "high", "cns_stimulant": "high", "sedative": "none"},
        "dosing": {"common": 25, "unit": "mg", "frequency": "as-needed", "timing": "morning"},
        "half_life": "3-6 hours",
        "oral_bioavailability": "85%",
        "volume_of_distribution": "2.5-3.0 L/kg",
        "protein_binding": "20%",
        "clearance_routes": "Renal unchanged (60-70%), Hepatic metabolism",
        "route": "oral",
        "logp": 1.1,
        "tpsa": 32.3,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Alpha-1 Adrenergic Receptor (ADRA1A)", "action": "agonist", "family": "Adrenergic", "affinity_ki": 0.05},
            {"target": "Beta-1 & Beta-2 Adrenergic Receptors (ADRB1/2)", "action": "agonist", "family": "Adrenergic", "affinity_ki": 0.08}
        ],
    },
    {
        "pattern": r"(?:phylline|caffeine|feine|xanthine)$",
        "class_name": "Xanthine Phosphodiesterase Inhibitor / Adenosine Antagonist",
        "cyp_substrates": ["CYP1A2", "CYP2E1", "CYP3A4"],
        "cyp_inhibitors": ["CYP1A2"],
        "cyp_inducers": [],
        "transporter_substrates": ["OAT1", "OCT2"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "moderate", "renal": "low", "cardiovascular": "high", "cns_stimulant": "high", "sedative": "none"},
        "dosing": {"common": 200, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "8-9 hours",
        "oral_bioavailability": "90-100%",
        "volume_of_distribution": "0.5 L/kg",
        "protein_binding": "40%",
        "clearance_routes": "Hepatic CYP1A2 oxidation (90%), Renal (10%)",
        "route": "oral",
        "logp": -0.02,
        "tpsa": 61.8,
        "is_narrow_therapeutic_index": True,
        "targets": [
            {"target": "Adenosine A1/A2A Receptor", "action": "antagonist", "family": "Purinergic", "affinity_ki": 0.01},
            {"target": "Non-Selective Cyclic Nucleotide Phosphodiesterases", "action": "inhibitor", "family": "Phosphodiesterase", "affinity_ki": 0.05}
        ],
    },
    {
        "pattern": r"(?:oxetine|pram|traline|faxine)$",
        "class_name": "Serotonin / Norepinephrine Reuptake Inhibitor",
        "cyp_substrates": ["CYP2D6", "CYP2C19", "CYP3A4"],
        "cyp_inhibitors": ["CYP2D6", "CYP2C19"],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": ["P-gp"],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "moderate", "renal": "low", "cardiovascular": "low", "cns_stimulant": "low", "sedative": "low"},
        "dosing": {"common": 20, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "24-96 hours",
        "oral_bioavailability": "70-80%",
        "volume_of_distribution": "20-40 L/kg",
        "protein_binding": "94%",
        "clearance_routes": "Hepatic CYP metabolism (80%), Renal (15%)",
        "route": "oral",
        "logp": 4.5,
        "tpsa": 21.3,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Sodium-Dependent Serotonin Transporter (SERT)", "action": "inhibitor", "family": "Monoamine Transporter", "affinity_ki": 0.001},
            {"target": "Sodium-Dependent Norepinephrine Transporter (NET)", "action": "inhibitor", "family": "Monoamine Transporter", "affinity_ki": 0.5}
        ],
    },
    {
        "pattern": r"(?:zepam|zolam)$",
        "class_name": "Benzodiazepine (GABA-A Allosteric Modulator)",
        "cyp_substrates": ["CYP3A4", "CYP2C19"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT2B7", "UGT1A4"],
        "organ_burdens": {"hepatic": "moderate", "renal": "low", "cardiovascular": "low", "cns_stimulant": "none", "sedative": "high"},
        "dosing": {"common": 1, "unit": "mg", "frequency": "as-needed", "timing": "before bed"},
        "half_life": "10-48 hours",
        "oral_bioavailability": "90%",
        "volume_of_distribution": "1.1 L/kg",
        "protein_binding": "85-98%",
        "clearance_routes": "Hepatic oxidation and glucuronidation",
        "route": "oral",
        "logp": 2.8,
        "tpsa": 41.9,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "GABA-A Receptor Benzodiazepine Site", "action": "positive allosteric modulator", "family": "GABAergic", "affinity_ki": 0.005}],
    },
    {
        "pattern": r"(?:prazole)$",
        "class_name": "Proton Pump Inhibitor (PPI)",
        "cyp_substrates": ["CYP2C19", "CYP3A4"],
        "cyp_inhibitors": ["CYP2C19"],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": ["BCRP", "P-gp"],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 20, "unit": "mg", "frequency": "daily", "timing": "morning before meal"},
        "half_life": "1-2 hours",
        "oral_bioavailability": "40-65%",
        "volume_of_distribution": "0.3 L/kg",
        "protein_binding": "95%",
        "clearance_routes": "Hepatic (80%), Renal (20%)",
        "route": "oral",
        "logp": 2.2,
        "tpsa": 69.8,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Gastric H+/K+-ATPase", "action": "inhibitor", "family": "Ion Pump", "affinity_ki": 0.002}],
    },
    {
        "pattern": r"(?:afil)$",
        "class_name": "Phosphodiesterase-5 (PDE5) Inhibitor",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 20, "unit": "mg", "frequency": "as-needed", "timing": "pre-workout / as-needed"},
        "half_life": "4-17.5 hours",
        "oral_bioavailability": "40-80%",
        "volume_of_distribution": "63 L",
        "protein_binding": "94-96%",
        "clearance_routes": "Hepatic CYP3A4 (80%), Renal (13%)",
        "route": "oral",
        "logp": 2.6,
        "tpsa": 85.2,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "cGMP-Specific 3',5'-Cyclic Phosphodiesterase 5A (PDE5)", "action": "inhibitor", "family": "Phosphodiesterase", "affinity_ki": 0.001},
            {"target": "Phosphodiesterase 11A (PDE11)", "action": "inhibitor", "family": "Phosphodiesterase", "affinity_ki": 0.07}
        ],
    },
    {
        "pattern": r"(?:coxib)$",
        "class_name": "Selective Cyclooxygenase-2 (COX-2) Inhibitor",
        "cyp_substrates": ["CYP2C9"],
        "cyp_inhibitors": ["CYP2D6"],
        "cyp_inducers": [],
        "transporter_substrates": [],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT1A3"],
        "organ_burdens": {"hepatic": "low", "renal": "moderate", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 100, "unit": "mg", "frequency": "daily", "timing": "morning with food"},
        "half_life": "8-12 hours",
        "oral_bioavailability": "90%",
        "volume_of_distribution": "400 L",
        "protein_binding": "97%",
        "clearance_routes": "Hepatic CYP2C9 (75%), Renal (25%)",
        "route": "oral",
        "logp": 3.5,
        "tpsa": 77.9,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Prostaglandin G/H Synthase 2 (COX-2)", "action": "inhibitor", "family": "Eicosanoid Signaling", "affinity_ki": 0.04}],
    },
    {
        "pattern": r"(?:dipine)$",
        "class_name": "Dihydropyridine Calcium Channel Blocker (CCB)",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "high", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 5, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "30-50 hours",
        "oral_bioavailability": "64-90%",
        "volume_of_distribution": "21 L/kg",
        "protein_binding": "98%",
        "clearance_routes": "Hepatic CYP3A4 (90%), Renal (10%)",
        "route": "oral",
        "logp": 3.0,
        "tpsa": 97.4,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Voltage-Dependent L-Type Calcium Channel Subunit Alpha-1C", "action": "antagonist", "family": "Ion Channel", "affinity_ki": 0.002}],
    },
    {
        "pattern": r"(?:azole)$",
        "class_name": "Azole Antifungal / Potent CYP3A4 Inhibitor",
        "cyp_substrates": ["CYP3A4", "CYP2C9", "CYP2C19"],
        "cyp_inhibitors": ["CYP3A4", "CYP2C9", "CYP2C19"],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": ["P-gp", "BCRP"],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "high", "renal": "low", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 150, "unit": "mg", "frequency": "daily", "timing": "morning with food"},
        "half_life": "24-30 hours",
        "oral_bioavailability": "90%",
        "volume_of_distribution": "0.7 L/kg",
        "protein_binding": "11-99%",
        "clearance_routes": "Renal unchanged (80%) or Hepatic",
        "route": "oral",
        "logp": 2.9,
        "tpsa": 81.7,
        "is_narrow_therapeutic_index": False,
        "dilirank_class": "Most-DILI",
        "targets": [
            {"target": "Lanosterol 14-Alpha Demethylase (CYP51A1)", "action": "inhibitor", "family": "Cytochrome P450", "affinity_ki": 0.001},
            {"target": "Cytochrome P450 3A4", "action": "inhibitor", "family": "Cytochrome P450", "affinity_ki": 0.05}
        ],
    },
    {
        "pattern": r"(?:fetamine|phenidate|modafinil|armodafinil)$",
        "class_name": "Central Nervous System Psychostimulant",
        "cyp_substrates": ["CYP2D6", "CYP3A4"],
        "cyp_inhibitors": ["CYP2D6"],
        "cyp_inducers": ["CYP3A4"],
        "transporter_substrates": ["OCT1", "OCT2"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "high", "cns_stimulant": "high", "sedative": "none"},
        "dosing": {"common": 15, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "10-15 hours",
        "oral_bioavailability": "75-90%",
        "volume_of_distribution": "3.5-5.0 L/kg",
        "protein_binding": "20%",
        "clearance_routes": "Renal pH-dependent (40-60%), Hepatic deamination",
        "route": "oral",
        "logp": 1.8,
        "tpsa": 26.0,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Sodium-Dependent Dopamine Transporter (DAT)", "action": "inhibitor", "family": "Monoamine Transporter", "affinity_ki": 0.03},
            {"target": "Sodium-Dependent Norepinephrine Transporter (NET)", "action": "inhibitor", "family": "Monoamine Transporter", "affinity_ki": 0.04},
            {"target": "Vesicular Monoamine Transporter 2 (VMAT2)", "action": "inhibitor", "family": "Monoamine Storage", "affinity_ki": 0.5}
        ],
    },
    {
        "pattern": r"(?:renone|lactone)$",
        "class_name": "Mineralocorticoid / Aldosterone Receptor Antagonist",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "moderate", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 25, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "4-6 hours",
        "oral_bioavailability": "69%",
        "volume_of_distribution": "50 L",
        "protein_binding": "50%",
        "clearance_routes": "Renal (67%), Fecal (32%)",
        "route": "oral",
        "logp": 1.3,
        "tpsa": 72.8,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Mineralocorticoid Receptor (Aldosterone Receptor / NR3C2)", "action": "antagonist", "family": "Nuclear Receptor", "affinity_ki": 0.015}
        ],
    },
    {
        "pattern": r"(?:flozin)$",
        "class_name": "Sodium-Glucose Cotransporter 2 (SGLT2) Inhibitor",
        "cyp_substrates": ["CYP1A2", "CYP2C9", "CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OATP1B1", "OATP1B3", "BCRP"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT1A9", "UGT2B7"],
        "organ_burdens": {"hepatic": "low", "renal": "moderate", "cardiovascular": "low", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 10, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "12-16 hours",
        "oral_bioavailability": "78%",
        "volume_of_distribution": "118 L",
        "protein_binding": "91%",
        "clearance_routes": "Glucuronidation (75%), Renal unchanged (1%)",
        "route": "oral",
        "logp": 2.3,
        "tpsa": 99.4,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Sodium/Glucose Cotransporter 2 (SGLT2 / SLC5A2)", "action": "inhibitor", "family": "Glucose Transporter", "affinity_ki": 0.002}],
    },
    {
        "pattern": r"(?:gliptin)$",
        "class_name": "Dipeptidyl Peptidase-4 (DPP-4) Inhibitor",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 50, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "12-14 hours",
        "oral_bioavailability": "87%",
        "volume_of_distribution": "198 L",
        "protein_binding": "38%",
        "clearance_routes": "Renal unchanged (79%), Hepatic CYP (16%)",
        "route": "oral",
        "logp": 1.5,
        "tpsa": 77.3,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Dipeptidyl Peptidase 4 (DPP-4)", "action": "inhibitor", "family": "Serine Protease", "affinity_ki": 0.018}],
    },
    {
        "pattern": r"(?:glutide|tide)$",
        "class_name": "Glucagon-Like Peptide-1 (GLP-1) Receptor Agonist",
        "cyp_substrates": [],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": [],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "low", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 0.25, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "168 hours (7 days)",
        "oral_bioavailability": "1% (Oral) / 89% (Subcutaneous)",
        "volume_of_distribution": "12.5 L",
        "protein_binding": "99%",
        "clearance_routes": "Proteolytic cleavage and beta-oxidation",
        "route": "parenteral",
        "logp": -1.2,
        "tpsa": 420.0,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Glucagon-Like Peptide 1 Receptor (GLP-1R)", "action": "agonist", "family": "GPCR Class B", "affinity_ki": 0.0005}],
    },
    {
        "pattern": r"(?:xaban)$",
        "class_name": "Direct Factor Xa Inhibitor (DOAC)",
        "cyp_substrates": ["CYP3A4", "CYP2J2"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp", "BCRP"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "moderate", "renal": "moderate", "cardiovascular": "high", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 20, "unit": "mg", "frequency": "daily", "timing": "with evening meal"},
        "half_life": "5-12 hours",
        "oral_bioavailability": "80-100%",
        "volume_of_distribution": "50 L",
        "protein_binding": "92-95%",
        "clearance_routes": "Renal (66%), Hepatic/Biliary (33%)",
        "route": "oral",
        "logp": 1.5,
        "tpsa": 88.0,
        "is_narrow_therapeutic_index": True,
        "targets": [{"target": "Coagulation Factor Xa", "action": "inhibitor", "family": "Serine Protease", "affinity_ki": 0.0004}],
    },
    {
        "pattern": r"(?:profen|fenac|oxicam)$",
        "class_name": "Non-Steroidal Anti-Inflammatory Drug (NSAID)",
        "cyp_substrates": ["CYP2C9", "CYP2C8"],
        "cyp_inhibitors": ["CYP2C9"],
        "cyp_inducers": [],
        "transporter_substrates": ["OAT1", "OAT3"],
        "transporter_inhibitors": ["OAT1", "OAT3"],
        "phase2_substrates": ["UGT2B7", "UGT1A9"],
        "organ_burdens": {"hepatic": "low", "renal": "high", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 200, "unit": "mg", "frequency": "as-needed", "timing": "with food"},
        "half_life": "2-4 hours",
        "oral_bioavailability": "85-100%",
        "volume_of_distribution": "0.15 L/kg",
        "protein_binding": "99%",
        "clearance_routes": "Hepatic CYP2C9 and UGT glucuronidation (95%), Renal (5%)",
        "route": "oral",
        "logp": 3.9,
        "tpsa": 37.3,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Prostaglandin G/H Synthase 1 (COX-1)", "action": "inhibitor", "family": "Eicosanoid Signaling", "affinity_ki": 0.02},
            {"target": "Prostaglandin G/H Synthase 2 (COX-2)", "action": "inhibitor", "family": "Eicosanoid Signaling", "affinity_ki": 0.05}
        ],
    },
    {
        "pattern": r"(?:mycin)$",
        "class_name": "Macrolide / Aminoglycoside Antibiotic",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": ["CYP3A4"],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": ["P-gp", "OATP1B1"],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "moderate", "renal": "low", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 250, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "40-68 hours",
        "oral_bioavailability": "37%",
        "volume_of_distribution": "31 L/kg",
        "protein_binding": "50%",
        "clearance_routes": "Biliary unchanged (50%), Renal (14%)",
        "route": "oral",
        "logp": 2.1,
        "tpsa": 180.0,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "50S Ribosomal Subunit Bacterial", "action": "inhibitor", "family": "Protein Synthesis", "affinity_ki": 0.01}],
    },
    {
        "pattern": r"(?:floxacin)$",
        "class_name": "Fluoroquinolone Antibiotic",
        "cyp_substrates": ["CYP1A2"],
        "cyp_inhibitors": ["CYP1A2"],
        "cyp_inducers": [],
        "transporter_substrates": ["OAT3", "OCT2"],
        "transporter_inhibitors": ["OAT1", "OAT3"],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "moderate", "cardiovascular": "moderate", "cns_stimulant": "low", "sedative": "none"},
        "dosing": {"common": 500, "unit": "mg", "frequency": "twice-daily", "timing": "empty stomach with water"},
        "half_life": "4-7 hours",
        "oral_bioavailability": "70-80%",
        "volume_of_distribution": "2.5 L/kg",
        "protein_binding": "30%",
        "clearance_routes": "Renal glomerular filtration and tubular secretion (70%)",
        "route": "oral",
        "logp": 0.3,
        "tpsa": 72.8,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "DNA Gyrase Subunit A Bacterial", "action": "inhibitor", "family": "Topoisomerase", "affinity_ki": 0.005},
            {"target": "DNA Topoisomerase 4 Bacterial", "action": "inhibitor", "family": "Topoisomerase", "affinity_ki": 0.01}
        ],
    },
    {
        "pattern": r"(?:cillin)$",
        "class_name": "Penicillin Beta-Lactam Antibiotic",
        "cyp_substrates": [],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OAT1", "OAT3", "PEPT1"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 500, "unit": "mg", "frequency": "twice-daily", "timing": "with food"},
        "half_life": "1-1.5 hours",
        "oral_bioavailability": "75-90%",
        "volume_of_distribution": "0.3 L/kg",
        "protein_binding": "20%",
        "clearance_routes": "Renal tubular secretion via OAT3 (70%)",
        "route": "oral",
        "logp": 0.9,
        "tpsa": 133.0,
        "is_narrow_therapeutic_index": False,
        "targets": [{"target": "Penicillin-Binding Protein 1A / Transpeptidase", "action": "inhibitor", "family": "Cell Wall Synthesis", "affinity_ki": 0.001}],
    },
    {
        "pattern": r"(?:sterone|steron|olone|androl|stan|dione)$",
        "class_name": "Androgenic Anabolic Steroid (AAS) / Nuclear Androgen Agonist",
        "cyp_substrates": ["CYP3A4", "CYP2C19", "CYP19A1"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp", "OATP2B1"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT2B17", "UGT2B15", "SULT2A1"],
        "organ_burdens": {"hepatic": "moderate", "renal": "low", "cardiovascular": "high", "cns_stimulant": "low", "sedative": "none"},
        "dosing": {"common": 20, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "4.5-8 days",
        "oral_bioavailability": "5-10% (oral unesterified) / 95% (parenteral ester)",
        "volume_of_distribution": "1.0 L/kg",
        "protein_binding": "98%",
        "clearance_routes": "Hepatic CYP/Phase II oxidation and glucuronidation (90%), Renal (10%)",
        "route": "parenteral",
        "logp": 3.3,
        "tpsa": 37.3,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 1.0},
            {"target": "Aromatase (CYP19A1)", "action": "substrate", "family": "Steroid Biosynthesis", "affinity_ki": 130.0},
            {"target": "5-Alpha Reductase Subtype 1 & 2", "action": "substrate", "family": "Steroid Biosynthesis", "affinity_ki": 2500.0},
            {"target": "Renal Erythropoietin (EPO) Signaling", "action": "agonist", "family": "Hematopoietic", "affinity_ki": 10.0},
            {"target": "Hepatic Angiotensinogen / RAAS Cascade", "action": "agonist", "family": "Renin-Angiotensin", "affinity_ki": 20.0}
        ],
    },
    {
        "pattern": r"(?:steride)$",
        "class_name": "Steroid 5-Alpha Reductase Inhibitor",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 1, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "6-8 hours",
        "oral_bioavailability": "65-80%",
        "volume_of_distribution": "0.7 L/kg",
        "protein_binding": "90%",
        "clearance_routes": "Hepatic CYP3A4 metabolism (60%), Fecal (57%), Renal (39%)",
        "route": "oral",
        "logp": 3.8,
        "tpsa": 41.1,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "5-Alpha Reductase Subtype 1 & 2", "action": "inhibitor", "family": "Steroid Biosynthesis", "affinity_ki": 5.0}
        ],
    },
    {
        "pattern": r"(?:trozole|rozole|mestane|anastrozole|letrozole|exemestane)$",
        "class_name": "Aromatase (CYP19A1) Inhibitor",
        "cyp_substrates": ["CYP3A4", "CYP2C8", "CYP2A6"],
        "cyp_inhibitors": ["CYP1A2", "CYP2C9", "CYP3A4"],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT1A4"],
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 1, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "40-50 hours",
        "oral_bioavailability": "85%",
        "volume_of_distribution": "1.0 L/kg",
        "protein_binding": "40%",
        "clearance_routes": "Hepatic metabolism (85%), Renal (11%)",
        "route": "oral",
        "logp": 2.2,
        "tpsa": 78.4,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Aromatase (CYP19A1)", "action": "inhibitor", "family": "Cytochrome P450 / Steroid Biosynthesis", "affinity_ki": 0.2}
        ],
    },
    {
        "pattern": r"(?:xifene|clomiphene|enclomiphene|tamoxifen|raloxifene)$",
        "class_name": "Selective Estrogen Receptor Modulator (SERM)",
        "cyp_substrates": ["CYP2D6", "CYP3A4", "CYP2C9"],
        "cyp_inhibitors": ["CYP2D6"],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp", "BCRP"],
        "transporter_inhibitors": ["P-gp"],
        "phase2_substrates": ["UGT1A8", "UGT1A10", "SULT1E1"],
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 20, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "5-7 days",
        "oral_bioavailability": "100%",
        "volume_of_distribution": "50-60 L/kg",
        "protein_binding": "99%",
        "clearance_routes": "Hepatic CYP2D6/CYP3A4 bioactivation to endoxifen and fecal excretion",
        "route": "oral",
        "logp": 4.6,
        "tpsa": 29.5,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Estrogen Receptor Alpha (ESR1 / ER-Alpha)", "action": "antagonist", "family": "Nuclear Receptor", "affinity_ki": 1.0},
            {"target": "Estrogen Receptor Beta (ESR2 / ER-Beta)", "action": "antagonist", "family": "Nuclear Receptor", "affinity_ki": 5.0},
            {"target": "Hypothalamic-Pituitary-Gonadal (HPG) Axis", "action": "agonist", "family": "Neuroendocrine", "affinity_ki": 10.0}
        ],
    },
    {
        "pattern": r"(?:estrol|estradiol|estrogen|ethinylestradiol)$",
        "class_name": "Estrogen Receptor Agonist / Bioidentical Steroid",
        "cyp_substrates": ["CYP3A4", "CYP1A2", "CYP2C9"],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["BCRP", "OATP1B1", "OATP2B1"],
        "transporter_inhibitors": [],
        "phase2_substrates": ["UGT1A1", "SULT1E1"],
        "organ_burdens": {"hepatic": "moderate", "renal": "none", "cardiovascular": "high", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 1, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "13-17 hours",
        "oral_bioavailability": "5-10% (oral first pass) / 100% (transdermal/parenteral)",
        "volume_of_distribution": "0.8 L/kg",
        "protein_binding": "98% (SHBG and Albumin)",
        "clearance_routes": "Hepatic metabolism and biliary/urinary excretion of sulfates and glucuronides",
        "route": "transdermal",
        "logp": 4.0,
        "tpsa": 40.5,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Estrogen Receptor Alpha (ESR1 / ER-Alpha)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 0.1},
            {"target": "Estrogen Receptor Beta (ESR2 / ER-Beta)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 0.3}
        ],
    },
    {
        "pattern": r"(?:sone|pred|dexamethasone|budesonide|cortisol|hydrocortisone)$",
        "class_name": "Glucocorticoid Receptor Agonist / Corticosteroid",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": [],
        "cyp_inducers": ["CYP3A4"],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": ["P-gp"],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "low", "cardiovascular": "moderate", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 10, "unit": "mg", "frequency": "daily", "timing": "morning with food"},
        "half_life": "2-4 hours",
        "oral_bioavailability": "80%",
        "volume_of_distribution": "1.0 L/kg",
        "protein_binding": "70-90%",
        "clearance_routes": "Hepatic reduction and glucuronidation (90%), Renal (10%)",
        "route": "oral",
        "logp": 1.6,
        "tpsa": 94.8,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Glucocorticoid Receptor (GR / NR3C1)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 2.0}
        ],
    },
    {
        "pattern": r"(?:st_johns_wort|stjohnswort|hypericum|hyperforin)$",
        "class_name": "Botanical PXR Inducer / Serotonergic Extract",
        "cyp_substrates": ["CYP3A4", "CYP2C9"],
        "cyp_inhibitors": [],
        "cyp_inducers": ["CYP3A4", "CYP2C9", "CYP2C19"],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": [],
        "transporter_inducers": ["P-gp"],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "none", "cns_stimulant": "low", "sedative": "none"},
        "dosing": {"common": 300, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "9-24 hours",
        "oral_bioavailability": "20%",
        "volume_of_distribution": "1.5 L/kg",
        "protein_binding": "90%",
        "clearance_routes": "Hepatic metabolism",
        "route": "oral",
        "logp": 4.2,
        "tpsa": 130.0,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Pregnane X Receptor (PXR / NR1I2 / CYP3A4 Inducer)", "action": "inducer", "family": "Nuclear Receptor", "gene_symbol": "NR1I2"},
            {"target": "Sodium-Dependent Serotonin Transporter (SERT / SLC6A4)", "action": "inhibitor", "family": "Monoamine Transporter", "gene_symbol": "SLC6A4"}
        ],
    },
    {
        "pattern": r"(?:piperine|bioperine)$",
        "class_name": "Botanical Bioenhancer Alkaloid",
        "cyp_substrates": ["CYP3A4"],
        "cyp_inhibitors": ["CYP3A4", "CYP2C9"],
        "cyp_inducers": [],
        "transporter_substrates": ["P-gp"],
        "transporter_inhibitors": ["P-gp"],
        "phase2_substrates": [],
        "phase2_inhibitors": ["UGT1A1"],
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 10, "unit": "mg", "frequency": "daily", "timing": "with meal"},
        "half_life": "2-4 hours",
        "oral_bioavailability": "90%",
        "volume_of_distribution": "1.0 L/kg",
        "protein_binding": "95%",
        "clearance_routes": "Hepatic CYP/UGT metabolism",
        "route": "oral",
        "logp": 3.7,
        "tpsa": 38.8,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Transient Receptor Potential Vanilloid 1 (TRPV1)", "action": "agonist", "family": "Ion Channel", "gene_symbol": "TRPV1"},
            {"target": "P-glycoprotein / ABCB1 Efflux Transporter (ABCB1)", "action": "inhibitor", "family": "ABC Transporter", "gene_symbol": "ABCB1"},
            {"target": "UDP-Glucuronosyltransferase 1A1 (UGT1A1)", "action": "inhibitor", "family": "Phase II Conjugation", "gene_symbol": "UGT1A1"}
        ],
    },
    {
        "pattern": r"(?:quercetin|egcg|green_tea_extract)$",
        "class_name": "Polyphenolic Flavonoid / COMT Inhibitor",
        "cyp_substrates": [],
        "cyp_inhibitors": ["CYP3A4", "CYP1A2"],
        "cyp_inducers": [],
        "transporter_substrates": ["OATP1B1"],
        "transporter_inhibitors": ["P-gp", "OATP1B1"],
        "phase2_substrates": ["SULT1A1"],
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 500, "unit": "mg", "frequency": "daily", "timing": "morning with food"},
        "half_life": "11-28 hours",
        "oral_bioavailability": "5-10%",
        "volume_of_distribution": "2.0 L/kg",
        "protein_binding": "98%",
        "clearance_routes": "Hepatic methylation and glucuronidation",
        "route": "oral",
        "logp": 1.8,
        "tpsa": 127.0,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Catechol-O-Methyltransferase (COMT)", "action": "inhibitor", "family": "Enzyme / Catecholamine Metabolism", "gene_symbol": "COMT"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense", "gene_symbol": "SLC7A11"}
        ],
    },
    {
        "pattern": r"(?:saw_palmetto|serenoa_repens|permixon)$",
        "class_name": "Botanical 5-Alpha Reductase Inhibitor",
        "cyp_substrates": [],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": [],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "low", "renal": "none", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 320, "unit": "mg", "frequency": "daily", "timing": "morning with food"},
        "half_life": "4-6 hours",
        "oral_bioavailability": "40%",
        "volume_of_distribution": "1.0 L/kg",
        "protein_binding": "90%",
        "clearance_routes": "Hepatic metabolism",
        "route": "oral",
        "logp": 4.5,
        "tpsa": 37.3,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "5-Alpha Reductase Subtype 1 & 2 (SRD5A1 / SRD5A2)", "action": "inhibitor", "family": "Steroid Biosynthesis", "gene_symbol": "SRD5A2"},
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "antagonist", "family": "Nuclear Receptor", "gene_symbol": "AR"}
        ],
    },
    {
        "pattern": r"(?:magnesium|zinc)$",
        "class_name": "Essential Dietary Mineral / GI Chelator",
        "cyp_substrates": [],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": [],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "none", "renal": "low", "cardiovascular": "none", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 200, "unit": "mg", "frequency": "daily", "timing": "evening"},
        "half_life": "24 hours",
        "oral_bioavailability": "30-50%",
        "volume_of_distribution": "1.0 L/kg",
        "protein_binding": "30%",
        "clearance_routes": "Renal excretion",
        "route": "oral",
        "logp": -1.0,
        "tpsa": 0.0,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Multivalent Cation Gastrointestinal Chelation Site", "action": "chelator", "family": "Physicochemical Interaction"}
        ],
    },
    {
        "stems": ["allicin", "allium", "garlic"],
        "class_name": "Organosulfur Botanical / Microbial Lyase Inhibitor",
        "cyp_substrates": [],
        "cyp_inhibitors": ["CYP2E1"],
        "cyp_inducers": [],
        "transporter_substrates": [],
        "transporter_inhibitors": ["P-GP"],
        "phase2_substrates": ["GST"],
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "low", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 10, "unit": "mg", "frequency": "daily", "timing": "with_meal"},
        "half_life": "1.0 hours",
        "oral_bioavailability": "80%",
        "volume_of_distribution": "0.8 L/kg",
        "protein_binding": "45%",
        "clearance_routes": "Hepatic metabolism & pulmonary/renal elimination",
        "route": "oral",
        "logp": 1.35,
        "tpsa": 42.5,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)", "action": "inhibitor", "family": "Gut Microbiome / Microbial Lyase", "inhibition_ic50": 0.05, "is_microbial": True},
            {"target": "HMG-CoA Reductase", "action": "inhibitor", "family": "Lipid Metabolism", "inhibition_ic50": 1.2},
            {"target": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)", "action": "agonist", "family": "Vascular Endothelium"},
            {"target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)", "action": "agonist", "family": "Antioxidant Defense"}
        ],
    },
    {
        "stems": ["carnitine", "alcar", "acetylcarnitine", "levocarnitine"],
        "class_name": "Dietary Nutrient / Mitochondrial Fatty Acid Shuttle",
        "cyp_substrates": [],
        "cyp_inhibitors": [],
        "cyp_inducers": [],
        "transporter_substrates": ["OCTN2"],
        "transporter_inhibitors": [],
        "phase2_substrates": [],
        "organ_burdens": {"hepatic": "none", "renal": "none", "cardiovascular": "low", "cns_stimulant": "none", "sedative": "none"},
        "dosing": {"common": 1000, "unit": "mg", "frequency": "daily", "timing": "morning"},
        "half_life": "15 hours",
        "oral_bioavailability": "15-20%",
        "volume_of_distribution": "0.65 L/kg",
        "protein_binding": "0%",
        "clearance_routes": "Renal tubular reabsorption & excretion; intestinal microbial cleavage",
        "route": "oral",
        "logp": -5.48,
        "tpsa": 60.4,
        "is_narrow_therapeutic_index": False,
        "targets": [
            {"target": "Carnitine Palmitoyltransferase 1A (CPT1A)", "action": "agonist", "family": "Mitochondrial Fatty Acid Oxidation", "affinity_ki": 10.0},
            {"target": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)", "action": "substrate", "family": "Gut Microbiome / Microbial Lyase", "is_microbial": True}
        ],
    },
]


class PharmacologyEnricher:
    """
    Infers structured pharmacology metadata from chemical nomenclature, USAN stems,
    ATC classifications, textual mechanisms, and target binding profiles.
    """

    @staticmethod
    def _match_usan_stem_rule(rule: Dict[str, Any], usan_stem: Optional[str], name_lower: str, key_lower: str) -> bool:
        """
        Deterministically match WHO INN / USAN stem rules using string suffixing and token equality
        without regex execution.
        """
        stems = rule.get("stems")
        if not stems:
            raw_pat = str(rule.get("pattern", ""))
            clean_stem = raw_pat.replace("(?:", "").replace(")$", "").replace("$", "").replace("^", "").replace("(", "").replace(")", "").strip()
            stems = [s.strip().lower() for s in clean_stem.split("|") if s.strip()]

        if usan_stem:
            u_clean = str(usan_stem).lower().strip()
            if any(u_clean == s or u_clean.endswith(s) for s in stems):
                return True

        for s in stems:
            if name_lower.endswith(s) or key_lower.endswith(s):
                return True

        tokens = name_lower.replace("-", " ").replace("_", " ").split()
        for s in stems:
            if any(tok.endswith(s) for tok in tokens):
                return True

        return False

    @classmethod
    def enrich_compound(cls, compound: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriches an existing compound record with inferred ADMET, CYP, Transporter,
        Phase II, and Receptor Target attributes.
        """
        enriched = dict(compound)

        name = str(compound.get("name") or compound.get("canonical_name") or compound.get("key") or "").strip()
        name_lower = name.lower()
        key = str(compound.get("key") or "").strip().lower()

        # Extract metadata sources
        meta = compound.get("metadata") or {}
        chembl_meta = meta.get("chembl") if isinstance(meta, dict) else {}
        if not isinstance(chembl_meta, dict):
            chembl_meta = {}

        usan_stem = str(chembl_meta.get("usan_stem") or "").strip().lower().replace("'", "").replace("-", "")
        atc_codes = chembl_meta.get("atc_codes") or []
        level_1_atc = str(chembl_meta.get("level_1_atc") or "").strip()
        mechanism_text = f"{str(compound.get('mechanism') or '')} {str(compound.get('drug_class') or '')} {name_lower} {key}".lower()

        # Extract existing properties
        matched_cyp_sub: Set[str] = set()
        matched_cyp_inh: Set[str] = set()
        matched_cyp_ind: Set[str] = set()
        matched_trans_sub: Set[str] = set()
        matched_trans_inh: Set[str] = set()
        matched_phase2_sub: Set[str] = set()
        matched_phase2_inh: Set[str] = set()
        matched_organ_burdens: Dict[str, str] = {
            "hepatic": "none",
            "renal": "none",
            "cardiovascular": "none",
            "cns_stimulant": "none",
            "sedative": "none",
        }
        matched_dosing: Dict[str, Any] = {}
        matched_targets: List[Dict[str, Any]] = []
        matched_half_life: Optional[str] = None
        matched_bioavail: Optional[str] = None
        matched_vd: Optional[str] = None
        matched_protein_binding: Optional[str] = None
        matched_clearance_routes: Optional[str] = None
        matched_route: Optional[str] = None
        matched_logp: Optional[float] = None
        matched_tpsa: Optional[float] = None
        is_nti = bool(compound.get("is_narrow_therapeutic_index", False))

        # 1. Match USAN Stems via Deterministic String Suffixing (Zero-Regex)
        for rule in USAN_STEM_RULES:
            if cls._match_usan_stem_rule(rule, usan_stem, name_lower, key.lower()):
                matched_cyp_sub.update(rule.get("cyp_substrates", []))
                matched_cyp_inh.update(rule.get("cyp_inhibitors", []))
                matched_cyp_ind.update(rule.get("cyp_inducers", []))
                matched_trans_sub.update(rule.get("transporter_substrates", []))
                matched_trans_inh.update(rule.get("transporter_inhibitors", []))
                matched_phase2_sub.update(rule.get("phase2_substrates", []))

                for org, lvl in rule.get("organ_burdens", {}).items():
                    if cls._severity_rank(lvl) > cls._severity_rank(matched_organ_burdens.get(org, "none")):
                        matched_organ_burdens[org] = lvl

                if not matched_dosing and rule.get("dosing"):
                    matched_dosing = dict(rule["dosing"])
                if not matched_half_life and rule.get("half_life"):
                    matched_half_life = rule["half_life"]
                if not matched_bioavail and rule.get("oral_bioavailability"):
                    matched_bioavail = rule["oral_bioavailability"]
                if not matched_vd and rule.get("volume_of_distribution"):
                    matched_vd = rule["volume_of_distribution"]
                if not matched_protein_binding and rule.get("protein_binding"):
                    matched_protein_binding = rule["protein_binding"]
                if not matched_clearance_routes and rule.get("clearance_routes"):
                    matched_clearance_routes = rule["clearance_routes"]
                if not matched_route and rule.get("route"):
                    matched_route = rule["route"]
                if matched_logp is None and rule.get("logp") is not None:
                    matched_logp = rule["logp"]
                if matched_tpsa is None and rule.get("tpsa") is not None:
                    matched_tpsa = rule["tpsa"]
                if rule.get("is_narrow_therapeutic_index"):
                    is_nti = True

                if not enriched.get("drug_class") and rule.get("class_name"):
                    enriched["drug_class"] = rule["class_name"]

                for t in rule.get("targets", []):
                    matched_targets.append(t)

        # 2. Match ATC Classification
        all_atcs = list(atc_codes)
        if level_1_atc:
            all_atcs.append(level_1_atc)

        for atc in all_atcs:
            atc_clean = str(atc).strip().upper()
            if atc_clean.startswith("N06B"):  # Psychostimulants
                matched_organ_burdens["cns_stimulant"] = "high"
                matched_organ_burdens["cardiovascular"] = "moderate"
                matched_cyp_sub.add("CYP2D6")
            elif atc_clean.startswith("N06A"):  # Antidepressants
                matched_organ_burdens["hepatic"] = "moderate"
                matched_cyp_sub.update(["CYP2D6", "CYP2C19"])
                matched_cyp_inh.add("CYP2D6")
            elif atc_clean.startswith("N05B") or atc_clean.startswith("N05C"):  # Anxiolytics / Sedatives
                matched_organ_burdens["sedative"] = "high"
                matched_cyp_sub.add("CYP3A4")
            elif atc_clean.startswith("N02A"):  # Opioids
                matched_organ_burdens["sedative"] = "high"
                matched_cyp_sub.update(["CYP3A4", "CYP2D6"])
                is_nti = True
            elif atc_clean.startswith("B01A"):  # Antithrombotic Agents (Anticoagulants/Antiplatelets)
                matched_organ_burdens["cardiovascular"] = "high"
                is_nti = True
            elif atc_clean.startswith("R03A") or atc_clean.startswith("R03C"):  # Adrenergics for systemic / inhalation use (Beta-2 Agonists)
                matched_organ_burdens["cardiovascular"] = "high"
                if cls._severity_rank(matched_organ_burdens["cns_stimulant"]) < cls._severity_rank("moderate"):
                    matched_organ_burdens["cns_stimulant"] = "moderate"
                matched_cyp_sub.update(["CYP2D6", "CYP3A4"])
            elif atc_clean.startswith("R03D"):  # Other systemic drugs for obstructive airway diseases (Xanthines)
                matched_organ_burdens["cardiovascular"] = "high"
                matched_organ_burdens["cns_stimulant"] = "high"
                matched_cyp_sub.add("CYP1A2")
            elif atc_clean.startswith("C01C"):  # Cardiac stimulants excluding cardiac glycosides (Adrenergic/Dopaminergic)
                matched_organ_burdens["cardiovascular"] = "high"
                if cls._severity_rank(matched_organ_burdens["cns_stimulant"]) < cls._severity_rank("moderate"):
                    matched_organ_burdens["cns_stimulant"] = "moderate"

        # 3. Mechanism Text Extraction
        if "serotonin" in mechanism_text or "5-ht" in mechanism_text or "ssri" in mechanism_text:
            matched_cyp_sub.add("CYP2D6")
            if "inhibitor" in mechanism_text or "reuptake" in mechanism_text:
                matched_cyp_inh.add("CYP2D6")

        if "gaba" in mechanism_text or "benzodiazepine" in mechanism_text:
            if cls._severity_rank(matched_organ_burdens["sedative"]) < cls._severity_rank("moderate"):
                matched_organ_burdens["sedative"] = "moderate"
            matched_cyp_sub.add("CYP3A4")

        if any(w in mechanism_text for w in ["dopamine", "amphetamine", "stimulant", "sympathomimetic", "norepinephrine"]):
            if "antagonist" not in mechanism_text and "blocker" not in mechanism_text:
                if cls._severity_rank(matched_organ_burdens["cns_stimulant"]) < cls._severity_rank("moderate"):
                    matched_organ_burdens["cns_stimulant"] = "moderate"

        # Direct Sympathomimetic & Ephedrine Class Extraction
        if any(w in mechanism_text for w in ["ephedrine", "pseudoephedrine", "synephrine", "sympathomimetic"]):
            if cls._severity_rank(matched_organ_burdens["cardiovascular"]) < cls._severity_rank("high"):
                matched_organ_burdens["cardiovascular"] = "high"
            if cls._severity_rank(matched_organ_burdens["cns_stimulant"]) < cls._severity_rank("high"):
                matched_organ_burdens["cns_stimulant"] = "high"

        # Adrenergic & Beta-Agonist Mechanism Extraction
        if any(w in mechanism_text for w in ["beta-2", "beta-1", "beta adrenergic", "adrb2", "adrb1", "adrenoreceptor agonist", "adrenergic receptor agonist", "bronchodilator"]):
            if "antagonist" not in mechanism_text and "blocker" not in mechanism_text and "inhibit" not in mechanism_text:
                if any(act in mechanism_text.split() or act in mechanism_text for act in ["agonist", "activator", "stimulator"]):
                    if cls._severity_rank(matched_organ_burdens["cardiovascular"]) < cls._severity_rank("high"):
                        matched_organ_burdens["cardiovascular"] = "high"
                    if cls._severity_rank(matched_organ_burdens["cns_stimulant"]) < cls._severity_rank("moderate"):
                        matched_organ_burdens["cns_stimulant"] = "moderate"
                    matched_cyp_sub.update(["CYP2D6", "CYP3A4"])

        # Alpha-2 Antagonist & Adenosine Antagonist Mechanism Extraction
        if ("alpha-2" in mechanism_text and any(act in mechanism_text for act in ["antagonist", "blocker", "inhibition"])) or any(w in mechanism_text for w in ["yohimbine", "rauwolscine"]):
            if cls._severity_rank(matched_organ_burdens["cardiovascular"]) < cls._severity_rank("high"):
                matched_organ_burdens["cardiovascular"] = "high"
            if cls._severity_rank(matched_organ_burdens["cns_stimulant"]) < cls._severity_rank("high"):
                matched_organ_burdens["cns_stimulant"] = "high"

        if ("adenosine" in mechanism_text and any(act in mechanism_text for act in ["antagonist", "blocker"])) or any(w in mechanism_text for w in ["caffeine", "methylxanthine", "theophylline"]):
            if cls._severity_rank(matched_organ_burdens["cardiovascular"]) < cls._severity_rank("moderate"):
                matched_organ_burdens["cardiovascular"] = "moderate"
            if cls._severity_rank(matched_organ_burdens["cns_stimulant"]) < cls._severity_rank("high"):
                matched_organ_burdens["cns_stimulant"] = "high"

        # CYP Regex Match
        for cyp_match in re.findall(r"cyp\s*([0-9][a-z][0-9]+)", mechanism_text, re.IGNORECASE):
            cyp_name = f"CYP{cyp_match.upper()}"
            if "inhibitor" in mechanism_text or "inhibit" in mechanism_text:
                matched_cyp_inh.add(cyp_name)
            elif "inducer" in mechanism_text or "induce" in mechanism_text:
                matched_cyp_ind.add(cyp_name)
            else:
                matched_cyp_sub.add(cyp_name)

        # 4. Merge with Existing Record Data
        def _merge_named_items(existing_items: Any, matched_set: Set[str], key_name: str) -> List[Any]:
            res = []
            seen = set()
            if isinstance(existing_items, (list, set, tuple)):
                for it in existing_items:
                    if isinstance(it, dict):
                        val = str(it.get(key_name) or it.get("name") or it.get("enzyme") or it.get("transporter") or "")
                        if val:
                            seen.add(val.upper())
                        res.append(it)
                    elif isinstance(it, str):
                        if it.upper() not in seen:
                            seen.add(it.upper())
                            res.append(it)
            elif isinstance(existing_items, str):
                seen.add(existing_items.upper())
                res.append(existing_items)

            for m in matched_set:
                if m.upper() not in seen:
                    seen.add(m.upper())
                    res.append(m)
            return sorted(res, key=lambda x: (x if isinstance(x, str) else str(x.get(key_name) or x.get('name') or '')))

        existing_cyp = compound.get("cyp_enzymes") or {}
        if not isinstance(existing_cyp, dict):
            existing_cyp = {}

        enriched["cyp_enzymes"] = {
            "substrates": _merge_named_items(existing_cyp.get("substrates"), matched_cyp_sub, "enzyme"),
            "inhibitors": _merge_named_items(existing_cyp.get("inhibitors"), matched_cyp_inh, "enzyme"),
            "inducers": _merge_named_items(existing_cyp.get("inducers"), matched_cyp_ind, "enzyme"),
        }

        existing_trans = compound.get("transporters") or {}
        if not isinstance(existing_trans, dict):
            existing_trans = {}
        enriched["transporters"] = {
            "substrates": _merge_named_items(existing_trans.get("substrates"), matched_trans_sub, "transporter"),
            "inhibitors": _merge_named_items(existing_trans.get("inhibitors"), matched_trans_inh, "transporter"),
            "inducers": _merge_named_items(existing_trans.get("inducers"), set(), "transporter"),
        }

        existing_phase2 = compound.get("phase2_enzymes") or {}
        if not isinstance(existing_phase2, dict):
            existing_phase2 = {}
        enriched["phase2_enzymes"] = {
            "substrates": _merge_named_items(existing_phase2.get("substrates"), matched_phase2_sub, "enzyme"),
            "inhibitors": _merge_named_items(existing_phase2.get("inhibitors"), matched_phase2_inh, "enzyme"),
            "inducers": _merge_named_items(existing_phase2.get("inducers"), set(), "enzyme"),
        }

        existing_organs = compound.get("organ_burdens") or {}
        if not isinstance(existing_organs, dict):
            existing_organs = {}

        final_organs = {}
        for org in ["hepatic", "renal", "cardiovascular", "cns_stimulant", "sedative"]:
            cur_lvl = existing_organs.get(org, "none")
            match_lvl = matched_organ_burdens.get(org, "none")
            final_organs[org] = cur_lvl if cls._severity_rank(cur_lvl) >= cls._severity_rank(match_lvl) else match_lvl
        enriched["organ_burdens"] = final_organs

        # ADMET Properties
        if not enriched.get("half_life") and matched_half_life:
            enriched["half_life"] = matched_half_life
        if not enriched.get("oral_bioavailability") and matched_bioavail:
            enriched["oral_bioavailability"] = matched_bioavail
        if not enriched.get("volume_of_distribution") and matched_vd:
            enriched["volume_of_distribution"] = matched_vd
        if not enriched.get("protein_binding") and matched_protein_binding:
            enriched["protein_binding"] = matched_protein_binding
        if not enriched.get("clearance_routes") and matched_clearance_routes:
            enriched["clearance_routes"] = matched_clearance_routes
        if not enriched.get("route_of_administration") and matched_route:
            enriched["route_of_administration"] = matched_route
        if enriched.get("logp") is None and matched_logp is not None:
            enriched["logp"] = matched_logp
        if enriched.get("tpsa") is None and matched_tpsa is not None:
            enriched["tpsa"] = matched_tpsa

        enriched["is_narrow_therapeutic_index"] = is_nti

        # Receptor Targets Merging
        from app.services.graph_service import (
            _normalize_target_node_id,
            is_steroidal_androgen,
            is_aromatizable_androgen,
            is_5alpha_reductase_substrate,
        )
        existing_targets = compound.get("receptor_targets") or []
        if not isinstance(existing_targets, list):
            existing_targets = []

        is_androgen = is_steroidal_androgen(compound) or "androgen" in str(compound.get("drug_class", "")).lower()
        is_arom = is_aromatizable_androgen(compound) if is_androgen else True
        is_5ar = is_5alpha_reductase_substrate(compound) if is_androgen else True

        # Filter out CYP19A1 from cyp substrates if chemically non-aromatizable
        if is_androgen and not is_arom:
            enriched["cyp_enzymes"]["substrates"] = [s for s in enriched["cyp_enzymes"]["substrates"] if s.upper() != "CYP19A1"]

        combined_targets = list(existing_targets)
        for t in matched_targets:
            t_raw = str(t.get("target") or "").lower()
            t_action = str(t.get("action") or "").lower()

            if is_androgen and not is_arom:
                if any(w in t_raw for w in ["aromatase", "cyp19", "cyp19a1", "estrogen receptor", "esr1", "esr2"]) and "substrate" in t_action:
                    continue

            if is_androgen and not is_5ar:
                if any(w in t_raw for w in ["5-alpha reductase", "srd5a", "5ar"]) and "substrate" in t_action:
                    continue

            t_norm = _normalize_target_node_id(t.get("target"))
            if not any(
                isinstance(existing, dict) and _normalize_target_node_id(existing.get("target")) == t_norm
                for existing in combined_targets
            ):
                combined_targets.append(t)

        # Ensure any pre-existing false aromatase/5ar substrate targets are removed for non-aromatizable compounds
        if is_androgen and not is_arom:
            combined_targets = [
                t for t in combined_targets
                if not (isinstance(t, dict) and any(w in str(t.get("target", "")).lower() for w in ["aromatase", "cyp19", "cyp19a1"]) and "substrate" in str(t.get("action", "")).lower())
            ]
        # Ensure aromatizable androgens have action="substrate" for aromatase targets and 5AR substrates have action="substrate"
        is_ai = any(w in str(compound.get("drug_class", "")).lower() or w in str(compound.get("name", "")).lower() for w in ["aromatase inhibitor", "ai", "anastrozole", "letrozole", "exemestane"])
        is_5ari = any(w in str(compound.get("drug_class", "")).lower() or w in str(compound.get("name", "")).lower() for w in ["5-alpha reductase inhibitor", "5ari", "finasteride", "dutasteride"])
        if is_androgen and is_arom and not is_ai:
            for t in combined_targets:
                if isinstance(t, dict) and any(w in str(t.get("target", "")).lower() for w in ["aromatase", "cyp19", "cyp19a1"]):
                    t["action"] = "substrate"
                    t["family"] = "Steroid Biosynthesis"
        if is_androgen and is_5ar and not is_5ari:
            for t in combined_targets:
                if isinstance(t, dict) and any(w in str(t.get("target", "")).lower() for w in ["5-alpha reductase", "srd5a", "5ar"]):
                    t["action"] = "substrate"
                    t["family"] = "Steroid Biosynthesis"

        enriched["receptor_targets"] = combined_targets

        # Dosing
        if not enriched.get("dosing"):
            if matched_dosing:
                enriched["dosing"] = matched_dosing
            else:
                enriched["dosing"] = {"common": 100, "unit": "mg", "frequency": "daily", "timing": "morning"}

        # Structured Quantitative PK/PD Benchmark Enrichment
        from app.services.pkpd_enricher import PKPDEnricher
        enriched = PKPDEnricher().enrich_compound_pkpd(enriched)

        return enriched

    @staticmethod
    def _severity_rank(level: str | None) -> int:
        mapping = {"none": 0, "low": 1, "moderate": 2, "high": 3, "severe": 4}
        return mapping.get(str(level or "none").lower(), 0)
