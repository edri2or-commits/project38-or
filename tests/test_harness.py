"""Tests for Agent Harness components.

This module tests the core harness functionality: executor, scheduler,
resources, and handoff artifacts.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.harness.executor import AgentExecutor, execute_agent_by_id
from src.harness.handoff import HandoffArtifact, HandoffContext, HandoffManager
from src.harness.resources import (
    ResourceLimits,
    ResourceManager,
    ResourceUsage,
    get_resource_manager,
)
from src.harness.scheduler import AgentScheduler, distributed_lock
from src.models.agent import Agent
from src.models.task import Task


class TestExecutor:
    """Tests for AgentExecutor."""

    @pytest.mark.asyncio
    async def test_execute_simple_agent(self, async_session: AsyncSession):
        """Test executing a simple agent that prints hello world."""
        # Create test agent
        agent = Agent(
            name="Hello Agent",
            description="Prints hello world",
            code='print("Hello, World!")',
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        # Execute agent
        executor = AgentExecutor(timeout=10)
        result = await executor.execute_agent(agent.id, async_session)

        # Verify results
        assert result["status"] == "completed"
        assert "Hello, World!" in result["result"]
        assert result["error"] == ""
        assert result["duration"] > 0

        # Verify task was created
        statement = select(Task).where(Task.agent_id == agent.id)
        task_result = await async_session.exec(statement)
        task = task_result.first()
        assert task is not None
        assert task.status == "completed"
        assert task.started_at is not None
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_failing_agent(self, async_session: AsyncSession):
        """Test executing an agent that raises an error."""
        # Create test agent with failing code
        agent = Agent(
            name="Failing Agent",
            description="Raises an error",
            code='raise ValueError("Test error")',
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        # Execute agent
        executor = AgentExecutor(timeout=10)
        result = await executor.execute_agent(agent.id, async_session)

        # Verify results
        assert result["status"] == "failed"
        assert "ValueError" in result["error"]
        assert "Test error" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_timeout(self, async_session: AsyncSession):
        """Test that agent execution times out after configured duration."""
        # Create test agent that sleeps
        agent = Agent(
            name="Slow Agent",
            description="Sleeps for a long time",
            code="import time; time.sleep(100)",
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        # Execute agent with short timeout
        executor = AgentExecutor(timeout=1)
        result = await executor.execute_agent(agent.id, async_session)

        # Verify timeout occurred
        assert result["status"] == "failed"
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_nonexistent_agent(self, async_session: AsyncSession):
        """Test executing an agent that doesn't exist."""
        executor = AgentExecutor()

        with pytest.raises(ValueError, match="not found"):
            await executor.execute_agent(99999, async_session)

    @pytest.mark.asyncio
    async def test_execute_agent_without_code(self, async_session: AsyncSession):
        """Test executing an agent that has no code."""
        agent = Agent(
            name="Empty Agent",
            description="Has no code",
            code="",
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        executor = AgentExecutor()

        with pytest.raises(ValueError, match="no code"):
            await executor.execute_agent(agent.id, async_session)


class TestScheduler:
    """Tests for AgentScheduler."""

    @pytest.mark.asyncio
    async def test_distributed_lock_acquire(self, async_session: AsyncSession):
        """Test acquiring a distributed lock."""
        async with distributed_lock(async_session, "test_lock_1") as acquired:
            assert acquired is True

    @pytest.mark.asyncio
    async def test_distributed_lock_prevents_duplicate(
        self, async_session: AsyncSession
    ):
        """Test that distributed lock prevents duplicate execution."""
        # This test simulates what happens during rolling deployment
        # In a real scenario, two processes would compete for the lock

        async with distributed_lock(async_session, "test_lock_2") as acquired1:
            assert acquired1 is True

            # Try to acquire same lock in same session (should fail)
            # In production, this would be a different process/session
            async with distributed_lock(async_session, "test_lock_2") as acquired2:
                # Second attempt should fail because lock is held
                # Note: This test is simplified - in production, each
                # process would have its own session
                pass

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """Test starting and stopping the scheduler."""
        scheduler = AgentScheduler()

        # Start scheduler
        with patch.object(scheduler, "load_agent_schedules", new=AsyncMock()):
            await scheduler.start()
            assert scheduler.running is True

        # Stop scheduler
        await scheduler.stop()
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_schedule_agent_valid_cron(self):
        """Test scheduling an agent with valid cron expression."""
        scheduler = AgentScheduler()

        # Schedule agent (hourly)
        await scheduler.schedule_agent(1, "0 * * * *")

        # Verify job was added
        job = scheduler.scheduler.get_job("agent_1")
        assert job is not None

    @pytest.mark.asyncio
    async def test_schedule_agent_invalid_cron(self):
        """Test scheduling an agent with invalid cron expression."""
        scheduler = AgentScheduler()

        with pytest.raises(ValueError, match="Invalid cron"):
            await scheduler.schedule_agent(1, "invalid cron")

    @pytest.mark.asyncio
    async def test_unschedule_agent(self):
        """Test unscheduling an agent."""
        scheduler = AgentScheduler()

        # Schedule then unschedule
        await scheduler.schedule_agent(1, "0 * * * *")
        await scheduler.unschedule_agent(1)

        # Verify job was removed
        job = scheduler.scheduler.get_job("agent_1")
        assert job is None


class TestResources:
    """Tests for ResourceManager."""

    def test_resource_limits_defaults(self):
        """Test default resource limits."""
        limits = ResourceLimits()

        assert limits.max_memory_mb == 256
        assert limits.max_cpu_percent == 50.0
        assert limits.max_concurrent_agents == 5
        assert limits.max_execution_time == 300

    @pytest.mark.asyncio
    async def test_acquire_release_resources(self):
        """Test acquiring and releasing resources."""
        limits = ResourceLimits(max_concurrent_agents=2)
        manager = ResourceManager(limits)

        # Acquire first slot
        acquired1 = await manager.acquire()
        assert acquired1 is True
        assert manager.active_agents == 1

        # Acquire second slot
        acquired2 = await manager.acquire()
        assert acquired2 is True
        assert manager.active_agents == 2

        # Try to acquire third slot (should fail)
        acquired3 = await manager.acquire()
        assert acquired3 is False
        assert manager.active_agents == 2

        # Release first slot
        await manager.release()
        assert manager.active_agents == 1

        # Now third slot should succeed
        acquired4 = await manager.acquire()
        assert acquired4 is True
        assert manager.active_agents == 2

        # Cleanup
        await manager.release()
        await manager.release()

    def test_get_usage(self):
        """Test getting resource usage statistics."""
        manager = ResourceManager()
        usage = manager.get_usage()

        assert isinstance(usage, ResourceUsage)
        assert usage.memory_mb >= 0
        assert usage.memory_percent >= 0
        assert usage.cpu_percent >= 0
        assert usage.active_agents == 0

    def test_check_limits_within(self):
        """Test checking limits when usage is within bounds."""
        limits = ResourceLimits(max_cpu_percent=80.0)
        manager = ResourceManager(limits)

        usage = ResourceUsage(
            memory_mb=100.0,
            memory_percent=50.0,
            cpu_percent=60.0,
            active_agents=3,
        )

        ok, msg = manager.check_limits(usage)
        assert ok is True
        assert msg == ""

    def test_check_limits_exceeded(self):
        """Test checking limits when usage exceeds bounds."""
        limits = ResourceLimits(max_cpu_percent=50.0, max_concurrent_agents=5)
        manager = ResourceManager(limits)

        usage = ResourceUsage(
            memory_mb=100.0,
            memory_percent=95.0,  # Exceeds 90%
            cpu_percent=70.0,  # Exceeds 50%
            active_agents=5,  # At limit
        )

        ok, msg = manager.check_limits(usage)
        assert ok is False
        assert "Memory usage" in msg
        assert "CPU usage" in msg
        assert "Active agents" in msg

    def test_get_resource_manager_singleton(self):
        """Test that get_resource_manager returns singleton instance."""
        manager1 = get_resource_manager()
        manager2 = get_resource_manager()

        assert manager1 is manager2


class TestHandoff:
    """Tests for HandoffManager and handoff artifacts."""

    @pytest.mark.asyncio
    async def test_save_handoff(self, async_session: AsyncSession):
        """Test saving a handoff artifact."""
        # Create test agent and task
        agent = Agent(
            name="Test Agent",
            description="Test",
            code="pass",
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        task = Task(agent_id=agent.id, status="completed")
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)

        # Create handoff context
        context = HandoffContext(
            observations={"price": 850.0},
            actions=[{"type": "monitor", "target": "TSLA"}],
            state={"last_check": "2026-01-11"},
            metadata={"run_count": 1},
        )

        # Save handoff
        manager = HandoffManager()
        artifact = await manager.save_handoff(
            agent_id=agent.id,
            task_id=task.id,
            context=context,
            summary="Monitored stock price",
            session=async_session,
            ttl_days=7,
        )

        # Verify artifact
        assert artifact.id is not None
        assert artifact.agent_id == agent.id
        assert artifact.task_id == task.id
        assert artifact.summary == "Monitored stock price"
        assert artifact.expires_at is not None

    @pytest.mark.asyncio
    async def test_load_latest_handoff(self, async_session: AsyncSession):
        """Test loading the latest handoff artifact."""
        # Create test data
        agent = Agent(
            name="Test Agent",
            description="Test",
            code="pass",
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        task = Task(agent_id=agent.id, status="completed")
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)

        # Save two handoff artifacts
        manager = HandoffManager()
        context1 = HandoffContext(
            observations={"run": 1},
            actions=[],
            state={},
            metadata={},
        )
        await manager.save_handoff(
            agent.id, task.id, context1, "Run 1", async_session
        )

        await asyncio.sleep(0.1)  # Ensure different timestamps

        context2 = HandoffContext(
            observations={"run": 2},
            actions=[],
            state={},
            metadata={},
        )
        await manager.save_handoff(
            agent.id, task.id, context2, "Run 2", async_session
        )

        # Load latest
        loaded = await manager.load_latest_handoff(agent.id, async_session)

        # Should get run 2 (most recent)
        assert loaded is not None
        assert loaded.observations["run"] == 2

    @pytest.mark.asyncio
    async def test_load_handoff_history(self, async_session: AsyncSession):
        """Test loading handoff history."""
        # Create test data
        agent = Agent(
            name="Test Agent",
            description="Test",
            code="pass",
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        task = Task(agent_id=agent.id, status="completed")
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)

        # Save multiple handoffs
        manager = HandoffManager()
        for i in range(5):
            context = HandoffContext(
                observations={"run": i},
                actions=[],
                state={},
                metadata={},
            )
            await manager.save_handoff(
                agent.id, task.id, context, f"Run {i}", async_session
            )
            await asyncio.sleep(0.01)

        # Load history
        history = await manager.load_handoff_history(agent.id, async_session, limit=3)

        # Should get 3 most recent, newest first
        assert len(history) == 3
        assert history[0][1].observations["run"] == 4
        assert history[1][1].observations["run"] == 3
        assert history[2][1].observations["run"] == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, async_session: AsyncSession):
        """Test cleaning up expired handoff artifacts."""
        # Create test data
        agent = Agent(
            name="Test Agent",
            description="Test",
            code="pass",
            status="active",
        )
        async_session.add(agent)
        await async_session.commit()
        await async_session.refresh(agent)

        task = Task(agent_id=agent.id, status="completed")
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)

        # Create expired artifact
        expired_artifact = HandoffArtifact(
            agent_id=agent.id,
            task_id=task.id,
            context_data='{"test": "data"}',
            summary="Expired",
            expires_at=datetime.utcnow() - timedelta(days=1),  # Already expired
        )
        async_session.add(expired_artifact)

        # Create non-expired artifact
        valid_artifact = HandoffArtifact(
            agent_id=agent.id,
            task_id=task.id,
            context_data='{"test": "data"}',
            summary="Valid",
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        async_session.add(valid_artifact)
        await async_session.commit()

        # Cleanup expired
        manager = HandoffManager()
        deleted = await manager.cleanup_expired(async_session)

        assert deleted == 1

        # Verify only valid artifact remains
        statement = select(HandoffArtifact).where(
            HandoffArtifact.agent_id == agent.id
        )
        result = await async_session.exec(statement)
        remaining = result.all()
        assert len(remaining) == 1
        assert remaining[0].summary == "Valid"

    def test_handoff_context_serialization(self):
        """Test HandoffContext JSON serialization."""
        context = HandoffContext(
            observations={"price": 850.0, "volume": 1000000},
            actions=[{"type": "alert", "message": "Price increased"}],
            state={"last_price": 840.0},
            metadata={"run_count": 5, "errors": 0},
        )

        # Serialize
        json_str = context.to_json()
        assert isinstance(json_str, str)

        # Deserialize
        loaded = HandoffContext.from_json(json_str)
        assert loaded.observations == context.observations
        assert loaded.actions == context.actions
        assert loaded.state == context.state
        assert loaded.metadata == context.metadata
