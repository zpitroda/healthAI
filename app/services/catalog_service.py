from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from app.data.compounds import COMPOUND_LIBRARY

DEFAULT_CATALOG_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "healthai_catalog.db")


def _get_default_compounds() -> List[Dict[str, Any]]:
    return [{"key": key, **value} for key, value in COMPOUND_LIBRARY.items()]


CANONICAL_SYNONYM_MAP: Dict[str, str] = {
    "masteron": "drostanolone",
    "dromostanolone": "drostanolone",
    "drostanolonepropionate": "drostanolone",
    "drostanoloneenanthate": "drostanolone",
    "masteronpropionate": "drostanolone",
    "masteronenanthate": "drostanolone",
    "superdrol": "methyldrostanolone",
    "methasterone": "methyldrostanolone",
    "17amethyldrostanolone": "methyldrostanolone",
    "17alphamethyldrostanolone": "methyldrostanolone",
    "arimidex": "anastrozole",
    "femara": "letrozole",
    "aromasin": "exemestane",
    "proscar": "finasteride",
    "propecia": "finasteride",
    "avodart": "dutasteride",
    "micardis": "telmisartan",
    "inspra": "eplerenone",
    "cialis": "tadalafil",
    "viagra": "sildenafil",
    "levitra": "vardenafil",
    "valium": "diazepam",
    "xanax": "alprazolam",
    "accutane": "isotretinoin",
    "glucophage": "metformin",
    "jardiance": "empagliflozin",
    "farxiga": "dapagliflozin",
    "ozempic": "semaglutide",
    "wegovy": "semaglutide",
    "mounjaro": "tirzepatide",
    "zepbound": "tirzepatide",
    "bystolic": "nebivolol",
    "lopressor": "metoprolol",
    "tenormin": "atenolol",
    # Supplements & Nutraceuticals
    "astaxanthin": "astaxanthin",
    "asta": "astaxanthin",
    "astaxanthine": "astaxanthin",
    "astareal": "astaxanthin",
    "coq10": "coq10",
    "ubiquinol": "coq10",
    "ubiquinone": "coq10",
    "coenzymeq10": "coq10",
    "milkthistle": "milk_thistle",
    "silymarin": "milk_thistle",
    "silybin": "milk_thistle",
    "silybummarianum": "milk_thistle",
    "siliphos": "milk_thistle",
    "curcumin": "curcumin",
    "turmeric": "curcumin",
    "turmericextract": "curcumin",
    "curcuminoids": "curcumin",
    "theracurmin": "curcumin",
    "longvida": "curcumin",
    "citrusbergamot": "citrus_bergamot",
    "bergamot": "citrus_bergamot",
    "bergamotextract": "citrus_bergamot",
    "bergamonte": "citrus_bergamot",
    "bpf": "citrus_bergamot",
    "alphalipoicacid": "alpha_lipoic_acid",
    "ala": "alpha_lipoic_acid",
    "rala": "alpha_lipoic_acid",
    "rlipoicacid": "alpha_lipoic_acid",
    "thiocticacid": "alpha_lipoic_acid",
    "taurine": "taurine",
    "ltaurine": "taurine",
    "melatonin": "melatonin",
    "circadin": "melatonin",
    "nac": "nac",
    "nacetylcysteine": "nac",
    "acetylcysteine": "nac",
    "nacetylcysteine": "nac",
    "tudca": "tudca",
    "tauroursodeoxycholicacid": "tudca",
    "tauroursodeoxycholate": "tudca",
    "alcar": "l_carnitine",
    "acetyllcarnitine": "l_carnitine",
    "carnitine": "l_carnitine",
    "lcarnitine": "l_carnitine",
    "lcarnitinetartrate": "l_carnitine",
    "ltheanine": "l_theanine",
    "theanine": "l_theanine",
    "suntheanine": "l_theanine",
    "berberine": "berberine",
    "berberinehcl": "berberine",
    "omega3": "omega_3",
    "fishoil": "omega_3",
    "krilloil": "omega_3",
    "epadha": "omega_3",
    "epa": "omega_3",
    "dha": "omega_3",
    "ashwagandha": "ashwagandha",
    "ksm66": "ashwagandha",
    "sensoril": "ashwagandha",
    "withaniasomnifera": "ashwagandha",
    # Peptides & Research Bioregulators
    "bpc157": "bpc_157",
    "bpc": "bpc_157",
    "bodyprotectioncompound157": "bpc_157",
    "pl14736": "bpc_157",
    "tb500": "tb_500",
    "thymosinbeta4": "tb_500",
    "tbeta4": "tb_500",
    "ghkcu": "ghk_cu",
    "copperpeptide": "ghk_cu",
    "glycylhistidyllysine": "ghk_cu",
    "kpv": "kpv",
    "ara290": "ara_290",
    "cibinetide": "ara_290",
    "ipamorelin": "ipamorelin",
    "ipam": "ipamorelin",
    "cjc1295": "cjc_1295",
    "cjc1295dac": "cjc_1295",
    "cjc1295nodac": "cjc_1295",
    "modgrf": "cjc_1295",
    "modgrf129": "cjc_1295",
    "sermorelin": "sermorelin",
    "geref": "sermorelin",
    "tesamorelin": "tesamorelin",
    "egrifta": "tesamorelin",
    "ghrp2": "ghrp_2",
    "pralmorelin": "ghrp_2",
    "ghrp6": "ghrp_6",
    "hexarelin": "hexarelin",
    "examorelin": "hexarelin",
    "aod9604": "aod_9604",
    "aod": "aod_9604",
    "semaglutide": "semaglutide",
    "ozempic": "semaglutide",
    "wegovy": "semaglutide",
    "rybelsus": "semaglutide",
    "tirzepatide": "tirzepatide",
    "mounjaro": "tirzepatide",
    "zepbound": "tirzepatide",
    "retatrutide": "retatrutide",
    "ly3437943": "retatrutide",
    "cagrilintide": "cagrilintide",
    "melanotanii": "melanotan_ii",
    "melanotan2": "melanotan_ii",
    "mt2": "melanotan_ii",
    "bremelanotide": "bremelanotide",
    "pt141": "bremelanotide",
    "vyleesi": "bremelanotide",
    "semax": "semax",
    "selank": "selank",
    "epithalon": "epithalon",
    "epitalon": "epithalon",
    "epithalone": "epithalon",
    "dsip": "dsip",
    "deltasleepinducingpeptide": "dsip",
    "oxytocin": "oxytocin",
    "pitocin": "oxytocin",
    "motsc": "mots_c",
    "mots": "mots_c",
    "ss31": "elamipretide",
    "elamipretide": "elamipretide",
    "bendavia": "elamipretide",
    "thymosinalpha1": "thymosin_alpha_1",
    "thymalfasin": "thymosin_alpha_1",
    "zadaxin": "thymosin_alpha_1",
    "talpha1": "thymosin_alpha_1",
    "kisspeptin10": "kisspeptin_10",
    "kisspeptin": "kisspeptin_10",
    "kp10": "kisspeptin_10",
    "desmopressin": "desmopressin",
    "ddavp": "desmopressin",
    "octreotide": "octreotide",
    "sandostatin": "octreotide",
    "leuprolide": "leuprolide",
    "lupron": "leuprolide",
    "leuprorelin": "leuprolide",
}



