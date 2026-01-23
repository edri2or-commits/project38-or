"""Tests for MCP Browser module.

Tests the browser automation module in src/mcp/browser.py.
Covers:
- BrowserTool enum
- BrowserResult dataclass
- BrowserServer initialization and operations
- LoopDetector functionality
- Accessibility tree operations
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBrowserTool:
    """Tests for BrowserTool enum."""

    def test_browser_tool_values(self):
        """Test that BrowserTool has expected values."""
        from src.mcp.browser import BrowserTool

        assert BrowserTool.NAVIGATE == "navigate"
        assert BrowserTool.CLICK == "click"
        assert BrowserTool.EXTRACT_TEXT == "extract_text"
        assert BrowserTool.SCREENSHOT == "screenshot"
        assert BrowserTool.FILL_FORM == "fill_form"
        assert BrowserTool.WAIT_FOR_ELEMENT == "wait_for_element"


class TestBrowserResult:
    """Tests for BrowserResult dataclass."""

    def test_default_values(self):
        """Test that BrowserResult initializes with correct defaults."""
        from src.mcp.browser import BrowserResult

        result = BrowserResult(tool="navigate", success=True)

        assert result.tool == "navigate"
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.url is None
        assert result.duration == 0.0
        assert result.timestamp is not None

    def test_timestamp_auto_set(self):
        """Test that timestamp is auto-set on initialization."""
        from src.mcp.browser import BrowserResult

        before = datetime.now(UTC)
        result = BrowserResult(tool="navigate", success=True)
        after = datetime.now(UTC)

        assert before <= result.timestamp <= after

    def test_to_dict(self):
        """Test that to_dict returns correct structure."""
        from src.mcp.browser import BrowserResult

        result = BrowserResult(
            tool="navigate",
            success=True,
            data={"key": "value"},
            url="https://example.com",
            duration=0.5,
        )

        data = result.to_dict()

        assert data["tool"] == "navigate"
        assert data["success"] is True
        assert data["data"] == {"key": "value"}
        assert data["error"] is None
        assert data["url"] == "https://example.com"
        assert data["duration"] == 0.5
        assert "timestamp" in data

    def test_to_dict_with_error(self):
        """Test to_dict includes error message."""
        from src.mcp.browser import BrowserResult

        result = BrowserResult(
            tool="navigate",
            success=False,
            error="Navigation timeout",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["error"] == "Navigation timeout"


class TestBrowserServer:
    """Tests for BrowserServer class."""

    def test_init_default_headless(self):
        """Test initialization with default headless mode."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        assert server.headless is True
        assert server._running is False
        assert server._playwright is None
        assert server._browser is None
        assert server._page is None

    def test_init_headless_false(self):
        """Test initialization with headless=False."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer(headless=False)

        assert server.headless is False

    def test_is_running_property(self):
        """Test is_running property."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        assert server.is_running is False

        server._running = True
        assert server.is_running is True

    def test_current_url_not_started(self):
        """Test current_url when not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        assert server.current_url is None

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test start raises error if already running."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True

        with pytest.raises(RuntimeError, match="already running"):
            await server.start()

    @pytest.mark.asyncio
    async def test_start_playwright_not_installed(self):
        """Test start raises error if playwright not installed."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            # Force import to fail
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(RuntimeError, match="playwright not installed"):
                    await server.start()

    @pytest.mark.asyncio
    async def test_navigate_not_started(self):
        """Test navigate raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.navigate("https://example.com")

    @pytest.mark.asyncio
    async def test_navigate_invalid_url(self):
        """Test navigate raises error for invalid URL."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True

        with pytest.raises(ValueError, match="Invalid URL"):
            await server.navigate("not-a-url")

    @pytest.mark.asyncio
    async def test_navigate_success(self):
        """Test successful navigation with mocked page."""
        from src.mcp.browser import BrowserServer, BrowserTool

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.goto = AsyncMock()
        server._page.url = "https://example.com/"

        result = await server.navigate("https://example.com")

        assert result.success is True
        assert result.tool == BrowserTool.NAVIGATE
        assert result.url == "https://example.com/"
        server._page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_failure(self):
        """Test navigation failure."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.goto = AsyncMock(side_effect=Exception("Timeout"))

        result = await server.navigate("https://example.com")

        assert result.success is False
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_click_not_started(self):
        """Test click raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.click("button")

    @pytest.mark.asyncio
    async def test_click_success(self):
        """Test successful click."""
        from src.mcp.browser import BrowserServer, BrowserTool

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.click = AsyncMock()
        server._page.url = "https://example.com/"

        result = await server.click("button.submit")

        assert result.success is True
        assert result.tool == BrowserTool.CLICK
        assert result.data["selector"] == "button.submit"

    @pytest.mark.asyncio
    async def test_click_failure(self):
        """Test click failure."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.click = AsyncMock(side_effect=Exception("Element not found"))
        server._page.url = "https://example.com/"

        result = await server.click("button.missing")

        assert result.success is False
        assert "Element not found" in result.error

    @pytest.mark.asyncio
    async def test_extract_text_not_started(self):
        """Test extract_text raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.extract_text("h1")

    @pytest.mark.asyncio
    async def test_extract_text_with_selector(self):
        """Test extract text from specific selector."""
        from src.mcp.browser import BrowserServer, BrowserTool

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()

        mock_locator = MagicMock()
        mock_locator.text_content = AsyncMock(return_value="Hello World")
        server._page.locator.return_value = mock_locator
        server._page.url = "https://example.com/"

        result = await server.extract_text("h1")

        assert result.success is True
        assert result.tool == BrowserTool.EXTRACT_TEXT
        assert result.data == "Hello World"

    @pytest.mark.asyncio
    async def test_extract_text_full_page(self):
        """Test extract text from full page."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.content = AsyncMock(return_value="<html>...</html>")
        server._page.url = "https://example.com/"

        result = await server.extract_text()

        assert result.success is True
        assert result.data == "<html>...</html>"

    @pytest.mark.asyncio
    async def test_screenshot_not_started(self):
        """Test screenshot raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.screenshot()

    @pytest.mark.asyncio
    async def test_screenshot_success(self):
        """Test successful screenshot."""
        from src.mcp.browser import BrowserServer, BrowserTool

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.screenshot = AsyncMock(return_value=b"PNG data")
        server._page.url = "https://example.com/"

        result = await server.screenshot()

        assert result.success is True
        assert result.tool == BrowserTool.SCREENSHOT
        assert result.data == b"PNG data"

    @pytest.mark.asyncio
    async def test_screenshot_to_file(self):
        """Test screenshot saved to file."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.screenshot = AsyncMock(return_value=b"PNG data")
        server._page.url = "https://example.com/"

        result = await server.screenshot(path="/tmp/test.png")

        assert result.success is True
        assert result.data == {"path": "/tmp/test.png"}

    @pytest.mark.asyncio
    async def test_fill_form_not_started(self):
        """Test fill_form raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.fill_form("input", "value")

    @pytest.mark.asyncio
    async def test_fill_form_success(self):
        """Test successful form fill."""
        from src.mcp.browser import BrowserServer, BrowserTool

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.fill = AsyncMock()
        server._page.url = "https://example.com/"

        result = await server.fill_form("input[name='email']", "test@example.com")

        assert result.success is True
        assert result.tool == BrowserTool.FILL_FORM
        server._page.fill.assert_called_once_with("input[name='email']", "test@example.com")

    @pytest.mark.asyncio
    async def test_wait_for_element_not_started(self):
        """Test wait_for_element raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.wait_for_element(".loading")

    @pytest.mark.asyncio
    async def test_wait_for_element_success(self):
        """Test successful wait for element."""
        from src.mcp.browser import BrowserServer, BrowserTool

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.wait_for_selector = AsyncMock()
        server._page.url = "https://example.com/"

        result = await server.wait_for_element(".content")

        assert result.success is True
        assert result.tool == BrowserTool.WAIT_FOR_ELEMENT
        assert result.data["selector"] == ".content"

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stop when not running does nothing."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        await server.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_success(self):
        """Test successful stop."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.close = AsyncMock()
        server._context = MagicMock()
        server._context.close = AsyncMock()
        server._browser = MagicMock()
        server._browser.close = AsyncMock()
        server._playwright = MagicMock()
        server._playwright.stop = AsyncMock()

        await server.stop()

        assert server._running is False
        assert server._page is None
        assert server._context is None
        assert server._browser is None
        assert server._playwright is None


