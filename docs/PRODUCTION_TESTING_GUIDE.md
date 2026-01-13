# Production Testing Guide

**Project**: project38-or
**Environment**: Railway Production
**URL**: https://or-infra.com
**Last Updated**: 2026-01-13

---

## Overview

This guide helps you test the deployed Agent Platform on Railway production. Since the Claude Code environment cannot access `*.up.railway.app` due to Anthropic proxy restrictions, you'll need to test from your local machine or browser.

---

## Environment Constraint: Anthropic Egress Proxy

**Issue**: Claude Code runs behind an Anthropic egress proxy that blocks `*.up.railway.app` domains.

**Error when testing from Claude Code**:
```
< HTTP/1.1 403 Forbidden
< x-deny-reason: host_not_allowed
```

**Allowed Domains** (proxy whitelist):
- ✅ `*.googleapis.com`, `*.github.com`, `*.docker.com`
- ✅ `*.npmjs.com`, `pypi.org`, `rubygems.org`
- ❌ `*.up.railway.app` **NOT allowed**

**Solution**: Test from your local machine using curl, Postman, or browser.

---

## Architecture Status

### ✅ Completed Phases (100%)

| Phase | Component | Files | Status |
|-------|-----------|-------|--------|
| 1 | Foundation + Security | WIF, secrets | ✅ Complete |
| 2 | Agent Infrastructure | Skills, workflows | ✅ Complete |
| 3.1 | Core Infrastructure | FastAPI + PostgreSQL | ✅ Complete |
| 3.2 | Agent Factory | Code generation, Ralph Loop | ✅ Complete |
| 3.3 | Agent Harness | Scheduler, executor, handoff | ✅ Complete |
| 3.4 | MCP Tools | Browser, filesystem, notifications | ✅ Complete |
| 3.5 | Observability | Metrics, monitoring | ✅ Complete |

**Total Code**: 5,341 lines across 24 source files
**Total Tests**: 9 test files covering all components
**Documentation**: 488KB across 18 files (4-layer architecture)

---

## Quick Health Check (Browser)

### 1. Test Health Endpoint

**URL**: https://or-infra.com/health

**Expected Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected",
  "timestamp": "2026-01-13T15:00:00Z"
}
```

**If database is disconnected**:
```json
{
  "status": "degraded",
  "database": "disconnected",
  ...
}
```

### 2. Test API Documentation (Swagger UI)

**URL**: https://or-infra.com/docs

**You should see**:
- Interactive API documentation (Swagger UI)
- 4 endpoint categories: health, agents, tasks, metrics
- All endpoints documented with schemas

---

## Local Testing (curl)

### 1. Health Check

```bash
# Test health endpoint
curl https://or-infra.com/health

# Expected: {"status":"healthy","version":"0.1.0",...}
```

### 2. Create Agent (Agent Factory)

```bash
# Create a simple agent from natural language
curl -X POST https://or-infra.com/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "description": "צור סוכן פשוט שמדפיס Hello World",
    "name": "Hello Agent",
    "created_by": "test-user"
  }'

# Expected response (30-60 seconds):
{
  "id": 1,
  "name": "Hello Agent",
  "description": "...",
  "code": "def main():\n    print(\"Hello World\")\n...",
  "status": "active",
  "created_at": "2026-01-13T15:00:00Z",
  "generation_cost": 0.05,
  "iterations": 1,
  "tokens_used": 1234
}
```

**What happens internally**:
1. Claude Sonnet 4.5 generates Python code from description
2. Ralph Wiggum Loop: Test → Fix → Test
3. Multi-stage validation: syntax, ruff, pydocstyle, security
4. Agent saved to PostgreSQL with status='active'

**Cost**: ~$0.015-0.06 per agent (Claude API usage)
**Time**: 30-60 seconds for first-time generation

### 3. List Agents

```bash
# Get all agents
curl https://or-infra.com/api/agents

# Expected: [{"id":1,"name":"Hello Agent",...}]
```

### 4. Get Specific Agent

```bash
# Get agent by ID
curl https://or-infra.com/api/agents/1

# Expected: {"id":1,"name":"Hello Agent","code":"..."}
```

### 5. Execute Agent

```bash
# Trigger manual execution
curl -X POST https://or-infra.com/api/agents/1/execute

# Expected: Task ID returned, execution happens async
{
  "task_id": 1,
  "status": "pending",
  "message": "Agent execution scheduled"
}
```

### 6. Check Task Status

```bash
# Get task execution history
curl https://or-infra.com/api/agents/1/tasks

# Expected: [{"id":1,"status":"completed","result":"Hello World\n",...}]
```

### 7. Metrics Endpoints

```bash
# System metrics summary
curl https://or-infra.com/metrics/summary

# Agent-specific metrics
curl https://or-infra.com/metrics/agents/1
```

---

## Production Testing Checklist

### Phase 1: Basic Connectivity ✅

- [ ] Health endpoint returns 200 OK
- [ ] Database status is "connected"
- [ ] Swagger UI loads at /docs
- [ ] ReDoc loads at /redoc

### Phase 2: Agent Creation (Phase 3.2)

- [ ] POST /api/agents creates agent successfully
- [ ] Claude API generates code (check logs)
- [ ] Ralph Loop validates code
- [ ] Agent saved to database with status='active'
- [ ] Response includes generation_cost, iterations, tokens_used

### Phase 3: Agent Execution (Phase 3.3)

- [ ] POST /api/agents/{id}/execute triggers execution
- [ ] Task record created with status='pending'
- [ ] Agent executes in isolated subprocess
- [ ] Task status changes to 'completed' or 'failed'
- [ ] Task result captured (stdout/stderr)

### Phase 4: MCP Tools (Phase 3.4)

Create agent with MCP tool usage:

```bash
curl -X POST https://or-infra.com/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "description": "צור סוכן שגולש לאתר example.com ומחלץ את הכותרת",
    "name": "Web Scraper Agent"
  }'
