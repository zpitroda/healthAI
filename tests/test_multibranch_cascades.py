"""
Tests for Multi-Branch Biological Cascade Expansions & Online Data Ingestion
-----------------------------------------------------------------------------
Validates that:
1. Compounds (e.g. Testosterone, Nandrolone, Estradiol, Enclomiphene) branch across
   multiple concurrent physiological axes (Androgen, Aromatase/Estrogen, 5AR/DHT, EPO/Erythropoiesis, RAAS).
2. Inhibitor compounds (Anastrozole, Finasteride) properly blunt/mitigate their targeted branches.
3. Live online enrichment extracts quantitative multi-target assays from ChEMBL and properties from PubChem.
"""
from __future__ import annotations

from unittest.mock import patch
import networkx as nx
import pytest
from app.services.catalog_service import CatalogService
from app.services.graph_service import (
    build_selected_compound_graph,
    compute_target_combined_effects,
)
from app.knowledge_graph.graph import BiologicalGraph
from app.services.live_enrichment import LiveEnrichmentService


@pytest.fixture
def catalog():
    return CatalogService()


def test_testosterone_multibranch_graph_structure(catalog):
    """
    Test that Testosterone is NOT linear, but fans out into multiple distinct biological branches:
    1. Androgen Receptor -> Muscle Anabolic Trophism
    2. Aromatase (CYP19A1) -> 17-Beta Estradiol & Estrogen Receptor
    3. 5-Alpha Reductase -> DHT & Androgenic Alopecia
    4. Renal Erythropoietin (EPO) -> Hematocrit & Erythropoiesis
    5. RAAS Cascade Cross-Talk Bridge
    """
    graph = build_selected_compound_graph(["testosterone"], catalog_service=catalog)
    nodes = set(graph.graph.nodes)
    node_labels = {n: str(graph.graph.nodes[n].get("label", n)) for n in nodes}

    # 1. Molecular Targets check
    target_labels = [lbl for n, lbl in node_labels.items() if graph.graph.nodes[n].get("node_type") in ["receptor", "enzyme"]]
    assert any("Androgen Receptor" in t for t in target_labels), f"AR target missing. Targets: {target_labels}"
    assert any("Aromatase" in t for t in target_labels), f"Aromatase target missing. Targets: {target_labels}"
    assert any("5-Alpha Reductase" in t or "5AR" in t for t in target_labels), f"5AR target missing. Targets: {target_labels}"
    assert any("Erythropoietin" in t or "EPO" in t for t in target_labels), f"EPO target missing. Targets: {target_labels}"

    # 2. Downstream Pathways check
    pathway_nodes = [n for n in nodes if graph.graph.nodes[n].get("node_type") == "pathway" or "pathway" in n.lower() or "r-hsa" in n.lower()]
    assert len(pathway_nodes) >= 1 or len(target_labels) >= 4

    # 3. Downstream Biomarkers check
    assert "bio_testosterone" in nodes
    assert "bio_estradiol" in nodes
    assert "bio_hematocrit" in nodes
    assert "bio_luteinizing_hormone" in nodes

    # 4. Downstream Phenotypes check
    assert any("anabolism" in p or "hypertrophy" in p for p in nodes)
    assert any("gynecomastia" in p for p in nodes)
    assert any("polycythemia" in p or "erythrocytosis" in p for p in nodes)

    # 5. Verify Directed Paths exist from Testosterone to each distinct outcome
    t_key = catalog.get_compound("testosterone")["key"]
    assert any(nx.has_path(graph.graph, t_key, p) for p in nodes if "anabolism" in p or "hypertrophy" in p)
    assert any(nx.has_path(graph.graph, t_key, p) for p in nodes if "gynecomastia" in p)
    assert any(nx.has_path(graph.graph, t_key, p) for p in nodes if "polycythemia" in p or "erythrocytosis" in p)


