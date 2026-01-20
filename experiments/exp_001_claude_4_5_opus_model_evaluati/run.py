#!/usr/bin/env python3
"""Experiment runner for exp_001: Claude 4.5 Opus Model Evaluation.

Auto-generated from research note classification.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.evaluation import EvaluationHarness, Decision


# Success criteria from ADR-009
SUCCESS_CRITERIA = {
    "quality_min": 0.85,
    "quality_regression_max": -0.02,
    "latency_max_ratio": 2.0,
    "cost_max_ratio": 1.5,
}


async def run_evaluation(provider_name: str, golden_set: str) -> dict:
    """Run evaluation with specified provider.

    Args:
        provider_name: Name of provider to evaluate
        golden_set: Path to golden set JSON

    Returns:
        Evaluation results dict
    """
    harness = EvaluationHarness()
    result = await harness.evaluate(
        provider_name=provider_name,
        golden_set_path=golden_set,
    )
    return result.to_dict()


def compare_results(baseline: dict, experiment: dict) -> tuple[str, str]:
    """Compare baseline and experiment results.

    Args:
        baseline: Baseline evaluation results
        experiment: Experiment evaluation results

    Returns:
        Tuple of (decision, reasoning)
    """
    quality_delta = experiment["avg_quality_score"] - baseline["avg_quality_score"]
    latency_ratio = experiment["avg_latency_ms"] / max(baseline["avg_latency_ms"], 1)
    cost_ratio = experiment["estimated_cost_usd"] / max(baseline["estimated_cost_usd"], 0.0001)

    # Decision logic from ADR-009
    # REJECT: Quality regression
    if quality_delta < SUCCESS_CRITERIA["quality_regression_max"]:
        return "REJECT", f"Quality dropped {quality_delta:.1%}"

    # REJECT: Too expensive without improvement
    if cost_ratio > SUCCESS_CRITERIA["cost_max_ratio"] and quality_delta < 0.05:
        return "REJECT", f"Cost +{(cost_ratio-1)*100:.0f}% without quality improvement"

    # ADOPT: All metrics better or same
    if quality_delta >= 0 and latency_ratio <= 1 and cost_ratio <= 1:
        return "ADOPT", "All metrics improved or stable"

    # ADOPT: Quality significantly better
    if quality_delta > 0.10 and cost_ratio <= 3.0:
        return "ADOPT", f"Quality +{quality_delta:.1%} justifies cost"

    # ADOPT: Faster and cheaper
    if latency_ratio < 0.9 and cost_ratio < 1 and quality_delta >= -0.01:
        return "ADOPT", "Faster and cheaper with stable quality"

    return "NEEDS_MORE_DATA", "Mixed results, expand test set"


def main():
    """Run experiment."""
    parser = argparse.ArgumentParser(description="Run exp_001 experiment")
    parser.add_argument(
        "--baseline",
        default="mock",
        help="Baseline provider name",
    )
    parser.add_argument(
        "--provider",
        default="mock",
        help="Experiment provider name",
    )
    parser.add_argument(
        "--golden-set",
        default="tests/golden/basic_queries.json",
        help="Path to golden set JSON",
    )
    parser.add_argument(
        "--output",
        default="results.json",
        help="Output file for results",
    )
    args = parser.parse_args()

    print(f"=== exp_001: Claude 4.5 Opus Model Evaluation ===")
    print()

    # Run baseline
    print(f"Running baseline evaluation with {args.baseline}...")
    baseline_results = asyncio.run(run_evaluation(args.baseline, args.golden_set))
    print(f"  Quality: {baseline_results['avg_quality_score']:.2%}")
    print(f"  Latency: {baseline_results['avg_latency_ms']:.0f}ms")
    print(f"  Cost: ${baseline_results['estimated_cost_usd']:.4f}")
    print()

    # Run experiment
    print(f"Running experiment evaluation with {args.provider}...")
    experiment_results = asyncio.run(run_evaluation(args.provider, args.golden_set))
    print(f"  Quality: {experiment_results['avg_quality_score']:.2%}")
    print(f"  Latency: {experiment_results['avg_latency_ms']:.0f}ms")
    print(f"  Cost: ${experiment_results['estimated_cost_usd']:.4f}")
    print()

    # Compare
    decision, reasoning = compare_results(baseline_results, experiment_results)

    print("=== Results ===")
    print(f"Decision: {decision}")
    print(f"Reasoning: {reasoning}")

    # Save results
    output_path = Path(__file__).parent / args.output
    results = {
        "experiment_id": "exp_001",
        "title": "Claude 4.5 Opus Model Evaluation",
        "timestamp": datetime.utcnow().isoformat(),
        "baseline": {
            "provider": args.baseline,
            "results": baseline_results,
        },
        "experiment": {
            "provider": args.provider,
            "results": experiment_results,
        },
        "comparison": {
            "quality_delta": experiment_results["avg_quality_score"] - baseline_results["avg_quality_score"],
            "latency_ratio": experiment_results["avg_latency_ms"] / max(baseline_results["avg_latency_ms"], 1),
            "cost_ratio": experiment_results["estimated_cost_usd"] / max(baseline_results["estimated_cost_usd"], 0.0001),
        },
        "decision": decision,
        "reasoning": reasoning,
    }

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {output_path}")

    return 0 if decision == "ADOPT" else 1


if __name__ == "__main__":
    sys.exit(main())
