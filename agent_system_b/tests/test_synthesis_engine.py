"""Tests for synthesis engine — pure data transformation, no LLM calls."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.synthesis_engine import AgenticResponse, synthesize
from pipeline.comp_evaluator import CompEvaluation, EvaluationResult


def _make_evaluation(num_comps=5, with_outlier=False):
    """Helper to build a realistic EvaluationResult for testing."""
    comps = []
    for i in range(num_comps):
        comps.append(CompEvaluation(
            address=f"Building {i+1}, Dubai Marina",
            rent=80_000 + i * 5_000,
            relevance_score=0.9 - i * 0.05,
            is_outlier=(i == num_comps - 1 and with_outlier),
            adjustment_notes="Standard adjustment" if i % 2 == 0 else "Furnished premium",
        ))
    return EvaluationResult(
        evaluated_comps=comps,
        estimated_value=95_000.0,
        confidence_score="High",
        reasoning_chain="Analyzed comps in Dubai Marina, strong match for 2-bed apartments.",
        adjustments_applied=["Furnished premium +8%", "High floor +3%"],
    )


class TestSynthesize:
    """Validates the EvaluationResult → AgenticResponse transformation."""

    def test_returns_agentic_response(self):
        evaluation = _make_evaluation()
        result = synthesize(evaluation)
        assert isinstance(result, AgenticResponse)

    def test_estimated_value_preserved(self):
        evaluation = _make_evaluation()
        result = synthesize(evaluation)
        assert result.estimated_value == 95_000.0

    def test_confidence_preserved(self):
        evaluation = _make_evaluation()
        result = synthesize(evaluation)
        assert result.confidence_score == "High"

    def test_reasoning_chain_preserved(self):
        evaluation = _make_evaluation()
        result = synthesize(evaluation)
        assert "Dubai Marina" in result.reasoning_chain

    def test_adjustments_preserved(self):
        evaluation = _make_evaluation()
        result = synthesize(evaluation)
        assert "Furnished premium +8%" in result.adjustments_applied

    def test_outliers_filtered_from_supporting_comps(self):
        """Outlier comps should NOT appear in the final supporting_comps list."""
        evaluation = _make_evaluation(num_comps=4, with_outlier=True)
        result = synthesize(evaluation)
        # The last comp was marked as outlier — should be excluded
        for comp in result.supporting_comps:
            assert "Building 4" not in comp.address

    def test_num_comps_analyzed_matches(self):
        evaluation = _make_evaluation(num_comps=6)
        result = synthesize(evaluation)
        assert result.num_comps_analyzed == 6

    def test_supporting_comp_fields(self):
        """Each supporting comp should have address, rent, relevance_score, notes."""
        evaluation = _make_evaluation(num_comps=3)
        result = synthesize(evaluation)
        for comp in result.supporting_comps:
            assert comp.address is not None
            assert comp.rent > 0
            assert 0 <= comp.relevance_score <= 1


class TestAgenticResponseModel:
    """Validates the response model structure."""

    def test_serialization(self):
        evaluation = _make_evaluation()
        result = synthesize(evaluation)
        data = result.model_dump()
        assert "estimated_value" in data
        assert "supporting_comps" in data
        assert isinstance(data["supporting_comps"], list)
