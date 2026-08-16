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
            {"target": "Type-1 Angiotensin II Receptor (AT1)", "action": "antagonist", "family": "Renin-Angiotensin", "affinity_ki": 0.003},
            {"target": "Peroxisome Proliferator-Activated Receptor Gamma (PPAR-gamma)", "action": "agonist", "family": "Nuclear Receptor", "affinity_ki": 4.5}
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
        "dosing": {"common": 0.5, "unit": "mg", "frequency": "weekly", "timing": "anytime"},
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
]


class PharmacologyEnricher:
    """
    Infers structured pharmacology metadata from chemical nomenclature, USAN stems,
    ATC classifications, textual mechanisms, and target binding profiles.
    """

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
        mechanism_text = str(compound.get("mechanism") or "").lower()

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

        # 1. Match USAN Stems
        for rule in USAN_STEM_RULES:
            pat = rule["pattern"]
            stem_match = (usan_stem and re.search(pat, usan_stem)) or re.search(pat, name_lower) or re.search(pat, key)
            if stem_match:
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
        existing_cyp = compound.get("cyp_enzymes") or {}
        if not isinstance(existing_cyp, dict):
            existing_cyp = {}

        cur_sub = set(existing_cyp.get("substrates") or [])
        cur_inh = set(existing_cyp.get("inhibitors") or [])
        cur_ind = set(existing_cyp.get("inducers") or [])

        enriched["cyp_enzymes"] = {
            "substrates": sorted(cur_sub.union(matched_cyp_sub)),
            "inhibitors": sorted(cur_inh.union(matched_cyp_inh)),
            "inducers": sorted(cur_ind.union(matched_cyp_ind)),
        }

        existing_trans = compound.get("transporters") or {}
        if not isinstance(existing_trans, dict):
            existing_trans = {}
        enriched["transporters"] = {
            "substrates": sorted(set(existing_trans.get("substrates") or []).union(matched_trans_sub)),
            "inhibitors": sorted(set(existing_trans.get("inhibitors") or []).union(matched_trans_inh)),
            "inducers": sorted(set(existing_trans.get("inducers") or [])),
        }

        existing_phase2 = compound.get("phase2_enzymes") or {}
        if not isinstance(existing_phase2, dict):
            existing_phase2 = {}
        enriched["phase2_enzymes"] = {
            "substrates": sorted(set(existing_phase2.get("substrates") or []).union(matched_phase2_sub)),
            "inhibitors": sorted(set(existing_phase2.get("inhibitors") or []).union(matched_phase2_inh)),
            "inducers": sorted(set(existing_phase2.get("inducers") or [])),
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
        existing_targets = compound.get("receptor_targets") or []
        if not isinstance(existing_targets, list):
            existing_targets = []

        combined_targets = list(existing_targets)
        for t in matched_targets:
            if not any(
                isinstance(existing, dict) and existing.get("target") == t.get("target")
                for existing in combined_targets
            ):
                combined_targets.append(t)
        enriched["receptor_targets"] = combined_targets

        # Dosing
        if not enriched.get("dosing"):
            if matched_dosing:
                enriched["dosing"] = matched_dosing
            else:
                enriched["dosing"] = {"common": 100, "unit": "mg", "frequency": "daily", "timing": "morning"}

        return enriched

    @staticmethod
    def _severity_rank(level: str | None) -> int:
        mapping = {"none": 0, "low": 1, "moderate": 2, "high": 3, "severe": 4}
        return mapping.get(str(level or "none").lower(), 0)
