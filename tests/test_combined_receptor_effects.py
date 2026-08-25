"""
Tests for multi-compound combined receptor effects and pharmacodynamics convergence.
"""

import pytest
from app.knowledge_graph.graph import BiologicalGraph
from app.knowledge_graph.models import CompoundNode, ReceptorNode, EdgeData, EdgeType
from app.services.graph_service import compute_target_combined_effects
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_agonist_and_antagonist_convergence():
    """Test competitive agonist and antagonist convergence on the same receptor."""
    graph = BiologicalGraph()
    
    # 1. Target Receptor
    graph.add_node(ReceptorNode(
        node_id="alpha2A_receptor",
        label="Alpha-2A Adrenergic Receptor",
        receptor_family="GPCR",
    ))
    
    # 2. Agonist (e.g. Clonidine)
    graph.add_node(CompoundNode(
        node_id="clonidine",
        label="Clonidine",
        smiles="C1=C(C(=CC=C1Cl)NC2=NCCN2)Cl"
    ))
    graph.add_edge(
        source_id="clonidine",
        target_id="alpha2A_receptor",
        edge_type=EdgeType.AGONIZES,
        edge_data=EdgeData(
            affinity_ki=15.0,  # 15 nM Ki
            confidence=0.95
        )
    )
    
    # 3. Antagonist (e.g. Yohimbine)
    graph.add_node(CompoundNode(
        node_id="yohimbine",
        label="Yohimbine",
        smiles="O=C(OC)[C@]1..."
    ))
    graph.add_edge(
        source_id="yohimbine",
        target_id="alpha2A_receptor",
        edge_type=EdgeType.ANTAGONIZES,
        edge_data=EdgeData(
            affinity_ki=5.0,   # 5 nM Ki (higher affinity than clonidine)
            confidence=0.95
        )
    )
    
    combined = compute_target_combined_effects(graph)
    
    assert "alpha2A_receptor" in combined
    res = combined["alpha2A_receptor"]
    
    assert res["has_multiple_ligands"] is True
    assert res["ligand_count"] == 2
    assert res["has_opposing_effects"] is True
    assert len(res["compounds"]) == 2
    
    # Check that occupancies sum to 100%
    total_occ = sum(c["fractional_occupancy_pct"] for c in res["compounds"])
    assert 99.0 <= total_occ <= 101.0
    
    # Yohimbine with Ki=5nM has higher potency than Clonidine with Ki=15nM -> net score should be negative (antagonist dominant)
    assert res["net_activation_score"] < 0
    assert "Blockade" in res["receptor_state"] or "Antagonism" in res["receptor_state"]
    assert "yohimbine" in res["dominant_compound"].lower()
    assert len(res["pharmacological_summary"]) > 20


def test_dual_agonists_synergy():
    """Test two agonists converging on the same receptor."""
    graph = BiologicalGraph()
    
    graph.add_node(ReceptorNode(node_id="gaba_a", label="GABA-A Receptor"))
    graph.add_node(CompoundNode(node_id="gaba", label="GABA"))
    graph.add_node(CompoundNode(node_id="muscimol", label="Muscimol"))
    
    graph.add_edge(source_id="gaba", target_id="gaba_a", edge_type=EdgeType.AGONIZES, edge_data=EdgeData(affinity_ki=20.0))
    graph.add_edge(source_id="muscimol", target_id="gaba_a", edge_type=EdgeType.AGONIZES, edge_data=EdgeData(affinity_ki=10.0))
    
    combined = compute_target_combined_effects(graph)
    
    assert "gaba_a" in combined
    res = combined["gaba_a"]
    assert res["has_multiple_ligands"] is True
    assert res["has_synergistic_effects"] is True
    assert res["has_opposing_effects"] is False
    assert res["net_activation_score"] > 0.8
    assert "Synergistic" in res["receptor_state"] or "Agonism" in res["receptor_state"]


def test_agonist_and_pam_modulation():
    """Test positive allosteric modulator (PAM) enhancing orthosteric agonist."""
    graph = BiologicalGraph()
    
    graph.add_node(ReceptorNode(node_id="gaba_a", label="GABA-A Receptor"))
    graph.add_node(CompoundNode(node_id="gaba", label="GABA"))
    graph.add_node(CompoundNode(node_id="diazepam", label="Diazepam"))
    
    # GABA agonist
    graph.add_edge(source_id="gaba", target_id="gaba_a", edge_type=EdgeType.AGONIZES, edge_data=EdgeData(affinity_ki=50.0))
    # Diazepam PAM
    graph.add_edge(source_id="diazepam", target_id="gaba_a", edge_type=EdgeType.POSITIVE_ALLOSTERIC_MODULATOR, edge_data=EdgeData(affinity_ki=15.0))
    
    combined = compute_target_combined_effects(graph)
    res = combined["gaba_a"]
    
    assert res["has_multiple_ligands"] is True
    assert any(c["is_pam"] for c in res["compounds"])
    assert res["net_activation_score"] > 0.35


def test_graph_data_endpoint_includes_combined_effects():
    """Test that /graph-data endpoint returns combined_effects and node metadata."""
    response = client.get("/graph-data?stack=caffeine&stack=theanine")
    assert response.status_code == 200
    data = response.json()
    
    assert "nodes" in data
    assert "edges" in data
    assert "combined_effects" in data
    assert isinstance(data["combined_effects"], dict)
    
    # Check node structure
    for node in data["nodes"]:
        assert "id" in node
        assert "node_type" in node
        if node.get("has_multiple_ligands"):
            assert "combined_effect" in node
            assert node["combined_effect"]["ligand_count"] >= 2


