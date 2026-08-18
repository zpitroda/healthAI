import json
import os
import sqlite3

from app.services.catalog_service import CatalogService
from scripts.populate_catalog import (
    filter_connected_chembl_indications,
    filter_connected_chembl_mechanisms,
    filter_low_signal_chembl_records,
    filter_chembl_drug_subset_records,
    inspect_chembl_sqlite_schema,
    merge_chembl_enrichment,
)


def test_catalog_service_can_seed_and_read_compounds(tmp_path):
    db_path = tmp_path / "catalog.db"
    os.environ["HEALTHAI_CATALOG_DB"] = str(db_path)

    service = CatalogService()
    service.reset_database()
    service.upsert_compound({
        "key": "testosterone",
        "name": "Testosterone",
        "drug_class": "androgen receptor agonist",
        "mechanism": "Binds androgen receptor and modulates transcription.",
        "receptor_targets": [{"target": "AR", "action": "agonist", "family": "androgen"}],
        "categories": ["hormone", "performance"],
        "indications": ["testosterone"],
        "dosing": {"unit": "mg/week", "basis": "bodyweight", "mg_per_kg": {"threshold": 0.6, "common": 1.2, "heavy": 1.8}},
        "reason": "Supports androgen receptor signaling.",
        "citation": "Test citation",
        "contraindications": ["Use with caution in cardiovascular disease."],
        "side_effects": ["Acne"],
        "interactions": ["Can potentiate aromatase-related effects."],
        "evidence_level": "moderate",
        "risk_band": "high",
        "graph_tags": ["androgen", "AR"],
    })

    saved = service.get_compound("testosterone")
    assert saved["name"] == "Testosterone"
    assert saved["receptor_targets"][0]["target"] == "AR"

    keys = [item["key"] for item in service.list_compounds()]
    assert "testosterone" in keys


def test_catalog_service_merges_duplicate_records_by_inchikey(tmp_path):
    db_path = tmp_path / "catalog.db"
    os.environ["HEALTHAI_CATALOG_DB"] = str(db_path)

    service = CatalogService()
    service.reset_database()

    service.upsert_compound({
        "key": "caffeine",
        "name": "Caffeine",
        "canonical_name": "Caffeine",
        "inchikey": "RUVINXRJKPEIMQ-UHFFFAOYSA-N",
        "external_ids": {"pubchem_cid": "2519", "chembl_id": "CHEMBL579"},
        "drug_class": "adenosine receptor antagonist",
        "mechanism": "Blocks adenosine receptors.",
        "receptor_targets": [{"target": "A1 receptor", "action": "antagonist", "family": "adenosine"}],
        "categories": ["focus"],
        "indications": ["focus"],
        "dosing": {"unit": "mg/day"},
        "reason": "Cognitive support.",
        "citation": "Test citation",
        "contraindications": [],
        "side_effects": ["Jitters"],
        "interactions": [],
        "evidence_level": "strong",
        "risk_band": "moderate",
        "graph_tags": ["adenosine"],
    })

    service.upsert_compound({
        "key": "caffeine-duplicate",
        "name": "cafFeine",
        "canonical_name": "Caffeine",
        "inchikey": "RUVINXRJKPEIMQ-UHFFFAOYSA-N",
        "external_ids": {"pubchem_cid": "2519", "chembl_id": "CHEMBL579"},
        "drug_class": "adenosine receptor antagonist",
        "mechanism": "Blocks adenosine receptors.",
        "receptor_targets": [{"target": "A1 receptor", "action": "antagonist", "family": "adenosine"}],
        "categories": ["focus"],
        "indications": ["focus"],
        "dosing": {"unit": "mg/day"},
        "reason": "Cognitive support.",
        "citation": "Test citation",
        "contraindications": [],
        "side_effects": ["Jitters"],
        "interactions": [],
        "evidence_level": "strong",
        "risk_band": "moderate",
        "graph_tags": ["adenosine"],
    })

    compounds = service.list_compounds()
    caffeine_entries = [item for item in compounds if item["inchikey"] == "RUVINXRJKPEIMQ-UHFFFAOYSA-N"]
    assert len(caffeine_entries) == 1
    assert caffeine_entries[0]["key"] == "caffeine"
    assert caffeine_entries[0]["canonical_key"] == "RUVINXRJKPEIMQ-UHFFFAOYSA-N"


