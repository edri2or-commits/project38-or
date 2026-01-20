# Research Integration Process

## Overview

This directory contains research notes, experiment designs, and integration decisions.
The process ensures that new AI discoveries are integrated safely and measurably.

**Architecture Decision:** [ADR-009](../decisions/ADR-009-research-integration-architecture.md)

## The 5-Stage Process

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   CAPTURE    │───▶│    TRIAGE    │───▶│  EXPERIMENT  │───▶│   EVALUATE   │───▶│  INTEGRATE   │
│              │    │              │    │              │    │              │    │              │
│  Document    │    │  Classify    │    │  Isolated    │    │  Compare to  │    │  Feature     │
│  discovery   │    │  impact      │    │  test        │    │  baseline    │    │  flag        │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
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

## Stage 2: Triage (Weekly Review)

Every week, review new research notes and classify:

| Classification | Action | Criteria |
|---------------|--------|----------|
| **Spike** | Create issue, run experiment | High potential, unclear impact |
| **ADR** | Create architecture decision | Clear change needed, significant scope |
| **Backlog** | Add to future work | Good idea, not urgent |
| **Discard** | Archive | Not relevant, superseded, or impractical |

### Weekly Review Checklist

- [ ] Review all new notes in `docs/research/notes/`
- [ ] Classify each note (Spike/ADR/Backlog/Discard)
- [ ] Create GitHub issues for Spikes
- [ ] Update experiment queue

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
