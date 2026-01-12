"""Tests for MCP Tools components.

Tests browser, filesystem, notifications, and registry modules.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp.browser import BrowserResult, BrowserServer
from src.mcp.filesystem import FilesystemResult, FilesystemServer, FilesystemTool
from src.mcp.notifications import NotificationResult, NotificationServer, NotificationTool
from src.mcp.registry import ToolLimits, ToolRegistry, ToolUsage


class TestFilesystem:
    """Tests for FilesystemServer."""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self):
        """Test writing and reading files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = FilesystemServer(agent_id=1, base_path=Path(tmpdir))

            # Write file
            write_result = await server.write_file("test.txt", "Hello, World!")
            assert write_result.success is True
            assert write_result.tool == FilesystemTool.WRITE_FILE

            # Read file
            read_result = await server.read_file("test.txt")
            assert read_result.success is True
            assert read_result.data == "Hello, World!"
            assert read_result.tool == FilesystemTool.READ_FILE

    @pytest.mark.asyncio
    async def test_list_files(self):
        """Test listing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = FilesystemServer(agent_id=1, base_path=Path(tmpdir))

            # Create files
            await server.write_file("file1.txt", "content1")
            await server.write_file("file2.json", "content2")

            # List files
            result = await server.list_files()
            assert result.success is True
            assert len(result.data) == 2
            file_names = [f["name"] for f in result.data]
            assert "file1.txt" in file_names
            assert "file2.json" in file_names

    @pytest.mark.asyncio
    async def test_sandbox_escape_prevention(self):
        """Test path traversal prevention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = FilesystemServer(agent_id=1, base_path=Path(tmpdir))

            # Try to escape sandbox with ../
            result = await server.read_file("../etc/passwd")
            assert result.success is False
            assert "escapes sandbox" in result.error

            # Try to escape with absolute path
            result = await server.read_file("/etc/passwd")
            assert result.success is False
            assert "escapes sandbox" in result.error

    @pytest.mark.asyncio
    async def test_file_size_limit(self):
        """Test file size limits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = FilesystemServer(agent_id=1, base_path=Path(tmpdir))

            # Try to write file larger than limit
            large_content = "x" * (FilesystemServer.MAX_FILE_SIZE + 1)
            result = await server.write_file("large.txt", large_content)
            assert result.success is False
            assert "too large" in result.error

    @pytest.mark.asyncio
    async def test_create_dir(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = FilesystemServer(agent_id=1, base_path=Path(tmpdir))

            # Create nested directory
            result = await server.create_dir("data/processed")
            assert result.success is True

            # Write file to new directory
            write_result = await server.write_file("data/processed/output.txt", "data")
            assert write_result.success is True

    @pytest.mark.asyncio
    async def test_delete_file(self):
        """Test file deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = FilesystemServer(agent_id=1, base_path=Path(tmpdir))

            # Create and delete file
            await server.write_file("temp.txt", "temporary")
            delete_result = await server.delete_file("temp.txt")
            assert delete_result.success is True

            # Verify file is gone
            read_result = await server.read_file("temp.txt")
            assert read_result.success is False
            assert "not found" in read_result.error.lower()

    @pytest.mark.asyncio
    async def test_file_info(self):
        """Test getting file information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = FilesystemServer(agent_id=1, base_path=Path(tmpdir))

            # Create file and get info
            await server.write_file("test.txt", "Hello!")
            info_result = await server.file_info("test.txt")
            assert info_result.success is True
            assert info_result.data["name"] == "test.txt"
            assert info_result.data["is_file"] is True
            assert info_result.data["size"] == 6


class TestBrowser:
    """Tests for BrowserServer."""

    @pytest.mark.asyncio
    async def test_browser_initialization(self):
        """Test BrowserServer initialization."""
        server = BrowserServer(headless=True)
        assert server.headless is True
        assert server.is_running is False

    @pytest.mark.asyncio
    async def test_browser_start_fails_gracefully_without_playwright(self):
        """Test start fails gracefully if playwright not available."""
        server = BrowserServer()

        # Try to start - should fail with RuntimeError if playwright not installed
        # or if browsers not downloaded
        try:
            await server.start()
            # If we get here, playwright is fully installed - stop the server
            await server.stop()
        except RuntimeError as e:
            # Expected if playwright not installed
            assert "playwright not installed" in str(e)
        except Exception as e:
            # Also acceptable: browser binaries not downloaded
            # (playwright installed but not fully configured)
            assert "Executable doesn't exist" in str(e) or "playwright" in str(e).lower()

    @pytest.mark.asyncio
    async def test_navigate_without_start(self):
        """Test navigate fails if server not started."""
        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.navigate("https://example.com")

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        """Test navigate with invalid URL."""
        server = BrowserServer()

        # Mock server as running
        server._running = True

        with pytest.raises(ValueError, match="Invalid URL"):
            await server.navigate("not-a-url")


class TestNotifications:
    """Tests for NotificationServer."""

    @pytest.mark.asyncio
    async def test_send_telegram_success(self):
        """Test sending Telegram message."""
        server = NotificationServer(telegram_token="test_token")

        # Mock httpx response
        with patch.object(server._http_client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
            mock_post.return_value = mock_response

            result = await server.send_telegram(chat_id=123, message="Test")
            assert result.success is True
            assert result.tool == NotificationTool.SEND_TELEGRAM

    @pytest.mark.asyncio
    async def test_send_telegram_without_token(self):
        """Test Telegram without token."""
        server = NotificationServer(telegram_token=None)

        result = await server.send_telegram(chat_id=123, message="Test")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_n8n_webhook_success(self):
        """Test sending n8n webhook."""
        server = NotificationServer(n8n_webhook_url="https://n8n.example.com/webhook")

        # Mock httpx response
        with patch.object(server._http_client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b'{"status": "received"}'
            mock_response.json.return_value = {"status": "received"}
            mock_post.return_value = mock_response

            result = await server.send_n8n_webhook({"test": "data"})
            assert result.success is True
            assert result.tool == NotificationTool.SEND_N8N_WEBHOOK

    @pytest.mark.asyncio
    async def test_send_n8n_webhook_without_url(self):
        """Test n8n webhook without URL."""
        server = NotificationServer(n8n_webhook_url=None)

        result = await server.send_n8n_webhook({"test": "data"})
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_notification_server_context_manager(self):
        """Test NotificationServer as async context manager."""
        async with NotificationServer() as server:
            assert isinstance(server, NotificationServer)


class TestToolRegistry:
    """Tests for ToolRegistry."""

    @pytest.mark.asyncio
    async def test_register_agent(self):
        """Test registering agent."""
        registry = ToolRegistry()

        await registry.register_agent(
            agent_id=1,
            allowed_tools=["browser", "filesystem", "notifications"],
            telegram_token="test_token",
            n8n_webhook_url="https://n8n.example.com",
        )

        assert 1 in registry._agent_tools
        assert registry._agent_tools[1] == {"browser", "filesystem", "notifications"}

    @pytest.mark.asyncio
    async def test_register_agent_invalid_tools(self):
        """Test registering with invalid tools."""
        registry = ToolRegistry()

        with pytest.raises(ValueError, match="Invalid tool types"):
            await registry.register_agent(
                agent_id=1,
                allowed_tools=["invalid_tool"],
            )

    @pytest.mark.asyncio
    async def test_get_filesystem(self):
        """Test getting filesystem server."""
        registry = ToolRegistry()
        await registry.register_agent(agent_id=1, allowed_tools=["filesystem"])

        fs = await registry.get_filesystem(agent_id=1)
        assert isinstance(fs, FilesystemServer)
        assert fs.agent_id == 1

    @pytest.mark.asyncio
    async def test_get_filesystem_no_access(self):
        """Test getting filesystem without access."""
        registry = ToolRegistry()
        await registry.register_agent(agent_id=1, allowed_tools=["browser"])

        with pytest.raises(ValueError, match="does not have access"):
            await registry.get_filesystem(agent_id=1)

    @pytest.mark.asyncio
    async def test_get_notifications(self):
        """Test getting notification server."""
        registry = ToolRegistry()
        await registry.register_agent(
            agent_id=1,
            allowed_tools=["notifications"],
            telegram_token="test",
        )

        notif = await registry.get_notifications(agent_id=1)
        assert isinstance(notif, NotificationServer)

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting."""
        limits = ToolLimits(max_requests_per_minute=2, max_requests_per_hour=10)
        registry = ToolRegistry(limits=limits)
        await registry.register_agent(agent_id=1, allowed_tools=["filesystem"])

        # First 2 requests should succeed
        await registry.get_filesystem(agent_id=1)
        await registry.get_filesystem(agent_id=1)

        # Third request should fail (per-minute limit)
        with pytest.raises(RuntimeError, match="exceeded rate limit"):
            await registry.get_filesystem(agent_id=1)

    @pytest.mark.asyncio
    async def test_record_usage(self):
        """Test recording usage."""
        registry = ToolRegistry()

        registry.record_usage(
            agent_id=1,
            tool_type="browser",
            operation="navigate",
            success=True,
            duration=1.5,
        )

        stats = await registry.get_usage_stats(agent_id=1)
        assert stats["total_operations"] == 1
        assert stats["successful"] == 1
        assert stats["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_usage_stats_filtering(self):
        """Test usage stats filtering."""
        registry = ToolRegistry()

        # Record usage for different agents
        registry.record_usage(agent_id=1, tool_type="browser", operation="navigate", success=True)
        registry.record_usage(agent_id=2, tool_type="filesystem", operation="read", success=True)
        registry.record_usage(agent_id=1, tool_type="browser", operation="click", success=False)

        # Get stats for agent 1
        stats = await registry.get_usage_stats(agent_id=1)
        assert stats["total_operations"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1

        # Get stats for all agents
        all_stats = await registry.get_usage_stats()
        assert all_stats["total_operations"] == 3

    @pytest.mark.asyncio
    async def test_unregister_agent(self):
        """Test unregistering agent."""
        registry = ToolRegistry()
        await registry.register_agent(agent_id=1, allowed_tools=["filesystem"])

        await registry.unregister_agent(agent_id=1)

        assert 1 not in registry._agent_tools
        assert 1 not in registry._filesystem_servers

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test registry cleanup."""
        registry = ToolRegistry()
        await registry.register_agent(
            agent_id=1,
            allowed_tools=["notifications"],
            telegram_token="test",
        )

        await registry.cleanup()
        # Cleanup should not raise errors


class TestDataClasses:
    """Tests for data classes."""

    def test_filesystem_result_to_dict(self):
        """Test FilesystemResult serialization."""
        result = FilesystemResult(
            tool="read_file",
            success=True,
            data="content",
            path="/workspace/agent_1/test.txt",
        )

        data = result.to_dict()
        assert data["tool"] == "read_file"
        assert data["success"] is True
        assert data["data"] == "content"
        assert data["path"] == "/workspace/agent_1/test.txt"

    def test_browser_result_to_dict(self):
        """Test BrowserResult serialization."""
        result = BrowserResult(
            tool="navigate",
            success=True,
            url="https://example.com",
            duration=1.5,
        )

        data = result.to_dict()
        assert data["tool"] == "navigate"
        assert data["success"] is True
        assert data["url"] == "https://example.com"
        assert data["duration"] == 1.5

    def test_notification_result_to_dict(self):
        """Test NotificationResult serialization."""
        result = NotificationResult(
            tool="send_telegram",
            success=True,
            data={"message_id": 123},
        )

        data = result.to_dict()
        assert data["tool"] == "send_telegram"
        assert data["success"] is True
        assert data["data"] == {"message_id": 123}

    def test_tool_usage_to_dict(self):
        """Test ToolUsage serialization."""
        usage = ToolUsage(
            agent_id=1,
            tool_type="browser",
            operation="navigate",
            success=True,
            duration=1.5,
        )

        data = usage.to_dict()
        assert data["agent_id"] == 1
        assert data["tool_type"] == "browser"
        assert data["operation"] == "navigate"
        assert data["success"] is True


# Run tests with: pytest tests/test_mcp.py -v