def test_graph_data_uses_selected_compound_target_edges(tmp_path):
    db_path = tmp_path / "catalog.db"
    os.environ["HEALTHAI_CATALOG_DB"] = str(db_path)

    service = CatalogService()
    service.reset_database()
    service.upsert_compound({
        "key": "CHEMBL38943",
        "name": "Test Agonist",
        "canonical_name": "Test Agonist",
        "drug_class": "androgen receptor agonist",
        "mechanism": "Binds androgen receptor.",
        "receptor_targets": [{"target": "Androgen receptor", "action": "agonist", "family": "androgen"}],
        "categories": ["hormone"],
        "indications": ["performance"],
        "dosing": {"unit": "mg/week"},
        "reason": "Androgen signaling support.",
        "citation": "Test citation",
        "contraindications": [],
        "side_effects": [],
        "interactions": [],
        "evidence_level": "moderate",
        "risk_band": "high",
        "graph_tags": ["androgen", "AR"],
    })

    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers.graph import graph_data

    client = TestClient(app)
    response = client.get("/graph-data", params={"stack": "CHEMBL38943", "depth": 2})
    payload = response.json()
    node_ids = {node["id"] for node in payload["nodes"]}
    edges = payload["edges"]

    assert response.status_code == 200
    assert "CHEMBL38943" in node_ids
    assert "Androgen Receptor (AR / NR3C4)" in node_ids
    assert any(
        edge["source"] == "CHEMBL38943" and edge["target"] == "Androgen Receptor (AR / NR3C4)" and str(edge["type"]).lower() in {"agonizes", "agonist"}
        for edge in edges
    )

    for stack_value in (["CHEMBL38943"], "CHEMBL38943"):
        response = graph_data(stack=stack_value, depth=2)
        payload = json.loads(response.body.decode())
        node_ids = {node["id"] for node in payload["nodes"]}
        edges = payload["edges"]

        assert "CHEMBL38943" in node_ids
        assert "Androgen Receptor (AR / NR3C4)" in node_ids
        assert any(
            edge["source"] == "CHEMBL38943" and edge["target"] == "Androgen Receptor (AR / NR3C4)" and str(edge["type"]).lower() in {"agonizes", "agonist"}
            for edge in edges
        )


def test_graph_data_labels_antagonist_edges_correctly(tmp_path):
    db_path = tmp_path / "catalog.db"
    os.environ["HEALTHAI_CATALOG_DB"] = str(db_path)

    service = CatalogService()
    service.reset_database()
    service.upsert_compound({
        "key": "CHEMBL1017",
        "name": "TELMISARTAN",
        "canonical_name": "TELMISARTAN",
        "drug_class": "ARB",
        "mechanism": "Type-1 angiotensin II receptor antagonist",
        "receptor_targets": [{"target": "Type-1 angiotensin II receptor", "action": "antagonist", "family": "SINGLE PROTEIN"}],
        "categories": ["cardio"],
        "indications": ["hypertension"],
        "dosing": {"unit": "mg/day"},
        "reason": "Blocks angiotensin signaling.",
        "citation": "Test citation",
        "contraindications": [],
        "side_effects": [],
        "interactions": [],
        "evidence_level": "strong",
        "risk_band": "moderate",
        "graph_tags": ["angiotensin"],
    })

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/graph-data", params={"stack": "CHEMBL1017", "depth": 2})
    payload = response.json()

    assert response.status_code == 200
    assert any(
        edge["source"] == "CHEMBL1017"
        and ("angiotensin" in str(edge["target"]).lower() or "agtr1" in str(edge["target"]).lower() or "at1" in str(edge["target"]).lower())
        and str(edge["type"]).upper() in ("ANTAGONIZES", "INHIBITOR", "ANTAGONIST")
        for edge in payload["edges"]
    )


def test_graph_data_preserves_labels_for_generic_target_actions(tmp_path):
    db_path = tmp_path / "catalog.db"
    os.environ["HEALTHAI_CATALOG_DB"] = str(db_path)

    service = CatalogService()
    service.reset_database()
    service.upsert_compound({
        "key": "caffeine",
        "name": "Caffeine",
        "canonical_name": "Caffeine",
        "mechanism": "Modulates alertness.",
        "receptor_targets": [{"target": "dopamine signaling", "action": "modulator", "family": "neuromodulation"}],
        "categories": ["focus"],
        "indications": ["focus"],
        "dosing": {"unit": "mg/day"},
        "reason": "Alertness.",
        "citation": "Test citation",
        "contraindications": [],
        "side_effects": [],
        "interactions": [],
        "evidence_level": "strong",
        "risk_band": "moderate",
        "graph_tags": ["CNS"],
    })
    service.upsert_compound({
        "key": "creatine",
        "name": "Creatine",
        "canonical_name": "Creatine",
        "mechanism": "Supports ATP regeneration.",
        "receptor_targets": [{"target": "ATP-PCr system", "action": "supports energetics", "family": "metabolism"}],
        "categories": ["strength"],
        "indications": ["strength"],
        "dosing": {"unit": "mg/day"},
        "reason": "Energetics.",
        "citation": "Test citation",
        "contraindications": [],
        "side_effects": [],
        "interactions": [],
        "evidence_level": "strong",
        "risk_band": "low",
        "graph_tags": ["metabolism"],
    })

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/graph-data", params={"stack": ["caffeine", "creatine"], "depth": 2})
    payload = response.json()

    assert response.status_code == 200
    assert any(edge["source"] == "caffeine" and "dopamine" in str(edge["target"]).lower() for edge in payload["edges"])
    assert any(edge["source"] == "creatine" and ("atp" in str(edge["target"]).lower() or "pcr" in str(edge["target"]).lower()) for edge in payload["edges"])


