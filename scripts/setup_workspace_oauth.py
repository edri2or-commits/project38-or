#!/usr/bin/env python3
"""Setup script for Google Workspace OAuth credentials.

This script helps create and configure OAuth credentials for the
Google Workspace MCP Bridge.

Usage:
    python scripts/setup_workspace_oauth.py --action generate-url
    python scripts/setup_workspace_oauth.py --action exchange-code --code AUTH_CODE
    python scripts/setup_workspace_oauth.py --action test-token
"""

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# OAuth configuration
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]

REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"


def get_credentials() -> tuple[str, str]:
    """Get OAuth credentials from environment or prompt."""
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

    if not client_id:
        print("\n📝 Enter your OAuth Client ID:")
        print("   (Get from: https://console.cloud.google.com/apis/credentials)")
        client_id = input("   Client ID: ").strip()

    if not client_secret:
        print("\n📝 Enter your OAuth Client Secret:")
        client_secret = input("   Client Secret: ").strip()

    return client_id, client_secret


def generate_auth_url(client_id: str) -> str:
    """Generate the OAuth authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange authorization code for tokens."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }

    response = httpx.post(TOKEN_URL, data=data)
    return response.json()


def test_token(refresh_token: str, client_id: str, client_secret: str) -> bool:
    """Test if refresh token is valid by getting an access token."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    response = httpx.post(TOKEN_URL, data=data)
    result = response.json()

    if "access_token" in result:
        print("✅ Token is valid!")
        print(f"   Access token expires in: {result.get('expires_in', 0)} seconds")
        return True
    else:
        print("❌ Token is invalid!")
        print(f"   Error: {result.get('error_description', result.get('error'))}")
        return False


def save_credentials(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    output_file: str = ".workspace_oauth.json",
) -> None:
    """Save credentials to a local file (for testing only)."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    path = Path(output_file)
    path.write_text(json.dumps(data, indent=2))
    print(f"\n💾 Credentials saved to: {output_file}")
    print("   ⚠️ WARNING: This file contains secrets! Do not commit to git!")


def main():
    parser = argparse.ArgumentParser(description="Setup Google Workspace OAuth")
    parser.add_argument(
        "--action",
        choices=["generate-url", "exchange-code", "test-token"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument(
        "--code",
        help="Authorization code (for exchange-code action)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save credentials to local file (testing only)",
    )

    args = parser.parse_args()

    print("\n🔐 Google Workspace OAuth Setup")
    print("=" * 40)

    if args.action == "generate-url":
        client_id, _ = get_credentials()

        print("\n📋 Authorization URL:")
        print("-" * 40)
        url = generate_auth_url(client_id)
        print(url)
        print("-" * 40)
        print("\nNext steps:")
        print("1. Open the URL above in your browser")
        print("2. Sign in with your Google account")
        print("3. Grant all requested permissions")
        print("4. Copy the authorization code shown")
        print(
            "5. Run: python scripts/setup_workspace_oauth.py --action exchange-code --code YOUR_CODE"
        )

    elif args.action == "exchange-code":
        if not args.code:
            print("❌ Authorization code required! Use --code argument")
            sys.exit(1)

        client_id, client_secret = get_credentials()

        print("\n🔄 Exchanging authorization code...")
        result = exchange_code(client_id, client_secret, args.code)

        if "error" in result:
            print(f"❌ Error: {result.get('error_description', result.get('error'))}")
            sys.exit(1)

        refresh_token = result.get("refresh_token")
        if not refresh_token:
            print("❌ No refresh token in response!")
            print(f"   Response: {result}")
            sys.exit(1)

        print("\n✅ SUCCESS! Refresh token obtained!")

        # SECURITY: Never print tokens to stdout - save to secure file instead
        token_file = Path.home() / ".oauth_refresh_token.txt"
        token_file.write_text(refresh_token)
        token_file.chmod(0o600)  # Owner read/write only
        print(f"\n🔑 Refresh Token saved to: {token_file}")
        print("   ⚠️  DELETE THIS FILE after storing in GCP Secret Manager!")

        if args.save:
            save_credentials(client_id, client_secret, refresh_token)

        print("\nNext steps:")
        print("1. Store refresh token in GCP Secret Manager:")
        print(f"   gcloud secrets create GOOGLE-OAUTH-REFRESH-TOKEN --data-file={token_file}")
        print("2. Delete the token file:")
        print(f"   rm {token_file}")
        print("\nRequired secrets in GCP Secret Manager:")
        print("  - GOOGLE-OAUTH-CLIENT-ID")
        print("  - GOOGLE-OAUTH-CLIENT-SECRET")
        print("  - GOOGLE-OAUTH-REFRESH-TOKEN")

    elif args.action == "test-token":
        client_id, client_secret = get_credentials()
        refresh_token = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "")
        if not refresh_token:
            print("\n📝 Enter your Refresh Token:")
            refresh_token = input("   Refresh Token: ").strip()

        print("\n🔍 Testing refresh token...")
        test_token(refresh_token, client_id, client_secret)


if __name__ == "__main__":
    main()