def _normalize_compound_name(name: str | None) -> str:
    cleaned = str(name or "").strip().lower()
    cleaned = re.sub(r"^(?:l-|d-|dl-|\(r\)-|\(s\)-|\(\+-\)-|\(±\)-)", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned)
    return cleaned


_CATALOG_MEMORY_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}


class CatalogService:
    def __init__(self, database_path: str | None = None):
        self._custom_database_path = database_path
        self._ensure_database()
        self.sync_seed_compounds()

    def sync_seed_compounds(self) -> None:
        for compound in _get_default_compounds():
            k = compound.get("key") or compound.get("name")
            if k:
                self.upsert_compound(compound)

    @property
    def database_path(self) -> str:
        if self._custom_database_path:
            return self._custom_database_path
        env_db = os.getenv("HEALTHAI_CATALOG_DB")
        if env_db:
            return env_db
        return DEFAULT_CATALOG_DB_PATH

    def _connect(self) -> sqlite3.Connection:
        db_dir = os.path.dirname(self.database_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL;")
            connection.execute("PRAGMA synchronous=NORMAL;")
            connection.execute("PRAGMA temp_store=MEMORY;")
            connection.execute("PRAGMA cache_size=-64000;")
        except sqlite3.DatabaseError:
            pass
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
                    t_half_numeric REAL,
                    bioavailability_f REAL,
                    volume_of_distribution_l_kg REAL,
                    clearance_l_h_kg REAL,
                    t_max_h REAL,
                    c_max_ng_ml REAL,
                    fraction_unbound REAL,
                    protein_binding_pct REAL,
                    absorption_rate_ka REAL,
                    renal_clearance_fraction REAL,
                    bcs_class TEXT,
                    mec_ng_ml REAL,
                    mtc_ng_ml REAL,
                    therapeutic_index REAL,
                    e_max REAL,
                    ec50_nm REAL,
                    ic50_nm REAL,
                    hill_coefficient REAL,
                    pathway_details TEXT,
                    source_tier TEXT DEFAULT 'seed',
                    last_enriched_at TEXT,
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
                "t_half_numeric": "REAL",
                "bioavailability_f": "REAL",
                "volume_of_distribution_l_kg": "REAL",
                "clearance_l_h_kg": "REAL",
                "t_max_h": "REAL",
                "c_max_ng_ml": "REAL",
                "fraction_unbound": "REAL",
                "protein_binding_pct": "REAL",
                "absorption_rate_ka": "REAL",
                "renal_clearance_fraction": "REAL",
                "bcs_class": "TEXT",
                "mec_ng_ml": "REAL",
                "mtc_ng_ml": "REAL",
                "therapeutic_index": "REAL",
                "e_max": "REAL",
                "ec50_nm": "REAL",
                "ic50_nm": "REAL",
                "hill_coefficient": "REAL",
                "pathway_details": "TEXT",
                "source_tier": "TEXT DEFAULT 'seed'",
                "last_enriched_at": "TEXT",
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_compounds_source_tier ON compounds(source_tier)")

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
        keys_to_del = [k for k in _CATALOG_MEMORY_CACHE if k[0] == self.database_path]
        for k in keys_to_del:
            _CATALOG_MEMORY_CACHE.pop(k, None)
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
            "t_half_numeric": compound.get("t_half_numeric"),
            "bioavailability_f": compound.get("bioavailability_f"),
            "volume_of_distribution_l_kg": compound.get("volume_of_distribution_l_kg"),
            "clearance_l_h_kg": compound.get("clearance_l_h_kg"),
            "t_max_h": compound.get("t_max_h"),
            "c_max_ng_ml": compound.get("c_max_ng_ml"),
            "fraction_unbound": compound.get("fraction_unbound"),
            "protein_binding_pct": compound.get("protein_binding_pct"),
            "absorption_rate_ka": compound.get("absorption_rate_ka"),
            "renal_clearance_fraction": compound.get("renal_clearance_fraction"),
            "bcs_class": compound.get("bcs_class"),
            "mec_ng_ml": compound.get("mec_ng_ml"),
            "mtc_ng_ml": compound.get("mtc_ng_ml"),
            "therapeutic_index": compound.get("therapeutic_index"),
            "e_max": compound.get("e_max"),
            "ec50_nm": compound.get("ec50_nm"),
            "ic50_nm": compound.get("ic50_nm"),
            "hill_coefficient": compound.get("hill_coefficient"),
            "pathway_details": self._serialize(compound.get("pathway_details", [])),
            "source_tier": compound.get("source_tier", "seed"),
            "last_enriched_at": compound.get("last_enriched_at"),
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
                    organ_burdens, synergies, metadata, evidence_level, risk_band, graph_tags,
                    t_half_numeric, bioavailability_f, volume_of_distribution_l_kg, clearance_l_h_kg,
                    t_max_h, c_max_ng_ml, fraction_unbound, protein_binding_pct, absorption_rate_ka,
                    renal_clearance_fraction, bcs_class, mec_ng_ml, mtc_ng_ml, therapeutic_index,
                    e_max, ec50_nm, ic50_nm, hill_coefficient, pathway_details, source_tier,
                    last_enriched_at, updated_at
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
                    :organ_burdens, :synergies, :metadata, :evidence_level, :risk_band, :graph_tags,
                    :t_half_numeric, :bioavailability_f, :volume_of_distribution_l_kg, :clearance_l_h_kg,
                    :t_max_h, :c_max_ng_ml, :fraction_unbound, :protein_binding_pct, :absorption_rate_ka,
                    :renal_clearance_fraction, :bcs_class, :mec_ng_ml, :mtc_ng_ml, :therapeutic_index,
                    :e_max, :ec50_nm, :ic50_nm, :hill_coefficient, :pathway_details, :source_tier,
                    :last_enriched_at, CURRENT_TIMESTAMP
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
                    t_half_numeric = COALESCE(excluded.t_half_numeric, compounds.t_half_numeric),
                    bioavailability_f = COALESCE(excluded.bioavailability_f, compounds.bioavailability_f),
                    volume_of_distribution_l_kg = COALESCE(excluded.volume_of_distribution_l_kg, compounds.volume_of_distribution_l_kg),
                    clearance_l_h_kg = COALESCE(excluded.clearance_l_h_kg, compounds.clearance_l_h_kg),
                    t_max_h = COALESCE(excluded.t_max_h, compounds.t_max_h),
                    c_max_ng_ml = COALESCE(excluded.c_max_ng_ml, compounds.c_max_ng_ml),
                    fraction_unbound = COALESCE(excluded.fraction_unbound, compounds.fraction_unbound),
                    protein_binding_pct = COALESCE(excluded.protein_binding_pct, compounds.protein_binding_pct),
                    absorption_rate_ka = COALESCE(excluded.absorption_rate_ka, compounds.absorption_rate_ka),
                    renal_clearance_fraction = COALESCE(excluded.renal_clearance_fraction, compounds.renal_clearance_fraction),
                    bcs_class = COALESCE(excluded.bcs_class, compounds.bcs_class),
                    mec_ng_ml = COALESCE(excluded.mec_ng_ml, compounds.mec_ng_ml),
                    mtc_ng_ml = COALESCE(excluded.mtc_ng_ml, compounds.mtc_ng_ml),
                    therapeutic_index = COALESCE(excluded.therapeutic_index, compounds.therapeutic_index),
                    e_max = COALESCE(excluded.e_max, compounds.e_max),
                    ec50_nm = COALESCE(excluded.ec50_nm, compounds.ec50_nm),
                    ic50_nm = COALESCE(excluded.ic50_nm, compounds.ic50_nm),
                    hill_coefficient = COALESCE(excluded.hill_coefficient, compounds.hill_coefficient),
                    pathway_details = COALESCE(excluded.pathway_details, compounds.pathway_details),
                    source_tier = COALESCE(excluded.source_tier, compounds.source_tier),
                    last_enriched_at = COALESCE(excluded.last_enriched_at, compounds.last_enriched_at),
                    updated_at = CURRENT_TIMESTAMP
                """,
                row,
            )
            conn.commit()

        # Invalidate memory cache for updated record
        for alias in [row.get("key"), row.get("name"), row.get("canonical_name")]:
            if alias:
                _CATALOG_MEMORY_CACHE.pop((self.database_path, _normalize_compound_name(alias)), None)

        return self.get_compound(row["key"], auto_enrich=False)

    def get_compound(self, key: str, auto_enrich: bool = True) -> Dict[str, Any] | None:
        if not key:
            return None

        norm_query = _normalize_compound_name(key)
        cache_key = (self.database_path, norm_query)
        if cache_key in _CATALOG_MEMORY_CACHE:
            return copy.deepcopy(_CATALOG_MEMORY_CACHE[cache_key])

        # Resolve known synonym/brand aliases to canonical entity key
        if norm_query in CANONICAL_SYNONYM_MAP:
            canonical_key = CANONICAL_SYNONYM_MAP[norm_query]
            if canonical_key != key:
                canon_res = self.get_compound(canonical_key, auto_enrich=auto_enrich)
                if canon_res:
                    _CATALOG_MEMORY_CACHE[cache_key] = canon_res
                    return copy.deepcopy(canon_res)

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
                # Exact InChIKey or canonical_key match
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(canonical_key) = LOWER(?) OR LOWER(inchikey) = LOWER(?) LIMIT 1",
                    (key.strip(), key.strip()),
                ).fetchone()
            if row is None:
                # Exact synonym match in JSON synonyms array
                clean_syn = key.strip().lower()
                row = conn.execute(
                    "SELECT * FROM compounds WHERE LOWER(synonyms) LIKE ? LIMIT 1",
                    (f'%"{clean_syn}"%',),
                ).fetchone()
            if row is None:
                # Normalized alphanumeric match across keys, names, and all synonyms
                target_norm = _normalize_compound_name(key)
                all_rows = conn.execute("SELECT * FROM compounds").fetchall()
                for r in all_rows:
                    if _normalize_compound_name(r["key"]) == target_norm or _normalize_compound_name(r["name"]) == target_norm:
                        row = r
                        break
                    syns = self._deserialize(r["synonyms"], [])
                    for s in syns:
                        if _normalize_compound_name(str(s)) == target_norm:
                            row = r
                            break
                    if row is not None:
                        break

        if row is not None:
            comp = self._row_to_compound(dict(row))
            for alias in [comp.get("key"), comp.get("name"), comp.get("canonical_name"), comp.get("canonical_key"), comp.get("inchikey"), key] + list(comp.get("synonyms") or []):
                if alias:
                    _CATALOG_MEMORY_CACHE[(self.database_path, _normalize_compound_name(alias))] = comp
            return copy.deepcopy(comp)

        if not auto_enrich:
            return None

        # Write-through lazy enrichment fallback
        try:
            from app.services.live_enrichment import LiveEnrichmentService
            enricher = LiveEnrichmentService()
            profile = enricher.fetch_compound_profile(key)
            if profile:
                return self.upsert_compound(profile)
        except Exception:
            pass

        return None

    def canonicalize_and_merge_stack(self, stack: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Unifies and merges stack entries that refer to the same chemical compound under different names
        (e.g., Drostanolone and Masteron, Methyldrostanolone and Superdrol).
        Aggregates dosages cleanly into a single canonical entry.
        """
        if not stack:
            return []

        merged_by_canonical: Dict[str, Dict[str, Any]] = {}
        for item in stack:
            if not isinstance(item, dict):
                continue
            raw_key = str(item.get("key") or item.get("name") or "").strip()
            if not raw_key:
                continue

            try:
                comp = self.get_compound(raw_key, auto_enrich=False)
            except TypeError:
                comp = self.get_compound(raw_key)
            canonical_id = (comp.get("canonical_key") or comp.get("inchikey") or comp.get("key") or raw_key).lower() if comp else raw_key.lower()

            dose_val = item.get("dose") if item.get("dose") is not None else item.get("dose_mg")
            try:
                dose_mg = float(dose_val) if dose_val is not None else None
            except (ValueError, TypeError):
                dose_mg = None

            unit = str(item.get("unit") or "mg").strip()

            if canonical_id in merged_by_canonical:
                existing = merged_by_canonical[canonical_id]
                if dose_mg is not None:
                    if existing.get("dose_mg") is not None:
                        existing["dose_mg"] += dose_mg
                        existing["dose"] = existing["dose_mg"]
                    else:
                        existing["dose_mg"] = dose_mg
                        existing["dose"] = dose_mg
                if "synonyms_merged" not in existing:
                    existing["synonyms_merged"] = [existing.get("name") or existing.get("key")]
                existing["synonyms_merged"].append(item.get("name") or raw_key)
            else:
                if comp:
                    new_entry = dict(comp)
                    new_entry.update(item)
                    new_entry["key"] = comp.get("key") or raw_key
                    new_entry["canonical_key"] = comp.get("canonical_key") or comp.get("key")
                    new_entry["canonical_name"] = comp.get("canonical_name") or comp.get("name")
                    new_entry["name"] = comp.get("name") or item.get("name") or comp.get("canonical_name")
                    new_entry["drug_class"] = comp.get("drug_class") or item.get("drug_class")
                    new_entry["inchikey"] = comp.get("inchikey")
                else:
                    new_entry = dict(item)
                if dose_mg is not None:
                    new_entry["dose_mg"] = dose_mg
                    new_entry["dose"] = dose_mg
                    new_entry["unit"] = unit
                merged_by_canonical[canonical_id] = new_entry

        return list(merged_by_canonical.values())

    def enrich_compound_online(self, key_or_name: str) -> Dict[str, Any] | None:
        """Enriches a compound in the catalog with live OpenFDA, ChEMBL, and RxNorm metadata."""
        from app.services.live_enrichment import LiveEnrichmentService
        from datetime import datetime, timezone

        compound = self.get_compound(key_or_name, auto_enrich=False)
        enricher = LiveEnrichmentService()
        if compound is None:
            return enricher.enrich_and_cache(key_or_name, catalog_service=self)

        enriched = enricher.enrich_compound(compound)
        enriched["source_tier"] = "live_enrichment"
        enriched["last_enriched_at"] = datetime.now(timezone.utc).isoformat()
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

    def search_compounds(self, query: str, limit: int = 20, auto_enrich: bool = True) -> List[Dict[str, Any]]:
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

        if unique_compounds:
            return unique_compounds

        # On-demand write-through lookup if search returned 0 matches
        if auto_enrich and len(query_str) >= 3:
            try:
                enriched = self.get_compound(query_str, auto_enrich=True)
                if enriched:
                    return [enriched]
            except Exception:
                pass

        return []

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
        keys_to_del = [k for k in _CATALOG_MEMORY_CACHE if k[0] == self.database_path and (k[1] == _normalize_compound_name(key) or _CATALOG_MEMORY_CACHE[k].get("key") == key)]
        for k in keys_to_del:
            _CATALOG_MEMORY_CACHE.pop(k, None)
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
        compound = {
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
            "t_half_numeric": row.get("t_half_numeric"),
            "bioavailability_f": row.get("bioavailability_f"),
            "volume_of_distribution_l_kg": row.get("volume_of_distribution_l_kg"),
            "clearance_l_h_kg": row.get("clearance_l_h_kg"),
            "t_max_h": row.get("t_max_h"),
            "c_max_ng_ml": row.get("c_max_ng_ml"),
            "fraction_unbound": row.get("fraction_unbound"),
            "protein_binding_pct": row.get("protein_binding_pct"),
            "absorption_rate_ka": row.get("absorption_rate_ka"),
            "renal_clearance_fraction": row.get("renal_clearance_fraction"),
            "bcs_class": row.get("bcs_class"),
            "mec_ng_ml": row.get("mec_ng_ml"),
            "mtc_ng_ml": row.get("mtc_ng_ml"),
            "therapeutic_index": row.get("therapeutic_index"),
            "e_max": row.get("e_max"),
            "ec50_nm": row.get("ec50_nm"),
            "ic50_nm": row.get("ic50_nm"),
            "hill_coefficient": row.get("hill_coefficient"),
            "pathway_details": self._deserialize(row.get("pathway_details"), default=[]),
            "source_tier": row.get("source_tier", "seed"),
            "last_enriched_at": row.get("last_enriched_at"),
        }

        burdens = compound.get("organ_burdens") or {}
        if not burdens or all(v == "none" for v in burdens.values()):
            from app.services.pharmacology_enricher import PharmacologyEnricher
            compound = PharmacologyEnricher.enrich_compound(compound)

        from app.services.dosing_service import get_default_compound_dose
        dose_info = get_default_compound_dose(compound)
        compound["default_dose"] = dose_info
        compound["dose"] = dose_info["dose_val"]
        compound["unit"] = dose_info["dose_unit"]
        compound["dose_display"] = dose_info["dose_display"]

        return compound
