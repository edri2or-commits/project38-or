# Preflight Check Skill

**Version:** 1.0.0
**Purpose:** Run all validation checks before creating PR to ensure auto-merge will succeed

---

## When to Use

**Triggers:**
- User is about to create a PR
- Keywords: "create pr", "ready to merge", "open pull request", "preflight"
- After completing a feature/fix

**Integration:**
```
Code complete
    ↓
preflight-check: Run all validations ✅
    ↓
If all pass → Create PR (auto-merge enabled)
If any fail → Report issues + fix guidance
```

---

## What It Does

Runs 4 critical checks in parallel (same as auto-merge.yml):

1. **🔒 Security Check**
   - Scans git diff for secrets patterns
   - Blocks: API keys, tokens, passwords, hardcoded credentials
   - Zero tolerance: Any match = fail

2. **🧪 Tests**
   - Runs full test suite: `pytest tests/ -v`
   - Reports: Pass/fail count, failed test names
   - Requirement: 100% pass rate

3. **🎨 Lint**
   - Runs: `ruff check src/ tests/`
   - Reports: Error count, file locations
   - Requirement: Zero errors

4. **📚 Documentation**
   - If `src/` changed → verify `changelog.md` updated
   - Runs: `pydocstyle src/` (Google style)
   - Requirement: All docstrings compliant

---

## Expected Behavior

### Success Path
```bash
🔒 Security: ✅ No secrets detected
🧪 Tests: ✅ 123/123 passed
🎨 Lint: ✅ All files clean
📚 Docs: ✅ Changelog updated, docstrings valid

✅ PREFLIGHT PASSED
Ready to create PR with auto-merge
```

**Action:** Create PR immediately - auto-merge will succeed

---

### Failure Path
```bash
🔒 Security: ✅ No secrets detected
🧪 Tests: ❌ 2 failed (test_api.py::test_auth, test_harness.py::test_lock)
🎨 Lint: ✅ All files clean
📚 Docs: ❌ changelog.md not updated

❌ PREFLIGHT FAILED (2 issues)

Issues:
1. Tests failed:
   - test_api.py::test_auth: AssertionError (line 45)
   - test_harness.py::test_lock: Timeout (line 120)

2. Documentation:
   - src/ modified but changelog.md not updated
   - Add entry under [Unreleased] section

Fix these issues before creating PR.
```

**Action:** Fix issues → Run preflight again → Create PR

---

## Implementation

```python
import subprocess
import sys

def run_security_check():
    """Check for secrets in git diff."""
    result = subprocess.run(
        ["git", "diff", "origin/main...HEAD"],
        capture_output=True,
        text=True
    )

    patterns = [
        "api[_-]?key", "secret", "password",
        "token.*=", "bearer ", "ghp_", "sk-ant-api"
    ]

    for pattern in patterns:
        if pattern.lower() in result.stdout.lower():
            return False, f"Secret pattern detected: {pattern}"

    return True, "No secrets detected"

def run_tests():
    """Run pytest and capture results."""
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True
    )

    # Parse output
    if result.returncode == 0:
        return True, "All tests passed"
    else:
        # Extract failed tests
        failed = [line for line in result.stdout.split('\n') if 'FAILED' in line]
        return False, f"{len(failed)} tests failed:\n" + "\n".join(failed[:5])

def run_lint():
    """Run ruff check."""
    result = subprocess.run(
        ["ruff", "check", "src/", "tests/"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return True, "All files clean"
    else:
        return False, result.stdout

def run_docs_check():
    """Check documentation compliance."""
    # Check if src/ changed
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True,
        text=True
    )

    if "src/" in result.stdout:
        # Check if changelog updated
        changelog_diff = subprocess.run(
            ["git", "diff", "origin/main...HEAD", "docs/changelog.md"],
            capture_output=True,
            text=True
        )

        if not changelog_diff.stdout:
            return False, "src/ changed but changelog.md not updated"

    # Run pydocstyle
    result = subprocess.run(
        ["pydocstyle", "src/"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return True, "Documentation compliant"
    else:
        return False, f"Docstring issues:\n{result.stdout[:500]}"

def main():
    """Run all preflight checks."""
    print("🚀 Running Preflight Checks...\n")

    checks = [
        ("🔒 Security", run_security_check),
        ("🧪 Tests", run_tests),
        ("🎨 Lint", run_lint),
        ("📚 Documentation", run_docs_check),
    ]

    results = []
    all_passed = True

    for name, check_fn in checks:
        passed, message = check_fn()
        results.append((name, passed, message))

        status = "✅" if passed else "❌"
        print(f"{status} {name}: {message.split(chr(10))[0]}")

        if not passed:
            all_passed = False
            print(f"   Details: {message}\n")

    print("\n" + "="*50)

    if all_passed:
        print("✅ PREFLIGHT PASSED")
        print("\nReady to create PR with auto-merge enabled.")
        return 0
    else:
        print("❌ PREFLIGHT FAILED")
        print("\nFix the issues above before creating PR.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

---

## Usage Examples

### Example 1: Ready to Merge
```bash
User: "I'm ready to create a PR"

