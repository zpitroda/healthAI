from app.services.protocol_builder import calculate_protocol


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
