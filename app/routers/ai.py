from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.copilot_agent import CopilotAgent
from app.services.protocol_agent import optimize_protocol
from app.services.stack_intent_engine import StackIntentEngine

logger = logging.getLogger("healthai.router.ai")

router = APIRouter(tags=["ai"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")


class CopilotChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="Conversation history")
    persona: Optional[str] = Field("architect", description="Active persona: architect, auditor, tutor, labs")
    stack: Optional[List[str]] = Field(default_factory=list, description="Active compound keys or names")
    biometrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Patient clearance parameters")
    protocol_goal: Optional[str] = Field(None, description="User-selected or inferred protocol goal ID")
    protocol_objective: Optional[str] = Field(None, description="User's custom protocol objective or notes")
    custom_instructions: Optional[str] = Field(None, description="Custom prompt constraints or user notes")
    max_exploration_steps: Optional[int] = Field(8, description="Maximum ReAct graph traversal & tool call exploration steps")


class InferPurposeRequest(BaseModel):
    stack: List[Any] = Field(default_factory=list, description="List of compound IDs or specs")
    biometrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Patient biometrics")
    user_goal: Optional[str] = Field(None, description="Optional user goal ID")
    user_objective: Optional[str] = Field(None, description="Optional custom user objective text")


class BuildStackFromScratchRequest(BaseModel):
    goal: Optional[str] = Field("cognitive_focus", description="Primary protocol goal ID (e.g. cognitive_focus, longevity_autophagy, etc.)")
    biometrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Patient clearance parameters")
    preferences: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="User constraints e.g. risk_tolerance, stimulant_level, complexity, substance_style, route_preference, schedule_preference, organ_priority, budget_tier"
    )
    requested_compounds: Optional[List[str]] = Field(default_factory=list, description="Explicit structured list of requested compound keys or names")
    exclusions: Optional[List[str]] = Field(default_factory=list, description="Explicit structured list of compound keys or names to exclude")
    custom_instructions: Optional[str] = Field(None, description="Custom user notes or clinical constraints")


class ToolExecutionRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the registered tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ProtocolOptimizationRequest(BaseModel):
    stack: List[Any] = Field(..., description="List of compound IDs or names")
    biometrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Patient biometrics")


@router.get("/api/ai/modes")
def get_copilot_modes() -> List[Dict[str, Any]]:
    """
    Returns registered Copilot personas, icons, descriptions, and contextual quick prompts.
    """
    return CopilotAgent.get_registered_modes()


@router.get("/api/ai/goals")
def get_protocol_goals() -> List[Dict[str, Any]]:
    """
    Returns the protocol purpose taxonomy for user selection.
    """
    return StackIntentEngine.get_goal_taxonomy()


@router.post("/api/ai/infer-purpose")
def infer_stack_purpose(request: InferPurposeRequest) -> Dict[str, Any]:
    """
    Analyzes active stack compounds to infer purpose, partition modalities,
    and identify therapeutic gaps.
    """
    from app.services.catalog_service import CatalogService
    from app.services.graph_service import parse_compound_spec

    catalog = CatalogService()
    cleaned_stack = [str(s).strip() for s in request.stack if s is not None and str(s).strip()]
    
    canonical_compounds = []
    for item_str in cleaned_stack:
        spec = parse_compound_spec(item_str)
        raw_key = spec.get("key", item_str)
        comp_record = catalog.get_compound(raw_key, auto_enrich=False) or catalog.find_by_synonym(raw_key)
        if comp_record:
            merged = dict(comp_record)
            merged.update(spec)
            canonical_compounds.append(merged)
        else:
            canonical_compounds.append(spec)

    canonical_compounds = catalog.canonicalize_and_merge_stack(canonical_compounds)

    return StackIntentEngine.analyze(
        compounds=canonical_compounds,
        biometrics=request.biometrics or {},
        user_goal_id=request.user_goal,
        user_objective_text=request.user_objective,
    )


@router.post("/api/ai/chat/stream")
async def stream_copilot_chat(request: CopilotChatRequest):
    """
    Server-Sent Events (SSE) streaming endpoint for real-time multi-turn Copilot chat,
    reasoning telemetry, and structured action card generation.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    raw_messages = [m.model_dump() for m in request.messages]
    cleaned_stack = [str(s).strip() for s in (request.stack or []) if s is not None and str(s).strip()]

    async def sse_event_generator():
        try:
            async for event_obj in CopilotAgent.stream_copilot_turn(
                messages=raw_messages,
                persona=request.persona or "architect",
                stack=cleaned_stack,
                biometrics=request.biometrics or {},
                protocol_goal=request.protocol_goal,
                protocol_objective=request.protocol_objective,
                custom_instructions=request.custom_instructions,
                max_exploration_steps=request.max_exploration_steps or 8,
            ):
                event_name = event_obj.get("event", "delta")
                data_val = event_obj.get("data")
                if data_val == "[DONE]":
                    yield f"event: done\ndata: \"[DONE]\"\n\n"
                    break
                payload_str = json.dumps(data_val)

                # Standard SSE chunk
                yield f"event: {event_name}\ndata: {payload_str}\n\n"
        except Exception as e:
            logger.error(f"Error in SSE copilot stream: {e}")
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Content-Encoding": "identity",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/api/ai/chat")
async def copilot_chat(request: CopilotChatRequest):
    """
    Non-streaming multi-turn chat endpoint for REST clients.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    raw_messages = [m.model_dump() for m in request.messages]
    cleaned_stack = [str(s).strip() for s in (request.stack or []) if s is not None and str(s).strip()]

    result = await CopilotAgent.chat_copilot_turn(
        messages=raw_messages,
        persona=request.persona or "architect",
        stack=cleaned_stack,
        biometrics=request.biometrics or {},
        protocol_goal=request.protocol_goal,
        protocol_objective=request.protocol_objective,
    )
    return result


