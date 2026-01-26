# SECRETS_MATRIX.md - Secrets Domain Mapping

> **Generated**: 2026-01-26
> **Purpose**: Baseline verification artifact for domain split (Business/Personal)

## Overview

This document maps every secret to its usage location and domain classification. Critical for ensuring PERSONAL secrets are not accessible from BUSINESS services and vice versa.

---

## Secret Inventory

### BUSINESS Domain Secrets

| Secret Name | Code Path | Purpose | Service |
|-------------|-----------|---------|---------|
| `RAILWAY-API` | `src/railway_client.py:16`, `src/credential_lifecycle.py:357`, `.github/workflows/deploy-railway.yml:115` | Railway API token | Main API, CI/CD |
| `N8N-API` | `src/orchestrator.py:30`, `src/credential_lifecycle.py:407`, `.github/workflows/test-n8n-deploy.yml:33` | n8n workflow automation | Main API, CI/CD |
| `github-app-private-key` | `src/github_auth.py:53`, `src/github_auth.sh:15`, `src/github_app_client.py:12`, `src/orchestrator.py:26` | GitHub App JWT signing | Main API |
| `MCP-GATEWAY-TOKEN` | `src/credential_lifecycle.py:440`, `src/mcp_gateway/config.py` | MCP Gateway auth | Main API |
| `MCP-TUNNEL-TOKEN` | `src/gcp_tunnel_client.py:66`, `src/gcp_tunnel/adapter.py:69`, `.github/workflows/daily-email-agent.yml:78` | GCP Tunnel auth | GCP Tunnel, **also PERSONAL** |
| `GCS-RELAY-SA-KEY` | `.github/workflows/configure-railway-gcs.yml:39` | GCS relay service account | CI/CD |
| `ANTHROPIC-API` | `services/litellm-gateway/` (via env), `src/factory/generator.py:106` | Anthropic API | LiteLLM Gateway |
| `OPENAI-API` | `services/litellm-gateway/` (via env) | OpenAI API | LiteLLM Gateway |
| `GEMINI-API` | `services/litellm-gateway/` (via env) | Google Gemini API | LiteLLM Gateway |

### PERSONAL Domain Secrets

| Secret Name | Code Path | Purpose | Service |
|-------------|-----------|---------|---------|
| `GOOGLE-OAUTH-CLIENT-ID` | `src/workspace_mcp_bridge/config.py:75`, `src/credential_lifecycle.py:290`, `.github/workflows/gmail-trash.yml:55` | Google OAuth | Workspace Bridge, Email Agent |
| `GOOGLE-OAUTH-CLIENT-SECRET` | `src/workspace_mcp_bridge/config.py:76`, `src/credential_lifecycle.py:291`, `.github/workflows/gmail-trash.yml:56` | Google OAuth | Workspace Bridge, Email Agent |
| `GOOGLE-OAUTH-REFRESH-TOKEN` | `src/workspace_mcp_bridge/config.py:77`, `src/credential_lifecycle.py:292`, `.github/workflows/gmail-trash.yml:57` | Google OAuth refresh | Workspace Bridge, Email Agent |
| `WORKSPACE-MCP-BRIDGE-TOKEN` | `src/workspace_mcp_bridge/config.py:78` | Workspace bridge auth | Workspace Bridge |
| `TELEGRAM-BOT-TOKEN` | `src/agents/smart_email/graph.py:126`, `src/background_agents/runner.py:121`, `.github/workflows/daily-email-agent.yml:88` | Telegram bot | Email Agent, **also BUSINESS** |
| `TELEGRAM-CHAT-ID` | `src/agents/smart_email/graph.py:127`, `src/background_agents/runner.py:122`, `.github/workflows/daily-email-agent.yml:97` | Personal Telegram chat | Email Agent |

### SHARED Secrets (Used by Both Domains)

| Secret Name | Code Path | Purpose | Notes |
|-------------|-----------|---------|-------|
| `MCP-TUNNEL-TOKEN` | See above | GCP Tunnel (has workspace tools) | **PROBLEM**: Used by both domains |
| `TELEGRAM-BOT-TOKEN` | See above | Telegram notifications | **PROBLEM**: Used by NightWatch (BUSINESS) and Email Agent (PERSONAL) |

---

## Environment Variables by Service

### Main FastAPI (`src/api/main.py`) - BUSINESS

```
DATABASE_URL                    # Railway PostgreSQL
PORT                           # Railway
RAILWAY_ENVIRONMENT            # Railway
ALLOWED_ORIGINS                # CORS
GCS_RELAY_ENABLED             # GCS relay toggle
MONITORING_AUTO_START         # NightWatch
GITHUB_RELAY_ENABLED          # GitHub relay toggle
MCP_GATEWAY_ENABLED           # MCP gateway toggle
WORKSPACE_MCP_ENABLED         # ⚠️ PERSONAL COUPLING - Remove!
```

### Telegram Bot (`services/telegram-bot/`) - BUSINESS

```
TELEGRAM_BOT_TOKEN            # Bot auth
DATABASE_URL                  # Railway PostgreSQL
TELEGRAM_WEBHOOK_URL          # Webhook URL
LITELLM_GATEWAY_URL          # LiteLLM gateway
GCP_PROJECT_ID               # GCP project
```

**Problem**: Also imports `src/agents/smart_email` (PERSONAL)

### LiteLLM Gateway (`services/litellm-gateway/`) - BUSINESS

