# COUPLING_SCAN.md - Domain Coupling Evidence

> **Generated**: 2026-01-26
> **Purpose**: Baseline verification artifact for domain split (Business/Personal)

## Overview

This document contains actual ripgrep scan outputs proving current coupling and defining AFTER state requirements.

---

## BEFORE STATE (Current Coupling)

### Scan 1: smart_email in BUSINESS paths

**Command**:
```bash
rg -l "smart_email|smart-email" src/api services --type py --type js
```

**Result**:
```
services/telegram-bot/handlers.py
```

**Evidence** (`services/telegram-bot/handlers.py`):
```python
# Line 287
from src.agents.smart_email.graph import run_smart_email_agent

# Line 301
from src.agents.smart_email.conversation import ConversationHandler

# Line 314
from src.agents.smart_email.actions import create_approval_manager

# Line 341, 396, 563
from src.agents.smart_email.graph import run_smart_email_agent

# Line 610
from src.agents.smart_email.actions import ActionType
```

**Severity**: CRITICAL - BUSINESS service imports PERSONAL code

---

### Scan 2: workspace_mcp in BUSINESS paths

**Command**:
```bash
rg -l "workspace_mcp|workspace-mcp" src/api src/mcp_gateway services --type py --type js
```

**Result**:
```
src/api/main.py
```

**Evidence** (`src/api/main.py:184-198`):
```python
# Mount Google Workspace MCP Bridge for Gmail, Calendar, Drive, Sheets, Docs
WORKSPACE_MCP_ENABLED = os.getenv("WORKSPACE_MCP_ENABLED", "false").lower() == "true"
if WORKSPACE_MCP_ENABLED:
    try:
        from src.workspace_mcp_bridge.server import create_app as create_workspace_app
        workspace_app = create_workspace_app()
        if workspace_app:
            app.mount("/workspace", workspace_app)
            logger.info("Google Workspace MCP Bridge mounted at /workspace")
```

**Severity**: HIGH - BUSINESS API conditionally mounts PERSONAL workspace bridge

---

### Scan 3: gmail/calendar in BUSINESS paths

**Command**:
```bash
rg -l "gmail|calendar" src/api src/mcp_gateway services --type py --type js | grep -v workspace_mcp
```

**Result**:
```
src/mcp_gateway/server.py
src/mcp_gateway/gcs_relay.py
src/mcp_gateway/tools/workspace.py
services/telegram-bot/handlers.py
services/mcp-gateway-cloudrun/main.py
src/api/routes/health.py
```

**Evidence**:

1. `src/mcp_gateway/tools/workspace.py` - ENTIRE FILE is PERSONAL tools in BUSINESS mcp_gateway
2. `src/mcp_gateway/server.py` - Imports workspace tools
3. `services/mcp-gateway-cloudrun/main.py` - Has Gmail/Calendar/Drive tools
4. `services/telegram-bot/handlers.py` - Uses smart_email which calls Gmail

**Severity**: CRITICAL - PERSONAL Gmail/Calendar tools mixed into BUSINESS infrastructure

---

### Scan 4: railway/n8n in PERSONAL paths

**Command**:
```bash
rg -l "railway|deploy|n8n" src/agents src/workspace_mcp_bridge --type py
```

**Result**:
```
src/agents/smart_email/persona.py
src/agents/smart_email/actions/executor.py
src/agents/smart_email/nodes/format_rtl.py
src/agents/smart_email/nodes/classify.py
src/agents/smart_email/nodes/research.py
src/agents/smart_email/nodes/draft.py
src/agents/smart_email/memory/store.py
```

**Analysis** (checking actual content):

| File | Line | Content | Type |
|------|------|---------|------|
| `persona.py:80` | `deploy, commit, PR` | String pattern | OK - email classification |
| `research.py:206` | `litellm-gateway-production-0339.up.railway.app` | Hardcoded URL | **COUPLING** |
| `classify.py:29` | `railway.app, railway` | Email domain filter | OK |
| `classify.py:209` | `litellm-gateway-production-0339.up.railway.app` | Hardcoded URL | **COUPLING** |
| `format_rtl.py:38` | `deploy, PR, CI/CD` | String pattern | OK |
| `draft.py:231` | `litellm-gateway-production-0339.up.railway.app` | Hardcoded URL | **COUPLING** |
| `memory/store.py:8` | `Railway PostgreSQL` | Comment | OK |
| `executor.py:488` | `n8n workflow` | TODO comment | OK |

**Severity**: MEDIUM - PERSONAL code has hardcoded BUSINESS LiteLLM gateway URLs

---

### Scan 5: Telegram Bot Dockerfile

**File**: `services/telegram-bot/Dockerfile:35-42`

```dockerfile
# Fetch src/agents for Smart Email Agent using sparse checkout
RUN git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/edri2or-commits/project38-or.git /tmp/repo && \
    cd /tmp/repo && \
    git sparse-checkout set src/agents && \
    mkdir -p /app/src && \
    cp -r /tmp/repo/src/agents /app/src/ && \
    rm -rf /tmp/repo
```

**Severity**: CRITICAL - BUSINESS container explicitly includes PERSONAL code at build time

---

