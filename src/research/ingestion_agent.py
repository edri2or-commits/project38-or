"""Research ingestion agent for ADR-009 Phase 5.

Converts minimal user input into full research notes:
- User provides: URL/Title + Brief description
- Agent infers: Summary, hypothesis, impact estimate, recommendation

Supports multiple input methods:
1. Direct prompt to Claude Code
2. File drop in docs/research/inbox/
3. GitHub Issue with 'research' label
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from src.research.classifier import (
    Classification,
    Effort,
    ImpactScope,
    Risk,
    auto_classify,
)


@dataclass
class ResearchInput:
    """Minimal input required from user."""

    source: str = ""  # URL or title
    description: str = ""  # Brief description (2-3 sentences)
    why_relevant: Optional[str] = None  # Optional context
    title: Optional[str] = None  # Optional explicit title
    raw_text: Optional[str] = None  # Full research text for parsing
    source_url: Optional[str] = None  # Explicit URL (separate from source)


@dataclass
class InferredFields:
    """Fields inferred by the agent."""

    source_type: str = ""
    title: str = ""
    summary: list[str] = None
    hypothesis: str = ""
    scope: Optional[ImpactScope] = None
    effort: Optional[Effort] = None
    risk: Optional[Risk] = None
    reversibility: str = ""
    recommendation: Optional[Classification] = None
    relevance_areas: list[str] = None

    def __post_init__(self):
        """Initialize list fields."""
        if self.summary is None:
            self.summary = []
        if self.relevance_areas is None:
            self.relevance_areas = []


def detect_source_type(source: str) -> str:
    """Detect the type of source from URL pattern.

    Args:
        source: URL or title string

    Returns:
        Source type string (YouTube, arXiv, Blog, Documentation, Paper, etc.)
    """
    source_lower = source.lower()

    # URL patterns
    patterns = {
        "YouTube": [
            "youtube.com",
            "youtu.be",
        ],
        "arXiv": [
            "arxiv.org",
        ],
        "Documentation": [
            "docs.",
            "/docs/",
            "documentation",
            ".readthedocs.",
        ],
        "GitHub": [
            "github.com",
        ],
        "Blog": [
            "blog.",
            "/blog/",
            "medium.com",
            "dev.to",
            "substack.com",
        ],
        "Paper": [
            "papers.",
            "/paper/",
            "openreview.net",
            "semanticscholar.org",
        ],
        "News": [
            "news.",
            "/news/",
            "techcrunch.com",
            "theverge.com",
        ],
        "Tool Release": [
            "release",
            "announcement",
            "launch",
        ],
    }

    for source_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in source_lower:
                return source_type

    # Check if it's a URL
    if source.startswith("http") or "://" in source:
        return "Web Article"

    # Default for non-URL sources
    return "Discovery"


def extract_key_findings(raw_text: str) -> list[str]:
    """Extract key findings from raw research text.

    Args:
        raw_text: Full research text

    Returns:
        List of key findings (max 5)
    """
    findings = []

    # Pattern 1: Numbered items (1. Finding, 2. Finding)
    numbered = re.findall(r"^\s*\d+[.)]\s*(.+)$", raw_text, re.MULTILINE)
    findings.extend(numbered[:3])

    # Pattern 2: Bullet points (-, *, •)
    bullets = re.findall(r"^\s*[-•*]\s*(.+)$", raw_text, re.MULTILINE)
    for bullet in bullets:
        if len(bullet) > 20 and len(bullet) < 200 and bullet not in findings:
            findings.append(bullet)
            if len(findings) >= 5:
                break

    # Pattern 3: Key phrases
    key_phrases = [
        r"key finding[s]?:\s*(.+)",
        r"result[s]?:\s*(.+)",
        r"conclusion[s]?:\s*(.+)",
        r"we found that\s*(.+)",
        r"shows that\s*(.+)",
        r"demonstrates that\s*(.+)",
    ]
    for pattern in key_phrases:
        matches = re.findall(pattern, raw_text, re.IGNORECASE)
        for match in matches:
            if match not in findings:
                findings.append(match.strip())
                if len(findings) >= 5:
                    break

    return findings[:5]


def extract_hypothesis_from_text(raw_text: str) -> str:
    """Extract or generate hypothesis from raw research text.

    Args:
        raw_text: Full research text

    Returns:
        Hypothesis string
    """
    # Look for explicit hypothesis statements
    hyp_patterns = [
        r"hypothesis[:\s]+([^.]+\.)",
        r"we hypothesize[:\s]+([^.]+\.)",
        r"our hypothesis is[:\s]+([^.]+\.)",
        r"this suggests[:\s]+([^.]+\.)",
        r"we propose[:\s]+([^.]+\.)",
        r"the claim is[:\s]+([^.]+\.)",
    ]

    for pattern in hyp_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Look for improvement claims
    improvement_patterns = [
        r"(\d+%?\s*(?:improvement|better|faster|more accurate)[^.]+\.)",
        r"(improves\s+[^.]+by\s+\d+[^.]+\.)",
        r"(achieves\s+[^.]+performance[^.]+\.)",
    ]

    for pattern in improvement_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            return f"If we adopt this approach, it may provide: {match.group(1).strip()}"

    return ""


def extract_metrics_from_text(raw_text: str) -> list[str]:
    """Extract mentioned metrics from research text.

    Args:
        raw_text: Full research text

    Returns:
        List of metrics mentioned
    """
    metrics = []

    # Percentage improvements
    pct_matches = re.findall(r"(\d+(?:\.\d+)?%\s*(?:improvement|increase|decrease|better|faster|reduction))", raw_text, re.IGNORECASE)
    metrics.extend(pct_matches)

    # X times improvements
    times_matches = re.findall(r"(\d+(?:\.\d+)?x\s*(?:faster|slower|better|improvement))", raw_text, re.IGNORECASE)
    metrics.extend(times_matches)

    # Latency/performance
    latency_matches = re.findall(r"(\d+(?:\.\d+)?\s*(?:ms|seconds?|minutes?)\s*(?:latency|response time)?)", raw_text, re.IGNORECASE)
    metrics.extend(latency_matches)

    return metrics[:5]


def infer_scope_from_description(description: str) -> ImpactScope:
    """Infer impact scope from description.

    Args:
        description: User-provided description

    Returns:
        Inferred ImpactScope
    """
    desc_lower = description.lower()

    # Scope detection patterns
    scope_patterns = {
        ImpactScope.MODEL: [
            "model",
            "llm",
            "claude",
            "gpt",
            "gemini",
            "reasoning",
            "inference",
            "fine-tun",
            "prompt",
        ],
        ImpactScope.SECURITY: [
            "security",
            "vulnerab",
            "attack",
            "exploit",
            "injection",
            "auth",
            "credential",
        ],
        ImpactScope.ARCHITECTURE: [
            "architect",
            "redesign",
            "refactor",
            "migration",
            "breaking change",
        ],
        ImpactScope.TOOL: [
            "tool",
            "integration",
            "api",
            "sdk",
            "library",
            "package",
        ],
        ImpactScope.ORCHESTRATION: [
            "orchestrat",
            "workflow",
            "multi-agent",
            "agent",
            "pipeline",
        ],
        ImpactScope.INFRASTRUCTURE: [
            "infra",
            "deploy",
            "scaling",
            "kubernetes",
            "docker",
            "cloud",
        ],
        ImpactScope.EVALUATION: [
            "evaluat",
            "benchmark",
            "metric",
            "quality",
            "testing",
        ],
        ImpactScope.KNOWLEDGE: [
            "rag",
            "context",
            "memory",
            "knowledge",
            "embeddings",
        ],
    }

    for scope, patterns in scope_patterns.items():
        for pattern in patterns:
            if pattern in desc_lower:
                return scope

    # Default
    return ImpactScope.MODEL


def infer_effort(description: str, scope: ImpactScope) -> Effort:
    """Infer effort estimate from description and scope.

    Args:
        description: User-provided description
        scope: Inferred impact scope

    Returns:
        Effort estimate
    """
    desc_lower = description.lower()

    # Quick indicators
    quick_patterns = [
        "simple",
        "quick",
        "easy",
        "minor",
        "small",
        "tweak",
        "config",
        "setting",
    ]

    # Large effort indicators
    large_patterns = [
        "rewrite",
        "redesign",
        "major",
        "significant",
        "overhaul",
        "migration",
    ]

    for pattern in large_patterns:
        if pattern in desc_lower:
            return Effort.WEEKS

    for pattern in quick_patterns:
        if pattern in desc_lower:
            return Effort.HOURS

    # Default based on scope
    scope_effort = {
        ImpactScope.ARCHITECTURE: Effort.WEEKS,
        ImpactScope.SECURITY: Effort.DAYS,
        ImpactScope.MODEL: Effort.DAYS,
        ImpactScope.ORCHESTRATION: Effort.DAYS,
        ImpactScope.INFRASTRUCTURE: Effort.DAYS,
        ImpactScope.TOOL: Effort.HOURS,
        ImpactScope.EVALUATION: Effort.HOURS,
        ImpactScope.KNOWLEDGE: Effort.DAYS,
    }

    return scope_effort.get(scope, Effort.DAYS)


def infer_risk(scope: ImpactScope, effort: Effort) -> Risk:
    """Infer risk level from scope and effort.

    Args:
        scope: Impact scope
        effort: Effort estimate

    Returns:
        Risk level
    """
    # High risk scopes
    if scope in (ImpactScope.SECURITY, ImpactScope.ARCHITECTURE):
        return Risk.HIGH

    # Large efforts are risky
    if effort == Effort.WEEKS:
        return Risk.MEDIUM

    # Infrastructure changes are risky
    if scope == ImpactScope.INFRASTRUCTURE:
        return Risk.MEDIUM

    # Quick changes are low risk
    if effort == Effort.HOURS:
        return Risk.LOW

    return Risk.LOW


def generate_hypothesis(description: str, scope: ImpactScope) -> str:
    """Generate a hypothesis from the description.

    Format: "If we do X, then Y will improve by Z"

    Args:
        description: User-provided description
        scope: Inferred impact scope

    Returns:
        Generated hypothesis
    """
    # Extract potential metrics from description
    metrics = {
        ImpactScope.MODEL: "quality/accuracy",
        ImpactScope.EVALUATION: "evaluation coverage",
        ImpactScope.TOOL: "capability/functionality",
        ImpactScope.ORCHESTRATION: "workflow efficiency",
        ImpactScope.INFRASTRUCTURE: "reliability/performance",
        ImpactScope.SECURITY: "security posture",
        ImpactScope.ARCHITECTURE: "maintainability",
        ImpactScope.KNOWLEDGE: "context quality",
    }

    metric = metrics.get(scope, "system performance")

    # Try to extract action from description
    desc_clean = description.strip()
    if desc_clean.endswith("."):
        desc_clean = desc_clean[:-1]

    # Simple hypothesis generation
    return f"If we integrate this research, then {metric} will improve measurably."


def generate_summary(description: str) -> list[str]:
    """Generate 3-point summary from description.

    Args:
        description: User-provided description

    Returns:
        List of 3 summary points
    """
    desc_clean = description.strip()

    # Create structured summary
    summary = [
        f"Discovery: {desc_clean}",
        "Relevance: Potentially applicable to the autonomous system.",
        "Next step: Evaluate for integration following ADR-009 process.",
    ]

    return summary


def infer_relevance_areas(scope: ImpactScope) -> list[str]:
    """Infer relevance areas from scope.

    Args:
        scope: Impact scope

    Returns:
        List of relevance area strings
    """
    area_map = {
        ImpactScope.MODEL: ["Model Layer"],
        ImpactScope.TOOL: ["Tool Layer"],
        ImpactScope.ORCHESTRATION: ["Orchestration"],
        ImpactScope.KNOWLEDGE: ["Knowledge/Prompts"],
        ImpactScope.INFRASTRUCTURE: ["Infrastructure"],
        ImpactScope.EVALUATION: ["Evaluation"],
        ImpactScope.SECURITY: ["Infrastructure", "Security"],
        ImpactScope.ARCHITECTURE: ["Orchestration", "Infrastructure"],
    }

    return area_map.get(scope, ["Model Layer"])


def infer_all_fields(user_input: ResearchInput) -> InferredFields:
    """Infer all fields from minimal user input.

    Args:
        user_input: Minimal input from user

    Returns:
        InferredFields with all inferred data
    """
    inferred = InferredFields()

    # Source type
    source = user_input.source_url or user_input.source
    inferred.source_type = detect_source_type(source)

    # Title - prefer explicit title, then extract from URL or description
    if user_input.title:
        inferred.title = user_input.title
    elif source.startswith("http"):
        # Extract title from URL path
        parsed = urlparse(source)
        path_parts = parsed.path.strip("/").split("/")
        if path_parts and path_parts[-1]:
            title = path_parts[-1].replace("-", " ").replace("_", " ").title()
            inferred.title = title[:80]  # Limit length
        else:
            inferred.title = user_input.description[:50]
    else:
        inferred.title = source if source else user_input.description[:50]

    # Use raw_text for richer inference if available
    if user_input.raw_text:
        combined_text = user_input.raw_text
        # Extract findings from raw text
        findings = extract_key_findings(user_input.raw_text)
        if findings:
            inferred.summary = findings[:3]
        # Extract hypothesis from raw text
        extracted_hyp = extract_hypothesis_from_text(user_input.raw_text)
        if extracted_hyp:
            inferred.hypothesis = extracted_hyp
    else:
        combined_text = f"{user_input.description} {user_input.why_relevant or ''}"

    # Scope
    inferred.scope = infer_scope_from_description(combined_text)

    # Effort and Risk
    inferred.effort = infer_effort(combined_text, inferred.scope)
    inferred.risk = infer_risk(inferred.scope, inferred.effort)

    # Reversibility
    if inferred.risk == Risk.LOW:
        inferred.reversibility = "Easy"
    elif inferred.risk == Risk.MEDIUM:
        inferred.reversibility = "Moderate"
    else:
        inferred.reversibility = "Difficult"

    # Hypothesis (if not extracted from raw_text)
    if not inferred.hypothesis:
        inferred.hypothesis = generate_hypothesis(user_input.description, inferred.scope)

    # Summary (if not extracted from raw_text)
    if not inferred.summary:
        inferred.summary = generate_summary(user_input.description)

    # Relevance areas
    inferred.relevance_areas = infer_relevance_areas(inferred.scope)

    return inferred


def create_research_note(
    user_input: ResearchInput,
    output_dir: Optional[Path] = None,
    author: str = "Claude Code Agent",
) -> tuple[Path, str]:
    """Create a full research note from minimal input.

    Args:
        user_input: Minimal input from user
        output_dir: Directory to write note (default: docs/research/notes/)
        author: Author name

    Returns:
        Tuple of (file path, note content)
    """
    # Infer all fields
    inferred = infer_all_fields(user_input)

    # Generate filename
    today = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", inferred.title.lower())[:40].strip("-")
    filename = f"{today}-{slug}.md"

    # Determine output path
    if output_dir is None:
        output_dir = Path("docs/research/notes")
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename

    # Build relevance checkboxes
    relevance_areas = {
        "Model Layer": "Model" in str(inferred.relevance_areas),
        "Tool Layer": "Tool" in str(inferred.relevance_areas),
        "Orchestration": "Orchestration" in str(inferred.relevance_areas),
        "Knowledge/Prompts": "Knowledge" in str(inferred.relevance_areas),
        "Infrastructure": "Infrastructure" in str(inferred.relevance_areas),
        "Evaluation": "Evaluation" in str(inferred.relevance_areas),
    }

    relevance_lines = []
    for area, checked in relevance_areas.items():
        checkbox = "[x]" if checked else "[ ]"
        relevance_lines.append(f"- {checkbox} **{area}**")

    # Determine recommendation checkbox
    # Create temporary note for classification
    from src.research.classifier import ResearchNote as ClassifierNote
    temp_note = ClassifierNote(
        hypothesis=inferred.hypothesis,
        impact=type("Impact", (), {
            "scope": inferred.scope,
            "effort": inferred.effort,
            "risk": inferred.risk,
        })(),
    )
    classification, reason = auto_classify(temp_note)
    inferred.recommendation = classification

    rec_checkboxes = {
        Classification.SPIKE: "[ ]",
        Classification.ADR: "[ ]",
        Classification.BACKLOG: "[ ]",
        Classification.DISCARD: "[ ]",
    }
    rec_checkboxes[classification] = "[x]"

    # Generate note content
    content = f"""# Research Note: {inferred.title}

