"""
MCP Gateway for Claude Code Autonomous Operations.

This module provides a Remote MCP Server that enables Claude Code to
autonomously operate Railway deployments and n8n workflows.

Example:
    To run the MCP server standalone:
    >>> from src.mcp_gateway.server import mcp
    >>> mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)

    To mount in FastAPI:
    >>> from fastapi import FastAPI
    >>> from src.mcp_gateway.server import create_mcp_app
    >>> app = FastAPI()
    >>> app.mount("/mcp", create_mcp_app())
"""

__version__ = "0.1.0"
