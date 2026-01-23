"""Health Synthesis Agent - Synthesizes system health metrics into readable summaries.

Uses SmartLLMClient with TaskType.SUMMARIZE (routes to gemini-flash, Tier 1).
Runs every 4 hours (6 runs per 24 hours).

Input: System metrics from monitoring_loop.py and performance_baseline.py
Output: Human-readable health summary with anomaly explanations

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
class HealthSummary:
    """Health summary output."""

    overall_status: str  # "healthy", "degraded", "critical"
    key_findings: list[str]  # 3-5 key points
    anomalies_detected: list[dict]
    recommendations: list[str]
    next_check_priority: str  # What to focus on next


class HealthSynthAgent:
    """Autonomous agent that synthesizes health metrics into readable summaries.

    Uses SmartLLMClient with SUMMARIZE task type (routes to gemini-flash).
    This is the cheapest tier ($0.30/1M) for straightforward synthesis tasks.

    Example:
        agent = HealthSynthAgent(litellm_url="https://litellm-gateway.railway.app")
        result = await agent.run()
        print(result['summary'])
    """

    AGENT_NAME = "health_synth_agent"
    MODEL_TASK_TYPE = TaskType.SUMMARIZE  # → gemini-flash (Tier 1)

    def __init__(
        self,
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
        metrics_collector: MetricsCollector | None = None,
    ):
        """Initialize HealthSynthAgent.

        Args:
            litellm_url: URL of LiteLLM Gateway
            metrics_collector: Optional metrics collector for tracking
        """
        self.litellm_url = litellm_url
        self.metrics_collector = metrics_collector or MetricsCollector()

    async def _get_health_data(self) -> dict:
        """Fetch current health metrics from the system.

        In production, this would call MonitoringLoop endpoints.
        For initial deployment, we use mock data to verify the agent works.
        """
        # TODO: Integrate with actual MonitoringLoop and PerformanceBaseline
        return {
            "timestamp": "2026-01-23T18:00:00Z",
            "services": {
                "main-api": {
                    "status": "healthy",
                    "uptime_percent": 99.95,
                    "avg_response_ms": 145,
                    "error_rate_percent": 0.02,
                    "requests_per_minute": 42,
                },
                "telegram-bot": {
                    "status": "healthy",
                    "uptime_percent": 100.0,
                    "avg_response_ms": 89,
                    "error_rate_percent": 0.0,
                    "messages_processed": 156,
                },
                "litellm-gateway": {
                    "status": "healthy",
                    "uptime_percent": 99.98,
                    "avg_response_ms": 1250,
                    "error_rate_percent": 0.5,
                    "llm_calls": 312,
                },
                "mcp-gateway": {
                    "status": "degraded",
                    "uptime_percent": 98.5,
                    "avg_response_ms": 320,
                    "error_rate_percent": 1.2,
                    "tool_calls": 89,
                },
            },
            "infrastructure": {
                "railway_database": {
                    "status": "healthy",
                    "connections_active": 12,
                    "connections_max": 100,
                    "storage_used_percent": 23.5,
                },
                "gcp_secrets": {
                    "status": "healthy",
                    "last_access": "2026-01-23T17:55:00Z",
                    "access_errors": 0,
                },
            },
            "anomalies_detected": [
                {
                    "service": "mcp-gateway",
                    "type": "elevated_error_rate",
                    "severity": "medium",
                    "value": 1.2,
                    "threshold": 1.0,
                    "first_detected": "2026-01-23T16:30:00Z",
                },
                {
                    "service": "litellm-gateway",
                    "type": "high_latency_spike",
                    "severity": "low",
                    "value": 2500,
                    "threshold": 2000,
                    "first_detected": "2026-01-23T17:45:00Z",
                    "resolved": True,
                },
            ],
            "performance_baseline": {
                "main-api": {"baseline_response_ms": 120, "current_vs_baseline": "+20.8%"},
                "telegram-bot": {"baseline_response_ms": 95, "current_vs_baseline": "-6.3%"},
                "litellm-gateway": {"baseline_response_ms": 1100, "current_vs_baseline": "+13.6%"},
            },
        }

    def _build_prompt(self, health_data: dict) -> str:
        """Build the synthesis prompt for the LLM."""
        return f"""You are a system health analyst. Synthesize the following metrics into a clear, actionable summary.

