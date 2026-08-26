# healthAI

> **Science-driven clinical pharmacology laboratory, biophysical PBPK/ODE simulation suite, hierarchical biological causal network mapper, and autonomous multi-persona clinical AI copilot.**

---

## Table of Contents

- [Executive Overview](#executive-overview)
- [Core Capabilities & Scientific Engines](#core-capabilities--scientific-engines)
  - [1. Autonomous AI Clinical Copilot & Multi-Persona Architecture](#1-autonomous-ai-clinical-copilot--multi-persona-architecture)
  - [2. Stack Intent Engine & Protocol Purpose Taxonomy](#2-stack-intent-engine--protocol-purpose-taxonomy)
  - [3. Pharmacokinetic (PK) & Pharmacodynamic (PD) Collision Engine](#3-pharmacokinetic-pk--pharmacodynamic-pd-collision-engine)
  - [4. Multi-Agent Emergent Syndrome Classifiers](#4-multi-agent-emergent-syndrome-classifiers)
  - [5. Biophysical PBPK & Continuous-Time ODE Simulation](#5-biophysical-pbpk--continuous-time-ode-simulation)
  - [6. Hierarchical Biological Knowledge Graph, Neo4j & GraphRAG](#6-hierarchical-biological-knowledge-graph-neo4j--graphrag)
  - [7. Dynamic Live Biomedical & Literature Enrichment](#7-dynamic-live-biomedical--literature-enrichment)
  - [8. Patient Biometric & Clinical Biomarker Calibration](#8-patient-biometric--clinical-biomarker-calibration)
- [Comprehensive Application Walkthrough](#comprehensive-application-walkthrough)
  - [Walkthrough 1: Pharmacology Lab & Collision Matrix (`/`)](#walkthrough-1-pharmacology-lab--collision-matrix-)
  - [Walkthrough 2: AI Clinical Copilot & Interactive Protocol Drawer](#walkthrough-2-ai-clinical-copilot--interactive-protocol-drawer)
  - [Walkthrough 3: Biological Knowledge Graph & Cascade Engine (`/graph`)](#walkthrough-3-biological-knowledge-graph--cascade-engine-graph)
  - [Walkthrough 4: Compound Intelligence, Biophysical PBPK & PK/PD Simulation (`/compound/{key}`)](#walkthrough-4-compound-intelligence-biophysical-pbpk--pkpd-simulation-compoundkey)
  - [Walkthrough 5: Catalog Administration & Data Ingestion (`/admin`)](#walkthrough-5-catalog-administration--data-ingestion-admin)
- [End-to-End Workflow Example: Multi-Compound Optimization](#end-to-end-workflow-example-multi-compound-optimization)
- [Hardware-Accelerated Local LLM & llama-server Setup](#hardware-accelerated-local-llm--llama-server-setup)
- [System Architecture](#system-architecture)
- [API Reference](#api-reference)
- [Setup & Local Execution](#setup--local-execution)
- [Running Tests](#running-tests)
- [License & Disclaimer](#license--disclaimer)

---

## Executive Overview

`healthAI` is a next-generation computational pharmacology and network biology platform built on FastAPI. While traditional drug interaction checkers perform simplistic binary pairwise lookups, `healthAI` models human physiology as a deeply interconnected, dynamic biological system.

It unifies:
- **Autonomous AI Clinical Copilot:** A multi-persona clinical intelligence agent (Protocol Architect, Risk Auditor, Pharmacology Tutor, Lab Analyst) adhering to a strict **Zero-Bro-Science standard**, grounded in deterministic pharmacokinetic formulas, dynamic collision matrices, and GraphRAG knowledge graphs.
- **Stack Intent & Modality Partitioning:** Automatically infers underlying protocol goals (e.g., Anabolic Physique, Cognitive Focus, Longevity/Autophagy, Cardiovascular Protection), partitions compounds into therapeutic modalities, flags uncompensated organ burdens, and derives evidence-graded clinical co-factors.
- **Mechanistic Pharmacokinetics (PK):** CYP450 enzyme competitive inhibition, mechanism-based (suicide) inactivation, PXR/CAR induction, drug transporter kinetics (P-gp, BCRP, OATP, OCT, OAT), Phase II glucuronidation, and protein-binding displacement surges.
- **Systemic Pharmacodynamics (PD):** Multi-ligand receptor competition, net activation/blockade scoring, Loewe Additivity & Bliss Independence synergy modeling, and multi-agent emergent syndrome classifiers.
- **Biophysical PBPK & Multi-Compartment ODE Simulation:** 1-Compartment & 2-Compartment Open Models ($\alpha/\beta$ phases), Rodgers-Rowland / Poulin-Theil tissue partition coefficients ($K_p$ for Brain, Liver, Kidney, Muscle, Adipose), Henderson-Hasselbalch lysosomal ion-trapping, Michaelis-Menten non-linear elimination, and Sigmoidal $E_{max}$ Hill pharmacodynamics.
- **6-Tier Biological Knowledge Graph & GraphRAG:** Direct ontological graph traversing Compounds, Molecular Targets, Signaling Cascades, Organ Physiology, Clinical Biomarkers, and Phenotypic Outcomes, backed by Neo4j and in-memory multigraphs.
- **Live Biomedical & Literature Enrichment:** Multi-source pipeline combining NCBI PubChem, EMBL-EBI ChEMBL, UniProt, Reactome Pathways, OpenFDA, RxNorm, and live Europe PMC literature queries for dynamic redox/ROS burden detection.

---

## Core Capabilities & Scientific Engines

```
                                      ┌──────────────────────────────┐
                                      │   Patient Profile & Labs     │
                                      └──────────────┬───────────────┘
                                                     │
┌──────────────────────────────┐                     ▼                     ┌──────────────────────────────┐
│     Compound Stack Input     │ ─────────► ┌─────────────────┐ ◄───────── │ Live Biomedical Enrichment   │
│  (Molecules, Doses, Timing)  │            │  healthAI Core  │            │ (PubChem, ChEMBL, EuropePMC) │
└──────────────────────────────┘            └────────┬────────┘            └──────────────────────────────┘
                                                     │
         ┌──────────────────────────────┬────────────┴────────────┬──────────────────────────────┐
         ▼                              ▼                         ▼                              ▼
┌──────────────────┐          ┌──────────────────┐      ┌──────────────────┐           ┌──────────────────┐
│  AI Copilot &    │          │  N x N Collision │      │ 6-Tier Cascade   │           │ Biophysical PBPK │
│ Protocol Agents  │          │  Matrix & Risks  │      │ Knowledge Graph  │           │ Continuous ODEs  │
└──────────────────┘          └──────────────────┘      └──────────────────┘           └──────────────────┘
```

### 1. Autonomous AI Clinical Copilot & Multi-Persona Architecture

The platform features an autonomous, multi-turn AI reasoning engine (`CopilotAgent`) equipped with Server-Sent Events (SSE) streaming (`/api/ai/chat/stream`), ReAct-style scratchpad reasoning, and deterministic pharmacology tool calling (`/api/ai/tools/execute`).

The AI Copilot operates under four specialized personas:

1. **🏛️ Protocol Architect (`architect`):**
   - Focuses on bio-individualized protocol design, circadian scheduling (Morning, Midday, Afternoon, Bedtime), half-life alignments, and evidence-based protective co-factor pairings.
   - Separates depot injectables (weekly/split IM/SubQ) from daily oral schedules and prevents desensitization via intelligent cyclic scheduling.
2. **🛡️ Risk & Conflict Auditor (`auditor`):**
   - Forensically red-teams compound stacks, quantifying risks against the deterministic collision matrix.
   - Evaluates CYP450 bottlenecks, mechanism-based inactivation (MBI), transporter saturation (P-gp, OATP1B1, BCRP), AUCR surges, and acute emergent syndrome hazards.
3. **🔬 Pharmacology Tutor (`tutor`):**
   - Provides PhD-level molecular pharmacology breakdowns.
   - Explains quantitative binding kinetics ($K_i, K_d, IC_{50}, EC_{50}$), receptor subtypes, G-protein coupling ($G_s, G_i, G_q$), second messenger cascades (cAMP, $IP_3/DAG$, $Ca^{2+}$, PKA/PKC), and nuclear translocation (AMPK $\rightarrow$ SIRT1 $\rightarrow$ PGC-1$\alpha$, Nrf2/ARE, mTORC1 $\rightarrow$ p70S6K).
4. **🩸 Biomarker & Lab Analyst (`labs`):**
   - Correlates quantitative patient blood panels (Lipids, Hepatic transaminases, eGFR, Hormonal axes, HbA1c, hs-CRP) with stack pharmacokinetics.
   - Recommends tailored dose calibrations and targeted clinical monitoring timelines.

#### Dynamic Action Cards (`<action_card type="stack_diff">`)
When the AI Copilot suggests stack adjustments, additions, or removals, it generates structured action cards in JSON format. The frontend renders these cards with a single-click **"Apply to Stack"** button that immediately updates the workbench stack.

---

### 2. Stack Intent Engine & Protocol Purpose Taxonomy

The `StackIntentEngine` analyzes compound combinations to infer intent and uncover structural gaps:
- **Automated Purpose Inference:** Maps active stacks to primary taxonomy goals (e.g., `anabolic_physique`, `cognitive_focus`, `longevity_autophagy`, `metabolic_glycemic`, `cardiovascular_lipid`, `sleep_stress_recovery`, `neuroprotection`).
- **Modality Segmentation:** Partitions stack components into functional modalities (e.g., Core Anabolic Base, Endothelial Support, Metabolic Enhancer, Neurotransmitter Modulator).
- **Therapeutic Gap Detection:** Identifies uncompensated physiological burdens (e.g., unmanaged RAAS vasoconstriction, elevated sympathetic tone, hepatic transaminase strain, progestogenic/prolactin surges).
- **Evidence-Graded Co-Factor Generation:** Suggests candidate compounds with documented clinical targets, dosages, and safety grades (e.g., Telmisartan for AT1/PPAR-$\gamma$ renal-cardiovascular protection, Nebivolol for selective $\beta_1$/eNOS support, P5P for prolactin balance, TUDCA/NAC for hepatobiliary defense, L-Theanine for stimulant buffering).

---

### 3. Pharmacokinetic (PK) & Pharmacodynamic (PD) Collision Engine

- **CYP450 Metabolism Collisions:** Identifies substrate-inhibitor-inducer conflicts across major isoforms (`CYP1A2`, `CYP2B6`, `CYP2C9`, `CYP2C19`, `CYP2D6`, `CYP3A4`). Distinguishes reversible competitive inhibition, irreversible Mechanism-Based Inactivation (MBI), and metabolic enzyme induction.
- **Transporter Interactions:** Maps uptake and efflux conflicts across `P-gp (ABCB1)`, `BCRP (ABCG2)`, `OATP1B1/OATP1B3 (SLCO1B1/3)`, `OCT1/OCT2 (SLC22A1/2)`, and `OAT1/OAT3 (SLC22A6/8)`.
- **Phase II Conjugation:** Evaluates glucuronidation bottlenecks via `UGT1A1`, `UGT2B7`, and sulfotransferases.
- **Plasma Protein Binding Surges:** Identifies severe unbound free-fraction ($f_u$) surges when multiple highly protein-bound compounds (>90% bound) compete for serum albumin binding sites.
- **Physicochemical Chelation:** Flags gastrointestinal absorption failure when multivalent cations ($Ca^{2+}, Mg^{2+}, Fe^{2+}, Zn^{2+}$) bind tetracyclines, fluoroquinolones, or bisphosphonates.

---

### 4. Multi-Agent Emergent Syndrome Classifiers

Evaluates compound combinations for life-threatening emergent clinical syndromes:
- **Serotonin Toxicity / Syndrome:** Additive serotonergic tone from MAOIs, SSRIs, SNRIs, TCAs, 5-HT agonists, and releasing agents.
- **Cardiac Electrophysiology & QTc Prolongation:** Cumulative delayed-rectifier potassium channel ($hERG / KCNH2$) blockade, flagging Torsades de Pointes (TdP) risk.
- **Renal "Triple Whammy":** Concurrent afferent arteriole constriction (NSAIDs), efferent arteriole dilation (ACEi/ARBs), and intravascular volume depletion (diuretics).
- **CNS & Respiratory Depression:** Additive GABAergic sedation across benzodiazepines, barbiturates, opioids, and sedative ancillaries.
- **Synergistic Hemorrhagic Bleeding:** Concurrent antiplatelet, anticoagulant, and serotonergic reuptake inhibition.
- **Sympathomimetic Hypertensive Crisis:** Hyper-adrenergic stimulation and uninhibited vasopressor surges.
- **Additive Anticholinergic Burden:** Cumulative central and peripheral muscarinic receptor blockade.

---

### 5. Biophysical PBPK & Continuous-Time ODE Simulation

`healthAI` includes a physiological and continuous numerical simulation suite:

- **1-Compartment & 2-Compartment Open Models:**
  Simulates blood and tissue concentration curves with distribution ($\alpha$) and elimination ($\beta$) phases:
  $$C(t) = A \cdot e^{-\alpha t} + B \cdot e^{-\beta t}$$
- **Rodgers-Rowland / Poulin-Theil PBPK Tissue Partitioning ($K_p$):**
  Calculates tissue-to-plasma partition coefficients for **Brain**, **Liver**, **Kidney**, **Muscle**, and **Adipose** tissues based on lipophilicity ($\log P$), ionization ($pK_a$), molecular weight, unbound fraction ($f_u$), and transporter kinetics.
- **Henderson-Hasselbalch Lysosomal Trapping:**
  Quantifies lysosomal sequestration for basic lipophilic compounds across pH gradients (cytosol pH 7.2 vs. lysosome pH 4.8):
  $$R_{lyso} = \frac{1 + 10^{(pK_a - pH_{lyso})}}{1 + 10^{(pK_a - pH_{cyto})}}$$
- **Michaelis-Menten Non-Linear Clearance:**
  Simulates capacity-limited enzyme saturation kinetics:
  $$\frac{dC}{dt} = -\frac{V_{max} \cdot C}{K_m + C}$$
- **Dynamic Time-Resolved DDI Simulation:**
  Integrates dynamic inhibitor concentration $I(t)$ over time to model continuous clearance inhibition:
  $$CL_{eff}(t) = \frac{CL_{base}}{1 + \frac{I(t)}{K_i}}$$
- **Sigmoidal $E_{max}$ Hill Pharmacodynamics:**
  Dynamic receptor occupancy and downstream effect modeling:
  $$E(C) = E_0 + \frac{E_{max} \cdot C^\gamma}{EC_{50}^\gamma + C^\gamma}$$
- **Population Distribution Uncertainty Bands:**
  Computes population percentile intervals ($P_{10}, P_{25}, P_{50}, P_{75}, P_{90}$) scaled to patient biometric completeness.

---

### 6. Hierarchical Biological Knowledge Graph, Neo4j & GraphRAG

`healthAI` models biological pathways as a directed graph spanning 6 distinct ontological tiers:
1. **Tier 0 — Compounds:** Active pharmacological molecules, prodrugs, peptides, and supplements.
2. **Tier 1 — Molecular Targets:** Receptors, enzymes, ion channels, transporters, and carrier proteins.
3. **Tier 2 — Signaling Cascades:** Intracellular pathways (MAPK/ERK, PI3K/Akt/mTOR, RAAS, cAMP/PKA, AMPK/SIRT1).
4. **Tier 3 — Organ Physiology:** Physiological functions (vascular tone, glomerular filtration, lipolysis, cardiac inotropy).
5. **Tier 4 — Clinical Biomarkers:** Measurable laboratory indicators (eGFR, ALT, hs-CRP, Cortisol, LDL-C, ApoB).
6. **Tier 5 — Clinical Outcomes:** Phenotypic outcomes and toxicities (Vasodilation, Left Ventricular Hypertrophy, Nephrotoxicity).

#### Neo4j & GraphRAG Causal Triples
- **Dedicated Neo4j Graph Database:** Executes Cypher queries (`/api/graph/cypher`) and traverses tens of thousands of biological edges with fast in-memory fallback.
- **GraphRAG Subgraph Context Extractor (`/api/graph/graphrag-context`):** Extracts multi-hop relationship triples, receptor competition dynamics, and causal reasoning chains formatted specifically for LLM prompt ingestion.

---

### 7. Dynamic Live Biomedical & Literature Enrichment

- **Tier 1 — Seed Library:** Fast in-memory curated compound profiles.
- **Tier 2 — SQLite Persistence:** Full local relational cache (`healthai_catalog.db`) storing structured pharmacology profiles.
- **Tier 3 — Live Online Enrichment:** Auto-queries NCBI PubChem (PUG-REST), EMBL-EBI ChEMBL (bioactivities, mechanisms, $K_i / IC_{50}$ values), NIH RxNorm, UniProt, Reactome Pathways, and FDA OpenFDA.
- **Dynamic Online Redox & Literature Detection (`RedoxEnricher`):** Dynamically queries Europe PMC REST API for published evidence of ROS generation, glutathione depletion, or lipid peroxidation without relying on hardcoded lists.
- **Async Ingestion & WebSockets Layer:** Asynchronous background worker pools (`IngestionJobQueue`) with real-time WebSocket event streaming (`/ws/enrichment`).

---

### 8. Patient Biometric & Clinical Biomarker Calibration

Dynamic risk scoring automatically adapts based on 20+ laboratory markers:
- **Renal Clearance:** Scales half-life and toxicity thresholds using eGFR, Serum Creatinine, and BUN.
- **Hepatic Metabolism:** Adjusts clearance and hepatic burden from ALT, AST, Total Bilirubin, and Alkaline Phosphatase.
- **Cardiovascular & Vitals:** Incorporates Systolic/Diastolic BP, Resting Heart Rate, and baseline QTc interval.
- **Electrolytes & Hematology:** Factors in Potassium ($K^+$), Sodium ($Na^+$), Magnesium ($Mg^{2+}$), Hematocrit, and Platelet count.
- **Metabolic & Lipid Panels:** Analyzes HbA1c, Fasting Glucose, LDL-C, HDL-C, ApoB, and Triglycerides.

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
│               [ Telmisartan ]         [ Enzalutamide ]        [ Sildenafil ]     │
│ [ Telmisartan ]     ───               CYP Conflict (Mod)      Synergistic BP     │
│ [ Enzalutamide ] CYP Conflict (Mod)         ───               CYP3A4 Induction   │
│ [ Sildenafil ]   Synergistic BP       CYP3A4 Induction              ───          │
├──────────────────────────────────────────────────────────────────────────────────┤
│  CLINICAL SYNDROME ALERTS & ORGAN BURDENS                                        │
│  ⚠️  CYP3A4 Substrate/Inducer Collision: Enzalutamide reduces Sildenafil AUC     │
│  💡 Synergistic Vasodilation: Telmisartan + Sildenafil improves flow             │
│  📊 Biomarker Impact: Projected eGFR preservation (+2.4%), BP drop (-8 mmHg)    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Step-by-Step Workflow in the Lab:
1. **Adding Compounds & Custom Dosages:**
   - Use the typeahead search input to select compounds by generic name, brand name (e.g., *Micardis*, *Ozempic*, *Cialis*), or drug class.
   - For each added compound, customize dose, unit, frequency, and timing (morning, evening, pre-workout).
2. **Configuring Patient Labs & Biometrics:**
   - Open the **Patient Profile & Labs Drawer** to customize renal markers (eGFR, Creatinine), liver enzymes (ALT, AST, Bilirubin), electrolytes ($K^+, Na^+, Mg^{2+}$), vitals (BP, Heart Rate, QTc), and lipid panels.
3. **Inspecting the $N \times N$ Collision Matrix:**
   - The interactive grid calculates every pairwise interaction in the stack. Click any intersection cell to open a detailed collision breakdown displaying mechanism, severity, affected metabolic pathways, and clinical guidance.
4. **Reviewing Syndrome Alerts & Organ Burdens:**
   - Monitor real-time organ burden gauges (Hepatic, Renal, Cardiovascular, CNS Stimulant, Sedative) and actionable alerts for emergent syndromes.

---

### Walkthrough 2: AI Clinical Copilot & Interactive Protocol Drawer

An autonomous conversational drawer accessible via the floating trigger or `Ctrl+K`.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  🤖 HEALTHAI CLINICAL COPILOT                                        [X] Close   │
├──────────────────────────────────────────────────────────────────────────────────┤
│  PERSONA SELECTOR:                                                               │
│  [🏛️ Protocol Architect]  [🛡️ Risk Auditor]  [🔬 Pharmacology Tutor] [🩸 Labs]    │
├──────────────────────────────────────────────────────────────────────────────────┤
│  ACTIVE WORKBENCH STACK (Synced in Real Time):                                   │
│  [Telmisartan 40mg] [Caffeine 200mg] [Rosuvastatin 10mg]                         │
├──────────────────────────────────────────────────────────────────────────────────┤
│  COPILOT REASONING TELEMETRY (SSE Stream):                                       │
│  ⚡ Evaluating 2-hop GraphRAG context & CYP450 matrix...                          │
│                                                                                  │
│  ### Executive Assessment                                                        │
│  The protocol is well-balanced for cardiovascular support, but the central       │
│  adenosine blockade from Caffeine creates mild peripheral vasoconstriction.      │
│                                                                                  │
│  ### Recommended Circadian Schedule Table                                        │
│  | Window   | Compound     | Dose & Route | Pharmacokinetic Rationale         |  │
│  | Morning  | Telmisartan  | 40 mg Oral   | RAAS blockade & PPAR-gamma peak   |  │
│  | Morning  | Caffeine     | 100 mg Oral  | Adenosine antagonism              |  │
│  | Morning  | L-Theanine   | 200 mg Oral  | Glutamate modulation (Anti-jitter)|  │
│  | Bedtime  | Rosuvastatin | 10 mg Oral   | Nocturnal hepatic HMGCR peak      |  │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ ⚡ PROPOSED PROTOCOL MODIFICATION (Action Card)                             │  │
│  │ + Add: L-Theanine (200 mg, Oral, Morning)                                  │  │
│  │ ~ Modify: Caffeine (200 mg -> 100 mg)                                      │  │
│  │ [ ✓ Apply to Workbench Stack ]                                             │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────────┤
│  [ Ask the Copilot a clinical question... (Ctrl+Enter)             ] [ Send ]    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Copilot Features:
- **Real-Time Persona Switching:** Toggle between Architect, Auditor, Tutor, and Labs modes dynamically with tailored prompt constraints.
- **Live SSE Streaming:** Streams reasoning telemetry, scratchpad hypotheses, and synthesized clinical advice in real time.
- **One-Click Action Card Execution:** Clicking **"Apply to Stack"** updates active compounds in the workbench without manual re-entry.

---

### Walkthrough 3: Biological Knowledge Graph & Cascade Engine (`/graph`)

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
- **Hierarchical 6-Tier Visualization:** Nodes are color-coded and structured across 6 biological tiers.
- **Receptor Target Occupancy & Net Activation:** Calculates competitive binding when multiple compounds bind the same target (e.g., *Dominated by Antagonist*, *Synergistic Agonism*).
- **Dynamic Cascade Simulation:** Choose a timeline (*Acute*, *Sub-Acute 1-4 Weeks*, *Chronic Months*) to simulate signal propagation, biological saturation, and downstream biomarker shifts.
- **Cross-Talk Pathfinding (`/graph-path`):** Select any two biological entities to discover the shortest regulatory path and intermediate cross-talk connections.
- **Node Inspector:** Click any node to view chemical metadata (SMILES, InChIKey, LogP, MW), binding affinities ($K_i, IC_{50}$), enzyme families, and degree centralities.

---

### Walkthrough 4: Compound Intelligence, Biophysical PBPK & PK/PD Simulation (`/compound/{key}`)

Deep-dive analytical dossier and continuous-time pharmacokinetic/pharmacodynamic simulation page for any compound.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  COMPOUND DOSSIER: Telmisartan (Key: telmisartan)                                 │
│  Class: ARB / AT1 Antagonist | Bioavailability: 42-58% | Half-life: ~24 hours    │
├──────────────────────────────────────────────────────────────────────────────────┤
│  CONTINUOUS-TIME PBPK & PK/PD SIMULATION (Bateman / 2-Compartment Open Model)    │
│   Conc (ng/mL)                                                                   │
│   1200 ┤        ╭───╮ (Cmax)                                                     │
│    800 ┤       ╭╯   ╰──────────╮                                                 │
│    400 ┤     ╭─╯               ╰─────────────────── (Steady-State Tau)           │
│      0 ┼─────┴────────────────────────────────────── Time (hours)                │
│        0     4      8     12     16     20     24                                │
│                                                                                  │
│   [AUC0-tau: 9,840 ng·h/mL] [Cmax,ss: 1,120 ng/mL] [Tmax,ss: 1.8 h] [PTF: 1.2]   │
│   [PBPK Kp: Adipose 3.4 | Muscle 1.1 | Liver 4.2 | Kidney 2.8 | Brain 0.12]      │
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
- **Interactive PBPK Controls:** Toggle 2-compartment distribution phases and view tissue-specific concentrations ($C_{brain}, C_{liver}, C_{kidney}, C_{muscle}, C_{adipose}$).
- **Multi-Dose Steady-State Dynamics:** Visualizes single-dose vs. steady-state accumulation curves with exact peak-to-trough fluctuations.
- **Dynamic DDI Modeling:** Add co-administered compounds to calculate real-time metabolic competition and observe systemic exposure ($AUC$) surges.
- **Live Online Multi-Source Enrichment Button:** Triggers real-time fetching from PubChem, ChEMBL, UniProt, and OpenFDA with write-through caching.

---

### Walkthrough 5: Catalog Administration & Data Ingestion (`/admin`)

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
- **Fast Multi-Token Search & Pagination:** Filter across thousands of compounds by name, mechanism, or class.
- **Comprehensive Compound Editor:** Edit molecular weights, SMILES, target affinities, CYP enzyme profiles, transporters, and organ burdens.
- **One-Click Online Re-Enrichment:** Trigger full live enrichment pipelines for individual compounds or batch records.

---

## End-to-End Workflow Example: Multi-Compound Optimization

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
   The user inputs recent lab values: Serum Potassium $4.8 \text{ mEq/L}$, eGFR $82 \text{ mL/min}$, Blood Pressure $118/74 \text{ mmHg}$.
   - The engine flags the high-normal baseline potassium and escalates the Telmisartan + Eplerenone interaction to **High Risk**.
4. **AI Copilot Consulting (`Ctrl+K`):**
   The user opens the Copilot with the **Protocol Architect** persona. The agent reasons through the GraphRAG causal chain and emits an Action Card recommending:
   - Switching Curcumin to a liposomal formulation without piperine to protect OATP1B1 clearance.
   - Titrating Eplerenone to 12.5 mg with bi-weekly potassium monitoring.
   - Scheduling Sildenafil separated from morning antihypertensives to prevent symptomatic hypotension.

---

## Hardware-Accelerated Local LLM & llama-server Setup

`healthAI` is optimized for local LLM inference with native Windows CUDA / CPU support and high-performance RTX 5090 acceleration.

### Downloading the Recommended Model (Qwen 3.8-27B)
Run the multi-threaded resumable downloader:
```bash
python scripts/download_model.py
```
*(Downloads `Qwen3.8-27B-UD-Q6_K.gguf` to `models/` in 24 concurrent threads with automatic integrity tracking).*

### Starting the Local LLM Server
Launch the hardware-accelerated `llama-server`:

**Windows Batch:**
```bat
start_llama_server.bat
```

**PowerShell:**
```powershell
.\start_llama_server.ps1
```

#### Included RTX 5090 Optimizations:
- **Multi-Target Prediction Speculative Decoding:** `--spec-draft-mtp --spec-draft-n-max 2`
- **Flash Attention:** `-fa`
- **8-bit KV Cache Quantization:** `-ctk q8_0 -ctv q8_0`
- **Context Window:** `-c 16384`
- **Jinja Templating:** `--jinja`
- **Memory Locking:** `--mlock`
- **Port:** `8080` (Auto-discovered by `app/services/ai_service.py`)

---

## System Architecture

```
healthAI/
├── app/
│   ├── main.py                     # FastAPI core application, CORS & router registrations
│   ├── schemas/                    # Pydantic validation models
│   │   ├── profiles.py             # UserProfile, LabProfile, InteractionWorkbenchRequest
│   │   └── pkpd.py                 # PBPK simulation requests, responses & tissue partition models
│   ├── routers/                    # Clean modular API & view routers
│   │   ├── ai.py                   # /api/ai/chat/stream (SSE), /api/ai/tools/execute, /api/ai/goals
│   │   ├── catalog.py              # /catalog and /api/compounds/search
│   │   ├── enrichment.py           # /api/enrichment/jobs & /ws/enrichment WebSockets
│   │   ├── graph.py                # /graph-data, /graph-path, /api/graph/cypher, /api/graph/graphrag-context
│   │   ├── interactions.py         # /api/interactions/matrix
│   │   ├── pkpd.py                 # /api/pkpd/simulate and quantitative PBPK endpoints
│   │   ├── protocols.py            # /protocol generation endpoint
│   │   └── views.py                # UI HTML views (/, /admin, /graph, /compound/{key})
│   ├── services/                   # High-performance scientific & domain logic
│   │   ├── ai_service.py           # Local LLM connector (llama-server / OpenAI-compatible API)
│   │   ├── catalog_service.py      # SQLite repository, multi-token search & write-through cache
│   │   ├── copilot_agent.py        # Multi-persona autonomous agent, GraphRAG reasoning & tools
│   │   ├── dosing_service.py       # Biometric-adjusted and clinical dosing algorithms
│   │   ├── graph_service.py        # 6-Tier biological network builder & cascade simulator
│   │   ├── ingestion_queue.py      # Async worker pool, job queue & WebSocket broadcaster
│   │   ├── interaction_engine.py   # Multi-pathway collision engine & syndrome classifiers
│   │   ├── live_enrichment.py      # Live OpenFDA, ChEMBL & RxNorm enrichment pipelines
│   │   ├── pathway_service.py      # Canonical biological signaling pathway definitions
│   │   ├── pharmacology_enricher.py# Comprehensive pharmacological parameter extractor
│   │   ├── pkpd_engine.py          # Continuous Bateman & 2-compartment PBPK/ODE models
│   │   ├── pkpd_enricher.py        # Quantitative affinity extraction (PubChem/ChEMBL)
│   │   ├── protocol_agent.py       # Bio-individualized protocol optimization service
│   │   ├── protocol_builder.py     # Deterministic protocol assembly engine
│   │   ├── redox_enricher.py       # Dynamic Europe PMC literature ROS/redox detection
│   │   ├── stack_intent_engine.py  # Protocol goal taxonomy & therapeutic gap analyzer
│   │   └── synergy_engine.py       # Loewe Additivity CI & Bliss Independence synergy calculator
│   ├── knowledge_graph/            # Graph database & ontological models
│   │   ├── graph.py                # Directed biological multigraph class (NetworkX)
│   │   ├── graph_db.py             # Neo4j driver, Cypher execution & GraphRAG extractor
│   │   └── models.py               # Biological node & edge schemas
│   ├── data/                       # Seed compound library
│   │   └── compounds.py
│   └── static/                     # Interactive frontends (Vanilla JS, CSS, Cytoscape)
│       ├── index.html              # Pharmacology Lab, Collision Matrix & AI Copilot Drawer
│       ├── graph.html              # Biological Knowledge Graph & Cascade Engine
│       ├── compound.html           # Compound Intelligence & Continuous PBPK Network
│       ├── admin.html              # Catalog Explorer & Ingestion Admin
│       └── cytoscape.min.js        # Graph canvas library
├── scripts/                        # Ingestion, enrichment & batch ETL scripts
│   ├── download_model.py           # Multi-threaded chunked GGUF model downloader
│   ├── populate_catalog.py         # Seed compound catalog initializer
│   ├── populate_database.py        # Automated multi-source database population script
│   ├── populate_peptides.py        # Peptide dataset importer
│   ├── enrich_database.py          # Batch enrichment script
│   └── import_chembl_drugs_csv.py  # ChEMBL CSV dataset parser
├── tests/                          # Automated pytest test suites
│   ├── test_ai_agent.py            # AI protocol optimization tests
│   ├── test_ai_copilot_suite.py    # Multi-turn Copilot, SSE streaming & ReAct tool tests
│   ├── test_biophysical_pbpk_and_odes.py # Rodgers-Rowland PBPK, lysosomal trapping & ODE tests
│   └── ...                         # Collision matrix, graph, and API endpoint tests
├── healthai_catalog.db             # Local SQLite compound catalog database
├── pyproject.toml                  # Build & test configuration
├── requirements.txt                # Core dependencies
├── run_server.py                   # Python server launcher script
├── start.bat                       # One-click Windows launch script (with Neo4j auto-check)
├── start.ps1                       # PowerShell launch script
├── start_llama_server.bat          # RTX 5090 llama-server batch launcher
├── start_llama_server.ps1          # RTX 5090 llama-server PowerShell launcher
├── start_neo4j.bat                 # Neo4j batch launcher
└── start_neo4j.ps1                 # Neo4j PowerShell launcher
```

---

## API Reference

### 1. AI Copilot & Autonomous Agent Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/api/ai/modes` | Returns registered Copilot personas (Architect, Auditor, Tutor, Labs) and quick prompts. |
| **GET** | `/api/ai/goals` | Returns the protocol purpose taxonomy (Anabolic, Cognitive, Longevity, etc.). |
| **POST** | `/api/ai/infer-purpose` | Infers protocol purpose, partitions modalities, and detects therapeutic gaps for a stack. |
| **POST** | `/api/ai/chat/stream` | Server-Sent Events (SSE) streaming endpoint for multi-turn Copilot chat with reasoning telemetry and action cards. |
| **POST** | `/api/ai/chat` | Non-streaming multi-turn chat endpoint for REST clients. |
| **POST** | `/api/ai/tools/execute` | Executes deterministic internal pharmacology tools (catalog, CYP450, PBPK, GraphRAG subgraph, synergies). |
| **POST** | `/api/ai/optimize-protocol`| GraphRAG-guided protocol optimization endpoint. |

### 2. Pharmacology Lab & Collision Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/health` | System health check and service status. |
| **GET** | `/` | Serves the Pharmacology Lab & Collision Matrix dashboard. |
| **POST** | `/api/interactions/matrix` | Evaluates $N \times N$ collision matrix, syndrome alerts, organ burdens, and cumulative risk score. |
| **POST** | `/protocol` | Generates individualized protocols based on user goals, biometrics, and lab values. |

### 3. Biological Knowledge Graph & Neo4j Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/graph` | Serves the Interactive Biological Knowledge Graph view. |
| **GET** | `/graph-data` | Returns 6-tier network graph nodes, edges, cascade simulations, and multi-ligand receptor occupancy. |
| **GET** | `/graph-path` | Calculates shortest biological path and cross-talk connections between two nodes. |
| **POST** | `/api/graph/cypher` | Executes arbitrary Cypher queries against dedicated Neo4j graph database backend. |
| **POST** | `/api/graph/graphrag-context` | Extracts structured GraphRAG subgraph context and triples for LLM integration. |

### 4. Biophysical PBPK & PK/PD Simulation Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/compound/{key}` | Serves the deep-dive Compound Intelligence & PBPK profile page. |
| **POST** | `/api/pkpd/simulate` | Simulates continuous Bateman/2-compartment PBPK curves, tissue partitions ($K_p$), lysosomal trapping, and Hill PD. |
| **GET** | `/api/compounds/{key}/pkpd` | Returns extracted quantitative PK parameters ($V_d, k_e, k_a, CL, f_u, K_p$) and PD affinities ($K_i, IC_{50}$). |

### 5. Catalog Administration & Data Ingestion Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/admin` | Serves the Catalog Administration and Ingestion interface. |
| **GET** | `/catalog` | Paginated catalog listing with multi-token filtering. |
| **GET** | `/catalog/{key}` | Retrieves full pharmacology profile with write-through cache status. |
| **POST** | `/catalog` | Creates or updates a compound record. |
| **DELETE**| `/catalog/{key}` | Deletes a compound record from the catalog database. |
| **GET** | `/api/compounds/search?q={query}` | Fast typeahead search across keys, brand names, drug classes, and indications. |
| **POST** | `/api/compounds/{key}/enrich-full` | Executes full live enrichment across PubChem, ChEMBL, UniProt, Reactome, and OpenFDA. |
| **POST** | `/api/enrichment/jobs` | Submits long-running multi-source enrichment batch job to async worker queue. |
| **GET** | `/api/enrichment/jobs/{job_id}` | Retrieves status, progress, logs, and results for a specific enrichment job. |
| **WS** | `/ws/enrichment` | Global WebSocket endpoint streaming real-time background job events and step logs. |

---

## Setup & Local Execution

### Prerequisites
- Python 3.10+ installed on your system.

### One-Click Launch (Windows)
Double-click `start.bat` or run:
```bat
start.bat
```
*(Automatically checks for Neo4j, activates `.venv`, starts the server on `http://127.0.0.1:8000`, and opens your default browser).*

### PowerShell Launch
```powershell
.\start.ps1
```

### Python Launcher Script
```bash
# Start server with hot-reload and open browser automatically
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
# Run all automated tests
pytest

# Run tests with verbose output
pytest -v

# Run the Biophysical PBPK & ODE test suite
pytest tests/test_biophysical_pbpk_and_odes.py -v

# Run the AI Copilot & Streaming test suite
pytest tests/test_ai_copilot_suite.py -v
```

---

## License & Disclaimer

*Disclaimer: `healthAI` is a computational pharmacology research and simulation engine intended for educational, research, and informational purposes. It is not a substitute for professional medical advice, diagnosis, or clinical treatment.*
