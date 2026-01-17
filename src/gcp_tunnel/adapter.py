#!/usr/bin/env python3
"""
GCP Tunnel Adapter - Protocol Encapsulation Client.

This script runs locally in the Claude Code session and tunnels MCP messages
through the cloudfunctions.googleapis.com API, bypassing Anthropic's egress proxy.

Architecture:
    Claude Code → stdio → This Adapter → HTTPS → googleapis.com → Cloud Function

Usage:
    python adapter.py

Environment Variables:
    GOOGLE_PROJECT_ID: GCP project ID (default: project38-483612)
    MCP_ROUTER_REGION: Cloud Function region (default: us-central1)
    MCP_ROUTER_NAME: Cloud Function name (default: mcp-router)
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account key (optional with WIF)
"""

import asyncio
import json
import logging
import os
import sys
from typing import Optional

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("gcp_tunnel")


class GoogleRestTransport:
    """
    MCP Transport that tunnels messages through Google Cloud Functions API.

    This transport encapsulates MCP JSON-RPC messages in the 'data' field
    of cloudfunctions.googleapis.com/v1/.../functions/...:call requests.
    """

    def __init__(
        self,
        project_id: str = None,
        region: str = None,
        function_name: str = None
    ):
        """
        Initialize the Google REST transport.

        Args:
            project_id: GCP project ID
            region: Cloud Function region
            function_name: Cloud Function name
        """
        self.project_id = project_id or os.environ.get("GOOGLE_PROJECT_ID", "project38-483612")
        self.region = region or os.environ.get("MCP_ROUTER_REGION", "us-central1")
        self.function_name = function_name or os.environ.get("MCP_ROUTER_NAME", "mcp-router")

        self.api_url = (
            f"https://cloudfunctions.googleapis.com/v1/"
            f"projects/{self.project_id}/"
            f"locations/{self.region}/"
            f"functions/{self.function_name}:call"
        )

        self.credentials = None
        self.token: Optional[str] = None
        self._http_client = None

        logger.info(f"Initialized transport: {self.api_url}")

    async def start(self):
        """Initialize credentials and HTTP client."""
        try:
            import httpx

            # Initialize HTTP client
            self._http_client = httpx.AsyncClient(timeout=120.0)

            # Try to get credentials
            await self._refresh_credentials()

            logger.info("Transport started successfully")

        except Exception as e:
            logger.error(f"Failed to start transport: {e}")
            raise

    async def _refresh_credentials(self):
        """Refresh OAuth2 credentials."""
        try:
            # Try google-auth library first
            import google.auth
            import google.auth.transport.requests

            self.credentials, project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            # Refresh the token
            request = google.auth.transport.requests.Request()
            self.credentials.refresh(request)
            self.token = self.credentials.token

            logger.info(f"Credentials refreshed, project: {project}")

        except ImportError:
            logger.warning("google-auth not available, trying environment token")
            # Fallback to environment variable
            self.token = os.environ.get("GOOGLE_ACCESS_TOKEN")
            if not self.token:
                raise RuntimeError(
                    "No credentials available. Install google-auth or set GOOGLE_ACCESS_TOKEN"
                )

    async def send(self, message: str) -> str:
        """
        Send an MCP message through the Google API tunnel.

        Args:
            message: JSON-RPC message as string

        Returns:
            Response message as string
        """
        if not self._http_client:
            await self.start()

        # Ensure we have valid credentials
        if self.credentials and self.credentials.expired:
            await self._refresh_credentials()

        # Encapsulate the MCP message
        payload = {"data": message}

        logger.debug(f"Sending to tunnel: {message[:100]}...")

        try:
            response = await self._http_client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"API error {response.status_code}: {error_text}")
                return json.dumps({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": f"API error: {response.status_code}"
                    }
                })

            # Decapsulate the response
            response_json = response.json()
            result = response_json.get("result", "{}")

            logger.debug(f"Received from tunnel: {result[:100]}...")
            return result

        except Exception as e:
            logger.exception("Transport error")
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": f"Transport error: {e}"
                }
            })

    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


class MCPStdioAdapter:
    """
    Bridges stdio MCP protocol with the Google REST transport.

    Reads JSON-RPC messages from stdin, sends them through the tunnel,
    and writes responses to stdout.
    """

    def __init__(self, transport: GoogleRestTransport):
        """Initialize the adapter with a transport."""
        self.transport = transport

    async def run(self):
        """Main loop: read from stdin, tunnel, write to stdout."""
        await self.transport.start()

        logger.info("MCP Stdio Adapter running")

        # Read from stdin line by line
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        loop = asyncio.get_event_loop()
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        try:
            while True:
                # Read a line from stdin
                line = await reader.readline()

                if not line:
                    logger.info("EOF received, exiting")
                    break

                line = line.decode("utf-8").strip()

                if not line:
                    continue

                logger.debug(f"Received from Claude: {line[:100]}...")

                # Send through tunnel
                response = await self.transport.send(line)

                # Write response to stdout
                sys.stdout.write(response + "\n")
                sys.stdout.flush()

                logger.debug(f"Sent to Claude: {response[:100]}...")

        except asyncio.CancelledError:
            logger.info("Adapter cancelled")
        finally:
            await self.transport.close()


async def main():
    """Entry point."""
    logger.info("Starting GCP Tunnel Adapter")
    logger.info(f"Project: {os.environ.get('GOOGLE_PROJECT_ID', 'project38-483612')}")

    transport = GoogleRestTransport()
    adapter = MCPStdioAdapter(transport)

    try:
        await adapter.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
