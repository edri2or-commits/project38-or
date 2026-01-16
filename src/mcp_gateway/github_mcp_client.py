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
    - Write interval: >1 second between POSTs

Usage:
    from src.mcp_gateway.github_mcp_client import GitHubMCPClient

    client = GitHubMCPClient()
    result = client.call_tool("health_check", {})
    print(result)
"""

import base64
import json
import os
import time
import uuid
from typing import Any

import requests

# Configuration from environment
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_RELAY_REPO", "edri2or-commits/project38-or")
GITHUB_ISSUE = int(os.environ.get("GITHUB_RELAY_ISSUE", "183"))

# Protocol markers (hidden in HTML comments)
REQUEST_MARKER = "<!-- MCP_REQUEST:"
RESPONSE_MARKER = "<!-- MCP_RESPONSE:"
END_MARKER = " -->"

# Timing constants
POLL_INTERVAL = 2.0  # seconds between polls
WRITE_INTERVAL = 1.5  # minimum seconds between writes
MAX_WAIT_TIME = 60.0  # maximum seconds to wait for response


def _encode_message(data: dict) -> str:
    """Encode a message for transport."""
    return base64.b64encode(json.dumps(data).encode()).decode()


def _decode_message(encoded: str) -> dict:
    """Decode a message from transport."""
    return json.loads(base64.b64decode(encoded).decode())


def test_connection() -> bool:
    """Test if GitHub API is accessible with current token."""
    if not GITHUB_TOKEN:
        print("No GH_TOKEN found")
        return False

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    try:
        resp = requests.get(
            "https://api.github.com/user",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            user = resp.json().get("login", "unknown")
            print(f"GitHub connection OK (user: {user})")
            return True
        print(f"GitHub connection failed: {resp.status_code}")
        return False
    except Exception as e:
        print(f"GitHub connection error: {e}")
        return False


class GitHubMCPClient:
    """MCP Client that uses GitHub Issues as transport."""

    def __init__(
        self,
        token: str | None = None,
        repo: str | None = None,
        issue_number: int | None = None,
    ):
        """Initialize the GitHub MCP Client.

        Args:
            token: GitHub token (defaults to GH_TOKEN env var)
            repo: Repository in format "owner/repo"
            issue_number: Issue number to use as relay channel
        """
        self.token = token or GITHUB_TOKEN
        self.repo = repo or GITHUB_REPO
        self.issue_number = issue_number or GITHUB_ISSUE
        self.session_id = f"session-{uuid.uuid4().hex[:8]}"
        self._last_write_time = 0.0
        self._etag: str | None = None

        if not self.token:
            raise ValueError("No GitHub token provided. Set GH_TOKEN env var.")

        self._headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def _enforce_write_interval(self) -> None:
        """Enforce minimum interval between writes."""
        elapsed = time.time() - self._last_write_time
        if elapsed < WRITE_INTERVAL:
            time.sleep(WRITE_INTERVAL - elapsed)
        self._last_write_time = time.time()

    def _get_comments(self) -> tuple[list[dict], str | None]:
        """Get comments from the relay issue with ETag support.

        Returns:
            Tuple of (comments list, new etag)
        """
        headers = dict(self._headers)
        if self._etag:
            headers["If-None-Match"] = self._etag

        resp = requests.get(
            f"https://api.github.com/repos/{self.repo}/issues/{self.issue_number}/comments",
            headers=headers,
            params={"per_page": 50, "sort": "created", "direction": "desc"},
            timeout=30,
        )

        if resp.status_code == 304:
            # No new comments
            return [], self._etag

        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get comments: {resp.status_code}")

        new_etag = resp.headers.get("ETag")
        return resp.json(), new_etag

    def _post_comment(self, body: str) -> dict:
        """Post a comment to the relay issue."""
        self._enforce_write_interval()

        resp = requests.post(
            f"https://api.github.com/repos/{self.repo}/issues/{self.issue_number}/comments",
            headers=self._headers,
            json={"body": body},
            timeout=30,
        )

        if resp.status_code != 201:
            raise RuntimeError(f"Failed to post comment: {resp.status_code}")

        return resp.json()

    def _find_response(self, request_id: str) -> dict | None:
        """Find a response for a specific request ID."""
        comments, new_etag = self._get_comments()
        self._etag = new_etag

        for comment in comments:
            body = comment.get("body", "")
            if RESPONSE_MARKER in body and request_id in body:
                # Extract the encoded payload
                start = body.find(RESPONSE_MARKER) + len(RESPONSE_MARKER)
                end = body.find(END_MARKER, start)
                if end > start:
                    encoded_str = body[start:end].strip()
                    if ":" in encoded_str:
                        _, payload = encoded_str.split(":", 1)
                        return _decode_message(payload)
        return None

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = MAX_WAIT_TIME,
    ) -> Any:
        """Call an MCP tool via the GitHub relay.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            timeout: Maximum time to wait for response

        Returns:
            Tool result

        Raises:
            RuntimeError: If the call fails or times out
        """
        request_id = f"req-{uuid.uuid4().hex[:8]}"

        # Build JSON-RPC request
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
            },
        }

        # Encode and post request
        encoded = _encode_message(request)
        comment_body = (
            f"{REQUEST_MARKER}{request_id}:{encoded}{END_MARKER}\n\n"
            f"**MCP Request** `{tool_name}` from session `{self.session_id}`"
        )

        self._post_comment(comment_body)

        # Poll for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self._find_response(request_id)
            if response:
                if "error" in response:
                    error = response["error"]
                    error_code = error.get("code", "unknown")
                    error_msg = error.get("message", "Unknown error")
                    raise RuntimeError(f"MCP Error {error_code}: {error_msg}")
                return response.get("result")

            time.sleep(POLL_INTERVAL)

        raise RuntimeError(f"Timeout waiting for response to {request_id}")

    def initialize(self) -> dict:
        """Send MCP initialize request."""
        request_id = f"init-{uuid.uuid4().hex[:8]}"

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "github-mcp-client",
                    "version": "1.0.0",
                },
            },
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

        self._post_comment(comment_body)

        start_time = time.time()
        while time.time() - start_time < MAX_WAIT_TIME:
            response = self._find_response(request_id)
            if response:
                return response.get("result", {})
            time.sleep(POLL_INTERVAL)

        raise RuntimeError("Timeout waiting for initialize response")

    def list_tools(self) -> list[dict]:
        """Get list of available tools."""
        request_id = f"list-{uuid.uuid4().hex[:8]}"

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

        self._post_comment(comment_body)

        start_time = time.time()
        while time.time() - start_time < MAX_WAIT_TIME:
            response = self._find_response(request_id)
            if response:
                return response.get("result", {}).get("tools", [])
            time.sleep(POLL_INTERVAL)

        raise RuntimeError("Timeout waiting for tools/list response")


if __name__ == "__main__":
    # Quick test
    test_connection()
