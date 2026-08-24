from __future__ import annotations

import pytest
from app.schemas.pkpd import PKPDSimulationRequest, PKPDSimulationResponse
from app.services.pkpd_enricher import PKPDEnricher
from app.services.pkpd_engine import PKPDEngine
from app.services.interaction_engine import InteractionEngine
from app.services.graph_service import parse_compound_spec


def test_route_pk_parameters_calculation():
    """Verify route-specific PK parameters dynamically scale F, ka, tmax, and first-pass extraction."""
    compound = {
        "name": "Testosterone",
        "key": "testosterone",
        "molecular_weight": 288.42,
        "logp": 3.32,
        "tpsa": 37.3,
        "oral_bioavailability": 0.05,  # High hepatic first-pass extraction
        "t_half_numeric": 1.5,
        "absorption_rate_ka": 1.2,
    }

    # 1. Oral Route
    oral_pk = PKPDEnricher.calculate_route_pk_parameters(compound, "oral")
    assert oral_pk["route_name"] == "oral"
    assert oral_pk["bioavailability_f"] <= 0.20
    assert oral_pk["first_pass_bypass_pct"] < 30.0
    assert oral_pk["first_pass_hepatic_pct"] > 70.0

    # 2. Intramuscular Route
    im_pk = PKPDEnricher.calculate_route_pk_parameters(compound, "intramuscular")
    assert im_pk["route_name"] == "intramuscular"
    assert im_pk["bioavailability_f"] >= 0.85
    assert im_pk["first_pass_bypass_pct"] == 100.0
    assert im_pk["first_pass_hepatic_pct"] == 0.0

    # 3. Transdermal Route (potts-guy skin permeation & flip-flop kinetics)
    td_pk = PKPDEnricher.calculate_route_pk_parameters(compound, "transdermal")
    assert td_pk["route_name"] == "transdermal"
    assert td_pk["absorption_rate_ka"] < 0.25
    assert td_pk["apparent_t_half_h"] > oral_pk["apparent_t_half_h"]  # Flip-flop absorption-limited elimination
    assert td_pk["first_pass_bypass_pct"] == 100.0

    # 4. Sublingual Route
    sl_pk = PKPDEnricher.calculate_route_pk_parameters(compound, "sublingual")
    assert sl_pk["route_name"] == "sublingual"
    assert sl_pk["bioavailability_f"] > oral_pk["bioavailability_f"]
    assert sl_pk["first_pass_bypass_pct"] == 100.0
    assert sl_pk["absorption_rate_ka"] > oral_pk["absorption_rate_ka"]

    # 5. Intravenous Route
    iv_pk = PKPDEnricher.calculate_route_pk_parameters(compound, "intravenous")
    assert iv_pk["route_name"] == "intravenous"
    assert iv_pk["bioavailability_f"] == 1.0
    assert iv_pk["first_pass_bypass_pct"] == 100.0


def test_pkpd_simulation_across_routes():
    """Verify PKPDEngine simulation reflects route-specific curve kinetics and metabolite exposure."""
    compound = {
        "name": "Metformin",
        "key": "metformin",
        "molecular_weight": 129.16,
        "logp": -1.43,
        "tpsa": 88.0,
        "bioavailability_f": 0.55,
        "t_half_numeric": 5.0,
        "volume_of_distribution_l_kg": 1.5,
    }

    # Run oral simulation
    req_oral = PKPDSimulationRequest(
        compound_key="metformin",
        dose_mg=500.0,
        dosing_interval_h=24.0,
        route="oral",
        steady_state=False,
    )
    res_oral = PKPDEngine.simulate(compound, req_oral)
    assert res_oral.route == "oral"
    assert res_oral.c_max_ng_ml > 0
    assert res_oral.route_pk_details is not None
    assert len(res_oral.time_series) > 0

    # Run IV simulation
    req_iv = PKPDSimulationRequest(
        compound_key="metformin",
        dose_mg=500.0,
        dosing_interval_h=24.0,
        route="intravenous",
        steady_state=False,
    )
    res_iv = PKPDEngine.simulate(compound, req_iv)
    assert res_iv.route == "intravenous"
    # IV should achieve higher Cmax and faster Tmax than oral
    assert res_iv.c_max_ng_ml > res_oral.c_max_ng_ml
    assert res_iv.t_max_h < res_oral.t_max_h
    assert res_iv.first_pass_bypass_pct == 100.0


