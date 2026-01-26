"""State Machine for Deployment Lifecycle Management.

Implements a finite state machine for managing Railway deployment lifecycles
with transition validation, rollback support, and audit logging.

States:
- PENDING: Deployment queued, waiting to start
- BUILDING: Building Docker image
- DEPLOYING: Deploying to Railway infrastructure
- ACTIVE: Successfully deployed and serving traffic
- FAILED: Deployment failed during build/deploy
- CRASHED: Deployed successfully but crashed at runtime
- ROLLING_BACK: Rollback in progress
- ROLLED_BACK: Successfully rolled back to previous version

Transitions:
- PENDING → BUILDING: Build started
- BUILDING → DEPLOYING: Build succeeded
- BUILDING → FAILED: Build failed
- DEPLOYING → ACTIVE: Deployment succeeded
- DEPLOYING → FAILED: Deployment failed
- ACTIVE → CRASHED: Runtime crash detected
- FAILED → ROLLING_BACK: Rollback initiated
- CRASHED → ROLLING_BACK: Rollback initiated
- ROLLING_BACK → ROLLED_BACK: Rollback succeeded
- ROLLING_BACK → FAILED: Rollback failed

Example:
    >>> from apps.business.core.state_machine import DeploymentStateMachine, DeploymentStatus
    >>>
    >>> # Initialize state machine
    >>> sm = DeploymentStateMachine(deployment_id="deploy-123")
    >>>
    >>> # Transition through lifecycle
    >>> sm.transition(DeploymentStatus.BUILDING)
    >>> sm.transition(DeploymentStatus.DEPLOYING)
    >>> sm.transition(DeploymentStatus.ACTIVE)
    >>>
    >>> # Check if can rollback
    >>> if sm.can_transition(DeploymentStatus.ROLLING_BACK):
    ...     sm.transition(DeploymentStatus.ROLLING_BACK)
"""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any


# ============================================================================
# ENUMS
# ============================================================================
class DeploymentStatus(str, Enum):
    """Railway deployment status values.

    These match Railway's GraphQL API status values.
    """

    PENDING = "PENDING"
    BUILDING = "BUILDING"
    DEPLOYING = "DEPLOYING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    CRASHED = "CRASHED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    REMOVED = "REMOVED"


# ============================================================================
# STATE TRANSITION DEFINITIONS
# ============================================================================
# Valid state transitions (from_state → to_state)
VALID_TRANSITIONS: dict[DeploymentStatus, set[DeploymentStatus]] = {
    DeploymentStatus.PENDING: {DeploymentStatus.BUILDING, DeploymentStatus.FAILED},
    DeploymentStatus.BUILDING: {
        DeploymentStatus.DEPLOYING,
        DeploymentStatus.FAILED,
        DeploymentStatus.ROLLING_BACK,
    },
    DeploymentStatus.DEPLOYING: {
        DeploymentStatus.ACTIVE,
        DeploymentStatus.FAILED,
        DeploymentStatus.ROLLING_BACK,
    },
    DeploymentStatus.ACTIVE: {
        DeploymentStatus.CRASHED,
        DeploymentStatus.ROLLING_BACK,
        DeploymentStatus.REMOVED,
    },
    DeploymentStatus.FAILED: {
        DeploymentStatus.ROLLING_BACK,
        DeploymentStatus.PENDING,  # Retry
        DeploymentStatus.REMOVED,
    },
    DeploymentStatus.CRASHED: {
        DeploymentStatus.ROLLING_BACK,
        DeploymentStatus.ACTIVE,  # Auto-restart
        DeploymentStatus.REMOVED,
    },
    DeploymentStatus.ROLLING_BACK: {
        DeploymentStatus.ROLLED_BACK,
        DeploymentStatus.FAILED,
    },
    DeploymentStatus.ROLLED_BACK: {
        DeploymentStatus.PENDING,  # New deployment
        DeploymentStatus.REMOVED,
    },
    DeploymentStatus.REMOVED: set(),  # Terminal state
}

# Terminal states (no further transitions possible except REMOVED)
TERMINAL_STATES = {
    DeploymentStatus.ACTIVE,
    DeploymentStatus.ROLLED_BACK,
    DeploymentStatus.REMOVED,
}

# States requiring immediate action
FAILURE_STATES = {DeploymentStatus.FAILED, DeploymentStatus.CRASHED}

# States indicating healthy deployment
HEALTHY_STATES = {DeploymentStatus.ACTIVE}


# ============================================================================
# STATE MACHINE
# ============================================================================
class DeploymentStateMachine:
    """Finite state machine for managing deployment lifecycle.

    Enforces valid state transitions, tracks history, and provides
    rollback support.

    Attributes:
        deployment_id: Railway deployment ID
        current_state: Current deployment state
        history: State transition history
        metadata: Additional context (commit SHA, author, etc.)
    """

    def __init__(
        self,
        deployment_id: str,
        initial_state: DeploymentStatus = DeploymentStatus.PENDING,
        metadata: dict[str, Any] | None = None,
    ):
        """Initialize state machine.

        Args:
            deployment_id: Railway deployment ID
            initial_state: Initial state (default: PENDING)
            metadata: Additional context

        Example:
            >>> sm = DeploymentStateMachine(
            ...     deployment_id="deploy-123",
            ...     metadata={"commit": "abc123", "author": "dev@example.com"}
            ... )
        """
        self.deployment_id = deployment_id
        self.current_state = initial_state
        self.metadata = metadata or {}
        self.history: list[dict[str, Any]] = [
            {
                "state": initial_state,
                "timestamp": datetime.now(UTC),
                "reason": "Initial state",
            }
        ]
        self.logger = logging.getLogger(__name__)

    def can_transition(self, to_state: DeploymentStatus) -> bool:
        """Check if transition to new state is valid.

        Args:
            to_state: Target state

        Returns:
            True if transition is valid, False otherwise

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> sm.can_transition(DeploymentStatus.BUILDING)
            True
            >>> sm.can_transition(DeploymentStatus.ACTIVE)
            False
        """
        valid_next_states = VALID_TRANSITIONS.get(self.current_state, set())
        return to_state in valid_next_states

    def transition(self, to_state: DeploymentStatus, reason: str | None = None) -> bool:
        """Transition to new state.

        Args:
            to_state: Target state
            reason: Reason for transition (optional)

        Returns:
            True if transition succeeded, False if invalid

        Raises:
            ValueError: If transition is invalid

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> sm.transition(DeploymentStatus.BUILDING, "Build started")
            True
            >>> sm.transition(DeploymentStatus.DEPLOYING, "Build succeeded")
            True
        """
        if not self.can_transition(to_state):
            error_msg = f"Invalid transition from {self.current_state} to {to_state}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        # Record transition
        self.history.append(
            {
                "from_state": self.current_state,
                "to_state": to_state,
                "timestamp": datetime.now(UTC),
                "reason": reason or f"Transition to {to_state}",
            }
        )

        # Update current state
        old_state = self.current_state
        self.current_state = to_state

        self.logger.info(
            f"Deployment {self.deployment_id}: {old_state} → {to_state} ({reason or 'no reason'})"
        )

        return True

    def get_duration(self) -> float:
        """Get deployment duration in seconds.

        Returns:
            Duration from first state to current state (seconds)

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> # ... transitions happen ...
            >>> duration = sm.get_duration()
            >>> print(f"Deployment took {duration:.1f} seconds")
        """
        if not self.history:
            return 0.0

        start_time = self.history[0]["timestamp"]
        current_time = datetime.now(UTC)
        return (current_time - start_time).total_seconds()

    def is_healthy(self) -> bool:
        """Check if deployment is in healthy state.

        Returns:
            True if ACTIVE, False otherwise

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> sm.transition(DeploymentStatus.BUILDING)
            >>> sm.is_healthy()
            False
            >>> sm.transition(DeploymentStatus.DEPLOYING)
            >>> sm.transition(DeploymentStatus.ACTIVE)
            >>> sm.is_healthy()
            True
        """
        return self.current_state in HEALTHY_STATES

    def is_failed(self) -> bool:
        """Check if deployment failed.

        Returns:
            True if FAILED or CRASHED, False otherwise

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> sm.transition(DeploymentStatus.BUILDING)
            >>> sm.transition(DeploymentStatus.FAILED)
            >>> sm.is_failed()
            True
        """
        return self.current_state in FAILURE_STATES

    def is_terminal(self) -> bool:
        """Check if in terminal state (no further transitions).

        Returns:
            True if in terminal state, False otherwise

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> sm.transition(DeploymentStatus.BUILDING)
            >>> sm.is_terminal()
            False
            >>> sm.transition(DeploymentStatus.DEPLOYING)
            >>> sm.transition(DeploymentStatus.ACTIVE)
            >>> sm.is_terminal()
            True
        """
        return self.current_state in TERMINAL_STATES

    def should_rollback(self) -> bool:
        """Determine if rollback should be initiated.

        Returns:
            True if in FAILED or CRASHED state, False otherwise

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> sm.transition(DeploymentStatus.BUILDING)
            >>> sm.transition(DeploymentStatus.FAILED)
            >>> sm.should_rollback()
            True
        """
        return self.is_failed()

    def get_history(self) -> list[dict[str, Any]]:
        """Get complete state transition history.

        Returns:
            List of transition records with timestamps and reasons

        Example:
            >>> sm = DeploymentStateMachine("deploy-123")
            >>> # ... transitions ...
            >>> history = sm.get_history()
            >>> for entry in history:
            ...     from_state = entry.get('from_state')
            ...     to_state = entry.get('to_state')
            ...     print(f"{entry['timestamp']}: {from_state} → {to_state}")
        """
        return self.history.copy()

    def __repr__(self) -> str:
        """String representation."""
        return f"DeploymentStateMachine(id={self.deployment_id}, state={self.current_state})"


