"""Task Management API Routes.

Provides endpoints for viewing and managing agent execution tasks.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.api.database import get_session
from src.harness.scheduler import execute_scheduled_task
from src.models.task import Task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Get specific task by ID.

    Args:
        task_id: Task ID to retrieve
        session: Database session (injected)

    Returns:
        Task model instance

    Raises:
        HTTPException: 404 if task not found

    Example:
        GET /tasks/123
        Response: {"id": 123, "agent_id": 1, "status": "completed", ...}
    """
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return task


@router.get("/agent/{agent_id}", response_model=list[Task])
async def get_agent_tasks(
    agent_id: int,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    """Get execution history for specific agent.

    Lists tasks ordered by created_at descending (most recent first).

    Args:
        agent_id: Agent ID to get tasks for
        limit: Maximum number of tasks to return (default: 50, max: 100)
        offset: Number of tasks to skip (default: 0)
        session: Database session (injected)

    Returns:
        List of Task model instances

    Example:
        GET /tasks/agent/1?limit=10
        Response: [{"id": 123, "status": "completed", ...}, ...]
    """
    # Validate limit
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    # Query tasks
    result = await session.execute(
        select(Task)
        .where(Task.agent_id == agent_id)
        .order_by(Task.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    tasks = result.scalars().all()

    return list(tasks)


@router.post("/{task_id}/retry", response_model=Task, status_code=status.HTTP_201_CREATED)
async def retry_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Retry a failed task.

    Creates a new task with the same agent_id and executes it immediately.
    The original task is not modified.

    Args:
        task_id: Task ID to retry
        session: Database session (injected)

    Returns:
        Newly created Task instance

    Raises:
        HTTPException: 404 if task not found, 400 if task not failed

    Example:
        POST /tasks/123/retry
        Response: {"id": 124, "agent_id": 1, "status": "pending", ...}
    """
    # Load original task
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    original_task = result.scalar_one_or_none()

    if not original_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if original_task.status not in ["failed", "timeout"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry task with status '{original_task.status}'",
        )

    # Create new task
    new_task = Task(
        agent_id=original_task.agent_id,
        status="pending",
        scheduled_at=datetime.now(timezone.utc),
        retry_count=original_task.retry_count + 1,
    )
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task)

    logger.info(
        "Created retry task %d for original task %d (agent %d)",
        new_task.id,
        task_id,
        original_task.agent_id,
    )

    # Execute immediately in background
    # Note: In production, use asyncio.create_task() or background task queue
    try:
        await execute_scheduled_task(original_task.agent_id, session)
        logger.info("Retry task %d executed successfully", new_task.id)
    except Exception as e:
        logger.error("Failed to execute retry task %d: %s", new_task.id, e)
        new_task.status = "failed"
        new_task.error = str(e)
        await session.commit()

    # Refresh to get updated status
    await session.refresh(new_task)

    return new_task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a task.

    Permanently deletes task from database. Cannot be undone.

    Args:
        task_id: Task ID to delete
        session: Database session (injected)

    Raises:
        HTTPException: 404 if task not found, 400 if task is running

    Example:
        DELETE /tasks/123
        Response: 204 No Content
    """
    # Load task
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if task.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete running task",
        )

    # Delete task
    await session.delete(task)
    await session.commit()

    logger.info("Deleted task %d", task_id)


@router.get("/stats/summary")
async def get_task_stats(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get task execution statistics.

    Returns aggregate statistics across all tasks.

    Args:
        session: Database session (injected)

    Returns:
        Dict with total, completed, failed, running counts

    Example:
        GET /tasks/stats/summary
        Response: {"total": 100, "completed": 85, "failed": 10, "running": 5}
    """
    # Get all tasks
    result = await session.execute(select(Task))
    tasks = result.scalars().all()

    # Calculate stats
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    failed = sum(1 for t in tasks if t.status == "failed")
    running = sum(1 for t in tasks if t.status == "running")
    pending = sum(1 for t in tasks if t.status == "pending")

    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "running": running,
        "pending": pending,
        "success_rate": (completed / total * 100) if total > 0 else 0.0,
    }
