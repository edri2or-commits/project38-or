# Experiment: Claude 4.5 Opus Model Evaluation

**ID:** exp_002
**Created:** 2026-01-20
**Status:** Framework Validated (Mock Run Complete)
**Research Note:** [2026-01-20-claude-4-opus-evaluation.md](../../docs/research/notes/2026-01-20-claude-4-opus-evaluation.md)

---

## Hypothesis

> If we use Claude 4.5 Opus for high-stakes autonomous decisions, then quality scores will improve by 10-15% while accepting 2-3x higher cost.

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
python experiments/exp_002_claude_4_5_opus_model_evaluati/run.py

# Or run with specific provider
python experiments/exp_002_claude_4_5_opus_model_evaluati/run.py --provider claude
```

---

## Results

### Mock Run (Framework Validation) - 2026-01-21

**Status:** ✅ Framework Validated

| Metric | Baseline (mock-sonnet) | Experiment (mock-opus) | Ratio | Pass? |
|--------|------------------------|------------------------|-------|-------|
| Quality | 18.33% | 18.33% | 1.0x | ⚠️ N/A (mock) |
| Latency | 297ms | 804ms | 2.71x | ❌ FAIL |
| Cost | $0.0068 | $0.0340 | 5.0x | ❌ FAIL |

**Key Observations:**
1. Framework correctly compares providers
2. Decision logic works (REJECT due to cost +400% without quality improvement)
3. Mock providers have correct characteristics (Opus: higher latency, 5x cost)
4. Quality scores are low because mock responses don't match golden set expectations

### Real Provider Run (Pending)

Requires real API providers to be registered (Claude Sonnet vs Claude Opus).

| Metric | Baseline | Experiment | Delta | Pass? |
|--------|----------|------------|-------|-------|
| Quality | - | - | - | - |
| Latency | - | - | - | - |
| Cost | - | - | - | - |

---

## Decision

### Mock Run Decision

**Outcome:** REJECT (Expected for mock validation)

**Reasoning:** Cost +400% without quality improvement (mock providers don't produce meaningful quality scores)

### Real Provider Decision

**Outcome:** PENDING

**Reasoning:** Requires real API providers to be registered and tested.

---

## Files

- `README.md` - This file
- `run.py` - Experiment execution script
- `config.yaml` - Experiment configuration
- `results.json` - Results (generated after run)
- `conclusion.md` - Conclusion (generated after analysis)
