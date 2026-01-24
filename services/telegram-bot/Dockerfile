# Telegram Bot Service - Dockerfile
# Multi-stage build for Python FastAPI application
#
# Fetches src/agents via git clone for Smart Email Agent support

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install system dependencies including git for fetching src/agents
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    git \
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

# Fetch src/agents for Smart Email Agent using sparse checkout
RUN git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/edri2or-commits/project38-or.git /tmp/repo && \
    cd /tmp/repo && \
    git sparse-checkout set src/agents && \
    mkdir -p /app/src && \
    cp -r /tmp/repo/src/agents /app/src/ && \
    rm -rf /tmp/repo

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
