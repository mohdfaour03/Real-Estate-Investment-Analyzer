"""Tests for comp evaluator — _format_comps is pure, evaluate_comps needs LLM mock."""
import pytest
import sys, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.comp_evaluator import _format_comps, evaluate_comps, EvaluationResult
from pipeline.comp_finder import ComparableProperty, CompFinderResult


def _make_finder_result(num_props=3):
    """Helper to build a CompFinderResult with test data."""
    props = []
    for i in range(num_props):
        props.append(ComparableProperty(
            address=f"Tower {i+1}, Dubai Marina",
            rent=90_000 + i * 10_000,
            beds=2,
            baths=2,
            property_type="Apartment",
            area_sqft=1_200 + i * 100,
            rent_per_sqft=round((90_000 + i * 10_000) / (1_200 + i * 100), 2),
            location="Dubai Marina",
            city="Dubai",
            furnished="Unfurnished",
        ))
    return CompFinderResult(
        comparable_properties=props,
        market_context=["Market report: Dubai Marina rents up 8% YoY"],
    )


class TestFormatComps:
    """Tests for _format_comps — pure string formatting."""

    def test_returns_string(self):
        result = _format_comps(_make_finder_result())
        assert isinstance(result, str)

    def test_includes_property_addresses(self):
        result = _format_comps(_make_finder_result())
        assert "Tower 1" in result
        assert "Tower 2" in result

    def test_includes_rent_values(self):
        result = _format_comps(_make_finder_result())
        assert "90000" in result or "90,000" in result

    def test_formats_property_details(self):
        """Output should include structured details like rent, beds, location."""
        result = _format_comps(_make_finder_result())
        assert "Rent:" in result or "AED" in result
        assert "Beds:" in result or "beds" in result.lower()

    def test_empty_properties(self):
        finder = CompFinderResult(comparable_properties=[], market_context=[])
        result = _format_comps(finder)
        assert isinstance(result, str)


class TestEvaluateComps:
    """Tests for evaluate_comps — requires mocking the OpenRouter LLM call."""

    @patch("pipeline.comp_evaluator.client")
    def test_returns_evaluation_result(self, mock_client):
        """With mocked LLM returning valid JSON, evaluate_comps should parse correctly."""
        # Mock LLM response with valid JSON evaluation
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''{
            "evaluated_comps": [
                {"address": "Tower 1, Dubai Marina", "rent": 90000, "relevance_score": 0.92, "is_outlier": false, "adjustment_notes": "Good match"},
                {"address": "Tower 2, Dubai Marina", "rent": 100000, "relevance_score": 0.85, "is_outlier": false, "adjustment_notes": "Slightly larger"}
            ],
            "estimated_value": 95000.0,
            "confidence_score": "High",
            "reasoning_chain": "Analyzed 2 comparable properties in Dubai Marina.",
            "adjustments_applied": ["Location premium +5%"]
        }'''
        mock_client.chat.completions.create.return_value = mock_response

        finder_result = _make_finder_result(2)
        result = evaluate_comps(finder_result)

        assert isinstance(result, EvaluationResult)
        assert result.estimated_value == 95_000.0
        assert result.confidence_score == "High"
        assert len(result.evaluated_comps) == 2

    @patch("pipeline.comp_evaluator.client")
    def test_handles_markdown_fenced_json(self, mock_client):
        """LLM sometimes wraps JSON in ```json``` fences — should still parse."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''```json
{
    "evaluated_comps": [],
    "estimated_value": 80000.0,
    "confidence_score": "Low",
    "reasoning_chain": "Insufficient comps.",
    "adjustments_applied": []
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        finder_result = _make_finder_result(1)
        result = evaluate_comps(finder_result)
        assert result.estimated_value == 80_000.0
