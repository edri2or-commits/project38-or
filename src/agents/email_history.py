"""Email History Lookup - Find past conversations with senders.

Provides context about previous email exchanges:
- Past threads with the same sender
- Communication frequency
- Previous topics discussed
- Relationship type (frequent contact, rare, new)

ADR-014 Phase 2: History Lookup

Supports both:
- GCP Tunnel (Cloud Run): JSON-RPC 2.0 format, has OAuth secrets
- Railway MCP Gateway: Simple /api/mcp/call format
"""

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RelationshipType(Enum):
    """Type of relationship with sender."""

    NEW = "new"  # First email from this sender
    RARE = "rare"  # Less than 5 emails ever
    OCCASIONAL = "occasional"  # 5-20 emails
    FREQUENT = "frequent"  # 20+ emails
    VIP = "vip"  # Marked as important contact


@dataclass
class SenderHistory:
    """Historical context about a sender."""

    email: str
    display_name: str
    total_emails: int
    last_contact: str | None
    relationship: RelationshipType
    common_topics: list[str]
    past_threads: list[dict]  # List of {subject, date, snippet}
    response_pattern: str  # "usually_replies", "rarely_replies", "unknown"


class EmailHistoryLookup:
    """Looks up past email history with senders.

    Uses Gmail search to find previous conversations.
    Supports both GCP Tunnel (JSON-RPC) and Railway (simple JSON) formats.

    Example:
        history = EmailHistoryLookup()
        sender_context = await history.get_sender_history("sender@example.com")
    """

    def __init__(
        self,
        mcp_gateway_url: str | None = None,
    ):
        """Initialize EmailHistoryLookup.

        Args:
            mcp_gateway_url: URL of MCP Gateway for Gmail access
                Default: GCP Tunnel which has OAuth secrets
        """
        # Default to GCP Tunnel which has OAuth secrets
        self.mcp_gateway_url = mcp_gateway_url or os.environ.get(
            "MCP_GATEWAY_URL",
            "https://mcp-router-979429709900.us-central1.run.app"
        )
        self._mcp_token: str | None = None
        # Detect if using GCP Tunnel (JSON-RPC) or Railway (simple format)
        self.use_jsonrpc = "mcp-router" in self.mcp_gateway_url or "cloudfunctions" in self.mcp_gateway_url

    async def _get_mcp_token(self) -> str:
        """Get MCP Gateway token.

        Tries in order:
        1. MCP_GATEWAY_TOKEN env var
        2. MCP-GATEWAY-TOKEN from GCP Secret Manager
        3. MCP-TUNNEL-TOKEN from GCP Secret Manager (for GCP Tunnel)
        """
        if self._mcp_token:
            return self._mcp_token

        token = os.environ.get("MCP_GATEWAY_TOKEN")
        if token:
            self._mcp_token = token
            return token

        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            # Try MCP Gateway token first
            token = manager.get_secret("MCP-GATEWAY-TOKEN")
            if token:
                self._mcp_token = token
                return token

            # Fall back to MCP Tunnel token
            token = manager.get_secret("MCP-TUNNEL-TOKEN")
            if token:
                self._mcp_token = token
                return token
        except Exception as e:
            logger.warning(f"Could not get MCP token: {e}")

        raise ValueError("MCP_GATEWAY_TOKEN not found")

    async def _call_mcp_tool(self, tool_name: str, params: dict) -> dict:
        """Call an MCP Gateway tool.

        Supports two formats:
        - JSON-RPC 2.0 (GCP Tunnel): {"jsonrpc": "2.0", "method": "tools/call", ...}
        - Simple JSON (Railway): {"tool_name": "...", "arguments": {...}}
        """
        token = await self._get_mcp_token()

        if self.use_jsonrpc:
            # GCP Tunnel: JSON-RPC 2.0 format
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": params,
                },
            }
        else:
            # Railway: Simple JSON format
            payload = {
                "tool_name": tool_name,
                "arguments": params,
            }

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.post(
                self.mcp_gateway_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            result = response.json()

            if self.use_jsonrpc:
                # JSON-RPC response: {"jsonrpc": "2.0", "id": "...", "result": {...}}
                if "error" in result:
                    error = result["error"]
                    msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                    return {"success": False, "error": msg}
                return result.get("result", result)
            else:
                # Simple format: {"status": "ok", "result": ...} or {"error": ...}
                if result.get("status") == "error" or "error" in result:
                    error = result.get("error", "Unknown error")
                    return {"success": False, "error": error}
                return result.get("result", result)

    def _extract_email(self, from_field: str) -> str:
        """Extract email from From field."""
        match = re.search(r"<([^>]+)>", from_field)
        if match:
            return match.group(1).lower()
        return from_field.lower().strip()

    def _extract_name(self, from_field: str) -> str:
        """Extract display name from From field."""
        match = re.match(r"([^<]+)\s*<", from_field)
        if match:
            return match.group(1).strip().strip('"')
        return from_field.split("@")[0]

    def _determine_relationship(self, email_count: int) -> RelationshipType:
        """Determine relationship type based on email count."""
        if email_count == 0:
            return RelationshipType.NEW
        elif email_count < 5:
            return RelationshipType.RARE
        elif email_count < 20:
            return RelationshipType.OCCASIONAL
        else:
            return RelationshipType.FREQUENT

    def _extract_topics(self, emails: list[dict]) -> list[str]:
        """Extract common topics from email subjects."""
        topics = []
        topic_patterns = [
            (r"פרויקט|project", "פרויקטים"),
            (r"פגישה|meeting", "פגישות"),
            (r"חשבונית|invoice", "חשבוניות"),
            (r"דוח|report", "דוחות"),
            (r"בקשה|request", "בקשות"),
            (r"עדכון|update", "עדכונים"),
            (r"שאלה|question", "שאלות"),
        ]

        all_subjects = " ".join(e.get("subject", "") for e in emails).lower()

        for pattern, topic in topic_patterns:
            if re.search(pattern, all_subjects, re.IGNORECASE):
                topics.append(topic)

        return topics[:5]  # Limit to 5 topics

    async def get_sender_history(
        self,
        sender_email: str,
        max_results: int = 20,
    ) -> SenderHistory:
        """Get history of emails from a specific sender.

        Args:
            sender_email: Email address of the sender
            max_results: Maximum number of past emails to fetch

        Returns:
            SenderHistory with context about the sender
        """
        # Search for emails from this sender
        query = f"from:{sender_email}"
        result = await self._call_mcp_tool(
            "gmail_search",
            {"query": query, "max_results": max_results},
        )

        if not result.get("success"):
            logger.warning(f"Failed to get history for {sender_email}: {result.get('error')}")
            return SenderHistory(
                email=sender_email,
                display_name=sender_email.split("@")[0],
                total_emails=0,
                last_contact=None,
                relationship=RelationshipType.NEW,
                common_topics=[],
                past_threads=[],
                response_pattern="unknown",
            )

        messages = result.get("messages", [])
        total_count = result.get("count", len(messages))

        # Extract display name from first message
        display_name = sender_email.split("@")[0]
        if messages:
            display_name = self._extract_name(messages[0].get("from", ""))

        # Get last contact date
        last_contact = None
        if messages:
            last_contact = messages[0].get("date")

        # Build past threads list
        past_threads = []
        for msg in messages[:10]:  # Limit to 10 for display
            past_threads.append({
                "subject": msg.get("subject", ""),
                "date": msg.get("date", ""),
                "snippet": msg.get("snippet", "")[:100],
            })

        # Determine relationship
        relationship = self._determine_relationship(total_count)

        # Extract common topics
        topics = self._extract_topics(messages)

        # Check response pattern (did we reply to their emails?)
        # This would require checking for emails TO this address
        response_pattern = "unknown"

        return SenderHistory(
            email=sender_email,
            display_name=display_name,
            total_emails=total_count,
            last_contact=last_contact,
            relationship=relationship,
            common_topics=topics,
            past_threads=past_threads,
            response_pattern=response_pattern,
        )

    async def get_thread_history(self, thread_id: str) -> list[dict]:
        """Get all messages in a thread.

        Args:
            thread_id: Gmail thread ID

        Returns:
            List of messages in the thread
        """
        # Search for messages in this thread
        query = f"thread:{thread_id}"
        result = await self._call_mcp_tool(
            "gmail_search",
            {"query": query, "max_results": 50},
        )

        if not result.get("success"):
            return []

        return result.get("messages", [])

    async def get_batch_history(
        self,
        sender_emails: list[str],
    ) -> dict[str, SenderHistory]:
        """Get history for multiple senders.

        Args:
            sender_emails: List of sender email addresses

        Returns:
            Dict mapping email to SenderHistory
        """
        results = {}

        # Deduplicate
        unique_emails = list(set(sender_emails))

        for email in unique_emails:
            history = await self.get_sender_history(email)
            results[email] = history

        return results

    def format_history_for_context(self, history: SenderHistory) -> str:
        """Format history as context string for LLM.

        Args:
            history: Sender history

        Returns:
            Formatted context string
        """
        relationship_hebrew = {
            RelationshipType.NEW: "איש קשר חדש",
            RelationshipType.RARE: "איש קשר נדיר",
            RelationshipType.OCCASIONAL: "איש קשר מזדמן",
            RelationshipType.FREQUENT: "איש קשר תדיר",
            RelationshipType.VIP: "איש קשר VIP",
        }

        lines = [
            f"**{history.display_name}** ({history.email})",
            f"סוג קשר: {relationship_hebrew.get(history.relationship, 'לא ידוע')}",
            f"סה\"כ מיילים: {history.total_emails}",
        ]

        if history.last_contact:
            lines.append(f"קשר אחרון: {history.last_contact}")

        if history.common_topics:
            lines.append(f"נושאים נפוצים: {', '.join(history.common_topics)}")

        if history.past_threads:
            lines.append("\nשיחות אחרונות:")
            for thread in history.past_threads[:3]:
                lines.append(f"  • {thread['subject'][:50]}")

        return "\n".join(lines)


async def main() -> None:
    """Test EmailHistoryLookup."""
    logging.basicConfig(level=logging.INFO)

    lookup = EmailHistoryLookup()

    # Test with a sample email
    history = await lookup.get_sender_history("test@example.com")

    print("\n=== Sender History ===")
    print(f"Email: {history.email}")
    print(f"Name: {history.display_name}")
    print(f"Total emails: {history.total_emails}")
    print(f"Relationship: {history.relationship.value}")
    print(f"Topics: {history.common_topics}")
    print(f"Last contact: {history.last_contact}")

    print("\n=== Formatted for LLM ===")
    print(lookup.format_history_for_context(history))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
