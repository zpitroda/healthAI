#!/usr/bin/env python3
"""
High-Speed Concurrent Catalog Backfill Script
--------------------------------------------
Performs concurrent structured enrichment of healthai_catalog.db:
1. Queries RxNorm, OpenFDA, and ChEMBL APIs to populate exact ATC codes.
2. Standardizes receptor targets with exact HGNC gene symbols and UniProt IDs.
3. Applies PharmacologyEnricher and PKPDEnricher for quantitative parameters.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill")

from app.services.catalog_service import CatalogService, DEFAULT_CATALOG_DB_PATH
from app.services.live_enrichment import LiveEnrichmentService
from app.services.pharmacology_enricher import PharmacologyEnricher
from app.services.pkpd_enricher import PKPDEnricher

_DB_LOCK = threading.Lock()


def enrich_single_compound(comp: Dict[str, Any], enricher: LiveEnrichmentService, pkpd_enricher: PKPDEnricher) -> Dict[str, Any]:
    key = comp.get("key")
    name = comp.get("name") or key

    try:
        # 1. Fetch live biomedical metadata
        live_profile = enricher.fetch_compound_profile(name) or {}

        # 2. Merge ATC codes
        ext_ids = dict(comp.get("external_ids") or {})
        atc_codes_set: Set[str] = set(ext_ids.get("atc_codes") or [])

        # From OpenFDA & Live
        fda_atcs = live_profile.get("metadata", {}).get("online_enrichment", {}).get("atc_classes") or []
        for a in fda_atcs:
            clean_a = re.sub(r"[^A-Z0-9]", "", str(a).upper())
            if clean_a:
                atc_codes_set.add(clean_a)

        # From categories
        categories = list(comp.get("categories") or [])
        for cat in categories:
            match = re.match(r"^([A-Z][0-9]{2}[A-Z]?[A-Z]?[0-9]*)", str(cat).strip(), re.IGNORECASE)
            if match:
                atc_codes_set.add(match.group(1).upper())

        ext_ids["atc_codes"] = sorted(list(atc_codes_set))
        comp["external_ids"] = ext_ids

        # 3. Standardize and merge receptor targets
        targets: List[Dict[str, Any]] = list(comp.get("receptor_targets") or [])
        live_targets = live_profile.get("receptor_targets") or []

        target_keys = {t.get("target") for t in targets if isinstance(t, dict) and t.get("target")}
        for lt in live_targets:
            if isinstance(lt, dict) and lt.get("target") and lt.get("target") not in target_keys:
                targets.append(lt)
                target_keys.add(lt.get("target"))

        comp["receptor_targets"] = targets

        # 4. Apply Pharmacology and PK/PD enrichers
        comp = PharmacologyEnricher.enrich_compound(comp)
        comp = pkpd_enricher.enrich_compound_pkpd(comp)
        return comp
    except Exception as e:
        logger.error(f"Error enriching {key}: {e}")
        return comp


def run_catalog_backfill(db_path: str = DEFAULT_CATALOG_DB_PATH, max_workers: int = 8) -> None:
    service = CatalogService(database_path=db_path)
    compounds = service.list_compounds()
    total = len(compounds)
    logger.info(f"Starting concurrent backfill for {total} compounds with {max_workers} workers...")

    enricher = LiveEnrichmentService(timeout_seconds=5.0)
    pkpd_enricher = PKPDEnricher(timeout_seconds=5.0)

    results: List[Dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_comp = {executor.submit(enrich_single_compound, c, enricher, pkpd_enricher): c for c in compounds}
        done_count = 0
        for future in concurrent.futures.as_completed(future_to_comp):
            done_count += 1
            enriched_comp = future.result()
            results.append(enriched_comp)
            if done_count % 10 == 0 or done_count == total:
                logger.info(f"Progress: {done_count}/{total} ({(done_count/total)*100:.1f}%)")

    logger.info("Writing all enriched records to database in a single transaction...")
    with sqlite3.connect(db_path) as conn:
        for comp in results:
            key = comp.get("key")
            conn.execute(
                """
                UPDATE compounds SET
                    external_ids = ?,
                    categories = ?,
                    receptor_targets = ?,
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
                    metadata = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE key = ?
                """,
                (
                    json.dumps(comp.get("external_ids", {})),
                    json.dumps(comp.get("categories", [])),
                    json.dumps(comp.get("receptor_targets", [])),
                    json.dumps(comp.get("cyp_enzymes", {})),
                    json.dumps(comp.get("transporters", {})),
                    json.dumps(comp.get("phase2_enzymes", {})),
                    json.dumps(comp.get("organ_burdens", {})),
                    json.dumps(comp.get("dosing", {})),
                    comp.get("half_life"),
                    comp.get("oral_bioavailability"),
                    comp.get("volume_of_distribution"),
                    comp.get("protein_binding"),
                    comp.get("clearance_routes"),
                    comp.get("route_of_administration"),
                    comp.get("logp"),
                    comp.get("tpsa"),
                    1 if comp.get("is_narrow_therapeutic_index") else 0,
                    comp.get("t_half_numeric"),
                    comp.get("bioavailability_f"),
                    comp.get("volume_of_distribution_l_kg"),
                    comp.get("clearance_l_h_kg"),
                    comp.get("t_max_h"),
                    comp.get("c_max_ng_ml"),
                    comp.get("fraction_unbound"),
                    comp.get("protein_binding_pct"),
                    comp.get("absorption_rate_ka"),
                    comp.get("renal_clearance_fraction"),
                    comp.get("bcs_class"),
                    comp.get("mec_ng_ml"),
                    comp.get("mtc_ng_ml"),
                    comp.get("therapeutic_index"),
                    comp.get("e_max"),
                    comp.get("ec50_nm"),
                    comp.get("ic50_nm"),
                    comp.get("hill_coefficient"),
                    json.dumps(comp.get("pathway_details", [])),
                    json.dumps(comp.get("metadata", {})),
                    key,
                ),
            )
        conn.commit()

    logger.info(f"Backfill complete! Updated {len(results)}/{total} compound records.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill structured ontologies across catalog.")
    parser.add_argument("--db", default=DEFAULT_CATALOG_DB_PATH, help="Database path")
    parser.add_argument("--workers", type=int, default=8, help="Number of concurrent worker threads")
    args = parser.parse_args()

    run_catalog_backfill(db_path=args.db, max_workers=args.workers)
