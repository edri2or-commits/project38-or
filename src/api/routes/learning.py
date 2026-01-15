"""API routes for Learning Service.

Provides endpoints for accessing learning insights, statistics,
and confidence adjustments from the autonomous system.
"""

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.learning_service import LearningService, create_learning_service

router = APIRouter(prefix="/learning", tags=["learning"])

# Global learning service instance
_learning_service: LearningService | None = None


def get_learning_service() -> LearningService:
    """Get or create the learning service instance.

    Returns:
        LearningService instance
    """
    global _learning_service
    if _learning_service is None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///:memory:")
        _learning_service = create_learning_service(database_url=database_url)
    return _learning_service


async def ensure_initialized() -> LearningService:
    """Ensure the learning service is initialized.

    Returns:
        Initialized LearningService
    """
    service = get_learning_service()
    if not service.initialized:
        await service.initialize()
    return service


# ============================================================================
# RESPONSE MODELS
# ============================================================================
class ActionStatsResponse(BaseModel):
    """Response model for action statistics."""

    action_type: str
    agent_type: str
    total_count: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_confidence: float
    avg_execution_time_ms: float
    last_executed: datetime | None
    confidence_trend: str


class ConfidenceAdjustmentResponse(BaseModel):
    """Response model for confidence adjustment."""

    action_type: str
    current_base: float
    recommended_base: float
    reason: str
    sample_size: int
    time_period_days: int


class LearningInsightResponse(BaseModel):
    """Response model for learning insight."""

    insight_type: str
    description: str
    recommendation: str
    impact_level: str
    action_types: list[str]
    data_points: int
    generated_at: datetime


class RecordActionRequest(BaseModel):
    """Request model for recording an action."""

    action_type: str
    success: bool
    agent_type: str = "AutonomousController"
    domain: str = "system"
    decision_reason: str = ""
    confidence_score: float = 0.0
    autonomous: bool = True
    result_summary: str = ""
    error_message: str | None = None
    execution_time_ms: int = 0
    affected_services: str = ""


class RecordActionResponse(BaseModel):
    """Response model for recorded action."""

    id: int
    action_type: str
    success: bool
    timestamp: datetime
    message: str


