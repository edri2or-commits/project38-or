# ADR-018: n8n Error Scanner Agent

## Status
**ACCEPTED** (2026-01-25) → Implementation in progress

## Context

### Business Need
המערכת כוללת יכולות monitoring ו-self-healing מתקדמות, אך חסרים שלושה רכיבים:

1. **GitHub Actions Scanning** - כשלונות CI לא נסרקים אוטומטית
2. **Daily Summary** - Night Watch פועל רק 00:00-06:00 UTC
3. **Fix Verification** - אין בדיקה מחודשת אחרי תיקון

### Existing Infrastructure (Verified 2026-01-25)

| Component | Status | Evidence |
|-----------|--------|----------|
| Night Watch | ✅ Working | verify-nightwatch.yml success |
| ML Anomaly Detection | ✅ Deployed | src/ml_anomaly_detector.py (835 lines) |
| Self-Healing Actions | ✅ 8 actions | src/autonomous_controller.py (954 lines) |
| MCP Gateway | ✅ Working | production-health-check.yml success |
| n8n | ✅ Working | diagnose-n8n-telegram.yml success |

### External Research (2026-01-25)

| Source | Key Finding |
|--------|-------------|
| [n8n Error Handling](https://www.aifire.co/p/5-n8n-error-handling-techniques-for-a-resilient-automation-workflow) | Exponential backoff: 3-5 retries with 1s→2s→5s→13s delays |
| [SRE Auto-Remediation 2025](https://visualpathblogs.com/site-reliability-engineering/auto-remediation-techniques-in-sre-and-how-to-use-them-in-2025/) | Self-healing flow: Detection → Triage → Orchestration → Action |
| [AI SRE Tools](https://incident.io/blog/sre-ai-tools-transform-devops-2025) | 60-80% fewer false positives, 50-70% faster MTTR |
| [Centralized Error Management](https://n8n.io/workflows/4519-centralized-n8n-error-management-system-with-automated-email-alerts-via-gmail/) | Single workflow handles ALL errors from ALL workflows |

## Decision

### Create n8n Error Scanner Agent

Daily n8n workflow that:
1. **Scans** all error sources (GitHub Actions, Railway, Production health)
2. **Categorizes** by severity (P1-P4)
3. **Fixes** automatically where safe
4. **Verifies** fix success
5. **Reports** daily summary to Telegram

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Error Scanner Agent Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  07:00 UTC ─→ SCAN ─→ CATEGORIZE ─→ FIX ─→ VERIFY ─→ REPORT│
│     │          │          │          │        │         │   │
│  Schedule   GitHub     P1-P4      Auto     Wait 60s  Telegram│
│             Railway    Priority   Remediate  Re-check  Summary│
│             Health                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Error Sources

| Source | API Endpoint | What to Check |
|--------|--------------|---------------|
| GitHub Actions | `api.github.com/repos/.../actions/runs?status=failure` | CI failures (last 24h) |
| Railway | `or-infra.com/mcp → railway_deployments` | FAILED/CRASHED deployments |
| Production Health | `or-infra.com/api/health` | status != "healthy" |
| Monitoring | `or-infra.com/api/monitoring/status` | anomaly_count > 0 |

### Severity Classification

| Priority | Criteria | Auto-Fix? |
|----------|----------|-----------|
| P1 Critical | Production down, deploy CRASHED | ✅ Rollback |
| P2 High | CI failures, deploy FAILED | ✅ Re-run / Retry |
| P3 Medium | Anomalies, high latency | ✅ Clear cache / Restart |
| P4 Low | Warnings, info-level | ❌ Report only |

### Auto-Remediation Actions

| Error Type | Action | Via |
|------------|--------|-----|
| CI_FAILURE | Re-run workflow | GitHub API |
| DEPLOY_FAILED | Retry deployment | MCP Gateway → railway_deploy |
| DEPLOY_CRASHED | Rollback | MCP Gateway → railway_rollback |
| HEALTH_DEGRADED | Restart service | MCP Gateway → railway_deploy |
| HIGH_LATENCY | Clear cache | MCP Gateway → n8n_trigger(cache-clear) |
| HIGH_MEMORY | Trigger cleanup | MCP Gateway → n8n_trigger(memory-cleanup) |

### Fix Verification

After each remediation:
1. Wait 60 seconds
2. Re-check the same endpoint
3. Compare before/after
4. Mark result: `FIXED` | `PARTIAL` | `FAILED`

### Safety Constraints

Following `src/autonomous_controller.py` guardrails:
- **Max actions per run**: 5
- **Confidence threshold**: 0.8
- **Cooldown between same action**: 10 minutes
- **Kill switch**: Stop if 3+ rollbacks triggered

## Alternatives Considered

### 1. Extend Night Watch
**Rejected**: Night Watch runs overnight (00:00-06:00 UTC). We need a daytime scan.

### 2. Real-time scanning (continuous)
**Rejected**: Already exists via `monitoring_loop.py`. Daily scan is complementary, not replacement.

### 3. GitHub Action instead of n8n
**Rejected**: n8n provides better visualization, easier maintenance, and is already deployed.

## Consequences

### Positive
- ✅ GitHub Actions failures now auto-detected and fixed
- ✅ Daily summary provides visibility
- ✅ Fix verification ensures remediation worked
- ✅ Complements (not replaces) Night Watch

### Negative
- ⚠️ Additional n8n workflow to maintain
- ⚠️ Requires MCP Gateway token for n8n

### Risks
- Risk: Over-aggressive auto-remediation
  - Mitigation: Max 5 actions per run, confidence threshold
- Risk: n8n downtime prevents scanning
  - Mitigation: Health check alerts if n8n unreachable

## Implementation

### Phase 1: Core Workflow ✅ COMPLETE (2026-01-25)
- [x] Create `src/workflows/error_scanner_workflow.py` (480 lines)
- [x] Implement SCAN phase (GitHub, Railway, Health, Monitoring)
- [x] Implement CATEGORIZE phase (P1-P4)
- [x] Create deployment workflow

### Phase 2: Auto-Remediation ✅ COMPLETE (2026-01-25)
- [x] Implement FIX phase with MCP Gateway calls
- [x] Add safety guardrails (max 5 actions per run)
- [x] CI re-run, rollback, restart, cache clear actions

### Phase 3: Verification & Reporting ✅ COMPLETE (2026-01-25)
- [x] Implement VERIFY phase (wait 60s + re-check)
- [x] Implement REPORT phase (Telegram summary)
- [x] Cron schedule: 07:00 UTC daily

### Phase 4: Deploy to n8n ⏳ PENDING
- [ ] Run `deploy-error-scanner.yml` with action=deploy
- [ ] Verify workflow active in n8n
- [ ] Test first manual execution

### Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `src/workflows/error_scanner_workflow.py` | n8n workflow JSON builder | 480 |
| `.github/workflows/deploy-error-scanner.yml` | Deploy workflow to n8n | 165 |
| `tests/test_error_scanner_workflow.py` | Unit tests | 150 |

## References

- [ADR-003: Railway Autonomous Control](ADR-003-railway-autonomous-control.md)
- [ADR-007: n8n Webhook Activation](ADR-007-n8n-webhook-activation-architecture.md)
- [ADR-008: Robust Automation Strategy](ADR-008-robust-automation-strategy.md)
- [ADR-013: Night Watch Service](ADR-013-nightwatch-service.md) (if exists)
- External: [n8n Error Handling Techniques](https://www.aifire.co/p/5-n8n-error-handling-techniques-for-a-resilient-automation-workflow)
- External: [SRE Auto-Remediation 2025](https://visualpathblogs.com/site-reliability-engineering/auto-remediation-techniques-in-sre-and-how-to-use-them-in-2025/)

## Update Log

| Date | Update | By |
|------|--------|-----|
| 2026-01-25 | Initial proposal | Claude |
| 2026-01-25 | Phase 1-3 implementation complete, pending deploy | Claude |
