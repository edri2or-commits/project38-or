# Railway MCP HTTP Bridge
# Exposes the official @railway/mcp-server over HTTP

FROM node:20-slim

# Install Railway CLI
RUN npm install -g @railway/cli

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY server.js ./

# Expose port
EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3001/health || exit 1

# Start the bridge
CMD ["npm", "start"]
