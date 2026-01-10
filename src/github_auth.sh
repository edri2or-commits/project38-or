#!/bin/bash
# GitHub App Authentication - Generate installation access tokens
# Uses openssl for JWT signing instead of Python crypto libraries

set -euo pipefail

GITHUB_APP_ID="${GITHUB_APP_ID:-2497877}"
GITHUB_INSTALLATION_ID="${GITHUB_INSTALLATION_ID:-100231961}"

# Get private key from GCP Secret Manager
get_private_key() {
    python3 -c "
from src.secrets_manager import SecretManager
manager = SecretManager()
key = manager.get_secret('github-app-private-key')
if key:
    print(key)
else:
    exit(1)
"
}

# Base64url encode (RFC 4648)
base64url_encode() {
    openssl base64 -e -A | tr '+/' '-_' | tr -d '='
}

# Generate JWT
generate_jwt() {
    local private_key="$1"
    local now
    now=$(date +%s)
    local iat=$((now - 60))
    local exp=$((now + 600))

    # Header
    local header='{"alg":"RS256","typ":"JWT"}'
    local header_b64
    header_b64=$(echo -n "$header" | base64url_encode)

    # Payload
    local payload="{\"iat\":${iat},\"exp\":${exp},\"iss\":${GITHUB_APP_ID}}"
    local payload_b64
    payload_b64=$(echo -n "$payload" | base64url_encode)

    # Sign
    local signature
    signature=$(echo -n "${header_b64}.${payload_b64}" | \
        openssl dgst -sha256 -sign <(echo "$private_key") | \
        base64url_encode)

    echo "${header_b64}.${payload_b64}.${signature}"
}

# Get installation token
get_installation_token() {
    local private_key
    private_key=$(get_private_key) || {
        echo "Failed to get private key from GCP" >&2
        return 1
    }

    local jwt
    jwt=$(generate_jwt "$private_key")

    local response
    response=$(curl -s -X POST \
        -H "Authorization: Bearer ${jwt}" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/app/installations/${GITHUB_INSTALLATION_ID}/access_tokens")

    echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))"
}

# Configure gh CLI
configure_gh() {
    local token
    token=$(get_installation_token) || return 1

    if [[ -z "$token" ]]; then
        echo "Failed to get installation token" >&2
        return 1
    fi

    export GH_TOKEN="$token"
    echo "✅ GH_TOKEN configured (valid for 1 hour)"
}

# Main
case "${1:-configure}" in
    token)
        get_installation_token
        ;;
    configure|*)
        configure_gh
        ;;
esac
