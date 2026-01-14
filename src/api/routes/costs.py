"""Cost Monitoring API Endpoints.

Provides endpoints for Railway cost tracking and budget management.
Implements Week 2 of Post-Launch Maintenance: Cost Monitoring.

Endpoints:
- GET /costs/estimate - Get current month cost estimate
- GET /costs/report - Generate full cost report
- GET /costs/budget - Check budget status
- GET /costs/recommendations - Get cost optimization recommendations
"""

import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/costs", tags=["Costs"])


# =============================================================================
# Pydantic Models
# =============================================================================


class CostEstimateResponse(BaseModel):
    """Cost estimate response model."""

    period_start: str = Field(description="Start of measurement period (ISO 8601)")
    period_end: str = Field(description="End of measurement period (ISO 8601)")
    usage: dict[str, float] = Field(
        description="Resource usage (vcpu_minutes, memory_gb_minutes, egress_gb)"
    )
    costs: dict[str, float] = Field(
        description="Cost breakdown (vcpu, memory, egress, base, total)"
    )
    currency: str = Field(default="USD", description="Currency code")


class BudgetStatusResponse(BaseModel):
    """Budget status response model."""

    budget: float = Field(description="Monthly budget in USD")
    projected_cost: float = Field(description="Projected monthly cost")
    exceeded: bool = Field(description="Whether budget is exceeded")
    percentage_used: float = Field(description="Percentage of budget used")
    status: str = Field(description="Status: ok, warning, or alert")


class CostRecommendation(BaseModel):
    """Cost optimization recommendation."""

    priority: str = Field(description="Priority: high, medium, or low")
    category: str = Field(description="Category: cpu, memory, or general")
    title: str = Field(description="Short recommendation title")
    description: str = Field(description="Detailed recommendation")
    potential_savings: str = Field(description="Estimated savings percentage")


class CostReportResponse(BaseModel):
    """Full cost report response model."""

    generated_at: str = Field(description="Report generation timestamp (ISO 8601)")
    pricing_plan: str = Field(description="Railway pricing plan name")
    estimate: CostEstimateResponse = Field(description="Cost estimate details")
    budget_status: BudgetStatusResponse = Field(description="Budget status")
    recommendations: list[CostRecommendation] = Field(
        default=[], description="Cost optimization recommendations"
    )
    trends: dict[str, Any] = Field(
        default={}, description="Usage trends (cpu, memory)"
    )


# =============================================================================
# Helper Functions
# =============================================================================


def get_cost_monitor():
    """Get or create CostMonitor instance.

    Returns:
        CostMonitor instance or None if not available

    Note:
        Returns mock data if Railway client is not configured.
    """
    # In production, this would use real Railway client
    # For now, return mock data when Railway is not configured

    railway_api_token = os.environ.get("RAILWAY_API_TOKEN")
    if not railway_api_token:
        return None

    # Only import when needed to avoid circular imports
    from src.cost_monitor import CostMonitor, RailwayPricing
    from src.railway_client import RailwayClient

    client = RailwayClient(api_token=railway_api_token)
    return CostMonitor(railway_client=client, pricing=RailwayPricing.hobby())


def get_mock_estimate() -> CostEstimateResponse:
    """Generate mock cost estimate for demo/development."""
    now = datetime.now(UTC)
    return CostEstimateResponse(
        period_start=(now.replace(day=1)).isoformat(),
        period_end=now.isoformat(),
        usage={
            "vcpu_minutes": 5000.0,
            "memory_gb_minutes": 2500.0,
            "egress_gb": 1.5,
        },
        costs={
            "vcpu": 1.16,
            "memory": 0.58,
            "egress": 0.15,
            "base": 5.0,
            "total": 6.89,
        },
        currency="USD",
    )


