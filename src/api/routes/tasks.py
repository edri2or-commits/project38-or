"""Task management API endpoints.

This module provides REST API endpoints for managing agent execution tasks,
viewing execution history, and manually triggering agent runs.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.database import get_session
from src.harness.scheduler import get_scheduler
from src.models.task import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskResponse(BaseModel):
    """Task response model.

    Attributes:
        id: Task ID
        agent_id: Agent ID
        status: Task status (pending/running/completed/failed)
        scheduled_at: When task was scheduled
        started_at: When execution started
        completed_at: When execution completed
        result: Execution output
        error: Error message if failed
        retry_count: Number of retry attempts
        created_at: When task was created
    """

    id: int
    agent_id: int
    status: str
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: str | None
    error: str | None
    retry_count: int
    created_at: datetime


class TaskExecuteRequest(BaseModel):
    """Request to manually execute an agent.

    Attributes:
        agent_id: ID of the agent to execute
    """

    agent_id: int


class TaskExecuteResponse(BaseModel):
    """Response from manual agent execution.

    Attributes:
        status: Execution status
        result: Output from agent
        error: Error message if failed
        duration: Execution time in seconds
        task_id: Created task ID
    """

    status: str
    result: str
    error: str
    duration: float
    task_id: int | None = None


@router.get(
    "/",
    response_model=list[TaskResponse],
    summary="List all tasks",
    description="Get a list of all agent execution tasks with optional filtering",
)
async def list_tasks(
    agent_id: int | None = Query(None, description="Filter by agent ID"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
):
    """List all tasks with optional filtering.

    Args:
        agent_id: Optional filter by agent ID
        status: Optional filter by status (pending/running/completed/failed)
        limit: Maximum number of results (1-1000)
        offset: Offset for pagination
        session: Database session

    Returns:
        List of tasks
    """
    # Build query
    statement = select(Task)

    if agent_id is not None:
        statement = statement.where(Task.agent_id == agent_id)

    if status is not None:
        statement = statement.where(Task.status == status)

    statement = (
        statement.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    )

    # Execute query
    result = await session.exec(statement)
    tasks = result.all()

    return [TaskResponse.model_validate(task) for task in tasks]


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task details",
    description="Get detailed information about a specific task",
)
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get details of a specific task.

    Args:
        task_id: Task ID
        session: Database session

    Returns:
        Task details

    Raises:
        HTTPException: 404 if task not found
    """
    statement = select(Task).where(Task.id == task_id)
    result = await session.exec(statement)
    task = result.first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskResponse.model_validate(task)


@router.post(
    "/execute",
    response_model=TaskExecuteResponse,
    summary="Execute agent manually",
    description="Trigger immediate execution of an agent (bypasses schedule)",
)
async def execute_agent(
    request: TaskExecuteRequest,
    session: AsyncSession = Depends(get_session),
):
    """Execute an agent immediately.

    This bypasses the schedule and runs the agent right now.
    Uses distributed locking to prevent conflicts.

    Args:
        request: Execution request with agent_id
        session: Database session

    Returns:
        Execution result

    Raises:
        HTTPException: 404 if agent not found, 500 if execution fails
    """
    scheduler = await get_scheduler()

    try:
        result = await scheduler.execute_now(request.agent_id)

        # If execution was skipped, find the running task
        task_id = None
        if result["status"] == "skipped":
            statement = (
                select(Task)
                .where(Task.agent_id == request.agent_id)
                .where(Task.status == "running")
                .order_by(Task.started_at.desc())
                .limit(1)
            )
            task_result = await session.exec(statement)
            task = task_result.first()
            if task:
                task_id = task.id
        else:
            # Find the task we just created
            statement = (
                select(Task)
                .where(Task.agent_id == request.agent_id)
                .order_by(Task.created_at.desc())
                .limit(1)
            )
            task_result = await session.exec(statement)
            task = task_result.first()
            if task:
                task_id = task.id

        return TaskExecuteResponse(
            status=result["status"],
            result=result.get("result", ""),
            error=result.get("error", ""),
            duration=result.get("duration", 0),
            task_id=task_id,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get(
    "/agents/{agent_id}/tasks",
    response_model=list[TaskResponse],
    summary="Get agent task history",
    description="Get execution history for a specific agent",
)
async def get_agent_tasks(
    agent_id: int,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    session: AsyncSession = Depends(get_session),
):
    """Get task execution history for an agent.

    Args:
        agent_id: Agent ID
        limit: Maximum number of results (1-500)
        session: Database session

    Returns:
        List of tasks for the agent
    """
    statement = (
        select(Task)
        .where(Task.agent_id == agent_id)
        .order_by(Task.created_at.desc())
        .limit(limit)
    )

    result = await session.exec(statement)
    tasks = result.all()

    return [TaskResponse.model_validate(task) for task in tasks]
