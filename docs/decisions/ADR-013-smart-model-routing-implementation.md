# ADR-013: Smart Model Routing Implementation

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

Potential savings with smart routing (from research):
- **Model Cascading**: 40-60% cost reduction
- **Adaptive Selection**: ~62% savings vs quality profile
- **Task-Based Routing**: 80% savings on simple tasks

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
│  - Simple (0-0.3): Haiku - formatting, summarizing, Q&A      │
│  - Medium (0.3-0.7): Sonnet - coding, analysis, features     │
│  - Complex (0.7-1.0): Opus - architecture, research, design  │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    LiteLLM GATEWAY                           │
│              (existing, at or-infra.com)                     │
│                                                              │
│  Models: claude-opus, claude-sonnet, claude-haiku,           │
│          gpt-4o, gemini-pro, gemini-flash                    │
│                                                              │
│  Fallback: haiku → sonnet → opus → gpt-4o → gemini          │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Immediate Wins (1-2 days)

**1.1 Add Haiku to LiteLLM Gateway**

Update `services/litellm-gateway/litellm-config.yaml`:

```yaml
model_list:
  - model_name: claude-haiku
    litellm_params:
      model: anthropic/claude-3-5-haiku-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
```

**1.2 Fix Factory Generator**

Change `src/factory/generator.py` to use LiteLLMClient:

```python
# Before (line 117):
client = Anthropic(api_key=api_key)

# After:
from services.telegram_bot.litellm_client import LiteLLMClient
client = LiteLLMClient()
response = await client.generate_response(messages, model="claude-sonnet")
```

**1.3 Add Smart LLM Client Module**

Create `src/smart_llm/client.py`:

```python
class SmartLLMClient:
    """LLM client with automatic model selection based on task complexity."""

    def __init__(self, base_url: str = "https://litellm-gateway-production-0339.up.railway.app"):
        self.client = AsyncOpenAI(base_url=base_url, api_key="dummy")

    async def complete(
        self,
        messages: list[dict],
        task_type: str = "general",  # simple, coding, analysis, architecture
        force_model: str | None = None
    ) -> tuple[str, dict]:
        """Complete with automatic model selection."""
        model = force_model or self._select_model(task_type)
        # ... implementation

    def _select_model(self, task_type: str) -> str:
        """Select optimal model based on task type."""
        mapping = {
            "simple": "claude-haiku",       # Q&A, formatting
            "coding": "claude-sonnet",      # Code generation
            "analysis": "claude-sonnet",    # Data analysis
            "architecture": "claude-opus",  # System design
            "research": "claude-opus",      # Research synthesis
        }
        return mapping.get(task_type, "claude-sonnet")
```

**Deliverables**:
- [ ] `services/litellm-gateway/litellm-config.yaml` - Add Haiku model
- [ ] `src/smart_llm/__init__.py` - New module
- [ ] `src/smart_llm/client.py` - SmartLLMClient
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
