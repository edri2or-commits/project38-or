# Workflow Consolidation Analysis

**Date:** 2026-01-25
**Source:** System Audit (AUD-002)
**Status:** 🟡 Pending Review

## Summary

| Metric | Count |
|--------|-------|
| **Total Workflows** | 129 |
| **Potential Consolidation Candidates** | ~50 |
| **Telegram-related** | 21 |
| **Railway-related** | 18 |
| **Debug/Check/Diagnose/Fix** | 27 |

## Problem Statement

129 GitHub Actions workflows creates:
- High maintenance burden (action version updates)
- Developer confusion (which workflow to use?)
- Wasted CI minutes on rarely-used workflows
- No clear organization

## Consolidation Candidates

### 1. Telegram Workflows (21 → ~5)

**Current:**
- check-telegram-service.yml
- check-telegram-webhook.yml
- configure-n8n-telegram.yml
- daily-telegram-summary.yml
- debug-telegram-config.yml
- debug-telegram.yml
- deploy-telegram-bot.yml
- diagnose-n8n-telegram.yml
- fix-telegram-bot.yml
- fix-telegram-webhook.yml
- get-telegram-bot-url.yml
- get-telegram-deploy-error.yml
- quick-deploy-telegram-bot.yml
- recreate-telegram-bot.yml
- report-telegram-url.yml
- send-telegram-message.yml
- set-telegram-webhook-fastapi.yml
- setup-telegram-chat-id.yml
- setup-telegram-n8n-webhook.yml
- test-telegram-direct.yml
- test-telegram-routes.yml

**Proposed:**
1. `telegram-deploy.yml` - All deployment actions
2. `telegram-diagnose.yml` - All health checks and debugging
3. `telegram-configure.yml` - Webhook setup, chat ID, n8n integration
4. `telegram-test.yml` - All testing
5. `telegram-send.yml` - Send messages (keep separate for quick access)

### 2. Railway Workflows (18 → ~4)

**Current:**
- check-railway-logs.yml
- check-railway-vars.yml
- configure-railway-gcs.yml
- delete-railway-spam.yml
- deploy-railway.yml
- disable-railway-pr-deploys.yml
- fetch-railway-logs.yml
- railway-autonomy.yml
- railway-config-check.yml
- railway-debug.yml
- railway-deploy-service.yml
- railway-diagnostics.yml
- railway-force-unstick.yml
- railway-inspect-service.yml
- railway-project-status.yml
- railway-status.yml
- railway-unstick-protocol.yml
- search-railway-emails.yml

**Proposed:**
1. `railway-deploy.yml` - All deployment (merge deploy-railway, railway-deploy-service)
2. `railway-status.yml` - All status checks (merge status, project-status, inspect-service)
3. `railway-diagnose.yml` - All debugging (merge debug, diagnostics, logs, config-check)
4. `railway-operations.yml` - Maintenance (merge unstick, force-unstick, spam, pr-deploys)

### 3. Debug/Check/Diagnose/Fix (27 → ~3)

**Pattern:** These are ad-hoc diagnostic workflows that should be:
1. Merged into service-specific diagnostic workflows
2. Or deleted if one-time use

**Proposed:**
1. `diagnose-services.yml` - Multi-service health check with inputs
2. `diagnose-gcp.yml` - GCP-specific diagnostics
3. `fix-common-issues.yml` - Common fixes with input selection

## Action Required

⚠️ **Before deletion, verify last run dates using:**

```bash
gh run list --workflow=<workflow-name>.yml --limit=1
```

**Criteria for deletion:**
- No runs in 30+ days
- Functionality duplicated in another workflow
- One-time debugging that's no longer relevant

## Impact Estimate

| Action | Workflows Affected | Lines Removed |
|--------|-------------------|---------------|
| Telegram consolidation | 21 → 5 | ~2,000 |
| Railway consolidation | 18 → 4 | ~1,500 |
| Debug consolidation | 27 → 3 | ~2,500 |
| **Total** | ~66 workflows | ~6,000 lines |

## Next Steps

1. [ ] Run `gh run list` for each candidate to verify usage
2. [ ] Create consolidated workflows with `workflow_dispatch` inputs
3. [ ] Migrate functionality gradually
4. [ ] Delete old workflows after 2-week deprecation period
5. [ ] Update CLAUDE.md workflow documentation
