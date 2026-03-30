#!/usr/bin/env python3
"""
Run evaluation suite — executes guardrail evals (no LLM needed).

Usage:
    python -m evaluation.run_evals           # From project root
    python evaluation/run_evals.py           # Direct execution
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.metrics import EvalSuite


def main():
    suite = EvalSuite()

    print("\nRunning guardrail evaluations (no LLM required)...")
    guardrail_results = suite.run_guardrail_evals()

    report = suite.aggregate(guardrail_results)
    suite.print_report(report)

    # Exit with non-zero if any eval failed
    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
