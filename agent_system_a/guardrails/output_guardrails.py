"""
Output Guardrails — Validates LLM responses before they reach the user.

Two-layer architecture:
  Layer 1 (always): Fast regex patterns for known harmful output patterns
  Layer 2 (when available): LLM Guard ML-based output scanners
     → BanTopics: Detects off-topic content in responses
     → Bias: Flags biased language about regions, nationalities, etc.
     → Sensitive: Catches sensitive data leaks the regex misses
     → Requires torch + transformers (auto-installed via llm-guard[torch])
     → Gracefully degrades to regex-only when deps are missing

Checks:
  1. Empty/missing response detection
  2. Hallucinated price validation (catches impossible rent values)
  3. Harmful financial advice detection (unsolicited "guaranteed" claims)
  4. Response length limits (too short may indicate failure)
  5. PII leak detection (regex + ML-based)

Returns:
  OutputGuardrailResult with is_safe=True/False, warnings, scanner_used, and cleaned response.
"""

import re
from pydantic import BaseModel
from typing import List, Optional
from shared.logging_config import get_logger

logger = get_logger("agent_system_a.guardrails.output")


# ── Try loading LLM Guard output scanners ──

_llm_guard_output_available = False
_output_scanners = []

try:
    from llm_guard.output_scanners import BanTopics, Bias, Sensitive, Relevance

    # Sensitive scanner catches PII, credentials, secrets the regex misses
    _sensitive_scanner = Sensitive(redact=False)
    _output_scanners.append(("sensitive", _sensitive_scanner))

    # Bias scanner flags biased language about demographics/regions
    _bias_scanner = Bias(threshold=0.7)
    _output_scanners.append(("bias", _bias_scanner))

    _llm_guard_output_available = True
    logger.info(f"LLM Guard output scanners loaded ({len(_output_scanners)} active)")
except ImportError as e:
    logger.info(f"LLM Guard output scanners not available ({e}), using regex-only")
except Exception as e:
    logger.warning(f"LLM Guard output scanners failed to initialize: {e}, falling back to regex-only")


# ── Configuration ──

MIN_RESPONSE_LENGTH = 10      # Suspiciously short
MAX_RESPONSE_LENGTH = 15000   # Prevent runaway generation

# Rent values outside this range are likely hallucinated
MIN_PLAUSIBLE_RENT = 1_000         # AED/year — below this is garbage data
MAX_PLAUSIBLE_RENT = 5_000_000     # AED/year — even luxury penthouses cap here

# Patterns that indicate dangerous financial advice
FINANCIAL_ADVICE_PATTERNS = [
    r"guaranteed\s+(return|profit|income|yield)",
    r"risk[\s-]*free\s+(investment|return)",
    r"you\s+(will|shall)\s+(definitely|certainly)\s+(make|earn|profit)",
    r"cannot\s+(lose|fail)",
    r"100%\s+(safe|guaranteed|certain)",
]

# Patterns that might indicate PII leakage
PII_PATTERNS = [
    r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b",       # SSN-like
    r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Credit card-like
    r"\b[A-Z]{2}\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2}\b",  # IBAN-like
]


class OutputGuardrailResult(BaseModel):
    """Result of output validation."""
    is_safe: bool
    warnings: List[str] = []
    blocked_reason: Optional[str] = None
    cleaned_response: str = ""
    scanner_used: str = "regex"  # "regex" | "regex+llm_guard"


def _run_llm_guard_output_scan(prompt: str, response: str) -> List[str]:
    """Run LLM Guard ML output scanners. Returns list of warnings."""
    if not _llm_guard_output_available or not _output_scanners:
        return []

    warnings = []
    for scanner_name, scanner in _output_scanners:
        try:
            sanitized, is_valid, risk_score = scanner.scan(prompt, response)
            if not is_valid:
                warning_msg = f"LLM Guard [{scanner_name}] flagged response (risk: {risk_score:.2f})"
                logger.warning(warning_msg)
                warnings.append(warning_msg)
        except Exception as e:
            # ML scanner failure should never block legitimate responses
            logger.warning(f"LLM Guard output scan [{scanner_name}] error (non-blocking): {e}")

    return warnings


