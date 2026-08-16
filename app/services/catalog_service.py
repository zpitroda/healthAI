from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set

from app.data.compounds import COMPOUND_LIBRARY


def _get_default_compounds() -> List[Dict[str, Any]]:
    return [{"key": key, **value} for key, value in COMPOUND_LIBRARY.items()]


def _normalize_compound_name(name: str | None) -> str:
    cleaned = str(name or "").strip().lower()
    cleaned = re.sub(r"^(?:l-|d-|dl-|\(r\)-|\(s\)-|\(\+-\)-|\(±\)-)", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned)
    return cleaned


class CatalogService:
    def __init__(self, database_path: str | None = None):
        self._custom_database_path = database_path
        self._ensure_database()
        if not self.list_compounds(limit=1):
            self.seed_default_compounds()

    @property
    def database_path(self) -> str:
        if self._custom_database_path:
            return self._custom_database_path
        return os.getenv("HEALTHAI_CATALOG_DB", "./healthai_catalog.db")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compounds (
                    key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    canonical_name TEXT,
                    canonical_key TEXT,
                    inchikey TEXT,
                    smiles TEXT,
                    logp REAL,
                    tpsa REAL,
                    molecular_weight REAL,
                    pka REAL,
                    hbd INTEGER,
                    hba INTEGER,
                    rotatable_bonds INTEGER,
                    synonyms TEXT,
                    external_ids TEXT,
                    drug_class TEXT,
                    compound_class TEXT,
                    route_of_administration TEXT,
                    formulation TEXT,
                    mechanism TEXT,
                    receptor_targets TEXT,
                    transporters TEXT,
                    phase2_enzymes TEXT,
                    categories TEXT,
                    indications TEXT,
                    dosing TEXT,
                    reason TEXT,
                    citation TEXT,
                    contraindications TEXT,
                    side_effects TEXT,
                    interactions TEXT,
                    warnings TEXT,
                    boxed_warning TEXT,
                    is_narrow_therapeutic_index INTEGER DEFAULT 0,
                    dilirank_class TEXT,
                    half_life TEXT,
                    oral_bioavailability REAL,
                    t_max REAL,
                    volume_of_distribution REAL,
                    protein_binding REAL,
                    metabolism TEXT,
                    clearance REAL,
                    clearance_routes TEXT,
                    primary_effects TEXT,
                    cyp_enzymes TEXT,
                    organ_burdens TEXT,
                    synergies TEXT,
                    metadata TEXT,
                    evidence_level TEXT DEFAULT 'moderate',
                    risk_band TEXT DEFAULT 'low',
                    graph_tags TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(compounds)").fetchall()}
            additions = {
                "canonical_name": "TEXT",
                "canonical_key": "TEXT",
                "inchikey": "TEXT",
                "smiles": "TEXT",
                "logp": "REAL",
                "tpsa": "REAL",
                "molecular_weight": "REAL",
                "pka": "REAL",
                "hbd": "INTEGER",
                "hba": "INTEGER",
                "rotatable_bonds": "INTEGER",
                "synonyms": "TEXT",
                "external_ids": "TEXT",
                "drug_class": "TEXT",
                "compound_class": "TEXT",
                "route_of_administration": "TEXT",
                "formulation": "TEXT",
                "mechanism": "TEXT",
                "receptor_targets": "TEXT",
                "transporters": "TEXT",
                "phase2_enzymes": "TEXT",
                "categories": "TEXT",
                "indications": "TEXT",
                "dosing": "TEXT",
                "reason": "TEXT",
                "citation": "TEXT",
                "contraindications": "TEXT",
                "side_effects": "TEXT",
                "interactions": "TEXT",
                "warnings": "TEXT",
                "boxed_warning": "TEXT",
                "is_narrow_therapeutic_index": "INTEGER DEFAULT 0",
                "dilirank_class": "TEXT",
                "half_life": "TEXT",
                "oral_bioavailability": "REAL",
                "t_max": "REAL",
                "volume_of_distribution": "REAL",
                "protein_binding": "REAL",
                "metabolism": "TEXT",
                "clearance": "REAL",
                "clearance_routes": "TEXT",
                "primary_effects": "TEXT",
                "cyp_enzymes": "TEXT",
                "organ_burdens": "TEXT",
                "synergies": "TEXT",
            }
            for column_name, column_type in additions.items():
                if column_name not in existing_columns:
                    conn.execute(f"ALTER TABLE compounds ADD COLUMN {column_name} {column_type}")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_name ON compounds(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_canonical_name ON compounds(canonical_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_drug_class ON compounds(drug_class)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_mechanism ON compounds(mechanism)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_indications ON compounds(indications)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_inchikey ON compounds(inchikey)")

    def _resolve_canonical_key(self, compound: Dict[str, Any]) -> str | None:
        candidates = [
            compound.get("canonical_key"),
            compound.get("inchikey"),
            compound.get("standard_inchi_key"),
            compound.get("inchi_key"),
            (compound.get("metadata") or {}).get("inchikey") if isinstance(compound.get("metadata"), dict) else None,
        ]
        for value in candidates:
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
        return None

    def _merge_duplicate_record(self, conn: sqlite3.Connection, compound: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
        canonical_key = row.get("canonical_key") or row.get("inchikey")
        if not canonical_key:
            return row

        existing = conn.execute(
            "SELECT key FROM compounds WHERE canonical_key = ? OR inchikey = ? LIMIT 1",
            (canonical_key, canonical_key),
        ).fetchone()
        if existing is None or existing["key"] == row["key"]:
            return row

        row["key"] = existing["key"]
        return row

    def deduplicate_database(self) -> int:
        """Finds and merges duplicate compound entries in the SQLite database by normalized name."""
        merged_count = 0
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM compounds").fetchall()
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for r in rows:
                row_dict = dict(r)
                norm_key = _normalize_compound_name(row_dict.get("name") or row_dict.get("key"))
                if norm_key:
                    grouped.setdefault(norm_key, []).append(row_dict)

            for norm_key, group_rows in grouped.items():
                if len(group_rows) < 2:
                    continue

                group_rows.sort(
                    key=lambda r: (
                        len(str(r.get("mechanism") or "")),
                        len(str(r.get("receptor_targets") or "")),
                        0 if str(r.get("key", "")).startswith("CHEMBL") else 1,
                    ),
                    reverse=True,
                )

                primary = group_rows[0]
                secondary_rows = group_rows[1:]

                for sec in secondary_rows:
                    if not primary.get("canonical_key") and sec.get("canonical_key"):
                        primary["canonical_key"] = sec["canonical_key"]
                    if not primary.get("inchikey") and sec.get("inchikey"):
                        primary["inchikey"] = sec["inchikey"]
                    if not primary.get("smiles") and sec.get("smiles"):
                        primary["smiles"] = sec["smiles"]

                    conn.execute("DELETE FROM compounds WHERE key = ?", (sec["key"],))
                    merged_count += 1

                conn.execute(
                    "UPDATE compounds SET canonical_key = ?, inchikey = ?, smiles = COALESCE(smiles, ?) WHERE key = ?",
                    (primary.get("canonical_key"), primary.get("inchikey"), primary.get("smiles"), primary["key"]),
                )

            conn.commit()
        return merged_count

    def reset_database(self) -> None:
        with self._connect() as conn:
            conn.execute("DROP TABLE IF EXISTS compounds")
        self._ensure_database()
        self.seed_default_compounds()

    def seed_default_compounds(self) -> None:
        for compound in _get_default_compounds():
            self.upsert_compound(compound)

    def _serialize(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _deserialize(self, value: str | None, default: Any = None) -> Any:
        if value is None:
            return default if default is not None else []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else []

    def upsert_compound(self, compound: Dict[str, Any]) -> Dict[str, Any]:
        key = str(compound.get("key") or compound.get("name") or "compound").strip() or "compound"
        canonical_key = self._resolve_canonical_key(compound)
        if canonical_key:
            key = str(compound.get("key") or canonical_key).strip() or canonical_key

        row = {
            "key": key,
            "name": compound.get("name", key),
            "canonical_name": compound.get("canonical_name") or compound.get("name") or key,
            "canonical_key": canonical_key,
            "inchikey": canonical_key,
            "smiles": compound.get("smiles") or (compound.get("metadata", {}).get("chembl", {}) if isinstance(compound.get("metadata"), dict) else {}).get("smiles"),
            "logp": compound.get("logp") or compound.get("logP"),
            "tpsa": compound.get("tpsa"),
            "molecular_weight": compound.get("molecular_weight") or compound.get("mw"),
            "pka": compound.get("pka"),
            "hbd": compound.get("hbd"),
            "hba": compound.get("hba"),
            "rotatable_bonds": compound.get("rotatable_bonds"),
            "synonyms": self._serialize(compound.get("synonyms", [])),
            "external_ids": self._serialize(compound.get("external_ids", {})),
            "drug_class": compound.get("drug_class"),
            "compound_class": compound.get("compound_class"),
            "route_of_administration": compound.get("route_of_administration"),
            "formulation": compound.get("formulation"),
            "mechanism": compound.get("mechanism"),
            "receptor_targets": self._serialize(compound.get("receptor_targets", [])),
            "transporters": self._serialize(compound.get("transporters", {"substrates": [], "inhibitors": [], "inducers": []})),
            "phase2_enzymes": self._serialize(compound.get("phase2_enzymes", {"substrates": [], "inhibitors": [], "inducers": []})),
            "categories": self._serialize(compound.get("categories", [])),
            "indications": self._serialize(compound.get("indications", [])),
            "dosing": self._serialize(compound.get("dosing", {})),
            "reason": compound.get("reason"),
            "citation": compound.get("citation"),
            "contraindications": self._serialize(compound.get("contraindications", [])),
            "side_effects": self._serialize(compound.get("side_effects", [])),
            "interactions": self._serialize(compound.get("interactions", [])),
            "warnings": self._serialize(compound.get("warnings", [])),
            "boxed_warning": compound.get("boxed_warning"),
            "is_narrow_therapeutic_index": 1 if compound.get("is_narrow_therapeutic_index") else 0,
            "dilirank_class": compound.get("dilirank_class"),
            "half_life": compound.get("half_life"),
            "oral_bioavailability": compound.get("oral_bioavailability"),
            "t_max": compound.get("t_max"),
            "volume_of_distribution": compound.get("volume_of_distribution"),
            "protein_binding": compound.get("protein_binding"),
            "metabolism": compound.get("metabolism"),
            "clearance": compound.get("clearance"),
            "clearance_routes": compound.get("clearance_routes"),
            "primary_effects": self._serialize(compound.get("primary_effects", [])),
            "cyp_enzymes": self._serialize(compound.get("cyp_enzymes", {"substrates": [], "inhibitors": [], "inducers": []})),
            "organ_burdens": self._serialize(compound.get("organ_burdens", {})),
            "synergies": self._serialize(compound.get("synergies", [])),
            "metadata": self._serialize(compound.get("metadata", {})),
            "evidence_level": compound.get("evidence_level", "moderate"),
            "risk_band": compound.get("risk_band", "low"),
            "graph_tags": self._serialize(compound.get("graph_tags", [])),
        }

        with self._connect() as conn:
            row = self._merge_duplicate_record(conn, compound, row)
            conn.execute(
                """
                INSERT INTO compounds (
                    key, name, canonical_name, canonical_key, inchikey, smiles, logp, tpsa,
                    molecular_weight, pka, hbd, hba, rotatable_bonds, synonyms, external_ids,
                    drug_class, compound_class, route_of_administration, formulation, mechanism,
                    receptor_targets, transporters, phase2_enzymes, categories, indications, dosing,
                    reason, citation, contraindications, side_effects, interactions, warnings,
                    boxed_warning, is_narrow_therapeutic_index, dilirank_class, half_life,
                    oral_bioavailability, t_max, volume_of_distribution, protein_binding,
                    metabolism, clearance, clearance_routes, primary_effects, cyp_enzymes,
                    organ_burdens, synergies, metadata, evidence_level, risk_band, graph_tags, updated_at
                )
                VALUES (
                    :key, :name, :canonical_name, :canonical_key, :inchikey, :smiles, :logp, :tpsa,
                    :molecular_weight, :pka, :hbd, :hba, :rotatable_bonds, :synonyms, :external_ids,
                    :drug_class, :compound_class, :route_of_administration, :formulation, :mechanism,
                    :receptor_targets, :transporters, :phase2_enzymes, :categories, :indications, :dosing,
                    :reason, :citation, :contraindications, :side_effects, :interactions, :warnings,
                    :boxed_warning, :is_narrow_therapeutic_index, :dilirank_class, :half_life,
                    :oral_bioavailability, :t_max, :volume_of_distribution, :protein_binding,
                    :metabolism, :clearance, :clearance_routes, :primary_effects, :cyp_enzymes,
                    :organ_burdens, :synergies, :metadata, :evidence_level, :risk_band, :graph_tags, CURRENT_TIMESTAMP
                )
                ON CONFLICT(key) DO UPDATE SET
                    name = excluded.name,
                    canonical_name = excluded.canonical_name,
                    canonical_key = excluded.canonical_key,
                    inchikey = excluded.inchikey,
                    smiles = COALESCE(excluded.smiles, compounds.smiles),
                    logp = COALESCE(excluded.logp, compounds.logp),
                    tpsa = COALESCE(excluded.tpsa, compounds.tpsa),
                    molecular_weight = COALESCE(excluded.molecular_weight, compounds.molecular_weight),
                    pka = COALESCE(excluded.pka, compounds.pka),
                    hbd = COALESCE(excluded.hbd, compounds.hbd),
                    hba = COALESCE(excluded.hba, compounds.hba),
                    rotatable_bonds = COALESCE(excluded.rotatable_bonds, compounds.rotatable_bonds),
                    synonyms = excluded.synonyms,
                    external_ids = excluded.external_ids,
                    drug_class = excluded.drug_class,
                    compound_class = excluded.compound_class,
                    route_of_administration = excluded.route_of_administration,
                    formulation = excluded.formulation,
                    mechanism = excluded.mechanism,
                    receptor_targets = excluded.receptor_targets,
                    transporters = excluded.transporters,
                    phase2_enzymes = excluded.phase2_enzymes,
                    categories = excluded.categories,
                    indications = excluded.indications,
                    dosing = excluded.dosing,
                    reason = excluded.reason,
                    citation = excluded.citation,
                    contraindications = excluded.contraindications,
                    side_effects = excluded.side_effects,
                    interactions = excluded.interactions,
                    warnings = excluded.warnings,
                    boxed_warning = excluded.boxed_warning,
                    is_narrow_therapeutic_index = excluded.is_narrow_therapeutic_index,
                    dilirank_class = excluded.dilirank_class,
                    half_life = excluded.half_life,
                    oral_bioavailability = excluded.oral_bioavailability,
                    t_max = excluded.t_max,
                    volume_of_distribution = excluded.volume_of_distribution,
                    protein_binding = excluded.protein_binding,
                    metabolism = excluded.metabolism,
                    clearance = excluded.clearance,
                    clearance_routes = excluded.clearance_routes,
                    primary_effects = excluded.primary_effects,
                    cyp_enzymes = excluded.cyp_enzymes,
                    organ_burdens = excluded.organ_burdens,
                    synergies = excluded.synergies,
                    metadata = excluded.metadata,
                    evidence_level = excluded.evidence_level,
                    risk_band = excluded.risk_band,
                    graph_tags = excluded.graph_tags,
                    updated_at = CURRENT_TIMESTAMP
                """,
                row,
            )
            conn.commit()

        return self.get_compound(row["key"])

    def get_compound(self, key: str) -> Dict[str, Any] | None:
        if not key:
            return None

        normalized_query = str(key).strip().lower().replace(" ", "_").replace("-", "_")

        with self._connect() as conn:
            row = conn.execute("SELECT * FROM compounds WHERE key = ?", (key,)).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(key) = LOWER(?) LIMIT 1",
                    (key.strip(),),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(key) = LOWER(?) LIMIT 1",
                    (normalized_query,),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(name) = LOWER(?) OR LOWER(canonical_name) = LOWER(?) LIMIT 1",
                    (key.strip(), key.strip()),
                ).fetchone()

        if row is None:
            return None

        return self._row_to_compound(dict(row))

    def enrich_compound_online(self, key_or_name: str) -> Dict[str, Any] | None:
        """Enriches a compound in the catalog with live OpenFDA, ChEMBL, and RxNorm metadata."""
        from app.services.live_enrichment import LiveEnrichmentService

        compound = self.get_compound(key_or_name)
        if compound is None:
            # Create a placeholder compound to enrich
            compound = {
                "key": key_or_name.strip().lower().replace(" ", "_").replace("-", "_"),
                "name": key_or_name.strip().title(),
                "canonical_name": key_or_name.strip().title(),
            }

        enricher = LiveEnrichmentService()
        enriched = enricher.enrich_compound(compound)
        return self.upsert_compound(enriched)

    def get_compounds_by_keys(self, keys: List[str]) -> Dict[str, Dict[str, Any]]:
        if not keys:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        for key in keys:
            compound = self.get_compound(key)
            if compound:
                results[compound["key"]] = compound
                if compound.get("name"):
                    results[compound["name"].lower()] = compound

        return results

    def search_compounds(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        query_str = str(query or "").strip().lower()
        if not query_str:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM compounds ORDER BY name ASC").fetchall()
            unique_compounds: List[Dict[str, Any]] = []
            seen_names: Set[str] = set()
            for row in rows:
                c = self._row_to_compound(dict(row))
                norm_name = str(c.get("name") or c.get("key") or "").strip().lower()
                if norm_name and norm_name not in seen_names:
                    seen_names.add(norm_name)
                    unique_compounds.append(c)
                    if len(unique_compounds) >= limit:
                        break
            return unique_compounds

        with self._connect() as conn:
            pattern = f"%{query_str}%"
            rows = conn.execute(
                """
                SELECT * FROM compounds 
                WHERE LOWER(key) LIKE ? 
                   OR LOWER(name) LIKE ? 
                   OR LOWER(canonical_name) LIKE ? 
                   OR LOWER(drug_class) LIKE ?
                   OR LOWER(indications) LIKE ?
                   OR LOWER(synonyms) LIKE ?
                ORDER BY 
                  CASE 
                    WHEN LOWER(name) = LOWER(?) THEN 0
                    WHEN LOWER(name) LIKE ? THEN 1
                    WHEN LOWER(key) LIKE ? THEN 2
                    ELSE 3
                  END,
                  name ASC
                """,
                (pattern, pattern, pattern, pattern, pattern, pattern, query_str, f"{query_str}%", f"{query_str}%"),
            ).fetchall()

        unique_compounds = []
        seen_names = set()
        for row in rows:
            c = self._row_to_compound(dict(row))
            norm_name = str(c.get("name") or c.get("key") or "").strip().lower()
            if norm_name and norm_name not in seen_names:
                seen_names.add(norm_name)
                unique_compounds.append(c)
                if len(unique_compounds) >= limit:
                    break

        return unique_compounds

    def query_compounds(self, limit: int = 20, offset: int = 0, search: Optional[str] = None) -> tuple[List[Dict[str, Any]], int]:
        page_size = max(limit, 1)
        start = max(offset, 0)

        with self._connect() as conn:
            base_query = "FROM compounds"
            params: List[Any] = []
            where_clauses: List[str] = []

            if search:
                tokens = [part.strip().lower() for part in str(search).split() if part.strip()]
                for token in tokens:
                    where_clauses.append(
                        "(LOWER(COALESCE(key, '') || ' ' || COALESCE(name, '') || ' ' || COALESCE(canonical_name, '') || ' ' || COALESCE(drug_class, '') || ' ' || COALESCE(compound_class, '') || ' ' || COALESCE(route_of_administration, '') || ' ' || COALESCE(mechanism, '') || ' ' || COALESCE(synonyms, '') || ' ' || COALESCE(indications, '') || ' ' || COALESCE(graph_tags, '')) LIKE ?)"
                    )
                    params.append(f"%{token}%")

            where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            count_query = f"SELECT COUNT(*) AS total {base_query}{where_str}"
            total_row = conn.execute(count_query, params).fetchone()
            total = int(total_row["total"]) if total_row else 0

            select_query = f"SELECT * {base_query}{where_str} ORDER BY name ASC LIMIT ? OFFSET ?"
            fetch_params = list(params) + [page_size, start]
            rows = conn.execute(select_query, fetch_params).fetchall()

        return [self._row_to_compound(dict(row)) for row in rows], total

    def delete_compound(self, key: str) -> bool:
        if not key:
            return False
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM compounds WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def list_compounds(self, limit: int | None = None, offset: int = 0) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if limit is not None:
                rows = conn.execute("SELECT * FROM compounds ORDER BY name ASC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM compounds ORDER BY name ASC").fetchall()

        return [self._row_to_compound(dict(row)) for row in rows]

    def _row_to_compound(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "key": row["key"],
            "name": row["name"],
            "canonical_name": row.get("canonical_name") or row.get("name"),
            "canonical_key": row.get("canonical_key") or row.get("inchikey"),
            "inchikey": row.get("inchikey") or row.get("canonical_key"),
            "smiles": row.get("smiles"),
            "logp": row.get("logp"),
            "tpsa": row.get("tpsa"),
            "molecular_weight": row.get("molecular_weight"),
            "pka": row.get("pka"),
            "hbd": row.get("hbd"),
            "hba": row.get("hba"),
            "rotatable_bonds": row.get("rotatable_bonds"),
            "synonyms": self._deserialize(row.get("synonyms")),
            "external_ids": self._deserialize(row.get("external_ids"), default={}),
            "drug_class": row["drug_class"],
            "compound_class": row.get("compound_class"),
            "route_of_administration": row.get("route_of_administration"),
            "formulation": row.get("formulation"),
            "mechanism": row["mechanism"],
            "receptor_targets": self._deserialize(row.get("receptor_targets")),
            "transporters": self._deserialize(row.get("transporters"), default={"substrates": [], "inhibitors": [], "inducers": []}),
            "phase2_enzymes": self._deserialize(row.get("phase2_enzymes"), default={"substrates": [], "inhibitors": [], "inducers": []}),
            "categories": self._deserialize(row.get("categories")),
            "indications": self._deserialize(row.get("indications")),
            "dosing": self._deserialize(row.get("dosing"), default={}),
            "reason": row.get("reason"),
            "citation": row.get("citation"),
            "contraindications": self._deserialize(row.get("contraindications")),
            "side_effects": self._deserialize(row.get("side_effects")),
            "interactions": self._deserialize(row.get("interactions")),
            "warnings": self._deserialize(row.get("warnings")),
            "boxed_warning": row.get("boxed_warning"),
            "is_narrow_therapeutic_index": bool(row.get("is_narrow_therapeutic_index", 0)),
            "dilirank_class": row.get("dilirank_class"),
            "half_life": row.get("half_life"),
            "oral_bioavailability": row.get("oral_bioavailability"),
            "t_max": row.get("t_max"),
            "volume_of_distribution": row.get("volume_of_distribution"),
            "protein_binding": row.get("protein_binding"),
            "metabolism": row.get("metabolism"),
            "clearance": row.get("clearance"),
            "clearance_routes": row.get("clearance_routes"),
            "primary_effects": self._deserialize(row.get("primary_effects")),
            "cyp_enzymes": self._deserialize(row.get("cyp_enzymes"), default={"substrates": [], "inhibitors": [], "inducers": []}),
            "organ_burdens": self._deserialize(row.get("organ_burdens"), default={}),
            "synergies": self._deserialize(row.get("synergies"), default=[]),
            "metadata": self._deserialize(row.get("metadata"), default={}),
            "evidence_level": row.get("evidence_level", "moderate"),
            "risk_band": row.get("risk_band", "low"),
            "graph_tags": self._deserialize(row.get("graph_tags")),
        }
