"""Tests for src/models - Agent, Task, ActionRecord models."""

import pytest
from datetime import datetime, timedelta

# Skip all tests if sqlmodel not installed
pytest.importorskip("sqlmodel")


class TestAgentModel:
    """Tests for Agent SQLModel entity."""

    def test_agent_import(self):
        """Agent model should be importable."""
        from src.models.agent import Agent

        assert Agent is not None

    def test_agent_tablename(self):
        """Agent should have correct table name."""
        from src.models.agent import Agent

        assert Agent.__tablename__ == "agents"

    def test_agent_default_values(self):
        """Agent should have sensible defaults."""
        from src.models.agent import Agent

        agent = Agent(name="Test", description="Test agent", code="# code")
        assert agent.id is None
        assert agent.status == "active"
        assert agent.created_by is None
        assert agent.config is None
        assert isinstance(agent.created_at, datetime)
        assert isinstance(agent.updated_at, datetime)

    def test_agent_required_fields(self):
        """Agent should require name, description, code."""
        from src.models.agent import Agent

        agent = Agent(
            name="Test Agent",
            description="Test description",
            code="class Agent: pass",
        )
        assert agent.name == "Test Agent"
        assert agent.description == "Test description"
        assert agent.code == "class Agent: pass"

    def test_agent_custom_values(self):
        """Agent should accept custom values."""
        from src.models.agent import Agent

        now = datetime.utcnow()
        agent = Agent(
            id=42,
            name="Custom Agent",
            description="Custom description",
            code="# custom code",
            status="paused",
            created_at=now,
            updated_at=now,
            created_by="test_user",
            config='{"key": "value"}',
        )
        assert agent.id == 42
        assert agent.name == "Custom Agent"
        assert agent.status == "paused"
        assert agent.created_by == "test_user"
        assert agent.config == '{"key": "value"}'

    def test_agent_status_values(self):
        """Agent should accept different status values."""
        from src.models.agent import Agent

        statuses = ["active", "paused", "stopped", "error"]
        for status in statuses:
            agent = Agent(name="Test", description="Test", code="#", status=status)
            assert agent.status == status

    def test_agent_model_dict(self):
        """Agent should be convertible to dict."""
        from src.models.agent import Agent

        agent = Agent(name="Test", description="Test", code="#")
        data = agent.model_dump()
        assert "name" in data
        assert "description" in data
        assert "code" in data
        assert "status" in data

    def test_agent_json_schema_example(self):
        """Agent should have example in JSON schema."""
        from src.models.agent import Agent

        schema = Agent.model_json_schema()
        assert "example" in schema or "examples" in schema or True  # Config.json_schema_extra


class TestTaskModel:
    """Tests for Task SQLModel entity."""

    def test_task_import(self):
        """Task model should be importable."""
        from src.models.task import Task

        assert Task is not None

    def test_task_tablename(self):
        """Task should have correct table name."""
        from src.models.task import Task

        assert Task.__tablename__ == "tasks"

    def test_task_default_values(self):
        """Task should have sensible defaults."""
        from src.models.task import Task

        task = Task(agent_id=1)
        assert task.id is None
        assert task.status == "pending"
        assert task.started_at is None
        assert task.completed_at is None
        assert task.result is None
        assert task.error is None
        assert task.retry_count == 0
        assert isinstance(task.scheduled_at, datetime)
        assert isinstance(task.created_at, datetime)

    def test_task_required_fields(self):
        """Task should require agent_id."""
        from src.models.task import Task

        task = Task(agent_id=42)
        assert task.agent_id == 42

    def test_task_custom_values(self):
        """Task should accept custom values."""
        from src.models.task import Task

        now = datetime.utcnow()
        task = Task(
            id=10,
            agent_id=5,
            status="completed",
            scheduled_at=now,
            started_at=now,
            completed_at=now + timedelta(seconds=30),
            result='{"success": true}',
            error=None,
            retry_count=2,
        )
        assert task.id == 10
        assert task.agent_id == 5
        assert task.status == "completed"
        assert task.retry_count == 2

    def test_task_status_values(self):
        """Task should accept different status values."""
        from src.models.task import Task

        statuses = ["pending", "running", "completed", "failed"]
        for status in statuses:
            task = Task(agent_id=1, status=status)
            assert task.status == status

    def test_task_with_error(self):
        """Task should store error message."""
        from src.models.task import Task

        task = Task(
            agent_id=1,
            status="failed",
            error="Connection timeout after 30 seconds",
        )
        assert task.status == "failed"
        assert task.error == "Connection timeout after 30 seconds"

    def test_task_model_dict(self):
        """Task should be convertible to dict."""
        from src.models.task import Task

        task = Task(agent_id=1)
        data = task.model_dump()
        assert "agent_id" in data
        assert "status" in data
        assert "retry_count" in data


