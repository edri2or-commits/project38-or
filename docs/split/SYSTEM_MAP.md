# SYSTEM_MAP.md - Runtime Components Inventory

> **Generated**: 2026-01-26
> **Purpose**: Baseline verification artifact for domain split (Business/Personal)

## Overview

This document inventories all runtime components in the monorepo, their entrypoints, deployment configurations, and domain classification.

---

## 1. Main FastAPI Application (BUSINESS + PERSONAL mixed)

| Property | Value |
|----------|-------|
| **Entrypoint** | `src/api/main.py` |
| **Start Command** | `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT` |
| **Railway Config** | `/railway.toml` |
| **Health Endpoint** | `/api/health` |
| **Domain** | **MIXED** (must be split) |

### Routes Mounted

| Route | Module | Domain |
|-------|--------|--------|
| `/api/health` | `src/api/routes/health.py` | BUSINESS |
| `/api/agents` | `src/api/routes/agents.py` | BUSINESS |
| `/api/tasks` | `src/api/routes/tasks.py` | BUSINESS |
| `/api/backups` | `src/api/routes/backups.py` | BUSINESS |
| `/metrics/*` | `src/api/routes/metrics.py` | BUSINESS |
| `/costs/*` | `src/api/routes/costs.py` | BUSINESS |
| `/monitoring/*` | `src/api/routes/monitoring.py` | BUSINESS |
| `/api/nightwatch/*` | `src/api/routes/nightwatch.py` | BUSINESS |
| `/api/learning/*` | `src/api/routes/learning.py` | BUSINESS |
| `/secrets/*` | `src/api/routes/secrets_health.py` | BUSINESS |
| `/mcp` (mount) | `src/mcp_gateway/server.py` | BUSINESS |
| `/workspace` (mount) | `src/workspace_mcp_bridge/server.py` | **PERSONAL** (coupling!) |

### Cron Jobs (Railway)

| Schedule | Endpoint | Domain |
|----------|----------|--------|
| `0 0-6 * * *` | `/api/nightwatch/tick` | BUSINESS |
| `0 6 * * *` | `/api/nightwatch/morning-summary` | BUSINESS |

---

## 2. Telegram Bot Service (BUSINESS with PERSONAL leak)

| Property | Value |
|----------|-------|
| **Entrypoint** | `services/telegram-bot/main.py` |
| **Dockerfile** | `services/telegram-bot/Dockerfile` |
| **Railway Config** | `services/telegram-bot/railway.toml` |
| **Health Endpoint** | `/health` |
| **Domain** | **BUSINESS** (but has PERSONAL code leak) |

### CRITICAL COUPLING

The Dockerfile at lines 35-42 explicitly clones `src/agents` into the container:

```dockerfile
# Fetch src/agents for Smart Email Agent using sparse checkout
RUN git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/edri2or-commits/project38-or.git /tmp/repo && \
    cd /tmp/repo && \
    git sparse-checkout set src/agents && \
    mkdir -p /app/src && \
    cp -r /tmp/repo/src/agents /app/src/ && \
    rm -rf /tmp/repo
```

**handlers.py imports** (lines 287-610):
- `from src.agents.smart_email.graph import run_smart_email_agent`
- `from src.agents.smart_email.conversation import ConversationHandler`
- `from src.agents.smart_email.actions import create_approval_manager`

**ACTION REQUIRED**: Remove all `src/agents` imports and Dockerfile cloning.

---

## 3. LiteLLM Gateway (BUSINESS)

| Property | Value |
|----------|-------|
| **Entrypoint** | LiteLLM proxy container (no custom code) |
| **Dockerfile** | `services/litellm-gateway/Dockerfile` |
| **Config** | `services/litellm-gateway/litellm-config.yaml` |
| **Railway Config** | `services/litellm-gateway/railway.toml` |
| **Health Endpoint** | `/health` |
| **Domain** | **BUSINESS** |

### LLM Provider Keys

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

**Decision Required**: Should PERSONAL use this gateway or call providers directly?

---

## 4. GCS MCP Relay (BUSINESS)

| Property | Value |
|----------|-------|
| **Entrypoint** | `services/gcs-mcp-relay/server.js` (Node.js) |
| **Dockerfile** | `services/gcs-mcp-relay/Dockerfile` |
| **Domain** | **BUSINESS** |

---

## 5. Railway MCP Bridge (BUSINESS)

| Property | Value |
|----------|-------|
| **Entrypoint** | `services/railway-mcp-bridge/server.js` (Node.js) |
| **Dockerfile** | `services/railway-mcp-bridge/Dockerfile` |
| **Railway Config** | `services/railway-mcp-bridge/railway.toml` |
| **Domain** | **BUSINESS** |

---

