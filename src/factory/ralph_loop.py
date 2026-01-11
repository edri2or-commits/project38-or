"""
Ralph Wiggum Loop - Recursive Test → Fix → Test cycle.

Named after Ralph Wiggum's "I'm helping!" - the loop keeps trying to fix
issues until the code passes validation or max iterations reached.

Implements the self-healing pattern:
1. Run validation on code
2. If fails, use Claude to analyze errors and fix
3. Repeat until success or max iterations
"""

import logging
from typing import Dict, List, Optional
from jinja2 import Template
from anthropic import Anthropic, APIError

from src.factory.validator import validate_code

logger = logging.getLogger(__name__)


# Prompt template for fixing code
CODE_FIX_PROMPT = Template("""You are an expert Python debugger helping to fix code issues.

The following Python code has validation errors:

```python
{{ code }}
```

Validation errors:
{% for error in errors %}
- {{ error }}
{% endfor %}

{% if warnings %}
Warnings:
{% for warning in warnings %}
- {{ warning }}
{% endfor %}
{% endif %}

Previous fix attempts: {{ attempt_number }}

{% if previous_fix %}
Previous fix that didn't work:
{{ previous_fix }}
{% endif %}

Your task:
1. Analyze each error carefully
2. Fix ALL errors in the code
3. Maintain the original functionality
4. Keep all docstrings and type hints
5. Return ONLY the fixed Python code, no explanations

Generate the complete fixed code:""")


class RalphLoopError(Exception):
    """Raised when Ralph Wiggum Loop fails after max iterations."""

    pass


