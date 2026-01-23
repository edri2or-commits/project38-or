"""Learning Insights Agent - Generates strategic insights from action history.

Uses SmartLLMClient with TaskType.COMPLEX (routes to claude-sonnet, Tier 3).
Runs every 8 hours (3 runs per 24 hours).

Input: Action history from src/learning_service.py
Output: Strategic insights and improvement recommendations

ADR-013 Phase 3: Background Autonomous Jobs
"""

import json
import logging
import time
from dataclasses import dataclass

from src.background_agents.metrics import AgentMetrics, MetricsCollector, generate_run_id
from src.smart_llm.classifier import TaskType

logger = logging.getLogger(__name__)


@dataclass
class StrategicInsight:
    """A strategic insight derived from learning data."""

    category: str  # "pattern", "trend", "opportunity", "risk"
    title: str
    description: str
    evidence: list[str]  # Supporting data points
    confidence: float  # 0.0 - 1.0
    actionable: bool
    suggested_action: str | None


class LearnInsightAgent:
    """Autonomous agent that generates strategic insights from action history.

    Uses SmartLLMClient with COMPLEX task type (routes to claude-sonnet).
    This is a premium tier ($15/1M) for complex pattern recognition.

    Example:
        agent = LearnInsightAgent(litellm_url="https://litellm-gateway.railway.app")
        result = await agent.run()
        for insight in result['insights']:
            print(f"- {insight['title']}")
    """

    AGENT_NAME = "learn_insight_agent"
    MODEL_TASK_TYPE = TaskType.COMPLEX  # → claude-sonnet (Tier 3)

    def __init__(
        self,
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
        metrics_collector: MetricsCollector | None = None,
    ):
        """Initialize LearnInsightAgent.

        Args:
            litellm_url: URL of LiteLLM Gateway
            metrics_collector: Optional metrics collector for tracking
        """
        self.litellm_url = litellm_url
        self.metrics_collector = metrics_collector or MetricsCollector()

    async def _get_learning_data(self) -> dict:
        """Fetch learning data from GitHub Actions workflow history.

        Analyzes real workflow runs to extract patterns and insights.
        This provides actual action history without needing database access.
        """
        import os

        import httpx

        learning_data = {
            "period": "last_30_days",
            "total_actions": 0,
            "actions_by_type": {},
            "failure_patterns": [],
            "success_patterns": [],
            "resource_usage_trends": {},
            "agent_performance": {},
            "previous_insights": [],
            "data_source": "github_actions",
        }

        # Get GitHub token from environment
        gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not gh_token:
            logger.warning("No GitHub token available, using minimal data")
            learning_data["data_source"] = "minimal"
            learning_data["actions_by_type"] = {
                "workflow_run": {"count": 0, "success_rate": 0, "note": "No token available"},
            }
            return learning_data

        headers = {
            "Authorization": f"token {gh_token}",
            "Accept": "application/vnd.github+json",
        }

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            # Get recent workflow runs
            try:
                response = await client.get(
                    "https://api.github.com/repos/edri2or-commits/project38-or/actions/runs",
                    params={"per_page": 100},
                )

                if response.status_code == 200:
                    runs_data = response.json()
                    runs = runs_data.get("workflow_runs", [])

                    # Analyze workflow runs by name
                    workflow_stats: dict[str, dict] = {}
                    for run in runs:
                        wf_name = run.get("name", "unknown")
                        if wf_name not in workflow_stats:
                            workflow_stats[wf_name] = {
                                "count": 0,
                                "success": 0,
                                "failure": 0,
                                "total_duration_ms": 0,
                            }

                        workflow_stats[wf_name]["count"] += 1
                        if run.get("conclusion") == "success":
                            workflow_stats[wf_name]["success"] += 1
                        elif run.get("conclusion") == "failure":
                            workflow_stats[wf_name]["failure"] += 1

                        learning_data["total_actions"] += 1

                    # Convert to expected format
                    for wf_name, stats in workflow_stats.items():
                        success_rate = (
                            stats["success"] / stats["count"]
                            if stats["count"] > 0
                            else 0
                        )
                        learning_data["actions_by_type"][wf_name] = {
                            "count": stats["count"],
                            "success_rate": round(success_rate, 3),
                            "failures": stats["failure"],
                        }

                    # Identify failure patterns
                    for wf_name, stats in workflow_stats.items():
                        if stats["failure"] > 2:
                            failure_rate = stats["failure"] / stats["count"]
                            learning_data["failure_patterns"].append({
                                "pattern": f"{wf_name}_failures",
                                "failures": stats["failure"],
                                "total": stats["count"],
                                "failure_rate": round(failure_rate, 3),
                            })

                    # Identify success patterns
                    for wf_name, stats in workflow_stats.items():
                        if stats["count"] >= 5 and stats["failure"] == 0:
                            learning_data["success_patterns"].append({
                                "pattern": f"{wf_name}_reliable",
                                "description": f"{wf_name} has 100% success rate",
                                "occurrences": stats["count"],
                            })

                    logger.info(f"Analyzed {len(runs)} workflow runs")

            except Exception as e:
                logger.warning(f"Could not fetch workflow runs: {e}")
                learning_data["error"] = str(e)

            # Try to get learning API metrics
            try:
                response = await client.get(
                    "https://or-infra.com/api/learning/metrics",
                    headers={"Accept": "application/json"},
                )
                if response.status_code == 200:
                    metrics = response.json()
                    learning_data["agent_performance"] = metrics.get("agents", {})
                    logger.info("Got learning API metrics")
            except Exception as e:
                logger.debug(f"Learning API not available: {e}")

        return learning_data

    def _build_prompt(self, learning_data: dict) -> str:
        """Build the analysis prompt for the LLM."""
        return f"""You are a strategic AI systems analyst specializing in autonomous agent optimization.

Analyze the following learning data to identify strategic insights, patterns, and improvement opportunities.

## Learning Data (Last 30 Days)
{json.dumps(learning_data, indent=2)}

## Your Task
1. Identify non-obvious patterns in the data
2. Find correlations between different metrics
3. Detect emerging trends (positive or negative)
4. Generate strategic recommendations for system improvement
5. Ensure insights are NOVEL (not repeating previous insights listed)

## Output Format
Respond with a JSON object:
{{
  "insights": [
    {{
      "category": "pattern|trend|opportunity|risk",
      "title": "Concise insight title (max 60 chars)",
      "description": "Detailed explanation with specific data references",
      "evidence": ["Data point 1", "Data point 2"],
      "confidence": 0.0-1.0,
      "actionable": true|false,
      "suggested_action": "Specific action to take (if actionable)",
      "novelty_score": 0.0-1.0
    }}
  ],
  "system_health_assessment": "Overall assessment of system learning trajectory",
  "top_priority": "Single most important thing to focus on",
  "confidence_in_analysis": 0.0-1.0
}}

Focus on quality over quantity. 3-5 high-quality insights are better than 10 shallow ones.
Each insight must reference specific numbers from the data.
Respond ONLY with the JSON object, no markdown."""

    async def run(self) -> dict:
        """Execute the learning insights generation.

        Returns:
            Dictionary with insights and execution metrics
        """
        from openai import AsyncOpenAI

        from src.smart_llm.classifier import MODEL_COSTS, MODEL_MAPPING

        run_id = generate_run_id()
        start_time = time.time()

        # Initialize metrics
        metrics = AgentMetrics(
            agent_name=self.AGENT_NAME,
            run_id=run_id,
            model_requested=MODEL_MAPPING.get(self.MODEL_TASK_TYPE, "claude-sonnet"),
            output_type="strategic_insights",
        )

        try:
            # Get learning data
            learning_data = await self._get_learning_data()

            # Build prompt
            prompt = self._build_prompt(learning_data)

            # Call LLM via LiteLLM Gateway
            logger.info(f"Creating OpenAI client with base_url={self.litellm_url}")
            client = AsyncOpenAI(
                base_url=self.litellm_url,
                api_key="dummy",  # Self-hosted gateway doesn't need key
            )

            model = MODEL_MAPPING.get(self.MODEL_TASK_TYPE, "claude-sonnet")
            logger.info(f"Calling LLM with model={model}")

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,  # Higher temperature for creative insights
                    max_tokens=2500,
                )
                logger.info(f"LLM call successful, model_used={response.model}")
            except Exception as llm_error:
                logger.error(f"LLM call failed: {type(llm_error).__name__}: {llm_error}")
                raise

            # Extract response
            content = response.choices[0].message.content
            usage = response.usage

            # Update metrics
            metrics.model_used = response.model
            metrics.input_tokens = usage.prompt_tokens
            metrics.output_tokens = usage.completion_tokens
            metrics.total_tokens = usage.total_tokens
            metrics.estimated_cost_usd = (
                usage.completion_tokens / 1_000_000 * MODEL_COSTS.get(model, 15.0)
            )

            # Parse insights
            try:
                # Remove markdown code blocks if present
                content_clean = content.strip()
                if content_clean.startswith("```"):
                    content_clean = content_clean.split("\n", 1)[1]
                if content_clean.endswith("```"):
                    content_clean = content_clean.rsplit("\n", 1)[0]
                content_clean = content_clean.strip()

                analysis = json.loads(content_clean)
                insights = analysis.get("insights", [])

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse insights JSON: {e}")
                analysis = {"insights": [], "parse_error": True}
                insights = []
                metrics.custom_metrics["parse_error"] = str(e)

            # Calculate quality metrics
            actionable_count = len([i for i in insights if i.get("actionable")])
            avg_confidence = (
                sum(i.get("confidence", 0) for i in insights) / len(insights)
                if insights
                else 0
            )
            avg_novelty = (
                sum(i.get("novelty_score", 0.5) for i in insights) / len(insights)
                if insights
                else 0
            )

            metrics.success = True
            metrics.output_count = len(insights)
            metrics.custom_metrics = {
                "insights_count": len(insights),
                "actionable_count": actionable_count,
                "avg_confidence": round(avg_confidence, 2),
                "avg_novelty": round(avg_novelty, 2),
                "top_priority": analysis.get("top_priority", "unknown"),
                "analysis_confidence": analysis.get("confidence_in_analysis", 0),
            }

            result = {
                "success": True,
                "run_id": run_id,
                "insights": insights,
                "system_assessment": analysis.get("system_health_assessment"),
                "top_priority": analysis.get("top_priority"),
                "insights_count": len(insights),
                "actionable_count": actionable_count,
                "model_used": metrics.model_used,
                "tokens_used": metrics.total_tokens,
                "cost_usd": metrics.estimated_cost_usd,
            }

        except Exception as e:
            logger.error(f"LearnInsightAgent failed: {e}")
            metrics.success = False
            metrics.error_message = str(e)
            result = {
                "success": False,
                "run_id": run_id,
                "error": str(e),
            }

        finally:
            # Record duration
            metrics.duration_ms = int((time.time() - start_time) * 1000)

            # Store metrics
            self.metrics_collector.store(metrics)

        return result


async def main() -> None:
    """Run LearnInsightAgent for testing.

    Executes the agent and prints results to stdout.
    """
    logging.basicConfig(level=logging.INFO)

    agent = LearnInsightAgent()
    result = await agent.run()

    print("\n=== LearnInsightAgent Results ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