## 6. MCP Gateway CloudRun (BUSINESS)

| Property | Value |
|----------|-------|
| **Entrypoint** | `services/mcp-gateway-cloudrun/main.py` |
| **Dockerfile** | `services/mcp-gateway-cloudrun/Dockerfile` |
| **Platform** | Google Cloud Run |
| **Domain** | **BUSINESS** |

---

## 7. GCP MCP Server (BUSINESS)

| Property | Value |
|----------|-------|
| **Entrypoint** | `src/gcp_mcp/server.py` |
| **Dockerfile** | `src/gcp_mcp/Dockerfile` |
| **Platform** | Google Cloud Run |
| **Domain** | **BUSINESS** |

---

## 8. Cloud Functions MCP Router (BUSINESS + PERSONAL tools)

| Property | Value |
|----------|-------|
| **Entrypoint** | `cloud_functions/mcp_router/main.py` |
| **Dockerfile** | `cloud_functions/mcp_router/Dockerfile` |
| **Platform** | Google Cloud Run / Cloud Functions |
| **Domain** | **MIXED** (includes workspace tools) |

### Tools Provided

| Tool Category | Domain |
|---------------|--------|
| Railway tools | BUSINESS |
| n8n tools | BUSINESS |
| Monitoring tools | BUSINESS |
| GCP tools | BUSINESS |
| **Workspace tools** (gmail, calendar, drive, sheets, docs) | **PERSONAL** |

---

## 9. Smart Email Agent (PERSONAL)

| Property | Value |
|----------|-------|
| **Module** | `src/agents/smart_email/` |
| **Main** | `src/agents/smart_email/graph.py` |
| **Workflow** | `.github/workflows/daily-email-agent.yml` |
| **Schedule** | `0 5 * * *` (05:00 UTC daily) |
| **Domain** | **PERSONAL** |

### Dependencies

- `MCP_TUNNEL_TOKEN` (for Gmail access via GCP Tunnel)
- `TELEGRAM_BOT_TOKEN` (for sending summaries)
- `TELEGRAM_CHAT_ID` (personal chat)
- Google OAuth tokens (via GCP Secrets)

---

## 10. Workspace MCP Bridge (PERSONAL)

| Property | Value |
|----------|-------|
| **Module** | `src/workspace_mcp_bridge/` |
| **Server** | `src/workspace_mcp_bridge/server.py` |
| **Auth** | `src/workspace_mcp_bridge/auth.py` |
| **Domain** | **PERSONAL** |

### Tools Provided

| Tool | Service |
|------|---------|
| `gmail_send`, `gmail_list`, `gmail_search` | Gmail |
| `calendar_list_events`, `calendar_create_event` | Calendar |
| `drive_list_files`, `drive_create_folder` | Drive |
| `sheets_read`, `sheets_write`, `sheets_create` | Sheets |
| `docs_create`, `docs_read`, `docs_append` | Docs |

---

## Domain Classification Summary

| Component | Current Domain | Action |
|-----------|---------------|--------|
| Main FastAPI (`src/api/main.py`) | MIXED | Split: Remove workspace mount |
| Telegram Bot (`services/telegram-bot/`) | BUSINESS + leak | Remove src/agents clone |
| LiteLLM Gateway | BUSINESS | Keep |
| GCS MCP Relay | BUSINESS | Keep |
| Railway MCP Bridge | BUSINESS | Keep |
| MCP Gateway CloudRun | BUSINESS | Keep |
| GCP MCP Server | BUSINESS | Keep |
| Cloud Functions MCP Router | MIXED | Split workspace tools |
| Smart Email Agent | PERSONAL | Move to apps/personal/ |
| Workspace MCP Bridge | PERSONAL | Move to apps/personal/ |

---

## Files to Move

### To `apps/business/`

```
src/api/** → apps/business/api/
src/mcp_gateway/** → apps/business/mcp_gateway/
src/multi_agent/** → apps/business/core/multi_agent/
src/autonomous_controller.py → apps/business/core/
src/orchestrator.py → apps/business/core/
src/state_machine.py → apps/business/core/
src/backup_manager.py → apps/business/core/
src/models/** → apps/business/models/
src/railway_client.py → apps/business/integrations/
src/github_app_client.py → apps/business/integrations/
src/n8n_client.py → apps/business/integrations/
src/nightwatch/** → apps/business/nightwatch/
```

### To `apps/personal/`

```
src/agents/smart_email/** → apps/personal/agents/smart_email/
src/workspace_mcp_bridge/** → apps/personal/integrations/workspace_mcp_bridge/
```

### To `libs/shared_core/`

```
src/secrets_manager.py → libs/shared_core/secrets.py
src/logging_config.py → libs/shared_core/logging.py
```
