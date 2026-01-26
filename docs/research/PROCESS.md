# Research Integration Process

## Overview

This directory contains research notes, experiment designs, and integration decisions.
The process ensures that new AI discoveries are integrated safely and measurably.

**Architecture Decision:** [ADR-009](../decisions/ADR-009-research-integration-architecture.md)

## The 6-Stage Process

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   CAPTURE    │───▶│   SYSTEM     │───▶│    TRIAGE    │───▶│  EXPERIMENT  │───▶│   EVALUATE   │───▶│  INTEGRATE   │
│              │    │   MAPPING    │    │              │    │              │    │              │    │              │
│  Document    │    │  Search for  │    │  Classify    │    │  Isolated    │    │  Compare to  │    │  Feature     │
│  discovery   │    │  existing    │    │  impact      │    │  test        │    │  baseline    │    │  flag        │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

## Stage 1: Capture

When you discover something new (YouTube video, article, tool release), create a research note.

### Create Research Note

```bash
# Create from template
cp docs/research/templates/research-note.md docs/research/notes/$(date +%Y-%m-%d)-title.md
```

### Fill In Template

- **Source**: Full URL or citation
- **Summary**: 3 sentences max
- **Hypothesis**: "If we do X, then Y will improve by Z"
- **Impact Estimate**: Scope, effort, risk

## Stage 1.5: System Mapping (CRITICAL)

⚠️ **This stage is MANDATORY before Triage. Skip this and you risk creating duplicate code.**

### Purpose

Prevent duplicate implementations by verifying concepts don't already exist in the codebase.

### Why This Exists

