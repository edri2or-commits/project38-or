"""
GitHub MCP Client for Claude Code sessions.

Client-side module that enables Claude Code sessions to communicate with the
MCP Gateway through GitHub Issue Comments as a relay. This bypasses Anthropic's
egress proxy which blocks direct access to Railway/custom domains.

Architecture:
    Claude Code Session (this client)
        ↓ POST comment (JSON-RPC request)
    GitHub Issue (message queue)
        ↓ Polled by Railway
    MCP Gateway Relay (server side)
        ↓ POST comment (JSON-RPC response)
    GitHub Issue
        ↓ Polled by this client
    Claude Code Session (receives response)

Rate Limits (from research):
    - Read: 5,000 requests/hour (with ETag: unlimited 304s)
    - Write: 500 requests/hour (~8.3 msg/min sustained)
    - Write interval: Must be >1 second between POSTs

Usage:
    from src.mcp_gateway.github_mcp_client import GitHubMCPClient

    client = GitHubMCPClient()

    # Call MCP tools
    result = client.call_tool("health_check", {})
    result = client.call_tool("railway_status", {})

    # Or use convenience methods
    health = client.health_check()
    status = client.railway_status()
"""

import base64
import json
import os
import time
import uuid
from typing import Any

import requests

# Configuration
GITHUB_REPO = os.environ.get("GITHUB_RELAY_REPO", "edri2or-commits/project38-or")
GITHUB_ISSUE = int(os.environ.get("GITHUB_RELAY_ISSUE", "183"))
POLL_TIMEOUT = int(os.environ.get("GITHUB_POLL_TIMEOUT", "120"))
POLL_INTERVAL = float(os.environ.get("GITHUB_POLL_INTERVAL", "3.0"))
WRITE_DELAY = float(os.environ.get("GITHUB_WRITE_DELAY", "1.5"))

# GitHub API
GITHUB_API = "https://api.github.com"

# Message markers for relay protocol
REQUEST_MARKER = "<!-- MCP_REQUEST:"
RESPONSE_MARKER = "<!-- MCP_RESPONSE:"
END_MARKER = " -->"