## AFTER STATE (Required Cleanliness)

### Requirement 1: No smart_email in BUSINESS

**Command**:
```bash
rg -l "smart_email|smart-email" apps/business services --type py --type js
```

**Expected Result**:
```
(no matches)
```

---

### Requirement 2: No workspace in BUSINESS

**Command**:
```bash
rg -l "workspace_mcp|workspace-mcp|workspace_bridge" apps/business services --type py --type js
```

**Expected Result**:
```
(no matches)
```

---

### Requirement 3: No gmail/calendar in BUSINESS

**Command**:
```bash
rg -l "gmail|calendar" apps/business services --type py --type js
```

**Expected Result**:
```
(no matches)
```

(Exception: String patterns in email classification that don't import PERSONAL code)

---

### Requirement 4: No railway/n8n/mcp_gateway in PERSONAL

**Command**:
```bash
rg -l "from.*railway|from.*n8n|from.*mcp_gateway|import railway|import n8n" apps/personal --type py
```

**Expected Result**:
```
(no matches)
```

---

### Requirement 5: No hardcoded BUSINESS URLs in PERSONAL

**Command**:
```bash
rg "railway\.app|or-infra\.com" apps/personal --type py
```

**Expected Result**:
```
(no matches)
```

(PERSONAL should use environment variables or direct provider APIs, not hardcoded BUSINESS URLs)

---

### Requirement 6: Telegram Bot has no src/agents

**Check Dockerfile**:
```bash
grep -E "src/agents|smart_email" services/telegram-bot/Dockerfile
```

**Expected Result**:
```
(no matches)
```

---

### Requirement 7: apps/business imports

**Command**:
```bash
rg "from apps\.personal|import apps\.personal" apps/business --type py
```

**Expected Result**:
```
(no matches)
```

---

### Requirement 8: apps/personal imports

**Command**:
```bash
rg "from apps\.business|import apps\.business" apps/personal --type py
```

**Expected Result**:
```
(no matches)
```

---

### Requirement 9: libs/shared_core imports

**Command**:
```bash
rg "from apps\.|import apps\." libs/shared_core --type py
```

**Expected Result**:
```
(no matches)
```

(shared_core must not import any domain code)

---

## Summary Table

| Check | BEFORE (Coupling Found) | AFTER (Required) |
|-------|------------------------|------------------|
| smart_email in BUSINESS | `services/telegram-bot/handlers.py` | No matches |
| workspace in BUSINESS | `src/api/main.py` | No matches |
| gmail/calendar in BUSINESS | 6 files | No matches |
| railway/n8n in PERSONAL | 7 files (3 actual couplings) | No matches |
| Dockerfile clones PERSONAL | Yes (lines 35-42) | No |
| BUSINESS imports PERSONAL | Possible | No matches |
| PERSONAL imports BUSINESS | Possible | No matches |
| shared_core imports domains | N/A (doesn't exist yet) | No matches |

---

## Validation Script

After restructuring, run this validation:

```bash
#!/bin/bash
# validate_split.sh

echo "=== Domain Split Validation ==="

FAIL=0

# Check 1: No smart_email in BUSINESS
if rg -l "smart_email" apps/business services --type py 2>/dev/null | grep -q .; then
    echo "❌ FAIL: smart_email found in BUSINESS"
    FAIL=1
else
    echo "✅ PASS: No smart_email in BUSINESS"
fi

# Check 2: No workspace in BUSINESS
if rg -l "workspace_mcp" apps/business services --type py 2>/dev/null | grep -q .; then
    echo "❌ FAIL: workspace_mcp found in BUSINESS"
    FAIL=1
else
    echo "✅ PASS: No workspace_mcp in BUSINESS"
fi

# Check 3: No cross-domain imports
if rg "from apps\.personal|import apps\.personal" apps/business --type py 2>/dev/null | grep -q .; then
    echo "❌ FAIL: BUSINESS imports PERSONAL"
    FAIL=1
else
    echo "✅ PASS: BUSINESS doesn't import PERSONAL"
fi

if rg "from apps\.business|import apps\.business" apps/personal --type py 2>/dev/null | grep -q .; then
    echo "❌ FAIL: PERSONAL imports BUSINESS"
    FAIL=1
else
    echo "✅ PASS: PERSONAL doesn't import BUSINESS"
fi

# Check 4: shared_core is domain-agnostic
if rg "from apps\.|import apps\." libs/shared_core --type py 2>/dev/null | grep -q .; then
    echo "❌ FAIL: shared_core imports domain code"
    FAIL=1
else
    echo "✅ PASS: shared_core is domain-agnostic"
fi

# Check 5: Telegram bot Dockerfile clean
if grep -E "src/agents|smart_email" services/telegram-bot/Dockerfile 2>/dev/null | grep -q .; then
    echo "❌ FAIL: Telegram bot Dockerfile includes PERSONAL code"
    FAIL=1
else
    echo "✅ PASS: Telegram bot Dockerfile is clean"
fi

echo ""
if [ $FAIL -eq 0 ]; then
    echo "=== ALL CHECKS PASSED ==="
    exit 0
else
    echo "=== SOME CHECKS FAILED ==="
    exit 1
fi
```
