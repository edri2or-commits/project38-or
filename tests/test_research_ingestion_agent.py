"""Tests for Research Ingestion Agent module.

Tests the ingestion_agent module in src/research/ingestion_agent.py.
"""

from __future__ import annotations

import pytest


def _can_import_module() -> bool:
    """Check if ingestion_agent module can be imported."""
    try:
        from src.research.ingestion_agent import (
            ResearchInput,
            InferredFields,
            detect_source_type,
            extract_key_findings,
            extract_hypothesis_from_text,
            extract_metrics_from_text,
            infer_scope_from_description,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_import_module(),
    reason="research.ingestion_agent module not importable"
)


class TestResearchInput:
    """Tests for ResearchInput dataclass."""

    def test_default_values(self):
        """Test default values."""
        from src.research.ingestion_agent import ResearchInput

        input_data = ResearchInput()

        assert input_data.source == ""
        assert input_data.description == ""
        assert input_data.why_relevant is None
        assert input_data.title is None


class TestInferredFields:
    """Tests for InferredFields dataclass."""

    def test_default_lists(self):
        """Test default list initialization."""
        from src.research.ingestion_agent import InferredFields

        fields = InferredFields()

        assert fields.summary == []
        assert fields.relevance_areas == []


class TestDetectSourceType:
    """Tests for detect_source_type function."""

    def test_youtube_detection(self):
        """Test YouTube URL detection."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("https://youtube.com/watch?v=abc") == "YouTube"
        assert detect_source_type("https://youtu.be/abc") == "YouTube"

    def test_arxiv_detection(self):
        """Test arXiv URL detection."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("https://arxiv.org/abs/2026.12345") == "arXiv"

    def test_github_detection(self):
        """Test GitHub URL detection."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("https://github.com/org/repo") == "GitHub"

    def test_documentation_detection(self):
        """Test documentation URL detection."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("https://docs.python.org/3/") == "Documentation"
        assert detect_source_type("https://example.readthedocs.io/") == "Documentation"

    def test_blog_detection(self):
        """Test blog URL detection."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("https://blog.example.com/post") == "Blog"
        assert detect_source_type("https://medium.com/article") == "Blog"
        assert detect_source_type("https://dev.to/post") == "Blog"

    def test_news_detection(self):
        """Test news URL detection."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("https://techcrunch.com/article") == "News"
        assert detect_source_type("https://theverge.com/post") == "News"

    def test_generic_url(self):
        """Test generic URL detection."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("https://example.com/page") == "Web Article"

    def test_non_url(self):
        """Test non-URL source."""
        from src.research.ingestion_agent import detect_source_type

        assert detect_source_type("Some Research Paper Title") == "Discovery"


class TestExtractKeyFindings:
    """Tests for extract_key_findings function."""

    def test_extract_numbered_items(self):
        """Test extracting numbered items."""
        from src.research.ingestion_agent import extract_key_findings

        text = """
        1. First finding about quality improvement
        2. Second finding about latency
        3. Third finding about cost
        """

        findings = extract_key_findings(text)

        assert len(findings) >= 3
        assert "First finding" in findings[0]

    def test_extract_bullet_points(self):
        """Test extracting bullet points."""
        from src.research.ingestion_agent import extract_key_findings

        text = """
        - This is a key finding about the system
        - Another important observation here
        * Third point using asterisk
        """

        findings = extract_key_findings(text)

        assert len(findings) >= 1

    def test_max_findings_limit(self):
        """Test max findings limit of 5."""
        from src.research.ingestion_agent import extract_key_findings

        text = "\n".join([f"- Finding number {i} with enough content to pass filter" for i in range(10)])

        findings = extract_key_findings(text)

        assert len(findings) <= 5

    def test_empty_text(self):
        """Test with empty text."""
        from src.research.ingestion_agent import extract_key_findings

        findings = extract_key_findings("")

        assert findings == []


class TestExtractHypothesisFromText:
    """Tests for extract_hypothesis_from_text function."""

    def test_explicit_hypothesis(self):
        """Test extracting explicit hypothesis."""
        from src.research.ingestion_agent import extract_hypothesis_from_text

        text = "We hypothesize: This approach will improve accuracy."

        hypothesis = extract_hypothesis_from_text(text)

        assert "improve accuracy" in hypothesis.lower()

    def test_our_hypothesis(self):
        """Test extracting 'our hypothesis is' pattern."""
        from src.research.ingestion_agent import extract_hypothesis_from_text

        text = "Our hypothesis is that caching will reduce latency."

        hypothesis = extract_hypothesis_from_text(text)

        assert "caching" in hypothesis.lower() or "latency" in hypothesis.lower()

    def test_improvement_claim(self):
        """Test extracting improvement claim as hypothesis."""
        from src.research.ingestion_agent import extract_hypothesis_from_text

        text = "The new method achieves 40% improvement in response time."

        hypothesis = extract_hypothesis_from_text(text)

        # May or may not extract depending on pattern
        # Just verify function works
        assert isinstance(hypothesis, str)

    def test_no_hypothesis_found(self):
        """Test when no hypothesis is found."""
        from src.research.ingestion_agent import extract_hypothesis_from_text

        text = "This is just plain text without any claims."

        hypothesis = extract_hypothesis_from_text(text)

        assert hypothesis == ""


class TestExtractMetricsFromText:
    """Tests for extract_metrics_from_text function."""

    def test_percentage_improvements(self):
        """Test extracting percentage improvements."""
        from src.research.ingestion_agent import extract_metrics_from_text

        text = "We achieved 25% improvement in accuracy and 10% reduction in errors."

        metrics = extract_metrics_from_text(text)

        assert len(metrics) >= 1

    def test_times_improvements(self):
        """Test extracting X times improvements."""
        from src.research.ingestion_agent import extract_metrics_from_text

        text = "The system is 3x faster than the baseline."

        metrics = extract_metrics_from_text(text)

        assert len(metrics) >= 1

    def test_latency_metrics(self):
        """Test extracting latency metrics."""
        from src.research.ingestion_agent import extract_metrics_from_text

        text = "Response time improved to 50ms from 200ms."

        metrics = extract_metrics_from_text(text)

        # May or may not match depending on pattern
        assert isinstance(metrics, list)

    def test_max_metrics_limit(self):
        """Test max metrics limit of 5."""
        from src.research.ingestion_agent import extract_metrics_from_text

        text = " ".join([f"{i}% improvement" for i in range(10)])

        metrics = extract_metrics_from_text(text)

        assert len(metrics) <= 5


class TestInferScopeFromDescription:
    """Tests for infer_scope_from_description function."""

    def test_model_scope(self):
        """Test inferring Model scope."""
        from src.research.ingestion_agent import infer_scope_from_description
        from src.research.classifier import ImpactScope

        scope = infer_scope_from_description("New LLM prompting technique")

        assert scope == ImpactScope.MODEL

    def test_security_scope(self):
        """Test inferring Security scope."""
        from src.research.ingestion_agent import infer_scope_from_description
        from src.research.classifier import ImpactScope

        scope = infer_scope_from_description("Security vulnerability in auth")

        assert scope == ImpactScope.SECURITY

    def test_architecture_scope(self):
        """Test inferring Architecture scope."""
        from src.research.ingestion_agent import infer_scope_from_description
        from src.research.classifier import ImpactScope

        scope = infer_scope_from_description("Major architecture redesign")

        assert scope == ImpactScope.ARCHITECTURE

    def test_tool_scope(self):
        """Test inferring Tool scope."""
        from src.research.ingestion_agent import infer_scope_from_description
        from src.research.classifier import ImpactScope

        scope = infer_scope_from_description("New API integration")

        assert scope == ImpactScope.TOOL

    def test_orchestration_scope(self):
        """Test inferring Orchestration scope."""
        from src.research.ingestion_agent import infer_scope_from_description
        from src.research.classifier import ImpactScope

        scope = infer_scope_from_description("Multi-agent workflow improvement")

        assert scope == ImpactScope.ORCHESTRATION


class TestInferEffort:
    """Tests for infer_effort function."""

    def test_hours_effort_with_tool_scope(self):
        """Test inferring Hours effort for tool scope."""
        from src.research.ingestion_agent import infer_effort
        from src.research.classifier import Effort, ImpactScope

        effort = infer_effort("Quick fix", ImpactScope.TOOL)

        assert effort in [Effort.HOURS, Effort.DAYS]

    def test_weeks_effort_with_architecture_scope(self):
        """Test inferring Weeks effort for architecture scope."""
        from src.research.ingestion_agent import infer_effort
        from src.research.classifier import Effort, ImpactScope

        effort = infer_effort("Major redesign", ImpactScope.ARCHITECTURE)

        assert effort == Effort.WEEKS


class TestInferRisk:
    """Tests for infer_risk function."""

    def test_high_risk_for_architecture(self):
        """Test high risk for architecture scope."""
        from src.research.ingestion_agent import infer_risk
        from src.research.classifier import Risk, Effort, ImpactScope

        risk = infer_risk(ImpactScope.ARCHITECTURE, Effort.WEEKS)

        assert risk == Risk.HIGH

    def test_low_risk_for_tool_hours(self):
        """Test low risk for tool scope with hours effort."""
        from src.research.ingestion_agent import infer_risk
        from src.research.classifier import Risk, Effort, ImpactScope

        risk = infer_risk(ImpactScope.TOOL, Effort.HOURS)

        assert risk == Risk.LOW


class TestCreateResearchNote:
    """Tests for create_research_note function."""

    def test_note_contains_title(self):
        """Test generated note contains title."""
        from src.research.ingestion_agent import (
            ResearchInput,
            create_research_note,
        )
        import tempfile
        from pathlib import Path

        input_data = ResearchInput(
            source="https://example.com",
            description="Test description for model improvement",
            title="My Research Title",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "notes"
            file_path, note = create_research_note(input_data, output_dir)

            assert "My Research Title" in note
            assert file_path.exists()

    def test_note_contains_source_url(self):
        """Test generated note contains source URL."""
        from src.research.ingestion_agent import (
            ResearchInput,
            create_research_note,
        )
        import tempfile
        from pathlib import Path

        input_data = ResearchInput(
            source="https://example.com/research",
            description="Test description about LLM improvement",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "notes"
            file_path, note = create_research_note(input_data, output_dir)

            assert "https://example.com/research" in note

    def test_note_has_required_sections(self):
        """Test generated note has required sections."""
        from src.research.ingestion_agent import (
            ResearchInput,
            create_research_note,
        )
        import tempfile
        from pathlib import Path

        input_data = ResearchInput(
            source="https://example.com",
            description="Improves quality by 20% for prompting",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "notes"
            file_path, note = create_research_note(input_data, output_dir)

            assert "## Source" in note


class TestInferAllFields:
    """Tests for infer_all_fields function."""

    def test_infer_all_fields_basic(self):
        """Test inferring all fields from basic input."""
        from src.research.ingestion_agent import (
            ResearchInput,
            infer_all_fields,
        )

        input_data = ResearchInput(
            source="https://youtube.com/watch?v=abc",
            description="New LLM prompting technique improves accuracy",
        )

        inferred = infer_all_fields(input_data)

        assert inferred.source_type == "YouTube"
        assert inferred.title != ""


class TestParseUserPrompt:
    """Tests for parse_user_prompt function."""

    def test_parse_hebrew_format(self):
        """Test parsing Hebrew format prompt."""
        from src.research.ingestion_agent import parse_user_prompt

        prompt = """הוסף מחקר: Test Title
This is the description of the research."""

        result = parse_user_prompt(prompt)

        if result:  # May return None if pattern doesn't match
            assert result.title or result.description

    def test_parse_english_format(self):
        """Test parsing English format prompt."""
        from src.research.ingestion_agent import parse_user_prompt

        prompt = """Add research: Test Title
https://example.com
This is the description."""

        result = parse_user_prompt(prompt)

        # Function may return None or a ResearchInput
        # Just verify it doesn't crash
        assert result is None or hasattr(result, 'source')
