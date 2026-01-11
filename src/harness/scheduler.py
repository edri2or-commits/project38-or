"""Task Scheduler - Automatic agent execution scheduling.

This module provides cron-like scheduling for agents using APScheduler:
- Per-agent schedules stored in agent.config JSON
- Automatic retry with exponential backoff
- Concurrent execution limits
- Background task management
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.database import get_session
from src.harness.executor import AgentExecutor
from src.harness.handoff import HandoffManager
from src.models.agent import Agent
from src.models.task import Task

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Schedule and manage automatic agent execution.

    This scheduler uses APScheduler to trigger agent runs based on
    schedules defined in agent.config JSON.

    Schedule format in agent.config:
        {
            "schedule": {
                "type": "cron",  # or "interval"
                "cron": "0 * * * *",  # hourly (if type=cron)
                "interval_minutes": 60,  # (if type=interval)
                "enabled": true
            }
        }

    Example:
        >>> scheduler = TaskScheduler()
        >>> await scheduler.start()
        >>> await scheduler.add_agent_schedule(agent_id=1)
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        retry_max_attempts: int = 3,
    ):
        """Initialize task scheduler.

        Args:
            max_concurrent: Maximum concurrent agent executions
            retry_max_attempts: Maximum retry attempts for failed tasks
        """
        self.scheduler = AsyncIOScheduler()
        self.executor = AgentExecutor()
        self.handoff_manager = HandoffManager()
        self.max_concurrent = max_concurrent
        self.retry_max_attempts = retry_max_attempts
        self._running_count = 0

    async def start(self) -> None:
        """Start the scheduler.

        This loads all agents with schedules and starts the APScheduler.
        """
        logger.info("Starting task scheduler")
        self.scheduler.start()

        # Load all active agents with schedules
        await self._load_all_schedules()

        logger.info("Task scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        logger.info("Stopping task scheduler")
        self.scheduler.shutdown(wait=True)
        logger.info("Task scheduler stopped")

    async def add_agent_schedule(self, agent_id: int) -> None:
        """Add or update schedule for an agent.

        Args:
            agent_id: Database ID of agent

        Raises:
            ValueError: If agent not found or schedule invalid
        """
        async for session in get_session():
            # Load agent
            result = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()

            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            # Parse schedule from config
            schedule_config = self._parse_schedule_config(agent)

            if not schedule_config or not schedule_config.get("enabled"):
                logger.info(f"No enabled schedule for agent {agent_id}")
                return

            # Remove existing job if any
            job_id = f"agent_{agent_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            # Create trigger
            trigger = self._create_trigger(schedule_config)

            # Add job
            self.scheduler.add_job(
                self._execute_agent_job,
                trigger=trigger,
                id=job_id,
                args=[agent_id],
                name=f"Agent {agent.name}",
                replace_existing=True,
            )

            logger.info(f"Scheduled agent {agent_id} with config: {schedule_config}")

    async def remove_agent_schedule(self, agent_id: int) -> None:
        """Remove schedule for an agent.

        Args:
            agent_id: Database ID of agent
        """
        job_id = f"agent_{agent_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed schedule for agent {agent_id}")

    async def retry_failed_task(self, task_id: int) -> None:
        """Retry a failed task.

        Args:
            task_id: Database ID of task to retry

        Raises:
            ValueError: If task not found or not failed
        """
        async for session in get_session():
            # Load task
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                raise ValueError(f"Task {task_id} not found")

            if task.status != "failed":
                raise ValueError(f"Task {task_id} is not failed (status: {task.status})")

            if task.retry_count >= self.retry_max_attempts:
                raise ValueError(
                    f"Task {task_id} exceeded max retry attempts "
                    f"({task.retry_count}/{self.retry_max_attempts})"
                )

            # Increment retry count
            task.retry_count += 1
            task.status = "pending"
            await session.commit()

            # Schedule retry with exponential backoff
            delay_seconds = 2 ** task.retry_count  # 2, 4, 8 seconds
            self.scheduler.add_job(
                self._execute_agent_job,
                trigger="date",
                run_date=datetime.utcnow() + timedelta(seconds=delay_seconds),
                args=[task.agent_id],
                id=f"retry_task_{task_id}",
            )

            logger.info(
                f"Scheduled retry for task {task_id} in {delay_seconds} seconds "
                f"(attempt {task.retry_count}/{self.retry_max_attempts})"
            )

    async def _load_all_schedules(self) -> None:
        """Load schedules for all active agents."""
        async for session in get_session():
            result = await session.execute(
                select(Agent).where(Agent.status == "active")
            )
            agents = result.scalars().all()

            for agent in agents:
                try:
                    await self.add_agent_schedule(agent.id)
                except Exception as e:
                    logger.error(f"Failed to load schedule for agent {agent.id}: {e}")

    async def _execute_agent_job(self, agent_id: int) -> None:
        """Execute agent job (called by scheduler).

        Args:
            agent_id: Database ID of agent
        """
        # Check concurrent limit
        if self._running_count >= self.max_concurrent:
            logger.warning(
                f"Concurrent limit reached ({self._running_count}/{self.max_concurrent}), "
                f"skipping execution of agent {agent_id}"
            )
            return

        self._running_count += 1

        try:
            # Load handoff artifact
            artifact = await self.handoff_manager.load_artifact(agent_id)
            context = artifact.state if artifact else {}

            # Execute agent
            logger.info(f"Executing agent {agent_id} (run #{artifact.run_count if artifact else 1})")
            result = await self.executor.execute_agent(agent_id, context=context)

            # Save handoff artifact if successful
            if result.success:
                new_state = await self.handoff_manager.compress_context(
                    agent_id,
                    result.stdout,
                    context,
                )
                await self.handoff_manager.save_artifact(
                    agent_id,
                    state=new_state,
                    summary=result.stdout[:200],
                )

            logger.info(
                f"Agent {agent_id} execution {'succeeded' if result.success else 'failed'} "
                f"in {result.duration_seconds:.2f}s"
            )

        except Exception as e:
            logger.error(f"Error executing agent {agent_id}: {e}", exc_info=True)

        finally:
            self._running_count -= 1

    def _parse_schedule_config(self, agent: Agent) -> dict | None:
        """Parse schedule configuration from agent.config.

        Args:
            agent: Agent entity

        Returns:
            Schedule config dict or None if invalid
        """
        if not agent.config:
            return None

        try:
            config = json.loads(agent.config)
            return config.get("schedule")
        except json.JSONDecodeError:
            return None

    def _create_trigger(self, schedule_config: dict):
        """Create APScheduler trigger from schedule config.

        Args:
            schedule_config: Schedule configuration dict

        Returns:
            APScheduler trigger instance

        Raises:
            ValueError: If schedule type invalid
        """
        schedule_type = schedule_config.get("type", "interval")

        if schedule_type == "cron":
            # Cron syntax: "minute hour day month day_of_week"
            cron_expr = schedule_config.get("cron", "0 * * * *")  # Default: hourly
            parts = cron_expr.split()
            if len(parts) != 5:
                raise ValueError(f"Invalid cron expression: {cron_expr}")

            return CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )

        elif schedule_type == "interval":
            # Interval in minutes
            interval_minutes = schedule_config.get("interval_minutes", 60)
            return IntervalTrigger(minutes=interval_minutes)

        else:
            raise ValueError(f"Unknown schedule type: {schedule_type}")
