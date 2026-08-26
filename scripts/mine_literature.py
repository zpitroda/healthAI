#!/usr/bin/env python3
"""
Literature Mining Pipeline CLI
-------------------------------
Unified CLI to enrich the HealthAI knowledge graph with literature-backed
relationships from curated databases and PubMed co-occurrence analysis.

Usage:
    python scripts/mine_literature.py --all
    python scripts/mine_literature.py --import-stitch --import-ctd
    python scripts/mine_literature.py --mine-cooccurrence --compounds-file seed_compounds.txt
    python scripts/mine_literature.py --import-drugbank
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.knowledge_graph.graph_db import get_graph_database
from app.services.catalog_service import CatalogService, DEFAULT_CATALOG_DB_PATH


def load_compounds(compounds_file: str) -> list[str]:
    """Load compound names from seed file or catalog database."""
    path = Path(compounds_file)
    if not path.is_absolute():
        path = ROOT / compounds_file
    if path.exists():
        compounds = [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        print(f"[Pipeline] Loaded {len(compounds)} compounds from {path}")
        return compounds
    print(f"[Pipeline] Compounds file not found at {path}, loading from catalog...")
    service = CatalogService()
    catalog_compounds = service.list_compounds()
    keys = [c.get("key", "") for c in catalog_compounds if c.get("key")]
    print(f"[Pipeline] Loaded {len(keys)} compounds from catalog database")
    return keys


def run_stitch(compounds: list[str], gdb, dry_run: bool = False) -> int:
    """Import STITCH chemical-protein interactions."""
    print("\n" + "=" * 60)
    print("  PHASE 1a: STITCH Chemical-Protein Interactions")
    print("=" * 60)
    from scripts.literature_importers import STITCHImporter
    if dry_run:
        gdb.close()
    importer = STITCHImporter(gdb)
    total = importer.run(compounds)
    print(f"\n  [STITCH Complete] {total} edges imported")
    return total


def run_ctd(compounds: list[str], gdb, dry_run: bool = False) -> int:
    """Import CTD chemical-gene-disease associations."""
    print("\n" + "=" * 60)
    print("  PHASE 1b: CTD Chemical-Gene Associations")
    print("=" * 60)
    from scripts.literature_importers import CTDImporter
    if dry_run:
        gdb.close()
    importer = CTDImporter(gdb)
    total = importer.run(compounds)
    print(f"\n  [CTD Complete] {total} edges imported")
    return total


def run_drugbank(compounds: list[str], gdb, dry_run: bool = False) -> int:
    """Import DrugBank drug-drug interactions."""
    print("\n" + "=" * 60)
    print("  PHASE 1c: DrugBank Drug-Drug Interactions")
    print("=" * 60)
    from scripts.literature_importers import DrugBankImporter
    if dry_run:
        gdb.close()
    importer = DrugBankImporter(gdb)
    total = importer.run(compounds)
    print(f"\n  [DrugBank Complete] {total} edges imported")
    return total


def run_cooccurrence(compounds: list[str], dry_run: bool = False) -> int:
    """Mine PubMed co-occurrence with PMI scoring."""
    print("\n" + "=" * 60)
    print("  PHASE 2: PubMed Co-occurrence Mining (PMI)")
    print("=" * 60)
    from app.services.cooccurrence_miner import CooccurrenceMiner
    api_key = os.getenv("NCBI_API_KEY")
    miner = CooccurrenceMiner(api_key=api_key)
    results = miner.mine_compound_pairs(
        compounds,
        min_cooccurrence=3,
        min_npmi=0.0,
    )
    if dry_run:
        print(f"\n  [Dry Run] Would create {len(results)} co-occurrence edges")
        for r in results[:10]:
            print(f"    {r['compound_a']} <-> {r['compound_b']}: "
                  f"co-occurrence={r['count_ab']}, NPMI={r['npmi']:.3f}")
        return 0
    else:
        edges = miner.save_to_graph(results)
        print(f"\n  [Co-occurrence Complete] {edges} edges saved to graph")
        return edges


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="HealthAI Literature Mining Pipeline — enrich the knowledge graph "
                    "with literature-backed compound relationships."
    )
    parser.add_argument("--import-stitch", action="store_true",
                        help="Import STITCH chemical-protein interactions")
    parser.add_argument("--import-ctd", action="store_true",
                        help="Import CTD chemical-gene-disease associations")
    parser.add_argument("--import-drugbank", action="store_true",
                        help="Import DrugBank drug-drug interactions (downloads from Kaggle)")
    parser.add_argument("--mine-cooccurrence", action="store_true",
                        help="Mine PubMed co-occurrence and compute PMI scores")
    parser.add_argument("--all", action="store_true",
                        help="Run all import and mining phases")
    parser.add_argument("--compounds-file", default="seed_compounds.txt",
                        help="Path to seed compounds file (default: seed_compounds.txt)")
    parser.add_argument("--db", default=os.getenv("HEALTHAI_CATALOG_DB", DEFAULT_CATALOG_DB_PATH),
                        help="Catalog database path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview operations without writing to database")
    args = parser.parse_args()

    # Default to --all if no specific phase selected
    run_all = args.all or not any([
        args.import_stitch, args.import_ctd, args.import_drugbank, args.mine_cooccurrence
    ])

    compounds = load_compounds(args.compounds_file)
    if not compounds:
        print("[Pipeline] No compounds found. Exiting.")
        sys.exit(1)

    gdb = get_graph_database()
    start_time = time.time()
    summary: dict[str, int] = {}

    if run_all or args.import_stitch:
        summary["stitch_edges"] = run_stitch(compounds, gdb, dry_run=args.dry_run)

    if run_all or args.import_ctd:
        summary["ctd_edges"] = run_ctd(compounds, gdb, dry_run=args.dry_run)

    if run_all or args.import_drugbank:
        summary["drugbank_edges"] = run_drugbank(compounds, gdb, dry_run=args.dry_run)

    if run_all or args.mine_cooccurrence:
        summary["cooccurrence_edges"] = run_cooccurrence(compounds, dry_run=args.dry_run)

    elapsed = time.time() - start_time
    total_edges = sum(summary.values())

    print("\n" + "=" * 60)
    print("  PIPELINE SUMMARY")
    print("=" * 60)
    for source, count in summary.items():
        print(f"  {source}: {count} edges")
    print(f"  Total: {total_edges} edges")
    print(f"  Time: {elapsed:.1f} seconds")
    if args.dry_run:
        print("  Mode: DRY RUN (no data written)")
    print("=" * 60)


if __name__ == "__main__":
    main()
