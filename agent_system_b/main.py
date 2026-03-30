"""
Agent System B — Independent Google ADK Microservice
ReAct agent that analyzes UAE rental properties.

Receives HTTP POST /analyze from Agent System A,
runs a 4-step reasoning pipeline, and returns
an agentic JSON response with valuation + reasoning.
"""

import json
import threading
from contextlib import contextmanager
from fastapi import FastAPI
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

from agent_system_b.config import HOST, PORT, LLM_MODEL
from agent_system_b.pipeline.request_parser import AnalysisRequest, parse_request
from agent_system_b.pipeline.comp_finder import find_comps, CompFinderResult
from agent_system_b.pipeline.comp_evaluator import evaluate_comps, EvaluationResult
from agent_system_b.pipeline.synthesis_engine import synthesize, AgenticResponse
from shared.logging_config import get_logger

logger = get_logger("agent_system_b.api")


# ═══════════════════════════════════════════════════════
# PIPELINE STATE — request-scoped via threading.local()
# ═══════════════════════════════════════════════════════
# Each concurrent request gets its own isolated state dict.
# Tools store/read results through _get_state() which returns
# the current thread's state — no cross-request contamination.
_thread_local = threading.local()


def _get_state() -> dict:
    """Get the pipeline state for the current request (thread-local)."""
    if not hasattr(_thread_local, "state"):
        _thread_local.state = {}
    return _thread_local.state


@contextmanager
def _scoped_state():
    """Context manager that resets pipeline state for a new request."""
    _thread_local.state = {}
    try:
        yield _thread_local.state
    finally:
        _thread_local.state = {}


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS — These are what the ReAct agent calls
# ═══════════════════════════════════════════════════════

def tool_parse_request(
    location: str,
    property_type: str = "Apartment",
    bedrooms: int = None,
    budget_max: float = None,
    furnished: str = None,
    query: str = "",
) -> dict:
    """Parse an incoming property analysis request into structured search criteria.
    Call this FIRST to understand what the user is looking for."""
    request = AnalysisRequest(
        location=location,
        property_type=property_type,
        bedrooms=bedrooms,
        budget_max=budget_max,
        furnished=furnished,
        query=query,
    )
    criteria = parse_request(request)
    _get_state()["criteria"] = criteria
    logger.info(f"Step 1: Parsed request | {property_type} in {location}, beds={bedrooms}, budget={budget_max}")
    return {"status": "parsed", "summary": f"{property_type} in {location}", "criteria": criteria.model_dump()}


def tool_find_comparables(
    location: str,
    property_type: str = "Apartment",
    bedrooms: int = None,
    budget_max: float = None,
    furnished: str = None,
    search_strategy: str = "",
) -> dict:
    """Search for comparable properties in the CSV database and market reports.
    Call this SECOND after parsing the request to find matching properties."""
    from agent_system_b.pipeline.request_parser import ParsedCriteria

    # Use stored criteria from step 1 if available, otherwise build from args
    criteria = _get_state().get("criteria") or ParsedCriteria(
        location=location,
        property_type=property_type,
        bedrooms=bedrooms,
        budget_max=budget_max,
        furnished=furnished,
        search_strategy=search_strategy,
    )
    result = find_comps(criteria)
    _get_state()["comps"] = result
    logger.info(f"Step 2: Found {result.num_comps_found} comparables | market_context_chunks={len(result.market_context)}")
    return {
        "status": "found",
        "num_comps": result.num_comps_found,
        "market_context_chunks": len(result.market_context),
        "sample": [
            {"address": c.address, "rent": c.rent}
            for c in result.comparable_properties[:3]
        ],
    }


def tool_evaluate_comparables() -> dict:
    """Evaluate the found comparable properties using AI reasoning — score relevance,
    detect outliers, apply market adjustments, and estimate rental value.
    Call this THIRD after finding comparables. No arguments needed — reads from previous step."""
    comps = _get_state().get("comps")
    if not comps:
        logger.error("Step 3: No comparables in pipeline state — tool_find_comparables was not called first")
        return {"error": "No comparables found yet. Call tool_find_comparables first."}

    evaluation = evaluate_comps(comps)
    _get_state()["evaluation"] = evaluation
    logger.info(f"Step 3: Evaluated comps | estimated_value={evaluation.estimated_value:,.0f} AED, confidence={evaluation.confidence_score}")
    return {
        "status": "evaluated",
        "estimated_value": evaluation.estimated_value,
        "confidence": evaluation.confidence_score,
        "num_evaluated": len(evaluation.evaluated_comps),
        "reasoning_preview": evaluation.reasoning_chain[:200],
    }


def tool_synthesize_response() -> dict:
    """Build the final agentic response with estimated value, confidence score,
    reasoning chain, and supporting comparables.
    Call this LAST to produce the final analysis. No arguments needed — reads from previous step."""
    evaluation = _get_state().get("evaluation")
    if not evaluation:
        logger.error("Step 4: No evaluation in pipeline state — tool_evaluate_comparables was not called first")
        return {"error": "No evaluation found yet. Call tool_evaluate_comparables first."}

    response = synthesize(evaluation)
    _get_state()["response"] = response
    logger.info(f"Step 4: Synthesized response | comps_analyzed={response.num_comps_analyzed}, confidence={response.confidence_score}")
    return response.model_dump()