## System Health Data
{json.dumps(health_data, indent=2)}

## Your Task
Create a concise health summary that:
1. Gives an overall status assessment
2. Highlights 3-5 key findings (most important first)
3. Explains any anomalies in plain language
4. Provides 1-3 actionable recommendations
5. Suggests what to prioritize in the next check

## Output Format
Respond with a JSON object:
{{
  "overall_status": "healthy|degraded|critical",
  "key_findings": ["Finding 1 (most critical)", "Finding 2", "Finding 3"],
  "anomaly_explanations": [
    {{"service": "...", "explanation": "Plain language explanation", "impact": "low|medium|high"}}
  ],
  "recommendations": ["Actionable recommendation 1", "Recommendation 2"],
  "next_check_priority": "What to focus on in next health check",
  "confidence": 0.0-1.0
}}

Be specific with numbers. Reference actual values from the data.
Respond ONLY with the JSON object, no markdown."""

    async def run(self) -> dict:
        """Execute the health synthesis.

        Returns:
            Dictionary with health summary and execution metrics
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
            model_requested=MODEL_MAPPING.get(self.MODEL_TASK_TYPE, "gemini-flash"),
            output_type="health_summary",
        )

        try:
            # Get health data
            health_data = await self._get_health_data()

            # Build prompt
            prompt = self._build_prompt(health_data)

            # Call LLM via LiteLLM Gateway
            client = AsyncOpenAI(
                base_url=self.litellm_url,
                api_key="dummy",  # Self-hosted gateway doesn't need key
            )

            model = MODEL_MAPPING.get(self.MODEL_TASK_TYPE, "gemini-flash")

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1500,
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
                usage.completion_tokens / 1_000_000 * MODEL_COSTS.get(model, 0.30)
            )

            # Parse summary
            try:
                # Remove markdown code blocks if present
                content_clean = content.strip()
                if content_clean.startswith("```"):
                    content_clean = content_clean.split("\n", 1)[1]
                if content_clean.endswith("```"):
                    content_clean = content_clean.rsplit("\n", 1)[0]
                content_clean = content_clean.strip()

                summary = json.loads(content_clean)

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse summary JSON: {e}")
                summary = {
                    "overall_status": "unknown",
                    "key_findings": ["Parse error - raw response stored"],
                    "raw_response": content,
                }
                metrics.custom_metrics["parse_error"] = str(e)

            # Calculate quality metrics
            findings_count = len(summary.get("key_findings", []))
            anomalies_explained = len(summary.get("anomaly_explanations", []))

            metrics.success = True
            metrics.output_count = findings_count
            metrics.custom_metrics = {
                "overall_status": summary.get("overall_status", "unknown"),
                "findings_count": findings_count,
                "anomalies_explained": anomalies_explained,
                "anomalies_in_data": len(health_data.get("anomalies_detected", [])),
            }

            result = {
                "success": True,
                "run_id": run_id,
                "summary": summary,
                "model_used": metrics.model_used,
                "tokens_used": metrics.total_tokens,
                "cost_usd": metrics.estimated_cost_usd,
            }

        except Exception as e:
            logger.error(f"HealthSynthAgent failed: {e}")
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
    """Run HealthSynthAgent for testing.

    Executes the agent and prints results to stdout.
    """
    logging.basicConfig(level=logging.INFO)

    agent = HealthSynthAgent()
    result = await agent.run()

    print("\n=== HealthSynthAgent Results ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
