# Google Workspace MCP Server - Persistent Autonomy Setup

**Date**: 2026-01-16
**Status**: Implementation Guide
**Goal**: Achieve TRUE persistent autonomy for Google Workspace (works in EVERY session)

---

## Why This Matters

The previous implementation (`src/workspace_mcp_bridge/`) required:
- Token loading in each session
- Dependencies (fastapi, google-api-python-client)
- Manual initialization

**The new approach** uses a standard MCP Server that:
- Works automatically in every Claude Code session
- Requires zero dependencies in the session
- OAuth tokens persist across all sessions

---

## Architecture Comparison

| Aspect | Old (workspace_mcp_bridge) | New (MCP Server) |
|--------|---------------------------|------------------|
| Works every session | ❌ Requires token loading | ✅ Automatic |
| Dependencies | ❌ fastapi, google-api | ✅ None in session |
| Installation | ❌ Per environment | ✅ Once globally |
| Tools available | ~28 | 100+ |
| Protocol | Custom API | Standard MCP |

---

## Recommended MCP Server

**[taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp)**

Features:
- 10 Google services: Gmail, Drive, Calendar, Docs, Sheets, Slides, Forms, Tasks, Chat, Search
- 100+ tools across all services
- OAuth 2.1 support with automatic token refresh
- One-click installation via `.dxt` file
- Remote OAuth support for multi-user deployments

---

## Setup Guide

### Step 1: Google Cloud Console Setup

#### 1.1 Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select project: `project38-483612` (or create new)
3. Navigate to **APIs & Services → Credentials**
4. Click **Create Credentials → OAuth Client ID**
5. Select **Desktop Application**
6. Name it: `Google Workspace MCP`
7. Click **Create**
8. **Save** the Client ID and Client Secret

#### 1.2 Enable Required APIs

Enable each API (one-click links when logged in):

| API | Enable Link |
|-----|-------------|
| Gmail API | https://console.cloud.google.com/apis/library/gmail.googleapis.com |
| Calendar API | https://console.cloud.google.com/apis/library/calendar-json.googleapis.com |
| Drive API | https://console.cloud.google.com/apis/library/drive.googleapis.com |
| Sheets API | https://console.cloud.google.com/apis/library/sheets.googleapis.com |
| Docs API | https://console.cloud.google.com/apis/library/docs.googleapis.com |
| Slides API | https://console.cloud.google.com/apis/library/slides.googleapis.com |
| Forms API | https://console.cloud.google.com/apis/library/forms.googleapis.com |
| Tasks API | https://console.cloud.google.com/apis/library/tasks.googleapis.com |
| Chat API | https://console.cloud.google.com/apis/library/chat.googleapis.com |

### Step 2: Store Credentials in GCP Secret Manager

Store credentials securely (consistent with existing architecture):

```bash
# Using GitHub workflow (recommended)
gh workflow run setup-workspace-mcp.yml \
  -f client_id="YOUR_CLIENT_ID.apps.googleusercontent.com" \
  -f client_secret="YOUR_CLIENT_SECRET"
```

Or manually via GCP Console:
- Secret: `WORKSPACE-MCP-CLIENT-ID`
- Secret: `WORKSPACE-MCP-CLIENT-SECRET`

### Step 3: Install MCP Server

#### Option A: Using uvx (No Installation)

```bash
uvx workspace-mcp --tool-tier complete
```

#### Option B: Using Homebrew (macOS)

```bash
# For ngs/google-mcp-server (lighter alternative)
brew tap ngs/tap && brew install google-mcp-server
```

#### Option C: Using pip

```bash
pip install workspace-mcp
```

### Step 4: Add to Claude Code (PERSISTENT)

```bash
# Add with user scope - persists across ALL sessions
claude mcp add --scope user google-workspace -- uvx workspace-mcp --tool-tier complete
```

Or for the ngs server:
```bash
claude mcp add --scope user google /opt/homebrew/bin/google-mcp-server
```