# ============================================================================
# ENDPOINTS
# ============================================================================
@router.get("/health")
async def learning_health() -> dict[str, str]:
    """Check learning service health.

    Returns:
        Health status
    """
    try:
        service = await ensure_initialized()
        return {
            "status": "healthy",
            "initialized": str(service.initialized),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@router.post("/actions", response_model=RecordActionResponse)
async def record_action(request: RecordActionRequest) -> RecordActionResponse:
    """Record an action outcome for learning.

    Args:
        request: Action details to record

    Returns:
        Recorded action confirmation
    """
    service = await ensure_initialized()

    record = await service.record_action(
        action_type=request.action_type,
        success=request.success,
        agent_type=request.agent_type,
        domain=request.domain,
        decision_reason=request.decision_reason,
        confidence_score=request.confidence_score,
        autonomous=request.autonomous,
        result_summary=request.result_summary,
        error_message=request.error_message,
        execution_time_ms=request.execution_time_ms,
        affected_services=request.affected_services,
    )

    return RecordActionResponse(
        id=record.id,
        action_type=record.action_type,
        success=record.success,
        timestamp=record.timestamp,
        message=f"Action {request.action_type} recorded successfully",
    )


@router.get("/actions/recent")
async def get_recent_actions(
    action_type: str | None = Query(None, description="Filter by action type"),
    agent_type: str | None = Query(None, description="Filter by agent type"),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    limit: int = Query(50, ge=1, le=500, description="Max records"),
) -> list[dict[str, Any]]:
    """Get recent action records.

    Args:
        action_type: Optional action type filter
        agent_type: Optional agent type filter
        hours: How many hours back to look
        limit: Maximum records to return

    Returns:
        List of recent action records
    """
    service = await ensure_initialized()

    records = await service.get_recent_actions(
        action_type=action_type,
        agent_type=agent_type,
        hours=hours,
        limit=limit,
    )

    return [
        {
            "id": r.id,
            "action_type": r.action_type,
            "agent_type": r.agent_type,
            "domain": r.domain,
            "success": r.success,
            "confidence_score": r.confidence_score,
            "autonomous": r.autonomous,
            "execution_time_ms": r.execution_time_ms,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in records
    ]


@router.get("/stats", response_model=ActionStatsResponse)
async def get_action_stats(
    action_type: str | None = Query(None, description="Filter by action type"),
    agent_type: str | None = Query(None, description="Filter by agent type"),
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
) -> ActionStatsResponse:
    """Get statistics for actions.

    Args:
        action_type: Optional action type filter
        agent_type: Optional agent type filter
        days: Number of days to analyze

    Returns:
        Action statistics
    """
    service = await ensure_initialized()

    stats = await service.get_action_stats(
        action_type=action_type,
        agent_type=agent_type,
        days=days,
    )

    return ActionStatsResponse(
        action_type=stats.action_type,
        agent_type=stats.agent_type,
        total_count=stats.total_count,
        success_count=stats.success_count,
        failure_count=stats.failure_count,
        success_rate=stats.success_rate,
        avg_confidence=stats.avg_confidence,
        avg_execution_time_ms=stats.avg_execution_time_ms,
        last_executed=stats.last_executed,
        confidence_trend=stats.confidence_trend,
    )


@router.get("/stats/all")
async def get_all_stats(
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
) -> list[ActionStatsResponse]:
    """Get statistics for all action types.

    Args:
        days: Number of days to analyze

    Returns:
        List of action statistics
    """
    service = await ensure_initialized()
    all_stats = await service.get_all_stats(days=days)

    return [
        ActionStatsResponse(
            action_type=stats.action_type,
            agent_type=stats.agent_type,
            total_count=stats.total_count,
            success_count=stats.success_count,
            failure_count=stats.failure_count,
            success_rate=stats.success_rate,
            avg_confidence=stats.avg_confidence,
            avg_execution_time_ms=stats.avg_execution_time_ms,
            last_executed=stats.last_executed,
            confidence_trend=stats.confidence_trend,
        )
        for stats in all_stats
    ]


@router.get("/adjustments", response_model=list[ConfidenceAdjustmentResponse])
async def get_confidence_adjustments(
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
) -> list[ConfidenceAdjustmentResponse]:
    """Get recommended confidence adjustments.

    Analyzes historical success rates and recommends confidence
    score adjustments for better decision making.

    Args:
        days: Number of days to analyze

    Returns:
        List of confidence adjustment recommendations
    """
    service = await ensure_initialized()
    adjustments = await service.get_confidence_adjustments(days=days)

    return [
        ConfidenceAdjustmentResponse(
            action_type=a.action_type,
            current_base=a.current_base,
            recommended_base=a.recommended_base,
            reason=a.reason,
            sample_size=a.sample_size,
            time_period_days=a.time_period_days,
        )
        for a in adjustments
    ]


@router.get("/confidence/{action_type}")
async def get_recommended_confidence(
    action_type: str,
    agent_type: str | None = Query(None, description="Optional agent type filter"),
) -> dict[str, Any]:
    """Get recommended confidence for an action type.

    Returns the recommended confidence score based on historical
    success rates, falling back to base score if insufficient data.

    Args:
        action_type: The action type to get confidence for
        agent_type: Optional agent type filter

    Returns:
        Recommended confidence score
    """
    service = await ensure_initialized()
    confidence = await service.get_recommended_confidence(
        action_type=action_type,
        agent_type=agent_type,
    )

    return {
        "action_type": action_type,
        "agent_type": agent_type or "all",
        "recommended_confidence": round(confidence, 4),
    }


@router.get("/insights", response_model=list[LearningInsightResponse])
async def get_insights(
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
) -> list[LearningInsightResponse]:
    """Get learning insights and recommendations.

    Analyzes patterns and generates actionable recommendations
    for improving autonomous operations.

    Args:
        days: Number of days to analyze

    Returns:
        List of learning insights
    """
    service = await ensure_initialized()
    insights = await service.generate_insights(days=days)

    return [
        LearningInsightResponse(
            insight_type=i.insight_type,
            description=i.description,
            recommendation=i.recommendation,
            impact_level=i.impact_level,
            action_types=i.action_types,
            data_points=i.data_points,
            generated_at=i.generated_at,
        )
        for i in insights
    ]


@router.get("/summary")
async def get_learning_summary(
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
) -> dict[str, Any]:
    """Get comprehensive learning summary.

    Provides a complete overview of learning data including
    statistics, adjustments, and insights.

    Args:
        days: Number of days to analyze

    Returns:
        Complete learning summary
    """
    service = await ensure_initialized()
    return await service.get_learning_summary(days=days)