def test_parse_compound_spec_with_routes():
    """Verify parse_compound_spec parses colon format route and dict route correctly."""
    # Colon string with route
    parsed1 = parse_compound_spec("testosterone:100mg:weekly:im")
    assert parsed1["key"] == "testosterone"
    assert parsed1["dose_mg"] == 100.0
    assert parsed1["frequency"] == "weekly"
    assert parsed1["route"] == "im"

    # Dict spec with route
    parsed2 = parse_compound_spec({
        "key": "semaglutide",
        "dose": 0.5,
        "unit": "mg",
        "frequency": "weekly",
        "route": "subcutaneous",
    })
    assert parsed2["key"] == "semaglutide"
    assert parsed2["dose_mg"] == 0.5
    assert parsed2["route"] == "subcutaneous"


def test_stack_analysis_hepatic_bypass_discount():
    """Verify stack evaluation discounts hepatic burden when route bypasses portal first-pass circulation."""
    engine = InteractionEngine()

    # Stack A: Oral 17-alkylated or hepatically cleared compound
    stack_oral = [
        {
            "key": "stanozolol",
            "name": "Stanozolol",
            "dose_mg": 25.0,
            "route": "oral",
            "organ_burdens": {"hepatic": "high", "cardiovascular": "moderate"},
        }
    ]
    res_oral = engine.analyze_stack(stack_oral)
    oral_hepatic_score = res_oral["breakdown"]["organ_burdens"]["hepatic"]["score"]

    # Stack B: Injectable / Parenteral compound bypassing first-pass
    stack_im = [
        {
            "key": "stanozolol",
            "name": "Stanozolol",
            "dose_mg": 25.0,
            "route": "intramuscular",
            "organ_burdens": {"hepatic": "high", "cardiovascular": "moderate"},
        }
    ]
    res_im = engine.analyze_stack(stack_im)
    im_hepatic_score = res_im["breakdown"]["organ_burdens"]["hepatic"]["score"]

    # First-pass portal bypass should reduce hepatic strain score
    assert im_hepatic_score < oral_hepatic_score


def test_androgen_oral_inactivation_and_route_switch():
    """Verify unalkylated steroidal androgens undergo first-pass inactivation if oral, but activate fully when IM."""
    from app.services.graph_service import build_selected_compound_graph, compute_target_combined_effects

    # 1. Oral Testosterone 20mg (negligible bioavailability ~3%)
    graph_oral = build_selected_compound_graph([{"key": "testosterone", "dose": 20, "unit": "mg", "route": "oral"}])
    eff_oral = compute_target_combined_effects(graph_oral, custom_doses={"testosterone": {"dose_mg": 20.0, "route": "oral"}})

    # 2. Intramuscular Testosterone 20mg (high bioavailability ~95%)
    graph_im = build_selected_compound_graph([{"key": "testosterone", "dose": 20, "unit": "mg", "route": "intramuscular"}])
    eff_im = compute_target_combined_effects(graph_im, custom_doses={"testosterone": {"dose_mg": 20.0, "route": "intramuscular"}})

    # Circulating testosterone pool stimulation should be vastly higher for IM (due to oral first-pass destruction)
    oral_pool = next((v for k, v in eff_oral.items() if "testosterone pool" in k.lower()), None)
    im_pool = next((v for k, v in eff_im.items() if "testosterone pool" in k.lower()), None)

    if oral_pool and im_pool:
        assert im_pool["net_activation"] > oral_pool["net_activation"] * 8.0

    # Androgen Receptor saturation should be significantly higher for IM than oral
    oral_ar = next((v for k, v in eff_oral.items() if "androgen receptor" in k.lower()), None)
    im_ar = next((v for k, v in eff_im.items() if "androgen receptor" in k.lower()), None)
    if oral_ar and im_ar:
        assert im_ar["receptor_saturation_pct"] > oral_ar["receptor_saturation_pct"] * 1.5

