# GCP MCP Server Dockerfile
FROM python:3.11-slim

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GCP_PROJECT_ID=project38-483612

# Expose port
EXPOSE 8080

# Run the server
CMD ["python", "server.py"]
