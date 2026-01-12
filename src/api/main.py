"""FastAPI application entry point for Agent Platform.

This module initializes the FastAPI application and registers all route handlers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import agents, health, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.

    This context manager handles startup and shutdown events.
    Resources are initialized on startup and cleaned up on shutdown.
    """
    # Startup: Initialize database connection
    # TODO: Initialize database connection pool
    yield
    # Shutdown: Cleanup resources
    # TODO: Close database connection pool


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
