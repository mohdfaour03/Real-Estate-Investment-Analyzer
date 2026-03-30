"""
Observability and tracing setup for LangGraph agents.

Provides optional LangSmith integration when LANGCHAIN_TRACING_V2=true,
plus a lightweight local callback that tracks token usage via cost_tracker.

Setup (optional — system works without it):
    export LANGCHAIN_TRACING_V2=true
    export LANGCHAIN_API_KEY=your-key
    export LANGCHAIN_PROJECT=real-estate-analyzer

Usage:
    from shared.observability import get_tracing_callbacks, trace_llm_call

    # For LangGraph agents — pass callbacks to .ainvoke()
    callbacks = get_tracing_callbacks()

    # For manual LLM calls — wrap and track
    trace_llm_call("openrouter/auto", input_tokens=500, output_tokens=200)
"""

import os
import time
from typing import Any
from shared.logging_config import get_logger
from shared.cost_tracker import cost_tracker

logger = get_logger("shared.observability")

# Check if LangSmith is configured
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"

if LANGSMITH_ENABLED:
    logger.info("LangSmith tracing enabled — traces will appear in your LangSmith dashboard")
else:
    logger.info("LangSmith tracing disabled — set LANGCHAIN_TRACING_V2=true to enable")


def get_tracing_callbacks() -> list:
    """Return LangChain callbacks for tracing.

    If LangSmith is configured, LangChain auto-sends traces (no explicit callback needed).
    We always include our local token-tracking callback.
    """
    return [TokenTrackingCallback()]


class TokenTrackingCallback:
    """Lightweight callback that records token usage from LLM responses
    into the cost_tracker. Works with any LangChain LLM."""

    def on_llm_end(self, response: Any, **kwargs):
        """Called after each LLM call completes."""
        try:
            if hasattr(response, "llm_output") and response.llm_output:
                usage = response.llm_output.get("token_usage", {})
                model = response.llm_output.get("model_name", "openrouter/auto")
                if usage:
                    cost_tracker.record(
                        model=model,
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                    )
        except Exception:
            pass  # Never break the agent pipeline for tracking


def trace_llm_call(model: str, input_tokens: int = 0, output_tokens: int = 0, duration_ms: float = 0):
    """Manual trace point for LLM calls outside LangChain (e.g., direct OpenAI calls)."""
    cost = cost_tracker.record(model, input_tokens, output_tokens)
    if duration_ms > 0:
        logger.debug(f"LLM call | model={model} | {duration_ms:.0f}ms | ${cost:.4f}")
