import pytest
from app.services.catalog_service import CatalogService
from app.services.graph_service import (
    build_selected_compound_graph,
    get_exact_target_cascade_blueprint,
    EXACT_CASCADE_LOOKUP,
    TARGET_LOOKUP_INDEX,
)
from app.services.interaction_engine import InteractionEngine


def test_drostanolone_and_masteron_canonical_entity_resolution():
    catalog = CatalogService()
    drostanolone = catalog.get_compound("drostanolone")
    masteron = catalog.get_compound("masteron")

    assert drostanolone is not None, "drostanolone should be found in catalog"
    assert masteron is not None, "masteron synonym should resolve in catalog"
    assert drostanolone["key"] == masteron["key"]
    assert masteron["key"] == "drostanolone"


def test_methyldrostanolone_and_superdrol_canonical_entity_resolution():
    catalog = CatalogService()
    methyldrostanolone = catalog.get_compound("methyldrostanolone")
    superdrol = catalog.get_compound("superdrol")

    assert methyldrostanolone is not None, "methyldrostanolone should be found in catalog"
    assert superdrol is not None, "superdrol synonym should resolve in catalog"
    assert methyldrostanolone["inchikey"] == superdrol["inchikey"]
    assert superdrol["canonical_key"] == "methyldrostanolone"
    assert any(t.get("gene_symbol") == "AR" or "androgen" in str(t.get("target")).lower() for t in superdrol["receptor_targets"])


def test_canonicalize_and_merge_stack_aggregates_synonym_doses():
    catalog = CatalogService()
    raw_stack = [
        {"key": "drostanolone", "dose": 100, "unit": "mg"},
        {"key": "masteron", "dose": 150, "unit": "mg"},
        {"key": "tudca", "dose": 500, "unit": "mg"},
    ]

    merged = catalog.canonicalize_and_merge_stack(raw_stack)
    assert len(merged) == 2, "drostanolone and masteron should be merged into a single entry"

    drost_entry = next(item for item in merged if item["key"] == "drostanolone")
    assert drost_entry["dose_mg"] == 250.0, "Doses of drostanolone (100mg) and masteron (150mg) should sum to 250mg"
    assert "tudca" in [item["key"] for item in merged]


def test_zero_regex_exact_target_cascade_blueprint_lookup():
    # 1. UniProt Lookups
    ar_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="P10275")
    assert ar_bp is not None
    assert "Androgen Receptor" in ar_bp["target_name"]

    arom_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="P11511")
    assert arom_bp is not None
    assert "Aromatase" in arom_bp["target_name"]

    gsh_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="Q16478")
    assert gsh_bp is not None
    assert "Glutathione Biosynthesis" in gsh_bp["target_name"]

    at1_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="P30556")
    assert at1_bp is not None
    assert "Angiotensin II" in at1_bp["target_name"]

    # 2. Gene Symbol Lookups
    b1_bp = get_exact_target_cascade_blueprint(target_name="unknown", gene_symbol="ADRB1")
    assert b1_bp is not None
    assert "Beta-1" in b1_bp["target_name"]

    mr_bp = get_exact_target_cascade_blueprint(target_name="unknown", gene_symbol="NR3C2")
    assert mr_bp is not None
    assert "Mineralocorticoid" in mr_bp["target_name"]

    # 3. ChEMBL Target ID Lookups
    pde5_bp = get_exact_target_cascade_blueprint(target_name="unknown", chembl_target_id="CHEMBL1824")
    assert pde5_bp is not None
    assert "PDE5" in pde5_bp["target_name"]


def test_superdrol_and_tudca_stack_synergy_and_graph_cascade():
    engine = InteractionEngine()
    stack = [
        {"key": "superdrol", "dose": 10, "unit": "mg"},
        {"key": "tudca", "dose": 500, "unit": "mg"},
    ]

    analysis = engine.analyze_stack(stack)
    assert analysis is not None
    full_stack_balance = analysis["full_stack_balance"]

    # Verify graph building
    graph = build_selected_compound_graph(["superdrol:10mg", "tudca:500mg"])
    assert graph.get_node("methyldrostanolone") is not None or graph.get_node("superdrol") is not None

    # Verify active mitigation or synergy detected
    mitigations = full_stack_balance.get("active_mitigations", [])
    synergies = analysis.get("synergies", [])
    
    has_hep_synergy = (
        any("bile" in str(m).lower() or "hepato" in str(m).lower() or "liver" in str(m).lower() for m in mitigations)
        or any("tudca" in str(s).lower() or "bile" in str(s).lower() or "hepatobiliary" in str(s).lower() for s in synergies)
        or any("methyldrostanolone" in str(s).lower() or "superdrol" in str(s).lower() for s in synergies)
    )
    assert has_hep_synergy or len(mitigations) > 0 or len(synergies) > 0


def test_duplicate_synonyms_in_interaction_engine_do_not_produce_self_collisions():
    engine = InteractionEngine()
    stack = [
        {"key": "drostanolone", "dose": 100, "unit": "mg"},
        {"key": "masteron", "dose": 100, "unit": "mg"},
    ]

    analysis = engine.analyze_stack(stack)
    # The matrix should be unified to 1x1 canonical entity, zero self-collisions
    matrix = analysis.get("matrix", [])
    assert len(matrix) == 1, "Matrix should contain 1 merged compound entity"
    assert len(matrix[0][0].get("conflicts", [])) == 0, "Drostanolone should not conflict with itself (Masteron)"
