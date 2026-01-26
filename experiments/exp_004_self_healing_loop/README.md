# Experiment: Self-Healing Loop for Railway/CI Failures

**ID:** exp_004
**Date:** 2026-01-25
**Status:** Running
**Research Note:** docs/research/notes/2026-01-25-autonomous-media-systems-claude-remotion.md
**Issue:** #615

## Hypothesis

> If we implement self-healing "Try-Heal-Retry" loops for Railway deployments and CI failures, then deployment success rate will increase while reducing manual intervention by 79%.

## Success Criteria

Define BEFORE running:

| Metric | Baseline | Target | Must Meet |
|--------|----------|--------|-----------|
| Auto-fix Rate | 0% | >= 70% | Yes |
| Max Retries | N/A | <= 3 | Yes |
| Error Parse Accuracy | 0% | >= 80% | Yes |
| False Positive Rate | N/A | <= 10% | Yes |

## Pattern Description

The self-healing loop works in 5 steps:
1. **Error Detection** - Capture stdout/stderr from failed operation
2. **Log Parsing** - Agent analyzes error to identify root cause
3. **Fix Generation** - Generate targeted fix based on error type
4. **Re-execution** - Retry the failed operation
5. **Verification** - Confirm success or loop again (max 3 times)

## Error Types Handled

| Error Type | Detection Pattern | Auto-Fix Strategy |
|------------|-------------------|-------------------|
| Build Failure | `npm ERR!`, `ModuleNotFoundError` | Install missing dependencies |
| Port Conflict | `EADDRINUSE`, `port already in use` | Kill process or change port |
| Memory Limit | `ENOMEM`, `heap out of memory` | Increase memory limit in config |
| Timeout | `TimeoutError`, `ETIMEDOUT` | Increase timeout, retry |
| Auth Failure | `401`, `403`, `Unauthorized` | Refresh token, alert human |
| Config Error | `missing env`, `undefined variable` | Check Railway variables |

## Test Cases

- **Test 1:** Intentional missing dependency → Should auto-install
- **Test 2:** Intentional port conflict → Should detect and suggest fix
- **Test 3:** Timeout scenario → Should retry with backoff
- **Test 4:** Auth failure → Should escalate (no auto-fix for security)
- **Test 5:** Real Railway deployment → Measure success rate

## Setup

```bash
# Run experiment
python experiments/exp_004_self_healing_loop/run.py

# Run with specific test
python experiments/exp_004_self_healing_loop/run.py --test build_failure
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SelfHealingLoop                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Execute  │───▶│ Capture  │───▶│  Parse   │              │
│  │ Operation│    │  Error   │    │  Error   │              │
│  └──────────┘    └──────────┘    └────┬─────┘              │
│       ▲                               │                     │
│       │                               ▼                     │
│       │                         ┌──────────┐               │
│       │                         │ Generate │               │
│       │                         │   Fix    │               │
│       │                         └────┬─────┘               │
│       │                               │                     │
│       │         ┌──────────┐         │                     │
│       └─────────│  Retry?  │◀────────┘                     │
│                 │ (max 3)  │                                │
│                 └────┬─────┘                                │
│                      │ No                                   │
│                      ▼                                      │
│                ┌──────────┐                                │
│                │ Escalate │                                │
│                │ to Human │                                │
│                └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

## Results

_Filled after experiment completes_

| Metric | Baseline | Actual | Delta | Pass? |
|--------|----------|--------|-------|-------|
| Auto-fix Rate | 0% | | | |
| Max Retries | N/A | | | |
| Error Parse Accuracy | 0% | | | |
| False Positive Rate | N/A | | | |

## Conclusion

**Decision:** _ADOPT / REJECT / NEEDS_MORE_DATA_

**Reasoning:** _To be filled_

## Next Steps

- [ ] Run with intentional failures
- [ ] Test with real Railway deployments
- [ ] Integrate with AutomationOrchestrator if successful
- [ ] Create ADR if adopting
