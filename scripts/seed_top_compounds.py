#!/usr/bin/env python3
"""
Pre-seed Top Essential Compounds & Therapeutics
------------------------------------------------
Batch-enriches and caches top essential medicines, metabolic agents,
cardiovascular drugs, psychotropics, and wellness compounds into the SQLite catalog
so they resolve instantly with sub-millisecond latency for users.

Queries all authoritative registries (RxNorm, NCBI MeSH, OpenFDA, ChEMBL, PubChem)
in parallel with zero hardcoded shortcuts or regex approximations.
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.catalog_service import CatalogService, DEFAULT_CATALOG_DB_PATH
from app.services.live_enrichment import LiveEnrichmentService

# Top 150 essential therapeutics and wellness compounds across clinical domains
TOP_COMPOUNDS: List[str] = [
    # Metabolic & Endocrine
    "Metformin", "Empagliflozin", "Dapagliflozin", "Canagliflozin", "Semaglutide",
    "Tirzepatide", "Liraglutide", "Dulaglutide", "Sitagliptin", "Linagliptin",
    "Glipizide", "Glimepiride", "Pioglitazone", "Levothyroxine", "Liothyronine",
    
    # Cardiovascular & Renal
    "Atorvastatin", "Rosuvastatin", "Simvastatin", "Pravastatin", "Ezetimibe",
    "Lisinopril", "Enalapril", "Ramipril", "Losartan", "Valsartan", "Telmisartan",
    "Amlodipine", "Nifedipine", "Diltiazem", "Verapamil", "Metoprolol", "Atenolol",
    "Carvedilol", "Nebivolol", "Propranolol", "Hydrochlorothiazide", "Chlorthalidone",
    "Furosemide", "Bumetanide", "Spironolactone", "Eplerenone", "Clopidogrel",
    "Aspirin", "Apixaban", "Rivaroxaban", "Warfarin",

    # Neuropsychiatric & CNS
    "Sertraline", "Escitalopram", "Fluoxetine", "Paroxetine", "Citalopram",
    "Duloxetine", "Venlafaxine", "Bupropion", "Mirtazapine", "Trazodone",
    "Buspirone", "Alprazolam", "Clonazepam", "Lorazepam", "Diazepam",
    "Gabapentin", "Pregabalin", "Lamotrigine", "Levetiracetam", "Topiramate",
    "Modafinil", "Armodafinil", "Methylphenidate", "Atomoxetine", "Memantine",
    "Donepezil", "Levodopa", "Carbidopa", "Pramipexole", "Ropinirole",

    # Gastrointestinal
    "Omeprazole", "Esomeprazole", "Pantoprazole", "Lansoprazole", "Famotidine",
    "Ondansetron", "Metoclopramide", "Dicyclomine", "Sucralfate",

    # Respiratory & Allergy
    "Albuterol", "Levalbuterol", "Salmeterol", "Fluticasone", "Budesonide",
    "Montelukast", "Cetirizine", "Loratadine", "Fexofenadine", "Diphenhydramine",

    # Analgesics & Anti-inflammatory
    "Acetaminophen", "Ibuprofen", "Naproxen", "Meloxicam", "Celecoxib",
    "Diclofenac", "Indomethacin", "Tramadol", "Cyclobenzaprine", "Baclofen",
    "Tizanidine", "Colchicine", "Allopurinol",

    # Anti-infectives
    "Amoxicillin", "Azithromycin", "Doxycycline", "Ciprofloxacin", "Levofloxacin",
    "Cephalexin", "Sulfamethoxazole", "Trimethoprim", "Fluconazole", "Valacyclovir",
    "Acyclovir", "Nitrofurantoin",

    # Urological & Reproductive
    "Finasteride", "Dutasteride", "Tamsulosin", "Alfuzosin", "Sildenafil",
    "Tadalafil", "Anastrozole", "Tamoxifen", "Clomiphene",

    # Peptides & Longevity
    "BPC-157", "TB-500", "GHK-Cu", "Ipamorelin", "CJC-1295", "Sermorelin",
    "Tesamorelin", "Semax", "Selank", "Epithalon", "Oxytocin", "Desmopressin",

    # Supplements & Nutraceuticals (from seed_compounds.txt)
    "Caffeine", "Creatine", "L-Carnitine", "Omega-3", "Beta-Alanine",
    "Ashwagandha", "Astaxanthin", "CoQ10", "Milk Thistle", "Curcumin",
    "Citrus Bergamot", "Alpha Lipoic Acid", "Taurine", "Melatonin", "NAC",
    "TUDCA", "L-Theanine", "Berberine", "Quercetin", "Resveratrol",
    "Rhodiola", "Bacopa", "Piperine", "Sulforaphane", "Saw Palmetto",
]


def seed_single_compound(
    compound_name: str,
    catalog_service: CatalogService,
    enricher: LiveEnrichmentService,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[str, bool, float, Optional[str]]:
    """
    Enriches and stores a single compound.
    Returns (compound_name, success, elapsed_seconds, error_or_status).
    """
    t0 = time.perf_counter()
    try:
        # Check existing
        if not force:
            existing = catalog_service.get_compound(compound_name, auto_enrich=False)
            if existing:
                elapsed = time.perf_counter() - t0
                return compound_name, True, elapsed, "already_cached"

        if dry_run:
            elapsed = time.perf_counter() - t0
            return compound_name, True, elapsed, "dry_run"

        # Cold fetch and enrich via authoritative sources
        profile = enricher.fetch_compound_profile(compound_name, shallow=False)
        if not profile:
            elapsed = time.perf_counter() - t0
            return compound_name, False, elapsed, "no_profile_found"

        catalog_service.upsert_compound(profile)
        elapsed = time.perf_counter() - t0
        return compound_name, True, elapsed, "enriched_and_persisted"
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return compound_name, False, elapsed, str(exc)


def seed_top_compounds(
    limit: Optional[int] = None,
    concurrency: int = 6,
    force: bool = False,
    dry_run: bool = False,
    db_path: str = DEFAULT_CATALOG_DB_PATH,
) -> None:
    catalog_service = CatalogService(database_path=db_path)
    enricher = LiveEnrichmentService()

    compounds_to_seed = list(dict.fromkeys(TOP_COMPOUNDS))  # Deduplicate preserving order
    if limit:
        compounds_to_seed = compounds_to_seed[:limit]

    total = len(compounds_to_seed)
    print(f"============================================================")
    print(f" Starting Batch Seeding: {total} compounds")
    print(f" Concurrency: {concurrency} workers | Force Re-enrich: {force} | Dry Run: {dry_run}")
    print(f" Database: {db_path}")
    print(f"============================================================")

    start_time = time.perf_counter()
    completed_count = 0
    cached_count = 0
    new_enriched_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                seed_single_compound,
                name,
                catalog_service,
                enricher,
                force,
                dry_run,
            ): name
            for name in compounds_to_seed
        }

        for fut in as_completed(futures):
            name = futures[fut]
            completed_count += 1
            try:
                name, success, elapsed, status = fut.result()
                if status == "already_cached":
                    cached_count += 1
                    print(f"[{completed_count:3d}/{total}] {name:<22} -> CACHED ({elapsed*1000:6.1f} ms)")
                elif status == "enriched_and_persisted":
                    new_enriched_count += 1
                    print(f"[{completed_count:3d}/{total}] {name:<22} -> ENRICHED ({elapsed:5.2f} s)")
                elif status == "dry_run":
                    print(f"[{completed_count:3d}/{total}] {name:<22} -> DRY RUN ({elapsed*1000:6.1f} ms)")
                else:
                    error_count += 1
                    print(f"[{completed_count:3d}/{total}] {name:<22} -> FAILED ({elapsed:5.2f} s): {status}")
            except Exception as e:
                error_count += 1
                print(f"[{completed_count:3d}/{total}] {name:<22} -> EXCEPTION: {e}")

    total_time = time.perf_counter() - start_time
    print(f"============================================================")
    print(f" Seeding Complete in {total_time:.2f} s")
    print(f" - Already cached: {cached_count}")
    print(f" - Newly enriched: {new_enriched_count}")
    print(f" - Errors / Not found: {error_count}")
    print(f"============================================================")


def main():
    parser = argparse.ArgumentParser(description="Pre-seed top essential compounds into HealthAI catalog database.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of compounds to seed.")
    parser.add_argument("--concurrency", type=int, default=6, help="Number of concurrent workers (default: 6).")
    parser.add_argument("--force", action="store_true", help="Force re-enrichment of already cached compounds.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect compounds without executing network or DB writes.")
    parser.add_argument("--db-path", type=str, default=DEFAULT_CATALOG_DB_PATH, help="Path to SQLite catalog database.")

    args = parser.parse_args()
    seed_top_compounds(
        limit=args.limit,
        concurrency=args.concurrency,
        force=args.force,
        dry_run=args.dry_run,
        db_path=args.db_path,
    )


if __name__ == "__main__":
    main()
