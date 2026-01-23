"""Cost Optimization Agent - Analyzes Railway costs and generates savings recommendations.

Uses SmartLLMClient with TaskType.ANALYSIS (routes to claude-haiku, Tier 2).
Runs every 6 hours (4 runs per 24 hours).

Input: Railway cost data from src/cost_monitor.py
Output: JSON recommendations for cost savings

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
class CostRecommendation:
    """A single cost optimization recommendation."""

    category: str  # e.g., "resource_scaling", "model_selection", "unused_resources"
    title: str
    description: str
    estimated_savings_usd: float
    confidence: float  # 0.0 - 1.0
    action_required: str
    priority: str  # "high", "medium", "low"


class CostOptAgent:
    """Autonomous agent that analyzes costs and generates savings recommendations.

    Uses SmartLLMClient with ANALYSIS task type (routes to claude-haiku).

    Example:
        agent = CostOptAgent(litellm_url="https://litellm-gateway.railway.app")
        result = await agent.run()
        print(f"Generated {len(result['recommendations'])} recommendations")
    """

    AGENT_NAME = "cost_opt_agent"
    MODEL_TASK_TYPE = TaskType.ANALYSIS  # → claude-haiku (Tier 2)

    def __init__(
        self,
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
        metrics_collector: MetricsCollector | None = None,
    ):
        """Initialize CostOptAgent.

        Args:
            litellm_url: URL of LiteLLM Gateway
            metrics_collector: Optional metrics collector for tracking
        """
        self.litellm_url = litellm_url
        self.metrics_collector = metrics_collector or MetricsCollector()

    async def _get_cost_data(self) -> dict:
        """Fetch current cost data from the system.

        In production, this would call CostMonitor. For initial deployment,
        we use mock data to verify the agent works.
        """
        # TODO: Integrate with actual CostMonitor
        # For now, return realistic mock data for testing
        return {
            "period": "last_7_days",
            "total_cost_usd": 47.82,
            "breakdown": {
                "railway_compute": 32.50,
                "railway_database": 10.00,
                "llm_api_calls": 5.32,
            },
            "services": [
                {"name": "main-api", "cost": 15.00, "cpu_avg": 0.12, "memory_avg": 0.45},
                {"name": "telegram-bot", "cost": 8.50, "cpu_avg": 0.05, "memory_avg": 0.20},
                {"name": "litellm-gateway", "cost": 9.00, "cpu_avg": 0.08, "memory_avg": 0.30},
                {"name": "mcp-gateway", "cost": 0.00, "cpu_avg": 0.02, "memory_avg": 0.15},
            ],
            "llm_usage": {
                "claude-sonnet": {"calls": 45, "tokens": 125000, "cost": 3.75},
                "gpt-4o": {"calls": 12, "tokens": 35000, "cost": 0.87},
                "gemini-flash": {"calls": 200, "tokens": 180000, "cost": 0.54},
                "deepseek-v3": {"calls": 15, "tokens": 45000, "cost": 0.16},
            },
        }

    def _build_prompt(self, cost_data: dict) -> str:
        """Build the analysis prompt for the LLM."""
        return f"""You are a cost optimization expert for cloud infrastructure and LLM APIs.

Analyze the following cost data and generate specific, actionable recommendations
for reducing costs while maintaining service quality.

## Cost Data (Last 7 Days)
{json.dumps(cost_data, indent=2)}

## Your Task
1. Identify cost optimization opportunities
2. Prioritize by potential savings and implementation effort
3. Provide specific, actionable recommendations

## Output Format
Respond with a JSON array of recommendations. Each recommendation must have:
- category: "resource_scaling" | "model_selection" | "unused_resources" | "architecture"
- title: Short title (max 50 chars)
- description: Detailed explanation
- estimated_savings_usd: Monthly savings estimate (number)
- confidence: Your confidence in this estimate (0.0-1.0)
- action_required: Specific action to take
- priority: "high" | "medium" | "low"

Example:
[
  {{
    "category": "model_selection",
    "title": "Switch simple queries to Gemini Flash",
    "description": "45 Claude Sonnet calls could use Gemini Flash instead, saving 95% on those calls.",
    "estimated_savings_usd": 12.50,
    "confidence": 0.8,
    "action_required": "Update TaskClassifier to route simple queries to gemini-flash",
    "priority": "high"
  }}
]

Respond ONLY with the JSON array, no markdown or explanation."""

    async def run(self) -> dict:
        """Execute the cost optimization analysis.

        Returns:
            Dictionary with recommendations and execution metrics
        """
        from openai import AsyncOpenAI

        from src.smart_llm.classifier import MODEL_COSTS, MODEL_MAPPING

        run_id = generate_run_id()
        start_time = time.time()

        # Initialize metrics
        metrics = AgentMetrics(
            agent_name=self.AGENT_NAME,
            run_id=run_id,
            model_requested=MODEL_MAPPING.get(self.MODEL_TASK_TYPE, "claude-haiku"),
            output_type="recommendations",
        )

        try:
            # Get cost data
            cost_data = await self._get_cost_data()

            # Build prompt
            prompt = self._build_prompt(cost_data)

            # Call LLM via LiteLLM Gateway
            logger.info(f"Creating OpenAI client with base_url={self.litellm_url}")
            client = AsyncOpenAI(
                base_url=self.litellm_url,
                api_key="dummy",  # Self-hosted gateway doesn't need key
            )

            model = MODEL_MAPPING.get(self.MODEL_TASK_TYPE, "claude-haiku")
            logger.info(f"Calling LLM with model={model}")

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000,
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
                usage.completion_tokens / 1_000_000 * MODEL_COSTS.get(model, 5.0)
            )

            # Parse recommendations
            try:
                # Remove markdown code blocks if present
                content_clean = content.strip()
                if content_clean.startswith("```"):
                    content_clean = content_clean.split("\n", 1)[1]
                if content_clean.endswith("```"):
                    content_clean = content_clean.rsplit("\n", 1)[0]
                content_clean = content_clean.strip()

                recommendations = json.loads(content_clean)

                # Validate structure
                validated = []
                for rec in recommendations:
                    if all(
                        k in rec
                        for k in [
                            "category",
                            "title",
                            "description",
                            "estimated_savings_usd",
                            "priority",
                        ]
                    ):
                        validated.append(rec)

                recommendations = validated

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse recommendations JSON: {e}")
                recommendations = []
                metrics.custom_metrics["parse_error"] = str(e)

            # Calculate quality metrics
            total_savings = sum(r.get("estimated_savings_usd", 0) for r in recommendations)
            high_priority = len([r for r in recommendations if r.get("priority") == "high"])

            metrics.success = True
            metrics.output_count = len(recommendations)
            metrics.custom_metrics = {
                "total_savings_identified_usd": total_savings,
                "high_priority_count": high_priority,
                "cost_data_period": cost_data.get("period", "unknown"),
            }

            result = {
                "success": True,
                "run_id": run_id,
                "recommendations": recommendations,
                "total_savings_identified_usd": total_savings,
                "model_used": metrics.model_used,
                "tokens_used": metrics.total_tokens,
                "cost_usd": metrics.estimated_cost_usd,
            }

        except Exception as e:
            logger.error(f"CostOptAgent failed: {e}")
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
    """Run CostOptAgent for testing.

    Executes the agent and prints results to stdout.
    """
    logging.basicConfig(level=logging.INFO)

    agent = CostOptAgent()
    result = await agent.run()

    print("\n=== CostOptAgent Results ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
