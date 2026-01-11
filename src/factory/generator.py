"""
Agent Code Generator - Natural Language to Python Agent.

Uses Claude Sonnet 4.5 via Anthropic API to generate Python code from
natural language descriptions.
"""

import os
import logging
from typing import Dict, Optional
from jinja2 import Template
from anthropic import Anthropic, APIError

logger = logging.getLogger(__name__)


# Prompt template for agent code generation
AGENT_GENERATION_PROMPT = Template("""You are an expert Python developer specializing in creating autonomous agents.

Your task is to generate a complete, production-ready Python agent based on the following description:

Description: {{ description }}

Requirements:
1. Generate a Python class called Agent with the following structure:
   - __init__(self, config: dict) method
   - async def execute(self) -> dict method (main execution logic)
   - async def cleanup(self) method (cleanup resources)

2. The agent must be self-contained and include:
   - Proper error handling (try/except blocks)
   - Logging using Python's logging module
   - Type hints for all methods
   - Google-style docstrings
   - Validation of inputs

3. Code style:
   - Follow PEP 8
   - Use async/await for I/O operations
   - No hardcoded credentials or API keys (use config dict)
   - Include imports at the top

4. Security considerations:
   - No use of eval() or exec()
   - No shell injection vulnerabilities
   - Validate all external inputs
   - No SQL string concatenation (if using database)

5. Return format:
   - The execute() method must return a dict with 'status' and 'result' keys
   - status: 'success' or 'error'
   - result: the output data or error message

Generate ONLY the Python code, no explanations. The code should be ready to save to a .py file.""")


class GeneratorError(Exception):
    """Raised when agent code generation fails."""

    pass


async def generate_agent_code(
    description: str,
    api_key: Optional[str] = None,
    max_tokens: int = 4096,
) -> Dict[str, str]:
    """
    Generate Python agent code from natural language description.

    Uses Claude Sonnet 4.5 to generate production-ready Python code based on
    the provided description. The generated code includes error handling,
    logging, type hints, and follows security best practices.

    Args:
        description: Natural language description of the agent's functionality
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        max_tokens: Maximum tokens in the response (default: 4096)

    Returns:
        Dict containing:
            - code: Generated Python code as string
            - model: Model used for generation
            - tokens_used: Approximate tokens used

    Raises:
        GeneratorError: If code generation fails
        ValueError: If description is empty or API key is missing

    Example:
        >>> result = await generate_agent_code(
        ...     "Monitor Tesla stock price and alert on 5% increase"
        ... )
        >>> print(result['code'])
        class Agent:
            async def execute(self) -> dict:
                ...
    """
    if not description or not description.strip():
        raise ValueError("Description cannot be empty")

    # Get API key from parameter or environment
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable"
        )

    # Generate the prompt
    prompt = AGENT_GENERATION_PROMPT.render(description=description.strip())

    logger.info("Generating agent code for: %s", description[:100])

    try:
        # Initialize Anthropic client
        client = Anthropic(api_key=api_key)

        # Call Claude Sonnet 4.5
        message = client.messages.create(
            model="claude-sonnet-4-20250514",  # Claude Sonnet 4.5
            max_tokens=max_tokens,
            temperature=0.3,  # Lower temperature for more deterministic code
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        # Extract the generated code
        if not message.content or len(message.content) == 0:
            raise GeneratorError("No content returned from Claude API")

        # The response is a list of content blocks, get the text
        code = message.content[0].text

        # Clean up code formatting (remove markdown code blocks if present)
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python") :].strip()
        if code.startswith("```"):
            code = code[len("```") :].strip()
        if code.endswith("```"):
            code = code[: -len("```")].strip()

        logger.info(
            "Successfully generated agent code (%d characters)", len(code)
        )

        return {
            "code": code,
            "model": message.model,
            "tokens_used": message.usage.input_tokens
            + message.usage.output_tokens,
        }

    except APIError as e:
        logger.error("Anthropic API error: %s", str(e))
        raise GeneratorError(f"Failed to generate code: {e}") from e
    except Exception as e:
        logger.error("Unexpected error during code generation: %s", str(e))
        raise GeneratorError(f"Code generation failed: {e}") from e


def estimate_cost(tokens_used: int) -> float:
    """
    Estimate the cost of code generation based on tokens used.

    Pricing (as of 2025):
    - Claude Sonnet 4.5: $3 per million input tokens, $15 per million output
    - Assuming 50/50 split for estimation

    Args:
        tokens_used: Total tokens (input + output)

    Returns:
        Estimated cost in USD

    Example:
        >>> estimate_cost(1000)
        0.009
    """
    # Rough estimate: assume 50% input, 50% output
    input_tokens = tokens_used // 2
    output_tokens = tokens_used // 2

    # Pricing per million tokens
    input_cost = (input_tokens / 1_000_000) * 3.0
    output_cost = (output_tokens / 1_000_000) * 15.0

    return input_cost + output_cost
