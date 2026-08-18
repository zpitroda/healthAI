from __future__ import annotations

import pytest
from app.services.dosing_service import (
    get_default_compound_dose,
    parse_dose_string_or_spec,
    CLINICAL_REFERENCE_DOSES_MG,
)
from app.services.catalog_service import CatalogService
from app.services.graph_service import parse_compound_spec


def test_clinical_reference_default_doses_and_natural_units():
    # Clenbuterol: 40 mcg (0.04 mg) -> 40 μg
    clen = get_default_compound_dose("clenbuterol")
    assert clen["dose_mg"] == 0.04
    assert clen["dose_val"] == 40.0
    assert clen["dose_unit"] == "μg"
    assert clen["dose_display"] == "40 μg"

    # Nebivolol: 5 mg -> 5 mg
    neb = get_default_compound_dose("nebivolol")
    assert neb["dose_mg"] == 5.0
    assert neb["dose_val"] == 5.0
    assert neb["dose_unit"] == "mg"
    assert neb["dose_display"] == "5 mg"

    # Clonidine: 0.1 mg -> 100 μg
    clon = get_default_compound_dose("clonidine")
    assert clon["dose_mg"] == 0.1
    assert clon["dose_val"] == 100.0
    assert clon["dose_unit"] == "μg"
    assert clon["dose_display"] == "100 μg"

    # Creatine: 5000 mg -> 5 g
    creatine = get_default_compound_dose("creatine")
    assert creatine["dose_mg"] == 5000.0
    assert creatine["dose_val"] == 5.0
    assert creatine["dose_unit"] == "g"
    assert creatine["dose_display"] == "5 g"

    # Caffeine: 200 mg -> 200 mg
    caff = get_default_compound_dose("caffeine")
    assert caff["dose_mg"] == 200.0
    assert caff["dose_val"] == 200.0
    assert caff["dose_unit"] == "mg"

    # Aspirin: 81 mg -> 81 mg
    asp = get_default_compound_dose("aspirin")
    assert asp["dose_mg"] == 81.0
    assert asp["dose_val"] == 81.0
    assert asp["dose_unit"] == "mg"

    # Metformin: 500 mg -> 500 mg
    met = get_default_compound_dose("metformin")
    assert met["dose_mg"] == 500.0
    assert met["dose_val"] == 500.0
    assert met["dose_unit"] == "mg"


def test_parse_dose_string_or_spec():
    p1 = parse_dose_string_or_spec("clenbuterol:40ug")
    assert p1["key"] == "clenbuterol"
    assert pytest.approx(p1["dose_mg"], 1e-4) == 0.04
    assert p1["dose_unit"] == "μg"
    assert p1["dose_val"] == 40.0

    p2 = parse_dose_string_or_spec("nebivolol:5mg")
    assert p2["key"] == "nebivolol"
    assert p2["dose_mg"] == 5.0
    assert p2["dose_unit"] == "mg"

    p3 = parse_dose_string_or_spec("creatine:5g")
    assert p3["key"] == "creatine"
    assert p3["dose_mg"] == 5000.0
    assert p3["dose_unit"] == "g"

    # Default fallback lookup when no dose is specified
    p4 = parse_dose_string_or_spec("clenbuterol")
    assert p4["key"] == "clenbuterol"
    assert pytest.approx(p4["dose_mg"], 1e-4) == 0.04
    assert p4["dose_unit"] == "μg"


def test_catalog_service_attaches_default_dose_to_compounds():
    service = CatalogService()
    compound = service.get_compound("clenbuterol")
    assert compound is not None
    assert "default_dose" in compound
    assert compound["default_dose"]["dose_val"] == 40.0
    assert compound["default_dose"]["dose_unit"] == "μg"
    assert compound["dose"] == 40.0
    assert compound["unit"] == "μg"


def test_graph_service_parse_compound_spec_structured_dict():
    spec = {"key": "clenbuterol", "dose": 40, "unit": "μg"}
    parsed = parse_compound_spec(spec)
    assert parsed["key"] == "clenbuterol"
    assert pytest.approx(parsed["dose_mg"], 1e-4) == 0.04
    assert parsed["dose_str"] == "40 μg"

    spec2 = {"key": "creatine", "dose": 5, "unit": "g"}
    parsed2 = parse_compound_spec(spec2)
    assert parsed2["key"] == "creatine"
    assert parsed2["dose_mg"] == 5000.0
    assert parsed2["dose_str"] == "5 g"
