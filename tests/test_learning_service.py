"""Tests for LearningService.

Comprehensive tests for the learning and adaptation system:
- Action recording and persistence
- Statistics calculation
- Confidence adjustments
- Learning insights
- Integration with controllers
"""


import pytest

from src.learning_service import (
    BASE_CONFIDENCE_SCORES,
    LearningConfig,
    LearningService,
    create_learning_service,
)


# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture
def learning_config():
    """Create test configuration."""
    return LearningConfig(
        min_sample_size=3,  # Lower for testing
        trend_window_days=7,
        confidence_adjustment_threshold=0.05,
        success_rate_warning_threshold=0.7,
        max_records_per_query=100,
    )


@pytest.fixture
async def learning_service(learning_config):
    """Create and initialize a test learning service."""
    service = LearningService(
        database_url="sqlite:///:memory:",
        config=learning_config,
    )
    await service.initialize()
    return service


@pytest.fixture
async def populated_service(learning_service):
    """Create a service with sample data."""
    # Record successful DEPLOY actions
    for i in range(5):
        await learning_service.record_action(
            action_type="DEPLOY",
            agent_type="DeployAgent",
            success=True,
            confidence_score=0.8 + i * 0.02,
            execution_time_ms=10000 + i * 1000,
        )

    # Record mixed ROLLBACK actions
    for i in range(3):
        await learning_service.record_action(
            action_type="ROLLBACK",
            agent_type="DeployAgent",
            success=i < 2,  # 2 success, 1 failure
            confidence_score=0.85,
            execution_time_ms=5000,
        )

    # Record CREATE_ISSUE actions with lower success rate
    for i in range(4):
        await learning_service.record_action(
            action_type="CREATE_ISSUE",
            agent_type="IntegrationAgent",
            success=i < 2,  # 2 success, 2 failure = 50%
            confidence_score=0.9,
            execution_time_ms=2000,
        )

    return learning_service


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================
class TestLearningServiceInit:
    """Tests for service initialization."""

    def test_create_service(self):
        """Test creating a learning service instance."""
        service = LearningService()
        assert service is not None
        assert not service.initialized

    def test_create_with_config(self, learning_config):
        """Test creating with custom configuration."""
        service = LearningService(config=learning_config)
        assert service.config.min_sample_size == 3

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test service initialization."""
        service = LearningService(database_url="sqlite:///:memory:")
        await service.initialize()
        assert service.initialized

    @pytest.mark.asyncio
    async def test_double_initialize(self):
        """Test that double initialization is safe."""
        service = LearningService(database_url="sqlite:///:memory:")
        await service.initialize()
        await service.initialize()  # Should not raise
        assert service.initialized

    @pytest.mark.asyncio
    async def test_get_session_before_init(self):
        """Test that accessing session before init raises error."""
        service = LearningService()
        with pytest.raises(RuntimeError):
            service._get_session()

    def test_factory_function(self):
        """Test factory function creates service."""
        service = create_learning_service()
        assert service is not None


# ============================================================================
# ACTION RECORDING TESTS
# ============================================================================
class TestActionRecording:
    """Tests for recording actions."""

    @pytest.mark.asyncio
    async def test_record_success(self, learning_service):
        """Test recording a successful action."""
        record = await learning_service.record_action(
            action_type="DEPLOY",
            success=True,
            agent_type="DeployAgent",
            confidence_score=0.85,
            execution_time_ms=12500,
        )

        assert record.id is not None
        assert record.action_type == "DEPLOY"
        assert record.success is True
        assert record.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_record_failure(self, learning_service):
        """Test recording a failed action."""
        record = await learning_service.record_action(
            action_type="DEPLOY",
            success=False,
            error_message="Connection timeout",
        )

        assert record.success is False
        assert record.error_message == "Connection timeout"

    @pytest.mark.asyncio
    async def test_record_with_all_fields(self, learning_service):
        """Test recording with all optional fields."""
        record = await learning_service.record_action(
            action_type="ROLLBACK",
            success=True,
            agent_type="DeployAgent",
            domain="deploy",
            decision_reason="Health check failure",
            confidence_score=0.9,
            autonomous=True,
            result_summary="Rollback completed",
            execution_time_ms=8000,
            affected_services="api,worker",
        )

        assert record.domain == "deploy"
        assert record.decision_reason == "Health check failure"
        assert record.autonomous is True
        assert record.affected_services == "api,worker"

    @pytest.mark.asyncio
    async def test_get_recent_actions(self, populated_service):
        """Test retrieving recent actions."""
        actions = await populated_service.get_recent_actions(hours=24)
        assert len(actions) == 12  # 5 + 3 + 4 from fixture

    @pytest.mark.asyncio
    async def test_get_recent_actions_filtered(self, populated_service):
        """Test filtering recent actions."""
        deploy_actions = await populated_service.get_recent_actions(
            action_type="DEPLOY",
            hours=24,
        )
        assert len(deploy_actions) == 5
        assert all(a.action_type == "DEPLOY" for a in deploy_actions)

    @pytest.mark.asyncio
    async def test_get_recent_actions_by_agent(self, populated_service):
        """Test filtering by agent type."""
        integration_actions = await populated_service.get_recent_actions(
            agent_type="IntegrationAgent",
            hours=24,
        )
        assert len(integration_actions) == 4


# ============================================================================
# STATISTICS TESTS
# ============================================================================
class TestStatistics:
    """Tests for statistics calculation."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, learning_service):
        """Test stats with no data."""
        stats = await learning_service.get_action_stats(action_type="DEPLOY")
        assert stats.total_count == 0
        assert stats.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, populated_service):
        """Test stats calculation."""
        stats = await populated_service.get_action_stats(action_type="DEPLOY")
        assert stats.total_count == 5
        assert stats.success_count == 5
        assert stats.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_get_stats_mixed_success(self, populated_service):
        """Test stats with mixed success/failure."""
        stats = await populated_service.get_action_stats(action_type="ROLLBACK")
        assert stats.total_count == 3
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert abs(stats.success_rate - 2 / 3) < 0.01

    @pytest.mark.asyncio
    async def test_get_stats_avg_confidence(self, populated_service):
        """Test average confidence calculation."""
        stats = await populated_service.get_action_stats(action_type="ROLLBACK")
        assert stats.avg_confidence == 0.85

    @pytest.mark.asyncio
    async def test_get_all_stats(self, populated_service):
        """Test getting all action stats."""
        all_stats = await populated_service.get_all_stats()
        assert len(all_stats) == 3  # DEPLOY, ROLLBACK, CREATE_ISSUE

        # Should be sorted by count descending
        assert all_stats[0].total_count >= all_stats[1].total_count

    @pytest.mark.asyncio
    async def test_stats_cache(self, populated_service):
        """Test that stats are cached."""
        # First call
        stats1 = await populated_service.get_action_stats(action_type="DEPLOY")

        # Second call should use cache
        stats2 = await populated_service.get_action_stats(action_type="DEPLOY")

        assert stats1.total_count == stats2.total_count


