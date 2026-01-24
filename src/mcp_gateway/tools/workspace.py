"""Google Workspace tools for MCP Gateway.

Provides tools for Gmail, Calendar, Drive, Sheets, and Docs operations.
OAuth credentials are loaded from GCP Secret Manager at startup.

Usage:
    These tools are automatically registered when the MCP Gateway starts.
    They work autonomously without any local setup.
"""

import base64
import logging
from email.mime.text import MIMEText
from typing import Any

import httpx

from .oauth import get_secret

logger = logging.getLogger(__name__)

# API base URLs
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"
DOCS_API = "https://docs.googleapis.com/v1"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105


class WorkspaceAuth:
    """Handles Google Workspace OAuth authentication."""

    _instance = None
    _access_token: str | None = None
    _token_expiry: float = 0

    def __new__(cls) -> "WorkspaceAuth":
        """Singleton pattern for token management."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed.

        Returns:
            Valid access token

        Raises:
            Exception: If unable to get token
        """
        import time

        # Check if current token is still valid (with 60s buffer)
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        # Get credentials from Secret Manager
        client_id = get_secret("GOOGLE-OAUTH-CLIENT-ID")
        client_secret = get_secret("GOOGLE-OAUTH-CLIENT-SECRET")
        refresh_token = get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            missing = []
            if not client_id:
                missing.append("GOOGLE-OAUTH-CLIENT-ID")
            if not client_secret:
                missing.append("GOOGLE-OAUTH-CLIENT-SECRET")
            if not refresh_token:
                missing.append("GOOGLE-OAUTH-REFRESH-TOKEN")
            raise ValueError(f"Missing OAuth secrets: {missing}")

        # Refresh the token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OAUTH_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                raise ValueError(f"Token refresh failed: {response.text}")

            data = response.json()
            self._access_token = data["access_token"]
            self._token_expiry = time.time() + data.get("expires_in", 3600)

            logger.info("Google Workspace access token refreshed")
            return self._access_token


# Global auth instance
_auth = WorkspaceAuth()


async def _get_headers() -> dict[str, str]:
    """Get authorization headers."""
    token = await _auth.get_access_token()
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Gmail Tools
# =============================================================================


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
        headers = await _get_headers()

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_API}/users/me/messages/send",
                headers=headers,
                json={"raw": raw},
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            return {
                "success": True,
                "message_id": data.get("id"),
                "thread_id": data.get("threadId"),
            }

    except Exception as e:
        logger.error(f"gmail_send failed: {e}")
        return {"success": False, "error": str(e)}


