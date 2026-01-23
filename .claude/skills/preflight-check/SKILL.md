---
name: preflight-check
description: Run all validation checks (security, tests, lint, docs) before creating PR. Use before "create pr", "ready to merge", or "open pull request".
version: 2.0.0
allowed-tools:
  - Bash(python, pytest, ruff, git)
  - Read
plan_mode_required: false
trigger_keywords:
  - preflight
  - create pr
  - ready to merge
  - open pull request
---

# Preflight Check

**Purpose**: Ensure CI will pass before creating PR.

---

## Preflight Results (Auto-Executed)

```
!`python .claude/skills/preflight-check/scripts/run_checks.py 2>&1`
```

---

## Analysis

Based on the results above:

### If PREFLIGHT PASSED ✅

```markdown
All checks passed. Ready to create PR.

Next: Use `/pr-helper` or ask me to create the PR.
```

### If PREFLIGHT FAILED ❌

For each failed check:

| Check | Fix |
|-------|-----|
| 🔒 Security | Remove secret from code, add to .gitignore |
| 🧪 Tests | Fix failing test, run `pytest tests/ -v` |
| 🎨 Lint | Run `ruff check --fix src/ tests/` |
| 📚 Docs | Update `docs/changelog.md` under [Unreleased] |

After fixing: Run `/preflight-check` again.

---

## What It Checks

1. **🔒 Security** - Scans git diff for API keys, tokens, passwords
2. **🧪 Tests** - Runs `pytest tests/ -v`
3. **🎨 Lint** - Runs `ruff check src/ tests/`
4. **📚 Docs** - Verifies changelog updated if src/ changed

---

## Integration

```
Code complete → /preflight-check → If pass → /pr-helper → CI validates → Merge
```

**Why check twice?**
- **Local (preflight)**: Fast feedback (<30s)
- **GitHub (CI)**: Clean environment verification

---

## Related Skills

- **test-runner**: Tests only
- **security-checker**: Security only
- **pr-helper**: Creates PR after preflight passes
