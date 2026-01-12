"""Agent Tool Registry - Manages MCP tool access and usage tracking.

Provides centralized registry for agent tool access, usage tracking,
rate limiting, and cost attribution.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from .browser import BrowserServer
from .filesystem import FilesystemServer
from .notifications import NotificationServer

logger = logging.getLogger(__name__)


class ToolType(str, Enum):
    """Available tool types."""

    BROWSER = "browser"
    FILESYSTEM = "filesystem"
    NOTIFICATIONS = "notifications"


@dataclass
class ToolUsage:
    """Record of tool usage by agent.

    Attributes:
        agent_id: Agent ID
        tool_type: Type of tool used
        operation: Specific operation (navigate, read_file, etc.)
        success: Whether operation succeeded
        duration: Operation duration in seconds
        timestamp: When operation occurred
        data: Additional usage data (bytes transferred, etc.)
    """

    agent_id: int
    tool_type: str
    operation: str
    success: bool
    duration: float = 0.0
    timestamp: datetime = None
    data: dict = field(default_factory=dict)

    def __post_init__(self):
        """Set default timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict:
        """Serialize to dictionary.

        Returns:
            Dictionary representation

        Example:
            >>> usage = ToolUsage(agent_id=1, tool_type="browser", operation="navigate", success=True)
            >>> data = usage.to_dict()
        """
        return {
            "agent_id": self.agent_id,
            "tool_type": self.tool_type,
            "operation": self.operation,
            "success": self.success,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "data": self.data,
        }


@dataclass
class ToolLimits:
    """Rate limits for tool usage.

    Attributes:
        max_requests_per_minute: Max operations per minute (default: 60)
        max_requests_per_hour: Max operations per hour (default: 1000)
        max_browser_sessions: Max concurrent browser sessions (default: 2)
        max_file_size_mb: Max file size in MB (default: 10)
        max_notification_per_hour: Max notifications per hour (default: 100)
    """

    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    max_browser_sessions: int = 2
    max_file_size_mb: int = 10
    max_notifications_per_hour: int = 100


