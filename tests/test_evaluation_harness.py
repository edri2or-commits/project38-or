"""Tests for src/evaluation/harness.py - Evaluation Harness."""

import json
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestDecisionEnum:
    """Tests for Decision enum."""

    def test_decision_import(self):
        """Decision should be importable."""
        from src.evaluation.harness import Decision

        assert Decision is not None

    def test_decision_values(self):
        """Decision should have ADOPT, REJECT, NEEDS_MORE_DATA."""
        from src.evaluation.harness import Decision

        assert Decision.ADOPT.value == "ADOPT"
        assert Decision.REJECT.value == "REJECT"
        assert Decision.NEEDS_MORE_DATA.value == "NEEDS_MORE_DATA"


class TestTestCase:
    """Tests for TestCase dataclass."""

    def test_test_case_import(self):
        """TestCase should be importable."""
        from src.evaluation.harness import TestCase

        assert TestCase is not None

    def test_test_case_required_fields(self):
        """TestCase should require id, category, query."""
        from src.evaluation.harness import TestCase

        tc = TestCase(
            id="test-001",
            category="basic",
            query="What is 2+2?",
        )
        assert tc.id == "test-001"
        assert tc.category == "basic"
        assert tc.query == "What is 2+2?"

    def test_test_case_defaults(self):
        """TestCase should have sensible defaults."""
        from src.evaluation.harness import TestCase

        tc = TestCase(id="test-001", category="basic", query="Test")
        assert tc.expected_keywords == []
        assert tc.expected_format is None
        assert tc.max_tokens == 1024
        assert tc.metadata == {}

    def test_test_case_from_dict(self):
        """TestCase.from_dict should create TestCase."""
        from src.evaluation.harness import TestCase

        data = {
            "id": "tc-001",
            "category": "complex",
            "query": "Write a function",
            "expected_keywords": ["def", "return"],
            "expected_format": "markdown",
            "max_tokens": 2048,
            "metadata": {"difficulty": "hard"},
        }
        tc = TestCase.from_dict(data)

        assert tc.id == "tc-001"
        assert tc.category == "complex"
        assert tc.expected_keywords == ["def", "return"]
        assert tc.max_tokens == 2048

    def test_test_case_from_dict_minimal(self):
        """TestCase.from_dict should work with minimal data."""
        from src.evaluation.harness import TestCase

        data = {"id": "tc-001", "query": "Hello"}
        tc = TestCase.from_dict(data)

        assert tc.id == "tc-001"
        assert tc.category == "general"  # Default


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_test_result_import(self):
        """TestResult should be importable."""
        from src.evaluation.harness import TestResult

        assert TestResult is not None

    def test_test_result_required_fields(self):
        """TestResult should require specific fields."""
        from src.evaluation.harness import TestResult

        result = TestResult(
            test_case_id="tc-001",
            success=True,
            response="The answer is 4",
            latency_ms=150.0,
            input_tokens=10,
            output_tokens=5,
            quality_score=0.95,
        )
        assert result.test_case_id == "tc-001"
        assert result.success is True
        assert result.quality_score == 0.95

    def test_test_result_defaults(self):
        """TestResult should have sensible defaults."""
        from src.evaluation.harness import TestResult

        result = TestResult(
            test_case_id="tc-001",
            success=True,
            response="Test",
            latency_ms=100.0,
            input_tokens=10,
            output_tokens=5,
            quality_score=0.9,
        )
        assert result.error is None
        assert result.timestamp is not None


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_evaluation_result_import(self):
        """EvaluationResult should be importable."""
        from src.evaluation.harness import EvaluationResult

        assert EvaluationResult is not None

    def test_evaluation_result_success_rate(self):
        """EvaluationResult.success_rate should calculate correctly."""
        from src.evaluation.harness import EvaluationResult

        result = EvaluationResult(
            provider_name="test",
            model_id="test-v1",
            total_cases=100,
            passed_cases=90,
            failed_cases=10,
            avg_latency_ms=150.0,
            p99_latency_ms=500.0,
            avg_quality_score=0.9,
            total_input_tokens=1000,
            total_output_tokens=500,
            estimated_cost_usd=0.05,
            test_results=[],
        )
        assert result.success_rate == 90.0

    def test_evaluation_result_success_rate_zero(self):
        """EvaluationResult.success_rate should handle zero cases."""
        from src.evaluation.harness import EvaluationResult

        result = EvaluationResult(
            provider_name="test",
            model_id="test-v1",
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            avg_latency_ms=0.0,
            p99_latency_ms=0.0,
            avg_quality_score=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            estimated_cost_usd=0.0,
            test_results=[],
        )
        assert result.success_rate == 0.0

    def test_evaluation_result_to_dict(self):
        """EvaluationResult.to_dict should return dict."""
        from src.evaluation.harness import EvaluationResult

        result = EvaluationResult(
            provider_name="test",
            model_id="test-v1",
            total_cases=50,
            passed_cases=45,
            failed_cases=5,
            avg_latency_ms=200.0,
            p99_latency_ms=800.0,
            avg_quality_score=0.9,
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.25,
            test_results=[],
        )
        d = result.to_dict()

        assert d["provider_name"] == "test"
        assert d["success_rate"] == 90.0
        assert "timestamp" in d


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_comparison_result_import(self):
        """ComparisonResult should be importable."""
        from src.evaluation.harness import ComparisonResult

        assert ComparisonResult is not None

    def test_comparison_result_to_dict(self):
        """ComparisonResult.to_dict should return dict."""
        from src.evaluation.harness import ComparisonResult, Decision, EvaluationResult

        baseline = EvaluationResult(
            provider_name="baseline",
            model_id="base-v1",
            total_cases=50,
            passed_cases=45,
            failed_cases=5,
            avg_latency_ms=200.0,
            p99_latency_ms=800.0,
            avg_quality_score=0.9,
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.25,
            test_results=[],
        )
        experiment = EvaluationResult(
            provider_name="experiment",
            model_id="exp-v1",
            total_cases=50,
            passed_cases=48,
            failed_cases=2,
            avg_latency_ms=150.0,
            p99_latency_ms=600.0,
            avg_quality_score=0.95,
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.20,
            test_results=[],
        )
        comparison = ComparisonResult(
            decision=Decision.ADOPT,
            baseline=baseline,
            experiment=experiment,
            quality_delta=0.05,
            latency_delta_pct=-25.0,
            cost_delta_pct=-20.0,
            reasons=["All metrics improved"],
        )
        d = comparison.to_dict()

        assert d["decision"] == "ADOPT"
        assert d["quality_delta"] == 0.05
        assert "baseline" in d
        assert "experiment" in d


