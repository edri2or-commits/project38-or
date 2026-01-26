"""FastAPI application entry point for Personal Domain.

This module initializes the FastAPI application for PERSONAL operations:
- Smart Email Agent (Gmail triage and summarization)
- Google Workspace integration

IMPORTANT: This domain does NOT include BUSINESS infrastructure features.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from libs.shared_core.logging import setup_logging

# Initialize structured logging on module import
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class EmailSummaryRequest(BaseModel):
    """Request model for email summary endpoint."""

    hours: int = 24
    send_telegram: bool = True
    enable_phase2: bool = True
    enable_research: bool = True
    enable_history: bool = True
    enable_drafts: bool = True


class EmailSummaryResponse(BaseModel):
    """Response model for email summary endpoint."""

    success: bool
    total_count: int = 0
    p1_count: int = 0
    p2_count: int = 0
    p3_count: int = 0
    p4_count: int = 0
    telegram_sent: bool = False
    duration_ms: int = 0
    errors: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    logger.info("Personal Domain API starting up")
    yield
    logger.info("Personal Domain API shutting down")


# Create FastAPI app instance
app = FastAPI(
    title="Personal Domain API",
    description="REST API for personal automation (email, calendar, etc.)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "domain": "PERSONAL"}


@app.post("/run_email_summary", response_model=EmailSummaryResponse)
async def run_email_summary(request: EmailSummaryRequest):
    """Run the Smart Email Agent to summarize recent emails.

    This endpoint triggers the Smart Email Agent which:
    1. Fetches recent emails from Gmail
    2. Classifies them by priority (P1-P4)
    3. Generates summaries
    4. Optionally sends summary to Telegram

    Args:
        request: Configuration for the email summary run

    Returns:
        EmailSummaryResponse with results
    """
    try:
        from apps.personal.agents.smart_email.graph import run_smart_email_agent

        result = await run_smart_email_agent(
            hours=request.hours,
            send_telegram=request.send_telegram,
            enable_phase2=request.enable_phase2,
            enable_research=request.enable_research,
            enable_history=request.enable_history,
            enable_drafts=request.enable_drafts,
        )

        return EmailSummaryResponse(
            success=True,
            total_count=result.get("total_count", 0),
            p1_count=result.get("p1_count", 0),
            p2_count=result.get("p2_count", 0),
            p3_count=result.get("p3_count", 0),
            p4_count=result.get("p4_count", 0),
            telegram_sent=result.get("telegram_sent", False),
            duration_ms=result.get("duration_ms", 0),
            errors=result.get("errors", []),
        )

    except ImportError as e:
        logger.error(f"Smart Email Agent import failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Smart Email Agent not available: {e}",
        )
    except Exception as e:
        logger.error(f"Email summary failed: {e}", exc_info=True)
        return EmailSummaryResponse(
            success=False,
            errors=[str(e)],
        )


@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint showing all registered routes."""
    return {
        "domain": "PERSONAL",
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
            "TELEGRAM_CHAT_ID": "set" if os.environ.get("TELEGRAM_CHAT_ID") else "missing",
            "MCP_GATEWAY_URL": os.environ.get("MCP_GATEWAY_URL", "not set"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Personal Domain API", extra={"port": 8001})

    uvicorn.run(
        "apps.personal.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )
