"""Metrics collection for background agents.

Tracks agent execution metrics for verification that smart model routing
and autonomous operations are working correctly.

ADR-013 Phase 3: Background Autonomous Jobs
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentMetrics:
    """Metrics for a single agent run."""

    agent_name: str
    run_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Execution metrics
    success: bool = False
    error_message: str | None = None
    duration_ms: int = 0

    # LLM metrics
    model_requested: str | None = None
    model_used: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Output metrics
    output_type: str | None = None  # e.g., "recommendations", "summary", "insights"
    output_count: int = 0  # Number of items generated
    output_quality_score: float | None = None  # Optional 0-5 quality score

    # Custom metrics (agent-specific)
    custom_metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


class MetricsCollector:
    """Collects and stores metrics from background agents.

    Stores metrics in JSON files for easy analysis and verification.
    File path: data/agent_metrics/YYYY-MM-DD/{agent_name}_{run_id}.json
    """

    def __init__(self, base_path: Path | None = None):
        """Initialize metrics collector.

        Args:
            base_path: Base directory for metrics files.
                       Defaults to ./data/agent_metrics/
        """
        self.base_path = base_path or Path("data/agent_metrics")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_metrics_path(self, metrics: AgentMetrics) -> Path:
        """Get the file path for storing metrics."""
        date_str = datetime.fromisoformat(metrics.timestamp).strftime("%Y-%m-%d")
        date_dir = self.base_path / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir / f"{metrics.agent_name}_{metrics.run_id}.json"

    def store(self, metrics: AgentMetrics) -> Path:
        """Store metrics to a JSON file.

        Args:
            metrics: AgentMetrics to store

        Returns:
            Path to the stored metrics file
        """
        path = self._get_metrics_path(metrics)
        path.write_text(metrics.to_json())
        logger.info(f"Stored metrics for {metrics.agent_name} at {path}")
        return path

    def load_day(self, date: datetime | None = None) -> list[AgentMetrics]:
        """Load all metrics for a specific day.

        Args:
            date: Date to load metrics for. Defaults to today.

        Returns:
            List of AgentMetrics for that day
        """
        if date is None:
            date = datetime.now(UTC)

        date_str = date.strftime("%Y-%m-%d")
        date_dir = self.base_path / date_str

        if not date_dir.exists():
            return []

        metrics = []
        for file_path in date_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text())
                metrics.append(AgentMetrics(**data))
            except Exception as e:
                logger.warning(f"Failed to load metrics from {file_path}: {e}")

        return metrics

    def get_summary(self, date: datetime | None = None) -> dict:
        """Get summary statistics for a day's metrics.

        Args:
            date: Date to summarize. Defaults to today.

        Returns:
            Dictionary with summary statistics
        """
        metrics = self.load_day(date)

        if not metrics:
            return {"total_runs": 0, "message": "No metrics found"}

        by_agent = {}
        total_cost = 0.0
        total_tokens = 0
        successful_runs = 0

        for m in metrics:
            if m.agent_name not in by_agent:
                by_agent[m.agent_name] = {
                    "runs": 0,
                    "successful": 0,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "models_used": [],
                }

            by_agent[m.agent_name]["runs"] += 1
            by_agent[m.agent_name]["total_cost"] += m.estimated_cost_usd
            by_agent[m.agent_name]["total_tokens"] += m.total_tokens

            if m.model_used and m.model_used not in by_agent[m.agent_name]["models_used"]:
                by_agent[m.agent_name]["models_used"].append(m.model_used)

            if m.success:
                by_agent[m.agent_name]["successful"] += 1
                successful_runs += 1

            total_cost += m.estimated_cost_usd
            total_tokens += m.total_tokens

        return {
            "date": (date or datetime.now(UTC)).strftime("%Y-%m-%d"),
            "total_runs": len(metrics),
            "successful_runs": successful_runs,
            "success_rate": successful_runs / len(metrics) if metrics else 0,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "by_agent": by_agent,
        }


def generate_run_id() -> str:
    """Generate a unique run ID."""
    import uuid

    return uuid.uuid4().hex[:8]
