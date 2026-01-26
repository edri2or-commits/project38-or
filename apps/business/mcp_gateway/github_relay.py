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
    - Max writes: 500/hour (~8 msg/min sustained)
"""

import asyncio
import base64
import json
import logging
import time
from typing import Any

import httpx

from apps.business.mcp_gateway.config import MCPGatewayConfig, load_config

# Protocol markers (must match client)
REQUEST_MARKER = "<!-- MCP_REQUEST:"
RESPONSE_MARKER = "<!-- MCP_RESPONSE:"
END_MARKER = " -->"

# Timing constants
POLL_INTERVAL = 3.0  # seconds between polls
WRITE_INTERVAL = 1.5  # minimum seconds between writes

logger = logging.getLogger(__name__)


def _encode_message(data: dict) -> str:
    """Encode a message for transport."""
    return base64.b64encode(json.dumps(data).encode()).decode()


def _decode_message(encoded: str) -> dict:
    """Decode a message from transport."""
    return json.loads(base64.b64decode(encoded).decode())


class GitHubMCPRelay:
    """MCP Relay service that uses GitHub Issues as transport."""

    def __init__(
        self,
        config: MCPGatewayConfig,
        github_client: httpx.AsyncClient | None = None,
    ):
        """Initialize the GitHub MCP Relay.

        Args:
            config: MCP Gateway configuration
            github_client: Optional httpx client for GitHub API
        """
        self.config = config
        self.repo = config.github_relay_repo
        self.issue_number = config.github_relay_issue
        self._last_write_time = 0.0
        self._etag: str | None = None
        self._processed_requests: set[str] = set()
        self._running = False

        # Initialize GitHub client
        if github_client:
            self._github_client = github_client
        else:
            self._github_client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )

        self._github_token: str | None = None

    async def _get_github_token(self) -> str:
        """Get GitHub token from GitHub App credentials.

        Uses the GitHubAppClient to generate an installation access token.
        """
        if self._github_token:
            return self._github_token

        # Import here to avoid circular imports
        from apps.business.integrations.github_app_client import GitHubAppClient

        try:
            client = GitHubAppClient(
                app_id=self.config.github_app_id,
                private_key=self.config.github_private_key,
                installation_id=int(self.config.github_installation_id),
            )
            self._github_token = client.get_installation_token()
            return self._github_token
        except Exception as e:
            logger.error(f"Failed to get GitHub token: {e}")
            raise

    async def _enforce_write_interval(self) -> None:
        """Enforce minimum interval between writes."""
        elapsed = time.time() - self._last_write_time
        if elapsed < WRITE_INTERVAL:
            await asyncio.sleep(WRITE_INTERVAL - elapsed)
        self._last_write_time = time.time()

    async def _get_comments(self) -> tuple[list[dict], str | None]:
        """Get comments from the relay issue with ETag support."""
        token = await self._get_github_token()
        headers = {"Authorization": f"token {token}"}
        if self._etag:
            headers["If-None-Match"] = self._etag

        resp = await self._github_client.get(
            f"/repos/{self.repo}/issues/{self.issue_number}/comments",
            headers=headers,
            params={"per_page": 50, "sort": "created", "direction": "desc"},
        )

        if resp.status_code == 304:
            return [], self._etag

        if resp.status_code != 200:
            logger.error(f"Failed to get comments: {resp.status_code}")
            return [], self._etag

        new_etag = resp.headers.get("ETag")
        return resp.json(), new_etag

    async def _post_response(
        self,
        request_id: str,
        response_data: dict,
    ) -> bool:
        """Post a response comment to the relay issue."""
        await self._enforce_write_interval()

        token = await self._get_github_token()
        encoded = _encode_message(response_data)

        # Truncate result preview for readability
        result_preview = json.dumps(response_data.get("result", response_data), indent=2)
        if len(result_preview) > 400:
            result_preview = result_preview[:400] + "..."

        body = (
            f"{RESPONSE_MARKER}{request_id}:{encoded}{END_MARKER}\n\n"
            f"**MCP Response** for `{request_id}`\n\n"
            f"```json\n{result_preview}\n```"
        )

        resp = await self._github_client.post(
            f"/repos/{self.repo}/issues/{self.issue_number}/comments",
            headers={"Authorization": f"token {token}"},
            json={"body": body},
        )

        if resp.status_code != 201:
            logger.error(f"Failed to post response: {resp.status_code}")
            return False

        logger.info(f"Posted response for {request_id}")
        return True

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict:
        """Execute an MCP tool locally.

        This calls the MCP Gateway's internal tool execution.
        """
        # Import tools dynamically to avoid circular imports
        try:
            if tool_name == "health_check":
                from apps.business.mcp_gateway.tools.monitoring import health_check

                result = await health_check()
                return {"result": result}

            elif tool_name == "railway_status":
                from apps.business.mcp_gateway.tools.railway import railway_status

                result = await railway_status()
                return {"result": result}

            elif tool_name == "railway_deploy":
                from apps.business.mcp_gateway.tools.railway import railway_deploy

                result = await railway_deploy()
                return {"result": result}

            elif tool_name == "railway_rollback":
                from apps.business.mcp_gateway.tools.railway import railway_rollback

                result = await railway_rollback()
                return {"result": result}

            elif tool_name == "n8n_list":
                from apps.business.mcp_gateway.tools.n8n import n8n_list

                result = await n8n_list()
                return {"result": result}

            elif tool_name == "n8n_trigger":
                from apps.business.mcp_gateway.tools.n8n import n8n_trigger

                workflow_id = arguments.get("workflow_id", "")
                result = await n8n_trigger(workflow_id)
                return {"result": result}

            else:
                return {
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}",
                    }
                }

        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return {
                "error": {
                    "code": -32000,
                    "message": str(e),
                }
            }

    async def _process_request(self, comment: dict) -> None:
        """Process a single MCP request from a comment."""
        body = comment.get("body", "")

        # Check if this is a request
        if REQUEST_MARKER not in body:
            return

        # Extract request data
        start = body.find(REQUEST_MARKER) + len(REQUEST_MARKER)
        end = body.find(END_MARKER, start)
        if end <= start:
            return

        encoded_str = body[start:end].strip()
        if ":" not in encoded_str:
            return

        request_id, payload = encoded_str.split(":", 1)

        # Skip if already processed
        if request_id in self._processed_requests:
            return

        self._processed_requests.add(request_id)
        logger.info(f"Processing request: {request_id}")

        try:
            request_data = _decode_message(payload)
        except Exception as e:
            logger.error(f"Failed to decode request {request_id}: {e}")
            return

        # Handle different methods
        method = request_data.get("method", "")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "github-mcp-relay",
                        "version": "1.0.0",
                    },
                },
            }

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "health_check",
                            "description": "Check health of all services",
                        },
                        {
                            "name": "railway_status",
                            "description": "Get Railway deployment status",
                        },
                        {
                            "name": "railway_deploy",
                            "description": "Trigger new deployment",
                        },
                        {
                            "name": "railway_rollback",
                            "description": "Rollback to previous deployment",
                        },
                        {"name": "n8n_list", "description": "List n8n workflows"},
                        {
                            "name": "n8n_trigger",
                            "description": "Trigger n8n workflow",
                        },
                    ]
                },
            }

        elif method == "tools/call":
            params = request_data.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            result = await self._execute_tool(tool_name, arguments)

            if "error" in result:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": result["error"],
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result["result"],
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

        await self._post_response(request_id, response)

    async def poll_once(self) -> int:
        """Poll for and process new requests.

        Returns:
            Number of requests processed
        """
        comments, new_etag = await self._get_comments()
        self._etag = new_etag

        processed = 0
        for comment in comments:
            if REQUEST_MARKER in comment.get("body", ""):
                await self._process_request(comment)
                processed += 1

        return processed

    async def run(self) -> None:
        """Run the relay service continuously."""
        logger.info(f"Starting GitHub MCP Relay for {self.repo}#{self.issue_number}")
        self._running = True

        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.exception(f"Poll error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    def stop(self) -> None:
        """Stop the relay service."""
        self._running = False
        logger.info("Stopping GitHub MCP Relay")


async def start_relay(config: MCPGatewayConfig | None = None) -> GitHubMCPRelay:
    """Start the GitHub MCP Relay service.

    Args:
        config: Optional MCP Gateway configuration

    Returns:
        Running relay instance

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If initial connection test fails
    """
    if config is None:
        config = load_config()

    if not config.github_relay_issue:
        raise ValueError("GITHUB_RELAY_ISSUE not configured")

    if not config.github_private_key:
        logger.error("GitHub private key not configured - relay cannot authenticate")
        raise ValueError("GITHUB_APP_PRIVATE_KEY not configured")

    relay = GitHubMCPRelay(config)

    # Test authentication before starting
    try:
        token = await relay._get_github_token()
        logger.info(f"GitHub authentication successful (token: {token[:10]}...)")
    except Exception as e:
        logger.error(f"GitHub authentication failed during startup: {e}")
        raise RuntimeError(f"GitHub authentication failed: {e}") from e

    # Post startup beacon to issue
    try:
        await relay._post_response(
            "startup-beacon",
            {
                "event": "relay_started",
                "repo": relay.repo,
                "issue": relay.issue_number,
                "token_ok": True,
            },
        )
        logger.info("Posted startup beacon to GitHub issue")
    except Exception as e:
        logger.warning(f"Failed to post startup beacon: {e}")

    asyncio.create_task(relay.run())
    return relay


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    config = load_config()
    if not config.github_relay_issue:
        print("Error: GITHUB_RELAY_ISSUE not set")
        sys.exit(1)

    asyncio.run(start_relay(config))
