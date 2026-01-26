"""Google Workspace MCP Tools.

Each module provides MCP tools for a specific Google Workspace service:
- gmail: Email operations
- calendar: Calendar and events
- drive: File storage and sharing
- sheets: Spreadsheet operations
- docs: Document operations
"""

from apps.personal.integrations.workspace_mcp_bridge.tools.calendar import register_calendar_tools
from apps.personal.integrations.workspace_mcp_bridge.tools.docs import register_docs_tools
from apps.personal.integrations.workspace_mcp_bridge.tools.drive import register_drive_tools
from apps.personal.integrations.workspace_mcp_bridge.tools.gmail import register_gmail_tools
from apps.personal.integrations.workspace_mcp_bridge.tools.sheets import register_sheets_tools

__all__ = [
    "register_gmail_tools",
    "register_calendar_tools",
    "register_drive_tools",
    "register_sheets_tools",
    "register_docs_tools",
]
