# ADR-011: ADR Architect - Structured Request Processing

**Status:** Proposed
**Date:** 2026-01-22
**Decision Makers:** User (edri2or-commits), Claude Code Agent
**Related:** ADR-009 (Research Integration), ADR-002 (Dual Documentation Strategy)

---

## Context

### User Raw Request (as-is)

> "Role: Claude Code – ADR Architect & System Investigator (עם גישה מלאה למערכת)
> Mission: לבנות איתי (המשתמש) ADR חדש שמתרגם בקשה גולמית/מפוזרת שלי להחלטה הנדסית מסודרת..."

### Interpreted Intent

The user requires a **systematic process** to convert:
- Scattered thoughts
- Vague ideas
- Unclear requests
- ADHD-driven impulses

Into:
- Structured engineering decisions
- Evidence-backed ADRs
- Actionable implementation plans

### Problem Statement

**Challenge:** User (non-technical, ADHD) generates ideas/requests that are often:
1. **Scattered** - Multiple unconnected thoughts in one message
2. **Ambiguous** - Intent unclear, missing context
3. **Impulsive** - May not reflect actual needs
4. **Disconnected** - User doesn't know current system state

**Risk without solution:**
- Wasted development effort on unclear requirements
- System changes that don't match user needs
- No accountability trail for decisions
- AI agent may exploit user's lack of technical knowledge

### Current State

The system has:
- ✅ ADR system for documenting decisions (ADR-001 to ADR-010)
- ✅ research-ingestion skill for processing research (ADR-009)
- ✅ 12 skills for various tasks
- ✅ 4-layer documentation architecture

But lacks:
- ❌ Process for handling scattered user requests (not just research)
- ❌ System investigation workflow before making changes
- ❌ Impulsivity check mechanism
- ❌ Historical pattern analysis for user requests
- ❌ "Truth Protocol" enforcement

---

## Decision

**Adopt ADR Architect workflow** - a 9-step systematic process that transforms raw user requests into validated engineering decisions.

### Architecture: 9-Step Workflow

```
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│   1. INTAKE    │───▶│  2. SYSTEM     │───▶│  3. REALITY    │
│                │    │     MAPPING    │    │     CHECK      │
│ - Parse raw    │    │ - Investigate  │    │ - Compare      │
│   request      │    │   codebase     │    │   expectation  │
│ - Extract      │    │ - Map relevant │    │   vs reality   │
│   intent       │    │   components   │    │ - Explain gaps │
│ - Identify     │    │ - Show proof   │    │   with         │
│   context      │    │   of work      │    │   evidence     │
└────────────────┘    └────────────────┘    └────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│ 4. DECISION    │───▶│ 5. EXTERNAL    │───▶│ 6. PATTERN     │
│    ANALYSIS    │    │    RESEARCH    │    │    FROM        │
│                │    │                │    │    HISTORY     │
│ - Problem      │    │ - Web search   │    │ - Check past   │
│   statement    │    │   for best     │    │   similar      │
│ - 2-4 options  │    │   practices    │    │   requests     │
│ - Pros/cons    │    │ - 3-7 sources  │    │ - Success/     │
│ - Recommend    │    │ - Document     │    │   failure rate │
└────────────────┘    └────────────────┘    └────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│ 7. IMPULSIVITY │───▶│   8. PLAN      │───▶│ 9. DELIVERABLE │
│    CHECK       │    │                │    │                │
│                │    │ - DoD          │    │ - Full ADR     │
│ - Show signals │    │ - Milestones   │    │ - Executive    │
│ - Ask ONE      │    │ - Risks        │    │   summary      │
│   question     │    │ - Metrics      │    │ - 3 questions  │
│ - Document     │    │ - Rollback     │    │ - Deep         │
│   answer       │    │   plan         │    │   research     │
└────────────────┘    └────────────────┘    │   prompt       │
                                            └────────────────┘
```

### Core Principles

#### 1. Truth Protocol (Non-negotiable)

