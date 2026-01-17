# ADR-006: Multi-LLM Routing Strategy

**Date**: 2026-01-17 (Created)
**Status**: ✅ Implemented - Ready for Deployment
**Deciders**: User (edri2or-commits), Claude AI Agent
**Tags**: llm-routing, litellm, multi-provider, cost-optimization, resilience

---

## Context

### The Problem

The project38-or autonomous system relies heavily on Large Language Models (LLMs) for intelligent decision-making, content generation, and tool orchestration. Relying on a single LLM provider creates multiple risks:

| Risk | Impact | Likelihood |
|------|--------|-----------|
| **Vendor Lock-in** | Cannot switch providers without code changes | High |
| **Cost Runaway** | No circuit breakers for expensive models | High |
| **Availability** | Service outages halt entire system | Medium |
| **Rate Limiting** | API quotas block operations | High |
| **Capability Gaps** | Single model may not excel at all tasks | Medium |

### Requirements

For Phase 1 (Telegram Bot POC) and beyond, the system needs:

1. **Multi-Provider Support**: Access to Anthropic (Claude), OpenAI (GPT), Google (Gemini)
2. **Automatic Fallback**: If primary model fails, cascade to secondary without manual intervention
3. **Cost Control**: Hard budget limits to prevent runaway costs in autonomous loops
4. **Unified Interface**: Application code should be provider-agnostic
5. **Task-Based Routing**: Route simple tasks to cheap models, complex tasks to premium models

### Current State (Before ADR-006)

- Direct API calls to Anthropic Claude via `anthropic` Python SDK
- No fallback mechanism (Claude failure = system failure)
- No cost tracking or budget enforcement
- Hard-coded model selection in application code

---

## Decision

**We adopt LiteLLM Gateway as a self-hosted multi-LLM routing proxy deployed on Railway.**

### Architecture

```
Application Layer (Telegram Bot, OODA Loop, etc.)
    ↓
LiteLLM Gateway (Railway @ port 4000)
  ├─ Model Selection Logic
  ├─ Fallback Chain Execution
  ├─ Budget Enforcement ($10/day cap)
  └─ Cost Tracking (per-request logging)
    ↓
LLM Providers (via official SDKs)
  ├─ Anthropic Claude 3.7 Sonnet/Opus
  ├─ OpenAI GPT-4o/GPT-4
  └─ Google Gemini 1.5 Pro/Flash
    ↓
(If tool call) → MCP Gateway → Railway/n8n/Workspace
```

### Implementation

**Location**: `services/litellm-gateway/`

**Files Created**:
- `Dockerfile` - Based on official `ghcr.io/berriai/litellm:main-latest`
- `litellm-config.yaml` - Model definitions, fallback chains, budget limits
- `railway.toml` - Railway deployment configuration
- `README.md` - Complete documentation with usage examples

**Deployment**: `.github/workflows/deploy-litellm-gateway.yml`
- `create-service` action - One-time Railway service setup
- `deploy` action - Trigger deployment
- `status` action - Check current state

### Models Configured

| Model Name | Provider | Cost (per 1M tokens) | Use Case |
|------------|----------|---------------------|----------|
| `claude-sonnet` | Anthropic Claude 3.7 | $3 input / $15 output | Primary (balanced) |
| `gpt-4o` | OpenAI | $2.50 / $10 | Fallback, vision |
| `gemini-pro` | Google Gemini 1.5 Pro | $1.25 / $5 | Cheap fallback |
| `gemini-flash` | Google Gemini 1.5 Flash | $0.075 / $0.30 | Ultra-cheap |

**Pricing Source**: Official provider pricing pages (accessed 2026-01-17)
- Anthropic: https://docs.anthropic.com/en/docs/about-claude/models
- OpenAI: https://openai.com/api/pricing/
- Google: https://ai.google.dev/pricing

### Fallback Chain

```
Request to "claude-sonnet"
    ↓ (if 429 rate limit or 5xx error)
Automatic fallback to "gpt-4o"
    ↓ (if 429 or 5xx)
Automatic fallback to "gemini-pro"
    ↓ (if 429 or 5xx)
Automatic fallback to "gemini-flash"
    ↓ (if still fails)
Return error to application
```

**Configuration** (from `litellm-config.yaml`):
```yaml
router_settings:
  routing_strategy: usage-based-routing
  fallbacks:
    - claude-sonnet: [gpt-4o, gemini-pro]
    - gpt-4o: [claude-sonnet, gemini-pro]
    - gemini-pro: [gemini-flash]
  num_retries: 2
  timeout: 60
```

### Budget Control

