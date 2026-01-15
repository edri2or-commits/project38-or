"""Learning Service for adaptive confidence and cross-agent learning.

Provides persistent storage and analysis of action outcomes to enable:
- Success rate tracking per action type and agent
- Confidence score improvements over time
- Trend analysis for decision making
- Cross-agent learning and knowledge sharing

Architecture:
    ┌────────────────────────────────────────────────────────────────┐
    │                    LearningService                              │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │               Action Recorder                             │  │
    │  │    Persist all action outcomes to PostgreSQL              │  │
    │  └──────────────────────────────────────────────────────────┘  │
    │                              ↓                                  │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │              Statistics Calculator                        │  │
    │  │    Success rates, execution times, failure patterns       │  │
    │  └──────────────────────────────────────────────────────────┘  │
    │                              ↓                                  │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │              Confidence Adjuster                          │  │
    │  │    Recommend confidence changes based on history          │  │
    │  └──────────────────────────────────────────────────────────┘  │
    │                              ↓                                  │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │              Insight Generator                            │  │
    │  │    Actionable recommendations for improvement             │  │
    │  └──────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────┘

Example:
    >>> from src.learning_service import LearningService
    >>> service = LearningService(database_url="postgresql://...")
    >>> await service.initialize()
    >>>
    >>> # Record an action
    >>> await service.record_action(
    ...     action_type="DEPLOY",
    ...     agent_type="DeployAgent",
    ...     success=True,
    ...     confidence_score=0.85,
    ...     execution_time_ms=12500
    ... )
    >>>
    >>> # Get statistics
    >>> stats = await service.get_action_stats("DEPLOY")
    >>> print(f"Success rate: {stats.success_rate:.1%}")
    >>>
    >>> # Get confidence recommendations
    >>> adjustments = await service.get_confidence_adjustments()
    >>> for adj in adjustments:
    ...     print(f"{adj.action_type}: {adj.current_base:.2f} -> {adj.recommended_base:.2f}")
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, create_engine, select

from src.models.action_record import (
    ActionRecord,
    ActionStats,
    ConfidenceAdjustment,
    LearningInsight,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================
@dataclass
class LearningConfig:
    """Configuration for the LearningService.

    Attributes:
        min_sample_size: Minimum actions before making recommendations
        trend_window_days: Days to analyze for trends
        confidence_adjustment_threshold: Min difference to suggest change
        success_rate_warning_threshold: Below this triggers warnings
        max_records_per_query: Limit for database queries
    """

    min_sample_size: int = 10
    trend_window_days: int = 7
    confidence_adjustment_threshold: float = 0.05
    success_rate_warning_threshold: float = 0.7
    max_records_per_query: int = 1000


# Base confidence scores for different action types
BASE_CONFIDENCE_SCORES = {
    "DEPLOY": 0.60,
    "ROLLBACK": 0.85,
    "CREATE_ISSUE": 0.95,
    "MERGE_PR": 0.70,
    "ALERT": 0.95,
    "EXECUTE_WORKFLOW": 0.80,
    "RESTART_SERVICE": 0.75,
    "SCALE_UP": 0.80,
    "SCALE_DOWN": 0.80,
    "CLEAR_CACHE": 0.90,
    "RESET_CONNECTIONS": 0.85,
}


# ============================================================================
# LEARNING SERVICE
# ============================================================================
class LearningService:
    """Service for learning from action outcomes and improving decisions.

    Provides:
    - Persistent action recording to PostgreSQL
    - Success rate calculations per action type/agent
    - Confidence adjustment recommendations
    - Trend analysis and insights
    - Cross-agent learning

    Attributes:
        engine: SQLAlchemy database engine
        config: Learning configuration
        initialized: Whether service is ready
    """

    def __init__(
        self,
        database_url: str | None = None,
        config: LearningConfig | None = None,
    ) -> None:
        """Initialize the LearningService.

        Args:
            database_url: PostgreSQL connection string. If None, uses in-memory SQLite.
            config: Learning configuration. Uses defaults if not provided.
        """
        self.database_url = database_url or "sqlite:///:memory:"
        self.config = config or LearningConfig()
        self.engine = None
        self.initialized = False

        # In-memory cache for performance
        self._stats_cache: dict[str, ActionStats] = {}
        self._cache_timestamp: datetime | None = None
        self._cache_ttl_seconds = 60

    async def initialize(self) -> None:
        """Initialize the database connection and create tables.

        Must be called before using other methods.
        """
        if self.initialized:
            return

        try:
            self.engine = create_engine(self.database_url, echo=False)
            # Note: In production, use Alembic for migrations
            # For now, SQLModel can create tables
            from sqlmodel import SQLModel

            SQLModel.metadata.create_all(self.engine)
            self.initialized = True
            logger.info("LearningService initialized with database: %s", self.database_url[:50])
        except Exception as e:
            logger.error("Failed to initialize LearningService: %s", e)
            raise

    def _get_session(self) -> Session:
        """Get a database session.

        Returns:
            SQLModel Session

        Raises:
            RuntimeError: If service not initialized
        """
        if not self.initialized or self.engine is None:
            raise RuntimeError("LearningService not initialized. Call initialize() first.")
        return Session(self.engine)

    # ========================================================================
    # ACTION RECORDING
    # ========================================================================
    async def record_action(
        self,
        action_type: str,
        success: bool,
        agent_type: str = "AutonomousController",
        domain: str = "system",
        decision_reason: str = "",
        confidence_score: float = 0.0,
        autonomous: bool = True,
        result_summary: str = "",
        error_message: str | None = None,
        execution_time_ms: int = 0,
        affected_services: str = "",
    ) -> ActionRecord:
        """Record an action outcome for learning.

        Args:
            action_type: Type of action (DEPLOY, ROLLBACK, etc.)
            success: Whether the action succeeded
            agent_type: Which agent executed the action
            domain: Domain category (deploy, monitoring, integration)
            decision_reason: Why this action was decided
            confidence_score: Confidence level when decision was made
            autonomous: Whether executed autonomously
            result_summary: Brief summary of outcome
            error_message: Error details if failed
            execution_time_ms: How long the action took
            affected_services: Comma-separated list of affected services

        Returns:
            The created ActionRecord
        """
        record = ActionRecord(
            action_type=action_type,
            agent_type=agent_type,
            domain=domain,
            decision_reason=decision_reason,
            confidence_score=confidence_score,
            autonomous=autonomous,
            success=success,
            result_summary=result_summary,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
            affected_services=affected_services,
            timestamp=datetime.now(UTC),
        )

        with self._get_session() as session:
            session.add(record)
            session.commit()
            session.refresh(record)

        # Invalidate cache
        self._stats_cache.clear()
        self._cache_timestamp = None

        logger.info(
            "Recorded action: %s by %s - %s (confidence: %.2f)",
            action_type,
            agent_type,
            "SUCCESS" if success else "FAILURE",
            confidence_score,
        )

        return record

    async def get_recent_actions(
        self,
        action_type: str | None = None,
        agent_type: str | None = None,
        hours: int = 24,
        limit: int = 100,
    ) -> list[ActionRecord]:
        """Get recent action records.

        Args:
            action_type: Filter by action type
            agent_type: Filter by agent type
            hours: How many hours back to look
            limit: Maximum records to return

        Returns:
            List of ActionRecords
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        with self._get_session() as session:
            statement = select(ActionRecord).where(ActionRecord.timestamp >= cutoff)

            if action_type:
                statement = statement.where(ActionRecord.action_type == action_type)
            if agent_type:
                statement = statement.where(ActionRecord.agent_type == agent_type)

            statement = statement.order_by(ActionRecord.timestamp.desc()).limit(limit)
            results = session.exec(statement).all()

        return list(results)

    # ========================================================================
    # STATISTICS CALCULATION
    # ========================================================================
    async def get_action_stats(
        self,
        action_type: str | None = None,
        agent_type: str | None = None,
        days: int = 7,
    ) -> ActionStats:
        """Get statistics for a specific action type.

        Args:
            action_type: Filter by action type (None for all)
            agent_type: Filter by agent type (None for all)
            days: Number of days to analyze

        Returns:
            ActionStats with success rates and timing
        """
        cache_key = f"{action_type or 'all'}:{agent_type or 'all'}:{days}"

        # Check cache
        if (
            self._cache_timestamp
            and (datetime.now(UTC) - self._cache_timestamp).total_seconds()
            < self._cache_ttl_seconds
            and cache_key in self._stats_cache
        ):
            return self._stats_cache[cache_key]

        cutoff = datetime.now(UTC) - timedelta(days=days)

        with self._get_session() as session:
            statement = select(ActionRecord).where(ActionRecord.timestamp >= cutoff)

            if action_type:
                statement = statement.where(ActionRecord.action_type == action_type)
            if agent_type:
                statement = statement.where(ActionRecord.agent_type == agent_type)

            records = session.exec(statement).all()

        if not records:
            return ActionStats(
                action_type=action_type or "all",
                agent_type=agent_type or "all",
            )

        total = len(records)
        successes = sum(1 for r in records if r.success)
        failures = total - successes

        avg_confidence = sum(r.confidence_score for r in records) / total
        avg_execution_time = sum(r.execution_time_ms for r in records) / total

        last_executed = max(r.timestamp for r in records) if records else None

        # Calculate trend
        trend = self._calculate_trend(records)

        stats = ActionStats(
            action_type=action_type or "all",
            agent_type=agent_type or "all",
            total_count=total,
            success_count=successes,
            failure_count=failures,
            success_rate=successes / total if total > 0 else 0.0,
            avg_confidence=avg_confidence,
            avg_execution_time_ms=avg_execution_time,
            last_executed=last_executed,
            confidence_trend=trend,
        )

        # Update cache
        self._stats_cache[cache_key] = stats
        self._cache_timestamp = datetime.now(UTC)

        return stats

    async def get_all_stats(self, days: int = 7) -> list[ActionStats]:
        """Get statistics for all action types.

        Args:
            days: Number of days to analyze

        Returns:
            List of ActionStats for each action type
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        with self._get_session() as session:
            statement = select(ActionRecord).where(ActionRecord.timestamp >= cutoff)
            records = session.exec(statement).all()

        if not records:
            return []

        # Group by action type
        by_action: dict[str, list[ActionRecord]] = defaultdict(list)
        for record in records:
            by_action[record.action_type].append(record)

        stats_list = []
        for action_type, action_records in by_action.items():
            total = len(action_records)
            successes = sum(1 for r in action_records if r.success)

            stats = ActionStats(
                action_type=action_type,
                total_count=total,
                success_count=successes,
                failure_count=total - successes,
                success_rate=successes / total if total > 0 else 0.0,
                avg_confidence=sum(r.confidence_score for r in action_records) / total,
                avg_execution_time_ms=sum(r.execution_time_ms for r in action_records) / total,
                last_executed=max(r.timestamp for r in action_records),
                confidence_trend=self._calculate_trend(action_records),
            )
            stats_list.append(stats)

        return sorted(stats_list, key=lambda s: s.total_count, reverse=True)

    def _calculate_trend(self, records: list[ActionRecord]) -> str:
        """Calculate confidence trend from records.

        Args:
            records: List of action records

        Returns:
            "improving", "stable", or "declining"
        """
        if len(records) < 5:
            return "stable"

        # Sort by timestamp
        sorted_records = sorted(records, key=lambda r: r.timestamp)

        # Compare first half vs second half success rates
        mid = len(sorted_records) // 2
        first_half = sorted_records[:mid]
        second_half = sorted_records[mid:]

        first_rate = sum(1 for r in first_half if r.success) / len(first_half)
        second_rate = sum(1 for r in second_half if r.success) / len(second_half)

        diff = second_rate - first_rate
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        return "stable"

    # ========================================================================
    # CONFIDENCE ADJUSTMENTS
    # ========================================================================
    async def get_confidence_adjustments(
        self,
        days: int = 7,
    ) -> list[ConfidenceAdjustment]:
        """Get recommended confidence adjustments based on learning.

        Analyzes historical success rates and compares to base confidence
        scores to recommend adjustments.

        Args:
            days: Number of days to analyze

        Returns:
            List of ConfidenceAdjustment recommendations
        """
        all_stats = await self.get_all_stats(days=days)
        adjustments = []

        for stats in all_stats:
            if stats.total_count < self.config.min_sample_size:
                continue

            action_type = stats.action_type
            current_base = BASE_CONFIDENCE_SCORES.get(action_type, 0.7)

            # Calculate recommended confidence based on success rate
            # Success rate directly influences confidence
            recommended = stats.success_rate

            # Only suggest adjustment if difference is significant
            diff = abs(recommended - current_base)
            if diff >= self.config.confidence_adjustment_threshold:
                reason = self._generate_adjustment_reason(stats, current_base, recommended)

                adjustments.append(
                    ConfidenceAdjustment(
                        action_type=action_type,
                        current_base=current_base,
                        recommended_base=round(recommended, 2),
                        reason=reason,
                        sample_size=stats.total_count,
                        time_period_days=days,
                    )
                )

        return sorted(
            adjustments,
            key=lambda a: abs(a.recommended_base - a.current_base),
            reverse=True,
        )

    def _generate_adjustment_reason(
        self,
        stats: ActionStats,
        current: float,
        recommended: float,
    ) -> str:
        """Generate explanation for confidence adjustment.

        Args:
            stats: Action statistics
            current: Current base confidence
            recommended: Recommended confidence

        Returns:
            Human-readable explanation
        """
        if recommended > current:
            return (
                f"Historical success rate ({stats.success_rate:.1%}) exceeds base confidence "
                f"({current:.1%}). {stats.total_count} actions analyzed over "
                f"{self.config.trend_window_days} days show consistent success."
            )
        else:
            return (
                f"Historical success rate ({stats.success_rate:.1%}) is below base confidence "
                f"({current:.1%}). Consider reviewing {stats.action_type} operations. "
                f"{stats.failure_count} failures in {stats.total_count} actions."
            )

    async def get_recommended_confidence(
        self,
        action_type: str,
        agent_type: str | None = None,
    ) -> float:
        """Get recommended confidence score for an action.

        Uses historical success rate if available, falls back to base.

        Args:
            action_type: Type of action
            agent_type: Optional agent type filter

        Returns:
            Recommended confidence score (0.0-1.0)
        """
        stats = await self.get_action_stats(action_type=action_type, agent_type=agent_type)

        if stats.total_count < self.config.min_sample_size:
            return BASE_CONFIDENCE_SCORES.get(action_type, 0.7)

        return stats.success_rate

    # ========================================================================
    # LEARNING INSIGHTS
    # ========================================================================
    async def generate_insights(self, days: int = 7) -> list[LearningInsight]:
        """Generate actionable learning insights.

        Analyzes patterns and generates recommendations for improvement.

        Args:
            days: Number of days to analyze

        Returns:
            List of LearningInsight recommendations
        """
        all_stats = await self.get_all_stats(days=days)
        insights = []

        for stats in all_stats:
            # Low success rate warning
            if (
                stats.total_count >= self.config.min_sample_size
                and stats.success_rate < self.config.success_rate_warning_threshold
            ):
                desc = f"{stats.action_type} has low success rate: {stats.success_rate:.1%}"
                rec = f"Review recent {stats.action_type} failures"
                insights.append(
                    LearningInsight(
                        insight_type="low_success_rate",
                        description=desc,
                        recommendation=rec,
                        impact_level="high" if stats.success_rate < 0.5 else "medium",
                        action_types=[stats.action_type],
                        data_points=stats.total_count,
                    )
                )

            # Declining trend warning
            if stats.confidence_trend == "declining":
                insights.append(
                    LearningInsight(
                        insight_type="declining_trend",
                        description=f"{stats.action_type} shows declining success rate",
                        recommendation="Investigate recent changes affecting reliability",
                        impact_level="medium",
                        action_types=[stats.action_type],
                        data_points=stats.total_count,
                    )
                )

            # Slow execution warning
            if stats.avg_execution_time_ms > 30000:  # > 30 seconds
                exec_time = stats.avg_execution_time_ms / 1000
                insights.append(
                    LearningInsight(
                        insight_type="slow_execution",
                        description=f"{stats.action_type} avg time: {exec_time:.1f}s",
                        recommendation="Consider optimizing or adding timeout handling",
                        impact_level="low",
                        action_types=[stats.action_type],
                        data_points=stats.total_count,
                    )
                )

        # Cross-agent analysis
        if len(all_stats) > 1:
            success_rates = [
                (s.action_type, s.success_rate)
                for s in all_stats
                if s.total_count >= 5
            ]
            if success_rates:
                best = max(success_rates, key=lambda x: x[1])
                worst = min(success_rates, key=lambda x: x[1])

                if best[1] - worst[1] > 0.3:
                    desc = f"Gap: {best[0]} ({best[1]:.1%}) vs {worst[0]} ({worst[1]:.1%})"
                    rec = f"Apply patterns from {best[0]} to improve {worst[0]}"
                    insights.append(
                        LearningInsight(
                            insight_type="action_performance_gap",
                            description=desc,
                            recommendation=rec,
                            impact_level="medium",
                            action_types=[best[0], worst[0]],
                            data_points=sum(s.total_count for s in all_stats),
                        )
                    )

        priority_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(insights, key=lambda i: priority_map[i.impact_level])

    # ========================================================================
    # REPORTING
    # ========================================================================
    async def get_learning_summary(self, days: int = 7) -> dict[str, Any]:
        """Get comprehensive learning summary.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with complete learning analysis
        """
        all_stats = await self.get_all_stats(days=days)
        adjustments = await self.get_confidence_adjustments(days=days)
        insights = await self.generate_insights(days=days)

        total_actions = sum(s.total_count for s in all_stats)
        total_successes = sum(s.success_count for s in all_stats)
        overall_success_rate = total_successes / total_actions if total_actions > 0 else 0.0

        return {
            "period_days": days,
            "total_actions": total_actions,
            "overall_success_rate": round(overall_success_rate, 4),
            "action_types_tracked": len(all_stats),
            "stats_by_action": [
                {
                    "action_type": s.action_type,
                    "count": s.total_count,
                    "success_rate": round(s.success_rate, 4),
                    "trend": s.confidence_trend,
                }
                for s in all_stats
            ],
            "confidence_adjustments": len(adjustments),
            "adjustments": [
                {
                    "action_type": a.action_type,
                    "current": a.current_base,
                    "recommended": a.recommended_base,
                    "reason": a.reason[:100] + "..." if len(a.reason) > 100 else a.reason,
                }
                for a in adjustments[:5]
            ],
            "insights_count": len(insights),
            "critical_insights": [
                {"type": i.insight_type, "description": i.description}
                for i in insights
                if i.impact_level in ("critical", "high")
            ],
            "generated_at": datetime.now(UTC).isoformat(),
        }


# ============================================================================
# FACTORY FUNCTION
# ============================================================================
def create_learning_service(
    database_url: str | None = None,
    config: LearningConfig | None = None,
) -> LearningService:
    """Create a LearningService instance.

    Args:
        database_url: PostgreSQL connection string
        config: Learning configuration

    Returns:
        Configured LearningService instance
    """
    return LearningService(database_url=database_url, config=config)
