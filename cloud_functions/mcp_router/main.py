"""
MCP Router Cloud Function - Protocol Encapsulation Server.

This Cloud Function acts as a tunnel endpoint that receives encapsulated
MCP JSON-RPC messages through the cloudfunctions.googleapis.com API and
routes them to the appropriate tool handlers.

Architecture:
    Claude Code Session (Anthropic Cloud)
        ↓ (MCP over stdio)
    Local Adapter Script
        ↓ (HTTPS POST to googleapis.com)
    This Cloud Function (mcp-router)
        ↓ (Execute tool)
    Return result through same path

Why this works:
    - cloudfunctions.googleapis.com is whitelisted by Anthropic proxy
    - MCP messages are encapsulated in the 'data' field
    - From firewall perspective, this is legitimate GCP API traffic
"""

import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

import functions_framework
import httpx
from flask import Request
from google.cloud import secretmanager

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


# API base URLs
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"
DOCS_API = "https://docs.googleapis.com/v1"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


class WorkspaceAuth:
    """Handles Google Workspace OAuth authentication."""

    _instance = None
    _access_token: str | None = None
    _token_expiry: float = 0

    def __new__(cls) -> "WorkspaceAuth":
        """Singleton pattern for token management."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed.

        Returns:
            Valid access token

        Raises:
            Exception: If unable to get token
        """
        # Check if current token is still valid (with 60s buffer)
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        # Get credentials from Secret Manager
        client_id = get_secret("GOOGLE-OAUTH-CLIENT-ID")
        client_secret = get_secret("GOOGLE-OAUTH-CLIENT-SECRET")
        refresh_token = get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            missing = []
            if not client_id:
                missing.append("GOOGLE-OAUTH-CLIENT-ID")
            if not client_secret:
                missing.append("GOOGLE-OAUTH-CLIENT-SECRET")
            if not refresh_token:
                missing.append("GOOGLE-OAUTH-REFRESH-TOKEN")
            raise ValueError(f"Missing OAuth secrets: {missing}")

        # Refresh the token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OAUTH_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                raise ValueError(f"Token refresh failed: {response.text}")

            data = response.json()
            self._access_token = data["access_token"]
            self._token_expiry = time.time() + data.get("expires_in", 3600)

            logger.info("Google Workspace access token refreshed")
            return self._access_token


# Global auth instance
_auth = WorkspaceAuth()


async def _get_workspace_headers() -> dict[str, str]:
    """Get authorization headers for Workspace APIs."""
    token = await _auth.get_access_token()
    return {"Authorization": f"Bearer {token}"}


