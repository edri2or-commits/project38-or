"""FastAPI application entry point for Agent Platform.

This module initializes the FastAPI application and registers all route handlers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import health

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


@app.on_event("startup")
async def startup_event():
    """Run on application startup.

    Initialize database connection pool and perform health checks.
    """
    # TODO: Initialize database connection
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown.

    Close database connections and cleanup resources.
    """
    # TODO: Close database connection
    pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