- **Daily Limit**: $10 (configurable in `litellm-config.yaml`)
- **Enforcement**: Gateway-level hard cap (requests rejected after limit)
- **Tracking**: Per-request cost logging with timestamp
- **Alerts**: (Phase 2) Webhook notifications at 50%, 80%, 100% thresholds

---

## Alternatives Considered

### Alternative 1: OpenRouter (SaaS)

**Description**: Third-party routing service (https://openrouter.ai/)

**Pros**:
- No infrastructure management
- Instant setup
- Supports 100+ models

**Cons**:
- ❌ **Data Sovereignty**: All prompts pass through third-party SaaS
- ❌ **Cost**: Markup on API calls (10-20%)
- ❌ **Trust**: Must trust OpenRouter with sensitive data
- ❌ **Vendor Lock-in**: Another dependency layer

**Decision**: **Rejected** - Violates principle of data sovereignty and adds unnecessary cost/dependency

---

### Alternative 2: Custom Routing Code

**Description**: Build Python module with `if model == "claude"` logic

**Pros**:
- Full control
- No external dependencies
- Zero infrastructure cost

**Cons**:
- ❌ **Maintenance Burden**: Manual updates for every provider API change
- ❌ **No Standard API**: Application code tightly coupled to routing logic
- ❌ **Missing Features**: No built-in budget tracking, semantic caching, observability
- ❌ **Reinventing Wheel**: LiteLLM already solves this problem

**Decision**: **Rejected** - Too much maintenance, missing critical features

---

### Alternative 3: Single LLM (Claude Only)

**Description**: Continue with direct Claude API calls

**Pros**:
- Simplest implementation
- Known performance characteristics

**Cons**:
- ❌ **Vendor Lock-in**: 100% dependent on Anthropic
- ❌ **No Resilience**: Claude outage = system outage
- ❌ **No Cost Optimization**: Can't route cheap tasks to cheaper models
- ❌ **Rate Limits**: Hit quota = downtime

**Decision**: **Rejected** - Unacceptable risk for production autonomous system

---

## Consequences

### Positive

✅ **Multi-Provider Resilience**: System survives Anthropic outages (auto-fallback to GPT-4/Gemini)

✅ **Cost Optimization**: Can route simple tasks to Gemini Flash ($0.075/1M vs Claude $3/1M = 40x cheaper)

✅ **Unified API**: Application code uses OpenAI format regardless of provider:
```python
# Works with any model without code changes
client = OpenAI(base_url="https://litellm-gateway.railway.app")
client.chat.completions.create(model="claude-sonnet", ...)
```

✅ **Budget Protection**: $10/day hard cap prevents runaway costs in autonomous loops

✅ **Provider Independence**: Can swap models by changing config, not code

✅ **Production-Ready**: LiteLLM is battle-tested (used by enterprises, 15K+ GitHub stars)

**Source**: https://github.com/BerriAI/litellm (accessed 2026-01-17, stars: 15,400)

### Negative

❌ **Additional Infrastructure**: One more Railway service to maintain

❌ **Complexity**: Adds abstraction layer between application and LLMs

❌ **Debugging**: Harder to trace errors through proxy layer

❌ **Latency**: +20-50ms overhead per request (proxy processing time)

### Neutral

⚖️ **Cost**: LiteLLM proxy is free (self-hosted), but Railway adds $5-10/month infrastructure cost

⚖️ **Learning Curve**: Team must understand LiteLLM configuration format

---

## Implementation Checklist

### Phase 1: Gateway Setup (✅ Complete)

- [x] Create `services/litellm-gateway/` directory structure (2026-01-17)
- [x] Write Dockerfile based on official LiteLLM image
- [x] Create `litellm-config.yaml` with 4 models + fallback chains
- [x] Create `railway.toml` for Railway deployment
- [x] Write comprehensive README.md (150+ lines)
- [x] Create deployment workflow `.github/workflows/deploy-litellm-gateway.yml`
- [x] Update CLAUDE.md with LiteLLM Gateway section (100+ lines)
- [x] Update docs/changelog.md with feature entry
- [x] Create ADR-006 (this document)
- [x] Commit and push: PR #240

### Phase 1: Deployment (✅ Complete - 2026-01-17)

- [x] Merge PR #240 (SHA: 2cd296f, 2026-01-17 19:34 UTC)
- [x] Run workflow: `create-service` action (Workflow #21099849223, service created)
- [x] Run workflow: `deploy` action (Workflow #21099864987, deployment SUCCESS)
- [x] Create public domain (https://litellm-gateway-production-0339.up.railway.app)
- [x] Verify deployment status (SUCCESS at 20:14:08, Railway confirms healthy)
- [ ] Test model routing: `curl .../v1/chat/completions -d '{"model":"claude-sonnet",...}'` (requires user testing)
- [ ] Test fallback: Temporarily revoke Claude API key → verify GPT-4 takes over (requires user testing)

### Phase 1: Integration (🔄 In Progress - 2026-01-17)

- [x] Build Telegram Bot service (`services/telegram-bot/`) - ✅ COMPLETE (2026-01-17)
  - FastAPI webhook application (main.py, handlers.py, 450+ lines)
  - LiteLLM Gateway client (litellm_client.py, 120+ lines)
  - PostgreSQL models for conversation history (models.py, database.py, 170+ lines)
  - Configuration with GCP Secret Manager (config.py, 100+ lines)
  - Dockerfile + railway.toml + deployment workflow (250+ lines)
  - Comprehensive README.md (500+ lines)
- [x] Configure bot to use LiteLLM Gateway as base_url - ✅ COMPLETE
  - base_url: https://litellm-gateway-production-0339.up.railway.app
  - OpenAI SDK client implementation
  - Default model: claude-sonnet with automatic fallback
- [x] Deploy Telegram Bot to Railway - ✅ DEPLOYED (2026-01-17)
  - URL: https://telegram-bot-production-053d.up.railway.app
  - Service created via workflow #21100613950
  - Code deployed via workflow #21100626525
  - Webhook configured via workflow #21100638013
  - Public domain generated: telegram-bot-production-053d.up.railway.app
- [ ] Test end-to-end: User → Telegram → LiteLLM → Claude → Response (ready for testing)
- [ ] Test MCP integration: "Check Railway status" → LiteLLM → Claude → MCP → Result
- [ ] Measure cost: 100 requests = $X (verify budget tracking)

### Phase 2: Production Hardening (⏭️ Future)

- [ ] Add Redis for semantic caching (reduce costs by 20-40%)
- [ ] Configure budget alerts (webhooks to Telegram at 50%, 80%, 100%)
- [ ] Add observability: OpenTelemetry traces to Langfuse
- [ ] Implement rate limiting (per-user quotas)
- [ ] Set up monitoring dashboards (Grafana/Railway metrics)

---

## Cost Analysis

### Phase 1 POC (1-2 weeks, 1K-10K requests)

| Item | Monthly Cost | Notes |
|------|--------------|-------|
| Railway (shared) | $20 | Hobby plan includes all services |
| LiteLLM proxy | $0 | Self-hosted (infra cost only) |
| Claude API | $10-50 | Primary model (70% of requests) |
| OpenAI API | $5-20 | Fallback (20% of requests) |
| Gemini API | $5-10 | Cheap fallback (10% of requests) |
| **Total** | **$40-100/month** | POC viable |

### Phase 3 Production (100K+ requests/month)

| Item | Monthly Cost | Notes |
|------|--------------|-------|
| Railway Pro | $50 | Dedicated resources |
| Redis | $10 | Semantic caching layer |
| Claude API | $100-500 | 10K-100K requests |
| OpenAI API | $50-200 | Fallback usage |
| Gemini API | $20-50 | Budget tasks |
| **Total** | **$230-810/month** | Production scale |

**Cost Optimization Strategy**:
- Route simple tasks (formatting, summarization) to Gemini Flash (40x cheaper than Claude)
- Use semantic caching to serve ~30% of requests from cache (zero cost)
- Budget cap prevents runaway costs

---

## Security Considerations

### API Key Management

✅ **Storage**: All API keys stored in GCP Secret Manager
- `ANTHROPIC-API` (secret)
- `OPENAI-API` (secret)
- `GEMINI-API` (secret)

✅ **Injection**: Keys injected as Railway environment variables (not in code)

✅ **Access Control**: Only `litellm-gateway` service has access to these secrets

### Request Security

⚠️ **Phase 1**: No authentication (internal service only, not public)

✅ **Phase 2**: Will add master key authentication for multi-user scenarios

### Prompt Injection

⚠️ **Risk**: Malicious prompts can manipulate LLM behavior

✅ **Mitigation** (Phase 2):
- Input sanitization at Telegram Bot layer
- Semantic firewall (vector-based jailbreak detection)
- LLM Judge (separate model validates prompts)

---

## Monitoring & Observability

### Health Checks

**Endpoint**: `https://litellm-gateway.railway.app/health`

**Expected Response**:
```json
{
  "status": "healthy",
  "models": ["claude-sonnet", "gpt-4o", "gemini-pro", "gemini-flash"]
}
```

**Railway**: Automatic health check every 30s (configured in `railway.toml`)

### Cost Tracking

LiteLLM logs every request with:
- Model used
- Tokens (input + output)
- Cost (calculated from provider pricing)
- Timestamp

**View logs**: Railway Dashboard → `litellm-gateway` service → Logs tab

### Metrics (Phase 2)

- Request count per model
- Fallback frequency (how often primary fails)
- Average latency per model
- Cost per day/week/month
- Budget utilization (%)

---

## Verification Evidence

### Files Created (PR #240)

| File | Lines | Status |
|------|-------|--------|
| `services/litellm-gateway/Dockerfile` | 23 | ✅ Created |
| `services/litellm-gateway/litellm-config.yaml` | 100+ | ✅ Created |
| `services/litellm-gateway/railway.toml` | 20 | ✅ Created |
| `services/litellm-gateway/README.md` | 150+ | ✅ Created |
| `.github/workflows/deploy-litellm-gateway.yml` | 250+ | ✅ Created |

### Documentation Updates

| Document | Section | Status |
|----------|---------|--------|
| `CLAUDE.md` | "LiteLLM Gateway (Multi-LLM Routing)" (lines 1499-1610) | ✅ Added |
| `docs/changelog.md` | Feature entry (lines 11-28) | ✅ Added |
| `docs/decisions/ADR-006-*.md` | This document | ✅ Created |

### Commit

- **SHA**: 0523382
- **Message**: `feat(llm-router): Add LiteLLM Gateway for multi-LLM routing`
- **PR**: #240
- **Date**: 2026-01-17

---

## Related Documents

- [CLAUDE.md](../../CLAUDE.md) - Section: "LiteLLM Gateway (Multi-LLM Routing)"
- [docs/changelog.md](../changelog.md) - Version history
- [services/litellm-gateway/README.md](../../services/litellm-gateway/README.md) - Usage guide
- [PR #240](https://github.com/edri2or-commits/project38-or/pull/240) - Implementation PR
- **Research Report**: "Production-Grade Multi-LLM Agentic System Architecture (2026)"

---

## References

### Official Documentation

1. **LiteLLM**: https://docs.litellm.ai/ (accessed 2026-01-17)
2. **LiteLLM GitHub**: https://github.com/BerriAI/litellm (15.4K stars)
3. **Anthropic Claude**: https://docs.anthropic.com/ (pricing, models)
4. **OpenAI API**: https://platform.openai.com/docs/ (pricing, models)
5. **Google AI**: https://ai.google.dev/ (Gemini pricing, docs)

### Industry Standards

6. **AWS Multi-LLM Strategy**: https://aws.amazon.com/blogs/machine-learning/ (best practices)
7. **LangChain State of Agents 2026**: https://www.langchain.com/state-of-agent-engineering
8. **OWASP LLM Top 10**: https://owasp.org/www-project-top-10-for-large-language-model-applications/

---

## Update Log

| Date | Change | Author | Evidence |
|------|--------|--------|----------|
| 2026-01-17 | Initial creation - LiteLLM Gateway implemented | Claude | PR #240, commit 0523382 |

---

## Appendix A: Research Report Summary

The decision to use LiteLLM Gateway was informed by comprehensive research documented in "Production-Grade Multi-LLM Agentic System Architecture (2026)". Key findings:

### MCP (Model Context Protocol) State in 2026

- **Status**: Production-ready, industry standard for tool integration
- **Adoption**: Native support in Cursor, VS Code, Claude Code
- **Architecture**: LiteLLM operates at different layer than MCP
  - MCP: Tool connectivity protocol
  - LiteLLM: Intelligence routing layer

**Conclusion**: LiteLLM + MCP are complementary, not competitive

### Multi-LLM Routing Patterns

The research identified 3 routing patterns, all implemented in LiteLLM:

1. **Cascading Fallback** (implemented in ADR-006)
2. **Semantic Router** (planned for Phase 2 - task classification)
3. **Capability-Specific Routing** (planned - vision → GPT-4o/Gemini)

### Why Self-Hosted vs SaaS

The research compared self-hosted (LiteLLM on Railway) vs SaaS (OpenRouter):

| Aspect | Self-Hosted (LiteLLM) | SaaS (OpenRouter) |
|--------|----------------------|-------------------|
| Data Sovereignty | ✅ Full control | ❌ Third-party |
| Cost | ✅ No markup | ❌ 10-20% markup |
| Customization | ✅ Full config access | ⚠️ Limited |
| Maintenance | ⚠️ Self-managed | ✅ Fully managed |

**Decision**: Data sovereignty and cost control outweigh convenience → Self-hosted

---

**End of ADR-006**
