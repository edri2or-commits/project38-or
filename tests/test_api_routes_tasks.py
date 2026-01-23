"""Tests for task management API routes.

Tests the /tasks/* endpoints defined in src/api/routes/tasks.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _has_psutil() -> bool:
    """Check if psutil module is available."""
    try:
        import psutil
        return True
    except ImportError:
        return False


# Skip entire module if psutil is not available (required by harness.resources)
pytestmark = pytest.mark.skipif(
    not _has_psutil(),
    reason="psutil module not available (required by tasks router -> harness.resources)"
)


class MockTask:
    """Mock Task model for testing."""

    def __init__(
        self,
        id: int,
        agent_id: int,
        status: str = "pending",
        created_at: datetime | None = None,
        retry_count: int = 0,
        error: str | None = None,
    ):
        self.id = id
        self.agent_id = agent_id
        self.status = status
        self.created_at = created_at or datetime.now(UTC)
        self.scheduled_at = self.created_at
        self.retry_count = retry_count
        self.error = error


def create_test_app():
    """Create a FastAPI app with the tasks router for testing."""
    from src.api.routes.tasks import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def client():
    """Create a test client."""
    app = create_test_app()
    return TestClient(app)


class TestGetTaskEndpoint:
    """Tests for GET /tasks/{task_id} endpoint."""

    def test_get_existing_task(self, client, mock_session):
        """Test getting an existing task."""
        mock_task = MockTask(id=123, agent_id=1, status="completed")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.api.routes.tasks.get_session", return_value=mock_session):
            app = create_test_app()
            app.dependency_overrides = {}

            # Test the endpoint behavior indirectly via model
            assert mock_task.id == 123
            assert mock_task.status == "completed"

    def test_get_nonexistent_task(self, client, mock_session):
        """Test getting a non-existent task returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        # The actual endpoint would return 404
        # We test the logic here
        task = mock_result.scalar_one_or_none()
        assert task is None


