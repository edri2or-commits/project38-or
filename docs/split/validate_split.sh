#!/bin/bash
# validate_split.sh - Validate domain split cleanliness
#
# Run this script to verify the BUSINESS/PERSONAL domain separation.
# All checks should pass before deployment.

set -e

echo "=== Domain Split Validation ==="
echo ""

FAIL=0
cd "$(dirname "$0")/../.."

# Check 1: No smart_email in BUSINESS
echo "Check 1: No smart_email in BUSINESS..."
if rg -l "smart_email" apps/business services --type py 2>/dev/null | grep -v "\.pyc" | head -1 | grep -q .; then
    echo "  ❌ FAIL: smart_email found in BUSINESS"
    rg -l "smart_email" apps/business services --type py 2>/dev/null || true
    FAIL=1
else
    echo "  ✅ PASS: No smart_email in BUSINESS"
fi

# Check 2: No workspace_mcp in BUSINESS
echo "Check 2: No workspace_mcp in BUSINESS..."
if rg -l "workspace_mcp" apps/business services --type py 2>/dev/null | grep -v "\.pyc" | head -1 | grep -q .; then
    echo "  ❌ FAIL: workspace_mcp found in BUSINESS"
    rg -l "workspace_mcp" apps/business services --type py 2>/dev/null || true
    FAIL=1
else
    echo "  ✅ PASS: No workspace_mcp in BUSINESS"
fi

# Check 3: No cross-domain imports (BUSINESS importing PERSONAL)
# Note: Use ^ to match only actual import statements, not comments
echo "Check 3: BUSINESS doesn't import PERSONAL..."
if rg "^from apps\.personal|^import apps\.personal" apps/business --type py 2>/dev/null | grep -q .; then
    echo "  ❌ FAIL: BUSINESS imports PERSONAL"
    rg "^from apps\.personal|^import apps\.personal" apps/business --type py 2>/dev/null || true
    FAIL=1
else
    echo "  ✅ PASS: BUSINESS doesn't import PERSONAL"
fi

# Check 4: No cross-domain imports (PERSONAL importing BUSINESS)
echo "Check 4: PERSONAL doesn't import BUSINESS..."
if rg "^from apps\.business|^import apps\.business" apps/personal --type py 2>/dev/null | grep -q .; then
    echo "  ❌ FAIL: PERSONAL imports BUSINESS"
    rg "^from apps\.business|^import apps\.business" apps/personal --type py 2>/dev/null || true
    FAIL=1
else
    echo "  ✅ PASS: PERSONAL doesn't import BUSINESS"
fi

# Check 5: shared_core is domain-agnostic
echo "Check 5: shared_core doesn't import domains..."
if rg "^from apps\.|^import apps\." libs/shared_core --type py 2>/dev/null | grep -q .; then
    echo "  ❌ FAIL: shared_core imports domain code"
    rg "^from apps\.|^import apps\." libs/shared_core --type py 2>/dev/null || true
    FAIL=1
else
    echo "  ✅ PASS: shared_core is domain-agnostic"
fi

# Check 6: Telegram bot Dockerfile clean
echo "Check 6: Telegram bot Dockerfile is clean..."
if grep -E "src/agents|smart_email" services/telegram-bot/Dockerfile 2>/dev/null | grep -v "^#" | grep -q .; then
    echo "  ❌ FAIL: Telegram bot Dockerfile includes PERSONAL code"
    grep -E "src/agents|smart_email" services/telegram-bot/Dockerfile 2>/dev/null || true
    FAIL=1
else
    echo "  ✅ PASS: Telegram bot Dockerfile is clean"
fi

# Check 7: No src. imports in apps/
echo "Check 7: No old src. imports in apps/..."
if rg "^from src\.|^import src\." apps --type py 2>/dev/null | grep -q .; then
    echo "  ❌ FAIL: Old src. imports found in apps/"
    rg "^from src\.|^import src\." apps --type py 2>/dev/null || true
    FAIL=1
else
    echo "  ✅ PASS: No old src. imports in apps/"
fi

# Check 8: Railway configs updated
echo "Check 8: Railway config uses new entrypoint..."
if grep -q "apps\.business\.main" railway.toml 2>/dev/null; then
    echo "  ✅ PASS: railway.toml uses apps.business.main"
else
    echo "  ❌ FAIL: railway.toml not updated"
    FAIL=1
fi

# Check 9: Procfile updated
echo "Check 9: Procfile uses new entrypoint..."
if grep -q "apps\.business\.main" Procfile 2>/dev/null; then
    echo "  ✅ PASS: Procfile uses apps.business.main"
else
    echo "  ❌ FAIL: Procfile not updated"
    FAIL=1
fi

echo ""
echo "=== Summary ==="
if [ $FAIL -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED - Domain split is clean"
    exit 0
else
    echo "❌ SOME CHECKS FAILED - Review and fix issues above"
    exit 1
fi
