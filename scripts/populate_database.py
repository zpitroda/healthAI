"""
Database Population & Online Biomedical Sourcing Script
-------------------------------------------------------
Batch-enriches 50+ clinical, hormonal, metabolic, cardiovascular, ergogenic,
and nootropic compounds from public APIs (ChEMBL, OpenFDA, PubChem, RxNorm)
and writes them through into the local HealthAI SQLite catalog.
"""
from __future__ import annotations

import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.catalog_service import CatalogService
from app.services.live_enrichment import LiveEnrichmentService

POPULATION_COMPOUND_LIST = [
    # Androgens & Endocrine
    "testosterone",
    "dihydrotestosterone",
    "nandrolone",
    "oxandrolone",
    "dhea",
    "pregnenolone",
    # Estrogens & SERMs
    "estradiol",
    "tamoxifen",
    "raloxifene",
    "clomiphene",
    "enclomiphene",
    # Aromatase & 5AR Inhibitors
    "anastrozole",
    "letrozole",
    "exemestane",
    "finasteride",
    "dutasteride",
    # Antidiabetic & Metabolic
    "metformin",
    "berberine",
    "dapagliflozin",
    "empagliflozin",
    "semaglutide",
    "tirzepatide",
    # Cardiovascular, Beta Blockers & RAAS
    "telmisartan",
    "losartan",
    "lisinopril",
    "nebivolol",
    "propranolol",
    "metoprolol",
    "atenolol",
    "amlodipine",
    "eplerenone",
    "spironolactone",
    # Ergogenic, Sympathomimetic & Respiratory
    "clenbuterol",
    "albuterol",
    "yohimbine",
    "creatine",
    "beta-alanine",
    "l-carnitine",
    # Nootropic & Cognitive
    "caffeine",
    "theanine",
    "alpha-gpc",
    "ashwagandha",
    "modafinil",
    "armodafinil",
    # Vasodilatory & PDE5
    "tadalafil",
    "sildenafil",
    # Hepatoprotective & Recovery
    "nac",
    "tudca",
    # Glucocorticoids
    "dexamethasone",
    "prednisone",
]


def populate_catalog():
    print(f"Starting online biomedical database population for {len(POPULATION_COMPOUND_LIST)} compounds...")
    catalog = CatalogService()
    enricher = LiveEnrichmentService(timeout_seconds=8.0)

    success_count = 0
    for name in POPULATION_COMPOUND_LIST:
        print(f"-> Enriching '{name}'...", end=" ", flush=True)
        try:
            compound = enricher.enrich_and_cache(name, catalog_service=catalog)
            if compound:
                targets_count = len(compound.get("receptor_targets") or [])
                cyp_count = len((compound.get("cyp_enzymes") or {}).get("substrates") or [])
                print(f"OK (Targets: {targets_count}, CYPs: {cyp_count}, Class: {compound.get('drug_class')})")
                success_count += 1
            else:
                # Fallback to catalog seed
                existing = catalog.get_compound(name, auto_enrich=False)
                if existing:
                    print(f"OK (Catalog Seed: {existing.get('drug_class')})")
                    success_count += 1
                else:
                    print("SKIPPED (No online hit)")
        except Exception as e:
            print(f"ERR ({e})")

    # Run deduplication
    deduped = catalog.deduplicate_database()
    total_compounds = len(catalog.list_compounds())
    print(f"\nPopulation complete! Total compounds in catalog: {total_compounds} (Merged duplicates: {deduped})")


if __name__ == "__main__":
    populate_catalog()
