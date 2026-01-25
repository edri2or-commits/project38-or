# Experiment: Autonomous Video Generation with Remotion

**ID:** exp_006
**Date:** 2026-01-25
**Status:** Planning
**Research Note:** docs/research/notes/2026-01-25-autonomous-media-systems-claude-remotion.md
**Issue:** #617

## Hypothesis

> If we implement Claude-controlled Remotion pipelines, then we can generate production-quality videos from natural language prompts at $0.45-1.21/min cost.

## Success Criteria

| Metric | Baseline | Target | Must Meet |
|--------|----------|--------|-----------|
| Natural Language → Video | 0% | Working | Yes |
| Self-Healing Render | 0% | >= 70% | Yes |
| Cost per Minute | N/A | <= $2.00 | Yes |
| Brand Consistency | 0% | >= 90% | No |

## Overview

This experiment explores autonomous video generation using:
- **Remotion** - React-based video framework
- **Claude** - LLM for code generation and reasoning
- **MCP** - Protocol for filesystem and terminal control
- **Self-Healing Loop** - From exp_004 for error recovery

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Video Generation Pipeline                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Natural  │───▶│ Generate │───▶│  Write   │              │
│  │ Language │    │ TSX Code │    │  Files   │              │
│  └──────────┘    └──────────┘    └────┬─────┘              │
│       │                               │                     │
│       │ Claude                        │ MCP Filesystem      │
│       │                               ▼                     │
│       │                         ┌──────────┐               │
│       │                         │ Remotion │               │
│       │                         │  Render  │               │
│       │                         └────┬─────┘               │
│       │                               │                     │
│       │         ┌──────────┐         │                     │
│       │         │Self-Heal │◀────────┘                     │
│       │         │  Loop    │                                │
│       │         └────┬─────┘                                │
│       │              │                                      │
│       │              ▼                                      │
│       │         ┌──────────┐                               │
│       └────────▶│  Video   │                               │
│                 │  Output  │                                │
│                 └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

## Technical Requirements

### Remotion Setup
```bash
# Initialize Remotion project
npx create-video@latest --blank video-project

# Project structure
video-project/
├── src/
│   ├── Root.tsx           # Main composition
│   ├── Composition.tsx    # Video component
│   └── constants.ts       # Brand constants (AI-editable)
├── public/
│   ├── brand/             # Logos, fonts
│   ├── audio/             # Voiceovers, music
│   └── images/            # Background images
├── remotion.config.ts     # Remotion configuration
└── package.json
```

### MCP Configuration
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/path/to/video-project"]
    },
    "terminal": {
      "command": "npx",
      "args": ["@hdresearch/mcp-shell"]
    }
  }
}
```

## AI-Resilient Code Patterns

### Constants-First Architecture
```typescript
// constants.ts - AI edits this file
export const BRAND = {
  primaryColor: '#2563eb',
  secondaryColor: '#1e40af',
  fontFamily: 'Inter, sans-serif',
  logoUrl: staticFile('brand/logo.svg'),
};

export const VIDEO = {
  fps: 30,
  width: 1920,
  height: 1080,
  durationInFrames: 300, // 10 seconds
};
```

### Deterministic Random
```typescript
// WRONG - causes render inconsistency
const x = Math.random() * 100;

// RIGHT - deterministic across renders
import { random } from 'remotion';
const x = random('my-seed') * 100;
```

### Sequence Wrapping
```typescript
// Composition with sequences
export const MyVideo: React.FC = () => {
  return (
    <>
      <Sequence from={0} durationInFrames={90}>
        <IntroScene />
      </Sequence>
      <Sequence from={90} durationInFrames={120}>
        <MainContent />
      </Sequence>
      <Sequence from={210} durationInFrames={90}>
        <OutroScene />
      </Sequence>
    </>
  );
};
```

## Cost Analysis

| Category | Prototype | At Scale | Notes |
|----------|-----------|----------|-------|
| LLM Tokens | $0.80/min | $0.30/min | Code generation + fixes |
| TTS | $0.24/min | $0.09/min | ElevenLabs or Kokoro |
| Image Gen | $0.15/min | $0.05/min | Flux, DALL-E, etc |
| Render | $0.02/min | $0.01/min | AWS Lambda |
| **Total** | **$1.21/min** | **$0.45/min** | |

## Implementation Plan

### Phase 1: Basic Setup
- [ ] Create Remotion project structure
- [ ] Define brand constants template
- [ ] Test manual render workflow

### Phase 2: Claude Integration
- [ ] Create prompt templates for video generation
- [ ] Implement code generation workflow
- [ ] Add self-healing loop from exp_004

### Phase 3: Asset Integration
- [ ] TTS integration (voiceover generation)
- [ ] Image generation for backgrounds
- [ ] Asset injection to /public folder

### Phase 4: Production Pipeline
- [ ] Docker containerization
- [ ] Lambda deployment for parallel rendering
- [ ] CI/CD integration

## Prompt Template

```markdown
Generate a Remotion video component for:

**Topic:** [USER_TOPIC]

**Duration:** 30 seconds (900 frames at 30fps)

**Style:**
- Brand colors: {BRAND.primaryColor}, {BRAND.secondaryColor}
- Font: {BRAND.fontFamily}
- Modern, clean design

**Structure:**
1. Intro (3 seconds) - Title with fade-in
2. Main content (20 seconds) - Key points with animations
3. Outro (7 seconds) - Call to action, logo

**Requirements:**
- Use constants from constants.ts
- Use staticFile() for assets
- Use random(seed) not Math.random()
- Use Sequence for timing
- Use interpolate() for animations
- Use spring() for smooth motion

Output the complete TSX component.
```

## Files

| File | Purpose |
|------|---------|
| `README.md` | This documentation |
| `video_generator.py` | Python wrapper for orchestration |
| `prompts/` | Prompt templates for different video types |
| `templates/` | Remotion component templates |

## Results

_To be filled after experiment_

| Metric | Baseline | Actual | Delta | Pass? |
|--------|----------|--------|-------|-------|
| Natural Language → Video | 0% | | | |
| Self-Healing Render | 0% | | | |
| Cost per Minute | N/A | | | |
| Brand Consistency | 0% | | | |

## Conclusion

**Decision:** _ADOPT / REJECT / NEEDS_MORE_DATA_

**Reasoning:** _To be filled_

## References

- [Remotion Documentation](https://remotion.dev/docs)
- [MCP Protocol](https://modelcontextprotocol.io)
- [Research Note](docs/research/notes/2026-01-25-autonomous-media-systems-claude-remotion.md)
- [Self-Healing Loop (exp_004)](experiments/exp_004_self_healing_loop/)
