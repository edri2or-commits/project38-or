"""Handoff Artifacts - State preservation between agent runs.

Implements state persistence and context handoff to enable long-running
agents that maintain memory across multiple executions.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HandoffArtifact:
    """Container for state passed between agent executions.

    Preserves context, intermediate results, and metadata across runs
    to enable long-running agents with memory.

    Attributes:
        agent_id: ID of the agent this artifact belongs to
        run_number: Sequential execution count
        state: Arbitrary state data (JSON-serializable dict)
        metadata: Execution metadata (timestamps, durations, etc.)
        created_at: Timestamp of artifact creation
        compressed: Whether state has been compressed
        summary: Human-readable summary of this run (optional)
    """

    agent_id: int
    run_number: int = 1
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    compressed: bool = False
    summary: str = ""

    def to_dict(self) -> dict:
        """Serialize artifact to dictionary.

        Returns:
            Dictionary representation for JSON storage

        Example:
            >>> artifact = HandoffArtifact(agent_id=1, state={'count': 5})
            >>> data = artifact.to_dict()
            >>> print(data['state']['count'])
            5
        """
        return {
            "agent_id": self.agent_id,
            "run_number": self.run_number,
            "state": self.state,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "compressed": self.compressed,
            "summary": self.summary,
        }

    def to_json(self) -> str:
        """Serialize artifact to JSON string.

        Returns:
            JSON string representation

        Example:
            >>> artifact = HandoffArtifact(agent_id=1)
            >>> json_str = artifact.to_json()
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "HandoffArtifact":
        """Deserialize artifact from dictionary.

        Args:
            data: Dictionary from to_dict() output

        Returns:
            HandoffArtifact instance

        Example:
            >>> data = {'agent_id': 1, 'run_number': 2, 'state': {}}
            >>> artifact = HandoffArtifact.from_dict(data)
        """
        # Parse datetime if string
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            agent_id=data["agent_id"],
            run_number=data.get("run_number", 1),
            state=data.get("state", {}),
            metadata=data.get("metadata", {}),
            created_at=created_at or datetime.now(UTC),
            compressed=data.get("compressed", False),
            summary=data.get("summary", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "HandoffArtifact":
        """Deserialize artifact from JSON string.

        Args:
            json_str: JSON string from to_json()

        Returns:
            HandoffArtifact instance

        Raises:
            json.JSONDecodeError: If JSON is invalid

        Example:
            >>> json_str = '{"agent_id": 1, "state": {}}'
            >>> artifact = HandoffArtifact.from_json(json_str)
        """
        data = json.loads(json_str)
        return cls.from_dict(data)


class HandoffManager:
    """Manages handoff artifacts for agent state persistence.

    Coordinates state preservation between agent executions, enabling
    long-running agents to maintain context across multiple runs.
    """

    def __init__(self):
        """Initialize handoff manager.

        Example:
            >>> manager = HandoffManager()
            >>> await manager.save_artifact(artifact)
        """
        self._artifacts: dict[int, HandoffArtifact] = {}
        logger.info("HandoffManager initialized")

    async def save_artifact(
        self,
        artifact: HandoffArtifact,
    ) -> None:
        """Save handoff artifact for agent.

        Stores artifact in memory. In production, this should persist
        to database (agent.config JSON field or separate table).

        Args:
            artifact: HandoffArtifact to save

        Example:
            >>> artifact = HandoffArtifact(agent_id=1, state={'count': 10})
            >>> await manager.save_artifact(artifact)
        """
        self._artifacts[artifact.agent_id] = artifact
        logger.info(
            "Saved handoff artifact for agent %d (run %d)",
            artifact.agent_id,
            artifact.run_number,
        )

    async def load_artifact(
        self,
        agent_id: int,
    ) -> HandoffArtifact | None:
        """Load previous handoff artifact for agent.

        Args:
            agent_id: ID of agent to load artifact for

        Returns:
            Previous HandoffArtifact or None if no previous run

        Example:
            >>> artifact = await manager.load_artifact(agent_id=1)
            >>> if artifact:
            ...     print(artifact.state)
        """
        artifact = self._artifacts.get(agent_id)

        if artifact:
            logger.info(
                "Loaded handoff artifact for agent %d (run %d)",
                agent_id,
                artifact.run_number,
            )
        else:
            logger.info(
                "No previous handoff artifact for agent %d",
                agent_id,
            )

        return artifact

    async def create_next_artifact(
        self,
        agent_id: int,
        result: dict,
        execution_metadata: dict | None = None,
    ) -> HandoffArtifact:
        """Create handoff artifact for next run based on current results.

        Loads previous artifact, increments run number, preserves relevant
        state, and adds new results.

        Args:
            agent_id: ID of agent
            result: Results from current execution
            execution_metadata: Optional metadata (duration, status, etc.)

        Returns:
            New HandoffArtifact for next run

        Example:
            >>> result = {'data': [1, 2, 3], 'processed': 3}
            >>> artifact = await manager.create_next_artifact(1, result)
            >>> print(artifact.run_number)
            2
        """
        # Load previous artifact
        previous = await self.load_artifact(agent_id)

        # Determine run number
        run_number = 1
        previous_state = {}
        if previous:
            run_number = previous.run_number + 1
            previous_state = previous.state.copy()

        # Create new artifact
        artifact = HandoffArtifact(
            agent_id=agent_id,
            run_number=run_number,
            state={
                "previous_run": previous_state,
                "current_result": result,
                "cumulative_data": previous_state.get("cumulative_data", []),
            },
            metadata=execution_metadata or {},
        )

        # Auto-save
        await self.save_artifact(artifact)

        logger.info(
            "Created handoff artifact for agent %d (run %d)",
            agent_id,
            run_number,
        )

        return artifact

    async def clear_artifact(self, agent_id: int) -> None:
        """Clear handoff artifact for agent.

        Useful for resetting agent state or cleaning up after deletion.

        Args:
            agent_id: ID of agent to clear

        Example:
            >>> await manager.clear_artifact(agent_id=1)
        """
        if agent_id in self._artifacts:
            del self._artifacts[agent_id]
            logger.info("Cleared handoff artifact for agent %d", agent_id)

    def compress_state(
        self,
        state: dict,
        max_size: int = 10000,
    ) -> dict:
        """Compress state by removing old or large data.

        Simple compression that keeps only recent/essential data.
        In production, this could use LLM summarization.

        Args:
            state: State dictionary to compress
            max_size: Maximum estimated size in characters

        Returns:
            Compressed state dictionary

        Example:
            >>> large_state = {'logs': ['entry'] * 10000}
            >>> compressed = manager.compress_state(large_state)
            >>> print(len(compressed['logs']))
            100
        """
        # Estimate size
        size_estimate = len(json.dumps(state))

        if size_estimate <= max_size:
            return state

        logger.info(
            "Compressing state (size: %d -> target: %d)",
            size_estimate,
            max_size,
        )

        compressed = {}

        # Keep only essential keys
        essential_keys = ["status", "error", "count", "last_value"]
        for key in essential_keys:
            if key in state:
                compressed[key] = state[key]

        # Truncate lists
        for key, value in state.items():
            if isinstance(value, list) and len(value) > 100:
                compressed[key] = value[-100:]  # Keep last 100 items
                logger.debug("Truncated %s from %d to 100 items", key, len(value))
            elif key not in compressed:
                compressed[key] = value

        compressed["_compressed"] = True
        compressed["_original_size"] = size_estimate

        return compressed


# Global handoff manager instance
_global_manager: HandoffManager | None = None


def get_handoff_manager() -> HandoffManager:
    """Get global HandoffManager singleton.

    Returns:
        Global HandoffManager instance

    Example:
        >>> manager = get_handoff_manager()
        >>> artifact = await manager.load_artifact(1)
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = HandoffManager()
    return _global_manager
