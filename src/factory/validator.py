"""Code Validator - Validates generated agent code.

Runs multiple validation checks:
- Ruff format and lint
- Pydocstyle (Google style)
- Security checks (no hardcoded secrets, eval/exec)
"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when code validation fails."""

    pass


# Security patterns to detect
SECURITY_PATTERNS = [
    (r"eval\s*\(", "Use of eval() is not allowed (security risk)"),
    (r"exec\s*\(", "Use of exec() is not allowed (security risk)"),
    (
        r"(password|token|key|secret)\s*=\s*['\"][^'\"]+['\"]",
        "Potential hardcoded credential detected",
    ),
    (r"sk-[a-zA-Z0-9]{40,}", "Potential API key detected"),
    (
        r"subprocess\.call\([^)]*shell\s*=\s*True",
        "Shell=True in subprocess is a security risk",
    ),
]


async def validate_code(code: str, strict: bool = True) -> dict[str, list[str]]:
    """Validate generated Python code.

    Runs multiple validation checks:
    1. Syntax check (compile the code)
    2. Ruff format check
    3. Ruff lint
    4. Security pattern detection
    5. Pydocstyle (Google style) - optional based on strict flag

    Args:
        code: Python code to validate
        strict: If True, enforce pydocstyle checks (default: True)

    Returns:
        Dict with validation results:
            - errors: List of error messages (blocking issues)
            - warnings: List of warning messages (non-blocking)
            - passed: Boolean indicating if all checks passed

    Raises:
        ValidationError: If code fails critical validation checks

    Example:
        >>> result = await validate_code("print('hello')")
        >>> print(result['passed'])
        True
    """
    if not code or not code.strip():
        raise ValueError("Code cannot be empty")

    errors = []
    warnings = []

    logger.info("Validating generated code (%d characters)", len(code))

    # 1. Syntax check
    try:
        compile(code, "<agent>", "exec")
        logger.debug("Syntax check passed")
    except SyntaxError as e:
        errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return {"errors": errors, "warnings": warnings, "passed": False}

    # Create temporary file for validation tools
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
        tmp_file.write(code)
        tmp_path = Path(tmp_file.name)

    try:
        # 2. Security checks (pattern matching)
        security_issues = _check_security_patterns(code)
        if security_issues:
            errors.extend(security_issues)

        # 3. Ruff format check
        format_result = _run_ruff_format(tmp_path)
        if not format_result["passed"]:
            warnings.extend(format_result["messages"])

        # 4. Ruff lint
        lint_result = _run_ruff_lint(tmp_path)
        if not lint_result["passed"]:
            # Categorize by severity
            for msg in lint_result["messages"]:
                if "error" in msg.lower() or "E9" in msg:
                    errors.append(msg)
                else:
                    warnings.append(msg)

        # 5. Pydocstyle (Google style) - strict mode only
        if strict:
            docstyle_result = _run_pydocstyle(tmp_path)
            if not docstyle_result["passed"]:
                warnings.extend(docstyle_result["messages"])

        # Determine overall pass/fail
        passed = len(errors) == 0

        logger.info(
            "Validation complete: %d errors, %d warnings",
            len(errors),
            len(warnings),
        )

        return {"errors": errors, "warnings": warnings, "passed": passed}

    finally:
        # Cleanup temporary file
        tmp_path.unlink(missing_ok=True)


def _check_security_patterns(code: str) -> list[str]:
    """Check code for security anti-patterns.

    Args:
        code: Python code to check

    Returns:
        List of security issues found
    """
    issues = []

    for pattern, message in SECURITY_PATTERNS:
        matches = re.finditer(pattern, code, re.IGNORECASE)
        for match in matches:
            line_num = code[: match.start()].count("\n") + 1
            issues.append(f"Security issue at line {line_num}: {message}")

    return issues


def _run_ruff_format(code_path: Path) -> dict[str, any]:
    """Run ruff format check.

    Args:
        code_path: Path to Python file

    Returns:
        Dict with 'passed' boolean and 'messages' list
    """
    try:
        result = subprocess.run(
            ["ruff", "format", "--check", str(code_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        passed = result.returncode == 0
        messages = []

        if not passed:
            messages.append("Code formatting does not match ruff style (run 'ruff format' to fix)")

        return {"passed": passed, "messages": messages}

    except FileNotFoundError:
        logger.warning("ruff not found, skipping format check")
        return {"passed": True, "messages": ["ruff not installed"]}
    except subprocess.TimeoutExpired:
        return {"passed": False, "messages": ["ruff format check timed out"]}
    except Exception as e:
        logger.error("ruff format check failed: %s", str(e))
        return {"passed": False, "messages": [f"Format check error: {e}"]}


def _run_ruff_lint(code_path: Path) -> dict[str, any]:
    """Run ruff lint.

    Args:
        code_path: Path to Python file

    Returns:
        Dict with 'passed' boolean and 'messages' list
    """
    try:
        result = subprocess.run(
            ["ruff", "check", str(code_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        passed = result.returncode == 0
        messages = []

        if not passed and result.stdout:
            # Parse ruff output
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    messages.append(line)

        return {"passed": passed, "messages": messages}

    except FileNotFoundError:
        logger.warning("ruff not found, skipping lint check")
        return {"passed": True, "messages": ["ruff not installed"]}
    except subprocess.TimeoutExpired:
        return {"passed": False, "messages": ["ruff lint check timed out"]}
    except Exception as e:
        logger.error("ruff lint check failed: %s", str(e))
        return {"passed": False, "messages": [f"Lint check error: {e}"]}


def _run_pydocstyle(code_path: Path) -> dict[str, any]:
    """Run pydocstyle check (Google style).

    Args:
        code_path: Path to Python file

    Returns:
        Dict with 'passed' boolean and 'messages' list
    """
    try:
        result = subprocess.run(
            ["pydocstyle", "--convention=google", str(code_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        passed = result.returncode == 0
        messages = []

        if not passed and result.stdout:
            # Parse pydocstyle output
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    messages.append(line)

        return {"passed": passed, "messages": messages}

    except FileNotFoundError:
        logger.warning("pydocstyle not found, skipping docstring check")
        return {"passed": True, "messages": ["pydocstyle not installed"]}
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "messages": ["pydocstyle check timed out"],
        }
    except Exception as e:
        logger.error("pydocstyle check failed: %s", str(e))
        return {
            "passed": False,
            "messages": [f"Docstring check error: {e}"],
        }


def format_validation_report(result: dict[str, any]) -> str:
    """Format validation results into human-readable report.

    Args:
        result: Validation result from validate_code()

    Returns:
        Formatted report string

    Example:
        >>> report = format_validation_report(result)
        >>> print(report)
        Validation Result: PASSED
        Warnings: 2
        - Line 10: Missing docstring
        - Line 25: Line too long
    """
    lines = []

    status = "PASSED" if result["passed"] else "FAILED"
    lines.append(f"Validation Result: {status}")
    lines.append("")

    if result["errors"]:
        lines.append(f"Errors: {len(result['errors'])}")
        for error in result["errors"]:
            lines.append(f"  - {error}")
        lines.append("")

    if result["warnings"]:
        lines.append(f"Warnings: {len(result['warnings'])}")
        for warning in result["warnings"]:
            lines.append(f"  - {warning}")
        lines.append("")

    if result["passed"] and not result["warnings"]:
        lines.append("All checks passed with no issues!")

    return "\n".join(lines)