class TestEvaluationHarnessInit:
    """Tests for EvaluationHarness initialization."""

    def test_evaluation_harness_import(self):
        """EvaluationHarness should be importable."""
        from src.evaluation.harness import EvaluationHarness

        assert EvaluationHarness is not None

    def test_evaluation_harness_init(self):
        """EvaluationHarness should initialize."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        assert harness is not None

    def test_evaluation_harness_thresholds(self):
        """EvaluationHarness should have threshold constants."""
        from src.evaluation.harness import EvaluationHarness

        assert EvaluationHarness.MIN_QUALITY_THRESHOLD == 0.85
        assert EvaluationHarness.MAX_LATENCY_INCREASE_PCT == 100
        assert EvaluationHarness.MAX_COST_INCREASE_PCT == 50
        assert EvaluationHarness.MIN_TEST_CASES == 20


class TestEvaluationHarnessLoadGoldenSet:
    """Tests for EvaluationHarness._load_golden_set method."""

    def test_load_golden_set_success(self):
        """_load_golden_set should load test cases from JSON."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"id": "tc-001", "query": "Test query"}], f)
            f.flush()

            test_cases = harness._load_golden_set(f.name)

        assert len(test_cases) == 1
        assert test_cases[0].id == "tc-001"

    def test_load_golden_set_not_found(self):
        """_load_golden_set should raise FileNotFoundError."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()

        with pytest.raises(FileNotFoundError):
            harness._load_golden_set("/nonexistent/path.json")

    def test_load_golden_set_empty(self):
        """_load_golden_set should raise ValueError for empty file."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            f.flush()

            with pytest.raises(ValueError, match="non-empty list"):
                harness._load_golden_set(f.name)


