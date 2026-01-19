# ADR-007: n8n Webhook Activation Architecture

**Date**: 2026-01-19
**Status**: ✅ Implemented and Verified
**Deciders**: User (edri2or-commits), Claude AI Agent
**Tags**: n8n, webhook, telegram, api, activation

> **Production URL**: `https://n8n-production-2fe0.up.railway.app/webhook/telegram-bot`
>
> **Evidence**: Diagnostic workflow #21130958624 - HTTP 200, executions working

---

## Context

### The Problem

After deploying n8n to Railway and creating a "Telegram Webhook Bot" workflow:
- Workflow was marked as `active: true` in the n8n API
- n8n health endpoint returned HTTP 200
- But `/webhook/telegram-bot` returned HTTP 404

**Symptoms**:
```
Telegram webhook info:
  last_error_message: "Wrong response from the webhook: 404 Not Found"
  pending_update_count: 4 (growing)
```

### Investigation Timeline

| Date | PR | Hypothesis | Result |
|------|-----|-----------|--------|
| 2026-01-18 | #292 | Simplified workflow JSON | ❌ 404 |
| 2026-01-18 | #297-298 | "active" field is read-only | ✅ Confirmed |
| 2026-01-18 | #299-300 | Need explicit activate call | Partial |
| 2026-01-19 | #304 | Missing env vars | Added vars, still 404 |
| 2026-01-19 | #305 | Toggle workflow on/off | ❌ 404 |
| 2026-01-19 | #306 | Delete + recreate | ❌ 404 |
| 2026-01-19 | #307 | Force restart service | ❌ 404 |
| 2026-01-19 | #308 | N8N_LISTEN_ADDRESS=0.0.0.0 | ❌ 404 |
| 2026-01-19 | #309 | Better debugging | Added response body |
| 2026-01-19 | #310 | **POST /activate** | ✅ **200 - FIXED** |

### Root Cause Discovery

**Critical Insight**: n8n's API has two semantically different activation methods:

**Method 1: PATCH** (Database Update Only)
```bash
PATCH /api/v1/workflows/{id}
Content-Type: application/json
X-N8N-API-KEY: $API_KEY

{"active": true}
```
- ✅ Updates `active` field in database
- ❌ Does NOT register webhook routes with internal router
- Result: Workflow appears active, but webhooks return 404

**Method 2: POST /activate** (Full Activation)
```bash
POST /api/v1/workflows/{id}/activate
X-N8N-API-KEY: $API_KEY
```
- ✅ Updates `active` field in database
- ✅ Registers webhook routes with internal HTTP router
- ✅ Loads workflow into execution engine
- Result: Webhooks return 200 and execute workflow

---

## Decision

**We use `POST /api/v1/workflows/{id}/activate` for all n8n workflow activations.**

### Implementation

**Activation Pattern**:
```bash
# Step 1: Create workflow (no active field)
WORKFLOW_ID=$(curl -s -X POST \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  "$N8N_URL/api/v1/workflows" \
  -d '{"name":"...", "nodes":[...], "connections":{}}' \
  | jq -r '.id')

# Step 2: Activate using POST (NOT PATCH)
curl -s -X POST \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "$N8N_URL/api/v1/workflows/$WORKFLOW_ID/activate"

# Step 3: Wait for webhook registration
sleep 5

# Step 4: Verify webhook is working
curl -s -X POST "$N8N_URL/webhook/your-path"
```

**Environment Variables Required**:

| Variable | Value | Purpose |
|----------|-------|---------|
| `N8N_HOST` | n8n-production-2fe0.up.railway.app | External hostname for webhooks |
| `N8N_PROTOCOL` | https | Required for external webhook URLs |
| `N8N_ENDPOINT_WEBHOOK` | webhook | Webhook URL prefix |
| `EXECUTIONS_MODE` | regular | Production execution mode |
| `N8N_LISTEN_ADDRESS` | 0.0.0.0 | Listen on all interfaces (Railway) |
| `WEBHOOK_TUNNEL_URL` | https://n8n-production-2fe0.up.railway.app/ | External webhook base URL |

---

## Consequences

### Positive

1. **Webhooks Work Reliably**: Using POST /activate guarantees webhook registration
2. **Clear API Semantics**: Documented difference between PATCH (data) and POST (action)
3. **Diagnostic Workflow**: Auto-fixes activation issues via diagnose-n8n-telegram.yml
4. **Timing Handled**: 5-second delay accounts for registration latency

### Negative

1. **Extra API Call**: Need both create and activate (not combined)
2. **Timing Dependency**: Must wait for webhook registration
3. **Not Documented**: This distinction is not clearly documented in n8n API docs

### Risks

1. **n8n Version Changes**: Future versions may change API behavior
2. **Timing Issues**: 5 seconds may not be enough under heavy load

---

## Implementation Checklist

- [x] PR #310: Use POST /activate endpoint
- [x] Updated `.github/workflows/diagnose-n8n-telegram.yml`
- [x] Updated `.github/workflows/deploy-n8n.yml`
- [x] Added required environment variables
- [x] Added 5-second wait for webhook registration
- [x] Verified via diagnostic workflow #21130958624

---

## Evidence

### Before Fix (2026-01-18)
```
PATCH /api/v1/workflows/{id} {"active": true}
→ Workflow active: true
→ GET /webhook/telegram-bot → 404 Not Found
```

### After Fix (2026-01-19)
```
POST /api/v1/workflows/{id}/activate
→ Workflow active: true
→ GET /webhook/telegram-bot → 200 OK
→ Workflow executes ✅
```

### Diagnostic Results (2026-01-19 08:48 UTC)
```
| Check | Result |
|-------|--------|
| Pending Updates | 0 |
| Last Error | none |
| Workflow Active | true |
| Recent Executions | true |
| Webhook HTTP | 200 ✅ |
```

---

## Update Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-19 | Claude | Created ADR-007 after resolving n8n webhook 404 issue |

---

## References

- n8n API Documentation: https://docs.n8n.io/api/
- Railway Container Networking: https://docs.railway.app/deploy/networking
- Issue #266: n8n deployment tracking
- PRs #292-#310: Investigation and fix history
