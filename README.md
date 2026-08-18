# healthAI

> **Science-driven clinical pharmacology laboratory, quantitative PK/PD simulation suite, biological network cascade mapper, and individualized protocol optimization engine.**

---

## Table of Contents

- [Executive Overview](#executive-overview)
- [Core Capabilities & Scientific Engines](#core-capabilities--scientific-engines)
  - [1. Pharmacokinetic (PK) & Pharmacodynamic (PD) Collision Engine](#1-pharmacokinetic-pk--pharmacodynamic-pd-collision-engine)
  - [2. Multi-Agent Syndrome Classifiers](#2-multi-agent-syndrome-classifiers)
  - [3. Patient Biometric & Clinical Biomarker Calibration](#3-patient-biometric--clinical-biomarker-calibration)
  - [4. Hierarchical Biological Knowledge Graph & Cascade Propagation](#4-hierarchical-biological-knowledge-graph--cascade-propagation)
  - [5. Quantitative Continuous-Time PK/PD Simulation](#5-quantitative-continuous-time-pkpd-simulation)
  - [6. Multi-Source Live Biomedical Data Enrichment](#6-multi-source-live-biomedical-data-enrichment)
- [Comprehensive Application Walkthrough](#comprehensive-application-walkthrough)
  - [Walkthrough 1: Pharmacology Lab & Collision Matrix (`/`)](#walkthrough-1-pharmacology-lab--collision-matrix-)
  - [Walkthrough 2: Biological Knowledge Graph & Cascade Engine (`/graph`)](#walkthrough-2-biological-knowledge-graph--cascade-engine-graph)
  - [Walkthrough 3: Compound Intelligence & PK/PD Simulation (`/compound/{key}`)](#walkthrough-3-compound-intelligence--pkpd-simulation-compoundkey)
  - [Walkthrough 4: Catalog Administration & Data Ingestion (`/admin`)](#walkthrough-4-catalog-administration--data-ingestion-admin)
- [End-to-End Workflow Example: Multi-Compound Optimization](#end-to-end-workflow-example-multi-compound-optimization)
- [System Architecture](#system-architecture)
- [API Reference](#api-reference)
- [Setup & Local Execution](#setup--local-execution)
- [Running Tests](#running-tests)

---

## Executive Overview

`healthAI` is a next-generation computational pharmacology and network biology platform built on FastAPI. While traditional drug checkers perform simple, binary pairwise lookups, `healthAI` models the human body as an interconnected biological system. 

It integrates:
- **Mechanistic Pharmacokinetics (PK):** CYP450 enzyme competitive inhibition, mechanism-based (suicide) inactivation, PXR/CAR induction, drug transporter kinetics (P-gp, BCRP, OATP, OCT, OAT), Phase II glucuronidation, and protein-binding displacement.
- **Systemic Pharmacodynamics (PD):** Multi-ligand receptor competition, net activation/blockade scoring, and additive/synergistic multi-agent toxicities (e.g., Serotonin Syndrome, QTc prolongation, Renal "Triple Whammy").
- **Network Biology:** A 6-tier directed ontological graph traversing compounds, molecular targets, signaling cascades, organ physiology, clinical biomarkers, and phenotypic outcomes.
- **Continuous PK/PD Simulation:** One-compartment Bateman oral/IV models, multi-dose steady-state accumulation, and sigmoidal $E_{max}$ Hill pharmacodynamics.
- **Individualized Health Calibration:** Real-time risk tuning against 20+ patient-specific laboratory markers (eGFR, ALT/AST, Bilirubin, Albumin, Electrolytes, Lipids, QTc, Vitals).

---

## Core Capabilities & Scientific Engines

```
                                ┌──────────────────────────────┐
                                │   Patient Profile & Labs     │
                                └──────────────┬───────────────┘
                                               │
┌──────────────────────────────┐               ▼               ┌──────────────────────────────┐
│     Compound Stack Input     │ ────► ┌───────────────┐ ◄──── │  Live Biomedical Enrichment  │
│  (Molecules, Doses, Timing)  │       │ healthAI Core │       │ (PubChem, ChEMBL, OpenFDA)   │
└──────────────────────────────┘       └───────┬───────┘       └──────────────────────────────┘
                                               │
         ┌────────────────────────┬────────────┴────────────┬────────────────────────┐
         ▼                        ▼                         ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  N x N Collision │    │ Multi-Agent      │    │ 6-Tier Cascade   │    │ Continuous PK/PD │
│  Matrix & Risks  │    │ Syndrome Alerts  │    │ Knowledge Graph  │    │ Dynamic Curves   │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 1. Pharmacokinetic (PK) & Pharmacodynamic (PD) Collision Engine
- **CYP450 Metabolism Collisions:** Detects substrate-inhibitor collisions across all major isoforms (`CYP1A2`, `CYP2B6`, `CYP2C9`, `CYP2C19`, `CYP2D6`, `CYP3A4`). Distinguishes reversible competitive inhibition, irreversible Mechanism-Based Inactivation (MBI), and metabolic enzyme induction.
- **Transporter Interactions:** Maps uptake and efflux conflicts across `P-gp (ABCB1)`, `BCRP (ABCG2)`, `OATP1B1/OATP1B3 (SLCO1B1/3)`, `OCT1/OCT2 (SLC22A1/2)`, and `OAT1/OAT3 (SLC22A6/8)`.
- **Phase II Conjugation:** Evaluates glucuronidation bottlenecks via `UGT1A1`, `UGT2B7`, and sulfotransferases.
- **Plasma Protein Binding Surges:** Identifies severe unbound free-fraction ($f_u$) surges when multiple highly protein-bound compounds (>90% bound) compete for serum albumin binding sites.
- **Physicochemical Chelation:** Flags gastrointestinal absorption failure from multivalent cations ($Ca^{2+}, Mg^{2+}, Fe^{2+}, Zn^{2+}$) binding tetracyclines, fluoroquinolones, or bisphosphonates.

### 2. Multi-Agent Syndrome Classifiers
Evaluates compound combinations for life-threatening emergent clinical syndromes:
- **Serotonin Toxicity / Syndrome:** Additive serotonergic tone from MAOIs, SSRIs, SNRIs, TCAs, 5-HT agonists, and releasing agents.
- **Cardiac Electrophysiology & QTc Prolongation:** Cumulative delayed-rectifier potassium channel ($hERG / KCNH2$) blockade, flagging Torsades de Pointes (TdP) risk.
- **Renal "Triple Whammy":** Dangerous simultaneous afferent arteriole constriction (NSAIDs), efferent arteriole dilation (ACEi/ARBs), and intravascular volume depletion (diuretics).
- **CNS & Respiratory Depression:** Additive GABAergic sedation across benzodiazepines, barbiturates, opioids, and sedative ancillaries.
- **Synergistic Hemorrhagic Bleeding:** Concurrent antiplatelet, anticoagulant, and serotonergic reuptake inhibition.
- **Sympathomimetic Hypertensive Crisis:** Hyper-adrenergic stimulation and uninhibited vasopressor surges.
- **Additive Anticholinergic Burden:** Cumulative central and peripheral muscarinic receptor blockade.

### 3. Patient Biometric & Clinical Biomarker Calibration
Dynamic risk scoring automatically adapts based on the patient's physiological state across 20+ laboratory markers:
- **Renal Clearance:** Adjusts compound half-life and toxicity thresholds using eGFR, Serum Creatinine, and BUN.
- **Hepatic Metabolism:** Scales clearance and hepatic burden from ALT, AST, Total Bilirubin, and Alkaline Phosphatase.
- **Cardiovascular & Vitals:** Incorporates Systolic/Diastolic Blood Pressure, Resting Heart Rate, and baseline QTc interval.
- **Electrolytes & Hematology:** Factors in Potassium ($K^+$), Sodium ($Na^+$), Magnesium ($Mg^{2+}$), Hematocrit, and Platelet count.
- **Metabolic & Lipid Panels:** Analyzes HbA1c, Fasting Glucose, LDL, HDL, and Triglycerides.

### 4. Hierarchical Biological Knowledge Graph & Cascade Propagation
`healthAI` models biological pathways as a directed graph spanning 6 distinct ontological tiers:
1. **Tier 0 — Compounds:** Active pharmacological agents, prodrugs, and supplements.
2. **Tier 1 — Molecular Targets:** Receptors, enzymes, ion channels, transporters, and carrier proteins.
3. **Tier 2 — Signaling Cascades:** Biochemical pathways (e.g., MAPK/ERK, PI3K/Akt/mTOR, RAAS, cAMP/PKA).
4. **Tier 3 — Organ Physiology:** Physiological functions (e.g., vascular tone, glomerular filtration, lipolysis).
5. **Tier 4 — Clinical Biomarkers:** Measurable laboratory indicators (e.g., eGFR, ALT, hs-CRP, Cortisol, LDL).
6. **Tier 5 — Clinical Outcomes:** Phenotypes, toxicities, and therapeutic benefits (e.g., Vasodilation, Nephrotoxicity).

The graph engine features **Multi-Ligand Receptor Occupancy** (modeling agonism vs. antagonism competition on shared targets) and **Dynamic Cascade Propagation** (simulating signal transmission with saturation over acute, sub-acute, and chronic timelines).

### 5. Quantitative Continuous-Time PK/PD Simulation
- **Bateman 1-Compartment Model:** Continuous-time blood concentration $C(t)$ curves for oral and IV administration:
  $$C(t) = \frac{D \cdot F \cdot k_a}{V_d \cdot (k_a - k_e)} \left(e^{-k_e t} - e^{-k_a t}\right)$$
- **Multi-Dose Steady-State Dynamics:** Calculates accumulation ratio ($R_{ac}$), peak-to-trough fluctuation ($PTF$), average steady-state concentration ($C_{ss,avg}$), $AUC_{0-\tau}$, and $T_{max,ss}$.
- **Sigmoidal $E_{max}$ Hill Equation:** Dynamic pharmacological effect modeling:
  $$E(C) = E_0 + \frac{E_{max} \cdot C^\gamma}{EC_{50}^\gamma + C^\gamma}$$
- **DDI Shift Modeling:** Calculates quantitative Area Under the Curve Ratios ($AUCR$) and $C_{max}$ multipliers during enzyme inhibition or induction.

### 6. Multi-Source Live Biomedical Data Enrichment
A resilient three-tier data layer provides zero-latency local operations with seamless on-demand online enrichment:
- **Tier 1 — Seed Library:** Instant in-memory curated compound profiles.
- **Tier 2 — SQLite Persistence:** Full local relational cache (`healthai_catalog.db`) storing structured pharmacology profiles.
- **Tier 3 — Live Online Enrichment:** Auto-queries NCBI PubChem (PUG-REST), EMBL-EBI ChEMBL (bioactivities, mechanisms, $K_i / IC_{50}$ values), NIH RxNorm, UniProt, Reactome Pathways, and FDA OpenFDA databases with write-through caching.

---

## Comprehensive Application Walkthrough

### Walkthrough 1: Pharmacology Lab & Collision Matrix (`/`)

The primary command dashboard for evaluating multi-compound stacks, inspecting pairwise collisions, and generating optimized protocols.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  HealthAI // PHARMACOLOGY LAB & COLLISION MATRIX WORKBENCH                       │
├──────────────────────────────────────┬───────────────────────────────────────────┤
│  COMPOUND SELECTOR & ACTIVE STACK    │  CUMULATIVE RISK OVERVIEW                 │
│  [ Search compound... (e.g. Aspirin) ]│  Health Index: 88/100 | Risk: MODERATE    │
│  • Telmisartan (40 mg, Daily)        │  [ Hepatic: Low ] [ Renal: Moderate ]     │
│  • Enzalutamide (160 mg, Daily)      │  [ Cardiac: Low ] [ CNS: None ]           │
├──────────────────────────────────────┴───────────────────────────────────────────┤
│  INTERACTIVE N x N COLLISION MATRIX                                              │
│               [ Telmisartan ]         [ Enzalutamide ]        [ Sildenafil ]    │
│ [ Telmisartan ]     ───               CYP Conflict (Mod)      Synergistic BP    │
│ [ Enzalutamide ] CYP Conflict (Mod)         ───               CYP3A4 Induction  │
│ [ Sildenafil ]   Synergistic BP       CYP3A4 Induction              ───          │
├──────────────────────────────────────────────────────────────────────────────────┤
│  CLINICAL SYNDROME ALERTS & ORGAN BURDENS                                        │
│  ⚠️  CYP3A4 Substrate/Inducer Collision: Enzalutamide reduces Sildenafil AUC    │
│  💡 Synergistic Vasodilation: Telmisartan + Sildenafil improves flow             │
│  📊 Biomarker Impact: Projected eGFR preservation (+2.4%), BP drop (-8 mmHg)   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Step-by-Step Workflow in the Lab:
1. **Adding Compounds & Custom Dosages:**
   - Use the typeahead search input to select compounds by generic name, brand name (e.g., *Micardis*, *Ozempic*, *Cialis*), or drug class.
   - For each added compound, customize the dose, unit, frequency (e.g., daily, twice daily, weekly), and timing (morning, evening, pre-workout).
2. **Configuring Patient Labs & Biometrics:**
   - Open the **Patient Profile & Labs Drawer** to customize renal markers (eGFR, Creatinine), liver enzymes (ALT, AST, Bilirubin), electrolytes ($K^+$, $Na^+$, $Mg^{2+}$), cardiovascular vitals (BP, Heart Rate, QTc), and metabolic indicators.
3. **Inspecting the $N \times N$ Collision Matrix:**
   - The interactive grid calculates every pairwise interaction in the stack.
   - Click any intersection cell to open a detailed collision breakdown displaying the mechanism, severity classification, affected metabolic pathways, and clinical management guidance.
4. **Reviewing Syndrome Alerts & Organ Burdens:**
   - Monitor the real-time organ burden gauges (Hepatic, Renal, Cardiovascular, CNS Stimulant, Sedative).
   - Review actionable alerts for multi-agent toxicities (e.g., Serotonin Syndrome, QTc prolongation, Bleeding risk).
5. **Protocol Optimization & Ancillary Recommendations:**
   - The Protocol Engine suggests protective ancillaries (e.g., TUDCA/NAC for hepatic support, CoQ10 for statin therapy) and timing separations to eliminate pharmacokinetic collisions.

---

### Walkthrough 2: Biological Knowledge Graph & Cascade Engine (`/graph`)

An interactive visual network canvas rendered with Cytoscape.js, illuminating the molecular pathways and systemic ripple effects of your stack.

```
 ┌─────────────┐        ┌─────────────┐
 │ Compound A  │        │ Compound B  │
 └──────┬──────┘        └──────┬──────┘
        │ AGONIZES             │ INHIBITS
        ▼                      ▼
 ┌─────────────┐        ┌─────────────┐
 │ Target Rec1 │        │ Target Rec2 │
 └──────┬──────┘        └──────┬──────┘
        │ ACTIVATES            │ SUPPRESSES
        ▼                      ▼
 ┌────────────────────────────────────┐
 │ Signaling Cascade (e.g., MAPK/ERK) │
 └─────────────────┬──────────────────┘
                   │ MODIFIES
                   ▼
         ┌──────────────────┐
         │ Organ Physiology │
         └─────────┬────────┘
                   │ REGULATES
                   ▼
        ┌────────────────────┐
        │ Clinical Biomarker │
        └──────────┬─────────┘
                   │ DRIVES
                   ▼
        ┌────────────────────┐
        │  Clinical Outcome  │
        └────────────────────┘
```

#### Features & Controls:
- **Hierarchical 6-Tier Visualization:** Nodes are color-coded and structured across 6 biological tiers from molecular ligand to clinical outcome.
- **Receptor Target Occupancy & Net Activation:** When multiple compounds in your stack bind the same receptor, the graph calculates competitive binding and displays net activation percentage and state (e.g., *Dominated by Antagonist*, *Synergistic Agonism*).
- **Dynamic Cascade Simulation:** Choose a timeline (*Acute*, *Sub-Acute 1-4 Weeks*, *Chronic Months*) to simulate signal propagation, biological saturation, and downstream biomarker shifts.
- **Cross-Talk Pathfinding (`/graph-path`):** Select any two biological entities to discover the shortest regulatory path and intermediate cross-talk connections between them.
- **Node Inspector:** Click any node to view chemical metadata (SMILES, InChIKey, LogP, Molecular Weight), binding affinities ($K_i, IC_{50}$), enzyme families, and degree centralities.

---

### Walkthrough 3: Compound Intelligence & PK/PD Simulation (`/compound/{key}`)

Deep-dive analytical dossier and continuous-time pharmacokinetic/pharmacodynamic simulation page for any compound.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  COMPOUND DOSSIER: Telmisartan (Key: telmisartan)                                 │
│  Class: ARB / AT1 Antagonist | Bioavailability: 42-58% | Half-life: ~24 hours    │
├──────────────────────────────────────────────────────────────────────────────────┤
│  CONTINUOUS-TIME PK SIMULATION (Bateman 1-Compartment)                           │
│   Conc (ng/mL)                                                                   │
│   1200 ┤        ╭───╮ (Cmax)                                                     │
│    800 ┤       ╭╯   ╰──────────╮                                                 │
│    400 ┤     ╭─╯               ╰─────────────────── (Steady-State Tau)           │
│      0 ┼─────┴────────────────────────────────────── Time (hours)                │
│        0     4      8     12     16     20     24                                │
│                                                                                  │
│   [AUC0-tau: 9,840 ng·h/mL] [Cmax,ss: 1,120 ng/mL] [Tmax,ss: 1.8 h] [PTF: 1.2]   │
├──────────────────────────────────────────────────────────────────────────────────┤
│  CO-ADMINISTERED DDI SIMULATION & AUC SHIFTS                                     │
│  Co-administered with CYP3A4 / P-gp Modulators:                                 │
│  • Projected AUC Ratio (AUCR): 1.42x (+42% systemic exposure)                    │
│  • Effective Half-Life: Extended from 24.0 h -> 34.1 h                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│  SIGMOIDAL Emax PHARMACODYNAMICS & RECEPTOR OCCUPANCY                            │
│  • Target: AGTR1 (Angiotensin II Type-1 Receptor) | Affinity: Ki 3.7 nM          │
│  • Peak Receptor Occupancy: 94.2% at Cmax | Net Effect: Sustained Vasodilation   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Analytical Capabilities:
- **Interactive PK Controls:** Adjust dose, route (Oral vs. IV Bolus), dosing interval ($\tau$), patient bodyweight, eGFR, ALT, and serum albumin in real time.
- **Multi-Dose Steady-State Curve:** Visualizes single-dose vs. steady-state accumulation dynamics, calculating the exact peak-to-trough fluctuation.
- **Drug-Drug Interaction (DDI) Testing:** Add co-administered compounds to calculate real-time metabolic enzyme competition and observe systemic exposure ($AUC$) surges.
- **Live Online Multi-Source Enrichment Button:** Triggers real-time fetching from PubChem, ChEMBL, and OpenFDA, populating quantitative binding constants and chemical descriptors with write-through caching.

---

### Walkthrough 4: Catalog Administration & Data Ingestion (`/admin`)

The master data management console for browsing, editing, enriching, and importing pharmacological records.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  HealthAI CATALOG ADMINISTRATION                                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│  [ Search catalog... (Multi-token search) ]   [ + Create New Compound ]          │
├──────────────────────────────────────────────────────────────────────────────────┤
│  Compound Key     Canonical Name    Drug Class            Source Tier   Actions  │
│  ────────────────────────────────────────────────────────────────────────────── │
│  telmisartan      Telmisartan       Antihypertensive      Enriched      [Edit]   │
│  semaglutide      Semaglutide       GLP-1 Receptor Agonist Seed         [Edit]   │
│  tadalafil        Tadalafil         PDE5 Inhibitor        Enriched      [Edit]   │
│  curcumin         Curcumin          Polyphenol Supplement Curated       [Edit]   │
├──────────────────────────────────────────────────────────────────────────────────┤
│  BATCH DATA INGESTION & PIPELINE TOOLING                                         │
│  • ChEMBL Drug Pipeline Ingestion                                                │
│  • Peptide & Bioregulator Extended Dataset Import                                │
│  • Automated Live OpenFDA / RxNorm Enrichment Sweep                              │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Administrative Tools:
- **Fast Multi-Token Search & Pagination:** Instantly filter across thousands of compounds by name, mechanism, or class.
- **Comprehensive Compound Editor:** Edit molecular weights, SMILES, target affinities, CYP enzyme profiles (substrates, inhibitors, inducers), transporter profiles, and organ burdens.
- **One-Click Online Re-Enrichment:** Trigger full live enrichment pipelines for individual compounds or batch records.

---

## End-to-End Workflow Example: Multi-Compound Optimization

Here is an example demonstrating how `healthAI` detects subtle pharmacokinetic collisions and resolves multi-agent risks:

### Scenario: Evaluating a Longevity & Cardiovascular Protocol
A user evaluates a stack comprising:
1. **Telmisartan** (40 mg daily) — Angiotensin Receptor Blocker
2. **Rosuvastatin** (10 mg daily) — HMG-CoA Reductase Inhibitor
3. **Curcumin Extract** (1000 mg with Piperine daily) — Anti-inflammatory Supplement
4. **Sildenafil** (25 mg as needed) — PDE5 Inhibitor
5. **Eplerenone** (25 mg daily) — Mineralocorticoid Receptor Antagonist

### Execution & Discoveries:
1. **Stack Assembly:**
   The user enters the compounds into the **Pharmacology Lab** (`/`).
2. **Collision Detection:**
   - **Transporter Conflict:** Piperine (in Curcumin extract) strongly inhibits `BCRP (ABCG2)` and `OATP1B1`, significantly increasing Rosuvastatin bioavailability and elevating myopathy risk.
   - **Electrolyte Collision:** Concurrent administration of Telmisartan + Eplerenone creates a compounding risk of hyperkalemia ($K^+ > 5.2 \text{ mEq/L}$).
   - **Additive Vasodilation:** Telmisartan + Sildenafil produces synergistic blood pressure reduction.
3. **Biomarker Input & Recalibration:**
   The user inputs their recent lab values: Serum Potassium $4.8 \text{ mEq/L}$, eGFR $82 \text{ mL/min}$, Blood Pressure $118/74 \text{ mmHg}$.
   - The engine flags the high-normal baseline potassium and escalates the Telmisartan + Eplerenone interaction to **High Risk**.
4. **Knowledge Graph Exploration (`/graph`):**
   Viewing the stack in the graph reveals that both Telmisartan and Eplerenone converge on the distal nephron aldosterone pathway, driving the potassium retention node.
5. **Resolution & Protocol Generation:**
   The engine recommends:
   - Separating Curcumin dosing or switching to a liposomal formulation without piperine.
   - Reducing Eplerenone to 12.5 mg with bi-weekly potassium monitoring.
   - Timing Sildenafil separated from morning antihypertensives to prevent symptomatic hypotension.

---

## System Architecture

```
healthAI/
├── app/
│   ├── main.py                     # FastAPI core application & middleware
│   ├── schemas/                    # Pydantic validation models
│   │   ├── profiles.py             # UserProfile, LabProfile, InteractionWorkbenchRequest
│   │   └── pkpd.py                 # PK/PD simulation requests, responses & parameters
│   ├── routers/                    # Clean modular API & view routers
│   │   ├── views.py                # UI routes (/, /admin, /graph, /compound/{key})
│   │   ├── catalog.py              # /catalog and /api/compounds/search
│   │   ├── interactions.py         # /api/interactions/matrix
│   │   ├── graph.py                # /graph-data and /graph-path
│   │   ├── pkpd.py                 # /api/pkpd/simulate and quantitative endpoints
│   │   └── protocols.py            # /protocol generation
│   ├── services/                   # High-performance scientific & domain logic
│   │   ├── catalog_service.py      # SQLite repository, search, and write-through cache
│   │   ├── interaction_engine.py   # Multi-pathway collision engine & syndrome classifiers
│   │   ├── pkpd_engine.py          # Continuous Bateman PK & Hill PD numerical models
│   │   ├── pkpd_enricher.py        # Quantitative affinity extraction (PubChem/ChEMBL)
│   │   ├── graph_service.py        # 6-Tier biological network builder & cascade simulator
│   │   ├── live_enrichment.py      # Live OpenFDA, ChEMBL & RxNorm enrichment pipelines
│   │   ├── pathway_service.py      # Canonical biological signaling pathway definitions
│   │   ├── dosing_service.py       # Weight-based and clinical dosing algorithms
│   │   └── protocol_builder.py     # Individualized protocol assembler
│   ├── knowledge_graph/            # NetworkX graph structures & ontological models
│   │   ├── graph.py                # Directed biological multigraph class
│   │   └── models.py               # Biological node & edge schemas
│   ├── data/                       # Seed compound library
│   │   └── compounds.py
│   └── static/                     # Interactive frontends (Vanilla JS, CSS, Cytoscape)
│       ├── index.html              # Pharmacology Lab & Collision Matrix Workbench
│       ├── graph.html              # Biological Knowledge Graph & Cascade Engine
│       ├── compound.html           # Compound Intelligence & Continuous PK/PD Network
│       ├── admin.html              # Catalog Explorer & Ingestion Admin
│       └── cytoscape.min.js        # Graph canvas library
├── scripts/                        # Ingestion, enrichment & batch ETL scripts
│   ├── populate_catalog.py
│   ├── populate_peptides.py
│   ├── enrich_database.py
│   └── import_chembl_drugs_csv.py
├── tests/                          # Automated pytest test suite
├── healthai_catalog.db             # Local SQLite compound catalog database
├── pyproject.toml                  # Build & test configuration
└── requirements.txt                # Core dependencies
```

---

## API Reference

### Core Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/health` | System health check and version status. |
| **GET** | `/` | Serves the Pharmacology Lab & Collision Matrix dashboard. |
| **GET** | `/graph` | Serves the Interactive Biological Knowledge Graph view. |
| **GET** | `/compound/{key}` | Serves the deep-dive Compound Intelligence & PK/PD profile page. |
| **GET** | `/admin` | Serves the Catalog Administration and Ingestion interface. |
| **POST** | `/api/interactions/matrix` | Evaluates $N \times N$ collision matrix, syndrome alerts, organ burdens, and cumulative risk score. |
| **GET** | `/graph-data` | Returns 6-tier network graph nodes, edges, cascade simulations, and multi-ligand receptor occupancy. |
| **GET** | `/graph-path` | Calculates shortest biological path and cross-talk connections between two nodes. |
| **POST** | `/api/pkpd/simulate` | Simulates continuous Bateman PK curves, multi-dose steady state, DDI AUC shifts, and Hill PD. |
| **GET** | `/api/compounds/{key}/pkpd` | Returns extracted quantitative PK parameters ($V_d, k_e, k_a, CL, f_u$) and PD affinities ($K_i, IC_{50}$). |
| **POST** | `/api/compounds/{key}/enrich-full` | Executes full live enrichment across PubChem, ChEMBL, UniProt, Reactome, and OpenFDA. |
| **GET** | `/api/compounds/search?q={query}` | Fast typeahead search across keys, brand names, drug classes, and indications. |
| **GET** | `/catalog` | Paginated catalog listing with multi-token filtering. |
| **GET** | `/catalog/{key}` | Retrieves full pharmacology profile with write-through cache status. |
| **POST** | `/catalog` | Creates or updates a compound record. |
| **DELETE**| `/catalog/{key}` | Deletes a compound record from the catalog database. |
| **POST** | `/protocol` | Generates individualized protocols based on user goals, biometrics, and lab values. |

---

## Setup & Local Execution

### Prerequisites
- Python 3.9+ installed on your system.

### One-Click Launch (Windows)
Double-click `start.bat` or run:
```bat
start.bat
```
*(Automatically creates/activates `.venv`, installs requirements, starts Uvicorn, and opens your default browser at `http://localhost:8000`)*

### PowerShell Launch
```powershell
.\start.ps1
```

### Python Launcher Script
```bash
# Start server with hot-reload and automatically open browser
python run_server.py --open-browser

# Custom port or host
python run_server.py --host 0.0.0.0 --port 8000
```

### Direct Uvicorn Launch
```bash
# 1. Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Running Tests

Execute the automated test suite with pytest:
```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v
```

---

## License & Disclaimer

*Disclaimer: `healthAI` is a computational pharmacology research and simulation engine intended for educational and informational purposes. It is not a substitute for professional medical advice, diagnosis, or treatment.*
