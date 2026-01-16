# Google Workspace MCP Setup Script for Windows
# Fetches OAuth credentials from GCP Secret Manager and configures workspace-mcp
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Python/uv installed
#
# Usage:
#   .\scripts\setup-workspace-mcp.ps1
#

$ErrorActionPreference = "Stop"

Write-Host "🚀 Google Workspace MCP Setup" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$GCP_PROJECT = "project38-483612"
$CREDENTIALS_DIR = "$env:USERPROFILE\.google_workspace_mcp\credentials"

# Check prerequisites
Write-Host "📋 Checking prerequisites..." -ForegroundColor Yellow

# Check gcloud
try {
    $null = Get-Command gcloud -ErrorAction Stop
    Write-Host "   ✅ gcloud CLI found" -ForegroundColor Green
} catch {
    Write-Host "❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Red
    exit 1
}

# Check uvx
try {
    $null = Get-Command uvx -ErrorAction Stop
    Write-Host "   ✅ uvx found" -ForegroundColor Green
} catch {
    Write-Host "❌ uvx not found. Install with: pip install uv" -ForegroundColor Red
    exit 1
}

# Check GCP authentication
$token = gcloud auth print-access-token 2>$null
if (-not $token) {
    Write-Host "⚠️  Not authenticated to GCP. Running gcloud auth login..." -ForegroundColor Yellow
    gcloud auth login
}
Write-Host "   ✅ GCP authenticated" -ForegroundColor Green

# Fetch credentials from GCP Secret Manager
Write-Host ""
Write-Host "🔐 Fetching credentials from GCP Secret Manager..." -ForegroundColor Yellow

$CLIENT_ID = gcloud secrets versions access latest --secret=GOOGLE-OAUTH-CLIENT-ID --project=$GCP_PROJECT 2>$null
if (-not $CLIENT_ID) {
    Write-Host "❌ Failed to fetch GOOGLE-OAUTH-CLIENT-ID" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ CLIENT_ID fetched" -ForegroundColor Green

$CLIENT_SECRET = gcloud secrets versions access latest --secret=GOOGLE-OAUTH-CLIENT-SECRET --project=$GCP_PROJECT 2>$null
if (-not $CLIENT_SECRET) {
    Write-Host "❌ Failed to fetch GOOGLE-OAUTH-CLIENT-SECRET" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ CLIENT_SECRET fetched" -ForegroundColor Green

$REFRESH_TOKEN = gcloud secrets versions access latest --secret=GOOGLE-OAUTH-REFRESH-TOKEN --project=$GCP_PROJECT 2>$null
if (-not $REFRESH_TOKEN) {
    Write-Host "❌ Failed to fetch GOOGLE-OAUTH-REFRESH-TOKEN" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ REFRESH_TOKEN fetched" -ForegroundColor Green

# Create credentials directory
Write-Host ""
Write-Host "📁 Creating credentials directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $CREDENTIALS_DIR | Out-Null
Write-Host "   ✅ $CREDENTIALS_DIR created" -ForegroundColor Green

# Create token file in Google OAuth format
Write-Host ""
Write-Host "📝 Creating token file..." -ForegroundColor Yellow
$TOKEN_FILE = "$CREDENTIALS_DIR\default_user.json"

$tokenContent = @{
    token = $null
    refresh_token = $REFRESH_TOKEN
    token_uri = "https://oauth2.googleapis.com/token"
    client_id = $CLIENT_ID
    client_secret = $CLIENT_SECRET
    scopes = @(
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
    )
    expiry = $null
} | ConvertTo-Json -Depth 10

$tokenContent | Out-File -FilePath $TOKEN_FILE -Encoding utf8
Write-Host "   ✅ Token file created: $TOKEN_FILE" -ForegroundColor Green

# Add MCP server to Claude Code
Write-Host ""
Write-Host "🔧 Configuring Claude Code MCP..." -ForegroundColor Yellow

# Remove if exists
claude mcp remove google-workspace 2>$null

# Add with user scope (persistent)
claude mcp add --scope user google-workspace -- uvx workspace-mcp --tool-tier complete --single-user

Write-Host "   ✅ MCP server added to Claude Code" -ForegroundColor Green

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "The Google Workspace MCP server is now configured."
Write-Host "It will work automatically in every Claude Code session."
Write-Host ""
Write-Host "Available services: Gmail, Calendar, Drive, Docs, Sheets,"
Write-Host "                    Slides, Forms, Tasks, Chat, Search"
Write-Host ""
Write-Host 'To test, start a new Claude Code session and ask:'
Write-Host '   "List my recent Gmail messages"' -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
