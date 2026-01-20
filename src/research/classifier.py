"""Research note classifier for ADR-009 Phase 5.

Provides automatic classification of research notes into:
- Spike: Create experiment, run isolated test
- ADR: Create architecture decision record
- Backlog: Add to future work
- Discard: Archive, not relevant

Classification is based on:
1. Explicit Recommendation field in note (if present)
2. Impact scope analysis (Architecture/Security -> ADR)
3. Model changes with hypothesis -> Spike
4. Quick, low-risk changes -> Backlog
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class Classification(Enum):
    """Research note classification types."""

    SPIKE = "Spike"
    ADR = "ADR"
    BACKLOG = "Backlog"
    DISCARD = "Discard"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ImpactScope(Enum):
    """Impact scope categories."""

    MODEL = "Model"
    TOOL = "Tool"
    ORCHESTRATION = "Orchestration"
    ARCHITECTURE = "Architecture"
    SECURITY = "Security"
    INFRASTRUCTURE = "Infrastructure"
    KNOWLEDGE = "Knowledge"
    EVALUATION = "Evaluation"


class Effort(Enum):
    """Effort estimates."""

    HOURS = "Hours"
    DAYS = "Days"
    WEEKS = "Weeks"


class Risk(Enum):
    """Risk levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class ImpactEstimate:
    """Impact estimate for a research note."""

    scope: Optional[ImpactScope] = None
    effort: Optional[Effort] = None
    risk: Optional[Risk] = None
    reversibility: Optional[str] = None


@dataclass
class ResearchNote:
    """Parsed research note structure."""

    # Core fields
    title: str = ""
    date: Optional[datetime] = None
    author: str = ""
    status: str = "Draft"

    # Source fields
    source_type: str = ""
    source_url: str = ""
    source_title: str = ""
    source_author: str = ""
    date_published: str = ""

    # Content
    summary: list[str] = field(default_factory=list)
    hypothesis: str = ""

    # Impact
    impact: ImpactEstimate = field(default_factory=ImpactEstimate)

    # Classification
    recommendation: Optional[Classification] = None
    relevance_areas: list[str] = field(default_factory=list)

    # Triage
    triage_date: Optional[datetime] = None
    triage_decision: Optional[Classification] = None
    issue_number: Optional[int] = None
    experiment_id: Optional[str] = None

    # File info
    file_path: Optional[Path] = None


