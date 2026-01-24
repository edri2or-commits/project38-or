"""Gmail Client for Smart Email Agent.

Provides a simple interface to fetch emails via MCP Gateway.
"""

import logging
import os
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
    """

    def __init__(self, mcp_url: str | None = None, mcp_token: str | None = None):
        """Initialize Gmail client.

        Args:
            mcp_url: MCP Gateway URL (default: from env or production URL)
            mcp_token: MCP Gateway token (default: from env)
        """
        self.mcp_url = mcp_url or os.environ.get(
            "MCP_GATEWAY_URL",
            "https://or-infra.com/mcp"
        )
        self.mcp_token = mcp_token or os.environ.get("MCP_GATEWAY_TOKEN", "")

    def _call_mcp_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool via the gateway.

        MCP uses JSON-RPC 2.0 format over HTTP:
        {
            "jsonrpc": "2.0",
            "id": <request_id>,
            "method": "tools/call",
            "params": {"name": "<tool_name>", "arguments": {...}}
        }

        Args:
            tool_name: Name of the MCP tool
            params: Tool parameters

        Returns:
            Tool result
        """
        import uuid

        headers = {"Content-Type": "application/json"}
        if self.mcp_token:
            headers["Authorization"] = f"Bearer {self.mcp_token}"

        # MCP Gateway URL - POST with JSON-RPC 2.0 format
        url = self.mcp_url

        # Build JSON-RPC 2.0 request
        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params,
            },
        }

        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
                follow_redirects=True,
            )
            response.raise_for_status()
            result = response.json()

            # JSON-RPC response has result or error
            if "error" in result:
                error = result["error"]
                raise RuntimeError(f"MCP error: {error.get('message', error)}")

            # Extract result from JSON-RPC response
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
            result = self._call_mcp_tool("gmail_list", {
                "label": "INBOX",
                "max_results": max_results,
                "unread_only": True,
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
