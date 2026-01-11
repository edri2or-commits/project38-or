"""GitHub Pull Request operations - Works in any environment.

This module provides PR operations that work regardless of gh CLI availability:
1. Prefers gh CLI if available (handles proxy correctly)
2. Falls back to requests + GH_TOKEN if gh is missing
3. Can auto-install gh CLI if needed and user has sudo

Security: Never logs or prints tokens.
"""

import json
import os
import shutil
import subprocess
from typing import Any


def _get_gh_token() -> str | None:
    """Get GitHub token from environment or gh CLI config.

    Returns:
        GitHub token or None if not found.
    """
    # Try GH_TOKEN environment variable first
    token = os.environ.get("GH_TOKEN")
    if token:
        return token

    # Try GITHUB_TOKEN (common in CI)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # Try gh CLI config
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return None


def ensure_gh_cli() -> bool:
    """Ensure gh CLI is available.

    Checks if gh is installed. If not, attempts to install it.
    Requires sudo/root access for installation.

    Returns:
        True if gh is available, False otherwise.
    """
    if shutil.which("gh"):
        return True

    # Try to install gh
    try:
        print("⚠️  gh CLI not found. Attempting to install...")

        # Ubuntu/Debian installation
        commands = [
            ["sudo", "apt", "update"],
            [
                "sudo",
                "apt",
                "install",
                "-y",
                "gh",
            ],
        ]

        for cmd in commands:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                return False

        # Verify installation
        return shutil.which("gh") is not None

    except (subprocess.SubprocessError, PermissionError):
        return False


def create_pr_with_gh(
    title: str,
    body: str,
    repo: str,
    head: str | None = None,
    base: str = "main",
) -> dict[str, Any] | None:
    """Create PR using gh CLI.

    Args:
        title: PR title
        body: PR body (markdown)
        repo: Repository in format "owner/repo"
        head: Source branch (default: current branch)
        base: Target branch (default: main)

    Returns:
        PR data dict with url, number, etc. or None on failure.
    """
    cmd = [
        "gh",
        "pr",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--repo",
        repo,
        "--base",
        base,
    ]

    if head:
        cmd.extend(["--head", head])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            return None

        # gh pr create returns the PR URL
        pr_url = result.stdout.strip()

        # Get PR number from URL
        pr_number = pr_url.split("/")[-1]

        return {
            "url": pr_url,
            "number": int(pr_number),
            "state": "open",
        }

    except subprocess.SubprocessError:
        return None


def create_pr_with_requests(
    title: str,
    body: str,
    repo: str,
    head: str,
    base: str = "main",
    token: str | None = None,
) -> dict[str, Any] | None:
    """Create PR using requests library (fallback).

    Note: This may fail in Anthropic environment due to proxy interference.
    Only use when gh CLI is unavailable.

    Args:
        title: PR title
        body: PR body (markdown)
        repo: Repository in format "owner/repo"
        head: Source branch
        base: Target branch (default: main)
        token: GitHub token (will try to get automatically if None)

    Returns:
        PR data dict or None on failure.
    """
    import requests

    if not token:
        token = _get_gh_token()

    if not token:
        return None

    url = f"https://api.github.com/repos/{repo}/pulls"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    data = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        pr_data = response.json()

        return {
            "url": pr_data["html_url"],
            "number": pr_data["number"],
            "state": pr_data["state"],
        }

    except Exception:  # Catch all exceptions (network, requests, etc.)
        return None


def create_pr(
    title: str,
    body: str,
    repo: str,
    head: str | None = None,
    base: str = "main",
) -> dict[str, Any] | None:
    """Create a GitHub Pull Request (works in any environment).

    Tries methods in order:
    1. gh CLI (preferred - handles proxy correctly)
    2. requests library (fallback - may fail with proxy)

    Args:
        title: PR title
        body: PR description (markdown)
        repo: Repository in format "owner/repo"
        head: Source branch (default: current branch)
        base: Target branch (default: main)

    Returns:
        Dict with PR data (url, number, state) or None on failure.

    Example:
        >>> pr = create_pr(
        ...     title="Add feature X",
        ...     body="## Summary\\nAdds feature X",
        ...     repo="owner/repo",
        ...     head="feature/x"
        ... )
        >>> if pr:
        ...     print(f"Created PR #{pr['number']}: {pr['url']}")
    """
    # Method 1: Try gh CLI (preferred)
    if shutil.which("gh"):
        result = create_pr_with_gh(title, body, repo, head, base)
        if result:
            return result

    # Method 2: Try requests (fallback)
    if not head:
        # Get current branch
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                head = result.stdout.strip()
        except Exception:  # Catch all exceptions
            return None

    if not head:
        return None

    return create_pr_with_requests(title, body, repo, head, base)


if __name__ == "__main__":
    # Quick test
    print(f"gh CLI available: {shutil.which('gh') is not None}")
    print(f"GH_TOKEN available: {_get_gh_token() is not None}")
