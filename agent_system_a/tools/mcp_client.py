"""
MCP Client Tools — Connects to the MCP Server via the Model Context Protocol.

The Property Analyst agent uses these for financial calculations.
These tools connect to the MCP Server using SSE transport and invoke
tools through the standard MCP protocol — not plain HTTP REST.

Flow: Agent calls tool → _run_async bridges to async →
      opens SSE connection → MCP handshake → call_tool → parse response →
      return formatted string to agent.
"""

import asyncio
import json
import concurrent.futures
from langchain_core.tools import StructuredTool
from mcp.client.sse import sse_client
from mcp import ClientSession
from pydantic import BaseModel, Field

from agent_system_a.config import MCP_SERVER_URL
from shared.logging_config import get_logger

logger = get_logger("agent_system_a.mcp_client")

# Reusable thread pool — avoids creating a new pool per MCP call
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


# ── MCP protocol helper ──

async def _call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Open an SSE connection to the MCP server and invoke a tool.

    This is the real MCP protocol in action:
      1. Connect via SSE to the MCP server
      2. Initialize the MCP session (capability negotiation)
      3. Call the named tool with arguments
      4. Parse the JSON response from the tool result
    """
    sse_url = f"{MCP_SERVER_URL}/sse"
    async with sse_client(sse_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return json.loads(result.content[0].text)


def _run_async(coro):
    """Run an async coroutine from a sync context.

    LangGraph's tool node calls tools synchronously even inside an async app.
    This bridges that gap by running the coroutine on the module-level thread pool.
    """
    return _executor.submit(asyncio.run, coro).result()


# ── Tool input schemas ──

class MortgageInput(BaseModel):
    property_price: float = Field(description="Total property price in AED")
    down_payment_pct: float = Field(default=20.0, description="Down payment percentage (default 20%)")
    annual_rate: float = Field(default=4.5, description="Annual interest rate percentage (default 4.5%)")
    loan_years: int = Field(default=25, description="Loan duration in years (default 25)")


class TaxInput(BaseModel):
    annual_rent: float = Field(description="Annual rental income in AED")
    property_value: float = Field(description="Total property market value in AED")
    emirate: str = Field(default="dubai", description="UAE emirate name")


# ── Sync implementations (call MCP via _run_async bridge) ──

def _calculate_mortgage_impl(
    property_price: float,
    down_payment_pct: float = 20.0,
    annual_rate: float = 4.5,
    loan_years: int = 25,
) -> str:
    logger.info(f"calculate_mortgage called | price={property_price:,.0f} AED, down={down_payment_pct}%, rate={annual_rate}%")
    try:
        data = _run_async(_call_mcp_tool("mortgage_calculator", {
            "property_price": property_price,
            "down_payment_pct": down_payment_pct,
            "annual_rate": annual_rate,
            "loan_years": loan_years,
        }))
        logger.info(f"Mortgage calculated | monthly={data['monthly_payment']:,.0f} AED, DTI={data['estimated_dti_pct']}%")
    except Exception as e:
        logger.error(f"MCP mortgage_calculator failed | error={type(e).__name__}: {e}")
        return "MCP mortgage calculator is unavailable. Please try again later."

    return (
        f"Mortgage Calculation:\n"
        f"  Property price: AED {data['property_price']:,.0f}\n"
        f"  Down payment: AED {data['down_payment']:,.0f} ({data['down_payment_pct']}%)\n"
        f"  Loan amount: AED {data['loan_amount']:,.0f}\n"
        f"  Rate: {data['annual_rate']}% | Term: {data['loan_years']} years\n"
        f"  Monthly payment: AED {data['monthly_payment']:,.0f}\n"
        f"  Total cost: AED {data['total_cost']:,.0f}\n"
        f"  Total interest: AED {data['total_interest']:,.0f}\n"
        f"  DTI ratio: {data['estimated_dti_pct']}% — {data['dti_assessment']}"
    )


def _estimate_property_tax_impl(
    annual_rent: float,
    property_value: float,
    emirate: str = "dubai",
) -> str:
    logger.info(f"estimate_property_tax called | rent={annual_rent:,.0f} AED, value={property_value:,.0f} AED, emirate={emirate}")
    try:
        data = _run_async(_call_mcp_tool("property_tax_estimator", {
            "annual_rent": annual_rent,
            "property_value": property_value,
            "emirate": emirate,
        }))
        logger.info(f"Tax estimated | effective_rate={data['effective_tax_rate_pct']}%, net_income={data['net_rental_income']:,.0f} AED")
    except Exception as e:
        logger.error(f"MCP property_tax_estimator failed | error={type(e).__name__}: {e}")
        return "MCP property tax estimator is unavailable. Please try again later."

    return (
        f"Property Tax Estimate ({data['emirate']}):\n"
        f"  Annual rent: AED {data['annual_rent']:,.0f}\n"
        f"  Housing fee: AED {data['housing_fee']:,.0f}\n"
        f"  Municipality fee: AED {data['municipality_fee']:,.0f}\n"
        f"  Total annual fees: AED {data['total_annual_fees']:,.0f}\n"
        f"  Registration fee (one-time): AED {data['registration_fee_one_time']:,.0f}\n"
        f"  Net rental income: AED {data['net_rental_income']:,.0f}\n"
        f"  Effective tax rate: {data['effective_tax_rate_pct']}%\n"
        f"  Note: {data['notes']}"
    )


# ── StructuredTool instances (sync-compatible for LangGraph's tool node) ──

calculate_mortgage = StructuredTool.from_function(
    func=_calculate_mortgage_impl,
    name="calculate_mortgage",
    description=(
        "Calculate mortgage payment details for a UAE property. "
        "Returns monthly payment, total cost, total interest, and DTI assessment. "
        "Default values: 20% down payment, 4.5% rate, 25-year term (UAE standard for expats)."
    ),
    args_schema=MortgageInput,
)

estimate_property_tax = StructuredTool.from_function(
    func=_estimate_property_tax_impl,
    name="estimate_property_tax",
    description=(
        "Estimate annual property-related fees and taxes for a UAE property. "
        "Returns housing fee, registration fee, net rental income, and effective tax rate."
    ),
    args_schema=TaxInput,
)
