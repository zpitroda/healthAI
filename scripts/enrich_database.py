#!/usr/bin/env python3
"""
Batch Database Enrichment Tool
------------------------------
Iterates over all compounds in healthai_catalog.db and applies
PharmacologyEnricher to populate ADMET, CYP450 enzymes, Transporters,
Phase II enzymes, organ burdens, dosing guidelines, and receptor targets.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.catalog_service import CatalogService
from app.services.pharmacology_enricher import PharmacologyEnricher


def run_enrichment(db_path: str, dry_run: bool = False) -> None:
    service = CatalogService(database_path=db_path)
    compounds = service.list_compounds()
    total = len(compounds)
    print(f"[Enrichment] Loaded {total} compounds from {db_path}")

    cyp_before = sum(1 for c in compounds if any(c.get("cyp_enzymes", {}).values()))
    organ_before = sum(1 for c in compounds if any(v != "none" for v in c.get("organ_burdens", {}).values()))
    dosing_before = sum(1 for c in compounds if c.get("dosing"))

    print(f"  * CYP data before: {cyp_before}/{total}")
    print(f"  * Organ burdens before: {organ_before}/{total}")
    print(f"  * Dosing before: {dosing_before}/{total}")

    enriched_count = 0
    with sqlite3.connect(db_path) as conn:
        for c in compounds:
            enriched = PharmacologyEnricher.enrich_compound(c)
            if not dry_run:
                conn.execute(
                    """
                    UPDATE compounds SET
                        cyp_enzymes = ?,
                        transporters = ?,
                        phase2_enzymes = ?,
                        organ_burdens = ?,
                        dosing = ?,
                        half_life = ?,
                        oral_bioavailability = ?,
                        volume_of_distribution = ?,
                        protein_binding = ?,
                        clearance_routes = ?,
                        route_of_administration = ?,
                        logp = ?,
                        tpsa = ?,
                        is_narrow_therapeutic_index = ?,
                        receptor_targets = ?,
                        t_half_numeric = ?,
                        bioavailability_f = ?,
                        volume_of_distribution_l_kg = ?,
                        clearance_l_h_kg = ?,
                        t_max_h = ?,
                        c_max_ng_ml = ?,
                        fraction_unbound = ?,
                        protein_binding_pct = ?,
                        absorption_rate_ka = ?,
                        renal_clearance_fraction = ?,
                        bcs_class = ?,
                        mec_ng_ml = ?,
                        mtc_ng_ml = ?,
                        therapeutic_index = ?,
                        e_max = ?,
                        ec50_nm = ?,
                        ic50_nm = ?,
                        hill_coefficient = ?,
                        pathway_details = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE key = ?
                    """,
                    (
                        json.dumps(enriched.get("cyp_enzymes", {})),
                        json.dumps(enriched.get("transporters", {})),
                        json.dumps(enriched.get("phase2_enzymes", {})),
                        json.dumps(enriched.get("organ_burdens", {})),
                        json.dumps(enriched.get("dosing", {})),
                        enriched.get("half_life"),
                        enriched.get("oral_bioavailability"),
                        enriched.get("volume_of_distribution"),
                        enriched.get("protein_binding"),
                        enriched.get("clearance_routes"),
                        enriched.get("route_of_administration"),
                        enriched.get("logp"),
                        enriched.get("tpsa"),
                        1 if enriched.get("is_narrow_therapeutic_index") else 0,
                        json.dumps(enriched.get("receptor_targets", [])),
                        enriched.get("t_half_numeric"),
                        enriched.get("bioavailability_f"),
                        enriched.get("volume_of_distribution_l_kg"),
                        enriched.get("clearance_l_h_kg"),
                        enriched.get("t_max_h"),
                        enriched.get("c_max_ng_ml"),
                        enriched.get("fraction_unbound"),
                        enriched.get("protein_binding_pct"),
                        enriched.get("absorption_rate_ka"),
                        enriched.get("renal_clearance_fraction"),
                        enriched.get("bcs_class"),
                        enriched.get("mec_ng_ml"),
                        enriched.get("mtc_ng_ml"),
                        enriched.get("therapeutic_index"),
                        enriched.get("e_max"),
                        enriched.get("ec50_nm"),
                        enriched.get("ic50_nm"),
                        enriched.get("hill_coefficient"),
                        json.dumps(enriched.get("pathway_details", [])),
                        enriched["key"],
                    ),
                )
            enriched_count += 1

        if not dry_run:
            conn.commit()

    reloaded = service.list_compounds()
    cyp_after = sum(1 for c in reloaded if any(c.get("cyp_enzymes", {}).values()))
    organ_after = sum(1 for c in reloaded if any(v != "none" for v in c.get("organ_burdens", {}).values()))
    dosing_after = sum(1 for c in reloaded if c.get("dosing"))
    trans_after = sum(1 for c in reloaded if any(c.get("transporters", {}).values()))

    print(f"[Enrichment Complete] Enriched {enriched_count} records")
    print(f"  * CYP active data after:         {cyp_after}/{total} ({(cyp_after/max(total,1))*100:.1f}%)")
    print(f"  * Transporters active after:     {trans_after}/{total} ({(trans_after/max(total,1))*100:.1f}%)")
    print(f"  * Organ burdens after:           {organ_after}/{total} ({(organ_after/max(total,1))*100:.1f}%)")
    print(f"  * Dosing populated after:        {dosing_after}/{total} ({(dosing_after/max(total,1))*100:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich compound catalog database.")
    parser.add_argument("--db", default=os.getenv("HEALTHAI_CATALOG_DB", "./healthai_catalog.db"), help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Preview enrichment without writing to DB")
    args = parser.parse_args()
    run_enrichment(args.db, dry_run=args.dry_run)