```
ANTHROPIC_API_KEY            # From GCP secret ANTHROPIC-API
OPENAI_API_KEY              # From GCP secret OPENAI-API
GEMINI_API_KEY              # From GCP secret GEMINI-API
LITELLM_MASTER_KEY          # Admin API key
DATABASE_URL                 # Railway PostgreSQL
REDIS_HOST                  # Railway Redis
REDIS_PORT                  # Railway Redis
REDIS_PASSWORD              # Railway Redis
ALERT_WEBHOOK_URL           # n8n budget alerts
OTEL_SERVICE_NAME           # OpenTelemetry
```

### Smart Email Agent (`.github/workflows/daily-email-agent.yml`) - PERSONAL

```
MCP_GATEWAY_URL             # GCP Tunnel URL
MCP_GATEWAY_TOKEN           # From GCP secret MCP-TUNNEL-TOKEN
TELEGRAM_BOT_TOKEN          # From GCP secret TELEGRAM-BOT-TOKEN
TELEGRAM_CHAT_ID            # From GCP secret TELEGRAM-CHAT-ID
```

### Workspace MCP Bridge (`src/workspace_mcp_bridge/`) - PERSONAL

```
GOOGLE_OAUTH_CLIENT_ID       # From GCP secret
GOOGLE_OAUTH_CLIENT_SECRET   # From GCP secret
GOOGLE_OAUTH_REFRESH_TOKEN   # From GCP secret
WORKSPACE_MCP_BRIDGE_TOKEN   # From GCP secret
```

---

## Coupling Issues Found

### Issue 1: Workspace Mount in Main API

**File**: `src/api/main.py:184-198`
**Problem**: Main BUSINESS API has conditional mount of PERSONAL workspace bridge
**Evidence**:
```python
WORKSPACE_MCP_ENABLED = os.getenv("WORKSPACE_MCP_ENABLED", "false").lower() == "true"
if WORKSPACE_MCP_ENABLED:
    from src.workspace_mcp_bridge.server import create_app as create_workspace_app
    workspace_app = create_workspace_app()
    app.mount("/workspace", workspace_app)
```
**Action**: Remove workspace mount from BUSINESS API

### Issue 2: MCP-TUNNEL-TOKEN Shared

**Problem**: The GCP Tunnel provides both BUSINESS tools (Railway, n8n) and PERSONAL tools (Gmail, Calendar, Drive)
**Evidence**: `cloud_functions/mcp_router/main.py` has tools for both domains
**Action**: Split GCP Tunnel into two services OR scope tools by token

### Issue 3: TELEGRAM-BOT-TOKEN Shared

**Problem**: Same Telegram bot used for:
- NightWatch BUSINESS notifications (`src/nightwatch/service.py:87`)
- Smart Email PERSONAL summaries (`src/agents/smart_email/graph.py:118`)
**Action**: Consider separate bots OR accept shared notification channel

### Issue 4: Telegram Bot Dockerfile Clones PERSONAL Code

**File**: `services/telegram-bot/Dockerfile:35-42`
**Problem**: Explicitly clones `src/agents` (PERSONAL) into BUSINESS container
**Evidence**:
```dockerfile
git sparse-checkout set src/agents && \
cp -r /tmp/repo/src/agents /app/src/
```
**Action**: Remove this clone - Telegram bot should NOT include Smart Email

---

## Recommended Secret Scoping

### BUSINESS Service Account / IAM Scope

Should have access to:
- `RAILWAY-API`
- `N8N-API`
- `github-app-private-key`
- `MCP-GATEWAY-TOKEN`
- `GCS-RELAY-SA-KEY`
- `ANTHROPIC-API` (for LiteLLM)
- `OPENAI-API` (for LiteLLM)
- `GEMINI-API` (for LiteLLM)
- `TELEGRAM-BOT-TOKEN` (for NightWatch notifications only)

Should NOT have access to:
- `GOOGLE-OAUTH-*` secrets
- `WORKSPACE-MCP-*` secrets
- `TELEGRAM-CHAT-ID` (personal)

### PERSONAL Service Account / IAM Scope

Should have access to:
- `GOOGLE-OAUTH-CLIENT-ID`
- `GOOGLE-OAUTH-CLIENT-SECRET`
- `GOOGLE-OAUTH-REFRESH-TOKEN`
- `WORKSPACE-MCP-BRIDGE-TOKEN`
- `TELEGRAM-BOT-TOKEN`
- `TELEGRAM-CHAT-ID`
- LLM key (separate personal key OR via direct API, NOT through LiteLLM Gateway)

Should NOT have access to:
- `RAILWAY-API`
- `N8N-API`
- `github-app-private-key`
- `MCP-GATEWAY-TOKEN`

---

## GCP Secret Manager Implementation

### Option A: Prefix-Based Separation (Simpler)

```
BUSINESS-RAILWAY-API
BUSINESS-N8N-API
BUSINESS-GITHUB-APP-KEY
PERSONAL-GOOGLE-OAUTH-CLIENT-ID
PERSONAL-GOOGLE-OAUTH-CLIENT-SECRET
PERSONAL-TELEGRAM-BOT-TOKEN
```

With IAM conditions:
- BUSINESS SA: `resource.name.startsWith("BUSINESS-")`
- PERSONAL SA: `resource.name.startsWith("PERSONAL-")`

### Option B: Separate GCP Projects (Stronger Isolation)

- Project A: `project38-business` - All BUSINESS secrets
- Project B: `project38-personal` - All PERSONAL secrets

Each has its own service account with no cross-access.

---

## Action Items

1. **Remove workspace mount** from `src/api/main.py`
2. **Remove src/agents clone** from `services/telegram-bot/Dockerfile`
3. **Split GCP Tunnel tools** or create domain-scoped tokens
4. **Create separate IAM scopes** for BUSINESS vs PERSONAL secrets
5. **Verify LiteLLM Gateway** - ensure PERSONAL doesn't route through it (or logging is disabled)
