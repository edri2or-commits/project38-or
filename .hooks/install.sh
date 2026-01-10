#!/bin/bash
# Install git hooks for project38-or

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

echo "Installing git hooks..."
echo ""
echo "Source: $SCRIPT_DIR"
echo "Target: $GIT_HOOKS_DIR"
echo ""

# Install pre-commit hook
if [ -f "$SCRIPT_DIR/pre-commit" ]; then
    cp "$SCRIPT_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
    chmod +x "$GIT_HOOKS_DIR/pre-commit"
    echo "✅ Installed: pre-commit"
else
    echo "❌ Source file not found: $SCRIPT_DIR/pre-commit"
    exit 1
fi

echo ""
echo "✅ Git hooks installed successfully!"
echo ""
echo "Hooks installed:"
echo "  - pre-commit: Checks docstrings, secrets, and changelog updates"
echo ""
echo "To test:"
echo "  git commit -m 'test commit' --allow-empty"
echo ""
echo "To bypass (not recommended):"
echo "  git commit --no-verify"
echo ""
