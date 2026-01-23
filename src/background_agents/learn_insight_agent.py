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
        """Fetch learning data from the system.

        In production, this would call LearningService.
        For initial deployment, we use mock data to verify the agent works.
        """
        # TODO: Integrate with actual LearningService
        return {
            "period": "last_30_days",
            "total_actions": 1247,
            "actions_by_type": {
                "deploy": {"count": 45, "success_rate": 0.93, "avg_duration_ms": 45000},
                "rollback": {"count": 3, "success_rate": 1.0, "avg_duration_ms": 12000},
                "scale": {"count": 12, "success_rate": 1.0, "avg_duration_ms": 8000},
                "alert": {"count": 89, "success_rate": 0.98, "avg_duration_ms": 500},
                "health_check": {"count": 720, "success_rate": 0.995, "avg_duration_ms": 2000},
                "cost_analysis": {"count": 28, "success_rate": 1.0, "avg_duration_ms": 3500},
                "backup": {"count": 30, "success_rate": 0.97, "avg_duration_ms": 120000},
                "api_call": {"count": 320, "success_rate": 0.89, "avg_duration_ms": 1500},
            },
            "failure_patterns": [
                {
                    "pattern": "deploy_after_midnight",
                    "failures": 2,
                    "total": 8,
                    "correlation": "Higher failure rate for deploys between 00:00-04:00 UTC",
                },
                {
                    "pattern": "api_call_rate_limit",
                    "failures": 35,
                    "total": 320,
                    "correlation": "GitHub API rate limiting during CI peaks",
                },
                {
                    "pattern": "backup_timeout",
                    "failures": 1,
                    "total": 30,
                    "correlation": "Single backup failure during high DB load",
                },
            ],
            "success_patterns": [
                {
                    "pattern": "gradual_rollout",
                    "description": "Deployments with canary phase have 0% rollback rate",
                    "occurrences": 15,
                },
                {
                    "pattern": "pre_deploy_health_check",
                    "description": "Deploys preceded by health check have 98% success rate",
                    "occurrences": 40,
                },
            ],
            "resource_usage_trends": {
                "cpu_trend": "stable",
                "memory_trend": "slowly_increasing",
                "storage_trend": "stable",
                "cost_trend": "decreasing",
            },
            "agent_performance": {
                "DeployAgent": {"avg_confidence": 0.87, "decisions_automated": 38},
                "MonitoringAgent": {"avg_confidence": 0.92, "decisions_automated": 650},
                "IntegrationAgent": {"avg_confidence": 0.78, "decisions_automated": 89},
            },
            "previous_insights": [
                {
                    "date": "2026-01-16",
                    "insight": "API rate limiting causing 10%+ failures",
                    "status": "addressed",
                },
                {
                    "date": "2026-01-20",
                    "insight": "Memory usage increasing 2% weekly",
                    "status": "monitoring",
                },
            ],
        }

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

        from src.smart_llm.classifier import MODEL_MAPPING
        from src.smart_llm.client import MODEL_COSTS

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
            client = AsyncOpenAI(
                base_url=self.litellm_url,
                api_key="dummy",  # Self-hosted gateway doesn't need key
            )

            model = MODEL_MAPPING.get(self.MODEL_TASK_TYPE, "claude-sonnet")

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,  # Higher temperature for creative insights
                max_tokens=2500,
            )

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


async def main():
    """CLI entry point for testing."""
    import asyncio

    logging.basicConfig(level=logging.INFO)

    agent = LearnInsightAgent()
    result = await agent.run()

    print("\n=== LearnInsightAgent Results ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
