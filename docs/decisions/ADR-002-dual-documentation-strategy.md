# ADR-002: Dual Documentation Strategy

**Date**: 2026-01-12
**Status**: Accepted
**Deciders**: User (edri2or-commits), Claude AI Agent
**Tags**: documentation, architecture, knowledge-management

---

## Context

Following the research synthesis decision (ADR-001), we needed a concrete documentation structure that serves multiple audiences:

1. **AI Agents** (Claude sessions): Need quick bootstrap context + deep technical details
2. **Human Developers**: Need narrative understanding + API references
3. **Future Maintainers**: Need decision history + architectural rationale

### Industry Context (2026)

Research revealed critical trends:
- **75% of developers** use MCP (Model Context Protocol) servers for AI tools
- **"Most agent failures are context failures"** - LangChain State of Agents Report
- **Context Engineering** is now treated as infrastructure, not optional documentation
- **ADR standard** adopted by AWS, Azure, Google Cloud for architecture decisions

**Sources**:
- [Document360 AI Trends 2026](https://document360.com/blog/ai-documentation-trends/)
- [LangChain State of Agents](https://www.langchain.com/state-of-agent-engineering)

---

## Decision

**We implement a 4-layer context architecture**:

### Layer 1: Quick Context (`CLAUDE.md`)
**Purpose**: Session bootstrap, file structure, quick reference
**Format**: Markdown guide checked into codebase
**Audience**: AI agents starting new sessions, developers onboarding
**Size**: Single 1,286-line file

**Key Sections**:
- Project overview
- Security rules (non-negotiable)
- GCP configuration
- File structure (includes integrations/ and autonomous/)
- Available skills
- Railway deployment status

### Layer 2: Decision Records (`docs/decisions/`)
**Purpose**: Architectural decisions with rationale, alternatives, consequences
**Format**: ADR standard (Date, Status, Context, Decision, Consequences, Alternatives)
**Audience**: Architects, future maintainers, audit/compliance
**Update Frequency**: Per major decision

**Current ADRs**:
- ADR-001: Research Synthesis Approach
- ADR-002: Dual Documentation Strategy (this document)
- ADR-003: Railway Autonomous Control

### Layer 3: Journey Documentation (`docs/JOURNEY.md`)
**Purpose**: Narrative timeline of major milestones, WHY behind the project
**Format**: Chronological markdown with dates, decisions, learnings
**Audience**: New team members, stakeholders, historical reference
**Update Frequency**: After major milestones

### Layer 4: Technical Artifacts
**Purpose**: Deep technical details, API references, working code

**Structure**:
```
docs/
├── integrations/         # Original research (203KB)
│   ├── implementation-roadmap.md    # 7-day plan
│   ├── railway-api-guide.md        # Railway GraphQL API
│   ├── github-app-setup.md         # GitHub App JWT auth
│   ├── n8n-integration.md          # n8n workflows
│   └── autonomous-architecture.md   # System design
│
└── autonomous/           # Hybrid synthesis (208KB)
    ├── 00-autonomous-philosophy.md     # Theory + ethics
    ├── 01-system-architecture-hybrid.md # Design + code
    ├── 02-railway-integration-hybrid.md # Railway + impl
    ├── 03-github-app-integration-hybrid.md # GitHub + impl
    ├── 04-n8n-orchestration-hybrid.md  # n8n + impl
    ├── 05-resilience-patterns-hybrid.md # Patterns + code
    ├── 06-security-architecture-hybrid.md # Security + impl
    └── 07-operational-scenarios-hybrid.md # Scenarios + code
```

---

## Consequences

### Positive

✅ **Multi-Audience Support**: Each layer optimized for specific use case
✅ **Context Preservation**: AI agents never lose historical context between sessions
✅ **Industry Alignment**: Follows AWS/Azure/Google Cloud ADR standards
✅ **Layered Complexity**: Quick start (Layer 1) → Deep dive (Layer 4)
✅ **Maintainability**: Changes documented in Layer 2 (ADRs), tracked in Layer 3 (JOURNEY)
✅ **Audit Trail**: Complete decision history for compliance/governance

### Negative

⚠️ **Documentation Overhead**: 4 layers require discipline to maintain
⚠️ **Learning Curve**: Contributors need to understand layer purposes
⚠️ **Sync Risk**: Updates may not propagate across all layers

### Mitigation

- **CLAUDE.md references all layers**: "See ADR-XXX for rationale"
- **Changelog ties layers together**: Single entry references multiple files
- **CI validation**: docs-check.yml ensures changelog updated when docs/ changes

---

## Alternatives Considered

### Alternative 1: Single-Layer (CLAUDE.md only)

**Pros**: Simple, one source of truth
**Cons**: Mixes concerns, loses decision history, becomes unmaintainable
**Rejected**: Fails at scale (CLAUDE.md already 1,286 lines)

### Alternative 2: Wiki/Confluence

**Pros**: Rich UI, version control, search
**Cons**: Context separated from code, not AI-agent friendly, requires external auth
**Rejected**: Violates "docs as code" principle, harder for MCP integration

### Alternative 3: Three Layers (no JOURNEY.md)

**Pros**: Less overhead
**Cons**: Loses narrative, hard to answer "how did we get here?"
**Rejected**: 2026 research emphasizes narrative understanding for knowledge transfer

### Alternative 4: Git Commit Messages as Context

**Pros**: Already exists, no extra work
**Cons**: Fragmented, hard to query, no high-level narrative
**Rejected**: Commits are atomic, not architectural

---

## Implementation Notes

### For AI Agents

**Session Start**:
1. Read CLAUDE.md (Layer 1) → Get current state
2. Check docs/decisions/ (Layer 2) → Understand WHY
3. Reference docs/JOURNEY.md (Layer 3) → Get timeline
4. Deep dive docs/autonomous/ or docs/integrations/ (Layer 4) → Technical details

### For Humans

**Onboarding**:
1. Start with docs/JOURNEY.md → Understand the story
2. Read CLAUDE.md → Get quick reference
3. Review ADRs in docs/decisions/ → Understand key decisions
4. Explore docs/autonomous/ → Learn the system

### For Updates

**When adding feature**:
1. Update Layer 4 (technical artifacts)
2. Create ADR if architectural (Layer 2)
3. Update JOURNEY.md if milestone (Layer 3)
4. Update CLAUDE.md if structure changed (Layer 1)
5. Update changelog.md (ties all together)

---

## Success Metrics

- ✅ New AI agent sessions understand context within 1 CLAUDE.md read
- ✅ Developers onboard with <30 min JOURNEY.md read
- ✅ Zero "Why does this directory exist?" questions
- ✅ ADRs referenced in code reviews when decisions questioned
- ✅ Context preserved across 100+ AI sessions

---

## Related Decisions

- ADR-001: Research Synthesis Approach (why dual docs/)
- ADR-003: Railway Autonomous Control (applies this structure)

---

## References

- [Context Engineering 2026](https://codeconductor.ai/blog/context-engineering/)
- [AWS ADR Process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
- [Azure ADR Guide](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)
- [Google Cloud ADR](https://docs.cloud.google.com/architecture/architecture-decision-records)
- [Document360 AI Documentation Trends](https://document360.com/blog/ai-documentation-trends/)
- [LangChain State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering)
