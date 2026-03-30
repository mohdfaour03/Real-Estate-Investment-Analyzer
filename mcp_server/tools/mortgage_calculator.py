"""Mortgage calculator tool for UAE property investment analysis."""


def calculate_mortgage(
    property_price: float,
    down_payment_pct: float = 20.0,
    annual_rate: float = 4.5,
    loan_years: int = 25,
) -> dict:
    """Calculate mortgage details for a UAE property purchase.

    Args:
        property_price: Total property price in AED.
        down_payment_pct: Down payment as percentage (default 20% — UAE minimum for expats).
        annual_rate: Annual interest rate as percentage (default 4.5% — typical UAE mortgage).
        loan_years: Loan duration in years (default 25 — UAE max for expats).

    Returns:
        Dictionary with loan breakdown: monthly payment, total cost, total interest, DTI estimate.
    """
    # Input validation — catch nonsensical values before they cause math errors
    if property_price <= 0:
        return {"error": "Property price must be a positive number."}
    if not (0 <= down_payment_pct < 100):
        return {"error": "Down payment percentage must be between 0 (inclusive) and 100 (exclusive)."}
    if annual_rate < 0 or annual_rate > 30:
        return {"error": "Annual interest rate must be between 0% and 30%."}
    if loan_years < 1 or loan_years > 35:
        return {"error": "Loan duration must be between 1 and 35 years."}

    # Core calculations
    down_payment = property_price * (down_payment_pct / 100)
    loan_amount = property_price - down_payment
    monthly_rate = (annual_rate / 100) / 12
    num_payments = loan_years * 12

    # Standard amortization formula
    if monthly_rate > 0:
        monthly_payment = loan_amount * (
            monthly_rate * (1 + monthly_rate) ** num_payments
        ) / ((1 + monthly_rate) ** num_payments - 1)
    else:
        monthly_payment = loan_amount / num_payments

    total_cost = monthly_payment * num_payments
    total_interest = total_cost - loan_amount

    # DTI estimate (assumes average UAE expat salary of AED 25,000/month)
    estimated_monthly_income = 25_000
    dti_ratio = (monthly_payment / estimated_monthly_income) * 100

    return {
        "property_price": round(property_price, 2),
        "down_payment": round(down_payment, 2),
        "down_payment_pct": down_payment_pct,
        "loan_amount": round(loan_amount, 2),
        "annual_rate": annual_rate,
        "loan_years": loan_years,
        "monthly_payment": round(monthly_payment, 2),
        "total_cost": round(total_cost, 2),
        "total_interest": round(total_interest, 2),
        "estimated_dti_pct": round(dti_ratio, 1),
        "dti_assessment": (
            "Healthy (under 30%)" if dti_ratio < 30
            else "Moderate (30-40%)" if dti_ratio < 40
            else "High risk (over 40%)"
        ),
    }
