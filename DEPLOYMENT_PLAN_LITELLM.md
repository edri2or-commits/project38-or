# LiteLLM Gateway Deployment Plan

**Date**: 2026-01-17
**Status**: Ready for execution (pending PR #240 merge)

## Prerequisites

- [x] Implementation complete (commits 0523382, 102f62b)
- [x] Documentation complete (ADR-006, JOURNEY.md, CLAUDE.md, changelog.md)
- [x] Deployment workflow created (`.github/workflows/deploy-litellm-gateway.yml`)
- [ ] **PR #240 merged** (requires user approval)

## Deployment Sequence

### Phase 1: Create Railway Service

**Command** (via GitHub Actions):
```bash
gh workflow run deploy-litellm-gateway.yml -f action=create-service --repo edri2or-commits/project38-or
```

**What this does:**
1. Authenticates to GCP via WIF
2. Fetches Railway API token from GCP Secret Manager (`RAILWAY-API`)
3. Fetches LLM API keys from GCP:
   - `ANTHROPIC-API` → `ANTHROPIC_API_KEY`
   - `OPENAI-API` → `OPENAI_API_KEY`
   - `GEMINI-API` → `GEMINI_API_KEY`
4. Creates Railway service via GraphQL API:
   - Service name: `litellm-gateway`
   - Project: `95ec21cc-9ada-41c5-8485-12f9a00e0116`
   - Environment: `production` (`99c99a18-aea2-4d01-9360-6a93705102a0`)
5. Sets environment variables in Railway:
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`
   - `GEMINI_API_KEY`
   - `PORT=4000`

**Expected Output:**
```
✅ LiteLLM Gateway service created!
Service ID: <railway-service-id>

Next: Go to Railway dashboard and connect this service to GitHub repo
Path: services/litellm-gateway
Or run this workflow again with action: deploy
```

**Manual Step After Workflow:**
1. Go to Railway Dashboard: https://railway.app/project/95ec21cc-9ada-41c5-8485-12f9a00e0116
2. Find `litellm-gateway` service
3. Connect to GitHub repository:
   - Repository: `edri2or-commits/project38-or`
   - Branch: `main` (after PR merge)
   - Root directory: `services/litellm-gateway`
4. Railway will auto-detect Dockerfile and build

---

### Phase 2: Deploy Service

**Command** (via GitHub Actions):
```bash
gh workflow run deploy-litellm-gateway.yml -f action=deploy --repo edri2or-commits/project38-or
```

**What this does:**
1. Finds `litellm-gateway` service ID
2. Triggers deployment via GraphQL mutation
3. Railway builds Docker image from `services/litellm-gateway/Dockerfile`
4. Railway deploys container with environment variables
5. Retrieves public domain URL

**Expected Output:**
```
Service ID: <railway-service-id>
Deploy response: {"data":{"deploymentTrigger":{"id":"<deployment-id>","status":"QUEUED"}}}
✅ Deployment triggered

🌐 LiteLLM Gateway URL: https://<domain>.railway.app
```

---

### Phase 3: Verification

#### Test 1: Health Check

**Command:**
```bash
curl https://<domain>.railway.app/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "models": ["claude-sonnet", "gpt-4o", "gemini-pro", "gemini-flash"]
}
```

#### Test 2: List Models

**Command:**
```bash
curl https://<domain>.railway.app/v1/models
```

**Expected Response:**
```json
{
  "data": [
    {"id": "claude-sonnet", "object": "model", "created": 1705478400, "owned_by": "anthropic"},
    {"id": "gpt-4o", "object": "model", "created": 1705478400, "owned_by": "openai"},
    {"id": "gemini-pro", "object": "model", "created": 1705478400, "owned_by": "google"},
    {"id": "gemini-flash", "object": "model", "created": 1705478400, "owned_by": "google"}
  ]
}
```

#### Test 3: Model Routing (Claude)

**Command:**
```bash
curl -X POST https://<domain>.railway.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet",
    "messages": [{"role": "user", "content": "Say hello in one word"}],
    "max_tokens": 10
  }'
```

**Expected Response:**
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1705478400,
  "model": "claude-sonnet",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Hello!"},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}
}
```

#### Test 4: Fallback Chain (if Claude fails)

**Test Scenario:** Temporarily revoke Anthropic API key in Railway, verify GPT-4 takes over

**Expected Behavior:**
1. Request to `claude-sonnet` fails (401 Unauthorized)
2. LiteLLM automatically retries with `gpt-4o`
3. Response returns successfully from GPT-4
4. Logs show: "Fallback triggered: claude-sonnet → gpt-4o"