def parse_research_note(content: str, file_path: Optional[Path] = None) -> ResearchNote:
    """Parse a research note markdown file into structured data.

    Args:
        content: Markdown content of the research note
        file_path: Optional path to the source file

    Returns:
        Parsed ResearchNote with extracted fields
    """
    note = ResearchNote(file_path=file_path)

    # Extract title from first # heading
    title_match = re.search(r"^#\s+(?:Research Note:\s*)?(.+)$", content, re.MULTILINE)
    if title_match:
        note.title = title_match.group(1).strip()

    # Extract date
    date_match = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", content)
    if date_match:
        try:
            note.date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
        except ValueError:
            pass

    # Extract author
    author_match = re.search(r"\*\*Author:\*\*\s*(.+)", content)
    if author_match:
        note.author = author_match.group(1).strip()

    # Extract status
    status_match = re.search(r"\*\*Status:\*\*\s*(.+)", content)
    if status_match:
        note.status = status_match.group(1).strip()

    # Extract source URL
    url_match = re.search(r"\*\*URL:\*\*\s*(\S+)", content)
    if url_match:
        note.source_url = url_match.group(1).strip()

    # Extract source type
    type_match = re.search(r"\*\*Type:\*\*\s*(.+)", content)
    if type_match:
        note.source_type = type_match.group(1).strip()

    # Extract hypothesis
    hypothesis_match = re.search(r"## Hypothesis\s+>\s*(.+)", content, re.MULTILINE)
    if hypothesis_match:
        note.hypothesis = hypothesis_match.group(1).strip()

    # Extract impact scope
    scope_match = re.search(r"\|\s*\*\*Scope\*\*\s*\|\s*(\w+)", content)
    if scope_match:
        scope_str = scope_match.group(1).strip()
        try:
            note.impact.scope = ImpactScope(scope_str)
        except ValueError:
            pass

    # Extract effort
    effort_match = re.search(r"\|\s*\*\*Effort\*\*\s*\|\s*(\w+)", content)
    if effort_match:
        effort_str = effort_match.group(1).strip()
        try:
            note.impact.effort = Effort(effort_str)
        except ValueError:
            pass

    # Extract risk
    risk_match = re.search(r"\|\s*\*\*Risk\*\*\s*\|\s*(\w+)", content)
    if risk_match:
        risk_str = risk_match.group(1).strip()
        try:
            note.impact.risk = Risk(risk_str)
        except ValueError:
            pass

    # Extract recommendation from Next Action checkboxes
    rec_patterns = [
        (r"\[x\]\s*\*\*Spike\*\*", Classification.SPIKE),
        (r"\[x\]\s*\*\*ADR\*\*", Classification.ADR),
        (r"\[x\]\s*\*\*Backlog\*\*", Classification.BACKLOG),
        (r"\[x\]\s*\*\*Discard\*\*", Classification.DISCARD),
    ]
    for pattern, classification in rec_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            note.recommendation = classification
            break

    # Extract relevance areas
    relevance_patterns = [
        (r"\[x\]\s*\*\*Model Layer\*\*", "Model"),
        (r"\[x\]\s*\*\*Tool Layer\*\*", "Tool"),
        (r"\[x\]\s*\*\*Orchestration\*\*", "Orchestration"),
        (r"\[x\]\s*\*\*Knowledge/Prompts\*\*", "Knowledge"),
        (r"\[x\]\s*\*\*Infrastructure\*\*", "Infrastructure"),
        (r"\[x\]\s*\*\*Evaluation\*\*", "Evaluation"),
    ]
    for pattern, area in relevance_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            note.relevance_areas.append(area)

    # Extract triage info
    triage_match = re.search(r"\*\*Reviewed:\*\*\s*(\d{4}-\d{2}-\d{2})", content)
    if triage_match:
        try:
            note.triage_date = datetime.strptime(triage_match.group(1), "%Y-%m-%d")
        except ValueError:
            pass

    decision_match = re.search(r"\*\*Decision:\*\*\s*(\w+)", content)
    if decision_match:
        decision_str = decision_match.group(1).strip()
        try:
            note.triage_decision = Classification(decision_str)
        except ValueError:
            pass

    # Extract issue number
    issue_match = re.search(r"\*\*Issue/PR:\*\*\s*#(\d+)", content)
    if issue_match:
        note.issue_number = int(issue_match.group(1))

    # Extract experiment ID
    exp_match = re.search(r"\*\*Experiment ID:\*\*\s*(exp_\w+)", content)
    if exp_match:
        note.experiment_id = exp_match.group(1)

    # Extract summary points (lines starting with numbers in Summary section)
    summary_section = re.search(
        r"## Summary\s+((?:\d+\.\s+.+\n?)+)", content, re.MULTILINE
    )
    if summary_section:
        summary_lines = re.findall(r"\d+\.\s+(.+)", summary_section.group(1))
        note.summary = [line.strip() for line in summary_lines]

    return note


