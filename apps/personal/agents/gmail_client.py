"""Gmail Client for Personal Domain.

Provides a GmailClient class that fetches emails via MCP Gateway.
This client uses the GCP Tunnel/MCP Gateway to access Gmail.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Email message representation."""

    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    date: str
    snippet: str
    labels: list[str]


class GmailClient:
    """Gmail client that uses MCP Gateway for email operations.

    This client communicates with the GCP Tunnel to access Gmail API
    without requiring direct OAuth credentials.
    """

    def __init__(self, gateway_url: str | None = None, gateway_token: str | None = None):
        """Initialize Gmail client.

        Args:
            gateway_url: MCP Gateway URL (default from env MCP_GATEWAY_URL)
            gateway_token: MCP Gateway token (default from env MCP_GATEWAY_TOKEN)
        """
        self.gateway_url = gateway_url or os.environ.get(
            "MCP_GATEWAY_URL", "https://mcp-router-979429709900.us-central1.run.app"
        )
        self.gateway_token = gateway_token or os.environ.get("MCP_GATEWAY_TOKEN", "")

        if not self.gateway_token:
            logger.warning("No MCP_GATEWAY_TOKEN found - Gmail operations may fail")

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool via the gateway.

        Args:
            tool_name: Name of the MCP tool to call
            arguments: Arguments for the tool

        Returns:
            Tool result
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.gateway_url}/call_tool",
                    headers={
                        "Authorization": f"Bearer {self.gateway_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"MCP tool call failed: {response.status_code} {response.text}")
                    return {"error": response.text}

            except Exception as e:
                logger.error(f"MCP tool call exception: {e}")
                return {"error": str(e)}

    def get_unread_emails(self, hours: int = 24, max_results: int = 50) -> list[EmailMessage]:
        """Get unread emails from Gmail.

        Args:
            hours: Look back this many hours
            max_results: Maximum emails to return

        Returns:
            List of EmailMessage objects
        """
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self._get_unread_emails_async(hours, max_results)
        )

    async def _get_unread_emails_async(
        self, hours: int = 24, max_results: int = 50
    ) -> list[EmailMessage]:
        """Async implementation of get_unread_emails.

        Args:
            hours: Look back this many hours
            max_results: Maximum emails to return

        Returns:
            List of EmailMessage objects
        """
        # Build Gmail search query
        after_date = datetime.utcnow() - timedelta(hours=hours)
        after_unix = int(after_date.timestamp())
        query = f"is:unread after:{after_unix}"

        result = await self._call_mcp_tool(
            "gmail_search",
            {
                "query": query,
                "max_results": max_results,
            },
        )

        if "error" in result:
            logger.error(f"Failed to fetch emails: {result['error']}")
            return []

        # Parse response into EmailMessage objects
        messages = []
        for msg_data in result.get("messages", result.get("result", {}).get("messages", [])):
            try:
                messages.append(
                    EmailMessage(
                        id=msg_data.get("id", ""),
                        thread_id=msg_data.get("thread_id", msg_data.get("threadId", "")),
                        subject=msg_data.get("subject", ""),
                        sender=msg_data.get("from", msg_data.get("sender", "")),
                        sender_email=self._extract_email(
                            msg_data.get("from", msg_data.get("sender", ""))
                        ),
                        date=msg_data.get("date", ""),
                        snippet=msg_data.get("snippet", ""),
                        labels=msg_data.get("labels", msg_data.get("labelIds", [])),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse email message: {e}")
                continue

        return messages

    @staticmethod
    def _extract_email(sender: str) -> str:
        """Extract email address from sender string.

        Args:
            sender: Sender string like "Name <email@example.com>"

        Returns:
            Email address
        """
        if "<" in sender and ">" in sender:
            start = sender.index("<") + 1
            end = sender.index(">")
            return sender[start:end]
        return sender