class TestAccessibilityTree:
    """Tests for accessibility tree operations."""

    @pytest.mark.asyncio
    async def test_get_accessibility_tree_not_started(self):
        """Test get_accessibility_tree raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.get_accessibility_tree()

    @pytest.mark.asyncio
    async def test_get_accessibility_tree_success(self):
        """Test successful accessibility tree retrieval."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.accessibility = MagicMock()
        server._page.accessibility.snapshot = AsyncMock(
            return_value={
                "role": "document",
                "name": "Test Page",
                "children": [{"role": "heading", "name": "Title"}],
            }
        )
        server._page.url = "https://example.com/"

        result = await server.get_accessibility_tree()

        assert result.success is True
        assert result.tool == "accessibility_tree"
        assert "tree" in result.data
        assert "hash" in result.data
        assert "node_count" in result.data
        assert result.data["tree"]["ref"] == "@e1"

    @pytest.mark.asyncio
    async def test_get_accessibility_tree_empty(self):
        """Test accessibility tree with None snapshot."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()
        server._running = True
        server._page = MagicMock()
        server._page.accessibility = MagicMock()
        server._page.accessibility.snapshot = AsyncMock(return_value=None)
        server._page.url = "https://example.com/"

        result = await server.get_accessibility_tree()

        assert result.success is True
        assert result.data["tree"]["role"] == "document"

    @pytest.mark.asyncio
    async def test_click_by_ref_not_started(self):
        """Test click_by_ref raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.click_by_ref("@e1")

    @pytest.mark.asyncio
    async def test_fill_by_ref_not_started(self):
        """Test fill_by_ref raises error if not started."""
        from src.mcp.browser import BrowserServer

        server = BrowserServer()

        with pytest.raises(RuntimeError, match="not started"):
            await server.fill_by_ref("@e1", "value")


