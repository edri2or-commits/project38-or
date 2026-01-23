#!/usr/bin/env python3
"""Preflight check script - runs all validations before PR creation."""

import subprocess
import sys
import re


def run_security_check():
    """Check for secrets in git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            timeout=30
        )
        diff = result.stdout.lower()

        patterns = [
            (r"api[_-]?key\s*=", "API key assignment"),
            (r"secret\s*=", "Secret assignment"),
            (r"password\s*=", "Password assignment"),
            (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
            (r"sk-ant-api", "Anthropic API key"),
            (r"sk-[a-zA-Z0-9]{48}", "OpenAI API key"),
            (r"bearer\s+[a-zA-Z0-9]{20,}", "Bearer token"),
        ]

        for pattern, name in patterns:
            if re.search(pattern, diff, re.IGNORECASE):
                return False, f"Secret pattern detected: {name}"

        return True, "No secrets detected"
    except Exception as e:
        return False, f"Error: {e}"


def run_tests():
    """Run pytest and capture results."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--tb=line", "-q"],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse output for summary
        output = result.stdout + result.stderr

        if result.returncode == 0:
            # Extract passed count
            match = re.search(r"(\d+) passed", output)
            count = match.group(1) if match else "all"
            return True, f"{count} tests passed"
        else:
            # Extract failed tests
            failed = re.findall(r"FAILED (.+?)(?:\s|$)", output)
            return False, f"{len(failed)} failed: " + ", ".join(failed[:3])
    except subprocess.TimeoutExpired:
        return False, "Tests timed out (>120s)"
    except Exception as e:
        return False, f"Error: {e}"


def run_lint():
    """Run ruff check."""
    try:
        result = subprocess.run(
            ["ruff", "check", "src/", "tests/", "--output-format=concise"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return True, "All files clean"
        else:
            # Count errors
            lines = result.stdout.strip().split("\n")
            return False, f"{len(lines)} lint errors"
    except FileNotFoundError:
        return True, "ruff not installed (skipped)"
    except Exception as e:
        return False, f"Error: {e}"


def run_docs_check():
    """Check documentation compliance."""
    try:
        # Check if src/ changed
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            timeout=30
        )

        changed_files = result.stdout

        if "src/" in changed_files:
            # Check if changelog updated
            changelog_result = subprocess.run(
                ["git", "diff", "origin/main...HEAD", "docs/changelog.md"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if not changelog_result.stdout.strip():
                return False, "src/ changed but changelog.md not updated"

        return True, "Documentation OK"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Run all preflight checks."""
    checks = [
        ("🔒 Security", run_security_check),
        ("🧪 Tests", run_tests),
        ("🎨 Lint", run_lint),
        ("📚 Docs", run_docs_check),
    ]

    all_passed = True

    for name, check_fn in checks:
        passed, message = check_fn()
        status = "✅" if passed else "❌"
        print(f"{name}: {status} {message}")

        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("✅ PREFLIGHT PASSED - Ready for PR")
        return 0
    else:
        print("❌ PREFLIGHT FAILED - Fix issues above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
