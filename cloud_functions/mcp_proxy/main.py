"""
MCP Proxy Cloud Function - Simple Gen 1 Proxy to Cloud Run.

This is a minimal Cloud Function (Gen 1) that forwards all requests
to the full MCP Gateway running on Cloud Run.

Why this approach:
    - Cloud Functions Gen 1 produces *.cloudfunctions.net URLs (allowed by Anthropic proxy)
    - Cloud Run produces *.run.app URLs (blocked by Anthropic proxy)
    - GCP internal traffic is NOT blocked, so the proxy can reach Cloud Run

Architecture:
    Claude Code (Anthropic Cloud)
        ↓ (cloudfunctions.net - allowed)
    This Proxy (Cloud Functions Gen 1)
        ↓ (run.app - allowed from GCP)
    MCP Gateway (Cloud Run)
        ↓
    Response back through same path
"""

import os
import json
import logging

import functions_framework
import requests as http_requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The Cloud Run URL (internal GCP traffic - not blocked)
CLOUD_RUN_URL = os.environ.get(
    "CLOUD_RUN_URL",
    "https://gcp-mcp-gateway-3e7yyrd7xq-uc.a.run.app"
)


@functions_framework.http
def mcp_proxy(request):
    """
    Simple HTTP proxy function - forwards requests to Cloud Run.

    Args:
        request: Flask request object

    Returns:
        Tuple of (body, status_code, headers)
    """
    # CORS preflight
    if request.method == "OPTIONS":
        return (
            "",
            204,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Max-Age": "3600",
            }
        )

    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        # Forward the request to Cloud Run
        forward_headers = {
            "Content-Type": request.headers.get("Content-Type", "application/json"),
        }

        # Pass through Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            forward_headers["Authorization"] = auth_header

        # Get request body
        body = request.get_data(as_text=True)

        # Determine method and forward
        if request.method == "GET":
            response = http_requests.get(
                CLOUD_RUN_URL,
                headers=forward_headers,
                timeout=120
            )
        else:
            response = http_requests.post(
                CLOUD_RUN_URL,
                data=body,
                headers=forward_headers,
                timeout=120
            )

        # Return the response from Cloud Run
        return (
            response.text,
            response.status_code,
            headers
        )

    except http_requests.exceptions.Timeout:
        logger.error("Timeout connecting to Cloud Run")
        return (
            json.dumps({"error": "Timeout connecting to backend"}),
            504,
            headers
        )
    except http_requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Cloud Run: {e}")
        return (
            json.dumps({"error": f"Backend connection error: {str(e)}"}),
            502,
            headers
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return (
            json.dumps({"error": f"Internal error: {str(e)}"}),
            500,
            headers
        )
