# ADR-009: Research Integration Architecture

**Status:** Implementing (Weeks 1-3 Complete)
**Date:** 2026-01-20
**Decision Makers:** User (edri2or-commits), Claude Code Agent

---

## Context

### Problem Statement

The AI landscape in 2026 evolves rapidly. The current learning method involves:
1. Watching YouTube videos and reading articles about new AI developments
2. Conducting research based on discoveries
3. Proposing changes to the system

**Risk:** Each new discovery can potentially invalidate decisions made yesterday, causing:
- Uncontrolled architectural changes
- Knowledge loss (forgetting why decisions were made)
- Regression in system quality
- "Architecture drift" from accumulated small changes

### User Quote (Hebrew)

> "תמיד יש סרטוני YouTube ומחקרים חדשים. אני מפחד שהשינויים שאני מציע למערכת גורמים לבלגן."

**Translation:** "There are always new YouTube videos and research. I'm afraid the changes I propose cause chaos in the system."

### Current State

The system has good foundations:
- ✅ ADR system for documenting decisions
- ✅ 4-layer documentation architecture
- ✅ Multi-path automation (ADR-008)

But lacks:
- ❌ Formal process for integrating new research
- ❌ Model abstraction layer (hard to swap providers)
- ❌ Evaluation harness (can't measure if changes improve or degrade)
- ❌ Feature flags for gradual rollout

---

## Decision

**Adopt a Research Integration Protocol** with 5 stages and supporting infrastructure.

### Architecture: 6-Layer System

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LAYER 6: APPLICATION                          │
│  UI / CLI / API Endpoints / Telegram Bot                            │
│  [Stable - changes rarely]                                           │
├─────────────────────────────────────────────────────────────────────┤
│                     LAYER 5: ORCHESTRATION                           │
│  AgentOrchestrator / OODA Loop / State Machine                      │
│  [Stable interfaces, configurable behavior]                          │
├─────────────────────────────────────────────────────────────────────┤
│                      LAYER 4: CAPABILITIES                           │
│  Tools / Skills / Actions (Plugin Registry)                          │
│  [Extensible - add new tools without changing core]                  │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 3: MODEL ABSTRACTION                        │
│  ModelProvider Interface + Adapters                                  │
│  [Swappable - change models without code changes]                    │
├─────────────────────────────────────────────────────────────────────┤
│                   LAYER 2: KNOWLEDGE & STATE                         │
│  Prompts / Context / Memory / Configuration                          │
│  [Versioned - track changes, rollback if needed]                     │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 1: INFRASTRUCTURE                           │
│  Secrets / Auth / Logging / Metrics / DB                            │
│  [Stable - rarely changes]                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Research Integration Protocol

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   CAPTURE    │───▶│    TRIAGE    │───▶│  EXPERIMENT  │───▶│   EVALUATE   │───▶│  INTEGRATE   │
│              │    │              │    │              │    │              │    │              │
│ - Document   │    │ - Classify   │    │ - Isolated   │    │ - Compare    │    │ - Feature    │
│   discovery  │    │   impact     │    │   test       │    │   to baseline│    │   flag       │
│ - Source URL │    │ - Prioritize │    │ - Measure    │    │ - Decision   │    │ - Gradual    │
│ - Hypothesis │    │ - Decide     │    │ - Document   │    │   ADOPT/     │    │   rollout    │
│              │    │              │    │              │    │   REJECT     │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### Stage Details

#### Stage 1: Capture
- Create research note in `docs/research/notes/YYYY-MM-DD-title.md`
- Include: source URL, summary, hypothesis, estimated impact
- Template provided in `docs/research/templates/research-note.md`

#### Stage 2: Triage
- Weekly review of new research notes
- Classify into: Spike / ADR / Backlog / Discard
- Create GitHub issue for Spikes

#### Stage 3: Experiment
- Create isolated experiment in `experiments/exp_NNN_description/`
- Define success criteria before running
- Run against golden set (baseline)
- Document results

#### Stage 4: Evaluate
- Compare experiment results to baseline
- Decision criteria:
  - Quality: Must be >= baseline (no regression)
  - Latency: Must be <= 2x baseline
  - Cost: Must be <= 1.5x baseline
- Decision: ADOPT / REJECT / NEEDS_MORE_DATA

#### Stage 5: Integrate
- Create feature flag in `config/feature_flags.yaml`
- Start with 0% rollout
- Gradual increase: 0% → 10% → 50% → 100%
- Monitor for regressions at each stage

---

## Implementation Plan

### Phase 1: Foundation (Week 1) ✅ Complete

- [x] Create `src/providers/base.py` - ModelProvider interface (PR #355, 2026-01-20)
- [x] Create `src/providers/registry.py` - Provider registry (PR #355, 2026-01-20)
- [x] Create `src/providers/claude.py` - Claude adapter (deferred - using base interface)
- [x] Create `config/feature_flags.yaml` - Feature flag config (PR #355, 2026-01-20)
- [x] Create `src/config/feature_flags.py` - Feature flag code (PR #355, 2026-01-20)

### Phase 2: Evaluation (Week 2) ✅ Complete

- [x] Create `src/evaluation/harness.py` - Evaluation runner (PR #357, 2026-01-20)
- [x] Create `src/evaluation/metrics/` - Quality, latency, cost metrics (PR #357, 2026-01-20)
- [x] Create `tests/golden/basic_queries.json` - Golden set (20 cases) (PR #357, 2026-01-20)
- [x] Create `scripts/run_evaluation.py` - CLI for evaluation (PR #357, 2026-01-20)

### Phase 3: Research Process (Week 3) ✅ Complete

- [x] Create `docs/research/PROCESS.md` - Process documentation (206 lines, 2026-01-20)
- [x] Create `docs/research/templates/` - Templates (research-note.md, 127 lines, 2026-01-20)
- [x] Create `experiments/README.md` - Experiment guidelines (208 lines, 2026-01-20)
- [ ] Run first research note through full process (optional - will happen organically)

### Phase 4: CI Integration (Week 4) 🔄 In Progress

- [x] Add evaluation to CI (GitHub Action) - `.github/workflows/evaluate.yml` (2026-01-20)
- [x] Create weekly review checklist - in `docs/research/PROCESS.md` line 51-55
- [ ] Run first weekly review (will happen on next Monday)
- [x] Update CLAUDE.md with new process (2026-01-20)

---

## Alternatives Considered

### Alternative 1: No Formal Process

**Description:** Continue current approach - integrate changes ad-hoc.

**Pros:**
- No overhead
- Fast iteration

**Cons:**
- Risk of regression
- Knowledge loss
- Architectural drift

**Verdict:** ❌ Rejected - unsustainable as system grows

### Alternative 2: Full Testing Before Every Change

**Description:** Require full test suite pass before any change.

**Pros:**
- Maximum safety

**Cons:**
- Very slow iteration
- May block beneficial changes
- Overkill for small changes

**Verdict:** ❌ Rejected - too slow, kills innovation

### Alternative 3: Feature Flags + Gradual Rollout (Chosen)

**Description:** Use feature flags to isolate changes, gradual rollout to catch regressions early.

**Pros:**
- Safe experimentation
- Easy rollback
- Measured impact

**Cons:**
- Some overhead
- Requires discipline

**Verdict:** ✅ Accepted - balanced approach

---

## Consequences

### Positive

✅ **Controlled Innovation:** New research can be integrated safely
✅ **Measurable Impact:** Know if changes improve or degrade system
✅ **Easy Rollback:** Feature flags allow instant rollback
✅ **Knowledge Preservation:** Research notes document the "why"
✅ **Reduced Regression Risk:** Evaluation harness catches regressions

### Negative

⚠️ **Overhead:** Takes more time to integrate changes
⚠️ **Discipline Required:** Must follow process consistently
⚠️ **Initial Investment:** ~1,150 lines of code to build infrastructure

### Mitigation

- Automate as much as possible (templates, CI checks)
- Weekly review keeps backlog manageable
- Feature flags make rollback easy if something goes wrong

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Research notes created | ≥1/week | Count in `docs/research/notes/` |
| Experiments run | ≥1/week | Count in `experiments/` |
| Regressions in production | 0 | CI evaluation failures |
| Integration time | <1 week | From research note to merged PR |
| Rollback events | <1/month | Feature flag disables |

---

## References

- ADR-008: Robust Automation Strategy (multi-path approach)
- ADR-002: Dual Documentation Strategy (4-layer architecture)
- CLAUDE.md: Context Architecture section

---

## Update Log

| Date | Event |
|------|-------|
| 2026-01-20 | ADR-009 Created based on user concerns about adaptability |
| 2026-01-20 | Phase 1 Complete: Model provider abstraction (PR #355) |
| 2026-01-20 | Phase 2 Complete: Evaluation harness with golden set (PR #357) |
| 2026-01-20 | Phase 3 Complete: Research process docs, templates, experiment guidelines |
| 2026-01-20 | Starting Phase 4: CI Integration |
| 2026-01-20 | Added `.github/workflows/evaluate.yml` with mock/real modes |
| 2026-01-20 | Created first research note: `2026-01-20-claude-4-opus-evaluation.md` |
| 2026-01-20 | Updated CLAUDE.md with evaluation CI workflow documentation |
