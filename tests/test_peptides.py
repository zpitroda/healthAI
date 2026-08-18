import pytest
from app.services.catalog_service import CatalogService
from app.services.graph_service import (
    build_selected_compound_graph,
    get_exact_target_cascade_blueprint,
    EXACT_CASCADE_LOOKUP,
    TARGET_LOOKUP_INDEX,
)
from app.services.interaction_engine import InteractionEngine


def test_bpc157_and_tb500_peptide_canonical_resolution():
    catalog = CatalogService()
    bpc = catalog.get_compound("bpc_157")
    bpc_syn = catalog.get_compound("bpc157")
    tb500 = catalog.get_compound("tb_500")
    tb_syn = catalog.get_compound("thymosinbeta4")

    assert bpc is not None, "bpc_157 must be in catalog"
    assert bpc_syn is not None, "bpc157 synonym must resolve"
    assert bpc["key"] == "bpc_157"
    assert bpc_syn["key"] == "bpc_157"

    assert tb500 is not None, "tb_500 must be in catalog"
    assert tb_syn is not None, "thymosinbeta4 synonym must resolve"
    assert tb500["key"] == "tb_500"
    assert tb_syn["key"] == "tb_500"


def test_research_peptide_evidence_tier_and_regulatory_status():
    catalog = CatalogService()
    bpc = catalog.get_compound("bpc_157")
    sema = catalog.get_compound("semaglutide")
    retatrutide = catalog.get_compound("retatrutide")

    assert bpc is not None
    assert bpc.get("metadata", {}).get("evidence_tier") == "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION"
    assert bpc.get("metadata", {}).get("regulatory_status") == "RESEARCH_CHEMICAL"
    assert bpc.get("metadata", {}).get("human_clinical_trials") is False

    assert sema is not None
    assert sema.get("metadata", {}).get("evidence_tier") == "FDA_APPROVED_CLINICAL_DATA"
    assert sema.get("metadata", {}).get("regulatory_status") == "APPROVED_RX"
    assert sema.get("metadata", {}).get("human_clinical_trials") is True

    assert retatrutide is not None
    assert retatrutide.get("metadata", {}).get("evidence_tier") == "IN_VITRO_AND_ALLOMETRIC_EXTRAPOLATION"
    assert retatrutide.get("metadata", {}).get("human_clinical_trials") is True


def test_peptide_exact_target_cascade_blueprints():
    # 1. Growth Hormone Secretagogue Receptor (GHSR)
    ghsr_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="Q92847")
    assert ghsr_bp is not None, "GHSR UniProt Q92847 must resolve to target cascade"
    assert ghsr_bp["pathway"]["id"] in {"pathway_ghsr_signaling", "R-HSA-375276"} or ghsr_bp["pathway"]["id"].startswith("R-HSA-")

    # 2. GHRH Receptor (GHRHR)
    ghrhr_bp = get_exact_target_cascade_blueprint(target_name="unknown", gene_symbol="GHRHR")
    assert ghrhr_bp is not None
    assert "Growth Hormone-Releasing Hormone Receptor" in ghrhr_bp["target_name"]

    # 3. GLP-1 Receptor (GLP1R)
    glp1r_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="P43220")
    assert glp1r_bp is not None
    assert "Glucagon-Like Peptide 1 Receptor" in glp1r_bp["target_name"]

    # 4. GIP Receptor (GIPR)
    gipr_bp = get_exact_target_cascade_blueprint(target_name="unknown", gene_symbol="GIPR")
    assert gipr_bp is not None
    assert "Gastric Inhibitory Polypeptide Receptor" in gipr_bp["target_name"]

    # 5. VEGFR2 / KDR (BPC-157 Target)
    kdr_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="P35968")
    assert kdr_bp is not None
    assert "Vascular Endothelial Growth Factor Receptor 2" in kdr_bp["target_name"]

    # 6. Oxytocin Receptor (OXTR)
    oxtr_bp = get_exact_target_cascade_blueprint(target_name="unknown", gene_symbol="OXTR")
    assert oxtr_bp is not None
    assert "Oxytocin Receptor" in oxtr_bp["target_name"]

    # 7. Vasopressin V2 Receptor (AVPR2)
    avpr2_bp = get_exact_target_cascade_blueprint(target_name="unknown", uniprot_id="P30518")
    assert avpr2_bp is not None
    assert "Vasopressin V2 Receptor" in avpr2_bp["target_name"]


def test_bpc157_and_tb500_stack_graph_generation():
    graph = build_selected_compound_graph(["bpc_157:500ug", "tb_500:2.5mg"])
    assert graph is not None

    bpc_node = graph.get_node("bpc_157")
    assert bpc_node is not None, "BPC-157 compound node should exist in graph"

    tb_node = graph.get_node("tb_500")
    assert tb_node is not None, "TB-500 compound node should exist in graph"


def test_ipamorelin_and_cjc1295_stack_synergy_and_gh_cascade():
    engine = InteractionEngine()
    stack = [
        {"key": "ipamorelin", "dose": 200, "unit": "mcg"},
        {"key": "cjc_1295", "dose": 100, "unit": "mcg"},
    ]

    analysis = engine.analyze_stack(stack)
    assert analysis is not None

    # Graph building test
    graph = build_selected_compound_graph(["ipamorelin:200ug", "cjc_1295:100ug"])
    assert graph.get_node("ipamorelin") is not None
    assert graph.get_node("cjc_1295") is not None
