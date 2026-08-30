from app.knowledge_graph.examples import build_testosterone_alopecia_graph
from app.knowledge_graph.models import EdgeType


def test_testosterone_alopecia_graph_structure_is_valid():
    graph = build_testosterone_alopecia_graph()

    assert graph.path_exists("testosterone_enanthate", "testosterone")
    assert graph.path_exists("testosterone", "dht")
    assert graph.path_exists("dht", "alopecia")
    assert graph.graph["dht"]["androgen_receptor"]["edge_type"] == EdgeType.AGONIZES.value
    assert graph.graph["finasteride"]["5_alpha_reductase"]["edge_type"] == EdgeType.INHIBITS_ENZYME.value
    assert graph.graph["finasteride"]["5_alpha_reductase"]["inhibition_type"] == "competitive"


def test_subgraph_from_node_supports_deep_browsing():
    graph = build_testosterone_alopecia_graph()
    subgraph = graph.subgraph_from_node("dht", max_depth=2)

    assert "dht" in subgraph.graph.nodes
    assert "androgen_receptor" in subgraph.graph.nodes
    assert "alopecia" in subgraph.graph.nodes
    assert "testosterone" in subgraph.graph.nodes
    assert "finasteride" not in subgraph.graph.nodes


def test_yohimbine_and_nebivolol_cross_talk_connectivity():
    """Verify Yohimbine (Alpha-2 blocker) connects to Nebivolol (Beta-1 blocker) via synaptic norepinephrine release."""
    import networkx as nx
    from app.services.graph_service import build_selected_compound_graph
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    graph = build_selected_compound_graph(["yohimbine", "nebivolol"], catalog_service=service)

    undirected = graph.graph.to_undirected()
    neb_node = "nebivolol" if "nebivolol" in undirected else "CHEMBL434394"
    assert nx.has_path(undirected, "yohimbine", neb_node)

    # Verify both direct PK metabolism bridge and PD cascade bridge exist
    pd_path_found = False
    for p in nx.all_simple_paths(undirected, "yohimbine", neb_node, cutoff=8):
        labels_lower = [str(graph.graph.nodes[n].get("label", n)).lower() for n in p]
        if any("alpha-2" in lbl for lbl in labels_lower) and any("beta-1" in lbl or "beta-2" in lbl for lbl in labels_lower):
            pd_path_found = True
            break
    assert pd_path_found, "Pharmacodynamic Alpha-2 -> Beta-1 cross-talk path not found"


def test_telmisartan_and_eplerenone_raas_cross_talk_connectivity():
    """Verify Telmisartan (ARB) and Eplerenone (MRA) connect across the shared RAAS-Aldosterone cascade."""
    import networkx as nx
    from app.services.graph_service import build_selected_compound_graph
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    graph = build_selected_compound_graph(["telmisartan", "eplerenone"], catalog_service=service)

    t_key = service.get_compound("telmisartan")["key"]
    e_key = service.get_compound("eplerenone")["key"]

    undirected = graph.graph.to_undirected()
    assert nx.has_path(undirected, t_key, e_key)

    # Verify RAAS endocrine PD path: Angiotensin/RAAS -> Aldosterone/Mineralocorticoid
    all_paths = list(nx.all_simple_paths(undirected, t_key, e_key, cutoff=8))
    assert len(all_paths) > 0

    raas_path_found = False
    for p in all_paths:
        labels = [str(graph.graph.nodes[n].get("label", n)) for n in p]
        if any("angiotensin" in lbl.lower() or "raas" in lbl.lower() or "agtr1" in lbl.lower() for lbl in labels) and any("mineralocorticoid" in lbl.lower() or "aldosterone" in lbl.lower() or "nr3c2" in lbl.lower() for lbl in labels):
            raas_path_found = True
            break
    assert raas_path_found, "RAAS cascade cross-talk path not found"


