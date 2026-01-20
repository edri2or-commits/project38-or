# LiteLLM Gateway Dockerfile
# Based on official LiteLLM Docker image
# Source: https://docs.litellm.ai/docs/proxy/deploy#docker-deploy
# Updated: 2026-01-20 (Phase 3: Monitoring Dashboards - ADR-010)

FROM ghcr.io/berriai/litellm:main-latest

# Set working directory
WORKDIR /app

# Copy configuration file
COPY litellm-config.yaml /app/config.yaml

# Expose port
EXPOSE 4000

# Phase 2: OpenTelemetry defaults
ENV OTEL_SERVICE_NAME=litellm-gateway
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/json

# Phase 3: Prometheus metrics (multi-worker support)
ENV PROMETHEUS_MULTIPROC_DIR=/prometheus_metrics
RUN mkdir -p /prometheus_metrics && chmod 777 /prometheus_metrics

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:4000/health || exit 1

# Run LiteLLM proxy
CMD ["litellm", "--config", "/app/config.yaml", "--port", "4000", "--host", "0.0.0.0"]