def auto_classify(note: ResearchNote) -> tuple[Classification, str]:
    """Automatically classify a research note.

    Classification rules (in order of priority):
    1. Use explicit Recommendation if present
    2. Architecture/Security scope -> ADR
    3. Quick, low-risk changes -> Backlog
    4. Model changes with hypothesis -> Spike
    5. Default: NEEDS_REVIEW

    Args:
        note: Parsed research note

    Returns:
        Tuple of (Classification, reason string)
    """
    # Rule 1: Explicit recommendation
    if note.recommendation:
        return note.recommendation, f"Explicit recommendation: {note.recommendation.value}"

    # Rule 2: Architecture or Security scope -> ADR
    if note.impact.scope in (ImpactScope.ARCHITECTURE, ImpactScope.SECURITY):
        return (
            Classification.ADR,
            f"High-impact scope ({note.impact.scope.value}) requires ADR",
        )

    # Rule 3: Quick and low-risk -> Backlog
    if note.impact.effort == Effort.HOURS and note.impact.risk == Risk.LOW:
        return (
            Classification.BACKLOG,
            "Quick (Hours) and low-risk change -> Backlog",
        )

    # Rule 4: Model change with hypothesis -> Spike
    if note.impact.scope == ImpactScope.MODEL and note.hypothesis:
        return (
            Classification.SPIKE,
            "Model change with hypothesis needs experiment",
        )

    # Rule 5: Evaluation with hypothesis -> Spike
    if note.impact.scope == ImpactScope.EVALUATION and note.hypothesis:
        return (
            Classification.SPIKE,
            "Evaluation change with hypothesis needs experiment",
        )

    # Rule 6: Tool with clear benefit -> Backlog
    if note.impact.scope == ImpactScope.TOOL and note.impact.risk != Risk.HIGH:
        return (
            Classification.BACKLOG,
            "Tool integration can be added to backlog",
        )

    # Default: Needs human review
    return (
        Classification.NEEDS_REVIEW,
        "Mixed signals - needs human review",
    )


def find_unclassified_notes(notes_dir: Path) -> list[Path]:
    """Find research notes that haven't been classified yet.

    A note is considered unclassified if:
    - It doesn't have a triage decision
    - Or it's marked as Draft status

    Args:
        notes_dir: Path to docs/research/notes/

    Returns:
        List of paths to unclassified note files
    """
    unclassified = []

    if not notes_dir.exists():
        return unclassified

    for note_path in notes_dir.glob("*.md"):
        # Skip templates
        if "template" in note_path.name.lower():
            continue

        content = note_path.read_text()
        note = parse_research_note(content, note_path)

        # Check if already classified
        if note.triage_decision is None:
            unclassified.append(note_path)
        elif note.status.lower() == "draft":
            unclassified.append(note_path)

    return unclassified


def update_note_with_classification(
    note_path: Path,
    classification: Classification,
    reason: str,
    issue_number: Optional[int] = None,
    experiment_id: Optional[str] = None,
) -> str:
    """Update a research note with classification results.

    Args:
        note_path: Path to the research note file
        classification: The classification decision
        reason: Reason for the classification
        issue_number: Optional GitHub issue number
        experiment_id: Optional experiment ID

    Returns:
        Updated note content
    """
    content = note_path.read_text()
    today = datetime.now().strftime("%Y-%m-%d")

    # Update or add Triage Notes section
    triage_section = f"""## Triage Notes

**Reviewed:** {today}
**Decision:** {classification.value}
**Reason:** {reason}"""

    if issue_number:
        triage_section += f"\n**Issue/PR:** #{issue_number}"

    if experiment_id:
        triage_section += f"\n**Experiment ID:** {experiment_id}"

    # Check if Triage Notes section exists
    if "## Triage Notes" in content:
        # Replace existing section
        content = re.sub(
            r"## Triage Notes.*?(?=\n## |\n---|\Z)",
            triage_section + "\n\n",
            content,
            flags=re.DOTALL,
        )
    else:
        # Add before Related section or at end
        if "## Related" in content:
            content = content.replace("## Related", triage_section + "\n\n---\n\n## Related")
        else:
            content = content.rstrip() + "\n\n---\n\n" + triage_section + "\n"

    # Update Status to Triaged
    content = re.sub(
        r"\*\*Status:\*\*\s*\w+",
        f"**Status:** Triaged ({classification.value})",
        content,
    )

    # Write back
    note_path.write_text(content)

    return content
