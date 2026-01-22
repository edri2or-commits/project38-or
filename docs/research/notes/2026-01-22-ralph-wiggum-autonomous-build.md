# Research Note: Ralph Wiggum Autonomous Build Philosophy

**Date:** 2026-01-22
**Author:** Claude (via research-ingestion skill)
**Status:** Triaged

---

## Source

- **Type:** Technical Architecture Guide
- **URL:** N/A (direct text input)
- **Title:** Implementing the Ralph Wiggum Autonomous Build Philosophy: A Comprehensive Architecture and Execution Guide
- **Creator/Author:** Unknown
- **Date Published:** 2026-01

---

## Summary

1. **What is it?** A comprehensive architecture for autonomous agentic development using iterative build-test-fix loops, treating failure as diagnostic data rather than endpoints.

2. **Why is it interesting?** We already have `src/factory/ralph_loop.py` implementing this pattern - this research validates and extends our approach with additional patterns (Bash harness, sandbox config, activity logging).

3. **What problem does it solve?** Removes human from the critical path during implementation phase, enabling "overnight builds" that iterate autonomously until objectives are met.

---

## Relevance to Our System

_Check all that apply:_

- [x] **Model Layer** - Token efficiency strategies (93% reduction with Vercel Agent Browser)
- [x] **Tool Layer** - Bash harness, browser validation tools
- [x] **Orchestration** - Recursive agent loops, state machine patterns
- [x] **Knowledge/Prompts** - Machine-readable PRD structure, plan.md/activity.md patterns
- [x] **Infrastructure** - Sandbox configuration, security boundaries
- [x] **Evaluation** - TDD enforcement, regression testing strategy

---

## Hypothesis

> If we enhance our existing `ralph_loop.py` with the patterns from this research (activity logging, Bash harness, Vercel Agent Browser validation), then:
> - Iteration success rate will improve
> - Token consumption per feature will decrease by ~50%
> - Overnight autonomous builds become feasible

---

## Impact Estimate

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| **Scope** | Module (factory/) | Enhancement to existing ralph_loop.py |
| **Effort** | Days | Patterns are well-documented, we have foundation |
| **Risk** | Low | Validates existing approach, incremental enhancement |
| **Reversibility** | Easy | Additive improvements |

---

## Current State (Before)

_We already have implementation:_

- **Current approach:**
  - `src/factory/ralph_loop.py` (306 lines) - Test→Fix→Test cycle
  - `src/factory/generator.py` (189 lines) - Claude code generation
  - `src/factory/validator.py` (307 lines) - Multi-stage validation
  - `src/harness/executor.py` (256 lines) - Subprocess execution

- **Current metrics:**
  - Lines of code: 1,058 lines across factory/harness modules
  - Test coverage: Unknown
  - Token efficiency: Not optimized with activity log rotation

- **Known limitations:**
  - No Bash harness wrapper (Python-based)
  - No activity.md log rotation for context management
  - No Vercel Agent Browser integration for validation

---

## Proposed Change (After)

_Potential enhancements based on research:_

- **Enhancement 1: Activity Log Rotation**
  - Add activity.md pattern to ralph_loop.py
  - Rotate logs when >100 lines to prevent context bloat
  - Keep tail of 20 entries for fresh context

- **Enhancement 2: Bash Harness Wrapper**
  - Create `scripts/ralph-loop.sh` as orchestrator
  - Handle SIGINT, PAUSE file, MAX_ITERATIONS
  - Call Python modules as subprocess

- **Enhancement 3: Vercel Agent Browser**
  - Replace heavy browser automation with lightweight CLI
  - 93% token reduction for validation steps
  - ~1.4k tokens/test vs ~7.8k for Playwright

- **Enhancement 4: Structured PRD Pattern**
  - Machine-readable PRD.md with verification steps
  - plan.md as mutable checklist with [x] tracking
  - ALL_TASKS_COMPLETE sentinel for exit condition

---

## Key Findings

### 1. Core Philosophy: Inverted Failure

| Traditional | Ralph Wiggum |
|-------------|--------------|
| Aim for one-shot success | Embrace iterative failure |
| Human in the loop | Machine-paced velocity |
| Context in chat history | Context in file system |
| Linear trajectory | Recursive convergence |

### 2. Architecture Components

```
┌─────────────────────────────────────────────┐
│              Bash Harness                   │
│         (ralph-loop.sh)                     │
│  - MAX_ITERATIONS guard                     │
│  - PAUSE file override                      │
│  - Log rotation                             │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│           Agent Runtime                      │
│         (Claude Code CLI)                   │
│  - Fresh context each iteration             │
│  - Reads: PROMPT.md, plan.md, activity.md   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│          Validation Layer                    │
│     (Vercel Agent Browser)                  │
│  - 93% token reduction                      │
│  - Accessibility tree output                │
└─────────────────────────────────────────────┘
```

