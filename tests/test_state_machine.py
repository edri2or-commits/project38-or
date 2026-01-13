"""Tests for Deployment State Machine."""

import pytest

from src.state_machine import (
    DeploymentStateMachine,
    DeploymentStatus,
    StateMachineManager,
)


# ============================================================================
# STATE MACHINE TESTS
# ============================================================================
class TestDeploymentStateMachine:
    """Tests for DeploymentStateMachine class."""

    def test_initialization(self):
        """Test state machine initialization."""
        sm = DeploymentStateMachine("deploy-123")

        assert sm.deployment_id == "deploy-123"
        assert sm.current_state == DeploymentStatus.PENDING
        assert len(sm.history) == 1
        assert sm.metadata == {}

    def test_initialization_with_metadata(self):
        """Test state machine initialization with metadata."""
        sm = DeploymentStateMachine(
            "deploy-123", metadata={"commit": "abc123", "author": "dev@example.com"}
        )

        assert sm.metadata["commit"] == "abc123"
        assert sm.metadata["author"] == "dev@example.com"

    def test_can_transition_valid(self):
        """Test checking valid transitions."""
        sm = DeploymentStateMachine("deploy-123")

        assert sm.can_transition(DeploymentStatus.BUILDING) is True
        assert sm.can_transition(DeploymentStatus.FAILED) is True

    def test_can_transition_invalid(self):
        """Test checking invalid transitions."""
        sm = DeploymentStateMachine("deploy-123")

        assert sm.can_transition(DeploymentStatus.ACTIVE) is False
        assert sm.can_transition(DeploymentStatus.ROLLED_BACK) is False

    def test_transition_valid(self):
        """Test valid state transition."""
        sm = DeploymentStateMachine("deploy-123")

        result = sm.transition(DeploymentStatus.BUILDING, "Build started")

        assert result is True
        assert sm.current_state == DeploymentStatus.BUILDING
        assert len(sm.history) == 2

    def test_transition_invalid(self):
        """Test invalid state transition raises error."""
        sm = DeploymentStateMachine("deploy-123")

        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(DeploymentStatus.ACTIVE)

    def test_transition_chain(self):
        """Test complete transition chain."""
        sm = DeploymentStateMachine("deploy-123")

        # PENDING → BUILDING
        sm.transition(DeploymentStatus.BUILDING)
        assert sm.current_state == DeploymentStatus.BUILDING

        # BUILDING → DEPLOYING
        sm.transition(DeploymentStatus.DEPLOYING)
        assert sm.current_state == DeploymentStatus.DEPLOYING

        # DEPLOYING → ACTIVE
        sm.transition(DeploymentStatus.ACTIVE)
        assert sm.current_state == DeploymentStatus.ACTIVE

        assert len(sm.history) == 4  # Initial + 3 transitions

    def test_transition_to_failed(self):
        """Test transition to FAILED state."""
        sm = DeploymentStateMachine("deploy-123")

        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.FAILED, "Build error")

        assert sm.current_state == DeploymentStatus.FAILED
        assert sm.history[-1]["reason"] == "Build error"

    def test_transition_rollback_flow(self):
        """Test rollback transition flow."""
        sm = DeploymentStateMachine("deploy-123")

        # Deploy and fail
        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.DEPLOYING)
        sm.transition(DeploymentStatus.FAILED)

        # Rollback
        sm.transition(DeploymentStatus.ROLLING_BACK)
        assert sm.current_state == DeploymentStatus.ROLLING_BACK

        sm.transition(DeploymentStatus.ROLLED_BACK)
        assert sm.current_state == DeploymentStatus.ROLLED_BACK

    def test_get_duration(self):
        """Test getting deployment duration."""
        sm = DeploymentStateMachine("deploy-123")

        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.DEPLOYING)

        duration = sm.get_duration()
        assert duration >= 0  # Should be very small but non-negative

    def test_is_healthy(self):
        """Test checking if deployment is healthy."""
        sm = DeploymentStateMachine("deploy-123")

        assert sm.is_healthy() is False

        sm.transition(DeploymentStatus.BUILDING)
        assert sm.is_healthy() is False

        sm.transition(DeploymentStatus.DEPLOYING)
        assert sm.is_healthy() is False

        sm.transition(DeploymentStatus.ACTIVE)
        assert sm.is_healthy() is True

    def test_is_failed(self):
        """Test checking if deployment failed."""
        sm = DeploymentStateMachine("deploy-123")

        assert sm.is_failed() is False

        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.FAILED)

        assert sm.is_failed() is True

    def test_is_failed_crashed(self):
        """Test checking if deployment crashed."""
        sm = DeploymentStateMachine("deploy-123")

        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.DEPLOYING)
        sm.transition(DeploymentStatus.ACTIVE)
        sm.transition(DeploymentStatus.CRASHED)

        assert sm.is_failed() is True

    def test_is_terminal(self):
        """Test checking if in terminal state."""
        sm = DeploymentStateMachine("deploy-123")

        assert sm.is_terminal() is False

        sm.transition(DeploymentStatus.BUILDING)
        assert sm.is_terminal() is False

        sm.transition(DeploymentStatus.DEPLOYING)
        sm.transition(DeploymentStatus.ACTIVE)

        assert sm.is_terminal() is True

    def test_should_rollback(self):
        """Test determining if rollback should be initiated."""
        sm = DeploymentStateMachine("deploy-123")

        assert sm.should_rollback() is False

        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.FAILED)

        assert sm.should_rollback() is True

    def test_get_history(self):
        """Test getting complete transition history."""
        sm = DeploymentStateMachine("deploy-123")

        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.DEPLOYING)

        history = sm.get_history()

        assert len(history) == 3  # Initial + 2 transitions
        assert history[0]["state"] == DeploymentStatus.PENDING
        assert history[1]["to_state"] == DeploymentStatus.BUILDING
        assert history[2]["to_state"] == DeploymentStatus.DEPLOYING

    def test_repr(self):
        """Test string representation."""
        sm = DeploymentStateMachine("deploy-123")

        repr_str = repr(sm)
        assert "deploy-123" in repr_str
        assert "PENDING" in repr_str


