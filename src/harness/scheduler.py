"""Task scheduler with distributed locking for agent execution.

This module provides APScheduler integration with PostgreSQL Advisory Locks
to ensure tasks run exactly once even during rolling deployments.
"""

import json
import logging
import zlib
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.database import get_session
from src.harness.executor import execute_agent_by_id
from src.models.agent import Agent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def distributed_lock(session: AsyncSession, lock_name: str):
    """Acquire a distributed lock using PostgreSQL Advisory Locks.

    This prevents duplicate task execution during rolling deployments
    when multiple container instances might be running simultaneously.

    Args:
        session: Database session
        lock_name: Unique name for the lock (e.g., "agent_execute_123")

    Yields:
        bool: True if lock was acquired, False otherwise

    Example:
        >>> async with distributed_lock(session, "agent_1") as acquired:
        ...     if acquired:
        ...         print("Lock acquired, running task")
        ...     else:
        ...         print("Another instance is running this task")
    """
    # Generate consistent 64-bit integer from lock name
    lock_id = zlib.crc32(lock_name.encode("utf-8"))

    # Try to acquire lock (non-blocking)
    result = await session.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": lock_id})
    acquired = result.scalar() if result else False

    try:
        yield acquired
    finally:
        if acquired:
            await session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})


class AgentScheduler:
    """Schedules and manages periodic agent execution.

    Uses APScheduler with PostgreSQL Advisory Locks to ensure
    tasks run exactly once, even during rolling deployments.

    Attributes:
        scheduler: APScheduler instance
        running: Whether scheduler is currently running
    """

    def __init__(self):
        """Initialize the agent scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.running = False

    async def start(self):
        """Start the scheduler and load agent schedules from database."""
        if self.running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting agent scheduler")
        self.scheduler.start()
        self.running = True

        # Load and schedule all active agents
        await self.load_agent_schedules()

    async def stop(self):
        """Stop the scheduler gracefully."""
        if not self.running:
            return

        logger.info("Stopping agent scheduler")
        self.scheduler.shutdown(wait=True)
        self.running = False

    async def load_agent_schedules(self):
        """Load all active agents from database and schedule them.

        Reads agent.config JSON for schedule information.
        Expected config format:
            {
                "schedule": "0 * * * *",  # Cron expression
                "enabled": true
            }
        """
        async with get_session() as session:
            statement = select(Agent).where(Agent.status == "active")
            result = await session.exec(statement)
            agents = result.all()

            for agent in agents:
                if not agent.config:
                    continue

                try:
                    config = json.loads(agent.config)
                    schedule = config.get("schedule")
                    enabled = config.get("enabled", True)

                    if schedule and enabled:
                        await self.schedule_agent(agent.id, schedule)
                        logger.info(f"Scheduled agent {agent.id} ({agent.name}) with cron: {schedule}")

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON config for agent {agent.id}")
                except Exception as e:
                    logger.error(f"Failed to schedule agent {agent.id}: {e}")

    async def schedule_agent(
        self,
        agent_id: int,
        cron_expression: str,
        job_id: Optional[str] = None,
    ):
        """Schedule an agent to run on a cron schedule.

        Args:
            agent_id: ID of the agent to schedule
            cron_expression: Cron expression (e.g., "0 * * * *" for hourly)
            job_id: Optional job ID (defaults to "agent_{agent_id}")

        Example:
            >>> scheduler = AgentScheduler()
            >>> await scheduler.schedule_agent(1, "0 0 * * *")  # Daily at midnight
        """
        if not job_id:
            job_id = f"agent_{agent_id}"

        # Parse cron expression
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
        except ValueError as e:
            raise ValueError(f"Invalid cron expression '{cron_expression}': {e}")

        # Add job to scheduler
        self.scheduler.add_job(
            self._execute_agent_with_lock,
            trigger=trigger,
            id=job_id,
            args=[agent_id],
            replace_existing=True,
            max_instances=1,  # Prevent overlapping executions
        )

    async def unschedule_agent(self, agent_id: int):
        """Remove an agent from the schedule.

        Args:
            agent_id: ID of the agent to unschedule
        """
        job_id = f"agent_{agent_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Unscheduled agent {agent_id}")
        except Exception as e:
            logger.warning(f"Failed to unschedule agent {agent_id}: {e}")

    async def _execute_agent_with_lock(self, agent_id: int):
        """Execute an agent with distributed locking.

        This is the internal method called by APScheduler.
        It acquires a distributed lock before execution to prevent
        duplicate runs during rolling deployments.

        Args:
            agent_id: ID of the agent to execute
        """
        lock_name = f"agent_execute_{agent_id}"

        async with get_session() as session:
            async with distributed_lock(session, lock_name) as acquired:
                if not acquired:
                    logger.info(f"Agent {agent_id} already running in another instance, skipping")
                    return

                logger.info(f"Executing scheduled agent {agent_id}")

                try:
                    result = await execute_agent_by_id(agent_id, session)
                    logger.info(f"Agent {agent_id} completed: {result['status']}")

                    if result["status"] == "failed":
                        logger.error(f"Agent {agent_id} failed: {result.get('error')}")

                except Exception as e:
                    logger.exception(f"Unexpected error executing agent {agent_id}: {e}")

    async def execute_now(self, agent_id: int) -> dict[str, str]:
        """Execute an agent immediately (manual trigger).

        This bypasses the schedule and executes the agent right away.
        Still uses distributed locking to prevent conflicts.

        Args:
            agent_id: ID of the agent to execute

        Returns:
            Execution result dictionary

        Example:
            >>> result = await scheduler.execute_now(1)
            >>> print(result["status"])
            completed
        """
        lock_name = f"agent_execute_{agent_id}"

        async with get_session() as session:
            async with distributed_lock(session, lock_name) as acquired:
                if not acquired:
                    return {
                        "status": "skipped",
                        "result": "",
                        "error": "Agent is already running in another instance",
                        "duration": 0,
                    }

                return await execute_agent_by_id(agent_id, session)


# Global scheduler instance
_scheduler: Optional[AgentScheduler] = None


async def get_scheduler() -> AgentScheduler:
    """Get or create the global scheduler instance.

    Returns:
        AgentScheduler: The global scheduler instance

    Example:
        >>> scheduler = await get_scheduler()
        >>> await scheduler.start()
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler
