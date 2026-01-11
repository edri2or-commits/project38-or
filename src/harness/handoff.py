"""Handoff Artifacts - State preservation between agent runs.

This module implements the Dual-Agent Pattern for long-running context:
- Initializer: Creates initial state
- Worker: Processes tasks with state
- Handoff: Compresses context after each run

Based on long-running agent harness patterns.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.database import get_session
from src.models.agent import Agent


@dataclass
class HandoffArtifact:
    """State artifact passed between agent runs.

    This artifact contains compressed context from previous runs,
    allowing agents to maintain long-running memory.

    Attributes:
        agent_id: Database ID of agent
        state: Serializable state dictionary
        summary: Human-readable summary of state
        created_at: When artifact was created
        run_count: Number of runs since initialization
    """

    agent_id: int
    state: dict[str, Any]
    summary: str
    created_at: datetime
    run_count: int


class HandoffManager:
    """Manage state persistence for long-running agents.

    This manager handles the Execute-Summarize-Reset loop:
    1. Load previous state from artifact
    2. Execute agent with state context
    3. Compress context into new artifact
    4. Store for next run

    Example:
        >>> manager = HandoffManager()
        >>> artifact = await manager.load_artifact(agent_id=1)
        >>> # ... execute agent with artifact.state ...
        >>> await manager.save_artifact(agent_id=1, new_state={"key": "value"})
    """

    def __init__(self):
        """Initialize handoff manager."""
        pass

    async def load_artifact(self, agent_id: int) -> HandoffArtifact | None:
        """Load latest handoff artifact for agent.

        Args:
            agent_id: Database ID of agent

        Returns:
            HandoffArtifact if exists, None if first run

        Raises:
            ValueError: If agent not found
        """
        async for session in get_session():
            # Verify agent exists
            result = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()

            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            # Load state from agent.config JSON
            if not agent.config:
                return None  # First run, no artifact

            try:
                config = json.loads(agent.config)
                handoff_data = config.get("handoff_artifact")

                if not handoff_data:
                    return None

                return HandoffArtifact(
                    agent_id=agent_id,
                    state=handoff_data.get("state", {}),
                    summary=handoff_data.get("summary", ""),
                    created_at=datetime.fromisoformat(
                        handoff_data.get("created_at", datetime.utcnow().isoformat())
                    ),
                    run_count=handoff_data.get("run_count", 0),
                )

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # Invalid artifact, return None
                return None

    async def save_artifact(
        self,
        agent_id: int,
        state: dict[str, Any],
        summary: str = "",
    ) -> HandoffArtifact:
        """Save handoff artifact for agent.

        Args:
            agent_id: Database ID of agent
            state: State dictionary to preserve
            summary: Human-readable summary of state

        Returns:
            Created HandoffArtifact

        Raises:
            ValueError: If agent not found
        """
        async for session in get_session():
            # Load agent
            result = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()

            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            # Load existing config or create new
            if agent.config:
                try:
                    config = json.loads(agent.config)
                except json.JSONDecodeError:
                    config = {}
            else:
                config = {}

            # Get previous run count
            prev_run_count = 0
            if "handoff_artifact" in config:
                prev_run_count = config["handoff_artifact"].get("run_count", 0)

            # Create new artifact
            artifact = HandoffArtifact(
                agent_id=agent_id,
                state=state,
                summary=summary,
                created_at=datetime.utcnow(),
                run_count=prev_run_count + 1,
            )

            # Update agent config with artifact
            config["handoff_artifact"] = {
                "state": artifact.state,
                "summary": artifact.summary,
                "created_at": artifact.created_at.isoformat(),
                "run_count": artifact.run_count,
            }

            agent.config = json.dumps(config)
            agent.updated_at = datetime.utcnow()

            session.add(agent)
            await session.commit()

            return artifact

    async def clear_artifact(self, agent_id: int) -> None:
        """Clear handoff artifact for agent (reset state).

        Args:
            agent_id: Database ID of agent

        Raises:
            ValueError: If agent not found
        """
        async for session in get_session():
            # Load agent
            result = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()

            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            # Load existing config
            if agent.config:
                try:
                    config = json.loads(agent.config)
                except json.JSONDecodeError:
                    config = {}
            else:
                config = {}

            # Remove handoff artifact
            if "handoff_artifact" in config:
                del config["handoff_artifact"]

            agent.config = json.dumps(config) if config else None
            agent.updated_at = datetime.utcnow()

            session.add(agent)
            await session.commit()

    async def compress_context(
        self,
        agent_id: int,
        raw_output: str,
        previous_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Compress execution output into compact state.

        This uses a simple compression strategy:
        - Keep only essential keys from previous state
        - Extract key facts from output
        - Limit state size to prevent growth

        In production, this could use Claude to intelligently
        summarize context.

        Args:
            agent_id: Database ID of agent
            raw_output: Raw execution output
            previous_state: State from previous run

        Returns:
            Compressed state dictionary
        """
        # Simple compression: truncate output and preserve state keys
        compressed = {
            "previous_output": raw_output[:500],  # Keep first 500 chars
            "run_count": previous_state.get("run_count", 0) + 1,
            "last_run": datetime.utcnow().isoformat(),
        }

        # Preserve specific keys if they exist
        for key in ["important_data", "counters", "alerts"]:
            if key in previous_state:
                compressed[key] = previous_state[key]

        return compressed