| Rule | Implementation |
|------|----------------|
| **No fabrication** | Every claim backed by file:line or URL |
| **Uncertainty explicit** | "אין באפשרותי לאשר זאת" when unsure |
| **Sources transparent** | Internal: path:line:commit. External: URL + date + quote |
| **No filler text** | Every paragraph must contribute |
| **Self-check** | Verify all claims before delivering |

#### 2. Evidence Requirements

**Internal Sources:**
```
src/module.py:45-67 (commit abc123)
```

**External Sources:**
```
URL: https://docs.example.com/guide
Accessed: 2026-01-22
Key finding: "..." (max 25 words)
```

#### 3. Proof of Work

Agent MUST document:
- Files examined (with line numbers)
- Search queries executed
- Tests/linters run (if any)
- What was NOT found (negative evidence)

---

## Goals / Non-Goals

### Goals

1. ✅ Convert scattered requests into structured ADRs
2. ✅ Investigate system before proposing changes
3. ✅ Detect and flag impulsive requests
4. ✅ Learn from historical patterns
5. ✅ Enforce truth protocol
6. ✅ Create actionable implementation plans

### Non-Goals

1. ❌ Automatic code changes (human approval required)
2. ❌ Diagnosis of user's mental state
3. ❌ Replacement of user judgment on priorities
4. ❌ External API calls without confirmation

---

## Assumptions / Unknowns

### Assumptions (marked!)

- **[A1]** User has ADHD and benefits from structured process
- **[A2]** User is non-technical and may not know system state
- **[A3]** Most requests have valid underlying needs
- **[A4]** Historical patterns exist and are useful

### Unknowns (marked!)

- **[U1]** How to quantify impulsivity objectively?
- **[U2]** What is acceptable false positive rate for impulsivity check?
- **[U3]** How to measure ADR quality over time?

---

## Options Considered

### Option A: Do Nothing

**Description:** Continue using ad-hoc request processing

**Pros:**
- No development effort
- Flexible

**Cons:**
- Scattered requests remain scattered
- No accountability trail
- User confusion persists

**Recommendation:** ❌ REJECT

### Option B: Minimal - Document Template Only

**Description:** Create ADR template with instructions, no automation

**Pros:**
- Low effort
- Human in control

**Cons:**
- User must follow template manually
- No investigation automation
- No impulsivity check

**Recommendation:** ❌ REJECT

### Option C: Medium - Skill with Guided Workflow

**Description:** Create `adr-architect` skill that guides through 9 steps

**Pros:**
- Full workflow support
- Automated investigation
- Impulsivity check included
- Evidence documented
- Fits existing skill system

**Cons:**
- Medium development effort
- Skill complexity

**Recommendation:** ✅ ACCEPT (Recommended)

### Option D: Full - Autonomous ADR Generator

**Description:** Fully autonomous system that generates ADRs without guidance

**Pros:**
- Minimal user interaction

**Cons:**
- High risk of misinterpretation
- Removes user from decision loop
- May exploit user's lack of knowledge

**Recommendation:** ❌ REJECT

---

## Decision

**Implement Option C: `adr-architect` skill with guided 9-step workflow.**

---

## Rationale (with evidence)

### 1. Fits Existing Architecture

The system already has 12 skills in `.claude/skills/`:
```
.claude/skills/
├── research-ingestion/   ← Similar pattern
├── pr-helper/           ← Similar pattern
├── doc-updater/         ← Similar pattern
└── ...
```

Adding `adr-architect` follows established patterns.

### 2. Addresses User Needs

User quote from specification:
> "אני לא טכנולוגי/לא מתכנת, ולעיתים החשיבה שלי מפוזרת בגלל ADHD. לכן אתה חייב לקחת אחריות"

The skill takes responsibility while keeping user in decision loop.

### 3. Truth Protocol Enforceable

The skill can:
- Run code searches (Grep, Glob)
- Read files with line numbers
- Execute web searches
- Document evidence systematically

