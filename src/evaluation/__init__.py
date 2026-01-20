"""
Evaluation Harness Module.

Provides infrastructure for measuring system quality, comparing experiments,
and preventing regressions.

Architecture Decision: ADR-009

Usage:
    from src.evaluation import EvaluationHarness, EvaluationResult

    # Run evaluation
    harness = EvaluationHarness()
    result = await harness.evaluate(
        provider="claude",
        golden_set="tests/golden/basic_queries.json"
    )

    # Compare to baseline
    comparison = harness.compare(baseline_result, experiment_result)
    print(comparison.decision)  # ADOPT / REJECT / NEEDS_MORE_DATA
"""

from src.evaluation.harness import (
    ComparisonResult,
    Decision,
    EvaluationHarness,
    EvaluationResult,
)

__all__ = [
    "EvaluationHarness",
    "EvaluationResult",
    "ComparisonResult",
    "Decision",
]
