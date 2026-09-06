# HealthAI // Next-Generation Clinical Pharmacology & Network Biology Platform

> **An interactive, science-driven clinical pharmacology workbench, biophysical small-molecule PBPK & biologic TMDD simulation suite, 6-tier biological causal network mapper, RxNorm combination drug decomposer, botanical phytochemical resolver, and multi-provider autonomous AI clinical copilot.**

---

## 🌟 Executive Overview & Mission

`HealthAI` transforms complex clinical pharmacology, molecular biology, and pharmacokinetics into an intuitive, visually rich, and interactive software experience. 

Traditional drug interaction checkers rely on static, binary pairwise lookup tables that fail to capture the multi-dimensional reality of human biology. In contrast, **HealthAI models the human body as a dynamic, interconnected network of biological systems**. It evaluates how multiple compounds, peptides, supplements, biologics, and active metabolites simultaneously compete for metabolic enzymes, saturate cellular transporters, modulate intracellular signaling cascades, and shift systemic biomarkers in response to a patient's individual genetic and laboratory profile.

Whether you are designing a targeted longevity regimen, red-teaming an advanced peptide or biologic protocol, decomposing OTC/Rx combination pharmaceuticals, auditing polypharmacy risks, or exploring molecular pharmacology pathways, HealthAI provides immediate visual clarity, quantitative biophysical simulations, and autonomous clinical intelligence.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       HEALTHAI ECOSYSTEM                                         │
├───────────────────────────────┬──────────────────────────────────┬───────────────────────────────┤
│    🔬 INTERACTIVE WORKBENCH   │     🌐 6-TIER KNOWLEDGE GRAPH    │    🧪 BIOPHYSICAL PBPK & TMDD │
│  • N x N Collision Matrix     │  • Cytoscape.js Network Canvas   │  • 1 & 2-Compartment Small-Mol│
│  • Multi-Agent Syndrome Alert │  • Multi-Ligand Net Occupancy    │  • Biologic TMDD & FcRn Model │
│  • Biometric Lab Calibration  │  • Shortest Regulatory Paths     │  • Subcutaneous Depot Kinetics│
│  • Circadian Protocol Engine  │  • Multi-Temporal Ripple Sim     │  • Rodgers-Rowland Tissue Kp  │
│  • Modality Filter (10 Tiers) │  • GraphRAG Causal Triples       │  • Dynamic DDI AUC Surges     │
│  • RxNorm Drug Decomposition  │  • Neo4j & NetworkX Fallback     │  • Sigmoidal Hill Emax PD     │
│  • Progressive SSE Streaming  │  • IUPHAR Target Annotations     │  • Target Occupancy (TO%)     │
├───────────────────────────────┴──────────────────────────────────┴───────────────────────────────┤
│                    🤖 AUTONOMOUS AI COPILOT & MULTI-PROVIDER REASONING ENGINE                    │
│    [🏛️ Protocol Architect]   [🛡️ Risk Auditor]   [🔬 Pharmacology Tutor]   [🩸 Labs Analyst]     │
│    • Live SSE Telemetry   • ReAct Scratchpad   • 1-Click Interactive Action Cards ("Apply")      │
│    • Local CUDA (RTX 5090) / OpenAI / OpenRouter / Ollama • Zero-Persistence Dynamic Key Auth   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📑 Table of Contents

