# MIGRATION_NOTES.md - Domain Split Migration Guide

> **Generated**: 2026-01-26
> **Purpose**: Document the monorepo restructuring into BUSINESS and PERSONAL domains

## Overview

This document captures the domain split migration, including what was moved, why, and how to complete the transition.

---

## Migration Summary

### Directory Structure Change

**Before** (monolithic):
```
src/
├── api/                  # Mixed
├── agents/              # PERSONAL
│   └── smart_email/
├── mcp_gateway/         # BUSINESS + workspace tools
├── workspace_mcp_bridge/ # PERSONAL
├── models/              # Shared → BUSINESS
└── *.py                 # Various modules
```

**After** (domain-separated):
```
apps/
├── business/            # BUSINESS domain
│   ├── api/
│   ├── core/
│   ├── integrations/
│   ├── mcp_gateway/    # Without workspace tools
│   ├── models/
│   └── main.py
├── personal/            # PERSONAL domain
│   ├── agents/
│   │   └── smart_email/
│   ├── integrations/
│   │   └── workspace_mcp_bridge/
│   └── main.py
libs/
└── shared_core/         # Domain-agnostic utilities
    ├── secrets.py
    └── logging.py
```

---

## What Was Moved

### To `apps/business/`

| Original Location | New Location | Purpose |
|-------------------|--------------|---------|
| `src/api/` | `apps/business/api/` | REST API routes |
| `src/mcp_gateway/` | `apps/business/mcp_gateway/` | MCP tools (Railway, n8n) |
| `src/multi_agent/` | `apps/business/core/multi_agent/` | Multi-agent orchestration |
| `src/orchestrator.py` | `apps/business/core/` | OODA loop |
| `src/state_machine.py` | `apps/business/core/` | Deployment state |
| `src/autonomous_controller.py` | `apps/business/core/` | Safety guardrails |
| `src/monitoring_loop.py` | `apps/business/core/` | Metrics collection |
| `src/backup_manager.py` | `apps/business/core/` | Database backups |
| `src/railway_client.py` | `apps/business/integrations/` | Railway API |
| `src/github_app_client.py` | `apps/business/integrations/` | GitHub App |
| `src/n8n_client.py` | `apps/business/integrations/` | n8n workflows |
| `src/models/` | `apps/business/models/` | Data entities |
| `src/nightwatch/` | `apps/business/nightwatch/` | Night Watch service |
| `src/workflows/` | `apps/business/workflows/` | n8n workflow definitions |

### To `apps/personal/`

| Original Location | New Location | Purpose |
|-------------------|--------------|---------|
| `src/agents/smart_email/` | `apps/personal/agents/smart_email/` | Email triage agent |
| `src/workspace_mcp_bridge/` | `apps/personal/integrations/workspace_mcp_bridge/` | Google Workspace tools |

### To `libs/shared_core/`

| Original Location | New Location | Purpose |
|-------------------|--------------|---------|
| `src/secrets_manager.py` | `libs/shared_core/secrets.py` | GCP Secret Manager |
| `src/logging_config.py` | `libs/shared_core/logging.py` | JSON logging |

---

## Configuration Changes

### Railway (BUSINESS)

**File**: `railway.toml`

```diff
- startCommand = "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
+ startCommand = "PYTHONPATH=/app uvicorn apps.business.main:app --host 0.0.0.0 --port $PORT"
```

### Railway (PERSONAL) - NEW

**File**: `railway.personal.toml`

- New Railway service for PERSONAL domain
- Daily cron at 05:00 UTC for email summary
- Separate secret scoping

### Procfile

```diff
- web: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
+ web: PYTHONPATH=/app uvicorn apps.business.main:app --host 0.0.0.0 --port $PORT
```

### Telegram Bot Dockerfile

```diff
- # Fetch src/agents for Smart Email Agent using sparse checkout
- RUN git clone --depth 1 --filter=blob:none --sparse \
-     https://github.com/edri2or-commits/project38-or.git /tmp/repo && \
-     git sparse-checkout set src/agents
+ # NOTE: REMOVED git clone of src/agents (PERSONAL domain code)
+ # The Telegram bot is a BUSINESS service and must NOT include PERSONAL code
```

### Daily Email Agent Workflow

```diff
- from src.agents.smart_email.graph import run_smart_email_agent
+ from apps.personal.agents.smart_email.graph import run_smart_email_agent
```

---

## Coupling Removed

### 1. Main API Workspace Mount

**Before**: Main API mounted workspace at `/workspace`
**After**: Workspace mount removed - lives in PERSONAL service only

### 2. Telegram Bot Smart Email

**Before**: Telegram bot cloned and imported src/agents/smart_email
**After**: Telegram bot shows message that email agent is separate service

### 3. MCP Gateway Workspace Tools

**Before**: `mcp_gateway/tools/workspace.py` in BUSINESS
**After**: Removed from BUSINESS, lives only in PERSONAL

---

## Remaining Tasks

### Mandatory Before Cutover

- [ ] Deploy PERSONAL service to Railway as separate service
- [ ] Configure PERSONAL service environment variables
- [ ] Test BUSINESS service with new entrypoint
- [ ] Test PERSONAL service independently
- [ ] Verify daily-email-agent workflow works with new paths

### Recommended Improvements

- [ ] Create separate GCP service accounts for BUSINESS/PERSONAL
- [ ] Add IAM conditions to restrict secret access by domain
- [ ] Update tests to run in both domains independently
- [ ] Add CI check for forbidden cross-domain imports

---

## Rollback Plan

If issues arise, the old `src/` directory is preserved. To rollback:

1. Update `railway.toml` to use old start command:
   ```
   startCommand = "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
   ```

2. Update `Procfile`:
   ```
   web: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
   ```

3. Revert Telegram bot Dockerfile git clone section

4. Revert daily-email-agent.yml imports

---

## Verification Checklist

Run after deployment to verify domain split:

```bash
# Check BUSINESS service
curl https://or-infra.com/api/health
# Should return: {"status": "healthy", ...}

# Verify no workspace endpoint in BUSINESS
curl https://or-infra.com/workspace/
# Should return: 404 Not Found

# Check PERSONAL service (once deployed)
curl https://personal-service.railway.app/health
# Should return: {"status": "ok", "domain": "PERSONAL"}

# Run validation script
bash docs/split/validate_split.sh
```

---

## Import Path Reference

| Old Import | New Import |
|------------|------------|
| `from src.secrets_manager import SecretManager` | `from libs.shared_core.secrets import SecretManager` |
| `from src.logging_config import setup_logging` | `from libs.shared_core.logging import setup_logging` |
| `from src.api.routes import health` | `from apps.business.api.routes import health` |
| `from src.railway_client import RailwayClient` | `from apps.business.integrations.railway_client import RailwayClient` |
| `from src.agents.smart_email.graph import run_smart_email_agent` | `from apps.personal.agents.smart_email.graph import run_smart_email_agent` |
| `from src.workspace_mcp_bridge.server import create_app` | `from apps.personal.integrations.workspace_mcp_bridge.server import create_app` |
