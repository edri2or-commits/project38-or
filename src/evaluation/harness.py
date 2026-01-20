"""
Evaluation Harness for Model Provider Testing.

This module provides the core evaluation infrastructure for:
- Running test cases against model providers
- Measuring quality, latency, and cost metrics
- Comparing experiments to baselines
- Making ADOPT/REJECT/NEEDS_MORE_DATA decisions

Architecture Decision: ADR-009
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.providers import ModelProvider, ModelRegistry, ModelResponse

logger = logging.getLogger(__name__)


class Decision(Enum):
    """Evaluation decision based on comparison."""

    ADOPT = "ADOPT"
    REJECT = "REJECT"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"


@dataclass
class TestCase:
    """A single test case from the golden set.

    Attributes:
        id: Unique identifier for the test case.
        category: Category (e.g., 'basic', 'complex', 'edge_case').
        query: The input query/prompt.
        expected_keywords: Keywords that should appear in response.
        expected_format: Expected response format (e.g., 'json', 'markdown').
        max_tokens: Maximum tokens for this test case.
        metadata: Additional test case metadata.
    """

    id: str
    category: str
    query: str
    expected_keywords: list[str] = field(default_factory=list)
    expected_format: str | None = None
    max_tokens: int = 1024
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCase":
        """Create TestCase from dictionary.

        Args:
            data: Dictionary with test case data.

        Returns:
            TestCase instance.
        """
        return cls(
            id=data["id"],
            category=data.get("category", "general"),
            query=data["query"],
            expected_keywords=data.get("expected_keywords", []),
            expected_format=data.get("expected_format"),
            max_tokens=data.get("max_tokens", 1024),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TestResult:
    """Result of running a single test case.

    Attributes:
        test_case_id: ID of the test case.
        success: Whether the test passed.
        response: The model's response content.
        latency_ms: Response time in milliseconds.
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens generated.
        quality_score: Quality score (0-1) based on keywords/format.
        error: Error message if test failed.
        timestamp: When the test was run.
    """

    test_case_id: str
    success: bool
    response: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    quality_score: float
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class EvaluationResult:
    """Aggregated results from running all test cases.

    Attributes:
        provider_name: Name of the provider evaluated.
        model_id: Specific model ID used.
        total_cases: Total number of test cases.
        passed_cases: Number of cases that passed.
        failed_cases: Number of cases that failed.
        avg_latency_ms: Average latency across all cases.
        p99_latency_ms: 99th percentile latency.
        avg_quality_score: Average quality score (0-1).
        total_input_tokens: Total input tokens used.
        total_output_tokens: Total output tokens generated.
        estimated_cost_usd: Estimated cost in USD.
        test_results: Individual test results.
        timestamp: When evaluation started.
        duration_seconds: Total evaluation duration.
        metadata: Additional metadata.
    """

    provider_name: str
    model_id: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_latency_ms: float
    p99_latency_ms: float
    avg_quality_score: float
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    test_results: list[TestResult]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_cases == 0:
            return 0.0
        return (self.passed_cases / self.total_cases) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "avg_quality_score": self.avg_quality_score,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


@dataclass
class ComparisonResult:
    """Result of comparing baseline to experiment.

    Attributes:
        decision: ADOPT, REJECT, or NEEDS_MORE_DATA.
        baseline: Baseline evaluation result.
        experiment: Experiment evaluation result.
        quality_delta: Change in quality score (positive = better).
        latency_delta_pct: Change in latency (negative = faster).
        cost_delta_pct: Change in cost (negative = cheaper).
        reasons: Reasons for the decision.
        timestamp: When comparison was made.
    """

    decision: Decision
    baseline: EvaluationResult
    experiment: EvaluationResult
    quality_delta: float
    latency_delta_pct: float
    cost_delta_pct: float
    reasons: list[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "decision": self.decision.value,
            "quality_delta": self.quality_delta,
            "latency_delta_pct": self.latency_delta_pct,
            "cost_delta_pct": self.cost_delta_pct,
            "reasons": self.reasons,
            "baseline": self.baseline.to_dict(),
            "experiment": self.experiment.to_dict(),
            "timestamp": self.timestamp,
        }


class EvaluationHarness:
    """Harness for evaluating model providers.

    Runs test cases against providers and compares results to make
    ADOPT/REJECT/NEEDS_MORE_DATA decisions.

    Example:
        harness = EvaluationHarness()
        result = await harness.evaluate("claude", "tests/golden/basic.json")
        comparison = harness.compare(baseline, result)
        print(comparison.decision)
    """

    # Thresholds for decision making
    MIN_QUALITY_THRESHOLD = 0.85  # Minimum acceptable quality score
    MAX_LATENCY_INCREASE_PCT = 100  # Max acceptable latency increase (%)
    MAX_COST_INCREASE_PCT = 50  # Max acceptable cost increase (%)
    MIN_TEST_CASES = 20  # Minimum test cases for valid comparison

    def __init__(self) -> None:
        """Initialize the evaluation harness."""
        self._registry = ModelRegistry

    async def evaluate(
        self,
        provider_name: str | None = None,
        golden_set_path: str | Path = "tests/golden/basic_queries.json",
        max_concurrent: int = 5,
    ) -> EvaluationResult:
        """Run evaluation against a provider.

        Args:
            provider_name: Name of provider to evaluate (uses default if None).
            golden_set_path: Path to JSON file with test cases.
            max_concurrent: Maximum concurrent requests.

        Returns:
            EvaluationResult with aggregated metrics.

        Raises:
            FileNotFoundError: If golden set file doesn't exist.
            ValueError: If golden set is empty or invalid.
        """
        start_time = time.time()

        # Get provider
        provider = self._registry.get(provider_name)
        logger.info(f"Evaluating provider: {provider.name} ({provider.model_id})")

        # Load test cases
        test_cases = self._load_golden_set(golden_set_path)
        logger.info(f"Loaded {len(test_cases)} test cases from {golden_set_path}")

        # Run tests with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        test_results = await asyncio.gather(
            *[self._run_test_case(provider, tc, semaphore) for tc in test_cases]
        )

        # Calculate aggregated metrics
        duration = time.time() - start_time
        return self._aggregate_results(provider, test_results, duration)

    def compare(
        self,
        baseline: EvaluationResult,
        experiment: EvaluationResult,
    ) -> ComparisonResult:
        """Compare experiment to baseline and make decision.

        Args:
            baseline: Baseline evaluation result.
            experiment: Experiment evaluation result.

        Returns:
            ComparisonResult with decision and analysis.
        """
        reasons = []

        # Calculate deltas
        quality_delta = experiment.avg_quality_score - baseline.avg_quality_score
        latency_delta_pct = (
            (experiment.avg_latency_ms - baseline.avg_latency_ms) / baseline.avg_latency_ms * 100
            if baseline.avg_latency_ms > 0
            else 0
        )
        cost_delta_pct = (
            (experiment.estimated_cost_usd - baseline.estimated_cost_usd)
            / baseline.estimated_cost_usd
            * 100
            if baseline.estimated_cost_usd > 0
            else 0
        )

        # Check minimum test cases
        if experiment.total_cases < self.MIN_TEST_CASES:
            reasons.append(
                f"Insufficient test cases: {experiment.total_cases} < {self.MIN_TEST_CASES}"
            )
            return ComparisonResult(
                decision=Decision.NEEDS_MORE_DATA,
                baseline=baseline,
                experiment=experiment,
                quality_delta=quality_delta,
                latency_delta_pct=latency_delta_pct,
                cost_delta_pct=cost_delta_pct,
                reasons=reasons,
            )

        # Decision logic based on ADR-009 matrix
        decision = self._make_decision(quality_delta, latency_delta_pct, cost_delta_pct, reasons)

        return ComparisonResult(
            decision=decision,
            baseline=baseline,
            experiment=experiment,
            quality_delta=quality_delta,
            latency_delta_pct=latency_delta_pct,
            cost_delta_pct=cost_delta_pct,
            reasons=reasons,
        )

    def _make_decision(
        self,
        quality_delta: float,
        latency_delta_pct: float,
        cost_delta_pct: float,
        reasons: list[str],
    ) -> Decision:
        """Apply decision matrix from ADR-009.

        Decision Matrix:
        | Quality | Latency | Cost | Decision |
        |---------|---------|------|----------|
        | Better  | Better  | Better | ADOPT |
        | Better  | Same    | Same   | ADOPT |
        | Same    | Better  | Same   | ADOPT |
        | Worse   | Any     | Any    | REJECT |
        | Same    | Worse   | Worse  | REJECT |
        | Mixed   | Mixed   | Mixed  | NEEDS_MORE_DATA |

        Args:
            quality_delta: Change in quality score.
            latency_delta_pct: Change in latency percentage.
            cost_delta_pct: Change in cost percentage.
            reasons: List to append decision reasons to.

        Returns:
            Decision enum value.
        """
        # Thresholds for "same" (within noise margin)
        quality_noise = 0.02  # 2% quality difference is noise
        latency_noise = 10  # 10% latency difference is noise
        cost_noise = 10  # 10% cost difference is noise

        # Categorize changes
        quality_better = quality_delta > quality_noise
        quality_worse = quality_delta < -quality_noise
        quality_same = not quality_better and not quality_worse

        latency_better = latency_delta_pct < -latency_noise
        latency_worse = latency_delta_pct > self.MAX_LATENCY_INCREASE_PCT
        latency_same = not latency_better and not latency_worse

        cost_better = cost_delta_pct < -cost_noise
        cost_worse = cost_delta_pct > self.MAX_COST_INCREASE_PCT
        cost_same = not cost_better and not cost_worse

        # Apply decision matrix
        if quality_worse:
            reasons.append(f"Quality degraded: {quality_delta:.2%}")
            return Decision.REJECT

        if quality_same and latency_worse and cost_worse:
            reasons.append("No quality improvement but worse latency and cost")
            return Decision.REJECT

        if quality_better and latency_better and cost_better:
            reasons.append("All metrics improved")
            return Decision.ADOPT

        if quality_better and latency_same and cost_same:
            reasons.append("Quality improved, other metrics stable")
            return Decision.ADOPT

        if quality_same and latency_better and cost_same:
            reasons.append("Latency improved, other metrics stable")
            return Decision.ADOPT

        if quality_same and cost_better and latency_same:
            reasons.append("Cost reduced, other metrics stable")
            return Decision.ADOPT

        # Mixed results
        reasons.append(
            f"Mixed results: quality={quality_delta:.2%}, "
            f"latency={latency_delta_pct:.1f}%, cost={cost_delta_pct:.1f}%"
        )
        return Decision.NEEDS_MORE_DATA

    def _load_golden_set(self, path: str | Path) -> list[TestCase]:
        """Load test cases from JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            List of TestCase objects.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If file is empty or invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Golden set not found: {path}")

        with open(path) as f:
            data = json.load(f)

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"Golden set must be non-empty list: {path}")

        return [TestCase.from_dict(tc) for tc in data]

    async def _run_test_case(
        self,
        provider: ModelProvider,
        test_case: TestCase,
        semaphore: asyncio.Semaphore,
    ) -> TestResult:
        """Run a single test case against provider.

        Args:
            provider: Model provider to test.
            test_case: Test case to run.
            semaphore: Concurrency semaphore.

        Returns:
            TestResult with metrics.
        """
        async with semaphore:
            start_time = time.time()
            try:
                response = await provider.complete(
                    messages=[{"role": "user", "content": test_case.query}],
                    max_tokens=test_case.max_tokens,
                )

                latency_ms = (time.time() - start_time) * 1000
                quality_score = self._calculate_quality(test_case, response)

                return TestResult(
                    test_case_id=test_case.id,
                    success=quality_score >= self.MIN_QUALITY_THRESHOLD,
                    response=response.content,
                    latency_ms=latency_ms,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    quality_score=quality_score,
                )

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(f"Test case {test_case.id} failed: {e}")
                return TestResult(
                    test_case_id=test_case.id,
                    success=False,
                    response="",
                    latency_ms=latency_ms,
                    input_tokens=0,
                    output_tokens=0,
                    quality_score=0.0,
                    error=str(e),
                )

    def _calculate_quality(
        self,
        test_case: TestCase,
        response: ModelResponse,
    ) -> float:
        """Calculate quality score for a response.

        Quality is based on:
        - Keyword presence (if expected_keywords defined)
        - Format compliance (if expected_format defined)
        - Response non-emptiness

        Args:
            test_case: The test case with expectations.
            response: The model's response.

        Returns:
            Quality score between 0 and 1.
        """
        if not response.content:
            return 0.0

        scores = []

        # Check keywords
        if test_case.expected_keywords:
            content_lower = response.content.lower()
            keyword_hits = sum(
                1 for kw in test_case.expected_keywords if kw.lower() in content_lower
            )
            keyword_score = keyword_hits / len(test_case.expected_keywords)
            scores.append(keyword_score)

        # Check format
        if test_case.expected_format:
            format_score = self._check_format(response.content, test_case.expected_format)
            scores.append(format_score)

        # Base score for non-empty response
        if not scores:
            return 1.0 if len(response.content) > 10 else 0.5

        return sum(scores) / len(scores)

    def _check_format(self, content: str, expected_format: str) -> float:
        """Check if response matches expected format.

        Args:
            content: Response content.
            expected_format: Expected format ('json', 'markdown', etc.).

        Returns:
            Score between 0 and 1.
        """
        if expected_format == "json":
            try:
                json.loads(content)
                return 1.0
            except json.JSONDecodeError:
                return 0.0

        if expected_format == "markdown":
            # Check for markdown indicators
            markdown_indicators = ["#", "```", "**", "- ", "1. "]
            hits = sum(1 for ind in markdown_indicators if ind in content)
            return min(hits / 2, 1.0)

        return 1.0  # Unknown format, assume OK

    def _aggregate_results(
        self,
        provider: ModelProvider,
        test_results: list[TestResult],
        duration: float,
    ) -> EvaluationResult:
        """Aggregate individual test results into evaluation result.

        Args:
            provider: The provider that was tested.
            test_results: Individual test results.
            duration: Total evaluation duration in seconds.

        Returns:
            EvaluationResult with aggregated metrics.
        """
        latencies = [r.latency_ms for r in test_results]
        latencies_sorted = sorted(latencies)

        total_input = sum(r.input_tokens for r in test_results)
        total_output = sum(r.output_tokens for r in test_results)

        # Estimate cost based on provider capabilities
        capabilities = provider.get_capabilities()
        estimated_cost = (
            total_input * capabilities.cost_per_1k_input_tokens / 1000
            + total_output * capabilities.cost_per_1k_output_tokens / 1000
        )

        # Calculate P99 latency
        p99_index = int(len(latencies_sorted) * 0.99)
        p99_latency = latencies_sorted[min(p99_index, len(latencies_sorted) - 1)]

        return EvaluationResult(
            provider_name=provider.name,
            model_id=provider.model_id,
            total_cases=len(test_results),
            passed_cases=sum(1 for r in test_results if r.success),
            failed_cases=sum(1 for r in test_results if not r.success),
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            p99_latency_ms=p99_latency,
            avg_quality_score=(
                sum(r.quality_score for r in test_results) / len(test_results)
                if test_results
                else 0
            ),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            estimated_cost_usd=estimated_cost,
            test_results=test_results,
            duration_seconds=duration,
        )

    async def save_results(
        self,
        result: EvaluationResult,
        output_path: str | Path,
    ) -> None:
        """Save evaluation results to JSON file.

        Args:
            result: Evaluation result to save.
            output_path: Path to output file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        logger.info(f"Results saved to {output_path}")