---

## Consequences

### Positive

1. Scattered requests become structured decisions
2. Evidence trail for all decisions
3. Impulsivity check prevents wasteful changes
4. Historical learning improves over time
5. User protected from AI exploitation

### Negative / Risks

1. **Risk:** Skill may slow down urgent requests
   - **Mitigation:** Add "urgent bypass" with explicit acknowledgment

2. **Risk:** Impulsivity check may offend user
   - **Mitigation:** Frame as neutral observation, not judgment

3. **Risk:** Over-documentation slows productivity
   - **Mitigation:** Streamlined output format

### Cost / Complexity

| Aspect | Estimate |
|--------|----------|
| Development effort | 2-4 hours |
| Files to create | 2 (ADR + SKILL.md) |
| Lines of code | ~400 (skill definition) |
| Maintenance | Low (skill is declarative) |

---

## Implementation Plan

### Steps

1. ✅ Create ADR-011 (this file)
2. ⬜ Create `.claude/skills/adr-architect/SKILL.md`
3. ⬜ Update CLAUDE.md with new skill
4. ⬜ Update changelog
5. ⬜ Test with sample request
6. ⬜ Commit and push

### Milestones

| Milestone | Definition of Done |
|-----------|-------------------|
| M1: Skill Created | SKILL.md exists and is valid |
| M2: Integrated | Listed in CLAUDE.md |
| M3: Tested | One full ADR generated successfully |
| M4: Documented | Changelog updated |

### Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| ADR creation time | N/A | < 30 minutes per ADR |
| Evidence coverage | N/A | 100% claims have sources |
| User satisfaction | N/A | Qualitative feedback |
| Impulsivity detection | N/A | Track and learn |

### Testing / Monitoring

1. **Test:** Process a sample scattered request
2. **Monitor:** Track ADRs created with this skill
3. **Learn:** Adjust workflow based on feedback

### Rollback

If skill causes problems:
1. Remove from CLAUDE.md skill list
2. Delete `.claude/skills/adr-architect/`
3. Continue using manual ADR process

---

## Historical Signals

### Similar Past Requests

| Date | Request | Outcome | Evidence |
|------|---------|---------|----------|
| 2026-01-20 | ADR-009 Research Integration | ✅ ADOPTED | Phase 5 complete |
| 2026-01-18 | ADR-006 GCP Autonomy | ✅ ADOPTED | 20+ tools deployed |
| 2026-01-17 | ADR-010 LiteLLM Gateway | ✅ ADOPTED | Production running |

**Pattern:** User's architectural requests have high adoption rate.

### Experience Index

- Similar requests implemented: 3/3 (100%)
- Average success rate: High
- No failed architectural ADRs found

---

## Impulsivity Check

**Signals observed in this request:**

| Signal | Present? | Notes |
|--------|----------|-------|
| Urgency words ("עכשיו", "מיד") | ❌ | Not detected |
| Topic jumping | ❌ | Focused on one capability |
| Incomplete thoughts | ⚠️ | Spec was detailed but long |
| Time of day | ⚠️ | Cannot determine |

**Question asked:** N/A (this is the founding ADR)

**User response:** To be documented in future ADRs

---

## Open Questions

1. Should impulsivity check be mandatory or optional?
2. What triggers should activate the skill automatically?
3. How to handle truly urgent requests that need to bypass the process?

---

## References

### Internal

| Path | Description |
|------|-------------|
| `.claude/skills/research-ingestion/SKILL.md` | Similar skill pattern |
| `docs/decisions/ADR-009-*.md` | Research integration (related) |
| `CLAUDE.md:Skills` | Current skill documentation |

### External

| Source | Key Finding |
|--------|-------------|
| [AWS ADR Process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html) | Industry standard ADR format |
| [LangChain State of Agents 2026](https://www.langchain.com/state-of-agent-engineering) | Context is critical for agent success |

---

## Update Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-22 | Claude Code | Initial ADR creation |