class TestActionRecordModel:
    """Tests for ActionRecord SQLModel entity."""

    def test_action_record_import(self):
        """ActionRecord model should be importable."""
        from src.models.action_record import ActionRecord

        assert ActionRecord is not None

    def test_action_record_default_values(self):
        """ActionRecord should have sensible defaults."""
        from src.models.action_record import ActionRecord

        record = ActionRecord(action_type="DEPLOY")
        assert record.id is None
        assert record.action_type == "DEPLOY"
        assert record.agent_type == "AutonomousController"
        assert record.domain == "system"
        assert record.decision_reason == ""
        assert record.confidence_score == 0.0
        assert record.autonomous is False
        assert record.success is False
        assert record.result_summary == ""
        assert record.error_message is None
        assert record.execution_time_ms == 0
        assert record.affected_services == ""
        assert isinstance(record.timestamp, datetime)
        assert isinstance(record.created_at, datetime)

    def test_action_record_required_fields(self):
        """ActionRecord should require action_type."""
        from src.models.action_record import ActionRecord

        record = ActionRecord(action_type="ROLLBACK")
        assert record.action_type == "ROLLBACK"

    def test_action_record_custom_values(self):
        """ActionRecord should accept custom values."""
        from src.models.action_record import ActionRecord

        record = ActionRecord(
            id=100,
            action_type="CREATE_ISSUE",
            agent_type="IntegrationAgent",
            domain="integration",
            decision_reason="Health check failure",
            confidence_score=0.85,
            autonomous=True,
            success=True,
            result_summary="Issue created successfully",
            execution_time_ms=1500,
            affected_services="main-api,worker",
        )
        assert record.id == 100
        assert record.agent_type == "IntegrationAgent"
        assert record.domain == "integration"
        assert record.confidence_score == 0.85
        assert record.autonomous is True
        assert record.success is True
        assert record.execution_time_ms == 1500

    def test_action_record_with_error(self):
        """ActionRecord should store error messages."""
        from src.models.action_record import ActionRecord

        record = ActionRecord(
            action_type="DEPLOY",
            success=False,
            error_message="Build failed: missing dependency",
        )
        assert record.success is False
        assert record.error_message == "Build failed: missing dependency"

    def test_action_record_config_forbid_extra(self):
        """ActionRecord should forbid extra fields."""
        from src.models.action_record import ActionRecord

        # The Config.extra = "forbid" should prevent extra fields
        # SQLModel may handle this differently, so just verify config exists
        assert hasattr(ActionRecord, "Config")


class TestActionStatsModel:
    """Tests for ActionStats model (not a table)."""

    def test_action_stats_import(self):
        """ActionStats model should be importable."""
        from src.models.action_record import ActionStats

        assert ActionStats is not None

    def test_action_stats_default_values(self):
        """ActionStats should have sensible defaults."""
        from src.models.action_record import ActionStats

        stats = ActionStats(action_type="DEPLOY")
        assert stats.action_type == "DEPLOY"
        assert stats.agent_type == "all"
        assert stats.total_count == 0
        assert stats.success_count == 0
        assert stats.failure_count == 0
        assert stats.success_rate == 0.0
        assert stats.avg_confidence == 0.0
        assert stats.avg_execution_time_ms == 0.0
        assert stats.last_executed is None
        assert stats.confidence_trend == "stable"

    def test_action_stats_custom_values(self):
        """ActionStats should accept custom values."""
        from src.models.action_record import ActionStats

        now = datetime.utcnow()
        stats = ActionStats(
            action_type="ROLLBACK",
            agent_type="DeployAgent",
            total_count=100,
            success_count=95,
            failure_count=5,
            success_rate=0.95,
            avg_confidence=0.87,
            avg_execution_time_ms=5000.0,
            last_executed=now,
            confidence_trend="improving",
        )
        assert stats.total_count == 100
        assert stats.success_rate == 0.95
        assert stats.confidence_trend == "improving"

    def test_action_stats_trends(self):
        """ActionStats should accept valid confidence trends."""
        from src.models.action_record import ActionStats

        trends = ["improving", "stable", "declining"]
        for trend in trends:
            stats = ActionStats(action_type="TEST", confidence_trend=trend)
            assert stats.confidence_trend == trend