**Date:** {today}
**Author:** {author}
**Status:** Draft

---

## Source

- **Type:** {inferred.source_type}
- **URL:** {user_input.source if user_input.source.startswith("http") else "N/A"}
- **Title:** {inferred.title}
- **Creator/Author:** Unknown
- **Date Published:** Unknown

---

## Summary

1. {inferred.summary[0]}
2. {inferred.summary[1]}
3. {inferred.summary[2]}

---

## Relevance to Our System

{chr(10).join(relevance_lines)}

---

## Hypothesis

> {inferred.hypothesis}

---

## Impact Estimate

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| **Scope** | {inferred.scope.value if inferred.scope else "Unknown"} | {inferred.scope.value if inferred.scope else "TBD"} layer |
| **Effort** | {inferred.effort.value if inferred.effort else "Unknown"} | Estimated implementation time |
| **Risk** | {inferred.risk.value if inferred.risk else "Unknown"} | Based on scope and effort |
| **Reversibility** | {inferred.reversibility} | {"Easy rollback" if inferred.risk == Risk.LOW else "Needs planning"} |

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
- Risks: {inferred.risk.value if inferred.risk else "Unknown"}

---

## Questions to Answer

1. What is the actual impact on our system?
2. How does this compare to our current approach?
3. What is the cost/benefit ratio?

