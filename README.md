# healthAI

Science-driven pharmacology lab, biological network mapping, and individualized protocol optimization engine.

## Overview

`healthAI` is a modern FastAPI platform that evaluates multi-compound stacks, detects pharmacokinetic (CYP450) collisions and pharmacodynamic conflicts, checks organ burdens and biomarker contraindications, and produces individualized health protocols.

## Architecture

```
healthAI/
├── app/
│   ├── main.py                  # Clean FastAPI application entrypoint
│   ├── schemas/                 # Pydantic data schemas
│   │   ├── __init__.py
│   │   └── profiles.py          # UserProfile, LabProfile, InteractionWorkbenchRequest
│   ├── routers/                 # Modular API & view routers
│   │   ├── __init__.py
│   │   ├── views.py             # UI routes (/, /admin, /graph, /compound/{key})
│   │   ├── catalog.py           # /catalog and /api/compounds/search
│   │   ├── interactions.py      # /api/interactions/matrix
│   │   ├── graph.py             # /graph-data
│   │   └── protocols.py         # /protocol
│   ├── services/                # Core business & computation logic
│   │   ├── catalog_service.py   # SQLite compound catalog repository & search
│   │   ├── interaction_engine.py# Pairwise N x N interaction matrix & risk scoring
│   │   ├── protocol_builder.py  # Goal- & biomarker-driven protocol assembly
│   │   └── graph_service.py     # Biological network graph construction & filtering
│   ├── knowledge_graph/         # NetworkX ontology & biological graph structures
│   │   ├── graph.py
│   │   ├── models.py
│   │   └── examples.py
│   ├── data/                    # Curated seed compound library
│   │   └── compounds.py
│   └── static/                  # Responsive web interfaces
│       ├── index.html
│       ├── admin.html
│       ├── graph.html
│       └── compound.html
├── scripts/                     # Data ingest & ChEMBL enrichment tooling
│   ├── import_chembl_drugs_csv.py
│   └── populate_catalog.py
├── tests/                       # Comprehensive test suite
├── pyproject.toml               # Build & pytest configuration
└── requirements.txt             # Python dependencies
```

## Running Locally

### One-Click Launch (Windows)
Double-click `start.bat` or run:
```bat
start.bat
```
*(Automatically checks `.venv`, starts the server, and opens http://localhost:8000 in your default browser)*

### PowerShell Launch
```powershell
.\start.ps1
```

### Python Launcher Script
```bash
# Start server with auto-reload and open browser
python run_server.py --open-browser

# Custom port or host
python run_server.py --host 0.0.0.0 --port 8000
```

### Direct Uvicorn Command
```bash
# Setup environment (if needed)
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# Run development server
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Running Tests

```bash
.venv\Scripts\pytest
```

## Core API Endpoints

- **`GET /health`**: Health check and status.
- **`GET /`**: Pharmacology Lab & Interactive Collision Matrix dashboard.
- **`GET /admin`**: Compound Catalog Management & Ingestion UI.
- **`GET /graph`**: Interactive Biological Knowledge Graph view.
- **`GET /compound/{key}`**: Deep-dive compound pharmacology profile page.
- **`GET /api/compounds/search?q={query}`**: Fast autocomplete across compounds, classes, and mechanisms.
- **`POST /api/interactions/matrix`**: Evaluates pairwise N x N collisions, organ burdens, and cumulative risk score.
- **`GET /graph-data?stack={compounds}&depth={depth}`**: Returns biological pathway nodes and directed interaction edges.
- **`GET /catalog`**: Paginated compound catalog listing with multi-token search.
- **`POST /catalog`**: Create or update compound record.
- **`DELETE /catalog/{key}`**: Remove compound record.
- **`POST /protocol`**: Generate tailored stacks based on user goals, biometrics, and lab values.