# ============================================================================
# STATE MACHINE FACTORY
# ============================================================================
class StateMachineManager:
    """Manager for multiple deployment state machines.

    Tracks state machines for all active deployments, provides
    lookup by deployment ID, and handles cleanup.

    Example:
        >>> manager = StateMachineManager()
        >>> sm = manager.create("deploy-123")
        >>> sm.transition(DeploymentStatus.BUILDING)
        >>> sm = manager.get("deploy-123")
        >>> print(sm.current_state)
        BUILDING
    """

    def __init__(self):
        """Initialize state machine manager."""
        self.state_machines: dict[str, DeploymentStateMachine] = {}
        self.logger = logging.getLogger(__name__)

    def create(
        self,
        deployment_id: str,
        initial_state: DeploymentStatus = DeploymentStatus.PENDING,
        metadata: dict[str, Any] | None = None,
    ) -> DeploymentStateMachine:
        """Create new state machine.

        Args:
            deployment_id: Railway deployment ID
            initial_state: Initial state (default: PENDING)
            metadata: Additional context

        Returns:
            New state machine instance

        Example:
            >>> manager = StateMachineManager()
            >>> sm = manager.create("deploy-123", metadata={"commit": "abc123"})
        """
        sm = DeploymentStateMachine(deployment_id, initial_state, metadata)
        self.state_machines[deployment_id] = sm
        self.logger.info(f"Created state machine for deployment {deployment_id}")
        return sm

    def get(self, deployment_id: str) -> DeploymentStateMachine | None:
        """Get state machine by deployment ID.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            State machine if exists, None otherwise

        Example:
            >>> manager = StateMachineManager()
            >>> manager.create("deploy-123")
            >>> sm = manager.get("deploy-123")
            >>> print(sm.current_state)
            PENDING
        """
        return self.state_machines.get(deployment_id)

    def remove(self, deployment_id: str) -> bool:
        """Remove state machine (cleanup).

        Args:
            deployment_id: Railway deployment ID

        Returns:
            True if removed, False if not found

        Example:
            >>> manager = StateMachineManager()
            >>> manager.create("deploy-123")
            >>> manager.remove("deploy-123")
            True
        """
        if deployment_id in self.state_machines:
            del self.state_machines[deployment_id]
            self.logger.info(f"Removed state machine for deployment {deployment_id}")
            return True
        return False

    def get_all_failed(self) -> list[DeploymentStateMachine]:
        """Get all state machines in failed state.

        Returns:
            List of state machines with FAILED or CRASHED status

        Example:
            >>> manager = StateMachineManager()
            >>> failed = manager.get_all_failed()
            >>> for sm in failed:
            ...     print(f"Failed: {sm.deployment_id}")
        """
        return [sm for sm in self.state_machines.values() if sm.is_failed()]

    def get_all_healthy(self) -> list[DeploymentStateMachine]:
        """Get all state machines in healthy state.

        Returns:
            List of state machines with ACTIVE status

        Example:
            >>> manager = StateMachineManager()
            >>> healthy = manager.get_all_healthy()
            >>> print(f"{len(healthy)} healthy deployments")
        """
        return [sm for sm in self.state_machines.values() if sm.is_healthy()]

    def count(self) -> int:
        """Get total number of tracked deployments.

        Returns:
            Number of active state machines

        Example:
            >>> manager = StateMachineManager()
            >>> print(f"Tracking {manager.count()} deployments")
        """
        return len(self.state_machines)
