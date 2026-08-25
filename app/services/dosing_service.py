from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, Optional, Union
import httpx

DEFAULT_DB_PATH = os.getenv("HEALTHAI_CATALOG_DB", str(Path(__file__).resolve().parents[2] / "healthai_catalog.db"))

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
    "pitavastatin": 2.0,      # 2 mg/day
    "pitavastatincalcium": 2.0,
    "chembl1200547": 2.0,
    "ezetimibe": 10.0,        # 10 mg/day
    "berberine": 500.0,       # 500 mg/day

    # Androgens, Endocrine & 5-AR
    "testosterone": 20.0,     # 20 mg/day standard daily unesterified dose
    "chembl386630": 20.0,
    "testosterone_cypionate": 175.0,    # 175 mg per injection (350 mg/week split IM/SubQ)
    "testosteronecypionate": 175.0,
    "testc": 175.0,
    "testcyp": 175.0,
    "depotestosterone": 175.0,
    "testosterone_enanthate": 175.0,    # 175 mg per injection (350 mg/week split IM/SubQ)
    "testosteroneenanthate": 175.0,
    "teste": 175.0,
    "delatestryl": 175.0,
    "testosterone_propionate": 50.0,    # 50 mg every other day
    "testosteronepropionate": 50.0,
    "testp": 50.0,
    "testosterone_undecanoate": 250.0,  # 250 mg bi-weekly or 750-1000 mg depot
    "testosteroneundecanoate": 250.0,
    "nebido": 250.0,
    "aveed": 250.0,
    "nandrolone_decanoate": 150.0,      # 150 mg weekly/split
    "nandrolonedecanoate": 150.0,
    "deca": 150.0,
    "deca_durabolin": 150.0,
    "nandrolone_phenylpropionate": 50.0,
    "npp": 50.0,
    "boldenone_undecylenate": 200.0,    # 200 mg weekly/split
    "boldenone": 200.0,
    "equipoise": 200.0,
    "drostanolone_propionate": 50.0,
    "masteron": 50.0,
    "drostanolone_enanthate": 150.0,
    "methenolone_enanthate": 100.0,
    "primobolan": 100.0,
    "oxandrolone": 20.0,                # 20 mg/day oral
    "anavar": 20.0,
    "stanozolol": 25.0,                 # 25 mg/day oral
    "winstrol": 25.0,
    "dianabol": 25.0,                   # 25 mg/day oral
    "methandrostenolone": 25.0,
    "anadrol": 50.0,                    # 50 mg/day oral
    "oxymetholone": 50.0,
    "finasteride": 1.0,       # 1 mg/day (alopecia) or 5 mg (BPH)
    "chembl553": 1.0,
    "dutasteride": 0.5,       # 0.5 mg/day
    "chembl1201083": 0.5,
    "anastrozole": 0.5,       # 0.5 mg oral (e.g. 0.25-0.5 mg twice weekly)
    "arimidex": 0.5,
    "exemestane": 12.5,       # 12.5 mg oral (e.g. 12.5 mg twice weekly with meals)
    "aromasin": 12.5,
    "letrozole": 1.25,        # 1.25 mg oral
    "femara": 1.25,
    "tamoxifen": 20.0,        # 20 mg/day oral
    "nolvadex": 20.0,
    "raloxifene": 60.0,       # 60 mg/day oral
    "evista": 60.0,
    "clomiphene": 25.0,       # 25 mg/day
    "enclomiphene": 12.5,     # 12.5 mg/day
    "hcg": 250.0,             # 250 IU/injection SubQ twice weekly

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

    # Research Chemicals, Nootropics & SARMs (Allometric / Preclinical Scaled)
    "trenbolone": 50.0,       # 50 mg
    "trenbolone_acetate": 50.0,
    "trenbolone_enanthate": 100.0,
    "tak_653": 1.0,           # 1.0 mg (scaled from rat ED50 0.1-0.5 mg/kg)
    "idra_21": 10.0,          # 10.0 mg (scaled from rodent 3 mg/kg)
    "noopept": 10.0,          # 10.0 mg
    "phenylpiracetam": 100.0, # 100.0 mg
    "fasoracetam": 20.0,      # 20.0 mg
    "bromantane": 50.0,       # 50.0 mg
    "nsi_189": 20.0,          # 20.0 mg
    "dihexa": 5.0,            # 5.0 mg (scaled from rat Morris Water Maze 1.44 mg/kg)
    "9_me_bc": 15.0,          # 15.0 mg
    "sunifiram": 5.0,         # 5.0 mg
    "unifiram": 5.0,          # 5.0 mg
    "pramiracetam": 300.0,    # 300.0 mg
    "oxiracetam": 750.0,      # 750.0 mg
    "aniracetam": 750.0,      # 750.0 mg
    "coluracetam": 20.0,      # 20.0 mg
    "rad_140": 10.0,          # 10.0 mg
    "rad140": 10.0,
    "lgd_4033": 5.0,          # 5.0 mg
    "lgd4033": 5.0,
    "mk_2866": 15.0,          # 15.0 mg
    "ostarine": 15.0,
    "mk_677": 15.0,           # 15.0 mg
    "ibutamoren": 15.0,
    "yk_11": 5.0,             # 5.0 mg
    "yk11": 5.0,
    "s_4": 25.0,              # 25.0 mg
    "andarine": 25.0,
    "emoxypine": 125.0,       # 125.0 mg
    "picamilon": 50.0,        # 50.0 mg
    "phenibut": 500.0,        # 500.0 mg
}

