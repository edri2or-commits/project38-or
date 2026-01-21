# ISSUE-0003: [Spike] Vercel Agent Browser - Autonomous UI Navigation

**Created:** 2026-01-21
**Status:** Open
**Classification:** Spike
**Research Note:** [2026-01-21-autonomous-qa-vercel-agent-browser.md](../notes/2026-01-21-autonomous-qa-vercel-agent-browser.md)

---

## Summary

Vercel Agent Browser CLI enables autonomous web testing using AI agents with Accessibility Tree approach (93% token reduction vs traditional DOM).

---

## Classification

**Decision:** Spike
**Reason:** Directly addresses limitation discovered during Railway troubleshooting - inability to interact with Railway Dashboard UI

---

## Hypothesis

> If we integrate Vercel Agent Browser CLI for UI interactions, then autonomous operations coverage will increase by 50%+ (from API-only to API+UI) while maintaining acceptable token costs (<$0.05 per complex operation).

---

## Impact

| Dimension | Value |
|-----------|-------|
| **Scope** | System-wide |
| **Effort** | Weeks |
| **Risk** | Medium |

---

## Success Criteria

| Metric | Baseline | Target | Must Meet |
|--------|----------|--------|-----------|
| Operations Coverage | 60% (API-only) | >= 90% | Yes |
| Token Cost per Step | N/A | <= $0.02 | Yes |
| Success Rate | N/A | >= 85% | Yes |
| Avg Latency per Step | N/A | <= 5s | No |
| Loop Detection Rate | N/A | >= 95% | Yes |

---

## Next Steps

- [x] Create experiment skeleton
- [ ] Install Playwright and verify browser automation
- [ ] Run Phase 1 tests (Basic Navigation)
- [ ] Run Phase 2 tests (Interactive Operations)
- [ ] Run Phase 3 tests (Complex Workflows)
- [ ] Analyze results
- [ ] Make ADOPT/REJECT decision

### Experiment

**ID:** exp_003_vercel_agent_browser
**Location:** `experiments/exp_003_vercel_agent_browser/`

```bash
# Run Phase 1 (Basic Navigation) - dry run
python experiments/exp_003_vercel_agent_browser/run.py --phase 1

# Run all phases - dry run
python experiments/exp_003_vercel_agent_browser/run.py --all

# Run live (CAUTION: interacts with real UIs)
python experiments/exp_003_vercel_agent_browser/run.py --all --live
```

---

## Technical Details

### Token Economics

| Method | Tokens/Step | Cost/Step |
|--------|-------------|-----------|
| Traditional (DOM + GPT-4o) | ~60,000 | ~$0.30 |
| Vercel Agent + Claude 3.5 | ~3,500 | ~$0.01 |

### Key Features

- Accessibility Tree extraction (93% token reduction)
- Reference IDs (@e1, @e2) instead of CSS selectors
- Loop detection with state machine
- Dry-run mode for safe testing

### Test Phases

1. **Basic Navigation** (5 tests): Navigate, snapshot, read status
2. **Interactive** (5 tests): Click buttons, open modals, pagination
3. **Complex Workflows** (3 tests): Multi-step sequences

---

## References

- Research Note: `docs/research/notes/2026-01-21-autonomous-qa-vercel-agent-browser.md`
- ADR-009: Research Integration Architecture
- Experiment: `experiments/exp_003_vercel_agent_browser/`
- Playwright Docs: https://playwright.dev/python/docs/accessibility
