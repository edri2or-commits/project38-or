"""
Authentication for MCP Gateway.

Provides bearer token validation against GCP Secret Manager.
"""

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_config

# Security scheme for Bearer token
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    """
    Verify bearer token from request header.

    Args:
        credentials: HTTP Authorization credentials from request.

    Returns:
        The validated token string.

    Raises:
        HTTPException 401: If token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    config = get_config()
    expected_token = config.gateway_token

    if not expected_token:
        raise HTTPException(status_code=500, detail="Gateway token not configured")

    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


def validate_token_sync(token: str) -> bool:
    """
    Synchronously validate a token.

    Args:
        token: Token string to validate.

    Returns:
        True if valid, False otherwise.
    """
    config = get_config()
    expected_token = config.gateway_token

    if not expected_token:
        return False

    return token == expected_token
