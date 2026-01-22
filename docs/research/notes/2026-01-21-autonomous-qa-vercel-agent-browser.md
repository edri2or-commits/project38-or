# Research Note: Autonomous QA with Vercel Agent Browser CLI

**Date:** 2026-01-21
**Author:** Claude (via user research submission)
**Status:** Draft

---

## Source

- **Type:** Research Document / Architecture Proposal
- **URL:** User-provided document (not public URL)
- **Title:** ארכיטקטורה מקיפה ותכנית ביצוע לתשתית QA אוטונומית מבוססת סוכני AI (Scriptless Testing)
- **Creator/Author:** Unknown (research compilation)
- **Date Published:** 2026 (estimated)

---

## Summary

1. **What is it?** A comprehensive architecture for autonomous web testing using AI agents with Vercel Agent Browser CLI, which converts DOM to Accessibility Tree for 93% token reduction.

2. **Why is it interesting?** Enables AI agents to navigate web UIs autonomously - clicking buttons, filling forms, reading screens - without brittle CSS selectors.

3. **What problem does it solve?** Extends AI agent autonomy beyond API-only interactions to full browser-based operations (dashboards, UIs without APIs).

---

## Relevance to Our System

_Check all that apply:_

- [ ] **Model Layer** - New models, prompting techniques, fine-tuning
- [x] **Tool Layer** - New tools, integrations, capabilities
- [x] **Orchestration** - Multi-agent, workflows, state management
- [ ] **Knowledge/Prompts** - Context management, RAG, memory
- [x] **Infrastructure** - Deployment, scaling, monitoring
- [x] **Evaluation** - Testing, benchmarks, quality metrics

---

## Hypothesis

> If we integrate Vercel Agent Browser CLI into Claude Code's toolset, then autonomous operations coverage will increase by 50%+ (from API-only to API+UI).

---

## Impact Estimate

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| **Scope** | System-wide | Affects all dashboard/UI interactions |
| **Effort** | Weeks | Need to setup CLI, integrate with MCP, create prompts |
| **Risk** | Medium | Browser automation can be flaky; token costs |
| **Reversibility** | Easy | Additive capability, doesn't replace existing |

---

## Current State (Before)

- Current approach: API-only interactions (Railway GraphQL, GitHub API, n8n webhooks)
- Current metrics:
  - Quality: Good for API-available operations
  - Latency: Fast (direct API calls)
  - Cost: Low (no browser overhead)
- Known limitations:
  - Cannot interact with UIs that lack APIs
  - Cannot read dashboards visually (Railway Dashboard, status pages)
  - Cannot perform click-based operations (delete buttons, etc.)

---

## Proposed Change (After)

- New approach: Hybrid API + Browser automation using Vercel Agent Browser CLI
- Expected metrics:
  - Quality: Higher coverage (API + UI operations)
  - Latency: Slower for UI ops (browser startup, rendering)
  - Cost: Higher (tokens for Accessibility Tree, browser resources)
- Benefits:
  - Full autonomy over web dashboards
  - Can read status pages directly
  - Can perform UI-only operations
  - Scriptless - adapts to UI changes automatically
- Risks:
  - Browser flakiness
  - Token cost for complex pages
  - Security (browser access to sensitive UIs)

---

## Questions to Answer

1. Is Vercel Agent Browser CLI compatible with Claude Code's MCP architecture?
2. What is the token cost per typical dashboard interaction?
3. Can we run headless browser in GitHub Actions / Railway?
4. How do we handle authentication (session injection vs. login flow)?

---

## Next Action

_Select ONE:_

- [x] **Spike** - Create experiment, run isolated test
- [ ] **ADR** - Create architecture decision record
- [ ] **Backlog** - Add to future work, not urgent
- [ ] **Discard** - Not relevant, archive this note

**Reason for decision:** Directly addresses a limitation discovered during Railway troubleshooting (2026-01-21) - inability to interact with Railway Dashboard UI to delete orphaned instances. Worth testing in isolation before committing to full integration.

---

## Triage Notes

_Filled during weekly review._

**Reviewed:** 2026-01-21
**Decision:** Spike
**Issue/PR:** ISSUE-0003
**Experiment ID:** exp_003_vercel_agent_browser

---

## Related

- Related ADRs: ADR-003 (Railway Autonomous Control), ADR-006 (GCP Agent Autonomy)
- Related experiments: [exp_003_vercel_agent_browser](../../../experiments/exp_003_vercel_agent_browser/)
- Related research notes: None yet
- Related issues: [ISSUE-0003](../issues/ISSUE-0003.md)

---

## Key Technical Details from Research

### Vercel Agent Browser CLI
- Converts DOM to Accessibility Tree (93% token reduction)
- Uses Reference IDs (@e1, @e2) instead of CSS selectors
- Commands: `snapshot`, `click`, `fill`, `scroll`, `navigate`

### Token Economics (from research)
| Method | Tokens/Step | Cost/Step |
|--------|-------------|-----------|
| Traditional (DOM + GPT-4o) | ~60,000 | ~$0.30 |
| Vercel Agent + Claude 3.5 | ~3,500 | ~$0.01 |

### Loop Prevention
- State machine tracking last 10 actions
- Snapshot hash comparison
- Confidence score threshold (60%)
- Recovery strategies (prompt injection, jitter, fail-safe)

### Security Considerations
- Session injection instead of UI login
- Sanitization layer for PII before sending to LLM
- Service accounts with API tokens preferred
