# LiteLLM Gateway

**Multi-LLM Routing Proxy for project38-or**

## Overview

LiteLLM Gateway is a self-hosted proxy that provides unified access to multiple LLM providers (Anthropic, OpenAI, Google) with automatic fallback, cost tracking, and budget controls.

**Architecture Position:**
```
Telegram Bot → LiteLLM Gateway → [Claude, GPT-4, Gemini] → MCP Gateway
```

## Features

### Phase 1 (✅ Complete)
- **Multi-Provider Support**: Claude 3.7, GPT-4o, Gemini 1.5 Pro/Flash
- **Automatic Fallback**: If primary model fails, cascades to secondary/tertiary
- **Cost Control**: $10/day budget limit (configurable)
- **Unified API**: All models exposed via OpenAI Chat Completion format
- **Health Monitoring**: `/health` endpoint for Railway health checks

### Phase 2 (✅ Complete - 2026-01-20)
- **Redis Semantic Caching**: 20-40% cost reduction via response caching
- **Budget Alerts**: Webhook notifications to Telegram via n8n
- **OpenTelemetry Tracing**: Full request/response observability
- **Per-User Rate Limiting**: Quotas via master key authentication

## Configuration

### Environment Variables (Railway)

**Phase 1 - LLM Providers** (stored in GCP Secret Manager):

| Variable | Purpose | Source |
|----------|---------|--------|
| `ANTHROPIC_API_KEY` | Claude API access | GCP Secret: `ANTHROPIC-API` |
| `OPENAI_API_KEY` | GPT-4 API access | GCP Secret: `OPENAI-API` |
| `GEMINI_API_KEY` | Gemini API access | GCP Secret: `GEMINI-API` |

**Phase 2 - Production Hardening** (configured via workflow):

| Variable | Purpose | Source |
|----------|---------|--------|
| `LITELLM_MASTER_KEY` | Admin API authentication | Auto-generated |
| `DATABASE_URL` | Spend tracking database | Railway PostgreSQL plugin |
| `REDIS_HOST` | Caching backend | Railway Redis plugin |
| `REDIS_PORT` | Redis port | Railway Redis plugin |
| `REDIS_PASSWORD` | Redis authentication | Railway Redis plugin |
| `ALERT_WEBHOOK_URL` | Budget alert destination | n8n webhook |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Tracing endpoint | Optional: Langfuse/Grafana |
| `OTEL_SERVICE_NAME` | Service identifier | Default: litellm-gateway |

### Model Routing

| Model Name | Provider | Use Case | Cost (per 1M tokens) |
|------------|----------|----------|---------------------|
| `claude-sonnet` | Anthropic | Primary (balanced) | $3 input, $15 output |
| `gpt-4o` | OpenAI | Fallback, vision | $2.50 input, $10 output |
| `gemini-pro` | Google | Cheap fallback | $1.25 input, $5 output |
| `gemini-flash` | Google | Ultra-cheap | $0.075 input, $0.30 output |

**Pricing Source**: Official provider pricing pages (2026-01-17)

### Fallback Chains

```
Primary Request: claude-sonnet
  ↓ (if 429/5xx)
Fallback 1: gpt-4o
  ↓ (if 429/5xx)
Fallback 2: gemini-pro
  ↓ (if 429/5xx)
FAIL (return error to user)
```

## Deployment

### Railway Deployment

1. **Create Railway Service**:
   ```bash
   # From repository root
   railway service create litellm-gateway
   railway service link litellm-gateway
   ```

2. **Set Environment Variables** (via Railway Dashboard or CLI):
   ```bash
   railway variables set ANTHROPIC_API_KEY=<from-gcp-secret-manager>
   railway variables set OPENAI_API_KEY=<from-gcp-secret-manager>
   railway variables set GEMINI_API_KEY=<from-gcp-secret-manager>
   ```

3. **Deploy**:
   ```bash
   # Railway auto-deploys from GitHub on push
   # Or manual: railway up --service litellm-gateway
   ```

4. **Verify**:
   ```bash
   curl https://litellm-gateway-<project-id>.railway.app/health
   # Expected: {"status": "healthy"}
   ```

