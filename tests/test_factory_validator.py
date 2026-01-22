"""Tests for src/factory/validator.py - Code Validator."""

import pytest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

# Skip all tests if dependencies not installed (factory/__init__.py imports anthropic)
pytest.importorskip("anthropic")
pytest.importorskip("jinja2")


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error_is_exception(self):
        """ValidationError should be an Exception subclass."""
        from src.factory.validator import ValidationError

        assert issubclass(ValidationError, Exception)

    def test_validation_error_message(self):
        """ValidationError should store message."""
        from src.factory.validator import ValidationError

        error = ValidationError("Validation failed")
        assert str(error) == "Validation failed"


class TestSecurityPatterns:
    """Tests for SECURITY_PATTERNS."""

    def test_security_patterns_is_list(self):
        """SECURITY_PATTERNS should be a list."""
        from src.factory.validator import SECURITY_PATTERNS

        assert isinstance(SECURITY_PATTERNS, list)

    def test_patterns_have_message(self):
        """Each pattern should have regex and message."""
        from src.factory.validator import SECURITY_PATTERNS

        for pattern, message in SECURITY_PATTERNS:
            assert isinstance(pattern, str)
            assert isinstance(message, str)
            assert len(message) > 0


class TestCheckSecurityPatterns:
    """Tests for _check_security_patterns function."""

    def test_clean_code_returns_empty_list(self):
        """Clean code should return no security issues."""
        from src.factory.validator import _check_security_patterns

        code = """
def hello():
    return "Hello, World!"
"""
        issues = _check_security_patterns(code)
        assert issues == []

    def test_detects_eval(self):
        """Should detect eval() usage."""
        from src.factory.validator import _check_security_patterns

        code = "result = eval(user_input)"
        issues = _check_security_patterns(code)
        assert len(issues) >= 1
        assert any("eval" in issue.lower() for issue in issues)

    def test_detects_exec(self):
        """Should detect exec() usage."""
        from src.factory.validator import _check_security_patterns

        code = "exec(code_string)"
        issues = _check_security_patterns(code)
        assert len(issues) >= 1
        assert any("exec" in issue.lower() for issue in issues)

    def test_detects_hardcoded_password(self):
        """Should detect hardcoded password."""
        from src.factory.validator import _check_security_patterns

        code = 'password = "secret123"'
        issues = _check_security_patterns(code)
        assert len(issues) >= 1
        assert any("credential" in issue.lower() for issue in issues)

    def test_detects_api_key_pattern(self):
        """Should detect API key patterns."""
        from src.factory.validator import _check_security_patterns

        code = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890abcd"'
        issues = _check_security_patterns(code)
        assert len(issues) >= 1

    def test_detects_shell_true_subprocess(self):
        """Should detect subprocess with shell=True."""
        from src.factory.validator import _check_security_patterns

        code = "subprocess.call(cmd, shell=True)"
        issues = _check_security_patterns(code)
        assert len(issues) >= 1
        assert any("shell" in issue.lower() for issue in issues)

    def test_reports_line_number(self):
        """Should report correct line number."""
        from src.factory.validator import _check_security_patterns

        code = """line1
line2
result = eval(x)
line4"""
        issues = _check_security_patterns(code)
        assert len(issues) >= 1
        assert "line 3" in issues[0]


class TestRunRuffFormat:
    """Tests for _run_ruff_format function."""

    def test_formatted_code_passes(self):
        """Well-formatted code should pass."""
        from src.factory.validator import _run_ruff_format

        code = 'print("hello")\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = _run_ruff_format(Path(f.name))
        assert result["passed"] is True

    def test_ruff_not_found_returns_passed(self):
        """Missing ruff should return passed with warning."""
        from src.factory.validator import _run_ruff_format

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _run_ruff_format(Path("/tmp/test.py"))
        assert result["passed"] is True
        assert "ruff not installed" in result["messages"]

    def test_timeout_returns_failed(self):
        """Timeout should return failed."""
        from src.factory.validator import _run_ruff_format
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 10)):
            result = _run_ruff_format(Path("/tmp/test.py"))
        assert result["passed"] is False
        assert any("timed out" in msg for msg in result["messages"])


class TestRunRuffLint:
    """Tests for _run_ruff_lint function."""

    def test_clean_code_passes(self):
        """Clean code should pass lint."""
        from src.factory.validator import _run_ruff_lint

        code = '''"""Module docstring."""

def hello() -> str:
    """Return greeting."""
    return "hello"
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = _run_ruff_lint(Path(f.name))
        # May or may not pass depending on ruff config, but should return valid structure
        assert "passed" in result
        assert "messages" in result

    def test_ruff_not_found_returns_passed(self):
        """Missing ruff should return passed with warning."""
        from src.factory.validator import _run_ruff_lint

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _run_ruff_lint(Path("/tmp/test.py"))
        assert result["passed"] is True
        assert "ruff not installed" in result["messages"]

    def test_timeout_returns_failed(self):
        """Timeout should return failed."""
        from src.factory.validator import _run_ruff_lint
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 10)):
            result = _run_ruff_lint(Path("/tmp/test.py"))
        assert result["passed"] is False


class TestRunPydocstyle:
    """Tests for _run_pydocstyle function."""

    def test_pydocstyle_not_found_returns_passed(self):
        """Missing pydocstyle should return passed with warning."""
        from src.factory.validator import _run_pydocstyle

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _run_pydocstyle(Path("/tmp/test.py"))
        assert result["passed"] is True
        assert "pydocstyle not installed" in result["messages"]

    def test_timeout_returns_failed(self):
        """Timeout should return failed."""
        from src.factory.validator import _run_pydocstyle
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pydocstyle", 10)):
            result = _run_pydocstyle(Path("/tmp/test.py"))
        assert result["passed"] is False


class TestValidateCode:
    """Tests for validate_code function."""

    @pytest.mark.asyncio
    async def test_empty_code_raises_value_error(self):
        """Empty code should raise ValueError."""
        from src.factory.validator import validate_code

        with pytest.raises(ValueError, match="Code cannot be empty"):
            await validate_code("")

    @pytest.mark.asyncio
    async def test_whitespace_code_raises_value_error(self):
        """Whitespace-only code should raise ValueError."""
        from src.factory.validator import validate_code

        with pytest.raises(ValueError, match="Code cannot be empty"):
            await validate_code("   \n  ")

    @pytest.mark.asyncio
    async def test_syntax_error_returns_error(self):
        """Syntax error should return errors."""
        from src.factory.validator import validate_code

        code = "def broken("  # Missing closing paren
        result = await validate_code(code)
        assert result["passed"] is False
        assert len(result["errors"]) > 0
        assert any("syntax" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_valid_code_returns_passed(self):
        """Valid code should pass validation."""
        from src.factory.validator import validate_code

        code = '''"""Module docstring."""


def hello() -> str:
    """Return greeting.

    Returns:
        Greeting string.
    """
    return "hello"
'''
        # Mock external tools to always pass
        with patch("src.factory.validator._run_ruff_format", return_value={"passed": True, "messages": []}):
            with patch("src.factory.validator._run_ruff_lint", return_value={"passed": True, "messages": []}):
                with patch("src.factory.validator._run_pydocstyle", return_value={"passed": True, "messages": []}):
                    result = await validate_code(code)
        assert result["passed"] is True
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_security_issues_are_errors(self):
        """Security issues should be in errors."""
        from src.factory.validator import validate_code

        code = '''"""Module."""


def run(cmd: str) -> str:
    """Run command.

    Args:
        cmd: Command string.

    Returns:
        Result.
    """
    return eval(cmd)
'''
        with patch("src.factory.validator._run_ruff_format", return_value={"passed": True, "messages": []}):
            with patch("src.factory.validator._run_ruff_lint", return_value={"passed": True, "messages": []}):
                with patch("src.factory.validator._run_pydocstyle", return_value={"passed": True, "messages": []}):
                    result = await validate_code(code)
        assert result["passed"] is False
        assert any("security" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_non_strict_skips_pydocstyle(self):
        """Non-strict mode should skip pydocstyle."""
        from src.factory.validator import validate_code

        code = '''"""Module."""


def hello():
    return "hello"
'''
        with patch("src.factory.validator._run_ruff_format", return_value={"passed": True, "messages": []}):
            with patch("src.factory.validator._run_ruff_lint", return_value={"passed": True, "messages": []}):
                with patch("src.factory.validator._run_pydocstyle") as mock_pydocstyle:
                    await validate_code(code, strict=False)
                    mock_pydocstyle.assert_not_called()

    @pytest.mark.asyncio
    async def test_lint_errors_categorized(self):
        """Lint errors should be categorized by severity."""
        from src.factory.validator import validate_code

        code = '''"""Module."""


def hello():
    """Say hello."""
    return "hello"
'''
        lint_messages = [
            "/tmp/test.py:5:1: E901 IndentationError",
            "/tmp/test.py:5:1: W291 trailing whitespace",
        ]
        with patch("src.factory.validator._run_ruff_format", return_value={"passed": True, "messages": []}):
            with patch("src.factory.validator._run_ruff_lint", return_value={"passed": False, "messages": lint_messages}):
                with patch("src.factory.validator._run_pydocstyle", return_value={"passed": True, "messages": []}):
                    result = await validate_code(code)
        # E9 errors should be in errors, others in warnings
        assert any("E901" in e or "E9" in e for e in result["errors"])


class TestFormatValidationReport:
    """Tests for format_validation_report function."""

    def test_passed_report(self):
        """Passed validation should show PASSED."""
        from src.factory.validator import format_validation_report

        result = {"passed": True, "errors": [], "warnings": []}
        report = format_validation_report(result)
        assert "PASSED" in report

    def test_failed_report(self):
        """Failed validation should show FAILED."""
        from src.factory.validator import format_validation_report

        result = {"passed": False, "errors": ["Error 1"], "warnings": []}
        report = format_validation_report(result)
        assert "FAILED" in report

    def test_report_includes_errors(self):
        """Report should include errors."""
        from src.factory.validator import format_validation_report

        result = {"passed": False, "errors": ["Error message 1", "Error message 2"], "warnings": []}
        report = format_validation_report(result)
        assert "Error message 1" in report
        assert "Error message 2" in report
        assert "Errors: 2" in report

    def test_report_includes_warnings(self):
        """Report should include warnings."""
        from src.factory.validator import format_validation_report

        result = {"passed": True, "errors": [], "warnings": ["Warning 1"]}
        report = format_validation_report(result)
        assert "Warning 1" in report
        assert "Warnings: 1" in report

    def test_clean_report_message(self):
        """Clean validation should show success message."""
        from src.factory.validator import format_validation_report

        result = {"passed": True, "errors": [], "warnings": []}
        report = format_validation_report(result)
        assert "All checks passed" in report
