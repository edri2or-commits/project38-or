"""Handoff Artifacts for long-running agent context preservation.

This module implements the Dual-Agent Pattern for maintaining state
across multiple agent executions. Context from previous runs is preserved
and made available to future runs, enabling long-running autonomous behavior.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class HandoffArtifact(SQLModel, table=True):
    """Handoff artifact for preserving context between agent runs.

    Each artifact represents a snapshot of agent state at the end of
    an execution. The next execution can load this state to maintain
    continuity across runs.

    Attributes:
        id: Unique identifier
        agent_id: Foreign key to agents table
        task_id: Task that created this artifact
        context_data: JSON-serialized context (observations, decisions, state)
        summary: Human-readable summary of what happened
        created_at: When this artifact was created
        expires_at: Optional expiration (for cleanup)
    """

    __tablename__ = "handoff_artifacts"

    id: int | None = Field(default=None, primary_key=True)
    agent_id: int = Field(foreign_key="agents.id", index=True)
    task_id: int = Field(foreign_key="tasks.id", index=True)
    context_data: str  # JSON - SQLModel will use TEXT type automatically
    summary: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    expires_at: datetime | None = Field(default=None, index=True)

    class Config:
        """SQLModel configuration."""

        json_schema_extra = {
            "example": {
                "agent_id": 1,
                "task_id": 123,
                "context_data": '{"last_price": 850.0, "alert_sent": false}',
                "summary": "Monitored TSLA price: $850.00, no alerts triggered",
                "expires_at": "2026-02-11T00:00:00Z",
            }
        }


@dataclass
class HandoffContext:
    """Context data structure for agent handoff.

    Attributes:
        observations: What the agent observed in this run
        actions: What actions the agent took
        state: Current state variables to preserve
        metadata: Additional metadata (run count, errors, etc.)
    """

    observations: dict
    actions: list[dict]
    state: dict
    metadata: dict

    def to_json(self) -> str:
        """Serialize context to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(
            {
                "observations": self.observations,
                "actions": self.actions,
                "state": self.state,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "HandoffContext":
        """Deserialize context from JSON string.

        Args:
            json_str: JSON string to parse

        Returns:
            HandoffContext instance
        """
        data = json.loads(json_str)
        return cls(
            observations=data.get("observations", {}),
            actions=data.get("actions", []),
            state=data.get("state", {}),
            metadata=data.get("metadata", {}),
        )


class HandoffManager:
    """Manages handoff artifacts for agent context preservation.

    Provides methods to save and load context between agent executions,
    enabling long-running autonomous behavior with memory.
    """

    async def save_handoff(
        self,
        agent_id: int,
        task_id: int,
        context: HandoffContext,
        summary: str,
        session: AsyncSession,
        ttl_days: int = 30,
    ) -> HandoffArtifact:
        """Save a handoff artifact after agent execution.

        Args:
            agent_id: ID of the agent
            task_id: ID of the task that created this artifact
            context: Context data to preserve
            summary: Human-readable summary
            session: Database session
            ttl_days: Time-to-live in days (default: 30)

        Returns:
            Created HandoffArtifact

        Example:
            >>> manager = HandoffManager()
            >>> context = HandoffContext(
            ...     observations={"price": 850.0},
            ...     actions=[{"type": "monitor"}],
            ...     state={"last_check": "2026-01-11"},
            ...     metadata={"run_count": 1}
            ... )
            >>> artifact = await manager.save_handoff(
            ...     agent_id=1,
            ...     task_id=123,
            ...     context=context,
            ...     summary="Monitored stock price",
            ...     session=session
            ... )
        """
        expires_at = datetime.utcnow() + timedelta(days=ttl_days)

        artifact = HandoffArtifact(
            agent_id=agent_id,
            task_id=task_id,
            context_data=context.to_json(),
            summary=summary,
            expires_at=expires_at,
        )

        session.add(artifact)
        await session.commit()
        await session.refresh(artifact)

        logger.info(f"Saved handoff artifact {artifact.id} for agent {agent_id}")
        return artifact

    async def load_latest_handoff(
        self,
        agent_id: int,
        session: AsyncSession,
    ) -> Optional[HandoffContext]:
        """Load the most recent handoff artifact for an agent.

        Args:
            agent_id: ID of the agent
            session: Database session

        Returns:
            HandoffContext if found, None otherwise

        Example:
            >>> manager = HandoffManager()
            >>> context = await manager.load_latest_handoff(1, session)
            >>> if context:
            ...     print(f"Last state: {context.state}")
        """
        statement = (
            select(HandoffArtifact)
            .where(HandoffArtifact.agent_id == agent_id)
            .order_by(HandoffArtifact.created_at.desc())
            .limit(1)
        )

        result = await session.exec(statement)
        artifact = result.first()

        if not artifact:
            logger.info(f"No handoff artifact found for agent {agent_id}")
            return None

        try:
            context = HandoffContext.from_json(artifact.context_data)
            logger.info(f"Loaded handoff artifact {artifact.id} for agent {agent_id}")
            return context
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse handoff artifact {artifact.id}: {e}")
            return None

    async def load_handoff_history(
        self,
        agent_id: int,
        session: AsyncSession,
        limit: int = 10,
    ) -> list[tuple[HandoffArtifact, HandoffContext]]:
        """Load handoff history for an agent.

        Args:
            agent_id: ID of the agent
            session: Database session
            limit: Maximum number of artifacts to load (default: 10)

        Returns:
            List of (artifact, context) tuples, newest first

        Example:
            >>> manager = HandoffManager()
            >>> history = await manager.load_handoff_history(1, session, limit=5)
            >>> for artifact, context in history:
            ...     print(f"{artifact.created_at}: {artifact.summary}")
        """
        statement = (
            select(HandoffArtifact)
            .where(HandoffArtifact.agent_id == agent_id)
            .order_by(HandoffArtifact.created_at.desc())
            .limit(limit)
        )

        result = await session.exec(statement)
        artifacts = result.all()

        history = []
        for artifact in artifacts:
            try:
                context = HandoffContext.from_json(artifact.context_data)
                history.append((artifact, context))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse handoff artifact {artifact.id}: {e}")
                continue

        return history

    async def cleanup_expired(
        self,
        session: AsyncSession,
    ) -> int:
        """Delete expired handoff artifacts.

        Args:
            session: Database session

        Returns:
            Number of artifacts deleted

        Example:
            >>> manager = HandoffManager()
            >>> deleted = await manager.cleanup_expired(session)
            >>> print(f"Cleaned up {deleted} expired artifacts")
        """
        statement = select(HandoffArtifact).where(
            HandoffArtifact.expires_at <= datetime.utcnow()
        )

        result = await session.exec(statement)
        artifacts = result.all()

        count = len(artifacts)
        for artifact in artifacts:
            await session.delete(artifact)

        await session.commit()

        if count > 0:
            logger.info(f"Cleaned up {count} expired handoff artifacts")

        return count