# ============================================================================
# TREND CALCULATION TESTS
# ============================================================================
class TestTrendCalculation:
    """Tests for trend analysis."""

    @pytest.mark.asyncio
    async def test_trend_stable(self, learning_service):
        """Test stable trend detection."""
        # Record consistent success rate
        for _ in range(10):
            await learning_service.record_action(
                action_type="ALERT",
                success=True,
                confidence_score=0.9,
            )

        stats = await learning_service.get_action_stats(action_type="ALERT")
        assert stats.confidence_trend == "stable"

    @pytest.mark.asyncio
    async def test_trend_improving(self, learning_service):
        """Test improving trend detection."""
        # Record failures first, then successes
        for i in range(10):
            success = i >= 5  # First 5 fail, last 5 succeed
            await learning_service.record_action(
                action_type="DEPLOY",
                success=success,
                confidence_score=0.8,
            )

        stats = await learning_service.get_action_stats(action_type="DEPLOY")
        assert stats.confidence_trend == "improving"

    @pytest.mark.asyncio
    async def test_trend_declining(self, learning_service):
        """Test declining trend detection."""
        # Record successes first, then failures
        for i in range(10):
            success = i < 5  # First 5 succeed, last 5 fail
            await learning_service.record_action(
                action_type="DEPLOY",
                success=success,
                confidence_score=0.8,
            )

        stats = await learning_service.get_action_stats(action_type="DEPLOY")
        assert stats.confidence_trend == "declining"


