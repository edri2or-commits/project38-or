"""
GCS MCP Client Bridge.

Client-side module for Claude Code sessions to communicate with the MCP Gateway
through GCS relay. This bypasses Anthropic's egress proxy limitations.

Uses the GCS JSON API directly with requests (no google-cloud-storage dependency).

Usage:
    from src.mcp_gateway.gcs_mcp_client import GCSMCPClient

    client = GCSMCPClient()

    # Call MCP tools
    result = client.call_tool("health_check", {})
    result = client.call_tool("railway_status", {})

    # Or use convenience methods
    health = client.health_check()
    status = client.railway_status()
"""

import os
import time
import uuid
from typing import Any

import requests

# Configuration
GCS_BUCKET = os.environ.get("GCS_BUCKET", "project38-mcp-relay")
GCS_PREFIX = os.environ.get("GCS_PREFIX", "mcp-relay")
POLL_TIMEOUT = int(os.environ.get("GCS_POLL_TIMEOUT", "60"))
POLL_INTERVAL = float(os.environ.get("GCS_POLL_INTERVAL", "1.0"))

# GCS API base URL
GCS_API_BASE = "https://storage.googleapis.com"
GCS_UPLOAD_BASE = "https://storage.googleapis.com/upload/storage/v1"
GCS_API_V1 = "https://storage.googleapis.com/storage/v1"


def _get_access_token() -> str | None:
    """
    Get access token for GCS.

    Tries multiple methods:
    1. GOOGLE_ACCESS_TOKEN environment variable
    2. gcloud auth print-access-token command
    3. Metadata server (if running in GCP)

    Returns:
        Access token string or None if not available
    """
    # Method 1: Environment variable
    token = os.environ.get("GOOGLE_ACCESS_TOKEN")
    if token:
        return token

    # Method 2: gcloud command
    try:
        import subprocess

        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:  # noqa: S110 - Expected failure if gcloud not installed
        pass

    # Method 3: GCE metadata server
    try:
        resp = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
            timeout=2,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception:  # noqa: S110 - Expected failure if not in GCP
        pass

    return None


