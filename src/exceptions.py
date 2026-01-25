"""
Unified Exception Hierarchy for project38-or.

This module provides a common exception hierarchy to replace the duplicated
exception classes found across multiple client modules (railway_client,
github_app_client, n8n_client, providers/base, etc.).

Usage:
    from src.exceptions import (
        APIClientError,
        AuthenticationError,
        RateLimitError,
        NotFoundError,
        ValidationError,
        TimeoutError,
    )

    try:
        await client.some_operation()
    except RateLimitError:
        # Handle rate limit - works for ANY client
        await backoff()
    except AuthenticationError:
        # Handle auth failure - works for ANY client
        refresh_token()

Note:
    This module was created as part of system audit (AUD-007) to consolidate
    28 duplicate exception classes across 7 modules into a single hierarchy.

    Existing module-specific exceptions remain for backwards compatibility,
    but new code should use these unified exceptions.
"""

from typing import Any


class APIClientError(Exception):
    """Base exception for all API client errors.

    All client-specific exceptions should inherit from this class.
    This allows catching any client error with a single except clause.

    Attributes:
        message: Human-readable error description.
        details: Optional dict with additional error context.
        status_code: HTTP status code if applicable.
        service: Name of the service that raised the error.
    """

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        service: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        self.service = service

    def __str__(self) -> str:
        parts = [self.message]
        if self.service:
            parts.insert(0, f"[{self.service}]")
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)


class AuthenticationError(APIClientError):
    """Authentication failed.

    Raised when:
    - API key/token is invalid or expired
    - JWT generation fails
    - OAuth token refresh fails
    - Service account credentials are invalid

    Example:
        try:
            await client.authenticate()
        except AuthenticationError as e:
            logger.error(f"Auth failed: {e}")
            await refresh_credentials()
    """
    pass


class RateLimitError(APIClientError):
    """Rate limit exceeded.

    Raised when the API rate limit is exceeded. Check the retry_after
    attribute for when to retry.

    Attributes:
        retry_after: Seconds to wait before retrying (if provided by API).

    Example:
        try:
            await client.make_request()
        except RateLimitError as e:
            wait_time = e.retry_after or 60
            await asyncio.sleep(wait_time)
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class NotFoundError(APIClientError):
    """Resource not found.

    Raised when:
    - Requested resource doesn't exist (HTTP 404)
    - Secret not found in Secret Manager
    - Workflow/deployment not found

    Attributes:
        resource_type: Type of resource (e.g., "secret", "deployment").
        resource_id: Identifier of the missing resource.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, status_code=404, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(APIClientError):
    """Input validation failed.

    Raised when:
    - Request parameters are invalid
    - Configuration values are malformed
    - Schema validation fails

    Attributes:
        field: Name of the field that failed validation.
        value: The invalid value (sanitized - never include secrets).
    """

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        field: str | None = None,
        value: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, status_code=400, **kwargs)
        self.field = field
        # Sanitize value - never include potential secrets
        self.value = str(value)[:100] if value is not None else None


class TimeoutError(APIClientError):  # noqa: A001 - intentionally shadows builtin
    """Operation timed out.

    Raised when an API call or operation exceeds its timeout.

    Attributes:
        timeout_seconds: The timeout that was exceeded.
        operation: Description of the operation that timed out.

    Note:
        This intentionally shadows the builtin TimeoutError for API consistency.
        Use builtins.TimeoutError if you need the standard exception.
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        *,
        timeout_seconds: float | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, status_code=408, **kwargs)
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class ConfigurationError(APIClientError):
    """Configuration is invalid or missing.

    Raised when:
    - Required environment variables are missing
    - Configuration file is malformed
    - Service configuration is incomplete
    """
    pass


class DeploymentError(APIClientError):
    """Deployment operation failed.

    Raised when:
    - Railway deployment fails
    - Cloud Run deployment fails
    - Service scaling fails

    Attributes:
        deployment_id: ID of the failed deployment.
        stage: Stage at which deployment failed.
    """

    def __init__(
        self,
        message: str = "Deployment failed",
        *,
        deployment_id: str | None = None,
        stage: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.deployment_id = deployment_id
        self.stage = stage


class WebhookError(APIClientError):
    """Webhook operation failed.

    Raised when:
    - Webhook delivery fails
    - Webhook URL is unreachable
    - Webhook response is invalid
    """
    pass


# Type aliases for backwards compatibility
# Modules can import these instead of defining their own
ClientError = APIClientError

__all__ = [
    "APIClientError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
    "TimeoutError",
    "ConfigurationError",
    "DeploymentError",
    "WebhookError",
    "ClientError",
]
