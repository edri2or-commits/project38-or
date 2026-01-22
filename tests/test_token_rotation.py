"""Tests for Token Rotation Interlock.

Tests the token_rotation module in src/token_rotation.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _can_import_module() -> bool:
    """Check if token_rotation module can be imported.

    This also implicitly checks for GCP libraries since token_rotation
    imports them at module level.
    """
    try:
        # First check if cryptography is available (required by GCP libs)
        import _cffi_backend
        import cryptography.hazmat.primitives
    except (ImportError, ModuleNotFoundError):
        return False
    except Exception:
        return False

    try:
        from src.token_rotation import (
            RotationResult,
            RotationState,
            TokenRotationInterlock,
            get_rotation_interlock,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_import_module(),
    reason="token_rotation module not importable (requires GCP libs and cryptography)"
)


class TestRotationState:
    """Tests for RotationState enum."""

    def test_rotation_state_values(self):
        """Test RotationState enum values."""
        from src.token_rotation import RotationState

        assert RotationState.IDLE.value == "idle"
        assert RotationState.VALIDATING_OLD.value == "validating_old"
        assert RotationState.CREATING_NEW.value == "creating_new"
        assert RotationState.VALIDATING_NEW.value == "validating_new"
        assert RotationState.ACTIVATING.value == "activating"
        assert RotationState.ROLLBACK.value == "rollback"
        assert RotationState.COMPLETED.value == "completed"
        assert RotationState.FAILED.value == "failed"


class TestRotationResult:
    """Tests for RotationResult dataclass."""

    def test_rotation_result_success(self):
        """Test successful rotation result."""
        from src.token_rotation import RotationResult, RotationState

        result = RotationResult(
            success=True,
            secret_name="TEST-SECRET",
            old_version="1",
            new_version="2",
            state=RotationState.COMPLETED,
            duration_seconds=1.5,
        )

        assert result.success is True
        assert result.secret_name == "TEST-SECRET"
        assert result.old_version == "1"
        assert result.new_version == "2"
        assert result.state == RotationState.COMPLETED
        assert result.error is None
        assert result.timestamp != ""

    def test_rotation_result_failure(self):
        """Test failed rotation result."""
        from src.token_rotation import RotationResult, RotationState

        result = RotationResult(
            success=False,
            secret_name="TEST-SECRET",
            old_version="1",
            new_version=None,
            state=RotationState.FAILED,
            error="Validation failed",
        )

        assert result.success is False
        assert result.error == "Validation failed"
        assert result.state == RotationState.FAILED


class TestTokenRotationInterlock:
    """Tests for TokenRotationInterlock class."""

    def test_get_secret_path(self):
        """Test secret path generation."""
        from src.token_rotation import TokenRotationInterlock

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient"):
            interlock = TokenRotationInterlock()
            path = interlock._get_secret_path("MY-SECRET")

        assert path == "projects/project38-483612/secrets/MY-SECRET"

    def test_get_version_path(self):
        """Test version path generation."""
        from src.token_rotation import TokenRotationInterlock

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient"):
            interlock = TokenRotationInterlock()
            path = interlock._get_version_path("MY-SECRET", "5")

        assert path == "projects/project38-483612/secrets/MY-SECRET/versions/5"

    def test_get_version_path_latest(self):
        """Test version path with latest."""
        from src.token_rotation import TokenRotationInterlock

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient"):
            interlock = TokenRotationInterlock()
            path = interlock._get_version_path("MY-SECRET")

        assert path.endswith("/versions/latest")

    def test_get_current_version_success(self):
        """Test getting current version."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.name = "projects/123/secrets/test/versions/5"
        mock_client.access_secret_version.return_value = mock_response

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            version = interlock._get_current_version("TEST-SECRET")

        assert version == "5"

    def test_get_current_version_not_found(self):
        """Test getting version when secret not found."""
        from google.api_core import exceptions

        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()
        mock_client.access_secret_version.side_effect = exceptions.NotFound("Not found")

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            version = interlock._get_current_version("NONEXISTENT")

        assert version is None

    def test_get_secret_value_success(self):
        """Test getting secret value."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.payload.data = b"secret-value"
        mock_client.access_secret_version.return_value = mock_response

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            value = interlock._get_secret_value("TEST-SECRET", "1")

        assert value == "secret-value"

    def test_add_secret_version_success(self):
        """Test adding new secret version."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.name = "projects/123/secrets/test/versions/6"
        mock_client.add_secret_version.return_value = mock_response

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            version = interlock._add_secret_version("TEST-SECRET", "new-value")

        assert version == "6"

    def test_disable_version_success(self):
        """Test disabling secret version."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = interlock._disable_version("TEST-SECRET", "5")

        assert result is True
        mock_client.disable_secret_version.assert_called_once()

    def test_enable_version_success(self):
        """Test enabling secret version."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = interlock._enable_version("TEST-SECRET", "5")

        assert result is True
        mock_client.enable_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_rotate_token_success(self):
        """Test successful token rotation."""
        from src.token_rotation import RotationState, TokenRotationInterlock

        mock_client = MagicMock()

        # Mock access_secret_version for getting current version and value
        mock_version_response = MagicMock()
        mock_version_response.name = "projects/123/secrets/test/versions/1"
        mock_version_response.payload.data = b"old-value"

        mock_new_version_response = MagicMock()
        mock_new_version_response.name = "projects/123/secrets/test/versions/2"

        mock_client.access_secret_version.return_value = mock_version_response
        mock_client.add_secret_version.return_value = mock_new_version_response

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = await interlock.rotate_token("TEST-SECRET", "new-value")

        assert result.success is True
        assert result.state == RotationState.COMPLETED
        assert result.old_version == "1"
        assert result.new_version == "2"

    @pytest.mark.asyncio
    async def test_rotate_token_with_validator_success(self):
        """Test token rotation with successful validation."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()

        mock_version_response = MagicMock()
        mock_version_response.name = "projects/123/secrets/test/versions/1"
        mock_version_response.payload.data = b"old-value"

        mock_new_version_response = MagicMock()
        mock_new_version_response.name = "projects/123/secrets/test/versions/2"

        mock_client.access_secret_version.return_value = mock_version_response
        mock_client.add_secret_version.return_value = mock_new_version_response

        validator = MagicMock(return_value=True)

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = await interlock.rotate_token("TEST-SECRET", "new-value", validator=validator)

        assert result.success is True
        validator.assert_called_once_with("new-value")

    @pytest.mark.asyncio
    async def test_rotate_token_with_validator_failure(self):
        """Test token rotation with failed validation causes rollback."""
        from src.token_rotation import RotationState, TokenRotationInterlock

        mock_client = MagicMock()

        mock_version_response = MagicMock()
        mock_version_response.name = "projects/123/secrets/test/versions/1"
        mock_version_response.payload.data = b"old-value"

        mock_new_version_response = MagicMock()
        mock_new_version_response.name = "projects/123/secrets/test/versions/2"

        mock_client.access_secret_version.return_value = mock_version_response
        mock_client.add_secret_version.return_value = mock_new_version_response

        validator = MagicMock(return_value=False)  # Validation fails

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = await interlock.rotate_token("TEST-SECRET", "new-value", validator=validator)

        assert result.success is False
        assert result.state == RotationState.ROLLBACK
        assert "rolled back" in result.error.lower()
        mock_client.disable_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_rotate_token_already_in_progress(self):
        """Test rotation blocked when already in progress."""
        from src.token_rotation import TokenRotationInterlock

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient"):
            interlock = TokenRotationInterlock()
            interlock._rotation_in_progress["TEST-SECRET"] = True

            result = await interlock.rotate_token("TEST-SECRET", "new-value")

        assert result.success is False
        assert "already in progress" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rotate_token_secret_not_found(self):
        """Test rotation when secret doesn't exist."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()
        mock_client.access_secret_version.side_effect = Exception("Not found")

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = await interlock.rotate_token("NONEXISTENT", "new-value")

        assert result.success is False

    def test_rollback_success(self):
        """Test manual rollback."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()

        # Mock for getting target version value
        mock_version_response = MagicMock()
        mock_version_response.payload.data = b"old-value"
        mock_version_response.name = "projects/123/secrets/test/versions/5"

        mock_client.access_secret_version.return_value = mock_version_response

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = interlock.rollback("TEST-SECRET", "3")

        assert result is True
        mock_client.enable_secret_version.assert_called()

    def test_rollback_version_not_found(self):
        """Test rollback when version doesn't exist."""
        from src.token_rotation import TokenRotationInterlock

        mock_client = MagicMock()
        mock_client.access_secret_version.side_effect = Exception("Not found")

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient", return_value=mock_client):
            interlock = TokenRotationInterlock()
            result = interlock.rollback("TEST-SECRET", "999")

        assert result is False

    def test_get_rotation_history_empty(self):
        """Test getting empty rotation history."""
        from src.token_rotation import TokenRotationInterlock

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient"):
            interlock = TokenRotationInterlock()
            history = interlock.get_rotation_history()

        assert history == []

    def test_get_rotation_history_with_filter(self):
        """Test getting rotation history with filter."""
        from src.token_rotation import RotationResult, RotationState, TokenRotationInterlock

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient"):
            interlock = TokenRotationInterlock()

            # Add some results
            interlock._rotation_history = [
                RotationResult(
                    success=True,
                    secret_name="SECRET-A",
                    old_version="1",
                    new_version="2",
                    state=RotationState.COMPLETED,
                ),
                RotationResult(
                    success=True,
                    secret_name="SECRET-B",
                    old_version="1",
                    new_version="2",
                    state=RotationState.COMPLETED,
                ),
            ]

            history = interlock.get_rotation_history("SECRET-A")

        assert len(history) == 1
        assert history[0]["secret_name"] == "SECRET-A"


class TestGlobalInterlock:
    """Tests for global interlock instance."""

    def test_get_rotation_interlock_singleton(self):
        """Test that get_rotation_interlock returns singleton."""
        import src.token_rotation as module
        from src.token_rotation import get_rotation_interlock

        # Reset global
        module._interlock = None

        with patch("src.token_rotation.secretmanager.SecretManagerServiceClient"):
            interlock1 = get_rotation_interlock()
            interlock2 = get_rotation_interlock()

        assert interlock1 is interlock2

        # Clean up
        module._interlock = None
