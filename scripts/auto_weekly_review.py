#!/usr/bin/env python3
"""Auto Weekly Review script for ADR-009 Phase 5.

Scans research notes and processes them:
1. Finds unclassified/new notes
2. Auto-classifies based on rules
3. For Spikes: Creates local issue + experiment skeleton
4. Updates notes with issue/experiment references

Usage:
    python scripts/auto_weekly_review.py
    python scripts/auto_weekly_review.py --dry-run
    python scripts/auto_weekly_review.py --notes-dir custom/path
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.classifier import (
    Classification,
    auto_classify,
    find_unclassified_notes,
    parse_research_note,
    update_note_with_classification,
)
from src.research.experiment_creator import (
    create_experiment_skeleton,
    get_next_experiment_id,
)


def get_next_issue_id(issues_dir: Path) -> int:
    """Get the next available local issue ID.

    Args:
        issues_dir: Path to issues directory

    Returns:
        Next issue ID number
    """
    if not issues_dir.exists():
        return 1

    existing_ids = []
    for issue_file in issues_dir.glob("ISSUE-*.md"):
        try:
            issue_id = int(issue_file.stem.split("-")[1])
            existing_ids.append(issue_id)
        except (IndexError, ValueError):
            continue

    return max(existing_ids, default=0) + 1


def create_local_issue(
    note_path: Path,
    classification: Classification,
    reason: str,
    issues_dir: Path,
    experiment_id: str = None,
) -> tuple[int, Path]:
    """Create a local issue file for a research note.

    Args:
        note_path: Path to the research note
        classification: Classification decision
        reason: Reason for classification
        issues_dir: Directory to store issues
        experiment_id: Optional experiment ID if created

    Returns:
        Tuple of (issue ID, issue file path)
    """
    issues_dir.mkdir(parents=True, exist_ok=True)

    # Read note for details
    content = note_path.read_text()
    note = parse_research_note(content, note_path)

    # Get next issue ID
    issue_id = get_next_issue_id(issues_dir)
    today = datetime.now().strftime("%Y-%m-%d")

    # Create issue content
    issue_content = f"""# ISSUE-{issue_id:04d}: [{classification.value}] {note.title}

**Created:** {today}
**Status:** Open
**Classification:** {classification.value}
**Research Note:** [{note_path.name}](../../{note_path})

---

## Summary

{note.summary[0] if note.summary else "See research note for details."}

---

## Classification

**Decision:** {classification.value}
**Reason:** {reason}

---

## Hypothesis

> {note.hypothesis or "To be determined"}

---

## Impact

| Dimension | Value |
|-----------|-------|
| **Scope** | {note.impact.scope.value if note.impact.scope else "Unknown"} |
| **Effort** | {note.impact.effort.value if note.impact.effort else "Unknown"} |
| **Risk** | {note.impact.risk.value if note.impact.risk else "Unknown"} |

---

## Next Steps

"""

    if classification == Classification.SPIKE:
        issue_content += f"""- [ ] Review research note
- [ ] Run experiment{f" ({experiment_id})" if experiment_id else ""}
- [ ] Analyze results
- [ ] Make ADOPT/REJECT decision

"""
        if experiment_id:
            issue_content += f"""### Experiment

**ID:** {experiment_id}
**Location:** `experiments/{experiment_id}/`

```bash
# Run the experiment
python experiments/{experiment_id}/run.py

# Or with specific provider
python experiments/{experiment_id}/run.py --provider claude
```

"""

    elif classification == Classification.ADR:
        issue_content += """- [ ] Review research note
- [ ] Draft ADR document
- [ ] Get stakeholder approval
- [ ] Implement decision

"""

    elif classification == Classification.BACKLOG:
        issue_content += """- [ ] Add to backlog/TODO list
- [ ] Prioritize when relevant
- [ ] Implement when needed

"""

    issue_content += f"""---

## References