### 3. Token Efficiency Comparison

| Tool | Tokens/Test | Use Case |
|------|-------------|----------|
| Vercel Agent Browser | ~1.4k | Rapid validation loops |
| Playwright MCP | ~7.8k | Complex UI/visual regression |
| **Reduction** | **93%** | |

### 4. Cost Model

| Metric | Value |
|--------|-------|
| Tokens per iteration | ~50k input + ~2k output |
| Cost per iteration | $0.15-$0.20 (Claude 3.5 Sonnet) |
| Iterations per feature | 1.5 (optimistic) - 3 (complex) |
| 15-feature build | ~$9.00 total |

### 5. Sandbox Configuration (settings.json)

```json
{
  "permissions": {
    "allow": ["Bash(npm *)", "Bash(npx *)", "Write(./src/**)", "Write(./tests/**)"],
    "deny": ["Bash(sudo *)", "Bash(rm -rf *)", "Read(~/.ssh/*)", "Read(.env.production)"],
    "ask": ["Bash(git push *)", "Write(./package.json)"]
  },
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true
  }
}
```

### 6. Key Patterns

| Pattern | Purpose |
|---------|---------|
| `plan.md` with `[ ]`/`[x]` | Mutable state tracking |
| `activity.md` rotation | Prevent context bloat |
| `ALL_TASKS_COMPLETE` sentinel | Structured exit condition |
| `PAUSE` file | Manual override without killing loop |
| Fresh agent per iteration | Garbage collect context |

---

## Comparison with Our Implementation

| Feature | Research | project38-or | Gap |
|---------|----------|--------------|-----|
| Test→Fix→Test loop | ✅ | ✅ `ralph_loop.py` | None |
| Multi-stage validation | ✅ | ✅ `validator.py` | None |
| Code generation | ✅ | ✅ `generator.py` | None |
| Subprocess execution | ✅ | ✅ `executor.py` | None |
| Bash harness wrapper | ✅ | ❌ | **Gap** |
| Activity log rotation | ✅ | ❌ | **Gap** |
| Vercel Agent Browser | ✅ | ❌ | **Gap** |
| PAUSE file override | ✅ | ❌ | **Gap** |

---

## Questions to Answer

1. **Vercel Agent Browser**: Is it available/stable for our use cases?
2. **Bash vs Python harness**: Benefits of adding Bash wrapper vs enhancing Python?
3. **Activity log format**: What schema for activity.md entries?
4. **Integration**: How to integrate with existing harness/scheduler modules?

---

## Next Action

_Select ONE:_

- [ ] **Spike** - Create experiment, run isolated test
- [ ] **ADR** - Create architecture decision record
- [x] **Backlog** - Add to future work, not urgent
- [ ] **Discard** - Not relevant, archive this note

**Reason for decision:**

We **already have the core implementation** in `src/factory/ralph_loop.py`. This research:
1. ✅ Validates our existing approach
2. ✅ Provides enhancement patterns (activity logging, Bash wrapper)
3. ✅ Suggests optimization (Vercel Agent Browser)

**Not urgent** because:
- Current implementation is functional
- Enhancements are incremental, not critical
- Good reference for future optimization sprint

**Consider Spike when:**
- Planning to run longer autonomous sessions
- Token costs become a concern
- Need overnight build capability

---

## Triage Notes

**Reviewed:** 2026-01-22
**Decision:** Backlog
**Issue/PR:** N/A
**Experiment ID:** N/A

---

## Related

- **Related ADRs:**
  - None directly, but validates our factory/harness architecture

- **Related code:**
  - `src/factory/ralph_loop.py` (306 lines) - Our implementation
  - `src/factory/validator.py` (307 lines) - Multi-stage validation
  - `src/factory/generator.py` (189 lines) - Code generation
  - `src/harness/executor.py` (256 lines) - Subprocess execution
  - `src/harness/scheduler.py` (388 lines) - APScheduler + locks

- **Related research notes:**
  - `2026-01-22-unstoppable-dev-environment.md` - Complementary patterns

---

## Raw Text Archive

<details>
<summary>Original Research Text (click to expand)</summary>

Implementing the Ralph Wiggum Autonomous Build Philosophy: A Comprehensive Architecture and Execution Guide

[Full text preserved in original submission - 8,000+ words covering:
- Executive Summary: Transition to Autonomous Engineering
- Paradigm Shift: Interactive Copilots to Recursive Agents
- System Architecture (Bash Harness, Agent Runtime, Validation Layer)
- Phase 1: Secure Sandbox Configuration
- Phase 2: Structured Planning (Machine-Readable PRD)
- Phase 3: Bash Loop Implementation
- Phase 4: Validation and Quality Assurance
- Phase 5: Integrated Testing Environment
- Operational Strategy: Economics and Risk]

</details>