### Local Testing

```bash
# Install LiteLLM
pip install litellm[proxy]

# Set env vars
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-proj-...
export GEMINI_API_KEY=AIza...

# Run locally
cd services/litellm-gateway
litellm --config litellm-config.yaml --port 4000

# Test
curl http://localhost:4000/v1/models
```

## Usage

### OpenAI SDK (Python)

```python
from openai import OpenAI

# Point to LiteLLM Gateway
client = OpenAI(
    base_url="https://litellm-gateway-<project-id>.railway.app",
    api_key="dummy"  # Not required for self-hosted
)

# Use any model
response = client.chat.completions.create(
    model="claude-sonnet",  # or "gpt-4o", "gemini-pro"
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

### Direct HTTP (curl)

```bash
curl -X POST https://litellm-gateway-<project-id>.railway.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet",
    "messages": [{"role": "user", "content": "Write a tweet about AI safety"}]
  }'
```

## Monitoring

### Health Check

```bash
curl https://litellm-gateway-<project-id>.railway.app/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "models": ["claude-sonnet", "gpt-4o", "gemini-pro", "gemini-flash"]
}
```

### Cost Tracking

LiteLLM logs cost per request. Budget limit ($10/day) enforced automatically.

**View logs** (Railway Dashboard):
- Navigate to `litellm-gateway` service
- Click "Logs" tab
- Search for: `cost` or `budget`

## Security

### Best Practices

1. **API Keys**: Never hardcode. Use Railway environment variables linked to GCP Secret Manager.
2. **CORS**: Restrict `allowed_origins` in `litellm-config.yaml` to specific domains.
3. **Rate Limiting**: Use Redis-backed rate limiter (Phase 2 enabled).
4. **Audit Logs**: OpenTelemetry enabled for full observability.

## Phase 2 Setup (Production Hardening)

### Quick Setup

Run the GitHub Actions workflow with `setup-phase2` action:

```bash
gh workflow run deploy-litellm-gateway.yml -f action=setup-phase2
```

This configures:
- ✅ `LITELLM_MASTER_KEY` - Generated 64-char hex token
- ✅ `ALERT_WEBHOOK_URL` - n8n webhook for alerts
- ✅ `OTEL_SERVICE_NAME` - Tracing identification

### Manual Steps Required

After running `setup-phase2`, add these Railway plugins:

1. **Redis Plugin** (for caching):
   ```
   Railway Dashboard → delightful-cat → Add Service → Redis
   ```
   Auto-injects: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`

2. **PostgreSQL Plugin** (for spend tracking):
   ```
   Railway Dashboard → delightful-cat → Add Service → PostgreSQL
   ```
   Auto-injects: `DATABASE_URL`

3. **Deploy with new config**:
   ```bash
   gh workflow run deploy-litellm-gateway.yml -f action=deploy
   ```

### Verify Phase 2

```bash
# Check health with caching info
curl https://litellm-gateway-production-0339.up.railway.app/health

# Test admin API (requires LITELLM_MASTER_KEY)
curl -H "Authorization: Bearer <MASTER_KEY>" \
  https://litellm-gateway-production-0339.up.railway.app/key/info

# Check cache stats
curl https://litellm-gateway-production-0339.up.railway.app/cache/ping
```

### Budget Alert Configuration

Alerts are sent to n8n webhook at: `https://n8n-production-2fe0.up.railway.app/webhook/litellm-alerts`

Create n8n workflow to handle alerts:
1. Webhook Trigger node (path: `/litellm-alerts`)
2. IF node: Check `body.alert_type == "budget_alerts"`
3. Telegram node: Send formatted message

### Rate Limiting (Per-User Quotas)

Create user keys with budgets:

```bash
curl -X POST https://litellm-gateway-production-0339.up.railway.app/key/generate \
  -H "Authorization: Bearer <MASTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "max_budget": 5.0,
    "budget_duration": "1d",
    "metadata": {"user": "telegram-bot"}
  }'
```

Response includes API key for that user with enforced budget.

### Secret Rotation

