#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.catalog_service import CatalogService, DEFAULT_CATALOG_DB_PATH


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_pipe_list(value: Any) -> List[str]:
    text = normalize_text(value)
    if not text:
        return []
    parts = [part.strip() for part in text.split("|") if part.strip()]
    return parts


def parse_bool(value: Any) -> bool:
    text = normalize_text(value).lower()
    if text in {"1", "true", "yes", "y", "t"}:
        return True
    return False


def extract_inchi_key(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    if text.startswith("InChI="):
        # The ChEMBL drugs export provides InChI, not InChIKey. Use the parent molecule
        # as the stable catalog identity when no InChIKey is supplied.
        return None
    return text


def parse_phase(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    try:
        numeric = float(text)
        if numeric >= 4:
            return "4"
        if numeric >= 3:
            return "3"
        if numeric >= 2:
            return "2"
        if numeric >= 1:
            return "1"
        if numeric >= 0:
            return "0"
        return ""
    except ValueError:
        return text


def classify_route(row: Dict[str, Any]) -> str | None:
    routes = []
    if parse_bool(row.get("Oral")):
        routes.append("oral")
    if parse_bool(row.get("Parenteral")):
        routes.append("parenteral")
    if parse_bool(row.get("Topical")):
        routes.append("topical")
    return ", ".join(routes) if routes else None


def build_record(row: Dict[str, Any]) -> Dict[str, Any]:
    parent_molecule = normalize_text(row.get("Parent Molecule"))
    name = normalize_text(row.get("Name")) or parent_molecule or "Compound"
    synonyms = parse_pipe_list(row.get("Synonyms"))
    research_codes = parse_pipe_list(row.get("Research Codes"))
    combined_synonyms = []
    for item in synonyms + research_codes:
        item = normalize_text(item)
        if item and item not in combined_synonyms:
            combined_synonyms.append(item)

    inchikey = extract_inchi_key(row.get("Inchi"))
    if inchikey is None:
        canonical_identity = parent_molecule or name.lower().replace(" ", "_")
    else:
        canonical_identity = inchikey
    smiles = normalize_text(row.get("Smiles"))
    phase = parse_phase(row.get("Phase"))
    drug_type = normalize_text(row.get("Drug Type"))
    availability = normalize_text(row.get("Availability Type"))
    withdrawn = parse_bool(row.get("Withdrawn Flag"))
    orphan = parse_bool(row.get("Orphan"))
    atc_codes = parse_pipe_list(row.get("ATC Codes"))
    level_1 = normalize_text(row.get("Level 1 ATC Codes"))
    level_2 = normalize_text(row.get("Level 2 ATC Codes"))
    level_3 = normalize_text(row.get("Level 3 ATC Codes"))
    level_4 = normalize_text(row.get("Level 4 ATC Codes"))
    categories = [item for item in [level_1, level_2, level_3, level_4] if item]

    return {
        "key": parent_molecule or name.lower().replace(" ", "_"),
        "name": name,
        "canonical_name": name,
        "canonical_key": canonical_identity,
        "inchikey": canonical_identity,
        "synonyms": combined_synonyms,
        "drug_class": drug_type,
        "compound_class": drug_type,
        "route_of_administration": classify_route(row),
        "categories": categories,
        "external_ids": {
            "chembl_parent_molecule": parent_molecule,
            "chembl_name": name,
            "atc_codes": atc_codes,
            "research_codes": research_codes,
        },
        "metadata": {
            "chembl": {
                "phase": phase,
                "drug_type": drug_type,
                "availability_type": availability,
                "withdrawn_flag": withdrawn,
                "orphan": orphan,
                "first_approval": normalize_text(row.get("First Approval")),
                "first_in_class": normalize_text(row.get("First In Class")),
                "chirality": normalize_text(row.get("Chirality")),
                "prodrug": normalize_text(row.get("Prodrug")),
                "oral": parse_bool(row.get("Oral")),
                "parenteral": parse_bool(row.get("Parenteral")),
                "topical": parse_bool(row.get("Topical")),
                "black_box": parse_bool(row.get("Black Box")),
                "smiles": smiles,
                "inchi": normalize_text(row.get("Inchi")),
                "atc_codes": atc_codes,
                "level_1_atc": level_1,
                "level_2_atc": level_2,
                "level_3_atc": level_3,
                "level_4_atc": level_4,
                "drug_applicants": normalize_text(row.get("Drug Applicants")),
                "usan_stem": normalize_text(row.get("USAN Stem")),
                "usan_year": normalize_text(row.get("USAN Year")),
                "usan_definition": normalize_text(row.get("USAN Definition")),
                "passes_rule_of_five": parse_bool(row.get("Passes Rule of Five")),
            }
        },
        "warnings": [],
        "interactions": [],
        "side_effects": [],
        "graph_tags": [],
    }


def import_csv(path: str, db_path: str, limit: int | None = None, dry_run: bool = False) -> List[Dict[str, Any]]:
    service = CatalogService(database_path=db_path)
    imported: List[Dict[str, Any]] = []

    count = 0
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=';')
        for row in reader:
            if limit is not None and count >= limit:
                break
            count += 1
            record = build_record(row)
            if not record["key"]:
                continue
            imported.append(record)
            if not dry_run:
                service.upsert_compound(record)
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the ChEMBL drug subset CSV into the app catalog schema.")
    parser.add_argument("--csv", default="ChemblDrugs.csv", help="Path to the ChEMBL drugs CSV export")
    parser.add_argument("--db", default=os.getenv("HEALTHAI_CATALOG_DB", DEFAULT_CATALOG_DB_PATH), help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Preview imported records without writing to the database")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on the number of records imported")
    args = parser.parse_args()

    records = import_csv(args.csv, args.db, limit=args.limit, dry_run=args.dry_run)
    print(f"Imported {len(records)} records")
    for record in records[:10]:
        print(json.dumps({
            "key": record.get("key"),
            "name": record.get("name"),
            "canonical_key": record.get("canonical_key"),
            "phase": (record.get("metadata") or {}).get("chembl", {}).get("phase"),
            "route": record.get("route_of_administration"),
        }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
