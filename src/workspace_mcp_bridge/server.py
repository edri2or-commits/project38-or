"""Google Workspace MCP Bridge Server.

FastMCP server providing Google Workspace tools:
- Gmail: 5 tools (send, search, read, list, labels)
- Calendar: 5 tools (list, events, create, update, delete)
- Drive: 7 tools (list, search, read, create_folder, upload, delete, share)
- Sheets: 6 tools (read, write, create, append, clear, metadata)
- Docs: 5 tools (read, create, append, insert, replace)

Total: 28 tools for full Google Workspace autonomy.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from mcp.server.fastmcp import FastMCP

from src.workspace_mcp_bridge.auth import GoogleOAuthManager, verify_bridge_token
from src.workspace_mcp_bridge.config import WorkspaceConfig
from src.workspace_mcp_bridge.tools.calendar import register_calendar_tools
from src.workspace_mcp_bridge.tools.docs import register_docs_tools
from src.workspace_mcp_bridge.tools.drive import register_drive_tools
from src.workspace_mcp_bridge.tools.gmail import register_gmail_tools
from src.workspace_mcp_bridge.tools.sheets import register_sheets_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = WorkspaceConfig.from_env()

# Try to load from GCP if env vars not set
if not config.oauth_client_id:
    try:
        config = WorkspaceConfig.from_gcp_secrets()
        logger.info("Configuration loaded from GCP Secret Manager")
    except Exception as e:
        logger.warning(f"Could not load from GCP: {e}")

# Initialize OAuth manager
oauth_manager = GoogleOAuthManager(config)

# Create FastMCP server
mcp = FastMCP(
    name="Google Workspace MCP Bridge",
    version="1.0.0",
    description="MCP tools for Gmail, Calendar, Drive, Sheets, and Docs",
)

# Register all tools
register_gmail_tools(mcp, oauth_manager)
register_calendar_tools(mcp, oauth_manager)
register_drive_tools(mcp, oauth_manager)
register_sheets_tools(mcp, oauth_manager)
register_docs_tools(mcp, oauth_manager)

logger.info("Registered 28 Google Workspace tools")


# Add health and status tools
@mcp.tool()
async def workspace_health() -> dict[str, Any]:
    """Check Google Workspace MCP Bridge health.

    Returns:
        Health status and configuration info
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "config": config.to_dict(),
        "tools": {
            "gmail": ["send", "search", "read", "list", "labels"],
            "calendar": ["list", "events", "create_event", "update_event", "delete_event"],
            "drive": ["list", "search", "read", "create_folder", "upload", "delete", "share"],
            "sheets": ["read", "write", "create", "append", "clear", "get_metadata"],
            "docs": ["read", "create", "append", "insert", "replace"],
        },
        "total_tools": 28,
    }


@mcp.tool()
async def workspace_auth_status() -> dict[str, Any]:
    """Check OAuth authentication status.

    Returns:
        Authentication status and token info
    """
    try:
        await oauth_manager.get_access_token()
        return {
            "authenticated": True,
            "token_valid": oauth_manager._is_token_valid(),
            "scopes": config.scopes,
        }
    except Exception as e:
        return {
            "authenticated": False,
            "error": str(e),
            "scopes": config.scopes,
        }


def create_app() -> FastAPI:
    """Create FastAPI application with MCP mount.

    Returns:
        FastAPI application instance
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan events."""
        logger.info("Starting Google Workspace MCP Bridge")
        logger.info(f"Config status: {config.to_dict()}")
        yield
        logger.info("Shutting down Google Workspace MCP Bridge")

    app = FastAPI(
        title="Google Workspace MCP Bridge",
        version="1.0.0",
        description="MCP tools for Google Workspace services",
        lifespan=lifespan,
    )

    # Health endpoint (no auth required)
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "workspace-mcp-bridge",
            "version": "1.0.0",
            "tools_registered": 30,  # 28 workspace + 2 status
        }

    # Configuration endpoint (requires auth)
    @app.get("/config")
    async def get_config(
        _: bool = Depends(verify_bridge_token(config))
    ):
        return config.to_dict()

    # Mount MCP server with authentication
    mcp_app = mcp.streamable_http_app()

    # Add authentication middleware to MCP routes
    @app.middleware("http")
    async def auth_middleware(request, call_next):
        # Skip auth for health endpoint
        if request.url.path == "/health":
            return await call_next(request)

        # Verify token for MCP routes
        if request.url.path.startswith("/mcp"):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing Authorization header"},
                )
            token = auth_header[7:]
            if config.bridge_token and token != config.bridge_token:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid bridge token"},
                )

        return await call_next(request)

    # Mount MCP at /mcp
    app.mount("/mcp", mcp_app)

    return app


# Create app instance for Railway/uvicorn
app = create_app()

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
