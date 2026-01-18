#!/usr/bin/env python3
"""
GCP Tunnel Adapter - Protocol Encapsulation Client.

This script runs locally in the Claude Code session and tunnels MCP messages
through Cloud Functions HTTP trigger, using a custom token for authentication.

Architecture:
    Claude Code → stdio → This Adapter → HTTPS → cloudfunctions.net → Cloud Function

Usage:
    python adapter.py

Environment Variables:
    MCP_TUNNEL_TOKEN: Custom authentication token (REQUIRED)
    GOOGLE_PROJECT_ID: GCP project ID (default: project38-483612)
    MCP_ROUTER_REGION: Cloud Function region (default: us-central1)
    MCP_ROUTER_NAME: Cloud Function name (default: mcp-router)

Note: This does NOT require GCP credentials. It uses a custom token that
works in Anthropic cloud sessions where GCP auth is not available.
"""

import asyncio
import json
import logging
import os
import sys

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("gcp_tunnel")


class MCPTunnelTransport:
    """
    MCP Transport that tunnels messages through Cloud Functions HTTP trigger.

    This transport uses a custom token (MCP_TUNNEL_TOKEN) for authentication,
    NOT GCP OAuth. This allows it to work in Anthropic cloud sessions where
    GCP credentials are not available.
    """

    def __init__(
        self,
        project_id: str = None,
        region: str = None,
        function_name: str = None,
        token: str = None,
    ):
        """
        Initialize the MCP tunnel transport.

        Args:
            project_id: GCP project ID
            region: Cloud Function region
            function_name: Cloud Function name
            token: Custom MCP tunnel token (or from MCP_TUNNEL_TOKEN env)
        """
        self.project_id = project_id or os.environ.get("GOOGLE_PROJECT_ID", "project38-483612")
        self.region = region or os.environ.get("MCP_ROUTER_REGION", "us-central1")
        self.function_name = function_name or os.environ.get("MCP_ROUTER_NAME", "mcp-router")

        # Custom token - NOT GCP OAuth
        self.token = token or os.environ.get("MCP_TUNNEL_TOKEN")

        # HTTP trigger URL (publicly accessible, but requires our custom token)
        # Format: https://{region}-{project}.cloudfunctions.net/{function}
        self.http_url = (
            f"https://{self.region}-{self.project_id}.cloudfunctions.net/{self.function_name}"
        )

        self._http_client = None

        logger.info(f"Initialized transport: {self.http_url}")

    async def start(self):
        """Initialize HTTP client and validate token."""
        if not self.token:
            raise RuntimeError(
                "MCP_TUNNEL_TOKEN environment variable is required.\n"
                "Set it in Claude Code UI: Environment > Add variable > MCP_TUNNEL_TOKEN=your-token"
            )

        try:
            import httpx

            self._http_client = httpx.AsyncClient(timeout=120.0)
            logger.info("Transport started successfully")
        except ImportError:
            raise RuntimeError("httpx library required. Install with: pip install httpx") from None

    async def stop(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("Transport stopped")

    async def send(self, message: str) -> str:
        """
        Send an MCP message through the Cloud Function tunnel.

        Args:
            message: JSON-RPC message as string

        Returns:
            Response message as string
        """
        if not self._http_client:
            await self.start()

        # Encapsulate the MCP message in 'data' field
        payload = {"data": message}

        logger.debug(f"Sending to tunnel: {message[:100]}...")

        try:
            response = await self._http_client.post(
                self.http_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if response.status_code == 401:
                logger.error("Authentication failed - check MCP_TUNNEL_TOKEN")
                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32001,
                            "message": "Authentication failed - invalid MCP_TUNNEL_TOKEN",
                        },
                    }
                )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"HTTP error {response.status_code}: {error_text}")
                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": f"HTTP error: {response.status_code}"},
                    }
                )

            # Decapsulate the response
            response_json = response.json()
            result = response_json.get("result", "{}")

            logger.debug(f"Received from tunnel: {result[:100]}...")
            return result

        except Exception as e:
            logger.exception(f"Request failed: {e}")
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": f"Transport error: {str(e)}"},
                }
            )


class MCPStdioServer:
    """Simple MCP server that bridges stdio to the Cloud Function tunnel."""

    def __init__(self, transport: MCPTunnelTransport):
        """Initialize with transport."""
        self.transport = transport
        self.running = False

    async def run(self):
        """Run the MCP stdio bridge."""
        await self.transport.start()
        self.running = True

        logger.info("MCP Tunnel Server started - reading from stdin")

        try:
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

            while self.running:
                line = await reader.readline()
                if not line:
                    break

                line = line.decode().strip()
                if not line:
                    continue

                logger.debug(f"Received from stdio: {line[:100]}...")

                # Forward to Cloud Function
                response = await self.transport.send(line)

                # Write response to stdout
                print(response, flush=True)

        except asyncio.CancelledError:
            logger.info("Server cancelled")
        except Exception as e:
            logger.exception(f"Server error: {e}")
        finally:
            await self.transport.stop()


async def main():
    """Entry point."""
    # Check for token
    if not os.environ.get("MCP_TUNNEL_TOKEN"):
        print(
            "ERROR: MCP_TUNNEL_TOKEN environment variable is required.\n\n"
            "To use this tunnel from Claude Code:\n"
            "1. Go to Claude Code UI\n"
            "2. Click on Environment name (top left)\n"
            "3. Add environment variable: MCP_TUNNEL_TOKEN=your-token\n"
            "4. Start a new session\n",
            file=sys.stderr,
        )
        sys.exit(1)

    transport = MCPTunnelTransport()
    server = MCPStdioServer(transport)

    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")


if __name__ == "__main__":
    asyncio.run(main())