def test_chembl_sqlite_bulk_records_can_be_ingested(tmp_path):
    db_path = tmp_path / "chembl_37.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE molecule_dictionary (molecule_chembl_id TEXT, pref_name TEXT, standard_inchi_key TEXT, molecule_type TEXT, max_phase TEXT, full_mwt REAL, alogp REAL, molecular_formula TEXT)"
    )
    conn.execute(
        "INSERT INTO molecule_dictionary VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("CHEMBL579", "Caffeine", "RUVINXRJKPEIMQ-UHFFFAOYSA-N", "Small molecule", "4", 194.19, -0.07, "C8H10N4O2"),
    )
    conn.execute(
        "CREATE TABLE molecule_synonyms (molecule_chembl_id TEXT, synonym TEXT)"
    )
    conn.execute(
        "INSERT INTO molecule_synonyms VALUES (?, ?)",
        ("CHEMBL579", "cafFeine"),
    )
    conn.commit()
    conn.close()

    from scripts.populate_catalog import read_chembl_sqlite_records

    records = read_chembl_sqlite_records(str(db_path))
    assert len(records) == 1
    record = records[0]
    assert record["key"] == "CHEMBL579"
    assert record["canonical_name"] == "Caffeine"
    assert record["canonical_key"] == "RUVINXRJKPEIMQ-UHFFFAOYSA-N"
    assert record["synonyms"] == ["cafFeine"]


def test_chembl_low_signal_records_are_filtered_out():
    records = [
        {
            "key": "CHEMBL579",
            "name": "Caffeine",
            "canonical_name": "Caffeine",
            "canonical_key": "RUVINXRJKPEIMQ-UHFFFAOYSA-N",
            "synonyms": ["cafFeine"],
            "metadata": {"chembl": {"molecule_type": "Small molecule", "max_phase": "4", "full_mwt": "194.19", "molecular_formula": "C8H10N4O2"}},
        },
        {
            "key": "CHEMBL99999",
            "name": "VeryNicheCompound",
            "canonical_name": "VeryNicheCompound",
            "canonical_key": None,
            "synonyms": [],
            "metadata": {"chembl": {"molecule_type": "", "max_phase": "", "full_mwt": "", "molecular_formula": ""}},
        },
    ]

    filtered = filter_low_signal_chembl_records(records, min_score=4, min_synonyms=1, min_metadata_fields=2)
    assert len(filtered) == 1
    assert filtered[0]["key"] == "CHEMBL579"


def test_chembl_drug_subset_filter_keeps_medically_relevant_entries():
    records = [
        {
            "key": "CHEMBL579",
            "name": "Caffeine",
            "canonical_name": "Caffeine",
            "canonical_key": "RUVINXRJKPEIMQ-UHFFFAOYSA-N",
            "synonyms": ["cafFeine"],
            "metadata": {"chembl": {"molecule_type": "Small molecule", "max_phase": "4"}},
        },
        {
            "key": "CHEMBL00000",
            "name": "HighlyExoticProbe",
            "canonical_name": "HighlyExoticProbe",
            "canonical_key": "X-EXOTIC",
            "synonyms": [],
            "metadata": {"chembl": {"molecule_type": "Unknown", "max_phase": ""}},
        },
    ]

    filtered = filter_chembl_drug_subset_records(records)
    assert len(filtered) == 1
    assert filtered[0]["key"] == "CHEMBL579"


