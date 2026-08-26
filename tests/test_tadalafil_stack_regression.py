import pytest
from app.services.catalog_service import CatalogService
from app.services.graph_service import build_selected_compound_graph, is_steroidal_androgen
from app.services.interaction_engine import InteractionEngine, _is_hormonal_or_endocrine_agent
from app.services.live_enrichment import LiveEnrichmentService


def test_tadalafil_is_not_classified_as_hormonal_or_androgen():
    """Verify that Tadalafil is not misclassified as a steroidal androgen or hormonal compound."""
    cs = CatalogService()
    tada = cs.get_compound("tadalafil")
    assert tada is not None

    assert is_steroidal_androgen(tada) is False
    is_hormonal, _, _ = _is_hormonal_or_endocrine_agent(tada)
    assert is_hormonal is False


def test_tadalafil_cascade_does_not_crash_testosterone():
    """Verify that propagating cascade for Tadalafil increases cGMP and lowers BP without touching testosterone or DHT."""
    cs = CatalogService()
    graph = build_selected_compound_graph(["tadalafil"], catalog_service=cs)
    results = graph.propagate_cascade(start_node_ids=["tadalafil"])

    shifts = results.get("biomarker_shifts", [])
    test_shift = next((b for b in shifts if b["biomarker_id"] == "bio_testosterone"), None)
    dht_shift = next((b for b in shifts if b["biomarker_id"] == "bio_dht"), None)
    cgmp_shift = next((b for b in shifts if b["biomarker_id"] == "bio_cgmp"), None)
    bp_shift = next((b for b in shifts if b["biomarker_id"] == "bio_blood_pressure"), None)

    # Testosterone and DHT should not be suppressed by Tadalafil
    assert test_shift is None or abs(test_shift["estimated_delta"]) < 1e-3
    assert dht_shift is None or abs(dht_shift["estimated_delta"]) < 1e-3

    # cGMP should increase and blood pressure should decrease
    assert cgmp_shift is not None
    assert cgmp_shift["estimated_delta"] > 0
    assert bp_shift is not None
    assert bp_shift["estimated_delta"] < 0


def test_testosterone_plus_tadalafil_stack_preserves_androgenic_action():
    """Verify that adding Tadalafil to Testosterone preserves androgenic efficacy while providing PDE5 vasodilation."""
    cs = CatalogService()
    graph = build_selected_compound_graph(["testosterone_cypionate", "tadalafil"], catalog_service=cs)
    results = graph.propagate_cascade(start_node_ids=["testosterone_cypionate", "tadalafil"])

    shifts = results.get("biomarker_shifts", [])
    test_shift = next((b for b in shifts if b["biomarker_id"] == "bio_testosterone"), None)
    cgmp_shift = next((b for b in shifts if b["biomarker_id"] == "bio_cgmp"), None)

    assert test_shift is not None
    assert test_shift["estimated_delta"] > 1000.0
    assert cgmp_shift is not None
    assert cgmp_shift["estimated_delta"] > 0


def test_tadalafil_stack_does_not_trigger_hormonal_fluctuation_warning():
    """Verify that InteractionEngine does not flag Tadalafil for steady-state hormonal fluctuations."""
    cs = CatalogService()
    tada = cs.get_compound("tadalafil")
    engine = InteractionEngine()

    result = engine.analyze_stack([tada])
    uncomp_risks = result.get("breakdown", {}).get("uncompensated_risks", [])
    
    # Ensure no hormonal fluctuation alert is present
    fluct_warnings = [r for r in uncomp_risks if "Fluctuation" in r.get("title", "")]
    assert len(fluct_warnings) == 0


def test_rxnorm_atc_filters_multi_ingredient_combination_classes():
    """Verify that fetch_rxnorm_atc filters out multi-ingredient combination drug concepts (e.g. finasteride / tadalafil)."""
    enricher = LiveEnrichmentService(timeout_seconds=8.0)
    atc_classes = enricher.fetch_rxnorm_atc("tadalafil")

    # Single ingredient ATC for tadalafil is G04BE (Drugs used in erectile dysfunction)
    # G04CB (Testosterone-5-alpha reductase inhibitors from finasteride/tadalafil) must be excluded
    assert "Testosterone-5-alpha reductase inhibitors" not in atc_classes
    assert "Antihypertensives for pulmonary arterial hypertension" not in atc_classes
    if atc_classes:
        assert any("erectile dysfunction" in c.lower() for c in atc_classes)


def test_tadalafil_10mg_lowers_blood_pressure_in_full_stack_balance():
    """Verify that InteractionEngine full_stack_balance correctly reflects blood pressure lowering and cGMP elevation for 10mg Tadalafil."""
    cs = CatalogService()
    tada = cs.get_compound("tadalafil")
    tada["dose"] = 10
    tada["unit"] = "mg"
    tada["frequency"] = "daily"

    engine = InteractionEngine()
    result = engine.analyze_stack([tada])
    fsb = result.get("full_stack_balance", {})
    axes = fsb.get("axes", [])

    bp_axis = next((a for a in axes if a.get("biomarker_id") == "bio_blood_pressure"), None)
    cgmp_axis = next((a for a in axes if a.get("biomarker_id") == "bio_cgmp"), None)

    assert bp_axis is not None
    assert bp_axis["estimated_value"] < bp_axis["baseline"]
    assert float(bp_axis["net_delta_str"].replace("mmHg", "").strip()) < 0.0

    assert cgmp_axis is not None
    assert cgmp_axis["estimated_value"] > cgmp_axis["baseline"]
    assert float(cgmp_axis["net_delta_str"].replace("index", "").strip()) > 0.0

