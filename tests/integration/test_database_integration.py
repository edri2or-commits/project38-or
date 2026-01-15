"""
Integration tests for database operations.

These tests require a running PostgreSQL instance.
Run with: DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test pytest tests/integration/
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from src.models.agent import Agent
from src.models.task import Task

pytestmark = pytest.mark.integration


class TestAgentDatabaseOperations:
    """Integration tests for Agent database operations."""

    @pytest.mark.asyncio
    async def test_create_agent(self, db_session, sample_agent_data):
        """Test creating an agent in the database."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        assert agent.id is not None
        assert agent.name == sample_agent_data["name"]
        assert agent.description == sample_agent_data["description"]
        assert agent.status == "active"
        assert agent.created_at is not None

    @pytest.mark.asyncio
    async def test_read_agent(self, db_session, sample_agent_data):
        """Test reading an agent from the database."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        result = await db_session.execute(
            select(Agent).where(Agent.id == agent.id)
        )
        fetched_agent = result.scalar_one()

        assert fetched_agent.id == agent.id
        assert fetched_agent.name == agent.name

    @pytest.mark.asyncio
    async def test_update_agent(self, db_session, sample_agent_data):
        """Test updating an agent in the database."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        agent.name = "Updated Agent Name"
        agent.status = "paused"
        await db_session.commit()
        await db_session.refresh(agent)

        result = await db_session.execute(
            select(Agent).where(Agent.id == agent.id)
        )
        updated_agent = result.scalar_one()

        assert updated_agent.name == "Updated Agent Name"
        assert updated_agent.status == "paused"

    @pytest.mark.asyncio
    async def test_delete_agent(self, db_session, sample_agent_data):
        """Test deleting an agent from the database."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        agent_id = agent.id
        await db_session.delete(agent)
        await db_session.commit()

        result = await db_session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        deleted_agent = result.scalar_one_or_none()

        assert deleted_agent is None

    @pytest.mark.asyncio
    async def test_list_agents_with_filter(self, db_session):
        """Test listing agents with status filter."""
        agents_data = [
            {"name": "Agent 1", "status": "active", "created_by": "user1"},
            {"name": "Agent 2", "status": "active", "created_by": "user1"},
            {"name": "Agent 3", "status": "paused", "created_by": "user2"},
        ]

        for data in agents_data:
            agent = Agent(**data)
            db_session.add(agent)
        await db_session.commit()

        result = await db_session.execute(
            select(Agent).where(Agent.status == "active")
        )
        active_agents = result.scalars().all()

        assert len(active_agents) == 2
        assert all(a.status == "active" for a in active_agents)

    @pytest.mark.asyncio
    async def test_list_agents_by_creator(self, db_session):
        """Test listing agents filtered by creator."""
        agents_data = [
            {"name": "Agent 1", "status": "active", "created_by": "user1"},
            {"name": "Agent 2", "status": "active", "created_by": "user1"},
            {"name": "Agent 3", "status": "active", "created_by": "user2"},
        ]

        for data in agents_data:
            agent = Agent(**data)
            db_session.add(agent)
        await db_session.commit()

        result = await db_session.execute(
            select(Agent).where(Agent.created_by == "user1")
        )
        user1_agents = result.scalars().all()

        assert len(user1_agents) == 2
        assert all(a.created_by == "user1" for a in user1_agents)


class TestTaskDatabaseOperations:
    """Integration tests for Task database operations."""

    @pytest.mark.asyncio
    async def test_create_task(self, db_session, sample_agent_data):
        """Test creating a task in the database."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        task = Task(
            agent_id=agent.id,
            status="pending",
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        assert task.id is not None
        assert task.agent_id == agent.id
        assert task.status == "pending"
        assert task.created_at is not None

    @pytest.mark.asyncio
    async def test_task_lifecycle(self, db_session, sample_agent_data):
        """Test task status transitions through lifecycle."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        task = Task(agent_id=agent.id, status="pending")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        task.status = "running"
        task.started_at = datetime.now(UTC)
        await db_session.commit()
        await db_session.refresh(task)

        assert task.status == "running"
        assert task.started_at is not None

        task.status = "completed"
        task.completed_at = datetime.now(UTC)
        task.result = '{"output": "success"}'
        await db_session.commit()
        await db_session.refresh(task)

        assert task.status == "completed"
        assert task.completed_at is not None
        assert task.result is not None

    @pytest.mark.asyncio
    async def test_task_failure_and_retry(self, db_session, sample_agent_data):
        """Test task failure and retry count."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        task = Task(agent_id=agent.id, status="pending")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        task.status = "failed"
        task.error = "Connection timeout"
        task.retry_count = 1
        await db_session.commit()
        await db_session.refresh(task)

        assert task.status == "failed"
        assert task.error == "Connection timeout"
        assert task.retry_count == 1

        task.status = "pending"
        task.retry_count = 2
        await db_session.commit()
        await db_session.refresh(task)

        assert task.status == "pending"
        assert task.retry_count == 2

    @pytest.mark.asyncio
    async def test_get_agent_tasks(self, db_session, sample_agent_data):
        """Test retrieving all tasks for an agent."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        task_statuses = ["completed", "completed", "failed", "pending"]
        for status in task_statuses:
            task = Task(agent_id=agent.id, status=status)
            db_session.add(task)
        await db_session.commit()

        result = await db_session.execute(
            select(Task).where(Task.agent_id == agent.id)
        )
        agent_tasks = result.scalars().all()

        assert len(agent_tasks) == 4

        result = await db_session.execute(
            select(Task).where(
                Task.agent_id == agent.id,
                Task.status == "completed"
            )
        )
        completed_tasks = result.scalars().all()

        assert len(completed_tasks) == 2


class TestAgentTaskRelationship:
    """Integration tests for Agent-Task relationship."""

    @pytest.mark.asyncio
    async def test_cascade_delete_tasks(self, db_session, sample_agent_data):
        """Test that deleting an agent cascades to tasks."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        agent_id = agent.id

        for _ in range(3):
            task = Task(agent_id=agent.id, status="completed")
            db_session.add(task)
        await db_session.commit()

        result = await db_session.execute(
            select(Task).where(Task.agent_id == agent_id)
        )
        tasks_before = result.scalars().all()
        assert len(tasks_before) == 3

        await db_session.delete(agent)
        await db_session.commit()

        result = await db_session.execute(
            select(Task).where(Task.agent_id == agent_id)
        )
        tasks_after = result.scalars().all()

        assert len(tasks_after) == 0

    @pytest.mark.asyncio
    async def test_multiple_agents_with_tasks(self, db_session):
        """Test multiple agents each with their own tasks."""
        agents = []
        for i in range(3):
            agent = Agent(name=f"Agent {i}", status="active")
            db_session.add(agent)
            agents.append(agent)
        await db_session.commit()

        for agent in agents:
            await db_session.refresh(agent)
            for _ in range(2):
                task = Task(agent_id=agent.id, status="pending")
                db_session.add(task)
        await db_session.commit()

        result = await db_session.execute(select(Task))
        all_tasks = result.scalars().all()

        assert len(all_tasks) == 6

        for agent in agents:
            result = await db_session.execute(
                select(Task).where(Task.agent_id == agent.id)
            )
            agent_tasks = result.scalars().all()
            assert len(agent_tasks) == 2