@router.post("/api/ai/chat/reset")
@router.post("/api/ai/reset")
async def reset_copilot_chat() -> Dict[str, Any]:
    """
    Completely resets Copilot conversational context and model memory,
    erasing local LLM KV cache slots, cached prompts, and session state.
    """
    try:
        return await CopilotAgent.reset_session_context()
    except Exception as e:
        logger.error(f"Error resetting copilot context: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/api/ai/tools/execute")
def execute_ai_tool(request: ToolExecutionRequest):
    """
    Executes a deterministic internal pharmacology tool on behalf of the AI or UI.
    """
    try:
        return CopilotAgent.execute_tool(request.tool_name, request.arguments)
    except Exception as e:
        logger.error(f"Error executing AI tool '{request.tool_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/build-stack-from-scratch")
def build_stack_from_scratch(request: BuildStackFromScratchRequest) -> Dict[str, Any]:
    """
    Generates a scientifically validated, calibrated compound stack from scratch
    tailored to the user's primary goal, preferences, and biometrics.
    """
    try:
        return StackIntentEngine.build_scratch_stack_proposal(
            goal_id=request.goal,
            biometrics=request.biometrics or {},
            preferences=request.preferences or {},
            custom_notes=request.custom_instructions or "",
            exclusions=request.exclusions,
            requested_compounds=request.requested_compounds,
        )
    except Exception as e:
        logger.error(f"Error building stack from scratch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/optimize-protocol")
async def api_optimize_protocol(request: ProtocolOptimizationRequest):
    """
    Analyzes the compound stack against patient biometrics using
    local AI grounded in multi-hop GraphRAG biological pathways.
    """
    cleaned_stack = [str(s).strip() for s in request.stack if s is not None and str(s).strip()]
    if not cleaned_stack:
        raise HTTPException(status_code=400, detail="Compound stack cannot be empty")

    try:
        result = await optimize_protocol(cleaned_stack, request.biometrics)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class StackDiffSimulationRequest(BaseModel):
    base_stack: List[Any] = Field(default_factory=list, description="Current stack compounds")
    diff: Dict[str, Any] = Field(default_factory=dict, description="Proposed additions, modifications, removals")
    biometrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Patient biometrics")


class LiteratureSearchRequest(BaseModel):
    query: str = Field(..., description="Biomedical query or compound name")
    max_results: Optional[int] = Field(4, description="Max literature citations to retrieve")


@router.post("/api/ai/simulate-stack-diff")
def api_simulate_stack_diff(request: StackDiffSimulationRequest) -> Dict[str, Any]:
    """
    Executes virtual 'what-if' experiment simulating the impact of proposed stack changes.
    """
    try:
        from app.services.stack_diff_simulator import StackDiffSimulator
        return StackDiffSimulator.simulate_diff(
            base_stack=request.base_stack,
            diff=request.diff,
            biometrics=request.biometrics or {},
        )
    except Exception as e:
        logger.error(f"Error simulating stack diff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/literature/search")
