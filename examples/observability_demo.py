"""
Observability Demo

Demonstrates how to use the observability module to track agent metrics.

Based on Research Paper #08: Real-Time Observability Dashboard.

Usage:
    python examples/observability_demo.py
"""

import asyncio
import random

from src.observability import MetricsCollector, instrument_tool
from src.observability.metrics import LatencyTracker

# Initialize metrics collector (Phase 1: in-memory fallback)
collector = MetricsCollector(db_pool=None)


# =============================================================================
# Example 1: Basic Tool Instrumentation
# =============================================================================


@instrument_tool("search_database")
async def search_database(query: str, limit: int = 10):
    """
    Example tool: Database search with automatic tracing.

    The @instrument_tool decorator automatically:
    - Creates an OTel span
    - Captures input arguments (sanitized)
    - Records success/failure
    - Tracks execution time
    """
    # Simulate database lookup
    await asyncio.sleep(random.uniform(0.1, 0.5))

    # Simulate occasional errors
    if random.random() < 0.1:  # 10% error rate
        raise ValueError("Database connection timeout")

    return [f"Result {i} for '{query}'" for i in range(limit)]


# =============================================================================
# Example 2: Manual Metrics Recording
# =============================================================================


async def agent_task_with_metrics():
    """
    Example: Agent task with manual metrics recording.

    Demonstrates:
    - Latency tracking with context manager
    - Token usage recording
    - Success/error recording
    """
    agent_id = "agent-demo-001"

    # Track latency automatically
    async with LatencyTracker(collector, agent_id, {"task": "search"}):
        try:
            # Simulate agent work
            results = await search_database("AI observability", limit=5)

            # Record token usage (simulated)
            await collector.record_tokens(
                agent_id=agent_id,
                input_tokens=100,
                output_tokens=50,
                model_id="claude-sonnet-4.5",
                reasoning_tokens=200,  # 2026 models with reasoning tokens
                labels={"environment": "demo"},
            )

            # Record success
            await collector.record_success(
                agent_id=agent_id, task_type="search", labels={"results_count": str(len(results))}
            )

            print(f"✅ Success: Found {len(results)} results")

        except Exception as e:
            # Record error
            await collector.record_error(
                agent_id=agent_id, error_type=type(e).__name__, error_message=str(e)
            )
            print(f"❌ Error: {e}")


# =============================================================================
# Example 3: Simulated Agent Fleet
# =============================================================================


async def simulate_agent_fleet(num_agents: int = 5, duration_seconds: int = 30):
    """
    Simulate a fleet of agents generating metrics.

    Args:
        num_agents: Number of concurrent agents
        duration_seconds: How long to run simulation
    """
    print(f"🚀 Starting simulation: {num_agents} agents for {duration_seconds}s")

    async def agent_worker(agent_id: str):
        """Single agent worker."""
        while True:
            try:
                await agent_task_with_metrics()
                # Random delay between tasks
                await asyncio.sleep(random.uniform(1, 3))
            except asyncio.CancelledError:
                break

    # Start all agents
    tasks = [asyncio.create_task(agent_worker(f"agent-{i:03d}")) for i in range(num_agents)]

    # Run for specified duration
    await asyncio.sleep(duration_seconds)

    # Cancel all tasks
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    print("\n📊 Simulation complete!")
    print(f"Collected {len(collector._in_memory_buffer)} metrics")

    # Show summary
    print_metrics_summary()


def print_metrics_summary():
    """Print summary of collected metrics."""
    buffer = collector._in_memory_buffer

    if not buffer:
        print("No metrics collected yet.")
        return

    # Group by metric name
    by_metric = {}
    for metric in buffer:
        if metric.metric_name not in by_metric:
            by_metric[metric.metric_name] = []
        by_metric[metric.metric_name].append(metric.value)

    print("\n📈 Metrics Summary:")
    print("-" * 60)
    for metric_name, values in by_metric.items():
        avg = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)
        print(
            f"{metric_name:20s} | Count: {len(values):4d} | "
            f"Avg: {avg:8.2f} | Min: {min_val:8.2f} | Max: {max_val:8.2f}"
        )


# =============================================================================
# Main
# =============================================================================


async def main():
    """Main demo function."""
    print("=" * 60)
    print("Project38-OR Observability Demo")
    print("=" * 60)
    print()

    # Example 1: Single task
    print("Example 1: Single Agent Task")
    print("-" * 60)
    await agent_task_with_metrics()
    print()

    # Example 2: Multiple tasks
    print("\nExample 2: Multiple Tasks")
    print("-" * 60)
    for i in range(5):
        await agent_task_with_metrics()
    print()

    print_metrics_summary()
    print()

    # Example 3: Agent fleet simulation (optional, commented out)
    # Uncomment to run full simulation:
    # print("\nExample 3: Agent Fleet Simulation")
    # print("-" * 60)
    # await simulate_agent_fleet(num_agents=3, duration_seconds=10)

    print("\n✅ Demo complete!")
    print("\nNext steps:")
    print("1. Set up TimescaleDB (see sql/observability_schema.sql)")
    print("2. Configure database connection in MetricsCollector")
    print("3. Start FastAPI server and access /metrics/summary")
    print("4. Build real-time dashboard with /metrics/timeseries")


if __name__ == "__main__":
    asyncio.run(main())