# Compatibility reference mapping
CLINICAL_REFERENCE_DOSES_MG: Dict[str, float] = dict(SEED_CLINICAL_REFERENCE_DOSES_MG)


class PreclinicalAllometricEngine:
    """
    Exact Interspecies Allometric Scaling Engine (FDA Reagan-Shaw Body Surface Area Normalization).
    Calculates exact Human Equivalent Dose (HED) and evaluates data limitations without arbitrary safety buffers.
    """
    KM_FACTORS: Dict[str, float] = {
        "mouse": 3.0,
        "rat": 6.0,
        "guinea_pig": 8.0,
        "rabbit": 12.0,
        "dog": 20.0,
        "monkey": 12.0,
        "human": 37.0,
    }

    @classmethod
    def calculate_hed(cls, animal_dose_mg_kg: float, species: str = "rat", human_weight_kg: float = 70.0) -> Dict[str, Any]:
        """
        Calculates exact Human Equivalent Dose (HED) via standard Body Surface Area (BSA) normalization.
        HED (mg/kg) = Animal Dose (mg/kg) * (Km_animal / Km_human)
        Total Human Dose (mg) = HED (mg/kg) * Human Body Weight (kg)
        """
        species_lower = str(species).strip().lower()
        km_animal = cls.KM_FACTORS.get(species_lower, 6.0)
        km_human = cls.KM_FACTORS["human"]

        hed_mg_kg = float(animal_dose_mg_kg) * (km_animal / km_human)
        total_human_dose_mg = hed_mg_kg * float(human_weight_kg)

        return {
            "animal_dose_mg_kg": float(animal_dose_mg_kg),
            "animal_species": species,
            "km_animal": km_animal,
            "km_human": km_human,
            "hed_mg_kg": round(hed_mg_kg, 6),
            "human_weight_kg": float(human_weight_kg),
            "total_human_dose_mg": round(total_human_dose_mg, 4),
            "calculation_method": f"FDA Reagan-Shaw BSA Allometric Normalization (Km {species}={km_animal} -> Human={km_human})",
            "is_human_validated": False,
        }

    @classmethod
    def evaluate_compound_limitations(cls, compound: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audits compound data completeness and produces structured disclosures of data gaps.
        """
        meta = compound.get("metadata") or {}
        evidence_tier = meta.get("evidence_tier") or compound.get("evidence_tier") or (
            "FDA_APPROVED_CLINICAL_DATA" if meta.get("is_fda_approved") else "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION"
        )
        has_human_trials = bool(meta.get("human_clinical_trials") or meta.get("is_fda_approved"))
        has_human_pk = bool(meta.get("has_human_pk") or (has_human_trials and compound.get("t_half_numeric") and compound.get("c_max_ng_ml")))
        has_chronic_tox = bool(meta.get("has_chronic_toxicity_studies") or meta.get("is_fda_approved"))
        has_cyp_mapping = bool(
            (compound.get("cyp_enzymes") or {}).get("substrates")
            or (compound.get("cyp_enzymes") or {}).get("inhibitors")
        )

        limitations: List[str] = []
        if not has_human_trials:
            limitations.append("Zero FDA/EMA randomized human clinical trials exist; parameters are derived from preclinical in vitro assays or animal in vivo models.")
        if not has_human_pk:
            limitations.append("Human pharmacokinetic parameters (clearance, volume of distribution, and bioavailability) have not been established in human subjects.")
        if not has_chronic_tox:
            limitations.append("Long-term chronic toxicity, carcinogenicity, and organ accumulation profiles remain uncharacterized.")
        if not has_cyp_mapping:
            limitations.append("Hepatic CYP450 phase I and phase II metabolic clearance pathways are unmapped.")

        return {
            "has_human_trials": has_human_trials,
            "has_human_pk": has_human_pk,
            "has_chronic_toxicity_studies": has_chronic_tox,
            "has_cyp_metabolite_mapping": has_cyp_mapping,
            "known_limitations": limitations,
            "evidence_tier": evidence_tier,
        }


def _get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or os.environ.get("HEALTHAI_CATALOG_DB") or os.environ.get("COMPOUNDS_DB_PATH") or DEFAULT_DB_PATH
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

    # 1. Authoritative seed reference table lookup
    seed_dose = (
        SEED_CLINICAL_REFERENCE_DOSES_MG.get(key_str)
        or SEED_CLINICAL_REFERENCE_DOSES_MG.get(clean_key)
        or SEED_CLINICAL_REFERENCE_DOSES_MG.get(name_str)
        or SEED_CLINICAL_REFERENCE_DOSES_MG.get(clean_name)
    )
    if seed_dose is not None:
        dose_mg = float(seed_dose)
        basis = "clinical_reference"

    # 2. Check SQLite Persistent Cache
    if dose_mg is None:
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


DOSING_FREQUENCY_METADATA: Dict[str, Dict[str, Any]] = {
    "daily": {
        "key": "daily",
        "label": "Once Daily (QD)",
        "multiplier": 1.0,
        "interval_hours": 24.0,
        "daily_doses": 1.0,
        "description": "Standard once-daily administration (every 24 hours)",
    },
    "once_daily": {
        "key": "daily",
        "label": "Once Daily (QD)",
        "multiplier": 1.0,
        "interval_hours": 24.0,
        "daily_doses": 1.0,
        "description": "Standard once-daily administration (every 24 hours)",
    },
    "qd": {
        "key": "daily",
        "label": "Once Daily (QD)",
        "multiplier": 1.0,
        "interval_hours": 24.0,
        "daily_doses": 1.0,
        "description": "Standard once-daily administration (every 24 hours)",
    },
    "twice_daily": {
        "key": "twice_daily",
        "label": "Twice Daily (BID)",
        "multiplier": 2.0,
        "interval_hours": 12.0,
        "daily_doses": 2.0,
        "description": "Twice-daily administration (every 12 hours)",
    },
    "bid": {
        "key": "twice_daily",
        "label": "Twice Daily (BID)",
        "multiplier": 2.0,
        "interval_hours": 12.0,
        "daily_doses": 2.0,
        "description": "Twice-daily administration (every 12 hours)",
    },
    "three_times_daily": {
        "key": "three_times_daily",
        "label": "Three Times Daily (TID)",
        "multiplier": 3.0,
        "interval_hours": 8.0,
        "daily_doses": 3.0,
        "description": "Three-times-daily administration (every 8 hours)",
    },
    "tid": {
        "key": "three_times_daily",
        "label": "Three Times Daily (TID)",
        "multiplier": 3.0,
        "interval_hours": 8.0,
        "daily_doses": 3.0,
        "description": "Three-times-daily administration (every 8 hours)",
    },
    "four_times_daily": {
        "key": "four_times_daily",
        "label": "Four Times Daily (QID)",
        "multiplier": 4.0,
        "interval_hours": 6.0,
        "daily_doses": 4.0,
        "description": "Four-times-daily administration (every 6 hours)",
    },
    "qid": {
        "key": "four_times_daily",
        "label": "Four Times Daily (QID)",
        "multiplier": 4.0,
        "interval_hours": 6.0,
        "daily_doses": 4.0,
        "description": "Four-times-daily administration (every 6 hours)",
    },
    "every_other_day": {
        "key": "every_other_day",
        "label": "Every Other Day (QOD)",
        "multiplier": 0.5,
        "interval_hours": 48.0,
        "daily_doses": 0.5,
        "description": "Every-other-day administration (every 48 hours)",
    },
    "qod": {
        "key": "every_other_day",
        "label": "Every Other Day (QOD)",
        "multiplier": 0.5,
        "interval_hours": 48.0,
        "daily_doses": 0.5,
        "description": "Every-other-day administration (every 48 hours)",
    },
    "twice_weekly": {
        "key": "twice_weekly",
        "label": "Twice Weekly (2x/wk)",
        "multiplier": 2.0 / 7.0,
        "interval_hours": 84.0,
        "daily_doses": 2.0 / 7.0,
        "description": "Administered twice weekly (e.g. Mon / Thu, ~every 3.5 days)",
    },
    "biw": {
        "key": "twice_weekly",
        "label": "Twice Weekly (2x/wk)",
        "multiplier": 2.0 / 7.0,
        "interval_hours": 84.0,
        "daily_doses": 2.0 / 7.0,
        "description": "Administered twice weekly (e.g. Mon / Thu, ~every 3.5 days)",
    },
    "weekly": {
        "key": "weekly",
        "label": "Once Weekly (QW)",
        "multiplier": 1.0 / 7.0,
        "interval_hours": 168.0,
        "daily_doses": 1.0 / 7.0,
        "description": "Administered once weekly (every 7 days)",
    },
    "once_weekly": {
        "key": "weekly",
        "label": "Once Weekly (QW)",
        "multiplier": 1.0 / 7.0,
        "interval_hours": 168.0,
        "daily_doses": 1.0 / 7.0,
        "description": "Administered once weekly (every 7 days)",
    },
    "qw": {
        "key": "weekly",
        "label": "Once Weekly (QW)",
        "multiplier": 1.0 / 7.0,
        "interval_hours": 168.0,
        "daily_doses": 1.0 / 7.0,
        "description": "Administered once weekly (every 7 days)",
    },
    "biweekly": {
        "key": "biweekly",
        "label": "Every 2 Weeks (Q2W)",
        "multiplier": 1.0 / 14.0,
        "interval_hours": 336.0,
        "daily_doses": 1.0 / 14.0,
        "description": "Administered every 2 weeks (every 14 days)",
    },
    "q2w": {
        "key": "biweekly",
        "label": "Every 2 Weeks (Q2W)",
        "multiplier": 1.0 / 14.0,
        "interval_hours": 336.0,
        "daily_doses": 1.0 / 14.0,
        "description": "Administered every 2 weeks (every 14 days)",
    },
    "monthly": {
        "key": "monthly",
        "label": "Monthly (QM)",
        "multiplier": 1.0 / 30.0,
        "interval_hours": 720.0,
        "daily_doses": 1.0 / 30.0,
        "description": "Administered once monthly (~every 30 days)",
    },
    "qm": {
        "key": "monthly",
        "label": "Monthly (QM)",
        "multiplier": 1.0 / 30.0,
        "interval_hours": 720.0,
        "daily_doses": 1.0 / 30.0,
        "description": "Administered once monthly (~every 30 days)",
    },
    "as_needed": {
        "key": "as_needed",
        "label": "As Needed (PRN)",
        "multiplier": 0.5,
        "interval_hours": 48.0,
        "daily_doses": 0.5,
        "description": "Administered occasionally on an as-needed basis",
    },
    "prn": {
        "key": "as_needed",
        "label": "As Needed (PRN)",
        "multiplier": 0.5,
        "interval_hours": 48.0,
        "daily_doses": 0.5,
        "description": "Administered occasionally on an as-needed basis",
    },
}


def normalize_dosing_frequency(freq: Any) -> str:
    """Normalize dosing frequency token to standard key (e.g. 'weekly', 'twice_daily', 'daily')."""
    raw = str(freq or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return "daily"
    meta = DOSING_FREQUENCY_METADATA.get(raw)
    if meta:
        return meta["key"]
    if "bid" in raw or "twice" in raw and "week" not in raw:
        return "twice_daily"
    if "tid" in raw or "three" in raw:
        return "three_times_daily"
    if "qid" in raw or "four" in raw:
        return "four_times_daily"
    if "qod" in raw or "other" in raw:
        return "every_other_day"
    if "biw" in raw or "twice" in raw and "week" in raw:
        return "twice_weekly"
    if "qw" in raw or "week" in raw and "2" not in raw and "bi" not in raw:
        return "weekly"
    if "q2w" in raw or "2_week" in raw or "biweek" in raw or "every_2_weeks" in raw:
        return "biweekly"
    if "qm" in raw or "month" in raw:
        return "monthly"
    if "prn" in raw or "needed" in raw:
        return "as_needed"
    return "daily"


def get_frequency_multiplier(frequency: Any) -> float:
    """Return effective daily dosing multiplier for a given frequency."""
    norm = normalize_dosing_frequency(frequency)
    meta = DOSING_FREQUENCY_METADATA.get(norm)
    return float(meta["multiplier"]) if meta else 1.0


def get_frequency_interval_hours(frequency: Any) -> float:
    """Return dosing interval tau in hours for a given frequency."""
    norm = normalize_dosing_frequency(frequency)
    meta = DOSING_FREQUENCY_METADATA.get(norm)
    return float(meta["interval_hours"]) if meta else 24.0


def infer_compound_route_and_frequency(key_or_name: str) -> Tuple[str, str]:
    """Infers standard clinical route and frequency based on compound pharmacokinetics and formulation."""
    blob = str(key_or_name or "").lower()
    
    # Depot androgens and esters
    if any(e in blob for e in [
        "cypionate", "enanthate", "decanoate", "undecanoate", "isocaproate", "depot",
        "testc", "testcyp", "teste", "testenan", "delatestryl", "deca", "durabolin",
        "equipoise", "primobolan", "masteron"
    ]):
        if "undecanoate" in blob or "nebido" in blob:
            return "intramuscular", "biweekly"
        elif "propionate" in blob:
            return "intramuscular", "every_other_day"
        return "intramuscular", "twice_weekly"
    
    # Peptides & Incretins (typically SubQ weekly or daily)
    if any(p in blob for p in ["semaglutide", "tirzepatide", "retatrutide", "cagrilintide"]):
        return "subcutaneous", "weekly"
    if any(p in blob for p in ["bpc_157", "bpc157", "tb_500", "tb500", "ghk_cu", "kpv", "ipamorelin", "cjc_1295", "sermorelin", "tesamorelin", "epitalon", "epithalon", "mots_c", "elamipretide", "ss31", "thymosin", "hcg"]):
        return "subcutaneous", "daily" if ("bpc" in blob or "ipam" in blob) else "twice_weekly"
    
    # Aromatase Inhibitors (typically oral twice-weekly or as needed)
    if any(a in blob for a in ["anastrozole", "arimidex", "exemestane", "aromasin", "letrozole", "femara"]):
        return "oral", "twice_weekly"
    
    return "oral", "daily"


def parse_dose_string_or_spec(spec_input: Any) -> Dict[str, Any]:
    """
    Parse strings like 'clenbuterol:40ug', 'nebivolol:5mg:daily', 'testosterone:200mg:weekly',
    'testosterone_cypionate:350mg:weekly', or 'creatine:5g', or dict specs.
    Returns structured { key, dose_mg, dose_val, dose_unit, dose_display, frequency, frequency_multiplier, effective_daily_dose_mg, effective_daily_display, route }.
    """
    if isinstance(spec_input, dict):
        key = str(spec_input.get("key") or spec_input.get("name") or "").strip()
        inferred_route, inferred_freq = infer_compound_route_and_frequency(key)
        dose_val = spec_input.get("dose_val") if spec_input.get("dose_val") is not None else spec_input.get("dose")
        if dose_val is None:
            dose_val = spec_input.get("dose_mg")
        dose_unit = str(spec_input.get("dose_unit") or spec_input.get("unit") or "mg").strip()
        raw_freq = spec_input.get("frequency") or spec_input.get("dosing_frequency")
        freq = str(raw_freq).strip() if raw_freq is not None else inferred_freq
        route = str(spec_input.get("route") or inferred_route).strip().lower()
        frequency = normalize_dosing_frequency(freq)
        freq_mult = get_frequency_multiplier(frequency)

        if dose_val is not None:
            val = float(dose_val)
            unit = dose_unit.lower()
            if unit in ["ug", "mcg"]:
                dose_mg = val / 1000.0
                unit = "μg"
            elif unit == "g":
                dose_mg = val * 1000.0
            else:
                dose_mg = val
                unit = "mg" if unit not in ["iu", "u"] else unit
            
            eff_daily = dose_mg * freq_mult
            eff_display = f"{eff_daily:g} mg/day" if eff_daily >= 1.0 else f"{eff_daily * 1000.0:g} μg/day"
            return {
                "key": key,
                "dose_mg": dose_mg,
                "dose_val": val,
                "dose_unit": unit,
                "dose_display": f"{val:g} {unit}",
                "frequency": frequency,
                "frequency_multiplier": freq_mult,
                "effective_daily_dose_mg": round(eff_daily, 4),
                "effective_daily_display": eff_display,
                "route": route,
            }
        else:
            default_info = get_default_compound_dose(key)
            dose_mg = float(default_info["dose_mg"])
            eff_daily = dose_mg * freq_mult
            eff_display = f"{eff_daily:g} mg/day" if eff_daily >= 1.0 else f"{eff_daily * 1000.0:g} μg/day"
            return {
                "key": key,
                "dose_mg": dose_mg,
                "dose_val": default_info["dose_val"],
                "dose_unit": default_info["dose_unit"],
                "dose_display": default_info["dose_display"],
                "frequency": frequency,
                "frequency_multiplier": freq_mult,
                "effective_daily_dose_mg": round(eff_daily, 4),
                "effective_daily_display": eff_display,
                "route": route,
            }

    spec = str(spec_input or "").strip()
    if not spec:
        return {
            "key": "",
            "dose_mg": 10.0,
            "dose_val": 10.0,
            "dose_unit": "mg",
            "dose_display": "10 mg",
            "frequency": "daily",
            "frequency_multiplier": 1.0,
            "effective_daily_dose_mg": 10.0,
            "effective_daily_display": "10 mg/day",
            "route": "oral",
        }

    parts = spec.split(":")
    key = parts[0].strip()
    inferred_route, inferred_freq = infer_compound_route_and_frequency(key)
    freq_candidate = inferred_freq
    route_candidate = inferred_route

    # Check if frequency or route tokens are included in parts
    if len(parts) >= 4:
        freq_candidate = parts[2].strip()
        route_candidate = parts[3].strip().lower()
    elif len(parts) >= 3:
        freq_candidate = parts[2].strip()
    elif len(parts) == 2 and any(k in parts[1].lower() for k in ["daily", "weekly", "bid", "tid", "qid", "qod", "biw", "qw", "prn", "month"]):
        if not re.search(r"\d", parts[1]):
            freq_candidate = parts[1].strip()
            parts = [key]

    frequency = normalize_dosing_frequency(freq_candidate)
    freq_mult = get_frequency_multiplier(frequency)

    if len(parts) == 1:
        default_info = get_default_compound_dose(key)
        dose_mg = float(default_info["dose_mg"])
        eff_daily = dose_mg * freq_mult
        eff_display = f"{eff_daily:g} mg/day" if eff_daily >= 1.0 else f"{eff_daily * 1000.0:g} μg/day"
        return {
            "key": key,
            "dose_mg": dose_mg,
            "dose_val": default_info["dose_val"],
            "dose_unit": default_info["dose_unit"],
            "dose_display": default_info["dose_display"],
            "frequency": frequency,
            "frequency_multiplier": freq_mult,
            "effective_daily_dose_mg": round(eff_daily, 4),
            "effective_daily_display": eff_display,
            "route": route_candidate,
        }

    dose_part = parts[1].strip()
    match = re.match(r"^([\d.]+)\s*([a-zA-Zμ]+)(?:_([a-zA-Z0-9_]+))?$", dose_part)
    if match:
        val = float(match.group(1))
        unit = match.group(2).lower()
        if match.group(3):
            frequency = normalize_dosing_frequency(match.group(3))
            freq_mult = get_frequency_multiplier(frequency)

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

        eff_daily = dose_mg * freq_mult
        eff_display = f"{eff_daily:g} mg/day" if eff_daily >= 1.0 else f"{eff_daily * 1000.0:g} μg/day"

        return {
            "key": key,
            "dose_mg": dose_mg,
            "dose_val": val,
            "dose_unit": clean_unit,
            "dose_display": f"{val:g} {clean_unit}",
            "frequency": frequency,
            "frequency_multiplier": freq_mult,
            "effective_daily_dose_mg": round(eff_daily, 4),
            "effective_daily_display": eff_display,
            "route": route_candidate,
        }

    try:
        val = float(dose_part)
        dose_mg = val
        eff_daily = dose_mg * freq_mult
        eff_display = f"{eff_daily:g} mg/day" if eff_daily >= 1.0 else f"{eff_daily * 1000.0:g} μg/day"
        return {
            "key": key,
            "dose_mg": val,
            "dose_val": val,
            "dose_unit": "mg",
            "dose_display": f"{val:g} mg",
            "frequency": frequency,
            "frequency_multiplier": freq_mult,
            "effective_daily_dose_mg": round(eff_daily, 4),
            "effective_daily_display": eff_display,
            "route": route_candidate,
        }
    except ValueError:
        default_info = get_default_compound_dose(key)
        dose_mg = float(default_info["dose_mg"])
        eff_daily = dose_mg * freq_mult
        eff_display = f"{eff_daily:g} mg/day" if eff_daily >= 1.0 else f"{eff_daily * 1000.0:g} μg/day"
        return {
            "key": key,
            "dose_mg": dose_mg,
            "dose_val": default_info["dose_val"],
            "dose_unit": default_info["dose_unit"],
            "dose_display": default_info["dose_display"],
            "frequency": frequency,
            "frequency_multiplier": freq_mult,
            "effective_daily_dose_mg": round(eff_daily, 4),
            "effective_daily_display": eff_display,
            "route": route_candidate,
        }
