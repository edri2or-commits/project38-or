# Experiment: Vision-Guided Verification for Web Deployments

**ID:** exp_005
**Date:** 2026-01-25
**Status:** Running
**Research Note:** docs/research/notes/2026-01-25-autonomous-media-systems-claude-remotion.md
**Issue:** #616

## Hypothesis

> If we implement vision-guided verification for web deployments, then visual regression detection will improve and human review time will decrease by 80%.

## Success Criteria

| Metric | Baseline | Target | Must Meet |
|--------|----------|--------|-----------|
| Visual Issue Detection | 0% | >= 90% | Yes |
| False Positive Rate | N/A | <= 10% | Yes |
| Screenshot Capture Time | N/A | <= 5s | Yes |
| Fix Suggestion Accuracy | 0% | >= 70% | No |

## Pattern Description

Vision verification eliminates "blind coding" where syntactically valid code produces broken visuals:

1. **Capture** - Take screenshot of deployed page
2. **Analyze** - Claude vision analyzes against specs
3. **Detect** - Identify visual artifacts
4. **Report** - Generate structured report with issues
5. **Fix** - Suggest CSS/HTML fixes (optional)

## Visual Issues Detected

| Issue Type | Detection Method | Auto-Fix? |
|------------|------------------|-----------|
| Overlapping text | Bounding box analysis | CSS z-index/position |
| Missing elements | Expected vs actual | Alert only |
| Broken layout | Grid/flex analysis | CSS fixes |
| Color contrast | WCAG analysis | Color suggestions |
| Mobile overflow | Viewport testing | CSS overflow fixes |
| Broken images | 404/missing src | Alert only |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  VisionVerifier                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Capture  │───▶│  Upload  │───▶│ Analyze  │              │
│  │Screenshot│    │ to Claude│    │  Vision  │              │
│  └──────────┘    └──────────┘    └────┬─────┘              │
│       │                               │                     │
│       │ Playwright                    │ Claude API          │
│       │                               ▼                     │
│       │                         ┌──────────┐               │
│       │                         │  Parse   │               │
│       │                         │  Issues  │               │
│       │                         └────┬─────┘               │
│       │                               │                     │
│       │         ┌──────────┐         │                     │
│       └────────▶│  Report  │◀────────┘                     │
│                 │ + Fixes  │                                │
│                 └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

## Test Cases

1. **Healthy Page** - No issues expected
2. **Overlapping Text** - Text on top of other text
3. **Missing Image** - Broken image placeholder
4. **Mobile Overflow** - Horizontal scroll on mobile
5. **Color Contrast** - Low contrast text
6. **Production Site** - Test or-infra.com

## Setup

```bash
# Install Playwright (if not installed)
pip install playwright
playwright install chromium

# Run experiment
python experiments/exp_005_vision_verification/run.py

# Test specific URL
python experiments/exp_005_vision_verification/run.py --url https://or-infra.com
```

## Results

_Filled after experiment completes_

| Metric | Baseline | Actual | Delta | Pass? |
|--------|----------|--------|-------|-------|
| Visual Issue Detection | 0% | | | |
| False Positive Rate | N/A | | | |
| Screenshot Capture Time | N/A | | | |
| Fix Suggestion Accuracy | 0% | | | |

## Conclusion

**Decision:** _ADOPT / REJECT / NEEDS_MORE_DATA_

**Reasoning:** _To be filled_

## Next Steps

- [ ] Run with test pages containing known issues
- [ ] Test with production deployment (or-infra.com)
- [ ] Integrate with deployment workflow
- [ ] Add to CI/CD pipeline
