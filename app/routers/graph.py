from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.knowledge_graph.graph_db import get_graph_database
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
    timeline: Optional[str] = Query(default=None),
    timeline_days: Optional[float] = Query(default=None),
    sex: Optional[str] = Query(default=None),
    age: Optional[int] = Query(default=None),
    weight_kg: Optional[float] = Query(default=None),
    height_cm: Optional[float] = Query(default=None),
    body_fat_pct: Optional[float] = Query(default=None),
    blood_pressure: Optional[float] = Query(default=None),
    alt_u_l: Optional[float] = Query(default=None),
    egfr: Optional[float] = Query(default=None),
    hematocrit_pct: Optional[float] = Query(default=None),
    potassium_meq_l: Optional[float] = Query(default=None),
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

    # Parse custom doses from parsed_stack (e.g. 'eplerenone:12.5mg:daily')
    custom_doses: dict[str, Any] = {}
    for item in parsed_stack:
        parsed = parse_compound_spec(item)
        if parsed.get("key"):
            custom_doses[parsed["key"].lower()] = parsed
            custom_doses[canonicalize_match_token(parsed["key"])] = parsed

    # Compute multi-compound combined receptor effects & occupancy
    combined_effects = compute_target_combined_effects(graph, custom_doses=custom_doses)

    def _clean_param(v: Any) -> Any:
        if v is None or type(v).__name__ == "Query" or (hasattr(v, "__class__") and "Query" in getattr(v, "__class__").__name__):
            return None
        return v

    patient_biometrics = {
        "sex": _clean_param(sex),
        "age": _clean_param(age),
        "weight_kg": _clean_param(weight_kg),
        "height_cm": _clean_param(height_cm),
        "body_fat_pct": _clean_param(body_fat_pct),
    }
    user_labs = {
        "blood_pressure": _clean_param(blood_pressure),
        "alt_u_l": _clean_param(alt_u_l),
        "egfr": _clean_param(egfr),
        "hematocrit_pct": _clean_param(hematocrit_pct),
        "potassium_meq_l": _clean_param(potassium_meq_l),
    }

    # Run dynamic cascade propagation with saturation, net activation, biometrics, and timeline calibration
    resolved_keys = resolve_stack_to_catalog_keys(parsed_stack)
    cascade_results = graph.propagate_cascade(
        resolved_keys or parsed_stack,
        combined_effects=combined_effects,
        timeline=timeline,
        timeline_days=timeline_days,
        patient_biometrics=patient_biometrics,
        user_labs=user_labs,
    )

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
            "open_targets": attrs.get("open_targets"),
            "alphafold_structure": attrs.get("alphafold_structure"),
            "faers_surveillance": attrs.get("faers_surveillance"),
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


class CypherQueryRequest(BaseModel):
    query: str = Field(
        ...,
        description="Cypher graph query to execute against dedicated Neo4j backend",
        examples=["MATCH (c:CompoundNode)-[r:RELATIONSHIP]->(t:TargetNode) RETURN c.label, t.label, r.edge_type LIMIT 10"],
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional parameter dictionary for Cypher query",
    )


class GraphRAGContextRequest(BaseModel):
    entity_ids: List[str] = Field(
        ...,
        description="Entity keys or target node IDs to retrieve GraphRAG subgraph context for",
        examples=[["telmisartan", "sildenafil"]],
    )
    max_hops: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum multi-hop depth for GraphRAG context expansion",
    )
    include_pkpd: bool = Field(
        default=True,
        description="Whether to include structured pharmacokinetic & clearance profiles in context",
    )
    include_kinetics: bool = Field(
        default=True,
        description="Whether to include downstream biomarker kinetic parameters in context",
    )
    include_causal_chains: bool = Field(
        default=True,
        description="Whether to extract multi-tier causal reasoning pathways",
    )


