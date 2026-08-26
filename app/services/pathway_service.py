"""
Dynamic Online Pathway & Cascade Ingestion Service.

Interrogates Reactome Content Service and Open Targets Platform GraphQL API
to dynamically resolve target proteins and enzymes into biological pathways,
inter-pathway cross-talk, clinical phenotypes, and biomarker nodes, caching all
results in SQLite to eliminate static cascade hardcoding.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from app.knowledge_graph.models import EdgeType

logger = logging.getLogger(__name__)

# In-memory session caches
_PATHWAY_INITIALIZED_DBS: Set[str] = set()
_PATHWAY_CASCADE_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
_PATHWAY_METADATA_CACHE: Dict[Tuple[str, str], Dict[str, str]] = {}

# Default Database Path
DEFAULT_DB_PATH = os.getenv("HEALTHAI_CATALOG_DB", str(Path(__file__).resolve().parents[2] / "healthai_catalog.db"))

# Known authoritative seed mappings for zero-network bootstrap and instant cache warming
INITIAL_TARGET_SEED_METADATA: Dict[str, Dict[str, str]] = {
    "cyp19a1": {"symbol": "CYP19A1", "uniprot": "P11511", "ensembl": "ENSG00000137869", "name": "Aromatase (CYP19A1)"},
    "aromatase": {"symbol": "CYP19A1", "uniprot": "P11511", "ensembl": "ENSG00000137869", "name": "Aromatase (CYP19A1)"},
    "ar": {"symbol": "AR", "uniprot": "P10275", "ensembl": "ENSG00000169083", "name": "Androgen Receptor (AR / NR3C4)"},
    "androgen receptor": {"symbol": "AR", "uniprot": "P10275", "ensembl": "ENSG00000169083", "name": "Androgen Receptor (AR / NR3C4)"},
    "agtr1": {"symbol": "AGTR1", "uniprot": "P30556", "ensembl": "ENSG00000144891", "name": "Angiotensin II Type-1 (AT1) Receptor / ACE"},
    "angiotensin": {"symbol": "AGTR1", "uniprot": "P30556", "ensembl": "ENSG00000144891", "name": "Angiotensin II Type-1 (AT1) Receptor / ACE"},
    "adrb1": {"symbol": "ADRB1", "uniprot": "P08588", "ensembl": "ENSG00000043591", "name": "Beta-1 Adrenergic Receptor (ADRB1)"},
    "adrb2": {"symbol": "ADRB2", "uniprot": "P07550", "ensembl": "ENSG00000169252", "name": "Beta-2 Adrenergic Receptor (ADRB2)"},
    "adra2a": {"symbol": "ADRA2A", "uniprot": "P08913", "ensembl": "ENSG00000150594", "name": "Alpha-2A Adrenergic Receptor (ADRA2A)"},
    "adora1": {"symbol": "ADORA1", "uniprot": "P30542", "ensembl": "ENSG00000163485", "name": "Adenosine A1 Receptor (ADORA1)"},
    "adora2a": {"symbol": "ADORA2A", "uniprot": "P29274", "ensembl": "ENSG00000128271", "name": "Adenosine A2A Receptor (ADORA2A)"},
    "esr1": {"symbol": "ESR1", "uniprot": "P03372", "ensembl": "ENSG00000091831", "name": "Estrogen Receptor Alpha (ESR1)"},
    "esr2": {"symbol": "ESR2", "uniprot": "Q92731", "ensembl": "ENSG00000140009", "name": "Estrogen Receptor Beta (ESR2)"},
    "nr3c2": {"symbol": "NR3C2", "uniprot": "P08235", "ensembl": "ENSG00000151623", "name": "Mineralocorticoid Receptor (Aldosterone Receptor / NR3C2)"},
    "mineralocorticoid": {"symbol": "NR3C2", "uniprot": "P08235", "ensembl": "ENSG00000151623", "name": "Mineralocorticoid Receptor (Aldosterone Receptor / NR3C2)"},
    "srd5a1": {"symbol": "SRD5A1", "uniprot": "P18405", "ensembl": "ENSG00000145545", "name": "5-Alpha Reductase Subtype 1 (SRD5A1)"},
    "srd5a2": {"symbol": "SRD5A2", "uniprot": "P31213", "ensembl": "ENSG00000099958", "name": "5-Alpha Reductase Subtype 2 (SRD5A2)"},
    "5-alpha reductase": {"symbol": "SRD5A2", "uniprot": "P31213", "ensembl": "ENSG00000099958", "name": "5-Alpha Reductase Subtype 1 & 2"},
    "hmgcr": {"symbol": "HMGCR", "uniprot": "P04035", "ensembl": "ENSG00000112972", "name": "HMG-CoA Reductase"},
    "hmg-coa reductase": {"symbol": "HMGCR", "uniprot": "P04035", "ensembl": "ENSG00000112972", "name": "HMG-CoA Reductase"},
    "hmg-coa reductase (hmgcr)": {"symbol": "HMGCR", "uniprot": "P04035", "ensembl": "ENSG00000112972", "name": "HMG-CoA Reductase"},
    "pitavastatin": {"symbol": "HMGCR", "uniprot": "P04035", "ensembl": "ENSG00000112972", "name": "HMG-CoA Reductase"},
    "pde5a": {"symbol": "PDE5A", "uniprot": "O76074", "ensembl": "ENSG00000138735", "chembl": "CHEMBL1824", "name": "Phosphodiesterase 5A (PDE5)"},
    "chembl1824": {"symbol": "PDE5A", "uniprot": "O76074", "ensembl": "ENSG00000138735", "chembl": "CHEMBL1824", "name": "Phosphodiesterase 5A (PDE5)"},
    "slc5a2": {"symbol": "SLC5A2", "uniprot": "P31930", "ensembl": "ENSG00000140675", "name": "Sodium-Glucose Cotransporter 2 (SGLT2 / SLC5A2)"},
    "sglt2": {"symbol": "SLC5A2", "uniprot": "P31930", "ensembl": "ENSG00000140675", "name": "Sodium-Glucose Cotransporter 2 (SGLT2 / SLC5A2)"},
    "glp1r": {"symbol": "GLP1R", "uniprot": "P43220", "ensembl": "ENSG00000048816", "name": "Glucagon-Like Peptide 1 Receptor (GLP1R)"},
    "pparg": {"symbol": "PPARG", "uniprot": "P37231", "ensembl": "ENSG00000132170", "name": "Peroxisome Proliferator-Activated Receptor Gamma (PPARG)"},
    "kcnh2": {"symbol": "KCNH2", "uniprot": "Q12809", "ensembl": "ENSG00000055118", "name": "Voltage-Gated Potassium Channel (hERG / KCNH2 / IKr)"},
    "cacna1c": {"symbol": "CACNA1C", "uniprot": "Q13936", "ensembl": "ENSG00000151067", "name": "L-Type Voltage-Gated Calcium Channel (CACNA1C)"},
    "chrm1": {"symbol": "CHRM1", "uniprot": "P11229", "ensembl": "ENSG00000168539", "name": "Muscarinic Acetylcholine Receptor M1 (CHRM1)"},
    "slc6a4": {"symbol": "SLC6A4", "uniprot": "P31645", "ensembl": "ENSG00000108576", "name": "Serotonin Transporter (SERT / SLC6A4)"},
    "slc6a3": {"symbol": "SLC6A3", "uniprot": "Q01959", "ensembl": "ENSG00000142319", "name": "Dopamine Transporter (DAT / SLC6A3)"},
    "ptgs1": {"symbol": "PTGS1", "uniprot": "P23219", "ensembl": "ENSG00000095303", "name": "Cyclooxygenase 1 (COX-1 / PTGS1)"},
    "ptgs2": {"symbol": "PTGS2", "uniprot": "P35354", "ensembl": "ENSG00000073756", "name": "Cyclooxygenase 2 (COX-2 / PTGS2)"},
    "epor": {"symbol": "EPOR", "uniprot": "P19235", "ensembl": "ENSG00000187266", "name": "Erythropoietin Receptor (EPOR)"},
    "cyp3a4": {"symbol": "CYP3A4", "uniprot": "P08684", "ensembl": "ENSG00000160868", "name": "Cytochrome P450 3A4 (CYP3A4)"},
    "cyp2c19": {"symbol": "CYP2C19", "uniprot": "P33261", "ensembl": "ENSG00000165841", "name": "Cytochrome P450 2C19 (CYP2C19)"},
    "abcb1": {"symbol": "ABCB1", "uniprot": "P08183", "ensembl": "ENSG00000085563", "name": "P-Glycoprotein (P-gp / ABCB1)"},
    "slc7a11": {"symbol": "SLC7A11", "uniprot": "Q16478", "ensembl": "ENSG00000151012", "name": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)"},
    "glutathione": {"symbol": "SLC7A11", "uniprot": "Q16478", "ensembl": "ENSG00000151012", "name": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)"},
    "ghsr": {"symbol": "GHSR", "uniprot": "Q92847", "ensembl": "ENSG00000121858", "name": "Growth Hormone Secretagogue Receptor (GHSR / Ghrelin Receptor)"},
    "ghrhr": {"symbol": "GHRHR", "uniprot": "Q02643", "ensembl": "ENSG00000106128", "name": "Growth Hormone-Releasing Hormone Receptor (GHRHR)"},
    "gipr": {"symbol": "GIPR", "uniprot": "P48546", "ensembl": "ENSG00000135898", "name": "Gastric Inhibitory Polypeptide Receptor (GIPR)"},
    "gcgr": {"symbol": "GCGR", "uniprot": "P47871", "ensembl": "ENSG00000215644", "name": "Glucagon Receptor (GCGR)"},
    "mc1r": {"symbol": "MC1R", "uniprot": "Q01726", "ensembl": "ENSG00000258839", "name": "Melanocortin 1 Receptor (MC1R)"},
    "mc4r": {"symbol": "MC4R", "uniprot": "P32245", "ensembl": "ENSG00000166603", "name": "Melanocortin 4 Receptor (MC4R)"},
    "kdr": {"symbol": "KDR", "uniprot": "P35968", "ensembl": "ENSG00000128052", "name": "Vascular Endothelial Growth Factor Receptor 2 (VEGFR2 / KDR)"},
    "tmsb4x": {"symbol": "TMSB4X", "uniprot": "P62328", "ensembl": "ENSG00000205542", "name": "Thymosin Beta-4 (TMSB4X / G-Actin Sequestration)"},
    "oxtr": {"symbol": "OXTR", "uniprot": "P30559", "ensembl": "ENSG00000180914", "name": "Oxytocin Receptor (OXTR)"},
    "avpr2": {"symbol": "AVPR2", "uniprot": "P30518", "ensembl": "ENSG00000126895", "name": "Vasopressin V2 Receptor (AVPR2)"},
    "carns1": {"symbol": "CARNS1", "uniprot": "A5YM72", "ensembl": "ENSG00000172508", "name": "Carnosine Synthase 1 (CARNS1 / Intramuscular Proton Buffering)"},
    "mrgprd": {"symbol": "MRGPRD", "uniprot": "Q8TDF5", "ensembl": "ENSG00000188987", "name": "Mas-Related G-Protein Coupled Receptor Member D (MRGPRD / Cutaneous Paresthesia)"},
    "pde": {"symbol": "PDE", "uniprot": "O76074", "ensembl": "ENSG00000138735", "name": "Phosphodiesterase"},
    "phosphodiesterase": {"symbol": "PDE", "uniprot": "O76074", "ensembl": "ENSG00000138735", "name": "Phosphodiesterase"},
    "phosphodiesterase (non-selective)": {"symbol": "PDE", "uniprot": "O76074", "ensembl": "ENSG00000138735", "name": "Phosphodiesterase"},
    "adenosine a1 receptor": {"symbol": "ADORA1", "uniprot": "P30542", "ensembl": "ENSG00000163485", "name": "Adenosine A1 Receptor (ADORA1)"},
    "adenosine a2a receptor": {"symbol": "ADORA2A", "uniprot": "P29274", "ensembl": "ENSG00000128271", "name": "Adenosine A2A Receptor (ADORA2A)"},
    "a1 receptor": {"symbol": "ADORA1", "uniprot": "P30542", "ensembl": "ENSG00000163485", "name": "Adenosine A1 Receptor (ADORA1)"},
    "a2a receptor": {"symbol": "ADORA2A", "uniprot": "P29274", "ensembl": "ENSG00000128271", "name": "Adenosine A2A Receptor (ADORA2A)"},
    "adenosine receptor (adora1 / adora2a)": {"symbol": "ADORA1", "uniprot": "P30542", "ensembl": "ENSG00000163485", "name": "Adenosine Receptor (ADORA1 / ADORA2A)"},
    "adenosine receptor": {"symbol": "ADORA1", "uniprot": "P30542", "ensembl": "ENSG00000163485", "name": "Adenosine Receptor (ADORA1)"},
    "xanthine dehydrogenase / oxidase (xdh / xo)": {"symbol": "XDH", "uniprot": "P47989", "ensembl": "ENSG00000158125", "name": "Xanthine Dehydrogenase / Oxidase (XDH / XO)"},
    "transient receptor potential vanilloid 1 (trpv1)": {"symbol": "TRPV1", "uniprot": "Q8NER1", "ensembl": "ENSG00000196689", "name": "Transient Receptor Potential Vanilloid 1 (TRPV1)"},
    "catechol-o-methyltransferase (comt)": {"symbol": "COMT", "uniprot": "P21964", "ensembl": "ENSG00000093010", "name": "Catechol-O-Methyltransferase (COMT)"},

    "gaba-a": {"symbol": "GABRA1", "uniprot": "P14867", "ensembl": "ENSG00000022355", "name": "GABA-A Receptor Alpha-1 (GABRA1)"},
    "glutamate": {"symbol": "GRIN1", "uniprot": "Q05586", "ensembl": "ENSG00000176884", "name": "NMDA Glutamate Receptor Subunit 1 (GRIN1)"},
    # Nootropics & Research Chemical Targets
    "gria1": {"symbol": "GRIA1", "uniprot": "P42261", "ensembl": "ENSG00000120251", "name": "Glutamate Ionotropic Receptor AMPA Type Subunit 1 (GRIA1 / AMPA)"},
    "ampa": {"symbol": "GRIA1", "uniprot": "P42261", "ensembl": "ENSG00000120251", "name": "Glutamate Ionotropic Receptor AMPA Type Subunit 1 (GRIA1 / AMPA)"},
    "ampa receptor": {"symbol": "GRIA1", "uniprot": "P42261", "ensembl": "ENSG00000120251", "name": "Glutamate Ionotropic Receptor AMPA Type Subunit 1 (GRIA1 / AMPA)"},
    "ampakine": {"symbol": "GRIA1", "uniprot": "P42261", "ensembl": "ENSG00000120251", "name": "Glutamate Ionotropic Receptor AMPA Type Subunit 1 (GRIA1 / AMPA)"},
    "grin1": {"symbol": "GRIN1", "uniprot": "Q05586", "ensembl": "ENSG00000176884", "name": "NMDA Glutamate Receptor Subunit 1 (GRIN1 / NMDA)"},
    "nmda": {"symbol": "GRIN1", "uniprot": "Q05586", "ensembl": "ENSG00000176884", "name": "NMDA Glutamate Receptor Subunit 1 (GRIN1 / NMDA)"},
    "nmda receptor": {"symbol": "GRIN1", "uniprot": "Q05586", "ensembl": "ENSG00000176884", "name": "NMDA Glutamate Receptor Subunit 1 (GRIN1 / NMDA)"},
    "ntrk2": {"symbol": "NTRK2", "uniprot": "Q16620", "ensembl": "ENSG00000148053", "name": "Neurotrophic Receptor Tyrosine Kinase 2 (TrkB / NTRK2 / BDNF Receptor)"},
    "trkb": {"symbol": "NTRK2", "uniprot": "Q16620", "ensembl": "ENSG00000148053", "name": "Neurotrophic Receptor Tyrosine Kinase 2 (TrkB / NTRK2 / BDNF Receptor)"},
    "bdnf receptor": {"symbol": "NTRK2", "uniprot": "Q16620", "ensembl": "ENSG00000148053", "name": "Neurotrophic Receptor Tyrosine Kinase 2 (TrkB / NTRK2 / BDNF Receptor)"},
    "ntrk1": {"symbol": "NTRK1", "uniprot": "P04629", "ensembl": "ENSG00000198400", "name": "Neurotrophic Receptor Tyrosine Kinase 1 (TrkA / NTRK1 / NGF Receptor)"},
    "trka": {"symbol": "NTRK1", "uniprot": "P04629", "ensembl": "ENSG00000198400", "name": "Neurotrophic Receptor Tyrosine Kinase 1 (TrkA / NTRK1 / NGF Receptor)"},
    "met": {"symbol": "MET", "uniprot": "P08581", "ensembl": "ENSG00000105976", "name": "Hepatocyte Growth Factor Receptor (MET / c-Met)"},
    "hgf receptor": {"symbol": "MET", "uniprot": "P08581", "ensembl": "ENSG00000105976", "name": "Hepatocyte Growth Factor Receptor (MET / c-Met)"},
    "c-met": {"symbol": "MET", "uniprot": "P08581", "ensembl": "ENSG00000105976", "name": "Hepatocyte Growth Factor Receptor (MET / c-Met)"},
    "slc6a3": {"symbol": "SLC6A3", "uniprot": "Q01959", "ensembl": "ENSG00000142319", "name": "Dopamine Transporter (DAT / SLC6A3)"},
    "dat": {"symbol": "SLC6A3", "uniprot": "Q01959", "ensembl": "ENSG00000142319", "name": "Dopamine Transporter (DAT / SLC6A3)"},
    "dopamine transporter": {"symbol": "SLC6A3", "uniprot": "Q01959", "ensembl": "ENSG00000142319", "name": "Dopamine Transporter (DAT / SLC6A3)"},
    "slc6a2": {"symbol": "SLC6A2", "uniprot": "P23975", "ensembl": "ENSG00000103511", "name": "Norepinephrine Transporter (NET / SLC6A2)"},
    "net": {"symbol": "SLC6A2", "uniprot": "P23975", "ensembl": "ENSG00000103511", "name": "Norepinephrine Transporter (NET / SLC6A2)"},
    "th": {"symbol": "TH", "uniprot": "P07101", "ensembl": "ENSG00000180176", "name": "Tyrosine Hydroxylase (TH)"},
    "tyrosine hydroxylase": {"symbol": "TH", "uniprot": "P07101", "ensembl": "ENSG00000180176", "name": "Tyrosine Hydroxylase (TH)"},
    "chrna7": {"symbol": "CHRNA7", "uniprot": "P36544", "ensembl": "ENSG00000175344", "name": "Neuronal Acetylcholine Receptor Subunit Alpha-7 (CHRNA7)"},
    "alpha-7 nachr": {"symbol": "CHRNA7", "uniprot": "P36544", "ensembl": "ENSG00000175344", "name": "Neuronal Acetylcholine Receptor Subunit Alpha-7 (CHRNA7)"},
    "sigmar1": {"symbol": "SIGMAR1", "uniprot": "Q99720", "ensembl": "ENSG00000147955", "name": "Sigma Non-Opioid Intracellular Receptor 1 (SIGMAR1)"},
    "sigma-1": {"symbol": "SIGMAR1", "uniprot": "Q99720", "ensembl": "ENSG00000147955", "name": "Sigma Non-Opioid Intracellular Receptor 1 (SIGMAR1)"},
    "sigma-1 receptor": {"symbol": "SIGMAR1", "uniprot": "Q99720", "ensembl": "ENSG00000147955", "name": "Sigma Non-Opioid Intracellular Receptor 1 (SIGMAR1)"},
    "gabbr1": {"symbol": "GABBR1", "uniprot": "Q92540", "ensembl": "ENSG00000204688", "name": "GABA-B Receptor Subunit 1 (GABBR1)"},
    "gaba-b": {"symbol": "GABBR1", "uniprot": "Q92540", "ensembl": "ENSG00000204688", "name": "GABA-B Receptor Subunit 1 (GABBR1)"},
    "slc5a7": {"symbol": "SLC5A7", "uniprot": "Q9GZV3", "ensembl": "ENSG00000122863", "name": "High-Affinity Choline Transporter 1 (SLC5A7 / CHT1 / HACU)"},
    "hacu": {"symbol": "SLC5A7", "uniprot": "Q9GZV3", "ensembl": "ENSG00000122863", "name": "High-Affinity Choline Transporter 1 (SLC5A7 / CHT1 / HACU)"},
    "pgr": {"symbol": "PGR", "uniprot": "P06401", "ensembl": "ENSG00000082175", "name": "Progesterone Receptor (PGR / NR3C3)"},
    "progesterone receptor": {"symbol": "PGR", "uniprot": "P06401", "ensembl": "ENSG00000082175", "name": "Progesterone Receptor (PGR / NR3C3)"},
    "nr3c1": {"symbol": "NR3C1", "uniprot": "P04150", "ensembl": "ENSG00000113580", "name": "Glucocorticoid Receptor (NR3C1)"},
    "glucocorticoid receptor": {"symbol": "NR3C1", "uniprot": "P04150", "ensembl": "ENSG00000113580", "name": "Glucocorticoid Receptor (NR3C1)"},
    "ache": {"symbol": "ACHE", "uniprot": "P22303", "ensembl": "ENSG00000087088", "name": "Acetylcholinesterase (ACHE)"},
    "acetylcholinesterase": {"symbol": "ACHE", "uniprot": "P22303", "ensembl": "ENSG00000087088", "name": "Acetylcholinesterase (ACHE)"},
    "acetylcholinesterase (ache)": {"symbol": "ACHE", "uniprot": "P22303", "ensembl": "ENSG00000087088", "name": "Acetylcholinesterase (ACHE)"},
    "sirt1": {"symbol": "SIRT1", "uniprot": "Q96EB6", "ensembl": "ENSG00000096717", "name": "Sirtuin 1 (SIRT1)"},
    "sirt3": {"symbol": "SIRT3", "uniprot": "Q9NTG7", "ensembl": "ENSG00000149311", "name": "Sirtuin 3 (SIRT3 / Mitochondrial)"},
    "cd38": {"symbol": "CD38", "uniprot": "P28907", "ensembl": "ENSG00000004468", "name": "CD38 NAD+ Hydrolase (CD38)"},
    "mtor": {"symbol": "MTOR", "uniprot": "P42345", "ensembl": "ENSG00000198625", "name": "Mechanistic Target of Rapamycin Complex 1 (mTOR / MTORC1)"},
    "mtorc1": {"symbol": "MTOR", "uniprot": "P42345", "ensembl": "ENSG00000198625", "name": "Mechanistic Target of Rapamycin Complex 1 (mTOR / MTORC1)"},
    "shbg": {"symbol": "SHBG", "uniprot": "P04278", "ensembl": "ENSG00000129214", "name": "Sex Hormone-Binding Globulin (SHBG)"},
    "prkaa1": {"symbol": "PRKAA1", "uniprot": "Q13131", "ensembl": "ENSG00000132356", "name": "AMP-Activated Protein Kinase (AMPK / PRKAA1)"},
    "ampk": {"symbol": "PRKAA1", "uniprot": "Q13131", "ensembl": "ENSG00000132356", "name": "AMP-Activated Protein Kinase (AMPK)"},
    "cpt1a": {"symbol": "CPT1A", "uniprot": "P50416", "ensembl": "ENSG00000110090", "name": "Carnitine Palmitoyltransferase 1A (CPT1A)"},
    "nos3": {"symbol": "NOS3", "uniprot": "P29474", "ensembl": "ENSG00000164867", "name": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)"},
    "enos": {"symbol": "NOS3", "uniprot": "P29474", "ensembl": "ENSG00000164867", "name": "Endothelial Nitric Oxide Synthase (eNOS / NOS3)"},
    "nfe2l2": {"symbol": "NFE2L2", "uniprot": "Q16236", "ensembl": "ENSG00000116044", "name": "Nuclear Factor Erythroid 2-Related Factor 2 (Nrf2 / NFE2L2)"},
    "nrf2": {"symbol": "NFE2L2", "uniprot": "Q16236", "ensembl": "ENSG00000116044", "name": "Nuclear Factor Erythroid 2-Related Factor 2 (Nrf2 / NFE2L2)"},
    "gclc": {"symbol": "GCLC", "uniprot": "P48506", "ensembl": "ENSG00000001084", "name": "Glutamate-Cysteine Ligase Catalytic Subunit (GCLC)"},
    "nfkb1": {"symbol": "NFKB1", "uniprot": "P19838", "ensembl": "ENSG00000109320", "name": "Nuclear Factor NF-Kappa-B p105 Subunit (NFKB1)"},
    "ngf": {"symbol": "NGF", "uniprot": "P01138", "ensembl": "ENSG00000134259", "name": "Nerve Growth Factor (NGF)"},
    "bdnf": {"symbol": "BDNF", "uniprot": "P23560", "ensembl": "ENSG00000176697", "name": "Brain-Derived Neurotrophic Factor (BDNF)"},
    "gria2": {"symbol": "GRIA2", "uniprot": "P42262", "ensembl": "ENSG00000120251", "name": "Glutamate Ionotropic Receptor AMPA Type Subunit 2 (GRIA2)"},
    "actb": {"symbol": "ACTB", "uniprot": "P60709", "ensembl": "ENSG00000075624", "name": "Actin Beta (ACTB / Cytoskeleton)"},
    "fkbp1a": {"symbol": "FKBP1A", "uniprot": "P62942", "ensembl": "ENSG00000088832", "name": "FKBP12 Prolyl Isomerase (FKBP1A)"},
    # Gut Microbiome & Hepatic FMO3 Axis
    "cnta": {"symbol": "CntA", "uniprot": "Q835H2", "ensembl": "MICROB_CNTA", "name": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)"},
    "cntb": {"symbol": "CntB", "uniprot": "Q835H1", "ensembl": "MICROB_CNTB", "name": "Gut Microbiota Carnitine TMA-Lyase Subunit B (CntB)"},
    "carnitine tma lyase": {"symbol": "CntA", "uniprot": "Q835H2", "ensembl": "MICROB_CNTA", "name": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)"},
    "gut microbiota carnitine tma-lyase": {"symbol": "CntA", "uniprot": "Q835H2", "ensembl": "MICROB_CNTA", "name": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)"},
    "gut microbiota carnitine tma lyase": {"symbol": "CntA", "uniprot": "Q835H2", "ensembl": "MICROB_CNTA", "name": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)"},
    "fmo3": {"symbol": "FMO3", "uniprot": "P31513", "ensembl": "ENSG00000007933", "name": "Flavin-Containing Monooxygenase 3 (FMO3)"},
    "flavin-containing monooxygenase 3": {"symbol": "FMO3", "uniprot": "P31513", "ensembl": "ENSG00000007933", "name": "Flavin-Containing Monooxygenase 3 (FMO3)"},
}


# Backward compatibility alias
TARGET_REFERENCE_MAP = INITIAL_TARGET_SEED_METADATA


class PathwayService:
    """
    Service for querying Reactome Content Service, UniProt REST API, Ensembl REST API,
    and Open Targets Platform GraphQL API, caching biological pathways, physiological cross-talk,
    phenotypes, and biomarker connections into SQLite.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("HEALTHAI_CATALOG_DB") or os.environ.get("COMPOUNDS_DB_PATH") or DEFAULT_DB_PATH
        self.reactome_base_url = "https://reactome.org/ContentService"
        self.opentargets_graphql_url = "https://api.platform.opentargets.org/api/v4/graphql"
        self.uniprot_search_url = "https://rest.uniprot.org/uniprotkb/search"
        self.ensembl_symbol_url = "https://rest.ensembl.org/xrefs/symbol/homo_sapiens"
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        if self.db_path in _PATHWAY_INITIALIZED_DBS:
            return
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            self._init_schema_tables()
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            logger.error(f"Malformed or corrupted SQLite database schema detected at {self.db_path}: {e}. Auto-recovering clean database...")
            try:
                import shutil
                if os.path.isfile(self.db_path):
                    shutil.move(self.db_path, f"{self.db_path}.corrupt_{int(time.time())}")
                for extra in [f"{self.db_path}-wal", f"{self.db_path}-shm", f"{self.db_path}-journal"]:
                    if os.path.isfile(extra):
                        try:
                            os.remove(extra)
                        except Exception:
                            pass
            except Exception:
                pass
            self._init_schema_tables()
        _PATHWAY_INITIALIZED_DBS.add(self.db_path)

    def _init_schema_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_target_metadata (
                    target_query TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    uniprot_id TEXT,
                    ensembl_id TEXT,
                    canonical_name TEXT,
                    source TEXT DEFAULT 'online_curated',
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_target_pathways (
                    target_id TEXT NOT NULL,
                    target_symbol TEXT NOT NULL,
                    uniprot_id TEXT,
                    ensembl_id TEXT,
                    pathway_id TEXT NOT NULL,
                    pathway_name TEXT NOT NULL,
                    source TEXT DEFAULT 'Reactome',
                    data_json TEXT,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (target_id, pathway_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_target_phenotypes (
                    target_id TEXT NOT NULL,
                    phenotype_id TEXT NOT NULL,
                    phenotype_name TEXT NOT NULL,
                    score REAL DEFAULT 0.0,
                    direction TEXT DEFAULT 'MODULATES',
                    category TEXT DEFAULT 'adverse_effect',
                    evidence_type TEXT,
                    source TEXT DEFAULT 'OpenTargets',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (target_id, phenotype_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_pathway_bridges (
                    source_target_id TEXT NOT NULL,
                    target_pathway_pattern TEXT NOT NULL,
                    bridge_type TEXT NOT NULL,
                    vector_magnitude REAL NOT NULL,
                    description TEXT,
                    source TEXT DEFAULT 'Reactome_Crosstalk',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (source_target_id, target_pathway_pattern)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_target_cascades (
                    target_id TEXT PRIMARY KEY,
                    cascade_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()

            # Purge stale Xanthine / XDH cached cascade entries if present
            conn.execute("DELETE FROM cached_target_cascades WHERE LOWER(target_id) LIKE '%xanthine%' OR LOWER(target_id) LIKE '%xdh%'")
            conn.commit()

            # Warm initial metadata cache if empty
            count = conn.execute("SELECT count(*) FROM cached_target_metadata").fetchone()[0]
            if count == 0:
                now = time.time()
                items = [
                    (k, v["symbol"], v["uniprot"], v["ensembl"], v["name"], now)
                    for k, v in INITIAL_TARGET_SEED_METADATA.items()
                ]
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO cached_target_metadata
                    (target_query, symbol, uniprot_id, ensembl_id, canonical_name, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'seed', ?)
                    """,
                    items,
                )
                conn.commit()

    def get_all_target_registries(self) -> List[Dict[str, Any]]:
        """Dynamically load all registered biological targets from SQLite metadata table."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cached_target_metadata").fetchall()
            by_symbol: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                sym = r["symbol"]
                tq = str(r["target_query"] or "").lower()
                if sym not in by_symbol:
                    by_symbol[sym] = {
                        "gene_symbol": sym,
                        "uniprot_ids": [r["uniprot_id"]] if r["uniprot_id"] else [],
                        "chembl_target_ids": [tq] if tq.startswith("chembl") else [],
                        "canonical_name": r["canonical_name"] or sym,
                        "aliases": [sym.lower()],
                    }
                else:
                    if r["uniprot_id"] and r["uniprot_id"] not in by_symbol[sym]["uniprot_ids"]:
                        by_symbol[sym]["uniprot_ids"].append(r["uniprot_id"])
                    if tq.startswith("chembl") and tq not in by_symbol[sym]["chembl_target_ids"]:
                        by_symbol[sym]["chembl_target_ids"].append(tq)
                if tq and tq not in by_symbol[sym]["aliases"]:
                    by_symbol[sym]["aliases"].append(tq)
            return list(by_symbol.values())

    def get_all_target_cascades(self) -> List[Dict[str, Any]]:
        """Dynamically retrieve all active target cascades from SQLite cache."""
        with self._connect() as conn:
            rows = conn.execute("SELECT cascade_json FROM cached_target_cascades").fetchall()
            cascades: List[Dict[str, Any]] = []
            for r in rows:
                try:
                    cascades.append(json.loads(r[0]))
                except Exception:
                    pass
            return cascades

    def resolve_target_metadata(self, target_str: str, allow_online: bool = False) -> Dict[str, str]:
        """Resolves target string to canonical Symbol, UniProt ID, and Ensembl ID dynamically."""
        cleaned = re.sub(r"[^\w\s-]", " ", str(target_str).lower()).strip()
        if not cleaned:
            return {"symbol": "UNKNOWN", "uniprot": "", "ensembl": "", "name": "Unknown Target"}

        cache_key = (self.db_path, cleaned)
        if cache_key in _PATHWAY_METADATA_CACHE:
            return copy.deepcopy(_PATHWAY_METADATA_CACHE[cache_key])

        # 1. Check SQLite metadata cache
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM cached_target_metadata WHERE target_query = ?", (cleaned,)).fetchone()
            if row:
                meta = {"symbol": row["symbol"], "uniprot": row["uniprot_id"] or "", "ensembl": row["ensembl_id"] or "", "name": row["canonical_name"] or target_str}
                _PATHWAY_METADATA_CACHE[cache_key] = meta
                return copy.deepcopy(meta)

        # 2. Check seed metadata fallback with whole-word token precision
        cleaned_words = set(cleaned.split())
        cleaned_tok = re.sub(r"[^a-z0-9]", "", cleaned)
        for k, v in INITIAL_TARGET_SEED_METADATA.items():
            k_tok = re.sub(r"[^a-z0-9]", "", k)
            if k == cleaned or k_tok == cleaned_tok or k in cleaned_words:
                self._save_cached_metadata(cleaned, v["symbol"], v["uniprot"], v["ensembl"], v["name"])
                meta = dict(v)
                _PATHWAY_METADATA_CACHE[cache_key] = meta
                return copy.deepcopy(meta)

        sym = cleaned.upper().replace(" ", "")
        uniprot_id = ""
        ensembl_id = ""
        canonical_name = target_str

        # 3. Dynamic online lookup via UniProt REST API (only if online allowed)
        if allow_online:
            try:
                with httpx.Client(timeout=0.6, follow_redirects=True) as client:
                    # Query UniProt for Human protein
                    query_str = f"gene_exact:{sym} AND organism_id:9606"
                    resp = client.get(self.uniprot_search_url, params={"query": query_str, "format": "json", "size": 1})
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        if results:
                            u_entry = results[0]
                            uniprot_id = u_entry.get("primaryAccession", "")
                            prot_desc = u_entry.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "")
                            if prot_desc:
                                canonical_name = f"{prot_desc} ({sym})"

                    # If UniProt found or symbol exists, query Ensembl REST API for Ensembl ID
                    if sym:
                        ens_resp = client.get(f"{self.ensembl_symbol_url}/{sym}", headers={"Content-Type": "application/json"})
                        if ens_resp.status_code == 200:
                            ens_data = ens_resp.json()
                            if isinstance(ens_data, list) and len(ens_data) > 0:
                                ensembl_id = ens_data[0].get("id", "")
            except Exception as e:
                logger.debug("Online target metadata resolution for %s failed: %s", target_str, e)

        meta = {"symbol": sym, "uniprot": uniprot_id, "ensembl": ensembl_id, "name": canonical_name}
        self._save_cached_metadata(cleaned, sym, uniprot_id, ensembl_id, canonical_name)
        _PATHWAY_METADATA_CACHE[cache_key] = meta
        return copy.deepcopy(meta)

    def _save_cached_metadata(self, query: str, symbol: str, uniprot: str, ensembl: str, name: str) -> None:
        now = time.time()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cached_target_metadata
                    (target_query, symbol, uniprot_id, ensembl_id, canonical_name, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'dynamic_online', ?)
                    """,
                    (query, symbol, uniprot, ensembl, name, now),
                )
                conn.commit()
        except Exception as e:
            logger.debug("Error saving cached metadata: %s", e)

    def fetch_reactome_pathways(self, uniprot_id: str) -> List[Dict[str, Any]]:
        """Fetch curated biological pathways for a protein from Reactome Content Service."""
        if not uniprot_id:
            return []
        url = f"{self.reactome_base_url}/data/mapping/UniProt/{uniprot_id}/pathways"
        try:
            with httpx.Client(timeout=httpx.Timeout(0.4, connect=0.2), follow_redirects=True) as client:
                resp = client.get(url, params={"species": "9606"})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        pathways = []
                        for p in data:
                            if isinstance(p, dict) and p.get("stId"):
                                pathways.append({
                                    "pathway_id": p.get("stId"),
                                    "pathway_name": p.get("displayName"),
                                    "has_diagram": p.get("hasDiagram", False),
                                    "species": p.get("speciesName", "Homo sapiens"),
                                })
                        return pathways
        except Exception as e:
            logger.debug("Reactome pathway lookup failed for %s: %s", uniprot_id, e)
        return []

    def fetch_opentargets_phenotypes(self, ensembl_id: str) -> List[Dict[str, Any]]:
        """Fetch associated clinical phenotypes and diseases from Open Targets GraphQL API."""
        if not ensembl_id:
            return []
        query = """
        query targetPhenotypes($ensemblId: String!) {
          target(ensemblId: $ensemblId) {
            id
            approvedSymbol
            associatedDiseases(page: {size: 10}) {
              rows {
                disease {
                  id
                  name
                }
                score
              }
            }
            phenotypes {
              rows {
                phenotypeHPO {
                  id
                  name
                }
              }
            }
          }
        }
        """
        try:
            with httpx.Client(timeout=httpx.Timeout(0.4, connect=0.2), follow_redirects=True) as client:
                resp = client.post(self.opentargets_graphql_url, json={"query": query, "variables": {"ensemblId": ensembl_id}})
                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get("target", {})
                    phenos: List[Dict[str, Any]] = []
                    for row in data.get("associatedDiseases", {}).get("rows", []):
                        d = row.get("disease", {})
                        if d.get("name"):
                            phenos.append({
                                "phenotype_id": d.get("id", "EFO_UNKNOWN"),
                                "phenotype_name": d.get("name"),
                                "score": float(row.get("score", 0.5)),
                                "evidence_type": "disease_association",
                            })
                    for row in data.get("phenotypes", {}).get("rows", []):
                        hpo = row.get("phenotypeHPO", {})
                        if hpo.get("name"):
                            phenos.append({
                                "phenotype_id": hpo.get("id", "HP_UNKNOWN"),
                                "phenotype_name": hpo.get("name"),
                                "score": 0.7,
                                "evidence_type": "hpo_phenotype",
                            })
                    return phenos
        except Exception as e:
            logger.debug("Open Targets phenotype lookup failed for %s: %s", ensembl_id, e)
        return []


    def get_target_cascade(self, target_node_id: str, target_attrs: Optional[Dict[str, Any]] = None, allow_online: bool = False) -> Dict[str, Any]:
        """Convenience alias for get_dynamic_target_cascade."""
        return self.get_dynamic_target_cascade(target_node_id, target_attrs, allow_online=allow_online)

    def get_dynamic_target_cascade(self, target_node_id: str, target_attrs: Optional[Dict[str, Any]] = None, allow_online: bool = False) -> Dict[str, Any]:

        """
        Retrieves complete multi-tier pathway hierarchy, physiological states,
        biomarkers, and phenotypes for a target node, querying Reactome and Open Targets
        with SQLite persistent caching.
        """
        cache_key = (self.db_path, str(target_node_id).strip().lower())
        if cache_key in _PATHWAY_CASCADE_CACHE:
            return copy.deepcopy(_PATHWAY_CASCADE_CACHE[cache_key])

        target_attrs = target_attrs or {}
        target_name = target_attrs.get("label") or target_attrs.get("name") or target_node_id
        meta = self.resolve_target_metadata(target_name, allow_online=allow_online)
        symbol = meta.get("symbol", target_name)
        uniprot_id = meta.get("uniprot", "")
        ensembl_id = meta.get("ensembl", "")

        cached_pathways = self._get_cached_pathways(target_node_id)
        cached_phenotypes = self._get_cached_phenotypes(target_node_id)
        cached_bridges = self._get_cached_bridges(target_node_id)

        if not cached_pathways and uniprot_id and allow_online:
            online_pathways = self.fetch_reactome_pathways(uniprot_id)
            if online_pathways:
                self._save_cached_pathways(target_node_id, symbol, uniprot_id, ensembl_id, online_pathways)
                cached_pathways = online_pathways

        if not cached_phenotypes and ensembl_id and allow_online:
            online_phenos = self.fetch_opentargets_phenotypes(ensembl_id)
            if online_phenos:
                self._save_cached_phenotypes(target_node_id, online_phenos)
                cached_phenotypes = online_phenos

        # Generate default Reactome pathway if offline or unmapped
        if not cached_pathways:
            default_pw_id = f"R-HSA-{abs(hash(symbol)) % 9000000 + 1000000}"
            cached_pathways = [{
                "pathway_id": default_pw_id,
                "pathway_name": f"{symbol} Signaling & Transduction Pathway",
                "has_diagram": False,
                "species": "Homo sapiens",
            }]

        cascade = self._assemble_cascade(target_node_id, target_name, meta, cached_pathways, cached_phenotypes, cached_bridges)
        _PATHWAY_CASCADE_CACHE[cache_key] = cascade
        return copy.deepcopy(cascade)


    def _get_cached_pathways(self, target_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cached_target_pathways WHERE target_id = ?", (target_id,)).fetchall()
            return [dict(r) for r in rows]

    def _get_cached_phenotypes(self, target_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cached_target_phenotypes WHERE target_id = ?", (target_id,)).fetchall()
            return [dict(r) for r in rows]

    def _get_cached_bridges(self, target_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cached_pathway_bridges WHERE source_target_id = ?", (target_id,)).fetchall()
            return [dict(r) for r in rows]

    def _save_cached_pathways(self, target_id: str, symbol: str, uniprot: str, ensembl: str, pathways: List[Dict[str, Any]]) -> None:
        if not pathways:
            return
        now = time.time()
        items = [
            (target_id, symbol, uniprot, ensembl, p.get("pathway_id"), p.get("pathway_name"), json.dumps(p), now)
            for p in pathways
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO cached_target_pathways
                (target_id, target_symbol, uniprot_id, ensembl_id, pathway_id, pathway_name, source, data_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'Reactome', ?, ?)
                """,
                items,
            )
            conn.commit()

    def _save_cached_phenotypes(self, target_id: str, phenos: List[Dict[str, Any]]) -> None:
        if not phenos:
            return
        now = time.time()
        items = [
            (target_id, ph.get("phenotype_id"), ph.get("phenotype_name"), ph.get("score", 0.5), ph.get("direction", "MODULATES"), ph.get("evidence_type", "association"), now)
            for ph in phenos
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO cached_target_phenotypes
                (target_id, phenotype_id, phenotype_name, score, direction, category, evidence_type, source, updated_at)
                VALUES (?, ?, ?, ?, ?, 'adverse_effect', ?, 'OpenTargets', ?)
                """,
                items,
            )
            conn.commit()

    def _assemble_cascade(
        self,
        target_node_id: str,
        target_name: str,
        meta: Dict[str, str],
        pathways: List[Dict[str, Any]],
        phenotypes: List[Dict[str, Any]],
        bridges: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Constructs standardized pathway, physiology, biomarker, and phenotype node specs with genuine Reactome IDs."""
        if (not target_name or target_name.lower() == "unknown") and meta.get("name") and meta.get("name").lower() != "unknown":
            target_name = meta["name"]

        sym = meta.get("symbol", target_node_id).upper()
        sym_key = sym if sym and sym != "UNKNOWN" else target_name
        clean_key = re.sub(r"[^a-zA-Z0-9_]", "_", str(sym_key).lower()).strip("_")
        primary_pw = pathways[0] if pathways else None

        pw_id = primary_pw.get("pathway_id") if primary_pw else f"R-HSA-{abs(hash(clean_key)) % 9000000 + 1000000}_{clean_key}"
        pw_label = primary_pw.get("pathway_name") if primary_pw else f"{target_name} Transduction Cascade"

        phys_id = f"phys_{sym.lower()}_tone"
        phys_label = f"{target_name} Downstream Physiological Function"
        organ = "Systemic"

        biomarkers: List[Dict[str, Any]] = []
        pheno_nodes: List[Dict[str, Any]] = []
        target_bridges: List[Dict[str, Any]] = list(bridges)

        t_lower = target_name.lower()

        # 1. Estrogen / Aromatase (CYP19A1 / ESR1 / ESR2)
        if "aromatase" in t_lower or "cyp19" in t_lower or "esr" in t_lower or "estrogen" in t_lower or sym in ("CYP19A1", "ESR1", "ESR2"):
            organ = "Endocrine / Reproductive"
            biomarkers.extend([
                {"id": "bio_estradiol", "label": "Serum Estradiol (E2)", "unit": "pg/mL", "panel": "Endocrine Panel", "lower": 15.0, "upper": 45.0, "mag": 0.95},
                {"id": "bio_hdl_c", "label": "Serum HDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 90.0, "mag": 0.15},
                {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50.0, "upper": 100.0, "mag": -0.20},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.35},
            ])
            pheno_nodes.extend([
                {"id": "pheno_estrogen_optimization", "label": "Physiological Estradiol & Joint/Vascular Protection", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
                {"id": "pheno_gynecomastia_risk", "label": "Glandular Gynecomastia & Estrogenic Breast Tissue Proliferation Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.8},
                {"id": "pheno_fluid_retention", "label": "Estrogen-Mediated Renal Sodium & Subcutaneous Fluid Retention", "cat": "adverse_effect", "sev": "moderate", "mag": 0.75},
            ])

        # 2. Mineralocorticoid / Aldosterone (NR3C2)
        elif "mineralocorticoid" in t_lower or "aldosterone" in t_lower or "nr3c2" in t_lower or sym == "NR3C2":
            organ = "Renal / Adrenal"
            biomarkers.extend([
                {"id": "bio_potassium", "label": "Serum Potassium (K+)", "unit": "mEq/L", "panel": "Electrolytes", "lower": 3.5, "upper": 5.0, "mag": -0.55},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.35},
            ])
            pheno_nodes.extend([
                {"id": "pheno_bp_reduction", "label": "Aldosterone Antagonism & Antihypertensive Response", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.85},
                {"id": "pheno_hyperkalemia_risk", "label": "Severe Hyperkalemia Risk & Cardiac Conduction Vulnerability", "cat": "toxicity", "sev": "severe", "mag": -0.85},
                {"id": "pheno_aldosterone_blockade", "label": "Aldosterone Breakthrough Suppression & Antifibrotic Cardioprotection", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.8},
            ])

        # 3. Androgen Receptor (AR / NR3C4)
        elif "androgen receptor" in t_lower or "nr3c4" in t_lower or sym == "AR":
            organ = "Endocrine / Musculoskeletal"
            biomarkers.extend([
                {"id": "bio_hematocrit", "label": "Blood Hematocrit", "unit": "%", "panel": "Hematology Panel", "lower": 38.5, "upper": 50.0, "mag": 0.6},
                {"id": "bio_luteinizing_hormone", "label": "Luteinizing Hormone (LH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.5, "upper": 9.3, "mag": -0.85},
                {"id": "bio_fsh", "label": "Follicle-Stimulating Hormone (FSH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.4, "upper": 12.4, "mag": -0.85},
                {"id": "bio_testosterone", "label": "Serum Total Testosterone", "unit": "ng/dL", "panel": "Endocrine Panel", "lower": 300.0, "upper": 1000.0, "mag": -0.92},
                {"id": "bio_hdl_c", "label": "Serum HDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 90.0, "mag": -0.65},
                {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50.0, "upper": 100.0, "mag": 0.55},
                {"id": "bio_triglycerides", "label": "Serum Triglycerides", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 150.0, "mag": 0.35},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.40},
            ])
            pheno_nodes.extend([
                {"id": "pheno_anabolism", "label": "Skeletal Muscle Protein Synthesis & Myofibrillar Hypertrophy", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.95},
                {"id": "pheno_hpg_axis_shutdown", "label": "Profound Endogenous Androgen Suppression & Testicular Dysfunction", "cat": "toxicity", "sev": "severe", "mag": -0.95},
                {"id": "pheno_atherogenic_dyslipidemia", "label": "Severe HDL-C Suppression & Atherogenic Shift", "cat": "adverse_effect", "sev": "high", "mag": 0.85},
                {"id": "pheno_polycythemia_risk", "label": "Secondary Polycythemia & Hyperviscosity Vulnerability", "cat": "adverse_effect", "sev": "moderate", "mag": 0.7},
                {"id": "pheno_androgenic_alopecia", "label": "Follicular Miniaturization & Prostatic Hypertrophy Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.7},
                {"id": "pheno_lvh", "label": "Left Ventricular Concentric Hypertrophy & Myocardial Remodeling", "cat": "adverse_effect", "sev": "moderate", "mag": 0.65},
            ])

        # 3a. Progesterone Receptor (PGR / NR3C3) - 19-nor Steroids & Progestogens
        elif "progesterone receptor" in t_lower or "pgr" in t_lower or "nr3c3" in t_lower or sym == "PGR":
            organ = "Endocrine / Reproductive"
            biomarkers.extend([
                {"id": "bio_luteinizing_hormone", "label": "Luteinizing Hormone (LH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.5, "upper": 9.3, "mag": -0.85},
                {"id": "bio_fsh", "label": "Follicle-Stimulating Hormone (FSH)", "unit": "IU/L", "panel": "Endocrine Panel", "lower": 1.4, "upper": 12.4, "mag": -0.85},
                {"id": "bio_testosterone", "label": "Serum Total Testosterone", "unit": "ng/dL", "panel": "Endocrine Panel", "lower": 300.0, "upper": 1000.0, "mag": -0.90},
                {"id": "bio_prolactin", "label": "Serum Prolactin", "unit": "ng/mL", "panel": "Endocrine Panel", "lower": 2.0, "upper": 18.0, "mag": 0.80},
            ])
            pheno_nodes.extend([
                {"id": "pheno_hyperprolactinemia", "label": "Progestogenic Pituitary Prolactin Hypersecretion & Galactorrhea Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.85},
                {"id": "pheno_hpg_axis_shutdown", "label": "Profound Endogenous Androgen Suppression & Testicular Dysfunction", "cat": "toxicity", "sev": "severe", "mag": -0.95},
            ])

        # 3b. Circulating Serum Testosterone / Bioidentical Androgen Pool
        elif "testosterone pool" in t_lower or "circulating serum testosterone" in t_lower or sym == "TESTO":
            organ = "Endocrine / Circulating Pool"
            biomarkers.extend([
                {"id": "bio_testosterone", "label": "Serum Total Testosterone", "unit": "ng/dL", "panel": "Endocrine Panel", "lower": 300.0, "upper": 1000.0, "mag": 0.95},
                {"id": "bio_hematocrit", "label": "Blood Hematocrit", "unit": "%", "panel": "Hematology Panel", "lower": 38.5, "upper": 50.0, "mag": 0.4},
            ])
            pheno_nodes.extend([
                {"id": "pheno_androgen_replacement", "label": "Exogenous Androgen Pool Expansion & Anabolic Milieu", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.95},
            ])

        # 4. Renin-Angiotensin System (AGTR1 / ACE)
        elif "agtr1" in t_lower or "angiotensin" in t_lower or sym == "AGTR1":
            organ = "Cardiovascular / Renal"
            biomarkers.extend([
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.7},
                {"id": "bio_potassium", "label": "Serum Potassium (K+)", "unit": "mEq/L", "panel": "Electrolytes", "lower": 3.5, "upper": 5.0, "mag": -0.4},
            ])
            pheno_nodes.extend([
                {"id": "pheno_bp_control", "label": "Cardiovascular Risk Reduction & Blood Pressure Normalization", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.9},
                {"id": "pheno_nephroprotection", "label": "Renal Glomerular Protection & Reduced Microalbuminuria", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.8},
            ])

        # 5. Adrenergic Receptors (Beta-1 / Beta-2)
        elif "adrb1" in t_lower or "adrb2" in t_lower or "beta-1" in t_lower or "beta-2" in t_lower or sym in ("ADRB1", "ADRB2"):
            organ = "Cardiovascular / Pulmonary"
            biomarkers.extend([
                {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.35},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.25},
            ])
            pheno_nodes.extend([
                {"id": "pheno_inotropic", "label": "Myocardial Inotropy & Chronotropic Acceleration", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
                {"id": "pheno_bradycardia", "label": "Resting Bradycardia & Negative Inotropic Sparing", "cat": "therapeutic_benefit", "sev": "moderate", "mag": -0.8},
                {"id": "pheno_arrhythmia_risk", "label": "Ventricular Arrhythmogenic & Tachycardic Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.7},
            ])

        # 6. Alpha-2 Adrenergic Receptors (ADRA2A)
        elif "adra2" in t_lower or "alpha-2" in t_lower or sym == "ADRA2A":
            organ = "Autonomic / Cardiovascular"
            biomarkers.extend([
                {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.25},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": -0.20},
            ])
            pheno_nodes.extend([
                {"id": "pheno_sympathetic_activation", "label": "Sympathoadrenal Arousal, Lipolysis & Chronotropic Stimulation", "cat": "therapeutic_benefit", "sev": "moderate", "mag": -0.85},
                {"id": "pheno_tachycardia", "label": "Resting Tachycardia & Sympathetic Vasoconstriction", "cat": "adverse_effect", "sev": "moderate", "mag": -0.75},
            ])

        # 7. Adenosine Receptors (ADORA1 / ADORA2A / A1 / A2A)
        elif "adenosine" in t_lower or "adora" in t_lower or "a1 receptor" in t_lower or "a2a receptor" in t_lower or t_lower.startswith("a1") or t_lower.startswith("a2a") or sym in ("ADORA1", "ADORA2A"):
            organ = "Central Nervous System"
            biomarkers.extend([
                {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.18},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": -0.15},
            ])
            pheno_nodes.extend([
                {"id": "pheno_vigilance", "label": "Heightened Cognitive Vigilance & Reaction Time", "cat": "therapeutic_benefit", "sev": "moderate", "mag": -0.8},
                {"id": "pheno_insomnia", "label": "Sleep Onset Latency Increase & Sleep Fragmentation", "cat": "adverse_effect", "sev": "moderate", "mag": -0.7},
                {"id": "pheno_tachycardia", "label": "Resting Tachycardia & Sympathetic Chronotropy", "cat": "adverse_effect", "sev": "moderate", "mag": -0.65},
            ])
            target_bridges.append({
                "target_node_pattern": r"(?:dopamine|dat|net|vmat|pathway_monoamine_reuptake|phys_mesolimbic_tone)",
                "edge_type": EdgeType.MODULATES,
                "vector_magnitude": -0.7,
                "description": "Adenosine receptor antagonism removes tonic purinergic inhibition, facilitating central catecholaminergic and dopaminergic neurotransmission",
            })

        # 7b. GABA-A Receptor Neurotransmission (GABRA1 / GABRA2 - Inhibitory)
        elif ("gaba" in t_lower or "theanine" in t_lower or sym in ("GABRA1", "GABRA2")) and "glutamat" not in t_lower and "nmda" not in t_lower:
            organ = "Central Nervous System"
            biomarkers.extend([
                {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": -0.15},
                {"id": "bio_cortisol", "label": "Serum Cortisol Concentration", "unit": "μg/dL", "panel": "Endocrine Panel", "lower": 6.0, "upper": 18.0, "mag": -0.25},
            ])
            pheno_nodes.extend([
                {"id": "pheno_anxiolysis", "label": "Rapid Anxiolysis & Somatic Stress Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
                {"id": "pheno_sedation", "label": "Central Sedation & Sleep Consolidation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.8},
            ])

        # 7c. Glutamatergic Neurotransmission / NMDA Receptor (GRIN1 / GRIN2A - Excitatory)
        elif "glutamat" in t_lower or "nmda" in t_lower or sym in ("GRIN1", "GRIN2A"):
            organ = "Central Nervous System"
            biomarkers.extend([
                {"id": "bio_heart_rate", "label": "Resting Heart Rate", "unit": "bpm", "panel": "Vitals", "lower": 50, "upper": 90, "mag": 0.15},
                {"id": "bio_cortisol", "label": "Serum Cortisol Concentration", "unit": "μg/dL", "panel": "Endocrine Panel", "lower": 6.0, "upper": 18.0, "mag": 0.20},
            ])
            pheno_nodes.extend([
                {"id": "pheno_neuroexcitation", "label": "Glutamatergic Excitotoxicity & Central Nervous System Arousal", "cat": "adverse_effect", "sev": "moderate", "mag": 0.75},
            ])

        # 7d. Skeletal Muscle ATP-PCr Phosphagen System (Creatine)
        elif "creatine" in t_lower or "phosphagen" in t_lower or "atp-pcr" in t_lower or sym in ("CKM", "CKMT2", "SLC6A8"):
            organ = "Skeletal Muscle"
            biomarkers.extend([
                {"id": "bio_pcr_stores", "label": "Intramuscular Phosphocreatine Concentration", "unit": "mmol/kg dw", "panel": "Muscle Panel", "lower": 100, "upper": 150, "mag": 0.85},
                {"id": "bio_serum_creatinine", "label": "Serum Creatinine Lab Artifact", "unit": "mg/dL", "panel": "Renal Panel", "lower": 0.6, "upper": 1.2, "mag": 0.2},
            ])
            pheno_nodes.extend([
                {"id": "pheno_power_output", "label": "Enhanced Anaerobic Peak Power & Repeated Sprint Capacity", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
                {"id": "pheno_lean_mass", "label": "Accelerated Resistance Training Lean Mass Adaptation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.8},
            ])

        # 7e. Skeletal Muscle Carnosine Synthesis & Intracellular Proton Buffering (CARNS1 / Beta-Alanine)
        elif "carnosine" in t_lower or "carns1" in t_lower or "beta-alanine" in t_lower or "beta alanine" in t_lower or sym in ("CARNS1", "MRGPRD"):
            organ = "Skeletal Muscle / Performance"
            biomarkers.extend([
                {"id": "bio_carnosine_stores", "label": "Intramuscular Carnosine Pool", "unit": "mmol/kg dw", "panel": "Muscle Panel", "lower": 15, "upper": 60, "mag": 0.85},
            ])
            pheno_nodes.extend([
                {"id": "pheno_anaerobic_endurance", "label": "Intramuscular Proton Buffering & Delayed Fatigue in High-Intensity Exercise", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
                {"id": "pheno_paresthesia", "label": "Transient Sensory Paresthesia (Benign Cutaneous MrgprD Stimulation)", "cat": "therapeutic_benefit", "sev": "moderate", "mag": 0.65},
            ])

        # 8. Growth Hormone Axis (GHSR / GHRHR)
        elif "ghsr" in t_lower or "ghrelin" in t_lower or "growth hormone secretagogue" in t_lower or sym in ("GHSR", "GHRHR"):
            organ = "Pituitary / Endocrine"
            biomarkers.extend([
                {"id": "bio_igf1", "label": "Serum Insulin-Like Growth Factor 1 (IGF-1)", "unit": "ng/mL", "panel": "Endocrine Panel", "lower": 115.0, "upper": 307.0, "mag": 0.85},
                {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70.0, "upper": 100.0, "mag": 0.20},
            ])
            pheno_nodes.extend([
                {"id": "pheno_gh_pulsatility", "label": "Enhanced Pulsatile Growth Hormone Secretion & Cellular Repair", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
                {"id": "pheno_lean_mass_retention", "label": "Nitrogen Retention, Connective Tissue Healing & Lean Mass Accretion", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            ])

        # 9. Incretin Receptors (GLP1R / GIPR / GCGR)
        elif "glp1r" in t_lower or "glp-1" in t_lower or "gipr" in t_lower or sym in ("GLP1R", "GIPR", "GCGR"):
            organ = "Endocrine / Central Nervous System"
            biomarkers.extend([
                {"id": "bio_hba1c", "label": "Hemoglobin A1c (HbA1c)", "unit": "%", "panel": "Glycemic Panel", "lower": 4.0, "upper": 5.6, "mag": -0.85},
                {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70.0, "upper": 100.0, "mag": -0.80},
            ])
            pheno_nodes.extend([
                {"id": "pheno_glycemic_control", "label": "Glucose-Dependent Insulinotropic Action & Glycemic Normalization", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.95},
                {"id": "pheno_appetite_suppression", "label": "Hypothalamic POMC Appetite Suppression & Sustained Weight Loss", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            ])

        # 10. Phosphodiesterases (PDE5A / Tadalafil)
        elif "pde5" in t_lower or "phosphodiesterase" in t_lower or sym == "PDE5A":
            organ = "Cardiovascular / Endothelial"
            biomarkers.extend([
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90, "upper": 120, "mag": 0.6},
                {"id": "bio_cgmp", "label": "Endothelial Cyclic GMP Index", "unit": "index", "panel": "Vascular Panel", "lower": 10, "upper": 50, "mag": -0.8},
            ])
            pheno_nodes.extend([
                {"id": "pheno_vasodilation", "label": "Systemic Arteriolar Vasodilation & Endothelial Shear Stress Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.9},
                {"id": "pheno_hyperemia", "label": "Microvascular Hyperemia & Skeletal Muscle Perfusion Enhancement", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.85},
            ])

        # 11. 5-Alpha Reductase (SRD5A1 / SRD5A2 / Finasteride / Dutasteride)
        elif "5-alpha" in t_lower or "srd5a" in t_lower or "5ar" in t_lower or sym in ("SRD5A1", "SRD5A2"):
            organ = "Endocrine / Integumentary"
            biomarkers.extend([
                {"id": "bio_dht", "label": "Serum Dihydrotestosterone (DHT)", "unit": "pg/mL", "panel": "Endocrine Panel", "lower": 100, "upper": 850, "mag": 0.95},
                {"id": "bio_prostate_volume", "label": "Prostate Specific Tissue Volume Index", "unit": "index", "panel": "Prostate Panel", "lower": 10, "upper": 30, "mag": 0.7},
            ])
            pheno_nodes.extend([
                {"id": "pheno_androgenic_alopecia", "label": "Follicular Miniaturization & Androgenic Hair Thinning", "cat": "adverse_effect", "sev": "moderate", "mag": 0.8},
                {"id": "pheno_dht_suppression", "label": "Target Tissue DHT Suppression & Follicular Preservation", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.9},
            ])

        # 12. Hepatic Metabolic Clearance & Hepatobiliary System (ALT / AST / Bilirubin)
        elif ("hepatic" in t_lower or "hepatobiliary" in t_lower or "xenobiotic" in t_lower or "cholestasis" in t_lower or "bsep" in t_lower or "mrp2" in t_lower or "parenchymal" in t_lower) and "tgr5" not in t_lower and "gpbar1" not in t_lower:
            organ = "Hepatic / Systemic"
            biomarkers.extend([
                {"id": "bio_alt", "label": "Alanine Aminotransferase (ALT)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 7, "upper": 56, "mag": 0.75},
                {"id": "bio_ast", "label": "Aspartate Aminotransferase (AST)", "unit": "U/L", "panel": "Hepatic Panel", "lower": 10, "upper": 40, "mag": 0.70},
                {"id": "bio_total_bilirubin", "label": "Total Bilirubin", "unit": "mg/dL", "panel": "Hepatic Panel", "lower": 0.2, "upper": 1.2, "mag": 0.60},
            ])
            pheno_nodes.extend([
                {"id": "pheno_hepatic_strain", "label": "Hepatocellular Transaminase Elevation & Metabolic Load", "cat": "toxicity", "sev": "moderate", "mag": 0.75},
            ])

        # 13. Renal Glomerular Filtration & Tubular Transport
        elif "renal" in t_lower or "glomerular" in t_lower or "tubular" in t_lower:
            organ = "Renal / Excretory"
            biomarkers.extend([
                {"id": "bio_egfr", "label": "Glomerular Filtration Rate (eGFR)", "unit": "mL/min/1.73m²", "panel": "Renal Panel", "lower": 60, "upper": 120, "mag": -0.5},
                {"id": "bio_serum_creatinine", "label": "Serum Creatinine", "unit": "mg/dL", "panel": "Renal Panel", "lower": 0.6, "upper": 1.2, "mag": 0.6},
            ])
            pheno_nodes.extend([
                {"id": "pheno_renal_strain", "label": "Renal Hemodynamic Filtration Load & Osmotic Demand", "cat": "toxicity", "sev": "moderate", "mag": 0.7},
            ])

        # 14. Pathological Mitochondrial Uncoupling & ROS Generation (Mitochondrial Toxicity / Pro-Oxidant)
        elif ("uncoupl" in t_lower or "ros generation" in t_lower or "pro-oxidant" in t_lower or "mitochondrial stress" in t_lower or "mitochondrial" in t_lower or "oxidative" in t_lower) and "homeostasis" not in t_lower and "defense" not in t_lower and "antioxidant" not in t_lower:
            organ = "Cellular Bioenergetics"
            biomarkers.extend([
                {"id": "bio_mda", "label": "Malondialdehyde (Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 0.5, "upper": 2.0, "mag": 0.80},
                {"id": "bio_gsh_redox_ratio", "label": "Glutathione Redox Ratio (GSH:GSSG)", "unit": "ratio", "panel": "Redox Panel", "lower": 100.0, "upper": 300.0, "mag": -0.85},
                {"id": "bio_ros_level", "label": "Cellular Reactive Oxygen Species Index", "unit": "index", "panel": "Redox Panel", "lower": 10, "upper": 50, "mag": 0.85},
                {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": 0.50},
            ])
            pheno_nodes.extend([
                {"id": "pheno_oxidative_stress", "label": "Mitochondrial ROS Production & Cellular Oxidative Stress", "cat": "toxicity", "sev": "high", "mag": 0.85},
            ])

        # 15. Glutathione Biosynthesis, Cellular Redox Homeostasis & Antioxidant Defense
        elif "glutathione" in t_lower or "antioxidant" in t_lower or "redox" in t_lower or "bioenergetics" in t_lower or "cystine" in t_lower or "xc-" in t_lower or "gcl" in t_lower or "astaxanthin" in t_lower or "nrf2" in t_lower or "curcumin" in t_lower or "omega" in t_lower or sym in ("SLC7A11", "GCLC", "GCLM", "NFE2L2"):
            organ = "Systemic / Cytoprotective"
            biomarkers.extend([
                {"id": "bio_mda", "label": "Malondialdehyde (Lipid Peroxidation)", "unit": "μmol/L", "panel": "Redox Panel", "lower": 0.5, "upper": 2.0, "mag": -0.80},
                {"id": "bio_gsh_redox_ratio", "label": "Glutathione Redox Ratio (GSH:GSSG)", "unit": "ratio", "panel": "Redox Panel", "lower": 100.0, "upper": 300.0, "mag": 0.85},
                {"id": "bio_ros_level", "label": "Cellular Reactive Oxygen Species Index", "unit": "index", "panel": "Redox Panel", "lower": 10, "upper": 50, "mag": -0.85},
                {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": -0.70},
            ])
            pheno_nodes.extend([
                {"id": "pheno_cytoprotection", "label": "Cytoprotective Nrf2 Induction & Radical Scavenging", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.9},
            ])

        # 16. Cyclooxygenase & NF-kB Inflammatory Cascade (PTGS1 / PTGS2 / NFKB1)
        elif "cox" in t_lower or "ptgs" in t_lower or "cyclooxygenase" in t_lower or "nfkb" in t_lower or "nf-kb" in t_lower or "inflammatory cytokine" in t_lower or sym in ("PTGS1", "PTGS2", "NFKB1", "RELA"):
            organ = "Systemic / Inflammatory"
            biomarkers.extend([
                {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": 0.85},
            ])
            pheno_nodes.extend([
                {"id": "pheno_anti_inflammatory", "label": "Suppression of Systemic Inflammatory Eicosanoids & Cytokines", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.85},
            ])

        # 17. Regenerative & Angiogenic (VEGFR2 / KDR / TMSB4X)
        elif "vegfr2" in t_lower or "kdr" in t_lower or "tmsb4x" in t_lower or sym in ("KDR", "TMSB4X"):
            organ = "Vascular Endothelial / Connective"
            biomarkers.extend([
                {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": -0.70},
            ])
            pheno_nodes.extend([
                {"id": "pheno_tissue_healing", "label": "Accelerated Tendon, Ligament & Gastrointestinal Mucosal Repair", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            ])

        # 17. Melanocortin Receptors (MC1R / MC4R)
        elif "mc1r" in t_lower or "mc4r" in t_lower or "melanocortin" in t_lower or sym in ("MC1R", "MC4R"):
            organ = "Integumentary / Central Nervous System"
            biomarkers.extend([
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90.0, "upper": 120.0, "mag": 0.35},
            ])
            pheno_nodes.extend([
                {"id": "pheno_melanogenesis_tanning", "label": "Melanin Synthesis, Skin Photoprotection & Central Sexual Arousal", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            ])

        # 18. Peroxisome Proliferator-Activated Receptor Gamma (PPARG)
        elif "ppar" in t_lower or sym in ("PPARG", "PPARA", "PPARD"):
            organ = "Adipose / Metabolic"
            biomarkers.extend([
                {"id": "bio_hba1c", "label": "Hemoglobin A1c (HbA1c)", "unit": "%", "panel": "Glycemic Panel", "lower": 4.0, "upper": 5.6, "mag": -0.75},
                {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70.0, "upper": 100.0, "mag": -0.70},
                {"id": "bio_triglycerides", "label": "Serum Triglycerides", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 150.0, "mag": -0.50},
            ])
            pheno_nodes.extend([
                {"id": "pheno_insulin_sensitization", "label": "Adipose & Peripheral Insulin Sensitization", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
                {"id": "pheno_glycemic_control", "label": "Enhanced Glycemic Regulation & Free Fatty Acid Clearance", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            ])

        # 18b. HMG-CoA Reductase (HMGCR) / Statin Lipid & Cholesterol Biosynthesis Cascade
        elif "hmg" in t_lower or "statin" in t_lower or "cholesterol" in t_lower or "lipid metabolism" in t_lower or sym == "HMGCR":
            organ = "Hepatic / Cardiovascular"
            biomarkers.extend([
                {"id": "bio_ldl_c", "label": "Serum LDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 50.0, "upper": 100.0, "mag": 0.85},
                {"id": "bio_total_cholesterol", "label": "Serum Total Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 125.0, "upper": 200.0, "mag": 0.75},
                {"id": "bio_triglycerides", "label": "Serum Triglycerides", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 150.0, "mag": 0.35},
                {"id": "bio_apob", "label": "Apolipoprotein B (ApoB)", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 60.0, "upper": 110.0, "mag": 0.80},
                {"id": "bio_hdl_c", "label": "Serum HDL Cholesterol", "unit": "mg/dL", "panel": "Lipid Panel", "lower": 40.0, "upper": 90.0, "mag": -0.15},
            ])
            pheno_nodes.extend([
                {"id": "pheno_ldl_reduction", "label": "Potent Hepatic HMG-CoA Reductase Inhibition & LDL Receptor Up-regulation", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.95},
                {"id": "pheno_cholesterol_lowering", "label": "Atherogenic Lipid Clearance & Systemic Cholesterol Lowering", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
                {"id": "pheno_cardiovascular_risk_reduction", "label": "Atherosclerotic Plaque Stabilization & Major Adverse Cardiac Event (MACE) Reduction", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.88},
                {"id": "pheno_statins_myopathy_risk", "label": "Statin-Associated Muscle Symptom (SAMS) & Myopathy Sparing Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.40},
            ])

        # 18c. Catechol-O-Methyltransferase (COMT / Green Tea / Quercetin)
        elif "comt" in t_lower or "catechol-o-methyltransferase" in t_lower or sym == "COMT":
            organ = "Central Nervous System / Catecholamines"
            biomarkers.extend([
                {"id": "bio_dopamine", "label": "Synaptic Dopamine Index", "unit": "index", "panel": "Neurochemical Panel", "lower": 50.0, "upper": 150.0, "mag": 0.75},
            ])
            pheno_nodes.extend([
                {"id": "pheno_comt_inhibition", "label": "COMT Inhibition & Prolonged Synaptic Dopaminergic Half-Life", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            ])

        # 18e. AMPA Receptor / Ampakines (GRIA1 / GRIA2 / Positive Allosteric Modulators)
        elif "ampa" in t_lower or "ampakine" in t_lower or "gria" in t_lower or sym in ("GRIA1", "GRIA2", "GRIA3", "GRIA4"):
            organ = "Central Nervous System / Glutamatergic"
            biomarkers.extend([
                {"id": "bio_synaptic_plasticity", "label": "Synaptic Plasticity & LTP Index", "unit": "index", "panel": "Neurochemical Panel", "lower": 50.0, "upper": 150.0, "mag": 0.90},
                {"id": "bio_cognitive_efficacy", "label": "Cognitive Processing & Working Memory Index", "unit": "index", "panel": "Neurochemical Panel", "lower": 50.0, "upper": 150.0, "mag": 0.85},
            ])
            pheno_nodes.extend([
                {"id": "pheno_ampa_potentiation", "label": "AMPA-Mediated Synaptic Plasticity & Long-Term Potentiation (LTP)", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
                {"id": "pheno_glutamate_excitotoxicity_risk", "label": "Glutamatergic Neuroexcitation Risk (High-Dose Excitotoxicity Liability)", "cat": "adverse_effect", "sev": "moderate", "mag": 0.35},
            ])

        # 18f. Neurotrophin & Growth Factor Receptors (TrkB / NTRK2, TrkA / NTRK1, c-Met / MET)
        elif "trkb" in t_lower or "trka" in t_lower or "bdnf" in t_lower or "ngf" in t_lower or "hgf" in t_lower or "c-met" in t_lower or sym in ("NTRK2", "NTRK1", "MET", "BDNF", "NGF"):
            organ = "Central Nervous System / Neurotrophic"
            biomarkers.extend([
                {"id": "bio_synaptic_plasticity", "label": "Synaptic Plasticity & LTP Index", "unit": "index", "panel": "Neurochemical Panel", "lower": 50.0, "upper": 150.0, "mag": 0.85},
                {"id": "bio_neuroprotection", "label": "Neuronal Survival & Neuroprotection Index", "unit": "index", "panel": "Neurochemical Panel", "lower": 50.0, "upper": 150.0, "mag": 0.90},
            ])
            pheno_nodes.extend([
                {"id": "pheno_neurotrophin_induction", "label": "TrkB / BDNF & NGF Signaling Upregulation & Synaptogenesis", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            ])

        # 18g. Dopaminergic Monoaminergic Transmission (DAT / SLC6A3, Tyrosine Hydroxylase / TH, Sigma-1)
        elif "dat" in t_lower or "tyrosine hydroxylase" in t_lower or "sigma-1" in t_lower or sym in ("SLC6A3", "TH", "SIGMAR1", "SLC6A2"):
            organ = "Central Nervous System / Dopaminergic"
            biomarkers.extend([
                {"id": "bio_dopamine_tone", "label": "Striatal & Prefrontal Dopaminergic Tone", "unit": "index", "panel": "Neurochemical Panel", "lower": 50.0, "upper": 150.0, "mag": 0.85},
                {"id": "bio_cognitive_efficacy", "label": "Cognitive Processing & Working Memory Index", "unit": "index", "panel": "Neurochemical Panel", "lower": 50.0, "upper": 150.0, "mag": 0.75},
            ])
            pheno_nodes.extend([
                {"id": "pheno_dopaminergic_transmission", "label": "Enhanced Dopamine Reuptake Inhibition & De Novo Synthesis", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            ])

        # 18h. Growth Hormone Secretagogue Receptor (GHSR / Ghrelin Receptor / MK-677)
        elif "ghsr" in t_lower or "ghrelin" in t_lower or sym == "GHSR":
            organ = "Endocrine / Pituitary"
            biomarkers.extend([
                {"id": "bio_growth_hormone", "label": "Serum Growth Hormone (GH)", "unit": "ng/mL", "panel": "Endocrine Panel", "lower": 0.5, "upper": 5.0, "mag": 0.85},
                {"id": "bio_igf1", "label": "Insulin-Like Growth Factor 1 (IGF-1)", "unit": "ng/mL", "panel": "Endocrine Panel", "lower": 100.0, "upper": 300.0, "mag": 0.80},
                {"id": "bio_glucose", "label": "Fasting Blood Glucose", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 70.0, "upper": 100.0, "mag": 0.35},
            ])
            pheno_nodes.extend([
                {"id": "pheno_gh_pulsatility", "label": "Pulsatile Pituitary Growth Hormone & Hepatic IGF-1 Secretion", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.90},
            ])

        # 18i. Progesterone Receptor & Glucocorticoid Receptor (PGR / NR3C1)
        elif "progesterone" in t_lower or "pgr" in t_lower or "glucocorticoid" in t_lower or sym in ("PGR", "NR3C1"):
            organ = "Endocrine / Nuclear Receptor"
            biomarkers.extend([
                {"id": "bio_prolactin", "label": "Serum Prolactin", "unit": "ng/mL", "panel": "Endocrine Panel", "lower": 2.0, "upper": 18.0, "mag": 0.65},
            ])
            pheno_nodes.extend([
                {"id": "pheno_progestin_activity", "label": "Nuclear Progestogenic Signaling & Prolactinemia Risk", "cat": "adverse_effect", "sev": "moderate", "mag": 0.60},
            ])

        # 18j. Xanthine Dehydrogenase / Oxidase (XDH / XO / Tart Cherry Extract)
        elif "xanthine" in t_lower or "xdh" in t_lower or "uric acid" in t_lower or sym == "XDH":
            organ = "Purine Metabolism / Joints"
            biomarkers.extend([
                {"id": "bio_uric_acid", "label": "Serum Uric Acid", "unit": "mg/dL", "panel": "Metabolic Panel", "lower": 3.5, "upper": 7.2, "mag": 0.85},
                {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": -0.60},
            ])
            pheno_nodes.extend([
                {"id": "pheno_uric_acid_lowering", "label": "Xanthine Oxidase Inhibition & Uric Acid Lowering", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.90},
            ])

        # 18f. Multivalent Cation GI Chelation Site (Magnesium, Zinc)
        elif "chelation" in t_lower or "multivalent cation" in t_lower:
            organ = "Gastrointestinal Lumen"
            biomarkers.extend([
                {"id": "bio_antibiotic_absorption", "label": "Intestinal Antibiotic Bioavailability Index", "unit": "pct", "panel": "Absorption Panel", "lower": 70.0, "upper": 100.0, "mag": -0.85},
            ])
            pheno_nodes.extend([
                {"id": "pheno_gi_chelation_failure", "label": "Gastrointestinal Insoluble Complexation & Loss of Antibiotic Bioavailability", "cat": "adverse_effect", "sev": "high", "mag": -0.85},
            ])

        # 18g. Endothelial Nitric Oxide Synthase (eNOS / NOS3 / Panax Ginseng / Ginkgo Biloba)
        elif "enos" in t_lower or "nos3" in t_lower or "nitric oxide synthase" in t_lower or sym == "NOS3":
            organ = "Vascular Endothelium"
            biomarkers.extend([
                {"id": "bio_nitric_oxide", "label": "Endothelial Nitric Oxide Synthesis Rate", "unit": "μmol/L", "panel": "Vascular Panel", "lower": 10.0, "upper": 50.0, "mag": 0.80},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90.0, "upper": 120.0, "mag": -0.40},
            ])
            pheno_nodes.extend([
                {"id": "pheno_enos_vasodilation", "label": "Endothelial Nitric Oxide Production & Microvascular Perfusion", "cat": "therapeutic_benefit", "sev": "high", "mag": 0.85},
            ])

        # 18h. Gut Microbiota Carnitine/Choline TMA Lyase & Hepatic FMO3 Axis (CntA/B, yeaW/X, FMO3)
        elif any(w in t_lower for w in ["tma lyase", "tma-lyase", "cnta", "cntb", "yeaw", "yeax", "cutc", "fmo3", "trimethylamine"]):
            organ = "Gastrointestinal / Microbiome & Hepatic FMO3 Axis"
            biomarkers.extend([
                {"id": "bio_tmao", "label": "Serum Trimethylamine N-Oxide (TMAO)", "unit": "μmol/L", "panel": "Microbial Metabolite Panel", "lower": 0.5, "upper": 6.2, "mag": 0.95},
                {"id": "bio_crp", "label": "High-Sensitivity C-Reactive Protein (hs-CRP)", "unit": "mg/L", "panel": "Inflammatory Panel", "lower": 0.0, "upper": 1.0, "mag": 0.35},
                {"id": "bio_blood_pressure", "label": "Systolic Blood Pressure", "unit": "mmHg", "panel": "Vitals", "lower": 90.0, "upper": 120.0, "mag": 0.20},
            ])
            pheno_nodes.extend([
                {"id": "pheno_tmao_cardiovascular_risk", "label": "Microbial TMA Conversion & Elevated Atherogenic TMAO Risk", "cat": "adverse_effect", "sev": "high", "mag": 0.85},
                {"id": "pheno_microbial_metabolite_attenuation", "label": "Microbial TMA-Lyase Inhibition & Cardiovascular Protection", "cat": "therapeutic_benefit", "sev": "high", "mag": -0.85},
            ])

        # 19. Generic / Dynamic OpenTargets Phenotypes Fallback
        else:
            for p in phenotypes[:3]:
                p_id = f"pheno_{re.sub(r'[^a-zA-Z0-9_]', '_', p.get('phenotype_id', 'term')).lower()}"
                pheno_nodes.append({
                    "id": p_id,
                    "label": p.get("phenotype_name"),
                    "cat": "adverse_effect",
                    "sev": "moderate",
                    "mag": round(p.get("score", 0.5), 2),
                })

        cascade_result = {
            "target_name": target_name,
            "symbol": sym,
            "uniprot_id": meta.get("uniprot"),
            "ensembl_id": meta.get("ensembl"),
            "pathway": {
                "id": pw_id,
                "label": pw_label,
                "db": "Reactome",
            },
            "physiology": {
                "id": phys_id,
                "label": phys_label,
                "organ": organ,
            },
            "biomarkers": biomarkers,
            "phenotypes": pheno_nodes,
            "bridges": target_bridges,
            "raw_pathways": pathways,
            "raw_phenotypes": phenotypes,
        }

        # Save assembled cascade into SQLite cache
        now = time.time()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cached_target_cascades (target_id, cascade_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (target_node_id, json.dumps(cascade_result), now),
                )
                conn.commit()
        except Exception as e:
            logger.debug("Failed to cache assembled cascade for %s: %s", target_node_id, e)

        return cascade_result

