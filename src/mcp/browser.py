"""Browser MCP Server - Playwright-based web automation for agents.

Provides safe browser automation capabilities using Playwright in headless mode.
Agents can navigate, click, extract text, and capture screenshots.

Enhanced with Accessibility Tree support for 93% token reduction (exp_003).
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
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
            msg = (
                "playwright not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
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

    async def get_accessibility_tree(self) -> BrowserResult:
        """Get Accessibility Tree snapshot (93% token reduction vs DOM).

        Returns compact representation using ARIA roles and reference IDs (@e1, @e2, etc.)
        instead of full DOM. This approach is from exp_003 research.

        Returns:
            BrowserResult with accessibility tree in data field

        Example:
            >>> result = await server.get_accessibility_tree()
            >>> tree = result.data
            >>> # Find button: tree["children"][0]["ref"] -> "@e1"
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            # Get accessibility snapshot from Playwright
            snapshot = await self._page.accessibility.snapshot()

            # Add reference IDs for easier navigation
            ref_counter = [0]  # Use list for mutable counter in closure

            def add_refs(node: dict) -> dict:
                """Recursively add reference IDs to nodes."""
                if node is None:
                    return None
                ref_counter[0] += 1
                node["ref"] = f"@e{ref_counter[0]}"
                if "children" in node:
                    node["children"] = [add_refs(c) for c in node["children"] if c]
                return node

            tree = add_refs(snapshot) if snapshot else {"role": "document", "ref": "@e1", "children": []}

            # Compute hash for loop detection
            tree_hash = hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest()[:16]

            duration = (datetime.now(UTC) - start_time).total_seconds()
            token_estimate = len(json.dumps(tree)) // 4

            logger.info(
                "Accessibility tree: %d nodes, ~%d tokens, hash=%s (%.2fs)",
                ref_counter[0],
                token_estimate,
                tree_hash,
                duration,
            )

            return BrowserResult(
                tool="accessibility_tree",
                success=True,
                data={
                    "tree": tree,
                    "hash": tree_hash,
                    "node_count": ref_counter[0],
                    "token_estimate": token_estimate,
                },
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Accessibility tree failed: %s", e)
            return BrowserResult(
                tool="accessibility_tree",
                success=False,
                error=str(e),
                url=self._page.url if self._page else None,
                duration=duration,
            )

    async def click_by_ref(self, ref: str, timeout: int = 5000) -> BrowserResult:
        """Click element by accessibility reference ID.

        Args:
            ref: Reference ID from accessibility tree (e.g., "@e1", "@e3")
            timeout: Wait timeout in milliseconds

        Returns:
            BrowserResult with success status

        Example:
            >>> tree = await server.get_accessibility_tree()
            >>> # Find button ref from tree
            >>> result = await server.click_by_ref("@e3")
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            # Get accessibility tree to find element
            tree_result = await self.get_accessibility_tree()
            if not tree_result.success:
                raise RuntimeError(f"Could not get accessibility tree: {tree_result.error}")

            # Find element by ref
            def find_by_ref(node: dict, target_ref: str) -> dict | None:
                if node.get("ref") == target_ref:
                    return node
                for child in node.get("children", []):
                    found = find_by_ref(child, target_ref)
                    if found:
                        return found
                return None

            element = find_by_ref(tree_result.data["tree"], ref)
            if not element:
                raise ValueError(f"Element with ref {ref} not found in accessibility tree")

            # Use name or role to find and click
            name = element.get("name", "")
            role = element.get("role", "")

            # Try to click using accessible name
            if name:
                await self._page.get_by_role(role, name=name).click(timeout=timeout)
            else:
                # Fallback to role-based click
                await self._page.get_by_role(role).first.click(timeout=timeout)

            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info("Clicked ref %s (role=%s, name=%s) (%.2fs)", ref, role, name, duration)
            return BrowserResult(
                tool="click_by_ref",
                success=True,
                data={"ref": ref, "role": role, "name": name},
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Click by ref %s failed: %s", ref, e)
            return BrowserResult(
                tool="click_by_ref",
                success=False,
                error=str(e),
                data={"ref": ref},
                url=self._page.url if self._page else None,
                duration=duration,
            )

    async def fill_by_ref(self, ref: str, value: str) -> BrowserResult:
        """Fill input element by accessibility reference ID.

        Args:
            ref: Reference ID from accessibility tree
            value: Value to enter

        Returns:
            BrowserResult with success status

        Example:
            >>> result = await server.fill_by_ref("@e5", "test@example.com")
        """
        if not self._running:
            raise RuntimeError("BrowserServer not started")

        start_time = datetime.now(UTC)
        try:
            tree_result = await self.get_accessibility_tree()
            if not tree_result.success:
                raise RuntimeError(f"Could not get accessibility tree: {tree_result.error}")

            def find_by_ref(node: dict, target_ref: str) -> dict | None:
                if node.get("ref") == target_ref:
                    return node
                for child in node.get("children", []):
                    found = find_by_ref(child, target_ref)
                    if found:
                        return found
                return None

            element = find_by_ref(tree_result.data["tree"], ref)
            if not element:
                raise ValueError(f"Element with ref {ref} not found")

            name = element.get("name", "")
            role = element.get("role", "textbox")

            if name:
                await self._page.get_by_role(role, name=name).fill(value)
            else:
                await self._page.get_by_role(role).first.fill(value)

            duration = (datetime.now(UTC) - start_time).total_seconds()

            logger.info("Filled ref %s (%.2fs)", ref, duration)
            return BrowserResult(
                tool="fill_by_ref",
                success=True,
                data={"ref": ref, "value_length": len(value)},
                url=self._page.url,
                duration=duration,
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Fill by ref %s failed: %s", ref, e)
            return BrowserResult(
                tool="fill_by_ref",
                success=False,
                error=str(e),
                data={"ref": ref},
                url=self._page.url if self._page else None,
                duration=duration,
            )


@dataclass
class LoopDetector:
    """Detects action loops to prevent infinite cycling (from exp_003).

    Tracks recent actions and snapshot hashes to identify when the agent
    is stuck in a loop.
    """

    history_size: int = 10
    action_history: list = field(default_factory=list)
    hash_history: list = field(default_factory=list)

    def add_action(self, action: str, target: str, snapshot_hash: str = "") -> bool:
        """Add action and check for loops.

        Args:
            action: Action type (navigate, click, etc.)
            target: Action target (URL, ref, etc.)
            snapshot_hash: Hash of accessibility tree after action

        Returns:
            True if loop detected, False otherwise
        """
        action_key = f"{action}:{target}"
        self.action_history.append(action_key)
        if len(self.action_history) > self.history_size:
            self.action_history.pop(0)

        if snapshot_hash:
            self.hash_history.append(snapshot_hash)
            if len(self.hash_history) > self.history_size:
                self.hash_history.pop(0)

        return self._check_loop()

    def _check_loop(self) -> bool:
        """Check if recent actions indicate a loop."""
        if len(self.action_history) < 4:
            return False

        # Check for repeated action patterns
        recent = self.action_history[-4:]
        if len(set(recent)) <= 2:
            return True

        # Check for repeated snapshots
        if len(self.hash_history) >= 3:
            recent_hashes = self.hash_history[-3:]
            if len(set(recent_hashes)) == 1:
                return True

        return False

    def reset(self) -> None:
        """Reset loop detector state."""
        self.action_history.clear()
        self.hash_history.clear()


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