- [🧭 AI Agent & Developer Architecture Map (`PROJECT_MAP.md`)](PROJECT_MAP.md)
- [✨ Key Features at a Glance](#-key-features-at-a-glance)
- [🖥️ User Experience & Interactive Walkthroughs](#️-user-experience--interactive-walkthroughs)
  - [1. Pharmacology Lab & Collision Matrix Workbench (`/`)](#1-pharmacology-lab--collision-matrix-workbench-)
  - [2. Autonomous AI Clinical Copilot & Multi-Provider Settings (`Ctrl+K` / Floating Drawer)](#2-autonomous-ai-clinical-copilot--multi-provider-settings-ctrlk--floating-drawer)
  - [3. Interactive Biological Knowledge Graph & Cascade Engine (`/graph`)](#3-interactive-biological-knowledge-graph--cascade-engine-graph)
  - [4. Compound Intelligence & Biophysical PBPK/TMDD Dossier (`/compound/{key}`)](#4-compound-intelligence--biophysical-pbpktmdd-dossier-compoundkey)
  - [5. Master Catalog Administration & Real-Time Data Ingestion (`/admin`)](#5-master-catalog-administration--real-time-data-ingestion-admin)
- [🧬 End-to-End User Story: Optimizing a Complex Protocol](#-end-to-end-user-story-optimizing-a-complex-protocol)
- [⚙️ How HealthAI Works (Under the Hood)](#️-how-healthai-works-under-the-hood)
  - [Pharmacokinetic (PK) & Transporter Collision Engine](#pharmacokinetic-pk--transporter-collision-engine)
  - [Biophysical Small-Molecule PBPK & Continuous ODE Mathematics](#biophysical-small-molecule-pbpk--continuous-ode-mathematics)
  - [Biologic PK/PD, Target-Mediated Drug Disposition (TMDD) & FcRn Salvage Kinetics](#biologic-pkpd-target-mediated-drug-disposition-tmdd--fcrn-salvage-kinetics)
  - [RxNorm Relational Graph Decomposition & Multi-Ingredient Resolution](#rxnorm-relational-graph-decomposition--multi-ingredient-resolution)
  - [NCBI MeSH Botanical & Phytochemical Resolution Engine](#ncbi-mesh-botanical--phytochemical-resolution-engine)
  - [Substance Modality Taxonomy (10-Tier Classification)](#substance-modality-taxonomy-10-tier-classification)
  - [High-Throughput In-Memory Index & Progressive Dual-Tier SSE Search](#high-throughput-in-memory-index--progressive-dual-tier-sse-search)
  - [6-Tier Biological Network Ontology & GraphRAG](#6-tier-biological-network-ontology--graphrag)
  - [Pharmacogenomics (PGx) & Biometric Lab Normalization](#pharmacogenomics-pgx--biometric-lab-normalization)
  - [Multi-Tier Live Biomedical Enrichment & IUPHAR Integration](#multi-tier-live-biomedical-enrichment--iuphar-integration)
- [🚀 Quick Start & Local Setup](#-quick-start--local-setup)
  - [Pre-Seeding Essential Therapeutics (`scripts/seed_top_compounds.py`)](#pre-seeding-essential-therapeutics-scriptsseed_top_compoundspy)
- [⚡ LLM Inference Configuration (Local GPU & Cloud Providers)](#-llm-inference-configuration-local-gpu--cloud-providers)
  - [Local Hardware-Accelerated Server (RTX 5090 / CUDA)](#local-hardware-accelerated-server-rtx-5090--cuda)
  - [Local Ollama / vLLM & Custom OpenAI-Compatible Endpoints](#local-ollama--vllm--custom-openai-compatible-endpoints)
  - [Cloud Providers (OpenRouter, OpenAI, Groq) & Dynamic Key Validation](#cloud-providers-openrouter-openai-groq--dynamic-key-validation)
- [📡 API & WebSockets Reference](#-api--websockets-reference)
- [🧪 Testing & Quality Assurance](#-testing--quality-assurance)
- [📜 License & Medical Disclaimer](#-license--medical-disclaimer)

---

## ✨ Key Features at a Glance

| Feature Area | User Experience & Capabilities |
| :--- | :--- |
| **Interactive Collision Matrix** | Color-coded $N \times N$ interaction grid with instant modal deep-dives into CYP450 competition, MBI suicide inactivation, transporter saturation, and displacement surges. |
| **RxNorm Combination Decomposer** | Deterministically traverses NLM RxNorm and DailyMed SPL to decompose multi-ingredient brand drugs (e.g., *DayQuil*, *NyQuil*, *Entresto*, *Excedrin*) into active pharmacological chemical entities with stripped salt forms. |
| **Botanical & MeSH Resolver** | Resolves crude herbs and adaptogens (*Ashwagandha*, *Kratom*, *Kava*, *Turmeric*, *Rhodiola*, *Berberine*) against NCBI MeSH Tree B01 to identify primary active phytochemicals and their specific receptor targets. |
| **Substance Modality Taxonomy** | Automated 10-tier modality classification (*Small Molecule*, *Biologic / mAb*, *Peptide*, *Combination Drug*, *Botanical*, *Mineral / Electrolyte*, etc.) backed by NCATS G-SRS, ChEMBL, and FDA EPC. |
| **Biologic PK/PD & TMDD Simulator** | Dedicated biophysical modeling for monoclonal antibodies and therapeutic peptides featuring Target-Mediated Drug Disposition (TMDD), neonatal FcRn salvage recycling ($t_{1/2} \approx 14-28\text{d}$), and subcutaneous absorption. |
| **Progressive SSE Streaming Search** | Dual-tier search: instantaneous sub-millisecond local in-memory index hits streamed immediately via Server-Sent Events, followed seamlessly by live upstream registry query candidates. |
| **Multi-Provider AI Copilot** | Multi-persona reasoning drawer (Architect, Auditor, Tutor, Labs) with real-time SSE streaming, tool telemetry, interactive **Action Cards**, and customizable LLM backends (Local CUDA, Ollama, OpenRouter, OpenAI). |
| **Multi-Agent Syndrome Classifiers** | Continuous detection of life-threatening emergent clinical syndromes: Serotonin Toxicity, QTc Prolongation ($hERG$), Renal "Triple Whammy", GABAergic CNS Depression, and Sympathomimetic Crises. |
| **Dynamic Lab & PGx Calibration** | Calibrate predictions using 20+ laboratory markers (eGFR, ALT/AST, electrolytes, vitals, lipids) and pharmacogenomic phenotypes (`CYP2D6`, `CYP2C19`, `CYP3A4`, `SLCO1B1`, `COMT`). |
| **6-Tier Biological Knowledge Graph** | Cytoscape.js canvas mapping interactions from Compounds $\rightarrow$ Molecular Targets $\rightarrow$ Intracellular Cascades $\rightarrow$ Organ Systems $\rightarrow$ Biomarkers $\rightarrow$ Phenotypes. |
| **Multi-Temporal Cascade Simulator** | Simulate biological signal propagation and homeostatic adaptation across Acute (hours), Sub-Acute (weeks), and Chronic (months) time horizons. |
| **Continuous PBPK & ODE Simulator** | 1- and 2-Compartment Open Models with Rodgers-Rowland tissue partitioning ($K_p$ for Brain, Liver, Kidney, Muscle, Adipose), lysosomal trapping, and Sigmoidal Hill $E_{max}$ pharmacodynamics. |
| **Stack Intent & Modality Parser** | Automatically identifies the user's primary protocol intent, partitions compounds into therapeutic modalities, flags uncompensated physiological burdens, and derives evidence-graded co-factors. |
| **Multi-Registry Biomedical Enrichment** | On-demand and batch automated data fetching from NCBI PubChem, EMBL-EBI ChEMBL, IUPHAR Guide to PHARMACOLOGY, UniProt, Reactome, NIH RxNorm, OpenFDA, and Europe PMC. |

---

## 🖥️ User Experience & Interactive Walkthroughs

HealthAI is built with modern, accessible, dark-mode ergonomics, glassmorphic surfaces, responsive controls, and instantaneous client-side feedback.

---

### 1. Pharmacology Lab & Collision Matrix Workbench (`/`)

The primary command center where users assemble compound stacks, customize dosages, inspect pairwise collisions, review emergent clinical risks, and generate circadian administration schedules.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  HealthAI // PHARMACOLOGY LAB & COLLISION MATRIX WORKBENCH                         [ 👤 Patient Labs ] [ 🤖 Copilot ] │
├──────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────┤
│  💊 COMPOUND SELECTOR & ACTIVE STACK                 │  🛡️ CUMULATIVE RISK & ORGAN GAUGES                        │
│  [ Search compound, peptide, or brand name...      ] │  Health Index: 84/100 (MODERATE RISK)                     │
│                                                      │  ┌──────────┬──────────┬──────────┬──────────┬──────────┐ │
│  Active Compounds:                                   │  │ Hepatic  │  Renal   │ Cardiac  │ CNS Stim │ Sedative │ │
│  • Telmisartan     │ 40 mg   │ Oral  │ Morning       │  │  [Low]   │  [Mod]   │  [Low]   │  [None]  │  [None]  │ │
│  • Rosuvastatin    │ 10 mg   │ Oral  │ Bedtime       │  └──────────┴──────────┴──────────┴──────────┴──────────┘ │
│  • Curcumin Extract│ 1000 mg │ Oral  │ Morning       │  🚨 EMERGENT SYNDROME ALERTS:                             │
│  • Sildenafil      │ 25 mg   │ Oral  │ PRN           │  ⚠️ OATP1B1 / BCRP Transporter Inhibition (Piperine)      │
│  • Eplerenone      │ 25 mg   │ Oral  │ Morning       │  ⚠️ Additive Hyperkalemia Hazard (Telmisartan+Eplerenone) │
├──────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────┤
│  📊 INTERACTIVE N x N COLLISION MATRIX (Click any cell to inspect mechanism)                                      │
│                     [ Telmisartan ]     [ Rosuvastatin ]     [ Curcumin ]        [ Sildenafil ]    [ Eplerenone ] │
│  [ Telmisartan ]          ───                Neutral             Neutral         Synergistic BP    ⚡ Hyperkalemia │
│  [ Rosuvastatin ]       Neutral                ───          ⚠️ BCRP / OATP1B1       Neutral            Neutral    │
│  [ Curcumin ]           Neutral         ⚠️ BCRP / OATP1B1          ───              Neutral            Neutral    │
│  [ Sildenafil ]     Synergistic BP           Neutral             Neutral              ───              Neutral    │
│  [ Eplerenone ]     ⚡ Hyperkalemia           Neutral             Neutral            Neutral             ───      │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ⚡ STACK INTENT, MODALITY BREAKDOWN & EVIDENCE-GRADED CO-FACTORS                                                │
│  • Primary Inferred Intent: Cardiovascular Protection & Lipid Optimization                                        │
│  • Modalities: [Core RAAS Blockade] [HMGCR Statin Base] [Anti-Inflammatory Ancillary] [PDE5 Endothelial Support] │
│  • Missing Co-Factor Suggestion: Coenzyme Q10 (Ubiquinol 100-200mg) to mitigate statin-induced mitochondrial loss │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Key User Interactions:
- **Instant Typeahead Compound Search:** Search across generic names, brand names (e.g., *Micardis*, *Lipitor*, *Viagra*, *Ozempic*), or therapeutic classes.
- **Progressive Dual-Tier SSE Streaming Search:** High-speed in-memory prefix indexing yields local matches in <5ms, followed progressively by live candidates streamed from RxNorm, PubChem, and ChEMBL via Server-Sent Events.
- **Automatic Multi-Ingredient & Brand Decomposition:** Entering commercial combination products (e.g., *DayQuil*, *NyQuil*, *Entresto*, *Excedrin*) automatically traverses the RxNorm Concept Graph to decompose the product into its pure constituent active chemical entities and exact doses.
- **Substance Modality Filter:** Scope searches and views by therapeutic modality: *All Modalities*, *Small Molecules*, *Biologics / Monoclonal Antibodies*, *Peptides*, *Botanicals / Phytochemicals*, and *Minerals & Electrolytes*.
- **Pre-Built Starter Stacks:** One-click presets to immediately explore canonical stacks (*Longevity & Senolytics*, *Cognitive Nootropic Focus*, *Cardiovascular & Lipid Defense*, *Metabolic & Glycemic Control*, *Anabolic Body Composition*).
- **Interactive Collision Modal:** Clicking any intersection in the $N \times N$ matrix opens a modal detailing:
  - Exact biochemical mechanism (e.g., competitive binding, transporter saturation, enzyme induction).
  - Clinical severity badge (**Synergy** / **Neutral** / **Moderate** / **Severe**).
  - Specific metabolic pathways affected (`CYP3A4`, `SLCO1B1`, `UGT1A1`, `hERG`).
  - Actionable clinical mitigation strategies (e.g., dosage reduction, separated timing windows, formulation switches).
- **Patient Labs Drawer:** Slide out the biometric profile drawer to input 20+ laboratory biomarkers and PGx phenotypes, instantly watching the risk gauges and collision matrix dynamically recalibrate.

---

### 2. Autonomous AI Clinical Copilot & Multi-Provider Settings (`Ctrl+K` / Floating Drawer)

An always-available, conversational clinical intelligence agent grounded in deterministic pharmacological databases, continuous ODE simulations, and graph-causal triples—adhering to a strict **Zero-Bro-Science standard**.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  🤖 HEALTHAI CLINICAL COPILOT                                        [ ⚙️ Settings ] [ ⟳ Clear ] [✕ Close ]        │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  PROVIDER: [ ● Local CUDA (Qwen 3.8-27B) ]  [ Custom OpenAI / OpenRouter ]  Status: Connected (12ms)             │
│  PERSONA SELECTOR:                                                                                               │
│  [ 🏛️ Protocol Architect ]   [ 🛡️ Risk Auditor ]   [ 🔬 Pharmacology Tutor ]   [ 🩸 Biomarker & Labs Analyst ]    │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ACTIVE SYNCED STACK: [Telmisartan 40mg] [Rosuvastatin 10mg] [Curcumin 1000mg] [Eplerenone 25mg]                 │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  LIVE COPILOT REASONING TELEMETRY:                                                                               │
│  ⚡ Analyzing multi-hop GraphRAG context & CYP/transporter saturation curves...                                  │
│                                                                                                                  │
│  ### Executive Assessment                                                                                        │
│  Your regimen provides robust dual-pathway aldosterone and RAAS suppression alongside lipid-lowering therapy.   │
│  However, the current configuration presents two critical pharmacokinetic and physiological liabilities:         │
│                                                                                                                  │
│  1. **OATP1B1 Transporter Blockade:** The piperine within standard Curcumin extracts inhibits `SLCO1B1` hepatic  │
│     uptake, causing up to a 2.4x surge in plasma Rosuvastatin AUC, elevating myopathy risk.                     │
│  2. **Compound Potassium Retention:** Concurrent AT1 blockade (Telmisartan) and mineralocorticoid receptor       │
│     antagonism (Eplerenone) in the presence of baseline Potassium 4.8 mEq/L poses a severe hyperkalemia risk.    │
│                                                                                                                  │
│  ### Recommended Protocol Modifications (Action Card):                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ ⚡ PROPOSED PROTOCOL REVISION                                                                              │  │
│  │ • ~ Modify: Eplerenone (25 mg -> 12.5 mg Daily Oral)                                                       │  │
│  │ • ~ Replace: Curcumin Extract (w/ Piperine) -> Liposomal Curcumin (500 mg, No Piperine)                    │  │
│  │ • + Add: Coenzyme Q10 / Ubiquinol (100 mg Daily Oral, Morning)                                             │  │
│  │                                                                                                            │  │
│  │ [ ✓ Apply Changes to Workbench Stack ]                                                                     │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  [ Ask a clinical or pharmacological question... (Press Enter to send)                            ] [ Send ]     │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Copilot Personas & Unique Roles:
1. **🏛️ Protocol Architect (`architect`):**
   - Specializes in circadian scheduling, split dosing, half-life alignment, and evidence-based protective co-factor pairings.
   - Separates daily oral timing from weekly injectable depot schedules.
2. **🛡️ Risk & Conflict Auditor (`auditor`):**
   - Forensically audits the stack for toxicological vulnerabilities, transporter saturation, suicide enzyme inactivation, and acute syndrome triggers.
3. **🔬 Pharmacology Tutor (`tutor`):**
   - Delivers PhD-level molecular breakdowns of receptor binding kinetics ($K_i, K_d, IC_{50}, EC_{50}$), G-protein coupling ($G_s, G_i, G_q$), second-messenger cascades (cAMP, $IP_3/DAG$, PKA/PKC), and gene transcription pathways (Nrf2/ARE, AMPK/SIRT1, mTORC1).
4. **🩸 Biomarker & Labs Analyst (`labs`):**
   - Correlates user blood panels with pharmacological clearance, flags anomalous biomarkers, and provides precise lab retesting timelines.

#### Multi-Provider LLM & Custom Endpoint Settings:
Clicking the settings gear (`⚙️`) in the Copilot header enables direct configuration of local or remote LLM providers:
- **Local Hardware-Accelerated Server:** Connects directly to local `llama-server` (e.g., `http://127.0.0.1:8080/v1` with CUDA/RTX 5090 acceleration).
- **Local & Self-Hosted Inference:** Fully compatible with Ollama (`http://localhost:11434/v1`), vLLM, LM Studio, or LocalAI.
- **Cloud Providers:** Direct support for OpenRouter (`https://openrouter.ai/api/v1`), OpenAI (`api.openai.com/v1`), Groq, or custom proxies.
- **Live Endpoint Health Checks (`POST /api/ai/validate-key`):** Verifies base URL reachability, queries accessible models, and validates API keys with live ping latency.
- **Zero Server-Side Key Persistence:** User API keys and custom endpoints reside exclusively in browser client-side storage and are transmitted securely on demand via `X-User-API-Key`, `X-User-Base-URL`, and `X-User-Model` HTTP headers.

#### Dynamic Action Cards (`<action_card type="stack_diff">`):
Whenever the AI Copilot suggests additions, dosage titrations, or compound substitutions, it generates an interactive **Action Card**. Users can review the exact diff and click **"Apply Changes to Workbench Stack"** to update their workbench in real time without manual re-entry.

---

### 3. Interactive Biological Knowledge Graph & Cascade Engine (`/graph`)

A visual 6-tier network canvas powered by Cytoscape.js that reveals the deep biological mechanisms, direct molecular targets, and downstream phenotypic ripple effects of your protocol.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  HealthAI // 6-TIER BIOLOGICAL KNOWLEDGE GRAPH & CASCADE SIMULATOR                                 [ Fullscreen ]│
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  CANVAS CONTROLS: [ Layout: Hierarchical | Force-Directed ]  [ Search Node: _____________ ] [ Export PNG/JSON ]  │
│  SIMULATION TIMELINE:  (●) Acute (0-24h)     ( ) Sub-Acute (1-4 Weeks)     ( ) Chronic (Months Adaptation)        │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│   [ Tier 0: Compounds ]        [ Telmisartan ]                [ Enzalutamide ]            [ Sildenafil ]         │
│                                       │ AGONIZES                     │ INHIBITS                  │ INHIBITS      │
│                                       ▼                              ▼                           ▼               │
│   [ Tier 1: Targets ]             [ AGTR1 ]                      [ AR Rec ]                  [ PDE5A ]           │
│                                       │ ANTAGONIZES                  │ SUPPRESSES                │ ELEVATES      │
│                                       ▼                              ▼                           ▼               │
│   [ Tier 2: Cascades ]       [ RAAS Vasoconstriction ]      [ Androgen Translocation ]     [ cGMP / PKG ]        │
│                                       │ INHIBITS                     │ DOWNREGULATES             │ STIMULATES    │
│                                       ▼                              ▼                           ▼               │
│   [ Tier 3: Physiology ]     [ Vascular Endothelium ]       [ Prostate Epithelium ]     [ Smooth Muscle Relax ]  │
│                                       │ DILATES                      │ INHIBITS GROWTH           │ ENHANCES FLOW │
│                                       ▼                              ▼                           ▼               │
│   [ Tier 4: Biomarkers ]     [ Systolic/Diastolic BP ]      [ Serum PSA ]               [ eGFR Filtration ]      │
│                                       │ REDUCES                      │ LOWERS                    │ PRESERVES     │
│                                       ▼                              ▼                           ▼               │
│   [ Tier 5: Outcomes ]       [ Cardiovascular Defense ]     [ Anti-Proliferation ]      [ Renal Protection ]     │
│                                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  NODE INSPECTOR PANEL: (Selected: AGTR1)                                                                         │
│  • Ontological Tier: Tier 1 (Molecular Target) | Target Type: GPCR (Gq-coupled)                                  │
│  • Binding Ligands in Stack: Telmisartan (Ki: 3.7 nM, Pure Antagonist, 94.2% Occupancy)                          │
│  • Net Receptor State: 94.2% Blockade (Dominated by Antagonist) | Downstream: Suppressed IP3/DAG & Vasodilation  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Graph Features & Exploration:
- **Hierarchical 6-Tier Color Coding:** Instant visual distinction between Compounds (Cyan), Receptors & Enzymes (Red/Amber), Signaling Cascades (Purple), Organ Physiology (Sky Blue), Biomarkers (Emerald), and Clinical Outcomes (Rose).
- **Multi-Ligand Receptor Occupancy:** If multiple stack items bind the same receptor (e.g., competing agonists and antagonists), the engine computes exact competitive binding equilibrium and displays the net activation status.
- **Shortest Regulatory Pathfinding (`/graph-path`):** Select any two biological entities to discover intermediate cross-talk connections, feedback loops, and signaling conduits.
- **Multi-Temporal Cascade Simulator:** Toggle between Acute (immediate receptor kinetics), Sub-Acute (transcriptional changes and enzyme induction), and Chronic (organ remodeling and receptor desensitization).
- **Neo4j & GraphRAG Integration:** Direct graph traversal backed by Neo4j Cypher queries or fast in-memory NetworkX multigraph fallback.

---

### 4. Compound Intelligence & Biophysical PBPK/TMDD Dossier (`/compound/{key}`)

An in-depth scientific dossier and continuous-time pharmacokinetic/pharmacodynamic simulation suite for both small-molecule pharmaceuticals and large-molecule biologics.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  COMPOUND DOSSIER: Telmisartan (CAS: 144701-48-4 | InChIKey: RMMXLAYQGBLRQ-UHFFFAOYSA-N)                         │
│  Class: ARB / AT1 Antagonist | Bioavailability: 42-58% | Elimination Half-Life: ~24.0 hours | LogP: 6.66        │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  📈 CONTINUOUS-TIME PBPK & PK/PD SIMULATION (2-Compartment Open Model with Tissue Partitioning)                  │
│                                                                                                                  │
│   Plasma & Tissue Conc (ng/mL)                                                                                   │
│   1200 ┤        ╭───╮ (Peak Cmax: 1,120 ng/mL at Tmax: 1.8h)                                                     │
│   1000 ┤       ╭╯   ╰──────────╮                                                                                 │
│    800 ┤     ╭─╯               ╰──────────────────╮  Adipose Tissue (Kp = 3.4)                                   │
│    600 ┤    ╭╯                                    ╰───────────────────── Liver Tissue (Kp = 4.2)                 │
│    400 ┤   ╭╯                                                           Plasma Concentration                     │
│    200 ┤  ╭╯                                                            Brain (Kp = 0.12, BBB Restricted)        │
│      0 ┼──┴──────────────────────────────────────────────────────────── Time (0 to 24 Hours)                     │
│        0    2    4    6    8   10   12   14   16   18   20   22   24                                              │
│                                                                                                                  │
│   [ Steady-State AUC0-tau: 9,840 ng·h/mL ]  [ Peak-to-Trough Fluctuation (PTF): 1.18 ]  [ Clearance: 0.11 L/h/kg ]│
│   [ Rodgers-Rowland Kp: Liver 4.2 │ Adipose 3.4 │ Kidney 2.8 │ Muscle 1.1 │ Brain 0.12 (Low BBB Penetration) ]   │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ⚡ DYNAMIC CO-ADMINISTERED DDI SIMULATION & AUC RATIO (AUCR) SHIFTS                                              │
│  • Baseline Clearance: 8.20 L/h | When co-administered with CYP3A4 / P-gp Inhibitors:                           │
│  • Projected Exposure Ratio (AUCR): 1.42x (+42% systemic AUC elevation)                                          │
│  • Effective Half-Life: Extended from 24.0 hours -> 34.1 hours                                                   │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  🎯 SIGMOIDAL Emax PHARMACODYNAMICS & RECEPTOR OCCUPANCY                                                         │
│  • Target Receptor: AGTR1 (Ki = 3.7 nM) | EC50: 12.4 ng/mL | Hill Coefficient (γ): 1.4                           │
│  • Peak Receptor Occupancy at Cmax: 94.2% | Target Biological Effect: Sustained RAAS Vasodilation (E = 92.8%)   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Analytical Dossier Tools:
- **Dual Biophysical PK Engines:**
  - **Small Molecules:** Classical 1- and 2-compartment open models with Rodgers-Rowland tissue partitioning ($K_p$) across Brain, Liver, Kidney, Muscle, and Adipose, plus lysosomal ion-trapping.
  - **Biologics & Monoclonal Antibodies (`biologic_pkpd_engine.py`):** 2-compartment vascular-interstitial model with lymphatic convective transport, Target-Mediated Drug Disposition (TMDD) with capacity-limited receptor clearance ($V_{max}, K_m$), endothelial neonatal Fc Receptor ($FcRn$) salvage recycling ($t_{1/2} \approx 14-28\text{ days}$), and Target Occupancy ($TO\%$) saturation dynamics.
- **Subcutaneous (SC) Depot Kinetics:** Models slow lymphatic absorption and incomplete bioavailability ($F_{sc} \approx 65\%$) vs. instantaneous IV bolus.
- **Lysosomal Ion-Trapping Calculator:** Computes subcellular sequestration based on Henderson-Hasselbalch basic $pK_a$ partitioning across cytosol (pH 7.2) and acidic lysosomes (pH 4.8).
- **Dynamic DDI Simulation:** Add co-administered inhibitors or inducers to instantly simulate AUC surges, half-life prolongation, and clearance attenuation curves.
- **Population Uncertainty Bands:** Visualizes $P_{10}, P_{25}, P_{50}, P_{75}, P_{90}$ population variance confidence intervals.
- **1-Click Live Multi-Source Re-Enrichment:** Refresh molecular weights, SMILES, target affinities ($K_i, IC_{50}$), and FDA labeling directly from live upstream APIs.

---

### 5. Master Catalog Administration & Real-Time Data Ingestion (`/admin`)

The administrative command center for managing, creating, editing, and batch-enriching the pharmacological database.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  HealthAI // CATALOG MANAGEMENT & DATA INGESTION SUITE                                                           │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  🔍 SEARCH CATALOG: [ Multi-token search (e.g., 'statin lipid cyp3a4')           ]   [ + Add New Compound ]     │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Compound Key    Canonical Name    Class / Modality      Tier       CYP Profile       Transporters    Actions    │
│  ────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│  telmisartan     Telmisartan       ARB / Vasodilator     Enriched   CYP2C9 (Sub)      OATP1B3, P-gp   [Edit] [↻] │
│  rosuvastatin    Rosuvastatin      HMG-CoA Reductase     Enriched   CYP2C9, 2C19      BCRP, OATP1B1   [Edit] [↻] │
│  curcumin        Curcumin          Polyphenol Supplement Curated    CYP3A4, 1A2 (Inh) BCRP, P-gp      [Edit] [↻] │
│  sildenafil      Sildenafil        PDE5 Inhibitor        Enriched   CYP3A4 (Sub)      P-gp            [Edit] [↻] │
│  semaglutide     Semaglutide       GLP-1 Receptor Agonist Seed      Non-CYP           Peptidase       [Edit] [↻] │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  📡 BACKGROUND ASYNC ENRICHMENT QUEUE (Connected via WebSocket: /ws/enrichment)                                  │
│  Job #108: Batch ChEMBL Bioactivity & Reactome Ingestion (Progress: [████████████████████░░░░] 82%)              │
│  • Ingested 142 target binding affinities (Ki / IC50) for 24 compounds...                                        │
│  • Enriched dynamic ROS/Redox literature citations via Europe PMC REST API...                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Administrative Features:
- **Full-Text Multi-Token Filtering:** Filter thousands of records simultaneously across compound keys, aliases, mechanism keywords, and target enzymes.
- **Compound Schema Editor:** Edit molecular weights, SMILES, 3D structures, primary and secondary molecular targets, Phase I/II clearance routes, and organ burden ratings.
- **Batch ETL Tooling:** Trigger asynchronous background pipelines for ChEMBL drug datasets, peptide databases, and OpenFDA adverse event tables.
- **Live WebSocket Progress Monitoring:** Monitor background ingestion workers with real-time progress bars, log streams, and error diagnostics.

---

## 🧬 End-to-End User Story: Optimizing a Complex Protocol

To illustrate how HealthAI operates in practice, consider a user assembling a multi-compound protocol for **Cardiovascular Health & Longevity**:

### 1. Protocol Assembly in the Lab
The user navigates to the **Pharmacology Lab** (`/`) and enters:
1. **Telmisartan** (40 mg Daily, Morning) — Angiotensin Receptor Blocker
2. **Rosuvastatin** (10 mg Daily, Bedtime) — HMG-CoA Reductase Inhibitor
3. **Curcumin Extract w/ Piperine** (1000 mg Daily, Morning) — Anti-inflammatory
4. **Eplerenone** (25 mg Daily, Morning) — Mineralocorticoid Receptor Antagonist
5. **Sildenafil** (25 mg As Needed) — PDE5 Inhibitor

### 2. Instant Collision Detection
The $N \times N$ matrix immediately flags two major conflicts:
- ⚠️ **Transporter Saturation:** Piperine strongly inhibits `BCRP (ABCG2)` and `OATP1B1 (SLCO1B1)`. This obstructs hepatic Rosuvastatin uptake, elevating systemic plasma concentrations by over 200% and increasing myotoxicity risk.
- ⚡ **Compounding Hyperkalemia:** Dual RAAS suppression via Telmisartan (AT1 blockade) and Eplerenone (aldosterone antagonism) causes additive renal potassium retention.

### 3. Patient Lab Calibration
The user opens the **Patient Profile Drawer** and inputs their latest blood work:
- **Serum Potassium ($K^+$):** $4.9 \text{ mEq/L}$ *(High-Normal)*
- **eGFR:** $76 \text{ mL/min/1.73m}^2$
- **Blood Pressure:** $122/78 \text{ mmHg}$

The system dynamically recalculates: the high-normal baseline potassium triggers an automatic escalation of the Telmisartan + Eplerenone collision to **High Severity Alert**.

### 4. Consulting the Autonomous AI Copilot (`Ctrl+K`)
The user opens the AI Copilot with the **Protocol Architect** persona. The Copilot executes GraphRAG queries, analyzes the collision matrix, and delivers:
- An explanation of why piperine-containing formulations are contraindicated alongside OATP1B1 statins.
- A warning regarding the high-normal baseline potassium under dual RAAS blockade.
- An interactive **Action Card** suggesting:
  1. *Switching* Curcumin to a piperine-free liposomal formulation.
  2. *Titrating* Eplerenone from 25 mg down to 12.5 mg daily.
  3. *Adding* Ubiquinol CoQ10 (100 mg) to preserve mitochondrial respiration during statin therapy.
  4. *Scheduling* Sildenafil separated by $\ge 4\text{ hours}$ from morning antihypertensives.

The user clicks **"Apply to Stack"**, and the entire workbench instantly updates to the optimized, risk-mitigated protocol.

---

## ⚙️ How HealthAI Works (Under the Hood)

While HealthAI prioritizes an intuitive user experience, its recommendations are powered by rigorous, deterministic biophysical and mathematical engines.

```
                                  ┌──────────────────────────────┐
                                  │   Patient Profile & Labs     │
                                  │ (eGFR, ALT, K+, PGx Phenos)  │
                                  └──────────────┬───────────────┘
                                                 │
┌──────────────────────────────┐                 ▼                 ┌──────────────────────────────┐
│     Compound Stack Input     │ ─────► ┌─────────────────┐ ◄───── │ Multi-Source Enrichment      │
│  (Molecules, Doses, Timing)  │        │  HealthAI Core  │        │ (PubChem, ChEMBL, EuropePMC) │
└──────────────────────────────┘        └────────┬────────┘        └──────────────────────────────┘
                                                 │
      ┌───────────────────────────┬──────────────┴──────────────┬───────────────────────────┐
      ▼                           ▼                             ▼                           ▼
┌──────────────────┐    ┌──────────────────┐          ┌──────────────────┐        ┌──────────────────┐
│ AI Copilot &     │    │ N x N Collision  │          │ 6-Tier Cascade   │        │ Biophysical PBPK │
│ ReAct Personas   │    │ & Risk Matrix    │          │ Knowledge Graph  │        │ Continuous ODEs  │
└──────────────────┘    └──────────────────┘          └──────────────────┘        └──────────────────┘
```

---

### Pharmacokinetic (PK) & Transporter Collision Engine

HealthAI's collision engine (`interaction_engine.py`) models metabolic and transport clearance dynamically:

1. **CYP450 Enzyme Kinetics:**
   - **Competitive Inhibition:** Calculates fractional clearance reductions using inhibitor concentration $I$ and inhibitor constant $K_i$:
     $$CL_{eff} = \frac{CL_{baseline}}{1 + \frac{I}{K_i}}$$
   - **Mechanism-Based Inactivation (MBI):** Models irreversible suicide inactivation parameterized by $k_{inact}$ and $K_I$.
   - **PXR / CAR Induction:** Simulates transcriptional upregulation of CYP3A4, CYP2C9, and CYP1A2.
2. **Phase II Conjugation:** Evaluates glucuronidation bottlenecks via `UGT1A1`, `UGT2B7`, and sulfotransferases.
3. **Membrane Transporter Competition:** Models uptake and efflux saturation across `P-gp (ABCB1)`, `BCRP (ABCG2)`, `OATP1B1/OATP1B3 (SLCO1B1/3)`, `OCT1/OCT2 (SLC22A1/2)`, and `OAT1/OAT3 (SLC22A6/8)`.
4. **Protein Binding Surges:** Flags dangerous free-fraction ($f_u$) surges when multiple highly plasma protein-bound molecules (>90% bound) compete for serum albumin binding sites.

---

### Biophysical Small-Molecule PBPK & Continuous ODE Mathematics

HealthAI's small-molecule PK/PD simulation engine (`pkpd_engine.py`) employs multi-compartment continuous differential equations:

1. **2-Compartment Open Pharmacokinetics:**
   Models rapid distribution ($\alpha$) and terminal elimination ($\beta$) phases:
   $$C(t) = \frac{D \cdot k_a}{V_d (k_a - k_e)} \left( e^{-k_e t} - e^{-k_a t} \right)$$
   $$C_{2-comp}(t) = A \cdot e^{-\alpha t} + B \cdot e^{-\beta t}$$

2. **Rodgers-Rowland & Poulin-Theil Tissue Partitioning ($K_p$):**
   Calculates tissue-to-plasma partition coefficients based on molecular lipophilicity ($\log P$), acid-base ionization ($pK_a$), fractional unbound state ($f_u$), and tissue water/neutral lipid compositions:
   $$K_p = \frac{C_{tissue}}{C_{plasma}}$$
   Evaluated for **Brain**, **Liver**, **Kidney**, **Muscle**, and **Adipose** tissues.

3. **Henderson-Hasselbalch Lysosomal Sequestration:**
   Basic lipophilic compounds accumulate inside acidic organelles ($pH_{lyso} \approx 4.8$) relative to the cytosol ($pH_{cyto} \approx 7.2$):
   $$R_{lyso} = \frac{1 + 10^{(pK_a - pH_{lyso})}}{1 + 10^{(pK_a - pH_{cyto})}}$$

4. **Sigmoidal $E_{max}$ Hill Pharmacodynamics:**
   Translates dynamic biophysical tissue concentration into receptor occupancy and clinical efficacy:
   $$E(C) = E_0 + \frac{E_{max} \cdot C^\gamma}{EC_{50}^\gamma + C^\gamma}$$

---

### Biologic PK/PD, Target-Mediated Drug Disposition (TMDD) & FcRn Salvage Kinetics

For monoclonal antibodies (mAbs) and large therapeutic peptides, classical hepatic CYP clearance and small-molecule lipophilic partitioning equations do not apply. HealthAI's biologic engine (`biologic_pkpd_engine.py`) models macromolecular disposition:

1. **2-Compartment Vascular-Interstitial Disposition:**
   Biologics distribute primarily into vascular blood volume ($V_1 \approx 45\text{ mL/kg}$) and interstitial fluid ($V_2 \approx 40\text{ mL/kg}$), with lymphatic convective transport ($Q \approx 0.6\text{ L/day}$):
   $$\frac{dC_1}{dt} = \frac{\text{Input}(t)}{V_1} - \frac{CL_{lin}}{V_1} C_1 - \frac{V_{max} \cdot C_1}{V_1 (K_m + C_1)} - \frac{Q}{V_1} C_1 + \frac{Q}{V_1} C_2$$
   $$\frac{dC_2}{dt} = \frac{Q}{V_2} C_1 - \frac{Q}{V_2} C_2$$

2. **Target-Mediated Drug Disposition (TMDD):**
   At low concentrations, biologics undergo rapid capacity-limited clearance via target receptor internalization ($V_{max}, K_m$). At high concentrations, target receptors saturate, and elimination transitions to linear zero/first-order clearance ($CL_{lin} \approx 0.25\text{ L/day}$).

3. **Neonatal Fc Receptor ($FcRn$) Endothelial Salvage:**
   IgG antibodies bind endothelial $FcRn$ in acidic endosomes ($pH \approx 6.0$), recycling them back into systemic circulation rather than lysosomal catabolism—reproducing their characteristic extended terminal half-life ($t_{1/2} \approx 14-28\text{ days}$).

4. **Subcutaneous (SC) vs. Intravenous (IV) Depot Kinetics:**
   Subcutaneous administration undergoes slow lymphatic convective uptake ($k_a \approx 0.015\text{ h}^{-1}$) with delayed $T_{max}$ (48-72 hours) and incomplete bioavailability ($F_{sc} \approx 65\%$):
   $$\frac{d(\text{Depot})}{dt} = -k_a \cdot \text{Depot}, \quad \text{Input}(t) = k_a \cdot \text{Depot}(t) \cdot F_{sc}$$

5. **Dynamic Target Occupancy ($TO\%$):**
   $$\text{TO}\% = \frac{C_1}{K_d + C_1} \times 100\%$$

---

### RxNorm Relational Graph Decomposition & Multi-Ingredient Resolution

Patients and clinicians frequently search using commercial brand names or OTC combination products containing multiple active pharmaceutical ingredients. HealthAI's decomposer (`rxnorm_graph_decomposer.py`) prevents incomplete safety audits:

1. **NLM RxNorm Relational Concept Graph Traversal:**
   Resolves branded products (*Entresto*, *DayQuil*, *NyQuil*, *Excedrin*, *Suboxone*, *Adderall*) by traversing `has_ingredient` (tty=IN) and `has_precise_ingredient` (tty=PIN) edges.
2. **FDA DailyMed Structured Product Label (SPL) Cross-Referencing:**
   Extracts active moieties and unit strengths directly from official SPL manufacturer filings.
3. **Active Moiety Normalization:**
   Deterministically strips salt counter-ions (`hydrochloride`, `maleate`, `succinate`, `tartrate`, `fumarate`, `besylate`) and FDA 4-letter biosimilar suffixes (`-pmph`, `-adaz`, `-bwwd`) to isolate the true pharmacological chemical entity for collision analysis.

---

### NCBI MeSH Botanical & Phytochemical Resolution Engine

Crude botanical and herbal extracts cannot be evaluated as single monolithic molecules. HealthAI's botanical resolver (`botanical_resolver.py`) resolves natural compounds into their active phytochemical profiles:

1. **NCBI MeSH Tree B01 Botanical Taxonomy:**
   Queries the National Library of Medicine Medical Subject Headings (MeSH) Tree B01 (Organisms / Plants) to validate authoritative plant species (*Withania somnifera*, *Mitragyna speciosa*, *Piper methysticum*, *Curcuma longa*, *Rhodiola rosea*).
2. **PubChem Phytochemical Constituent Unbundling:**
   Extracts primary bioactive chemical constituents (e.g., *Ashwagandha* $\rightarrow$ Withaferin A & Withanolide D; *Kava* $\rightarrow$ Kavain & Dihydromethysticin; *Turmeric* $\rightarrow$ Curcuminoids & Piperine).
3. **Multi-Constituent Collision Integration:**
   Feeds each constituent directly into the $N \times N$ collision matrix, revealing herb-drug interactions (e.g., piperine OATP1B1 inhibition, kava CYP2E1 competition, St. John's Wort P-gp induction).

---

### Substance Modality Taxonomy (10-Tier Classification)

Every substance in HealthAI is deterministically categorized into a 10-tier pharmacological modality taxonomy (`modality_resolver.py`):

| Modality Class | Identifier | Authoritative Source Registries | Clinical / Kinetic Profile |
| :--- | :--- | :--- | :--- |
| **Small Molecule** | `small_molecule` | ChEMBL, PubChem, DailyMed | CYP/Transporter clearance, Rodgers-Rowland $K_p$ tissue distribution. |
| **Biologic / mAb** | `biologic_antibody` | NCATS G-SRS, ChEMBL Biotherapeutics | Vascular-interstitial 2-comp kinetics, TMDD, endothelial FcRn recycling. |
| **Peptide** | `peptide` | IUPHAR Guide to PHARMACOLOGY, UniProt | Proteolytic degradation, receptor desensitization, non-CYP clearance. |
| **Combination Drug** | `combination_drug` | NLM RxNorm Graph, DailyMed SPL | Multi-active formulations decomposed into discrete chemical entities. |
| **Botanical / Natural** | `botanical_natural` | NCBI MeSH Tree B01, PubChem | Crude botanicals decomposed into primary bioactive phytochemicals. |
| **Mineral / Electrolyte** | `mineral_electrolyte` | PubChem Periodic System, DailyMed | Renal electrolyte clearance, serum osmolality and cardiac conduction. |
| **Radiopharmaceutical** | `radiopharmaceutical` | NCATS G-SRS, DailyMed | Targeted radionuclide decay kinetics and radiation dosimetry. |
| **Cell / Gene Therapy** | `cell_gene_therapy` | FDA CBER Registries, G-SRS | Transduction kinetics, persistent vector expression, immunogenicity. |
| **Vaccine** | `vaccine` | FDA CBER, DailyMed | Antigen presentation kinetics, adjuvant immune cascade activation. |
| **Unknown / Unclassified**| `unknown` | Heuristic Fallback | Dynamically assigned pending upstream registry curation. |

---

### High-Throughput In-Memory Index & Progressive Dual-Tier SSE Search

To deliver instantaneous search across thousands of compounds without stalling when external APIs are slow, HealthAI employs a dual-tier search engine (`fast_search_resolver.py` & `/api/compounds/search/stream`):

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        PROGRESSIVE DUAL-TIER SSE COMPOUND SEARCH                               │
├───────────────────────────────────────────────────┬────────────────────────────────────────────┤
│  ⚡ TIER 1: IN-MEMORY TRIE / PREFIX INDEX (<5ms)   │  🌐 TIER 2: ASYNC REGISTRY DISCOVERY (SSE) │
│  • Normalized tokenized prefix index              │  • Queries RxNorm, PubChem, ChEMBL, IUPHAR │
│  • Instant client-side candidate rendering        │  • Yields external matches progressively   │
│  • Deduplicated against active local catalog      │  • Auto-enriches on selection              │
└───────────────────────────────────────────────────┴────────────────────────────────────────────┘
```

1. **Sub-Millisecond Local Index (`GET /api/compounds/index`):** Pre-computed, tokenized prefix trie of all catalog entries and aliases loaded into client and server memory.
2. **Server-Sent Events Stream (`GET /api/compounds/search/stream`):** Delivers local hits immediately via `event: local_results`, then asynchronously searches external registries in the background, streaming newly discovered candidates via `event: external_results`.
3. **Modality & Indication Scoping:** Allows narrowing queries to specific modalities (e.g. `?modality=peptide&q=glp`) to instantly filter noise.

---

### 6-Tier Biological Network Ontology & GraphRAG

The biological knowledge graph organizes pharmacology into six interconnected ontological tiers:

```
[ Tier 0: Compounds ] ──► [ Tier 1: Targets ] ──► [ Tier 2: Signaling Cascades ]
                                                              │
[ Tier 5: Clinical Outcomes ] ◄── [ Tier 4: Biomarkers ] ◄────┴──► [ Tier 3: Organ Physiology ]
```

- **GraphRAG Subgraph Context Extraction (`/api/graph/graphrag-context`):** Extracts multi-hop causal triples and receptor competition dynamics formatted directly for LLM prompt context, ensuring zero AI hallucinations.
- **Neo4j Backend Support:** Full Cypher querying capabilities (`/api/graph/cypher`) backed by Neo4j, with seamless in-memory NetworkX multigraph fallback.

---

### Pharmacogenomics (PGx) & Biometric Lab Normalization

The PGx engine (`pgx_engine.py`) integrates CPIC / PharmGKB activity scores to individualize clearance rates:

| Gene / Target | Phenotype | Clearance Multiplier | Clinical Impact |
| :--- | :--- | :--- | :--- |
| **CYP2D6** | Poor Metabolizer (PM) | **0.15x** | Severe accumulation of 2D6 substrates; prodrug activation failure. |
| **CYP2D6** | Ultra-Rapid Metabolizer (UM) | **2.20x** | Rapid clearance; failure to reach therapeutic steady state. |
| **CYP2C19** | Poor Metabolizer (PM) | **0.20x** | Substantially reduced Phase I clearance of PPIs and anxiolytics. |
| **SLCO1B1** | `*5/*5` (Poor Transporter) | **0.35x** | Obstructed hepatic statin uptake; 2.5x plasma AUC surge; high myopathy hazard. |
| **COMT** | `Met/Met` (Slow Breakdown) | **0.60x** | Elevated baseline catecholamines; extreme sensitivity to stimulant anxiety. |

---

### Multi-Tier Live Biomedical Enrichment & IUPHAR Integration

HealthAI implements a robust 3-tier data enrichment architecture:
- **Tier 1 (Seed Cache):** Instant in-memory curated compound catalog.
- **Tier 2 (Relational SQLite Cache):** Local `healthai_catalog.db` database.
- **Tier 3 (Live Upstream REST APIs):** On-demand querying of **NCBI PubChem** (structures, 2D/3D coordinates), **EMBL-EBI ChEMBL** (binding affinities, $K_i, IC_{50}$), **IUPHAR / BPS Guide to PHARMACOLOGY** (peptides, GPCR receptor targets), **UniProt** (target identifiers), **Reactome** (canonical biological pathways), **NIH RxNorm**, **OpenFDA** (adverse events), and **Europe PMC** (dynamic literature ROS/redox mining).

---

## 🚀 Quick Start & Local Setup

### Prerequisites
- **Python 3.10+** installed.
- Modern web browser (Chrome, Edge, Firefox, Safari).

### One-Click Launch (Windows)
Double-click `start.bat` or run:
```bat
start.bat
```
*(Automatically sets up the environment, validates dependencies, launches the server at `http://127.0.0.1:8000`, and opens your default browser).*

### PowerShell Launch (Windows)
```powershell
.\start.ps1
```

### Manual Setup & Run (Linux / macOS / Windows)
```bash
# 1. Clone the repository
git clone https://github.com/zpitroda/healthAI.git
cd healthAI

# 2. Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 3. Install required dependencies
pip install -r requirements.txt

# 4. Start the application
python run_server.py --open-browser
```

Navigate to `http://127.0.0.1:8000` in your web browser.

### Pre-Seeding Essential Therapeutics (`scripts/seed_top_compounds.py`)
To warm the local SQLite database with 150+ essential medicines, peptides, and wellness compounds (with all target binding affinities and biophysical parameters cached locally):
```bash
python scripts/seed_top_compounds.py
```
*(Batch-enriches essential compounds via RxNorm, ChEMBL, PubChem, and MeSH concurrently with zero hardcoded approximations).*

---

## ⚡ LLM Inference Configuration (Local GPU & Cloud Providers)

HealthAI features a multi-provider inference architecture supporting both local hardware-accelerated GPUs and remote/cloud OpenAI-compatible endpoints.

### Local Hardware-Accelerated Server (RTX 5090 / CUDA)

HealthAI is pre-configured to interface seamlessly with local hardware-accelerated LLMs via `llama.cpp` / `llama-server`.

#### 1. Download the Recommended Model (Qwen 3.8-27B GGUF)
Run the multi-threaded resumable downloader:
```bash
python scripts/download_model.py
```
*(Downloads `Qwen3.8-27B-UD-Q6_K.gguf` directly to `models/` with 24 concurrent connection workers and automatic sha256 verification).*

#### 2. Start the Hardware-Accelerated Local Inference Server
Launch the pre-configured `llama-server` runner:

**Windows Batch:**
```bat
start_llama_server.bat
```

**PowerShell:**
```powershell
.\start_llama_server.ps1
```

##### Included GPU Optimizations:
- **Speculative Multi-Target Prediction (MTP):** `--spec-draft-mtp --spec-draft-n-max 2`
- **Flash Attention:** `-fa`
- **4-bit Quantized KV Cache:** `-ctk q4_0 -ctv q4_0`
- **Large Context Window:** `-c 65536` (64k context)
- **Auto-Connection:** HealthAI automatically detects and connects to the active LLM server on port `8080`.

### Local Ollama / vLLM & Custom OpenAI-Compatible Endpoints

To use an existing self-hosted inference engine on your machine or local network:
1. Open the Copilot drawer (`Ctrl+K` or click **🤖 Copilot**).
2. Click the settings gear (`⚙️`) to open **AI Provider Configuration**.
3. Select **Custom OpenAI-Compatible** and enter your Base URL:
   - **Ollama:** `http://localhost:11434/v1` (Model: e.g., `qwen2.5:32b`, `llama3.3`)
   - **vLLM / LM Studio / LocalAI:** `http://localhost:1234/v1` or custom port.
4. Click **Test & Save Configuration** to verify connection and model access in real time.

### Cloud Providers (OpenRouter, OpenAI, Groq) & Dynamic Key Validation

If you prefer cloud-hosted inference:
1. In Copilot Settings, set Base URL to `https://openrouter.ai/api/v1` (or leave default for OpenAI).
2. Enter your API Key and target model identifier (e.g., `anthropic/claude-3.5-sonnet`, `openai/gpt-4o`, `deepseek/deepseek-r1`).
3. Click **Test & Save Configuration**: the server runs a live ping via `POST /api/ai/validate-key` confirming quota, auth, and model accessibility.
4. **Privacy Guarantee:** Your API key is stored exclusively in client-side browser storage and passed per-turn via the `X-User-API-Key` HTTP header. It is never persisted on disk or in the server database.

---

## 📡 API & WebSockets Reference

HealthAI provides a clean, modular REST and WebSocket API documented interactively at `http://127.0.0.1:8000/docs`.

### Primary API Endpoints

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **AI Copilot** | `POST` | `/api/ai/chat/stream` | Server-Sent Events (SSE) streaming chat with reasoning telemetry & action cards. |
| **AI Copilot** | `POST` | `/api/ai/infer-purpose` | Infers stack intent, partitions modalities, and detects uncompensated burdens. |
| **AI Copilot** | `POST` | `/api/ai/tools/execute` | Executes deterministic pharmacology tools (catalog, CYP450, PBPK, GraphRAG). |
| **AI Copilot** | `POST` | `/api/ai/validate-key` | Live connectivity test, model verification, and latency ping for LLM endpoints. |
| **Interactions** | `POST` | `/api/interactions/matrix` | Evaluates $N \times N$ collisions, syndrome alerts, organ burdens, and risk score. |
| **Protocols** | `POST` | `/protocol` | Generates individualized circadian schedules based on biometrics and goals. |
| **Knowledge Graph**| `GET` | `/graph-data` | Returns 6-tier network nodes, edges, receptor occupancies, and cascade states. |
| **Knowledge Graph**| `GET` | `/graph-path` | Calculates shortest biological paths and cross-talk connections. |
| **Knowledge Graph**| `POST` | `/api/graph/cypher` | Executes custom Cypher queries against the Neo4j database. |
| **PBPK / ODE** | `POST` | `/api/pkpd/simulate` | Simulates 2-compartment small-molecule or biologic TMDD/FcRn curves and Hill PD. |
| **Catalog** | `GET` | `/catalog` | Paginated catalog listing with multi-token search and modality filtering. |
| **Catalog Index** | `GET` | `/api/compounds/index` | Full in-memory tokenized search prefix index for sub-millisecond autocomplete. |
| **Catalog Search**| `GET` | `/api/compounds/search` | Typeahead search across compound keys, names, classes, and modalities. |
| **Catalog Search**| `GET` | `/api/compounds/search/stream` | Progressive dual-tier SSE search (local matches first, live registry stream second). |
| **Decomposition** | `GET` | `/api/catalog/decompose/{query}` | Decomposes brand/combo drugs into active chemical entities via RxNorm Graph. |
| **Botanical** | `GET` | `/api/catalog/botanical/{query}` | Resolves crude botanicals to NCBI MeSH Tree B01 & active phytochemicals. |
| **Modality** | `GET` | `/api/catalog/modality/{query}` | Classifies substance modality across 10 classes via NCATS G-SRS and ChEMBL. |
| **Catalog** | `POST` | `/api/compounds/{key}/enrich-full` | Triggers full live multi-source enrichment (PubChem, ChEMBL, UniProt, OpenFDA). |
| **Enrichment WS**| `WS` | `/ws/enrichment` | WebSocket stream broadcasting real-time background worker progress and logs. |

---

## 🧪 Testing & Quality Assurance

HealthAI includes an extensive automated test suite covering deterministic collision engines, biophysical ODE simulations, pharmacogenomics, and AI Copilot streaming:

```bash
# Run all test suites
pytest

# Run tests with verbose output
pytest -v

# Run the Biophysical Small-Molecule PBPK & Biologic TMDD test suites
pytest tests/test_biophysical_pbpk_and_odes.py tests/test_modality_expansion.py -v

# Run Fast Search & Progressive SSE Streaming search test suites
pytest tests/test_fast_compound_search.py tests/test_streaming_compound_search.py tests/test_search_filters.py -v

# Run Target Cascade Determinism test suite
pytest tests/test_target_cascade_determinism.py -v

# Run the AI Copilot & SSE Streaming test suite
pytest tests/test_ai_copilot_suite.py -v
```

---

## 📜 License & Medical Disclaimer

### License
This project is licensed under the MIT License - see the `LICENSE` file for details.

### Medical & Scientific Disclaimer
> **IMPORTANT NOTICE:** `HealthAI` is an advanced computational pharmacology research, simulation, and educational platform. It is designed to assist researchers, students, clinicians, and health enthusiasts in understanding molecular mechanisms, pharmacokinetic principles, and biological systems. **HealthAI is NOT a licensed medical device and does NOT provide medical advice, clinical diagnoses, or treatment prescriptions.** Always consult a qualified healthcare provider before initiating, modifying, or discontinuing any pharmaceutical, peptide, or supplement protocol.