def get_mock_budget_status(budget: float = 50.0) -> BudgetStatusResponse:
    """Generate mock budget status for demo/development."""
    projected = 6.89
    return BudgetStatusResponse(
        budget=budget,
        projected_cost=projected,
        exceeded=projected > budget,
        percentage_used=round((projected / budget) * 100, 1),
        status="ok" if projected < budget * 0.8 else "warning",
    )


def get_mock_recommendations() -> list[CostRecommendation]:
    """Generate mock recommendations for demo/development."""
    return [
        CostRecommendation(
            priority="low",
            category="general",
            title="Resource usage is optimized",
            description=(
                "Current resource allocation appears well-matched to usage. "
                "Continue monitoring for changes."
            ),
            potential_savings="0%",
        )
    ]


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/estimate", response_model=CostEstimateResponse)
async def get_cost_estimate(
    deployment_id: str | None = Query(
        None,
        description="Railway deployment ID (uses default if not provided)",
    ),
) -> CostEstimateResponse:
    """Get current month cost estimate.

    Returns projected cost for the current billing month based on
    resource usage patterns.

    Args:
        deployment_id: Railway deployment ID (optional)

    Returns:
        CostEstimateResponse with usage and cost breakdown

    Example:
        GET /costs/estimate
        GET /costs/estimate?deployment_id=abc123
    """
    monitor = get_cost_monitor()

    if monitor is None:
        # Return mock data when Railway is not configured
        return get_mock_estimate()

    # Use environment variable or provided deployment ID
    dep_id = deployment_id or os.environ.get("RAILWAY_DEPLOYMENT_ID")
    if not dep_id:
        raise HTTPException(
            status_code=400,
            detail="deployment_id required (or set RAILWAY_DEPLOYMENT_ID env var)",
        )

    try:
        estimate = await monitor.get_current_month_cost(dep_id)
        data = estimate.to_dict()

        return CostEstimateResponse(
            period_start=data["period_start"],
            period_end=data["period_end"],
            usage=data["usage"],
            costs=data["costs"],
            currency=data["currency"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/budget", response_model=BudgetStatusResponse)
async def check_budget_status(
    budget: float = Query(50.0, description="Monthly budget in USD", ge=1.0),
    deployment_id: str | None = Query(None, description="Railway deployment ID"),
) -> BudgetStatusResponse:
    """Check if projected cost exceeds budget.

    Compares projected monthly cost against specified budget and
    returns status with percentage used.

    Args:
        budget: Monthly budget in USD (default: $50)
        deployment_id: Railway deployment ID (optional)

    Returns:
        BudgetStatusResponse with budget status

    Example:
        GET /costs/budget?budget=100
    """
    monitor = get_cost_monitor()

    if monitor is None:
        return get_mock_budget_status(budget)

    dep_id = deployment_id or os.environ.get("RAILWAY_DEPLOYMENT_ID")
    if not dep_id:
        raise HTTPException(
            status_code=400,
            detail="deployment_id required (or set RAILWAY_DEPLOYMENT_ID env var)",
        )

    try:
        exceeded, projected = await monitor.is_budget_exceeded(dep_id, budget)
        percentage = round((projected / budget) * 100, 1)

        if percentage < 80:
            status = "ok"
        elif percentage < 100:
            status = "warning"
        else:
            status = "alert"

        return BudgetStatusResponse(
            budget=budget,
            projected_cost=round(projected, 2),
            exceeded=exceeded,
            percentage_used=percentage,
            status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/recommendations", response_model=list[CostRecommendation])
async def get_cost_recommendations(
    deployment_id: str | None = Query(None, description="Railway deployment ID"),
) -> list[CostRecommendation]:
    """Get cost optimization recommendations.

    Analyzes current resource usage and provides actionable
    recommendations to reduce costs.

    Args:
        deployment_id: Railway deployment ID (optional)

    Returns:
        List of CostRecommendation objects

    Example:
        GET /costs/recommendations
    """
    monitor = get_cost_monitor()

    if monitor is None:
        return get_mock_recommendations()

    dep_id = deployment_id or os.environ.get("RAILWAY_DEPLOYMENT_ID")
    if not dep_id:
        raise HTTPException(
            status_code=400,
            detail="deployment_id required (or set RAILWAY_DEPLOYMENT_ID env var)",
        )

    try:
        # Get current usage
        usage = await monitor.get_current_usage(dep_id)
        recommendations = monitor.get_cost_optimization_recommendations(usage)

        return [
            CostRecommendation(
                priority=r["priority"],
                category=r["category"],
                title=r["title"],
                description=r["description"],
                potential_savings=r["potential_savings"],
            )
            for r in recommendations
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/report", response_model=CostReportResponse)
async def generate_cost_report(
    deployment_id: str | None = Query(None, description="Railway deployment ID"),
    budget: float = Query(50.0, description="Monthly budget in USD", ge=1.0),
) -> CostReportResponse:
    """Generate comprehensive cost report.

    Combines cost estimate, budget status, and recommendations
    into a single report.

    Args:
        deployment_id: Railway deployment ID (optional)
        budget: Monthly budget in USD (default: $50)

    Returns:
        CostReportResponse with full cost analysis

    Example:
        GET /costs/report?budget=100
    """
    monitor = get_cost_monitor()
    now = datetime.now(UTC)

    if monitor is None:
        # Return mock data
        estimate = get_mock_estimate()
        budget_status = get_mock_budget_status(budget)
        recommendations = get_mock_recommendations()

        return CostReportResponse(
            generated_at=now.isoformat(),
            pricing_plan="Hobby",
            estimate=estimate,
            budget_status=budget_status,
            recommendations=recommendations,
            trends={
                "cpu": {"min": 20, "max": 40, "avg": 30, "trend": "stable"},
                "memory": {"min": 200, "max": 300, "avg": 250, "trend": "stable"},
            },
        )

    dep_id = deployment_id or os.environ.get("RAILWAY_DEPLOYMENT_ID")
    if not dep_id:
        raise HTTPException(
            status_code=400,
            detail="deployment_id required (or set RAILWAY_DEPLOYMENT_ID env var)",
        )

    try:
        # Get all components
        cost_estimate = await monitor.get_current_month_cost(dep_id)
        exceeded, projected = await monitor.is_budget_exceeded(dep_id, budget)
        usage = await monitor.get_current_usage(dep_id)
        recommendations = monitor.get_cost_optimization_recommendations(usage)

        # Build response
        estimate_data = cost_estimate.to_dict()
        percentage = round((projected / budget) * 100, 1)

        return CostReportResponse(
            generated_at=now.isoformat(),
            pricing_plan=monitor.pricing.plan_name,
            estimate=CostEstimateResponse(
                period_start=estimate_data["period_start"],
                period_end=estimate_data["period_end"],
                usage=estimate_data["usage"],
                costs=estimate_data["costs"],
                currency=estimate_data["currency"],
            ),
            budget_status=BudgetStatusResponse(
                budget=budget,
                projected_cost=round(projected, 2),
                exceeded=exceeded,
                percentage_used=percentage,
                status="ok" if percentage < 80 else "warning" if percentage < 100 else "alert",
            ),
            recommendations=[
                CostRecommendation(
                    priority=r["priority"],
                    category=r["category"],
                    title=r["title"],
                    description=r["description"],
                    potential_savings=r["potential_savings"],
                )
                for r in recommendations
            ],
            trends={
                "cpu": monitor.get_usage_trend("cpu"),
                "memory": monitor.get_usage_trend("memory"),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
async def costs_health_check():
    """Health check for cost monitoring API.

    Returns:
        Status message with Railway configuration status
    """
    railway_configured = bool(os.environ.get("RAILWAY_API_TOKEN"))

    return {
        "status": "healthy",
        "service": "cost-monitoring-api",
        "railway_configured": railway_configured,
        "timestamp": datetime.now(UTC).isoformat(),
    }
