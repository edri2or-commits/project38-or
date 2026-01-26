"""Google Workspace MCP Bridge.

Provides MCP tools for Google Workspace services:
- Gmail: Send, read, search emails
- Calendar: Events, meetings, reminders
- Drive: Files, folders, sharing
- Sheets: Spreadsheet operations
- Docs: Document operations

Authentication uses OAuth 2.0 with tokens stored in GCP Secret Manager.
"""

from apps.personal.integrations.workspace_mcp_bridge.server import create_app, mcp

__all__ = ["create_app", "mcp"]
