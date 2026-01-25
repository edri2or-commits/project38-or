# Experiment 004: GSD State Management Pattern

**Status**: IN_PROGRESS
**Started**: 2026-01-25
**Research Note**: `docs/research/notes/2026-01-25-saas-factory-gsd-framework.md`

---

## Hypothesis

> If we use a STATE.md file to externalize session state, then:
> 1. Session resumption will be faster (< 30 seconds to full context)
> 2. Context rot will decrease (fewer "forgotten" decisions mid-session)
> 3. Long sessions (2+ hours) will maintain higher task accuracy

---

## What We're Testing

The GSD Framework proposes externalizing LLM "memory" to files:

| File | Purpose | We're Testing |
|------|---------|---------------|
| STATE.md | Current phase, status, recent context | ✅ Yes |
| PLAN.md | XML task definitions | ❌ Not yet (we have TodoWrite) |

---

## Measurement Plan

### Metric 1: Resumption Speed
- **Before**: New session requires re-reading CLAUDE.md (~65KB) + conversation
- **After**: Read STATE.md (~3KB) for immediate context
- **Measure**: Time from "Resume" to first productive action

### Metric 2: Context Accuracy
- **Test**: After 10+ tool calls, ask Claude "what are we working on?"
- **Before**: May drift from original goal
- **After**: Should match STATE.md current focus

### Metric 3: Session Continuity
- **Test**: Interrupt session, start new one, say "resume"
- **Success**: Claude correctly identifies last task and next steps

---

## Protocol

### Session Start
```
1. Claude reads STATE.md automatically (or user says "קרא STATE.md")
2. Claude confirms current focus and next steps
3. Work continues from documented state
```

### Task Completion
```
1. Complete task
2. Update STATE.md "Recent Accomplishments"
3. Update "Next Steps"
4. Commit with other changes
```

### Session End
```
1. Update STATE.md with final state
2. Ensure "Next Steps" is clear for next session
3. Commit and push
```

---

## Results Log

| Date | Session | Observation | Rating |
|------|---------|-------------|--------|
| 2026-01-25 | Initial | Created STATE.md, testing pattern | ⏳ |
| 2026-01-25 | Test #1 | SessionStart hook did NOT read STATE.md automatically. Context came from system-reminder showing file changes, not from intentional state loading. User must explicitly request "קרא STATE.md". | ⚠️ Partial |

### Test #1 Details
- **Expected**: Claude reads STATE.md at session start, immediately knows context
- **Actual**: Claude learned about STATE.md from system-reminder (file modification notice)
- **Gap**: No automatic loading mechanism exists
- **Conclusion**: Pattern requires either (a) manual user request, or (b) hook modification

---

## Decision Criteria

| Outcome | Criteria |
|---------|----------|
| **ADOPT** | 2/3 metrics improve, no significant overhead |
| **MODIFY** | Some benefit but needs adjustment |
| **REJECT** | No measurable improvement or too much overhead |

---

## Files

- `/STATE.md` - The state file being tested
- `/docs/research/notes/2026-01-25-saas-factory-gsd-framework.md` - Source research