class TestLoopDetector:
    """Tests for LoopDetector class."""

    def test_initialization(self):
        """Test LoopDetector initialization."""
        from src.mcp.browser import LoopDetector

        detector = LoopDetector()

        assert detector.history_size == 10
        assert detector.action_history == []
        assert detector.hash_history == []

    def test_custom_history_size(self):
        """Test LoopDetector with custom history size."""
        from src.mcp.browser import LoopDetector

        detector = LoopDetector(history_size=5)

        assert detector.history_size == 5

    def test_add_action_no_loop(self):
        """Test adding actions without loop detection."""
        from src.mcp.browser import LoopDetector

        detector = LoopDetector()

        # Add diverse actions
        assert detector.add_action("navigate", "url1") is False
        assert detector.add_action("click", "button1") is False
        assert detector.add_action("fill", "input1") is False

    def test_add_action_detects_loop(self):
        """Test loop detection with repeated actions."""
        from src.mcp.browser import LoopDetector

        detector = LoopDetector()

        # Add same action repeatedly
        detector.add_action("click", "button1")
        detector.add_action("click", "button1")
        detector.add_action("click", "button1")
        result = detector.add_action("click", "button1")

        assert result is True  # Loop detected

    def test_add_action_hash_loop(self):
        """Test loop detection via repeated hashes."""
        from src.mcp.browser import LoopDetector

        detector = LoopDetector()

        # Add actions with same hash - need 4 to trigger detection
        # (loop detection requires 4 actions with <= 2 unique types)
        detector.add_action("click", "btn1", "hash123")
        detector.add_action("click", "btn2", "hash123")
        detector.add_action("click", "btn3", "hash123")
        result = detector.add_action("click", "btn4", "hash123")

        assert result is True  # Identical snapshots detected

    def test_history_limit(self):
        """Test history doesn't exceed limit."""
        from src.mcp.browser import LoopDetector

        detector = LoopDetector(history_size=5)

        # Add more than history_size actions
        for i in range(10):
            detector.add_action("navigate", f"url{i}")

        assert len(detector.action_history) == 5

    def test_reset(self):
        """Test reset clears history."""
        from src.mcp.browser import LoopDetector

        detector = LoopDetector()

        detector.add_action("navigate", "url1")
        detector.add_action("click", "button1", "hash1")

        detector.reset()

        assert detector.action_history == []
        assert detector.hash_history == []


class TestGetBrowserServer:
    """Tests for get_browser_server singleton function."""

    def test_returns_singleton(self):
        """Test that get_browser_server returns singleton instance."""
        from src.mcp import browser

        # Reset global
        browser._global_server = None

        server1 = browser.get_browser_server()
        server2 = browser.get_browser_server()

        assert server1 is server2

        # Cleanup
        browser._global_server = None

    def test_respects_headless_on_first_call(self):
        """Test headless setting on first call."""
        from src.mcp import browser

        browser._global_server = None

        server = browser.get_browser_server(headless=False)

        assert server.headless is False

        browser._global_server = None
