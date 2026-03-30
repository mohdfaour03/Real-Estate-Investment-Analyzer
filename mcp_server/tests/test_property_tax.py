"""Tests for the property tax estimator — emirate-specific rates, no external deps."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.property_tax_estimator import estimate_property_tax


class TestEstimatePropertyTax:
    """Validates emirate-specific tax calculations against known rates."""

    # ── Dubai (5% housing, 0.5% municipality, 4% registration) ──

    def test_dubai_housing_fee(self):
        result = estimate_property_tax(100_000, 1_500_000, "dubai")
        assert result["housing_fee"] == 5_000  # 5% of 100K rent

    def test_dubai_municipality_fee(self):
        result = estimate_property_tax(100_000, 1_500_000, "dubai")
        # Dubai municipality fee is 0% (no municipality fee on residential rentals)
        assert result["municipality_fee"] == 0

    def test_dubai_registration_fee(self):
        result = estimate_property_tax(100_000, 1_500_000, "dubai")
        assert result["registration_fee_one_time"] == 60_000  # 4% of 1.5M value

    def test_dubai_total_annual_fees(self):
        result = estimate_property_tax(100_000, 1_500_000, "dubai")
        assert result["total_annual_fees"] == 5_000  # housing only (5% of 100K)

    def test_dubai_net_rental_income(self):
        result = estimate_property_tax(100_000, 1_500_000, "dubai")
        assert result["net_rental_income"] == 95_000  # 100K - 5K fees

    # ── Abu Dhabi (3% housing, 0% municipality, 2% registration) ──

    def test_abu_dhabi_rates(self):
        result = estimate_property_tax(80_000, 1_000_000, "abu dhabi")
        assert result["housing_fee"] == 2_400       # 3% of 80K
        assert result["municipality_fee"] == 0       # 0%
        assert result["registration_fee_one_time"] == 20_000  # 2% of 1M

    # ── Sharjah (2% housing, 0% municipality, 2% registration) ──

    def test_sharjah_rates(self):
        result = estimate_property_tax(60_000, 800_000, "sharjah")
        assert result["housing_fee"] == 1_200        # 2% of 60K
        assert result["municipality_fee"] == 0       # 0%
        assert result["registration_fee_one_time"] == 16_000  # 2% of 800K

    # ── Case insensitivity ──

    def test_case_insensitive_emirate(self):
        """Emirate name should be case-insensitive."""
        result_lower = estimate_property_tax(100_000, 1_000_000, "dubai")
        result_upper = estimate_property_tax(100_000, 1_000_000, "Dubai")
        result_mixed = estimate_property_tax(100_000, 1_000_000, "DUBAI")
        assert result_lower["housing_fee"] == result_upper["housing_fee"] == result_mixed["housing_fee"]

    # ── Unknown emirate falls back to defaults ──

    def test_unknown_emirate_uses_defaults(self):
        """Unknown emirate should use default rates (2% housing, 0% municipality, 2% registration)."""
        result = estimate_property_tax(100_000, 1_000_000, "fujairah")
        assert result["housing_fee"] == 2_000        # 2% default
        assert result["municipality_fee"] == 0       # 0% default

    # ── Effective tax rate ──

    def test_effective_tax_rate(self):
        """Effective tax rate = total_annual_fees / annual_rent × 100."""
        result = estimate_property_tax(200_000, 3_000_000, "dubai")
        expected_rate = (result["total_annual_fees"] / 200_000) * 100
        assert result["effective_tax_rate_pct"] == pytest.approx(expected_rate, rel=0.01)

    # ── Output fields present ──

    def test_all_required_fields_present(self):
        result = estimate_property_tax(100_000, 1_500_000, "dubai")
        required = ["emirate", "annual_rent", "property_value", "housing_fee",
                     "municipality_fee", "total_annual_fees", "registration_fee_one_time",
                     "net_rental_income", "effective_tax_rate_pct", "notes"]
        for field in required:
            assert field in result, f"Missing field: {field}"
