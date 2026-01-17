# LiteLLM Gateway

**Multi-LLM Routing Proxy for project38-or**

## Overview

LiteLLM Gateway is a self-hosted proxy that provides unified access to multiple LLM providers (Anthropic, OpenAI, Google) with automatic fallback, cost tracking, and budget controls.

**Architecture Position:**
```
Telegram Bot → LiteLLM Gateway → [Claude, GPT-4, Gemini] → MCP Gateway
```

## Features

- **Multi-Provider Support**: Claude 3.7, GPT-4o, Gemini 1.5 Pro/Flash
- **Automatic Fallback**: If primary model fails, cascades to secondary/tertiary
- **Cost Control**: $10/day budget limit (configurable)
- **Unified API**: All models exposed via OpenAI Chat Completion format
- **Health Monitoring**: `/health` endpoint for Railway health checks

## Configuration

### Environment Variables (Railway)

Required secrets (stored in GCP Secret Manager):

| Variable | Purpose | Source |
|----------|---------|--------|
| `ANTHROPIC_API_KEY` | Claude API access | GCP Secret: `ANTHROPIC-API` |
| `OPENAI_API_KEY` | GPT-4 API access | GCP Secret: `OPENAI-API` |
| `GEMINI_API_KEY` | Gemini API access | GCP Secret: `GEMINI-API` |

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
3. **Rate Limiting**: Consider adding Redis-backed rate limiter (Phase 2).
4. **Audit Logs**: Enable `success_callback` for observability (Phase 2).

### Secret Rotation

When rotating API keys:
1. Update in GCP Secret Manager
2. Update Railway environment variables
3. Restart service: `railway service restart litellm-gateway`

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

**Status**: ✅ Ready for Deployment (Phase 1)
**Last Updated**: 2026-01-17
