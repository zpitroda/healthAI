from __future__ import annotations

import os
import re
import sqlite3
import time
from typing import Any, Dict, Optional, Union
import httpx

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "compounds.db")

# Authoritative clinical seed benchmarks for instant cache bootstrap
SEED_CLINICAL_REFERENCE_DOSES_MG: Dict[str, float] = {
    # Beta-agonists & Sympathomimetics
    "clenbuterol": 0.04,      # 40 mcg (0.04 mg) standard single athletic/therapeutic dose
    "chembl49080": 0.04,
    "albuterol": 4.0,         # 4 mg oral
    "salbutamol": 4.0,
    "chembl714": 4.0,
    "ephedrine": 25.0,        # 25 mg
    "pseudoephedrine": 60.0,  # 60 mg
    "yohimbine": 5.0,         # 5 mg
    "synephrine": 20.0,       # 20 mg

    # Beta-blockers
    "nebivolol": 5.0,         # 5 mg standard adult dose
    "chembl434394": 5.0,
    "propranolol": 40.0,      # 40 mg
    "chembl27": 40.0,
    "metoprolol": 50.0,       # 50 mg
    "chembl18": 50.0,
    "atenolol": 50.0,         # 50 mg
    "chembl25": 50.0,
    "carvedilol": 12.5,       # 12.5 mg
    "chembl641": 12.5,
    "bisoprolol": 5.0,        # 5 mg
    "chembl525": 5.0,

    # Alpha-2 Agonists
    "clonidine": 0.1,         # 100 mcg (0.1 mg)
    "chembl39": 0.1,
    "guanfacine": 1.0,        # 1 mg
    "chembl754": 1.0,

    # Ergogenics, Nootropics & Stimulants
    "caffeine": 200.0,        # 200 mg standard single dose
    "theanine": 200.0,        # 200 mg
    "l_theanine": 200.0,
    "creatine": 5000.0,       # 5 g (5000 mg) maintenance dose
    "creatine_monohydrate": 5000.0,
    "beta_alanine": 3200.0,   # 3.2 g
    "citrulline": 6000.0,     # 6 g
    "l_citrulline": 6000.0,
    "citrulline_malate": 8000.0,
    "alpha_gpc": 300.0,       # 300 mg
    "tyrosine": 1000.0,       # 1000 mg / 1 g
    "l_tyrosine": 1000.0,
    "ashwagandha": 600.0,     # 600 mg extract
    "rhodiola": 300.0,        # 300 mg
    "bacopa": 300.0,          # 300 mg
    "modafinil": 100.0,       # 100 mg
    "armodafinil": 150.0,     # 150 mg
    "nac": 600.0,             # 600 mg
    "n_acetylcysteine": 600.0,
    "acetylcysteine": 600.0,
    "tudca": 500.0,           # 500 mg
    "glutathione": 500.0,     # 500 mg

    # RAAS & Blood Pressure
    "telmisartan": 40.0,      # 40 mg
    "chembl723": 40.0,
    "losartan": 50.0,         # 50 mg
    "chembl159": 50.0,
    "valsartan": 80.0,        # 80 mg
    "chembl667": 80.0,
    "olmesartan": 20.0,       # 20 mg
    "eplerenone": 50.0,       # 50 mg
    "chembl1201127": 50.0,
    "spironolactone": 50.0,   # 50 mg
    "chembl1415": 50.0,
    "lisinopril": 10.0,       # 10 mg
    "ramipril": 5.0,          # 5 mg
    "amlodipine": 5.0,        # 5 mg
    "diltiazem": 120.0,       # 120 mg
    "verapamil": 80.0,        # 80 mg

    # Metabolic & Lipids
    "metformin": 500.0,       # 500 mg
    "chembl1431": 500.0,
    "empagliflozin": 10.0,    # 10 mg/day
    "chembl2107830": 10.0,
    "dapagliflozin": 10.0,    # 10 mg/day
    "chembl1229517": 10.0,
    "semaglutide": 0.25,      # 0.25 mg/day
    "tirzepatide": 0.7,       # 0.7 mg/day
    "atorvastatin": 20.0,     # 20 mg/day
    "chembl1487": 20.0,
    "rosuvastatin": 10.0,     # 10 mg/day
    "chembl438": 10.0,
    "simvastatin": 20.0,      # 20 mg/day
    "ezetimibe": 10.0,        # 10 mg/day
    "berberine": 500.0,       # 500 mg/day

    # Androgens, Endocrine & 5-AR
    "testosterone": 20.0,     # 20 mg/day standard daily replacement dose
    "chembl386630": 20.0,
    "finasteride": 1.0,       # 1 mg/day (alopecia) or 5 mg (BPH)
    "chembl553": 1.0,
    "dutasteride": 0.5,       # 0.5 mg/day
    "chembl1201083": 0.5,
    "anastrozole": 0.5,       # 0.5 mg/day
    "exemestane": 12.5,       # 12.5 mg/day
    "tamoxifen": 20.0,        # 20 mg/day
    "clomiphene": 25.0,       # 25 mg/day
    "enclomiphene": 12.5,     # 12.5 mg/day

    # Anti-inflammatory & Analgesics
    "aspirin": 81.0,          # 81 mg cardioprotective (or 325 mg)
    "ibuprofen": 400.0,       # 400 mg
    "naproxen": 250.0,        # 250 mg
    "celecoxib": 100.0,       # 100 mg
    "acetaminophen": 500.0,   # 500 mg
    "paracetamol": 500.0,

    # CNS & Anxiolytics
    "diazepam": 10.0,         # 10 mg
    "chembl12": 10.0,
    "alprazolam": 0.5,        # 0.5 mg (500 mcg)
    "chembl698": 0.5,
    "lorazepam": 1.0,         # 1 mg
    "clonazepam": 0.5,        # 0.5 mg
    "buspirone": 10.0,        # 10 mg
    "gabapentin": 300.0,      # 300 mg
    "pregabalin": 75.0,       # 75 mg
    "melatonin": 3.0,         # 3 mg

    # Peptides & Incretin Mimetics
    "bpc_157": 0.5,           # 500 mcg (0.5 mg)
    "bpc157": 0.5,
    "tb_500": 2.5,            # 2.5 mg
    "tb500": 2.5,
    "ghk_cu": 2.0,            # 2 mg
    "kpv": 0.5,               # 500 mcg
    "ara_290": 4.0,           # 4 mg
    "ipamorelin": 0.2,        # 200 mcg
    "cjc_1295": 0.1,          # 100 mcg
    "sermorelin": 0.3,        # 300 mcg
    "tesamorelin": 2.0,       # 2 mg
    "ghrp_2": 0.1,            # 100 mcg
    "ghrp_6": 0.1,            # 100 mcg
    "hexarelin": 0.1,         # 100 mcg
    "aod_9604": 0.3,          # 300 mcg
    "semaglutide": 0.5,       # 0.5 mg/week
    "tirzepatide": 5.0,       # 5 mg/week
    "retatrutide": 2.0,       # 2 mg/week
    "cagrilintide": 0.6,      # 0.6 mg/week
    "melanotan_ii": 0.5,      # 500 mcg
    "bremelanotide": 1.75,    # 1.75 mg
    "semax": 0.6,             # 600 mcg
    "selank": 0.4,            # 400 mcg
    "epithalon": 5.0,         # 5 mg
    "epitalon": 5.0,
    "dsip": 0.1,              # 100 mcg
    "oxytocin": 0.05,         # 50 mcg (30 IU)
    "mots_c": 5.0,            # 5 mg
    "elamipretide": 10.0,     # 10 mg
    "ss31": 10.0,
    "thymosin_alpha_1": 1.6,  # 1.6 mg
    "kisspeptin_10": 0.1,     # 100 mcg
    "desmopressin": 0.1,      # 100 mcg (0.1 mg)
    "octreotide": 0.1,        # 100 mcg
    "leuprolide": 3.75,       # 3.75 mg
}