@router.post("/api/graph/cypher")
def execute_cypher_query(request: CypherQueryRequest) -> JSONResponse:
    """Execute arbitrary Cypher query against dedicated Neo4j graph database backend."""
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Cypher query string cannot be empty.")

    try:
        db = get_graph_database()
        results = db.execute_cypher(request.query, request.parameters)
        return JSONResponse(
            {"query": request.query, "results": results, "count": len(results)},
            headers=NO_CACHE_HEADERS,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cypher execution error: {str(e)}")


@router.post("/api/graph/graphrag-context")
def get_graphrag_context_api(request: GraphRAGContextRequest) -> JSONResponse:
    """Extract structured GraphRAG subgraph context, triples, causal chains, PK/PD matrix, and formatted prompt context for LLM integration."""
    if not request.entity_ids:
        raise HTTPException(status_code=400, detail="At least one entity ID is required.")

    # Ensure compound graph is built & synced to Neo4j
    try:
        build_selected_compound_graph(request.entity_ids)
    except Exception as e:
        import logging; logging.getLogger(__name__).debug("Suppressed exception: %s", e, exc_info=True)

    try:
        db = get_graph_database()
        context = db.get_graphrag_context(
            request.entity_ids,
            max_hops=request.max_hops,
            include_pkpd=request.include_pkpd,
            include_kinetics=request.include_kinetics,
            include_causal_chains=request.include_causal_chains,
        )
        return JSONResponse(context, headers=NO_CACHE_HEADERS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GraphRAG context extraction error: {str(e)}")


@router.get("/api/graph/evidence-timeline/{entity_id}")
def get_evidence_timeline(entity_id: str) -> JSONResponse:
    """Retrieve chronological discovery and clinical validation milestones for a biological entity."""
    if not entity_id or not entity_id.strip():
        raise HTTPException(status_code=400, detail="Entity ID is required.")

    try:
        db = get_graph_database()
        timeline = db.get_chronological_evidence_timeline(entity_id.strip())
        return JSONResponse(
            {
                "entity_id": entity_id,
                "milestone_count": len(timeline),
                "timeline": timeline,
            },
            headers=NO_CACHE_HEADERS,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evidence timeline error: {str(e)}")


@router.get("/api/graph/conflicts")
def get_graph_conflicts(
    entity_ids: Optional[List[str]] = Query(default=None),
) -> JSONResponse:
    """Extract disputed biological edges, opposing PMIDs, and scientific controversies for specified entities."""
    try:
        db = get_graph_database()
        res = db.get_conflicting_evidence_subgraph(entity_ids or [])
        return JSONResponse(res, headers=NO_CACHE_HEADERS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conflict subgraph extraction error: {str(e)}")


@router.get("/api/graph/temporal-snapshot")
def get_temporal_snapshot(
    year: int = Query(default=2026, ge=1950, le=2030, description="Snapshot year for historical literature cutoff"),
) -> JSONResponse:
    """Retrieve active nodes and edges in the scientific knowledge graph published on or before the specified year."""
    try:
        db = get_graph_database()
        snapshot = db.get_temporal_graph_snapshot(year)
        return JSONResponse(snapshot, headers=NO_CACHE_HEADERS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Temporal snapshot extraction error: {str(e)}")


@router.get("/api/graph/cooccurrences/{compound_key}")
def get_compound_cooccurrences(compound_key: str) -> JSONResponse:
    """
    Retrieves all literature co-occurrences, co-mention frequencies, and PMI scores
    for a compound from the Knowledge Graph.
    """
    clean_k = str(compound_key or "").strip().lower().replace(" ", "_")
    if not clean_k:
        raise HTTPException(status_code=400, detail="Compound key is required.")

    try:
        db = get_graph_database()
        cooccurrences = []
        seen = set()

        for edge in db._mock_edges:
            e_type = edge.get("edge_type") or edge.get("type")
            if e_type == "LITERATURE_COOCCURRENCE":
                s = str(edge.get("source", "")).lower()
                t = str(edge.get("target", "")).lower()
                partner = None
                if s == clean_k:
                    partner = t
                elif t == clean_k:
                    partner = s

                if partner and partner != clean_k and partner not in seen:
                    seen.add(partner)
                    cooccurrences.append({
                        "compound": clean_k,
                        "partner_compound": partner,
                        "cooccurrence_count": edge.get("count_ab") or edge.get("cooccurrence_count") or 1,
                        "pmi_score": round(float(edge.get("pmi", 0.0)), 3),
                        "npmi_score": round(float(edge.get("npmi_score", 0.0) or edge.get("npmi", 0.0)), 3),
                        "confidence": round(float(edge.get("confidence", 0.5)), 3),
                        "evidence_level": edge.get("evidence_level", "literature_cooccurrence"),
                    })

        cooccurrences.sort(key=lambda x: (x.get("npmi_score", 0), x.get("cooccurrence_count", 0)), reverse=True)
        return JSONResponse(
            {
                "compound_key": clean_k,
                "cooccurrence_count": len(cooccurrences),
                "cooccurrences": cooccurrences,
            },
            headers=NO_CACHE_HEADERS,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve literature co-occurrences: {str(e)}")


class MineCooccurrenceRequest(BaseModel):
    compound_a: str = Field(..., description="First compound name or key")
    compound_b: str = Field(..., description="Second compound name or key")


@router.post("/api/graph/mine-cooccurrences")
def mine_cooccurrences_endpoint(request: MineCooccurrenceRequest) -> JSONResponse:
    """
    Computes live PubMed co-occurrence frequency, PMI, and NPMI for a pair of compounds
    and automatically ingests the relationship edge into the Knowledge Graph.
    """
    try:
        from app.services.cooccurrence_miner import CooccurrenceMiner
        miner = CooccurrenceMiner()
        result = miner.compute_pmi(request.compound_a, request.compound_b)
        miner.write_cooccurrences_to_graph([result])
        return JSONResponse(result, headers=NO_CACHE_HEADERS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error mining literature co-occurrence: {str(e)}")