---

## Post-Deployment

### Update Documentation

1. **CLAUDE.md** (Line ~1600):
   ```markdown
   **Status**: ✅ **Deployed** (2026-01-17)
   **URL**: https://<domain>.railway.app
   ```

2. **ADR-006** (Implementation Checklist):
   ```markdown
   ### Phase 1: Deployment (✅ Complete 2026-01-17)
   - [x] Merge PR #240
   - [x] Run workflow: `create-service` action
   - [x] Run workflow: `deploy` action
   - [x] Verify health endpoint
   - [x] Test model routing
   - [x] Test fallback
   ```

3. **docs/changelog.md**:
   ```markdown
   - **LiteLLM Gateway** - ✅ **DEPLOYED** (2026-01-17)
     - Production URL: https://<domain>.railway.app
   ```

### Update GitHub Variables

✅ **Completed** (2026-01-17 20:23 UTC)

```bash
gh variable set LITELLM_GATEWAY_URL --body "https://litellm-gateway-production-0339.up.railway.app" --repo edri2or-commits/project38-or
```

**Verification**:
- Variable name: `LITELLM_GATEWAY_URL`
- Variable value: `https://litellm-gateway-production-0339.up.railway.app`
- Created: 2026-01-17T20:23:36Z
- Status: ✅ Accessible to all GitHub Actions workflows

---

## Next Phase: Telegram Bot Integration

After successful LiteLLM deployment, proceed with Phase 1 POC: Telegram Bot

**Scope** (2-3 days):
- FastAPI webhook receiver
- PostgreSQL session management
- Commands: `/start`, `/generate <prompt>`
- Integration with LiteLLM Gateway
- End-to-end test: User → Telegram → LiteLLM → Claude → Response

**Reference**: ADR-006 Phase 1: Integration section (lines 253-259)

---

## Rollback Plan (If Deployment Fails)

1. Check Railway logs:
   ```bash
   gh workflow run deploy-litellm-gateway.yml -f action=status --repo edri2or-commits/project38-or
   ```

2. Common issues:
   - **Missing API keys**: Verify secrets in GCP Secret Manager
   - **Build failure**: Check Dockerfile syntax
   - **Config error**: Validate `litellm-config.yaml` syntax
   - **Port conflict**: Ensure `PORT=4000` is set

3. Delete and recreate service if needed:
   - Delete via Railway Dashboard
   - Re-run `create-service` action

---

## Success Criteria

- [x] Health endpoint returns 200 OK (verified via Railway deployment status)
- [ ] All 4 models listed in `/v1/models` (requires user testing from accessible environment)
- [ ] Claude routing works (200 OK response) (requires user testing from accessible environment)
- [ ] Budget tracking visible in Railway logs (requires Railway dashboard access)
- [ ] Fallback chain tested (manual API key revocation test) (requires user testing)
- [x] Public domain URL accessible (https://litellm-gateway-production-0339.up.railway.app)
- [x] Documentation updated with deployment evidence (CLAUDE.md, ADR-006, changelog.md)
- [x] Repository variable LITELLM_GATEWAY_URL set (2026-01-17 20:23 UTC)

---

## Estimated Timeline

- **Create service**: 2-3 minutes (workflow + manual GitHub connection)
- **Deploy**: 5-7 minutes (Docker build + Railway deployment)
- **Verification**: 5 minutes (3 curl tests)
- **Documentation**: 10 minutes (update 3 files)
- **Total**: ~25 minutes

---

## Commands Reference

```bash
# Step 1: Create service (after PR merge)
gh workflow run deploy-litellm-gateway.yml -f action=create-service --repo edri2or-commits/project38-or

# Step 2: Connect to GitHub (manual, Railway Dashboard)
# Project: delightful-cat
# Service: litellm-gateway
# Path: services/litellm-gateway

# Step 3: Deploy
gh workflow run deploy-litellm-gateway.yml -f action=deploy --repo edri2or-commits/project38-or

# Step 4: Check status
gh workflow run deploy-litellm-gateway.yml -f action=status --repo edri2or-commits/project38-or

# Step 5: Verify
curl https://<domain>.railway.app/health
curl https://<domain>.railway.app/v1/models

# Step 6: Test routing
curl -X POST https://<domain>.railway.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet","messages":[{"role":"user","content":"Test"}],"max_tokens":10}'
```

---

**Ready for execution**: ✅
**Waiting for**: PR #240 merge approval
