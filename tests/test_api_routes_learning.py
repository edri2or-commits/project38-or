"""Tests for src/api/routes/learning.py - Learning API Routes."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip all tests if fastapi not installed
pytest.importorskip("fastapi")


class TestLearningResponseModels:
    """Tests for learning response models."""

    def test_action_stats_response_import(self):
        """ActionStatsResponse should be importable."""
        from src.api.routes.learning import ActionStatsResponse

        assert ActionStatsResponse is not None

    def test_action_stats_response_fields(self):
        """ActionStatsResponse should include all fields."""
        from src.api.routes.learning import ActionStatsResponse

        response = ActionStatsResponse(
            action_type="DEPLOY",
            agent_type="DeployAgent",
            total_count=100,
            success_count=95,
            failure_count=5,
            success_rate=0.95,
            avg_confidence=0.87,
            avg_execution_time_ms=5000.0,
            last_executed=datetime.utcnow(),
            confidence_trend="improving",
        )
        assert response.action_type == "DEPLOY"
        assert response.success_rate == 0.95

    def test_confidence_adjustment_response(self):
        """ConfidenceAdjustmentResponse should include all fields."""
        from src.api.routes.learning import ConfidenceAdjustmentResponse

        response = ConfidenceAdjustmentResponse(
            action_type="DEPLOY",
            current_base=0.7,
            recommended_base=0.85,
            reason="High success rate",
            sample_size=50,
            time_period_days=7,
        )
        assert response.recommended_base == 0.85

    def test_learning_insight_response(self):
        """LearningInsightResponse should include all fields."""
        from src.api.routes.learning import LearningInsightResponse

        response = LearningInsightResponse(
            insight_type="success_rate_trend",
            description="Success rate improving",
            recommendation="Continue strategy",
            impact_level="medium",
            action_types=["DEPLOY"],
            data_points=100,
            generated_at=datetime.utcnow(),
        )
        assert response.insight_type == "success_rate_trend"


class TestLearningRequestModels:
    """Tests for learning request models."""

    def test_record_action_request_defaults(self):
        """RecordActionRequest should have sensible defaults."""
        from src.api.routes.learning import RecordActionRequest

        request = RecordActionRequest(
            action_type="DEPLOY",
            success=True,
        )
        assert request.agent_type == "AutonomousController"
        assert request.domain == "system"
        assert request.autonomous is True

    def test_record_action_request_custom(self):
        """RecordActionRequest should accept custom values."""
        from src.api.routes.learning import RecordActionRequest

        request = RecordActionRequest(
            action_type="ROLLBACK",
            success=False,
            agent_type="DeployAgent",
            domain="deploy",
            decision_reason="Health check failure",
            confidence_score=0.85,
            autonomous=True,
            result_summary="Rollback completed",
            error_message=None,
            execution_time_ms=5000,
            affected_services="main-api,worker",
        )
        assert request.action_type == "ROLLBACK"
        assert request.confidence_score == 0.85

    def test_record_action_response(self):
        """RecordActionResponse should include all fields."""
        from src.api.routes.learning import RecordActionResponse

        response = RecordActionResponse(
            id=1,
            action_type="DEPLOY",
            success=True,
            timestamp=datetime.utcnow(),
            message="Recorded",
        )
        assert response.id == 1
        assert response.success is True


class TestLearningRouterSetup:
    """Tests for learning router configuration."""

    def test_router_import(self):
        """Router should be importable."""
        from src.api.routes.learning import router

        assert router is not None

    def test_router_prefix(self):
        """Router should have /learning prefix."""
        from src.api.routes.learning import router

        assert router.prefix == "/learning"

    def test_router_tags(self):
        """Router should have learning tag."""
        from src.api.routes.learning import router

        assert "learning" in router.tags


class TestGetLearningService:
    """Tests for get_learning_service function."""

    def test_get_learning_service_creates_instance(self):
        """get_learning_service should create LearningService."""
        from src.api.routes.learning import get_learning_service

        with patch("src.api.routes.learning._learning_service", None):
            with patch("src.api.routes.learning.create_learning_service") as mock_create:
                mock_service = MagicMock()
                mock_create.return_value = mock_service

                result = get_learning_service()

        mock_create.assert_called_once()


class TestLearningHealthEndpoint:
    """Tests for GET /learning/health endpoint."""

    @pytest.mark.asyncio
    async def test_learning_health_healthy(self):
        """learning_health should return healthy status."""
        from src.api.routes.learning import learning_health

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await learning_health()

        assert response["status"] == "healthy"
        assert response["initialized"] == "True"

    @pytest.mark.asyncio
    async def test_learning_health_unhealthy(self):
        """learning_health should return unhealthy on error."""
        from src.api.routes.learning import learning_health

        with patch("src.api.routes.learning.get_learning_service", side_effect=Exception("DB error")):
            response = await learning_health()

        assert response["status"] == "unhealthy"
        assert "error" in response


class TestRecordActionEndpoint:
    """Tests for POST /learning/actions endpoint."""

    @pytest.mark.asyncio
    async def test_record_action_success(self):
        """record_action should record and return confirmation."""
        from src.api.routes.learning import RecordActionRequest, record_action

        mock_record = MagicMock()
        mock_record.id = 1
        mock_record.action_type = "DEPLOY"
        mock_record.success = True
        mock_record.timestamp = datetime.utcnow()

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.record_action = AsyncMock(return_value=mock_record)

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            request = RecordActionRequest(action_type="DEPLOY", success=True)
            response = await record_action(request)

        assert response.id == 1
        assert response.action_type == "DEPLOY"
        assert "recorded successfully" in response.message

    @pytest.mark.asyncio
    async def test_record_action_with_error(self):
        """record_action should handle failure records."""
        from src.api.routes.learning import RecordActionRequest, record_action

        mock_record = MagicMock()
        mock_record.id = 2
        mock_record.action_type = "DEPLOY"
        mock_record.success = False
        mock_record.timestamp = datetime.utcnow()

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.record_action = AsyncMock(return_value=mock_record)

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            request = RecordActionRequest(
                action_type="DEPLOY",
                success=False,
                error_message="Connection timeout",
            )
            response = await record_action(request)

        assert response.success is False


class TestGetRecentActionsEndpoint:
    """Tests for GET /learning/actions/recent endpoint."""

    @pytest.mark.asyncio
    async def test_get_recent_actions_empty(self):
        """get_recent_actions should return empty list when no actions."""
        from src.api.routes.learning import get_recent_actions

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_recent_actions = AsyncMock(return_value=[])

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_recent_actions()

        assert response == []

    @pytest.mark.asyncio
    async def test_get_recent_actions_with_data(self):
        """get_recent_actions should return action records."""
        from src.api.routes.learning import get_recent_actions

        mock_record = MagicMock()
        mock_record.id = 1
        mock_record.action_type = "DEPLOY"
        mock_record.agent_type = "DeployAgent"
        mock_record.domain = "deploy"
        mock_record.success = True
        mock_record.confidence_score = 0.85
        mock_record.autonomous = True
        mock_record.execution_time_ms = 5000
        mock_record.timestamp = datetime.utcnow()

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_recent_actions = AsyncMock(return_value=[mock_record])

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_recent_actions(hours=24, limit=50)

        assert len(response) == 1
        assert response[0]["action_type"] == "DEPLOY"

    @pytest.mark.asyncio
    async def test_get_recent_actions_with_filters(self):
        """get_recent_actions should pass filters to service."""
        from src.api.routes.learning import get_recent_actions

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_recent_actions = AsyncMock(return_value=[])

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            await get_recent_actions(
                action_type="DEPLOY",
                agent_type="DeployAgent",
                hours=48,
                limit=100,
            )

        mock_service.get_recent_actions.assert_called_once_with(
            action_type="DEPLOY",
            agent_type="DeployAgent",
            hours=48,
            limit=100,
        )


class TestGetActionStatsEndpoint:
    """Tests for GET /learning/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_action_stats(self):
        """get_action_stats should return statistics."""
        from src.api.routes.learning import get_action_stats

        mock_stats = MagicMock()
        mock_stats.action_type = "DEPLOY"
        mock_stats.agent_type = "all"
        mock_stats.total_count = 100
        mock_stats.success_count = 95
        mock_stats.failure_count = 5
        mock_stats.success_rate = 0.95
        mock_stats.avg_confidence = 0.87
        mock_stats.avg_execution_time_ms = 5000.0
        mock_stats.last_executed = datetime.utcnow()
        mock_stats.confidence_trend = "stable"

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_action_stats = AsyncMock(return_value=mock_stats)

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_action_stats(action_type="DEPLOY", days=7)

        assert response.action_type == "DEPLOY"
        assert response.success_rate == 0.95


