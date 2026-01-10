"""
GitHub App Authentication - Generate installation access tokens.

This module generates short-lived installation tokens from a GitHub App
private key stored in GCP Secret Manager. Tokens are valid for 1 hour.
"""

import time
from typing import Optional

import jwt
import requests

from src.secrets_manager import SecretManager

# GitHub App configuration
GITHUB_APP_ID = 2497877
GITHUB_INSTALLATION_ID = 100231961


def generate_jwt(app_id: int, private_key: str) -> str:
    """
    Generate a JWT for GitHub App authentication.

    Args:
        app_id: The GitHub App ID
        private_key: The PEM-encoded private key

    Returns:
        A signed JWT string valid for 10 minutes
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,  # Issued 60 seconds ago (clock skew)
        "exp": now + 600,  # Expires in 10 minutes
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_token(
    app_id: int = GITHUB_APP_ID,
    installation_id: int = GITHUB_INSTALLATION_ID,
) -> Optional[str]:
    """
    Get an installation access token for the GitHub App.

    Args:
        app_id: The GitHub App ID
        installation_id: The installation ID for the repo/org

    Returns:
        An installation access token valid for 1 hour, or None on failure

    Note:
        The token is never logged or printed to prevent exposure.
    """
    # Get private key from GCP Secret Manager
    manager = SecretManager()
    private_key = manager.get_secret("github-app-private-key")

    if not private_key:
        return None

    # Generate JWT
    app_jwt = generate_jwt(app_id, private_key)

    # Exchange JWT for installation token
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json().get("token")
    except requests.RequestException:
        return None


def configure_gh_cli() -> bool:
    """
    Configure the gh CLI with an installation token.

    Returns:
        True if configuration succeeded, False otherwise

    Example:
        >>> if configure_gh_cli():
        ...     # gh commands will now work
        ...     pass
    """
    import os
    import subprocess

    token = get_installation_token()
    if not token:
        return False

    # Set token for gh CLI
    os.environ["GH_TOKEN"] = token

    # Verify authentication
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


if __name__ == "__main__":
    # Quick test - configure gh and show status
    if configure_gh_cli():
        print("✅ GitHub CLI configured successfully")
    else:
        print("❌ Failed to configure GitHub CLI")
