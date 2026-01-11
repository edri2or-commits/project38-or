"""FastAPI application entry point for Agent Platform.

This module initializes the FastAPI application and registers all route handlers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.database import create_db_and_tables
from src.api.routes import agents, health, tasks
from src.harness.handoff import HandoffArtifact  # noqa: F401 - Ensure model is registered
from src.harness.scheduler import get_scheduler
from src.models.agent import Agent  # noqa: F401 - Ensure model is registered
from src.models.task import Task  # noqa: F401 - Ensure model is registered

# Create FastAPI app instance
app = FastAPI(
    title="Agent Platform API",
    description="REST API for autonomous AI agent creation and orchestration",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route handlers
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])


@app.on_event("startup")
async def startup_event():
    """Run on application startup.

    Initialize database connection pool, agent scheduler, and perform health checks.
    """
    # Create database tables
    await create_db_and_tables()

    # Start agent scheduler
    scheduler = await get_scheduler()
    await scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown.

    Stop agent scheduler, close database connections and cleanup resources.
    """
    # Stop agent scheduler
    scheduler = await get_scheduler()
    await scheduler.stop()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
