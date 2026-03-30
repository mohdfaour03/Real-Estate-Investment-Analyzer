"""
Supervisor Agent — Orchestrates the multi-agent workflow.

Analyzes user intent, routes to the right specialist(s),
and synthesizes their outputs into a final recommendation.

Routing logic:
  - Financial queries (ROI, yield, mortgage) → Property Analyst
  - Market queries (trends, comparisons, areas) → Market Researcher
  - Complex queries (investment decisions) → Both specialists
"""

from concurrent.futures import ThreadPoolExecutor

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from typing import Annotated
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing import Literal

from agent_system_a.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL
from agent_system_a.agents.property_analyst import property_analyst
from agent_system_a.agents.market_researcher import market_researcher
from shared.logging_config import get_logger

logger = get_logger("agent_system_a.supervisor")


# --- Graph state — extends MessagesState with route tracking for status events ---
class SupervisorState(MessagesState):
    route: str = ""
    status: str = ""


# --- Supervisor LLM ---
llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    temperature=0.1,
)


# --- Structured output for routing decisions ---
class RouteDecision(BaseModel):
    """The supervisor's routing decision."""
    route: Literal["property_analyst", "market_researcher", "both", "direct"] = Field(
        description="Which agent should handle this query",
    )
    summary: str = Field(
        description="3-4 word status of what you're about to do, e.g. 'Searching Dubai apartments...'",
    )

router_llm = llm.with_structured_output(RouteDecision, method="function_calling")


ROUTER_PROMPT = """You are a supervisor routing real estate queries to specialist agents.

Given the user's message (and any prior conversation for context), decide who should handle it:

- "property_analyst" — for ANY query about specific properties or financial analysis.
  Includes: property search, find/suggest listings, budget-based filtering, area-specific
  property requests, ROI, rental yield, cap rate, mortgage, cash flow, property tax.
  Examples: "properties under 100k in Sharjah", "find me a 2-bed apartment", "what's the yield?"
- "market_researcher" — for market-level analysis: area trends, comparable sales,
  neighborhood profiles, price history, area comparisons, market outlook.
  Examples: "how is Dubai Marina performing?", "compare JBR vs Downtown"
- "both" — for complex investment decisions that need BOTH financial analysis
  AND market research (e.g., "Should I invest in Dubai Marina?", "Best areas for 8% yield")
- "direct" — ONLY for simple greetings (hi, hello) and pure small talk.

IMPORTANT RULES:
- If the query mentions ANY property, area, price, budget, rent, or real estate term → route to a specialist, NEVER to "direct".
- If the query asks about current events, news, regulations → route to "market_researcher" (it has web_search).
- NEVER answer factual questions via "direct" — always route to a specialist who can use tools."""

DIRECT_PROMPT = """You are a friendly real estate investment assistant specializing in the UAE rental market.
The user sent a general message (greeting, clarification, or off-topic question).
Respond naturally and briefly. If relevant, mention that you can help with property search,
financial analysis, market comparisons, mortgage calculations, and area insights."""


def _messages_to_chat_history(messages):
    """Convert LangGraph messages (LangChain objects or raw dicts) to OpenAI-format dicts."""
    history = []
    for msg in messages:
        role = getattr(msg, "type", None)
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        else:
            role = msg.get("role", "user") if isinstance(msg, dict) else "user"
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if content:
            history.append({"role": role, "content": content})
    return history


def route_query(state: MessagesState) -> Command[Literal["property_analyst", "market_researcher", "both", "direct"]]:
    """Supervisor decides which specialist(s) to invoke."""
    history = [{"role": "system", "content": ROUTER_PROMPT}]
    history.extend(_messages_to_chat_history(state["messages"]))

    decision = router_llm.invoke(history)
    user_msg = state["messages"][-1].content if state["messages"] else "<empty>"
    logger.info(f"Routing query to '{decision.route}' | status='{decision.summary}' | query='{user_msg[:80]}...'")
    return Command(goto=decision.route, update={"route": decision.route, "status": decision.summary})


def run_direct(state: MessagesState):
    """Supervisor handles the query directly — no specialist agents needed."""
    logger.info("Handling query directly (greeting/off-topic)")
    history = [{"role": "system", "content": DIRECT_PROMPT}]
    history.extend(_messages_to_chat_history(state["messages"]))

    response = llm.invoke(history)
    logger.info(f"Direct response generated | length={len(response.content)} chars")
    return {"messages": [response]}


def run_property_analyst(state: MessagesState):
    """Run the Property Analyst agent."""
    result = property_analyst.invoke(state)
    return result


def run_market_researcher(state: MessagesState):
    """Run the Market Researcher agent."""
    result = market_researcher.invoke(state)
    return result


SYNTHESIS_PROMPT = """You are synthesizing responses from two specialist agents into one cohesive answer.

Combine the Property Analyst's financial analysis with the Market Researcher's market insights
into a single, well-structured response using markdown formatting.
Do not mention that you are combining two sources — present the information as one unified expert analysis.

**Property Analyst's findings:**
{pa_content}

**Market Researcher's findings:**
{mr_content}"""


def _extract_final_content(messages):
    """Extract the last AI message content from a message list."""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return msg.content
    return "No analysis available."


def run_both(state: MessagesState):
    """Run both specialists in parallel, then synthesize a single unified response."""
    logger.info("Running both specialists in parallel")
    with ThreadPoolExecutor(max_workers=2) as pool:
        pa_future = pool.submit(property_analyst.invoke, state)
        mr_future = pool.submit(market_researcher.invoke, state)
        pa_result = pa_future.result()
        mr_result = mr_future.result()

    pa_content = _extract_final_content(pa_result["messages"])
    mr_content = _extract_final_content(mr_result["messages"])
    logger.info(f"Both agents done | PA={len(pa_content)} chars, MR={len(mr_content)} chars | synthesizing...")

    user_query = state["messages"][-1].content

    # Synthesize — tagged "synthesis" so the stream handler can filter intermediate agent tokens
    synthesis = llm.invoke(
        [
            {"role": "system", "content": SYNTHESIS_PROMPT.format(
                pa_content=pa_content, mr_content=mr_content,
            )},
            {"role": "user", "content": user_query},
        ],
        config={"tags": ["synthesis"]},
    )

    return {"messages": [synthesis]}


# --- Build the supervisor graph ---
workflow = StateGraph(SupervisorState)

# Add nodes
workflow.add_node("router", route_query)
workflow.add_node("direct", run_direct)
workflow.add_node("property_analyst", run_property_analyst)
workflow.add_node("market_researcher", run_market_researcher)
workflow.add_node("both", run_both)

# Add edges
workflow.add_edge(START, "router")
workflow.add_edge("direct", END)
workflow.add_edge("property_analyst", END)
workflow.add_edge("market_researcher", END)
workflow.add_edge("both", END)

# Compile the graph
# recursion_limit is passed at invocation time (.invoke(input, config={"recursion_limit": 25}))
# to cap total node executions and prevent infinite loops
supervisor = workflow.compile()