```

Expected behavior:
- [ ] Agent uses `browser.navigate()` tool
- [ ] Agent uses `browser.extract_text()` tool
- [ ] Rate limiting enforced (check logs)
- [ ] Usage tracking recorded

### Phase 5: Resilience & Monitoring (Phase 3.5)

- [ ] Failed agents create error logs
- [ ] Retry logic works (exponential backoff)
- [ ] Metrics endpoint returns usage stats
- [ ] Health checks detect database disconnect

---

## Common Issues & Troubleshooting

### Issue 1: Health endpoint returns 503

**Symptoms**: `{"status":"degraded","database":"disconnected"}`

**Cause**: PostgreSQL database not connected

**Solution**:
```bash
# Check Railway logs
gh run view --repo edri2or-commits/project38-or

# Or via Railway dashboard
# https://railway.app/project/95ec21cc-9ada-41c5-8485-12f9a00e0116
```

**Fix**: Ensure `DATABASE_URL` environment variable is set in Railway.

---

### Issue 2: Agent creation fails with timeout

**Symptoms**: Request takes > 60 seconds, returns 504 Gateway Timeout

**Cause**: Claude API rate limit or network issue

**Solution**:
```bash
# Check logs for "AnthropicAPIError"
# Verify ANTHROPIC-API secret in GCP Secret Manager
gh workflow run test-wif.yml --repo edri2or-commits/project38-or
```

**Fix**: Verify Claude API key is valid and not rate-limited.

---

### Issue 3: Agent execution fails

**Symptoms**: Task status='failed', error field populated

**Cause**: Agent code has runtime errors

**Solution**:
```bash
# Get task details to see error
curl https://or-infra.com/api/tasks/1

# Check error field for stack trace
{
  "id": 1,
  "status": "failed",
  "error": "ModuleNotFoundError: No module named 'xyz'"
}
```

**Fix**: Ralph Loop should catch these - may need to adjust validation.

---

### Issue 4: MCP tools fail

**Symptoms**: Agent execution fails with "Tool not registered"

**Cause**: Agent not registered in MCP tool registry

**Solution**: Check logs for `registry.register_agent()` calls.

**Fix**: Ensure agent is registered before execution:
```python
from src.mcp.registry import register_agent, get_browser

# Register agent (done automatically in harness)
register_agent(agent_id=1, allowed_tools=["browser", "filesystem"])

# Get tools
browser = await get_browser(agent_id=1)
```

---

## Expected Performance

| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| Health check latency | < 200ms | < 500ms |
| Agent creation time | 30-60s | < 90s |
| Agent execution time | < 5 minutes | < 10 minutes |
| Agent creation cost | ~$0.05 | < $0.10 |
| Database query latency | < 100ms | < 300ms |
| Uptime | 99.9% | > 99% |

---

## Next Steps After Validation

### 1. Enable Monitoring (UptimeRobot)

Set up external monitoring:
- URL: https://or-infra.com/health
- Interval: 5 minutes
- Alert on: status != 200 OR database != "connected"

### 2. Set Up Custom Domain (Optional)

```bash
# In Railway dashboard
# Settings → Domains → Add Custom Domain
# Example: api.yourdomain.com
```

### 3. Enable Preview Deployments

Configure Railway to create preview environments for PRs:
```toml
# railway.toml
[deploy]
previewEnvironments = true
```

### 4. Implement Cost Tracking

Use the `cost-optimizer` skill:
```bash
# From Claude Code
"Run cost optimizer skill to track Claude API spending"
```

### 5. Advanced CI/CD

Implement preview deployments for PRs (BOOTSTRAP_PLAN.md, line 681):
- Preview environments per PR
- Integration tests with test database
- Automated rollback on failure

---

## Production URLs

| Endpoint | URL | Purpose |
|----------|-----|---------|
| **Health** | https://or-infra.com/health | System health |
| **API Docs** | https://or-infra.com/docs | Swagger UI |
| **ReDoc** | https://or-infra.com/redoc | Alternative docs |
| **Create Agent** | POST /api/agents | Agent Factory |
| **List Agents** | GET /api/agents | All agents |
| **Execute Agent** | POST /api/agents/{id}/execute | Trigger execution |
| **Metrics** | GET /metrics/summary | System metrics |

---

## Support & Documentation

| Resource | Location |
|----------|----------|
| **BOOTSTRAP_PLAN.md** | Architecture roadmap |
| **JOURNEY.md** | Project timeline |
| **CLAUDE.md** | Agent quick reference |
| **docs/decisions/** | Architecture Decision Records |
| **docs/autonomous/** | Autonomous system theory + code |
| **docs/api/** | API reference documentation |

---

## Security Notes

1. **No Authentication**: Currently public API (add auth in production)
2. **Rate Limiting**: MCP tools have per-agent rate limits
3. **Secrets**: Fetched from GCP Secret Manager via WIF (never in code)
4. **Sandboxing**: Agents execute in isolated subprocesses
5. **CORS**: Wide open (`allow_origins=["*"]`) - restrict in production

---

*Last Updated: 2026-01-13*
*Status: Ready for Production Testing*
*Railway Project: delightful-cat (95ec21cc-9ada-41c5-8485-12f9a00e0116)*
