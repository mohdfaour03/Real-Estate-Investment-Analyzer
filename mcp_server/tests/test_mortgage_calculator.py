"""Tests for the mortgage calculator — pure math, no external dependencies."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.mortgage_calculator import calculate_mortgage


class TestCalculateMortgage:
    """Validates the amortization formula and UAE-specific defaults."""

    def test_basic_calculation(self):
        """Standard case: AED 1M property, 20% down, 4.5% rate, 25yr."""
        result = calculate_mortgage(1_000_000)
        assert result["property_price"] == 1_000_000
        assert result["down_payment"] == 200_000      # 20% of 1M
        assert result["loan_amount"] == 800_000        # 80% of 1M
        assert result["annual_rate"] == 4.5
        assert result["loan_years"] == 25
        # Monthly payment should be ~AED 4,445 for 800K loan at 4.5%/25yr
        assert 4_400 < result["monthly_payment"] < 4_500

    def test_down_payment_percentage(self):
        """Custom down payment: 30% on AED 2M property."""
        result = calculate_mortgage(2_000_000, down_payment_pct=30.0)
        assert result["down_payment"] == 600_000
        assert result["loan_amount"] == 1_400_000

    def test_total_cost_exceeds_loan(self):
        """Total cost must always exceed the loan amount (interest adds up)."""
        result = calculate_mortgage(1_500_000)
        assert result["total_cost"] > result["loan_amount"]
        assert result["total_interest"] > 0
        assert result["total_cost"] == pytest.approx(
            result["loan_amount"] + result["total_interest"], rel=0.01
        )

    def test_dti_assessment_healthy(self):
        """Low-cost property should yield Healthy DTI (<30%)."""
        # AED 500K property, 20% down = 400K loan → ~AED 2,222/month
        # DTI vs assumed 25K income = ~8.9%
        result = calculate_mortgage(500_000)
        assert "Healthy" in result["dti_assessment"]
        assert result["estimated_dti_pct"] < 30

    def test_dti_assessment_moderate(self):
        """Mid-cost property should yield Moderate DTI (30-40%)."""
        # AED 2M property, 20% down = 1.6M loan → ~AED 8,890/month
        # DTI vs assumed 25K income = ~35.6%
        result = calculate_mortgage(2_000_000)
        assert "Moderate" in result["dti_assessment"]

    def test_dti_assessment_high_risk(self):
        """Expensive property should yield High risk DTI (>40%)."""
        # AED 3M property, 20% down = 2.4M loan → ~AED 13,335/month
        # DTI vs assumed 25K income = ~53%
        result = calculate_mortgage(3_000_000)
        assert "High" in result["dti_assessment"]

    def test_custom_rate_and_term(self):
        """Non-default rate (6%) and term (15yr)."""
        result = calculate_mortgage(1_000_000, annual_rate=6.0, loan_years=15)
        assert result["annual_rate"] == 6.0
        assert result["loan_years"] == 15
        # Shorter term + higher rate = higher monthly but less total interest
        standard = calculate_mortgage(1_000_000)
        assert result["monthly_payment"] > standard["monthly_payment"]
        assert result["total_interest"] < standard["total_interest"]

    def test_zero_down_payment(self):
        """Edge case: 0% down payment (full financing)."""
        result = calculate_mortgage(1_000_000, down_payment_pct=0)
        assert result["down_payment"] == 0
        assert result["loan_amount"] == 1_000_000

    def test_all_values_rounded(self):
        """All monetary values should be rounded to 2 decimal places."""
        result = calculate_mortgage(1_234_567)
        for key in ["down_payment", "loan_amount", "monthly_payment",
                     "total_cost", "total_interest"]:
            val = result[key]
            assert val == round(val, 2), f"{key} not rounded: {val}"