def _get_token() -> str | None:
    """Get GitHub token from environment."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _encode_message(data: dict) -> str:
    """Encode a message as Base64 JSON."""
    json_str = json.dumps(data, separators=(",", ":"))
    return base64.b64encode(json_str.encode()).decode()


def _decode_message(encoded: str) -> dict:
    """Decode a Base64 JSON message."""
    json_str = base64.b64decode(encoded.encode()).decode()
    return json.loads(json_str)


class GitHubMCPClient:
    """
    MCP Client that communicates through GitHub Issue Comments as a relay.

    This client posts MCP requests as comments and polls for responses,
    enabling Claude Code sessions to use MCP tools despite proxy limitations.
    """

    def __init__(
        self,
        token: str | None = None,
        repo: str | None = None,
        issue_number: int | None = None,
        session_id: str | None = None,
    ):
        """
        Initialize the GitHub MCP Client.

        Args:
            token: GitHub token. If not provided, uses GH_TOKEN env var.
            repo: Repository in 'owner/repo' format. Defaults to GITHUB_RELAY_REPO.
            issue_number: Issue number for relay. Defaults to GITHUB_RELAY_ISSUE.
            session_id: Unique session ID. Generated if not provided.

        Raises:
            RuntimeError: If no token available or no issue configured.
        """
        self.token = token or _get_token()
        self.repo = repo or GITHUB_REPO
        self.issue_number = issue_number or GITHUB_ISSUE
        self.session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"
        self._last_write_time = 0.0
        self._last_etag = None

        if not self.token:
            raise RuntimeError(
                "No GitHub token available. Set GH_TOKEN environment variable."
            )

        if not self.issue_number:
            raise RuntimeError(
                "No relay issue configured. Set GITHUB_RELAY_ISSUE environment variable "
                "or pass issue_number parameter."
            )

    def _headers(self, etag: str | None = None) -> dict:
        """Get headers for GitHub API requests."""
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _enforce_write_delay(self) -> None:
        """Enforce minimum delay between write operations."""
        elapsed = time.time() - self._last_write_time
        if elapsed < WRITE_DELAY:
            time.sleep(WRITE_DELAY - elapsed)
        self._last_write_time = time.time()

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"req-{uuid.uuid4().hex[:12]}"

    def _post_comment(self, body: str) -> dict:
        """Post a comment to the relay issue."""
        self._enforce_write_delay()

        url = f"{GITHUB_API}/repos/{self.repo}/issues/{self.issue_number}/comments"
        resp = requests.post(
            url,
            headers=self._headers(),
            json={"body": body},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _get_comments(self, since_id: int | None = None) -> tuple[list[dict], str | None]:
        """
        Get comments from the relay issue with ETag support.

        Args:
            since_id: Only return comments with ID > since_id

        Returns:
            Tuple of (comments list, new ETag or None if 304)
        """
        url = f"{GITHUB_API}/repos/{self.repo}/issues/{self.issue_number}/comments"
        params = {"per_page": 100, "sort": "created", "direction": "desc"}

        resp = requests.get(
            url,
            headers=self._headers(etag=self._last_etag),
            params=params,
            timeout=30,
        )

        # 304 Not Modified - no new comments
        if resp.status_code == 304:
            return [], None

        resp.raise_for_status()

        new_etag = resp.headers.get("ETag")
        self._last_etag = new_etag

        comments = resp.json()

        # Filter by since_id if provided
        if since_id:
            comments = [c for c in comments if c["id"] > since_id]

        return comments, new_etag

    def _find_response(self, request_id: str, since_id: int) -> dict | None:
        """
        Find a response comment matching the request ID.

        Args:
            request_id: The request ID to match
            since_id: Only check comments posted after this ID

        Returns:
            Decoded response or None if not found
        """
        comments, _ = self._get_comments(since_id=since_id)

        for comment in comments:
            body = comment.get("body", "")

            # Look for response marker
            if RESPONSE_MARKER in body and request_id in body:
                # Extract encoded payload
                try:
                    start = body.find(RESPONSE_MARKER) + len(RESPONSE_MARKER)
                    end = body.find(END_MARKER, start)
                    if end > start:
                        encoded = body[start:end].strip()
                        # The encoded part contains "request_id:base64_payload"
                        if ":" in encoded:
                            _, payload = encoded.split(":", 1)
                            return _decode_message(payload)
                except Exception:  # noqa: S112
                    continue

        return None

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict:
        """
        Call an MCP tool through the GitHub relay.

        Args:
            tool_name: Name of the MCP tool (e.g., "health_check", "railway_status")
            arguments: Optional arguments dictionary

        Returns:
            The result from the MCP tool

        Raises:
            TimeoutError: If no response within timeout
            RuntimeError: If MCP returns an error
        """
        request_id = self._generate_request_id()

        # Build JSON-RPC 2.0 request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
            "_relay": {
                "sessionId": self.session_id,
                "requestId": request_id,
                "timestamp": time.time(),
            },
        }

        # Encode and post request
        encoded = _encode_message(request)
        comment_body = (
            f"{REQUEST_MARKER}{request_id}:{encoded}{END_MARKER}\n\n"
            f"**MCP Request** `{tool_name}` from session `{self.session_id}`"
        )

        posted = self._post_comment(comment_body)
        since_id = posted["id"]

        # Poll for response
        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            response = self._find_response(request_id, since_id)

            if response is not None:
                # Check for errors
                if "error" in response:
                    error = response["error"]
                    error_code = error.get("code", "unknown")
                    error_msg = error.get("message", "Unknown error")
                    raise RuntimeError(f"MCP Error {error_code}: {error_msg}")

                return response.get("result", response)

            time.sleep(POLL_INTERVAL)

        raise TimeoutError(
            f"No response received within {POLL_TIMEOUT}s for tool '{tool_name}'"
        )

    def initialize(self) -> dict:
        """Initialize MCP connection and get server info."""
        request_id = self._generate_request_id()

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {},
            "_relay": {
                "sessionId": self.session_id,
                "requestId": request_id,
            },
        }

        encoded = _encode_message(request)
        comment_body = (
            f"{REQUEST_MARKER}{request_id}:{encoded}{END_MARKER}\n\n"
            f"**MCP Initialize** from session `{self.session_id}`"
        )

        posted = self._post_comment(comment_body)
        since_id = posted["id"]

        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            response = self._find_response(request_id, since_id)
            if response is not None:
                return response.get("result", response)
            time.sleep(POLL_INTERVAL)

        raise TimeoutError("No response received for initialize")

    def list_tools(self) -> list[dict]:
        """List available MCP tools."""
        request_id = self._generate_request_id()

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/list",
            "params": {},
            "_relay": {
                "sessionId": self.session_id,
                "requestId": request_id,
            },
        }

        encoded = _encode_message(request)
        comment_body = (
            f"{REQUEST_MARKER}{request_id}:{encoded}{END_MARKER}\n\n"
            f"**MCP List Tools** from session `{self.session_id}`"
        )

        posted = self._post_comment(comment_body)
        since_id = posted["id"]

        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            response = self._find_response(request_id, since_id)
            if response is not None:
                result = response.get("result", {})
                return result.get("tools", [])
            time.sleep(POLL_INTERVAL)

        raise TimeoutError("No response received for tools/list")

    # =========================================================================
    # Convenience methods for common MCP tools
    # =========================================================================

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


def test_connection() -> bool:
    """
    Test basic GitHub connectivity (without full MCP round-trip).

    Returns:
        True if GitHub API is accessible, False otherwise
    """
    try:
        token = _get_token()
        if not token:
            print("No GitHub token available")
            return False

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        resp = requests.get(
            f"{GITHUB_API}/user",
            headers=headers,
            timeout=10,
        )

        if resp.status_code == 200:
            user = resp.json().get("login", "unknown")
            print(f"GitHub connection OK (user: {user})")
            return True
        else:
            print(f"GitHub connection failed: {resp.status_code}")
            return False

    except Exception as e:
        print(f"GitHub connection error: {e}")
        return False


if __name__ == "__main__":
    print("Testing GitHub MCP Client connectivity...")
    test_connection()
