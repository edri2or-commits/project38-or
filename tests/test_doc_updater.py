"""
Tests for doc_updater module.

Verifies changelog management, docstring checking, and utility functions.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.doc_updater import (
    ChangelogEntry,
    ChangelogManager,
    DocstringChecker,
    detect_secrets_in_content,
    get_changed_python_files,
)


class TestChangelogEntry:
    """Test ChangelogEntry class."""

    def test_valid_entry(self):
        """Test creating a valid changelog entry."""
        entry = ChangelogEntry("Added", "New feature X")
        assert entry.category == "Added"
        assert entry.description == "New feature X"

    def test_invalid_category(self):
        """Test that invalid category raises ValueError."""
        with pytest.raises(ValueError, match="Invalid category"):
            ChangelogEntry("InvalidCategory", "Something")

    def test_string_format(self):
        """Test entry formatting as markdown."""
        entry = ChangelogEntry("Fixed", "Bug in authentication")
        assert str(entry) == "- Bug in authentication"


class TestChangelogManager:
    """Test ChangelogManager class."""

    @pytest.fixture
    def sample_changelog(self):
        """Create a sample changelog file."""
        content = """# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Initial feature

### Changed
- Updated documentation

## [1.0.0] - 2026-01-01

### Added
- First release
"""
        return content

    @pytest.fixture
    def temp_changelog(self, sample_changelog):
        """Create a temporary changelog file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(sample_changelog)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_read_current(self, temp_changelog):
        """Test reading current changelog."""
        manager = ChangelogManager(temp_changelog)
        content = manager.read_current()
        assert "[Unreleased]" in content
        assert "Initial feature" in content

    def test_read_nonexistent(self):
        """Test reading nonexistent changelog raises error."""
        manager = ChangelogManager("/nonexistent/changelog.md")
        with pytest.raises(FileNotFoundError):
            manager.read_current()

    def test_add_entry(self, temp_changelog):
        """Test adding a new entry."""
        manager = ChangelogManager(temp_changelog)
        manager.add_entry("Added", "New authentication system")
        assert len(manager.entries) == 1
        assert manager.entries[0].category == "Added"

    def test_write_new_category(self, temp_changelog):
        """Test writing entry in new category."""
        manager = ChangelogManager(temp_changelog)
        manager.add_entry("Security", "Fixed XSS vulnerability")

        updated = manager.write(dry_run=True)
        assert "### Security" in updated
        assert "Fixed XSS vulnerability" in updated

    def test_write_existing_category(self, temp_changelog):
        """Test writing entry in existing category."""
        manager = ChangelogManager(temp_changelog)
        manager.add_entry("Added", "Another new feature")

        updated = manager.write(dry_run=True)
        assert "Another new feature" in updated
        # Should only have one "### Added" section in Unreleased
        unreleased_section = updated.split("## [1.0.0]")[0]
        assert unreleased_section.count("### Added") == 1

    def test_write_multiple_entries(self, temp_changelog):
        """Test writing multiple entries."""
        manager = ChangelogManager(temp_changelog)
        manager.add_entry("Added", "Feature A")
        manager.add_entry("Added", "Feature B")
        manager.add_entry("Fixed", "Bug X")

        updated = manager.write(dry_run=True)
        assert "Feature A" in updated
        assert "Feature B" in updated
        assert "Bug X" in updated
        assert "### Fixed" in updated

    def test_find_unreleased_section(self, temp_changelog, sample_changelog):
        """Test finding [Unreleased] section boundaries."""
        manager = ChangelogManager(temp_changelog)
        start, end = manager._find_unreleased_section(sample_changelog)
        assert start >= 0
        assert end > start

    def test_missing_unreleased_section(self):
        """Test error when [Unreleased] section missing."""
        content = "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n### Added\n- Something"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            manager = ChangelogManager(temp_path)
            manager.add_entry("Added", "Test")

            with pytest.raises(ValueError, match="Could not find \\[Unreleased\\]"):
                manager.write(dry_run=True)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestDocstringChecker:
    """Test DocstringChecker class."""

    def test_init(self):
        """Test DocstringChecker initialization."""
        checker = DocstringChecker("src")
        assert checker.base_path == Path("src")

    @patch("subprocess.run")
    def test_check_success(self, mock_run):
        """Test successful docstring check."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        checker = DocstringChecker()
        success, output = checker.check()

        assert success is True
        assert "✅" in output

    @patch("subprocess.run")
    def test_check_failure(self, mock_run):
        """Test failed docstring check."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="src/test.py:1: Missing docstring"
        )

        checker = DocstringChecker()
        success, output = checker.check()

        assert success is False
        assert "Missing docstring" in output

    @patch("subprocess.run")
    def test_check_file_not_found(self, mock_run):
        """Test when pydocstyle is not installed."""
        mock_run.side_effect = FileNotFoundError()

        checker = DocstringChecker()
        success, output = checker.check()

        assert success is False
        assert "not installed" in output