async def ralph_wiggum_loop(
    code: str,
    api_key: Optional[str] = None,
    max_iterations: int = 5,
    strict: bool = True,
) -> Dict[str, any]:
    """
    Run recursive Test → Fix → Test cycle until code passes validation.

    The "Ralph Wiggum Loop" (named after "I'm helping!") attempts to
    automatically fix validation errors by:
    1. Running validation checks
    2. If errors found, using Claude to fix them
    3. Repeating until code passes or max iterations reached

    Args:
        code: Python code to validate and fix
        api_key: Anthropic API key (optional, uses env var if not provided)
        max_iterations: Maximum fix attempts (default: 5)
        strict: If True, enforce strict validation including pydocstyle

    Returns:
        Dict containing:
            - code: Final (fixed) code
            - passed: Boolean indicating if validation passed
            - iterations: Number of fix iterations performed
            - errors: List of remaining errors (if any)
            - warnings: List of remaining warnings
            - history: List of attempts with their results

    Raises:
        RalphLoopError: If max iterations reached without success
        ValueError: If code is empty

    Example:
        >>> result = await ralph_wiggum_loop(broken_code)
        >>> if result['passed']:
        ...     print(f"Fixed in {result['iterations']} iterations")
        ... else:
        ...     print(f"Failed: {result['errors']}")
    """
    if not code or not code.strip():
        raise ValueError("Code cannot be empty")

    logger.info(
        "Starting Ralph Wiggum Loop (max_iterations=%d)", max_iterations
    )

    history: List[Dict] = []
    current_code = code
    previous_fix = None

    for iteration in range(max_iterations):
        logger.info("Iteration %d: Validating code", iteration + 1)

        # Validate current code
        validation = await validate_code(current_code, strict=strict)

        # Record this attempt in history
        history.append(
            {
                "iteration": iteration + 1,
                "passed": validation["passed"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            }
        )

        # Check if validation passed
        if validation["passed"]:
            logger.info(
                "Ralph Wiggum Loop succeeded after %d iterations",
                iteration + 1,
            )
            return {
                "code": current_code,
                "passed": True,
                "iterations": iteration + 1,
                "errors": [],
                "warnings": validation["warnings"],
                "history": history,
            }

        # If validation failed, attempt to fix
        logger.warning(
            "Validation failed with %d errors, attempting fix",
            len(validation["errors"]),
        )

        try:
            fixed_code = await _fix_code_with_claude(
                code=current_code,
                errors=validation["errors"],
                warnings=validation["warnings"],
                attempt_number=iteration + 1,
                previous_fix=previous_fix,
                api_key=api_key,
            )

            # Store for next iteration
            previous_fix = fixed_code
            current_code = fixed_code

        except Exception as e:
            logger.error("Failed to fix code in iteration %d: %s", iteration + 1, str(e))
            # Continue to next iteration with same code
            # (maybe a transient error)
            continue

    # Max iterations reached without success
    logger.error(
        "Ralph Wiggum Loop failed after %d iterations", max_iterations
    )

    # Get final validation state
    final_validation = await validate_code(current_code, strict=strict)

    raise RalphLoopError(
        f"Failed to fix code after {max_iterations} iterations. "
        f"Remaining errors: {len(final_validation['errors'])}"
    )


async def _fix_code_with_claude(
    code: str,
    errors: List[str],
    warnings: List[str],
    attempt_number: int,
    previous_fix: Optional[str],
    api_key: Optional[str],
) -> str:
    """
    Use Claude to fix code based on validation errors.

    Args:
        code: Code to fix
        errors: List of error messages
        warnings: List of warning messages
        attempt_number: Current attempt number
        previous_fix: Previous fix attempt (if any)
        api_key: Anthropic API key

    Returns:
        Fixed code

    Raises:
        APIError: If Claude API call fails
    """
    import os

    # Get API key
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Anthropic API key not found")

    # Generate fix prompt
    prompt = CODE_FIX_PROMPT.render(
        code=code,
        errors=errors,
        warnings=warnings,
        attempt_number=attempt_number,
        previous_fix=previous_fix if attempt_number > 1 else None,
    )

    logger.debug("Requesting code fix from Claude")

    try:
        client = Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",  # Claude Sonnet 4.5
            max_tokens=4096,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract fixed code
        if not message.content or len(message.content) == 0:
            raise APIError("No content returned from Claude API")

        fixed_code = message.content[0].text.strip()

        # Clean up markdown if present
        if fixed_code.startswith("```python"):
            fixed_code = fixed_code[len("```python") :].strip()
        if fixed_code.startswith("```"):
            fixed_code = fixed_code[len("```") :].strip()
        if fixed_code.endswith("```"):
            fixed_code = fixed_code[: -len("```")].strip()

        logger.info("Received fixed code (%d characters)", len(fixed_code))

        return fixed_code

    except APIError as e:
        logger.error("Claude API error during fix: %s", str(e))
        raise
    except Exception as e:
        logger.error("Unexpected error during code fix: %s", str(e))
        raise


def get_loop_summary(result: Dict[str, any]) -> str:
    """
    Generate human-readable summary of Ralph Loop execution.

    Args:
        result: Result dict from ralph_wiggum_loop()

    Returns:
        Formatted summary string

    Example:
        >>> summary = get_loop_summary(result)
        >>> print(summary)
        Ralph Wiggum Loop Summary
        -------------------------
        Status: SUCCESS
        Iterations: 3
        Final Warnings: 2
        ...
    """
    lines = []
    lines.append("Ralph Wiggum Loop Summary")
    lines.append("-" * 30)
    lines.append(f"Status: {'SUCCESS' if result['passed'] else 'FAILED'}")
    lines.append(f"Iterations: {result['iterations']}")
    lines.append(f"Final Errors: {len(result.get('errors', []))}")
    lines.append(f"Final Warnings: {len(result.get('warnings', []))}")
    lines.append("")

    if result.get("history"):
        lines.append("Iteration History:")
        for attempt in result["history"]:
            status = "✓" if attempt["passed"] else "✗"
            lines.append(
                f"  {status} Iteration {attempt['iteration']}: "
                f"{len(attempt['errors'])} errors, "
                f"{len(attempt['warnings'])} warnings"
            )
        lines.append("")

    if result.get("errors"):
        lines.append("Remaining Errors:")
        for error in result["errors"]:
            lines.append(f"  - {error}")

    return "\n".join(lines)
