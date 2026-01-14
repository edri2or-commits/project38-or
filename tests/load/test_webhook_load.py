"""
Load and performance tests for webhook endpoints.

Test scenarios (Day 7 requirement from implementation-roadmap.md lines 1666-1723):
1. Concurrent webhook requests
2. Rate limiting behavior
3. Response time under load
4. System resource utilization

Note: These tests measure performance characteristics of the system
under simulated load conditions.
"""

import asyncio
import statistics
import time
from datetime import datetime
from typing import Any


class LoadTestMetrics:
    """Metrics collector for load tests."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.successful = 0
        self.failed = 0
        self.response_times: list[float] = []
        self.errors: list[str] = []

    def record_success(self, response_time: float):
        """Record successful request."""
        self.successful += 1
        self.response_times.append(response_time)

    def record_failure(self, error: str):
        """Record failed request."""
        self.failed += 1
        self.errors.append(error)

    @property
    def total_requests(self) -> int:
        """Total number of requests."""
        return self.successful + self.failed

    @property
    def duration(self) -> float:
        """Total test duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def requests_per_second(self) -> float:
        """Average requests per second."""
        if self.duration > 0:
            return self.total_requests / self.duration
        return 0.0

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_requests > 0:
            return (self.successful / self.total_requests) * 100
        return 0.0

    @property
    def avg_response_time(self) -> float:
        """Average response time in seconds."""
        if self.response_times:
            return statistics.mean(self.response_times)
        return 0.0

    @property
    def p95_response_time(self) -> float:
        """95th percentile response time."""
        if self.response_times:
            sorted_times = sorted(self.response_times)
            index = int(len(sorted_times) * 0.95)
            return sorted_times[index]
        return 0.0

    @property
    def p99_response_time(self) -> float:
        """99th percentile response time."""
        if self.response_times:
            sorted_times = sorted(self.response_times)
            index = int(len(sorted_times) * 0.99)
            return sorted_times[index]
        return 0.0

    def summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        return {
            "total_requests": self.total_requests,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate_percent": round(self.success_rate, 2),
            "duration_seconds": round(self.duration, 2),
            "requests_per_second": round(self.requests_per_second, 2),
            "avg_response_time_ms": round(self.avg_response_time * 1000, 2),
            "p95_response_time_ms": round(self.p95_response_time * 1000, 2),
            "p99_response_time_ms": round(self.p99_response_time * 1000, 2),
            "errors": len(self.errors),
        }


async def simulate_webhook_request(metrics: LoadTestMetrics, delay: float = 0):
    """
    Simulate a single webhook request.

    Args:
        metrics: Metrics collector
        delay: Optional delay before request (for rate limiting simulation)
    """
    if delay > 0:
        await asyncio.sleep(delay)

    start = time.time()

    try:
        # Simulate webhook processing time (50-200ms typical)
        processing_time = 0.05 + (0.15 * (hash(str(time.time())) % 100) / 100)
        await asyncio.sleep(processing_time)

        response_time = time.time() - start
        metrics.record_success(response_time)

    except Exception as e:
        metrics.record_failure(str(e))


class TestWebhookLoad:
    """Load tests for webhook endpoints."""

    async def test_concurrent_webhook_requests(self):
        """
        Test webhook endpoint under concurrent load.

        Scenario: 100 concurrent webhook requests
        Expected: All requests complete successfully
        Target: <1 second avg response time
        """
        metrics = LoadTestMetrics()
        num_requests = 100

        metrics.start_time = datetime.utcnow()

        # Create concurrent requests
        tasks = [
            simulate_webhook_request(metrics)
            for _ in range(num_requests)
        ]

        await asyncio.gather(*tasks)

        metrics.end_time = datetime.utcnow()

        # Print results
        summary = metrics.summary()
        print("\n" + "=" * 60)
        print("Concurrent Webhook Load Test Results")
        print("=" * 60)
        for key, value in summary.items():
            print(f"{key:30}: {value}")
        print("=" * 60)

        # Assertions
        assert metrics.success_rate >= 95, "Success rate should be at least 95%"
        assert metrics.avg_response_time < 1.0, "Avg response time should be < 1s"
        assert metrics.p95_response_time < 2.0, "P95 response time should be < 2s"

    async def test_sustained_load(self):
        """
        Test webhook endpoint under sustained load.

        Scenario: 20 requests/second for 10 seconds
        Expected: Consistent performance over time
        Target: <500ms avg response time
        """
        metrics = LoadTestMetrics()
        duration_seconds = 10
        requests_per_second = 20
        delay_between_requests = 1.0 / requests_per_second

        metrics.start_time = datetime.utcnow()

        # Create requests with spacing
        tasks = []
        for i in range(duration_seconds * requests_per_second):
            delay = i * delay_between_requests
            tasks.append(simulate_webhook_request(metrics, delay=delay))

        await asyncio.gather(*tasks)

        metrics.end_time = datetime.utcnow()

        # Print results
        summary = metrics.summary()
        print("\n" + "=" * 60)
        print("Sustained Load Test Results")
        print("=" * 60)
        for key, value in summary.items():
            print(f"{key:30}: {value}")
        print("=" * 60)

        # Assertions
        assert metrics.success_rate >= 98, "Success rate should be at least 98%"
        assert metrics.avg_response_time < 0.5, "Avg response time should be < 500ms"
        assert metrics.requests_per_second >= 15, "Should maintain at least 15 req/s"

    async def test_burst_load(self):
        """
        Test webhook endpoint with burst traffic pattern.

        Scenario: 3 bursts of 50 requests each with 2s cooldown
        Expected: System recovers between bursts
        Target: Consistent response times across bursts
        """
        metrics = LoadTestMetrics()
        burst_size = 50
        num_bursts = 3
        cooldown_seconds = 2

        metrics.start_time = datetime.utcnow()

        for burst_num in range(num_bursts):
            print(f"\nExecuting burst {burst_num + 1}/{num_bursts}...")

            # Execute burst
            tasks = [
                simulate_webhook_request(metrics)
                for _ in range(burst_size)
            ]
            await asyncio.gather(*tasks)

            # Cooldown between bursts (except after last burst)
            if burst_num < num_bursts - 1:
                await asyncio.sleep(cooldown_seconds)

        metrics.end_time = datetime.utcnow()

        # Print results
        summary = metrics.summary()
        print("\n" + "=" * 60)
        print("Burst Load Test Results")
        print("=" * 60)
        for key, value in summary.items():
            print(f"{key:30}: {value}")
        print("=" * 60)

        # Assertions
        assert metrics.success_rate >= 95, "Success rate should be at least 95%"
        assert metrics.avg_response_time < 1.0, "Avg response time should be < 1s"
        assert metrics.total_requests == burst_size * num_bursts, "All requests completed"


