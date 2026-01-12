"""MCP Tools - Browser automation, filesystem, and notifications for agents.

This module provides Model Context Protocol (MCP) tool servers that enable
agents to interact with the outside world safely:

- Browser: Playwright-based web automation
- Filesystem: Sandboxed file operations
- Notifications: Telegram and n8n webhooks
- Registry: Tool management and access control

Example:
    >>> from src.mcp import BrowserServer, FilesystemServer, NotificationServer
    >>>
    >>> # Create browser server
    >>> browser = BrowserServer()
    >>> result = await browser.navigate("https://example.com")
    >>>
    >>> # Create filesystem server for agent
    >>> fs = FilesystemServer(agent_id=1)
    >>> await fs.write_file("output.txt", "Hello, World!")
    >>>
    >>> # Send notification
    >>> notif = NotificationServer()
    >>> await notif.send_telegram("Task completed!")
"""

from .browser import BrowserServer, BrowserTool
from .filesystem import FilesystemServer, FilesystemTool
from .notifications import NotificationServer, NotificationTool
from .registry import ToolRegistry, ToolUsage

__all__ = [
    # Browser
    "BrowserServer",
    "BrowserTool",
    # Filesystem
    "FilesystemServer",
    "FilesystemTool",
    # Notifications
    "NotificationServer",
    "NotificationTool",
    # Registry
    "ToolRegistry",
    "ToolUsage",
]
