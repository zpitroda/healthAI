from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.graph_service import (
    build_selected_compound_graph,
    canonicalize_match_token,
    compute_target_combined_effects,
    filter_graph_by_stack,
    parse_compound_spec,
    resolve_stack_to_catalog_keys,
)

router = APIRouter(tags=["graph"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _get_node_tier(node_type: str) -> tuple[int, str]:
    """Map node_type to a hierarchical tier index (0-5) and human-friendly tier label."""
    nt = (node_type or "").lower()
    if nt == "compound":
        return 0, "Compound"
    if nt in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
        return 1, "Molecular Target"
    if nt in ("signaling_pathway", "reaction", "pathway"):
        return 2, "Signaling Cascade"
    if nt in ("physiology", "organ_system"):
        return 3, "Organ Physiology"
    if nt in ("biomarker", "lab"):
        return 4, "Clinical Biomarker"
    if nt in ("phenotype", "outcome", "toxicity", "benefit"):
        return 5, "Clinical Outcome"
    return 3, "Biological Entity"


def _classify_interaction_direction(edge_type: str, mag: float) -> str:
    """Classify edge into positive, negative, allosteric, metabolic, or neutral."""
    et = (edge_type or "").upper()
    if any(k in et for k in ["INHIBIT", "ANTAGONIZ", "SUPPRESS", "BLOCK", "DECREASE", "MITIGATE", "NEGATIVE"]):
        return "negative"
    if any(k in et for k in ["AGONIZ", "ACTIVAT", "INDUCE", "OPEN", "INCREASE", "DRIVE", "POTENTIAT", "POSITIVE", "SYNERGIZ"]):
        return "positive"
    if "ALLOSTERIC" in et:
        return "allosteric"
    if any(k in et for k in ["SUBSTRATE", "EFFLUX", "UPTAKE", "METABOLIZ"]):
        return "metabolic"
    if mag < 0:
        return "negative"
    return "positive" if mag > 0 else "neutral"


@router.get("/graph-data")
def graph_data(
    focus: Optional[str] = None,
    depth: int = 5,
    stack: Optional[List[str]] = Query(default=None),
) -> JSONResponse:
    """Return JSON node and edge network graph data, dynamic cascade simulation, and combined target receptor activation for the active compound stack."""
    focus_str = focus if isinstance(focus, str) else None
    depth_val = depth if isinstance(depth, int) else 5

    if stack is None:
        return JSONResponse(
            {"nodes": [], "edges": [], "focus": focus_str, "depth": depth_val, "cascade_simulation": {}, "combined_effects": {}},
            headers=NO_CACHE_HEADERS,
        )

    parsed_stack: List[str] = []
    if isinstance(stack, str):
        values = [stack]
    else:
        values = stack

    for value in values:
        if value is None:
            continue
        for item in str(value).split(","):
            cleaned = item.strip()
            if cleaned:
                parsed_stack.append(cleaned)

    if not parsed_stack:
        return JSONResponse(
            {"nodes": [], "edges": [], "focus": focus_str, "depth": depth_val, "cascade_simulation": {}, "combined_effects": {}},
            headers=NO_CACHE_HEADERS,
        )

    graph = build_selected_compound_graph(parsed_stack)
    graph = filter_graph_by_stack(graph, parsed_stack, max_depth=max(depth_val, 2))

    # Parse custom doses from parsed_stack (e.g. 'eplerenone:12.5mg')
    custom_doses: dict[str, float] = {}
    for item in parsed_stack:
        parsed = parse_compound_spec(item)
        if parsed.get("key") and parsed.get("dose_mg") is not None:
            custom_doses[parsed["key"].lower()] = parsed["dose_mg"]
            custom_doses[canonicalize_match_token(parsed["key"])] = parsed["dose_mg"]

    # Compute multi-compound combined receptor effects & occupancy
    combined_effects = compute_target_combined_effects(graph, custom_doses=custom_doses)

    # Run dynamic cascade propagation with saturation & net activation calibration
    resolved_keys = resolve_stack_to_catalog_keys(parsed_stack)
    cascade_results = graph.propagate_cascade(resolved_keys or parsed_stack, combined_effects=combined_effects)

    if focus_str:
        if focus_str not in graph.graph:
            raise HTTPException(status_code=404, detail=f"Node '{focus_str}' was not found in the graph.")
        graph = graph.subgraph_from_node(focus_str, max_depth=depth_val)

    nodes = []
    for node_id, attrs in graph.graph.nodes(data=True):
        nt = attrs.get("node_type", "unknown")
        tier_idx, tier_name = _get_node_tier(nt)
        in_degree = graph.graph.in_degree(node_id) if graph.graph.has_node(node_id) else 0
        out_degree = graph.graph.out_degree(node_id) if graph.graph.has_node(node_id) else 0
        
        cat = str(attrs.get("category") or "").upper()
        if nt == "compound":
            pk_pd = "Compound"
        elif "PK" in cat or "PHARMACOKINETIC" in cat or "CYP" in str(attrs.get("enzyme_family", "")).upper() or nt == "transporter":
            pk_pd = "PK"
        else:
            pk_pd = "PD"

        comb = combined_effects.get(node_id)
        node_payload = {
            "id": node_id,
            "label": attrs.get("label", node_id),
            "node_type": nt,
            "tier": tier_idx,
            "tier_name": tier_name,
            "pk_pd_class": pk_pd,
            "category": attrs.get("category") or attrs.get("phenotype_category"),
            "enzyme_family": attrs.get("enzyme_family"),
            "transporter_family": attrs.get("transporter_family"),
            "unit": attrs.get("unit"),
            "biomarker_panel": attrs.get("biomarker_panel"),
            "organ_system": attrs.get("organ_system"),
            "pathway_database": attrs.get("pathway_database"),
            "smiles": attrs.get("smiles"),
            "inchikey": attrs.get("inchikey"),
            "logP": attrs.get("logP"),
            "molecular_weight": attrs.get("molecular_weight"),
            "in_degree": in_degree,
            "out_degree": out_degree,
            "degree": in_degree + out_degree,
            "combined_effect": comb,
            "has_multiple_ligands": bool(comb and comb.get("has_multiple_ligands")),
            "ligand_count": comb.get("ligand_count", 0) if comb else 0,
            "net_activation_score": comb.get("net_activation_score") if comb else None,
            "net_activation_pct": comb.get("net_activation_pct") if comb else None,
            "receptor_state": comb.get("receptor_state") if comb else None,
        }
        nodes.append(node_payload)

    def _readable_edge_label(edge_type: str, mag: float) -> str:
        """Convert internal edge type + magnitude into a concise, human-readable graph label."""
        et = (edge_type or "").upper()
        direction = "INCREASES" if mag >= 0 else "DECREASES"
        if et == "MODIFIES_BIOMARKER":
            return direction
        if et == "ALTERS_PHYSIOLOGY":
            return "ACTIVATES" if mag >= 0 else "SUPPRESSES"
        if et == "ACTIVATES_CASCADE":
            return "ACTIVATES"
        if et == "INHIBITS_CASCADE":
            return "INHIBITS"
        if et == "ACTIVATES_PATHWAY":
            return "ACTIVATES"
        if et == "INHIBITS_PATHWAY":
            return "INHIBITS"
        if et == "INHIBITS_ENZYME":
            return "INHIBITS"
        if et == "INDUCES_ENZYME":
            return "INDUCES"
        if et == "DRIVES_PHENOTYPE":
            return "DRIVES"
        if et == "MITIGATES_PHENOTYPE":
            return "MITIGATES"
        if et == "BLOCKS_CHANNEL":
            return "BLOCKS"
        if et == "OPENS_CHANNEL":
            return "OPENS"
        if et == "POSITIVE_ALLOSTERIC_MODULATOR":
            return "POTENTIATES"
        if et == "NEGATIVE_ALLOSTERIC_MODULATOR":
            return "DAMPENS"
        if et == "SYNERGIZES_WITH":
            return "SYNERGIZES"
        if et == "CONTRAINDICATED_WITH":
            return "CONTRAINDICATED"
        if et == "SUBSTRATE_OF":
            return "METABOLIZED BY"
        if et == "EFFLUXED_BY":
            return "EFFLUXED BY"
        if et == "UPTAKE_BY":
            return "UPTAKE BY"
        # Types that are already concise and human-readable — pass through verbatim
        return et

    edges = []
    for source, target, attrs in graph.graph.edges(data=True):
        raw_type = attrs.get("edge_type", "")
        mag = float(attrs.get("vector_magnitude", 1.0))
        if raw_type == "SUBSTRATE_OF":
            # The enzyme acts upon the substrate compound: orient arrow from Enzyme -> Substrate with active verb METABOLIZES
            edges.append({
                "source": target,
                "target": source,
                "type": "METABOLIZES",
                "raw_type": raw_type,
                "vector_magnitude": mag,
                "direction_class": "inhibitory",
                "affinity_ki": attrs.get("affinity_ki"),
                "inhibition_ic50": attrs.get("inhibition_ic50"),
                "is_bridge": bool(attrs.get("is_bridge", False)),
                "description": attrs.get("description") or f"{target} metabolizes {source}",
            })
        else:
            edges.append({
                "source": source,
                "target": target,
                "type": _readable_edge_label(raw_type, mag),
                "raw_type": raw_type,
                "vector_magnitude": mag,
                "direction_class": _classify_interaction_direction(raw_type, mag),
                "affinity_ki": attrs.get("affinity_ki"),
                "inhibition_ic50": attrs.get("inhibition_ic50"),
                "is_bridge": bool(attrs.get("is_bridge", False)),
                "description": attrs.get("description"),
            })

    return JSONResponse(
        {
            "nodes": nodes,
            "edges": edges,
            "focus": focus,
            "depth": depth,
            "cascade_simulation": cascade_results,
            "combined_effects": combined_effects,
        },
        headers=NO_CACHE_HEADERS,
    )


@router.get("/graph-path")
def graph_path(
    source: str,
    target: str,
    stack: Optional[List[str]] = Query(default=None),
) -> JSONResponse:
    """Find the shortest biological path and cross-talk connections between two nodes in the graph."""
    if not source or not target:
        raise HTTPException(status_code=400, detail="Both source and target node IDs are required.")

    parsed_stack: List[str] = []
    if stack:
        for val in stack:
            for item in str(val).split(","):
                cleaned = item.strip()
                if cleaned:
                    parsed_stack.append(cleaned)

    graph = build_selected_compound_graph(parsed_stack or [source, target])

    import networkx as nx

    # Try directed path first, then undirected fallback
    path: List[str] = []
    try:
        if nx.has_path(graph.graph, source, target):
            path = nx.shortest_path(graph.graph, source, target)
        else:
            undirected = graph.graph.to_undirected()
            if nx.has_path(undirected, source, target):
                path = nx.shortest_path(undirected, source, target)
    except Exception:
        path = []

    return JSONResponse(
        {"source": source, "target": target, "path": path, "length": len(path)},
        headers=NO_CACHE_HEADERS,
    )