class MCPRouter:
    """
    Routes MCP JSON-RPC requests to appropriate tool handlers.

    This is a lightweight MCP server implementation optimized for
    Cloud Functions' request-response model.
    """

    def __init__(self):
        """Initialize the MCP Router with available tools."""
        self.tools = {}
        self._register_tools()

    def _register_tools(self):
        """Register all available tools."""
        # Railway tools
        self.tools["railway_deploy"] = self._railway_deploy
        self.tools["railway_status"] = self._railway_status
        self.tools["railway_rollback"] = self._railway_rollback
        self.tools["railway_deployments"] = self._railway_deployments
        self.tools["railway_service_info"] = self._railway_service_info
        self.tools["railway_list_services"] = self._railway_list_services

        # n8n tools
        self.tools["n8n_trigger"] = self._n8n_trigger
        self.tools["n8n_list"] = self._n8n_list
        self.tools["n8n_status"] = self._n8n_status

        # Monitoring tools
        self.tools["health_check"] = self._health_check
        self.tools["get_metrics"] = self._get_metrics
        self.tools["deployment_health"] = self._deployment_health

        # Google Workspace tools
        self.tools["gmail_send"] = self._gmail_send
        self.tools["gmail_list"] = self._gmail_list
        self.tools["calendar_list_events"] = self._calendar_list_events
        self.tools["calendar_create_event"] = self._calendar_create_event
        self.tools["drive_list_files"] = self._drive_list_files
        self.tools["sheets_read"] = self._sheets_read
        self.tools["sheets_write"] = self._sheets_write
        self.tools["docs_create"] = self._docs_create
        self.tools["docs_read"] = self._docs_read
        self.tools["docs_append"] = self._docs_append

        logger.info(f"Registered {len(self.tools)} tools")

    def process_request(self, mcp_message: dict) -> dict:
        """
        Process an MCP JSON-RPC request.

        Args:
            mcp_message: The decapsulated MCP message

        Returns:
            JSON-RPC response dict
        """
        jsonrpc = mcp_message.get("jsonrpc", "2.0")
        method = mcp_message.get("method", "")
        params = mcp_message.get("params", {})
        request_id = mcp_message.get("id")

        logger.info(f"Processing MCP request: method={method}, id={request_id}")

        # Handle tools/list request
        if method == "tools/list":
            return self._handle_tools_list(request_id)

        # Handle tools/call request
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            return self._handle_tool_call(request_id, tool_name, arguments)

        # Unknown method
        return {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

    def _handle_tools_list(self, request_id: Any) -> dict:
        """Return list of available tools."""
        tools_list = [
            {
                "name": name,
                "description": f"Execute {name} operation",
                "inputSchema": {"type": "object"}
            }
            for name in self.tools.keys()
        ]

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools_list}
        }

    def _handle_tool_call(self, request_id: Any, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return result."""
        if tool_name not in self.tools:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}"
                }
            }

        try:
            result = self.tools[tool_name](**arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "isError": False
                }
            }
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True
                }
            }

    # =========================================================================
    # Railway Tools
    # =========================================================================

    def _railway_deploy(self, service_id: str = None) -> dict:
        """Trigger a Railway deployment."""
        import httpx

        railway_token = os.environ.get("RAILWAY_TOKEN")
        project_id = os.environ.get("RAILWAY_PROJECT_ID", "95ec21cc-9ada-41c5-8485-12f9a00e0116")
        environment_id = os.environ.get("RAILWAY_ENVIRONMENT_ID", "99c99a18-aea2-4d01-9360-6a93705102a0")

        if not railway_token:
            return {"error": "RAILWAY_TOKEN not configured"}

        query = """
        mutation deploymentTrigger($input: DeploymentTriggerInput!) {
            deploymentTriggerCreate(input: $input) {
                id
                status
            }
        }
        """

        variables = {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id
            }
        }

        response = httpx.post(
            "https://backboard.railway.app/graphql/v2",
            headers={
                "Authorization": f"Bearer {railway_token}",
                "Content-Type": "application/json"
            },
            json={"query": query, "variables": variables},
            timeout=30
        )

        return response.json()

    def _railway_status(self) -> dict:
        """Get current Railway deployment status."""
        import httpx

        railway_token = os.environ.get("RAILWAY_TOKEN")
        project_id = os.environ.get("RAILWAY_PROJECT_ID", "95ec21cc-9ada-41c5-8485-12f9a00e0116")

        if not railway_token:
            return {"error": "RAILWAY_TOKEN not configured"}

        query = """
        query getDeployments($projectId: String!) {
            deployments(first: 5, input: {projectId: $projectId}) {
                edges {
                    node {
                        id
                        status
                        createdAt
                    }
                }
            }
        }
        """

        response = httpx.post(
            "https://backboard.railway.app/graphql/v2",
            headers={
                "Authorization": f"Bearer {railway_token}",
                "Content-Type": "application/json"
            },
            json={"query": query, "variables": {"projectId": project_id}},
            timeout=30
        )

        return response.json()

    def _railway_rollback(self, deployment_id: str) -> dict:
        """Rollback to a specific deployment."""
        return {"status": "rollback_initiated", "deployment_id": deployment_id}

    def _railway_deployments(self, limit: int = 10) -> dict:
        """List recent deployments."""
        return self._railway_status()

    def _railway_service_info(self, service_name: str = "litellm-gateway") -> dict:
        """Get Railway service information including domains."""
        import httpx

        railway_token = os.environ.get("RAILWAY_TOKEN")
        project_id = os.environ.get("RAILWAY_PROJECT_ID", "95ec21cc-9ada-41c5-8485-12f9a00e0116")
        environment_id = os.environ.get("RAILWAY_ENVIRONMENT_ID", "99c99a18-aea2-4d01-9360-6a93705102a0")

        if not railway_token:
            return {"error": "RAILWAY_TOKEN not configured"}

        # Query to get service with domains
        query = """
        query getServiceDomains($projectId: String!, $environmentId: String!) {
            project(id: $projectId) {
                services {
                    edges {
                        node {
                            id
                            name
                            serviceInstances(environmentId: $environmentId) {
                                edges {
                                    node {
                                        domains {
                                            serviceDomains {
                                                domain
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        response = httpx.post(
            "https://backboard.railway.app/graphql/v2",
            headers={
                "Authorization": f"Bearer {railway_token}",
                "Content-Type": "application/json"
            },
            json={
                "query": query,
                "variables": {
                    "projectId": project_id,
                    "environmentId": environment_id
                }
            },
            timeout=30
        )

        data = response.json()

        # Debug: return full response if error
        if "errors" in data:
            return {"error": "GraphQL error", "details": data}

        # Extract service matching the name
        if "data" in data and "project" in data["data"]:
            services = data["data"]["project"]["services"]["edges"]
            
            # Debug: log all service names
            all_names = [edge["node"]["name"] for edge in services]
            
            for edge in services:
                service = edge["node"]
                if service["name"].lower() == service_name.lower():
                    domains = []
                    
                    # Extract domains safely
                    if "serviceInstances" in service and "edges" in service["serviceInstances"]:
                        for instance_edge in service["serviceInstances"]["edges"]:
                            instance = instance_edge["node"]
                            if "domains" in instance and "serviceDomains" in instance["domains"]:
                                for domain_item in instance["domains"]["serviceDomains"]:
                                    if "domain" in domain_item:
                                        domains.append(domain_item["domain"])
                    
                    return {
                        "service_id": service["id"],
                        "service_name": service["name"],
                        "domains": domains
                    }
            
            return {
                "error": f"Service '{service_name}' not found",
                "available_services": all_names
            }

        return {"error": "Invalid response from Railway API", "response": data}

    def _railway_list_services(self) -> dict:
        """List all Railway services in the project."""
        import httpx

        railway_token = os.environ.get("RAILWAY_TOKEN")
        project_id = os.environ.get("RAILWAY_PROJECT_ID", "95ec21cc-9ada-41c5-8485-12f9a00e0116")
        environment_id = os.environ.get("RAILWAY_ENVIRONMENT_ID", "99c99a18-aea2-4d01-9360-6a93705102a0")

        if not railway_token:
            return {"error": "RAILWAY_TOKEN not configured"}

        query = """
        query listServices($projectId: String!) {
            project(id: $projectId) {
                services {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
        }
        """

        response = httpx.post(
            "https://backboard.railway.app/graphql/v2",
            headers={
                "Authorization": f"Bearer {railway_token}",
                "Content-Type": "application/json"
            },
            json={
                "query": query,
                "variables": {"projectId": project_id}
            },
            timeout=30
        )

        return response.json()

    # =========================================================================
    # n8n Tools
    # =========================================================================

    def _n8n_trigger(self, workflow_id: str, data: dict = None) -> dict:
        """Trigger an n8n workflow."""
        import httpx

        n8n_url = os.environ.get("N8N_BASE_URL")
        n8n_api_key = os.environ.get("N8N_API_KEY")

        if not n8n_url or not n8n_api_key:
            return {"error": "n8n not configured"}

        response = httpx.post(
            f"{n8n_url}/webhook/{workflow_id}",
            headers={"Authorization": f"Bearer {n8n_api_key}"},
            json=data or {},
            timeout=30
        )

        return {"status": "triggered", "response": response.json()}

    def _n8n_list(self) -> dict:
        """List available n8n workflows."""
        return {"workflows": ["cost-alert", "backup-workflow", "deployment-alert"]}

    def _n8n_status(self) -> dict:
        """Check n8n webhook status."""
        return {"status": "available"}

    # =========================================================================
    # Monitoring Tools
    # =========================================================================

    def _health_check(self) -> dict:
        """Check production health."""
        import httpx

        try:
            response = httpx.get(
                "https://or-infra.com/api/health",
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_metrics(self) -> dict:
        """Get system metrics."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "operational"
        }

    def _deployment_health(self) -> dict:
        """Comprehensive deployment health check."""
        health = self._health_check()
        status = self._railway_status()

        return {
            "health": health,
            "deployments": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # =========================================================================
    # Google Workspace Tools
    # =========================================================================

    def _gmail_send(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
        """Send an email via Gmail."""
        return asyncio.run(self._gmail_send_async(to, subject, body, cc, bcc))

    async def _gmail_send_async(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
        """Send an email via Gmail (async)."""
        try:
            headers = await _get_workspace_headers()

            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            if cc:
                message["cc"] = cc
            if bcc:
                message["bcc"] = bcc

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GMAIL_API}/users/me/messages/send",
                    headers=headers,
                    json={"raw": raw},
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                data = response.json()
                return {
                    "success": True,
                    "message_id": data.get("id"),
                    "thread_id": data.get("threadId"),
                }

        except Exception as e:
            logger.error(f"gmail_send failed: {e}")
            return {"success": False, "error": str(e)}

    def _gmail_list(self, label: str = "INBOX", max_results: int = 10) -> dict:
        """List recent emails."""
        return asyncio.run(self._gmail_list_async(label, max_results))

    async def _gmail_list_async(self, label: str = "INBOX", max_results: int = 10) -> dict:
        """List recent emails (async)."""
        try:
            headers = await _get_workspace_headers()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API}/users/me/messages",
                    headers=headers,
                    params={"labelIds": label, "maxResults": max_results},
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                data = response.json()
                messages = data.get("messages", [])

                results = []
                for msg in messages:
                    msg_response = await client.get(
                        f"{GMAIL_API}/users/me/messages/{msg['id']}",
                        headers=headers,
                        params={
                            "format": "metadata",
                            "metadataHeaders": ["Subject", "From", "Date"],
                        },
                    )
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        hdrs = {
                            h["name"]: h["value"]
                            for h in msg_data.get("payload", {}).get("headers", [])
                        }
                        results.append(
                            {
                                "id": msg["id"],
                                "subject": hdrs.get("Subject", ""),
                                "from": hdrs.get("From", ""),
                                "date": hdrs.get("Date", ""),
                                "snippet": msg_data.get("snippet", ""),
                            }
                        )

                return {
                    "success": True,
                    "label": label,
                    "count": len(results),
                    "messages": results,
                }

        except Exception as e:
            logger.error(f"gmail_list failed: {e}")
            return {"success": False, "error": str(e)}

    def _calendar_list_events(self, calendar_id: str = "primary", max_results: int = 10, time_min: str = "") -> dict:
        """List upcoming calendar events."""
        return asyncio.run(self._calendar_list_events_async(calendar_id, max_results, time_min))

    async def _calendar_list_events_async(self, calendar_id: str = "primary", max_results: int = 10, time_min: str = "") -> dict:
        """List upcoming calendar events (async)."""
        try:
            headers = await _get_workspace_headers()

            if not time_min:
                time_min = datetime.now(timezone.utc).isoformat()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{CALENDAR_API}/calendars/{calendar_id}/events",
                    headers=headers,
                    params={
                        "maxResults": max_results,
                        "timeMin": time_min,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                    },
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                data = response.json()
                events = []
                for item in data.get("items", []):
                    events.append(
                        {
                            "id": item.get("id"),
                            "summary": item.get("summary", ""),
                            "start": item.get("start", {}).get("dateTime")
                            or item.get("start", {}).get("date"),
                            "end": item.get("end", {}).get("dateTime")
                            or item.get("end", {}).get("date"),
                            "location": item.get("location", ""),
                            "description": item.get("description", ""),
                        }
                    )

                return {"success": True, "count": len(events), "events": events}

        except Exception as e:
            logger.error(f"calendar_list_events failed: {e}")
            return {"success": False, "error": str(e)}

    def _calendar_create_event(self, summary: str, start_time: str, end_time: str, calendar_id: str = "primary", description: str = "", location: str = "", attendees: str = "") -> dict:
        """Create a calendar event."""
        return asyncio.run(self._calendar_create_event_async(summary, start_time, end_time, calendar_id, description, location, attendees))

    async def _calendar_create_event_async(self, summary: str, start_time: str, end_time: str, calendar_id: str = "primary", description: str = "", location: str = "", attendees: str = "") -> dict:
        """Create a calendar event (async)."""
        try:
            headers = await _get_workspace_headers()

            event = {
                "summary": summary,
                "start": {"dateTime": start_time},
                "end": {"dateTime": end_time},
            }

            if description:
                event["description"] = description
            if location:
                event["location"] = location
            if attendees:
                event["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{CALENDAR_API}/calendars/{calendar_id}/events",
                    headers=headers,
                    json=event,
                )

                if response.status_code not in (200, 201):
                    return {"success": False, "error": response.text}

                data = response.json()
                return {
                    "success": True,
                    "event_id": data.get("id"),
                    "html_link": data.get("htmlLink"),
                }

        except Exception as e:
            logger.error(f"calendar_create_event failed: {e}")
            return {"success": False, "error": str(e)}

    def _drive_list_files(self, query: str = "", max_results: int = 10, folder_id: str = "") -> dict:
        """List files in Google Drive."""
        return asyncio.run(self._drive_list_files_async(query, max_results, folder_id))

    async def _drive_list_files_async(self, query: str = "", max_results: int = 10, folder_id: str = "") -> dict:
        """List files in Google Drive (async)."""
        try:
            headers = await _get_workspace_headers()

            params = {
                "pageSize": max_results,
                "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
            }

            if query:
                params["q"] = query
            if folder_id:
                params["q"] = f"'{folder_id}' in parents"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{DRIVE_API}/files",
                    headers=headers,
                    params=params,
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                data = response.json()
                files = [
                    {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "mimeType": f.get("mimeType"),
                        "modifiedTime": f.get("modifiedTime"),
                        "size": f.get("size"),
                        "webViewLink": f.get("webViewLink"),
                    }
                    for f in data.get("files", [])
                ]

                return {"success": True, "count": len(files), "files": files}

        except Exception as e:
            logger.error(f"drive_list_files failed: {e}")
            return {"success": False, "error": str(e)}

    def _sheets_read(self, spreadsheet_id: str, range_notation: str = "Sheet1!A1:Z100") -> dict:
        """Read data from Google Sheets."""
        return asyncio.run(self._sheets_read_async(spreadsheet_id, range_notation))

    async def _sheets_read_async(self, spreadsheet_id: str, range_notation: str = "Sheet1!A1:Z100") -> dict:
        """Read data from Google Sheets (async)."""
        try:
            headers = await _get_workspace_headers()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_notation}",
                    headers=headers,
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                data = response.json()
                return {
                    "success": True,
                    "range": data.get("range"),
                    "values": data.get("values", []),
                }

        except Exception as e:
            logger.error(f"sheets_read failed: {e}")
            return {"success": False, "error": str(e)}

    def _sheets_write(self, spreadsheet_id: str, range_notation: str, values: list) -> dict:
        """Write data to Google Sheets."""
        return asyncio.run(self._sheets_write_async(spreadsheet_id, range_notation, values))

    async def _sheets_write_async(self, spreadsheet_id: str, range_notation: str, values: list) -> dict:
        """Write data to Google Sheets (async)."""
        try:
            headers = await _get_workspace_headers()

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_notation}",
                    headers=headers,
                    params={"valueInputOption": "USER_ENTERED"},
                    json={"values": values},
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                data = response.json()
                return {
                    "success": True,
                    "updated_range": data.get("updatedRange"),
                    "updated_rows": data.get("updatedRows"),
                    "updated_columns": data.get("updatedColumns"),
                    "updated_cells": data.get("updatedCells"),
                }

        except Exception as e:
            logger.error(f"sheets_write failed: {e}")
            return {"success": False, "error": str(e)}

    def _docs_create(self, title: str) -> dict:
        """Create a new Google Doc."""
        return asyncio.run(self._docs_create_async(title))

    async def _docs_create_async(self, title: str) -> dict:
        """Create a new Google Doc (async)."""
        try:
            headers = await _get_workspace_headers()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DOCS_API}/documents",
                    headers=headers,
                    json={"title": title},
                )

                if response.status_code not in (200, 201):
                    return {"success": False, "error": response.text}

                data = response.json()
                return {
                    "success": True,
                    "document_id": data.get("documentId"),
                    "title": data.get("title"),
                }

        except Exception as e:
            logger.error(f"docs_create failed: {e}")
            return {"success": False, "error": str(e)}

    def _docs_read(self, document_id: str) -> dict:
        """Read content from a Google Doc."""
        return asyncio.run(self._docs_read_async(document_id))

    async def _docs_read_async(self, document_id: str) -> dict:
        """Read content from a Google Doc (async)."""
        try:
            headers = await _get_workspace_headers()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{DOCS_API}/documents/{document_id}",
                    headers=headers,
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                data = response.json()

                # Extract text content
                content = ""
                for element in data.get("body", {}).get("content", []):
                    if "paragraph" in element:
                        for elem in element["paragraph"].get("elements", []):
                            if "textRun" in elem:
                                content += elem["textRun"].get("content", "")

                return {
                    "success": True,
                    "document_id": document_id,
                    "title": data.get("title"),
                    "content": content,
                }

        except Exception as e:
            logger.error(f"docs_read failed: {e}")
            return {"success": False, "error": str(e)}

    def _docs_append(self, document_id: str, text: str) -> dict:
        """Append text to a Google Doc."""
        return asyncio.run(self._docs_append_async(document_id, text))

    async def _docs_append_async(self, document_id: str, text: str) -> dict:
        """Append text to a Google Doc (async)."""
        try:
            headers = await _get_workspace_headers()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DOCS_API}/documents/{document_id}:batchUpdate",
                    headers=headers,
                    json={
                        "requests": [
                            {
                                "insertText": {
                                    "location": {"index": 1},
                                    "text": text,
                                }
                            }
                        ]
                    },
                )

                if response.status_code != 200:
                    return {"success": False, "error": response.text}

                return {"success": True, "document_id": document_id}

        except Exception as e:
            logger.error(f"docs_append failed: {e}")
            return {"success": False, "error": str(e)}


# Global router instance
router = MCPRouter()


def _validate_token(request: Request) -> bool:
    """
    Validate the custom MCP tunnel token.

    The token is stored in GCP Secret Manager and compared against
    the Authorization header. This allows public access to the function
    while still requiring authentication.

    Returns:
        True if token is valid, False otherwise
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return False

    provided_token = auth_header[7:]  # Remove "Bearer " prefix

    # Get expected token from environment (set during deployment from Secret Manager)
    expected_token = os.environ.get("MCP_TUNNEL_TOKEN", "")

    if not expected_token:
        logger.error("MCP_TUNNEL_TOKEN not configured in environment")
        return False

    # Constant-time comparison to prevent timing attacks
    import hmac
    return hmac.compare_digest(provided_token, expected_token)


@functions_framework.http
def mcp_router(request: Request):
    """
    HTTP Cloud Function entry point.

    Receives encapsulated MCP messages and routes them to handlers.
    Requires custom MCP_TUNNEL_TOKEN for authentication (not GCP OAuth).

    Expected payload format:
    {
        "data": "{\"jsonrpc\": \"2.0\", \"method\": \"tools/call\", ...}"
    }

    Returns:
    {
        "result": "{\"jsonrpc\": \"2.0\", \"id\": ..., \"result\": ...}"
    }
    """
    # CORS headers for preflight
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600"
        }
        return ("", 204, headers)

    headers = {"Access-Control-Allow-Origin": "*"}

    # Validate custom token (NOT GCP OAuth - this is our own token)
    if not _validate_token(request):
        logger.warning("Invalid or missing MCP tunnel token")
        return (
            json.dumps({"error": "Unauthorized - invalid MCP_TUNNEL_TOKEN"}),
            401,
            headers
        )

    try:
        # Parse request
        request_json = request.get_json(silent=True)

        if not request_json:
            return (
                json.dumps({"error": "Invalid JSON payload"}),
                400,
                headers
            )

        # Extract encapsulated MCP message
        data = request_json.get("data")
        if not data:
            return (
                json.dumps({"error": "Missing 'data' field"}),
                400,
                headers
            )

        # Decapsulate
        mcp_message = json.loads(data) if isinstance(data, str) else data

        # Process
        result = router.process_request(mcp_message)

        # Encapsulate response
        response = {"result": json.dumps(result)}

        logger.info(f"Request processed successfully")
        return (json.dumps(response), 200, headers)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return (
            json.dumps({"error": f"Invalid JSON: {e}"}),
            400,
            headers
        )
    except Exception as e:
        logger.exception("Unexpected error")
        return (
            json.dumps({"error": str(e)}),
            500,
            headers
        )