class GCSMCPClient:
    """
    MCP Client that communicates through GCS relay.

    This client writes MCP requests to GCS and polls for responses,
    enabling Claude Code sessions to use MCP tools despite proxy limitations.
    """

    def __init__(self, session_id: str | None = None, access_token: str | None = None):
        """
        Initialize the GCS MCP Client.

        Args:
            session_id: Optional session ID. If not provided, generates a unique one.
            access_token: Optional GCS access token. If not provided, tries to get one.
        """
        self.session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"
        self.access_token = access_token or _get_access_token()
        self.bucket = GCS_BUCKET

        if not self.access_token:
            raise RuntimeError(
                "No GCS access token available. Set GOOGLE_ACCESS_TOKEN environment variable "
                "or ensure gcloud is configured."
            )

    def _get_headers(self) -> dict:
        """Get headers for GCS API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"req-{uuid.uuid4().hex[:8]}"

    def _get_paths(self, request_id: str) -> tuple[str, str]:
        """Get request and response paths for a given request ID."""
        request_path = f"{GCS_PREFIX}/requests/{self.session_id}/{request_id}.json"
        response_path = f"{GCS_PREFIX}/responses/{self.session_id}/{request_id}.json"
        return request_path, response_path

    def _upload_object(self, path: str, data: dict) -> bool:
        """Upload a JSON object to GCS."""
        url = f"{GCS_UPLOAD_BASE}/b/{self.bucket}/o?uploadType=media&name={path}"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        resp = requests.post(url, headers=headers, json=data, timeout=30)
        return resp.status_code in (200, 201)

    def _download_object(self, path: str) -> dict | None:
        """Download a JSON object from GCS."""
        url = f"{GCS_API_BASE}/{self.bucket}/{path}"
        headers = self._get_headers()

        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return None

    def _object_exists(self, path: str) -> bool:
        """Check if an object exists in GCS."""
        url = f"{GCS_API_V1}/b/{self.bucket}/o/{requests.utils.quote(path, safe='')}"
        headers = self._get_headers()

        resp = requests.get(url, headers=headers, timeout=10)
        return resp.status_code == 200

    def _delete_object(self, path: str) -> bool:
        """Delete an object from GCS."""
        url = f"{GCS_API_V1}/b/{self.bucket}/o/{requests.utils.quote(path, safe='')}"
        headers = self._get_headers()

        resp = requests.delete(url, headers=headers, timeout=10)
        return resp.status_code in (200, 204, 404)

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict:
        """
        Call an MCP tool through the GCS relay.

        Args:
            tool_name: Name of the MCP tool to call (e.g., "health_check", "railway_status")
            arguments: Optional dictionary of arguments to pass to the tool

        Returns:
            The result from the MCP tool

        Raises:
            TimeoutError: If no response received within timeout
            RuntimeError: If the MCP call returns an error
        """
        request_id = self._generate_request_id()
        request_path, response_path = self._get_paths(request_id)

        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
            "_bridge": {
                "sessionId": self.session_id,
                "requestId": request_id,
                "responsePath": response_path,
            },
        }

        # Upload request to GCS
        if not self._upload_object(request_path, request):
            raise RuntimeError(f"Failed to upload request to GCS: {request_path}")

        # Poll for response
        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            response = self._download_object(response_path)

            if response is not None:
                # Clean up
                self._delete_object(response_path)

                # Check for errors
                if "error" in response:
                    error = response["error"]
                    error_code = error.get("code", "unknown")
                    error_msg = error.get("message", "Unknown error")
                    raise RuntimeError(f"MCP Error {error_code}: {error_msg}")

                return response.get("result", response)

            time.sleep(POLL_INTERVAL)

        # Timeout - clean up request if still there
        self._delete_object(request_path)

        raise TimeoutError(
            f"No response received within {POLL_TIMEOUT} seconds for tool '{tool_name}'"
        )

    def initialize(self) -> dict:
        """
        Initialize MCP connection.

        Returns:
            Server info and capabilities
        """
        request_id = self._generate_request_id()
        request_path, response_path = self._get_paths(request_id)

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {},
            "_bridge": {
                "sessionId": self.session_id,
                "requestId": request_id,
                "responsePath": response_path,
            },
        }

        if not self._upload_object(request_path, request):
            raise RuntimeError("Failed to upload initialize request")

        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            response = self._download_object(response_path)
            if response is not None:
                self._delete_object(response_path)
                return response.get("result", response)
            time.sleep(POLL_INTERVAL)

        raise TimeoutError("No response received for initialize")

    def list_tools(self) -> list[dict]:
        """
        List available MCP tools.

        Returns:
            List of available tools with their descriptions
        """
        request_id = self._generate_request_id()
        request_path, response_path = self._get_paths(request_id)

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/list",
            "params": {},
            "_bridge": {
                "sessionId": self.session_id,
                "requestId": request_id,
                "responsePath": response_path,
            },
        }

        if not self._upload_object(request_path, request):
            raise RuntimeError("Failed to upload tools/list request")

        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            response = self._download_object(response_path)
            if response is not None:
                self._delete_object(response_path)
                result = response.get("result", {})
                return result.get("tools", [])
            time.sleep(POLL_INTERVAL)

        raise TimeoutError("No response received for tools/list")

    # Convenience methods for common tools
    def health_check(self) -> dict:
        """Check health of all services."""
        return self.call_tool("health_check", {})

    def get_metrics(self) -> dict:
        """Get system metrics."""
        return self.call_tool("get_metrics", {})

    def deployment_health(self) -> dict:
        """Get comprehensive deployment health."""
        return self.call_tool("deployment_health", {})

    def railway_status(self) -> dict:
        """Get Railway deployment status."""
        return self.call_tool("railway_status", {})

    def railway_deployments(self, limit: int = 5) -> dict:
        """Get recent Railway deployments."""
        return self.call_tool("railway_deployments", {"limit": limit})

    def railway_deploy(self) -> dict:
        """Trigger a new Railway deployment."""
        return self.call_tool("railway_deploy", {})

    def railway_rollback(self, deployment_id: str | None = None) -> dict:
        """Rollback to a previous deployment."""
        args = {}
        if deployment_id:
            args["deployment_id"] = deployment_id
        return self.call_tool("railway_rollback", args)

    def n8n_list(self) -> dict:
        """List n8n workflows."""
        return self.call_tool("n8n_list", {})

    def n8n_trigger(self, workflow_id: str, data: dict | None = None) -> dict:
        """Trigger an n8n workflow."""
        args = {"workflow_id": workflow_id}
        if data:
            args["data"] = data
        return self.call_tool("n8n_trigger", args)

    def n8n_status(self, workflow_id: str) -> dict:
        """Check n8n workflow status."""
        return self.call_tool("n8n_status", {"workflow_id": workflow_id})

    # Google Workspace tools
    def gmail_send(self, to: str, subject: str, body: str) -> dict:
        """Send an email via Gmail."""
        return self.call_tool("gmail_send", {"to": to, "subject": subject, "body": body})

    def gmail_search(self, query: str, max_results: int = 10) -> dict:
        """Search Gmail."""
        return self.call_tool("gmail_search", {"query": query, "max_results": max_results})

    def gmail_list(self, max_results: int = 10) -> dict:
        """List recent emails."""
        return self.call_tool("gmail_list", {"max_results": max_results})

    def calendar_list_events(self, max_results: int = 10) -> dict:
        """List upcoming calendar events."""
        return self.call_tool("calendar_list_events", {"max_results": max_results})

    def calendar_create_event(
        self, summary: str, start: str, end: str, description: str = ""
    ) -> dict:
        """Create a calendar event."""
        return self.call_tool(
            "calendar_create_event",
            {"summary": summary, "start": start, "end": end, "description": description},
        )

    def drive_list_files(self, max_results: int = 10) -> dict:
        """List Drive files."""
        return self.call_tool("drive_list_files", {"max_results": max_results})

    def drive_create_folder(self, name: str, parent_id: str | None = None) -> dict:
        """Create a Drive folder."""
        args = {"name": name}
        if parent_id:
            args["parent_id"] = parent_id
        return self.call_tool("drive_create_folder", args)

    def sheets_read(self, spreadsheet_id: str, range_name: str) -> dict:
        """Read from a spreadsheet."""
        return self.call_tool(
            "sheets_read", {"spreadsheet_id": spreadsheet_id, "range": range_name}
        )

    def sheets_write(self, spreadsheet_id: str, range_name: str, values: list[list]) -> dict:
        """Write to a spreadsheet."""
        return self.call_tool(
            "sheets_write",
            {"spreadsheet_id": spreadsheet_id, "range": range_name, "values": values},
        )

    def sheets_create(self, title: str) -> dict:
        """Create a new spreadsheet."""
        return self.call_tool("sheets_create", {"title": title})

    def docs_create(self, title: str) -> dict:
        """Create a new document."""
        return self.call_tool("docs_create", {"title": title})

    def docs_read(self, document_id: str) -> dict:
        """Read a document."""
        return self.call_tool("docs_read", {"document_id": document_id})

    def docs_append(self, document_id: str, text: str) -> dict:
        """Append text to a document."""
        return self.call_tool("docs_append", {"document_id": document_id, "text": text})


# Quick test function
def test_connection() -> bool:
    """
    Test the GCS MCP relay connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = GCSMCPClient()
        result = client.initialize()
        print("Connection successful!")
        print(f"Server: {result.get('serverInfo', {}).get('name', 'unknown')}")
        print(f"Version: {result.get('serverInfo', {}).get('version', 'unknown')}")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing GCS MCP Client...")
    test_connection()
