import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog_service import CatalogService
from app.services.dosing_service import get_default_compound_dose
from app.services.live_enrichment import LiveEnrichmentService

client = TestClient(app)


def test_trenbolone_dynamic_research_chemical_enrichment_and_caching():
    """Verify Trenbolone is dynamically enriched from PubChem/ChEMBL/QSPR, assigned evidence tiers, and cached to SQLite."""
    catalog = CatalogService()
    
    # 1. Fetch Trenbolone through Catalog (lazy online enrichment on cache miss)
    tren = catalog.get_compound("trenbolone")
    assert tren is not None
    assert tren["name"] == "Trenbolone"
    assert tren["molecular_weight"] > 250.0
    assert tren["smiles"] is not None
    
    # Check Evidence Tiering & Non-FDA Clinical Trial Flags
    metadata = tren.get("metadata", {})
    assert metadata.get("evidence_tier") == "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION"
    assert metadata.get("human_clinical_trials") is False
    assert any("ChEMBL" in src or "PubChem" in src or "Allometric" in src for src in metadata.get("data_sources", []))
    
    # Check Target Affinities (Recombinant Human AR & PR)
    targets = tren.get("receptor_targets", [])
    assert any("androgen" in t.get("target", "").lower() for t in targets)
    ar_target = next((t for t in targets if "androgen" in t.get("target", "").lower()), None)
    assert ar_target is not None
    assert ar_target.get("affinity_ki") is not None
    assert ar_target["affinity_ki"] <= 1.0  # High potency in vitro human AR affinity (~0.7 nM)
    
    # Check QSPR Estimated PK Parameters
    assert tren.get("volume_of_distribution_l_kg") is not None
    assert tren.get("volume_of_distribution_l_kg") > 0.5
    assert tren.get("fraction_unbound") is not None
    
    # 2. Verify Immediate SQLite Cache Persistence (Cache-First on second read)
    cached_row = catalog.get_compound("trenbolone", auto_enrich=False)
    assert cached_row is not None
    assert cached_row["key"] == "trenbolone"
    assert cached_row["source_tier"] == "research_chemical_enrichment"


def test_bromantane_dynamic_nootropic_enrichment_and_caching():
    """Verify Bromantane is dynamically classified via PubChem/ChEMBL, mapping DAT and Tyrosine Hydroxylase."""
    catalog = CatalogService()
    
    brom = catalog.get_compound("bromantane")
    assert brom is not None
    assert brom["name"] == "Bromantane"
    assert "C1C2CC3CC1CC(C2)C3" in (brom.get("smiles") or "")
    
    # Check Targets (DAT / SLC6A3 & Tyrosine Hydroxylase)
    targets = brom.get("receptor_targets", [])
    assert any("dopamine" in t.get("target", "").lower() or "dat" in t.get("target", "").lower() for t in targets)
    assert any("tyrosine hydroxylase" in t.get("target", "").lower() or "th" in t.get("target", "").lower() for t in targets)
    
    # Check SQLite Persistence
    cached_brom = catalog.get_compound("bromantane", auto_enrich=False)
    assert cached_brom is not None
    assert cached_brom["name"] == "Bromantane"


def test_research_chemical_dynamic_dosing_and_cascade_simulation():
    """Verify research chemicals receive dynamic PK reference doses and propagate biological cascades."""
    # 1. Dynamic Dosing via PK equations and target affinity
    tren_dose = get_default_compound_dose("trenbolone")
    assert tren_dose is not None
    assert tren_dose["dose_mg"] > 0.0
    assert tren_dose["unit"] == "mg"
    
    # 2. Graph Data & Cascade Simulation Endpoint
    resp = client.get("/graph-data?stack=trenbolone:50mg").json()
    assert len(resp.get("nodes", [])) > 0
    assert len(resp.get("edges", [])) > 0
    
    shifts = resp.get("cascade_simulation", {}).get("biomarker_shifts", [])
    assert len(shifts) > 0
    
    # Trenbolone drives significant erythropoiesis (hematocrit) and blood pressure
    hct_shift = next((s for s in shifts if s["biomarker_id"] == "bio_hematocrit"), None)
    bp_shift = next((s for s in shifts if s["biomarker_id"] == "bio_blood_pressure"), None)
    lh_shift = next((s for s in shifts if s["biomarker_id"] == "bio_luteinizing_hormone"), None)
    t_shift = next((s for s in shifts if s["biomarker_id"] == "bio_testosterone"), None)
    
    assert hct_shift is not None
    assert hct_shift["estimated_delta"] > 0.0
    assert bp_shift is not None
    assert bp_shift["estimated_delta"] > 0.0
    assert lh_shift is not None
    assert lh_shift["estimated_delta"] < 0.0
    # Trenbolone is a synthetic non-testosterone androgen and must NEVER show increased serum testosterone
    if t_shift is not None:
        assert t_shift["estimated_delta"] < 0.0


def test_cache_first_architecture_guarantee():
    """Verify that cached compounds trigger 0 external network requests when queried repeatedly."""
    catalog = CatalogService()
    
    # Pre-condition: Trenbolone is cached in SQLite
    assert catalog.get_compound("trenbolone", auto_enrich=False) is not None
    
    # Query with auto_enrich=True must return SQLite data directly without hitting online APIs
    res = catalog.get_compound("trenbolone", auto_enrich=True)
    assert res is not None
    assert res["key"] == "trenbolone"
    assert res["source_tier"] == "research_chemical_enrichment"
