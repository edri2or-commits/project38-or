"""Browser MCP Server - Playwright-based web automation for agents.

Provides safe browser automation capabilities using Playwright in headless mode.
Agents can navigate, click, extract text, and capture screenshots.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BrowserTool(str, Enum):
    """Available browser automation tools."""

    NAVIGATE = "navigate"
    CLICK = "click"
    EXTRACT_TEXT = "extract_text"
    SCREENSHOT = "screenshot"
    FILL_FORM = "fill_form"
    WAIT_FOR_ELEMENT = "wait_for_element"


@dataclass
class BrowserResult:
    """Result from browser operation.

    Attributes:
        tool: Tool that was used
        success: Whether operation succeeded
        data: Extracted data (text, screenshot bytes, etc.)
        error: Error message if failed
        url: Current URL after operation
        duration: Operation duration in seconds
        timestamp: When operation completed
    """

    tool: str
    success: bool
    data: Any = None
    error: str | None = None
    url: str | None = None
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
            >>> result = BrowserResult(tool="navigate", success=True)
            >>> data = result.to_dict()
        """
        return {
            "tool": self.tool,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "url": self.url,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class BrowserServer:
    """Browser automation server using Playwright.

    Provides headless browser capabilities for agent automation.
    Supports navigation, element interaction, and data extraction.

    Example:
        >>> server = BrowserServer()
        >>> await server.start()
        >>> result = await server.navigate("https://example.com")
        >>> text = await server.extract_text("h1")
        >>> await server.stop()
    """

    def __init__(self, headless: bool = True):
        """Initialize browser server.

        Args:
            headless: Run browser in headless mode (default: True)

        Example:
            >>> server = BrowserServer(headless=True)
        """
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._running = False
        logger.info("BrowserServer initialized (headless=%s)", headless)

    async def start(self) -> None:
        """Start browser server.

        Launches Playwright browser instance and creates context.

        Raises:
            RuntimeError: If server already running or Playwright not available

        Example:
            >>> server = BrowserServer()
            >>> await server.start()
        """
        if self._running:
            raise RuntimeError("BrowserServer already running")

        try:
            # Dynamic import to avoid requiring playwright if not used
            from playwright.async_api import async_playwright
        except ImportError as e:
            msg = "playwright not installed. Run: pip install playwright && playwright install chromium"
            raise RuntimeError(msg) from e

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
            self._running = True
            logger.info("BrowserServer started successfully")
        except Exception as e:
            logger.error("Failed to start BrowserServer: %s", e)
            raise

    async def stop(self) -> None:
        """Stop browser server.

        Closes browser and cleans up resources.

        Example:
            >>> await server.stop()
        """
        if not self._running:
            return

        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error("Error stopping BrowserServer: %s", e)
        finally:
            self._running = False
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            logger.info("BrowserServer stopped")

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> BrowserResult:
        """Navigate to URL.

        Args:
            url: URL to navigate to
            wait_until: When to consider navigation complete
                       ('load', 'domcontentloaded', 'networkidle')

        Returns:
            BrowserResult with success status and current URL

        Raises:
            RuntimeError: If server not started
            ValueError: If URL is invalid

        Example:
            >>> result = await server.navigate("https://example.com")
            >>> print(result.success, result.url)
            True https://example.com/
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started. Call start() first.")

        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL: {url}")

        start_time = datetime.now(UTC)
        try:
            await self._page.goto(url, wait_until=wait_until, timeout=30000)
            current_url = self._page.url
            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info("Navigated to %s (%.2fs)", current_url, duration)
            return BrowserResult(
                tool=BrowserTool.NAVIGATE,
                success=True,
                url=current_url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Navigation to %s failed: %s", url, e)
            return BrowserResult(
                tool=BrowserTool.NAVIGATE,
                success=False,
                error=str(e),
                url=url,
                duration=duration,
            )

    async def click(self, selector: str, timeout: int = 5000) -> BrowserResult:
        """Click on element.

        Args:
            selector: CSS selector for element
            timeout: Wait timeout in milliseconds (default: 5000)

        Returns:
            BrowserResult with success status

        Example:
            >>> result = await server.click("button.submit")
            >>> print(result.success)
            True
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            await self._page.click(selector, timeout=timeout)
            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info("Clicked %s (%.2fs)", selector, duration)
            return BrowserResult(
                tool=BrowserTool.CLICK,
                success=True,
                data={"selector": selector},
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Click on %s failed: %s", selector, e)
            return BrowserResult(
                tool=BrowserTool.CLICK,
                success=False,
                error=str(e),
                data={"selector": selector},
                url=self._page.url,
                duration=duration,
            )

    async def extract_text(self, selector: str | None = None) -> BrowserResult:
        """Extract text from page or element.

        Args:
            selector: CSS selector for element (None = entire page)

        Returns:
            BrowserResult with extracted text in data field

        Example:
            >>> result = await server.extract_text("h1")
            >>> print(result.data)
            "Welcome to Example"
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            if selector:
                text = await self._page.locator(selector).text_content()
            else:
                text = await self._page.content()

            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info(
                "Extracted text from %s (%d chars, %.2fs)",
                selector or "page",
                len(text) if text else 0,
                duration,
            )
            return BrowserResult(
                tool=BrowserTool.EXTRACT_TEXT,
                success=True,
                data=text,
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Extract text from %s failed: %s", selector or "page", e)
            return BrowserResult(
                tool=BrowserTool.EXTRACT_TEXT,
                success=False,
                error=str(e),
                url=self._page.url,
                duration=duration,
            )

    async def screenshot(self, path: str | None = None, full_page: bool = False) -> BrowserResult:
        """Capture screenshot.

        Args:
            path: File path to save screenshot (None = return bytes)
            full_page: Capture full scrollable page (default: False)

        Returns:
            BrowserResult with screenshot bytes in data field

        Example:
            >>> result = await server.screenshot("/tmp/page.png")
            >>> print(result.success)
            True
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            screenshot_bytes = await self._page.screenshot(path=path, full_page=full_page)
            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info(
                "Screenshot captured (%s, %d bytes, %.2fs)",
                path or "bytes",
                len(screenshot_bytes),
                duration,
            )
            return BrowserResult(
                tool=BrowserTool.SCREENSHOT,
                success=True,
                data=screenshot_bytes if not path else {"path": path},
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Screenshot failed: %s", e)
            return BrowserResult(
                tool=BrowserTool.SCREENSHOT,
                success=False,
                error=str(e),
                url=self._page.url,
                duration=duration,
            )

    async def fill_form(self, selector: str, value: str) -> BrowserResult:
        """Fill form field.

        Args:
            selector: CSS selector for input field
            value: Value to enter

        Returns:
            BrowserResult with success status

        Example:
            >>> result = await server.fill_form("input[name='email']", "test@example.com")
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            await self._page.fill(selector, value)
            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info("Filled %s (%.2fs)", selector, duration)
            return BrowserResult(
                tool=BrowserTool.FILL_FORM,
                success=True,
                data={"selector": selector},
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Fill %s failed: %s", selector, e)
            return BrowserResult(
                tool=BrowserTool.FILL_FORM,
                success=False,
                error=str(e),
                data={"selector": selector},
                url=self._page.url,
                duration=duration,
            )

    async def wait_for_element(self, selector: str, timeout: int = 10000) -> BrowserResult:
        """Wait for element to appear.

        Args:
            selector: CSS selector for element
            timeout: Wait timeout in milliseconds (default: 10000)

        Returns:
            BrowserResult with success status

        Example:
            >>> result = await server.wait_for_element(".dynamic-content")
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info("Element %s appeared (%.2fs)", selector, duration)
            return BrowserResult(
                tool=BrowserTool.WAIT_FOR_ELEMENT,
                success=True,
                data={"selector": selector},
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Wait for %s failed: %s", selector, e)
            return BrowserResult(
                tool=BrowserTool.WAIT_FOR_ELEMENT,
                success=False,
                error=str(e),
                data={"selector": selector},
                url=self._page.url,
                duration=duration,
            )

    @property
    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if server is running

        Example:
            >>> if server.is_running:
            ...     await server.navigate("https://example.com")
        """
        return self._running

    @property
    def current_url(self) -> str | None:
        """Get current page URL.

        Returns:
            Current URL or None if not started

        Example:
            >>> url = server.current_url
        """
        return self._page.url if self._page else None


# Singleton instance
_global_server: BrowserServer | None = None


def get_browser_server(headless: bool = True) -> BrowserServer:
    """Get global BrowserServer singleton.

    Args:
        headless: Run in headless mode (default: True)

    Returns:
        Global BrowserServer instance

    Example:
        >>> server = get_browser_server()
        >>> await server.start()
    """
    global _global_server
    if _global_server is None:
        _global_server = BrowserServer(headless=headless)
    return _global_server
