# ADR-017: AI Landing Page Factory (3D Framework)

**Status:** Proposed
**Date:** 2026-01-25
**Decision Makers:** User (edri2or-commits), Claude Code Agent

---

## Context

### Problem Statement

Creating landing pages is a manual, time-intensive process:
1. Extract design tokens from reference sites (colors, fonts, spacing)
2. Configure Tailwind CSS based on extracted tokens
3. Build React/Next.js components that match the design
4. Deploy and optimize for SEO

**Current State:**
- No design extraction capability in project38
- No UI/frontend code generation
- `src/factory/generator.py` generates agent code only, not UI
- `src/mcp/browser.py` can navigate/screenshot but cannot extract design tokens

### Research Discovery

Research document "AI-Driven Landing Page Factory" (analyzed 2026-01-25) proposes the **3D Framework**:

```
DESIGN → DEVELOP → DEPLOY
   ↓         ↓         ↓
Firecrawl  Cursor   Next.js ISR
```

**Verified Claims (Truth Protocol):**

| Claim | Verification | Source |
|-------|-------------|--------|
| Firecrawl has `formats=['branding']` | ✅ Confirmed | [GitHub v2.6.0](https://github.com/firecrawl/firecrawl/releases/tag/v2.6.0) |
| Gemini 3 released Nov 2025 | ✅ Confirmed | [Google Blog](https://blog.google/products/gemini/gemini-3/) |
| Firecrawl: $16/5k pages | ✅ Confirmed | [eesel.ai](https://www.eesel.ai/blog/firecrawl-pricing) |
| Gemini 3 context: 1M tokens | ✅ Confirmed | [Google Blog](https://blog.google/products/gemini/gemini-3-flash/) |

### System Mapping (ADR-009 Compliance)

| Research Concept | Existing Module | Overlap | Decision |
|-----------------|-----------------|---------|----------|
| Design token extraction | `src/mcp/browser.py` (490 lines) | 20% | **EXTEND** |
| Code generation | `src/factory/generator.py` (189 lines) | 30% | **EXTEND** |
| Cursor rules generation | None | 0% | **CREATE NEW** |
| LLM routing (Gemini) | `services/litellm-gateway/` | 90% | Config change |
| Next.js ISR automation | None | 0% | **CREATE NEW** |

**Overall Overlap:** 15-20%

---

## Decision

### Option A: Full Firecrawl Integration (Rejected)

**Approach:** Use Firecrawl's `branding` API as external service

**Pros:**
- Production-ready API
- Handles complex JS-rendered SPAs
- Well-documented

**Cons:**
- Recurring cost: $16-333/month
- External dependency
- Less control over extraction logic

**Cost Analysis:**
- 100 sites/month: $16/month (Hobby tier covers it)
- 1,000 sites/month: $83/month (Standard tier)

### Option B: DIY Design Extraction (Selected)

**Approach:** Extend existing `src/mcp/browser.py` with Claude-based CSS analysis

**Pros:**
- No external dependency
- One-time development cost
- Full control over extraction
- Uses existing infrastructure

**Cons:**
- Development effort: 14-22 hours
- May miss edge cases initially

**Cost Analysis:**
- Per-site: $0.01-0.05 (Claude API only)
- 1,000 sites: ~$50 vs $83 for Firecrawl

### Option C: Hybrid (Future Consideration)

Use DIY for simple sites, Firecrawl for complex SPAs. Deferred until DIY is validated.

---

## Implementation Plan

### Phase 1: Design Extraction (14-22 hours)

**Objective:** Extract design tokens from any URL

**Deliverables:**

| File | Description | Est. Lines |
|------|-------------|------------|
| `src/factory/design_extractor.py` | CSS analysis via Claude | ~200 |
| `src/factory/cursor_rules_generator.py` | Generate `.cursorrules` | ~150 |

**Architecture:**

```
URL → browser_navigate() → browser_screenshot() + DOM
                                    ↓
                          Claude Sonnet Analysis
                                    ↓
                          Design Tokens JSON
                          {
                            colors: {...},
                            typography: {...},
                            spacing: {...},
                            components: {...}
                          }
```

**Success Criteria:**
- [ ] Extract colors from 90%+ of sites
- [ ] Extract typography from 80%+ of sites
- [ ] Generate valid `tailwind.config.js`

### Phase 2: UI Component Generation (20-30 hours)

**Objective:** Generate React components from design tokens

**Deliverables:**

| File | Description | Est. Lines |
|------|-------------|------------|
| `src/factory/ui_generator.py` | Component generation logic | ~400 |
| `src/factory/templates/` | Tailwind + shadcn templates | ~800 |

**Architecture:**

```
Design Tokens + Content Spec
           ↓
    Gemini 3 / Claude
           ↓
    React Components (TSX)
    + tailwind.config.js
    + .cursorrules
```

**Success Criteria:**
- [ ] Generate valid React components
- [ ] Components pass accessibility checks
- [ ] Lighthouse performance > 90

### Phase 3: pSEO Automation (30-50 hours)

**Objective:** Mass-produce SEO-optimized landing pages

**Deliverables:**

| File | Description | Est. Lines |
|------|-------------|------------|
| `src/factory/pseo_generator.py` | Programmatic SEO engine | ~600 |
| `src/factory/templates/nextjs-isr/` | Next.js ISR templates | ~400 |
| `src/factory/deployment.py` | Vercel/Railway deployment | ~300 |

**Architecture:**

```
Keyword Database
       ↓
 Content Generation (Gemini)
       ↓
 Page Rendering (Next.js ISR)
       ↓
 Deployment (Vercel/Railway)
```

**ISR Strategy (from research):**

| Page Volume | Strategy | Build Time |
|-------------|----------|------------|
| < 1,000 | SSG (all paths) | ~10 min |
| 1,000 - 10k | Hybrid (top 10%) | ~3 min |
| > 10,000 | ISR (empty array) | ~1 min |

**Success Criteria:**
- [ ] Generate 1,000+ pages without memory issues
- [ ] First-paint < 1.5s for ISR pages
- [ ] SEO metadata generation accurate

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| CSS extraction fails on complex sites | Medium | Medium | Fallback to Firecrawl for edge cases |
| LLM hallucination in code generation | Medium | High | Strict validation, ESLint, TypeScript |
| Memory issues at scale (pSEO) | Low | High | Use ISR with empty `generateStaticParams` |

### Legal Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Trade Dress infringement | Low | High | Extract tokens only, apply different brand |
| Copyright (code copying) | Low | Medium | Generate new code, don't copy source |

**Legal Note:** This ADR does NOT constitute legal advice. Consult attorney before commercial use of generated designs.

---

## Resource Estimates

| Phase | Hours | New LOC | Dependencies |
|-------|-------|---------|--------------|
| Phase 1 | 14-22 | ~350 | None (uses existing) |
| Phase 2 | 20-30 | ~1,200 | shadcn/ui templates |
| Phase 3 | 30-50 | ~1,300 | Next.js 15, Vercel SDK |
| **Total** | **64-102** | **~2,850** | |

**Timeline:** Not specified (user decides scheduling)

---

## Acceptance Criteria

### Phase 1 Complete When:
- [ ] `src/factory/design_extractor.py` exists and tested
- [ ] Can extract design tokens from 10 test URLs
- [ ] Generates valid `tailwind.config.js`
- [ ] Unit tests pass (>80% coverage)

### Phase 2 Complete When:
- [ ] `src/factory/ui_generator.py` exists and tested
- [ ] Generates valid React/TSX components
- [ ] Components render without errors
- [ ] Lighthouse accessibility > 90

### Phase 3 Complete When:
- [ ] pSEO pipeline generates 100+ pages
- [ ] ISR deployment works on Vercel/Railway
- [ ] No memory issues at scale

---

## Related

- **Research Note:** `docs/research/notes/2026-01-25-ai-landing-page-factory.md`
- **ADR-009:** Research Integration Architecture (process followed)
- **ADR-010:** Multi-LLM Routing (Gemini integration)
- **Experiment:** exp_004_design_extraction (proposed)

---

## Decision Record

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-25 | Select Option B (DIY) | Lower recurring cost, uses existing infrastructure |
| 2026-01-25 | Defer Phase 3 until Phase 1-2 validated | Reduce risk, incremental approach |

---

## Appendix: Verified External Sources

| Source | URL | Accessed |
|--------|-----|----------|
| Firecrawl v2.6.0 Release | https://github.com/firecrawl/firecrawl/releases/tag/v2.6.0 | 2026-01-25 |
| Google Gemini 3 Blog | https://blog.google/products/gemini/gemini-3/ | 2026-01-25 |
| Firecrawl Pricing Analysis | https://www.eesel.ai/blog/firecrawl-pricing | 2026-01-25 |
| Gemini 3 Flash Blog | https://blog.google/products/gemini/gemini-3-flash/ | 2026-01-25 |
