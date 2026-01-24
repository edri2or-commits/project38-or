"""Gmail Client for Smart Email Agent.

Provides a simple interface to fetch emails via MCP Gateway.
Supports both:
- GCP Tunnel (Cloud Run): JSON-RPC 2.0 format, has OAuth secrets
- Railway MCP Gateway: Simple /api/mcp/call format
"""

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents an email message."""
    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    date: str
    snippet: str
    labels: list[str]
    body: str = ""


class GmailClient:
    """Client for fetching emails via MCP Gateway.

    Uses the MCP Gateway's gmail_list tool to fetch unread emails.
    Supports both GCP Tunnel (JSON-RPC) and Railway (simple JSON) formats.
    """

    def __init__(self, mcp_url: str | None = None, mcp_token: str | None = None):
        """Initialize Gmail client.

        Args:
            mcp_url: MCP Gateway URL (default: from env or GCP Tunnel)
            mcp_token: MCP Gateway token (default: from env)
        """
        # Default to GCP Tunnel which has OAuth secrets
        # Railway MCP Gateway at or-infra.com doesn't have Google OAuth secrets
        self.mcp_url = mcp_url or os.environ.get(
            "MCP_GATEWAY_URL",
            "https://mcp-router-979429709900.us-central1.run.app"
        )
        self.mcp_token = mcp_token or os.environ.get("MCP_GATEWAY_TOKEN", "")

        # Detect if using GCP Tunnel (JSON-RPC) or Railway (simple format)
        self.use_jsonrpc = "mcp-router" in self.mcp_url or "cloudfunctions" in self.mcp_url

    def _call_mcp_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool via the MCP Gateway.

        Supports two formats:
        - GCP Tunnel: {"data": "{JSON-RPC encapsulated}"} - protocol encapsulation
        - Railway: {"tool_name": "...", "arguments": {...}} - simple format

        Args:
            tool_name: Name of the MCP tool
            params: Tool parameters

        Returns:
            Tool result
        """
        import json as json_lib

        headers = {"Content-Type": "application/json"}
        if self.mcp_token:
            headers["Authorization"] = f"Bearer {self.mcp_token}"

        url = self.mcp_url

        if self.use_jsonrpc:
            # GCP Tunnel: Protocol encapsulation format
            # The MCP message must be wrapped in a 'data' field (string or object)
            mcp_message = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": params,
                },
            }
            # Wrap in data field as expected by GCP Tunnel
            payload = {"data": json_lib.dumps(mcp_message)}
        else:
            # Railway: Simple JSON format
            payload = {
                "tool_name": tool_name,
                "arguments": params,
            }

        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=60,  # Increased for Gmail operations
                follow_redirects=True,
            )
            response.raise_for_status()
            result = response.json()

            if self.use_jsonrpc:
                # GCP Tunnel response: {"result": "{JSON-RPC encapsulated}"}
                if "error" in result:
                    error = result["error"]
                    msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                    raise RuntimeError(f"MCP error: {msg}")

                # The response has a 'result' field containing stringified JSON-RPC
                encapsulated = result.get("result", result)
                if isinstance(encapsulated, str):
                    # Parse the encapsulated JSON-RPC response
                    mcp_response = json_lib.loads(encapsulated)
                    if "error" in mcp_response:
                        error = mcp_response["error"]
                        msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                        raise RuntimeError(f"MCP error: {msg}")
                    return mcp_response.get("result", mcp_response)
                else:
                    return encapsulated
            else:
                # Simple format: {"status": "ok", "result": ...} or {"status": "error", ...}
                if result.get("status") == "error" or "error" in result:
                    error = result.get("error", "Unknown error")
                    raise RuntimeError(f"MCP error: {error}")
                return result.get("result", result)

        except httpx.HTTPError as e:
            logger.error(f"MCP call failed: {e}")
            raise

    def get_unread_emails(
        self,
        hours: int = 24,
        max_results: int = 50,
    ) -> list[EmailMessage]:
        """Fetch unread emails from the last N hours.

        Args:
            hours: Hours to look back
            max_results: Maximum emails to fetch

        Returns:
            List of EmailMessage objects
        """
        try:
            # Call gmail_list via MCP Gateway
            # Note: GCP Tunnel doesn't support unread_only, so we fetch all INBOX
            # and filter UNREAD label client-side if needed
            result = self._call_mcp_tool("gmail_list", {
                "label": "INBOX",
                "max_results": max_results,
            })

            messages: list[EmailMessage] = []

            for msg in result.get("messages", []):
                # Parse sender
                sender_full = msg.get("from", "Unknown")
                sender_email = ""
                sender_name = sender_full

                # Extract email from "Name <email@domain.com>" format
                if "<" in sender_full and ">" in sender_full:
                    parts = sender_full.split("<")
                    sender_name = parts[0].strip().strip('"')
                    sender_email = parts[1].rstrip(">")
                elif "@" in sender_full:
                    sender_email = sender_full
                    sender_name = sender_full.split("@")[0]

                messages.append(EmailMessage(
                    id=msg.get("id", ""),
                    thread_id=msg.get("threadId", msg.get("id", "")),
                    subject=msg.get("subject", "(no subject)"),
                    sender=sender_name,
                    sender_email=sender_email,
                    date=msg.get("date", ""),
                    snippet=msg.get("snippet", ""),
                    labels=msg.get("labelIds", []),
                    body=msg.get("body", ""),
                ))

            logger.info(f"Fetched {len(messages)} unread emails")
            return messages

        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            return []

    def search_emails(
        self,
        query: str,
        max_results: int = 20,
    ) -> list[EmailMessage]:
        """Search emails with Gmail query syntax.

        Args:
            query: Gmail search query (e.g., "from:example@gmail.com")
            max_results: Maximum emails to return

        Returns:
            List of matching EmailMessage objects
        """
        try:
            result = self._call_mcp_tool("gmail_search", {
                "query": query,
                "max_results": max_results,
            })

            messages: list[EmailMessage] = []

            for msg in result.get("messages", []):
                sender_full = msg.get("from", "Unknown")
                sender_email = ""
                sender_name = sender_full

                if "<" in sender_full and ">" in sender_full:
                    parts = sender_full.split("<")
                    sender_name = parts[0].strip().strip('"')
                    sender_email = parts[1].rstrip(">")
                elif "@" in sender_full:
                    sender_email = sender_full
                    sender_name = sender_full.split("@")[0]

                messages.append(EmailMessage(
                    id=msg.get("id", ""),
                    thread_id=msg.get("threadId", msg.get("id", "")),
                    subject=msg.get("subject", "(no subject)"),
                    sender=sender_name,
                    sender_email=sender_email,
                    date=msg.get("date", ""),
                    snippet=msg.get("snippet", ""),
                    labels=msg.get("labelIds", []),
                    body=msg.get("body", ""),
                ))

            return messages

        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            return []
