"""Tests for src/factory/generator.py - Agent Code Generator."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Skip all tests if dependencies not installed
pytest.importorskip("anthropic")
pytest.importorskip("jinja2")


class TestGeneratorError:
    """Tests for GeneratorError exception."""

    def test_generator_error_is_exception(self):
        """GeneratorError should be an Exception subclass."""
        from src.factory.generator import GeneratorError

        assert issubclass(GeneratorError, Exception)

    def test_generator_error_message(self):
        """GeneratorError should store message."""
        from src.factory.generator import GeneratorError

        error = GeneratorError("Test error message")
        assert str(error) == "Test error message"


class TestAgentGenerationPrompt:
    """Tests for AGENT_GENERATION_PROMPT template."""

    def test_prompt_is_jinja_template(self):
        """Prompt should be a Jinja2 Template."""
        from src.factory.generator import AGENT_GENERATION_PROMPT
        from jinja2 import Template

        assert isinstance(AGENT_GENERATION_PROMPT, Template)

    def test_prompt_renders_description(self):
        """Prompt should include description when rendered."""
        from src.factory.generator import AGENT_GENERATION_PROMPT

        result = AGENT_GENERATION_PROMPT.render(description="Monitor stock prices")
        assert "Monitor stock prices" in result

    def test_prompt_contains_requirements(self):
        """Prompt should contain code generation requirements."""
        from src.factory.generator import AGENT_GENERATION_PROMPT

        result = AGENT_GENERATION_PROMPT.render(description="Test")
        assert "Agent" in result
        assert "execute" in result
        assert "async" in result


class TestGenerateAgentCode:
    """Tests for generate_agent_code function."""

    @pytest.mark.asyncio
    async def test_empty_description_raises_value_error(self):
        """Empty description should raise ValueError."""
        from src.factory.generator import generate_agent_code

        with pytest.raises(ValueError, match="Description cannot be empty"):
            await generate_agent_code("")

    @pytest.mark.asyncio
    async def test_whitespace_description_raises_value_error(self):
        """Whitespace-only description should raise ValueError."""
        from src.factory.generator import generate_agent_code

        with pytest.raises(ValueError, match="Description cannot be empty"):
            await generate_agent_code("   ")

    @pytest.mark.asyncio
    async def test_no_api_key_raises_value_error(self):
        """Missing API key should raise ValueError."""
        from src.factory.generator import generate_agent_code

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key not found"):
                await generate_agent_code("Test description")

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Successful generation should return code dict."""
        from src.factory.generator import generate_agent_code

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="class Agent:\n    pass")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch("src.factory.generator.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = await generate_agent_code("Test agent", api_key="test-key")

        assert "code" in result
        assert "model" in result
        assert "tokens_used" in result
        assert result["tokens_used"] == 300

    @pytest.mark.asyncio
    async def test_strips_markdown_code_blocks_python(self):
        """Should strip ```python code blocks from response."""
        from src.factory.generator import generate_agent_code

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="```python\nclass Agent:\n    pass\n```")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch("src.factory.generator.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = await generate_agent_code("Test agent", api_key="test-key")

        assert "```" not in result["code"]
        assert "class Agent" in result["code"]

    @pytest.mark.asyncio
    async def test_strips_markdown_code_blocks_generic(self):
        """Should strip generic ``` code blocks from response."""
        from src.factory.generator import generate_agent_code

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="```\nclass Agent:\n    pass\n```")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch("src.factory.generator.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = await generate_agent_code("Test agent", api_key="test-key")

        assert "```" not in result["code"]

    @pytest.mark.asyncio
    async def test_empty_response_raises_generator_error(self):
        """Empty API response should raise GeneratorError."""
        from src.factory.generator import generate_agent_code, GeneratorError

        mock_response = MagicMock()
        mock_response.content = []

        with patch("src.factory.generator.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            with pytest.raises(GeneratorError, match="No content returned"):
                await generate_agent_code("Test agent", api_key="test-key")

    @pytest.mark.asyncio
    async def test_api_error_raises_generator_error(self):
        """API error should raise GeneratorError."""
        from src.factory.generator import generate_agent_code, GeneratorError
        from anthropic import APIError

        with patch("src.factory.generator.Anthropic") as mock_client:
            mock_client.return_value.messages.create.side_effect = APIError(
                message="API Error",
                request=MagicMock(),
                body=None,
            )
            with pytest.raises(GeneratorError, match="Failed to generate code"):
                await generate_agent_code("Test agent", api_key="test-key")

    @pytest.mark.asyncio
    async def test_uses_environment_api_key(self):
        """Should use ANTHROPIC_API_KEY from environment."""
        from src.factory.generator import generate_agent_code

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="class Agent:\n    pass")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-key"}):
            with patch("src.factory.generator.Anthropic") as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response
                await generate_agent_code("Test agent")
                mock_client.assert_called_with(api_key="env-key")

    @pytest.mark.asyncio
    async def test_custom_max_tokens(self):
        """Should use custom max_tokens parameter."""
        from src.factory.generator import generate_agent_code

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="class Agent:\n    pass")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch("src.factory.generator.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            await generate_agent_code("Test agent", api_key="test-key", max_tokens=8192)
            call_kwargs = mock_client.return_value.messages.create.call_args[1]
            assert call_kwargs["max_tokens"] == 8192


class TestEstimateCost:
    """Tests for estimate_cost function."""

    def test_zero_tokens(self):
        """Zero tokens should return zero cost."""
        from src.factory.generator import estimate_cost

        assert estimate_cost(0) == 0.0

    def test_small_token_count(self):
        """Small token count should return small cost."""
        from src.factory.generator import estimate_cost

        # 1000 tokens: 500 input @ $3/M + 500 output @ $15/M
        # = 0.0015 + 0.0075 = 0.009
        cost = estimate_cost(1000)
        assert cost == pytest.approx(0.009, rel=0.01)

    def test_million_tokens(self):
        """One million tokens should match pricing."""
        from src.factory.generator import estimate_cost

        # 1M tokens: 500K input @ $3/M + 500K output @ $15/M
        # = 1.5 + 7.5 = 9.0
        cost = estimate_cost(1_000_000)
        assert cost == pytest.approx(9.0, rel=0.01)

    def test_cost_scales_linearly(self):
        """Cost should scale linearly with tokens."""
        from src.factory.generator import estimate_cost

        cost_1k = estimate_cost(1000)
        cost_2k = estimate_cost(2000)
        assert cost_2k == pytest.approx(cost_1k * 2, rel=0.01)

    def test_odd_token_count(self):
        """Odd token count should still calculate correctly."""
        from src.factory.generator import estimate_cost

        # Floor division means 1001 tokens = 500 + 500 = 1000 effective
        cost = estimate_cost(1001)
        assert cost > 0
