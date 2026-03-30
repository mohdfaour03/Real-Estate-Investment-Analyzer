"""Tests for RAG tools — search_properties and get_area_statistics use pandas (mock CSV).
search_market_reports and web_search need external service mocks.

Uses importlib to defer module loading until after mocks are in place."""
import pytest
import sys, os
import importlib
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# Sample DataFrame that mimics the real CSV structure
MOCK_DF = pd.DataFrame([
    {"Address": "Tower A, Dubai Marina", "City": "Dubai", "Location": "Dubai Marina",
     "Type": "Apartment", "Beds": 2, "Baths": 2, "Rent": 95000, "Area_in_sqft": 1200,
     "Rent_per_sqft": 79.17, "Furnishing": "Unfurnished", "Rent_category": "Medium"},
    {"Address": "Tower B, Dubai Marina", "City": "Dubai", "Location": "Dubai Marina",
     "Type": "Apartment", "Beds": 2, "Baths": 2, "Rent": 110000, "Area_in_sqft": 1400,
     "Rent_per_sqft": 78.57, "Furnishing": "Furnished", "Rent_category": "Medium"},
    {"Address": "Villa C, JVC", "City": "Dubai", "Location": "JVC",
     "Type": "Villa", "Beds": 3, "Baths": 3, "Rent": 150000, "Area_in_sqft": 2500,
     "Rent_per_sqft": 60.0, "Furnishing": "Unfurnished", "Rent_category": "High"},
    {"Address": "Studio D, Sharjah", "City": "Sharjah", "Location": "Al Nahda",
     "Type": "Apartment", "Beds": 0, "Baths": 1, "Rent": 25000, "Area_in_sqft": 400,
     "Rent_per_sqft": 62.5, "Furnishing": "Unfurnished", "Rent_category": "Low"},
    {"Address": "Apt E, Business Bay", "City": "Dubai", "Location": "Business Bay",
     "Type": "Apartment", "Beds": 1, "Baths": 1, "Rent": 75000, "Area_in_sqft": 800,
     "Rent_per_sqft": 93.75, "Furnishing": "Furnished", "Rent_category": "Medium"},
])


@pytest.fixture(scope="module")
def rag_tools():
    """Import the rag_tool module with mocked heavy dependencies (Qdrant, OpenAI, CSV).
    This prevents connection errors during test collection and ensures
    the mock DataFrame is used instead of the real 73K-row CSV."""
    with patch.dict("sys.modules", {}):
        # Patch module-level heavy initializations before import
        with patch("pandas.read_csv", return_value=MOCK_DF), \
             patch("qdrant_client.QdrantClient", return_value=MagicMock()), \
             patch("openai.OpenAI", return_value=MagicMock()):
            # Force fresh import with mocks active
            if "tools.rag_tool" in sys.modules:
                del sys.modules["tools.rag_tool"]
            mod = importlib.import_module("tools.rag_tool")
            # Ensure the df is our mock
            mod.df = MOCK_DF
            return mod


class TestSearchProperties:
    """Tests structured property search via pandas filtering."""

    def test_filter_by_city(self, rag_tools):
        result = rag_tools.search_properties.invoke({"city": "Dubai"})
        assert "Dubai" in result
        assert "Studio D" not in result  # Sharjah

    def test_filter_by_bedrooms(self, rag_tools):
        result = rag_tools.search_properties.invoke({"bedrooms": 2})
        assert "Tower A" in result or "Tower B" in result
        assert "Villa C" not in result  # 3 beds

    def test_filter_by_max_rent(self, rag_tools):
        result = rag_tools.search_properties.invoke({"max_rent": 100000})
        assert "Tower A" in result  # 95K
        assert "Tower B" not in result  # 110K

    def test_filter_by_min_rent(self, rag_tools):
        result = rag_tools.search_properties.invoke({"min_rent": 100000})
        assert "Tower B" in result or "Villa C" in result
        assert "Studio D" not in result  # 25K

    def test_filter_by_location(self, rag_tools):
        result = rag_tools.search_properties.invoke({"location": "Dubai Marina"})
        assert "Tower A" in result

    def test_filter_by_property_type(self, rag_tools):
        result = rag_tools.search_properties.invoke({"property_type": "Villa"})
        assert "Villa C" in result
        assert "Tower A" not in result

    def test_filter_by_furnished(self, rag_tools):
        result = rag_tools.search_properties.invoke({"furnished": "Furnished"})
        assert "Tower B" in result  # Furnished
        assert "Furnished" in result

    def test_combined_filters(self, rag_tools):
        result = rag_tools.search_properties.invoke({
            "city": "Dubai",
            "bedrooms": 2,
            "max_rent": 100000,
        })
        assert "Tower A" in result  # Dubai, 2 bed, 95K ✓
        assert "Tower B" not in result  # 110K > 100K ✗

    def test_no_results(self, rag_tools):
        result = rag_tools.search_properties.invoke({"city": "Abu Dhabi"})
        assert "No properties found" in result or "no" in result.lower()


class TestGetAreaStatistics:
    """Tests area-level aggregation statistics."""

    def test_dubai_stats(self, rag_tools):
        result = rag_tools.get_area_statistics.invoke({"city": "Dubai"})
        assert isinstance(result, str)
        assert any(char.isdigit() for char in result)

    def test_location_stats(self, rag_tools):
        result = rag_tools.get_area_statistics.invoke({"location": "Dubai Marina"})
        assert isinstance(result, str)

    def test_property_type_filter(self, rag_tools):
        result = rag_tools.get_area_statistics.invoke({"property_type": "Apartment"})
        assert isinstance(result, str)
