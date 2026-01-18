# MCP Router - Cloud Run Container
# Matching working gcp-mcp-gateway pattern
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Environment (matching working deployment)
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GCP_PROJECT_ID=project38-483612

EXPOSE 8080

# Run Flask directly (same pattern as working gcp-mcp-gateway)
CMD ["python", "app.py"]
