# Experiment: Vercel Agent Browser - Autonomous UI Navigation

**ID:** exp_003
**Date:** 2026-01-21
**Status:** Planning
**Research Note:** [docs/research/notes/2026-01-21-autonomous-qa-vercel-agent-browser.md](../../docs/research/notes/2026-01-21-autonomous-qa-vercel-agent-browser.md)

## Hypothesis

> If we integrate Vercel Agent Browser CLI for UI interactions, then autonomous operations coverage will increase by 50%+ (from API-only to API+UI) while maintaining acceptable token costs (<$0.05 per complex operation).

## Problem Statement

Current limitations discovered during Railway troubleshooting (2026-01-21):
- Cannot interact with UIs that lack APIs (Railway Dashboard delete operations)
- Cannot read status pages visually
- Cannot perform click-based operations (buttons, dropdowns, modals)

## Success Criteria

Define BEFORE running:

| Metric | Baseline (API-only) | Target | Must Meet |
|--------|---------------------|--------|-----------|
| Operations Coverage | 60% (API available) | >= 90% | Yes |
| Token Cost per Step | N/A (no browser) | <= $0.02 | Yes |
| Success Rate | N/A | >= 85% | Yes |
| Avg Latency per Step | N/A | <= 5s | No |
| Loop Detection Rate | N/A | >= 95% | Yes |

## Test Cases

### Phase 1: Basic Navigation (5 cases)
1. Navigate to Railway Dashboard login page
2. Read deployment status from Railway Dashboard
3. Read service list from project overview
4. Navigate to deployment logs page
5. Read environment variable names (not values)

### Phase 2: Interactive Operations (5 cases)
1. Click "Redeploy" button (dry-run)
2. Open service settings modal
3. Navigate through pagination
4. Filter deployments by status
5. Expand/collapse service details

### Phase 3: Complex Workflows (3 cases)
1. Find and identify stuck deployment
2. Navigate to delete confirmation dialog
3. Full workflow: Login → Find Service → Check Status → Return

**Total Cases:** 13
**Categories:** Navigation, Reading, Clicking, Complex Workflows

## Technical Approach

### Vercel Agent Browser CLI

From research note - key features:
- Converts DOM to Accessibility Tree (93% token reduction)
- Uses Reference IDs (@e1, @e2) instead of CSS selectors
- Commands: `snapshot`, `click`, `fill`, `scroll`, `navigate`

### Token Economics (from research)

| Method | Tokens/Step | Cost/Step |
|--------|-------------|-----------|
| Traditional (DOM + GPT-4o) | ~60,000 | ~$0.30 |
| Vercel Agent + Claude 3.5 | ~3,500 | ~$0.01 |

### Architecture

```
Claude Code Session
    ↓ (Tool call: browser_navigate, browser_click, etc.)
MCP Browser Tool (new)
    ↓ (Subprocess)
Vercel Agent Browser CLI
    ↓ (Playwright/Puppeteer)
Target Website (Railway Dashboard, etc.)
    ↓ (Accessibility Tree snapshot)
Claude Code (action decision)
```

## Setup

### Prerequisites

```bash
# Install Vercel Agent Browser CLI (TBD - verify package name)
npm install -g @anthropic/agentkit  # or similar

# Or use Playwright directly with accessibility tree
pip install playwright
playwright install chromium
```

### Environment Variables

```bash
# Railway credentials for dashboard access
RAILWAY_SESSION_TOKEN=...  # For session injection (preferred)
# OR
RAILWAY_EMAIL=...
RAILWAY_PASSWORD=...  # For login flow (less secure)
```

### Run Experiment

```bash
# Phase 1: Basic navigation tests
python experiments/exp_003_vercel_agent_browser/run.py --phase 1

# Phase 2: Interactive tests (dry-run)
python experiments/exp_003_vercel_agent_browser/run.py --phase 2 --dry-run

# Full experiment
python experiments/exp_003_vercel_agent_browser/run.py --all
```

## Implementation Plan

### Step 1: Browser Tool Skeleton
- [ ] Create `src/mcp/browser_agent.py` with Playwright base
- [ ] Implement Accessibility Tree extraction
- [ ] Add basic commands: navigate, snapshot, click

### Step 2: Loop Prevention
- [ ] State machine tracking last 10 actions
- [ ] Snapshot hash comparison
- [ ] Confidence score threshold (60%)

### Step 3: MCP Integration
- [ ] Register browser tools in MCP Gateway
- [ ] Add to tool registry
- [ ] Test from Claude Code session

### Step 4: Test Cases
- [ ] Run Phase 1 tests
- [ ] Run Phase 2 tests (dry-run first)
- [ ] Run Phase 3 complex workflows

## Results

_Filled after experiment completes_

| Metric | Baseline | Actual | Delta | Pass? |
|--------|----------|--------|-------|-------|
| Operations Coverage | 60% | - | - | - |
| Token Cost per Step | N/A | - | - | - |
| Success Rate | N/A | - | - | - |
| Avg Latency per Step | N/A | - | - | - |
| Loop Detection Rate | N/A | - | - | - |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Browser flakiness | Medium | Retry logic, screenshot on failure |
| High token cost | High | Accessibility Tree (93% reduction) |
| Auth complexity | Medium | Session injection > login flow |
| UI changes break tests | Medium | Use ARIA labels, not CSS selectors |
| Security (browser access) | High | Service accounts, sanitize PII |

## Conclusion

**Decision:** _TBD_

**Reasoning:** _TBD_

## Next Steps

- [ ] Install and verify Vercel Agent Browser CLI availability
- [ ] Create browser_agent.py skeleton
- [ ] Run Phase 1 tests
- [ ] Document results and make ADOPT/REJECT decision

## References

- Research Note: `docs/research/notes/2026-01-21-autonomous-qa-vercel-agent-browser.md`
- ADR-009: Research Integration Architecture
- Vercel Agent Browser: https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo
- Playwright Accessibility: https://playwright.dev/python/docs/accessibility
