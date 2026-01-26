# Research Note: The SaaS Factory - GSD Framework for Autonomous Development

**Date:** 2026-01-25
**Author:** Claude (Research Ingestion Agent)
**Status:** Triaged

---

## Source

- **Type:** Technical Report / Framework Documentation
- **URL:** Not provided (original research document)
- **Title:** The SaaS Factory: Architecting Autonomous Software Development with Claude Code, n8n, and the GSD Framework
- **Creator/Author:** Not specified
- **Date Published:** 2026 (estimated)

---

## Summary

1. **What is it?** A comprehensive methodology combining Claude Code (agentic CLI), n8n (low-code orchestration), and GSD (Get Shit Done) framework for context engineering and state management in AI-assisted development.

2. **Why is it interesting?** Addresses two critical bottlenecks: "Code Liability" (reducing custom code via n8n) and "Context Rot" (preventing LLM memory degradation via file-based state externalization).

3. **What problem does it solve?** Enables single engineers to build SaaS applications with 25x productivity improvement by managing LLM context effectively and reducing boilerplate code.

---

## Relevance to Our System

_Check all that apply:_

- [ ] **Model Layer** - New models, prompting techniques, fine-tuning
- [ ] **Tool Layer** - New tools, integrations, capabilities
- [x] **Orchestration** - Multi-agent, workflows, state management
- [x] **Knowledge/Prompts** - Context management, RAG, memory
- [x] **Infrastructure** - Deployment, scaling, monitoring
- [ ] **Evaluation** - Testing, benchmarks, quality metrics

---

## Hypothesis

> If we adopt GSD's file-based state management (STATE.md, PLAN.md patterns), then context rot during long development sessions will decrease by 50%, and task completion accuracy will improve measurably.

---

## Impact Estimate

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| **Scope** | Module / Orchestration | Affects development workflow, not production system |
| **Effort** | Days | Adapting GSD patterns to existing CLAUDE.md structure |
| **Risk** | Low | Additive changes, doesn't break existing functionality |
| **Reversibility** | Easy | File-based, can remove patterns if not beneficial |

---

## Current State (Before)

- Current approach:
  - CLAUDE.md provides context via ADR-002 4-layer documentation
  - Skills provide workflow automation
  - No explicit session state tracking between tasks

- Current metrics:
  - Quality: Good (skills enforce consistency)
  - Latency: Variable (context loading depends on session)
  - Cost: Not tracked per-task

- Known limitations:
  - Long sessions may accumulate context garbage
  - No explicit "resume" mechanism for interrupted work
  - Task breakdown is ad-hoc, not XML-structured

---

## Proposed Change (After)

- New approach:
  - Add STATE.md for session state persistence
  - Add PLAN.md with XML-structured task definitions
  - Implement "Thin Orchestrator, Fat Agent" pattern for spawning sub-tasks

- Expected metrics:
  - Quality: Improved (structured planning enforces completeness)
  - Latency: Faster resumption (state.md allows instant context reload)
  - Cost: $3-5 per feature (claimed 25x improvement)

- Benefits:
  - Explicit state externalization prevents context rot
  - XML task schemas reduce ambiguity
  - Sub-agent spawning keeps main context clean

- Risks:
  - Overhead of maintaining additional files
  - Learning curve for XML task format
  - May conflict with existing skill patterns

---

## Key Findings from Research

### 1. The GSD File System Architecture

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `PROJECT.md` | Immutable vision, tech stack constraints | Once at start |
| `STATE.md` | Current phase, status, blockers, next steps | After every task |
| `PLAN.md` | XML-structured task definitions with verification | Per phase |
| `SUMMARY.md` | Retrospective log per completed phase | Per phase |
| `VERIFICATION.md` | UAT checklist for validation | Per phase |

### 2. Context Engineering Principles

- **Externalize state**: Write decisions to files, read before next decision
- **Atomic tasks**: Execute in fresh context, return results to orchestrator
- **Thin Orchestrator**: Main session stays lightweight, spawns specialized agents
- **Context Compaction**: Use `/compact` after phase completion

### 3. n8n-First Backend Philosophy

- "Low-Code First" principle: Prefer n8n workflow over custom code
- Shifts artifact from "imperative code" to "declarative workflows"
- Enables "Hotfix Deployment" - change logic without redeploying frontend