- Research Note: `{note_path}`
- ADR-009: Research Integration Architecture
"""

    if experiment_id:
        issue_content += f"- Experiment: `experiments/{experiment_id}/`\n"

    # Write issue file
    issue_filename = f"ISSUE-{issue_id:04d}.md"
    issue_path = issues_dir / issue_filename
    issue_path.write_text(issue_content)

    return issue_id, issue_path


def process_note(
    note_path: Path,
    issues_dir: Path,
    experiments_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Process a single research note.

    Args:
        note_path: Path to the research note
        issues_dir: Directory for local issues
        experiments_dir: Directory for experiments
        dry_run: If True, don't create files

    Returns:
        Processing result dictionary
    """
    result = {
        "note": note_path.name,
        "classification": None,
        "reason": None,
        "issue_id": None,
        "experiment_id": None,
        "actions": [],
    }

    # Read and parse note
    content = note_path.read_text()
    note = parse_research_note(content, note_path)

    # Classify
    classification, reason = auto_classify(note)
    result["classification"] = classification.value
    result["reason"] = reason

    print(f"  Classification: {classification.value}")
    print(f"  Reason: {reason}")

    if dry_run:
        result["actions"].append("DRY RUN - no changes made")
        return result

    # For Spikes: Create experiment skeleton first
    experiment_id = None
    if classification == Classification.SPIKE:
        exp_dir = create_experiment_skeleton(note_path, experiments_dir)
        if exp_dir:
            experiment_id = exp_dir.name
            result["experiment_id"] = experiment_id
            result["actions"].append(f"Created experiment: {experiment_id}")
            print(f"  Created experiment: {experiment_id}")

    # Create local issue for Spikes and ADRs
    if classification in (Classification.SPIKE, Classification.ADR):
        issue_id, issue_path = create_local_issue(
            note_path=note_path,
            classification=classification,
            reason=reason,
            issues_dir=issues_dir,
            experiment_id=experiment_id,
        )
        result["issue_id"] = issue_id
        result["actions"].append(f"Created issue: ISSUE-{issue_id:04d}")
        print(f"  Created issue: ISSUE-{issue_id:04d}")

        # Update note with classification and references
        update_note_with_classification(
            note_path=note_path,
            classification=classification,
            reason=reason,
            issue_number=issue_id,
            experiment_id=experiment_id,
        )
        result["actions"].append("Updated note with triage info")
        print("  Updated note with triage info")
    else:
        # Just update classification for Backlog/Discard
        update_note_with_classification(
            note_path=note_path,
            classification=classification,
            reason=reason,
        )
        result["actions"].append("Updated note with classification")
        print("  Updated note with classification")

    return result


def run_weekly_review(
    notes_dir: Path = None,
    issues_dir: Path = None,
    experiments_dir: Path = None,
    dry_run: bool = False,
) -> dict:
    """Run the weekly review process.

    Args:
        notes_dir: Path to research notes
        issues_dir: Path for local issues
        experiments_dir: Path for experiments
        dry_run: If True, don't create any files

    Returns:
        Summary dictionary with results
    """
    # Set defaults
    if notes_dir is None:
        notes_dir = Path("docs/research/notes")
    if issues_dir is None:
        issues_dir = Path("docs/research/issues")
    if experiments_dir is None:
        experiments_dir = Path("experiments")

    print("=" * 60)
    print("ADR-009 Auto Weekly Review")
    print("=" * 60)
    print(f"Notes directory: {notes_dir}")
    print(f"Issues directory: {issues_dir}")
    print(f"Experiments directory: {experiments_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    # Find unclassified notes
    unclassified = find_unclassified_notes(notes_dir)
    print(f"Found {len(unclassified)} unclassified notes")
    print()

    if not unclassified:
        print("No notes to process. Exiting.")
        return {
            "total": 0,
            "processed": 0,
            "spikes": 0,
            "adrs": 0,
            "backlog": 0,
            "discard": 0,
            "results": [],
        }

    # Process each note
    results = []
    counts = {
        "Spike": 0,
        "ADR": 0,
        "Backlog": 0,
        "Discard": 0,
        "NEEDS_REVIEW": 0,
    }

    for note_path in unclassified:
        print(f"Processing: {note_path.name}")
        result = process_note(
            note_path=note_path,
            issues_dir=issues_dir,
            experiments_dir=experiments_dir,
            dry_run=dry_run,
        )
        results.append(result)
        counts[result["classification"]] = counts.get(result["classification"], 0) + 1
        print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total notes processed: {len(results)}")
    for cls, count in counts.items():
        if count > 0:
            print(f"  {cls}: {count}")

    return {
        "total": len(unclassified),
        "processed": len(results),
        "spikes": counts.get("Spike", 0),
        "adrs": counts.get("ADR", 0),
        "backlog": counts.get("Backlog", 0),
        "discard": counts.get("Discard", 0),
        "results": results,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ADR-009 Auto Weekly Review",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run weekly review
    python scripts/auto_weekly_review.py

    # Dry run (no changes)
    python scripts/auto_weekly_review.py --dry-run

    # Custom directories
    python scripts/auto_weekly_review.py --notes-dir my/notes
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't create any files, just show what would happen",
    )
    parser.add_argument(
        "--notes-dir",
        type=Path,
        default=Path("docs/research/notes"),
        help="Path to research notes directory",
    )
    parser.add_argument(
        "--issues-dir",
        type=Path,
        default=Path("docs/research/issues"),
        help="Path to issues directory",
    )
    parser.add_argument(
        "--experiments-dir",
        type=Path,
        default=Path("experiments"),
        help="Path to experiments directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    result = run_weekly_review(
        notes_dir=args.notes_dir,
        issues_dir=args.issues_dir,
        experiments_dir=args.experiments_dir,
        dry_run=args.dry_run,
    )

    if args.json:
        print()
        print(json.dumps(result, indent=2, default=str))

    return 0 if result["processed"] > 0 or result["total"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