class TestEvaluationHarnessCalculateQuality:
    """Tests for EvaluationHarness._calculate_quality method."""

    def test_calculate_quality_empty_response(self):
        """_calculate_quality should return 0 for empty response."""
        from src.evaluation.harness import EvaluationHarness, TestCase

        harness = EvaluationHarness()
        test_case = TestCase(id="tc-001", category="basic", query="Test")

        mock_response = MagicMock()
        mock_response.content = ""

        score = harness._calculate_quality(test_case, mock_response)
        assert score == 0.0

    def test_calculate_quality_with_keywords(self):
        """_calculate_quality should check keywords."""
        from src.evaluation.harness import EvaluationHarness, TestCase

        harness = EvaluationHarness()
        test_case = TestCase(
            id="tc-001",
            category="basic",
            query="Test",
            expected_keywords=["python", "function"],
        )

        mock_response = MagicMock()
        mock_response.content = "Here is a Python function that solves the problem"

        score = harness._calculate_quality(test_case, mock_response)
        assert score == 1.0  # Both keywords found

    def test_calculate_quality_partial_keywords(self):
        """_calculate_quality should handle partial keyword matches."""
        from src.evaluation.harness import EvaluationHarness, TestCase

        harness = EvaluationHarness()
        test_case = TestCase(
            id="tc-001",
            category="basic",
            query="Test",
            expected_keywords=["python", "java", "rust"],
        )

        mock_response = MagicMock()
        mock_response.content = "Here is Python code"

        score = harness._calculate_quality(test_case, mock_response)
        assert score == pytest.approx(1 / 3, 0.01)  # 1 of 3 keywords

    def test_calculate_quality_no_keywords(self):
        """_calculate_quality should return 1.0 for non-empty response without keywords."""
        from src.evaluation.harness import EvaluationHarness, TestCase

        harness = EvaluationHarness()
        test_case = TestCase(id="tc-001", category="basic", query="Test")

        mock_response = MagicMock()
        mock_response.content = "This is a valid response with enough content"

        score = harness._calculate_quality(test_case, mock_response)
        assert score == 1.0


