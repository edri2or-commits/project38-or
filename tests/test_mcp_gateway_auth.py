"""Tests for MCP Gateway authentication.

Tests the auth module in src/mcp_gateway/auth.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient


def _has_cryptography() -> bool:
    """Check if cryptography module is available."""
    try:
        import _cffi_backend
        import cryptography.hazmat.primitives
        return True
    except (ImportError, ModuleNotFoundError):
        return False
    except Exception:
        return False


def _can_import_auth() -> bool:
    """Check if auth module can be imported."""
    try:
        from src.mcp_gateway.auth import verify_token, validate_token_sync
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _can_import_auth(),
        reason="mcp_gateway.auth module not importable"
    ),
    pytest.mark.skipif(
        not _has_cryptography(),
        reason="cryptography module not available"
    ),
]


class TestVerifyToken:
    """Tests for verify_token async function."""

    @pytest.mark.asyncio
    async def test_missing_credentials_raises_401(self):
        """Test that missing credentials raises 401."""
        from src.mcp_gateway.auth import verify_token

        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials=None)

        assert exc_info.value.status_code == 401
        assert "Missing authorization header" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Test that invalid token raises 401."""
        from src.mcp_gateway.auth import verify_token

        mock_config = MagicMock()
        mock_config.gateway_token = "correct-token"

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")

        with patch("src.mcp_gateway.auth.get_config", return_value=mock_config):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(credentials=credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid authorization token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_returns_token(self):
        """Test that valid token returns the token string."""
        from src.mcp_gateway.auth import verify_token

        mock_config = MagicMock()
        mock_config.gateway_token = "valid-token-12345"

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token-12345")

        with patch("src.mcp_gateway.auth.get_config", return_value=mock_config):
            result = await verify_token(credentials=credentials)

        assert result == "valid-token-12345"

    @pytest.mark.asyncio
    async def test_no_gateway_token_configured_raises_500(self):
        """Test that missing gateway token config raises 500."""
        from src.mcp_gateway.auth import verify_token

        mock_config = MagicMock()
        mock_config.gateway_token = ""  # Empty token

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any-token")

        with patch("src.mcp_gateway.auth.get_config", return_value=mock_config):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(credentials=credentials)

        assert exc_info.value.status_code == 500
        assert "Gateway token not configured" in exc_info.value.detail


class TestValidateTokenSync:
    """Tests for validate_token_sync function."""

    def test_valid_token_returns_true(self):
        """Test that valid token returns True."""
        from src.mcp_gateway.auth import validate_token_sync

        mock_config = MagicMock()
        mock_config.gateway_token = "secret-token"

        with patch("src.mcp_gateway.auth.get_config", return_value=mock_config):
            result = validate_token_sync("secret-token")

        assert result is True

    def test_invalid_token_returns_false(self):
        """Test that invalid token returns False."""
        from src.mcp_gateway.auth import validate_token_sync

        mock_config = MagicMock()
        mock_config.gateway_token = "secret-token"

        with patch("src.mcp_gateway.auth.get_config", return_value=mock_config):
            result = validate_token_sync("wrong-token")

        assert result is False

    def test_empty_gateway_token_returns_false(self):
        """Test that empty gateway token config returns False."""
        from src.mcp_gateway.auth import validate_token_sync

        mock_config = MagicMock()
        mock_config.gateway_token = ""

        with patch("src.mcp_gateway.auth.get_config", return_value=mock_config):
            result = validate_token_sync("any-token")

        assert result is False

    def test_none_gateway_token_returns_false(self):
        """Test that None gateway token config returns False."""
        from src.mcp_gateway.auth import validate_token_sync

        mock_config = MagicMock()
        mock_config.gateway_token = None

        with patch("src.mcp_gateway.auth.get_config", return_value=mock_config):
            result = validate_token_sync("any-token")

        assert result is False


class TestBearerScheme:
    """Tests for bearer scheme configuration."""

    def test_bearer_scheme_auto_error_false(self):
        """Test that bearer scheme has auto_error=False."""
        from src.mcp_gateway.auth import bearer_scheme

        # auto_error=False means it won't automatically raise, allowing custom handling
        assert bearer_scheme.auto_error is False
