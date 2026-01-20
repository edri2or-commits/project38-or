# ISSUE-0002: [Spike] Chain-of-Thought Prompting Research

**Created:** 2026-01-20
**Status:** Open
**Classification:** Spike
**Research Note:** [2026-01-20-chain-of-thought-prompting-research.md](../../docs/research/notes/2026-01-20-chain-of-thought-prompting-research.md)

---

## Summary

CoT prompting improves accuracy on math problems by 40%

---

## Classification

**Decision:** Spike
**Reason:** Explicit recommendation: Spike

---

## Hypothesis

> If we apply this approach, then: The study found that:

---

## Impact

| Dimension | Value |
|-----------|-------|
| **Scope** | Model |
| **Effort** | Weeks |
| **Risk** | Medium |

---

## Next Steps

- [ ] Review research note
- [ ] Run experiment (exp_002_chain_of_thought_prompting_res)
- [ ] Analyze results
- [ ] Make ADOPT/REJECT decision

### Experiment

**ID:** exp_002_chain_of_thought_prompting_res
**Location:** `experiments/exp_002_chain_of_thought_prompting_res/`

```bash
# Run the experiment
python experiments/exp_002_chain_of_thought_prompting_res/run.py

# Or with specific provider
python experiments/exp_002_chain_of_thought_prompting_res/run.py --provider claude
```

---

## References

- Research Note: `docs/research/notes/2026-01-20-chain-of-thought-prompting-research.md`
- ADR-009: Research Integration Architecture
- Experiment: `experiments/exp_002_chain_of_thought_prompting_res/`
