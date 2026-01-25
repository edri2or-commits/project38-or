# ADR-015: Smart Model Routing Implementation

**Date**: 2026-01-23
**Status**: 🟡 Proposed
**Deciders**: User (edri2or-commits), Claude AI Agent
**Tags**: llm-routing, cost-optimization, autonomous-agents, haiku, sonnet, opus

---

## Context

### The Problem

Despite having:
- ✅ LiteLLM Gateway deployed and operational
- ✅ Model Provider abstraction layer (`src/providers/`)
- ✅ APIs for Claude, GPT-4, Gemini in Secret Manager
- ✅ ADR-010 documenting multi-LLM strategy

**Only ~3% of the codebase actually uses LLMs** (Telegram bot only).

User feedback (2026-01-23):
> "אני מרגיש שאנחנו לא מספיק משתמשים בפרקטיקה של שימוש במודלים שונים לכל משימה וחיסכון בכסף ובטוקנים... ואני הגעתי להגבלה בעבודה עם קלוד קוד למרות שאני במנוי מאקס"

### Gap Analysis

| Component | ADR-010 Promise | Reality |
|-----------|-----------------|---------|
| **Telegram Bot** | Multi-LLM routing | ✅ Uses LiteLLM |
| **Factory Generator** | Provider abstraction | ❌ Direct Anthropic API |
| **Multi-Agent System** | "Intelligent autonomous" | ❌ Rule-based, 0 LLM calls |
| **OODA Orchestrator** | "Autonomous decisions" | ❌ Threshold-based, 0 LLM |
| **Research Classifier** | "Smart classification" | ❌ Heuristic regex |
| **Background Jobs** | N/A (not mentioned) | ❌ Don't exist |

### Cost Impact

Current state with Claude Code Max subscription:
- User hits usage limits regularly
- All tasks go to expensive models (Opus 4.5 for Claude Code)
- No delegation to cheaper models for simple tasks
- Background work doesn't happen when user is offline

### Multi-Provider Cost Analysis (2026 Pricing)

| Provider | Model | Input/1M | Output/1M | Best For | vs Sonnet |
|----------|-------|----------|-----------|----------|-----------|
| **Anthropic** | Claude Opus 4.5 | $15.00 | $75.00 | Complex reasoning | 5x more |
| **Anthropic** | Claude Sonnet 4.5 | $3.00 | $15.00 | Balanced (baseline) | 1x |
| **Anthropic** | Claude Haiku 4.5 | $1.00 | $5.00 | Simple tasks | **3x cheaper** |
| **OpenAI** | GPT-4o | $2.50 | $10.00 | Vision, general | 1.5x cheaper |
| **OpenAI** | GPT-4o-mini | $0.15 | $0.60 | Fast, cheap | **25x cheaper** |
| **Google** | Gemini Pro | $1.25 | $5.00 | Long context | 3x cheaper |
| **Google** | Gemini Flash | $0.075 | $0.30 | Ultra-cheap | **50x cheaper** |
| **DeepSeek** | V3 | $0.27 | $1.10 | Coding, math | **13x cheaper** |
| **DeepSeek** | V3.2-Exp | $0.28 | $0.42 | Latest, cheaper | **35x cheaper** |
| **DeepSeek** | R1 | $0.55 | $2.19 | Reasoning | 7x cheaper |

**Key Insight**: DeepSeek V3 is **x35 cheaper** than Claude Sonnet for output tokens and excellent for coding tasks.

