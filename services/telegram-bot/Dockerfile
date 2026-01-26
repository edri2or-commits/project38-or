# Telegram Bot Service - Dockerfile
# Multi-stage build for Python FastAPI application
#
# BUSINESS Domain service - NO PERSONAL code (smart_email, workspace)
# See docs/split/COUPLING_SCAN.md for domain separation requirements

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install system dependencies (git no longer needed - removed PERSONAL code fetch)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# NOTE: REMOVED git clone of src/agents (PERSONAL domain code)
# The Telegram bot is a BUSINESS service and must NOT include:
# - src/agents/smart_email (PERSONAL)
# - src/workspace_mcp_bridge (PERSONAL)
# Email agent runs as a separate PERSONAL service.

# Create non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

# Expose port
EXPOSE 8000

# Health check (uses PORT env var or default 8000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os; import requests; requests.get(f'http://localhost:{os.environ.get(\"PORT\", 8000)}/health')" || exit 1

# Run application - Railway provides PORT env var dynamically
# Using shell form to interpret environment variables
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
