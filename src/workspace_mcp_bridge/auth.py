"""Authentication for Google Workspace MCP Bridge."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

import httpx
from fastapi import HTTPException, Request

from src.workspace_mcp_bridge.config import WorkspaceConfig

logger = logging.getLogger(__name__)


class GoogleOAuthManager:
    """Manages Google OAuth tokens and authentication.

    Handles token refresh and provides access tokens for API calls.
    """

    OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"

    def __init__(self, config: WorkspaceConfig):
        """Initialize OAuth manager.

        Args:
            config: Workspace configuration with OAuth credentials
        """
        self.config = config
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed.

        Returns:
            Valid OAuth access token

        Raises:
            HTTPException: If token refresh fails
        """
        if self._is_token_valid():
            return self._access_token  # type: ignore

        return await self._refresh_token()

    def _is_token_valid(self) -> bool:
        """Check if current access token is valid.

        Returns:
            True if token exists and hasn't expired
        """
        if not self._access_token or not self._token_expiry:
            return False
        # Add 5 minute buffer before expiry
        return datetime.now(UTC) < (self._token_expiry - timedelta(minutes=5))

    async def _refresh_token(self) -> str:
        """Refresh the OAuth access token.

        Returns:
            New access token

        Raises:
            HTTPException: If refresh fails
        """
        if not self.config.oauth_refresh_token:
            raise HTTPException(
                status_code=401,
                detail="No OAuth refresh token configured",
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_ENDPOINT,
                data={
                    "client_id": self.config.oauth_client_id,
                    "client_secret": self.config.oauth_client_secret,
                    "refresh_token": self.config.oauth_refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                raise HTTPException(
                    status_code=401,
                    detail="Failed to refresh OAuth token",
                )

            data = response.json()
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expiry = datetime.now(UTC) + timedelta(seconds=expires_in)

            logger.info("OAuth token refreshed successfully")
            return self._access_token

    def get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers for API requests.

        Returns:
            Headers dict with Bearer token

        Note:
            This is synchronous and uses cached token.
            Call get_access_token() first to ensure token is valid.
        """
        if not self._access_token:
            raise HTTPException(
                status_code=401,
                detail="No access token available",
            )
        return {"Authorization": f"Bearer {self._access_token}"}


def verify_bridge_token(config: WorkspaceConfig) -> Callable:
    """Create a dependency that verifies the bridge token.

    Args:
        config: Workspace configuration with bridge token

    Returns:
        FastAPI dependency function
    """
    def verify(request: Request) -> bool:
        """Verify the Authorization header contains valid bridge token.

        Args:
            request: FastAPI request object

        Returns:
            True if token is valid

        Raises:
            HTTPException: If token is missing or invalid
        """
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header",
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        if not config.bridge_token:
            logger.warning("No bridge token configured - accepting all requests")
            return True

        if token != config.bridge_token:
            raise HTTPException(
                status_code=401,
                detail="Invalid bridge token",
            )

        return True

    return verify


def require_oauth(func: Callable) -> Callable:
    """Decorator to ensure OAuth token is available before calling.

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function that ensures token is valid
    """
    @wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self, "oauth_manager"):
            await self.oauth_manager.get_access_token()
        return await func(self, *args, **kwargs)
    return wrapper