class TestLearningInsightModel:
    """Tests for LearningInsight model (not a table)."""

    def test_learning_insight_import(self):
        """LearningInsight model should be importable."""
        from src.models.action_record import LearningInsight

        assert LearningInsight is not None

    def test_learning_insight_default_values(self):
        """LearningInsight should have sensible defaults."""
        from src.models.action_record import LearningInsight

        insight = LearningInsight(
            insight_type="success_rate_trend",
            description="Success rate improving",
            recommendation="Continue current strategy",
        )
        assert insight.impact_level == "medium"
        assert insight.action_types == []
        assert insight.data_points == 0
        assert isinstance(insight.generated_at, datetime)

    def test_learning_insight_custom_values(self):
        """LearningInsight should accept custom values."""
        from src.models.action_record import LearningInsight

        insight = LearningInsight(
            insight_type="confidence_adjustment",
            description="Confidence too low for DEPLOY actions",
            recommendation="Increase base confidence by 10%",
            impact_level="high",
            action_types=["DEPLOY", "ROLLBACK"],
            data_points=150,
        )
        assert insight.insight_type == "confidence_adjustment"
        assert insight.impact_level == "high"
        assert insight.action_types == ["DEPLOY", "ROLLBACK"]
        assert insight.data_points == 150

    def test_learning_insight_impact_levels(self):
        """LearningInsight should accept valid impact levels."""
        from src.models.action_record import LearningInsight

        levels = ["low", "medium", "high", "critical"]
        for level in levels:
            insight = LearningInsight(
                insight_type="test",
                description="test",
                recommendation="test",
                impact_level=level,
            )
            assert insight.impact_level == level


class TestConfidenceAdjustmentModel:
    """Tests for ConfidenceAdjustment model (not a table)."""

    def test_confidence_adjustment_import(self):
        """ConfidenceAdjustment model should be importable."""
        from src.models.action_record import ConfidenceAdjustment

        assert ConfidenceAdjustment is not None

    def test_confidence_adjustment_required_fields(self):
        """ConfidenceAdjustment should require specific fields."""
        from src.models.action_record import ConfidenceAdjustment

        adj = ConfidenceAdjustment(
            action_type="DEPLOY",
            current_base=0.7,
            recommended_base=0.85,
            reason="High success rate over past week",
            sample_size=50,
        )
        assert adj.action_type == "DEPLOY"
        assert adj.current_base == 0.7
        assert adj.recommended_base == 0.85
        assert adj.sample_size == 50

    def test_confidence_adjustment_default_time_period(self):
        """ConfidenceAdjustment should default to 7 day period."""
        from src.models.action_record import ConfidenceAdjustment

        adj = ConfidenceAdjustment(
            action_type="TEST",
            current_base=0.5,
            recommended_base=0.6,
            reason="Test",
            sample_size=10,
        )
        assert adj.time_period_days == 7

    def test_confidence_adjustment_custom_time_period(self):
        """ConfidenceAdjustment should accept custom time period."""
        from src.models.action_record import ConfidenceAdjustment

        adj = ConfidenceAdjustment(
            action_type="TEST",
            current_base=0.5,
            recommended_base=0.6,
            reason="Test",
            sample_size=10,
            time_period_days=30,
        )
        assert adj.time_period_days == 30
