#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.catalog_service import CatalogService, DEFAULT_CATALOG_DB_PATH

PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/InChIKey,CanonicalSMILES,MF,MW,ExactMass/JSON"
CHEMBL_URL = "https://www.ebi.ac.uk/chembl/api/data/compound/search?query={name}&limit=5"
CHEMBL_BULK_URL = "https://www.ebi.ac.uk/chembl/api/data/compound?limit={limit}&offset={offset}"
REACTOME_URL = "https://reactome.org/ContentService/data/query/{name}"


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_placeholder_text(value: Any) -> bool:
    text = normalize_text(value).casefold()
    if not text:
        return True
    placeholders = {"none", "null", "n/a", "na", "unknown", "not available", "not applicable", "--", "-"}
    return text in placeholders or text.startswith("none ")


def canonicalize_key(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    return text.replace("\n", "").strip()


def safe_json_get(payload: Any, *path: str) -> Any:
    current = payload
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "healthAI-catalog-ingest/1.0"})
    with urlopen(request, timeout=20) as response:
        payload = response.read()
        if not payload:
            return {}
        return json.loads(payload.decode("utf-8"))


def fetch_pubchem_record(name: str) -> Dict[str, Any]:
    encoded_name = quote(name)
    payload = fetch_json(PUBCHEM_URL.format(name=encoded_name))
    rows = safe_json_get(payload, "Properties", "Property") or []
    if not rows:
        return {}
    first = rows[0] if isinstance(rows, list) else rows
    return {
        "name": name,
        "canonical_name": normalize_text(first.get("CID") or name),
        "inchikey": canonicalize_key(first.get("InChIKey")),
        "external_ids": {"pubchem_name": name},
        "metadata": {
            "pubchem": {
                "canonical_smiles": normalize_text(first.get("CanonicalSMILES")),
                "molecular_formula": normalize_text(first.get("MF")),
                "molecular_weight": normalize_text(first.get("MW")),
                "exact_mass": normalize_text(first.get("ExactMass")),
            }
        },
    }


def fetch_chembl_record(name: str) -> Dict[str, Any]:
    encoded_name = quote(name)
    payload = fetch_json(CHEMBL_URL.format(name=encoded_name))
    results = payload.get("compounds") or []
    if not results:
        return {}
    compound = results[0]
    return {
        "name": normalize_text(compound.get("pref_name") or compound.get("name") or name),
        "canonical_name": normalize_text(compound.get("pref_name") or compound.get("name") or name),
        "inchikey": canonicalize_key(compound.get("standard_inchi_key") or compound.get("inchi_key")),
        "external_ids": {
            "chembl_id": normalize_text(compound.get("chembl_id") or compound.get("chemblId")),
            "molecule_type": normalize_text(compound.get("molecule_type")),
        },
        "metadata": {
            "chembl": {
                "molecule_type": normalize_text(compound.get("molecule_type")),
                "max_phase": normalize_text(compound.get("max_phase")),
            }
        },
    }


def chembl_compound_to_catalog_record(compound: Dict[str, Any]) -> Dict[str, Any]:
    name = normalize_text(compound.get("pref_name") or compound.get("title") or compound.get("name") or compound.get("molecule_chembl_id"))
    inchikey = canonicalize_key(compound.get("standard_inchi_key") or compound.get("inchi_key"))
    chembl_id = normalize_text(compound.get("molecule_chembl_id") or compound.get("chembl_id") or compound.get("chemblId"))
    synonyms = compound.get("synonyms") or []
    if isinstance(synonyms, str):
        synonyms = [synonyms]
    return {
        "key": chembl_id or name.lower().replace(" ", "_") or "compound",
        "name": name or chembl_id or "Compound",
        "canonical_name": name or chembl_id or "Compound",
        "canonical_key": inchikey,
        "inchikey": inchikey,
        "synonyms": [normalize_text(item) for item in synonyms if normalize_text(item)],
        "external_ids": {
            "chembl_id": chembl_id,
            "molecule_chembl_id": chembl_id,
        },
        "metadata": {
            "chembl": {
                "molecule_type": normalize_text(compound.get("molecule_type")),
                "max_phase": normalize_text(compound.get("max_phase")),
                "full_mwt": normalize_text(compound.get("full_mwt")),
                "alogp": normalize_text(compound.get("alogp")),
                "molecular_formula": normalize_text(compound.get("molecular_formula")),
            }
        },
    }