# ═══════════════════════════════════════════════════════
# REACT AGENT — Google ADK agent with tools
# ═══════════════════════════════════════════════════════

AGENT_INSTRUCTION = """You are a senior UAE real estate analyst. When given a property analysis request,
you MUST follow these steps using your tools IN ORDER:

1. Call tool_parse_request with the location and property details
2. Call tool_find_comparables with the same search criteria
3. Call tool_evaluate_comparables (no arguments — it reads from the previous step)
4. Call tool_synthesize_response (no arguments — it reads from the previous step)

Always complete all 4 steps. Never skip a step. Return the final synthesized response."""

agent = Agent(
    name="property_analyzer",
    model=LLM_MODEL,
    instruction=AGENT_INSTRUCTION,
    tools=[
        tool_parse_request,
        tool_find_comparables,
        tool_evaluate_comparables,
        tool_synthesize_response,
    ],
)

runner = InMemoryRunner(agent=agent, app_name="agent_system_b")


# ═══════════════════════════════════════════════════════
# FASTAPI — HTTP endpoint for Agent System A
# ═══════════════════════════════════════════════════════

app = FastAPI(
    title="Agent System B — Property Analyzer",
    description="Independent Google ADK microservice for rental property analysis",
)


@app.post("/analyze", response_model=AgenticResponse)
async def analyze_property(request: AnalysisRequest):
    """Main endpoint called by Agent System A's Market Researcher.

    Runs the ReAct agent which orchestrates the 4-step pipeline:
    parse → find → evaluate → synthesize
    """
    logger.info(f"POST /analyze | location={request.location}, type={request.property_type}, beds={request.bedrooms}")
    # Initialize clean, request-scoped pipeline state (thread-local)
    _thread_local.state = {}

    # Build the query for the ReAct agent
    query = (
        f"Analyze rental properties: {request.property_type} "
        f"in {request.location}"
    )
    if request.bedrooms:
        query += f", {request.bedrooms} bedrooms"
    if request.budget_max:
        query += f", budget under AED {request.budget_max:,.0f}"
    if request.furnished:
        query += f", {request.furnished}"

    # Run the ReAct agent
    try:
        session = await runner.session_service.create_session(
            app_name="agent_system_b",
            user_id="system_a",
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        )

        # Let the agent run through all 4 steps
        final_response = None
        async for event in runner.run_async(
            user_id="system_a",
            session_id=session.id,
            new_message=user_message,
        ):
            if event.actions and event.actions.escalate:
                break
            if event.content and event.content.parts:
                final_response = event

        # Check if pipeline completed via the thread-local state
        state = _get_state()
        if "response" in state:
            logger.info("Agent completed full 4-step pipeline via ReAct loop")
            return state["response"]

        # Try parsing the agent's text output as fallback
        if final_response and final_response.content.parts:
            text = final_response.content.parts[0].text
            try:
                data = json.loads(text)
                return AgenticResponse(**data)
            except (json.JSONDecodeError, ValueError):
                pass
    except Exception as e:
        logger.warning(f"ReAct agent failed, falling back to direct pipeline | error={type(e).__name__}: {e}")

    # Fallback: run pipeline directly if agent fails
    logger.info("Running fallback direct pipeline (no LLM orchestration)")
    criteria = parse_request(request)
    comps = find_comps(criteria)
    evaluation = evaluate_comps(comps)
    return synthesize(evaluation)


@app.post("/chat")
async def chat(request: dict):
    """Free-text chat endpoint — direct conversation with Agent B's ADK agent.

    The ADK ReAct agent handles the conversation naturally:
    greetings, questions, and property analysis using its 4 tools.
    """
    query = request.get("query", "")
    sid = request.get("session_id", "chat-default")
    logger.info(f"POST /chat | session={sid} | query='{query[:80]}...'")

    # Initialize clean pipeline state for this request
    _thread_local.state = {}

    try:
        session = await runner.session_service.create_session(
            app_name="agent_system_b",
            user_id=sid,
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        )

        # Run the ADK agent — it decides whether to use tools or just respond
        final_text = ""
        async for event in runner.run_async(
            user_id=sid,
            session_id=session.id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

        # If the pipeline completed (agent used all 4 tools), format the structured response
        state = _get_state()
        if "response" in state:
            result = state["response"]
            response_text = (
                f"**Independent Valuation Report**\n\n"
                f"**Estimated Value:** AED {result.estimated_value:,.0f}/year\n"
                f"**Confidence:** {result.confidence_score}\n\n"
                f"**Reasoning:** {result.reasoning_chain}\n\n"
            )
            if result.supporting_comps:
                response_text += "**Comparable Properties:**\n"
                for comp in result.supporting_comps[:5]:
                    response_text += f"- {comp.get('address', 'N/A')} — AED {comp.get('rent', 0):,.0f}/yr (relevance: {comp.get('relevance_score', 0):.0%})\n"
            if result.adjustments_applied:
                response_text += f"\n**Adjustments:** {', '.join(result.adjustments_applied)}"
            return {"response": response_text, "session_id": sid}

        # Otherwise return the agent's natural text response (greetings, questions, etc.)
        return {"response": final_text or "I couldn't process that. Try asking about a specific property or area.", "session_id": sid}

    except Exception as e:
        logger.error(f"POST /chat failed | error={type(e).__name__}: {e}")
        return {"response": f"Sorry, something went wrong: {str(e)}", "session_id": sid}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "agent_system_b"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
