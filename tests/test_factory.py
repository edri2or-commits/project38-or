"""Tests for Agent Factory modules (Phase 3.2).

Tests cover:
- Code generation with Claude Sonnet 4.5
- Code validation (ruff, pydocstyle, security)
- Ralph Wiggum Loop (recursive fix cycle)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.factory.generator import generate_agent_code, estimate_cost, GeneratorError
from src.factory.validator import (
    validate_code,
    _check_security_patterns,
    format_validation_report,
)
from src.factory.ralph_loop import ralph_wiggum_loop, get_loop_summary, RalphLoopError


# Sample valid Python code
VALID_CODE = '''
import logging

logger = logging.getLogger(__name__)


class Agent:
    """Sample agent for testing.

    Args:
        config: Configuration dictionary
    """

    def __init__(self, config: dict) -> None:
        """Initialize agent.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        logger.info("Agent initialized")

    async def execute(self) -> dict:
        """Execute agent logic.

        Returns:
            dict: Execution result with status and result
        """
        return {"status": "success", "result": "Agent executed"}

    async def cleanup(self) -> None:
        """Cleanup agent resources."""
        logger.info("Agent cleaned up")
'''

# Code with security issues
INSECURE_CODE = '''
import subprocess

password = "hardcoded_secret"
api_key = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"

def run_command(cmd):
    subprocess.call(cmd, shell=True)
    result = eval(cmd)
    return result
