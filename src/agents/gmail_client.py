"""Direct Gmail API client using OAuth.

Provides Gmail access without MCP Gateway dependency.
Used by SmartEmailAgent for actual email operations.
"""

import os
from dataclasses import dataclass

import httpx


@dataclass
class GmailMessage:
    """Gmail message data."""

    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    date: str
    snippet: str
    body: str = ""
    labels: list[str] = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = []


class GmailClient:
    """Direct Gmail API client using OAuth credentials."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
    ):
        """Initialize Gmail client.

        Args:
            client_id: Google OAuth Client ID (or from env/secrets)
            client_secret: Google OAuth Client Secret (or from env/secrets)
            refresh_token: Google OAuth Refresh Token (or from env/secrets)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._access_token: str | None = None

    def _load_credentials(self) -> None:
        """Load credentials from environment or GCP Secret Manager."""
        if self.client_id and self.client_secret and self.refresh_token:
            return

        # Try environment variables
        self.client_id = self.client_id or os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        self.client_secret = self.client_secret or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        self.refresh_token = self.refresh_token or os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")

        if self.client_id and self.client_secret and self.refresh_token:
            return

        # Try GCP Secret Manager
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            if not self.client_id:
                self.client_id = manager.get_secret("GOOGLE-OAUTH-CLIENT-ID")
            if not self.client_secret:
                self.client_secret = manager.get_secret("GOOGLE-OAUTH-CLIENT-SECRET")
            if not self.refresh_token:
                self.refresh_token = manager.get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")
        except Exception as e:
            raise ValueError(f"Could not load Gmail credentials: {e}")

    def _refresh_access_token(self) -> str:
        """Refresh the OAuth access token."""
        self._load_credentials()

        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        self._access_token = response.json()["access_token"]
        return self._access_token

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        if not self._access_token:
            self._refresh_access_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    def search_emails(
        self,
        query: str = "is:unread",
        max_results: int = 50,
    ) -> list[GmailMessage]:
        """Search for emails.

        Args:
            query: Gmail search query (e.g., "is:unread newer_than:24h")
            max_results: Maximum number of results

        Returns:
            List of GmailMessage objects
        """
        headers = self._get_headers()

        # Search for messages
        response = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers=headers,
            params={"q": query, "maxResults": max_results},
            timeout=30,
        )

        if response.status_code == 401:
            # Token expired, refresh and retry
            self._refresh_access_token()
            headers = self._get_headers()
            response = httpx.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={"q": query, "maxResults": max_results},
                timeout=30,
            )

        if response.status_code != 200:
            raise Exception(f"Gmail search failed: {response.text}")

        data = response.json()
        message_refs = data.get("messages", [])

        # Fetch details for each message
        messages = []
        for ref in message_refs[:max_results]:
            msg = self._get_message(ref["id"], headers)
            if msg:
                messages.append(msg)

        return messages

    def _get_message(self, message_id: str, headers: dict) -> GmailMessage | None:
        """Get full message details."""
        response = httpx.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            timeout=30,
        )

        if response.status_code != 200:
            return None

        data = response.json()
        headers_list = data.get("payload", {}).get("headers", [])

        subject = ""
        sender = ""
        date = ""
        for h in headers_list:
            if h["name"] == "Subject":
                subject = h["value"]
            elif h["name"] == "From":
                sender = h["value"]
            elif h["name"] == "Date":
                date = h["value"]

        # Extract email from sender
        sender_email = sender
        if "<" in sender and ">" in sender:
            sender_email = sender.split("<")[1].split(">")[0]

        return GmailMessage(
            id=data["id"],
            thread_id=data.get("threadId", ""),
            subject=subject,
            sender=sender.split("<")[0].strip(),
            sender_email=sender_email,
            date=date,
            snippet=data.get("snippet", ""),
            labels=data.get("labelIds", []),
        )

    def get_unread_emails(self, hours: int = 24, max_results: int = 50) -> list[GmailMessage]:
        """Get unread emails from the last N hours.

        Args:
            hours: Number of hours to look back
            max_results: Maximum number of results

        Returns:
            List of GmailMessage objects
        """
        query = f"is:unread newer_than:{hours}h"
        return self.search_emails(query=query, max_results=max_results)

    def get_profile(self) -> dict:
        """Get user's Gmail profile (email address)."""
        headers = self._get_headers()

        response = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"Profile fetch failed: {response.text}")

        return response.json()
