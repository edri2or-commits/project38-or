"""Tests for MCP Notifications module.

Tests the notifications module in src/mcp/notifications.py.
Covers:
- NotificationResult dataclass
- NotificationServer initialization and methods
- Telegram message sending
- n8n webhook sending
- Convenience functions
- Error handling
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestNotificationTool:
    """Tests for NotificationTool enum."""

    def test_notification_tool_values(self):
        """Test that NotificationTool has expected values."""
        from src.mcp.notifications import NotificationTool

        assert NotificationTool.SEND_TELEGRAM == "send_telegram"
        assert NotificationTool.SEND_N8N_WEBHOOK == "send_n8n_webhook"


class TestNotificationResult:
    """Tests for NotificationResult dataclass."""

    def test_default_values(self):
        """Test that NotificationResult initializes with correct defaults."""
        from src.mcp.notifications import NotificationResult

        result = NotificationResult(tool="test", success=True)

        assert result.tool == "test"
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.duration == 0.0
        assert result.timestamp is not None

    def test_timestamp_auto_set(self):
        """Test that timestamp is auto-set on initialization."""
        from src.mcp.notifications import NotificationResult

        before = datetime.now(UTC)
        result = NotificationResult(tool="test", success=True)
        after = datetime.now(UTC)

        assert before <= result.timestamp <= after

    def test_to_dict(self):
        """Test that to_dict returns correct structure."""
        from src.mcp.notifications import NotificationResult

        result = NotificationResult(
            tool="send_telegram",
            success=True,
            data={"message_id": 123},
            duration=0.5,
        )

        data = result.to_dict()

        assert data["tool"] == "send_telegram"
        assert data["success"] is True
        assert data["data"] == {"message_id": 123}
        assert data["error"] is None
        assert data["duration"] == 0.5
        assert "timestamp" in data

    def test_to_dict_with_error(self):
        """Test to_dict includes error message."""
        from src.mcp.notifications import NotificationResult

        result = NotificationResult(
            tool="send_telegram",
            success=False,
            error="Connection timeout",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["error"] == "Connection timeout"


class TestNotificationServer:
    """Tests for NotificationServer class."""

    def test_init_no_credentials(self):
        """Test initialization without credentials."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer()

        assert server.telegram_token is None
        assert server.n8n_webhook_url is None

    def test_init_with_credentials(self):
        """Test initialization with credentials."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer(
            telegram_token="test-token",
            n8n_webhook_url="https://n8n.test/webhook",
        )

        assert server.telegram_token == "test-token"
        assert server.n8n_webhook_url == "https://n8n.test/webhook"

    @pytest.mark.asyncio
    async def test_send_telegram_no_token(self):
        """Test send_telegram returns error when token not configured."""
        from src.mcp.notifications import NotificationServer, NotificationTool

        server = NotificationServer(telegram_token=None)

        result = await server.send_telegram(chat_id=123, message="Test")

        assert result.success is False
        assert result.tool == NotificationTool.SEND_TELEGRAM
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_telegram_success(self):
        """Test successful Telegram message sending."""
        from src.mcp.notifications import NotificationServer, NotificationTool

        server = NotificationServer(telegram_token="test-token")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 456}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await server.send_telegram(chat_id=123, message="Hello!")

        assert result.success is True
        assert result.tool == NotificationTool.SEND_TELEGRAM
        assert result.data["ok"] is True
        assert result.duration > 0

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "bot" in call_args[0][0]
        assert "test-token" in call_args[0][0]
        assert call_args[1]["json"]["chat_id"] == 123
        assert call_args[1]["json"]["text"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_telegram_with_parse_mode(self):
        """Test Telegram message with custom parse mode."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer(telegram_token="test-token")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await server.send_telegram(
                chat_id=123,
                message="<b>Bold</b>",
                parse_mode="HTML",
            )

        call_args = mock_post.call_args
        assert call_args[1]["json"]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_send_telegram_http_error(self):
        """Test Telegram error handling."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer(telegram_token="test-token")

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Connection failed")
            result = await server.send_telegram(chat_id=123, message="Test")

        assert result.success is False
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_send_n8n_webhook_no_url(self):
        """Test send_n8n_webhook returns error when URL not configured."""
        from src.mcp.notifications import NotificationServer, NotificationTool

        server = NotificationServer(n8n_webhook_url=None)

        result = await server.send_n8n_webhook(payload={"test": "data"})

        assert result.success is False
        assert result.tool == NotificationTool.SEND_N8N_WEBHOOK
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_n8n_webhook_success(self):
        """Test successful n8n webhook sending."""
        from src.mcp.notifications import NotificationServer, NotificationTool

        server = NotificationServer(n8n_webhook_url="https://n8n.test/webhook")

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.content = b'{"success": true}'
        mock_response.raise_for_status = MagicMock()

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await server.send_n8n_webhook(payload={"agent_id": 1})

        assert result.success is True
        assert result.tool == NotificationTool.SEND_N8N_WEBHOOK
        assert result.data["success"] is True

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://n8n.test/webhook"
        assert call_args[1]["json"] == {"agent_id": 1}

    @pytest.mark.asyncio
    async def test_send_n8n_webhook_custom_url(self):
        """Test n8n webhook with custom URL override."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer(n8n_webhook_url="https://default.url")

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = MagicMock()

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await server.send_n8n_webhook(
                payload={},
                webhook_url="https://custom.url/webhook",
            )

        call_args = mock_post.call_args
        assert call_args[0][0] == "https://custom.url/webhook"

    @pytest.mark.asyncio
    async def test_send_n8n_webhook_empty_response(self):
        """Test n8n webhook handles empty response body."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer(n8n_webhook_url="https://n8n.test/webhook")

        mock_response = MagicMock()
        mock_response.content = b''  # Empty content
        mock_response.raise_for_status = MagicMock()

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await server.send_n8n_webhook(payload={"test": True})

        assert result.success is True
        assert result.data == {"status": "sent"}

    @pytest.mark.asyncio
    async def test_send_n8n_webhook_http_error(self):
        """Test n8n webhook error handling."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer(n8n_webhook_url="https://n8n.test/webhook")

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Server error")
            result = await server.send_n8n_webhook(payload={})

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_close(self):
        """Test close method closes HTTP client."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer()

        with patch.object(server._http_client, "aclose", new_callable=AsyncMock) as mock_close:
            await server.close()

        mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager protocol."""
        from src.mcp.notifications import NotificationServer

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with NotificationServer() as server:
                assert server is not None

            mock_client.aclose.assert_called_once()


