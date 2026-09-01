import json
import logging
from typing import Dict, Any, List

from app.knowledge_graph.graph_db import get_graph_database
from app.services.ai_service import ask_local_llm

logger = logging.getLogger("healthai.protocol_agent")

SYSTEM_PROMPT = """You are the HealthAI Clinical Protocol Optimizer, an expert pharmacology and multi-tier network reasoning engine.
Your sole responsibility is to analyze a compound stack, patient biometrics, and the provided GraphRAG biological network context to produce an optimized, risk-mitigated dosing and scheduling protocol.

### STRICT OPERATING RULES (NO HALLUCINATION):
1. **100% Graph Grounding**: You must NEVER invent unverified biological mechanisms, enzyme pathways, or binding affinities.
2. **Prioritize Provided Parameters**: Base half-life timings, target competition clashes, and renal/hepatic clearance strictly on the provided PK/PD matrix and biological triples.
3. **Missing Data**: If a specific pathway or parameter is not present in the graph context, explicitly state "Graph data unavailable" instead of relying on memory.
4. **JSON Schema Compliance**: Output ONLY a valid JSON object matching the schema below. Do not include markdown codeblocks or conversational filler.

```json
{
  "dosage_adjustments": [
    {
      "compound": "Compound Name",
      "adjustment_reasoning": "Quantitative reasoning referencing eGFR, ALT, or target clashes",
      "recommended_dose_change": "e.g., Reduce dose by 50% or maintain standard"
    }
  ],
  "scheduling": [
    {
      "compound": "Compound Name",
      "timing": "e.g., Morning with food / Bedtime / Space 4h apart",
      "reasoning": "Grounding in half-life (t1/2) and receptor occupancy kinetics"
    }
  ],
  "countermeasures": [
    {
      "risk": "Identified biological risk or target clash",
      "recommended_compound": "Protective compound or cofactor to introduce",
      "reasoning": "Mechanism of protection verified by causal chain or pathway"
    }
  ],
  "summary_analysis": "Concise 2-3 sentence clinical synthesis of the stack's net equilibrium."
}
```
"""

async def optimize_protocol(stack: List[str], biometrics: Dict[str, Any], history: str = "") -> Dict[str, Any]:
    """
    Orchestrates the 3-step optimization process:
    1. GraphRAG Context Extraction
    2. Prompt Construction
    3. Local LLM Inference
    """
    db = get_graph_database()
    
    # 1. Extract Deep GraphRAG Context (up to 3 hops)
    try:
        graphrag_context = db.get_graphrag_context(
            entity_ids=stack,
            max_hops=3,
            include_pkpd=True,
            include_kinetics=True,
            include_causal_chains=True
        )
        graph_text = graphrag_context.get("formatted_prompt_context", "No context found.")
    except Exception as e:
        logger.error(f"Error extracting GraphRAG context: {e}")
        graph_text = f"Error retrieving graph context: {str(e)}"

    # Format the history block if provided
    history_block = f"\n### PREVIOUS OPTIMIZATION PASSES (MEMORY)\n{history}\nReview the history to understand why the current stack looks the way it does. Verify if any countermeasures you previously added have introduced new conflicts that now need to be resolved or adjusted." if history else ""

    # 2. Construct Grounded Prompt
    user_prompt = f"""
### PATIENT BIOMETRICS
- Age: {biometrics.get('age', 'Unknown')}
- Weight (kg): {biometrics.get('weight_kg', 'Unknown')}
- eGFR (Renal): {biometrics.get('egfr', 'Unknown')}
- ALT (Hepatic): {biometrics.get('alt_u_l', 'Unknown')}
- Blood Pressure: {biometrics.get('blood_pressure', 'Unknown')}
- Body Fat %: {biometrics.get('body_fat_pct', 'Unknown')}

### ACTIVE COMPOUND STACK
{', '.join(stack)}
{history_block}

{graph_text}

Analyze the above stack and biometrics against the provided GraphRAG context. Provide dosage adjustments, optimal scheduling, and necessary protective countermeasures in JSON format.
"""

    # 3. Call Local AI
    try:
        response_json = await ask_local_llm(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        return response_json
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        return {
            "error": str(e),
            "dosage_adjustments": [],
            "scheduling": [],
            "countermeasures": [],
            "summary_analysis": "AI optimization failed. Please check if the local AI engine (llama-server or Ollama) is running."
        }