class TestUtilityFunctions:
    """Test utility functions."""

    @patch("subprocess.run")
    def test_get_changed_python_files(self, mock_run):
        """Test getting changed Python files."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=" M src/secrets_manager.py\n A src/new_module.py\n",
        )

        files = get_changed_python_files()
        assert "src/secrets_manager.py" in files
        assert "src/new_module.py" in files

    @patch("subprocess.run")
    def test_get_changed_files_no_git(self, mock_run):
        """Test when git is not available."""
        mock_run.side_effect = Exception("git not found")

        files = get_changed_python_files()
        assert files == []

    def test_detect_secrets_api_key(self):
        """Test detecting API keys."""
        content = "OPENAI_API_KEY=sk-1234567890abcdefghij"
        secrets = detect_secrets_in_content(content)
        assert len(secrets) > 0

    def test_detect_secrets_github_pat(self):
        """Test detecting GitHub PAT."""
        content = "token = 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'"
        secrets = detect_secrets_in_content(content)
        assert len(secrets) > 0

    def test_detect_secrets_bearer_token(self):
        """Test detecting Bearer tokens."""
        content = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        secrets = detect_secrets_in_content(content)
        assert len(secrets) > 0

    def test_detect_no_secrets(self):
        """Test clean content without secrets."""
        content = """
        # Documentation
        This is a sample documentation file.
        No secrets here, just regular text.
        """
        secrets = detect_secrets_in_content(content)
        assert len(secrets) == 0


class TestIntegration:
    """Integration tests for doc_updater."""

    def test_full_changelog_workflow(self):
        """Test complete changelog update workflow."""
        # Create temporary changelog
        content = """# Changelog

## [Unreleased]

## [1.0.0] - 2026-01-01

### Added
- Initial release
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Create manager and add entries
            manager = ChangelogManager(temp_path)
            manager.add_entry("Added", "DocUpdater skill")
            manager.add_entry("Added", "Helper utilities")
            manager.add_entry("Fixed", "Documentation drift issue")

            # Write changes
            updated = manager.write(dry_run=False)

            # Verify
            assert "DocUpdater skill" in updated
            assert "Helper utilities" in updated
            assert "Documentation drift issue" in updated
            assert updated.count("## [Unreleased]") == 1

            # Verify file was actually written
            written_content = Path(temp_path).read_text()
            assert "DocUpdater skill" in written_content

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @patch("subprocess.run")
    def test_changed_files_and_docstring_check(self, mock_run):
        """Test integration between changed files detection and docstring check."""
        # Mock git status to return changed files
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=" M src/doc_updater.py\n",
        )

        changed_files = get_changed_python_files()
        assert len(changed_files) > 0

        # Mock pydocstyle check
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        checker = DocstringChecker()
        success, _ = checker.check(changed_files[0])
        assert success is True