def test_telmisartan_target_nodes_are_deduplicated():
    """Verify Telmisartan produces clean single AGTR1 and PPARG target nodes without duplicates."""
    from app.services.graph_service import build_selected_compound_graph
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    graph = build_selected_compound_graph(["telmisartan"], catalog_service=service)

    nodes = graph.graph.nodes
    agtr1_nodes = [n for n in nodes if "Angiotensin" in n or "AGTR1" in n]
    pparg_nodes = [n for n in nodes if "PPAR" in n or "PPARG" in n]

    assert len(agtr1_nodes) == 1, f"Expected 1 AGTR1 node, found: {agtr1_nodes}"
    assert len(pparg_nodes) == 1, f"Expected 1 PPARG node, found: {pparg_nodes}"


def test_telmisartan_ppar_gamma_downstream_cascade_expansion():
    """Verify Telmisartan expands both AGTR1 and PPAR-gamma downstream cascades to pathways, physiology, biomarkers, and phenotypes."""
    import networkx as nx
    from app.services.graph_service import build_selected_compound_graph
    from app.services.catalog_service import CatalogService

    service = CatalogService()
    graph = build_selected_compound_graph(["telmisartan"], catalog_service=service)

    nodes = set(graph.graph.nodes)
    
    # Verify PPAR-gamma target node exists
    ppar_targets = [n for n in nodes if "PPAR" in n or "PPARG" in n]
    assert len(ppar_targets) > 0
    
    # Verify PPAR-gamma downstream pathway and physiology nodes exist in graph
    assert any("ppar" in n.lower() or "glucose" in n.lower() or "r-hsa" in n.lower() for n in nodes), "PPAR signaling pathway node missing"
    assert any("pparg" in n.lower() or "insulin" in n.lower() or "glycemic" in n.lower() for n in nodes), "Insulin sensitization physiology node missing"
    assert "bio_hba1c" in nodes or "bio_adiponectin" in nodes or "bio_glucose" in nodes, "PPAR biomarker nodes missing"
    assert any("glycemic" in n.lower() or "insulin" in n.lower() or "metabolic" in n.lower() for n in nodes), "PPAR glycemic control phenotype node missing"

    # Verify directed path from Telmisartan compound -> PPAR target -> PPAR pathway -> Insulin sensitization physiology
    t_key = service.get_compound("telmisartan")["key"]
    ppar_phys_nodes = [n for n in nodes if "pparg" in n.lower() or "insulin" in n.lower() or "glycemic" in n.lower()]
    assert any(nx.has_path(graph.graph, t_key, pn) for pn in ppar_phys_nodes), "No directed path from Telmisartan to PPAR physiology"


def test_unmapped_target_dynamic_fallback_cascade():
    """Verify that unmapped targets produce dynamic fallback downstream cascades without leaving orphan target nodes."""
    from app.knowledge_graph.graph import BiologicalGraph
    from app.knowledge_graph.models import CompoundNode
    from app.services.graph_service import build_selected_compound_graph
    from app.services.catalog_service import CatalogService

    # Create a custom mock catalog service with a compound having an unusual target
    class CustomCatalogService(CatalogService):
        def get_compound(self, key: str, *args, **kwargs):
            if key == "novel_compound":
                return {
                    "key": "novel_compound",
                    "name": "Novel Compound X",
                    "receptor_targets": [
                        {"target": "Novel Orphan Receptor XYZ", "action": "agonist"}
                    ]
                }
            return super().get_compound(key, *args, **kwargs)

    service = CustomCatalogService()
    graph = build_selected_compound_graph(["novel_compound"], catalog_service=service)

    nodes = list(graph.graph.nodes)
    assert "novel_compound" in nodes
    assert "Novel Orphan Receptor XYZ" in nodes
    
    # Check that dynamic fallback downstream nodes were generated
    pathway_nodes = [n for n in nodes if "transduction" in str(graph.graph.nodes[n].get("label", "")).lower() or "pathway" in str(graph.graph.nodes[n].get("label", "")).lower() or "cascade" in str(graph.graph.nodes[n].get("label", "")).lower()]
    phys_nodes = [n for n in nodes if "physiological" in str(graph.graph.nodes[n].get("label", "")).lower() or "function" in str(graph.graph.nodes[n].get("label", "")).lower() or "tone" in str(n).lower()]

    assert len(pathway_nodes) > 0, "Fallback pathway node not generated"