# Compatibility reference mapping
CLINICAL_REFERENCE_DOSES_MG: Dict[str, float] = dict(SEED_CLINICAL_REFERENCE_DOSES_MG)


def _get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or os.environ.get("COMPOUNDS_DB_PATH") or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cached_reference_doses (
            compound_key TEXT PRIMARY KEY,
            dose_mg REAL NOT NULL,
            unit TEXT DEFAULT 'mg',
            basis TEXT NOT NULL,
            source TEXT DEFAULT 'openfda_daily_med',
            updated_at REAL NOT NULL
        )
        """
    )
    # Warm table if empty
    count = conn.execute("SELECT count(*) FROM cached_reference_doses").fetchone()[0]
    if count == 0:
        now = time.time()
        for k, v in SEED_CLINICAL_REFERENCE_DOSES_MG.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO cached_reference_doses (compound_key, dose_mg, unit, basis, source, updated_at)
                VALUES (?, ?, 'mg', 'clinical_reference', 'seed', ?)
                """,
                (k, v, now),
            )
        conn.commit()
    return conn


def canonicalize_token(name: str) -> str:
    """Strip punctuation and whitespace for robust key lookup."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def fetch_openfda_dosing(query_name: str) -> Optional[float]:
    """Dynamically query OpenFDA drug label API for package strength and recommended dosing."""
    cleaned = query_name.strip().lower()
    if not cleaned:
        return None
    try:
        url = "https://api.fda.gov/drug/label.json"
        search_query = f'openfda.generic_name:"{cleaned}"+OR+openfda.brand_name:"{cleaned}"'
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url, params={"search": search_query, "limit": 1})
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    label = results[0]
                    # Parse dosage text or active ingredient strength
                    dosage_text = " ".join(label.get("dosage_and_administration", []))
                    match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|microgram|g)", dosage_text, re.IGNORECASE)
                    if match:
                        num = float(match.group(1))
                        u = match.group(2).lower()
                        if "mcg" in u or "micro" in u:
                            return num / 1000.0
                        elif "g" == u:
                            return num * 1000.0
                        return num
    except Exception:
        pass
    return None


def get_default_compound_dose(
    compound_or_key: Union[str, Dict[str, Any]],
    weight_kg: float = 70.0,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Determine the most accurate standard clinical/ergogenic default dose and natural unit
    dynamically calculated from SQLite cache, PK parameters, or OpenFDA.
    """
    key_str = ""
    name_str = ""
    dosing_data: Dict[str, Any] = {}
    compound_dict: Dict[str, Any] = {}

    if isinstance(compound_or_key, dict):
        compound_dict = compound_or_key
        key_str = str(compound_or_key.get("key") or "").lower()
        name_str = str(compound_or_key.get("name") or compound_or_key.get("canonical_name") or "").lower()
        dosing_raw = compound_or_key.get("dosing")
        if isinstance(dosing_raw, dict):
            dosing_data = dosing_raw
    else:
        key_str = str(compound_or_key or "").lower().strip()
        name_str = key_str

    clean_key = canonicalize_token(key_str)
    clean_name = canonicalize_token(name_str)

    dose_mg: Optional[float] = None
    basis = "clinical_reference"

    # 1. Check SQLite Persistent Cache
    try:
        with _get_db_connection(db_path) as conn:
            row = conn.execute(
                "SELECT dose_mg, basis FROM cached_reference_doses WHERE compound_key IN (?, ?, ?, ?)",
                (key_str, clean_key, name_str, clean_name),
            ).fetchone()
            if row:
                dose_mg = float(row["dose_mg"])
                basis = str(row["basis"])
    except Exception:
        pass

    # 2. Check compound structured dosing dictionary if available
    if dose_mg is None and dosing_data:
        mg_per_kg_data = dosing_data.get("mg_per_kg")
        if isinstance(mg_per_kg_data, dict):
            common_val = mg_per_kg_data.get("common") or mg_per_kg_data.get("threshold")
            if isinstance(common_val, (int, float)) and common_val > 0:
                dose_mg = round(float(common_val) * weight_kg, 2)
                basis = "weight_scaled_mg_per_kg"
        elif isinstance(dosing_data.get("common_dose_mg"), (int, float)):
            dose_mg = float(dosing_data["common_dose_mg"])
            basis = "catalog_dosing_entry"

    # 3. Dynamic PK Calculation: Dose = (C_target * Vd * W) / (F * 1000)
    if dose_mg is None and compound_dict:
        vd_l_kg = compound_dict.get("volume_of_distribution_l_kg") or compound_dict.get("volume_of_distribution")
        mec_ng_ml = compound_dict.get("mec_ng_ml")
        bioav = compound_dict.get("bioavailability_f") or compound_dict.get("oral_bioavailability") or 1.0
        if isinstance(vd_l_kg, (int, float)) and isinstance(mec_ng_ml, (int, float)) and float(vd_l_kg) > 0 and float(mec_ng_ml) > 0:
            target_conc = float(mec_ng_ml) * 1.5  # ng/mL = ug/L
            total_vd_l = float(vd_l_kg) * weight_kg
            calculated_mg = (target_conc * total_vd_l) / (max(0.1, float(bioav)) * 1000.0)
            if 0.001 < calculated_mg < 10000.0:
                dose_mg = round(calculated_mg, 2)
                basis = "dynamic_pk_vd_mec_calculation"

    # 4. Fallback lookup in seed reference table
    if dose_mg is None:
        dose_mg = (
            SEED_CLINICAL_REFERENCE_DOSES_MG.get(key_str)
            or SEED_CLINICAL_REFERENCE_DOSES_MG.get(clean_key)
            or SEED_CLINICAL_REFERENCE_DOSES_MG.get(name_str)
            or SEED_CLINICAL_REFERENCE_DOSES_MG.get(clean_name)
        )
        if dose_mg is not None:
            basis = "clinical_reference"

    # 5. Dynamic online OpenFDA query
    if dose_mg is None and name_str:
        online_dose = fetch_openfda_dosing(name_str)
        if online_dose is not None:
            dose_mg = online_dose
            basis = "openfda_dynamic_query"

    # 6. Final heuristic fallback
    if dose_mg is None:
        combined_text = f"{key_str} {name_str}"
        if any(w in combined_text for w in ["micro", "mcg", "clenbuterol", "clonidine", "fentanyl", "t3", "triiodothyronine"]):
            dose_mg = 0.05
            basis = "microgram_class_heuristic"
        elif any(w in combined_text for w in ["creatine", "citrulline", "glutamine", "carnitine", "arginine", "protein"]):
            dose_mg = 5000.0
            basis = "amino_acid_bulk_heuristic"
        elif any(w in combined_text for w in ["statin", "sartan", "olol", "pril", "afil", "gliflozin"]):
            dose_mg = 20.0
            basis = "cardiovascular_heuristic"
        else:
            dose_mg = 10.0
            basis = "standard_fallback"

    # Save calculated dose into SQLite cache
    try:
        with _get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cached_reference_doses (compound_key, dose_mg, unit, basis, source, updated_at)
                VALUES (?, ?, 'mg', ?, 'dynamic_calculation', ?)
                """,
                (clean_key or key_str, dose_mg, basis, time.time()),
            )
            conn.commit()
    except Exception:
        pass

    # Determine optimal natural unit and display value dynamically
    if dose_mg < 1.0:
        val = round(dose_mg * 1000.0, 2)
        unit = "μg"
    elif dose_mg >= 1000.0 and (dose_mg % 1000.0 == 0 or dose_mg >= 3000.0):
        val = round(dose_mg / 1000.0, 2)
        unit = "g"
    else:
        val = round(dose_mg, 2)
        unit = "mg"

    val_str = f"{val:g}"
    display = f"{val_str} {unit}"

    return {
        "dose_mg": dose_mg,
        "dose_val": val,
        "dose_unit": unit,
        "unit": unit,
        "dose_display": display,
        "basis": basis,
    }


def parse_dose_string_or_spec(spec_str: str) -> Dict[str, Any]:
    """
    Parse strings like 'clenbuterol:40ug', 'nebivolol:5mg', 'creatine:5g', or 'caffeine'.
    Returns structured { key, dose_mg, dose_val, dose_unit, dose_display }.
    """
    spec = str(spec_str or "").strip()
    if not spec:
        return {"key": "", "dose_mg": 10.0, "dose_val": 10.0, "dose_unit": "mg", "dose_display": "10 mg"}

    parts = spec.split(":", 1)
    key = parts[0].strip()

    if len(parts) == 1:
        default_info = get_default_compound_dose(key)
        return {
            "key": key,
            "dose_mg": default_info["dose_mg"],
            "dose_val": default_info["dose_val"],
            "dose_unit": default_info["dose_unit"],
            "dose_display": default_info["dose_display"],
        }

    dose_part = parts[1].strip()
    match = re.match(r"^([\d.]+)\s*([a-zA-Zμ]+)$", dose_part)
    if match:
        val = float(match.group(1))
        unit = match.group(2).lower()
        if unit in ("ug", "mcg", "μg", "microgram", "micrograms"):
            clean_unit = "μg"
            dose_mg = val / 1000.0
        elif unit in ("g", "gram", "grams"):
            clean_unit = "g"
            dose_mg = val * 1000.0
        elif unit in ("iu", "international_units"):
            clean_unit = "IU"
            dose_mg = val * 0.025
        else:
            clean_unit = "mg"
            dose_mg = val

        return {
            "key": key,
            "dose_mg": dose_mg,
            "dose_val": val,
            "dose_unit": clean_unit,
            "dose_display": f"{val:g} {clean_unit}",
        }

    try:
        val = float(dose_part)
        return {
            "key": key,
            "dose_mg": val,
            "dose_val": val,
            "dose_unit": "mg",
            "dose_display": f"{val:g} mg",
        }
    except ValueError:
        default_info = get_default_compound_dose(key)
        return {
            "key": key,
            "dose_mg": default_info["dose_mg"],
            "dose_val": default_info["dose_val"],
            "dose_unit": default_info["dose_unit"],
            "dose_display": default_info["dose_display"],
        }
