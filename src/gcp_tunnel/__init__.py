"""
GCP Tunnel - Protocol Encapsulation for Claude Code Autonomy.

This module provides the client-side adapter for tunneling MCP messages
through Google Cloud Functions API, bypassing Anthropic's egress proxy.

Usage:
    from gcp_tunnel.adapter import GoogleRestTransport, MCPStdioAdapter

    transport = GoogleRestTransport(
        project_id="project38-483612",
        region="us-central1",
        function_name="mcp-router"
    )
    adapter = MCPStdioAdapter(transport)
    await adapter.run()

Or run directly:
    python -m gcp_tunnel.adapter
"""

from .adapter import GoogleRestTransport, MCPStdioAdapter

__all__ = ["GoogleRestTransport", "MCPStdioAdapter"]
__version__ = "1.0.0"
