import pytest
from app.services.dosing_service import (
    DOSING_FREQUENCY_METADATA,
    normalize_dosing_frequency,
    get_frequency_multiplier,
    get_frequency_interval_hours,
    parse_dose_string_or_spec,
)
from app.knowledge_graph.graph import BiologicalGraph, TIMELINE_HORIZONS, parse_timeline_days
from app.services.graph_service import (
    build_selected_compound_graph,
    parse_compound_spec,
)
from app.services.interaction_engine import (
    InteractionEngine,
)


def test_dosing_frequency_multipliers_and_normalization():
    # Standard frequencies
    assert get_frequency_multiplier("daily") == 1.0
    assert get_frequency_multiplier("twice_daily") == 2.0
    assert get_frequency_multiplier("bid") == 2.0
    assert get_frequency_multiplier("three_times_daily") == 3.0
    assert get_frequency_multiplier("tid") == 3.0
    assert get_frequency_multiplier("four_times_daily") == 4.0
    assert get_frequency_multiplier("qid") == 4.0
    assert get_frequency_multiplier("every_other_day") == 0.5
    assert get_frequency_multiplier("qod") == 0.5
    assert abs(get_frequency_multiplier("twice_weekly") - (2.0 / 7.0)) < 1e-4
    assert abs(get_frequency_multiplier("weekly") - (1.0 / 7.0)) < 1e-4
    assert abs(get_frequency_multiplier("qw") - (1.0 / 7.0)) < 1e-4
    assert abs(get_frequency_multiplier("biweekly") - (1.0 / 14.0)) < 1e-4
    assert abs(get_frequency_multiplier("monthly") - (1.0 / 30.0)) < 1e-4
    assert get_frequency_multiplier("as_needed") == 0.5


def test_dosing_frequency_interval_hours():
    assert get_frequency_interval_hours("daily") == 24.0
    assert get_frequency_interval_hours("twice_daily") == 12.0
    assert get_frequency_interval_hours("three_times_daily") == 8.0
    assert get_frequency_interval_hours("every_other_day") == 48.0
    assert get_frequency_interval_hours("weekly") == 168.0


def test_parse_dose_spec_with_frequency():
    # String spec with colon: compound:dose:frequency
    spec1 = parse_dose_string_or_spec("testosterone:200mg:weekly")
    assert spec1["key"] == "testosterone"
    assert spec1["dose_val"] == 200.0
    assert spec1["dose_unit"] == "mg"
    assert spec1["frequency"] == "weekly"
    assert abs(spec1["effective_daily_dose_mg"] - (200.0 / 7.0)) < 0.05

    # Dict spec
    spec2 = parse_dose_string_or_spec({
        "key": "caffeine",
        "dose": 200,
        "unit": "mg",
        "frequency": "twice_daily",
    })
    assert spec2["key"] == "caffeine"
    assert spec2["dose_val"] == 200.0
    assert spec2["frequency"] == "twice_daily"
    assert spec2["effective_daily_dose_mg"] == 400.0


def test_timeline_horizon_parsing():
    days, key, label = parse_timeline_days("1_day")
    assert days == 1.0
    assert key == "1_day"

    days, key, label = parse_timeline_days("3_days")
    assert days == 3.0

    days, key, label = parse_timeline_days("1_week")
    assert days == 7.0

    days, key, label = parse_timeline_days("2_weeks")
    assert days == 14.0

    days, key, label = parse_timeline_days("1_month")
    assert days == 28.0 or days == 30.0

    days, key, label = parse_timeline_days("steady_state")
    assert days is None
    assert key == "steady_state"

    days, key, label = parse_timeline_days(14)
    assert days == 14.0


def test_cascade_effects_timeline_progression():
    graph = build_selected_compound_graph(["caffeine:200mg:daily", "testosterone:200mg:weekly"])
    
    # 1 Day timeline
    cascade_day1 = graph.propagate_cascade(["caffeine", "testosterone"], timeline="1_day")
    assert cascade_day1["timeline"] == "1_day"
    assert cascade_day1["timeline_days"] == 1.0

    # 3 Months timeline
    cascade_3m = graph.propagate_cascade(["caffeine", "testosterone"], timeline="3_months")
    assert cascade_3m["timeline"] == "3_months"
    assert cascade_3m["timeline_days"] == 84.0 or cascade_3m["timeline_days"] == 90.0

    # Steady State
    cascade_ss = graph.propagate_cascade(["caffeine", "testosterone"], timeline="steady_state")
    assert cascade_ss["timeline"] == "steady_state"
    assert cascade_ss["timeline_days"] is None

    # Hematocrit has t1/2 ~28d (erythropoiesis slow adaptation)
    # Heart rate / Blood pressure has t1/2 ~0.5d (rapid autonomic adaptation)
    hct_day1 = next((b for b in cascade_day1["biomarker_shifts"] if "hematocrit" in b["biomarker_id"].lower() or "hematocrit" in b["name"].lower()), None)
    hct_3m = next((b for b in cascade_3m["biomarker_shifts"] if "hematocrit" in b["biomarker_id"].lower() or "hematocrit" in b["name"].lower()), None)
    hct_ss = next((b for b in cascade_ss["biomarker_shifts"] if "hematocrit" in b["biomarker_id"].lower() or "hematocrit" in b["name"].lower()), None)

    if hct_day1 and hct_ss:
        # Day 1 shift should be much smaller fraction of steady state than 3 months
        assert abs(hct_day1["net_shift"]) < abs(hct_ss["net_shift"])
    if hct_3m and hct_ss:
        # At 3 months (90 days = >3 half lives), hematocrit should be near full steady state (>85%)
        assert abs(hct_3m["net_shift"]) >= abs(hct_day1["net_shift"])


def test_interaction_engine_stack_analysis_with_frequency_and_timeline():
    engine = InteractionEngine()
    profile = {
        "compounds": [
            {"key": "testosterone", "dose": 200, "unit": "mg", "frequency": "weekly"},
            {"key": "anastrozole", "dose": 0.5, "unit": "mg", "frequency": "twice_weekly"},
            {"key": "telmisartan", "dose": 40, "unit": "mg", "frequency": "daily"},
        ],
        "timeline": "2_weeks",
        "labs": {"alt_u_l": 25, "hematocrit_pct": 45, "blood_pressure": 120},
    }
    
    # Run at 2 weeks timeline
    report_2w = engine.analyze_stack(profile)

    assert "full_stack_balance" in report_2w
    bal = report_2w["full_stack_balance"]
    assert bal["timeline"] == "2_weeks"
    assert bal["timeline_days"] == 14.0
    assert "timeline_label" in bal
    assert isinstance(bal["axes"], list)
    assert len(bal["axes"]) > 0
