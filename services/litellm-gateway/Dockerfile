# LiteLLM Gateway Dockerfile
# Based on official LiteLLM Docker image
# Source: https://docs.litellm.ai/docs/proxy/deploy#docker-deploy

FROM ghcr.io/berriai/litellm:main-latest

# Set working directory
WORKDIR /app

# Copy configuration file
COPY litellm-config.yaml /app/config.yaml

# Expose port
EXPOSE 4000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:4000/health || exit 1

# Run LiteLLM proxy
CMD ["litellm", "--config", "/app/config.yaml", "--port", "4000", "--host", "0.0.0.0"]