def api_search_literature(request: LiteratureSearchRequest) -> Dict[str, Any]:
    """
    Searches PubMed and Europe PMC for peer-reviewed citations matching the query.
    """
    try:
        from app.services.pubmed_service import PubMedService
        pubmed_svc = PubMedService()
        citations = pubmed_svc.search_literature(request.query, max_results=request.max_results or 4)
        return {"query": request.query, "count": len(citations), "citations": citations}
    except Exception as e:
        logger.error(f"Error searching biomedical literature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class LiteratureAbstractRequest(BaseModel):
    pmid: str = Field(..., description="PMID of the publication to fetch abstract for")


class HybridLiteratureSearchRequest(BaseModel):
    query: str = Field(..., description="Search query or therapeutic endpoint")
    entity_ids: Optional[List[str]] = Field(default_factory=list, description="Target compound keys or entity IDs")
    max_results: Optional[int] = Field(5, description="Max results")


@router.post("/api/ai/literature/abstract")
def api_fetch_abstract(request: LiteratureAbstractRequest) -> Dict[str, Any]:
    """
    Fetches the full structured abstract and publication metadata for a given PMID.
    """
    try:
        from app.services.pubmed_service import PubMedService
        pubmed_svc = PubMedService()
        abstract_data = pubmed_svc.fetch_abstract(request.pmid)
        if not abstract_data:
            raise HTTPException(status_code=404, detail=f"Abstract for PMID '{request.pmid}' not found.")
        return abstract_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching paper abstract: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/literature/hybrid-search")
def api_hybrid_literature_search(request: HybridLiteratureSearchRequest) -> Dict[str, Any]:
    """
    Unified Hybrid GraphRAG and literature search returning multi-hop causal chains and empirical citations.
    """
    try:
        from app.knowledge_graph.graph_db import get_graph_database
        graph_db = get_graph_database()
        return graph_db.search_hybrid_graph_and_literature(
            query=request.query,
            entity_ids=request.entity_ids,
            max_results=request.max_results or 5,
        )
    except Exception as e:
        logger.error(f"Error executing hybrid literature search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class LiteratureTitleSearchRequest(BaseModel):
    query: str = Field(..., description="Query string for title discovery")
    max_results: Optional[int] = Field(8, description="Maximum candidate titles to return")


@router.post("/api/ai/literature/search-titles")
def api_search_titles(request: LiteratureTitleSearchRequest) -> Dict[str, Any]:
    """
    Lightweight candidate title discovery for agentic reasoning and search autocomplete.
    """
    try:
        from app.services.pubmed_service import PubMedService
        pubmed_svc = PubMedService()
        titles = pubmed_svc.search_pubmed_titles(request.query, max_results=request.max_results or 8)
        return {"query": request.query, "count": len(titles), "candidate_titles": titles}
    except Exception as e:
        logger.error(f"Error searching paper titles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FullTextSectionRequest(BaseModel):
    pmid_or_pmcid: str = Field(..., description="PMID or PMCID of the study")
    section: Optional[str] = Field("results", description="Target section: results, methods, dosage, adverse_effects, discussion")
    max_words: Optional[int] = Field(600, description="Max word count for section truncation")


@router.post("/api/ai/literature/full-text-section")
def api_fetch_full_text_section(request: FullTextSectionRequest) -> Dict[str, Any]:
    """
    Section-targeted reader for Open Access PMC articles with paywall abstract fallback.
    """
    try:
        from app.services.pubmed_service import PubMedService
        pubmed_svc = PubMedService()
        return pubmed_svc.fetch_paper_full_text_section(
            request.pmid_or_pmcid,
            section=request.section or "results",
            max_words=request.max_words or 600,
        )
    except Exception as e:
        logger.error(f"Error reading paper section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SearchWithinPaperRequest(BaseModel):
    pmid_or_pmcid: str = Field(..., description="PMID or PMCID")
    query: str = Field(..., description="Target passage query")
    max_passages: Optional[int] = Field(3, description="Max passages to return")


@router.post("/api/ai/literature/search-within-paper")
def api_search_within_paper(request: SearchWithinPaperRequest) -> Dict[str, Any]:
    """
    Passage-level semantic search within an individual study.
    """
    try:
        from app.services.pubmed_service import PubMedService
        pubmed_svc = PubMedService()
        return pubmed_svc.search_within_paper(
            request.pmid_or_pmcid,
            query=request.query,
            max_passages=request.max_passages or 3,
        )
    except Exception as e:
        logger.error(f"Error searching within paper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SimilarPapersRequest(BaseModel):
    pmid: str = Field(..., description="Target study PMID")
    top_k: Optional[int] = Field(4, description="Number of similar studies to retrieve")


@router.post("/api/ai/literature/similar")
def api_find_similar_papers(request: SimilarPapersRequest) -> Dict[str, Any]:
    """
    Finds structurally and mechanistically related studies using vector embeddings across the knowledge graph.
    """
    try:
        from app.services.pubmed_service import PubMedService
        pubmed_svc = PubMedService()
        similar = pubmed_svc.find_similar_papers(request.pmid, top_k=request.top_k or 4)
        return {"pmid": request.pmid, "count": len(similar), "similar_papers": similar}
    except Exception as e:
        logger.error(f"Error finding similar papers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SemanticLiteratureSearchRequest(BaseModel):
    query: str = Field(..., description="Semantic query text")
    top_k: Optional[int] = Field(5, description="Max results")


@router.post("/api/ai/literature/semantic-search")
def api_semantic_literature_search(request: SemanticLiteratureSearchRequest) -> Dict[str, Any]:
    """
    Dense semantic vector search across all cached citation nodes in the graph database.
    """
    try:
        from app.knowledge_graph.graph_db import get_graph_database
        graph_db = get_graph_database()
        results = graph_db.search_citations_semantic(request.query, top_k=request.top_k or 5)
        return {"query": request.query, "count": len(results), "citations": results}
    except Exception as e:
        logger.error(f"Error in semantic literature search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

