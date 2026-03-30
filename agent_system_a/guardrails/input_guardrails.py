"""
Input Guardrails — Validates user queries before they reach the LLM.

Two-layer architecture:
  Layer 1 (always): Fast regex patterns for known injection/malicious content
  Layer 2 (when available): LLM Guard ML-based PromptInjection scanner
     → Uses a fine-tuned DeBERTa model to catch paraphrased attacks regex misses
     → Requires torch + transformers (auto-installed via llm-guard[torch])
     → Gracefully degrades to regex-only when deps are missing

Checks:
  1. Query length limits (too short / too long)
  2. Prompt injection detection (regex + ML)
  3. Off-topic filtering (queries unrelated to real estate)
  4. Malicious content patterns (SQL injection, code execution)

Returns:
  InputGuardrailResult with is_safe=True/False, blocked_reason, scanner_used, and sanitized_query.
"""

import re
from pydantic import BaseModel
from typing import Optional
from shared.logging_config import get_logger

logger = get_logger("agent_system_a.guardrails.input")


# ── Try loading LLM Guard (ML-based scanner) ──

_llm_guard_available = False
_prompt_injection_scanner = None

try:
    from llm_guard.input_scanners import PromptInjection
    from llm_guard.input_scanners.prompt_injection import MatchType

    # Initialize scanner — uses protectai/deberta-v3-base-prompt-injection-v2
    # threshold=0.5 balances precision/recall; match_type=FULL scans entire input
    _prompt_injection_scanner = PromptInjection(threshold=0.5, match_type=MatchType.FULL)
    _llm_guard_available = True
    logger.info("LLM Guard PromptInjection scanner loaded (ML-based detection active)")
except ImportError as e:
    logger.info(f"LLM Guard not available ({e}), using regex-only injection detection")
except Exception as e:
    logger.warning(f"LLM Guard failed to initialize: {e}, falling back to regex-only")


# ── Configuration ──

MIN_QUERY_LENGTH = 2         # Minimum characters
MAX_QUERY_LENGTH = 2000      # Maximum characters (prevent context stuffing)

# Patterns that suggest prompt injection attempts
# These are the fast regex first-pass — catches obvious attacks in <1ms
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+(instructions|prompts|rules)",
    r"ignore\s+above",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(a|an)\s+",
    r"system\s*:\s*",
    r"<\s*system\s*>",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode",
    r"ignore\s+your\s+(restrictions|rules|guidelines)",
    r"bypass\s+(your\s+)?(rules|restrictions|filters|guardrails)",
    r"override\s+(your\s+)?(instructions|programming|system)",
    # Extended patterns (common prompt injection variants from research)
    r"do\s+anything\s+now",
    r"new\s+instruction[s]?\s*:",
    r"forget\s+(all\s+)?(your\s+)?(previous\s+)?(instructions|rules|training)",
    r"disregard\s+(all\s+)?(previous|above|prior)",
    r"you\s+must\s+obey",
    r"from\s+now\s+on\s+you\s+(are|will)",
    r"respond\s+to\s+every\s+prompt\s+with",
    r"\[INST\]",            # Llama-style injection
    r"<<sys>>",             # Llama system tag injection (lowercase — we match on .lower())
    r"<\|im_start\|>",      # ChatML injection
    r"BEGININSTRUCTION",    # Instruction marker injection
]

# Patterns for malicious input (SQL injection, code execution)
MALICIOUS_PATTERNS = [
    r"drop\s+table",
    r"delete\s+from",
    r"union\s+select",
    r"<script\b",
    r"javascript\s*:",
    r"exec\s*\(",
    r"eval\s*\(",
    r"__import__",
    r"os\.system",
    r"subprocess\.",
]

# Keywords that indicate the query is about real estate / investment
# Used for soft off-topic detection (warning, not blocking)
RE_KEYWORDS = [
    "rent", "property", "apartment", "villa", "studio", "dubai",
    "abu dhabi", "sharjah", "ajman", "uae", "emirates",
    "bedroom", "bed", "bath", "sqft", "square",
    "invest", "yield", "roi", "mortgage", "tax", "fee",
    "area", "location", "downtown", "marina", "jbr", "business bay",
    "price", "budget", "aed", "affordable", "luxury",
    "market", "trend", "compare", "analysis", "valuation",
    "buy", "sell", "lease", "tenant", "landlord",
    "furnished", "unfurnished", "annual",
    # Allow greetings through
    "hi", "hello", "hey", "thanks", "thank you", "help",
]