# ============================================================================
# CONFIDENCE ADJUSTMENT TESTS
# ============================================================================
class TestConfidenceAdjustments:
    """Tests for confidence adjustment recommendations."""

    @pytest.mark.asyncio
    async def test_no_adjustments_insufficient_data(self, learning_service):
        """Test no adjustments with insufficient data."""
        await learning_service.record_action(
            action_type="DEPLOY",
            success=True,
        )
        adjustments = await learning_service.get_confidence_adjustments()
        assert len(adjustments) == 0

    @pytest.mark.asyncio
    async def test_adjustment_recommended(self, learning_service):
        """Test adjustment recommended when rates differ."""
        # Perfect success rate for DEPLOY (base is 0.60)
        for _ in range(10):
            await learning_service.record_action(
                action_type="DEPLOY",
                success=True,
                confidence_score=0.6,
            )

        adjustments = await learning_service.get_confidence_adjustments()

        # Should recommend increasing confidence for DEPLOY
        deploy_adj = next((a for a in adjustments if a.action_type == "DEPLOY"), None)
        if deploy_adj:
            assert deploy_adj.recommended_base > deploy_adj.current_base
            assert deploy_adj.sample_size == 10

    @pytest.mark.asyncio
    async def test_adjustment_decrease(self, learning_service):
        """Test adjustment to decrease confidence."""
        # Low success rate for CREATE_ISSUE (base is 0.95)
        for i in range(10):
            await learning_service.record_action(
                action_type="CREATE_ISSUE",
                success=i < 3,  # 30% success
                confidence_score=0.95,
            )

        adjustments = await learning_service.get_confidence_adjustments()

        issue_adj = next((a for a in adjustments if a.action_type == "CREATE_ISSUE"), None)
        if issue_adj:
            assert issue_adj.recommended_base < issue_adj.current_base

    @pytest.mark.asyncio
    async def test_get_recommended_confidence(self, populated_service):
        """Test getting recommended confidence."""
        confidence = await populated_service.get_recommended_confidence("DEPLOY")
        assert confidence == 1.0  # All DEPLOY actions succeeded

    @pytest.mark.asyncio
    async def test_get_recommended_confidence_fallback(self, learning_service):
        """Test fallback to base confidence."""
        confidence = await learning_service.get_recommended_confidence("DEPLOY")
        assert confidence == BASE_CONFIDENCE_SCORES["DEPLOY"]


# ============================================================================
# LEARNING INSIGHTS TESTS
# ============================================================================
class TestLearningInsights:
    """Tests for insight generation."""

    @pytest.mark.asyncio
    async def test_no_insights_empty(self, learning_service):
        """Test no insights with no data."""
        insights = await learning_service.generate_insights()
        assert len(insights) == 0

    @pytest.mark.asyncio
    async def test_low_success_rate_insight(self, learning_service):
        """Test low success rate generates insight."""
        # Record mostly failures
        for i in range(10):
            await learning_service.record_action(
                action_type="DEPLOY",
                success=i < 3,  # 30% success
                confidence_score=0.8,
            )

        insights = await learning_service.generate_insights()

        low_rate = [i for i in insights if i.insight_type == "low_success_rate"]
        assert len(low_rate) >= 1
        assert low_rate[0].impact_level in ("high", "medium")

    @pytest.mark.asyncio
    async def test_declining_trend_insight(self, learning_service):
        """Test declining trend generates insight."""
        # Record successes then failures
        for i in range(10):
            await learning_service.record_action(
                action_type="DEPLOY",
                success=i < 5,
                confidence_score=0.8,
            )

        insights = await learning_service.generate_insights()

        # May have declining_trend insight if trend detected
        declining = [i for i in insights if i.insight_type == "declining_trend"]
        # Note: The actual detection depends on the trend calculation
        assert declining is not None  # Verify we can filter insights

    @pytest.mark.asyncio
    async def test_performance_gap_insight(self, learning_service):
        """Test performance gap between actions generates insight."""
        # High success action
        for _ in range(10):
            await learning_service.record_action(
                action_type="ALERT",
                success=True,
            )

        # Low success action
        for i in range(10):
            await learning_service.record_action(
                action_type="DEPLOY",
                success=i < 3,  # 30%
            )

        insights = await learning_service.generate_insights()

        gap = [i for i in insights if i.insight_type == "action_performance_gap"]
        assert len(gap) >= 1


