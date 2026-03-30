from openai import OpenAI
from pydantic import BaseModel
from typing import List, Optional

from agent_system_b.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL_OPENAI
from agent_system_b.pipeline.comp_finder import CompFinderResult
from shared.logging_config import get_logger

logger = get_logger("agent_system_b.comp_evaluator")


# --- Output models ---

class CompEvaluation(BaseModel):
    """Evaluation of a single comparable property."""
    address: str
    rent: float
    relevance_score: float
    is_outlier: bool
    adjustment_notes: str


class EvaluationResult(BaseModel):
    """Full evaluation output from the reasoning engine."""
    evaluated_comps: List[CompEvaluation]
    estimated_value: float
    confidence_score: str
    reasoning_chain: str
    adjustments_applied: List[str]


# --- LLM client ---
client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

EVALUATION_PROMPT = """You are a senior real estate analyst evaluating comparable properties for a rental valuation.

## Comparable Properties Found:
{comps_text}

## Market Context (from reports):
{market_context}

## Your Task:
Analyze each comparable property and produce a valuation. Think step by step:

1. **Score each comp** for relevance (0.0 to 1.0) based on how similar it is to the target criteria.
2. **Flag outliers** — distressed sales, unusually high/low rents, or properties with special circumstances.
3. **Apply adjustments** — consider location premiums, floor level, furnishing status, demand trends from market reports.
4. **Calculate estimated value** — weighted average of non-outlier comps, adjusted for market conditions.
5. **Determine confidence** — "High" (4+ good comps), "Medium" (2-3 good comps), "Low" (0-1 good comps).

Respond in this exact JSON format:
{{
    "evaluated_comps": [
        {{
            "address": "...",
            "rent": 0,
            "relevance_score": 0.0,
            "is_outlier": false,
            "adjustment_notes": "..."
        }}
    ],
    "estimated_value": 0,
    "confidence_score": "High/Medium/Low",
    "reasoning_chain": "Step-by-step explanation of your reasoning...",
    "adjustments_applied": ["list", "of", "adjustments"]
}}"""


def evaluate_comps(finder_result: CompFinderResult) -> EvaluationResult:
    """Use LLM to reason over comparable properties and market context."""
    import json
    import re

    # Format comps into readable text for the LLM
    comps_text = _format_comps(finder_result)
    market_context = "\n\n".join(finder_result.market_context) or "No market context available."
    logger.info(f"Evaluating {len(finder_result.comparable_properties)} comps with LLM reasoning engine")

    # Single LLM call — the reasoning engine
    # NOTE: response_format={"type": "json_object"} is NOT used because
    # OpenRouter doesn't support it for Claude models. Instead we rely on
    # the system prompt instruction + robust JSON extraction from the response.
    response = client.chat.completions.create(
        model=LLM_MODEL_OPENAI,
        messages=[
            {"role": "system", "content": "You are a senior real estate analyst. Always respond with valid JSON only — no markdown fences, no commentary."},
            {"role": "user", "content": EVALUATION_PROMPT.format(
                comps_text=comps_text,
                market_context=market_context,
            )},
        ],
        temperature=0.2,
    )

    # Extract JSON from response — Claude may wrap it in ```json fences
    text = response.choices[0].message.content.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        logger.debug("Stripped markdown JSON fence from LLM response")
        text = fence_match.group(1).strip()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON | error={e} | response_preview={text[:200]}")
        raise

    result = EvaluationResult(**raw)
    logger.info(f"Evaluation complete | estimated_value={result.estimated_value:,.0f} AED, confidence={result.confidence_score}")
    return result


def _format_comps(finder_result: CompFinderResult) -> str:
    """Format comparable properties into readable text for the LLM."""
    if not finder_result.comparable_properties:
        return "No comparable properties found."

    lines = []
    for i, comp in enumerate(finder_result.comparable_properties, 1):
        line = (
            f"{i}. {comp.address}\n"
            f"   Rent: AED {comp.rent:,.0f} | "
            f"Beds: {comp.beds} | Baths: {comp.baths} | "
            f"Type: {comp.property_type} | "
            f"Area: {comp.area_sqft:,.0f} sqft | "
            f"Rent/sqft: AED {comp.rent_per_sqft:,.2f} | "
            f"Location: {comp.location}, {comp.city} | "
            f"Furnished: {comp.furnished}"
        )
        lines.append(line)

    return "\n\n".join(lines)