# ============================================================================
# STATE MACHINE MANAGER TESTS
# ============================================================================
class TestStateMachineManager:
    """Tests for StateMachineManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = StateMachineManager()

        assert manager.count() == 0
        assert manager.state_machines == {}

    def test_create_state_machine(self):
        """Test creating a state machine."""
        manager = StateMachineManager()

        sm = manager.create("deploy-123")

        assert sm.deployment_id == "deploy-123"
        assert manager.count() == 1

    def test_create_state_machine_with_metadata(self):
        """Test creating a state machine with metadata."""
        manager = StateMachineManager()

        sm = manager.create("deploy-123", metadata={"commit": "abc123"})

        assert sm.metadata["commit"] == "abc123"

    def test_get_existing_state_machine(self):
        """Test getting an existing state machine."""
        manager = StateMachineManager()

        created_sm = manager.create("deploy-123")
        retrieved_sm = manager.get("deploy-123")

        assert retrieved_sm is not None
        assert retrieved_sm.deployment_id == created_sm.deployment_id

    def test_get_nonexistent_state_machine(self):
        """Test getting a nonexistent state machine."""
        manager = StateMachineManager()

        sm = manager.get("deploy-nonexistent")

        assert sm is None

    def test_remove_state_machine(self):
        """Test removing a state machine."""
        manager = StateMachineManager()

        manager.create("deploy-123")
        assert manager.count() == 1

        result = manager.remove("deploy-123")

        assert result is True
        assert manager.count() == 0

    def test_remove_nonexistent_state_machine(self):
        """Test removing a nonexistent state machine."""
        manager = StateMachineManager()

        result = manager.remove("deploy-nonexistent")

        assert result is False

    def test_get_all_failed(self):
        """Test getting all failed state machines."""
        manager = StateMachineManager()

        # Create multiple state machines with different states
        sm1 = manager.create("deploy-1")
        sm1.transition(DeploymentStatus.BUILDING)
        sm1.transition(DeploymentStatus.FAILED)

        sm2 = manager.create("deploy-2")
        sm2.transition(DeploymentStatus.BUILDING)
        sm2.transition(DeploymentStatus.DEPLOYING)
        sm2.transition(DeploymentStatus.ACTIVE)

        sm3 = manager.create("deploy-3")
        sm3.transition(DeploymentStatus.BUILDING)
        sm3.transition(DeploymentStatus.DEPLOYING)
        sm3.transition(DeploymentStatus.ACTIVE)
        sm3.transition(DeploymentStatus.CRASHED)

        failed = manager.get_all_failed()

        assert len(failed) == 2
        assert sm1 in failed
        assert sm3 in failed

    def test_get_all_healthy(self):
        """Test getting all healthy state machines."""
        manager = StateMachineManager()

        # Create multiple state machines with different states
        sm1 = manager.create("deploy-1")
        sm1.transition(DeploymentStatus.BUILDING)
        sm1.transition(DeploymentStatus.DEPLOYING)
        sm1.transition(DeploymentStatus.ACTIVE)

        sm2 = manager.create("deploy-2")
        sm2.transition(DeploymentStatus.BUILDING)
        sm2.transition(DeploymentStatus.FAILED)

        sm3 = manager.create("deploy-3")
        sm3.transition(DeploymentStatus.BUILDING)
        sm3.transition(DeploymentStatus.DEPLOYING)
        sm3.transition(DeploymentStatus.ACTIVE)

        healthy = manager.get_all_healthy()

        assert len(healthy) == 2
        assert sm1 in healthy
        assert sm3 in healthy

    def test_count(self):
        """Test counting tracked deployments."""
        manager = StateMachineManager()

        assert manager.count() == 0

        manager.create("deploy-1")
        assert manager.count() == 1

        manager.create("deploy-2")
        manager.create("deploy-3")
        assert manager.count() == 3

        manager.remove("deploy-2")
        assert manager.count() == 2


# ============================================================================
# INTEGRATION TESTS
# ============================================================================
class TestStateTransitionIntegration:
    """Integration tests for complete deployment lifecycle."""

    def test_successful_deployment_lifecycle(self):
        """Test complete successful deployment lifecycle."""
        sm = DeploymentStateMachine("deploy-123", metadata={"commit": "abc123"})

        # Start deployment
        sm.transition(DeploymentStatus.BUILDING, "Build started")
        assert sm.current_state == DeploymentStatus.BUILDING

        # Build succeeded, deploying
        sm.transition(DeploymentStatus.DEPLOYING, "Build succeeded")
        assert sm.current_state == DeploymentStatus.DEPLOYING

        # Deployment succeeded
        sm.transition(DeploymentStatus.ACTIVE, "Deployment succeeded")
        assert sm.current_state == DeploymentStatus.ACTIVE
        assert sm.is_healthy() is True
        assert sm.is_terminal() is True

    def test_failed_deployment_with_rollback(self):
        """Test failed deployment with rollback."""
        sm = DeploymentStateMachine("deploy-123")

        # Start deployment
        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.DEPLOYING)

        # Deployment failed
        sm.transition(DeploymentStatus.FAILED, "Deployment timeout")
        assert sm.should_rollback() is True

        # Rollback
        sm.transition(DeploymentStatus.ROLLING_BACK, "Initiating rollback")
        sm.transition(DeploymentStatus.ROLLED_BACK, "Rollback succeeded")

        assert sm.current_state == DeploymentStatus.ROLLED_BACK
        assert sm.is_terminal() is True

    def test_crashed_deployment_with_rollback(self):
        """Test crashed deployment with rollback."""
        sm = DeploymentStateMachine("deploy-123")

        # Successful deployment
        sm.transition(DeploymentStatus.BUILDING)
        sm.transition(DeploymentStatus.DEPLOYING)
        sm.transition(DeploymentStatus.ACTIVE)

        # Runtime crash
        sm.transition(DeploymentStatus.CRASHED, "Out of memory")
        assert sm.is_failed() is True
        assert sm.should_rollback() is True

        # Rollback
        sm.transition(DeploymentStatus.ROLLING_BACK)
        sm.transition(DeploymentStatus.ROLLED_BACK)

        assert sm.current_state == DeploymentStatus.ROLLED_BACK

    def test_multiple_deployments_in_manager(self):
        """Test managing multiple deployments simultaneously."""
        manager = StateMachineManager()

        # Create 3 deployments
        sm1 = manager.create("deploy-1", metadata={"commit": "abc123"})
        sm2 = manager.create("deploy-2", metadata={"commit": "def456"})
        sm3 = manager.create("deploy-3", metadata={"commit": "ghi789"})

        # Progress them to different states
        sm1.transition(DeploymentStatus.BUILDING)
        sm1.transition(DeploymentStatus.DEPLOYING)
        sm1.transition(DeploymentStatus.ACTIVE)

        sm2.transition(DeploymentStatus.BUILDING)
        sm2.transition(DeploymentStatus.FAILED)

        sm3.transition(DeploymentStatus.BUILDING)

        # Verify states
        assert manager.count() == 3
        assert len(manager.get_all_healthy()) == 1
        assert len(manager.get_all_failed()) == 1

        # Cleanup failed deployment
        manager.remove("deploy-2")
        assert manager.count() == 2
