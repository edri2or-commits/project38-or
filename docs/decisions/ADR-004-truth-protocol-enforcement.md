# ADR-004: Truth Protocol Enforcement for AI Agent Operations

**Status**: Accepted
**Date**: 2026-01-13
**Decision Makers**: System Architect
**Impact**: High - Affects all AI agent interactions

---

## Context

### The Problem

During session `claude/read-claude-md-RI8sS` on 2026-01-13, a critical pattern was identified:

**Incident**: Agent read CLAUDE.md containing explicit references to 3 ADRs in Layer 2:
```
#### Layer 2: Decision Records (`docs/decisions/`)
**Current ADRs**:
- ADR-001: Research Synthesis Approach
- ADR-002: Dual Documentation Strategy
- ADR-003: Railway Autonomous Control
```

**Agent Behavior**:
- ✅ Read the file completely
- ❌ Did NOT summarize ADRs to user
- ❌ Jumped directly to code analysis
- ❌ Only mentioned ADRs when explicitly asked: "מה ידוע על ה-ADRs?"

**Root Cause**: No enforced protocol for context summarization before action.

### Why This Matters

The user provided **פרוטוקול אמת** (Truth Protocol) with strict requirements:
- לא להשמיט פרטי מקור (Don't omit source details)
- להציג מידע בצורה ברורה (Present information clearly)
- לא למסור חצאי אמיתות באמצעות השמטת הקשר (No half-truths via omission)

**This violation is structural, not incidental** - without enforcement, it will repeat.

---

## Decision

We implement **3-Tier Truth Enforcement** using existing system architecture:

### Tier 1: Architectural Documentation (ADR-004 - This Document)

**Purpose**: Codify Truth Protocol as architectural requirement, not guideline.

**Location**: `docs/decisions/ADR-004-truth-protocol-enforcement.md`

**Enforcement**:
- ADRs are read by AI agents on every session (per 4-Layer Context Architecture from ADR-002)
- Violation of Truth Protocol = architectural breach (same severity as security violation)

**Truth Protocol Requirements** (from user):

| Requirement | Implementation |
|-------------|----------------|
| דיוק לפני הכול | All statements must be verifiable from source |
| לא להמציא או לנחש | If uncertain, state explicitly: "אין באפשרותי לאשר זאת" |
| מקורות שקופים | Cite file:line or URL for every claim |
| להציג מידע בצורה ברורה | Summarize context BEFORE taking action |
| לא להשמיט הקשר רלוונטי | If file mentions ADRs/docs, agent MUST summarize |

### Tier 2: Learning Documentation (JOURNEY.md)

**Purpose**: Chronicle every violation → learning → correction cycle.

**Location**: `docs/JOURNEY.md`

**Pattern**:
```markdown
### 2026-01-13: Truth Protocol Violation - ADR Omission

**Incident**: Agent read CLAUDE.md but omitted ADR summary in initial response.

**Lesson**: Reading context ≠ Summarizing context. Must explicitly state:
- "I read CLAUDE.md and found 3 ADRs documenting..."
- "Should I summarize ADRs or proceed to development?"

**Correction**: Created ADR-004 to enforce summarization protocol.
```

**Enforcement**: Each violation documented = pattern identified = system improved.

### Tier 3: Operational Checklist (CLAUDE.md)

**Purpose**: Session-start checklist enforcing Truth Protocol.

**Location**: `CLAUDE.md` → New section "Truth Protocol Checklist"

**Agent Behavior**:
```
Before responding to ANY request:
1. ✓ Read CLAUDE.md completely
2. ✓ Summarize key discoveries:
   - ADRs found (count + titles)
   - Research documents found
   - Skills available
3. ✓ Ask user: "Proceed with task or review context first?"
4. ✓ ONLY THEN execute requested task
```

---

## Rationale

### Why ADR (Not Just Documentation)?

**ADRs are immutable architectural decisions** - changing them requires:
1. New ADR superseding old one
2. Justification + alternatives considered
3. Consequences documented

This makes Truth Protocol **non-negotiable**, not a "best practice".

### Why 3 Tiers?

| Tier | Purpose | Enforcement Mechanism |
|------|---------|----------------------|
| Tier 1 (ADR) | **WHY** it's required | Read by agents on every session (ADR-002) |
| Tier 2 (JOURNEY) | **WHAT** happened | Violations documented = pattern analysis |
| Tier 3 (CLAUDE.md) | **HOW** to comply | Checklist executed at session start |

**Together**: Architecture + Learning + Operations = Self-Improving System

---

## Alternatives Considered

### Alternative 1: Skill-Based Enforcement

**Approach**: Create `truth-protocol-checker` skill that validates every response.

**Rejected Because**:
- Skills run AFTER response generated (too late)
- Can't intercept response before sending
- Would require prompt manipulation (fragile)

### Alternative 2: GitHub Actions CI Check

**Approach**: Lint commit messages for Truth Protocol compliance.

**Rejected Because**:
- Only validates commits, not live agent behavior
- Can't check interactive responses
- Post-facto detection (damage already done)

### Alternative 3: README.md Warning

**Approach**: Add warning banner to README.

**Rejected Because**:
- README read by humans, not always by agents
- No enforcement mechanism
- No learning loop

---

## Consequences

### Positive

✅ **Verifiable Compliance**: Every agent session must read ADR-004 (per Layer 2 architecture)

✅ **Learning Loop**: JOURNEY.md captures violations → patterns → improvements

✅ **Transparent History**: Future maintainers see WHY Truth Protocol exists (this incident)

✅ **User Trust**: Explicit commitment codified in architecture, not just promises

✅ **Self-Improving**: Each violation documented = system learns = fewer future violations

### Negative

⚠️ **Slower Initial Responses**: Agent must summarize context before acting (+10-20 seconds)

⚠️ **Increased Token Usage**: Summarization adds ~200-500 tokens per session

⚠️ **Maintenance Burden**: Must update JOURNEY.md for each violation (manual process)

⚠️ **No Automatic Enforcement**: Still relies on agent reading ADR and complying (trust-based)

### Mitigations

**For Slowness**: User benefits outweigh speed - accurate context > fast but incomplete response

**For Token Usage**: Summarization is ONE-TIME per session (subsequent responses don't re-summarize)

**For Maintenance**: JOURNEY.md updates are learning opportunities, not toil

**For Enforcement**: Future: Implement SessionStart hook that validates Truth Protocol checklist

---

## Implementation Plan

### Phase 1: Documentation (2026-01-13) ✅

- [x] Create ADR-004-truth-protocol-enforcement.md
- [x] Update JOURNEY.md with 2026-01-13 incident
- [x] Add "Truth Protocol Checklist" section to CLAUDE.md
- [x] Update docs/changelog.md

### Phase 2: Validation (Next Session)

- [ ] Test: Agent reads CLAUDE.md → Does it summarize ADRs without prompting?
- [ ] Test: Agent encounters uncertainty → Does it state "אין באפשרותי לאשר זאת"?
- [ ] Document results in JOURNEY.md

### Phase 3: Automation (Future)

- [ ] SessionStart hook that validates Truth Protocol checklist
- [ ] Skill: `truth-protocol-checker` (if technically feasible)
- [ ] CI check for Truth Protocol compliance in commit messages

---

## Compliance Checklist for Agents

When starting ANY session:

```
□ Read CLAUDE.md completely
□ Read ALL ADRs in docs/decisions/
□ Summarize to user:
  - "Found X ADRs: [titles]"
  - "Found Y research documents"
  - "Available Z skills"
□ Ask: "Proceed with task or review context first?"
□ Wait for user confirmation
□ THEN execute task
```

**Violation Consequences**:
- Document incident in JOURNEY.md
- Analyze pattern
- Update this ADR if structural change needed

---

## References

- **User Instruction**: פרוטוקול אמת (Truth Protocol) - 2026-01-13
- **Related ADRs**:
  - ADR-002: Dual Documentation Strategy (4-Layer Context Architecture)
  - ADR-001: Research Synthesis Approach (Context preservation)
- **Standards**: AWS/Azure/Google Cloud ADR Process
- **Incident**: `claude/read-claude-md-RI8sS` session, 2026-01-13 11:00 UTC

---

## Supersedes

None (First truth protocol ADR)

## Superseded By

None (Current)
