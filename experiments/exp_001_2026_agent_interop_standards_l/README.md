# Experiment: 2026 Agent Interop Standards Landscape

**ID:** exp_001
**Created:** 2026-01-20
**Status:** Not Started
**Research Note:** [2026-01-20-2026-agent-interop-standards-landscape.md](../../docs/research/notes/2026-01-20-2026-agent-interop-standards-landscape.md)

---

## Hypothesis

> Hypothesis: Combining MCP (tool connectivity) + AGENTS.

---

## Background

This experiment was auto-generated from research note classification.
It tests whether the proposed change improves system performance.

---

## Success Criteria

| Metric | Threshold | Description |
|--------|-----------|-------------|
| Quality | >= 85% | Must meet minimum quality |
| Quality Regression | <= -2.0% | Max allowed regression |
| Latency | <= 2.0x baseline | Max latency increase |
| Cost | <= 1.5x baseline | Max cost increase |

---

## Methodology

1. **Baseline Measurement**
   - Run evaluation with `mock` provider
   - Record: quality score, latency, cost

2. **Experiment Measurement**
   - Run evaluation with `mock` provider
   - Record: quality score, latency, cost

3. **Comparison**
   - Calculate deltas
   - Apply decision matrix

---

## How to Run

```bash
# Run the experiment
python experiments/exp_001_2026_agent_interop_standards_l/run.py

# Or run with specific provider
python experiments/exp_001_2026_agent_interop_standards_l/run.py --provider claude
```

---

## Results

**Status:** Not yet run

| Metric | Baseline | Experiment | Delta | Pass? |
|--------|----------|------------|-------|-------|
| Quality | - | - | - | - |
| Latency | - | - | - | - |
| Cost | - | - | - | - |

---

## Decision

**Outcome:** PENDING

**Reasoning:** Experiment not yet run.

---

## Files

- `README.md` - This file
- `run.py` - Experiment execution script
- `config.yaml` - Experiment configuration
- `results.json` - Results (generated after run)
- `conclusion.md` - Conclusion (generated after analysis)
