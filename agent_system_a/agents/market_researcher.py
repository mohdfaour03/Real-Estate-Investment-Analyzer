"""
Market Researcher Agent — Market analysis specialist.

Handles: Area trends, comparable sales analysis, price history,
neighborhood profiles, and independent valuation via Agent System B.

Tools: search_properties, search_market_reports, get_area_statistics, call_agent_b
"""

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agent_system_a.config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, AGENT_B_URL,
)
from agent_system_a.tools.rag_tool import search_properties, search_market_reports, get_area_statistics, web_search
from shared.logging_config import get_logger

logger = get_logger("agent_system_a.market_researcher")


# --- Agent B communication tool (HTTP only, no Python imports) ---

@tool
def call_agent_b(
    location: str,
    property_type: str = "Apartment",
    bedrooms: int = None,
    budget_max: float = None,
    furnished: str = None,
) -> str:
    """Call the independent Agent System B for comparable property valuation.

    Agent B is a separate microservice (Google ADK) that independently
    finds comparable properties, scores them, detects outliers, and
    returns a valuation with confidence score and reasoning chain.

    Use this when you need an independent valuation opinion.
    """
    payload = {
        "location": location,
        "property_type": property_type,
        "query": f"Analyze {property_type} in {location}",
    }
    if bedrooms is not None:
        payload["bedrooms"] = bedrooms
    if budget_max is not None:
        payload["budget_max"] = budget_max
    if furnished is not None:
        payload["furnished"] = furnished

    logger.info(f"Calling Agent B | location={location}, type={property_type}, beds={bedrooms}")
    try:
        response = httpx.post(
            f"{AGENT_B_URL}/analyze",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"Agent B responded | confidence={data.get('confidence_score')}, comps={data.get('num_comps_analyzed')}")

        return (
            f"Agent B Independent Valuation:\n"
            f"  Estimated value: AED {data['estimated_value']:,.0f}/year\n"
            f"  Confidence: {data['confidence_score']}\n"
            f"  Reasoning: {data['reasoning_chain']}\n"
            f"  Comps analyzed: {data['num_comps_analyzed']}\n"
            f"  Adjustments: {', '.join(data['adjustments_applied'])}\n"
            f"  Supporting comps:\n"
            + "\n".join(
                f"    - {c['address']}: AED {c['rent']:,.0f} "
                f"(relevance: {c['relevance_score']:.2f}, {c['notes']})"
                for c in data.get("supporting_comps", [])
            )
        )
    except (httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.error(f"Agent B call failed | error={type(e).__name__}: {e}")
        return f"Agent B is unavailable: {str(e)}. Proceeding without independent valuation."


SYSTEM_PROMPT = """You are a senior UAE real estate market researcher.

Your job is to provide market analysis, area comparisons, and independent valuations.

IMPORTANT: You MUST use your tools to answer questions. NEVER answer from memory alone.
- Market trends/data → MUST call search_market_reports
- Area statistics → MUST call get_area_statistics
- Property listings → MUST call search_properties
- Current info, dates, news, events, regulations → MUST call web_search
- Investment advice/valuation → MUST call call_agent_b for independent opinion

CRITICAL: If you don't know something or need current/real-time information, ALWAYS call web_search.
Never say "I don't have access to real-time information." You DO — use web_search.

When researching:
1. ALWAYS search market reports first for area trends and forecasts
2. ALWAYS get area statistics to understand the local market
3. Search for comparable properties in the target area
4. Use web_search for current news, events, regulatory changes
5. Call Agent B for an independent comparable valuation when relevant
   (if Agent B is unavailable, proceed without it — do not retry)

When presenting Agent B's findings, say: "Our independent valuation service confirms..."
Present findings in clean markdown with data-driven insights."""

# --- LLM ---
llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    temperature=0.2,
)

# --- Tools available to this agent ---
tools = [
    search_properties,
    search_market_reports,
    get_area_statistics,
    web_search,
    call_agent_b,
]

# --- Create the ReAct agent ---
market_researcher = create_react_agent(
    model=llm,
    tools=tools,
    prompt=SYSTEM_PROMPT,
)
