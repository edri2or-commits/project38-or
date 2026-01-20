# Research Note: 2026 Agent Interop Standards Landscape

**Date:** 2026-01-20
**Author:** Claude Code Agent
**Status:** Triaged (Spike)

---

## Source

- **Type:** Discovery
- **URL:** N/A
- **Title:** 2026 Agent Interop Standards Landscape
- **Creator/Author:** Unknown
- **Date Published:** Unknown

---

## Summary

1. MCP (Model Context Protocol) - For tool connectivity
2. AGENTS.md - For project context and agent onboarding
3. Agent Skills - For portable capability definitions

---

## Relevance to Our System

- [x] **Model Layer**
- [ ] **Tool Layer**
- [ ] **Orchestration**
- [ ] **Knowledge/Prompts**
- [ ] **Infrastructure**
- [ ] **Evaluation**

---

## Hypothesis

> Hypothesis: Combining MCP (tool connectivity) + AGENTS.

---

## Impact Estimate

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| **Scope** | Model | Model layer |
| **Effort** | Weeks | Estimated implementation time |
| **Risk** | Medium | Based on scope and effort |
| **Reversibility** | Moderate | Needs planning |

---

## Current State (Before)

- Current approach: [To be analyzed]
- Current metrics: [To be measured]
- Known limitations: [To be documented]

---

## Proposed Change (After)

- New approach: Based on this research
- Expected metrics: [To be evaluated]
- Benefits: [To be determined]
- Risks: Medium

---

## Questions to Answer

1. What is the actual impact on our system?
2. How does this compare to our current approach?
3. What is the cost/benefit ratio?

---

## Next Action

- [x] **Spike** - Create experiment, run isolated test
- [ ] **ADR** - Create architecture decision record
- [ ] **Backlog** - Add to future work, not urgent
- [ ] **Discard** - Not relevant, archive this note

**Auto-Recommendation:** Spike
**Reason:** Model change with hypothesis needs experiment

---

## Triage Notes

**Reviewed:** 2026-01-20
**Decision:** Spike
**Reason:** Explicit recommendation: Spike
**Issue/PR:** #1
**Experiment ID:** exp_001_2026_agent_interop_standards_l

---

## Related

- Related ADRs: ADR-009 (Research Integration Architecture)
- Related experiments: None yet
- Related research notes: None yet

---

## User Input (Preserved)

**Source:** 
**Description:** MCP Transports + AGENTS.md + Agent Skills - Vendor Adoption + Implementation Blueprint
**Why Relevant:** Not specified

---

## Raw Research Text

<details>
<summary>Click to expand full research text</summary>


# 2026 Agent Interop Standards Landscape

## Executive Summary

The agentic AI ecosystem in 2026 has consolidated around three key interoperability standards:
1. MCP (Model Context Protocol) - For tool connectivity
2. AGENTS.md - For project context and agent onboarding
3. Agent Skills - For portable capability definitions

## MCP Transports Evolution

### Transport Options
1. **stdio** - Local process communication (original)
2. **SSE (Server-Sent Events)** - HTTP-based streaming (2024)
3. **Streamable HTTP** - Bidirectional streaming over HTTP (2025/2026)

### Key Finding: Streamable HTTP Adoption
- Streamable HTTP is emerging as the preferred transport for cloud deployments
- Enables full bidirectional communication without WebSocket complexity
- Compatible with standard HTTP infrastructure (load balancers, proxies)
- Adoption rate: ~40% of new MCP deployments use Streamable HTTP

### Vendor Adoption
| Vendor | MCP Support | Preferred Transport |
|--------|-------------|---------------------|
| Anthropic | Native | Streamable HTTP |
| OpenAI | Via adapters | SSE |
| Google | Via Vertex | stdio |
| Microsoft | Azure AI | SSE |

## AGENTS.md Specification

### Purpose
AGENTS.md provides structured project context for AI agents entering a codebase:
- Project overview and tech stack
- Code conventions and patterns
- Security considerations
- Testing requirements

### Adoption
- 30% of GitHub projects with CI now include AGENTS.md
- Reduces agent onboarding time by estimated 60%
- Enables consistent behavior across different agent implementations

### Key Sections
1. **Project Context** - What the project does
2. **Code Style** - How to write code for this project
3. **Security Rules** - What to avoid
4. **Testing Requirements** - How to verify changes

## Agent Skills Framework

### Definition
Agent Skills are portable, version-controlled capability definitions that agents can load and execute.

### Structure
```
.claude/skills/
  skill-name/
    SKILL.md       # Definition and instructions
    templates/     # Optional templates
    examples/      # Usage examples
```

### Key Findings
1. Skills reduce repeated instructions by 80%
2. Enable consistent behavior across sessions
3. Support version control for agent capabilities
4. Allow organizations to standardize agent workflows

### Adoption Metrics
- ~25% of enterprise Claude Code deployments use custom skills
- Average organization has 5-10 custom skills
- Skills are shared via internal repositories

## Implementation Blueprint

### Phase 1: MCP Gateway (Week 1-2)
- Deploy HTTP-based MCP gateway
- Support both SSE and Streamable HTTP
- Implement authentication layer

### Phase 2: AGENTS.md Integration (Week 3)
- Create comprehensive AGENTS.md
- Include all code conventions
- Document security rules

### Phase 3: Skills Framework (Week 4-5)
- Identify repeatable workflows
- Create skill definitions
- Test and iterate

## Hypothesis

Hypothesis: Combining MCP (tool connectivity) + AGENTS.md (project context) + Agent Skills (portable capabilities) 
creates a complete interoperability stack that enables autonomous agents to:
1. Connect to any tool ecosystem (MCP)
2. Understand any codebase (AGENTS.md)
3. Execute standardized workflows (Skills)

Expected outcome: 70% reduction in agent setup time, 50% improvement in task completion accuracy.

## Conclusions

1. MCP is the de-facto standard for tool connectivity
2. AGENTS.md adoption is growing rapidly
3. Agent Skills enable workflow standardization
4. The three standards are complementary, not competing
5. Early adopters report significant productivity gains


</details>

### Extracted Metrics

- 70% reduction
- 50% improvement
