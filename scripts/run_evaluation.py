#!/usr/bin/env python3
"""
Evaluation CLI - Run model provider evaluations.

Usage:
    # Run evaluation with default provider
    python scripts/run_evaluation.py

    # Run with specific provider
    python scripts/run_evaluation.py --provider claude

    # Compare two providers
    python scripts/run_evaluation.py --baseline claude --experiment gpt-4

    # Save results to file
    python scripts/run_evaluation.py --output results.json

Architecture Decision: ADR-009
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import EvaluationHarness, Decision


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Run model provider evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run evaluation with default provider
    python scripts/run_evaluation.py

    # Run with specific provider
    python scripts/run_evaluation.py --provider claude

    # Compare two providers
    python scripts/run_evaluation.py --baseline claude --experiment gpt-4

    # Custom golden set
    python scripts/run_evaluation.py --golden tests/golden/custom.json
        """,
    )

    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default=None,
        help="Provider name to evaluate (uses default if not specified)",
    )

    parser.add_argument(
        "--golden",
        "-g",
        type=str,
        default="tests/golden/basic_queries.json",
        help="Path to golden set JSON file",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file for results (JSON format)",
    )

    parser.add_argument(
        "--baseline",
        "-b",
        type=str,
        default=None,
        help="Baseline provider for comparison",
    )

    parser.add_argument(
        "--experiment",
        "-e",
        type=str,
        default=None,
        help="Experiment provider to compare against baseline",
    )

    parser.add_argument(
        "--max-concurrent",
        "-c",
        type=int,
        default=5,
        help="Maximum concurrent requests",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def print_result(result, verbose: bool = False) -> None:
    """Print evaluation result to console.

    Args:
        result: EvaluationResult instance.
        verbose: Whether to print detailed results.
    """
    print("\n" + "=" * 60)
    print(f"EVALUATION RESULTS - {result.provider_name}")
    print("=" * 60)

    print(f"\nProvider: {result.provider_name} ({result.model_id})")
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.duration_seconds:.1f}s")

    print("\n--- Summary ---")
    print(f"Total Cases: {result.total_cases}")
    print(f"Passed: {result.passed_cases} ({result.success_rate:.1f}%)")
    print(f"Failed: {result.failed_cases}")

    print("\n--- Quality ---")
    print(f"Avg Quality Score: {result.avg_quality_score:.2%}")

    print("\n--- Latency ---")
    print(f"Avg Latency: {result.avg_latency_ms:.0f}ms")
    print(f"P99 Latency: {result.p99_latency_ms:.0f}ms")

    print("\n--- Cost ---")
    print(f"Input Tokens: {result.total_input_tokens:,}")
    print(f"Output Tokens: {result.total_output_tokens:,}")
    print(f"Estimated Cost: ${result.estimated_cost_usd:.4f}")

    if verbose:
        print("\n--- Individual Results ---")
        for tr in result.test_results:
            status = "✅" if tr.success else "❌"
            print(
                f"  {status} {tr.test_case_id}: "
                f"quality={tr.quality_score:.2f}, latency={tr.latency_ms:.0f}ms"
            )
            if tr.error:
                print(f"      Error: {tr.error}")


