"""Notification MCP Server - Telegram and n8n webhook integration for agents.

Provides notification capabilities via Telegram bot and n8n webhooks.
Agents can send alerts, status updates, and execution results.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NotificationTool(str, Enum):
    """Available notification tools."""

    SEND_TELEGRAM = "send_telegram"
    SEND_N8N_WEBHOOK = "send_n8n_webhook"


@dataclass
class NotificationResult:
    """Result from notification operation.

    Attributes:
        tool: Tool that was used
        success: Whether operation succeeded
        data: Response data from notification service
        error: Error message if failed
        duration: Operation duration in seconds
        timestamp: When operation completed
    """

    tool: str
    success: bool
    data: Any = None
    error: str | None = None
    duration: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        """Set default timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict:
        """Serialize to dictionary.

        Returns:
            Dictionary representation

        Example:
            >>> result = NotificationResult(tool="send_telegram", success=True)
            >>> data = result.to_dict()
        """
        return {
            "tool": self.tool,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class NotificationServer:
    """Notification server for Telegram and n8n webhooks.

    Provides agents with notification capabilities via:
    - Telegram bot (using python-telegram-bot)
    - n8n webhooks (using httpx)

    Example:
        >>> from src.secrets_manager import SecretManager
        >>> secrets = SecretManager()
        >>> telegram_token = secrets.get_secret("TELEGRAM-BOT-TOKEN")
        >>> n8n_url = secrets.get_secret("N8N-API")
        >>>
        >>> server = NotificationServer(
        ...     telegram_token=telegram_token,
        ...     n8n_webhook_url=n8n_url
        ... )
        >>> await server.send_telegram(chat_id=123, message="Task completed!")
    """

    def __init__(
        self,
        telegram_token: str | None = None,
        n8n_webhook_url: str | None = None,
    ):
        """Initialize notification server.

        Args:
            telegram_token: Telegram bot token (from TELEGRAM-BOT-TOKEN secret)
            n8n_webhook_url: n8n webhook URL (from N8N-API secret)

        Example:
            >>> server = NotificationServer(
            ...     telegram_token="1234567890:ABC...",
            ...     n8n_webhook_url="https://n8n.example.com/webhook/..."
            ... )
        """
        self.telegram_token = telegram_token
        self.n8n_webhook_url = n8n_webhook_url
        self._telegram_bot = None
        self._http_client = httpx.AsyncClient(timeout=10.0)

        logger.info(
            "NotificationServer initialized (telegram=%s, n8n=%s)",
            bool(telegram_token),
            bool(n8n_webhook_url),
        )

    async def send_telegram(
        self,
        chat_id: int | str,
        message: str,
        parse_mode: str = "Markdown",
    ) -> NotificationResult:
        """Send Telegram message.

        Args:
            chat_id: Telegram chat ID or @username
            message: Message text
            parse_mode: Parse mode (Markdown, HTML, or None)

        Returns:
            NotificationResult with success status

        Example:
            >>> result = await server.send_telegram(
            ...     chat_id=123456789,
            ...     message="✅ Task completed successfully!"
            ... )
        """
        start_time = datetime.now(UTC)

        if not self.telegram_token:
            return NotificationResult(
                tool=NotificationTool.SEND_TELEGRAM,
                success=False,
                error="Telegram token not configured",
                duration=0.0,
            )

        try:
            # Use telegram bot API directly via httpx (no dependency on python-telegram-bot)
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }

            response = await self._http_client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info(
                "Sent Telegram message to %s (%.2fs)",
                chat_id,
                duration,
            )

            return NotificationResult(
                tool=NotificationTool.SEND_TELEGRAM,
                success=True,
                data=data,
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Send Telegram to %s failed: %s", chat_id, e)
            return NotificationResult(
                tool=NotificationTool.SEND_TELEGRAM,
                success=False,
                error=str(e),
                duration=duration,
            )

    async def send_n8n_webhook(
        self,
        payload: dict,
        webhook_url: str | None = None,
    ) -> NotificationResult:
        """Send data to n8n webhook.

        Args:
            payload: JSON payload to send
            webhook_url: Webhook URL (uses default if not provided)

        Returns:
            NotificationResult with success status

        Example:
            >>> result = await server.send_n8n_webhook({
            ...     "agent_id": 1,
            ...     "status": "completed",
            ...     "result": {"processed": 100}
            ... })
        """
        start_time = datetime.now(UTC)

        webhook_url = webhook_url or self.n8n_webhook_url

        if not webhook_url:
            return NotificationResult(
                tool=NotificationTool.SEND_N8N_WEBHOOK,
                success=False,
                error="n8n webhook URL not configured",
                duration=0.0,
            )

        try:
            response = await self._http_client.post(webhook_url, json=payload)
            response.raise_for_status()

            data = response.json() if response.content else {"status": "sent"}
            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info(
                "Sent n8n webhook (%d bytes, %.2fs)",
                len(response.content),
                duration,
            )

            return NotificationResult(
                tool=NotificationTool.SEND_N8N_WEBHOOK,
                success=True,
                data=data,
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Send n8n webhook failed: %s", e)
            return NotificationResult(
                tool=NotificationTool.SEND_N8N_WEBHOOK,
                success=False,
                error=str(e),
                duration=duration,
            )

    async def close(self) -> None:
        """Close HTTP client.

        Example:
            >>> await server.close()
        """
        if self._http_client:
            await self._http_client.aclose()
            logger.info("NotificationServer closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Convenience functions


async def send_telegram_notification(
    message: str,
    chat_id: int | str,
    telegram_token: str,
) -> bool:
    """Send Telegram notification (convenience function).

    Args:
        message: Message text
        chat_id: Telegram chat ID
        telegram_token: Bot token

    Returns:
        True if successful, False otherwise

    Example:
        >>> from src.secrets_manager import SecretManager
        >>> secrets = SecretManager()
        >>> token = secrets.get_secret("TELEGRAM-BOT-TOKEN")
        >>> success = await send_telegram_notification(
        ...     "Task completed!",
        ...     chat_id=123456789,
        ...     telegram_token=token
        ... )
    """
    async with NotificationServer(telegram_token=telegram_token) as server:
        result = await server.send_telegram(chat_id=chat_id, message=message)
        return result.success


async def send_n8n_notification(
    payload: dict,
    webhook_url: str,
) -> bool:
    """Send n8n webhook notification (convenience function).

    Args:
        payload: JSON payload
        webhook_url: Webhook URL

    Returns:
        True if successful, False otherwise

    Example:
        >>> from src.secrets_manager import SecretManager
        >>> secrets = SecretManager()
        >>> webhook = secrets.get_secret("N8N-API")
        >>> success = await send_n8n_notification(
        ...     {"status": "completed"},
        ...     webhook_url=webhook
        ... )
    """
    async with NotificationServer(n8n_webhook_url=webhook_url) as server:
        result = await server.send_n8n_webhook(payload=payload)
        return result.success