class TestEvaluationHarnessCheckFormat:
    """Tests for EvaluationHarness._check_format method."""

    def test_check_format_json_valid(self):
        """_check_format should return 1.0 for valid JSON."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        score = harness._check_format('{"key": "value"}', "json")
        assert score == 1.0

    def test_check_format_json_invalid(self):
        """_check_format should return 0.0 for invalid JSON."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        score = harness._check_format("not json", "json")
        assert score == 0.0

    def test_check_format_markdown(self):
        """_check_format should detect markdown indicators."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()

        # With markdown indicators
        content = "# Header\n\n```python\ncode\n```\n\n- list item"
        score = harness._check_format(content, "markdown")
        assert score == 1.0

    def test_check_format_unknown(self):
        """_check_format should return 1.0 for unknown format."""
        from src.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        score = harness._check_format("anything", "unknown_format")
        assert score == 1.0


class TestEvaluationHarnessCompare:
    """Tests for EvaluationHarness.compare method."""

    def test_compare_adopt_all_better(self):
        """compare should return ADOPT when all metrics improve."""
        from src.evaluation.harness import Decision, EvaluationHarness, EvaluationResult

        harness = EvaluationHarness()

        baseline = EvaluationResult(
            provider_name="baseline",
            model_id="base-v1",
            total_cases=25,
            passed_cases=20,
            failed_cases=5,
            avg_latency_ms=200.0,
            p99_latency_ms=800.0,
            avg_quality_score=0.85,
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.25,
            test_results=[],
        )
        experiment = EvaluationResult(
            provider_name="experiment",
            model_id="exp-v1",
            total_cases=25,
            passed_cases=24,
            failed_cases=1,
            avg_latency_ms=100.0,  # Better
            p99_latency_ms=400.0,
            avg_quality_score=0.95,  # Better
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.15,  # Better
            test_results=[],
        )

        result = harness.compare(baseline, experiment)
        assert result.decision == Decision.ADOPT

    def test_compare_reject_quality_worse(self):
        """compare should return REJECT when quality degrades."""
        from src.evaluation.harness import Decision, EvaluationHarness, EvaluationResult

        harness = EvaluationHarness()

        baseline = EvaluationResult(
            provider_name="baseline",
            model_id="base-v1",
            total_cases=25,
            passed_cases=23,
            failed_cases=2,
            avg_latency_ms=200.0,
            p99_latency_ms=800.0,
            avg_quality_score=0.95,  # High quality
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.25,
            test_results=[],
        )
        experiment = EvaluationResult(
            provider_name="experiment",
            model_id="exp-v1",
            total_cases=25,
            passed_cases=20,
            failed_cases=5,
            avg_latency_ms=100.0,  # Better latency
            p99_latency_ms=400.0,
            avg_quality_score=0.80,  # Worse quality!
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.10,  # Better cost
            test_results=[],
        )

        result = harness.compare(baseline, experiment)
        assert result.decision == Decision.REJECT

    def test_compare_needs_more_data_insufficient_tests(self):
        """compare should return NEEDS_MORE_DATA for insufficient tests."""
        from src.evaluation.harness import Decision, EvaluationHarness, EvaluationResult

        harness = EvaluationHarness()

        baseline = EvaluationResult(
            provider_name="baseline",
            model_id="base-v1",
            total_cases=10,  # Too few
            passed_cases=9,
            failed_cases=1,
            avg_latency_ms=200.0,
            p99_latency_ms=800.0,
            avg_quality_score=0.9,
            total_input_tokens=1000,
            total_output_tokens=500,
            estimated_cost_usd=0.05,
            test_results=[],
        )
        experiment = EvaluationResult(
            provider_name="experiment",
            model_id="exp-v1",
            total_cases=10,  # Too few
            passed_cases=10,
            failed_cases=0,
            avg_latency_ms=100.0,
            p99_latency_ms=400.0,
            avg_quality_score=0.95,
            total_input_tokens=1000,
            total_output_tokens=500,
            estimated_cost_usd=0.03,
            test_results=[],
        )

        result = harness.compare(baseline, experiment)
        assert result.decision == Decision.NEEDS_MORE_DATA

    def test_compare_calculates_deltas(self):
        """compare should calculate correct deltas."""
        from src.evaluation.harness import EvaluationHarness, EvaluationResult

        harness = EvaluationHarness()

        baseline = EvaluationResult(
            provider_name="baseline",
            model_id="base-v1",
            total_cases=25,
            passed_cases=20,
            failed_cases=5,
            avg_latency_ms=200.0,
            p99_latency_ms=800.0,
            avg_quality_score=0.90,
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.20,
            test_results=[],
        )
        experiment = EvaluationResult(
            provider_name="experiment",
            model_id="exp-v1",
            total_cases=25,
            passed_cases=24,
            failed_cases=1,
            avg_latency_ms=150.0,  # -25%
            p99_latency_ms=600.0,
            avg_quality_score=0.95,  # +5%
            total_input_tokens=5000,
            total_output_tokens=2500,
            estimated_cost_usd=0.16,  # -20%
            test_results=[],
        )

        result = harness.compare(baseline, experiment)

        assert result.quality_delta == pytest.approx(0.05, 0.001)
        assert result.latency_delta_pct == pytest.approx(-25.0, 0.1)
        assert result.cost_delta_pct == pytest.approx(-20.0, 0.1)


class TestEvaluationHarnessRunTestCase:
    """Tests for EvaluationHarness._run_test_case method."""

    @pytest.mark.asyncio
    async def test_run_test_case_success(self):
        """_run_test_case should return TestResult on success."""
        import asyncio

        from src.evaluation.harness import EvaluationHarness, TestCase

        harness = EvaluationHarness()
        test_case = TestCase(id="tc-001", category="basic", query="Hello")

        mock_response = MagicMock()
        mock_response.content = "Hello, world!"
        mock_response.input_tokens = 5
        mock_response.output_tokens = 3

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        semaphore = asyncio.Semaphore(1)
        result = await harness._run_test_case(mock_provider, test_case, semaphore)

        assert result.test_case_id == "tc-001"
        assert result.response == "Hello, world!"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_test_case_error(self):
        """_run_test_case should handle errors gracefully."""
        import asyncio

        from src.evaluation.harness import EvaluationHarness, TestCase

        harness = EvaluationHarness()
        test_case = TestCase(id="tc-001", category="basic", query="Hello")

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=Exception("API Error"))

        semaphore = asyncio.Semaphore(1)
        result = await harness._run_test_case(mock_provider, test_case, semaphore)

        assert result.test_case_id == "tc-001"
        assert result.success is False
        assert result.error == "API Error"
        assert result.quality_score == 0.0


class TestEvaluationHarnessAggregateResults:
    """Tests for EvaluationHarness._aggregate_results method."""

    def test_aggregate_results(self):
        """_aggregate_results should calculate aggregated metrics."""
        from src.evaluation.harness import EvaluationHarness, TestResult
        from src.providers.base import ModelCapabilities

        harness = EvaluationHarness()

        test_results = [
            TestResult(
                test_case_id="tc-001",
                success=True,
                response="Response 1",
                latency_ms=100.0,
                input_tokens=50,
                output_tokens=25,
                quality_score=0.9,
            ),
            TestResult(
                test_case_id="tc-002",
                success=True,
                response="Response 2",
                latency_ms=200.0,
                input_tokens=60,
                output_tokens=30,
                quality_score=0.95,
            ),
            TestResult(
                test_case_id="tc-003",
                success=False,
                response="",
                latency_ms=300.0,
                input_tokens=40,
                output_tokens=0,
                quality_score=0.0,
                error="Timeout",
            ),
        ]

        mock_provider = MagicMock()
        mock_provider.name = "test"
        mock_provider.model_id = "test-v1"
        mock_provider.get_capabilities.return_value = ModelCapabilities(
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
        )

        result = harness._aggregate_results(mock_provider, test_results, 5.0)

        assert result.provider_name == "test"
        assert result.total_cases == 3
        assert result.passed_cases == 2
        assert result.failed_cases == 1
        assert result.avg_latency_ms == 200.0
        assert result.total_input_tokens == 150
        assert result.total_output_tokens == 55
        assert result.duration_seconds == 5.0
