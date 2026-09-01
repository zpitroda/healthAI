import pytest
from app.services.catalog_service import CatalogService
from app.services.pharmacological_utility_engine import PharmacologicalUtilityEngine
from app.services.stack_intent_engine import StackIntentEngine


def test_exemestane_vs_anastrozole_scoring():
    catalog = CatalogService()
    exemestane = catalog.get_compound("exemestane")
    anastrozole = catalog.get_compound("anastrozole")
    letrozole = catalog.get_compound("letrozole")

    assert exemestane is not None
    assert anastrozole is not None
    assert letrozole is not None

    score_exemestane = PharmacologicalUtilityEngine.score_compound(
        exemestane, route="oral", target_context="CYP19A1 Aromatase", action_context="inhibitor"
    )
    score_anastrozole = PharmacologicalUtilityEngine.score_compound(
        anastrozole, route="oral", target_context="CYP19A1 Aromatase", action_context="inhibitor"
    )
    score_letrozole = PharmacologicalUtilityEngine.score_compound(
        letrozole, route="oral", target_context="CYP19A1 Aromatase", action_context="inhibitor"
    )

    # Exemestane scores higher than Anastrozole and Letrozole due to irreversible suicide inactivation and HDL preservation
    assert score_exemestane["total_score"] > score_anastrozole["total_score"]
    assert score_exemestane["total_score"] > score_letrozole["total_score"]
    assert score_exemestane["sub_scores"]["pharmacodynamics"] > score_anastrozole["sub_scores"]["pharmacodynamics"]


def test_injectable_vs_oral_carnitine_scoring():
    catalog = CatalogService()
    carnitine = catalog.get_compound("l_carnitine")
    assert carnitine is not None

    score_im = PharmacologicalUtilityEngine.score_compound(
        carnitine, route="intramuscular"
    )
    score_oral = PharmacologicalUtilityEngine.score_compound(
        carnitine, route="oral"
    )

    # Injectable carnitine achieves ~100% F and bypasses gut TMA-lyase (no TMAO penalty)
    assert score_im["total_score"] > score_oral["total_score"]
    assert score_im["sub_scores"]["pharmacokinetics"] > score_oral["sub_scores"]["pharmacokinetics"]
    assert score_im["sub_scores"]["protocol_economy"] > score_oral["sub_scores"]["protocol_economy"]


def test_optimal_route_resolution():
    catalog = CatalogService()
    carnitine = catalog.get_compound("l_carnitine")
    assert carnitine is not None

    # Unrestricted route -> resolves to intramuscular for optimal bioavailability & TMAO bypass
    route_default = PharmacologicalUtilityEngine.determine_optimal_route(carnitine, route_preference="all")
    assert route_default == "intramuscular"

    # Restricted to oral -> strictly respects user constraint
    route_oral = PharmacologicalUtilityEngine.determine_optimal_route(carnitine, route_preference="oral_only")
    assert route_oral == "oral"


def test_telmisartan_and_nebivolol_utility_scores():
    catalog = CatalogService()
    telmisartan = catalog.get_compound("telmisartan")
    nebivolol = catalog.get_compound("nebivolol")

    assert telmisartan is not None
    assert nebivolol is not None

    score_telmi = PharmacologicalUtilityEngine.score_compound(telmisartan)
    score_nebi = PharmacologicalUtilityEngine.score_compound(nebivolol)

    # Both achieve high utility scores due to pleiotropic beneficial targets (PPAR-gamma and eNOS respectively)
    assert score_telmi["total_score"] >= 70.0
    assert score_nebi["total_score"] >= 65.0


def test_rank_candidates_for_aromatase_target():
    catalog = CatalogService()
    ranked = PharmacologicalUtilityEngine.rank_candidates_for_target(
        target_name_or_keyword="CYP19A1 Aromatase",
        action="inhibitor",
        catalog=catalog
    )
    assert len(ranked) >= 2
    top_candidate_key = ranked[0]["key"]
    # Exemestane ranks #1 dynamically based on pharmacological properties
    assert top_candidate_key == "exemestane"


def test_build_scratch_stack_default_injectable_carnitine_and_no_allicin():
    # When route preference is unrestricted, anabolic physique stack chooses Injectable L-Carnitine
    # and does NOT trigger the oral TMAO gap (so Allicin is not included)
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="anabolic_physique",
        preferences={"route_preference": "all"}
    )
    compounds = proposal.get("compounds", [])
    keys = [c["key"] for c in compounds]
    names = [c["name"] for c in compounds]

    assert "l_carnitine" in keys
    carnitine_entry = next(c for c in compounds if c["key"] == "l_carnitine")
    assert carnitine_entry["route"] in ("intramuscular", "subcutaneous")
    assert carnitine_entry["dose"] <= 600  # Injectable dose is ~400mg vs 2000mg oral

    # Allicin is NOT needed because carnitine is injectable
    assert "allicin" not in keys


def test_build_scratch_stack_oral_only_uses_oral_carnitine_with_allicin():
    # When route preference is strictly oral_only, carnitine stays oral and Allicin is paired
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="anabolic_physique",
        preferences={"route_preference": "oral_only"}
    )
    compounds = proposal.get("compounds", [])
    keys = [c["key"] for c in compounds]

    assert "l_carnitine" in keys
    carnitine_entry = next(c for c in compounds if c["key"] == "l_carnitine")
    assert carnitine_entry["route"] == "oral"
    assert carnitine_entry["dose"] >= 1500  # Oral dose is ~2000mg

    # Allicin IS attached to inhibit bacterial TMA-lyase for oral carnitine
    assert "allicin" in keys


def test_build_scratch_stack_enhanced_selects_exemestane_for_aromatization():
    # When testosterone cypionate is in enhanced mode, aromatase protection dynamically selects Exemestane
    proposal = StackIntentEngine.build_scratch_stack_proposal(
        goal_id="anabolic_physique",
        preferences={"substance_style": "enhanced", "risk_tolerance": "performance"}
    )
    compounds = proposal.get("compounds", [])
    keys = [c["key"] for c in compounds]

    assert "testosterone_cypionate" in keys
    # Exemestane is dynamically selected as the superior irreversible aromatase inactivator
    assert "exemestane" in keys