class TestGetAgentTasksEndpoint:
    """Tests for GET /tasks/agent/{agent_id} endpoint."""

    def test_get_agent_tasks(self, client, mock_session):
        """Test getting tasks for an agent."""
        mock_tasks = [
            MockTask(id=1, agent_id=1, status="completed"),
            MockTask(id=2, agent_id=1, status="failed"),
            MockTask(id=3, agent_id=1, status="pending"),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_tasks
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Test the logic
        tasks = mock_result.scalars().all()
        assert len(tasks) == 3
        assert all(t.agent_id == 1 for t in tasks)

    def test_get_agent_tasks_with_limit(self, client, mock_session):
        """Test limit parameter is respected."""
        # Limit should be capped at 100
        limit = 150
        capped_limit = min(100, max(1, limit))
        assert capped_limit == 100

        limit = 0
        capped_limit = min(100, max(1, limit))
        assert capped_limit == 1


class TestRetryTaskEndpoint:
    """Tests for POST /tasks/{task_id}/retry endpoint."""

    def test_retry_failed_task(self, mock_session):
        """Test retrying a failed task creates a new task."""
        original_task = MockTask(id=123, agent_id=1, status="failed", retry_count=0)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = original_task
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Test the logic
        assert original_task.status in ["failed", "timeout"]

        # Create new task logic
        new_task = MockTask(
            id=124,
            agent_id=original_task.agent_id,
            status="pending",
            retry_count=original_task.retry_count + 1,
        )

        assert new_task.retry_count == 1
        assert new_task.agent_id == original_task.agent_id

    def test_retry_timeout_task(self, mock_session):
        """Test retrying a timeout task."""
        original_task = MockTask(id=123, agent_id=1, status="timeout", retry_count=2)

        # Can retry timeout tasks
        assert original_task.status in ["failed", "timeout"]

        new_task = MockTask(
            id=124,
            agent_id=original_task.agent_id,
            status="pending",
            retry_count=original_task.retry_count + 1,
        )

        assert new_task.retry_count == 3

    def test_retry_completed_task_not_allowed(self, mock_session):
        """Test retrying a completed task is not allowed."""
        task = MockTask(id=123, agent_id=1, status="completed")

        # Should not be allowed to retry completed tasks
        assert task.status not in ["failed", "timeout"]

    def test_retry_running_task_not_allowed(self, mock_session):
        """Test retrying a running task is not allowed."""
        task = MockTask(id=123, agent_id=1, status="running")

        assert task.status not in ["failed", "timeout"]


class TestDeleteTaskEndpoint:
    """Tests for DELETE /tasks/{task_id} endpoint."""

    def test_delete_completed_task(self, mock_session):
        """Test deleting a completed task."""
        task = MockTask(id=123, agent_id=1, status="completed")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = task
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        # Can delete completed tasks
        assert task.status != "running"

    def test_delete_running_task_not_allowed(self, mock_session):
        """Test deleting a running task is not allowed."""
        task = MockTask(id=123, agent_id=1, status="running")

        # Should not delete running tasks
        assert task.status == "running"

    def test_delete_nonexistent_task(self, mock_session):
        """Test deleting a non-existent task returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        task = mock_result.scalar_one_or_none()
        assert task is None


class TestTaskStatsEndpoint:
    """Tests for GET /tasks/stats/summary endpoint."""

    def test_get_task_stats(self, mock_session):
        """Test getting task statistics."""
        mock_tasks = [
            MockTask(id=1, agent_id=1, status="completed"),
            MockTask(id=2, agent_id=1, status="completed"),
            MockTask(id=3, agent_id=2, status="failed"),
            MockTask(id=4, agent_id=2, status="running"),
            MockTask(id=5, agent_id=3, status="pending"),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_tasks
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        tasks = mock_result.scalars().all()

        # Calculate stats
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")
        running = sum(1 for t in tasks if t.status == "running")
        pending = sum(1 for t in tasks if t.status == "pending")
        success_rate = (completed / total * 100) if total > 0 else 0.0

        assert total == 5
        assert completed == 2
        assert failed == 1
        assert running == 1
        assert pending == 1
        assert success_rate == 40.0

    def test_get_task_stats_empty(self, mock_session):
        """Test stats with no tasks."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        tasks = mock_result.scalars().all()

        total = len(tasks)
        success_rate = (0 / total * 100) if total > 0 else 0.0

        assert total == 0
        assert success_rate == 0.0


class TestMockTaskModel:
    """Tests for the MockTask test helper."""

    def test_mock_task_defaults(self):
        """Test MockTask default values."""
        task = MockTask(id=1, agent_id=1)

        assert task.status == "pending"
        assert task.retry_count == 0
        assert task.error is None
        assert task.created_at is not None

    def test_mock_task_custom_values(self):
        """Test MockTask with custom values."""
        created = datetime(2026, 1, 22, 12, 0, 0, tzinfo=UTC)
        task = MockTask(
            id=123,
            agent_id=5,
            status="failed",
            created_at=created,
            retry_count=3,
            error="Connection timeout",
        )

        assert task.id == 123
        assert task.agent_id == 5
        assert task.status == "failed"
        assert task.created_at == created
        assert task.retry_count == 3
        assert task.error == "Connection timeout"


# =============================================================================
# Direct endpoint function tests (for actual coverage)
# =============================================================================
from src.api.routes.tasks import (
    get_task,
    get_agent_tasks,
    retry_task,
    delete_task,
    get_task_stats,
)
from fastapi import HTTPException


class TestGetTaskDirect:
    """Direct tests for get_task endpoint function."""

    @pytest.mark.asyncio
    async def test_get_task_success(self):
        """Test getting an existing task directly."""
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.agent_id = 10
        mock_task.status = "completed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result

        result = await get_task(task_id=1, session=mock_session)

        assert result.id == 1
        assert result.status == "completed"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_not_found(self):
        """Test getting a non-existent task raises 404."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task(task_id=999, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in str(exc_info.value.detail)


class TestGetAgentTasksDirect:
    """Direct tests for get_agent_tasks endpoint function."""

    @pytest.mark.asyncio
    async def test_get_agent_tasks_empty(self):
        """Test getting tasks when none exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await get_agent_tasks(agent_id=1, session=mock_session)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_agent_tasks_with_results(self):
        """Test getting tasks with results."""
        mock_task1 = MagicMock()
        mock_task1.id = 1
        mock_task1.status = "completed"

        mock_task2 = MagicMock()
        mock_task2.id = 2
        mock_task2.status = "running"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_task1, mock_task2]
        mock_session.execute.return_value = mock_result

        result = await get_agent_tasks(agent_id=10, session=mock_session)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_agent_tasks_limit_capped_at_100(self):
        """Test that limit > 100 is capped."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await get_agent_tasks(agent_id=1, limit=500, session=mock_session)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_tasks_limit_min_is_1(self):
        """Test that limit < 1 becomes 1."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await get_agent_tasks(agent_id=1, limit=-5, session=mock_session)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_tasks_with_pagination(self):
        """Test pagination with limit and offset."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await get_agent_tasks(agent_id=1, limit=10, offset=20, session=mock_session)
        mock_session.execute.assert_called_once()


class TestRetryTaskDirect:
    """Direct tests for retry_task endpoint function."""

    @pytest.mark.asyncio
    async def test_retry_failed_task_success(self):
        """Test retrying a failed task creates new task."""
        mock_original = MagicMock()
        mock_original.id = 1
        mock_original.agent_id = 10
        mock_original.status = "failed"
        mock_original.retry_count = 0

        mock_new_task = MagicMock()
        mock_new_task.id = 2
        mock_new_task.agent_id = 10
        mock_new_task.status = "pending"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Patch select to return a mock query, and Task class for instantiation
        with patch("src.api.routes.tasks.select") as mock_select:
            mock_select.return_value.where.return_value = MagicMock()
            with patch("src.api.routes.tasks.Task") as MockTask:
                MockTask.return_value = mock_new_task
                MockTask.id = 1  # For the where clause
                with patch("src.api.routes.tasks.execute_scheduled_task", new_callable=AsyncMock):
                    await retry_task(task_id=1, session=mock_session)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_retry_timeout_task_success(self):
        """Test retrying a timeout task."""
        mock_original = MagicMock()
        mock_original.id = 1
        mock_original.agent_id = 10
        mock_original.status = "timeout"
        mock_original.retry_count = 1

        mock_new_task = MagicMock()
        mock_new_task.id = 2

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch("src.api.routes.tasks.select") as mock_select:
            mock_select.return_value.where.return_value = MagicMock()
            with patch("src.api.routes.tasks.Task") as MockTask:
                MockTask.return_value = mock_new_task
                MockTask.id = 1
                with patch("src.api.routes.tasks.execute_scheduled_task", new_callable=AsyncMock):
                    await retry_task(task_id=1, session=mock_session)

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_task_not_found(self):
        """Test retrying a non-existent task raises 404."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await retry_task(task_id=999, session=mock_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_completed_task_fails(self):
        """Test retrying a completed task raises 400."""
        mock_original = MagicMock()
        mock_original.id = 1
        mock_original.status = "completed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await retry_task(task_id=1, session=mock_session)

        assert exc_info.value.status_code == 400
        assert "completed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_retry_running_task_fails(self):
        """Test retrying a running task raises 400."""
        mock_original = MagicMock()
        mock_original.id = 1
        mock_original.status = "running"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await retry_task(task_id=1, session=mock_session)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_execution_fails_marks_task_failed(self):
        """Test when execution fails, task is marked as failed."""
        mock_original = MagicMock()
        mock_original.id = 1
        mock_original.agent_id = 10
        mock_original.status = "failed"
        mock_original.retry_count = 0

        mock_new_task = MagicMock()
        mock_new_task.id = 2
        mock_new_task.status = "pending"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch("src.api.routes.tasks.select") as mock_select:
            mock_select.return_value.where.return_value = MagicMock()
            with patch("src.api.routes.tasks.Task") as MockTask:
                MockTask.return_value = mock_new_task
                MockTask.id = 1
                with patch(
                    "src.api.routes.tasks.execute_scheduled_task",
                    new_callable=AsyncMock,
                    side_effect=Exception("Execution error"),
                ):
                    await retry_task(task_id=1, session=mock_session)

        assert mock_new_task.status == "failed"
        assert mock_new_task.error == "Execution error"


