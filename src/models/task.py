"""
Task model for database storage.

This module defines the Task entity schema using SQLModel.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Task(SQLModel, table=True):
    """
    Task entity representing agent execution history and scheduled tasks.

    Each task represents a single execution or scheduled run of an agent.
    Tasks track execution status, results, and errors.

    Attributes:
        id: Unique identifier (auto-generated)
        agent_id: Foreign key to agents table
        status: Current task status (pending/running/completed/failed)
        scheduled_at: When the task should execute
        started_at: When execution began (optional)
        completed_at: When execution finished (optional)
        result: Execution result or output (optional)
        error: Error message if failed (optional)
        retry_count: Number of retry attempts
        created_at: Timestamp when task was created
    """

    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    agent_id: int = Field(foreign_key="agents.id", index=True)
    status: str = Field(default="pending", max_length=50, index=True)
    scheduled_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    result: Optional[str] = Field(default=None, sa_column_kwargs={"type_": "TEXT"})
    error: Optional[str] = Field(default=None, sa_column_kwargs={"type_": "TEXT"})
    retry_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """SQLModel configuration."""

        json_schema_extra = {
            "example": {
                "agent_id": 1,
                "status": "completed",
                "scheduled_at": "2026-01-11T18:00:00Z",
                "started_at": "2026-01-11T18:00:01Z",
                "completed_at": "2026-01-11T18:00:15Z",
                "result": "Stock price increased by 6.2%",
                "retry_count": 0,
            }
        }