async def gmail_search(query: str, max_results: int = 10) -> dict[str, Any]:
    """Search emails in Gmail.

    Args:
        query: Gmail search query (e.g., "from:user@example.com is:unread")
        max_results: Maximum number of results

    Returns:
        List of matching email summaries
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API}/users/me/messages",
                headers=headers,
                params={"q": query, "maxResults": max_results},
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            messages = data.get("messages", [])

            results = []
            for msg in messages[:max_results]:
                msg_response = await client.get(
                    f"{GMAIL_API}/users/me/messages/{msg['id']}",
                    headers=headers,
                    params={
                        "format": "metadata",
                        "metadataHeaders": ["Subject", "From", "To", "Date"],
                    },
                )
                if msg_response.status_code == 200:
                    msg_data = msg_response.json()
                    hdrs = {
                        h["name"]: h["value"]
                        for h in msg_data.get("payload", {}).get("headers", [])
                    }
                    results.append(
                        {
                            "id": msg["id"],
                            "thread_id": msg_data.get("threadId"),
                            "subject": hdrs.get("Subject", ""),
                            "from": hdrs.get("From", ""),
                            "to": hdrs.get("To", ""),
                            "date": hdrs.get("Date", ""),
                            "snippet": msg_data.get("snippet", ""),
                        }
                    )

            return {"success": True, "count": len(results), "messages": results}

    except Exception as e:
        logger.error(f"gmail_search failed: {e}")
        return {"success": False, "error": str(e)}


async def gmail_list(
    label: str = "INBOX",
    max_results: int = 10,
    unread_only: bool = False,
) -> dict[str, Any]:
    """List recent emails in a label.

    Args:
        label: Gmail label (default: INBOX)
        max_results: Maximum number of results
        unread_only: Only return unread emails (default: False)

    Returns:
        List of recent email summaries
    """
    try:
        headers = await _get_headers()

        # Build params - add UNREAD label if filtering for unread
        params: dict[str, Any] = {"labelIds": label, "maxResults": max_results}
        if unread_only:
            # Add UNREAD to labels filter
            params["labelIds"] = [label, "UNREAD"]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API}/users/me/messages",
                headers=headers,
                params=params,
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            messages = data.get("messages", [])

            results = []
            for msg in messages:
                msg_response = await client.get(
                    f"{GMAIL_API}/users/me/messages/{msg['id']}",
                    headers=headers,
                    params={
                        "format": "metadata",
                        "metadataHeaders": ["Subject", "From", "Date"],
                    },
                )
                if msg_response.status_code == 200:
                    msg_data = msg_response.json()
                    hdrs = {
                        h["name"]: h["value"]
                        for h in msg_data.get("payload", {}).get("headers", [])
                    }
                    results.append(
                        {
                            "id": msg["id"],
                            "subject": hdrs.get("Subject", ""),
                            "from": hdrs.get("From", ""),
                            "date": hdrs.get("Date", ""),
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


# =============================================================================
# Gmail Trash/Archive Tools
# =============================================================================


async def gmail_trash(message_id: str) -> dict[str, Any]:
    """Move a single email to trash.

    Args:
        message_id: Gmail message ID to trash

    Returns:
        Result with success status
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_API}/users/me/messages/{message_id}/trash",
                headers=headers,
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            return {"success": True, "message_id": message_id, "action": "trashed"}

    except Exception as e:
        logger.error(f"gmail_trash failed: {e}")
        return {"success": False, "error": str(e)}


