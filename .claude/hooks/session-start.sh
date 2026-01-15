#!/bin/bash
# SessionStart Hook - Loads MCP tokens and sets up autonomy
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

# Try to load token from GCP Secret Manager
load_gcp_secret() {
    local secret_name="$1"
    local env_var_name="$2"

    # Check if gcloud is available
    if ! command -v gcloud &> /dev/null; then
        return 1
    fi

    # Try to get the token
    local token
    token=$(gcloud secrets versions access latest --secret="$secret_name" --project="project38-483612" 2>/dev/null) || return 1

    if [ -n "$token" ]; then
        echo "   ✅ $secret_name loaded from GCP" >&2

        # If CLAUDE_ENV_FILE is available, persist the token
        if [ -n "$CLAUDE_ENV_FILE" ]; then
            echo "export $env_var_name='$token'" >> "$CLAUDE_ENV_FILE"
        fi
        return 0
    fi

    return 1
}

# Get GCP access token for Google Cloud MCP servers
get_gcp_access_token() {
    # Check if gcloud is available
    if ! command -v gcloud &> /dev/null; then
        echo "   ⚠️ gcloud not available - GCP MCP servers disabled" >&2
        return 1
    fi

    # Get access token
    local token
    token=$(gcloud auth print-access-token 2>/dev/null) || return 1

    if [ -n "$token" ]; then
        echo "   ✅ GCP access token obtained" >&2
        if [ -n "$CLAUDE_ENV_FILE" ]; then
            echo "export GCP_ACCESS_TOKEN='$token'" >> "$CLAUDE_ENV_FILE"
        fi
        return 0
    fi

    return 1
}

# Load MCP Gateway token
if [ -z "$MCP_GATEWAY_TOKEN" ]; then
    load_gcp_secret "MCP-GATEWAY-TOKEN" "MCP_GATEWAY_TOKEN" || true
else
    echo "   ✅ MCP Gateway token already in environment" >&2
fi

# Load MCP Bridge token (for Railway MCP)
if [ -z "$MCP_BRIDGE_TOKEN" ]; then
    load_gcp_secret "MCP-BRIDGE-TOKEN" "MCP_BRIDGE_TOKEN" || true
else
    echo "   ✅ MCP Bridge token already in environment" >&2
fi

# Load Workspace MCP Bridge token (for Google Workspace)
if [ -z "$WORKSPACE_MCP_BRIDGE_TOKEN" ]; then
    load_gcp_secret "WORKSPACE-MCP-BRIDGE-TOKEN" "WORKSPACE_MCP_BRIDGE_TOKEN" || true
else
    echo "   ✅ Workspace MCP Bridge token already in environment" >&2
fi

# Get GCP access token for Google Cloud MCP servers
GCP_TOKEN_AVAILABLE=false
if [ -z "$GCP_ACCESS_TOKEN" ]; then
    get_gcp_access_token && GCP_TOKEN_AVAILABLE=true
else
    echo "   ✅ GCP access token already in environment" >&2
    GCP_TOKEN_AVAILABLE=true
fi

# Set up additional environment variables
if [ -n "$CLAUDE_ENV_FILE" ]; then
    echo "export PROJECT38_AUTONOMY_ENABLED=true" >> "$CLAUDE_ENV_FILE"
    echo "export RAILWAY_PROJECT_ID=95ec21cc-9ada-41c5-8485-12f9a00e0116" >> "$CLAUDE_ENV_FILE"
    echo "export PRODUCTION_URL=https://or-infra.com" >> "$CLAUDE_ENV_FILE"
    echo "export RAILWAY_MCP_BRIDGE_URL=https://railway-mcp-bridge.up.railway.app" >> "$CLAUDE_ENV_FILE"
    echo "export GCP_PROJECT_ID=project38-483612" >> "$CLAUDE_ENV_FILE"
fi

# Build context for Claude
CONTEXT="Project38 Autonomy Status:\\n"
CONTEXT+="- MCP Gateway: https://or-infra.com/mcp\\n"
CONTEXT+="- Railway MCP Bridge: https://railway-mcp-bridge.up.railway.app\\n"
CONTEXT+="- Railway Project: delightful-cat\\n"
CONTEXT+="- Available MCP Tools: railway_deploy, railway_rollback, n8n_trigger, health_check\\n"

# Google Cloud MCP servers
if [ "$GCP_TOKEN_AVAILABLE" = true ]; then
    CONTEXT+="- GCP MCP Servers: BigQuery, Compute, GKE, Storage, Maps\\n"
    CONTEXT+="- GCP Project: project38-483612\\n"
else
    CONTEXT+="- GCP MCP Servers: ⚠️ Not authenticated\\n"
fi

# Google Workspace MCP
if [ -n "$WORKSPACE_MCP_BRIDGE_TOKEN" ]; then
    CONTEXT+="- Google Workspace: Gmail, Calendar, Drive, Sheets, Docs (28 tools)\\n"
else
    CONTEXT+="- Google Workspace: ⚠️ Token not loaded\\n"
fi

# Check token status
TOKENS_AVAILABLE=false
if [ -n "$MCP_GATEWAY_TOKEN" ] || [ -n "$MCP_BRIDGE_TOKEN" ]; then
    TOKENS_AVAILABLE=true
fi

if [ "$TOKENS_AVAILABLE" = true ] || [ -n "$CLAUDE_ENV_FILE" ]; then
    CONTEXT+="- Token Status: ✅ Available\\n"
else
    CONTEXT+="- Token Status: ⚠️ Not loaded (run setup workflows)\\n"
fi

output_context "$CONTEXT"

echo "   ✅ SessionStart hook completed" >&2
exit 0