When rotating API keys:
1. Update in GCP Secret Manager
2. Update Railway environment variables
3. Restart service: `railway service restart litellm-gateway`

## Phase 3: Monitoring Dashboards (2026-01-20)

### Prometheus Metrics

LiteLLM exposes Prometheus metrics at `/metrics`:

```bash
# View raw metrics
curl https://litellm-gateway-production-0339.up.railway.app/metrics
```

**Available Metric Groups:**

| Group | Metrics | Purpose |
|-------|---------|---------|
| `token_consumption` | input/output/total tokens | Track token usage by model |
| `request_tracking` | total/failed requests | Monitor request volume and errors |
| `deployment_health` | success/failure responses | Track provider reliability |
| `budget_tracking` | spend, remaining budget | Monitor costs |

### Grafana Cloud Setup (Free Tier)

1. **Create Grafana Cloud account**: https://grafana.com/auth/sign-up/create-user

2. **Deploy Grafana Alloy on Railway**:
   ```bash
   # Use the Railway template
   # https://railway.com/deploy/railway-grafana-alloy
   ```

   Configure environment variables:
   ```
   GRAFANA_CLOUD_PROMETHEUS_URL=<your-prometheus-remote-write-url>
   GRAFANA_CLOUD_PROMETHEUS_USER=<your-metrics-instance-id>
   GRAFANA_CLOUD_TOKEN=<your-access-policy-token>
   ```

3. **Import Dashboard**:
   - Go to Grafana → Dashboards → Import
   - Upload `grafana-dashboard.json` from this directory
   - Or use dashboard ID: `24055` (official LiteLLM dashboard)

### Dashboard Panels

The included `grafana-dashboard.json` provides:

| Panel | Description |
|-------|-------------|
| Request Rate | Requests per second by model |
| Failed Requests | Error count over 1 hour |
| Token Usage | Input/output tokens over time |
| Daily Spend | Cost tracking with $10 budget line |
| Success Rate | Provider reliability percentage |
| Latency | Response time per output token |
| Infrastructure Status | LiteLLM/Redis/PostgreSQL health |

### Alternative: Railway Metrics

Railway provides built-in metrics without Grafana:

```bash
# View in Railway Dashboard
# https://railway.app/project/delightful-cat
# → litellm-gateway → Metrics tab
```

Available metrics:
- CPU/Memory usage
- Network I/O
- Request count (via health checks)

## Troubleshooting

### Issue: "Model not found"

**Cause**: Invalid model name in request.
**Fix**: Use one of: `claude-sonnet`, `gpt-4o`, `gemini-pro`, `gemini-flash`

### Issue: "Budget exceeded"

**Cause**: Hit $10/day limit.
**Fix**: Increase `max_budget` in `litellm-config.yaml` or wait for daily reset.

### Issue: "All models failed"

**Cause**: All fallback models returned errors.
**Fix**: Check API keys are valid. View logs: `railway logs --service litellm-gateway`

## References

- **LiteLLM Documentation**: https://docs.litellm.ai/
- **Railway Documentation**: https://docs.railway.app/
- **Anthropic API**: https://docs.anthropic.com/
- **OpenAI API**: https://platform.openai.com/docs/
- **Google AI API**: https://ai.google.dev/

---

**Status**: ✅ Phase 3 Complete (Monitoring Dashboards)
**Last Updated**: 2026-01-20

## Changelog

### 2026-01-20 (Phase 3)
- Added Prometheus metrics endpoint (`/metrics`)
- Added prometheus_metrics_config with 4 metric groups
- Added service_callback for Redis/PostgreSQL health
- Created Grafana dashboard JSON (importable)
- Added Phase 3 documentation

### 2026-01-20 (Phase 2)
- Added Redis semantic caching configuration
- Added budget alerts via webhook
- Added OpenTelemetry observability
- Added per-user rate limiting with master key
- Created `setup-phase2` workflow action
- Updated documentation

### 2026-01-17 (Phase 1)
- Initial deployment
- Multi-provider support (Claude, GPT-4, Gemini)
- Automatic fallback chains
- Basic budget control ($10/day)