class InputGuardrailResult(BaseModel):
    """Result of input validation."""
    is_safe: bool
    blocked_reason: Optional[str] = None
    is_off_topic: bool = False
    sanitized_query: str = ""
    scanner_used: str = "regex"  # "regex" | "regex+llm_guard"


def _run_llm_guard_scan(query: str) -> Optional[str]:
    """Run LLM Guard ML scanner. Returns blocked_reason if injection detected, None if safe."""
    if not _llm_guard_available or _prompt_injection_scanner is None:
        return None

    try:
        sanitized_output, is_valid, risk_score = _prompt_injection_scanner.scan(query)
        logger.debug(f"LLM Guard scan | valid={is_valid}, risk_score={risk_score:.3f}")

        if not is_valid:
            return f"Input flagged by ML-based injection detector (risk: {risk_score:.2f}). Please rephrase your real estate question."
    except Exception as e:
        # ML scanner failure should never block legitimate queries
        logger.warning(f"LLM Guard scan error (non-blocking): {e}")

    return None


def validate_input(query: str) -> InputGuardrailResult:
    """Run all input guardrail checks on a user query.

    Two-layer approach:
      1. Fast regex scan (always runs, <1ms)
      2. ML-based LLM Guard scan (when available, catches paraphrased attacks)

    Returns InputGuardrailResult with is_safe=False if the query should be blocked.
    """
    raw = query.strip()
    scanner_used = "regex+llm_guard" if _llm_guard_available else "regex"

    # 1. Length check
    if len(raw) < MIN_QUERY_LENGTH:
        logger.warning(f"Query too short | length={len(raw)}")
        return InputGuardrailResult(
            is_safe=False,
            blocked_reason="Query is too short. Please provide more detail.",
            sanitized_query=raw,
            scanner_used=scanner_used,
        )

    if len(raw) > MAX_QUERY_LENGTH:
        logger.warning(f"Query too long | length={len(raw)}")
        return InputGuardrailResult(
            is_safe=False,
            blocked_reason=f"Query exceeds maximum length ({MAX_QUERY_LENGTH} characters). Please shorten your message.",
            sanitized_query=raw[:MAX_QUERY_LENGTH],
            scanner_used=scanner_used,
        )

    # 2. Layer 1 — Fast regex injection detection
    lower = raw.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            logger.warning(f"Prompt injection detected (regex) | pattern='{pattern}' | query='{raw[:80]}...'")
            return InputGuardrailResult(
                is_safe=False,
                blocked_reason="Your query contains patterns that aren't supported. Please rephrase your real estate question.",
                sanitized_query=raw,
                scanner_used=scanner_used,
            )

    # 3. Malicious content detection
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, lower):
            logger.warning(f"Malicious input detected (regex) | pattern='{pattern}' | query='{raw[:80]}...'")
            return InputGuardrailResult(
                is_safe=False,
                blocked_reason="Your query contains unsupported content. Please ask a real estate question.",
                sanitized_query=raw,
                scanner_used=scanner_used,
            )

    # 4. Layer 2 — ML-based injection detection (when available)
    # Catches paraphrased/creative attacks that bypass regex
    ml_block_reason = _run_llm_guard_scan(raw)
    if ml_block_reason:
        logger.warning(f"Prompt injection detected (LLM Guard ML) | query='{raw[:80]}...'")
        return InputGuardrailResult(
            is_safe=False,
            blocked_reason=ml_block_reason,
            sanitized_query=raw,
            scanner_used=scanner_used,
        )

    # 5. Off-topic detection (soft — warns but doesn't block)
    has_re_keyword = any(kw in lower for kw in RE_KEYWORDS)
    is_off_topic = not has_re_keyword and len(raw.split()) > 3

    if is_off_topic:
        logger.info(f"Off-topic query detected (not blocked) | query='{raw[:80]}...'")

    logger.debug(f"Input guardrail passed | length={len(raw)}, off_topic={is_off_topic}, scanner={scanner_used}")
    return InputGuardrailResult(
        is_safe=True,
        is_off_topic=is_off_topic,
        sanitized_query=raw,
        scanner_used=scanner_used,
    )
