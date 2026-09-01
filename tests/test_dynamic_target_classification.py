import pytest
from app.services.live_enrichment import infer_target_classification
from app.services.catalog_service import CatalogService
from app.services.graph_service import build_selected_compound_graph


class TestDynamicTargetClassification:
    def test_infer_target_classification_enzymes(self):
        t_class, norm_act = infer_target_classification(
            target_name="Carnosine Synthase 1 (CARNS1)",
            action="substrate",
        )
        assert t_class == "Enzyme"
        assert norm_act == "substrate"

        t_class, norm_act = infer_target_classification(
            target_name="Creatine Kinase M-Type (CKM)",
            action="substrate",
        )
        assert t_class == "Enzyme"
        assert norm_act == "substrate"

        t_class, norm_act = infer_target_classification(
            target_name="Aromatase (CYP19A1)",
            action="inhibitor",
        )
        assert t_class == "Enzyme"
        assert norm_act == "inhibitor"

    def test_infer_target_classification_transporters(self):
        t_class, norm_act = infer_target_classification(
            target_name="Sodium- and chloride-dependent creatine transporter 1 (SLC6A8)",
            action="substrate",
        )
        assert t_class == "Transporter"
        assert norm_act == "substrate"

        t_class, norm_act = infer_target_classification(
            target_name="Dopamine Transporter (DAT / SLC6A3)",
            action="inhibitor",
        )
        assert t_class == "Transporter"
        assert norm_act == "inhibitor"

    def test_infer_target_classification_receptors(self):
        t_class, norm_act = infer_target_classification(
            target_name="Mas-Related G-Protein Coupled Receptor Member D (MRGPRD)",
            action="agonist",
            protein_class="GPCR / Sensory",
        )
        assert t_class == "Receptor"
        assert norm_act == "agonist"

        t_class, norm_act = infer_target_classification(
            target_name="Androgen Receptor (AR)",
            action="agonist",
        )
        assert t_class == "Receptor"
        assert norm_act == "agonist"

    def test_infer_target_classification_ion_channels(self):
        t_class, norm_act = infer_target_classification(
            target_name="Glutamate Ionotropic Receptor AMPA Type Subunit 1 (GRIA1)",
            action="pam",
            protein_class="Ion Channel",
        )
        assert t_class == "Ion Channel"
        assert norm_act == "pam"

    def test_catalog_creatine_target_structure(self):
        catalog = CatalogService()
        creatine = catalog.get_compound("creatine", auto_enrich=False)
        assert creatine is not None
        targets = creatine.get("receptor_targets") or []
        assert len(targets) > 0
        first_t = targets[0]
        assert first_t.get("action") == "substrate"
        assert first_t.get("target_class") == "Enzyme"

    def test_graph_node_instantiation_for_beta_alanine_and_creatine(self):
        catalog = CatalogService()
        
        # Test Beta-Alanine graph generation
        ba_graph = build_selected_compound_graph(
            stack=[{"name": "Beta-Alanine", "dose": 3200.0, "unit": "mg"}],
            catalog_service=catalog,
        )
        nodes = ba_graph.graph.nodes
        
        # Should have Carnosine Synthase 1 as EnzymeNode
        carns_nodes = [nid for nid, data in nodes.items() if "carns1" in nid.lower() or "carnosine synthase" in str(data.get("label", "")).lower()]
        assert len(carns_nodes) > 0, f"Expected CARNS1 node in {list(nodes.keys())}"
        carns_data = nodes[carns_nodes[0]]
        assert carns_data.get("node_type") == "enzyme"

        # Should have MRGPRD as ReceptorNode
        mrgprd_nodes = [nid for nid, data in nodes.items() if "mrgprd" in nid.lower() or "mas-related" in str(data.get("label", "")).lower()]
        assert len(mrgprd_nodes) > 0, f"Expected MRGPRD node in {list(nodes.keys())}"
        mrgprd_data = nodes[mrgprd_nodes[0]]
        assert mrgprd_data.get("node_type") == "receptor"
