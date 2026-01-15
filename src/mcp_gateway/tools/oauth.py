"""OAuth tools for Google Workspace MCP Bridge.

Provides functions to exchange OAuth codes and manage tokens
using GCP Secret Manager.
"""

import httpx
from google.cloud import secretmanager

GCP_PROJECT_ID = "project38-483612"
OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
OAUTH_REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"


def get_secret(secret_name: str) -> str | None:
    """Get a secret from GCP Secret Manager.

    Args:
        secret_name: Name of the secret

    Returns:
        Secret value or None if not found
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception:
        return None


def set_secret(secret_name: str, value: str) -> bool:
    """Set a secret in GCP Secret Manager.

    Args:
        secret_name: Name of the secret
        value: Value to store

    Returns:
        True if successful
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{GCP_PROJECT_ID}"

        # Try to create the secret first
        try:
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
        except Exception:
            pass  # Secret already exists

        # Add new version
        secret_path = f"projects/{GCP_PROJECT_ID}/secrets/{secret_name}"
        client.add_secret_version(
            request={
                "parent": secret_path,
                "payload": {"data": value.encode("UTF-8")},
            }
        )
        return True
    except Exception:
        return False


async def exchange_oauth_code(auth_code: str) -> dict:
    """Exchange OAuth authorization code for refresh token.

    Args:
        auth_code: The authorization code from Google OAuth

    Returns:
        Success status and any error messages
    """
    # Get Client ID and Secret from Secret Manager
    client_id = get_secret("GOOGLE-OAUTH-CLIENT-ID")
    client_secret = get_secret("GOOGLE-OAUTH-CLIENT-SECRET")

    if not client_id:
        return {
            "success": False,
            "error": "GOOGLE-OAUTH-CLIENT-ID not found in Secret Manager",
        }

    if not client_secret:
        return {
            "success": False,
            "error": "GOOGLE-OAUTH-CLIENT-SECRET not found in Secret Manager",
        }

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OAUTH_TOKEN_ENDPOINT,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": OAUTH_REDIRECT_URI,
            },
        )

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Token exchange failed: {response.text}",
            }

        data = response.json()

        if "error" in data:
            return {
                "success": False,
                "error": data.get("error_description", data.get("error")),
            }

        refresh_token = data.get("refresh_token")
        if not refresh_token:
            return {
                "success": False,
                "error": "No refresh token in response",
            }

        # Store refresh token in Secret Manager
        if not set_secret("GOOGLE-OAUTH-REFRESH-TOKEN", refresh_token):
            return {
                "success": False,
                "error": "Failed to store refresh token in Secret Manager",
                "note": "Token was obtained but could not be saved",
            }

        return {
            "success": True,
            "message": "Refresh token obtained and stored in Secret Manager",
            "secrets_updated": ["GOOGLE-OAUTH-REFRESH-TOKEN"],
        }


async def check_oauth_status() -> dict:
    """Check Google Workspace OAuth configuration status.

    Returns:
        Which OAuth secrets are configured in Secret Manager
    """
    secrets = {
        "GOOGLE-OAUTH-CLIENT-ID": False,
        "GOOGLE-OAUTH-CLIENT-SECRET": False,
        "GOOGLE-OAUTH-REFRESH-TOKEN": False,
        "WORKSPACE-MCP-BRIDGE-TOKEN": False,
    }

    for secret_name in secrets:
        value = get_secret(secret_name)
        secrets[secret_name] = bool(value)

    all_configured = all(secrets.values())

    return {
        "configured": all_configured,
        "secrets": secrets,
        "ready_for_deployment": all_configured,
        "missing": [k for k, v in secrets.items() if not v],
    }
