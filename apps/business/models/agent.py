"""Agent model for database storage.

This module defines the Agent entity schema using SQLModel.
"""

from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class Agent(SQLModel, table=True):
    """Agent entity representing an autonomous AI agent.

    Agents are created from natural language descriptions and can execute
    tasks autonomously. Each agent has generated code, configuration, and
    execution history.

    Attributes:
        id: Unique identifier (auto-generated)
        name: Human-readable agent name
        description: Natural language description of agent's purpose
        code: Generated Python code for the agent
        status: Current agent status (active/paused/stopped/error)
        created_at: Timestamp when agent was created
        updated_at: Timestamp of last update
        created_by: User who created the agent (optional)
        config: JSON configuration (optional)
    """

    __tablename__ = "agents"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True)
    description: str = Field(max_length=2000)
    code: str = Field(sa_column=Column(Text))
    status: str = Field(default="active", max_length=50, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(default=None, max_length=255)
    config: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    class Config:
        """SQLModel configuration."""

        json_schema_extra = {
            "example": {
                "name": "Stock Monitor Agent",
                "description": "סוכן שעוקב אחרי מניות של טסלה ומתריע כאשר המחיר עולה ב-5%",
                "code": "# Generated agent code here",
                "status": "active",
                "config": '{"stocks": ["TSLA"], "threshold": 0.05}',
            }
        }
