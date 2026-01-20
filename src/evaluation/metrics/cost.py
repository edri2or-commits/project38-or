"""
Cost Metrics for Model Evaluation.

Provides metrics for measuring API costs:
- Per-token costs (input/output)
- Per-request costs
- Estimated daily/monthly costs
- Cost comparisons between providers

Architecture Decision: ADR-009

Pricing Reference (2026):
- Claude Sonnet 4: $3/MTok input, $15/MTok output
- Claude Opus 4.5: $15/MTok input, $75/MTok output
- Claude Haiku 3.5: $0.25/MTok input, $1.25/MTok output
- GPT-4o: $2.50/MTok input, $10/MTok output
- Gemini 1.5 Pro: $1.25/MTok input, $5/MTok output
"""

from dataclasses import dataclass, field
from typing import Any

# Default pricing (USD per 1K tokens)
DEFAULT_PRICING = {
    "claude-sonnet": {"input": 0.003, "output": 0.015},
    "claude-opus": {"input": 0.015, "output": 0.075},
    "claude-haiku": {"input": 0.00025, "output": 0.00125},
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gemini-pro": {"input": 0.00125, "output": 0.005},
    "default": {"input": 0.003, "output": 0.015},
}


@dataclass
class CostMetrics:
    """Cost metrics for model usage.

    Attributes:
        total_input_tokens: Total input tokens consumed.
        total_output_tokens: Total output tokens generated.
        total_cost_usd: Total cost in USD.
        cost_per_request_usd: Average cost per request.
        cost_per_1k_input: Cost per 1K input tokens.
        cost_per_1k_output: Cost per 1K output tokens.
        request_count: Number of requests.
        estimated_daily_usd: Estimated daily cost at current rate.
        estimated_monthly_usd: Estimated monthly cost at current rate.
    """

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    cost_per_request_usd: float = 0.0
    cost_per_1k_input: float = 0.003
    cost_per_1k_output: float = 0.015
    request_count: int = 0
    estimated_daily_usd: float = 0.0
    estimated_monthly_usd: float = 0.0
    _pricing_model: str = field(default="default", repr=False)

    @classmethod
    def calculate(
        cls,
        input_tokens: int,
        output_tokens: int,
        request_count: int,
        pricing_model: str = "default",
        requests_per_day: int | None = None,
    ) -> "CostMetrics":
        """Calculate cost metrics from token usage.

        Args:
            input_tokens: Total input tokens.
            output_tokens: Total output tokens.
            request_count: Number of API requests.
            pricing_model: Pricing model name (e.g., 'claude-sonnet').
            requests_per_day: Estimated requests per day for projections.

        Returns:
            CostMetrics instance with calculated values.
        """
        pricing = DEFAULT_PRICING.get(pricing_model, DEFAULT_PRICING["default"])
        cost_per_1k_input = pricing["input"]
        cost_per_1k_output = pricing["output"]

        # Calculate total cost
        input_cost = (input_tokens / 1000) * cost_per_1k_input
        output_cost = (output_tokens / 1000) * cost_per_1k_output
        total_cost = input_cost + output_cost

        # Cost per request
        cost_per_request = total_cost / request_count if request_count > 0 else 0

        # Projections
        if requests_per_day:
            daily_cost = cost_per_request * requests_per_day
        else:
            # Assume current rate continues for 8 hours
            daily_cost = total_cost * 8 if request_count > 0 else 0

        monthly_cost = daily_cost * 30

        return cls(
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_cost_usd=total_cost,
            cost_per_request_usd=cost_per_request,
            cost_per_1k_input=cost_per_1k_input,
            cost_per_1k_output=cost_per_1k_output,
            request_count=request_count,
            estimated_daily_usd=daily_cost,
            estimated_monthly_usd=monthly_cost,
            _pricing_model=pricing_model,
        )

    @classmethod
    def from_capabilities(
        cls,
        input_tokens: int,
        output_tokens: int,
        request_count: int,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
    ) -> "CostMetrics":
        """Calculate costs using provider capabilities pricing.

        Args:
            input_tokens: Total input tokens.
            output_tokens: Total output tokens.
            request_count: Number of requests.
            cost_per_1k_input: Cost per 1K input tokens from capabilities.
            cost_per_1k_output: Cost per 1K output tokens from capabilities.

        Returns:
            CostMetrics instance.
        """
        input_cost = (input_tokens / 1000) * cost_per_1k_input
        output_cost = (output_tokens / 1000) * cost_per_1k_output
        total_cost = input_cost + output_cost

        cost_per_request = total_cost / request_count if request_count > 0 else 0
        daily_cost = total_cost * 8 if request_count > 0 else 0

        return cls(
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_cost_usd=total_cost,
            cost_per_request_usd=cost_per_request,
            cost_per_1k_input=cost_per_1k_input,
            cost_per_1k_output=cost_per_1k_output,
            request_count=request_count,
            estimated_daily_usd=daily_cost,
            estimated_monthly_usd=daily_cost * 30,
            _pricing_model="custom",
        )

    @property
    def total_tokens(self) -> int:
        """Get total tokens (input + output)."""
        return self.total_input_tokens + self.total_output_tokens

    def is_within_budget(
        self,
        daily_budget_usd: float = 10.0,
        monthly_budget_usd: float = 300.0,
    ) -> bool:
        """Check if costs are within budget.

        Args:
            daily_budget_usd: Daily budget limit.
            monthly_budget_usd: Monthly budget limit.

        Returns:
            True if within both budgets.
        """
        return (
            self.estimated_daily_usd <= daily_budget_usd
            and self.estimated_monthly_usd <= monthly_budget_usd
        )

    def compare(self, other: "CostMetrics") -> dict[str, float]:
        """Compare costs to another provider.

        Args:
            other: CostMetrics to compare against.

        Returns:
            Dictionary with percentage changes (positive = more expensive).
        """
        def pct_change(new: float, old: float) -> float:
            if old == 0:
                return 0.0 if new == 0 else 100.0
            return ((new - old) / old) * 100

        return {
            "total_cost_change_pct": pct_change(self.total_cost_usd, other.total_cost_usd),
            "per_request_change_pct": pct_change(
                self.cost_per_request_usd, other.cost_per_request_usd
            ),
            "daily_change_pct": pct_change(
                self.estimated_daily_usd, other.estimated_daily_usd
            ),
            "monthly_change_pct": pct_change(
                self.estimated_monthly_usd, other.estimated_monthly_usd
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cost_per_request_usd": round(self.cost_per_request_usd, 6),
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "request_count": self.request_count,
            "estimated_daily_usd": round(self.estimated_daily_usd, 2),
            "estimated_monthly_usd": round(self.estimated_monthly_usd, 2),
            "pricing_model": self._pricing_model,
        }

    def summary(self) -> str:
        """Get human-readable summary.

        Returns:
            Summary string.
        """
        return (
            f"Cost: ${self.total_cost_usd:.4f} total "
            f"(${self.cost_per_request_usd:.4f}/req), "
            f"~${self.estimated_daily_usd:.2f}/day, "
            f"~${self.estimated_monthly_usd:.2f}/month"
        )


def get_pricing(model_name: str) -> dict[str, float]:
    """Get pricing for a model.

    Args:
        model_name: Model name (e.g., 'claude-sonnet').

    Returns:
        Dictionary with 'input' and 'output' pricing per 1K tokens.
    """
    # Normalize model name
    normalized = model_name.lower().replace("_", "-").replace(" ", "-")

    # Match known models
    for key in DEFAULT_PRICING:
        if key in normalized:
            return DEFAULT_PRICING[key]

    return DEFAULT_PRICING["default"]