class TestDatabaseConstraints:
    """Integration tests for database constraints."""

    @pytest.mark.asyncio
    async def test_agent_name_not_null(self, db_session):
        """Test that agent name cannot be null."""
        agent = Agent(name=None, status="active")  # type: ignore
        db_session.add(agent)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_task_agent_id_foreign_key(self, db_session):
        """Test that task must reference valid agent."""
        task = Task(agent_id=99999, status="pending")
        db_session.add(task)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_agent_status_values(self, db_session):
        """Test valid agent status values."""
        valid_statuses = ["active", "paused", "error", "inactive"]

        for status in valid_statuses:
            agent = Agent(name=f"Agent {status}", status=status)
            db_session.add(agent)

        await db_session.commit()

        result = await db_session.execute(select(Agent))
        agents = result.scalars().all()

        assert len(agents) == 4


class TestDatabasePerformance:
    """Integration tests for database performance."""

    @pytest.mark.asyncio
    async def test_bulk_insert_agents(self, db_session):
        """Test bulk inserting many agents."""
        agents = [
            Agent(name=f"Bulk Agent {i}", status="active")
            for i in range(100)
        ]

        for agent in agents:
            db_session.add(agent)
        await db_session.commit()

        result = await db_session.execute(select(Agent))
        all_agents = result.scalars().all()

        assert len(all_agents) == 100

    @pytest.mark.asyncio
    async def test_bulk_insert_tasks(self, db_session, sample_agent_data):
        """Test bulk inserting many tasks for an agent."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        tasks = [
            Task(agent_id=agent.id, status="completed")
            for _ in range(100)
        ]

        for task in tasks:
            db_session.add(task)
        await db_session.commit()

        result = await db_session.execute(
            select(Task).where(Task.agent_id == agent.id)
        )
        all_tasks = result.scalars().all()

        assert len(all_tasks) == 100
