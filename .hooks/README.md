# Git Hooks for project38-or

This directory contains git hook templates for the project.

## Available Hooks

### pre-commit

Runs before each commit to verify:
- ✅ All docstrings are present and valid (Google style)
- ✅ No secrets are exposed in staged changes
- ⚠️ Reminds to update changelog if `src/` files changed

**Exit codes:**
- `0` - All checks passed, commit proceeds
- `1` - Checks failed, commit blocked

## Installation

### Quick Install

```bash
# From project root
bash .hooks/install.sh
```

### Manual Install

```bash
# Copy pre-commit hook
cp .hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Usage

Once installed, the hook runs automatically on every commit:

```bash
git add src/my_module.py
git commit -m "feat: add new module"

# Output:
# 🔍 Running pre-commit checks...
#
# Running doc-updater --verify...
# === Verification Report ===
#
# 1. Docstring Check:
#    ✅ All docstrings valid in src
#
# 2. Secret Detection:
#    ✅ No secrets detected in staged changes
#
# ✅ All checks passed
# ✅ Pre-commit checks complete
```

## Bypass Hook (Not Recommended)

In rare cases where you need to bypass the hook:

```bash
git commit --no-verify -m "commit message"
```

**⚠️ Warning:** Only use `--no-verify` when absolutely necessary. You may be introducing:
- Undocumented code
- Security vulnerabilities
- Documentation drift

## Troubleshooting

### Hook not running

1. Check if installed:
   ```bash
   ls -la .git/hooks/pre-commit
   ```

2. Verify executable:
   ```bash
   chmod +x .git/hooks/pre-commit
   ```

3. Test manually:
   ```bash
   .git/hooks/pre-commit
   ```

### "python3 not found"

Install Python 3.11+:
```bash
# macOS
brew install python@3.11

# Ubuntu/Debian
apt install python3.11

# Windows
# Download from python.org
```

### "pydocstyle not installed"

```bash
pip install pydocstyle
```

### Hook failing on valid code

1. Check what's failing:
   ```bash
   python3 src/doc_updater.py --verify
   ```

2. Review the output and fix issues

3. If it's a false positive, report at:
   https://github.com/edri2or-commits/project38-or/issues

## Uninstall

```bash
rm .git/hooks/pre-commit
```

## Development

To modify the hook:

1. Edit `.hooks/pre-commit`
2. Test changes:
   ```bash
   bash .hooks/pre-commit
   ```
3. Reinstall:
   ```bash
   bash .hooks/install.sh
   ```
4. Commit changes to template
5. Team members run `bash .hooks/install.sh` to update

## Integration with CI/CD

The pre-commit hook uses the same checks as CI:
- Local: `.git/hooks/pre-commit` (optional, fast feedback)
- CI: `.github/workflows/doc-updater.yml` (mandatory, runs on PR)

This ensures:
- Early error detection (local)
- Consistent enforcement (CI)
- No surprises in code review
