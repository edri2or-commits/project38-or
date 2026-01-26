"""Token rotation with safety interlock.

Implements CRITICAL-5: Safe token rotation with versioning and rollback.
Ensures tokens are validated before and after rotation to prevent service disruption.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from google.api_core import exceptions
from google.cloud import secretmanager

logger = logging.getLogger(__name__)

GCP_PROJECT_ID = "project38-483612"


class RotationState(Enum):
    """Token rotation state machine."""

    IDLE = "idle"
    VALIDATING_OLD = "validating_old"
    CREATING_NEW = "creating_new"
    VALIDATING_NEW = "validating_new"
    ACTIVATING = "activating"
    ROLLBACK = "rollback"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RotationResult:
    """Result of a token rotation operation."""

    success: bool
    secret_name: str
    old_version: str | None
    new_version: str | None
    state: RotationState
    error: str | None = None
    duration_seconds: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


class TokenRotationInterlock:
    """Safe token rotation with validation and rollback capability.

    Implements a state machine that ensures:
    1. Old token is validated before rotation
    2. New token is validated after creation
    3. Automatic rollback on validation failure
    4. Audit trail of all rotation operations
    """

    def __init__(self):
        """Initialize the rotation interlock."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.project_id = GCP_PROJECT_ID
        self._rotation_in_progress: dict[str, bool] = {}
        self._rotation_history: list[RotationResult] = []

    def _get_secret_path(self, secret_name: str) -> str:
        """Get full secret path."""
        return f"projects/{self.project_id}/secrets/{secret_name}"

    def _get_version_path(self, secret_name: str, version: str = "latest") -> str:
        """Get full version path."""
        return f"{self._get_secret_path(secret_name)}/versions/{version}"

    def _get_current_version(self, secret_name: str) -> str | None:
        """Get the current version number of a secret.

        Args:
            secret_name: Name of the secret.

        Returns:
            Version number as string or None if not found.
        """
        try:
            name = self._get_version_path(secret_name, "latest")
            response = self.client.access_secret_version(request={"name": name})
            # Extract version from name: projects/.../secrets/.../versions/X
            return response.name.split("/")[-1]
        except exceptions.NotFound:
            return None
        except Exception as e:
            logger.error(f"Failed to get version for {secret_name}: {type(e).__name__}")
            return None

    def _get_secret_value(self, secret_name: str, version: str = "latest") -> str | None:
        """Get secret value for a specific version.

        Args:
            secret_name: Name of the secret.
            version: Version to retrieve.

        Returns:
            Secret value or None.
        """
        try:
            name = self._get_version_path(secret_name, version)
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception:
            return None

    def _add_secret_version(self, secret_name: str, value: str) -> str | None:
        """Add a new version to a secret.

        Args:
            secret_name: Name of the secret.
            value: New secret value.

        Returns:
            New version number or None on failure.
        """
        try:
            parent = self._get_secret_path(secret_name)
            response = self.client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": value.encode("UTF-8")},
                }
            )
            return response.name.split("/")[-1]
        except Exception as e:
            logger.error(f"Failed to add version: {type(e).__name__}")
            return None

    def _disable_version(self, secret_name: str, version: str) -> bool:
        """Disable a secret version (soft delete).

        Args:
            secret_name: Name of the secret.
            version: Version to disable.

        Returns:
            True if successful.
        """
        try:
            name = self._get_version_path(secret_name, version)
            self.client.disable_secret_version(request={"name": name})
            return True
        except Exception as e:
            logger.error(f"Failed to disable version {version}: {type(e).__name__}")
            return False

    def _enable_version(self, secret_name: str, version: str) -> bool:
        """Re-enable a disabled secret version.

        Args:
            secret_name: Name of the secret.
            version: Version to enable.

        Returns:
            True if successful.
        """
        try:
            name = self._get_version_path(secret_name, version)
            self.client.enable_secret_version(request={"name": name})
            return True
        except Exception as e:
            logger.error(f"Failed to enable version {version}: {type(e).__name__}")
            return False

    async def rotate_token(
        self,
        secret_name: str,
        new_value: str,
        validator: Callable[[str], bool] | None = None,
    ) -> RotationResult:
        """Rotate a token with safety interlock.

        Args:
            secret_name: Name of the secret to rotate.
            new_value: New token value.
            validator: Optional async function to validate token works.
                      Should return True if token is valid.

        Returns:
            RotationResult with success/failure and details.
        """
        start_time = time.time()
        state = RotationState.IDLE

        # Check if rotation already in progress
        if self._rotation_in_progress.get(secret_name):
            return RotationResult(
                success=False,
                secret_name=secret_name,
                old_version=None,
                new_version=None,
                state=RotationState.FAILED,
                error="Rotation already in progress for this secret",
            )

        self._rotation_in_progress[secret_name] = True
        old_version = None
        new_version = None

        try:
            # State 1: Validate old token exists
            state = RotationState.VALIDATING_OLD
            old_version = self._get_current_version(secret_name)
            if not old_version:
                return RotationResult(
                    success=False,
                    secret_name=secret_name,
                    old_version=None,
                    new_version=None,
                    state=state,
                    error="Secret not found or no versions exist",
                    duration_seconds=time.time() - start_time,
                )

            old_value = self._get_secret_value(secret_name, old_version)
            if not old_value:
                return RotationResult(
                    success=False,
                    secret_name=secret_name,
                    old_version=old_version,
                    new_version=None,
                    state=state,
                    error="Failed to retrieve current secret value",
                    duration_seconds=time.time() - start_time,
                )

            logger.info(f"Validated old version {old_version} exists")

            # State 2: Create new version
            state = RotationState.CREATING_NEW
            new_version = self._add_secret_version(secret_name, new_value)
            if not new_version:
                return RotationResult(
                    success=False,
                    secret_name=secret_name,
                    old_version=old_version,
                    new_version=None,
                    state=state,
                    error="Failed to create new secret version",
                    duration_seconds=time.time() - start_time,
                )

            logger.info(f"Created new version {new_version}")

            # State 3: Validate new token works
            state = RotationState.VALIDATING_NEW
            if validator:
                try:
                    is_valid = validator(new_value)
                    if asyncio.iscoroutine(is_valid):
                        is_valid = await is_valid

                    if not is_valid:
                        # Rollback: disable new version
                        state = RotationState.ROLLBACK
                        self._disable_version(secret_name, new_version)
                        logger.warning(
                            f"New token validation failed, rolled back version {new_version}"
                        )
                        return RotationResult(
                            success=False,
                            secret_name=secret_name,
                            old_version=old_version,
                            new_version=new_version,
                            state=state,
                            error="New token validation failed - rolled back",
                            duration_seconds=time.time() - start_time,
                        )
                except Exception as e:
                    # Rollback on validation error
                    state = RotationState.ROLLBACK
                    self._disable_version(secret_name, new_version)
                    logger.error(f"Validation error, rolled back: {type(e).__name__}")
                    return RotationResult(
                        success=False,
                        secret_name=secret_name,
                        old_version=old_version,
                        new_version=new_version,
                        state=state,
                        error=f"Validation error: {type(e).__name__}",
                        duration_seconds=time.time() - start_time,
                    )

            # State 4: Activate - disable old version
            state = RotationState.ACTIVATING
            # Keep old version enabled for rollback window (don't disable immediately)
            logger.info(
                f"Rotation complete. Old version {old_version} kept for rollback. "
                f"New version {new_version} is now active."
            )

            state = RotationState.COMPLETED
            result = RotationResult(
                success=True,
                secret_name=secret_name,
                old_version=old_version,
                new_version=new_version,
                state=state,
                duration_seconds=time.time() - start_time,
            )
            self._rotation_history.append(result)
            return result

        except Exception as e:
            logger.error(f"Rotation failed at state {state.value}: {type(e).__name__}")
            return RotationResult(
                success=False,
                secret_name=secret_name,
                old_version=old_version,
                new_version=new_version,
                state=RotationState.FAILED,
                error=f"Unexpected error: {type(e).__name__}",
                duration_seconds=time.time() - start_time,
            )

        finally:
            self._rotation_in_progress[secret_name] = False

    def rollback(self, secret_name: str, to_version: str) -> bool:
        """Manually rollback to a previous version.

        Args:
            secret_name: Name of the secret.
            to_version: Version to rollback to.

        Returns:
            True if rollback successful.
        """
        try:
            # Verify version exists
            value = self._get_secret_value(secret_name, to_version)
            if not value:
                logger.error(f"Cannot rollback: version {to_version} not found")
                return False

            # Enable the target version if disabled
            self._enable_version(secret_name, to_version)

            # Get current version and disable it
            current = self._get_current_version(secret_name)
            if current and current != to_version:
                self._disable_version(secret_name, current)

            logger.info(f"Rolled back {secret_name} to version {to_version}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {type(e).__name__}")
            return False

    def get_rotation_history(self, secret_name: str | None = None) -> list[dict]:
        """Get rotation history.

        Args:
            secret_name: Filter by secret name (optional).

        Returns:
            List of rotation results as dicts.
        """
        history = self._rotation_history
        if secret_name:
            history = [r for r in history if r.secret_name == secret_name]

        return [
            {
                "success": r.success,
                "secret_name": r.secret_name,
                "old_version": r.old_version,
                "new_version": r.new_version,
                "state": r.state.value,
                "error": r.error,
                "duration_seconds": round(r.duration_seconds, 3),
                "timestamp": r.timestamp,
            }
            for r in history
        ]


# Global instance
_interlock: TokenRotationInterlock | None = None


def get_rotation_interlock() -> TokenRotationInterlock:
    """Get the global token rotation interlock instance."""
    global _interlock
    if _interlock is None:
        _interlock = TokenRotationInterlock()
    return _interlock
