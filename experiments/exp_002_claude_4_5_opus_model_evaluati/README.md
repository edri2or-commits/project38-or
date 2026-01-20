# Experiment: Claude 4.5 Opus Model Evaluation

**ID:** exp_002
**Created:** 2026-01-20
**Status:** Not Started
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

**Status:** ✅ Completed (2026-01-20)

| Metric | Baseline (mock) | Experiment (mock-opus) | Delta | Pass? |
|--------|-----------------|------------------------|-------|-------|
| Quality | 81.25% | 81.25% | 0.0% | ⚠️ No improvement |
| Latency | 51ms | 151ms | +198% | ⚠️ Worse |
| Cost | $0.0016 | $0.0785 | +4747% | ❌ Much worse |
| Success Rate | 70% (14/20) | 70% (14/20) | 0% | ⚠️ No improvement |

**Test Set:** 20 golden queries covering greeting, math, coding, JSON, markdown, reasoning

---

## Decision

**Outcome:** REJECT

**Reasoning:** Cost increased by 4747% without any quality improvement.

**Analysis:**
1. Mock providers produce identical quality scores because they use similar response templates
2. The cost difference reflects Opus's 5x pricing ($0.015/$0.075 vs $0.001/$0.002 per 1K tokens)
3. Latency increased 3x (simulated 150ms vs 50ms)

**Framework Validation:**
This experiment validates that the ADR-009 decision matrix is working correctly:
- Same quality + much higher cost → **REJECT**

**Next Steps for Real Evaluation:**
To make a real ADOPT/REJECT decision with actual API providers:

```bash
# Run with real Claude Sonnet baseline
python experiments/exp_002_claude_4_5_opus_model_evaluati/run.py \
    --baseline claude-sonnet \
    --provider claude-opus
```

This requires:
1. Register actual Claude providers with API keys
2. Budget approval for API costs (~$5-10 for full golden set)
3. Compare real quality differences on complex reasoning tasks

---

## Files

- `README.md` - This file
- `run.py` - Experiment execution script
- `config.yaml` - Experiment configuration
- `results.json` - Results (generated after run)
- `conclusion.md` - Conclusion (generated after analysis)
