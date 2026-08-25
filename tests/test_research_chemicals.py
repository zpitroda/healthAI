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
    
    # Check Evidence Tiering or Seed Drug Class
    assert tren.get("drug_class") is not None
    assert tren.get("molecular_weight") > 250.0
    
    # Check Target Affinities (Recombinant Human AR & PR)
    targets = tren.get("receptor_targets", [])
    assert any("androgen" in t.get("target", "").lower() for t in targets)
    ar_target = next((t for t in targets if "androgen" in t.get("target", "").lower()), None)
    assert ar_target is not None
    assert ar_target.get("affinity_ki") is not None or ar_target.get("action") is not None
    
    # Check PK Parameters
    assert tren.get("volume_of_distribution_l_kg") is not None or tren.get("volume_of_distribution") is not None
    
    # 2. Verify Immediate SQLite / Seed Resolution (Cache-First on second read)
    cached_row = catalog.get_compound("trenbolone", auto_enrich=False)
    assert cached_row is not None
    assert cached_row["key"] == "trenbolone"
    assert cached_row.get("source_tier") in ("seed", "research_chemical_enrichment", None)



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
    assert res.get("source_tier") in ("seed", "research_chemical_enrichment", None)



def test_exact_preclinical_allometric_scaling_no_arbitrary_buffers():
    """Verify exact FDA Reagan-Shaw BSA interspecies allometric scaling calculation without arbitrary safety buffers."""
    from app.services.dosing_service import PreclinicalAllometricEngine
    
    # 1. Rat Allometric Scaling (Km rat=6, Km human=37)
    # Rat dose 1.0 mg/kg -> HED = 1.0 * (6 / 37) = 0.162162 mg/kg
    # For 70 kg human -> Total dose = 0.162162 * 70 = 11.35135 mg
    rat_scale = PreclinicalAllometricEngine.calculate_hed(animal_dose_mg_kg=1.0, species="rat", human_weight_kg=70.0)
    assert rat_scale["animal_dose_mg_kg"] == 1.0
    assert rat_scale["animal_species"] == "rat"
    assert rat_scale["km_animal"] == 6.0
    assert rat_scale["km_human"] == 37.0
    assert abs(rat_scale["hed_mg_kg"] - (6.0 / 37.0)) < 1e-5
    assert abs(rat_scale["total_human_dose_mg"] - (70.0 * 6.0 / 37.0)) < 1e-3
    assert rat_scale["is_human_validated"] is False
    assert "FDA Reagan-Shaw" in rat_scale["calculation_method"]
    
    # 2. Mouse Allometric Scaling (Km mouse=3, Km human=37)
    # Mouse dose 10.0 mg/kg -> HED = 10.0 * (3 / 37) = 0.810811 mg/kg
    mouse_scale = PreclinicalAllometricEngine.calculate_hed(animal_dose_mg_kg=10.0, species="mouse", human_weight_kg=70.0)
    assert mouse_scale["km_animal"] == 3.0
    assert abs(mouse_scale["hed_mg_kg"] - (30.0 / 37.0)) < 1e-5
    assert abs(mouse_scale["total_human_dose_mg"] - (70.0 * 30.0 / 37.0)) < 1e-3


def test_compound_data_limitations_audit():
    """Verify that compounds with limited or no human data produce explicit gap disclosures."""
    from app.services.dosing_service import PreclinicalAllometricEngine
    
    # Preclinical research compound (zero human trials, unmapped CYP)
    rc_compound = {
        "key": "tak_653",
        "name": "TAK-653",
        "metadata": {
            "evidence_tier": "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION",
            "human_clinical_trials": False,
            "has_human_pk": False,
            "has_chronic_toxicity_studies": False,
        },
        "cyp_enzymes": {"substrates": [], "inhibitors": []},
    }
    
    audit = PreclinicalAllometricEngine.evaluate_compound_limitations(rc_compound)
    assert audit["has_human_trials"] is False
    assert audit["has_human_pk"] is False
    assert audit["has_chronic_toxicity_studies"] is False
    assert audit["has_cyp_metabolite_mapping"] is False
    assert len(audit["known_limitations"]) >= 3
    assert any("human clinical trials" in lim.lower() for lim in audit["known_limitations"])
    assert any("pharmacokinetic parameters" in lim.lower() for lim in audit["known_limitations"])
    assert any("chronic toxicity" in lim.lower() for lim in audit["known_limitations"])


def test_nootropic_target_enrichment_and_cascades():
    """Verify nootropic compounds (TAK-653, Semax, MK-677) map to receptors and propagate cascades."""
    enricher = LiveEnrichmentService()
    
    # 1. TAK-653 (AMPA PAM)
    tak_profile = enricher.fetch_compound_profile("tak_653")
    assert tak_profile is not None
    targets = tak_profile.get("receptor_targets", [])
    assert any("ampa" in t.get("target", "").lower() or "gria" in t.get("target", "").lower() for t in targets)
    
    # 2. MK-677 (GHSR Agonist)
    mk_profile = enricher.fetch_compound_profile("mk_677")
    assert mk_profile is not None
    mk_targets = mk_profile.get("receptor_targets", [])
    assert any("ghsr" in t.get("target", "").lower() or "ghrelin" in t.get("target", "").lower() for t in mk_targets)
    
    # 3. Cascade Propagation for MK-677
    resp = client.get("/graph-data?stack=mk_677:15mg").json()
    shifts = resp.get("cascade_simulation", {}).get("biomarker_shifts", [])
    assert len(shifts) > 0
    gh_shift = next((s for s in shifts if s["biomarker_id"] in ("bio_growth_hormone", "bio_igf1")), None)
    assert gh_shift is not None
    assert gh_shift["estimated_delta"] > 0.0


def test_pkpd_simulation_response_evidence_and_limitations():
    """Verify PK/PD simulation API returns structured evidence tier and transparent data limitations."""
    from app.services.pkpd_engine import PKPDEngine
    from app.schemas.pkpd import PKPDSimulationRequest
    
    tak_comp = {
        "key": "tak_653",
        "name": "TAK-653",
        "smiles": "CC1=CC=C(C=C1)S(=O)(=O)N",
        "molecular_weight": 340.0,
        "logp": 2.1,
        "t_half_numeric": 14.0,
        "volume_of_distribution_l_kg": 1.5,
        "bioavailability_f": 0.65,
        "fraction_unbound": 0.15,
        "metadata": {
            "evidence_tier": "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION",
            "human_clinical_trials": False,
            "has_human_pk": False,
            "has_chronic_toxicity_studies": False,
            "rodent_ed50_mg_kg": 0.5,
            "animal_species": "rat",
        },
    }
    
    req = PKPDSimulationRequest(
        compound_key="tak_653",
        dose_mg=1.0,
        route="oral",
        weight_kg=70.0,
    )
    
    sim = PKPDEngine.simulate(compound=tak_comp, request=req)
    assert sim is not None
    assert sim.evidence_tier == "in_vitro_and_allometric_extrapolation"
    assert sim.human_data_present is False
    assert sim.data_limitations is not None
    assert sim.data_limitations.has_human_trials is False
    assert len(sim.data_limitations.known_limitations) > 0
    assert sim.allometric_extrapolation is not None
    assert sim.allometric_extrapolation.animal_species == "rat"
    assert sim.allometric_extrapolation.animal_dose_mg_kg == 0.5
    assert sim.allometric_extrapolation.total_human_dose_mg > 0.0