def test_chembl_schema_inspection_lists_relevant_tables_and_columns(tmp_path):
    db_path = tmp_path / "chembl_37.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE molecule_dictionary (molecule_chembl_id TEXT, pref_name TEXT, standard_inchi_key TEXT, molecule_type TEXT)"
    )
    conn.execute(
        "CREATE TABLE molecule_synonyms (molecule_chembl_id TEXT, synonym TEXT)"
    )
    conn.execute(
        "CREATE TABLE drug_indication (molecule_chembl_id TEXT, efo_term TEXT)"
    )
    conn.execute(
        "INSERT INTO molecule_dictionary VALUES (?, ?, ?, ?)",
        ("CHEMBL579", "Caffeine", "RUVINXRJKPEIMQ-UHFFFAOYSA-N", "Small molecule"),
    )
    conn.execute(
        "INSERT INTO molecule_synonyms VALUES (?, ?)",
        ("CHEMBL579", "cafFeine"),
    )
    conn.execute(
        "INSERT INTO drug_indication VALUES (?, ?)",
        ("CHEMBL579", "Nervous system disease"),
    )
    conn.commit()
    conn.close()

    schema = inspect_chembl_sqlite_schema(str(db_path))
    assert "molecule_dictionary" in schema
    assert "pref_name" in schema["molecule_dictionary"]
    assert "molecule_synonyms" in schema
    assert "drug_indication" in schema


def test_chembl_enrichment_keeps_synonyms_out_of_indications_and_merges_warnings():
    indications = [{
        "Parent Molecule ChEMBL ID": "CHEMBL123",
        "MESH Heading": "Hypertension",
        "EFO Terms": "Cardiovascular disease",
        "Synonyms": "beta-blocker|alpha-blocker",
    }]
    mechanisms = [{
        "Parent Molecule ChEMBL ID": "CHEMBL123",
        "Mechanism of Action": "Binds beta receptors",
        "Target ChEMBL ID": "CHEMBL456",
        "Target Name": "ADRB1",
        "Action Type": "antagonist",
    }]
    targets = [{
        "Target ChEMBL ID": "CHEMBL456",
        "Target Name": "ADRB1",
        "Type": "Receptor",
        "Organism": "Human",
    }]
    warnings = [{
        "Parent Molecule ChEMBL ID": "CHEMBL123",
        "Warning Type": "Black Box Warning",
        "Warning Class": "hematological toxicity",
        "Description": "None",
        "EFO Term": "None",
    }]

    merged = merge_chembl_enrichment(indications, mechanisms, targets, warnings)
    payload = merged["CHEMBL123"]

    assert "Hypertension" in payload["indications"]
    assert "Cardiovascular disease" in payload["indications"]
    assert "beta-blocker" not in payload["indications"]
    assert "alpha-blocker" not in payload["indications"]
    assert any("warning" in warning.lower() or "hematological" in warning.lower() for warning in payload["warnings"])
    assert all("none" not in warning.lower() for warning in payload["warnings"])


def test_chembl_warning_normalization_removes_placeholder_values():
    warnings = [{
        "Parent Molecule ChEMBL ID": "CHEMBL123",
        "Warning Type": "None",
        "Warning Class": "None",
        "Description": "None",
    }]

    merged = merge_chembl_enrichment([], [], [], warnings)
    payload = merged["CHEMBL123"]

    assert payload["warnings"] == []


def test_chembl_enrichment_rows_are_filtered_to_connected_drugs():
    drug_ids = {"CHEMBL579", "CHEMBL123"}
    indications = [
        {"Parent Molecule ChEMBL ID": "CHEMBL579", "MESH Heading": "Hypertension", "EFO Terms": "hypertension"},
        {"Parent Molecule ChEMBL ID": "CHEMBL999", "MESH Heading": "Cancer", "EFO Terms": "oncology"},
    ]
    mechanisms = [
        {"Parent Molecule ChEMBL ID": "CHEMBL579", "Mechanism of Action": "Adenosine receptor antagonist", "Target ChEMBL ID": "CHEMBL233", "Target Name": "Adenosine A1 receptor", "Action Type": "ANTAGONIST"},
        {"Parent Molecule ChEMBL ID": "CHEMBL999", "Mechanism of Action": "Unknown", "Target ChEMBL ID": "CHEMBL555", "Target Name": "Unrelated target", "Action Type": "INHIBITOR"},
    ]
    targets = [
        {"Target ChEMBL ID": "CHEMBL233", "Target Name": "Adenosine A1 receptor", "Type": "SINGLE PROTEIN", "Organism": "Homo sapiens"},
        {"Target ChEMBL ID": "CHEMBL555", "Target Name": "Unrelated target", "Type": "SINGLE PROTEIN", "Organism": "Homo sapiens"},
    ]

    filtered_indications = filter_connected_chembl_indications(indications, drug_ids)
    filtered_mechanisms = filter_connected_chembl_mechanisms(mechanisms, drug_ids)
    merged = merge_chembl_enrichment(filtered_indications, filtered_mechanisms, targets)

    assert len(filtered_indications) == 1
    assert len(filtered_mechanisms) == 1
    assert merged["CHEMBL579"]["indications"] == ["Hypertension"]
    assert merged["CHEMBL579"]["mechanism"] == "Adenosine receptor antagonist"
    assert merged["CHEMBL579"]["receptor_targets"][0]["target"] == "Adenosine A1 receptor"
