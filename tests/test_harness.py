"""Tests for Agent Harness - Executor, Handoff, Scheduler, Resources.

These tests verify the 24/7 orchestration infrastructure:
- Code execution in subprocess isolation
- State preservation between runs
- Automatic scheduling and retry
- Resource monitoring and limits
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import psutil
import pytest
from sqlmodel import select

from src.harness import (
    AgentExecutor,
    ExecutionResult,
    HandoffArtifact,
    HandoffManager,
    ResourceLimits,
    ResourceManager,
    TaskScheduler,
)
from src.models.agent import Agent
from src.models.task import Task


class TestAgentExecutor:
    """Test AgentExecutor - safe code execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_agent(self, test_db_session):
        """Test executing a simple agent that prints output."""
        # Create test agent
        agent = Agent(
            name="Test Agent",
            description="Simple print agent",
            code='print("Hello from agent!")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Execute agent
        executor = AgentExecutor(timeout_seconds=10)
        result = await executor.execute_agent(agent.id)

        # Verify success
        assert result.success
        assert "Hello from agent!" in result.stdout
        assert result.exit_code == 0
        assert result.duration_seconds > 0

        # Verify task record created
        task_result = await test_db_session.execute(
            select(Task).where(Task.agent_id == agent.id)
        )
        task = task_result.scalar_one()
        assert task.status == "completed"
        assert task.result == result.stdout
        assert task.started_at is not None
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_agent_with_error(self, test_db_session):
        """Test executing an agent that raises an error."""
        # Create agent with error
        agent = Agent(
            name="Error Agent",
            description="Agent that fails",
            code='raise ValueError("Test error")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Execute agent
        executor = AgentExecutor()
        result = await executor.execute_agent(agent.id)

        # Verify failure
        assert not result.success
        assert result.exit_code != 0
        assert "Test error" in result.stderr

        # Verify task record shows failure
        task_result = await test_db_session.execute(
            select(Task).where(Task.agent_id == agent.id)
        )
        task = task_result.scalar_one()
        assert task.status == "failed"
        assert task.error is not None

    @pytest.mark.asyncio
    async def test_execute_agent_timeout(self, test_db_session):
        """Test timeout protection for long-running agents."""
        # Create agent that sleeps forever
        agent = Agent(
            name="Timeout Agent",
            description="Agent that times out",
            code="import time; time.sleep(999)",
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Execute with short timeout
        executor = AgentExecutor(timeout_seconds=1)
        result = await executor.execute_agent(agent.id)

        # Verify timeout
        assert not result.success
        assert "Timeout" in result.error_message
        assert result.duration_seconds >= 1

    @pytest.mark.asyncio
    async def test_execute_agent_with_context(self, test_db_session):
        """Test executing agent with injected context."""
        # Create agent that uses context
        agent = Agent(
            name="Context Agent",
            description="Agent that uses context",
            code='print(f"Value: {CONTEXT[\'key\']}")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Execute with context
        executor = AgentExecutor()
        result = await executor.execute_agent(agent.id, context={"key": "test_value"})

        # Verify context was injected
        assert result.success
        assert "Value: test_value" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_inactive_agent(self, test_db_session):
        """Test executing an inactive agent raises error."""
        # Create inactive agent
        agent = Agent(
            name="Inactive Agent",
            description="Should not execute",
            code='print("Should not run")',
            status="paused",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Attempt to execute
        executor = AgentExecutor()
        result = await executor.execute_agent(agent.id)

        # Verify failure due to status
        assert not result.success
        assert "not active" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_nonexistent_agent(self, test_db_session):
        """Test executing non-existent agent raises error."""
        executor = AgentExecutor()
        result = await executor.execute_agent(agent_id=99999)

        # Verify failure
        assert not result.success
        assert "not found" in result.error_message.lower()


class TestHandoffManager:
    """Test HandoffManager - state preservation."""

    @pytest.mark.asyncio
    async def test_save_and_load_artifact(self, test_db_session):
        """Test saving and loading handoff artifacts."""
        # Create test agent
        agent = Agent(
            name="Stateful Agent",
            description="Agent with state",
            code='print("test")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Save artifact
        manager = HandoffManager()
        state = {"counter": 42, "last_value": "test"}
        artifact = await manager.save_artifact(
            agent.id,
            state=state,
            summary="Test run",
        )

        assert artifact.agent_id == agent.id
        assert artifact.state == state
        assert artifact.summary == "Test run"
        assert artifact.run_count == 1

        # Load artifact
        loaded = await manager.load_artifact(agent.id)
        assert loaded is not None
        assert loaded.state == state
        assert loaded.run_count == 1

    @pytest.mark.asyncio
    async def test_artifact_run_count_increments(self, test_db_session):
        """Test run count increments with each save."""
        # Create agent
        agent = Agent(
            name="Counter Agent",
            description="Counts runs",
            code='print("test")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        manager = HandoffManager()

        # Save multiple times
        for i in range(3):
            artifact = await manager.save_artifact(agent.id, state={"run": i})
            assert artifact.run_count == i + 1

        # Verify final count
        loaded = await manager.load_artifact(agent.id)
        assert loaded.run_count == 3

    @pytest.mark.asyncio
    async def test_load_artifact_first_run(self, test_db_session):
        """Test loading artifact on first run returns None."""
        # Create agent with no artifact
        agent = Agent(
            name="New Agent",
            description="First run",
            code='print("test")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        manager = HandoffManager()
        artifact = await manager.load_artifact(agent.id)

        # First run should return None
        assert artifact is None

    @pytest.mark.asyncio
    async def test_clear_artifact(self, test_db_session):
        """Test clearing artifact resets state."""
        # Create agent with artifact
        agent = Agent(
            name="Clear Agent",
            description="Test clear",
            code='print("test")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        manager = HandoffManager()

        # Save artifact
        await manager.save_artifact(agent.id, state={"data": "test"})

        # Clear it
        await manager.clear_artifact(agent.id)

        # Verify cleared
        artifact = await manager.load_artifact(agent.id)
        assert artifact is None

    @pytest.mark.asyncio
    async def test_compress_context(self, test_db_session):
        """Test context compression."""
        # Create agent
        agent = Agent(
            name="Compress Agent",
            description="Test compression",
            code='print("test")',
            status="active",
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        manager = HandoffManager()

        # Compress context
        previous_state = {"run_count": 5, "important_data": {"key": "value"}}
        raw_output = "Long output " * 100  # 1000+ chars
        compressed = await manager.compress_context(
            agent.id,
            raw_output,
            previous_state,
        )

        # Verify compression
        assert len(compressed["previous_output"]) <= 500  # Truncated
        assert compressed["run_count"] == 6  # Incremented
        assert "important_data" in compressed  # Preserved


class TestResourceManager:
    """Test ResourceManager - resource monitoring."""

    def test_get_process_usage(self):
        """Test getting process resource usage."""
        manager = ResourceManager()

        # Get usage for current process
        usage = manager.get_process_usage(os.getpid())

        # Verify metrics present
        assert "memory_mb" in usage
        assert "cpu_percent" in usage
        assert "num_threads" in usage
        assert "num_children" in usage
        assert usage["memory_mb"] > 0

    def test_get_process_usage_nonexistent(self):
        """Test getting usage for non-existent process raises error."""
        manager = ResourceManager()

        with pytest.raises(ValueError, match="not found"):
            manager.get_process_usage(999999)

    def test_exceeds_limits_memory(self):
        """Test memory limit detection."""
        manager = ResourceManager()

        usage = {"memory_mb": 300, "cpu_percent": 10, "num_children": 2}
        limits = ResourceLimits(max_memory_mb=256)

        assert manager.exceeds_limits(usage, limits)

    def test_exceeds_limits_cpu(self):
        """Test CPU limit detection."""
        manager = ResourceManager()

        usage = {"memory_mb": 100, "cpu_percent": 95, "num_children": 2}
        limits = ResourceLimits(max_cpu_percent=80)

        assert manager.exceeds_limits(usage, limits)

    def test_exceeds_limits_processes(self):
        """Test process count limit detection."""
        manager = ResourceManager()

        usage = {"memory_mb": 100, "cpu_percent": 50, "num_children": 10}
        limits = ResourceLimits(max_processes=5)

        assert manager.exceeds_limits(usage, limits)

    def test_within_limits(self):
        """Test within limits returns False."""
        manager = ResourceManager()

        usage = {"memory_mb": 100, "cpu_percent": 50, "num_children": 2}
        limits = ResourceLimits(max_memory_mb=256, max_cpu_percent=80, max_processes=5)

        assert not manager.exceeds_limits(usage, limits)

    def test_get_system_resources(self):
        """Test getting overall system resources."""
        manager = ResourceManager()

        resources = manager.get_system_resources()

        # Verify keys present
        assert "total_memory_mb" in resources
        assert "available_memory_mb" in resources
        assert "memory_percent" in resources
        assert "cpu_count" in resources
        assert "cpu_percent" in resources

        # Sanity checks
        assert resources["total_memory_mb"] > 0
        assert resources["cpu_count"] > 0


class TestTaskScheduler:
    """Test TaskScheduler - automatic scheduling."""

    @pytest.mark.asyncio
    async def test_add_agent_schedule_interval(self, test_db_session):
        """Test adding interval-based schedule."""
        # Create agent with schedule
        config = {
            "schedule": {
                "type": "interval",
                "interval_minutes": 30,
                "enabled": True,
            }
        }
        agent = Agent(
            name="Scheduled Agent",
            description="Runs every 30 minutes",
            code='print("Scheduled run")',
            status="active",
            config=json.dumps(config),
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Add schedule
        scheduler = TaskScheduler()
        scheduler.scheduler.start()
        await scheduler.add_agent_schedule(agent.id)

        # Verify job added
        job = scheduler.scheduler.get_job(f"agent_{agent.id}")
        assert job is not None
        assert job.name == f"Agent {agent.name}"

        scheduler.scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_add_agent_schedule_cron(self, test_db_session):
        """Test adding cron-based schedule."""
        # Create agent with cron schedule
        config = {
            "schedule": {
                "type": "cron",
                "cron": "0 * * * *",  # Hourly
                "enabled": True,
            }
        }
        agent = Agent(
            name="Cron Agent",
            description="Runs hourly",
            code='print("Hourly run")',
            status="active",
            config=json.dumps(config),
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Add schedule
        scheduler = TaskScheduler()
        scheduler.scheduler.start()
        await scheduler.add_agent_schedule(agent.id)

        # Verify job added
        job = scheduler.scheduler.get_job(f"agent_{agent.id}")
        assert job is not None

        scheduler.scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_remove_agent_schedule(self, test_db_session):
        """Test removing agent schedule."""
        # Create scheduled agent
        config = {
            "schedule": {
                "type": "interval",
                "interval_minutes": 10,
                "enabled": True,
            }
        }
        agent = Agent(
            name="Remove Schedule Agent",
            description="Schedule will be removed",
            code='print("test")',
            status="active",
            config=json.dumps(config),
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Add and then remove schedule
        scheduler = TaskScheduler()
        scheduler.scheduler.start()
        await scheduler.add_agent_schedule(agent.id)

        # Verify exists
        assert scheduler.scheduler.get_job(f"agent_{agent.id}") is not None

        # Remove
        await scheduler.remove_agent_schedule(agent.id)

        # Verify removed
        assert scheduler.scheduler.get_job(f"agent_{agent.id}") is None

        scheduler.scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_schedule_disabled(self, test_db_session):
        """Test disabled schedule is not added."""
        # Create agent with disabled schedule
        config = {
            "schedule": {
                "type": "interval",
                "interval_minutes": 10,
                "enabled": False,
            }
        }
        agent = Agent(
            name="Disabled Agent",
            description="Schedule disabled",
            code='print("test")',
            status="active",
            config=json.dumps(config),
        )
        test_db_session.add(agent)
        await test_db_session.commit()
        await test_db_session.refresh(agent)

        # Attempt to add schedule
        scheduler = TaskScheduler()
        scheduler.scheduler.start()
        await scheduler.add_agent_schedule(agent.id)

        # Verify not added
        assert scheduler.scheduler.get_job(f"agent_{agent.id}") is None

        scheduler.scheduler.shutdown(wait=False)
