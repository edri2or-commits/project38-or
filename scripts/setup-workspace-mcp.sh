#!/bin/bash
#
# Google Workspace MCP Setup Script
# Fetches OAuth credentials from GCP Secret Manager and configures workspace-mcp
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Access to project38-483612 GCP project
#
# Usage:
#   ./scripts/setup-workspace-mcp.sh
#

set -e

echo "🚀 Google Workspace MCP Setup"
echo "=============================="
echo ""

# Configuration
GCP_PROJECT="project38-483612"
CREDENTIALS_DIR="$HOME/.google_workspace_mcp/credentials"

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo "   ✅ gcloud CLI found"

if ! command -v uvx &> /dev/null; then
    echo "❌ uvx not found. Install with: pip install uv"
    exit 1
fi
echo "   ✅ uvx found"

# Check GCP authentication
if ! gcloud auth print-access-token &> /dev/null; then
    echo "⚠️  Not authenticated to GCP. Running gcloud auth login..."
    gcloud auth login
fi
echo "   ✅ GCP authenticated"

# Fetch credentials from GCP Secret Manager
echo ""
echo "🔐 Fetching credentials from GCP Secret Manager..."

CLIENT_ID=$(gcloud secrets versions access latest --secret=GOOGLE-OAUTH-CLIENT-ID --project=$GCP_PROJECT 2>/dev/null)
if [ -z "$CLIENT_ID" ]; then
    echo "❌ Failed to fetch GOOGLE-OAUTH-CLIENT-ID"
    exit 1
fi
echo "   ✅ CLIENT_ID fetched"

CLIENT_SECRET=$(gcloud secrets versions access latest --secret=GOOGLE-OAUTH-CLIENT-SECRET --project=$GCP_PROJECT 2>/dev/null)
if [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Failed to fetch GOOGLE-OAUTH-CLIENT-SECRET"
    exit 1
fi
echo "   ✅ CLIENT_SECRET fetched"

REFRESH_TOKEN=$(gcloud secrets versions access latest --secret=GOOGLE-OAUTH-REFRESH-TOKEN --project=$GCP_PROJECT 2>/dev/null)
if [ -z "$REFRESH_TOKEN" ]; then
    echo "❌ Failed to fetch GOOGLE-OAUTH-REFRESH-TOKEN"
    exit 1
fi
echo "   ✅ REFRESH_TOKEN fetched"

# Create credentials directory
echo ""
echo "📁 Creating credentials directory..."
mkdir -p "$CREDENTIALS_DIR"
chmod 700 "$CREDENTIALS_DIR"
echo "   ✅ $CREDENTIALS_DIR created"

# Create token file in Google OAuth format
echo ""
echo "📝 Creating token file..."
TOKEN_FILE="$CREDENTIALS_DIR/default_user.json"

cat > "$TOKEN_FILE" << EOF
{
    "token": null,
    "refresh_token": "$REFRESH_TOKEN",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "$CLIENT_ID",
    "client_secret": "$CLIENT_SECRET",
    "scopes": [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/tasks",
        "https://www.googleapis.com/auth/forms",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email"
    ],
    "expiry": null
}
EOF

chmod 600 "$TOKEN_FILE"
echo "   ✅ Token file created: $TOKEN_FILE"

# Add MCP server to Claude Code
echo ""
echo "🔧 Configuring Claude Code MCP..."

# Check if already configured
if claude mcp list 2>/dev/null | grep -q "google-workspace"; then
    echo "   ⚠️  google-workspace already configured, updating..."
    claude mcp remove google-workspace 2>/dev/null || true
fi

# Add with user scope (persistent)
claude mcp add --scope user google-workspace -- uvx workspace-mcp --tool-tier complete --single-user

echo "   ✅ MCP server added to Claude Code"

# Verify setup
echo ""
echo "🧪 Verifying setup..."

# Quick test - just check if it starts
if timeout 5 uvx workspace-mcp --tool-tier complete --single-user 2>&1 | grep -q "Created credentials directory\|Scope management configured"; then
    echo "   ✅ workspace-mcp starts successfully"
else
    echo "   ⚠️  Could not verify workspace-mcp (may still work)"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "The Google Workspace MCP server is now configured."
echo "It will work automatically in every Claude Code session."
echo ""
echo "Available services: Gmail, Calendar, Drive, Docs, Sheets,"
echo "                    Slides, Forms, Tasks, Chat, Search"
echo ""
echo "To test, start a new Claude Code session and ask:"
echo '   "List my recent Gmail messages"'
echo "════════════════════════════════════════════════════════════"