Added 2026-01-25 after the WAT Framework incident:
- Research proposed: ToolRegistry, AgentDomain, AgentCapability, Self-Healing
- All already existed in: `src/mcp/registry.py`, `src/multi_agent/base.py`, `src/autonomous_controller.py`
- Result: 1,800 lines of duplicate code created, then reverted (PR #609 → PR #610)
- Root cause: No system mapping was performed

### Required Steps

1. **Extract Concepts** - List key concepts from the research
2. **Search Codebase** - `grep -r "pattern" src/` for each concept
3. **Map to Existing** - Document which files contain related code
4. **Decide** - CREATE_NEW / EXTEND_EXISTING / SKIP

### Search Examples

```bash
# For a "Tool Registry" concept:
grep -r "ToolRegistry\|tool.*registry\|Registry.*tool" src/
grep -r "class.*Registry" src/

# For an "Agent" concept:
grep -r "class.*Agent" src/
grep -r "Agent.*Domain\|AgentCapability" src/

# For a "Self-Healing" concept:
grep -r "self.heal\|self_heal\|healing" src/
grep -r "recovery\|rollback" src/
```

### Decision Matrix

| Search Result | Decision | Action |
|--------------|----------|--------|
| Nothing found | CREATE_NEW | Proceed to TRIAGE as new implementation |
| Similar concept, different implementation | EXTEND_EXISTING | Add to existing module |
| Exact duplicate | SKIP | Archive note, document why redundant |

### Template Section

The research note template includes a "System Mapping (REQUIRED)" section that must be completed:

```markdown
## System Mapping (REQUIRED)

### Concepts to Search
| Concept | Search Terms |
|---------|--------------|
| [name] | `pattern1`, `pattern2` |

### Search Results
| Concept | Search Command | Files Found | Lines |
|---------|---------------|-------------|-------|
| [name] | `grep -r "X" src/` | `src/file.py` | 42-67 |

### Mapping Decision
| Concept | Decision | Rationale |
|---------|----------|-----------|
| [name] | EXTEND_EXISTING | Similar to src/existing.py |
```

## Stage 2: Triage (Weekly Review)

Every week, review new research notes and classify:

| Classification | Action | Criteria |
|---------------|--------|----------|
| **Spike** | Create issue, run experiment | High potential, unclear impact |
| **ADR** | Create architecture decision | Clear change needed, significant scope |
| **Backlog** | Add to future work | Good idea, not urgent |
| **Discard** | Archive | Not relevant, superseded, or impractical |

### Manual Weekly Review Checklist

- [ ] Review all new notes in `docs/research/notes/`
- [ ] Classify each note (Spike/ADR/Backlog/Discard)
- [ ] Create GitHub issues for Spikes
- [ ] Update experiment queue

### Auto Weekly Review (Autonomous Mode)

The system can automatically process research notes. See [ADR-009 Phase 5](../decisions/ADR-009-research-integration-architecture.md).

**Triggers:**
- Scheduled: Every Monday 09:00 UTC (GitHub Action)
- On-demand: Manual workflow dispatch
- Immediate: On new note creation (optional)

**Auto-Classification Rules:**

```python
# Classification is based on Recommendation field + content analysis
if note.recommendation:
    return note.recommendation  # Use explicit recommendation

if impact.scope in ["Architecture", "Security"]:
    return "ADR"  # Big changes → ADR

if impact.scope == "Model" and hypothesis:
    return "Spike"  # Model + hypothesis → Spike

if effort == "Hours" and risk == "Low":
    return "Backlog"  # Quick & safe → Backlog
```

**Auto-Actions:**

| Classification | Automatic Actions |
|----------------|-------------------|
| Spike | Create GitHub Issue, Create experiment skeleton |
| ADR | Create draft ADR, Create Issue for review |
| Backlog | Add to backlog tracking Issue |
| Discard | Move to archive folder |

**What Still Needs Human:**
- Approve PR merges
- Increase rollout percentage above 0%
- Real evaluations (cost money)

## Stage 3: Experiment

For Spikes, create an isolated experiment.

### Experiment Structure

```
experiments/
├── exp_001_new_model_provider/
│   ├── README.md           # Hypothesis, success criteria
│   ├── run.py              # Experiment code
│   ├── results.json        # Results data
│   └── conclusion.md       # Analysis and decision
```

### Experiment Template

See `experiments/README.md` for detailed template.

### Success Criteria (Define BEFORE Running)

1. **Quality**: Must be >= baseline (no regression)
2. **Latency**: Must be <= 2x baseline
3. **Cost**: Must be <= 1.5x baseline
4. **Reliability**: Must be >= 99% success rate

## Stage 4: Evaluate

Compare experiment results to baseline:

| Metric | Baseline | Experiment | Delta | Pass? |
|--------|----------|------------|-------|-------|
| Quality Score | 0.85 | 0.87 | +2.4% | ✅ |
| Avg Latency (ms) | 500 | 450 | -10% | ✅ |
| Cost per 1K tokens | $0.003 | $0.004 | +33% | ⚠️ |

### Decision Matrix

| Quality | Latency | Cost | Decision |
|---------|---------|------|----------|
| Better | Better | Better | **ADOPT** |
| Better | Same | Same | **ADOPT** |
| Same | Better | Same | **ADOPT** |
| Worse | Any | Any | **REJECT** |
| Same | Worse | Worse | **REJECT** |
| Mixed | Mixed | Mixed | **NEEDS_MORE_DATA** |

## Stage 5: Integrate

For ADOPT decisions, use feature flags for gradual rollout.

### Rollout Stages

1. **0%** → Merge code behind flag
2. **10%** → Monitor for 2 days
3. **50%** → Monitor for 3 days
4. **100%** → Full rollout
5. **Remove flag** → After 2 weeks at 100%

### Feature Flag Example

```yaml
# config/feature_flags.yaml
new_model_provider:
  enabled: true
  rollout_percentage: 10
  description: "Use new model provider from experiment exp_001"
  experiment_id: "exp_001"
```

### Rollback

If issues detected:
1. Set `rollout_percentage: 0` in config
2. Restart application
3. Document in research note

---

## Directory Structure

```
docs/research/
├── README.md              # This file
├── notes/                 # Research notes
│   └── YYYY-MM-DD-title.md
└── templates/             # Templates
    ├── research-note.md
    └── experiment-design.md

experiments/
├── README.md              # Experiment guidelines
├── exp_001_description/   # Experiment 1
├── exp_002_description/   # Experiment 2
└── ...
```

---

## Templates

### Research Note Template

Location: `docs/research/templates/research-note.md`

### Experiment Design Template

Location: `experiments/README.md`

---

## FAQ

### Q: Do I need a research note for every change?

**A**: No. Research notes are for:
- New technologies or approaches
- Changes to model providers
- Architectural changes
- External tool integrations

Not needed for:
- Bug fixes
- Documentation updates
- Code cleanup
- Minor features

### Q: How long should an experiment run?

**A**: Until you have statistically significant results:
- Minimum: 100 test cases
- Recommended: 500+ test cases
- Complex changes: 1000+ test cases

### Q: What if experiment results are mixed?

**A**: Options:
1. Run more tests (NEEDS_MORE_DATA)
2. Try different configuration
3. Partial adoption (specific use cases only)
4. Reject and document learnings

### Q: Can I skip the experiment for urgent changes?

**A**: Only with explicit approval and:
1. Document why experiment was skipped
2. Add extra monitoring
3. Use 10% rollout maximum
4. Review within 1 week
