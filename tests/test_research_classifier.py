"""Tests for Research Classifier module.

Tests the classifier module in src/research/classifier.py.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

import pytest


def _can_import_module() -> bool:
    """Check if classifier module can be imported."""
    try:
        from src.research.classifier import (
            Classification,
            ImpactScope,
            Effort,
            Risk,
            ResearchNote,
            parse_research_note,
            auto_classify,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_import_module(),
    reason="research.classifier module not importable"
)


class TestClassificationEnum:
    """Tests for Classification enum."""

    def test_classification_values(self):
        """Test Classification enum values."""
        from src.research.classifier import Classification

        assert Classification.SPIKE.value == "Spike"
        assert Classification.ADR.value == "ADR"
        assert Classification.BACKLOG.value == "Backlog"
        assert Classification.DISCARD.value == "Discard"
        assert Classification.NEEDS_REVIEW.value == "NEEDS_REVIEW"


class TestImpactScopeEnum:
    """Tests for ImpactScope enum."""

    def test_impact_scope_values(self):
        """Test ImpactScope enum values."""
        from src.research.classifier import ImpactScope

        assert ImpactScope.MODEL.value == "Model"
        assert ImpactScope.TOOL.value == "Tool"
        assert ImpactScope.ARCHITECTURE.value == "Architecture"
        assert ImpactScope.SECURITY.value == "Security"


class TestEffortEnum:
    """Tests for Effort enum."""

    def test_effort_values(self):
        """Test Effort enum values."""
        from src.research.classifier import Effort

        assert Effort.HOURS.value == "Hours"
        assert Effort.DAYS.value == "Days"
        assert Effort.WEEKS.value == "Weeks"


class TestRiskEnum:
    """Tests for Risk enum."""

    def test_risk_values(self):
        """Test Risk enum values."""
        from src.research.classifier import Risk

        assert Risk.LOW.value == "Low"
        assert Risk.MEDIUM.value == "Medium"
        assert Risk.HIGH.value == "High"


class TestResearchNote:
    """Tests for ResearchNote dataclass."""

    def test_research_note_defaults(self):
        """Test ResearchNote default values."""
        from src.research.classifier import ResearchNote

        note = ResearchNote()

        assert note.title == ""
        assert note.date is None
        assert note.status == "Draft"
        assert note.summary == []
        assert note.hypothesis == ""
        assert note.recommendation is None


class TestParseResearchNote:
    """Tests for parse_research_note function."""

    def test_parse_title(self):
        """Test parsing title from markdown."""
        from src.research.classifier import parse_research_note

        content = "# Research Note: Test Title\n\nSome content"
        note = parse_research_note(content)

        assert note.title == "Test Title"

    def test_parse_date(self):
        """Test parsing date from markdown."""
        from src.research.classifier import parse_research_note

        content = "# Title\n**Date:** 2026-01-22\n"
        note = parse_research_note(content)

        assert note.date == datetime(2026, 1, 22)

    def test_parse_author(self):
        """Test parsing author from markdown."""
        from src.research.classifier import parse_research_note

        content = "# Title\n**Author:** Test Author\n"
        note = parse_research_note(content)

        assert note.author == "Test Author"

    def test_parse_status(self):
        """Test parsing status from markdown."""
        from src.research.classifier import parse_research_note

        content = "# Title\n**Status:** Triaged\n"
        note = parse_research_note(content)

        assert note.status == "Triaged"

    def test_parse_source_url(self):
        """Test parsing source URL."""
        from src.research.classifier import parse_research_note

        content = "# Title\n**URL:** https://example.com/research\n"
        note = parse_research_note(content)

        assert note.source_url == "https://example.com/research"

    def test_parse_hypothesis(self):
        """Test parsing hypothesis."""
        from src.research.classifier import parse_research_note

        content = "# Title\n## Hypothesis\n> This will improve quality by 20%\n"
        note = parse_research_note(content)

        assert "improve quality by 20%" in note.hypothesis

    def test_parse_impact_scope(self):
        """Test parsing impact scope."""
        from src.research.classifier import parse_research_note, ImpactScope

        content = "# Title\n| **Scope** | Model |\n"
        note = parse_research_note(content)

        assert note.impact.scope == ImpactScope.MODEL

    def test_parse_effort(self):
        """Test parsing effort."""
        from src.research.classifier import parse_research_note, Effort

        content = "# Title\n| **Effort** | Hours |\n"
        note = parse_research_note(content)

        assert note.impact.effort == Effort.HOURS

    def test_parse_risk(self):
        """Test parsing risk."""
        from src.research.classifier import parse_research_note, Risk

        content = "# Title\n| **Risk** | Low |\n"
        note = parse_research_note(content)

        assert note.impact.risk == Risk.LOW

    def test_parse_spike_recommendation(self):
        """Test parsing Spike recommendation."""
        from src.research.classifier import parse_research_note, Classification

        content = "# Title\n[x] **Spike**\n"
        note = parse_research_note(content)

        assert note.recommendation == Classification.SPIKE

    def test_parse_adr_recommendation(self):
        """Test parsing ADR recommendation."""
        from src.research.classifier import parse_research_note, Classification

        content = "# Title\n[x] **ADR**\n"
        note = parse_research_note(content)

        assert note.recommendation == Classification.ADR

    def test_parse_relevance_areas(self):
        """Test parsing relevance areas."""
        from src.research.classifier import parse_research_note

        content = "# Title\n[x] **Model Layer**\n[x] **Tool Layer**\n"
        note = parse_research_note(content)

        assert "Model" in note.relevance_areas
        assert "Tool" in note.relevance_areas

    def test_parse_triage_info(self):
        """Test parsing triage information."""
        from src.research.classifier import parse_research_note, Classification

        content = "# Title\n**Reviewed:** 2026-01-22\n**Decision:** Spike\n"
        note = parse_research_note(content)

        assert note.triage_date == datetime(2026, 1, 22)
        assert note.triage_decision == Classification.SPIKE

    def test_parse_issue_number(self):
        """Test parsing issue number."""
        from src.research.classifier import parse_research_note

        content = "# Title\n**Issue/PR:** #123\n"
        note = parse_research_note(content)

        assert note.issue_number == 123

    def test_parse_experiment_id(self):
        """Test parsing experiment ID."""
        from src.research.classifier import parse_research_note

        content = "# Title\n**Experiment ID:** exp_001\n"
        note = parse_research_note(content)

        assert note.experiment_id == "exp_001"


class TestAutoClassify:
    """Tests for auto_classify function."""

    def test_explicit_recommendation(self):
        """Test classification uses explicit recommendation."""
        from src.research.classifier import (
            ResearchNote,
            Classification,
            auto_classify,
        )

        note = ResearchNote(recommendation=Classification.ADR)
        classification, reason = auto_classify(note)

        assert classification == Classification.ADR
        assert "Explicit" in reason

    def test_architecture_scope_becomes_adr(self):
        """Test Architecture scope classifies as ADR."""
        from src.research.classifier import (
            ResearchNote,
            Classification,
            ImpactScope,
            ImpactEstimate,
            auto_classify,
        )

        note = ResearchNote()
        note.impact = ImpactEstimate(scope=ImpactScope.ARCHITECTURE)
        classification, reason = auto_classify(note)

        assert classification == Classification.ADR
        assert "Architecture" in reason

    def test_security_scope_becomes_adr(self):
        """Test Security scope classifies as ADR."""
        from src.research.classifier import (
            ResearchNote,
            Classification,
            ImpactScope,
            ImpactEstimate,
            auto_classify,
        )

        note = ResearchNote()
        note.impact = ImpactEstimate(scope=ImpactScope.SECURITY)
        classification, reason = auto_classify(note)

        assert classification == Classification.ADR
        assert "Security" in reason

    def test_quick_low_risk_becomes_backlog(self):
        """Test quick and low-risk changes go to Backlog."""
        from src.research.classifier import (
            ResearchNote,
            Classification,
            Effort,
            Risk,
            ImpactEstimate,
            auto_classify,
        )

        note = ResearchNote()
        note.impact = ImpactEstimate(effort=Effort.HOURS, risk=Risk.LOW)
        classification, reason = auto_classify(note)

        assert classification == Classification.BACKLOG
        assert "Quick" in reason

    def test_model_with_hypothesis_becomes_spike(self):
        """Test model change with hypothesis classifies as Spike."""
        from src.research.classifier import (
            ResearchNote,
            Classification,
            ImpactScope,
            ImpactEstimate,
            auto_classify,
        )

        note = ResearchNote()
        note.impact = ImpactEstimate(scope=ImpactScope.MODEL)
        note.hypothesis = "This will improve quality by 20%"
        classification, reason = auto_classify(note)

        assert classification == Classification.SPIKE
        assert "Model" in reason

    def test_tool_scope_becomes_backlog(self):
        """Test Tool scope classifies as Backlog."""
        from src.research.classifier import (
            ResearchNote,
            Classification,
            ImpactScope,
            ImpactEstimate,
            auto_classify,
        )

        note = ResearchNote()
        note.impact = ImpactEstimate(scope=ImpactScope.TOOL)
        classification, reason = auto_classify(note)

        assert classification == Classification.BACKLOG
        assert "Tool" in reason

    def test_default_needs_review(self):
        """Test default classification is NEEDS_REVIEW."""
        from src.research.classifier import (
            ResearchNote,
            Classification,
            auto_classify,
        )

        note = ResearchNote()
        classification, reason = auto_classify(note)

        assert classification == Classification.NEEDS_REVIEW
        assert "Mixed" in reason


class TestFindUnclassifiedNotes:
    """Tests for find_unclassified_notes function."""

    def test_find_unclassified_in_empty_dir(self):
        """Test finding unclassified notes in empty directory."""
        from src.research.classifier import find_unclassified_notes

        with tempfile.TemporaryDirectory() as tmpdir:
            notes_dir = Path(tmpdir) / "notes"
            notes_dir.mkdir()

            result = find_unclassified_notes(notes_dir)

            assert result == []

    def test_find_unclassified_skips_templates(self):
        """Test that templates are skipped."""
        from src.research.classifier import find_unclassified_notes

        with tempfile.TemporaryDirectory() as tmpdir:
            notes_dir = Path(tmpdir) / "notes"
            notes_dir.mkdir()

            template = notes_dir / "research-template.md"
            template.write_text("# Template\n**Status:** Draft\n")

            result = find_unclassified_notes(notes_dir)

            assert template not in result

    def test_find_unclassified_finds_draft(self):
        """Test finding draft notes."""
        from src.research.classifier import find_unclassified_notes

        with tempfile.TemporaryDirectory() as tmpdir:
            notes_dir = Path(tmpdir) / "notes"
            notes_dir.mkdir()

            draft = notes_dir / "2026-01-22-test.md"
            draft.write_text("# Test\n**Status:** Draft\n")

            result = find_unclassified_notes(notes_dir)

            assert draft in result


class TestUpdateNoteWithClassification:
    """Tests for update_note_with_classification function."""

    def test_update_adds_triage_section(self):
        """Test that update adds triage section."""
        from src.research.classifier import (
            Classification,
            update_note_with_classification,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            note_path = Path(tmpdir) / "test.md"
            note_path.write_text("# Test\n**Status:** Draft\n")

            result = update_note_with_classification(
                note_path,
                Classification.SPIKE,
                "Test reason",
            )

            assert "## Triage Notes" in result
            assert "Spike" in result
            assert "Test reason" in result

    def test_update_changes_status(self):
        """Test that update changes status."""
        from src.research.classifier import (
            Classification,
            update_note_with_classification,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            note_path = Path(tmpdir) / "test.md"
            note_path.write_text("# Test\n**Status:** Draft\n")

            result = update_note_with_classification(
                note_path,
                Classification.SPIKE,
                "Test reason",
            )

            assert "Triaged (Spike)" in result

    def test_update_includes_issue_number(self):
        """Test that update includes issue number."""
        from src.research.classifier import (
            Classification,
            update_note_with_classification,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            note_path = Path(tmpdir) / "test.md"
            note_path.write_text("# Test\n**Status:** Draft\n")

            result = update_note_with_classification(
                note_path,
                Classification.SPIKE,
                "Test reason",
                issue_number=42,
            )

            assert "#42" in result

    def test_update_includes_experiment_id(self):
        """Test that update includes experiment ID."""
        from src.research.classifier import (
            Classification,
            update_note_with_classification,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            note_path = Path(tmpdir) / "test.md"
            note_path.write_text("# Test\n**Status:** Draft\n")

            result = update_note_with_classification(
                note_path,
                Classification.SPIKE,
                "Test reason",
                experiment_id="exp_001",
            )

            assert "exp_001" in result
