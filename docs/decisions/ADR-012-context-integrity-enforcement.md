# ADR-012: Context Integrity Enforcement Architecture

**Status:** Accepted
**Date:** 2026-01-22
**Decision Makers:** User (edri2or-commits), Claude Code Agent
**Related:** ADR-002 (Dual Documentation Strategy), ADR-011 (ADR Architect)

---

## Context

### User Raw Request

> "כל פעם אני צריך לוודא את עניין התיעוד וכל הזמן אני באמת רואה שאם אני לא שואל אותך שתידעת כמו שצריך אז אתה מגלה פספוסים ואני רוצה שזה יהיה יותר מקצועי ואמין ובלי התערבות שלי"

### Problem Statement

**"Context Drift"** - When code evolves but documentation remains static, the AI agent's "world model" diverges from reality. This leads to:
- Hallucinated implementations based on stale documentation
- Cyclic error generation (fix creates new bug based on old context)
- Operational paralysis requiring manual intervention

**Evidence:** On 2026-01-22, the JOURNEY.md update for Phase 38 (ADR-011) was forgotten until the user manually verified documentation completeness. This pattern of "user must verify" is unsustainable.

### Research Foundation

This ADR is based on comprehensive Deep Research:
- **Title:** "Context Integrity Assurance: A Policy-as-Code Architecture for Autonomous AI Systems"
- **Date:** 2026-01-22
- **Key Finding:** Hybrid Enforcement Model (DangerJS + AI) scores 4.8/5 for solo developers

---

## Decision

**Implement a Hybrid Enforcement Model** with two layers:

1. **Hard Gate (Deterministic):** DangerJS workflow that blocks PRs when documentation is missing
2. **Soft Gate (Probabilistic):** CodeRabbit AI verification for semantic accuracy

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         PR Opened                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    HARD GATE (DangerJS)                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Load .github/doc-policy.json                            │   │
│  │  For each policy:                                        │   │
│  │    - Check if trigger files modified                     │   │
│  │    - If yes, verify required files also modified         │   │
│  │    - If no, FAIL or WARN based on severity               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Deterministic: Same input → Same output                        │
│  Action: BLOCK PR if requirements not met                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SOFT GATE (CodeRabbit)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  AI analyzes documentation content                        │   │
│  │  Verifies semantic accuracy:                             │   │
│  │    - Does CLAUDE.md reflect actual changes?              │   │
│  │    - Is the ADR well-structured?                         │   │
│  │    - Does JOURNEY.md explain "why"?                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Non-Deterministic: Cannot reliably block (flaky)               │
│  Action: WARN only, never block                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why Hybrid?

| Gate | Type | Can Block? | Purpose |
|------|------|------------|---------|
| Hard (DangerJS) | Deterministic | ✅ Yes | Ensure files are updated |
| Soft (CodeRabbit) | Probabilistic | ❌ No | Verify content quality |

**Critical Insight from Research:**
> "Temperature 0 does not guarantee determinism in LLMs. You cannot rely on an LLM to reliably block a build."

---

## Rationale

### Tool Selection: DangerJS

| Criteria | DangerJS | OPA/Conftest | Python Script |
|----------|----------|--------------|---------------|
| Learning Curve | Low (TypeScript) | High (Rego) | Low (Python) |
| GitHub Integration | Native | Requires wrapper | Manual |
| PR Comments | Built-in | Manual | Manual |
| Maintainability | High | Low | Medium |
| **Score** | **4.8/5** | **3.0/5** | **4.0/5** |

### Policy-as-Code Approach

Policies are defined in `.github/doc-policy.json`, not hardcoded in scripts:
- **Separation of Concerns:** Policy definition vs. enforcement mechanism
- **Maintainability:** Non-developers can update rules
- **Auditability:** Clear record of what's enforced

### Security Considerations

| Risk | Mitigation |
|------|------------|
| tj-actions/changed-files compromise (March 2025) | Use DangerJS instead of third-party actions |
| Mutable action tags | Audit all actions; prefer stable versions |
| Prompt injection in AI reviewer | AI has comment-only permissions, cannot merge |

---

## Implementation

### Components Created

| File | Purpose | Lines |
|------|---------|-------|
| `.github/doc-policy.json` | Policy rules definition | 100+ |
| `dangerfile.ts` | Hard Gate enforcement logic | 180+ |
| `.github/workflows/enforce-docs.yml` | CI workflow | 80+ |
| `.coderabbit.yaml` | Soft Gate configuration | 100+ |

### Policy Rules

| ID | Trigger | Requires | Severity |
|----|---------|----------|----------|
| layer1-context-sync | src/**/*.py, railway.toml | CLAUDE.md | fail |
| layer2-adr-journey | docs/decisions/ADR-*.md | docs/JOURNEY.md | fail |
| layer2-skill-claude | .claude/skills/**/SKILL.md | CLAUDE.md | fail |
| layer4-changelog | src/**/*.py | docs/changelog.md | fail |
| layer3-significant-changes | src/**/*.py (100+ lines) | docs/JOURNEY.md | warn |

### Escape Hatches

Labels that bypass enforcement:
- `skip-docs` - For hotfixes
- `hotfix` - Emergency fixes
- `typo-fix` - Minor corrections

---

## Consequences

### Positive

1. **Zero manual verification needed** - CI enforces documentation completeness
2. **Context Drift prevented** - AI agent always has accurate context
3. **Clear feedback** - DangerJS posts detailed comments on PRs
4. **Maintainable** - Policies in JSON, not hardcoded
5. **Industry-standard approach** - Based on 2026 best practices

### Negative / Risks

| Risk | Mitigation |
|------|------------|
| False positives block legitimate PRs | Escape hatch labels available |
| DangerJS adds CI time (~30s) | Acceptable tradeoff for integrity |
| Learning curve for contributors | Clear error messages with guidance |

### Cost / Complexity

| Aspect | Value |
|--------|-------|
| Development time | 2-3 hours |
| CI time added | ~30 seconds per PR |
| Maintenance | Low (policy file updates only) |
| Dependencies | danger, minimatch (npm) |

---

## Success Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| User documentation verifications | 1+/week | 0 | User reports |
| Documentation completeness failures | Unknown | <5% of PRs | CI metrics |
| Context drift incidents | 1 (JOURNEY.md miss) | 0 | Incident tracking |

---

## Alternatives Considered

### Option A: OPA/Conftest
- **Rejected:** High learning curve (Rego), overkill for solo developer
- **Score:** 3.0/5

### Option B: Pure Python Script
- **Rejected:** Lacks built-in PR commenting, more boilerplate
- **Score:** 4.0/5

### Option C: No automation (status quo)
- **Rejected:** Proven to cause context drift (JOURNEY.md incident)

---

## References

### Internal
- ADR-002: Dual Documentation Strategy
- ADR-011: ADR Architect Structured Request Processing
- `.github/doc-policy.json`: Policy definition
- `dangerfile.ts`: Enforcement implementation

### External Research
- Deep Research: "Context Integrity Assurance: A Policy-as-Code Architecture for Autonomous AI Systems" (2026-01-22)
- [DangerJS Documentation](https://danger.systems/js/)
- [CodeRabbit Configuration](https://docs.coderabbit.ai/)
- [OPA CI/CD Integration](https://www.openpolicyagent.org/docs/cicd)

### Case Studies Referenced
- Twenty CRM (DangerJS usage)
- Storybook (Label enforcement)
- Turborepo Boundaries (conceptual mapping)

---

## Update Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-22 | Claude Code | Initial ADR creation based on Deep Research |
