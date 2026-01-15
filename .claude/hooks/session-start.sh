#!/bin/bash
# SessionStart Hook - Loads MCP Gateway token and sets up autonomy
# This hook runs at the start of every Claude Code session

set -e

# Output JSON for additionalContext
output_context() {
    local context="$1"
    echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$context\"}}"
}

# Check if we're in a remote/web environment
IS_REMOTE="${CLAUDE_CODE_REMOTE:-false}"

echo "🚀 Project38 SessionStart Hook" >&2
echo "   Environment: $([ "$IS_REMOTE" = "true" ] && echo "Web/Remote" || echo "Local")" >&2

# Try to load MCP Gateway token from GCP Secret Manager
load_mcp_token() {
    # Check if gcloud is available
    if ! command -v gcloud &> /dev/null; then
        echo "   ⚠️ gcloud not available, skipping token load" >&2
        return 1
    fi

    # Try to get the token
    local token
    token=$(gcloud secrets versions access latest --secret="MCP-GATEWAY-TOKEN" --project="project38-483612" 2>/dev/null) || {
        echo "   ⚠️ Could not fetch MCP token from GCP" >&2
        return 1
    }

    if [ -n "$token" ]; then
        echo "   ✅ MCP Gateway token loaded from GCP" >&2

        # If CLAUDE_ENV_FILE is available, persist the token
        if [ -n "$CLAUDE_ENV_FILE" ]; then
            echo "export MCP_GATEWAY_TOKEN='$token'" >> "$CLAUDE_ENV_FILE"
            echo "   ✅ Token persisted to session environment" >&2
        fi

        return 0
    fi

    return 1
}

# Check if token is already in environment
if [ -n "$MCP_GATEWAY_TOKEN" ]; then
    echo "   ✅ MCP Gateway token already in environment" >&2
else
    load_mcp_token || true
fi

# Set up additional environment variables
if [ -n "$CLAUDE_ENV_FILE" ]; then
    # Set project-specific environment
    echo "export PROJECT38_AUTONOMY_ENABLED=true" >> "$CLAUDE_ENV_FILE"
    echo "export RAILWAY_PROJECT_ID=95ec21cc-9ada-41c5-8485-12f9a00e0116" >> "$CLAUDE_ENV_FILE"
    echo "export PRODUCTION_URL=https://or-infra.com" >> "$CLAUDE_ENV_FILE"
fi

# Output context for Claude
CONTEXT="Project38 Autonomy Status:\\n"
CONTEXT+="- MCP Gateway: https://or-infra.com/mcp\\n"
CONTEXT+="- Railway Project: delightful-cat\\n"
CONTEXT+="- Available MCP Tools: railway_deploy, railway_rollback, n8n_trigger, health_check\\n"

if [ -n "$MCP_GATEWAY_TOKEN" ] || [ -n "$CLAUDE_ENV_FILE" ]; then
    CONTEXT+="- Token Status: ✅ Available\\n"
else
    CONTEXT+="- Token Status: ⚠️ Not loaded (run setup-mcp-gateway.yml workflow)\\n"
fi

output_context "$CONTEXT"

echo "   ✅ SessionStart hook completed" >&2
exit 0
