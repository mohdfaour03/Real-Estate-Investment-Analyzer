"""
Cost and token tracking for LLM API calls.

Tracks per-request and cumulative token usage and estimated cost
for OpenRouter and Groq API calls.

Usage:
    from shared.cost_tracker import cost_tracker

    cost_tracker.record("openrouter/auto", input_tokens=1500, output_tokens=400)
    cost_tracker.get_summary()
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from shared.logging_config import get_logger

logger = get_logger("shared.cost_tracker")

# OpenRouter pricing (USD per 1M tokens) — updated March 2026
# "openrouter/auto" routes dynamically; we use a blended estimate.
PRICING = {
    "openrouter/auto": {"input": 2.00, "output": 8.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.00},
    "whisper-large-v3-turbo": {"input": 0.00, "output": 0.00},  # Groq free tier
}

DEFAULT_PRICING = {"input": 2.00, "output": 8.00}


@dataclass
class RequestCost:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float


class CostTracker:
    """Thread-safe singleton for tracking API costs across all services."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests: list[RequestCost] = []
        self._totals: dict = defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0})
        self._session_start = time.time()

    def record(self, model: str, input_tokens: int = 0, output_tokens: int = 0) -> float:
        """Record a single API call. Returns estimated cost in USD."""
        pricing = PRICING.get(model, DEFAULT_PRICING)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        entry = RequestCost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=time.time(),
        )

        with self._lock:
            self._requests.append(entry)
            t = self._totals[model]
            t["input_tokens"] += input_tokens
            t["output_tokens"] += output_tokens
            t["cost_usd"] += cost
            t["calls"] += 1

        if cost > 0.01:  # Log if over 1 cent
            logger.info(f"API cost | model={model} | in={input_tokens} out={output_tokens} | ${cost:.4f}")

        return cost

    def get_summary(self) -> dict:
        """Return cumulative cost summary across all models."""
        with self._lock:
            total_cost = sum(t["cost_usd"] for t in self._totals.values())
            total_calls = sum(t["calls"] for t in self._totals.values())
            uptime_hours = (time.time() - self._session_start) / 3600

            return {
                "total_cost_usd": round(total_cost, 4),
                "total_calls": total_calls,
                "uptime_hours": round(uptime_hours, 2),
                "projected_daily_usd": round(total_cost / max(uptime_hours, 0.01) * 24, 2),
                "by_model": {
                    model: {
                        "calls": data["calls"],
                        "input_tokens": data["input_tokens"],
                        "output_tokens": data["output_tokens"],
                        "cost_usd": round(data["cost_usd"], 4),
                    }
                    for model, data in self._totals.items()
                },
            }

    def get_request_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost without recording (for budget checks)."""
        pricing = PRICING.get(model, DEFAULT_PRICING)
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


# Global singleton
cost_tracker = CostTracker()