def print_comparison(comparison) -> None:
    """Print comparison result to console.

    Args:
        comparison: ComparisonResult instance.
    """
    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)

    # Decision with color
    decision_colors = {
        Decision.ADOPT: "\033[92m",  # Green
        Decision.REJECT: "\033[91m",  # Red
        Decision.NEEDS_MORE_DATA: "\033[93m",  # Yellow
    }
    reset = "\033[0m"
    color = decision_colors.get(comparison.decision, "")

    print(f"\n{'=' * 20}")
    print(f"  DECISION: {color}{comparison.decision.value}{reset}")
    print(f"{'=' * 20}")

    print("\n--- Deltas ---")
    print(f"Quality: {comparison.quality_delta:+.2%}")
    print(f"Latency: {comparison.latency_delta_pct:+.1f}%")
    print(f"Cost: {comparison.cost_delta_pct:+.1f}%")

    print("\n--- Reasons ---")
    for reason in comparison.reasons:
        print(f"  • {reason}")

    print("\n--- Baseline ---")
    print(f"  Provider: {comparison.baseline.provider_name}")
    print(f"  Quality: {comparison.baseline.avg_quality_score:.2%}")
    print(f"  Latency: {comparison.baseline.avg_latency_ms:.0f}ms")
    print(f"  Cost: ${comparison.baseline.estimated_cost_usd:.4f}")

    print("\n--- Experiment ---")
    print(f"  Provider: {comparison.experiment.provider_name}")
    print(f"  Quality: {comparison.experiment.avg_quality_score:.2%}")
    print(f"  Latency: {comparison.experiment.avg_latency_ms:.0f}ms")
    print(f"  Cost: ${comparison.experiment.estimated_cost_usd:.4f}")


async def run_single_evaluation(
    harness: EvaluationHarness,
    provider: str | None,
    golden_set: str,
    max_concurrent: int,
    output_path: str | None,
    verbose: bool,
) -> None:
    """Run evaluation for a single provider.

    Args:
        harness: EvaluationHarness instance.
        provider: Provider name.
        golden_set: Path to golden set file.
        max_concurrent: Max concurrent requests.
        output_path: Output file path.
        verbose: Verbose output.
    """
    print("Running evaluation...")
    print(f"  Provider: {provider or 'default'}")
    print(f"  Golden Set: {golden_set}")

    result = await harness.evaluate(
        provider_name=provider,
        golden_set_path=golden_set,
        max_concurrent=max_concurrent,
    )

    print_result(result, verbose)

    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\nResults saved to: {output_path}")


async def run_comparison(
    harness: EvaluationHarness,
    baseline: str,
    experiment: str,
    golden_set: str,
    max_concurrent: int,
    output_path: str | None,
    verbose: bool,
) -> None:
    """Run comparison between two providers.

    Args:
        harness: EvaluationHarness instance.
        baseline: Baseline provider name.
        experiment: Experiment provider name.
        golden_set: Path to golden set file.
        max_concurrent: Max concurrent requests.
        output_path: Output file path.
        verbose: Verbose output.
    """
    print("Running comparison...")
    print(f"  Baseline: {baseline}")
    print(f"  Experiment: {experiment}")
    print(f"  Golden Set: {golden_set}")

    # Run baseline
    print(f"\n[1/2] Evaluating baseline ({baseline})...")
    baseline_result = await harness.evaluate(
        provider_name=baseline,
        golden_set_path=golden_set,
        max_concurrent=max_concurrent,
    )

    # Run experiment
    print(f"[2/2] Evaluating experiment ({experiment})...")
    experiment_result = await harness.evaluate(
        provider_name=experiment,
        golden_set_path=golden_set,
        max_concurrent=max_concurrent,
    )

    # Compare
    comparison = harness.compare(baseline_result, experiment_result)

    if verbose:
        print_result(baseline_result, verbose=False)
        print_result(experiment_result, verbose=False)

    print_comparison(comparison)

    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(comparison.to_dict(), f, indent=2)
        print(f"\nResults saved to: {output_path}")


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    # Check golden set exists
    golden_path = Path(args.golden)
    if not golden_path.exists():
        print(f"Error: Golden set not found: {args.golden}")
        print("Create a golden set first or specify a different path with --golden")
        return 1

    harness = EvaluationHarness()

    try:
        if args.baseline and args.experiment:
            # Comparison mode
            await run_comparison(
                harness=harness,
                baseline=args.baseline,
                experiment=args.experiment,
                golden_set=args.golden,
                max_concurrent=args.max_concurrent,
                output_path=args.output,
                verbose=args.verbose,
            )
        else:
            # Single evaluation mode
            await run_single_evaluation(
                harness=harness,
                provider=args.provider,
                golden_set=args.golden,
                max_concurrent=args.max_concurrent,
                output_path=args.output,
                verbose=args.verbose,
            )

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error during evaluation: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
