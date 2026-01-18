# GCP MCP Server Dockerfile
FROM google/cloud-sdk:alpine

# Install Python 3.11
RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GCP_PROJECT_ID=project38-483612

# Expose port
EXPOSE 8080

# Run the server
CMD ["python3", "server.py"]
