"""Health check endpoint for monitoring API availability.

This module provides endpoints for health checks and system status.
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.database import check_database_connection

router = APIRouter(prefix="/api")


class HealthResponse(BaseModel):
    """Health check response model.

    Attributes:
        status: Current health status (healthy/degraded/unhealthy)
        timestamp: Current server timestamp
        version: API version
        database: Database connection status
        build: Build marker to verify deployment version
    """

    status: str
    timestamp: datetime
    version: str
    database: str = "not_connected"
    build: str = ""


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns current system health status including database connectivity.

    Returns:
        HealthResponse: System health information

    Example:
        >>> response = await health_check()
        >>> print(response.status)
        healthy
    """
    # Check database connection
    db_status = "connected" if await check_database_connection() else "disconnected"

    # Determine overall health status
    status = "healthy" if db_status == "connected" else "degraded"

    # Build marker to verify deployment version
    # Change this value to verify Railway is deploying new code
    build_marker = "2026-01-24-mcp-debug"

    return HealthResponse(
        status=status,
        timestamp=datetime.now(UTC),
        version="0.1.0",
        database=db_status,
        build=build_marker,
    )


@router.get("/", response_model=dict[str, str])
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns basic API information and documentation links.

    Returns:
        dict: API metadata
    """
    return {
        "name": "Agent Platform API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@router.get("/test/ping")
async def test_ping() -> dict:
    """Test endpoint to verify routes are being registered."""
    return {"status": "pong", "message": "If you see this, routes are working"}


@router.get("/mcp/status")
async def mcp_gateway_status() -> dict:
    """Check MCP Gateway status.

    Returns:
        dict: MCP Gateway status information
    """
    import os

    mcp_enabled_raw = os.getenv("MCP_GATEWAY_ENABLED", "NOT_SET")
    mcp_enabled = mcp_enabled_raw.lower() == "true" if mcp_enabled_raw != "NOT_SET" else False

    # Check if fastmcp is available
    fastmcp_available = False
    try:
        import fastmcp
        fastmcp_available = True
    except ImportError:
        pass

    # Check if MCP app was created
    mcp_app_created = False
    mcp_app_error = None
    if mcp_enabled and fastmcp_available:
        try:
            from src.mcp_gateway.server import create_mcp_app
            app = create_mcp_app()
            mcp_app_created = app is not None
        except Exception as e:
            mcp_app_error = str(e)

    # Check if /mcp is actually mounted in the FastAPI app
    mcp_mounted = False
    mounted_apps = []
    route_types = []
    try:
        from starlette.routing import Mount
        from src.api.main import app as main_app

        for route in main_app.routes:
            route_type = type(route).__name__
            route_types.append(route_type)

            # Check for mounted ASGI apps
            if isinstance(route, Mount):
                mount_path = route.path
                mounted_apps.append(mount_path)
                if mount_path == "/mcp":
                    mcp_mounted = True
    except Exception as e:
        mounted_apps = [f"Error: {e}"]

    return {
        "mcp_gateway_enabled_raw": mcp_enabled_raw,
        "mcp_gateway_enabled": mcp_enabled,
        "fastmcp_installed": fastmcp_available,
        "mcp_app_created": mcp_app_created,
        "mcp_app_error": mcp_app_error,
        "expected_path": "/mcp" if mcp_enabled and mcp_app_created else None,
        "mcp_actually_mounted": mcp_mounted,
        "mounted_apps": mounted_apps,
        "route_types_sample": list(set(route_types))[:10],
    }


@router.post("/mcp/test")
async def mcp_test() -> dict:
    """Test MCP Gateway directly.

    Calls MCP Gateway with a simple request to diagnose errors.

    Returns:
        dict: MCP response or error details
    """
    import os
    import traceback

    mcp_enabled = os.getenv("MCP_GATEWAY_ENABLED", "false").lower() == "true"
    if not mcp_enabled:
        return {"error": "MCP Gateway not enabled"}

    try:
        from src.mcp_gateway.server import create_mcp_server

        mcp = create_mcp_server()
        if mcp is None:
            return {"error": "FastMCP not available"}

        # Try to get the tools list
        try:
            # Get available tools from the server - try all known attribute names
            tools = []
            tools_attr = None
            if hasattr(mcp, "_tools"):
                tools_attr = "_tools"
                tools = list(mcp._tools.keys())
            elif hasattr(mcp, "tools"):
                tools_attr = "tools"
                try:
                    tools = [t.name for t in mcp.tools]
                except Exception:
                    tools = list(mcp.tools) if hasattr(mcp.tools, "__iter__") else []
            elif hasattr(mcp, "_tool_manager"):
                tools_attr = "_tool_manager"
                tm = mcp._tool_manager
                if hasattr(tm, "list_tools"):
                    tools = [t.name for t in tm.list_tools()]
                elif hasattr(tm, "_tools"):
                    tools = list(tm._tools.keys())

            # Get all attributes to debug
            attrs = [a for a in dir(mcp) if not a.startswith("__")]

            return {
                "status": "ok",
                "mcp_server_type": type(mcp).__name__,
                "tools_count": len(tools),
                "tools_attr_used": tools_attr,
                "tools_sample": tools[:10] if tools else [],
                "has_http_app": hasattr(mcp, "http_app"),
                "mcp_attrs": attrs[:20],  # First 20 attributes
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@router.post("/mcp/call")
async def mcp_call_tool(tool_name: str = "health_check", arguments: dict = {}) -> dict:
    """Call an MCP tool directly.

    Args:
        tool_name: Name of tool to call
        arguments: Tool arguments

    Returns:
        dict: Tool result or error
    """
    import os
    import traceback

    mcp_enabled = os.getenv("MCP_GATEWAY_ENABLED", "false").lower() == "true"
    if not mcp_enabled:
        return {"error": "MCP Gateway not enabled"}

    try:
        from src.mcp_gateway.server import create_mcp_server

        mcp = create_mcp_server()
        if mcp is None:
            return {"error": "FastMCP not available"}

        # Try to call the tool directly
        try:
            import asyncio
            import inspect

            # Get the tool
            tm = mcp._tool_manager
            tool = None
            if hasattr(tm, "get_tool"):
                getter = tm.get_tool(tool_name)
                # Check if get_tool returns a coroutine
                if asyncio.iscoroutine(getter):
                    tool = await getter
                else:
                    tool = getter
            elif hasattr(tm, "_tools"):
                tool = tm._tools.get(tool_name)

            if tool is None:
                return {"error": f"Tool not found: {tool_name}"}

            # Call the tool
            if hasattr(tool, "fn"):
                if asyncio.iscoroutinefunction(tool.fn):
                    result = await tool.fn(**arguments)
                else:
                    result = tool.fn(**arguments)
            elif callable(tool):
                result = await tool(**arguments)
            else:
                return {"error": f"Tool not callable: {type(tool)}"}

            return {"status": "ok", "result": result}

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@router.get("/relay/status")
async def relay_status() -> dict:
    """Check GitHub MCP Relay status.

    Returns:
        dict: Relay status information
    """
    import os

    from src.api.main import get_github_relay, get_relay_startup_error

    relay = get_github_relay()
    startup_error = get_relay_startup_error()
    relay_enabled = os.getenv("GITHUB_RELAY_ENABLED", "true").lower() == "true"

    if relay is None:
        return {
            "status": "not_started",
            "relay_enabled": relay_enabled,
            "startup_error": startup_error,
            "message": "GitHub relay was not initialized",
            "repo": None,
            "issue": None,
        }

    return {
        "status": "running" if relay._running else "stopped",
        "relay_enabled": relay_enabled,
        "repo": relay.repo,
        "issue": relay.issue_number,
        "processed_requests": len(relay._processed_requests),
        "has_token": relay._github_token is not None,
    }
