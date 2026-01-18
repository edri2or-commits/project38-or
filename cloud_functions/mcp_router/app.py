"""
Flask application wrapper for Cloud Run deployment.

This module creates a Flask app that wraps the MCP Router functionality,
allowing deployment as a Cloud Run service instead of Cloud Functions.
"""

from flask import Flask, request
from main import mcp_router as handle_mcp_request

app = Flask(__name__)


@app.route("/", methods=["GET", "POST", "OPTIONS"])
def index():
    """Main endpoint - delegates to MCP router handler."""
    return handle_mcp_request(request)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy", "service": "mcp-router"}


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
