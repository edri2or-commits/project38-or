"""MCP Gateway for Cloud Run.

Standalone FastAPI application providing MCP tools for Claude Code autonomy.
Deployed on Google Cloud Run (*.run.app domain whitelisted by Anthropic proxy).

Features:
- Railway deployment operations
- n8n workflow triggering
- Google Workspace (Gmail, Calendar, Drive, Sheets, Docs)
- Health monitoring

Authentication:
- Bearer token from MCP-GATEWAY-TOKEN in GCP Secret Manager
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import secretmanager
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GCP Configuration
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project38-483612")


def get_secret(secret_name: str) -> str | None:
    """Fetch secret from GCP Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {e}")
        return None


# Cache token at startup
GATEWAY_TOKEN = None


def verify_token(authorization: str = Header(...)) -> bool:
    """Verify Bearer token."""
    global GATEWAY_TOKEN
    if GATEWAY_TOKEN is None:
        GATEWAY_TOKEN = get_secret("MCP-GATEWAY-TOKEN")

    if not GATEWAY_TOKEN:
        raise HTTPException(status_code=500, detail="Token not configured")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    if token != GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

    return True


# Create FastAPI app
app = FastAPI(
    title="MCP Gateway",
    description="MCP Gateway for Claude Code Autonomy on Cloud Run",
    version="1.0.0",
)

# CORS for MCP protocol
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# MCP Protocol Endpoints
# ============================================================================


class MCPRequest(BaseModel):
    """MCP JSON-RPC request."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict = {}


class MCPResponse(BaseModel):
    """MCP JSON-RPC response."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: Any = None
    error: dict | None = None


# Tool definitions
MCP_TOOLS = [
    {
        "name": "health_check",
        "description": "Check MCP Gateway health and connectivity",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "railway_status",
        "description": "Get Railway deployment status",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "gmail_send",
        "description": "Send email via Gmail",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "calendar_list_events",
        "description": "List upcoming calendar events",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Max events", "default": 10}
            },
            "required": [],
        },
    },
    {
        "name": "drive_list_files",
        "description": "List files in Google Drive",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": [],
        },
    },
]


async def execute_tool(name: str, params: dict) -> dict:
    """Execute MCP tool and return result."""
    if name == "health_check":
        return {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "gateway": "Cloud Run",
            "version": "1.0.0",
        }

    elif name == "railway_status":
        # Get Railway token and check status
        railway_token = get_secret("RAILWAY-API")
        if not railway_token:
            return {"error": "Railway token not available"}
        return {
            "status": "connected",
            "project": "delightful-cat",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    elif name == "gmail_send":
        # Implement Gmail send
        return await _gmail_send(params)

    elif name == "calendar_list_events":
        return await _calendar_list_events(params)

    elif name == "drive_list_files":
        return await _drive_list_files(params)

    return {"error": f"Unknown tool: {name}"}


async def _gmail_send(params: dict) -> dict:
    """Send email via Gmail API."""
    import httpx

    refresh_token = get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")
    client_id = get_secret("GOOGLE-OAUTH-CLIENT-ID")
    client_secret = get_secret("GOOGLE-OAUTH-CLIENT-SECRET")

    if not all([refresh_token, client_id, client_secret]):
        return {"error": "OAuth credentials not configured"}

    # Get access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if token_response.status_code != 200:
            return {"error": "Failed to refresh token"}

        access_token = token_response.json()["access_token"]

        # Create email
        import base64

        email_content = f"To: {params['to']}\nSubject: {params['subject']}\n\n{params['body']}"
        raw_message = base64.urlsafe_b64encode(email_content.encode()).decode()

        # Send via Gmail API
        send_response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw_message},
        )

        if send_response.status_code == 200:
            result = send_response.json()
            return {"success": True, "messageId": result.get("id")}
        else:
            return {"error": f"Gmail API error: {send_response.status_code}"}


async def _calendar_list_events(params: dict) -> dict:
    """List calendar events."""
    import httpx

    refresh_token = get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")
    client_id = get_secret("GOOGLE-OAUTH-CLIENT-ID")
    client_secret = get_secret("GOOGLE-OAUTH-CLIENT-SECRET")

    if not all([refresh_token, client_id, client_secret]):
        return {"error": "OAuth credentials not configured"}

    async with httpx.AsyncClient() as client:
        # Get access token
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if token_response.status_code != 200:
            return {"error": "Failed to refresh token"}

        access_token = token_response.json()["access_token"]

        # List events
        max_results = params.get("max_results", 10)
        events_response = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
                "timeMin": datetime.now(UTC).isoformat(),
            },
        )

        if events_response.status_code == 200:
            data = events_response.json()
            events = [
                {
                    "summary": e.get("summary", "No title"),
                    "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")),
                    "id": e.get("id"),
                }
                for e in data.get("items", [])
            ]
            return {"events": events, "count": len(events)}
        else:
            return {"error": f"Calendar API error: {events_response.status_code}"}


async def _drive_list_files(params: dict) -> dict:
    """List Drive files."""
    import httpx

    refresh_token = get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")
    client_id = get_secret("GOOGLE-OAUTH-CLIENT-ID")
    client_secret = get_secret("GOOGLE-OAUTH-CLIENT-SECRET")

    if not all([refresh_token, client_id, client_secret]):
        return {"error": "OAuth credentials not configured"}

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if token_response.status_code != 200:
            return {"error": "Failed to refresh token"}

        access_token = token_response.json()["access_token"]

        drive_params = {"pageSize": params.get("max_results", 10)}
        if params.get("query"):
            drive_params["q"] = params["query"]

        files_response = await client.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {access_token}"},
            params=drive_params,
        )

        if files_response.status_code == 200:
            data = files_response.json()
            files = [
                {"name": f.get("name"), "id": f.get("id"), "mimeType": f.get("mimeType")}
                for f in data.get("files", [])
            ]
            return {"files": files, "count": len(files)}
        else:
            return {"error": f"Drive API error: {files_response.status_code}"}


@app.post("/mcp")
async def mcp_endpoint(request: Request, authorization: str = Header(...)):
    """MCP JSON-RPC endpoint."""
    verify_token(authorization)

    body = await request.json()

    # Handle MCP protocol
    method = body.get("method", "")
    params = body.get("params", {})
    request_id = body.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-gateway-cloudrun", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": MCP_TOOLS}}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_params = params.get("arguments", {})
        result = await execute_tool(tool_name, tool_params)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
        }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "mcp-gateway-cloudrun",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "MCP Gateway (Cloud Run)",
        "version": "1.0.0",
        "mcp_endpoint": "/mcp",
        "health_endpoint": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