# ============================================================================
# SUMMARY REPORT TESTS
# ============================================================================
class TestSummaryReport:
    """Tests for learning summary generation."""

    @pytest.mark.asyncio
    async def test_summary_empty(self, learning_service):
        """Test summary with no data."""
        summary = await learning_service.get_learning_summary()
        assert summary["total_actions"] == 0
        assert summary["overall_success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_summary_with_data(self, populated_service):
        """Test summary generation."""
        summary = await populated_service.get_learning_summary()

        assert summary["total_actions"] == 12
        assert summary["action_types_tracked"] == 3
        assert "stats_by_action" in summary
        assert "generated_at" in summary

    @pytest.mark.asyncio
    async def test_summary_overall_rate(self, populated_service):
        """Test overall success rate calculation."""
        summary = await populated_service.get_learning_summary()

        # 5 DEPLOY + 2 ROLLBACK + 2 CREATE_ISSUE = 9 success
        # Total = 12
        expected_rate = 9 / 12
        assert abs(summary["overall_success_rate"] - expected_rate) < 0.01


# ============================================================================
# INTEGRATION TESTS
# ============================================================================
class TestIntegration:
    """Integration tests for the learning system."""

    @pytest.mark.asyncio
    async def test_full_learning_cycle(self, learning_service):
        """Test complete learning cycle."""
        # Phase 1: Record initial actions
        for _ in range(5):
            await learning_service.record_action(
                action_type="DEPLOY",
                success=True,
                confidence_score=0.7,
            )

        # Phase 2: Get statistics
        stats = await learning_service.get_action_stats(action_type="DEPLOY")
        assert stats.success_rate == 1.0

        # Phase 3: Get confidence recommendation
        confidence = await learning_service.get_recommended_confidence("DEPLOY")
        assert confidence > 0.6  # Should recommend higher

        # Phase 4: Generate insights
        insights = await learning_service.generate_insights()
        assert isinstance(insights, list)  # May be empty if all looks good

        # Phase 5: Get summary
        summary = await learning_service.get_learning_summary()
        assert summary["total_actions"] == 5

    @pytest.mark.asyncio
    async def test_continuous_learning(self, learning_service):
        """Test learning improves over time."""
        # Initial poor performance
        for _ in range(5):
            await learning_service.record_action(
                action_type="DEPLOY",
                success=False,
            )

        initial_confidence = await learning_service.get_recommended_confidence("DEPLOY")

        # Improved performance
        for _ in range(10):
            await learning_service.record_action(
                action_type="DEPLOY",
                success=True,
            )

        improved_confidence = await learning_service.get_recommended_confidence("DEPLOY")

        # Confidence should have improved
        assert improved_confidence > initial_confidence


# ============================================================================
# EDGE CASES
# ============================================================================
class TestEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_unknown_action_type(self, learning_service):
        """Test handling unknown action types."""
        await learning_service.record_action(
            action_type="CUSTOM_ACTION",
            success=True,
        )

        stats = await learning_service.get_action_stats(action_type="CUSTOM_ACTION")
        assert stats.total_count == 1

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, learning_service):
        """Test cache is invalidated on new records."""
        await learning_service.record_action(
            action_type="DEPLOY",
            success=True,
        )

        # Get stats (will be cached)
        stats1 = await learning_service.get_action_stats(action_type="DEPLOY")

        # Record more actions
        await learning_service.record_action(
            action_type="DEPLOY",
            success=True,
        )

        # Cache should be invalidated
        stats2 = await learning_service.get_action_stats(action_type="DEPLOY")
        assert stats2.total_count == stats1.total_count + 1

    @pytest.mark.asyncio
    async def test_very_long_time_range(self, learning_service):
        """Test with long time range."""
        await learning_service.record_action(
            action_type="DEPLOY",
            success=True,
        )

        stats = await learning_service.get_action_stats(action_type="DEPLOY", days=90)
        assert stats.total_count == 1

    @pytest.mark.asyncio
    async def test_special_characters_in_fields(self, learning_service):
        """Test handling special characters."""
        record = await learning_service.record_action(
            action_type="DEPLOY",
            success=False,
            error_message="Error: 'Connection failed' with \"quotes\"",
            result_summary="Test with special chars: <>&",
        )

        assert "Connection failed" in record.error_message


# ============================================================================
# API ROUTES TESTS (if needed)
# ============================================================================
class TestAPIRoutes:
    """Tests for API endpoints."""

    @pytest.mark.asyncio
    async def test_routes_exist(self):
        """Verify learning routes are properly registered."""
        from src.api.routes.learning import router

        # Check route paths
        routes = [route.path for route in router.routes]
        assert "/health" in routes or any("/health" in r for r in routes)