def test_clenbuterol_and_nebivolol_adrb2_and_adrb1_convergence():
    """Test Clenbuterol (40 mcg selective beta-2 agonist) + Nebivolol (5 mg selective beta-1 blocker)."""
    response = client.get("/graph-data?stack=clenbuterol&stack=nebivolol")
    assert response.status_code == 200
    data = response.json()
    
    combined = data.get("combined_effects", {})
    assert "Beta-1 Adrenergic Receptor (ADRB1)" in combined
    
    adrb1 = combined["Beta-1 Adrenergic Receptor (ADRB1)"]
    assert adrb1["has_multiple_ligands"] is True
    assert adrb1["has_opposing_effects"] is True
    assert str(adrb1["dominant_compound"]).upper() == "CLENBUTEROL"
    # Clenbuterol commands >90% bound occupancy share and positive net activation
    assert adrb1["net_activation_score"] > 0.30
    assert adrb1["net_activation_pct"] > 30.0
    assert adrb1["receptor_saturation_pct"] > 50.0
    
    clen_comp = next((c for c in adrb1["compounds"] if "CLENBUTEROL" in str(c["compound_label"]).upper()), None)
    nebi_comp = next((c for c in adrb1["compounds"] if "NEBIVOLOL" in str(c["compound_label"]).upper()), None)
    assert clen_comp is not None
    assert clen_comp["fractional_occupancy_pct"] >= 80.0
    assert clen_comp["is_agonist"] is True
    assert clen_comp["is_antagonist"] is False
    assert nebi_comp is not None
    assert nebi_comp["is_antagonist"] is True
    assert nebi_comp["is_agonist"] is False
    assert clen_comp["dose_display"] == "40 μg"
    assert nebi_comp["dose_display"] == "5 mg"


def test_dose_dependent_receptor_saturation_scaling():
    """Verify that dose-dependent receptor saturation and functional effect scale biophysically."""
    res_1mg = client.get("/graph-data?stack=nebivolol:1mg").json().get("combined_effects", {})
    res_5mg = client.get("/graph-data?stack=nebivolol:5mg").json().get("combined_effects", {})
    res_20mg = client.get("/graph-data?stack=nebivolol:20mg").json().get("combined_effects", {})
    
    adrb1_1mg = res_1mg.get("Beta-1 Adrenergic Receptor (ADRB1)")
    adrb1_5mg = res_5mg.get("Beta-1 Adrenergic Receptor (ADRB1)")
    adrb1_20mg = res_20mg.get("Beta-1 Adrenergic Receptor (ADRB1)")
    
    assert adrb1_1mg is not None and adrb1_5mg is not None and adrb1_20mg is not None
    
    # Receptor saturation monotonically increases with dose
    assert 0.5 <= adrb1_1mg["receptor_saturation_pct"] < adrb1_5mg["receptor_saturation_pct"]
    assert adrb1_5mg["receptor_saturation_pct"] < adrb1_20mg["receptor_saturation_pct"]
    assert adrb1_1mg["unoccupied_reserve_pct"] > 80.0



def test_high_clenbuterol_and_low_nebivolol_increases_heart_rate_and_blood_pressure():
    """Verify 60 mcg clenbuterol (high agonist) + 1 mg nebivolol (low blocker) causes HR and BP increase."""
    res = client.get("/graph-data?stack=clenbuterol:60ug,nebivolol:1mg").json()
    shifts = res.get("cascade_simulation", {}).get("biomarker_shifts", [])
    
    hr = next((b for b in shifts if b["biomarker_id"] == "bio_heart_rate"), None)
    bp = next((b for b in shifts if b["biomarker_id"] == "bio_blood_pressure"), None)
    
    assert hr is not None
    assert hr["direction"] == "INCREASE"
    assert hr["net_shift"] > 0.05
    
    assert bp is not None
    assert bp["direction"] == "INCREASE"
    assert bp["net_shift"] > 0.05


def test_testosterone_and_telmisartan_blood_pressure_attenuation():
    """Verify telmisartan 80mg significantly attenuates testosterone 70mg hypertensive RAAS cascade."""
    res_testo_only = client.get("/graph-data?stack=testosterone:70mg").json()
    res_stacked = client.get("/graph-data?stack=testosterone:70mg,telmisartan:80mg").json()
    
    shifts_testo = res_testo_only.get("cascade_simulation", {}).get("biomarker_shifts", [])
    shifts_stacked = res_stacked.get("cascade_simulation", {}).get("biomarker_shifts", [])
    
    bp_testo = next((b for b in shifts_testo if b["biomarker_id"] == "bio_blood_pressure"), None)
    bp_stacked = next((b for b in shifts_stacked if b["biomarker_id"] == "bio_blood_pressure"), None)
    
    assert bp_testo is not None
    assert bp_stacked is not None
    
    # Stacking telmisartan 80mg must significantly reduce the net blood pressure shift compared to testosterone alone
    assert bp_stacked["estimated_delta"] < bp_testo["estimated_delta"]
    assert bp_stacked["estimated_value"] < bp_testo["estimated_value"]
    # Net delta must be bounded and not exhibit erroneous unbounded multi-path explosion (+49+ mmHg)
    assert bp_stacked["estimated_delta"] < 25.0



