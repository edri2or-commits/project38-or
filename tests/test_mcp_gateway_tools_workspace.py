"""Tests for MCP Gateway Google Workspace tools.

Tests the workspace module in src/mcp_gateway/tools/workspace.py.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Mock the oauth module before importing workspace
# This allows tests to run without google.cloud dependency
@pytest.fixture(autouse=True)
def mock_oauth_module():
    """Mock the oauth module for all tests."""
    mock_oauth = MagicMock()
    mock_oauth.get_secret = MagicMock(return_value="mock-secret")

    # Store original if it exists
    original = sys.modules.get("src.mcp_gateway.tools.oauth")
    sys.modules["src.mcp_gateway.tools.oauth"] = mock_oauth

    yield mock_oauth

    # Restore original
    if original:
        sys.modules["src.mcp_gateway.tools.oauth"] = original
    else:
        sys.modules.pop("src.mcp_gateway.tools.oauth", None)


def _can_import_httpx() -> bool:
    """Check if httpx is available for tests."""
    try:
        import httpx
        return True
    except ImportError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _can_import_httpx(),
        reason="httpx not available"
    ),
]


# =============================================================================
# WorkspaceAuth Tests
# =============================================================================


class TestWorkspaceAuth:
    """Tests for WorkspaceAuth class."""

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """Test WorkspaceAuth uses singleton pattern."""
        from src.mcp_gateway.tools.workspace import WorkspaceAuth

        auth1 = WorkspaceAuth()
        auth2 = WorkspaceAuth()
        assert auth1 is auth2

    @pytest.mark.asyncio
    async def test_get_access_token_refreshes_when_expired(self):
        """Test token refresh when expired."""
        from src.mcp_gateway.tools.workspace import WorkspaceAuth

        auth = WorkspaceAuth()
        # Reset state
        auth._access_token = None
        auth._token_expiry = 0

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }

        with patch("src.mcp_gateway.tools.workspace.get_secret") as mock_secret:
            mock_secret.side_effect = lambda key: {
                "GOOGLE-OAUTH-CLIENT-ID": "client-id",
                "GOOGLE-OAUTH-CLIENT-SECRET": "client-secret",
                "GOOGLE-OAUTH-REFRESH-TOKEN": "refresh-token",
            }.get(key)

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                token = await auth.get_access_token()

        assert token == "new-token"
        assert auth._access_token == "new-token"

    @pytest.mark.asyncio
    async def test_get_access_token_uses_cached_when_valid(self):
        """Test cached token is used when still valid."""
        import time

        from src.mcp_gateway.tools.workspace import WorkspaceAuth

        auth = WorkspaceAuth()
        auth._access_token = "cached-token"
        auth._token_expiry = time.time() + 3600  # Expires in 1 hour

        # Should return cached token without making API call
        token = await auth.get_access_token()
        assert token == "cached-token"

    @pytest.mark.asyncio
    async def test_get_access_token_missing_secrets(self):
        """Test error when OAuth secrets are missing."""
        from src.mcp_gateway.tools.workspace import WorkspaceAuth

        auth = WorkspaceAuth()
        auth._access_token = None
        auth._token_expiry = 0

        with patch("src.mcp_gateway.tools.workspace.get_secret") as mock_secret:
            mock_secret.return_value = None  # All secrets missing

            with pytest.raises(ValueError, match="Missing OAuth secrets"):
                await auth.get_access_token()

    @pytest.mark.asyncio
    async def test_get_access_token_refresh_failure(self):
        """Test error handling when token refresh fails."""
        from src.mcp_gateway.tools.workspace import WorkspaceAuth

        auth = WorkspaceAuth()
        auth._access_token = None
        auth._token_expiry = 0

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid refresh token"

        with patch("src.mcp_gateway.tools.workspace.get_secret") as mock_secret:
            mock_secret.side_effect = lambda key: {
                "GOOGLE-OAUTH-CLIENT-ID": "client-id",
                "GOOGLE-OAUTH-CLIENT-SECRET": "client-secret",
                "GOOGLE-OAUTH-REFRESH-TOKEN": "bad-token",
            }.get(key)

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                with pytest.raises(ValueError, match="Token refresh failed"):
                    await auth.get_access_token()


# =============================================================================
# Gmail Tools Tests
# =============================================================================


class TestGmailSend:
    """Tests for gmail_send function."""

    @pytest.mark.asyncio
    async def test_gmail_send_success(self):
        """Test successful email sending."""
        from src.mcp_gateway.tools.workspace import gmail_send

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "msg-123",
            "threadId": "thread-456",
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_send(
                    to="recipient@example.com",
                    subject="Test Subject",
                    body="Test body",
                )

        assert result["success"] is True
        assert result["message_id"] == "msg-123"
        assert result["thread_id"] == "thread-456"

    @pytest.mark.asyncio
    async def test_gmail_send_with_cc_bcc(self):
        """Test email sending with CC and BCC."""
        from src.mcp_gateway.tools.workspace import gmail_send

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg-123", "threadId": "thread-456"}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_send(
                    to="recipient@example.com",
                    subject="Test",
                    body="Body",
                    cc="cc@example.com",
                    bcc="bcc@example.com",
                )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_gmail_send_failure(self):
        """Test email sending failure."""
        from src.mcp_gateway.tools.workspace import gmail_send

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid recipient"

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_send(
                    to="invalid",
                    subject="Test",
                    body="Body",
                )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_gmail_send_exception(self):
        """Test email sending handles exceptions."""
        from src.mcp_gateway.tools.workspace import gmail_send

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.side_effect = Exception("Auth failed")

            result = await gmail_send(
                to="recipient@example.com",
                subject="Test",
                body="Body",
            )

        assert result["success"] is False
        assert "Auth failed" in result["error"]


class TestGmailSearch:
    """Tests for gmail_search function."""

    @pytest.mark.asyncio
    async def test_gmail_search_success(self):
        """Test successful email search."""
        from src.mcp_gateway.tools.workspace import gmail_search

        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {
            "messages": [{"id": "msg-1"}, {"id": "msg-2"}]
        }

        msg_response = MagicMock()
        msg_response.status_code = 200
        msg_response.json.return_value = {
            "threadId": "thread-1",
            "snippet": "Preview text...",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Date", "value": "Mon, 22 Jan 2026 10:00:00 +0000"},
                ]
            },
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = [list_response, msg_response, msg_response]
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_search(query="from:sender@example.com", max_results=5)

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["messages"]) == 2

    @pytest.mark.asyncio
    async def test_gmail_search_empty_results(self):
        """Test search with no results."""
        from src.mcp_gateway.tools.workspace import gmail_search

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": []}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_search(query="nonexistent")

        assert result["success"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_gmail_search_failure(self):
        """Test search failure."""
        from src.mcp_gateway.tools.workspace import gmail_search

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_search(query="test")

        assert result["success"] is False


class TestGmailList:
    """Tests for gmail_list function."""

    @pytest.mark.asyncio
    async def test_gmail_list_success(self):
        """Test successful email listing."""
        from src.mcp_gateway.tools.workspace import gmail_list

        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {
            "messages": [{"id": "msg-1"}]
        }

        msg_response = MagicMock()
        msg_response.status_code = 200
        msg_response.json.return_value = {
            "snippet": "Email preview...",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hello"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Date", "value": "Mon, 22 Jan 2026 10:00:00 +0000"},
                ]
            },
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = [list_response, msg_response]
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_list(label="INBOX", max_results=10)

        assert result["success"] is True
        assert result["label"] == "INBOX"
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_gmail_list_different_label(self):
        """Test listing from different label."""
        from src.mcp_gateway.tools.workspace import gmail_list

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": []}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await gmail_list(label="SENT")

        assert result["success"] is True
        assert result["label"] == "SENT"


# =============================================================================
# Calendar Tools Tests
# =============================================================================


class TestCalendarListEvents:
    """Tests for calendar_list_events function."""

    @pytest.mark.asyncio
    async def test_calendar_list_events_success(self):
        """Test successful event listing."""
        from src.mcp_gateway.tools.workspace import calendar_list_events

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "event-1",
                    "summary": "Team Meeting",
                    "start": {"dateTime": "2026-01-22T14:00:00Z"},
                    "end": {"dateTime": "2026-01-22T15:00:00Z"},
                    "location": "Room 101",
                    "description": "Weekly sync",
                }
            ]
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await calendar_list_events(max_results=10)

        assert result["success"] is True
        assert result["count"] == 1
        assert result["events"][0]["summary"] == "Team Meeting"

    @pytest.mark.asyncio
    async def test_calendar_list_events_all_day_event(self):
        """Test listing all-day events."""
        from src.mcp_gateway.tools.workspace import calendar_list_events

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "event-1",
                    "summary": "Holiday",
                    "start": {"date": "2026-01-22"},
                    "end": {"date": "2026-01-23"},
                }
            ]
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await calendar_list_events()

        assert result["success"] is True
        assert result["events"][0]["start"] == "2026-01-22"

    @pytest.mark.asyncio
    async def test_calendar_list_events_with_time_min(self):
        """Test event listing with time_min parameter."""
        from src.mcp_gateway.tools.workspace import calendar_list_events

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await calendar_list_events(time_min="2026-02-01T00:00:00Z")

        assert result["success"] is True


class TestCalendarCreateEvent:
    """Tests for calendar_create_event function."""

    @pytest.mark.asyncio
    async def test_calendar_create_event_success(self):
        """Test successful event creation."""
        from src.mcp_gateway.tools.workspace import calendar_create_event

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "event-123",
            "htmlLink": "https://calendar.google.com/event?eid=abc",
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await calendar_create_event(
                    summary="New Meeting",
                    start_time="2026-01-22T14:00:00Z",
                    end_time="2026-01-22T15:00:00Z",
                )

        assert result["success"] is True
        assert result["event_id"] == "event-123"
        assert "calendar.google.com" in result["html_link"]

    @pytest.mark.asyncio
    async def test_calendar_create_event_with_all_options(self):
        """Test event creation with all options."""
        from src.mcp_gateway.tools.workspace import calendar_create_event

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "event-123", "htmlLink": "https://..."}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await calendar_create_event(
                    summary="Team Sync",
                    start_time="2026-01-22T14:00:00Z",
                    end_time="2026-01-22T15:00:00Z",
                    description="Weekly team meeting",
                    location="Conference Room A",
                    attendees="user1@example.com, user2@example.com",
                )

        assert result["success"] is True

        # Verify attendees were parsed correctly
        call_args = mock_instance.post.call_args
        event_json = call_args.kwargs["json"]
        assert "attendees" in event_json
        assert len(event_json["attendees"]) == 2

    @pytest.mark.asyncio
    async def test_calendar_create_event_failure(self):
        """Test event creation failure."""
        from src.mcp_gateway.tools.workspace import calendar_create_event

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid time format"

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await calendar_create_event(
                    summary="Test",
                    start_time="invalid",
                    end_time="invalid",
                )

        assert result["success"] is False


# =============================================================================
# Drive Tools Tests
# =============================================================================


class TestDriveListFiles:
    """Tests for drive_list_files function."""

    @pytest.mark.asyncio
    async def test_drive_list_files_success(self):
        """Test successful file listing."""
        from src.mcp_gateway.tools.workspace import drive_list_files

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "files": [
                {
                    "id": "file-1",
                    "name": "Document.docx",
                    "mimeType": "application/vnd.google-apps.document",
                    "modifiedTime": "2026-01-22T10:00:00Z",
                    "size": "1024",
                    "webViewLink": "https://docs.google.com/...",
                }
            ]
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await drive_list_files(max_results=10)

        assert result["success"] is True
        assert result["count"] == 1
        assert result["files"][0]["name"] == "Document.docx"

    @pytest.mark.asyncio
    async def test_drive_list_files_with_query(self):
        """Test file listing with search query."""
        from src.mcp_gateway.tools.workspace import drive_list_files

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"files": []}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await drive_list_files(query="name contains 'report'")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_drive_list_files_in_folder(self):
        """Test file listing in specific folder."""
        from src.mcp_gateway.tools.workspace import drive_list_files

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"files": []}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await drive_list_files(folder_id="folder-123")

        assert result["success"] is True

        # Verify folder filter was applied
        call_args = mock_instance.get.call_args
        params = call_args.kwargs["params"]
        assert "'folder-123' in parents" in params.get("q", "")


class TestDriveCreateFolder:
    """Tests for drive_create_folder function."""

    @pytest.mark.asyncio
    async def test_drive_create_folder_success(self):
        """Test successful folder creation."""
        from src.mcp_gateway.tools.workspace import drive_create_folder

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "folder-123",
            "name": "New Folder",
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await drive_create_folder(name="New Folder")

        assert result["success"] is True
        assert result["folder_id"] == "folder-123"
        assert result["name"] == "New Folder"

    @pytest.mark.asyncio
    async def test_drive_create_folder_with_parent(self):
        """Test folder creation with parent folder."""
        from src.mcp_gateway.tools.workspace import drive_create_folder

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "folder-456", "name": "Subfolder"}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await drive_create_folder(name="Subfolder", parent_id="parent-123")

        assert result["success"] is True

        # Verify parent was included
        call_args = mock_instance.post.call_args
        metadata = call_args.kwargs["json"]
        assert metadata["parents"] == ["parent-123"]


# =============================================================================
# Sheets Tools Tests
# =============================================================================


class TestSheetsRead:
    """Tests for sheets_read function."""

    @pytest.mark.asyncio
    async def test_sheets_read_success(self):
        """Test successful sheet reading."""
        from src.mcp_gateway.tools.workspace import sheets_read

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "range": "Sheet1!A1:B3",
            "values": [
                ["Name", "Value"],
                ["Item 1", "100"],
                ["Item 2", "200"],
            ],
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await sheets_read(
                    spreadsheet_id="sheet-123",
                    range_notation="Sheet1!A1:B3",
                )

        assert result["success"] is True
        assert result["range"] == "Sheet1!A1:B3"
        assert len(result["values"]) == 3

    @pytest.mark.asyncio
    async def test_sheets_read_empty_range(self):
        """Test reading empty range."""
        from src.mcp_gateway.tools.workspace import sheets_read

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"range": "Sheet1!A1:A1"}  # No values

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await sheets_read(spreadsheet_id="sheet-123")

        assert result["success"] is True
        assert result["values"] == []


class TestSheetsWrite:
    """Tests for sheets_write function."""

    @pytest.mark.asyncio
    async def test_sheets_write_success(self):
        """Test successful sheet writing."""
        from src.mcp_gateway.tools.workspace import sheets_write

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "updatedRange": "Sheet1!A1:B2",
            "updatedRows": 2,
            "updatedColumns": 2,
            "updatedCells": 4,
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.put.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await sheets_write(
                    spreadsheet_id="sheet-123",
                    range_notation="Sheet1!A1:B2",
                    values=[["A", "B"], ["C", "D"]],
                )

        assert result["success"] is True
        assert result["updated_rows"] == 2
        assert result["updated_cells"] == 4

    @pytest.mark.asyncio
    async def test_sheets_write_failure(self):
        """Test sheet writing failure."""
        from src.mcp_gateway.tools.workspace import sheets_write

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Spreadsheet not found"

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.put.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await sheets_write(
                    spreadsheet_id="invalid",
                    range_notation="Sheet1!A1",
                    values=[["data"]],
                )

        assert result["success"] is False


class TestSheetsCreate:
    """Tests for sheets_create function."""

    @pytest.mark.asyncio
    async def test_sheets_create_success(self):
        """Test successful sheet creation."""
        from src.mcp_gateway.tools.workspace import sheets_create

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "spreadsheetId": "new-sheet-123",
            "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/new-sheet-123",
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await sheets_create(title="New Spreadsheet")

        assert result["success"] is True
        assert result["spreadsheet_id"] == "new-sheet-123"
        assert "spreadsheets" in result["url"]


# =============================================================================
# Docs Tools Tests
# =============================================================================


class TestDocsCreate:
    """Tests for docs_create function."""

    @pytest.mark.asyncio
    async def test_docs_create_success(self):
        """Test successful document creation."""
        from src.mcp_gateway.tools.workspace import docs_create

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "documentId": "doc-123",
            "title": "New Document",
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await docs_create(title="New Document")

        assert result["success"] is True
        assert result["document_id"] == "doc-123"
        assert result["title"] == "New Document"

    @pytest.mark.asyncio
    async def test_docs_create_failure(self):
        """Test document creation failure."""
        from src.mcp_gateway.tools.workspace import docs_create

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Permission denied"

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await docs_create(title="Test")

        assert result["success"] is False


class TestDocsRead:
    """Tests for docs_read function."""

    @pytest.mark.asyncio
    async def test_docs_read_success(self):
        """Test successful document reading."""
        from src.mcp_gateway.tools.workspace import docs_read

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "documentId": "doc-123",
            "title": "My Document",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Hello, "}}
                            ]
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "World!"}}
                            ]
                        }
                    },
                ]
            },
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await docs_read(document_id="doc-123")

        assert result["success"] is True
        assert result["document_id"] == "doc-123"
        assert result["title"] == "My Document"
        assert "Hello" in result["content"]
        assert "World" in result["content"]

    @pytest.mark.asyncio
    async def test_docs_read_empty_document(self):
        """Test reading empty document."""
        from src.mcp_gateway.tools.workspace import docs_read

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "documentId": "doc-123",
            "title": "Empty Doc",
            "body": {"content": []},
        }

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await docs_read(document_id="doc-123")

        assert result["success"] is True
        assert result["content"] == ""


class TestDocsAppend:
    """Tests for docs_append function."""

    @pytest.mark.asyncio
    async def test_docs_append_success(self):
        """Test successful document append."""
        from src.mcp_gateway.tools.workspace import docs_append

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await docs_append(
                    document_id="doc-123",
                    text="New paragraph content",
                )

        assert result["success"] is True
        assert result["document_id"] == "doc-123"

    @pytest.mark.asyncio
    async def test_docs_append_verifies_batch_update_format(self):
        """Test that append uses correct batchUpdate format."""
        from src.mcp_gateway.tools.workspace import docs_append

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                await docs_append(document_id="doc-123", text="Test text")

        # Verify batchUpdate structure
        call_args = mock_instance.post.call_args
        url = call_args.args[0]
        assert ":batchUpdate" in url

        request_body = call_args.kwargs["json"]
        assert "requests" in request_body
        assert "insertText" in request_body["requests"][0]

    @pytest.mark.asyncio
    async def test_docs_append_failure(self):
        """Test document append failure."""
        from src.mcp_gateway.tools.workspace import docs_append

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Document not found"

        with patch("src.mcp_gateway.tools.workspace._get_headers", new_callable=AsyncMock) as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer token"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await docs_append(document_id="invalid", text="Test")

        assert result["success"] is False
