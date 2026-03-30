"""Property tax estimator tool for UAE emirates."""

from mcp_server.config import TAX_RATES, DEFAULT_TAX_RATES


def estimate_property_tax(
    annual_rent: float,
    property_value: float,
    emirate: str = "dubai",
) -> dict:
    """Estimate annual property-related fees for a UAE rental property.

    Args:
        annual_rent: Annual rental income in AED.
        property_value: Total property market value in AED.
        emirate: UAE emirate name (dubai, abu dhabi, sharjah, etc.).

    Returns:
        Dictionary with fee breakdown: housing fee, registration fee, net rental income.
    """
    # Input validation — catch nonsensical values before they cause math errors
    if annual_rent < 0:
        return {"error": "Annual rent cannot be negative."}
    if property_value <= 0:
        return {"error": "Property value must be a positive number."}

    # Lookup rates for the given emirate
    emirate_key = emirate.lower().strip()
    rates = TAX_RATES.get(emirate_key, DEFAULT_TAX_RATES)

    # Calculate fees
    housing_fee = annual_rent * (rates["housing_fee"] / 100)
    municipality_fee = annual_rent * (rates["municipality_fee"] / 100)
    registration_fee = property_value * (rates["registration_fee"] / 100)

    total_annual_fees = housing_fee + municipality_fee
    net_rental_income = annual_rent - total_annual_fees
    effective_tax_rate = (total_annual_fees / annual_rent * 100) if annual_rent > 0 else 0

    return {
        "emirate": emirate.title(),
        "annual_rent": round(annual_rent, 2),
        "property_value": round(property_value, 2),
        "housing_fee": round(housing_fee, 2),
        "municipality_fee": round(municipality_fee, 2),
        "total_annual_fees": round(total_annual_fees, 2),
        "registration_fee_one_time": round(registration_fee, 2),
        "net_rental_income": round(net_rental_income, 2),
        "effective_tax_rate_pct": round(effective_tax_rate, 1),
        "notes": (
            f"Housing fee is {rates['housing_fee']}% of annual rent in {emirate.title()}. "
            f"Registration fee ({rates['registration_fee']}% of property value) "
            f"is a one-time cost paid at purchase."
        ),
    }