### 4. Token Economics

| Phase | Token Usage | Cost (Claude 3.5 Sonnet) |
|-------|-------------|--------------------------|
| Planning | ~40k input | ~$0.12 |
| Execution | ~100k input / 10k output | ~$1.50-3.00 |
| Verification | ~20k input | ~$0.06 |
| **Total per Feature** | ~150k tokens | **~$3-5** |

### 5. MCP Integration Pattern

```bash
# n8n-mcp critical environment variables
MCP_MODE=stdio
DISABLE_CONSOLE_OUTPUT=true  # Prevents JSON stream corruption
LOG_LEVEL=error
```

### 6. GSD Command Lifecycle

| Command | Agent | Action |
|---------|-------|--------|
| `/gsd:new-project` | Architect | Generate PROJECT.md, ROADMAP.md |
| `/gsd:map-codebase` | Researcher | Analyze existing code (brownfield) |
| `/gsd:discuss-phase` | Product Manager | Capture preferences in CONTEXT.md |
| `/gsd:plan-phase` | Planner | Generate XML PLAN.md with Checker loop |
| `/gsd:execute-phase` | Executor | Run tasks in waves, fresh context each |
| `/gsd:verify-work` | QA Engineer | Generate UAT, spawn Debugger if needed |

---

## Questions to Answer

1. How does GSD's STATE.md pattern compare to our existing JOURNEY.md + ADR update protocol?
2. Can we adopt XML task schemas without conflicting with our CLAUDE.md skill triggers?
3. Is the "Thin Orchestrator, Fat Agent" pattern compatible with Claude Code's Task tool?
4. What's the overhead of maintaining additional GSD files vs. the context savings?

---

## Next Action

- [x] **Spike** - Create experiment, run isolated test

**Reason for decision:** This research provides a structured context engineering methodology that directly addresses the context management challenges in AI-assisted development. Our system already uses n8n (ADR-007, ADR-008), so the n8n-first pattern aligns well. A spike would test whether GSD's state externalization improves session continuity.

---

## Triage Notes

**Reviewed:** 2026-01-25
**Decision:** Spike
**Issue/PR:** TBD (local issue to be created)
**Experiment ID:** TBD (exp_NNN_gsd_context_engineering)

---

## Related

- Related ADRs:
  - [ADR-002: Dual Documentation Strategy](../../decisions/ADR-002-dual-documentation-strategy.md) - Existing 4-layer context
  - [ADR-007: n8n Webhook Activation](../../decisions/ADR-007-n8n-webhook-activation-architecture.md) - n8n patterns
  - [ADR-008: Robust Automation Strategy](../../decisions/ADR-008-robust-automation-strategy.md) - Multi-path automation
  - [ADR-011: ADR Architect](../../decisions/ADR-011-adr-architect-structured-request-processing.md) - Structured request processing

- Related experiments: None yet

- Related research notes:
  - [2026-01-22-ai-business-os-architecture.md](2026-01-22-ai-business-os-architecture.md) - System architecture patterns

---

## Raw Research Excerpt (Key Sections)

### GSD File-Based Memory Quote

> "GSD ensures that the agent's 'memory' is effectively infinite, as it can reload the relevant state at the start of every discrete task."

### Context Rot Definition

> "As the context window approaches capacity, the model's reasoning ability degrades non-linearly. It begins to 'forget' earlier instructions, hallucinates file paths, and loses track of the overall project architecture."

### The "Thin Orchestrator" Pattern

> "The main user session is the Orchestrator. It remains lightweight. When deep work is required, it spawns specialized sub-agents."
> "Each task (or small batch of tasks) is executed in a fresh 200k token context. The Orchestrator passes only the necessary files and instructions to the Executor."

### XML Task Schema Example

```xml
<plan>
  <phase id="1.0" name="Core Infrastructure">
    <task id="1.1" type="scaffold">
      <name>Initialize React App</name>
      <description>Create a new Vite project with TypeScript.</description>
      <files>
        <file path="package.json">Add dependencies</file>
      </files>
      <verification>
        <command>npm run build</command>
        <criteria>Build completes with exit code 0</criteria>
      </verification>
    </task>
  </phase>
</plan>
```