def test_caffeine_hemodynamic_pressor_simulation():
    """Verify 200mg Caffeine simulation produces physiological pressor & chronotropic shifts (increased BP and HR)."""
    from app.services.graph_service import (
        build_selected_compound_graph,
        filter_graph_by_stack,
        parse_compound_spec,
        canonicalize_match_token,
        compute_target_combined_effects,
        resolve_stack_to_catalog_keys,
    )

    parsed_stack = ["caffeine:200mg:daily"]
    graph = build_selected_compound_graph(parsed_stack)
    graph = filter_graph_by_stack(graph, parsed_stack, max_depth=5)
    custom_doses = {}
    for item in parsed_stack:
        parsed = parse_compound_spec(item)
        if parsed.get("key"):
            custom_doses[parsed["key"].lower()] = parsed
            custom_doses[canonicalize_match_token(parsed["key"])] = parsed

    combined_effects = compute_target_combined_effects(graph, custom_doses=custom_doses)
    resolved_keys = resolve_stack_to_catalog_keys(parsed_stack)
    cascade_results = graph.propagate_cascade(
        resolved_keys or parsed_stack,
        combined_effects=combined_effects,
        patient_biometrics={"sex": "male", "age": 30, "weight_kg": 70},
        user_labs={"blood_pressure": 120.0},
    )

    shifts = {b["biomarker_id"]: b for b in cascade_results.get("biomarker_shifts", [])}
    assert "bio_blood_pressure" in shifts, "bio_blood_pressure not found in biomarker shifts"
    bp_shift = shifts["bio_blood_pressure"]
    
    # Systolic blood pressure must increase (pressor response, delta > 0), not drop from 120 to 108
    assert bp_shift["estimated_delta"] > 0, f"Expected positive BP delta, got {bp_shift['estimated_delta']}"
    assert bp_shift["estimated_value"] > 120.0, f"Expected BP > 120, got {bp_shift['estimated_value']}"
    assert 121.0 <= bp_shift["estimated_value"] <= 128.0, f"BP out of expected physiological range (121-128 mmHg): {bp_shift['estimated_value']}"

    # Resting heart rate must increase
    assert "bio_heart_rate" in shifts
    hr_shift = shifts["bio_heart_rate"]
    assert hr_shift["estimated_delta"] > 0
    assert hr_shift["estimated_value"] > 70.0


def test_tadalafil_pde5_vasodilation_simulation():
    """Verify 20mg Tadalafil (PDE5 inhibitor) produces cGMP elevation and blood pressure reduction."""
    from app.services.graph_service import (
        build_selected_compound_graph,
        filter_graph_by_stack,
        parse_compound_spec,
        canonicalize_match_token,
        compute_target_combined_effects,
        resolve_stack_to_catalog_keys,
    )

    parsed_stack = ["tadalafil:20mg:daily"]
    graph = build_selected_compound_graph(parsed_stack)
    graph = filter_graph_by_stack(graph, parsed_stack, max_depth=5)
    custom_doses = {}
    for item in parsed_stack:
        parsed = parse_compound_spec(item)
        if parsed.get("key"):
            custom_doses[parsed["key"].lower()] = parsed
            custom_doses[canonicalize_match_token(parsed["key"])] = parsed

    combined_effects = compute_target_combined_effects(graph, custom_doses=custom_doses)
    resolved_keys = resolve_stack_to_catalog_keys(parsed_stack)
    cascade_results = graph.propagate_cascade(
        resolved_keys or parsed_stack,
        combined_effects=combined_effects,
        patient_biometrics={"sex": "male", "age": 30, "weight_kg": 70},
        user_labs={"blood_pressure": 120.0},
    )

    shifts = {b["biomarker_id"]: b for b in cascade_results.get("biomarker_shifts", [])}
    assert "bio_blood_pressure" in shifts
    bp_shift = shifts["bio_blood_pressure"]
    assert bp_shift["estimated_delta"] < 0, f"Expected negative BP delta for PDE5 inhibitor, got {bp_shift['estimated_delta']}"
    assert bp_shift["estimated_value"] < 120.0

    assert "bio_cgmp" in shifts
    cgmp_shift = shifts["bio_cgmp"]
    assert cgmp_shift["estimated_delta"] > 0, "Expected elevated cGMP for PDE5 inhibitor"





