"""Tests for src/harness/scheduler.py - Task Scheduler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip all tests if dependencies not installed (harness/__init__.py imports psutil)
pytest.importorskip("psutil")
pytest.importorskip("apscheduler")
pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")


class TestSchedulerError:
    """Tests for SchedulerError exception."""

    def test_scheduler_error_is_exception(self):
        """SchedulerError should be an Exception subclass."""
        from src.harness.scheduler import SchedulerError

        assert issubclass(SchedulerError, Exception)

    def test_scheduler_error_message(self):
        """SchedulerError should store message."""
        from src.harness.scheduler import SchedulerError

        error = SchedulerError("Scheduler failed")
        assert str(error) == "Scheduler failed"


class TestAdvisoryLock:
    """Tests for advisory_lock context manager."""

    @pytest.mark.asyncio
    async def test_lock_acquired(self):
        """advisory_lock should yield True when lock acquired."""
        from src.harness.scheduler import advisory_lock

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_session.execute.return_value = mock_result

        async with advisory_lock(mock_session, "test_lock") as acquired:
            assert acquired is True

    @pytest.mark.asyncio
    async def test_lock_not_acquired(self):
        """advisory_lock should yield False when lock not acquired."""
        from src.harness.scheduler import advisory_lock

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_session.execute.return_value = mock_result

        async with advisory_lock(mock_session, "test_lock") as acquired:
            assert acquired is False

    @pytest.mark.asyncio
    async def test_lock_released_after_context(self):
        """advisory_lock should release lock after context."""
        from src.harness.scheduler import advisory_lock

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_session.execute.return_value = mock_result

        async with advisory_lock(mock_session, "test_lock"):
            pass

        # Should have called execute twice: acquire and release
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_lock_not_released_when_not_acquired(self):
        """advisory_lock should not release when lock not acquired."""
        from src.harness.scheduler import advisory_lock

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False  # Lock not acquired
        mock_session.execute.return_value = mock_result

        async with advisory_lock(mock_session, "test_lock"):
            pass

        # Should have called execute only once: acquire attempt
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_consistent_lock_id(self):
        """Same lock name should generate same lock ID."""
        import zlib

        from src.harness.scheduler import advisory_lock

        lock_name = "my_unique_lock"
        expected_id = zlib.crc32(lock_name.encode("utf-8"))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_session.execute.return_value = mock_result

        async with advisory_lock(mock_session, lock_name):
            pass

        # Check that the correct lock_id was used
        call_args = mock_session.execute.call_args_list[0]
        assert call_args[0][1]["lock_id"] == expected_id


class TestExecuteScheduledTask:
    """Tests for execute_scheduled_task function."""

    @pytest.mark.asyncio
    async def test_skip_when_lock_not_acquired(self):
        """Should skip execution when lock not acquired."""
        from src.harness.scheduler import execute_scheduled_task

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False  # Lock not acquired
        mock_session.execute.return_value = mock_result

        # Should return without error
        await execute_scheduled_task(1, mock_session)

    @pytest.mark.asyncio
    async def test_raises_when_agent_not_found(self):
        """Should raise SchedulerError when agent not found."""
        from src.harness.scheduler import SchedulerError, execute_scheduled_task

        mock_session = AsyncMock()

        # Lock acquired
        lock_result = MagicMock()
        lock_result.scalar.return_value = True

        # Agent not found
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [lock_result, agent_result, MagicMock()]

        with pytest.raises(SchedulerError, match="not found"):
            await execute_scheduled_task(999, mock_session)

    @pytest.mark.asyncio
    async def test_skip_inactive_agent(self):
        """Should skip execution for inactive agent."""
        from src.harness.scheduler import execute_scheduled_task

        mock_session = AsyncMock()

        # Lock acquired
        lock_result = MagicMock()
        lock_result.scalar.return_value = True

        # Agent found but inactive
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.status = "paused"
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = mock_agent

        mock_session.execute.side_effect = [lock_result, agent_result, MagicMock()]

        # Should complete without error
        await execute_scheduled_task(1, mock_session)

    @pytest.mark.asyncio
    async def test_executes_active_agent(self):
        """Should execute active agent code."""
        from src.harness.scheduler import execute_scheduled_task

        mock_session = AsyncMock()

        # Lock acquired
        lock_result = MagicMock()
        lock_result.scalar.return_value = True

        # Agent found and active
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"
        mock_agent.code = "class Agent:\n    def __init__(self, config): pass\n    async def execute(self): return {'status': 'success'}"
        mock_agent.config = "{}"
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = mock_agent

        mock_session.execute.side_effect = [lock_result, agent_result, MagicMock()]
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Mock task with ID
        with patch("src.harness.scheduler.Task") as mock_task_class:
            mock_task = MagicMock()
            mock_task.id = 1
            mock_task.retry_count = 0
            mock_task_class.return_value = mock_task

            # Mock execution
            with patch("src.harness.scheduler.execute_agent_code", new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = MagicMock(status="success", result={}, error=None)
                await execute_scheduled_task(1, mock_session)

                mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_json_config(self):
        """Should parse JSON config."""
        from src.harness.scheduler import execute_scheduled_task

        mock_session = AsyncMock()

        lock_result = MagicMock()
        lock_result.scalar.return_value = True

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test"
        mock_agent.status = "active"
        mock_agent.code = "class Agent:\n    pass"
        mock_agent.config = '{"timeout": 600, "max_retries": 5}'
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = mock_agent

        mock_session.execute.side_effect = [lock_result, agent_result, MagicMock()]
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch("src.harness.scheduler.Task") as mock_task_class:
            mock_task = MagicMock()
            mock_task.id = 1
            mock_task.retry_count = 0
            mock_task_class.return_value = mock_task

            with patch("src.harness.scheduler.execute_agent_code", new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = MagicMock(status="success", result={})
                await execute_scheduled_task(1, mock_session)

                # Should have passed config with timeout
                call_kwargs = mock_execute.call_args[1]
                assert call_kwargs["timeout"] == 600


class TestAgentScheduler:
    """Tests for AgentScheduler class."""

    def test_init(self):
        """AgentScheduler should initialize with session factory."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        assert scheduler.session_factory == mock_factory
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_start_loads_agents(self):
        """start should load and schedule active agents."""
        from src.harness.scheduler import AgentScheduler

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test"
        mock_agent.status = "active"
        mock_agent.config = '{"schedule": "0 * * * *"}'

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_agent]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_factory():
            yield mock_session


        scheduler = AgentScheduler(mock_factory)

        with patch.object(scheduler, "_schedule_agent", new_callable=AsyncMock) as mock_schedule:
            await scheduler.start()
            mock_schedule.assert_called_once_with(mock_agent)

        assert scheduler.running is True
        scheduler.scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_start_raises_if_already_running(self):
        """start should raise if scheduler already running."""
        from src.harness.scheduler import AgentScheduler, SchedulerError

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)
        scheduler.running = True

        with pytest.raises(SchedulerError, match="already running"):
            await scheduler.start()

    @pytest.mark.asyncio
    async def test_stop(self):
        """stop should stop the scheduler."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)
        scheduler.running = True

        with patch.object(scheduler.scheduler, "shutdown") as mock_shutdown:
            await scheduler.stop()

        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """stop should do nothing when not running."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        # Should not raise
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_schedule_agent_no_config(self):
        """_schedule_agent should skip agent without config."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.config = None

        # Should not raise
        await scheduler._schedule_agent(mock_agent)

    @pytest.mark.asyncio
    async def test_schedule_agent_no_schedule_in_config(self):
        """_schedule_agent should skip agent without schedule."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.config = '{"timeout": 300}'  # No schedule

        # Should not raise
        await scheduler._schedule_agent(mock_agent)

    @pytest.mark.asyncio
    async def test_schedule_agent_invalid_cron(self):
        """_schedule_agent should handle invalid cron expression."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.config = '{"schedule": "invalid"}'  # Invalid cron

        # Should not raise
        await scheduler._schedule_agent(mock_agent)

    @pytest.mark.asyncio
    async def test_schedule_agent_valid_cron(self):
        """_schedule_agent should schedule agent with valid cron."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test Agent"
        mock_agent.config = '{"schedule": "0 */6 * * *"}'

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            await scheduler._schedule_agent(mock_agent)
            mock_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_agent_dynamically(self):
        """add_agent should schedule agent dynamically."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 5
        mock_agent.name = "Dynamic Agent"
        mock_agent.config = '{"schedule": "*/5 * * * *"}'

        with patch.object(scheduler, "_schedule_agent", new_callable=AsyncMock) as mock_schedule:
            await scheduler.add_agent(mock_agent)
            mock_schedule.assert_called_once_with(mock_agent)

    @pytest.mark.asyncio
    async def test_remove_agent(self):
        """remove_agent should remove agent from scheduler."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        # Add a mock job
        mock_job = MagicMock()
        with patch.object(scheduler.scheduler, "get_job", return_value=mock_job):
            with patch.object(scheduler.scheduler, "remove_job") as mock_remove:
                await scheduler.remove_agent(1)
                mock_remove.assert_called_once_with("agent_1")

    @pytest.mark.asyncio
    async def test_remove_agent_not_found(self):
        """remove_agent should handle non-existent agent."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        with patch.object(scheduler.scheduler, "get_job", return_value=None):
            # Should not raise
            await scheduler.remove_agent(999)


class TestCronParsing:
    """Tests for cron expression parsing in _schedule_agent."""

    @pytest.mark.asyncio
    async def test_every_minute(self):
        """Should parse every-minute cron."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test"
        mock_agent.config = '{"schedule": "* * * * *"}'

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            await scheduler._schedule_agent(mock_agent)
            mock_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_hourly(self):
        """Should parse hourly cron."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test"
        mock_agent.config = '{"schedule": "0 * * * *"}'

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            await scheduler._schedule_agent(mock_agent)
            mock_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_at_midnight(self):
        """Should parse daily midnight cron."""
        from src.harness.scheduler import AgentScheduler

        mock_factory = MagicMock()
        scheduler = AgentScheduler(mock_factory)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test"
        mock_agent.config = '{"schedule": "0 0 * * *"}'

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            await scheduler._schedule_agent(mock_agent)
            mock_add.assert_called_once()
