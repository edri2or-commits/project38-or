# Experiment 007: Design Extraction POC

**Status:** Active
**Date:** 2026-01-26
**Related:** ADR-017 (AI Landing Page Factory), Phase 1

## Purpose

Minimal POC to validate DIY design extraction approach (Option B from ADR-017).
Takes a URL and returns design tokens (colors, fonts, style) using Claude Vision.

## Usage

```bash
# From project root
cd experiments/exp_007_design_extraction_poc

# Run extraction
python extract_design.py https://stripe.com
```

## Requirements

```bash
pip install playwright anthropic
playwright install chromium
```

## Output

Returns JSON with:
- `dominant_colors`: List of hex colors with usage (primary/secondary/etc)
- `fonts`: Heading and body font families
- `style`: Overall style description (minimal/corporate/playful/etc)
- `layout`: Layout type and column count

## Example Output

```json
{
  "dominant_colors": [
    {"hex": "#635BFF", "usage": "primary", "percentage": 15},
    {"hex": "#0A2540", "usage": "text", "percentage": 20},
    {"hex": "#FFFFFF", "usage": "background", "percentage": 45}
  ],
  "fonts": {
    "headings": "Inter",
    "body": "Inter"
  },
  "style": {
    "overall": "minimal",
    "has_gradients": true,
    "has_shadows": true,
    "border_radius": "medium"
  }
}
```

## Cost

- Screenshot: Free (local Playwright)
- Claude Vision: ~$0.01-0.03 per analysis (depends on image size)

## Success Criteria

- [ ] Extracts 3+ dominant colors with reasonable accuracy
- [ ] Identifies primary brand color correctly
- [ ] Works on 90%+ of standard websites
- [ ] Completes in <30 seconds

## Files

- `extract_design.py` - Main extraction script
- `last_screenshot.png` - Most recent screenshot (for debugging)
- `last_result.json` - Most recent extraction result
