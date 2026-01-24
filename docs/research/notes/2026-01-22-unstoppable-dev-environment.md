# Research Note: The Unstoppable Dev Environment (Antigravity + OpenCode + OpenRouter)

**Date:** 2026-01-22
**Author:** Claude (via research-ingestion skill)
**Status:** Triaged

---

## Source

- **Type:** Technical Deep Research Report
- **URL:** N/A (direct text input)
- **Title:** The Unstoppable Dev Environment (Antigravity + OpenCode + OpenRouter) — Technical Deep Research Report (Jan 2026)
- **Creator/Author:** Unknown
- **Date Published:** 2026-01

---

## Summary

1. **What is it?** A hybrid "Hub & Spoke" architecture combining Google Antigravity (visual strategic hub) with OpenCode CLI (tactical executor) and OpenRouter (model routing layer) for resilient, cost-optimized AI development.

2. **Why is it interesting?** Achieves 10-20x cost reduction through model arbitrage (DeepSeek R1 for planning, Claude for execution) while eliminating single-provider dependencies.

3. **What problem does it solve?** Addresses vendor lock-in, rate limiting vulnerabilities, and the "weekly limit" hard stops by enabling seamless failover between cloud and local models.

---

## Relevance to Our System

_Check all that apply:_

- [x] **Model Layer** - Multi-model routing (DeepSeek R1/Claude/Gemini), cost arbitrage
- [x] **Tool Layer** - OpenCode CLI as alternative executor, Ollama local fallback
- [x] **Orchestration** - Hub & Spoke pattern, Agent Manager paradigm, parallel execution
- [ ] **Knowledge/Prompts** - AGENTS.md as shared context (we have CLAUDE.md)
- [x] **Infrastructure** - DevContainer isolation, local fallback ("Bunker Mode")
- [ ] **Evaluation** - SWE-bench references but no new evaluation methods

---

## Hypothesis

> If we implement a Hub & Spoke architecture with model routing and local fallback, then:
> - Cost per feature will decrease by 10-20x (from $3.50 to $0.20)
> - System resilience will improve (no single point of failure)
> - Developer autonomy will increase (provider-agnostic execution)

---

## Impact Estimate

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| **Scope** | System-wide | Would affect orchestration, model layer, tooling |
| **Effort** | Weeks | Requires OpenCode integration, routing logic, fallback chains |
| **Risk** | Medium | New tools (Antigravity preview), configuration complexity |
| **Reversibility** | Medium | Additive architecture, but deep integration points |

---

## Current State (Before)

_How project38-or currently works in this area._

- **Current approach:**
  - LiteLLM Gateway (ADR-010) for multi-LLM routing (Claude/GPT-4/Gemini)
  - Single executor: Claude Code
  - MCP Gateway for autonomous operations

- **Current metrics:**
  - Quality: High (Claude Sonnet as primary)
  - Latency: Variable (depends on model availability)
  - Cost: ~$3/MTok input, $15/MTok output (Sonnet)

- **Known limitations:**
  - Single executor (Claude Code)
  - No local fallback for complete offline operation
  - Rate limits can block work during high-intensity sprints

---

## Proposed Change (After)

_What would change based on this research._

- **New approach:**
  - **Hub**: Antigravity for visual planning (alternative: keep existing MCP/Claude)
  - **Spoke**: OpenCode CLI for tactical execution (additive capability)
  - **Routing**: Enhance LiteLLM with phase-aware routing (Plan→R1, Execute→Claude, Debug→Flash)
  - **Bunker Mode**: Ollama with DeepSeek distilled models for offline

- **Expected metrics:**
  - Quality: Same or better (model-specialized by task)
  - Latency: Better (parallel agents, local fallback)
  - Cost: 10-20x reduction ($0.20 vs $3.50 per feature)

- **Benefits:**
  - Zero single-point-of-failure
  - Provider-agnostic execution
  - Massive cost savings through arbitrage

- **Risks:**
  - Antigravity is in preview (unstable)
  - OpenCode integration effort
  - Configuration complexity

---

## Key Findings

### 1. Model Economics (Jan 2026)

| Phase | Model | Input $/1M | Output $/1M | Use Case |
|-------|-------|------------|-------------|----------|
| Planning | DeepSeek R1 | $0.55 | $2.19 | Deep reasoning, architecture |
| Execution | Claude 3.5 Sonnet | $3.00 | $15.00 | Precise code generation |
| Drafting | DeepSeek V3 | $0.14 | $0.28 | Bulk code generation |
| Debug | Gemini 2.0 Flash | $0.10 | $0.40 | High-speed iteration |