---

## Next Action

- {rec_checkboxes[Classification.SPIKE]} **Spike** - Create experiment, run isolated test
- {rec_checkboxes[Classification.ADR]} **ADR** - Create architecture decision record
- {rec_checkboxes[Classification.BACKLOG]} **Backlog** - Add to future work, not urgent
- {rec_checkboxes[Classification.DISCARD]} **Discard** - Not relevant, archive this note

**Auto-Recommendation:** {classification.value}
**Reason:** {reason}

---

## Related

- Related ADRs: ADR-009 (Research Integration Architecture)
- Related experiments: None yet
- Related research notes: None yet

---

## User Input (Preserved)

**Source:** {user_input.source_url or user_input.source}
**Description:** {user_input.description}
**Why Relevant:** {user_input.why_relevant or "Not specified"}
"""

    # Add raw text section if provided
    if user_input.raw_text:
        raw_text_section = f"""
---

## Raw Research Text

<details>
<summary>Click to expand full research text</summary>

{user_input.raw_text}

</details>

### Extracted Metrics

{chr(10).join(f"- {m}" for m in extract_metrics_from_text(user_input.raw_text)) or "- No explicit metrics found"}
"""
        content += raw_text_section

    # Write file
    file_path.write_text(content)

    return file_path, content


def parse_user_prompt(prompt: str) -> Optional[ResearchInput]:
    """Parse a user prompt into ResearchInput.

    Supports formats:
    - "Add research: <url> - <description>"
    - "Research: <url> <description>"
    - "<url> <description>"

    Args:
        prompt: User's prompt text

    Returns:
        ResearchInput if parseable, None otherwise
    """
    # Pattern 1: "Add research: <url> - <description>"
    match = re.match(
        r"(?:add\s+)?research:\s*(\S+)\s*[-–]\s*(.+)",
        prompt,
        re.IGNORECASE,
    )
    if match:
        return ResearchInput(
            source=match.group(1).strip(),
            description=match.group(2).strip(),
        )

    # Pattern 2: URL followed by description
    match = re.match(r"(https?://\S+)\s+(.+)", prompt)
    if match:
        return ResearchInput(
            source=match.group(1).strip(),
            description=match.group(2).strip(),
        )

    # Pattern 3: Title - Description format
    match = re.match(r"([^-]+)\s*[-–]\s*(.+)", prompt)
    if match:
        return ResearchInput(
            source=match.group(1).strip(),
            description=match.group(2).strip(),
        )

    return None


async def ingest_research(
    prompt: str,
    output_dir: Optional[Path] = None,
) -> Optional[tuple[Path, str, Classification]]:
    """Main entry point for research ingestion.

    Args:
        prompt: User's prompt with research info
        output_dir: Optional output directory

    Returns:
        Tuple of (file path, content, classification) or None if parsing failed
    """
    # Parse user input
    user_input = parse_user_prompt(prompt)
    if not user_input:
        return None

    # Create research note
    file_path, content = create_research_note(user_input, output_dir)

    # Get classification
    from src.research.classifier import parse_research_note
    note = parse_research_note(content, file_path)
    classification, _ = auto_classify(note)

    return file_path, content, classification
