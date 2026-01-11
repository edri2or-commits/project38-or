"""Task API routes - Execution history and task management.

This module provides REST API endpoints for:
- Viewing task execution history
- Retrying failed tasks
- Getting task details
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.database import get_session
from src.harness.scheduler import TaskScheduler
from src.models.task import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/agents/{agent_id}/tasks")
async def get_agent_tasks(
    agent_id: int,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    """Get execution history for an agent.

    Args:
        agent_id: Database ID of agent
        status: Optional status filter (pending/running/completed/failed)
        limit: Maximum number of tasks to return (default: 100)
        offset: Pagination offset (default: 0)

    Returns:
        Dict with tasks list and pagination metadata

    Example:
        GET /tasks/agents/1/tasks?status=completed&limit=10
    """
    async for session in get_session():
        # Build query
        query = select(Task).where(Task.agent_id == agent_id)

        if status:
            query = query.where(Task.status == status)

        # Add ordering and pagination
        query = query.order_by(desc(Task.created_at)).offset(offset).limit(limit)

        # Execute
        result = await session.execute(query)
        tasks = result.scalars().all()

        # Get total count
        count_query = select(Task).where(Task.agent_id == agent_id)
        if status:
            count_query = count_query.where(Task.status == status)

        count_result = await session.execute(count_query)
        total_count = len(count_result.scalars().all())

        return {
            "tasks": [task.model_dump() for task in tasks],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }


@router.get("/{task_id}")
async def get_task(task_id: int) -> dict[str, Any]:
    """Get details for a specific task.

    Args:
        task_id: Database ID of task

    Returns:
        Task details

    Raises:
        HTTPException: 404 if task not found

    Example:
        GET /tasks/123
    """
    async for session in get_session():
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return task.model_dump()


@router.post("/{task_id}/retry")
async def retry_task(task_id: int) -> dict[str, Any]:
    """Retry a failed task.

    This endpoint schedules a retry for a failed task with exponential backoff.
    Maximum 3 retry attempts.

    Args:
        task_id: Database ID of task to retry

    Returns:
        Dict with retry status and scheduled time

    Raises:
        HTTPException: 404 if task not found
        HTTPException: 400 if task not failed or max retries exceeded

    Example:
        POST /tasks/123/retry
    """
    async for session in get_session():
        # Verify task exists and is failed
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if task.status != "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Task {task_id} is not failed (status: {task.status})",
            )

        # Initialize scheduler and retry
        scheduler = TaskScheduler()

        try:
            await scheduler.retry_failed_task(task_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {
            "message": f"Task {task_id} scheduled for retry",
            "retry_count": task.retry_count + 1,
            "max_retries": scheduler.retry_max_attempts,
        }