**Sources**:
- [DeepSeek vs Claude Comparison](https://elephas.app/blog/deepseek-vs-claude)
- [LLM API Pricing 2026](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
- [AI Pricing Calculator](https://aipricing.org/)

Potential savings with smart routing (from research):
- **Model Cascading**: 40-60% cost reduction
- **Adaptive Selection**: ~62% savings vs quality profile
- **Task-Based Routing**: 80% savings on simple tasks
- **DeepSeek for Coding**: 90%+ savings on code generation

---

## Decision

**We implement a 4-phase Smart Model Routing system that:**

1. **Phase 1**: Fix immediate gaps (Factory Generator, add Haiku support)
2. **Phase 2**: Implement task complexity classifier
3. **Phase 3**: Add background autonomous jobs
4. **Phase 4**: Continuous optimization based on metrics

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                          │
├──────────────────────────────────────────────────────────────┤
│  Telegram Bot  │  Factory Generator  │  Background Jobs      │
│  (existing)    │  (Phase 1 fix)      │  (Phase 3 new)        │
└───────┬────────┴────────┬────────────┴────────┬──────────────┘
        │                 │                      │
        ▼                 ▼                      ▼
┌──────────────────────────────────────────────────────────────┐
│              TASK COMPLEXITY CLASSIFIER (Phase 2)             │
│                                                              │
│  Input: task description + context                           │
│  Output: complexity_score (0-1), recommended_model           │
│                                                              │
│  Rules:                                                      │
│  - Ultra-cheap: gemini-flash, deepseek-v3, gpt-4o-mini      │
│  - Budget: claude-haiku, deepseek-r1                         │
│  - Premium: claude-sonnet, gpt-4o                            │
│  - Premium+: claude-opus (architecture only)                 │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    LiteLLM GATEWAY                           │
│              (existing, at or-infra.com)                     │
│                                                              │
│  TIER 1 (Ultra-Cheap): deepseek-v3, gemini-flash, gpt-4o-mini│
│  TIER 2 (Budget): claude-haiku, deepseek-r1                  │
│  TIER 3 (Premium): claude-sonnet, gpt-4o, gemini-pro         │
│  TIER 4 (Premium+): claude-opus                              │
│                                                              │
│  Fallback: deepseek-v3 → haiku → sonnet → gpt-4o → gemini   │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Immediate Wins (1-2 days)

**1.1 Add ALL Cheap Providers to LiteLLM Gateway**

Update `services/litellm-gateway/litellm-config.yaml`:

```yaml
model_list:
  # ============================================================
  # TIER 1: Ultra-Cheap (< $1/1M output) - Use for simple tasks
  # ============================================================

  # DeepSeek V3 - x35 cheaper than Sonnet, excellent for coding
  - model_name: deepseek-v3
    litellm_params:
      model: deepseek/deepseek-chat
      api_key: os.environ/DEEPSEEK_API_KEY
      max_tokens: 8192
    model_info:
      mode: chat
      input_cost_per_token: 0.00000027
      output_cost_per_token: 0.0000011

  # Gemini Flash - x50 cheaper than Sonnet
  - model_name: gemini-flash
    litellm_params:
      model: gemini/gemini-1.5-flash-latest
      api_key: os.environ/GEMINI_API_KEY

  # GPT-4o-mini - x25 cheaper than Sonnet
  - model_name: gpt-4o-mini
    litellm_params:
      model: gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY

  # ============================================================
  # TIER 2: Budget ($1-5/1M output) - Balanced quality/cost
  # ============================================================

  # Claude Haiku - x3 cheaper than Sonnet, fast
  - model_name: claude-haiku
    litellm_params:
      model: anthropic/claude-3-5-haiku-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # DeepSeek R1 - Reasoning model, cheaper than Opus
  - model_name: deepseek-r1
    litellm_params:
      model: deepseek/deepseek-reasoner
      api_key: os.environ/DEEPSEEK_API_KEY

  # ============================================================
  # TIER 3: Premium ($5-15/1M output) - High quality
  # ============================================================

  # Claude Sonnet (existing) - Baseline
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY

  # GPT-4o (existing) - Vision support
  - model_name: gpt-4o
    litellm_params:
      model: gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  # ============================================================
  # TIER 4: Premium+ ($15+/1M output) - Complex reasoning only
  # ============================================================

  # Claude Opus - Only for architecture/research
  - model_name: claude-opus
    litellm_params:
      model: anthropic/claude-opus-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
```

**Required Secret Manager Keys**:
- `ANTHROPIC-API` ✅ (exists)
- `OPENAI-API` ✅ (exists)
- `GEMINI-API` ✅ (exists)
- `DEEPSEEK-API` ❓ (need to add)

**1.2 Update Smart Model Selection Logic**

```python
def _select_model(self, task_type: str) -> str:
    """Select optimal model based on task type and cost."""
    mapping = {
        # ULTRA-CHEAP TIER (Tier 1)
        "simple": "gemini-flash",       # Q&A, formatting ($0.30/1M)
        "translate": "gemini-flash",    # Translation
        "summarize": "gemini-flash",    # Summarization

        # BUDGET TIER (Tier 1-2)
        "coding": "deepseek-v3",        # Code generation ($1.10/1M) - best ROI!
        "math": "deepseek-v3",          # Math problems
        "data": "gpt-4o-mini",          # Data processing

        # BALANCED TIER (Tier 2)
        "analysis": "claude-haiku",     # Analysis ($5/1M)
        "review": "claude-haiku",       # Code review

        # PREMIUM TIER (Tier 3)
        "feature": "claude-sonnet",     # Feature development ($15/1M)
        "refactor": "claude-sonnet",    # Refactoring

        # PREMIUM+ TIER (Tier 4)
        "architecture": "claude-opus",  # System design ($75/1M)
        "research": "deepseek-r1",      # Research ($2.19/1M) - great for reasoning!
    }
    return mapping.get(task_type, "claude-haiku")  # Default to cheap
```

**Cost Comparison for 1M Output Tokens**:

| Task Type | Old Model | Old Cost | New Model | New Cost | Savings |
|-----------|-----------|----------|-----------|----------|---------|
| Q&A | Sonnet | $15.00 | Gemini Flash | $0.30 | **98%** |
| Coding | Sonnet | $15.00 | DeepSeek V3 | $1.10 | **93%** |
| Analysis | Sonnet | $15.00 | Haiku | $5.00 | **67%** |
| Architecture | Opus | $75.00 | Opus | $75.00 | 0% |
| Research | Opus | $75.00 | DeepSeek R1 | $2.19 | **97%** |

**Deliverables**:
- [ ] `services/litellm-gateway/litellm-config.yaml` - Add 6 new models
- [ ] Add `DEEPSEEK-API` to GCP Secret Manager
- [ ] `src/smart_llm/__init__.py` - New module
- [ ] `src/smart_llm/client.py` - SmartLLMClient with multi-tier selection
- [ ] `src/factory/generator.py` - Use SmartLLMClient
- [ ] Tests for SmartLLMClient

---

### Phase 2: Task Complexity Classifier (3-5 days)

**2.1 Create Classifier Module**

`src/smart_llm/classifier.py`:

```python
class TaskComplexityClassifier:
    """Classifies tasks to determine optimal model."""

    # Patterns for simple tasks (Haiku)
    SIMPLE_PATTERNS = [
        r"format|summarize|translate|convert",
        r"what is|explain|define",
        r"list|enumerate|count",
    ]

    # Patterns for complex tasks (Opus)
    COMPLEX_PATTERNS = [
        r"architect|design|plan",
        r"research|analyze deeply|synthesize",
        r"refactor entire|rewrite",
    ]

    def classify(self, task: str, context: str = "") -> tuple[float, str]:
        """
        Returns (complexity_score, recommended_model).

        Score:
        - 0.0-0.3: Simple → Haiku
        - 0.3-0.7: Medium → Sonnet
        - 0.7-1.0: Complex → Opus
        """
        # Rule-based + optional LLM meta-classification
```

**2.2 Integrate with SmartLLMClient**

```python
async def complete(self, messages, auto_classify: bool = True):
    if auto_classify:
        task = messages[-1]["content"]
        score, model = self.classifier.classify(task)
        logger.info(f"Auto-selected {model} (complexity={score:.2f})")
    # ...
```

**Deliverables**:
- [ ] `src/smart_llm/classifier.py` - TaskComplexityClassifier
- [ ] `src/smart_llm/patterns.py` - Pattern definitions
- [ ] Integration with SmartLLMClient
- [ ] Tests with 50+ task examples
- [ ] Metrics logging for classification accuracy

---

### Phase 3: Background Autonomous Jobs (1-2 weeks)

**3.1 Scheduled Job Framework**

Create jobs that run independently using cheap models:

| Job | Schedule | Model | Purpose |
|-----|----------|-------|---------|
| `daily_codebase_summary` | Daily 6am | Haiku | Generate codebase health report |
| `weekly_cost_analysis` | Weekly Mon | Haiku | Analyze LLM spending patterns |
| `pr_auto_review` | On PR create | Sonnet | Auto-review PRs |
| `dependency_check` | Weekly | Haiku | Check for vulnerabilities |
| `research_digest` | Daily | Haiku | Summarize new research notes |

**3.2 Implementation**

`src/smart_llm/jobs/`:
```
jobs/
├── __init__.py
├── base.py           # BaseJob class
├── codebase_summary.py
├── cost_analysis.py
├── pr_review.py
└── scheduler.py      # APScheduler integration
```

**3.3 Railway Deployment**

Add worker process to `Procfile`:
```
web: uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: python -m src.smart_llm.jobs.scheduler
```

**Deliverables**:
- [ ] Job framework (`src/smart_llm/jobs/`)
- [ ] 5 initial jobs implemented
- [ ] APScheduler integration
- [ ] Railway worker deployment
- [ ] Monitoring dashboard for job status

---

### Phase 4: Continuous Optimization (Ongoing)

**4.1 Metrics Collection**

Track per-model:
- Requests count
- Average latency
- Cost
- Quality score (user feedback or auto-eval)

**4.2 Adaptive Routing**

Use historical data to improve classification:
```python
# After 1000+ requests, use ML-based classifier
if self.has_enough_data():
    return self.ml_classifier.predict(task)
else:
    return self.rule_based_classify(task)
```

**4.3 Cost Reports**

Weekly Telegram report:
```
📊 Weekly LLM Costs (Jan 17-23)

Model Usage:
- Haiku: 450 requests ($2.25)
- Sonnet: 120 requests ($5.40)
- Opus: 15 requests ($1.50)

Total: $9.15 (vs $45.60 if all Opus)
Savings: 80%

Top expensive tasks:
1. Architecture design (Opus, $0.45)
2. PR review (Sonnet, $0.30)
```

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| LLM cost per month | ~$100 | ~$40 | LiteLLM metrics |
| Claude Code limit hits | Weekly | Never | User feedback |
| Background jobs running | 0 | 5+ daily | Job scheduler logs |
| Tasks using Haiku | 0% | 40% | LiteLLM routing logs |
| Tasks using smart routing | 3% | 80% | Codebase analysis |

---

## Alternatives Considered

### Alternative 1: Use claude-router (Open Source)

**Description**: Integrate [0xrdan/claude-router](https://github.com/0xrdan/claude-router)

**Pros**:
- Ready-made solution
- Proven 80% cost savings

**Cons**:
- External dependency
- May not fit our LiteLLM Gateway architecture
- Less control over routing logic

**Decision**: **Partially adopt** - Study their classification patterns, implement our own

### Alternative 2: Keep Everything on Sonnet

**Description**: Just use Sonnet for everything, accept current costs

**Pros**:
- No development effort
- Consistent quality

**Cons**:
- Wastes money on simple tasks
- Doesn't solve Claude Code limits
- No background automation

**Decision**: **Rejected** - User explicitly wants cost optimization

### Alternative 3: Full Migration to Gemini

**Description**: Move all tasks to Gemini Flash (40x cheaper than Claude)

**Pros**:
- Dramatic cost reduction
- Fast response times

**Cons**:
- Lower quality for complex tasks
- Different API format
- Loss of Claude's strengths

**Decision**: **Rejected** - Use Gemini for simple tasks only, keep Claude for quality

---

## Consequences

### Positive

✅ **Cost Reduction**: 40-80% savings based on task routing

✅ **No More Limits**: Background jobs run with cheap models, not Claude Code

✅ **Actually Using Infrastructure**: LiteLLM Gateway utilized beyond Telegram

✅ **Autonomous Operation**: Work continues when user is offline

✅ **Quality Where Needed**: Opus for architecture, Haiku for simple tasks

### Negative

❌ **Complexity**: More code to maintain

❌ **Classification Errors**: May route complex tasks to Haiku (quality loss)

❌ **Debugging**: Harder to trace which model answered

### Mitigations

| Risk | Mitigation |
|------|------------|
| Classification errors | Allow `force_model` override, log all routing decisions |
| Quality degradation | A/B testing, user feedback mechanism |
| Increased complexity | Clear module boundaries, comprehensive tests |

---

## Implementation Checklist

### Phase 1: Immediate Wins

- [ ] Add `claude-haiku` to LiteLLM Gateway config
- [ ] Create `src/smart_llm/` module
- [ ] Implement SmartLLMClient
- [ ] Fix Factory Generator to use SmartLLMClient
- [ ] Add tests
- [ ] Deploy updated LiteLLM Gateway
- [ ] Update CLAUDE.md

### Phase 2: Classifier

- [ ] Implement TaskComplexityClassifier
- [ ] Create pattern library
- [ ] Integrate with SmartLLMClient
- [ ] Test with 50+ examples
- [ ] Add metrics logging

### Phase 3: Background Jobs

- [ ] Create job framework
- [ ] Implement 5 initial jobs
- [ ] Add APScheduler
- [ ] Deploy worker to Railway
- [ ] Add monitoring

### Phase 4: Optimization

- [ ] Implement metrics collection
- [ ] Create cost reports
- [ ] Add adaptive routing (ML-based)
- [ ] Weekly optimization reviews

---

## Related Documents

- [ADR-010: Multi-LLM Routing Strategy](ADR-010-multi-llm-routing-strategy.md)
- [ADR-009: Research Integration Architecture](ADR-009-research-integration-architecture.md)
- `src/providers/base.py` - Existing provider abstraction
- `services/litellm-gateway/README.md` - LiteLLM Gateway docs

---

## References

- [claude-router](https://github.com/0xrdan/claude-router) - Open source model routing
- [Model Cascading Pattern](https://caylent.com/blog/claude-haiku-4-5-deep-dive-cost-capabilities-and-the-multi-agent-opportunity)
- [Anthropic API Pricing 2026](https://www.metacto.com/blogs/anthropic-api-pricing-a-full-breakdown-of-costs-and-integration)

---

## Update Log

| Date | Change | Author | Evidence |
|------|--------|--------|----------|
| 2026-01-23 | Initial creation | Claude | ADR-architect process |

---

**End of ADR-013**
