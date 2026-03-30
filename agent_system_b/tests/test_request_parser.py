"""Tests for request parser — pure function, no external dependencies."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.request_parser import AnalysisRequest, ParsedCriteria, parse_request


class TestParseRequest:
    """Validates that AnalysisRequest is correctly transformed to ParsedCriteria."""

    def test_basic_request(self):
        req = AnalysisRequest(location="Dubai Marina", property_type="Apartment")
        result = parse_request(req)
        assert isinstance(result, ParsedCriteria)
        assert result.location == "Dubai Marina"
        assert result.property_type == "Apartment"

    def test_full_request(self):
        req = AnalysisRequest(
            location="JVC",
            property_type="Villa",
            bedrooms=3,
            budget_max=150_000,
            furnished="Furnished",
        )
        result = parse_request(req)
        assert result.bedrooms == 3
        assert result.budget_max == 150_000
        assert result.furnished == "Furnished"

    def test_search_strategy_includes_location(self):
        """Search strategy string should mention the location."""
        req = AnalysisRequest(location="Business Bay")
        result = parse_request(req)
        assert "Business Bay" in result.search_strategy

    def test_search_strategy_includes_bedrooms(self):
        """Search strategy should mention bedroom count when provided."""
        req = AnalysisRequest(location="Downtown", bedrooms=2)
        result = parse_request(req)
        assert "2" in result.search_strategy

    def test_search_strategy_includes_budget(self):
        """Search strategy should mention budget when provided."""
        req = AnalysisRequest(location="JBR", budget_max=120_000)
        result = parse_request(req)
        assert "120" in result.search_strategy

    def test_optional_fields_default_none(self):
        """Optional fields default to None when not provided."""
        req = AnalysisRequest(location="Sharjah")
        result = parse_request(req)
        assert result.bedrooms is None
        assert result.budget_max is None
        assert result.furnished is None

    def test_default_property_type(self):
        """Property type defaults to 'Apartment'."""
        req = AnalysisRequest(location="Dubai Marina")
        assert req.property_type == "Apartment"
        result = parse_request(req)
        assert result.property_type == "Apartment"


class TestAnalysisRequestModel:
    """Validates the Pydantic model itself."""

    def test_required_field_location(self):
        """Location is required."""
        with pytest.raises(Exception):
            AnalysisRequest()  # missing location

    def test_optional_query_field(self):
        req = AnalysisRequest(location="Dubai", query="Find me cheap apartments")
        assert req.query == "Find me cheap apartments"