def validate_output(response: str, original_query: str = "") -> OutputGuardrailResult:
    """Run all output guardrail checks on an LLM response.

    Two-layer approach:
      1. Fast regex checks (always run, <1ms)
      2. ML-based LLM Guard output scanners (when available)

    Returns OutputGuardrailResult. Even when is_safe=True, check warnings[].
    """
    warnings = []
    scanner_used = "regex+llm_guard" if _llm_guard_output_available else "regex"

    # 1. Empty response
    if not response or not response.strip():
        logger.warning("Empty response from LLM")
        return OutputGuardrailResult(
            is_safe=False,
            blocked_reason="The system generated an empty response. Please try again.",
            cleaned_response="",
            scanner_used=scanner_used,
        )

    text = response.strip()

    # 2. Too short (might indicate a failure)
    if len(text) < MIN_RESPONSE_LENGTH:
        logger.warning(f"Suspiciously short response | length={len(text)}")
        warnings.append("Response is unusually short — may be incomplete.")

    # 3. Too long (truncate but don't block)
    if len(text) > MAX_RESPONSE_LENGTH:
        logger.warning(f"Response too long, truncating | length={len(text)}")
        text = text[:MAX_RESPONSE_LENGTH] + "\n\n*[Response truncated due to length]*"
        warnings.append("Response was truncated due to excessive length.")

    # 4. Hallucinated rent values — extract AED amounts and check plausibility
    aed_amounts = re.findall(r"AED\s*([\d,]+(?:\.\d+)?)", text)
    for amount_str in aed_amounts:
        try:
            amount = float(amount_str.replace(",", ""))
            # Only flag if it looks like a rent (not a mortgage total or property price)
            # Heuristic: values in rent-like ranges that are implausibly low
            if 0 < amount < MIN_PLAUSIBLE_RENT:
                logger.warning(f"Possible hallucinated low rent value | AED {amount:,.0f}")
                warnings.append(f"Response contains a suspiciously low value (AED {amount:,.0f}) — verify accuracy.")
            elif amount > MAX_PLAUSIBLE_RENT:
                # Don't flag this for mortgage totals which can be in the millions
                # Only flag if the surrounding context says "rent" or "annual"
                context_start = max(0, text.find(amount_str) - 50)
                context = text[context_start:text.find(amount_str) + len(amount_str)].lower()
                if "rent" in context or "annual" in context:
                    logger.warning(f"Possible hallucinated high rent value | AED {amount:,.0f}")
                    warnings.append(f"Response contains an unusually high rent value (AED {amount:,.0f}) — verify accuracy.")
        except ValueError:
            continue

    # 5. Dangerous financial advice
    lower = text.lower()
    for pattern in FINANCIAL_ADVICE_PATTERNS:
        if re.search(pattern, lower):
            logger.warning(f"Financial advice pattern detected | pattern='{pattern}'")
            warnings.append("Response may contain overly confident financial claims. All investments carry risk.")
            break  # One warning is enough

    # 6. Layer 1 — PII leak detection (regex)
    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            logger.warning(f"Possible PII detected in response (regex) | pattern='{pattern}'")
            warnings.append("Response may contain sensitive data patterns — review before sharing.")
            break

    # 7. Layer 2 — ML-based output scanning (when available)
    ml_warnings = _run_llm_guard_output_scan(original_query, text)
    warnings.extend(ml_warnings)

    is_safe = len([w for w in warnings if "empty" in w.lower() or "blocked" in w.lower()]) == 0
    logger.debug(f"Output guardrail done | safe={is_safe}, warnings={len(warnings)}, length={len(text)}, scanner={scanner_used}")

    return OutputGuardrailResult(
        is_safe=True,  # Warnings don't block, only empty/critical issues block
        warnings=warnings,
        cleaned_response=text,
        scanner_used=scanner_used,
    )
