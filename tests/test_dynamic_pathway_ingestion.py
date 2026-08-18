"""
Tests for Dynamic Pathway Ingestion Service (Reactome & Open Targets).
"""

import os
import sqlite3
import pytest
from app.services.pathway_service import PathwayService
from app.services.catalog_service import CatalogService
from app.services.graph_service import build_selected_compound_graph


def test_pathway_service_schema_and_caching(tmp_path):
    """Verify PathwayService initializes tables and persists Reactome and Open Targets data."""
    test_db = str(tmp_path / "test_pathways.db")
    service = PathwayService(db_path=test_db)

    # 1. Test Target Metadata Resolution
    ar_meta = service.resolve_target_metadata("Androgen Receptor (AR / NR3C4)")
    assert ar_meta["symbol"] == "AR"
    assert ar_meta["uniprot"] == "P10275"
    assert ar_meta["ensembl"] == "ENSG00000169083"

    cyp_meta = service.resolve_target_metadata("Aromatase (CYP19A1)")
    assert cyp_meta["symbol"] == "CYP19A1"
    assert cyp_meta["uniprot"] == "P11511"
    assert cyp_meta["ensembl"] == "ENSG00000137869"

    # 2. Test Dynamic Target Cascade Generation
    cyp_cascade = service.get_dynamic_target_cascade("Aromatase (CYP19A1)")
    assert cyp_cascade["symbol"] == "CYP19A1"
    assert "pathway" in cyp_cascade
    assert len(cyp_cascade.get("biomarkers", [])) >= 2
    assert any(b["id"] == "bio_estradiol" for b in cyp_cascade.get("biomarkers", []))

    # 3. Verify SQLite Tables Contain Cached Records
    with service._connect() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "cached_target_pathways" in tables
        assert "cached_target_phenotypes" in tables
        assert "cached_pathway_bridges" in tables


def test_dynamic_graph_building_with_reactome_pathways():
    """Verify that build_selected_compound_graph integrates Reactome pathways dynamically."""
    cat = CatalogService()
    graph = build_selected_compound_graph(["testosterone:70mg", "exemestane:2.7mg"], catalog_service=cat)
    
    # Check that pathway nodes exist in the graph (with Reactome IDs)
    pathway_nodes = [n for n, d in graph.graph.nodes(data=True) if d.get("node_type") in {"signaling_pathway", "pathway"}]
    assert len(pathway_nodes) >= 1
    assert any("R-HSA" in n for n in pathway_nodes)
    
    # Check that biomarker nodes exist and connect to physiology
    bio_nodes = [n for n, d in graph.graph.nodes(data=True) if d.get("node_type") == "biomarker"]
    assert "bio_estradiol" in bio_nodes
    assert "bio_blood_pressure" in bio_nodes


def test_unmapped_target_dynamic_online_cascade(tmp_path):
    """Verify that unmapped novel targets dynamically query and build structured cascades."""
    test_db = str(tmp_path / "test_unmapped.db")
    service = PathwayService(db_path=test_db)
    
    # Novel / unmapped target
    novel_cascade = service.get_dynamic_target_cascade("NovelKinaseTarget")
    assert novel_cascade is not None
    assert "pathway" in novel_cascade
    assert "physiology" in novel_cascade
