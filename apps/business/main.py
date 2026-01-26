"""FastAPI application entry point for Business Domain.

This module initializes the FastAPI application for BUSINESS operations:
- Railway deployment management
- GitHub integration
- n8n workflow orchestration
- NightWatch autonomous monitoring
- Cost monitoring and optimization

IMPORTANT: This domain does NOT include Workspace/Personal features.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.business.api.routes import (
    agents,
    backups,
    costs,
    health,
    learning,
    metrics,
    monitoring,
    nightwatch,
    secrets_health,
    tasks,
)
from libs.shared_core.logging import setup_logging

# Initialize structured logging on module import
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Global relay instance for status checking
_github_relay = None
_relay_startup_error = None


def get_github_relay():
    """Get the global GitHub relay instance."""
    return _github_relay


def get_relay_startup_error():
    """Get the relay startup error if any."""
    return _relay_startup_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.

    This context manager handles startup and shutdown events.
    Resources are initialized on startup and cleaned up on shutdown.
    """
    from apps.business.api.database import close_db_connection, create_db_and_tables

    # Startup: Initialize database tables
    try:
        await create_db_and_tables()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Start GCS relay polling if enabled
    if os.getenv("GCS_RELAY_ENABLED", "false").lower() == "true":
        try:
            from apps.business.mcp_gateway.gcs_relay import start_background_polling

            start_background_polling()
            logger.info("GCS MCP Relay started")
        except Exception as e:
            logger.warning(f"Failed to start GCS relay: {e}")

    # Start MonitoringLoop if enabled (for Night Watch)
    monitoring_auto_start = os.getenv("MONITORING_AUTO_START", "false").lower() == "true"
    if monitoring_auto_start:
        try:
            from apps.business.core.monitoring_loop import create_railway_monitoring_loop

            monitoring_loop = create_railway_monitoring_loop()
            # Start in background task
            import asyncio

            asyncio.create_task(monitoring_loop.start())
            logger.info("MonitoringLoop auto-started for Night Watch")
        except Exception as e:
            logger.warning(f"Failed to auto-start MonitoringLoop: {e}")

    # Start GitHub relay polling if enabled
    global _github_relay, _relay_startup_error
    relay_enabled = os.getenv("GITHUB_RELAY_ENABLED", "false").lower() == "true"
    logger.info(f"GitHub relay enabled: {relay_enabled}")

    if relay_enabled:
        try:
            from apps.business.mcp_gateway.github_relay import start_relay

            _github_relay = await start_relay()
            logger.info("GitHub MCP Relay started successfully")
        except Exception as e:
            _relay_startup_error = str(e)
            logger.error(f"Failed to start GitHub relay: {e}", exc_info=True)

    yield

    # Shutdown: Close database connection pool
    try:
        await close_db_connection()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Failed to close database connections: {e}")


# Create FastAPI app instance
app = FastAPI(
    title="Business Domain API",
    description="REST API for autonomous infrastructure management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS middleware
ENVIRONMENT = os.getenv("RAILWAY_ENVIRONMENT", "development")
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = ALLOWED_ORIGINS_ENV.split(",") if ALLOWED_ORIGINS_ENV else []

if ENVIRONMENT == "production":
    if not ALLOWED_ORIGINS:
        ALLOWED_ORIGINS = ["https://or-infra.com"]
        logger.warning("Using default production origin: https://or-infra.com")
else:
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

# Register route handlers (BUSINESS only)
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(backups.router, prefix="/api", tags=["backups"])
app.include_router(metrics.router, tags=["metrics"])
app.include_router(costs.router, tags=["costs"])
app.include_router(monitoring.router, tags=["monitoring"])
app.include_router(nightwatch.router, tags=["nightwatch"])
app.include_router(learning.router, prefix="/api", tags=["learning"])
app.include_router(secrets_health.router, tags=["secrets"])

# Mount MCP Gateway for autonomous Railway/n8n operations (BUSINESS only)
MCP_GATEWAY_ENABLED = os.getenv("MCP_GATEWAY_ENABLED", "false").lower() == "true"
if MCP_GATEWAY_ENABLED:
    try:
        from apps.business.mcp_gateway.server import create_mcp_app

        mcp_app = create_mcp_app()
        if mcp_app:
            app.mount("/mcp", mcp_app)
            logger.info("MCP Gateway mounted at /mcp (BUSINESS tools only)")
        else:
            logger.warning("MCP Gateway not available (fastmcp not installed)")
    except ImportError as e:
        logger.warning(f"MCP Gateway import failed: {e}")
else:
    logger.info("MCP Gateway disabled (set MCP_GATEWAY_ENABLED=true to enable)")

# NOTE: Workspace MCP Bridge is NOT mounted here - it belongs to PERSONAL domain


@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint showing all registered routes."""
    return {
        "domain": "BUSINESS",
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
    import uvicorn

    logger.info("Starting Business Domain API", extra={"port": 8000})

    uvicorn.run(
        "apps.business.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
