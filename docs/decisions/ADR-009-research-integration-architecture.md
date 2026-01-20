# ADR-009: Research Integration Architecture

**Status:** ✅ Implemented (Weeks 1-4) + 🚀 Phase 5: Autonomy Enhancement
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

### Phase 4: CI Integration (Week 4) ✅ Complete

- [x] Add evaluation to CI (GitHub Action) - `.github/workflows/evaluate.yml` (2026-01-20)
- [x] Create weekly review checklist - in `docs/research/PROCESS.md` line 51-55
- [x] Run first weekly review (2026-01-20, Issue #361 created for Spike)
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

## Phase 5: Research Ingestion & Autonomy (Enhancement)

### Goal

Transform from: "User creates research note manually, runs weekly review manually"
To: "User drops research → System handles everything automatically"

### End-to-End Autonomous Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           RESEARCH INGESTION FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  USER INPUT (minimal)              INGESTION AGENT                                  │
│  ┌──────────────────┐             ┌─────────────────────────────────────────┐       │
│  │ • Link/URL       │────────────▶│ 1. Parse source (web fetch if URL)      │       │
│  │ • Title          │             │ 2. Extract key findings                 │       │
│  │ • 2-3 sentences  │             │ 3. Generate hypothesis                  │       │
│  │   (optional)     │             │ 4. Estimate impact (scope/effort/risk)  │       │
│  └──────────────────┘             │ 5. Create standardized research note    │       │
│                                    │ 6. Auto-recommend classification        │       │
│                                    └──────────────┬──────────────────────────┘       │
│                                                   │                                  │
│                                                   ▼                                  │
│                              ┌─────────────────────────────────────────┐             │
│                              │     docs/research/notes/YYYY-MM-DD-*.md │             │
│                              └──────────────┬──────────────────────────┘             │
│                                             │                                        │
├─────────────────────────────────────────────┼────────────────────────────────────────┤
│                                             ▼                                        │
│                           AUTO WEEKLY REVIEW (runs on schedule or on-demand)        │
│                              ┌─────────────────────────────────────────┐             │
│                              │ 1. Scan docs/research/notes/            │             │
│                              │ 2. Find unclassified notes              │             │
│                              │ 3. Auto-classify: Spike/ADR/Backlog/    │             │
│                              │    Discard based on Recommendation      │             │
│                              │ 4. For Spike: Create GitHub Issue       │             │
│                              │ 5. For Spike with model: Create         │             │
│                              │    experiment skeleton                  │             │
│                              │ 6. Update note with Issue/PR links      │             │
│                              └──────────────┬──────────────────────────┘             │
│                                             │                                        │
├─────────────────────────────────────────────┼────────────────────────────────────────┤
│                                             ▼                                        │
│                           AUTO EXPERIMENT (for Spikes with model changes)           │
│                              ┌─────────────────────────────────────────┐             │
│                              │ 1. Create experiments/exp_NNN_*/        │             │
│                              │ 2. Generate run.py from template        │             │
│                              │ 3. Run evaluation harness               │             │
│                              │ 4. Compare to baseline (golden set)     │             │
│                              │ 5. Apply decision rules → ADOPT/REJECT  │             │
│                              └──────────────┬──────────────────────────┘             │
│                                             │                                        │
├─────────────────────────────────────────────┼────────────────────────────────────────┤
│                                             ▼                                        │
│                           AUTO INTEGRATE (for ADOPT decisions)                      │
│                              ┌─────────────────────────────────────────┐             │
│                              │ 1. Create feature flag (0% rollout)     │             │
│                              │ 2. Create PR with changes               │             │
│                              │ 3. Post summary to GitHub Issue         │             │
│                              │ 4. Await human approval for merge       │             │
│                              └─────────────────────────────────────────┘             │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Research Ingestion Agent

#### What User Must Provide (Minimum)

| Field | Required | Example |
|-------|----------|---------|
| **Source URL or Title** | ✅ Yes | `https://youtube.com/watch?v=...` or "GPT-5 Announcement" |
| **Brief Description** | ✅ Yes | "New model claims 2x faster reasoning" |
| **Why Relevant** | ⚪ Optional | "Could replace our current Sonnet usage" |

#### What Agent Infers Automatically

| Field | How Inferred |
|-------|--------------|
| **Source Type** | URL pattern (YouTube, arXiv, blog, docs) |
| **Summary** | Web fetch + LLM summarization |
| **Key Findings** | Extract from source content |
| **Hypothesis** | Generate based on findings + system context |
| **Impact Estimate** | Analyze scope (Model/Tool/Orchestration/Infra) |
| **Effort** | Hours/Days/Weeks based on scope |
| **Risk** | Low/Medium/High based on blast radius |
| **Recommendation** | Spike/ADR/Backlog/Discard based on impact+effort |

#### Invocation

```bash
# Option 1: Claude Code prompt
"Add research: https://youtube.com/watch?v=XYZ - New prompting technique for 40% better reasoning"

# Option 2: Direct file creation (minimal)
echo "URL: https://...\nDescription: ..." > docs/research/inbox/new-research.txt

# Option 3: GitHub Issue with label 'research'
# Agent will process issues labeled 'research'
```

### Auto Weekly Review

#### Trigger Conditions

| Trigger | Frequency | Action |
|---------|-----------|--------|
| **Scheduled** | Every Monday 09:00 UTC | GitHub Action |
| **On-Demand** | Manual dispatch | GitHub Action |
| **On New Note** | When note created | Optional immediate triage |

#### Classification Rules

```python
# Automatic classification based on Recommendation field + content analysis

def auto_classify(note: ResearchNote) -> Classification:
    # 1. Check explicit Recommendation in note
    if note.recommendation:
        return note.recommendation  # Spike/ADR/Backlog/Discard

    # 2. Infer from impact estimate
    if note.impact.scope in ["Architecture", "Security"]:
        return "ADR"  # Significant scope → ADR

    if note.impact.effort == "Hours" and note.impact.risk == "Low":
        return "Backlog"  # Quick, low-risk → Backlog

    if note.impact.scope == "Model" and note.hypothesis:
        return "Spike"  # Model change with hypothesis → Spike

    # 3. Default: needs human review
    return "NEEDS_REVIEW"
```

#### Auto-Actions by Classification

| Classification | Automatic Actions | Human Approval Needed? |
|----------------|-------------------|------------------------|
| **Spike** | Create Issue, Create experiment skeleton | No (for Issue), Yes (for merge) |
| **ADR** | Create draft ADR file, Create Issue | Yes (ADR approval) |
| **Backlog** | Add to backlog Issue | No |
| **Discard** | Move to archive, Log reason | No |
| **NEEDS_REVIEW** | Create Issue with 'needs-review' label | Yes |

### Automated Decision Rules

#### For Model Changes (Spikes)

```python
# Decision matrix with specific thresholds

THRESHOLDS = {
    "quality_improvement_min": 0.05,     # 5% quality improvement needed
    "quality_regression_max": -0.02,     # Max 2% quality drop
    "latency_increase_max": 1.0,         # Max 100% latency increase
    "cost_increase_max": 0.50,           # Max 50% cost increase
    "cost_increase_quality_trade": 3.0,  # Allow 3x cost if quality >> better
}

def auto_decide(baseline: EvaluationResult, experiment: EvaluationResult) -> Decision:
    quality_delta = experiment.avg_quality - baseline.avg_quality
    latency_delta = (experiment.avg_latency - baseline.avg_latency) / baseline.avg_latency
    cost_delta = (experiment.cost - baseline.cost) / baseline.cost

    # REJECT: Quality regression
    if quality_delta < THRESHOLDS["quality_regression_max"]:
        return Decision.REJECT, f"Quality dropped {quality_delta:.1%}"

    # REJECT: Too expensive without quality improvement
    if cost_delta > THRESHOLDS["cost_increase_max"] and quality_delta < THRESHOLDS["quality_improvement_min"]:
        return Decision.REJECT, f"Cost +{cost_delta:.0%} without quality improvement"

    # ADOPT: All metrics better or same
    if quality_delta >= 0 and latency_delta <= 0 and cost_delta <= 0:
        return Decision.ADOPT, "All metrics improved or stable"

    # ADOPT: Quality significantly better, cost acceptable
    if quality_delta > THRESHOLDS["quality_improvement_min"] * 2:
        if cost_delta <= THRESHOLDS["cost_increase_quality_trade"]:
            return Decision.ADOPT, f"Quality +{quality_delta:.1%} justifies cost +{cost_delta:.0%}"

    # ADOPT: Faster and cheaper, quality stable
    if latency_delta < -0.10 and cost_delta < 0 and quality_delta >= -0.01:
        return Decision.ADOPT, "Faster and cheaper with stable quality"

    # Otherwise: Need more data
    return Decision.NEEDS_MORE_DATA, "Mixed results, expand test set"
```

#### Automatic Feature Flag Creation

```python
# When ADOPT decision is made, auto-create feature flag

def auto_create_feature_flag(experiment_id: str, decision: Decision) -> str:
    if decision != Decision.ADOPT:
        return None

    flag_name = f"exp_{experiment_id}_rollout"
    flag_config = {
        "enabled": True,
        "rollout_percentage": 0,  # Start at 0%
        "description": f"Gradual rollout for experiment {experiment_id}",
        "auto_created": True,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Add to config/feature_flags.yaml
    update_feature_flags(flag_name, flag_config)

    return flag_name
```

### What Requires Human Approval

| Action | Auto-Allowed? | Why |
|--------|---------------|-----|
| Create research note | ✅ Yes | Low risk, reversible |
| Create GitHub Issue | ✅ Yes | Low risk, can close |
| Create experiment skeleton | ✅ Yes | No production impact |
| Run evaluation (mock) | ✅ Yes | No API cost |
| Run evaluation (real) | ⚠️ Needs approval | Costs money |
| Create feature flag at 0% | ✅ Yes | No production impact |
| Increase rollout >0% | ❌ No | Production impact |
| Merge PR | ❌ No | Code change |
| Delete/archive research | ❌ No | Data loss risk |

### Implementation Status

#### Phase 5 Components

| Component | Status | Location |
|-----------|--------|----------|
| Research Ingestion Agent | 📋 Planned | `src/research/ingestion_agent.py` |
| Auto Weekly Review | 📋 Planned | `.github/workflows/auto-weekly-review.yml` |
| Auto Classification | 📋 Planned | `src/research/classifier.py` |
| Auto Experiment Creator | 📋 Planned | `src/research/experiment_creator.py` |
| Decision Engine | ✅ Exists | `src/evaluation/harness.py` (enhance) |

#### Current Capability vs Target

| Capability | Current (Manual) | Target (Autonomous) |
|------------|------------------|---------------------|
| Create research note | User creates file | Agent creates from minimal input |
| Weekly review | User runs manually | Scheduled GitHub Action |
| Classification | User decides | Auto-classify with override |
| Issue creation | User creates | Auto-create for Spikes |
| Experiment setup | User creates files | Auto-generate skeleton |
| Evaluation | User runs script | Auto-run for model Spikes |
| Decision | User interprets | Auto-decide with clear rules |
| Feature flag | User creates | Auto-create at 0% |
| Rollout | User increases % | Suggest, await approval |

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
| 2026-01-20 | First Weekly Review: Created Issue #361 for Opus Spike |
| 2026-01-20 | **ADR-009 COMPLETE** - All 4 phases implemented |
| 2026-01-20 | **Phase 5 Added**: Research Ingestion & Autonomy Enhancement |
| 2026-01-20 | Added: End-to-end autonomous flow diagram |
| 2026-01-20 | Added: Research Ingestion Agent specification |
| 2026-01-20 | Added: Auto Weekly Review design |
| 2026-01-20 | Added: Automated decision rules with thresholds |
