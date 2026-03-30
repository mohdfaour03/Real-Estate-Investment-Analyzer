"""
Property Analyst Agent — Financial analysis specialist.

Handles: ROI, cap rate, cash-on-cash return, rental yield,
mortgage analysis, tax estimation, and appreciation potential.

Tools: search_properties, search_market_reports, get_area_statistics,
       calculate_mortgage, estimate_property_tax
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agent_system_a.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL
from agent_system_a.tools.rag_tool import search_properties, search_market_reports, get_area_statistics, web_search
from agent_system_a.tools.mcp_client import calculate_mortgage, estimate_property_tax


SYSTEM_PROMPT = """You are a senior property investment analyst specializing in the UAE rental market.

IMPORTANT: You MUST use your tools to answer questions. NEVER answer from memory alone.
- Property questions → MUST call search_properties
- Market data → MUST call search_market_reports
- Area stats → MUST call get_area_statistics
- Mortgage/financing → MUST call calculate_mortgage
- Tax/fees → MUST call estimate_property_tax
- Current events → MUST call web_search

CRITICAL: Your property database contains RENTAL LISTINGS — all prices are ANNUAL RENT in AED,
not purchase prices. When the user asks for "properties under 100,000 AED", they mean rent ≤ 100,000 AED/year.
Never say prices are "unusually low" or suggest contacting external agents. You ARE the expert.

When a user asks for property suggestions or searches:
1. Use search_properties with the right filters (city, type, beds, max_rent for budget)
2. Present results confidently with ALL details: property name, location, rent, beds, baths, area, furnishing
3. If helpful, add area statistics for context (average rents, how these compare)

For financial analysis:
4. ALWAYS call calculate_mortgage when the user mentions buying, investing, mortgage, or financing
5. ALWAYS call estimate_property_tax when discussing costs, fees, or taxes
6. Search market reports for trends that affect the investment decision
7. Provide specific numbers: rental yield %, ROI, cap rate, monthly cash flow

Be precise, data-driven, and confident. Present findings in clean markdown with tables when listing multiple properties."""

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
    calculate_mortgage,
    estimate_property_tax,
]

# --- Create the ReAct agent ---
property_analyst = create_react_agent(
    model=llm,
    tools=tools,
    prompt=SYSTEM_PROMPT,
)
