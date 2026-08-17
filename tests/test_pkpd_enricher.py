from app.services.pkpd_enricher import PKPDEnricher


def test_usan_stem_benchmarks_statin():
    enricher = PKPDEnricher()
    compound = {"key": "rosuvastatin", "name": "Rosuvastatin"}
    match = enricher.match_usan_pkpd(compound)
    assert match is not None
    assert match["class_name"] == "HMG-CoA Reductase Inhibitor"
    assert match["t_half_numeric"] == 14.0
    assert match["bcs_class"] == "Class II (Low Sol, High Perm)"


def test_usan_stem_benchmarks_sartan():
    enricher = PKPDEnricher()
    compound = {"key": "candesartan", "name": "Candesartan"}
    match = enricher.match_usan_pkpd(compound)
    assert match is not None
    assert "Angiotensin II Receptor" in match["class_name"]
    assert match["t_half_numeric"] == 24.0
    assert match["therapeutic_index"] == 26.6


def test_qspr_parameter_completer():
    enricher = PKPDEnricher()
    # Unclassified test compound
    compound = {
        "key": "novel_compound_xyz",
        "name": "Novel Compound XYZ",
        "logp": 3.5,
        "tpsa": 70.0,
    }
    enriched = enricher.enrich_compound_pkpd(compound, online=False)
    assert enriched["t_half_numeric"] is not None
    assert enriched["volume_of_distribution_l_kg"] is not None
    assert enriched["bioavailability_f"] is not None
    assert enriched["fraction_unbound"] is not None
    assert enriched["protein_binding_pct"] is not None


def test_enrich_compound_with_usan_pathway():
    enricher = PKPDEnricher()
    compound = {"key": "metoprolol", "name": "Metoprolol"}
    enriched = enricher.enrich_compound_pkpd(compound, online=False)
    assert enriched["t_half_numeric"] == 5.0
    assert enriched["bioavailability_f"] == 0.50
    assert len(enriched.get("pathway_details", [])) >= 1
    assert "R-HSA-" in enriched["pathway_details"][0]["id"]