'''


class TestGenerator:
    """Tests for generator.py - Claude code generation."""

    @pytest.mark.asyncio
    async def test_generate_agent_code_success(self):
        """Test successful agent code generation."""
        # Mock Anthropic client
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=VALID_CODE)]
        mock_message.model = "claude-sonnet-4-20250514"
        mock_message.usage = MagicMock(input_tokens=500, output_tokens=1500)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("src.factory.generator.Anthropic", return_value=mock_client):
            result = await generate_agent_code(
                description="Create a simple agent",
                api_key="test-key",
            )

        assert "code" in result
        assert "model" in result
        assert "tokens_used" in result
        assert result["tokens_used"] == 2000
        assert "class Agent" in result["code"]

    @pytest.mark.asyncio
    async def test_generate_agent_code_strips_markdown(self):
        """Test that markdown code blocks are stripped."""
        code_with_markdown = f"```python\n{VALID_CODE}\n```"

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=code_with_markdown)]
        mock_message.model = "claude-sonnet-4-20250514"
        mock_message.usage = MagicMock(input_tokens=500, output_tokens=1500)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("src.factory.generator.Anthropic", return_value=mock_client):
            result = await generate_agent_code(
                description="Test",
                api_key="test-key",
            )

        # Should not contain markdown markers
        assert "```python" not in result["code"]
        assert "```" not in result["code"]
        assert "class Agent" in result["code"]

    @pytest.mark.asyncio
    async def test_generate_agent_code_empty_description(self):
        """Test that empty description raises ValueError."""
        with pytest.raises(ValueError, match="Description cannot be empty"):
            await generate_agent_code(description="", api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_agent_code_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key not found"):
                await generate_agent_code(description="Test agent")

    @pytest.mark.asyncio
    async def test_generate_agent_code_api_error(self):
        """Test handling of Anthropic API errors."""
        mock_client = MagicMock()
        # Raise a generic exception to simulate API failure
        mock_client.messages.create.side_effect = Exception("API connection failed")

        with patch("src.factory.generator.Anthropic", return_value=mock_client):
            with pytest.raises(GeneratorError, match="Code generation failed"):
                await generate_agent_code(
                    description="Test",
                    api_key="test-key",
                )

    def test_estimate_cost(self):
        """Test cost estimation."""
        # 1000 tokens total (500 input + 500 output)
        cost = estimate_cost(1000)

        # Expected: (500/1M * $3) + (500/1M * $15) = $0.009
        assert cost == pytest.approx(0.009, rel=0.001)


class TestValidator:
    """Tests for validator.py - Code validation."""

    @pytest.mark.asyncio
    async def test_validate_code_success(self):
        """Test validation of valid code."""
        result = await validate_code(VALID_CODE, strict=False)

        assert result["passed"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_code_syntax_error(self):
        """Test detection of syntax errors."""
        bad_code = "def foo(\n    print('incomplete'"

        result = await validate_code(bad_code, strict=False)

        assert result["passed"] is False
        assert len(result["errors"]) > 0
        assert "Syntax error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_validate_code_security_issues(self):
        """Test detection of security anti-patterns."""
        result = await validate_code(INSECURE_CODE, strict=False)

        assert result["passed"] is False
        assert len(result["errors"]) > 0

        # Should detect eval(), hardcoded secrets, shell=True
        error_text = " ".join(result["errors"])
        assert "eval()" in error_text or "security" in error_text.lower()

    def test_check_security_patterns(self):
        """Test security pattern detection."""
        issues = _check_security_patterns(INSECURE_CODE)

        assert len(issues) > 0

        issue_text = " ".join(issues)
        assert "eval()" in issue_text or "exec()" in issue_text
        assert "credential" in issue_text.lower() or "key" in issue_text.lower()

    def test_format_validation_report(self):
        """Test validation report formatting."""
        result = {
            "passed": False,
            "errors": ["Syntax error at line 5"],
            "warnings": ["Missing docstring", "Line too long"],
        }

        report = format_validation_report(result)

        assert "FAILED" in report
        assert "Errors: 1" in report
        assert "Warnings: 2" in report
        assert "Syntax error" in report


class TestRalphLoop:
    """Tests for ralph_loop.py - Recursive fix cycle."""

    @pytest.mark.asyncio
    async def test_ralph_loop_passes_immediately(self):
        """Test that valid code passes without iterations."""
        # Mock validate_code to return success immediately
        with patch("src.factory.ralph_loop.validate_code") as mock_validate:
            mock_validate.return_value = {
                "passed": True,
                "errors": [],
                "warnings": [],
            }

            result = await ralph_wiggum_loop(
                code=VALID_CODE,
                api_key="test-key",
                max_iterations=5,
            )

        assert result["passed"] is True
        assert result["iterations"] == 1
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_ralph_loop_fixes_errors(self):
        """Test that Ralph loop fixes validation errors."""
        # Mock validation: fail first, then succeed
        validation_results = [
            {"passed": False, "errors": ["Syntax error"], "warnings": []},
            {"passed": True, "errors": [], "warnings": []},
        ]

        # Mock fixed code
        fixed_code = VALID_CODE

        # Mock Anthropic client for fix
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=fixed_code)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("src.factory.ralph_loop.validate_code") as mock_validate:
            with patch("src.factory.ralph_loop.Anthropic", return_value=mock_client):
                mock_validate.side_effect = validation_results

                result = await ralph_wiggum_loop(
                    code="bad code",
                    api_key="test-key",
                    max_iterations=5,
                )

        assert result["passed"] is True
        assert result["iterations"] == 2
        assert len(result["history"]) == 2

    @pytest.mark.asyncio
    async def test_ralph_loop_max_iterations_exceeded(self):
        """Test that loop raises error after max iterations."""
        # Always fail validation
        with patch("src.factory.ralph_loop.validate_code") as mock_validate:
            with patch("src.factory.ralph_loop.Anthropic") as mock_anthropic:
                mock_validate.return_value = {
                    "passed": False,
                    "errors": ["Unfixable error"],
                    "warnings": [],
                }

                # Mock fix attempt
                mock_client = MagicMock()
                mock_message = MagicMock()
                mock_message.content = [MagicMock(text="attempted fix")]
                mock_client.messages.create.return_value = mock_message
                mock_anthropic.return_value = mock_client

                with pytest.raises(RalphLoopError, match="Failed to fix code"):
                    await ralph_wiggum_loop(
                        code="bad code",
                        api_key="test-key",
                        max_iterations=3,
                    )

    @pytest.mark.asyncio
    async def test_ralph_loop_empty_code(self):
        """Test that empty code raises ValueError."""
        with pytest.raises(ValueError, match="Code cannot be empty"):
            await ralph_wiggum_loop(code="", api_key="test-key")

    def test_get_loop_summary(self):
        """Test loop summary generation."""
        result = {
            "passed": True,
            "iterations": 3,
            "errors": [],
            "warnings": ["Minor issue"],
            "history": [
                {
                    "iteration": 1,
                    "passed": False,
                    "errors": ["Error 1"],
                    "warnings": [],
                },
                {
                    "iteration": 2,
                    "passed": False,
                    "errors": ["Error 2"],
                    "warnings": [],
                },
                {"iteration": 3, "passed": True, "errors": [], "warnings": []},
            ],
        }

        summary = get_loop_summary(result)

        assert "SUCCESS" in summary
        assert "Iterations: 3" in summary
        assert "Iteration History:" in summary