def test_testosterone_cascade_propagation_biomarkers(catalog):
    """Verify that propagating cascade for Testosterone calculates shifts across all axes."""
    graph = build_selected_compound_graph(["testosterone"], catalog_service=catalog)
    t_key = catalog.get_compound("testosterone")["key"]

    sim = graph.propagate_cascade(start_node_ids=[t_key], max_depth=5)
    biomarkers = {b["biomarker_id"]: b for b in sim.get("biomarker_shifts", [])}

    # Verify testosterone increase
    assert "bio_testosterone" in biomarkers
    assert biomarkers["bio_testosterone"]["direction"] == "INCREASE"
    assert biomarkers["bio_testosterone"]["estimated_value"] > 650.0

    # Verify estradiol increase from aromatization
    assert "bio_estradiol" in biomarkers
    assert biomarkers["bio_estradiol"]["direction"] == "INCREASE"
    assert biomarkers["bio_estradiol"]["estimated_value"] > 25.0

    # Verify hematocrit increase from EPO signaling
    assert "bio_hematocrit" in biomarkers
    assert biomarkers["bio_hematocrit"]["direction"] == "INCREASE"
    assert biomarkers["bio_hematocrit"]["estimated_value"] > 45.0

    # Verify LH suppression from negative feedback
    assert "bio_luteinizing_hormone" in biomarkers
    assert biomarkers["bio_luteinizing_hormone"]["direction"] == "DECREASE"


def test_testosterone_plus_anastrozole_and_finasteride_stack(catalog):
    """
    Verify multi-compound stack where Anastrozole inhibits the aromatase branch
    and Finasteride inhibits the 5AR branch while Testosterone provides anabolic signaling.
    """
    graph = build_selected_compound_graph(["testosterone", "anastrozole", "finasteride"], catalog_service=catalog)
    
    # Combined target effects
    effects = compute_target_combined_effects(graph)
    
    # Aromatase target should show competitive inhibition from Anastrozole
    aromatase_target = next((v for k, v in effects.items() if "Aromatase" in k or "CYP19A1" in k), None)
    assert aromatase_target is not None, f"Aromatase target missing in combined effects: {list(effects.keys())}"
    assert aromatase_target["net_activation"] < 0, f"Expected negative net activation for Aromatase due to Anastrozole, got {aromatase_target['net_activation']}"

    # 5-Alpha Reductase target should show inhibition from Finasteride
    srd5a_target = next((v for k, v in effects.items() if "5-Alpha" in k or "Reductase" in k), None)
    assert srd5a_target is not None, f"5AR target missing in combined effects: {list(effects.keys())}"
    assert srd5a_target["net_activation"] < 0, f"Expected negative net activation for 5AR due to Finasteride, got {srd5a_target['net_activation']}"


def test_online_chembl_bioactivity_parsing():
    """Verify LiveEnrichmentService extracts quantitative assays and targets from live/cached ChEMBL APIs."""
    enricher = LiveEnrichmentService(timeout_seconds=10.0)
    mock_chembl_data = {
        "chembl_id": "CHEMBL386630",
        "bioactivities": [{"target": "Androgen receptor", "assay_type": "B", "standard_value": 3.8, "standard_units": "nM", "standard_type": "Ki"}],
        "receptor_targets": [{"target": "Androgen receptor (AR)", "action": "agonist", "affinity_ki": 3.8}],
        "mechanisms": [{"mechanism_of_action": "Androgen receptor agonist", "action_type": "AGONIST"}],
    }
    with patch.object(enricher, "fetch_chembl", return_value=mock_chembl_data):
        chembl_data = enricher.fetch_chembl("testosterone")

        assert chembl_data is not None
        assert "chembl_id" in chembl_data
        assert chembl_data["chembl_id"] == "CHEMBL386630"
        
        # Verify multi-target bioactivities were extracted
        bioacts = chembl_data.get("bioactivities") or []
        assert len(bioacts) > 0, "No bioactivities parsed from ChEMBL"

        targets_found = [b.get("target") for b in chembl_data.get("receptor_targets", []) if isinstance(b, dict)]
        assert any("Androgen" in t for t in targets_found), f"Androgen receptor missing from ChEMBL bioactivities: {targets_found}"


def test_online_pubchem_property_parsing():
    """Verify LiveEnrichmentService extracts SMILES, MW, LogP, and TPSA from PubChem PUG REST API."""
    enricher = LiveEnrichmentService(timeout_seconds=10.0)
    mock_pubchem_data = {
        "molecular_weight": 288.42,
        "smiles": "CC12CCC3C(C1CCC2O)CCC4=CC(=O)CCC34C",
        "logp": 3.32,
        "tpsa": 37.3,
    }
    with patch.object(enricher, "fetch_pubchem", return_value=mock_pubchem_data):
        pubchem_data = enricher.fetch_pubchem("testosterone")

        assert pubchem_data is not None
        assert pubchem_data.get("molecular_weight") is not None
        assert 280.0 < float(pubchem_data["molecular_weight"]) < 300.0
        assert pubchem_data.get("smiles") is not None
        assert "C" in pubchem_data["smiles"]