class ToolRegistry:
    """Centralized registry for agent tool access.

    Manages tool creation, access control, usage tracking, and rate limiting.

    Example:
        >>> registry = ToolRegistry()
        >>> await registry.register_agent(agent_id=1, allowed_tools=["browser", "filesystem"])
        >>>
        >>> # Get browser for agent
        >>> browser = await registry.get_browser(agent_id=1)
        >>> await browser.navigate("https://example.com")
        >>>
        >>> # Track usage
        >>> usage = await registry.get_usage_stats(agent_id=1)
    """

    def __init__(self, limits: ToolLimits | None = None):
        """Initialize tool registry.

        Args:
            limits: Tool usage limits (uses defaults if not provided)

        Example:
            >>> limits = ToolLimits(max_requests_per_minute=30)
            >>> registry = ToolRegistry(limits=limits)
        """
        self.limits = limits or ToolLimits()
        self._agent_tools: dict[int, set[str]] = {}
        self._browser_servers: dict[int, BrowserServer] = {}
        self._filesystem_servers: dict[int, FilesystemServer] = {}
        self._notification_servers: dict[int, NotificationServer] = {}
        self._usage_history: list[ToolUsage] = []
        self._rate_limit_counters: dict[int, dict[str, list[datetime]]] = defaultdict(
            lambda: defaultdict(list)
        )

        logger.info("ToolRegistry initialized with limits: %s", self.limits)

    async def register_agent(
        self,
        agent_id: int,
        allowed_tools: list[str],
        telegram_token: str | None = None,
        n8n_webhook_url: str | None = None,
    ) -> None:
        """Register agent and their allowed tools.

        Args:
            agent_id: Agent ID
            allowed_tools: List of tool types ("browser", "filesystem", "notifications")
            telegram_token: Telegram token (required if notifications enabled)
            n8n_webhook_url: n8n webhook URL (required if notifications enabled)

        Raises:
            ValueError: If invalid tool types provided

        Example:
            >>> await registry.register_agent(
            ...     agent_id=1,
            ...     allowed_tools=["browser", "filesystem", "notifications"],
            ...     telegram_token="123:ABC",
            ...     n8n_webhook_url="https://..."
            ... )
        """
        # Validate tool types
        valid_tools = {t.value for t in ToolType}
        invalid_tools = set(allowed_tools) - valid_tools
        if invalid_tools:
            raise ValueError(f"Invalid tool types: {invalid_tools}")

        self._agent_tools[agent_id] = set(allowed_tools)

        # Pre-create filesystem server (always safe)
        if ToolType.FILESYSTEM in allowed_tools:
            self._filesystem_servers[agent_id] = FilesystemServer(agent_id=agent_id)

        # Pre-create notification server if configured
        if ToolType.NOTIFICATIONS in allowed_tools:
            self._notification_servers[agent_id] = NotificationServer(
                telegram_token=telegram_token,
                n8n_webhook_url=n8n_webhook_url,
            )

        logger.info("Registered agent %d with tools: %s", agent_id, allowed_tools)

    async def unregister_agent(self, agent_id: int) -> None:
        """Unregister agent and cleanup resources.

        Args:
            agent_id: Agent ID

        Example:
            >>> await registry.unregister_agent(agent_id=1)
        """
        # Stop browser if running
        if agent_id in self._browser_servers:
            await self._browser_servers[agent_id].stop()
            del self._browser_servers[agent_id]

        # Close notification server
        if agent_id in self._notification_servers:
            await self._notification_servers[agent_id].close()
            del self._notification_servers[agent_id]

        # Remove filesystem server
        if agent_id in self._filesystem_servers:
            del self._filesystem_servers[agent_id]

        # Remove from registry
        if agent_id in self._agent_tools:
            del self._agent_tools[agent_id]

        logger.info("Unregistered agent %d", agent_id)

    def _check_access(self, agent_id: int, tool_type: str) -> None:
        """Check if agent has access to tool.

        Args:
            agent_id: Agent ID
            tool_type: Tool type to check

        Raises:
            ValueError: If agent not registered or lacks access
        """
        if agent_id not in self._agent_tools:
            raise ValueError(f"Agent {agent_id} not registered")

        if tool_type not in self._agent_tools[agent_id]:
            raise ValueError(f"Agent {agent_id} does not have access to {tool_type}")

    def _check_rate_limit(self, agent_id: int, tool_type: str) -> bool:
        """Check if agent is within rate limits.

        Args:
            agent_id: Agent ID
            tool_type: Tool type

        Returns:
            True if within limits, False otherwise
        """
        now = datetime.now(UTC)
        counters = self._rate_limit_counters[agent_id][tool_type]

        # Remove old timestamps
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        counters[:] = [ts for ts in counters if ts > one_hour_ago]

        # Check limits
        recent_minute = sum(1 for ts in counters if ts > one_minute_ago)
        recent_hour = len(counters)

        if recent_minute >= self.limits.max_requests_per_minute:
            logger.warning(
                "Agent %d hit per-minute limit for %s (%d/%d)",
                agent_id,
                tool_type,
                recent_minute,
                self.limits.max_requests_per_minute,
            )
            return False

        if recent_hour >= self.limits.max_requests_per_hour:
            logger.warning(
                "Agent %d hit per-hour limit for %s (%d/%d)",
                agent_id,
                tool_type,
                recent_hour,
                self.limits.max_requests_per_hour,
            )
            return False

        # Record this request
        counters.append(now)
        return True

    async def get_browser(self, agent_id: int) -> BrowserServer:
        """Get browser server for agent.

        Args:
            agent_id: Agent ID

        Returns:
            BrowserServer instance

        Raises:
            ValueError: If agent not registered or lacks browser access
            RuntimeError: If rate limit exceeded

        Example:
            >>> browser = await registry.get_browser(agent_id=1)
            >>> await browser.start()
            >>> result = await browser.navigate("https://example.com")
        """
        self._check_access(agent_id, ToolType.BROWSER)

        if not self._check_rate_limit(agent_id, ToolType.BROWSER):
            raise RuntimeError(f"Agent {agent_id} exceeded rate limit for browser")

        # Create browser if not exists
        if agent_id not in self._browser_servers:
            # Check concurrent browser limit
            active_browsers = sum(
                1 for server in self._browser_servers.values() if server.is_running
            )
            if active_browsers >= self.limits.max_browser_sessions:
                raise RuntimeError(
                    f"Max concurrent browsers reached ({self.limits.max_browser_sessions})"
                )

            self._browser_servers[agent_id] = BrowserServer(headless=True)

        return self._browser_servers[agent_id]

    async def get_filesystem(self, agent_id: int) -> FilesystemServer:
        """Get filesystem server for agent.

        Args:
            agent_id: Agent ID

        Returns:
            FilesystemServer instance

        Raises:
            ValueError: If agent not registered or lacks filesystem access
            RuntimeError: If rate limit exceeded

        Example:
            >>> fs = await registry.get_filesystem(agent_id=1)
            >>> result = await fs.write_file("output.txt", "Hello!")
        """
        self._check_access(agent_id, ToolType.FILESYSTEM)

        if not self._check_rate_limit(agent_id, ToolType.FILESYSTEM):
            raise RuntimeError(f"Agent {agent_id} exceeded rate limit for filesystem")

        if agent_id not in self._filesystem_servers:
            raise ValueError(f"Filesystem server not initialized for agent {agent_id}")

        return self._filesystem_servers[agent_id]

    async def get_notifications(self, agent_id: int) -> NotificationServer:
        """Get notification server for agent.

        Args:
            agent_id: Agent ID

        Returns:
            NotificationServer instance

        Raises:
            ValueError: If agent not registered or lacks notification access
            RuntimeError: If rate limit exceeded

        Example:
            >>> notif = await registry.get_notifications(agent_id=1)
            >>> result = await notif.send_telegram(chat_id=123, message="Done!")
        """
        self._check_access(agent_id, ToolType.NOTIFICATIONS)

        if not self._check_rate_limit(agent_id, ToolType.NOTIFICATIONS):
            raise RuntimeError(f"Agent {agent_id} exceeded rate limit for notifications")

        if agent_id not in self._notification_servers:
            raise ValueError(f"Notification server not initialized for agent {agent_id}")

        return self._notification_servers[agent_id]

    def record_usage(
        self,
        agent_id: int,
        tool_type: str,
        operation: str,
        success: bool,
        duration: float = 0.0,
        data: dict | None = None,
    ) -> None:
        """Record tool usage for analytics.

        Args:
            agent_id: Agent ID
            tool_type: Tool type
            operation: Operation name
            success: Whether operation succeeded
            duration: Operation duration in seconds
            data: Additional usage data

        Example:
            >>> registry.record_usage(
            ...     agent_id=1,
            ...     tool_type="browser",
            ...     operation="navigate",
            ...     success=True,
            ...     duration=1.5
            ... )
        """
        usage = ToolUsage(
            agent_id=agent_id,
            tool_type=tool_type,
            operation=operation,
            success=success,
            duration=duration,
            data=data or {},
        )
        self._usage_history.append(usage)

        logger.debug(
            "Recorded usage: agent=%d tool=%s op=%s success=%s duration=%.2fs",
            agent_id,
            tool_type,
            operation,
            success,
            duration,
        )

    async def get_usage_stats(
        self,
        agent_id: int | None = None,
        since: datetime | None = None,
    ) -> dict:
        """Get usage statistics.

        Args:
            agent_id: Filter by agent (None = all agents)
            since: Filter by time (None = all time)

        Returns:
            Dictionary with usage statistics

        Example:
            >>> stats = await registry.get_usage_stats(agent_id=1)
            >>> print(stats["total_operations"], stats["success_rate"])
        """
        # Filter usage history
        filtered = self._usage_history
        if agent_id is not None:
            filtered = [u for u in filtered if u.agent_id == agent_id]
        if since is not None:
            filtered = [u for u in filtered if u.timestamp >= since]

        # Calculate stats
        total = len(filtered)
        successful = sum(1 for u in filtered if u.success)
        failed = total - successful

        stats = {
            "total_operations": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "by_tool": defaultdict(int),
            "by_operation": defaultdict(int),
            "total_duration": sum(u.duration for u in filtered),
        }

        for usage in filtered:
            stats["by_tool"][usage.tool_type] += 1
            stats["by_operation"][usage.operation] += 1

        return dict(stats)

    async def cleanup(self) -> None:
        """Cleanup all resources.

        Example:
            >>> await registry.cleanup()
        """
        # Stop all browsers
        for browser in self._browser_servers.values():
            if browser.is_running:
                await browser.stop()

        # Close all notification servers
        for notif_server in self._notification_servers.values():
            await notif_server.close()

        logger.info("ToolRegistry cleaned up")


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_tool_registry(limits: ToolLimits | None = None) -> ToolRegistry:
    """Get global ToolRegistry singleton.

    Args:
        limits: Tool usage limits (uses defaults if not provided)

    Returns:
        Global ToolRegistry instance

    Example:
        >>> registry = get_tool_registry()
        >>> await registry.register_agent(agent_id=1, allowed_tools=["browser"])
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry(limits=limits)
    return _global_registry