Agent: "Let me run preflight checks first to ensure auto-merge will succeed."
[Runs preflight-check skill]

Output:
🔒 Security: ✅ No secrets detected
🧪 Tests: ✅ 123/123 passed
🎨 Lint: ✅ All files clean
📚 Docs: ✅ Changelog updated

✅ PREFLIGHT PASSED

Agent: "All checks passed! Creating PR with auto-merge enabled..."
[Creates PR using pr-helper skill]

Result: PR created, auto-merge workflow approves and merges automatically
```

---

### Example 2: Needs Fixes
```bash
User: "Create PR for my changes"

Agent: "Running preflight checks first..."
[Runs preflight-check skill]

Output:
🔒 Security: ✅ No secrets detected
🧪 Tests: ❌ 2 failed
🎨 Lint: ❌ 3 errors in src/api/main.py
📚 Docs: ✅ Changelog updated

❌ PREFLIGHT FAILED

Agent: "Preflight checks failed. Let me fix the issues:

1. Lint errors in src/api/main.py (unused imports)
2. Test failures in test_api.py

Fixing lint errors..."
[Fixes issues]

Agent: "Fixes applied. Running preflight again..."
[Runs preflight again]

Output: ✅ PREFLIGHT PASSED

Agent: "All checks passed! Creating PR now..."
```

---

## Integration with Auto-Merge

**Workflow:**
```
Developer completes feature
    ↓
preflight-check skill runs locally
    ↓
If pass → Create PR
    ↓
auto-merge.yml workflow runs on GitHub
    ↓
Same 4 checks (redundant verification)
    ↓
If all pass → Auto-merge enabled
    ↓
PR merged + branch deleted
```

**Why run checks twice?**
- **Local (preflight):** Fast feedback, no CI wait time
- **GitHub (auto-merge):** Verification, security gate

---

## Error Handling

| Error | Cause | Action |
|-------|-------|--------|
| Secret detected | API key in diff | Remove secret, add to .gitignore |
| Tests failed | Code bug | Fix bug, run tests locally |
| Lint errors | Code quality | Run `ruff check --fix` |
| Docs missing | Forgot changelog | Update docs/changelog.md |
| Git error | Not on branch | Create feature branch |

---

## Success Metrics

- ✅ Zero PR rejections due to validation failures
- ✅ < 1 minute from "create PR" to merge
- ✅ 100% of preflight passes result in auto-merge success
- ✅ Clear, actionable error messages

---

## Configuration

```python
# .claude/skills/preflight-check/config.py

SECURITY_PATTERNS = [
    r"api[_-]?key",
    r"secret",
    r"password\s*=",
    r"token\s*=",
    r"bearer\s",
    r"ghp_",
    r"sk-ant-api",
]

REQUIRED_CHECKS = [
    "security",
    "tests",
    "lint",
    "docs",
]

# Fail fast on first error (False) or run all checks (True)
RUN_ALL_CHECKS = True
```

---

## Safety

- **Read-only operations:** Only runs checks, doesn't modify code
- **No secrets:** Doesn't access or log secret values
- **Fast:** Runs in < 30 seconds for typical changes
- **Parallel:** Runs checks concurrently for speed
- **Idempotent:** Safe to run multiple times

---

## Related Skills

- **test-runner** - Runs tests (subset of preflight)
- **security-checker** - Checks secrets (subset of preflight)
- **doc-updater** - Updates docs (fixes preflight doc failures)
- **pr-helper** - Creates PR (runs after preflight passes)

---

## Notes

- This skill is the **final gate** before PR creation
- Ensures CI auto-merge will succeed on first try
- Reduces CI wait time (no failed builds)
- Provides immediate feedback vs. waiting for GitHub Actions
