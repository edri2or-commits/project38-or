"""Background Agents Runner - Executes agents and reports metrics.

This script is designed to be called from GitHub Actions on a schedule.
It runs the specified agent(s) and outputs results as GitHub Actions outputs.

Usage:
    python -m src.background_agents.runner --agent cost_opt
    python -m src.background_agents.runner --agent health_synth
    python -m src.background_agents.runner --agent learn_insight
    python -m src.background_agents.runner --all
    python -m src.background_agents.runner --summary  # Show daily metrics summary

ADR-013 Phase 3: Background Autonomous Jobs
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime

from src.background_agents.cost_opt_agent import CostOptAgent
from src.background_agents.health_synth_agent import HealthSynthAgent
from src.background_agents.learn_insight_agent import LearnInsightAgent
from src.background_agents.metrics import MetricsCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Agent registry
AGENTS = {
    "cost_opt": CostOptAgent,
    "health_synth": HealthSynthAgent,
    "learn_insight": LearnInsightAgent,
}


async def run_agent(agent_name: str, litellm_url: str) -> dict:
    """Run a single agent and return its result.

    Args:
        agent_name: Name of the agent to run (cost_opt, health_synth, learn_insight)
        litellm_url: URL of the LiteLLM Gateway

    Returns:
        Dictionary with agent result including success status and outputs

    Raises:
        ValueError: If agent_name is not recognized
    """
    if agent_name not in AGENTS:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(AGENTS.keys())}")

    agent_class = AGENTS[agent_name]
    agent = agent_class(litellm_url=litellm_url)

    logger.info(f"Running {agent_name}...")
    result = await agent.run()

    return result


async def run_all_agents(litellm_url: str) -> dict:
    """Run all agents and return combined results.

    Args:
        litellm_url: URL of the LiteLLM Gateway

    Returns:
        Dictionary mapping agent names to their results
    """
    results = {}

    for agent_name in AGENTS:
        try:
            result = await run_agent(agent_name, litellm_url)
            results[agent_name] = result
        except Exception as e:
            logger.error(f"Agent {agent_name} failed: {e}")
            results[agent_name] = {"success": False, "error": str(e)}

    return results


def get_metrics_summary() -> dict:
    """Get summary of today's agent metrics.

    Returns:
        Dictionary with summary statistics including runs, cost, and tokens
    """
    collector = MetricsCollector()
    return collector.get_summary(datetime.now(UTC))


def set_github_output(name: str, value: str) -> None:
    """Set GitHub Actions output variable.

    Args:
        name: Output variable name
        value: Output variable value
    """
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            # Handle multiline values
            if "\n" in value:
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")
    else:
        # Not in GitHub Actions, just print
        print(f"Output: {name}={value[:100]}...")


def main() -> int:
    """CLI entry point for running background agents.

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    parser = argparse.ArgumentParser(description="Background Agents Runner")
    parser.add_argument(
        "--agent",
        choices=list(AGENTS.keys()),
        help="Agent to run (cost_opt, health_synth, learn_insight)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all agents",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show daily metrics summary",
    )
    parser.add_argument(
        "--litellm-url",
        default="https://litellm-gateway-production-0339.up.railway.app",
        help="LiteLLM Gateway URL",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if args.summary:
        summary = get_metrics_summary()
        print("\n=== Daily Metrics Summary ===")
        print(json.dumps(summary, indent=2))
        return 0

    if not args.agent and not args.all:
        parser.print_help()
        return 1

    # Run agents
    if args.all:
        results = asyncio.run(run_all_agents(args.litellm_url))
    else:
        results = {args.agent: asyncio.run(run_agent(args.agent, args.litellm_url))}

    # Output results
    if args.output_json:
        print(json.dumps(results, indent=2))
    else:
        for agent_name, result in results.items():
            print(f"\n=== {agent_name} ===")
            if result.get("success"):
                print(f"  Status: SUCCESS")
                print(f"  Model: {result.get('model_used', 'unknown')}")
                print(f"  Tokens: {result.get('tokens_used', 0)}")
                print(f"  Cost: ${result.get('cost_usd', 0):.6f}")
                if "recommendations" in result:
                    print(f"  Recommendations: {len(result['recommendations'])}")
                if "summary" in result:
                    print(f"  Status: {result['summary'].get('overall_status', 'unknown')}")
                if "insights" in result:
                    print(f"  Insights: {len(result['insights'])}")
            else:
                print(f"  Status: FAILED")
                print(f"  Error: {result.get('error', 'unknown')}")

    # Set GitHub Actions outputs
    all_success = all(r.get("success", False) for r in results.values())
    total_cost = sum(r.get("cost_usd", 0) for r in results.values() if r.get("success"))
    total_tokens = sum(r.get("tokens_used", 0) for r in results.values() if r.get("success"))

    set_github_output("success", str(all_success).lower())
    set_github_output("total_cost_usd", f"{total_cost:.6f}")
    set_github_output("total_tokens", str(total_tokens))
    set_github_output("results_json", json.dumps(results))

    # Get and output daily summary
    summary = get_metrics_summary()
    set_github_output("daily_summary", json.dumps(summary))

    print("\n=== Daily Summary ===")
    print(json.dumps(summary, indent=2))

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
