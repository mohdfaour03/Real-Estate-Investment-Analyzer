"""
MCP Server — Financial analysis tools for UAE real estate.

Implements the Model Context Protocol (MCP) using fastmcp.
Exposes two tools over SSE transport so Agent System A can connect
as a proper MCP client:
  1. mortgage_calculator  — Loan payments, total cost, DTI assessment
  2. property_tax_estimator — Annual fees by emirate, net rental income

This is a REAL MCP server — not a REST API wrapper. Agent System A
connects via SSE and invokes tools through the MCP protocol.
"""

from fastmcp import FastMCP

from mcp_server.tools.mortgage_calculator import calculate_mortgage as _calculate_mortgage
from mcp_server.tools.property_tax_estimator import estimate_property_tax as _estimate_property_tax
from mcp_server.config import HOST, PORT
from shared.logging_config import get_logger

logger = get_logger("mcp_server")


# ── FastMCP server instance ──

mcp = FastMCP(
    name="Real Estate MCP Server",
    instructions=(
        "Financial analysis tools for UAE real estate investment. "
        "Use mortgage_calculator for loan payment breakdowns and "
        "property_tax_estimator for emirate-specific fee estimates."
    ),
)


# ── MCP Tools ──
# The @mcp.tool() decorator registers these with the MCP protocol.
# fastmcp auto-generates the JSON schema from the type hints + docstring.

@mcp.tool()
def mortgage_calculator(
    property_price: float,
    down_payment_pct: float = 20.0,
    annual_rate: float = 4.5,
    loan_years: int = 25,
) -> dict:
    """Calculate mortgage payment details for a UAE property purchase.

    Args:
        property_price: Total property price in AED.
        down_payment_pct: Down payment as percentage (default 20%% — UAE minimum for expats).
        annual_rate: Annual interest rate as percentage (default 4.5%% — typical UAE mortgage).
        loan_years: Loan duration in years (default 25 — UAE max for expats).

    Returns:
        Loan breakdown with monthly payment, total cost, interest, and DTI assessment.
    """
    logger.info(f"mortgage_calculator called | price={property_price:,.0f}, down={down_payment_pct}%, rate={annual_rate}%")
    result = _calculate_mortgage(property_price, down_payment_pct, annual_rate, loan_years)
    logger.info(f"mortgage_calculator done | monthly={result['monthly_payment']:,.0f} AED")
    return result


@mcp.tool()
def property_tax_estimator(
    annual_rent: float,
    property_value: float,
    emirate: str = "dubai",
) -> dict:
    """Estimate annual property-related fees and taxes for a UAE rental property.

    Args:
        annual_rent: Annual rental income in AED.
        property_value: Total property market value in AED.
        emirate: UAE emirate name (dubai, abu dhabi, sharjah, ajman, ras al khaimah).

    Returns:
        Fee breakdown with housing fee, registration fee, net rental income, effective tax rate.
    """
    logger.info(f"property_tax_estimator called | rent={annual_rent:,.0f}, value={property_value:,.0f}, emirate={emirate}")
    result = _estimate_property_tax(annual_rent, property_value, emirate)
    logger.info(f"property_tax_estimator done | effective_rate={result['effective_tax_rate_pct']}%")
    return result


# ── Entry point ──
# SSE transport makes this accessible over HTTP at /sse for MCP clients.

if __name__ == "__main__":
    mcp.run(transport="sse", host=HOST, port=PORT)