### Step 5: Configure Environment Variables

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "uvx",
      "args": ["workspace-mcp", "--tool-tier", "complete"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "${WORKSPACE_MCP_CLIENT_ID}",
        "GOOGLE_OAUTH_CLIENT_SECRET": "${WORKSPACE_MCP_CLIENT_SECRET}"
      }
    }
  }
}
```

### Step 6: Complete OAuth Flow (One-Time Only)

Run the server directly to complete OAuth:

```bash
uvx workspace-mcp --tool-tier complete
# Browser opens → Authorize with Google account → Token saved automatically
```

---

## Verification

### Check MCP Server is Registered

```bash
claude mcp list
# Should show: google-workspace: uvx workspace-mcp --tool-tier complete
```

### Test in New Session

Start a new Claude Code session and ask:
```
"List my recent Gmail messages"
```

If it works without any token loading → **SUCCESS!**

---

## Available Tools (100+)

### Gmail
- `gmail_send_email` - Send emails
- `gmail_search` - Search messages
- `gmail_read_email` - Read specific message
- `gmail_list_labels` - List all labels
- `gmail_modify_labels` - Add/remove labels
- `gmail_trash_email` - Move to trash
- `gmail_create_draft` - Create draft

### Calendar
- `calendar_list_events` - List upcoming events
- `calendar_create_event` - Create new event
- `calendar_update_event` - Modify event
- `calendar_delete_event` - Delete event
- `calendar_list_calendars` - List all calendars

### Drive
- `drive_list_files` - List files/folders
- `drive_search` - Search files
- `drive_upload` - Upload file
- `drive_download` - Download file
- `drive_create_folder` - Create folder
- `drive_share` - Share file
- `drive_delete` - Delete file

### Sheets
- `sheets_create` - Create spreadsheet
- `sheets_read_range` - Read cells
- `sheets_write_range` - Write cells
- `sheets_append` - Append rows
- `sheets_get_metadata` - Get sheet info

### Docs
- `docs_create` - Create document
- `docs_read` - Read content
- `docs_insert_text` - Insert text
- `docs_delete_content` - Delete content
- `docs_get_metadata` - Get document info

### Slides
- `slides_create` - Create presentation
- `slides_add_slide` - Add new slide
- `slides_update_text` - Update text
- `slides_get_metadata` - Get presentation info

### Forms
- `forms_create` - Create form
- `forms_add_question` - Add question
- `forms_get_responses` - Get responses

### Tasks
- `tasks_list` - List task lists
- `tasks_create` - Create task
- `tasks_update` - Update task
- `tasks_complete` - Mark complete

### Chat
- `chat_send_message` - Send message to space
- `chat_list_spaces` - List spaces

### Search
- `custom_search` - Web search via Google

---

## Troubleshooting

### "MCP server not found"
- Verify installation: `which google-mcp-server` or `uvx --version`
- Check `~/.claude.json` configuration

### "OAuth token expired"
- Re-run: `uvx workspace-mcp --tool-tier complete`
- Complete OAuth flow in browser

### "API not enabled"
- Go to Google Cloud Console
- Enable the specific API that's failing

### "Insufficient permissions"
- Re-authorize with all scopes
- Check OAuth consent screen includes all APIs

---

## Security Considerations

1. **Credentials in GCP Secret Manager** - Not in code or env files
2. **OAuth tokens stored locally** - In OS keychain, not plaintext
3. **Scope limitation** - Only enable APIs you need
4. **Audit logging** - Google Cloud logs all API access

---

## Migration from Old Implementation

The old `src/workspace_mcp_bridge/` can be:
1. **Kept as backup** - Still works via GitHub Actions
2. **Deprecated** - MCP Server is superior for daily use
3. **Removed** - After verifying MCP Server works

Recommended: Keep for 30 days, then remove if MCP Server proves reliable.

---

## References

- [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp)
- [ngs/google-mcp-server](https://github.com/ngs/google-mcp-server)
- [Google Cloud MCP Announcement](https://cloud.google.com/blog/products/ai-machine-learning/announcing-official-mcp-support-for-google-services)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