def read_chembl_sqlite_records(db_path: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not db_path or not os.path.exists(db_path):
        return records

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        table_names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        if "molecule_dictionary" not in table_names:
            return records

        synonym_rows = conn.execute(
            "SELECT molecule_chembl_id, synonym FROM molecule_synonyms WHERE synonym IS NOT NULL"
        ).fetchall()
        synonym_map: Dict[str, List[str]] = {}
        for row in synonym_rows:
            chembl_id = normalize_text(row["molecule_chembl_id"])
            synonym = normalize_text(row["synonym"])
            if not chembl_id or not synonym:
                continue
            synonym_map.setdefault(chembl_id, [])
            if synonym not in synonym_map[chembl_id]:
                synonym_map[chembl_id].append(synonym)

        for row in conn.execute(
            "SELECT molecule_chembl_id, pref_name, standard_inchi_key, molecule_type, max_phase, full_mwt, alogp, molecular_formula FROM molecule_dictionary"
        ).fetchall():
            chembl_id = normalize_text(row["molecule_chembl_id"])
            name = normalize_text(row["pref_name"]) or chembl_id or "Compound"
            inchikey = canonicalize_key(row["standard_inchi_key"])
            record = {
                "key": chembl_id or name.lower().replace(" ", "_") or "compound",
                "name": name,
                "canonical_name": name,
                "canonical_key": inchikey,
                "inchikey": inchikey,
                "synonyms": synonym_map.get(chembl_id, []),
                "external_ids": {"chembl_id": chembl_id, "molecule_chembl_id": chembl_id},
                "metadata": {
                    "chembl": {
                        "molecule_type": normalize_text(row["molecule_type"]),
                        "max_phase": normalize_text(row["max_phase"]),
                        "full_mwt": normalize_text(row["full_mwt"]),
                        "alogp": normalize_text(row["alogp"]),
                        "molecular_formula": normalize_text(row["molecular_formula"]),
                    }
                },
            }
            if record["synonyms"]:
                record["synonyms"] = [item for item in record["synonyms"] if item and item != name]
            records.append(record)
    return records


def filter_low_signal_chembl_records(records: Iterable[Dict[str, Any]], min_score: int = 4, min_synonyms: int = 1, min_metadata_fields: int = 2) -> List[Dict[str, Any]]:
    def score(record: Dict[str, Any]) -> int:
        score_value = 0
        chembl_meta = (record.get("metadata") or {}).get("chembl") or {}
        name = normalize_text(record.get("name") or record.get("canonical_name"))
        canonical_key = normalize_text(record.get("canonical_key") or record.get("inchikey"))
        synonyms = record.get("synonyms") or []
        if canonical_key:
            score_value += 2
        if name and name.lower() not in {"compound", "unknown", "n/a"}:
            score_value += 1
        if isinstance(synonyms, list):
            score_value += min(len(synonyms), 3)
        if normalize_text(chembl_meta.get("molecule_type")):
            score_value += 1
        if normalize_text(chembl_meta.get("max_phase")):
            score_value += 1
        if normalize_text(chembl_meta.get("full_mwt")):
            score_value += 1
        if normalize_text(chembl_meta.get("molecular_formula")):
            score_value += 1
        return score_value

    filtered: List[Dict[str, Any]] = []
    for record in records:
        chembl_meta = (record.get("metadata") or {}).get("chembl") or {}
        metadata_fields = sum(
            1 for value in (
                chembl_meta.get("molecule_type"),
                chembl_meta.get("max_phase"),
                chembl_meta.get("full_mwt"),
                chembl_meta.get("alogp"),
                chembl_meta.get("molecular_formula"),
            ) if normalize_text(value)
        )
        synonym_count = len(record.get("synonyms") or [])
        signal_score = score(record)
        if signal_score >= min_score and synonym_count >= min_synonyms and metadata_fields >= min_metadata_fields:
            filtered.append(record)
    return filtered


def inspect_chembl_sqlite_schema(db_path: str) -> Dict[str, List[str]]:
    if not db_path or not os.path.exists(db_path):
        return {}

    schema: Dict[str, List[str]] = {}
    with sqlite3.connect(db_path) as conn:
        for table_name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
            schema[table_name] = columns
    return schema


def filter_chembl_drug_subset_records(records: Iterable[Dict[str, Any]], min_score: int = 4) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for record in records:
        chembl_meta = (record.get("metadata") or {}).get("chembl") or {}
        molecule_type = normalize_text(chembl_meta.get("molecule_type")).lower()
        max_phase = normalize_text(chembl_meta.get("max_phase"))
        name = normalize_text(record.get("name") or record.get("canonical_name"))
        canonical_key = normalize_text(record.get("canonical_key") or record.get("inchikey"))
        synonyms = record.get("synonyms") or []
        synonym_count = len(synonyms) if isinstance(synonyms, list) else 0

        if not canonical_key:
            continue
        if not name or name.lower() in {"compound", "unknown", "n/a"}:
            continue
        if molecule_type in {"", "unknown", "n/a"} and max_phase == "":
            continue
        if max_phase and max_phase not in {"0", "1", "2", "3", "4"}:
            continue

        signal_score = 0
        if canonical_key:
            signal_score += 2
        if name:
            signal_score += 1
        if synonym_count:
            signal_score += min(synonym_count, 3)
        if molecule_type and molecule_type not in {"unknown", "n/a"}:
            signal_score += 1
        if max_phase:
            signal_score += 1

        if signal_score >= min_score:
            filtered.append(record)
    return filtered


def read_chembl_csv_rows(csv_path: str, delimiter: str = ";") -> List[Dict[str, Any]]:
    if not csv_path or not os.path.exists(csv_path):
        return []

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            rows.append(dict(row))
    return rows


def filter_connected_chembl_indications(rows: Iterable[Dict[str, Any]], drug_ids: Iterable[str] | None = None) -> List[Dict[str, Any]]:
    known_ids = {normalize_text(value).lower() for value in (drug_ids or []) if normalize_text(value)}
    filtered: List[Dict[str, Any]] = []

    for row in rows:
        molecule_id = normalize_text(row.get("Parent Molecule ChEMBL ID"))
        if not molecule_id:
            continue
        if known_ids and molecule_id.lower() not in known_ids:
            continue
        filtered.append(row)
    return filtered


def filter_connected_chembl_mechanisms(rows: Iterable[Dict[str, Any]], drug_ids: Iterable[str] | None = None) -> List[Dict[str, Any]]:
    known_ids = {normalize_text(value).lower() for value in (drug_ids or []) if normalize_text(value)}
    filtered: List[Dict[str, Any]] = []

    for row in rows:
        molecule_id = normalize_text(row.get("Parent Molecule ChEMBL ID"))
        if not molecule_id:
            continue
        if known_ids and molecule_id.lower() not in known_ids:
            continue
        filtered.append(row)
    return filtered


def merge_chembl_enrichment(
    indications: Iterable[Dict[str, Any]],
    mechanisms: Iterable[Dict[str, Any]],
    targets: Iterable[Dict[str, Any]],
    warnings: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Dict[str, Any]]:
    target_map: Dict[str, Dict[str, Any]] = {}
    for row in targets:
        target_id = normalize_text(row.get("Target ChEMBL ID"))
        if not target_id:
            continue
        target_map[target_id] = {
            "target": normalize_text(row.get("Target Name")) or target_id,
            "type": normalize_text(row.get("Type")),
            "organism": normalize_text(row.get("Organism")),
            "accessions": normalize_text(row.get("Accessions")),
        }

    merged: Dict[str, Dict[str, Any]] = {}
    indication_sets: Dict[str, Set[str]] = {}
    warning_sets: Dict[str, Set[str]] = {}
    target_sets: Dict[str, Set[Tuple[str, str]]] = {}

    def normalize_label(label: str) -> str:
        text = normalize_text(label)
        if not text or is_placeholder_text(text):
            return ""

        separators = {"|", ",", ";", "\n", "/", "(", ")", "[", "]", "{", "}", "<", ">", ":"}
        for separator in separators:
            text = text.replace(separator, " ")

        tokens = []
        for part in text.split():
            cleaned = part.strip().strip("'\"")
            lowered = cleaned.casefold()
            if not cleaned or lowered in {"none", "null", "n/a", "na", "unknown", "not available", "not applicable", "--", "-"}:
                continue
            tokens.append(cleaned)

        normalized = " ".join(tokens)
        if not normalized or is_placeholder_text(normalized):
            return ""
        return normalized

    for row in indications:
        drug_id = normalize_text(row.get("Parent Molecule ChEMBL ID"))
        if not drug_id:
            continue
        drug = merged.setdefault(drug_id, {"indications": [], "mechanism": "", "receptor_targets": [], "warnings": []})
        ind_set = indication_sets.setdefault(drug_id, set())

        for field in ("MESH Heading", "EFO Terms"):
            value = normalize_text(row.get(field))
            if not value:
                continue
            for part in [segment.strip() for segment in value.replace("|", ",").split(",") if segment.strip()]:
                norm = normalize_label(part)
                if norm and norm.casefold() not in ind_set:
                    ind_set.add(norm.casefold())
                    drug["indications"].append(norm)

    for row in mechanisms:
        drug_id = normalize_text(row.get("Parent Molecule ChEMBL ID"))
        if not drug_id:
            continue
        mechanism_text = normalize_text(row.get("Mechanism of Action") or row.get("Mechanism Comment") or row.get("Selectivity Comment"))
        target_id = normalize_text(row.get("Target ChEMBL ID"))
        target_name = normalize_text(row.get("Target Name"))
        action = normalize_text(row.get("Action Type"))
        drug = merged.setdefault(drug_id, {"indications": [], "mechanism": "", "receptor_targets": [], "warnings": []})
        t_set = target_sets.setdefault(drug_id, set())

        if mechanism_text:
            if not drug["mechanism"]:
                drug["mechanism"] = mechanism_text
            elif mechanism_text not in drug["mechanism"]:
                drug["mechanism"] = "; ".join(part for part in [drug["mechanism"], mechanism_text] if part)

        target_payload = target_map.get(target_id, {}) if target_id else {}
        resolved_name = target_name or target_payload.get("target") or target_id
        if resolved_name:
            action_clean = action.lower() if action else "modulator"
            key_pair = (resolved_name, action_clean)
            if key_pair not in t_set:
                t_set.add(key_pair)
                receptor = {
                    "target": resolved_name,
                    "action": action_clean,
                    "family": target_payload.get("type") or normalize_text(row.get("Target Type")) or normalize_text(row.get("Target Organism")) or "target",
                    "target_id": target_id,
                    "accessions": target_payload.get("accessions"),
                }
                drug["receptor_targets"].append(receptor)

    if warnings:
        for row in warnings:
            drug_id = normalize_text(row.get("Parent Molecule ChEMBL ID"))
            if not drug_id:
                continue
            warning_type = normalize_text(row.get("Warning Type"))
            warning_class = normalize_text(row.get("Warning Class"))
            warning_description = normalize_text(row.get("Description"))
            if not warning_type and not warning_class and not warning_description:
                continue
            drug = merged.setdefault(drug_id, {"indications": [], "mechanism": "", "receptor_targets": [], "warnings": []})
            candidate = " ".join(part for part in [warning_type, warning_class, warning_description] if part)
            norm = normalize_label(candidate)
            if norm:
                w_set = warning_sets.setdefault(drug_id, set())
                if norm.casefold() not in w_set:
                    w_set.add(norm.casefold())
                    drug["warnings"].append(norm)

    return merged


def extract_chembl_archive(archive_path: str, extract_dir: str | None = None) -> str | None:
    if not archive_path or not os.path.exists(archive_path):
        return None

    destination = extract_dir or os.path.join(os.path.dirname(archive_path), "chembl_sqlite")
    os.makedirs(destination, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(destination)

    candidates = []
    for root, _, files in os.walk(destination):
        for filename in files:
            if filename.endswith(".db") or filename.endswith(".sqlite"):
                candidates.append(os.path.join(root, filename))

    if not candidates:
        return None
    return sorted(candidates)[0]


def fetch_chembl_full_catalog(limit: int = 1000) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    offset = 0
    while True:
        payload = fetch_json(CHEMBL_BULK_URL.format(limit=limit, offset=offset))
        compounds = payload.get("compounds") or []
        if not compounds:
            break
        collected.extend(compounds)
        if len(compounds) < limit:
            break
        offset += len(compounds)
    return collected


def fetch_reactome_record(name: str) -> Dict[str, Any]:
    encoded_name = quote(name)
    payload = fetch_json(REACTOME_URL.format(name=encoded_name))
    if not payload:
        return {}
    return {
        "name": normalize_text(name),
        "canonical_name": normalize_text(name),
        "reference_sources": ["reactome"],
        "metadata": {"reactome": payload},
    }


def merge_payloads(*payloads: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "key": "",
        "name": "",
        "canonical_name": "",
        "canonical_key": None,
        "inchikey": None,
        "synonyms": [],
        "external_ids": {},
        "metadata": {},
        "drug_class": None,
        "mechanism": None,
        "receptor_targets": [],
        "categories": [],
        "indications": [],
        "dosing": {},
        "reason": None,
        "citation": None,
        "contraindications": [],
        "side_effects": [],
        "interactions": [],
        "warnings": [],
        "graph_tags": [],
    }

    for payload in payloads:
        if not payload:
            continue
        for key, value in payload.items():
            if key in {"external_ids", "metadata"}:
                if not value:
                    continue
                if isinstance(value, dict):
                    merged[key].update(value)
                continue
            if key in {"synonyms", "receptor_targets", "categories", "indications", "contraindications", "side_effects", "interactions", "warnings", "graph_tags"}:
                if isinstance(value, list):
                    for item in value:
                        if item not in merged[key]:
                            merged[key].append(item)
                continue
            if value is None or value == "":
                continue
            if key == "key":
                if not merged["key"]:
                    merged["key"] = str(value)
            elif key == "name" and not merged["name"]:
                merged["name"] = str(value)
            elif key == "canonical_name" and not merged["canonical_name"]:
                merged["canonical_name"] = str(value)
            elif key in {"canonical_key", "inchikey"}:
                merged[key] = str(value)
                merged["canonical_key"] = merged.get("canonical_key") or merged.get("inchikey")
                merged["inchikey"] = merged.get("inchikey") or merged.get("canonical_key")
            else:
                merged[key] = value

    if not merged["name"] and merged["canonical_name"]:
        merged["name"] = merged["canonical_name"]
    if not merged["canonical_name"] and merged["name"]:
        merged["canonical_name"] = merged["name"]
    if not merged["key"] and merged["canonical_name"]:
        merged["key"] = str(merged["canonical_name"]).lower().replace(" ", "_")
    if merged["canonical_key"]:
        merged["key"] = merged["key"] or str(merged["canonical_key"]).lower()
    return merged


def enrich_record(name: str) -> Dict[str, Any]:
    payloads: List[Dict[str, Any]] = []
    for fetcher in (fetch_pubchem_record, fetch_chembl_record):
        try:
            result = fetcher(name)
            if result:
                payloads.append(result)
        except Exception:
            continue
    payload = merge_payloads(*payloads)
    if not payload.get("key"):
        payload["key"] = str(name).strip().lower().replace(" ", "_")
    if not payload.get("name"):
        payload["name"] = name
    if not payload.get("canonical_name"):
        payload["canonical_name"] = name
    if payload.get("inchikey"):
        payload["canonical_key"] = payload["inchikey"]
    return payload


def load_compounds_from_csv(path: str) -> List[str]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        names: List[str] = []
        for row in reader:
            for field in ("compound", "name", "canonical_name", "title"):
                value = normalize_text(row.get(field))
                if value:
                    names.append(value)
                    break
        return names


def load_bulk_names(path: str) -> List[str]:
    values: List[str] = []
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            for part in [seg.strip() for seg in line.split(",") if seg.strip()]:
                values.append(part)
    return values


def ingest_names(service: CatalogService, names: Iterable[str], dry_run: bool = False) -> List[Dict[str, Any]]:
    imported: List[Dict[str, Any]] = []
    for item in names:
        name = normalize_text(item)
        if not name:
            continue
        payload = enrich_record(name)
        if payload.get("inchikey"):
            payload["canonical_key"] = payload["inchikey"]
        payload["key"] = payload.get("key") or str(name).lower().replace(" ", "_")
        imported.append(payload)
        if not dry_run:
            service.upsert_compound(payload)
    return imported


def ingest_chembl_catalog(service: CatalogService, limit: int = 1000, dry_run: bool = False, sqlite_db_path: str | None = None) -> List[Dict[str, Any]]:
    imported: List[Dict[str, Any]] = []
    if sqlite_db_path and os.path.exists(sqlite_db_path):
        for record in read_chembl_sqlite_records(sqlite_db_path):
            if record.get("inchikey"):
                record["canonical_key"] = record["inchikey"]
            imported.append(record)
            if not dry_run:
                service.upsert_compound(record)
        return imported

    for compound in fetch_chembl_full_catalog(limit=limit):
        payload = chembl_compound_to_catalog_record(compound)
        if payload.get("inchikey"):
            payload["canonical_key"] = payload["inchikey"]
        imported.append(payload)
        if not dry_run:
            service.upsert_compound(payload)
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate the healthAI catalog from public chemical databases using canonical InChIKey merging.")
    parser.add_argument("--source", choices=["names", "csv", "bulk", "chembl", "chembl-drugs", "chembl-enrichment"], default="chembl-drugs", help="Source of data to import. Default is the ChEMBL drug subset for the live app catalog.")
    parser.add_argument("--names", help="Comma-separated compound names or a file path with one name per line")
    parser.add_argument("--csv", help="CSV file with compound names in a column named compound/name/canonical_name/title")
    parser.add_argument("--file", "--bulk", dest="bulk_file", help="Bulk text file listing compounds, one per line or comma-separated")
    parser.add_argument("--indications-csv", help="ChEMBL indications export filtered to rows connected to drug molecules.")
    parser.add_argument("--mechanisms-csv", help="ChEMBL mechanisms export filtered to rows connected to drug molecules.")
    parser.add_argument("--targets-csv", help="ChEMBL targets export filtered to rows connected to drug molecules.")
    parser.add_argument("--warnings-csv", help="ChEMBL warnings export containing parent molecule warning metadata to merge into warnings fields.")
    parser.add_argument("--dry-run", action="store_true", help="Preview records without writing to the database")
    parser.add_argument("--limit", type=int, default=1000, help="Page size for ChEMBL bulk pagination")
    parser.add_argument("--db", default=os.getenv("HEALTHAI_CATALOG_DB", DEFAULT_CATALOG_DB_PATH), help="SQLite database path")
    parser.add_argument("--sqlite-db", help="Path to a ChEMBL SQLite database or extracted .db file to ingest directly.")
    parser.add_argument("--archive", help="Path to a ChEMBL .tar.gz archive to extract and read directly.")
    parser.add_argument("--schema-only", action="store_true", help="Inspect ChEMBL schema and exit without importing records.")
    parser.add_argument("--min-score", type=int, default=4, help="Minimum relevance score for a ChEMBL record to be imported.")
    parser.add_argument("--min-synonyms", type=int, default=1, help="Minimum number of synonym entries required before import.")
    parser.add_argument("--min-metadata-fields", type=int, default=2, help="Minimum number of populated ChEMBL metadata fields required before import.")
    args = parser.parse_args()

    service = CatalogService(database_path=args.db)

    if args.source == "chembl-enrichment" or (args.indications_csv or args.mechanisms_csv or args.targets_csv):
        if not args.indications_csv or not args.mechanisms_csv or not args.targets_csv:
            print("All three ChEMBL enrichment CSVs are required: --indications-csv, --mechanisms-csv, and --targets-csv.", file=sys.stderr)
            return 1

        warnings_csv = args.warnings_csv or os.environ.get("CHEMBL_WARNINGS_CSV")
        warnings = read_chembl_csv_rows(warnings_csv, delimiter=';') if warnings_csv and os.path.exists(warnings_csv) else []

        drug_ids = {normalize_text(entry.get("key") or entry.get("canonical_key") or entry.get("name")) for entry in service.list_compounds() if normalize_text(entry.get("key") or entry.get("canonical_key") or entry.get("name"))}
        indications = filter_connected_chembl_indications(read_chembl_csv_rows(args.indications_csv, delimiter=';'), drug_ids)
        mechanisms = filter_connected_chembl_mechanisms(read_chembl_csv_rows(args.mechanisms_csv, delimiter=';'), drug_ids)
        targets = read_chembl_csv_rows(args.targets_csv, delimiter=';')
        merged = merge_chembl_enrichment(indications, mechanisms, targets, warnings)

        print(f"Merged {len(merged)} drug-linked ChEMBL enrichment records")
        for drug_id, payload in sorted(merged.items())[:10]:
            print(json.dumps({
                "key": drug_id,
                "indications": payload.get("indications", []),
                "mechanism": payload.get("mechanism"),
                "receptor_targets": payload.get("receptor_targets", []),
            }, ensure_ascii=False, sort_keys=True))

        if not args.dry_run:
            print(f"Persisting {len(merged)} enriched records to {args.db} in single transaction...")
            with sqlite3.connect(args.db) as conn:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_canonical_key ON compounds(canonical_key)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_inchikey ON compounds(inchikey)")
                for drug_id, payload in merged.items():
                    conn.execute(
                        """
                        UPDATE compounds SET
                            mechanism = COALESCE(?, mechanism),
                            receptor_targets = ?,
                            indications = ?,
                            warnings = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE key = ?
                        """,
                        (
                            payload.get("mechanism"),
                            json.dumps(payload.get("receptor_targets", [])),
                            json.dumps(payload.get("indications", [])),
                            json.dumps(payload.get("warnings", [])),
                            drug_id,
                        ),
                    )
                conn.commit()
            print("[ChEMBL Enrichment Ingested Successfully]")
        return 0

    if args.source in {"chembl", "chembl-drugs"}:
        if args.schema_only:
            sqlite_db = args.sqlite_db or (extract_chembl_archive(args.archive) if args.archive else None)
            schema = inspect_chembl_sqlite_schema(sqlite_db) if sqlite_db else {}
            if not schema:
                print("No ChEMBL SQLite schema found.", file=sys.stderr)
                return 1
            for table_name, columns in schema.items():
                print(f"{table_name}: {', '.join(columns[:20])}")
            return 0
        sqlite_db = args.sqlite_db
        if not sqlite_db and args.archive:
            sqlite_db = extract_chembl_archive(args.archive)
        imported_raw = []
        if sqlite_db and os.path.exists(sqlite_db):
            imported_raw = read_chembl_sqlite_records(sqlite_db)
            if args.source == "chembl-drugs":
                imported = filter_chembl_drug_subset_records(imported_raw, min_score=args.min_score)
            else:
                imported = filter_low_signal_chembl_records(
                    imported_raw,
                    min_score=args.min_score,
                    min_synonyms=args.min_synonyms,
                    min_metadata_fields=args.min_metadata_fields,
                )
        else:
            imported = ingest_chembl_catalog(service, limit=args.limit, dry_run=args.dry_run, sqlite_db_path=None)

        if not args.dry_run and sqlite_db and os.path.exists(sqlite_db):
            for record in imported:
                if record.get("inchikey"):
                    record["canonical_key"] = record["inchikey"]
                service.upsert_compound(record)

        print(f"Processed {len(imported)} compounds from ChEMBL")
        for record in imported[:10]:
            print(json.dumps({
                "key": record.get("key"),
                "name": record.get("name"),
                "canonical_name": record.get("canonical_name"),
                "inchikey": record.get("inchikey"),
                "external_ids": record.get("external_ids", {}),
            }, ensure_ascii=False, sort_keys=True))
        return 0

    names: List[str] = []
    if args.names:
        names.extend(part.strip() for part in args.names.split(",") if part.strip())
    if args.csv:
        names.extend(load_compounds_from_csv(args.csv))
    if args.bulk_file:
        names.extend(load_bulk_names(args.bulk_file))

    if not names:
        print("No compound names supplied. Use --names, --csv, or --file.", file=sys.stderr)
        return 1

    imported = ingest_names(service, names, dry_run=args.dry_run)

    print(f"Processed {len(imported)} compounds")
    for record in imported[:10]:
        print(json.dumps({
            "key": record.get("key"),
            "name": record.get("name"),
            "canonical_name": record.get("canonical_name"),
            "inchikey": record.get("inchikey"),
            "external_ids": record.get("external_ids", {}),
        }, ensure_ascii=False, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