**Key insight:** DeepSeek R1 is 96% cheaper than OpenAI o1 for reasoning tasks.

### 2. Hub & Spoke Architecture

```
┌─────────────────────────────────────┐
│           STRATEGIC HUB             │
│    (Antigravity / Mission Control)  │
│  - Visual Agent Dashboard           │
│  - Implementation Plans             │
│  - Browser/Terminal Integration     │
└─────────────┬───────────────────────┘
              │ "Baton Pass" (file-based)
              ▼
┌─────────────────────────────────────┐
│          TACTICAL SPOKE             │
│         (OpenCode CLI)              │
│  - Provider-agnostic execution      │
│  - Permission-gated operations      │
│  - Local fallback (Ollama)          │
└─────────────────────────────────────┘
```

### 3. OpenCode Configuration Pattern

```json
{
  "model": "openrouter/anthropic/claude-3.5-sonnet",
  "small_model": "openrouter/google/gemini-2.0-flash-lite",
  "agents": {
    "plan": {
      "model": "openrouter/deepseek/deepseek-r1",
      "tools": {"edit": false, "bash": false, "read": true}
    },
    "build": {
      "model": "openrouter/anthropic/claude-3.5-sonnet",
      "tools": {"edit": true, "bash": true, "lsp": true}
    }
  }
}
```

### 4. Local Fallback ("Bunker Mode")

| Model | VRAM Required | Hardware |
|-------|---------------|----------|
| DeepSeek-R1-Distill-Llama-8B | 6-8GB | Laptop (M1/M2, RTX 3060) |
| DeepSeek-R1-Distill-Qwen-32B | 18-20GB | High-end (M2 Max, RTX 4090) |

### 5. Cost Per Feature Comparison

| Stack | Cost | Factor |
|-------|------|--------|
| Pure OpenAI (o1 + GPT-4o) | $3.50-$5.00 | 25x |
| Pure Anthropic (Opus) | $2.50 | 12x |
| Hybrid "Unstoppable" | $0.20 | 1x (baseline) |

---

## Questions to Answer

1. **OpenCode maturity?** Is `anomalyco/opencode` production-ready or experimental?
2. **Antigravity stability?** Preview product - what are the real-world failure modes?
3. **Integration effort?** How much work to add OpenCode as secondary executor?
4. **LiteLLM enhancement?** Can we add phase-aware routing to existing gateway?
5. **Ollama in Railway?** Can we run local models in Railway for "bunker mode"?

---

## Next Action

_Select ONE:_

- [ ] **Spike** - Create experiment, run isolated test
- [ ] **ADR** - Create architecture decision record
- [x] **Backlog** - Add to future work, not urgent
- [ ] **Discard** - Not relevant, archive this note

**Reason for decision:**

We already have significant coverage of this pattern:
- ✅ LiteLLM Gateway (ADR-010) provides multi-LLM routing
- ✅ MCP Gateway provides similar "Mission Control" capabilities
- ✅ Multi-agent system exists for parallel execution

The research is valuable as an **architectural reference** for future enhancement:
1. Phase-aware model routing (Plan→R1, Execute→Claude) could enhance LiteLLM
2. OpenCode CLI integration could be a future Spike
3. Ollama local fallback is worth exploring for true offline capability

**Not urgent** because current system is functional and deployed.

---

## Triage Notes

**Reviewed:** 2026-01-22
**Decision:** Backlog
**Issue/PR:** N/A (backlog)
**Experiment ID:** N/A

---

## Related

- **Related ADRs:**
  - [ADR-010: Multi-LLM Routing Strategy](../../decisions/ADR-010-multi-llm-routing-strategy.md) - Already implements LiteLLM Gateway
  - [ADR-009: Research Integration Architecture](../../decisions/ADR-009-research-integration-architecture.md) - This process

- **Related experiments:** None yet

- **Related research notes:** None

---

## Raw Text Archive

<details>
<summary>Original Research Text (click to expand)</summary>

The Unstoppable Dev Environment (Antigravity + OpenCode + OpenRouter) — Technical Deep Research Report (Jan 2026)

[Full text preserved in original submission - 11,000+ words covering:
- Introduction to Agentic Development
- Google Antigravity capabilities and constraints
- OpenCode CLI architecture and configuration
- OpenRouter economics and model routing
- Hub & Spoke integration protocol
- Implementation guide and DevContainer setup
- Cost optimization models
- Legal/ToS considerations
- Benchmarks (SWE-bench)]

</details>