async def gmail_batch_trash(query: str, max_results: int = 100) -> dict[str, Any]:
    """Move multiple emails to trash based on search query.

    Args:
        query: Gmail search query (e.g., "from:notifications@github.com")
        max_results: Maximum number of emails to trash (default: 100, max: 500)

    Returns:
        Result with count of trashed emails
    """
    try:
        # Cap at 500 to prevent accidents
        max_results = min(max_results, 500)

        headers = await _get_headers()
        trashed_count = 0
        errors = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            # First, search for messages
            response = await client.get(
                f"{GMAIL_API}/users/me/messages",
                headers=headers,
                params={"q": query, "maxResults": max_results},
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            messages = data.get("messages", [])

            if not messages:
                return {
                    "success": True,
                    "trashed_count": 0,
                    "message": "No messages found matching query",
                }

            # Trash each message
            for msg in messages:
                trash_response = await client.post(
                    f"{GMAIL_API}/users/me/messages/{msg['id']}/trash",
                    headers=headers,
                )

                if trash_response.status_code == 200:
                    trashed_count += 1
                else:
                    errors.append(
                        {"id": msg["id"], "error": trash_response.status_code}
                    )

            result = {
                "success": True,
                "query": query,
                "found": len(messages),
                "trashed_count": trashed_count,
            }

            if errors:
                result["errors"] = errors

            return result

    except Exception as e:
        logger.error(f"gmail_batch_trash failed: {e}")
        return {"success": False, "error": str(e)}


async def gmail_unsubscribe_filter(
    sender_pattern: str, action: str = "trash"
) -> dict[str, Any]:
    """Create a filter to automatically handle future emails from a sender.

    Note: Gmail API filter creation requires additional scopes.
    This function provides instructions for manual filter creation.

    Args:
        sender_pattern: Email pattern to filter (e.g., "notifications@github.com")
        action: What to do with matching emails ("trash", "archive", "skip_inbox")

    Returns:
        Instructions for creating the filter manually
    """
    return {
        "success": True,
        "type": "instructions",
        "message": "Gmail filter creation requires manual setup",
        "steps": [
            "1. Go to https://mail.google.com/mail/u/0/#settings/filters",
            "2. Click 'Create a new filter'",
            f"3. In 'From' field, enter: {sender_pattern}",
            "4. Click 'Create filter'",
            f"5. Select: {'Delete it' if action == 'trash' else 'Skip the Inbox' if action == 'archive' else action}",
            "6. Check 'Also apply filter to matching conversations'",
            "7. Click 'Create filter'",
        ],
        "filter_url": "https://mail.google.com/mail/u/0/#settings/filters",
    }


# =============================================================================
# Calendar Tools
# =============================================================================


async def calendar_list_events(
    calendar_id: str = "primary",
    max_results: int = 10,
    time_min: str = "",
) -> dict[str, Any]:
    """List upcoming calendar events.

    Args:
        calendar_id: Calendar ID (default: primary)
        max_results: Maximum number of events
        time_min: Start time in ISO format (default: now)

    Returns:
        List of upcoming events
    """
    try:
        from datetime import UTC, datetime

        headers = await _get_headers()

        if not time_min:
            time_min = datetime.now(UTC).isoformat()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CALENDAR_API}/calendars/{calendar_id}/events",
                headers=headers,
                params={
                    "maxResults": max_results,
                    "timeMin": time_min,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            events = []
            for item in data.get("items", []):
                events.append(
                    {
                        "id": item.get("id"),
                        "summary": item.get("summary", ""),
                        "start": item.get("start", {}).get("dateTime")
                        or item.get("start", {}).get("date"),
                        "end": item.get("end", {}).get("dateTime")
                        or item.get("end", {}).get("date"),
                        "location": item.get("location", ""),
                        "description": item.get("description", ""),
                    }
                )

            return {"success": True, "count": len(events), "events": events}

    except Exception as e:
        logger.error(f"calendar_list_events failed: {e}")
        return {"success": False, "error": str(e)}


async def calendar_create_event(
    summary: str,
    start_time: str,
    end_time: str,
    calendar_id: str = "primary",
    description: str = "",
    location: str = "",
    attendees: str = "",
) -> dict[str, Any]:
    """Create a calendar event.

    Args:
        summary: Event title
        start_time: Start time in ISO format
        end_time: End time in ISO format
        calendar_id: Calendar ID (default: primary)
        description: Event description
        location: Event location
        attendees: Comma-separated email addresses

    Returns:
        Created event details
    """
    try:
        headers = await _get_headers()

        event = {
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
        }

        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CALENDAR_API}/calendars/{calendar_id}/events",
                headers=headers,
                json=event,
            )

            if response.status_code not in (200, 201):
                return {"success": False, "error": response.text}

            data = response.json()
            return {
                "success": True,
                "event_id": data.get("id"),
                "html_link": data.get("htmlLink"),
            }

    except Exception as e:
        logger.error(f"calendar_create_event failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Drive Tools
# =============================================================================


async def drive_list_files(
    query: str = "",
    max_results: int = 10,
    folder_id: str = "",
) -> dict[str, Any]:
    """List files in Google Drive.

    Args:
        query: Search query (e.g., "name contains 'report'")
        max_results: Maximum number of results
        folder_id: Specific folder ID to search in

    Returns:
        List of files
    """
    try:
        headers = await _get_headers()

        params: dict[str, Any] = {
            "pageSize": max_results,
            "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
        }

        if query:
            params["q"] = query
        if folder_id:
            params["q"] = f"'{folder_id}' in parents"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DRIVE_API}/files",
                headers=headers,
                params=params,
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            files = [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "mimeType": f.get("mimeType"),
                    "modifiedTime": f.get("modifiedTime"),
                    "size": f.get("size"),
                    "webViewLink": f.get("webViewLink"),
                }
                for f in data.get("files", [])
            ]

            return {"success": True, "count": len(files), "files": files}

    except Exception as e:
        logger.error(f"drive_list_files failed: {e}")
        return {"success": False, "error": str(e)}


