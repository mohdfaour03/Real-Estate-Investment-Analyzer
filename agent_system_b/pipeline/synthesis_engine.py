from pydantic import BaseModel
from typing import List

from agent_system_b.pipeline.comp_evaluator import EvaluationResult


class SupportingComp(BaseModel):
    """A single comp included in the final response."""
    address: str
    rent: float
    relevance_score: float
    notes: str


class AgenticResponse(BaseModel):
    """The final agentic response returned to Agent System A.

    This is what proves System B is an AGENT, not a tool.
    A tool would return: {"estimated_value": 450000}
    An agent returns: value + confidence + reasoning + evidence.
    """
    estimated_value: float
    confidence_score: str
    reasoning_chain: str
    supporting_comps: List[SupportingComp]
    adjustments_applied: List[str]
    num_comps_analyzed: int


def synthesize(evaluation: EvaluationResult) -> AgenticResponse:
    """Transform evaluation result into the final agentic response.

    No LLM call needed — just restructuring the evaluation
    into the response format that Agent System A expects.
    """
    # Build supporting comps from non-outlier evaluated comps
    supporting = [
        SupportingComp(
            address=comp.address,
            rent=comp.rent,
            relevance_score=comp.relevance_score,
            notes=comp.adjustment_notes,
        )
        for comp in evaluation.evaluated_comps
        if not comp.is_outlier
    ]

    return AgenticResponse(
        estimated_value=evaluation.estimated_value,
        confidence_score=evaluation.confidence_score,
        reasoning_chain=evaluation.reasoning_chain,
        supporting_comps=supporting,
        adjustments_applied=evaluation.adjustments_applied,
        num_comps_analyzed=len(evaluation.evaluated_comps),
    )
