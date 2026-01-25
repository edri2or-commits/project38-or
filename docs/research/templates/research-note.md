# Research Note: [TITLE]

**Date:** YYYY-MM-DD
**Author:** [Your name]
**Status:** Draft | Triaged | Experiment | Integrated | Archived

---

## Source

- **Type:** YouTube / Article / Paper / Tool Release / Other
- **URL:** [Full URL]
- **Title:** [Original title]
- **Creator/Author:** [Name]
- **Date Published:** YYYY-MM-DD

---

## Summary

_Write 3 sentences maximum describing the key discovery._

1. What is it?
2. Why is it interesting?
3. What problem does it solve?

---

## Relevance to Our System

_Check all that apply:_

- [ ] **Model Layer** - New models, prompting techniques, fine-tuning
- [ ] **Tool Layer** - New tools, integrations, capabilities
- [ ] **Orchestration** - Multi-agent, workflows, state management
- [ ] **Knowledge/Prompts** - Context management, RAG, memory
- [ ] **Infrastructure** - Deployment, scaling, monitoring
- [ ] **Evaluation** - Testing, benchmarks, quality metrics

---

## System Mapping (REQUIRED)

⚠️ **This section is MANDATORY before proceeding to Triage.**

_Search the codebase for existing implementations of concepts in this research._

### Concepts to Search

_List key concepts from the research that might already exist:_

| # | Concept | Search Terms |
|---|---------|--------------|
| 1 | [concept name] | `pattern1`, `pattern2` |
| 2 | [concept name] | `pattern1`, `pattern2` |
| 3 | [concept name] | `pattern1`, `pattern2` |

### Search Results

_Execute searches and document findings:_

| Concept | Search Command | Files Found | Lines |
|---------|---------------|-------------|-------|
| [concept] | `grep -r "pattern" src/` | `src/file.py` | 42-67 |
| [concept] | `grep -r "pattern" src/` | None | - |

### Overlap Analysis

_For each concept found, describe similarity:_

- **[Concept 1]**: [Describe how it relates to existing code]
- **[Concept 2]**: [Describe how it relates to existing code]

### Mapping Decision

_For each concept, decide:_

| Concept | Decision | Rationale |
|---------|----------|-----------|
| [concept] | CREATE_NEW / EXTEND_EXISTING / SKIP | [Why] |

**Overall Decision:**

- [ ] **CREATE_NEW** - No significant overlap, create new module
- [ ] **EXTEND_EXISTING** - Add to existing module: `[module path]`
- [ ] **SKIP** - Already exists, archive this note

---

## Hypothesis

_State a testable hypothesis. Format: "If we [ACTION], then [METRIC] will [CHANGE] by [AMOUNT]"_

> If we [implement X], then [metric Y] will [improve/decrease] by [Z%/amount].

---

## Impact Estimate

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| **Scope** | Local / Module / System-wide | Which components affected? |
| **Effort** | Hours / Days / Weeks | Implementation time |
| **Risk** | Low / Medium / High | What could go wrong? |
| **Reversibility** | Easy / Medium / Hard | Can we undo this? |

---

## Current State (Before)

_Describe how the system currently works in this area._

- Current approach:
- Current metrics:
  - Quality:
  - Latency:
  - Cost:
- Known limitations:

---

## Proposed Change (After)

_Describe what would change._

- New approach:
- Expected metrics:
  - Quality:
  - Latency:
  - Cost:
- Benefits:
- Risks:

---

## Questions to Answer

_List questions that need answers before proceeding._

1.
2.
3.

---

## Next Action

_Select ONE:_

- [ ] **Spike** - Create experiment, run isolated test
- [ ] **ADR** - Create architecture decision record
- [ ] **Backlog** - Add to future work, not urgent
- [ ] **Discard** - Not relevant, archive this note

**Reason for decision:**

---

## Triage Notes

_Filled during weekly review._

**Reviewed:** YYYY-MM-DD
**Decision:** Spike / ADR / Backlog / Discard
**Issue/PR:** #XXX (if applicable)
**Experiment ID:** exp_NNN (if applicable)

---

## Related

- Related ADRs:
- Related experiments:
- Related research notes:
