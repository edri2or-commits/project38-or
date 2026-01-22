"""Tests for src/factory/ralph_loop.py - Ralph Wiggum Loop."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Skip all tests if dependencies not installed
pytest.importorskip("anthropic")
pytest.importorskip("jinja2")


class TestRalphLoopError:
    """Tests for RalphLoopError exception."""

    def test_ralph_loop_error_is_exception(self):
        """RalphLoopError should be an Exception subclass."""
        from src.factory.ralph_loop import RalphLoopError

        assert issubclass(RalphLoopError, Exception)

    def test_ralph_loop_error_message(self):
        """RalphLoopError should store message."""
        from src.factory.ralph_loop import RalphLoopError

        error = RalphLoopError("Max iterations reached")
        assert str(error) == "Max iterations reached"


class TestCodeFixPrompt:
    """Tests for CODE_FIX_PROMPT template."""

    def test_prompt_is_jinja_template(self):
        """Prompt should be a Jinja2 Template."""
        from src.factory.ralph_loop import CODE_FIX_PROMPT
        from jinja2 import Template

        assert isinstance(CODE_FIX_PROMPT, Template)

    def test_prompt_renders_code(self):
        """Prompt should include code when rendered."""
        from src.factory.ralph_loop import CODE_FIX_PROMPT

        result = CODE_FIX_PROMPT.render(
            code="def broken():\n    pass",
            errors=["Error 1"],
            warnings=[],
            attempt_number=1,
            previous_fix=None,
        )
        assert "def broken" in result

    def test_prompt_renders_errors(self):
        """Prompt should include errors."""
        from src.factory.ralph_loop import CODE_FIX_PROMPT

        result = CODE_FIX_PROMPT.render(
            code="code",
            errors=["Error message one", "Error message two"],
            warnings=[],
            attempt_number=1,
            previous_fix=None,
        )
        assert "Error message one" in result
        assert "Error message two" in result

    def test_prompt_renders_warnings(self):
        """Prompt should include warnings."""
        from src.factory.ralph_loop import CODE_FIX_PROMPT

        result = CODE_FIX_PROMPT.render(
            code="code",
            errors=[],
            warnings=["Warning 1"],
            attempt_number=1,
            previous_fix=None,
        )
        assert "Warning 1" in result

    def test_prompt_renders_previous_fix(self):
        """Prompt should include previous fix when provided."""
        from src.factory.ralph_loop import CODE_FIX_PROMPT

        result = CODE_FIX_PROMPT.render(
            code="code",
            errors=["Error"],
            warnings=[],
            attempt_number=2,
            previous_fix="previous fix code",
        )
        assert "previous fix code" in result


class TestRalphWiggumLoop:
    """Tests for ralph_wiggum_loop function."""

    @pytest.mark.asyncio
    async def test_empty_code_raises_value_error(self):
        """Empty code should raise ValueError."""
        from src.factory.ralph_loop import ralph_wiggum_loop

        with pytest.raises(ValueError, match="Code cannot be empty"):
            await ralph_wiggum_loop("")

    @pytest.mark.asyncio
    async def test_whitespace_code_raises_value_error(self):
        """Whitespace-only code should raise ValueError."""
        from src.factory.ralph_loop import ralph_wiggum_loop

        with pytest.raises(ValueError, match="Code cannot be empty"):
            await ralph_wiggum_loop("   ")

    @pytest.mark.asyncio
    async def test_valid_code_passes_first_iteration(self):
        """Valid code should pass on first iteration."""
        from src.factory.ralph_loop import ralph_wiggum_loop

        code = "print('hello')"

        with patch("src.factory.ralph_loop.validate_code", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {"passed": True, "errors": [], "warnings": []}
            result = await ralph_wiggum_loop(code, api_key="test-key")

        assert result["passed"] is True
        assert result["iterations"] == 1
        assert result["errors"] == []
        assert len(result["history"]) == 1

    @pytest.mark.asyncio
    async def test_code_fixed_after_iterations(self):
        """Code should be fixed after iterations."""
        from src.factory.ralph_loop import ralph_wiggum_loop

        code = "broken code"

        validation_results = [
            {"passed": False, "errors": ["Error 1"], "warnings": []},
            {"passed": False, "errors": ["Error 2"], "warnings": []},
            {"passed": True, "errors": [], "warnings": []},
        ]

        mock_validate = AsyncMock(side_effect=validation_results)

        with patch("src.factory.ralph_loop.validate_code", mock_validate):
            with patch("src.factory.ralph_loop._fix_code_with_claude", new_callable=AsyncMock) as mock_fix:
                mock_fix.return_value = "fixed code"
                result = await ralph_wiggum_loop(code, api_key="test-key")

        assert result["passed"] is True
        assert result["iterations"] == 3

    @pytest.mark.asyncio
    async def test_max_iterations_raises_error(self):
        """Exceeding max iterations should raise RalphLoopError."""
        from src.factory.ralph_loop import ralph_wiggum_loop, RalphLoopError

        code = "broken code"

        with patch("src.factory.ralph_loop.validate_code", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {"passed": False, "errors": ["Error"], "warnings": []}
            with patch("src.factory.ralph_loop._fix_code_with_claude", new_callable=AsyncMock) as mock_fix:
                mock_fix.return_value = "still broken"
                with pytest.raises(RalphLoopError, match="Failed to fix code after 3 iterations"):
                    await ralph_wiggum_loop(code, api_key="test-key", max_iterations=3)

    @pytest.mark.asyncio
    async def test_history_recorded(self):
        """History should record each iteration."""
        from src.factory.ralph_loop import ralph_wiggum_loop

        code = "code"

        validation_results = [
            {"passed": False, "errors": ["Error 1"], "warnings": ["Warning 1"]},
            {"passed": True, "errors": [], "warnings": []},
        ]

        mock_validate = AsyncMock(side_effect=validation_results)

        with patch("src.factory.ralph_loop.validate_code", mock_validate):
            with patch("src.factory.ralph_loop._fix_code_with_claude", new_callable=AsyncMock) as mock_fix:
                mock_fix.return_value = "fixed"
                result = await ralph_wiggum_loop(code, api_key="test-key")

        assert len(result["history"]) == 2
        assert result["history"][0]["iteration"] == 1
        assert result["history"][0]["passed"] is False
        assert result["history"][1]["iteration"] == 2
        assert result["history"][1]["passed"] is True

    @pytest.mark.asyncio
    async def test_strict_mode_passed_to_validate(self):
        """Strict mode should be passed to validate_code."""
        from src.factory.ralph_loop import ralph_wiggum_loop

        code = "code"

        with patch("src.factory.ralph_loop.validate_code", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {"passed": True, "errors": [], "warnings": []}
            await ralph_wiggum_loop(code, api_key="test-key", strict=False)
            mock_validate.assert_called_with(code, strict=False)

    @pytest.mark.asyncio
    async def test_fix_error_continues_loop(self):
        """Fix error should continue to next iteration."""
        from src.factory.ralph_loop import ralph_wiggum_loop

        code = "broken"

        validation_results = [
            {"passed": False, "errors": ["Error"], "warnings": []},
            {"passed": False, "errors": ["Error"], "warnings": []},
            {"passed": True, "errors": [], "warnings": []},
        ]

        mock_validate = AsyncMock(side_effect=validation_results)

        with patch("src.factory.ralph_loop.validate_code", mock_validate):
            with patch("src.factory.ralph_loop._fix_code_with_claude", new_callable=AsyncMock) as mock_fix:
                # First call raises error, second succeeds
                mock_fix.side_effect = [Exception("API Error"), "fixed code"]
                result = await ralph_wiggum_loop(code, api_key="test-key")

        # Should still succeed after error
        assert result["passed"] is True


class TestFixCodeWithClaude:
    """Tests for _fix_code_with_claude function."""

    @pytest.mark.asyncio
    async def test_no_api_key_raises_value_error(self):
        """Missing API key should raise ValueError."""
        from src.factory.ralph_loop import _fix_code_with_claude

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key not found"):
                await _fix_code_with_claude(
                    code="broken",
                    errors=["Error"],
                    warnings=[],
                    attempt_number=1,
                    previous_fix=None,
                    api_key=None,
                )

    @pytest.mark.asyncio
    async def test_successful_fix(self):
        """Successful fix should return fixed code."""
        from src.factory.ralph_loop import _fix_code_with_claude

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="fixed code")]

        with patch("src.factory.ralph_loop.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = await _fix_code_with_claude(
                code="broken",
                errors=["Error"],
                warnings=[],
                attempt_number=1,
                previous_fix=None,
                api_key="test-key",
            )

        assert result == "fixed code"

    @pytest.mark.asyncio
    async def test_strips_markdown(self):
        """Should strip markdown code blocks."""
        from src.factory.ralph_loop import _fix_code_with_claude

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="```python\nfixed code\n```")]

        with patch("src.factory.ralph_loop.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = await _fix_code_with_claude(
                code="broken",
                errors=["Error"],
                warnings=[],
                attempt_number=1,
                previous_fix=None,
                api_key="test-key",
            )

        assert "```" not in result
        assert "fixed code" in result

    @pytest.mark.asyncio
    async def test_uses_environment_api_key(self):
        """Should use ANTHROPIC_API_KEY from environment."""
        from src.factory.ralph_loop import _fix_code_with_claude

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="fixed")]

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-key"}):
            with patch("src.factory.ralph_loop.Anthropic") as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response
                await _fix_code_with_claude(
                    code="broken",
                    errors=["Error"],
                    warnings=[],
                    attempt_number=1,
                    previous_fix=None,
                    api_key=None,
                )
                mock_client.assert_called_with(api_key="env-key")


class TestGetLoopSummary:
    """Tests for get_loop_summary function."""

    def test_success_summary(self):
        """Success result should show SUCCESS."""
        from src.factory.ralph_loop import get_loop_summary

        result = {
            "passed": True,
            "iterations": 2,
            "errors": [],
            "warnings": ["Warning 1"],
            "history": [
                {"iteration": 1, "passed": False, "errors": ["Error"], "warnings": []},
                {"iteration": 2, "passed": True, "errors": [], "warnings": []},
            ],
        }
        summary = get_loop_summary(result)
        assert "SUCCESS" in summary
        assert "Iterations: 2" in summary

    def test_failed_summary(self):
        """Failed result should show FAILED."""
        from src.factory.ralph_loop import get_loop_summary

        result = {
            "passed": False,
            "iterations": 3,
            "errors": ["Remaining error"],
            "warnings": [],
            "history": [],
        }
        summary = get_loop_summary(result)
        assert "FAILED" in summary
        assert "Remaining error" in summary

    def test_history_in_summary(self):
        """Summary should include iteration history."""
        from src.factory.ralph_loop import get_loop_summary

        result = {
            "passed": True,
            "iterations": 2,
            "errors": [],
            "warnings": [],
            "history": [
                {"iteration": 1, "passed": False, "errors": ["E1"], "warnings": ["W1"]},
                {"iteration": 2, "passed": True, "errors": [], "warnings": []},
            ],
        }
        summary = get_loop_summary(result)
        assert "Iteration 1" in summary
        assert "Iteration 2" in summary
        assert "✓" in summary or "✗" in summary

    def test_summary_includes_error_count(self):
        """Summary should include error count."""
        from src.factory.ralph_loop import get_loop_summary

        result = {
            "passed": False,
            "iterations": 1,
            "errors": ["Error 1", "Error 2"],
            "warnings": [],
            "history": [],
        }
        summary = get_loop_summary(result)
        assert "Final Errors: 2" in summary

    def test_summary_includes_warning_count(self):
        """Summary should include warning count."""
        from src.factory.ralph_loop import get_loop_summary

        result = {
            "passed": True,
            "iterations": 1,
            "errors": [],
            "warnings": ["W1", "W2", "W3"],
            "history": [],
        }
        summary = get_loop_summary(result)
        assert "Final Warnings: 3" in summary
