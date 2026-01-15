"""FastAPI application entry point for Agent Platform.

This module initializes the FastAPI application and registers all route handlers.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import (
    agents,
    backups,
    costs,
    health,
    learning,
    metrics,
    monitoring,
    secrets_health,
    tasks,
)
from src.logging_config import setup_logging

# Initialize structured logging on module import
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.

    This context manager handles startup and shutdown events.
    Resources are initialized on startup and cleaned up on shutdown.
    """
    from src.api.database import close_db_connection, create_db_and_tables

    # Startup: Initialize database tables
    try:
        await create_db_and_tables()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    yield

    # Shutdown: Close database connection pool
    try:
        await close_db_connection()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Failed to close database connections: {e}")


# Create FastAPI app instance
app = FastAPI(
    title="Agent Platform API",
    description="REST API for autonomous AI agent creation and orchestration",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS middleware
# Restrict origins based on environment
ENVIRONMENT = os.getenv("RAILWAY_ENVIRONMENT", "development")
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = ALLOWED_ORIGINS_ENV.split(",") if ALLOWED_ORIGINS_ENV else []

if ENVIRONMENT == "production":
    # Production: whitelist only
    if not ALLOWED_ORIGINS:
        ALLOWED_ORIGINS = ["https://or-infra.com"]
        logger.warning("Using default production origin: https://or-infra.com")
else:
    # Development: allow localhost
    if not ALLOWED_ORIGINS:
        ALLOWED_ORIGINS = [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# Register route handlers
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(backups.router, prefix="/api", tags=["backups"])
app.include_router(metrics.router, tags=["metrics"])
app.include_router(costs.router, tags=["costs"])
app.include_router(monitoring.router, tags=["monitoring"])
app.include_router(learning.router, prefix="/api", tags=["learning"])
app.include_router(secrets_health.router, tags=["secrets"])

# Mount MCP Gateway for autonomous Railway/n8n operations
MCP_GATEWAY_ENABLED = os.getenv("MCP_GATEWAY_ENABLED", "false").lower() == "true"
if MCP_GATEWAY_ENABLED:
    try:
        from src.mcp_gateway.server import create_mcp_app

        mcp_app = create_mcp_app()
        if mcp_app:
            app.mount("/mcp", mcp_app)
            logger.info("MCP Gateway mounted at /mcp")
        else:
            logger.warning("MCP Gateway not available (fastmcp not installed)")
    except ImportError as e:
        logger.warning(f"MCP Gateway import failed: {e}")
else:
    logger.info("MCP Gateway disabled (set MCP_GATEWAY_ENABLED=true to enable)")

# Mount Google Workspace MCP Bridge for Gmail, Calendar, Drive, Sheets, Docs
WORKSPACE_MCP_ENABLED = os.getenv("WORKSPACE_MCP_ENABLED", "false").lower() == "true"
if WORKSPACE_MCP_ENABLED:
    try:
        from src.workspace_mcp_bridge.server import create_app as create_workspace_app

        workspace_app = create_workspace_app()
        if workspace_app:
            app.mount("/workspace", workspace_app)
            logger.info("Google Workspace MCP Bridge mounted at /workspace")
        else:
            logger.warning("Workspace MCP Bridge not available")
    except ImportError as e:
        logger.warning(f"Workspace MCP Bridge import failed: {e}")
else:
    logger.info("Workspace MCP disabled (set WORKSPACE_MCP_ENABLED=true to enable)")


# Debug endpoint to verify routes are registered
@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint showing all registered routes."""
    import os

    return {
        "total_routes": len(app.routes),
        "routes": [
            {
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if hasattr(route, "methods") else [],
            }
            for route in app.routes
        ],
        "environment": {
            "DATABASE_URL": "set" if os.environ.get("DATABASE_URL") else "missing",
            "PORT": os.environ.get("PORT", "not set"),
            "RAILWAY_ENVIRONMENT": os.environ.get("RAILWAY_ENVIRONMENT", "not railway"),
        },
    }


if __name__ == "__main__":
    import logging

    import uvicorn

    # Logging already configured by setup_logging() above
    logger = logging.getLogger(__name__)
    logger.info("Starting FastAPI application", extra={"port": 8000})

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
