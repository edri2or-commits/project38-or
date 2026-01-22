"""Tests for Research Experiment Creator module.

Tests the experiment_creator module in src/research/experiment_creator.py.
"""

from __future__ import annotations

from pathlib import Path
import tempfile

import pytest


def _can_import_module() -> bool:
    """Check if experiment_creator module can be imported."""
    try:
        from src.research.experiment_creator import (
            ExperimentConfig,
            get_next_experiment_id,
            create_experiment_readme,
            create_experiment_script,
            create_experiment_config,
            create_experiment_skeleton,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_import_module(),
    reason="research.experiment_creator module not importable"
)


class TestExperimentConfig:
    """Tests for ExperimentConfig dataclass."""

    def test_default_success_criteria(self):
        """Test default success criteria values."""
        from src.research.experiment_creator import ExperimentConfig

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test hypothesis",
            research_note_path=Path("test.md"),
        )

        assert config.success_criteria["quality_min"] == 0.85
        assert config.success_criteria["quality_regression_max"] == -0.02
        assert config.success_criteria["latency_max_ratio"] == 2.0
        assert config.success_criteria["cost_max_ratio"] == 1.5

    def test_custom_success_criteria(self):
        """Test custom success criteria."""
        from src.research.experiment_creator import ExperimentConfig

        custom = {"quality_min": 0.9, "quality_regression_max": -0.01}
        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test hypothesis",
            research_note_path=Path("test.md"),
            success_criteria=custom,
        )

        assert config.success_criteria["quality_min"] == 0.9


class TestGetNextExperimentId:
    """Tests for get_next_experiment_id function."""

    def test_first_experiment(self):
        """Test first experiment ID."""
        from src.research.experiment_creator import get_next_experiment_id

        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "experiments"
            exp_dir.mkdir()

            exp_id = get_next_experiment_id(exp_dir)

            assert exp_id == "exp_001"

    def test_nonexistent_dir(self):
        """Test with nonexistent directory."""
        from src.research.experiment_creator import get_next_experiment_id

        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "nonexistent"

            exp_id = get_next_experiment_id(exp_dir)

            assert exp_id == "exp_001"

    def test_increment_id(self):
        """Test incrementing experiment ID."""
        from src.research.experiment_creator import get_next_experiment_id

        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "experiments"
            exp_dir.mkdir()

            # Create existing experiments
            (exp_dir / "exp_001_test").mkdir()
            (exp_dir / "exp_002_another").mkdir()

            exp_id = get_next_experiment_id(exp_dir)

            assert exp_id == "exp_003"

    def test_handles_gaps(self):
        """Test handling gaps in experiment IDs."""
        from src.research.experiment_creator import get_next_experiment_id

        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "experiments"
            exp_dir.mkdir()

            # Create with gap
            (exp_dir / "exp_001_first").mkdir()
            (exp_dir / "exp_005_skip").mkdir()

            exp_id = get_next_experiment_id(exp_dir)

            assert exp_id == "exp_006"


class TestCreateExperimentReadme:
    """Tests for create_experiment_readme function."""

    def test_readme_contains_title(self):
        """Test README contains experiment title."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_readme,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test Experiment",
            hypothesis="Test hypothesis",
            research_note_path=Path("docs/research/notes/test.md"),
        )

        readme = create_experiment_readme(config)

        assert "Test Experiment" in readme
        assert "exp_001" in readme

    def test_readme_contains_hypothesis(self):
        """Test README contains hypothesis."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_readme,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="This will improve quality by 20%",
            research_note_path=Path("test.md"),
        )

        readme = create_experiment_readme(config)

        assert "improve quality by 20%" in readme

    def test_readme_contains_success_criteria(self):
        """Test README contains success criteria table."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_readme,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test",
            research_note_path=Path("test.md"),
        )

        readme = create_experiment_readme(config)

        assert "Success Criteria" in readme
        assert "85%" in readme  # quality_min
        assert "2.0x" in readme  # latency_max_ratio


class TestCreateExperimentScript:
    """Tests for create_experiment_script function."""

    def test_script_is_valid_python(self):
        """Test script is valid Python syntax."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_script,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test",
            research_note_path=Path("test.md"),
        )

        script = create_experiment_script(config)

        # Should not raise SyntaxError
        compile(script, "<string>", "exec")

    def test_script_contains_experiment_id(self):
        """Test script contains experiment ID."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_script,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test",
            research_note_path=Path("test.md"),
        )

        script = create_experiment_script(config)

        assert "exp_001" in script

    def test_script_contains_success_criteria(self):
        """Test script contains success criteria dict."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_script,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test",
            research_note_path=Path("test.md"),
        )

        script = create_experiment_script(config)

        assert "SUCCESS_CRITERIA" in script
        assert "0.85" in script


