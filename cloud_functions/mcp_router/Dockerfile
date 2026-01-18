# MCP Router - Cloud Run Container
# Python 3.12 with gunicorn for production

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY . .

# Cloud Run sets PORT environment variable
ENV PORT=8080

# Run with gunicorn for production
# workers=1 because Cloud Run handles scaling at container level
# threads=8 for concurrent requests within the container
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 120 app:app