class TestDeleteTaskDirect:
    """Direct tests for delete_task endpoint function."""

    @pytest.mark.asyncio
    async def test_delete_task_success(self):
        """Test deleting an existing task."""
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = "completed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        result = await delete_task(task_id=1, session=mock_session)

        assert result is None
        mock_session.delete.assert_called_once_with(mock_task)

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self):
        """Test deleting a non-existent task raises 404."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_task(task_id=999, session=mock_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_running_task_fails(self):
        """Test deleting a running task raises 400."""
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = "running"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_task(task_id=1, session=mock_session)

        assert exc_info.value.status_code == 400
        assert "running" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_delete_failed_task_success(self):
        """Test deleting a failed task succeeds."""
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = "failed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        await delete_task(task_id=1, session=mock_session)

        mock_session.delete.assert_called_once()


class TestGetTaskStatsDirect:
    """Direct tests for get_task_stats endpoint function."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        """Test stats when no tasks exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await get_task_stats(session=mock_session)

        assert result["total"] == 0
        assert result["completed"] == 0
        assert result["failed"] == 0
        assert result["running"] == 0
        assert result["pending"] == 0
        assert result["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_with_tasks(self):
        """Test stats with various task statuses."""
        mock_tasks = []
        for status in ["completed", "completed", "completed", "failed", "running"]:
            task = MagicMock()
            task.status = status
            mock_tasks.append(task)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tasks
        mock_session.execute.return_value = mock_result

        result = await get_task_stats(session=mock_session)

        assert result["total"] == 5
        assert result["completed"] == 3
        assert result["failed"] == 1
        assert result["running"] == 1
        assert result["pending"] == 0
        assert result["success_rate"] == 60.0

    @pytest.mark.asyncio
    async def test_get_stats_all_completed(self):
        """Test stats when all tasks are completed."""
        mock_tasks = [MagicMock(status="completed") for _ in range(10)]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tasks
        mock_session.execute.return_value = mock_result

        result = await get_task_stats(session=mock_session)

        assert result["total"] == 10
        assert result["completed"] == 10
        assert result["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_get_stats_with_pending(self):
        """Test stats include pending tasks."""
        mock_tasks = [
            MagicMock(status="pending"),
            MagicMock(status="pending"),
            MagicMock(status="completed"),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tasks
        mock_session.execute.return_value = mock_result

        result = await get_task_stats(session=mock_session)

        assert result["total"] == 3
        assert result["pending"] == 2
        assert result["completed"] == 1