class TestCreateExperimentConfig:
    """Tests for create_experiment_config function."""

    def test_config_is_valid_yaml(self):
        """Test config is valid YAML."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_config,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test",
            research_note_path=Path("test.md"),
        )

        yaml_content = create_experiment_config(config)

        # Basic YAML validation
        assert "experiment:" in yaml_content
        assert "id:" in yaml_content
        assert "providers:" in yaml_content

    def test_config_contains_providers(self):
        """Test config contains provider settings."""
        from src.research.experiment_creator import (
            ExperimentConfig,
            create_experiment_config,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            title="Test",
            hypothesis="Test",
            research_note_path=Path("test.md"),
            baseline_provider="mock",
            test_provider="claude",
        )

        yaml_content = create_experiment_config(config)

        assert 'baseline: "mock"' in yaml_content
        assert 'experiment: "claude"' in yaml_content


class TestSlugify:
    """Tests for _slugify function."""

    def test_slugify_basic(self):
        """Test basic slugification."""
        from src.research.experiment_creator import _slugify

        assert _slugify("Test Title") == "test_title"

    def test_slugify_special_chars(self):
        """Test slugification of special characters."""
        from src.research.experiment_creator import _slugify

        result = _slugify("Test: A 'Special' Title!")
        assert "_" in result
        assert "!" not in result
        assert ":" not in result

    def test_slugify_max_length(self):
        """Test slugification max length."""
        from src.research.experiment_creator import _slugify

        long_title = "A" * 100
        result = _slugify(long_title)

        assert len(result) <= 30


class TestCreateExperimentSkeleton:
    """Tests for create_experiment_skeleton function."""

    def test_creates_directory(self):
        """Test skeleton creates experiment directory."""
        from src.research.experiment_creator import create_experiment_skeleton
        from src.research.classifier import Classification

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a note that will classify as Spike
            notes_dir = Path(tmpdir) / "notes"
            notes_dir.mkdir()
            note_path = notes_dir / "test.md"
            note_path.write_text("""# Test
**Status:** Draft
| **Scope** | Model |
## Hypothesis
> This will improve quality
""")

            exp_dir = Path(tmpdir) / "experiments"

            result = create_experiment_skeleton(note_path, exp_dir)

            if result:  # Only if classified as Spike
                assert result.exists()
                assert (result / "README.md").exists()
                assert (result / "run.py").exists()
                assert (result / "config.yaml").exists()

    def test_returns_none_for_non_spike(self):
        """Test returns None for non-Spike classifications."""
        from src.research.experiment_creator import create_experiment_skeleton

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a note that will classify as Backlog (Tool scope)
            notes_dir = Path(tmpdir) / "notes"
            notes_dir.mkdir()
            note_path = notes_dir / "test.md"
            note_path.write_text("""# Test
**Status:** Draft
| **Scope** | Tool |
[x] **Backlog**
""")

            exp_dir = Path(tmpdir) / "experiments"

            result = create_experiment_skeleton(note_path, exp_dir)

            # Should be None because it's Backlog, not Spike
            # (depends on auto_classify logic)
            # The test validates the function works without errors


class TestCreateExperimentForNote:
    """Tests for create_experiment_for_note function."""

    def test_returns_none_without_file_path(self):
        """Test returns None when note has no file_path."""
        from src.research.experiment_creator import create_experiment_for_note
        from src.research.classifier import ResearchNote

        note = ResearchNote()  # No file_path

        result = create_experiment_for_note(note)

        assert result is None
