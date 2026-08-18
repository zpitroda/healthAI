from app.knowledge_graph.examples import build_testosterone_alopecia_graph
from app.routers.graph import graph_data
from app.services.graph_service import filter_graph_by_stack, resolve_stack_to_catalog_keys
from app.services.protocol_builder import calculate_protocol


def test_calculate_protocol_returns_safe_stack_for_goal():
    profile = {
        "goals": ["strength", "focus"],
        "experience": "intermediate",
        "sex": "male",
        "age": 30,
        "weight_kg": 82,
        "height_cm": 180,
        "sleep_hours": 6,
        "body_fat_pct": 18,
        "blood_pressure": 120,
        "labs": {
            "testosterone_ng_dl": 600,
            "hematocrit_pct": 47,
            "ldl_mg_dl": 100,
            "alt_u_l": 25,
        },
    }

    result = calculate_protocol(profile)

    assert result["summary"]
    assert any(item["compound"] == "Creatine" for item in result["stack"])
    assert any(item["compound"] == "Caffeine" for item in result["stack"])
    assert all(item["dose_mg"] > 0 for item in result["stack"])
    assert result["contraindications"] == []


def test_calculate_protocol_reviews_current_stack_for_conflicts_and_stress():
    profile = {
        "stack": ["caffeine", "caffeine"],
        "experience": "intermediate",
        "sex": "male",
        "age": 31,
        "weight_kg": 80,
        "height_cm": 180,
        "sleep_hours": 5.5,
        "body_fat_pct": 18,
        "blood_pressure": 125,
        "labs": {
            "testosterone_ng_dl": 620,
            "hematocrit_pct": 52,
            "ldl_mg_dl": 170,
            "alt_u_l": 85,
        },
    }

    result = calculate_protocol(profile)

    assert result["issues"]
    issue_text = " ".join(result["issues"]).lower()
    assert "oxidative" in issue_text or "stimulant" in issue_text or "duplicate" in issue_text
    assert result["interactions"]
    assert any("caffeine" in item.lower() for item in result["interactions"])


def test_calculate_protocol_accepts_compound_entries_with_dose_frequency_and_context():
    profile = {
        "stack": [
            {"compound": "caffeine", "dose": 100, "unit": "mg", "frequency": "daily", "timing": "with food"},
            {"compound": "caffeine", "dose": 100, "unit": "mg", "frequency": "daily", "timing": "before bed"},
        ],
        "sleep_hours": 5,
        "labs": {"hematocrit_pct": 48, "ldl_mg_dl": 120, "alt_u_l": 30},
    }

    result = calculate_protocol(profile)

    assert result["issues"]
    assert any(item["compound"] == "Caffeine" for item in result["stack"])
    assert any("daily" in item.lower() for item in result["interactions"])


def test_resolve_stack_to_catalog_keys_uses_database_names_and_keys():
    result = resolve_stack_to_catalog_keys(["Caffeine", {"compound": "Creatine"}, "unknown-compound"])
    assert result == ["caffeine", "creatine"]


def test_graph_data_returns_empty_when_stack_is_missing():
    response = graph_data(stack=[])
    import json
    payload = json.loads(response.body.decode())
    assert payload["nodes"] == []
    assert payload["edges"] == []


def test_data_driven_protocol_includes_rich_metadata():
    profile = {
        "goals": ["strength", "focus"],
        "weight_kg": 80,
        "labs": {"hematocrit_pct": 47, "ldl_mg_dl": 100, "alt_u_l": 25},
        "sleep_hours": 6.5,
    }

    result = calculate_protocol(profile)

    creatine = next(item for item in result["stack"] if item["compound"] == "Creatine")
    caffeine = next(item for item in result["stack"] if item["compound"] == "Caffeine")

    assert "side_effects" in creatine
    assert "interactions" in creatine
    assert "evidence_level" in creatine
    assert creatine["dose"]["dosage_range"]["common"] == 1600
    assert caffeine["receptor_targets"][0]["target"] == "A1 receptor"
    assert caffeine["dose"]["recommended_dose"] == 240


def test_filter_graph_by_stack_keeps_selected_compounds_visible_when_no_graph_match_exists():
    graph = build_testosterone_alopecia_graph()
    filtered = filter_graph_by_stack(graph, ["caffeine", "l_carnitine"], max_depth=2)

    assert "caffeine" in filtered.graph.nodes
    assert "l_carnitine" in filtered.graph.nodes
    assert len(filtered.graph.nodes) >= 2
    assert len(filtered.graph.edges) == 0
