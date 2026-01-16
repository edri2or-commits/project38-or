"""
GitHub MCP Relay Service for Railway.

Server-side component that polls GitHub Issue Comments for MCP requests,
executes them against the local MCP Gateway, and posts responses.

Architecture:
    GitHub Issue (message queue)
        ↑ Polled by this relay
    MCP Gateway Relay (this service)
        ↓ Executes MCP tools locally
    GitHub Issue
        ↓ Response posted as comment
    Claude Code Session (reads response)

This service runs as a background task alongside the MCP Gateway on Railway.

Rate Limits (enforced):
    - Polling: Every 3 seconds with ETag (free if 304)
    - Writing: >1.5 seconds between POSTs
    - Sustained: Max 500 writes/hour

Usage:
    # Start relay as background task
    from src.mcp_gateway.github_relay import GitHubMCPRelay

    relay = GitHubMCPRelay()
    await relay.start()

    # Or run directly
    python -m src.mcp_gateway.github_relay
"""

import asyncio
import base64
import json
import logging
import time
from typing import Any

import httpx

from .config import get_config

logger = logging.getLogger(__name__)

# Constants
GITHUB_API = "https://api.github.com"
POLL_INTERVAL = 3.0  # seconds
WRITE_DELAY = 1.5  # seconds between writes
MAX_RETRIES = 3

# Message markers (must match client)
REQUEST_MARKER = "<!-- MCP_REQUEST:"
RESPONSE_MARKER = "<!-- MCP_RESPONSE:"
END_MARKER = " -->"


def _encode_message(data: dict) -> str:
    """Encode a message as Base64 JSON."""
    json_str = json.dumps(data, separators=(",", ":"))
    return base64.b64encode(json_str.encode()).decode()


def _decode_message(encoded: str) -> dict:
    """Decode a Base64 JSON message."""
    json_str = base64.b64decode(encoded.encode()).decode()
    return json.loads(json_str)


