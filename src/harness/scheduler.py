"""Task Scheduler - Orchestrates 24/7 agent execution.

Uses APScheduler with PostgreSQL Advisory Locks to ensure idempotent
task execution across multiple replicas.
"""

import json
import logging
import zlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.agent import Agent
from src.models.task import Task

from .executor import execute_agent_code

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Raised when scheduler operations fail."""

    pass


@asynccontextmanager
async def advisory_lock(
    session: AsyncSession,
    lock_name: str,
) -> AsyncGenerator[bool, None]:
    """Acquire PostgreSQL advisory lock to prevent duplicate execution.

    Advisory locks are database-level mutexes that prevent multiple
    processes from executing the same task concurrently. This is critical
    for Railway deployments where multiple replicas might run simultaneously.

    Args:
        session: AsyncSession for database connection
        lock_name: Unique identifier for the lock (e.g., "task_123")

    Yields:
        True if lock was acquired, False otherwise

    Example:
        >>> async with advisory_lock(session, "task_security_scan") as acquired:
        ...     if acquired:
        ...         print("Got the lock, executing task")
        ...     else:
        ...         print("Another process is running this task")
    """
    # Generate consistent 64-bit integer from lock name
    lock_id = zlib.crc32(lock_name.encode("utf-8"))

    # Try to acquire lock (non-blocking)
    result = await session.execute(
        text("SELECT pg_try_advisory_lock(:lock_id)"),
        {"lock_id": lock_id},
    )
    acquired = result.scalar()

    try:
        yield acquired
    finally:
        if acquired:
            # Release lock
            await session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": lock_id},
            )


async def execute_scheduled_task(
    agent_id: int,
    session: AsyncSession,
) -> None:
    """Execute a scheduled agent task with idempotency protection.

    Loads agent from database, acquires advisory lock, creates Task record,
    executes agent code, and updates task with results.

    Args:
        agent_id: ID of the agent to execute
        session: Database session

    Raises:
        SchedulerError: If agent not found or execution fails critically

    Example:
        >>> await execute_scheduled_task(agent_id=1, session=db_session)
    """
    lock_name = f"agent_execution_{agent_id}"

    async with advisory_lock(session, lock_name) as acquired:
        if not acquired:
            logger.info(
                "Agent %d already running in another process, skipping",
                agent_id,
            )
            return

        logger.info("Acquired lock for agent %d, starting execution", agent_id)

        # Load agent from database
        result = await session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise SchedulerError(f"Agent {agent_id} not found in database")

        if agent.status != "active":
            logger.info(
                "Agent %d is not active (status: %s), skipping",
                agent_id,
                agent.status,
            )
            return

        # Parse config
        config = {}
        if agent.config:
            try:
                config = json.loads(agent.config)
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse agent config: %s", e)

        # Create Task record
        task = Task(
            agent_id=agent.id,
            status="running",
            scheduled_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        logger.info(
            "Created task %d for agent %d (%s)",
            task.id,
            agent.id,
            agent.name,
        )

        try:
            # Execute agent code
            result = await execute_agent_code(
                agent_code=agent.code,
                config=config,
                timeout=config.get("timeout", 300),  # Default 5min
            )

            # Update task with results
            task.completed_at = datetime.now(UTC)

            if result.status == "success":
                task.status = "completed"
                task.result = json.dumps(result.result)
                logger.info("Task %d completed successfully", task.id)

            elif result.status == "timeout":
                task.status = "failed"
                task.error = result.error
                logger.error("Task %d timed out: %s", task.id, result.error)

            else:  # error
                task.status = "failed"
                task.error = result.error
                logger.error("Task %d failed: %s", task.id, result.error)

                # Check if retry is needed
                max_retries = config.get("max_retries", 3)
                if task.retry_count < max_retries:
                    # Schedule retry with exponential backoff
                    task.retry_count += 1
                    retry_delay = 2 ** task.retry_count  # 2, 4, 8 seconds
                    logger.info(
                        "Scheduling retry %d/%d in %ds",
                        task.retry_count,
                        max_retries,
                        retry_delay,
                    )
                    # TODO: Schedule retry using APScheduler.add_job()

            await session.commit()

        except Exception as execution_error:
            # Catch unexpected errors
            logger.exception("Unexpected error during task execution")
            task.status = "failed"
            task.error = f"Unexpected error: {execution_error}"
            task.completed_at = datetime.now(UTC)
            await session.commit()


class AgentScheduler:
    """24/7 orchestration of agent execution.

    Manages scheduled execution of agents using APScheduler. Loads agent
    schedules from database and ensures idempotent execution using
    PostgreSQL advisory locks.

    Attributes:
        scheduler: APScheduler AsyncIOScheduler instance
        session: Database session factory
        running: Whether scheduler is currently running
    """

    def __init__(self, session_factory):
        """Initialize scheduler.

        Args:
            session_factory: Callable that returns AsyncSession
        """
        self.scheduler = AsyncIOScheduler()
        self.session_factory = session_factory
        self.running = False

    async def start(self) -> None:
        """Start the scheduler and load agent schedules.

        Loads all active agents from database and schedules their
        execution based on cron expressions in config.

        Raises:
            SchedulerError: If scheduler is already running

        Example:
            >>> scheduler = AgentScheduler(get_session)
            >>> await scheduler.start()
        """
        if self.running:
            raise SchedulerError("Scheduler is already running")

        logger.info("Starting AgentScheduler")

        # Load agents and create schedules
        async with self.session_factory() as session:
            result = await session.execute(
                select(Agent).where(Agent.status == "active")
            )
            agents = result.scalars().all()

            for agent in agents:
                await self._schedule_agent(agent)

        # Start APScheduler
        self.scheduler.start()
        self.running = True

        logger.info(
            "AgentScheduler started with %d scheduled agents",
            len(self.scheduler.get_jobs()),
        )

    async def stop(self) -> None:
        """Stop the scheduler and cancel all jobs.

        Example:
            >>> await scheduler.stop()
        """
        if not self.running:
            return

        logger.info("Stopping AgentScheduler")
        self.scheduler.shutdown(wait=True)
        self.running = False
        logger.info("AgentScheduler stopped")

    async def _schedule_agent(self, agent: Agent) -> None:
        """Add agent to scheduler based on config.

        Parses agent.config JSON for schedule settings and creates
        APScheduler job with cron trigger.

        Args:
            agent: Agent model instance

        Example config:
            {
                "schedule": "0 */6 * * *",  # Every 6 hours
                "timeout": 300,
                "max_retries": 3
            }
        """
        if not agent.config:
            logger.warning("Agent %d has no config, skipping schedule", agent.id)
            return

        try:
            config = json.loads(agent.config)
            schedule = config.get("schedule")

            if not schedule:
                logger.info(
                    "Agent %d has no schedule configured, skipping",
                    agent.id,
                )
                return

            # Parse cron expression
            # Format: "minute hour day month day_of_week"
            parts = schedule.split()
            if len(parts) != 5:
                logger.error(
                    "Invalid cron schedule for agent %d: %s",
                    agent.id,
                    schedule,
                )
                return

            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )

            # Add job to scheduler
            self.scheduler.add_job(
                func=self._execute_agent_wrapper,
                trigger=trigger,
                args=[agent.id],
                id=f"agent_{agent.id}",
                name=f"Agent: {agent.name}",
                replace_existing=True,
            )

            logger.info(
                "Scheduled agent %d (%s) with cron: %s",
                agent.id,
                agent.name,
                schedule,
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse config for agent %d: %s", agent.id, e)
        except Exception:
            logger.exception("Failed to schedule agent %d", agent.id)

    async def _execute_agent_wrapper(self, agent_id: int) -> None:
        """Wrapper to execute agent with database session.

        APScheduler jobs must be async functions, so this wrapper
        creates a database session and calls execute_scheduled_task.

        Args:
            agent_id: ID of agent to execute
        """
        async with self.session_factory() as session:
            try:
                await execute_scheduled_task(agent_id, session)
            except Exception:
                logger.exception("Failed to execute agent %d", agent_id)

    async def add_agent(self, agent: Agent) -> None:
        """Dynamically add agent to scheduler without restart.

        Args:
            agent: Agent model instance to schedule

        Example:
            >>> await scheduler.add_agent(new_agent)
        """
        await self._schedule_agent(agent)
        logger.info("Dynamically added agent %d to scheduler", agent.id)

    async def remove_agent(self, agent_id: int) -> None:
        """Remove agent from scheduler.

        Args:
            agent_id: ID of agent to remove

        Example:
            >>> await scheduler.remove_agent(1)
        """
        job_id = f"agent_{agent_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info("Removed agent %d from scheduler", agent_id)
        else:
            logger.warning("Agent %d not found in scheduler", agent_id)
