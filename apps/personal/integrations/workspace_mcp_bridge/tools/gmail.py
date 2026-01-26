"""Gmail MCP Tools.

Provides tools for email operations:
- gmail_send: Send an email
- gmail_search: Search emails
- gmail_read: Read email content
- gmail_list: List recent emails
- gmail_labels: List labels
"""

import base64
import logging
from email.mime.text import MIMEText
from typing import Any

import httpx

from apps.personal.integrations.workspace_mcp_bridge.auth import GoogleOAuthManager

logger = logging.getLogger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


def register_gmail_tools(mcp: Any, oauth_manager: GoogleOAuthManager) -> None:
    """Register Gmail tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        oauth_manager: OAuth manager for authentication
    """

    @mcp.tool()
    async def gmail_send(
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> dict[str, Any]:
        """Send an email via Gmail.

        Args:
            to: Recipient email address(es), comma-separated
            subject: Email subject
            body: Email body (plain text)
            cc: CC recipients, comma-separated
            bcc: BCC recipients, comma-separated

        Returns:
            Result with message ID and thread ID
        """
        try:
            token = await oauth_manager.get_access_token()

            # Create MIME message
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            if cc:
                message["cc"] = cc
            if bcc:
                message["bcc"] = bcc

            # Encode to base64url
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GMAIL_API_BASE}/users/me/messages/send",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"raw": raw},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to send email: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "message_id": data.get("id"),
                    "thread_id": data.get("threadId"),
                }

        except Exception as e:
            logger.error(f"gmail_send failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def gmail_search(
        query: str,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Search emails in Gmail.

        Args:
            query: Gmail search query (e.g., "from:user@example.com is:unread")
            max_results: Maximum number of results (default: 10)

        Returns:
            List of matching email summaries
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"q": query, "maxResults": max_results},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Search failed: {response.text}",
                    }

                data = response.json()
                messages = data.get("messages", [])

                # Fetch details for each message
                results = []
                for msg in messages[:max_results]:
                    msg_response = await client.get(
                        f"{GMAIL_API_BASE}/users/me/messages/{msg['id']}",
                        headers={"Authorization": f"Bearer {token}"},
                        params={
                            "format": "metadata",
                            "metadataHeaders": [
                                "Subject",
                                "From",
                                "To",
                                "Date",
                            ],
                        },
                    )
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        headers = {
                            h["name"]: h["value"]
                            for h in msg_data.get("payload", {}).get("headers", [])
                        }
                        results.append(
                            {
                                "id": msg["id"],
                                "thread_id": msg_data.get("threadId"),
                                "subject": headers.get("Subject", ""),
                                "from": headers.get("From", ""),
                                "to": headers.get("To", ""),
                                "date": headers.get("Date", ""),
                                "snippet": msg_data.get("snippet", ""),
                            }
                        )

                return {
                    "success": True,
                    "count": len(results),
                    "messages": results,
                }

        except Exception as e:
            logger.error(f"gmail_search failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def gmail_read(message_id: str) -> dict[str, Any]:
        """Read full email content by ID.

        Args:
            message_id: Gmail message ID

        Returns:
            Full email content including body
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"format": "full"},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to read message: {response.text}",
                    }

                data = response.json()
                headers = {
                    h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])
                }

                # Extract body
                body = ""
                payload = data.get("payload", {})

                def extract_body(part: dict) -> str:
                    """Extract text body from message part."""
                    if part.get("mimeType") == "text/plain":
                        body_data = part.get("body", {}).get("data", "")
                        if body_data:
                            return base64.urlsafe_b64decode(body_data).decode()
                    if "parts" in part:
                        for sub_part in part["parts"]:
                            result = extract_body(sub_part)
                            if result:
                                return result
                    return ""

                body = extract_body(payload)
                if not body and payload.get("body", {}).get("data"):
                    body = base64.urlsafe_b64decode(payload["body"]["data"]).decode()

                return {
                    "success": True,
                    "id": message_id,
                    "thread_id": data.get("threadId"),
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "body": body,
                    "labels": data.get("labelIds", []),
                }

        except Exception as e:
            logger.error(f"gmail_read failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def gmail_list(
        label: str = "INBOX",
        max_results: int = 10,
    ) -> dict[str, Any]:
        """List recent emails in a label.

        Args:
            label: Gmail label (default: INBOX)
            max_results: Maximum number of results (default: 10)

        Returns:
            List of recent email summaries
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"labelIds": label, "maxResults": max_results},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to list messages: {response.text}",
                    }

                data = response.json()
                messages = data.get("messages", [])

                # Fetch summaries
                results = []
                for msg in messages:
                    msg_response = await client.get(
                        f"{GMAIL_API_BASE}/users/me/messages/{msg['id']}",
                        headers={"Authorization": f"Bearer {token}"},
                        params={
                            "format": "metadata",
                            "metadataHeaders": [
                                "Subject",
                                "From",
                                "Date",
                            ],
                        },
                    )
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        headers = {
                            h["name"]: h["value"]
                            for h in msg_data.get("payload", {}).get("headers", [])
                        }
                        results.append(
                            {
                                "id": msg["id"],
                                "subject": headers.get("Subject", ""),
                                "from": headers.get("From", ""),
                                "date": headers.get("Date", ""),
                                "snippet": msg_data.get("snippet", ""),
                            }
                        )

                return {
                    "success": True,
                    "label": label,
                    "count": len(results),
                    "messages": results,
                }

        except Exception as e:
            logger.error(f"gmail_list failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def gmail_labels() -> dict[str, Any]:
        """List all Gmail labels.

        Returns:
            List of available labels
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/labels",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to list labels: {response.text}",
                    }

                data = response.json()
                labels = [
                    {"id": label["id"], "name": label["name"], "type": label.get("type")}
                    for label in data.get("labels", [])
                ]

                return {
                    "success": True,
                    "count": len(labels),
                    "labels": labels,
                }

        except Exception as e:
            logger.error(f"gmail_labels failed: {e}")
            return {"success": False, "error": str(e)}