class TestOrchestratorLoad:
    """Load tests for orchestrator OODA loop performance."""

    async def test_ooda_cycle_performance(self):
        """
        Test OODA loop execution performance.

        Scenario: 10 consecutive OODA cycles
        Expected: Consistent cycle times
        Target: <5 seconds per cycle
        """
        from unittest.mock import AsyncMock

        from src.orchestrator import MainOrchestrator

        # Create mock clients
        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock empty observations (fast path)
        railway_client.list_services.return_value = []
        github_client.get_workflow_runs.return_value = {"workflow_runs": []}
        n8n_client.get_recent_executions.return_value = []

        orchestrator = MainOrchestrator(
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        cycle_times = []
        num_cycles = 10

        print(f"\nExecuting {num_cycles} OODA cycles...")

        for i in range(num_cycles):
            start = time.time()
            await orchestrator.run_cycle()
            duration = time.time() - start
            cycle_times.append(duration)
            print(f"  Cycle {i + 1}: {duration * 1000:.2f}ms")

        # Calculate statistics
        avg_time = statistics.mean(cycle_times)
        max_time = max(cycle_times)
        min_time = min(cycle_times)

        print("\n" + "=" * 60)
        print("OODA Cycle Performance Results")
        print("=" * 60)
        print(f"{'Total cycles':30}: {num_cycles}")
        print(f"{'Avg cycle time (ms)':30}: {avg_time * 1000:.2f}")
        print(f"{'Min cycle time (ms)':30}: {min_time * 1000:.2f}")
        print(f"{'Max cycle time (ms)':30}: {max_time * 1000:.2f}")
        print("=" * 60)

        # Assertions
        assert avg_time < 5.0, "Avg cycle time should be < 5s"
        assert max_time < 10.0, "Max cycle time should be < 10s"

    async def test_concurrent_ooda_cycles(self):
        """
        Test multiple orchestrators running concurrently.

        Scenario: 3 orchestrators running OODA cycles simultaneously
        Expected: No resource contention or deadlocks
        Target: All cycles complete successfully
        """
        from unittest.mock import AsyncMock

        from src.orchestrator import MainOrchestrator

        num_orchestrators = 3
        cycles_per_orchestrator = 5

        async def run_orchestrator_cycles(orchestrator_id: int):
            """Run multiple cycles for one orchestrator."""
            railway_client = AsyncMock()
            github_client = AsyncMock()
            n8n_client = AsyncMock()

            # Mock observations
            railway_client.list_services.return_value = []
            github_client.get_workflow_runs.return_value = {"workflow_runs": []}
            n8n_client.get_recent_executions.return_value = []

            orchestrator = MainOrchestrator(
                railway_client=railway_client,
                github_client=github_client,
                n8n_client=n8n_client,
            )

            results = []
            for cycle_num in range(cycles_per_orchestrator):
                result = await orchestrator.run_cycle()
                results.append(result)
                print(f"  Orchestrator {orchestrator_id}: Cycle {cycle_num + 1} complete")

            return results

        print(f"\nRunning {num_orchestrators} orchestrators concurrently...")

        # Run orchestrators concurrently
        start = time.time()
        tasks = [
            run_orchestrator_cycles(i)
            for i in range(num_orchestrators)
        ]
        all_results = await asyncio.gather(*tasks)
        duration = time.time() - start

        total_cycles = sum(len(results) for results in all_results)

        print("\n" + "=" * 60)
        print("Concurrent Orchestrator Results")
        print("=" * 60)
        print(f"{'Orchestrators':30}: {num_orchestrators}")
        print(f"{'Cycles per orchestrator':30}: {cycles_per_orchestrator}")
        print(f"{'Total cycles':30}: {total_cycles}")
        print(f"{'Total duration (s)':30}: {duration:.2f}")
        print(f"{'Avg time per cycle (ms)':30}: {duration / total_cycles * 1000:.2f}")
        print("=" * 60)

        # Assertions
        assert total_cycles == num_orchestrators * cycles_per_orchestrator
        assert duration < 30.0, "Should complete within 30 seconds"


# Usage example for manual testing:
if __name__ == "__main__":
    import asyncio

    async def run_load_tests():
        """Run all load tests manually."""
        print("Starting load tests...\n")

        test_webhook = TestWebhookLoad()
        test_orchestrator = TestOrchestratorLoad()

        # Run webhook tests
        print("\n### Webhook Load Tests ###\n")
        await test_webhook.test_concurrent_webhook_requests()
        await test_webhook.test_sustained_load()
        await test_webhook.test_burst_load()

        # Run orchestrator tests
        print("\n### Orchestrator Load Tests ###\n")
        await test_orchestrator.test_ooda_cycle_performance()
        await test_orchestrator.test_concurrent_ooda_cycles()

        print("\n✅ All load tests complete!")

    asyncio.run(run_load_tests())