async def drive_create_folder(name: str, parent_id: str = "") -> dict[str, Any]:
    """Create a folder in Google Drive.

    Args:
        name: Folder name
        parent_id: Parent folder ID (optional)

    Returns:
        Created folder details
    """
    try:
        headers = await _get_headers()

        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if parent_id:
            metadata["parents"] = [parent_id]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DRIVE_API}/files",
                headers=headers,
                json=metadata,
            )

            if response.status_code not in (200, 201):
                return {"success": False, "error": response.text}

            data = response.json()
            return {
                "success": True,
                "folder_id": data.get("id"),
                "name": data.get("name"),
            }

    except Exception as e:
        logger.error(f"drive_create_folder failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Sheets Tools
# =============================================================================


async def sheets_read(
    spreadsheet_id: str,
    range_notation: str = "Sheet1!A1:Z100",
) -> dict[str, Any]:
    """Read data from a Google Sheet.

    Args:
        spreadsheet_id: Spreadsheet ID
        range_notation: A1 notation range (e.g., "Sheet1!A1:B10")

    Returns:
        Cell values
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_notation}",
                headers=headers,
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            return {
                "success": True,
                "range": data.get("range"),
                "values": data.get("values", []),
            }

    except Exception as e:
        logger.error(f"sheets_read failed: {e}")
        return {"success": False, "error": str(e)}


async def sheets_write(
    spreadsheet_id: str,
    range_notation: str,
    values: list[list[Any]],
) -> dict[str, Any]:
    """Write data to a Google Sheet.

    Args:
        spreadsheet_id: Spreadsheet ID
        range_notation: A1 notation range
        values: 2D array of values to write

    Returns:
        Update result
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_notation}",
                headers=headers,
                params={"valueInputOption": "USER_ENTERED"},
                json={"values": values},
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()
            return {
                "success": True,
                "updated_range": data.get("updatedRange"),
                "updated_rows": data.get("updatedRows"),
                "updated_columns": data.get("updatedColumns"),
                "updated_cells": data.get("updatedCells"),
            }

    except Exception as e:
        logger.error(f"sheets_write failed: {e}")
        return {"success": False, "error": str(e)}


async def sheets_create(title: str) -> dict[str, Any]:
    """Create a new Google Sheet.

    Args:
        title: Spreadsheet title

    Returns:
        Created spreadsheet details
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SHEETS_API}/spreadsheets",
                headers=headers,
                json={"properties": {"title": title}},
            )

            if response.status_code not in (200, 201):
                return {"success": False, "error": response.text}

            data = response.json()
            return {
                "success": True,
                "spreadsheet_id": data.get("spreadsheetId"),
                "url": data.get("spreadsheetUrl"),
            }

    except Exception as e:
        logger.error(f"sheets_create failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Docs Tools
# =============================================================================


async def docs_create(title: str) -> dict[str, Any]:
    """Create a new Google Doc.

    Args:
        title: Document title

    Returns:
        Created document details
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DOCS_API}/documents",
                headers=headers,
                json={"title": title},
            )

            if response.status_code not in (200, 201):
                return {"success": False, "error": response.text}

            data = response.json()
            return {
                "success": True,
                "document_id": data.get("documentId"),
                "title": data.get("title"),
            }

    except Exception as e:
        logger.error(f"docs_create failed: {e}")
        return {"success": False, "error": str(e)}


async def docs_read(document_id: str) -> dict[str, Any]:
    """Read content from a Google Doc.

    Args:
        document_id: Document ID

    Returns:
        Document content
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DOCS_API}/documents/{document_id}",
                headers=headers,
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            data = response.json()

            # Extract text content
            content = ""
            for element in data.get("body", {}).get("content", []):
                if "paragraph" in element:
                    for elem in element["paragraph"].get("elements", []):
                        if "textRun" in elem:
                            content += elem["textRun"].get("content", "")

            return {
                "success": True,
                "document_id": document_id,
                "title": data.get("title"),
                "content": content,
            }

    except Exception as e:
        logger.error(f"docs_read failed: {e}")
        return {"success": False, "error": str(e)}


async def docs_append(document_id: str, text: str) -> dict[str, Any]:
    """Append text to a Google Doc.

    Args:
        document_id: Document ID
        text: Text to append

    Returns:
        Update result
    """
    try:
        headers = await _get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DOCS_API}/documents/{document_id}:batchUpdate",
                headers=headers,
                json={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": 1},
                                "text": text,
                            }
                        }
                    ]
                },
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text}

            return {"success": True, "document_id": document_id}

    except Exception as e:
        logger.error(f"docs_append failed: {e}")
        return {"success": False, "error": str(e)}