class TestSendTelegramNotification:
    """Tests for send_telegram_notification convenience function."""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful notification via convenience function."""
        from src.mcp.notifications import send_telegram_notification

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            success = await send_telegram_notification(
                message="Test message",
                chat_id=123456789,
                telegram_token="test-token",
            )

        assert success is True

    @pytest.mark.asyncio
    async def test_failure(self):
        """Test failed notification returns False."""
        from src.mcp.notifications import send_telegram_notification

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=Exception("Failed"))
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            success = await send_telegram_notification(
                message="Test",
                chat_id=123,
                telegram_token="test-token",
            )

        assert success is False


class TestSendN8nNotification:
    """Tests for send_n8n_notification convenience function."""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful webhook via convenience function."""
        from src.mcp.notifications import send_n8n_notification

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.content = b'{"success": true}'
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            success = await send_n8n_notification(
                payload={"test": "data"},
                webhook_url="https://n8n.test/webhook",
            )

        assert success is True

    @pytest.mark.asyncio
    async def test_failure(self):
        """Test failed webhook returns False."""
        from src.mcp.notifications import send_n8n_notification

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=Exception("Failed"))
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            success = await send_n8n_notification(
                payload={},
                webhook_url="https://n8n.test/webhook",
            )

        assert success is False


class TestIntegration:
    """Integration tests for notifications module."""

    @pytest.mark.asyncio
    async def test_both_notifications(self):
        """Test sending both Telegram and n8n notifications."""
        from src.mcp.notifications import NotificationServer

        server = NotificationServer(
            telegram_token="test-token",
            n8n_webhook_url="https://n8n.test/webhook",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.content = b'{"ok": true}'
        mock_response.raise_for_status = MagicMock()

        with patch.object(server._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            telegram_result = await server.send_telegram(chat_id=123, message="Test")
            n8n_result = await server.send_n8n_webhook(payload={"status": "done"})

        assert telegram_result.success is True
        assert n8n_result.success is True
        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_result_serialization(self):
        """Test that results can be serialized to JSON."""
        import json

        from src.mcp.notifications import NotificationResult

        result = NotificationResult(
            tool="send_telegram",
            success=True,
            data={"message_id": 123},
            duration=0.5,
        )

        # Should serialize without error
        json_str = json.dumps(result.to_dict(), default=str)
        parsed = json.loads(json_str)

        assert parsed["tool"] == "send_telegram"
        assert parsed["success"] is True