class TestGetAllStatsEndpoint:
    """Tests for GET /learning/stats/all endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_stats_empty(self):
        """get_all_stats should return empty list when no data."""
        from src.api.routes.learning import get_all_stats

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_all_stats = AsyncMock(return_value=[])

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_all_stats(days=7)

        assert response == []

    @pytest.mark.asyncio
    async def test_get_all_stats_with_data(self):
        """get_all_stats should return list of statistics."""
        from src.api.routes.learning import get_all_stats

        mock_stats = MagicMock()
        mock_stats.action_type = "DEPLOY"
        mock_stats.agent_type = "all"
        mock_stats.total_count = 50
        mock_stats.success_count = 48
        mock_stats.failure_count = 2
        mock_stats.success_rate = 0.96
        mock_stats.avg_confidence = 0.88
        mock_stats.avg_execution_time_ms = 4500.0
        mock_stats.last_executed = datetime.utcnow()
        mock_stats.confidence_trend = "improving"

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_all_stats = AsyncMock(return_value=[mock_stats])

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_all_stats(days=7)

        assert len(response) == 1
        assert response[0].action_type == "DEPLOY"


class TestGetConfidenceAdjustmentsEndpoint:
    """Tests for GET /learning/adjustments endpoint."""

    @pytest.mark.asyncio
    async def test_get_confidence_adjustments(self):
        """get_confidence_adjustments should return recommendations."""
        from src.api.routes.learning import get_confidence_adjustments

        mock_adjustment = MagicMock()
        mock_adjustment.action_type = "DEPLOY"
        mock_adjustment.current_base = 0.7
        mock_adjustment.recommended_base = 0.85
        mock_adjustment.reason = "High success rate"
        mock_adjustment.sample_size = 50
        mock_adjustment.time_period_days = 7

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_confidence_adjustments = AsyncMock(return_value=[mock_adjustment])

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_confidence_adjustments(days=7)

        assert len(response) == 1
        assert response[0].recommended_base == 0.85


class TestGetRecommendedConfidenceEndpoint:
    """Tests for GET /learning/confidence/{action_type} endpoint."""

    @pytest.mark.asyncio
    async def test_get_recommended_confidence(self):
        """get_recommended_confidence should return confidence score."""
        from src.api.routes.learning import get_recommended_confidence

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_recommended_confidence = AsyncMock(return_value=0.85)

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_recommended_confidence("DEPLOY", agent_type="DeployAgent")

        assert response["action_type"] == "DEPLOY"
        assert response["recommended_confidence"] == 0.85


class TestGetInsightsEndpoint:
    """Tests for GET /learning/insights endpoint."""

    @pytest.mark.asyncio
    async def test_get_insights(self):
        """get_insights should return learning insights."""
        from src.api.routes.learning import get_insights

        mock_insight = MagicMock()
        mock_insight.insight_type = "success_rate_trend"
        mock_insight.description = "Success rate improving"
        mock_insight.recommendation = "Continue strategy"
        mock_insight.impact_level = "medium"
        mock_insight.action_types = ["DEPLOY"]
        mock_insight.data_points = 100
        mock_insight.generated_at = datetime.utcnow()

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.generate_insights = AsyncMock(return_value=[mock_insight])

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_insights(days=7)

        assert len(response) == 1
        assert response[0].insight_type == "success_rate_trend"


class TestGetLearningSummaryEndpoint:
    """Tests for GET /learning/summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_learning_summary(self):
        """get_learning_summary should return complete summary."""
        from src.api.routes.learning import get_learning_summary

        mock_summary = {
            "total_actions": 100,
            "success_rate": 0.95,
            "top_actions": ["DEPLOY", "ROLLBACK"],
        }

        mock_service = MagicMock()
        mock_service.initialized = True
        mock_service.initialize = AsyncMock()
        mock_service.get_learning_summary = AsyncMock(return_value=mock_summary)

        with patch("src.api.routes.learning.get_learning_service", return_value=mock_service):
            response = await get_learning_summary(days=7)

        assert response["total_actions"] == 100
        assert response["success_rate"] == 0.95