class GitHubMCPRelay:
    """
    MCP Relay that bridges GitHub Issue Comments to local MCP tools.

    This service:
    1. Polls GitHub Issue for new request comments
    2. Decodes and validates JSON-RPC requests
    3. Executes the requested MCP tool
    4. Posts the response as a new comment
    """

    def __init__(self):
        """Initialize the relay with configuration from MCP Gateway."""
        config = get_config()

        self.repo = config.github_relay_repo
        self.issue_number = config.github_relay_issue
        self.app_id = config.github_app_id
        self.installation_id = config.github_installation_id
        self.private_key = config.github_private_key

        # State
        self._last_etag: str | None = None
        self._last_write_time: float = 0.0
        self._processed_ids: set[str] = set()
        self._installation_token: str | None = None
        self._token_expires_at: float = 0.0
        self._running: bool = False

        # MCP tool handlers (imported on first use)
        self._tool_handlers: dict[str, Any] | None = None

        if not self.issue_number:
            logger.warning(
                "GitHub relay issue not configured. "
                "Set GITHUB_RELAY_ISSUE environment variable."
            )

    async def _get_installation_token(self) -> str:
        """Get or refresh GitHub App installation token."""
        import jwt

        # Check if current token is still valid (with 5 min buffer)
        if self._installation_token and time.time() < self._token_expires_at - 300:
            return self._installation_token

        # Generate JWT
        now = int(time.time())
        payload = {
            "iat": now - 60,  # 1 minute in the past for clock skew
            "exp": now + 600,  # 10 minutes
            "iss": self.app_id,
        }

        jwt_token = jwt.encode(payload, self.private_key, algorithm="RS256")

        # Exchange JWT for installation token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API}/app/installations/{self.installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=10.0,
            )
            response.raise_for_status()

            data = response.json()
            self._installation_token = data["token"]

            # Parse expiration
            from datetime import datetime

            expires_at_str = data["expires_at"].replace("Z", "+00:00")
            expires_dt = datetime.fromisoformat(expires_at_str)
            self._token_expires_at = expires_dt.timestamp()

            logger.debug("Refreshed GitHub App installation token")
            return self._installation_token

    def _headers(self, token: str, etag: str | None = None) -> dict:
        """Get headers for GitHub API requests."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if etag:
            headers["If-None-Match"] = etag
        return headers

    async def _enforce_write_delay(self) -> None:
        """Enforce minimum delay between write operations."""
        elapsed = time.time() - self._last_write_time
        if elapsed < WRITE_DELAY:
            await asyncio.sleep(WRITE_DELAY - elapsed)
        self._last_write_time = time.time()

    async def _get_comments(self) -> list[dict]:
        """
        Get recent comments from the relay issue with ETag support.

        Returns:
            List of comments (empty if 304 Not Modified)
        """
        token = await self._get_installation_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API}/repos/{self.repo}/issues/{self.issue_number}/comments",
                headers=self._headers(token, etag=self._last_etag),
                params={"per_page": 50, "sort": "created", "direction": "desc"},
                timeout=30.0,
            )

            # 304 Not Modified - no new comments
            if response.status_code == 304:
                return []

            response.raise_for_status()

            # Update ETag for next request
            self._last_etag = response.headers.get("ETag")

            return response.json()

    async def _post_response(self, request_id: str, response_data: dict) -> None:
        """Post a response comment to the relay issue."""
        await self._enforce_write_delay()

        token = await self._get_installation_token()
        encoded = _encode_message(response_data)

        # Format: visible info + hidden encoded payload
        body = (
            f"{RESPONSE_MARKER}{request_id}:{encoded}{END_MARKER}\n\n"
            f"**MCP Response** for `{request_id}`\n\n"
            f"```json\n{json.dumps(response_data.get('result', {}), indent=2)[:400]}\n```"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API}/repos/{self.repo}/issues/{self.issue_number}/comments",
                headers=self._headers(token),
                json={"body": body},
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info(f"Posted response for request {request_id}")

    def _parse_request(self, comment: dict) -> tuple[str, dict] | None:
        """
        Parse a request from a comment.

        Returns:
            Tuple of (request_id, request_data) or None if not a valid request
        """
        body = comment.get("body", "")

        if REQUEST_MARKER not in body:
            return None

        try:
            start = body.find(REQUEST_MARKER) + len(REQUEST_MARKER)
            end = body.find(END_MARKER, start)
            if end <= start:
                return None

            encoded = body[start:end].strip()
            if ":" not in encoded:
                return None

            request_id, payload = encoded.split(":", 1)

            # Skip already processed requests
            if request_id in self._processed_ids:
                return None

            request_data = _decode_message(payload)
            return request_id, request_data

        except Exception as e:
            logger.warning(f"Failed to parse request from comment: {e}")
            return None

    async def _get_tool_handlers(self) -> dict:
        """Lazily load MCP tool handlers."""
        if self._tool_handlers is not None:
            return self._tool_handlers

        # Import the MCP tools
        from .tools import monitoring, n8n, railway

        self._tool_handlers = {
            # Railway tools
            "railway_deploy": railway.trigger_deployment,
            "railway_status": railway.get_deployment_status,
            "railway_deployments": railway.get_recent_deployments,
            "railway_rollback": railway.rollback_deployment,
            # n8n tools
            "n8n_list": n8n.list_workflows,
            "n8n_trigger": n8n.trigger_workflow,
            "n8n_status": n8n.get_workflow_status,
            # Monitoring tools
            "health_check": monitoring.health_check,
            "get_metrics": monitoring.get_metrics,
            "deployment_health": monitoring.deployment_health,
        }

        return self._tool_handlers

    async def _execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Execute an MCP tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        handlers = await self._get_tool_handlers()

        if tool_name not in handlers:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            handler = handlers[tool_name]
            result = await handler(**arguments)
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return {"error": str(e), "type": type(e).__name__}

    async def _process_request(self, request_id: str, request: dict) -> None:
        """Process a single MCP request."""
        logger.info(f"Processing request {request_id}")

        method = request.get("method", "")
        params = request.get("params", {})

        # Handle different JSON-RPC methods
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "serverInfo": {
                        "name": "GitHub MCP Relay",
                        "version": "1.0.0",
                    },
                    "capabilities": {
                        "tools": True,
                    },
                },
            }

        elif method == "tools/list":
            handlers = await self._get_tool_handlers()
            tools = [
                {"name": name, "description": f"MCP tool: {name}"}
                for name in handlers.keys()
            ]
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools},
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = await self._execute_tool(tool_name, arguments)

            if "error" in result:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": result["error"],
                    },
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result.get("result", result),
                }

        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}",
                },
            }

        # Mark as processed before posting (to avoid re-processing on retry)
        self._processed_ids.add(request_id)

        # Post response
        await self._post_response(request_id, response)

    async def poll_once(self) -> int:
        """
        Poll for and process new requests.

        Returns:
            Number of requests processed
        """
        if not self.issue_number:
            return 0

        try:
            comments = await self._get_comments()
            processed = 0

            for comment in comments:
                parsed = self._parse_request(comment)
                if parsed:
                    request_id, request_data = parsed
                    await self._process_request(request_id, request_data)
                    processed += 1

            return processed

        except Exception as e:
            logger.exception(f"Error polling for requests: {e}")
            return 0

    async def start(self) -> None:
        """Start the relay polling loop."""
        if not self.issue_number:
            logger.error("Cannot start relay: no issue configured")
            return

        if not self.private_key:
            logger.error("Cannot start relay: no GitHub App private key configured")
            return

        logger.info(
            f"Starting GitHub MCP Relay for {self.repo}#{self.issue_number}"
        )
        self._running = True

        while self._running:
            try:
                processed = await self.poll_once()
                if processed > 0:
                    logger.debug(f"Processed {processed} requests")
            except Exception as e:
                logger.exception(f"Relay loop error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    def stop(self) -> None:
        """Stop the relay polling loop."""
        logger.info("Stopping GitHub MCP Relay")
        self._running = False


async def main():
    """Run the relay as a standalone service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    relay = GitHubMCPRelay()
    await relay.start()


if __name__ == "__main__":
    asyncio.run(main())
