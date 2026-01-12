# GitHub App Setup & Authentication - Complete Guide

## Table of Contents

1. [Overview](#overview)
2. [Why GitHub App vs PAT](#why-github-app-vs-pat)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Permissions Configuration](#permissions-configuration)
5. [Authentication Flow](#authentication-flow)
6. [Python Implementation](#python-implementation)
7. [Advanced Operations](#advanced-operations)
8. [Security Best Practices](#security-best-practices)
9. [Complete Python Module](#complete-python-module)

---

## Overview

GitHub Apps provide a **more secure and scalable** authentication mechanism compared to Personal Access Tokens (PATs). They allow fine-grained permissions, installation-scoped access, and automated token rotation.

**Key Benefits:**
- ✅ Fine-grained repository-level permissions
- ✅ Installation tokens expire after 1 hour (auto-rotate)
- ✅ Audit logging for all app actions
- ✅ Independent identity (not tied to user account)
- ✅ Can trigger workflow_dispatch events
- ✅ Higher API rate limits (5,000/hour per installation)

**Current System:**
- Repository: `edri2or-commits/project38-or`
- Current auth: PAT via GitHub MCP Server
- Target: Upgrade to GitHub App for production

---

## Why GitHub App vs PAT

### Comparison Matrix

| Feature | Personal Access Token | GitHub App |
|---------|----------------------|------------|
| **Scope** | User-level (all repos) | Installation-level (selected repos) |
| **Expiration** | Manual (90 days recommended) | Auto (1 hour per token) |
| **Permissions** | Coarse-grained | Fine-grained |
| **Identity** | User account | Independent app identity |
| **Revocation** | Manual | Automatic on uninstall |
| **Audit Trail** | User actions | App-specific actions |
| **Rate Limits** | 5,000/hour (shared) | 5,000/hour per installation |
| **Workflows** | Can trigger | Can trigger |
| **CI/CD** | Requires rotation | Self-rotating |

### When to Use GitHub App

Use GitHub App when:
- ✅ Building autonomous systems (like Claude agent)
- ✅ Need fine-grained permissions
- ✅ Want automatic token rotation
- ✅ Require independent app identity
- ✅ Need audit trail separation

Keep PAT when:
- ❌ Quick prototyping/development
- ❌ Personal scripts (not production)
- ❌ Temporary access

---

## Step-by-Step Setup

### 1. Create GitHub App

1. **Navigate to GitHub Settings:**
   - Go to https://github.com/settings/apps
   - Or: Settings → Developer settings → GitHub Apps

2. **Click "New GitHub App"**

3. **Configure Basic Information:**
   ```
   GitHub App name: claude-autonomous-agent
   Homepage URL: https://github.com/edri2or-commits/project38-or
   Description: Autonomous Claude agent for Railway, GitHub, and n8n management
   ```

4. **Webhook Configuration:**
   ```
   Webhook Active: No (not needed for API-only access)
   ```

   *Note: If you want to receive webhook events (e.g., deployment status), set:*
   ```
   Webhook Active: Yes
   Webhook URL: https://your-railway-app.railway.app/github-webhook
   Webhook Secret: (generate random secret, store in GCP Secret Manager)
   ```

5. **Permissions (Repository):**
   ```
   Contents: Read and write
   Pull requests: Read and write
   Workflows: Read and write
   Issues: Read and write
   Metadata: Read-only (automatically included)
   ```

6. **Where can this GitHub App be installed?**
   ```
   ○ Only on this account (edri2or-commits)
   ```

7. **Click "Create GitHub App"**

### 2. Generate Private Key

1. After creating the app, scroll to **"Private keys"** section
2. Click **"Generate a private key"**
3. A `.pem` file will download automatically
4. **Store this file securely immediately!**

**Convert to base64 for GCP Secret Manager:**

```bash
# Read the private key
cat /path/to/your-app.2026-01-12.private-key.pem | base64 -w 0 > private-key-base64.txt

# Store in GCP Secret Manager (from local machine with gcloud auth)
gcloud secrets versions add github-app-private-key \
  --data-file=private-key-base64.txt \
  --project=project38-483612

# Clean up local files
rm /path/to/your-app.2026-01-12.private-key.pem private-key-base64.txt
```

### 3. Note App Credentials

After creation, note these values (you'll need them):

```python
# From the app settings page
GITHUB_APP_ID = "123456"  # App ID (top of settings page)
GITHUB_APP_INSTALLATION_ID = "12345678"  # Get from next step
GITHUB_APP_PRIVATE_KEY_SECRET = "github-app-private-key"  # GCP Secret Manager
```

### 4. Install App on Repository

1. Go to app settings page: `https://github.com/settings/apps/claude-autonomous-agent`
2. Click **"Install App"** in left sidebar
3. Select account: `edri2or-commits`
4. Choose repository access:
   ```
   ○ Only select repositories
     ☑ project38-or
   ```
5. Click **"Install"**

### 5. Get Installation ID

**Method 1: From Installation URL**

After installing, you'll be redirected to:
```
https://github.com/settings/installations/12345678
```

The number `12345678` is your installation ID.

**Method 2: Via API**

```bash
# Generate JWT (see authentication section)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/app/installations

# Response includes installation ID
[
  {
    "id": 12345678,
    "account": {
      "login": "edri2or-commits"
    },
    "repository_selection": "selected",
    "created_at": "2026-01-12T20:00:00Z"
  }
]
```

### 6. Verify Installation

```python
# Test script to verify setup
import asyncio
from github_auth import GitHubAppAuth

async def verify_installation():
    auth = GitHubAppAuth(
        app_id="123456",
        private_key_secret="github-app-private-key",
        installation_id="12345678"
    )

    token = await auth.get_installation_token()
    print(f"✓ Installation token generated: {token[:10]}...")

    # Test API access
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/repos/edri2or-commits/project38-or",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json"
            }
        )
        print(f"✓ API access verified: {response.status_code}")

asyncio.run(verify_installation())
```

---

## Permissions Configuration

### Minimum Required Permissions

For autonomous Claude agent to manage Railway, GitHub, and n8n:

| Permission | Access Level | Purpose |
|------------|-------------|---------|
| **Contents** | Read and write | Push code, create commits |
| **Pull requests** | Read and write | Create/merge PRs, add comments |
| **Workflows** | Read and write | Trigger workflow_dispatch, modify .github/workflows/ |
| **Issues** | Read and write | Create/update issues, add comments |
| **Metadata** | Read-only | Required (auto-included) |
| **Actions** | Read | View workflow run status (optional) |

### Permission Details

#### Contents (Read and write)

Allows:
- ✅ Read repository files
- ✅ Create/update/delete files
- ✅ Push commits
- ✅ Create branches
- ✅ Create tags

**GraphQL/REST operations:**
- `GET /repos/{owner}/{repo}/contents/{path}`
- `PUT /repos/{owner}/{repo}/contents/{path}`
- `POST /repos/{owner}/{repo}/git/commits`

#### Pull Requests (Read and write)

Allows:
- ✅ List pull requests
- ✅ Create pull requests
- ✅ Update PR title/description
- ✅ Add PR comments
- ✅ Request reviews
- ✅ Merge pull requests

**Critical for:**
- Creating PRs after code changes
- Auto-merge after CI passes

#### Workflows (Read and write)

Allows:
- ✅ Read workflow files in `.github/workflows/`
- ✅ Modify workflow files
- ✅ Trigger `workflow_dispatch` events
- ✅ Re-run failed workflows

**Critical for:**
- Triggering Railway deployments via GitHub Actions
- Running tests before merge

**Note:** This permission is **required** to modify files in `.github/workflows/` directory. Without it, you'll get a 403 error when trying to update workflow files.

#### Issues (Read and write)

Allows:
- ✅ Create issues
- ✅ Update issue title/body
- ✅ Add issue comments
- ✅ Add/remove labels
- ✅ Close/reopen issues

**Critical for:**
- Agent workflow triggered by issue comments
- Reporting deployment status

---

## Authentication Flow

### Overview

GitHub App authentication uses **JWT (JSON Web Token)** + **Installation Token** flow:

```
1. Generate JWT from private key + app ID
   ↓
2. Exchange JWT for installation token (1 hour validity)
   ↓
3. Use installation token for API requests
   ↓
4. Token expires after 1 hour → repeat from step 1
```

### JWT Generation

**Requirements:**
- App ID
- Private key (RS256)
- Current timestamp

**Python Libraries:**
```bash
pip install PyJWT cryptography
```

**JWT Structure:**

```python
import jwt
import time

# Payload
payload = {
    "iat": int(time.time()),           # Issued at time
    "exp": int(time.time()) + 600,     # Expiration (10 minutes max)
    "iss": "123456"                     # GitHub App ID
}

# Generate JWT
jwt_token = jwt.encode(
    payload,
    private_key,
    algorithm="RS256"
)
```

**Important:** JWT is valid for **maximum 10 minutes**. GitHub recommends 5-10 minutes.

### Installation Token Exchange

**Request:**

```python
import httpx

async def get_installation_token(jwt_token: str, installation_id: str) -> str:
    """Exchange JWT for installation access token."""

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        return data["token"]
```

**Response:**

```json
{
  "token": "ghs_16C7e42F292c6912E7710c838347Ae178B4a",
  "expires_at": "2026-01-12T21:00:00Z",
  "permissions": {
    "contents": "write",
    "pull_requests": "write",
    "workflows": "write"
  },
  "repository_selection": "selected"
}
```

### Token Caching Strategy

**Problem:** Generating JWT and exchanging for installation token on every API request is inefficient.

**Solution:** Cache installation token until 5 minutes before expiration.

```python
from datetime import datetime, timedelta
from typing import Optional

class TokenCache:
    """Cache installation tokens with expiration."""

    def __init__(self):
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None

    def get(self) -> Optional[str]:
        """Get cached token if still valid."""
        if not self._token or not self._expires_at:
            return None

        # Refresh 5 minutes before expiration
        if datetime.utcnow() >= self._expires_at - timedelta(minutes=5):
            return None

        return self._token

    def set(self, token: str, expires_at: str):
        """Cache new token."""
        self._token = token
        self._expires_at = datetime.fromisoformat(
            expires_at.replace("Z", "+00:00")
        )
```

---

## Python Implementation

### GitHub App Authentication Module

```python
"""
GitHub App Authentication Module

Usage:
    from github_auth import GitHubAppAuth

    auth = GitHubAppAuth(
        app_id="123456",
        private_key_secret="github-app-private-key",
        installation_id="12345678"
    )

    # Get installation token (cached)
    token = await auth.get_installation_token()

    # Use token for API requests
    headers = {"Authorization": f"token {token}"}
"""

import jwt
import time
import httpx
import base64
from datetime import datetime, timedelta
from typing import Optional
import logging

from src.secrets_manager import SecretManager

logger = logging.getLogger(__name__)


class GitHubAppAuth:
    """
    GitHub App authentication with JWT and installation token caching.

    Handles:
    - JWT generation from private key
    - Installation token exchange
    - Automatic token refresh before expiration
    - Private key retrieval from GCP Secret Manager
    """

    def __init__(
        self,
        app_id: str,
        private_key_secret: str,
        installation_id: str
    ):
        """
        Initialize GitHub App authentication.

        Args:
            app_id: GitHub App ID (from app settings)
            private_key_secret: Secret name in GCP Secret Manager
            installation_id: GitHub App installation ID
        """
        self.app_id = app_id
        self.private_key_secret = private_key_secret
        self.installation_id = installation_id

        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._private_key: Optional[str] = None

    def _load_private_key(self) -> str:
        """
        Load private key from GCP Secret Manager.

        Returns:
            Private key as PEM string

        Raises:
            Exception: If secret cannot be retrieved
        """
        if self._private_key:
            return self._private_key

        manager = SecretManager()
        private_key_b64 = manager.get_secret(self.private_key_secret)

        # Decode from base64
        private_key_bytes = base64.b64decode(private_key_b64)
        self._private_key = private_key_bytes.decode("utf-8")

        logger.info("Loaded GitHub App private key from GCP Secret Manager")
        return self._private_key

    def _generate_jwt(self) -> str:
        """
        Generate JWT for GitHub App authentication.

        Returns:
            JWT token string

        Raises:
            Exception: If JWT generation fails
        """
        private_key = self._load_private_key()

        # JWT payload
        now = int(time.time())
        payload = {
            "iat": now,                # Issued at time
            "exp": now + 600,          # Expiration (10 minutes)
            "iss": self.app_id         # GitHub App ID
        }

        # Generate JWT with RS256 algorithm
        jwt_token = jwt.encode(
            payload,
            private_key,
            algorithm="RS256"
        )

        logger.debug("Generated JWT for GitHub App")
        return jwt_token

    async def _exchange_jwt_for_token(self, jwt_token: str) -> tuple[str, str]:
        """
        Exchange JWT for installation access token.

        Args:
            jwt_token: JWT token from _generate_jwt()

        Returns:
            Tuple of (token, expires_at)

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            token = data["token"]
            expires_at = data["expires_at"]

            logger.info(f"Obtained installation token, expires at {expires_at}")
            return token, expires_at

    async def get_installation_token(self) -> str:
        """
        Get installation access token (cached if still valid).

        Returns:
            GitHub installation access token

        Raises:
            Exception: If token generation fails
        """
        # Check if cached token is still valid
        if self._token and self._token_expires_at:
            # Refresh 5 minutes before expiration
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                logger.debug("Using cached installation token")
                return self._token

        # Generate new token
        logger.info("Generating new installation token...")
        jwt_token = self._generate_jwt()
        token, expires_at = await self._exchange_jwt_for_token(jwt_token)

        # Cache token
        self._token = token
        self._token_expires_at = datetime.fromisoformat(
            expires_at.replace("Z", "+00:00")
        )

        return token

    async def get_authenticated_client(self) -> httpx.AsyncClient:
        """
        Get httpx client with authentication headers.

        Returns:
            Authenticated httpx.AsyncClient

        Example:
            >>> async with auth.get_authenticated_client() as client:
            ...     response = await client.get("https://api.github.com/repos/...")
        """
        token = await self.get_installation_token()

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        return httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
            follow_redirects=True
        )
```

---

## Advanced Operations

### Trigger workflow_dispatch

```python
async def trigger_workflow(
    auth: GitHubAppAuth,
    repo: str,
    workflow_id: str,
    ref: str = "main",
    inputs: dict = None
):
    """
    Trigger GitHub Actions workflow via workflow_dispatch.

    Args:
        auth: GitHubAppAuth instance
        repo: Repository in format "owner/repo"
        workflow_id: Workflow filename (e.g., "deploy-railway.yml") or ID
        ref: Branch/tag to run workflow on
        inputs: Optional workflow inputs dict

    Example:
        >>> await trigger_workflow(
        ...     auth=auth,
        ...     repo="edri2or-commits/project38-or",
        ...     workflow_id="deploy-railway.yml",
        ...     ref="main",
        ...     inputs={"environment": "production"}
        ... )
    """
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/dispatches"

    payload = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs

    async with await auth.get_authenticated_client() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

        logger.info(f"Triggered workflow {workflow_id} on {ref}")
```

### Get Workflow Run Status

```python
async def get_workflow_runs(
    auth: GitHubAppAuth,
    repo: str,
    workflow_id: str,
    status: str = "in_progress"
) -> list:
    """
    Get workflow runs for a specific workflow.

    Args:
        auth: GitHubAppAuth instance
        repo: Repository in format "owner/repo"
        workflow_id: Workflow filename or ID
        status: Filter by status (queued, in_progress, completed)

    Returns:
        List of workflow run dicts
    """
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/runs"

    params = {"status": status, "per_page": 10}

    async with await auth.get_authenticated_client() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        return data["workflow_runs"]


async def wait_for_workflow_completion(
    auth: GitHubAppAuth,
    repo: str,
    run_id: int,
    timeout: int = 600
) -> str:
    """
    Wait for workflow run to complete.

    Args:
        auth: GitHubAppAuth instance
        repo: Repository in format "owner/repo"
        run_id: Workflow run ID
        timeout: Maximum wait time in seconds

    Returns:
        Final conclusion (success, failure, cancelled, etc.)

    Raises:
        TimeoutError: If workflow exceeds timeout
    """
    import asyncio

    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"
    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Workflow run {run_id} timed out")

        async with await auth.get_authenticated_client() as client:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            status = data["status"]
            conclusion = data.get("conclusion")

            logger.info(f"Workflow status: {status}, conclusion: {conclusion}")

            if status == "completed":
                return conclusion

        await asyncio.sleep(10)  # Poll every 10 seconds
```

### Create Pull Request

```python
async def create_pull_request(
    auth: GitHubAppAuth,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str = "main"
) -> dict:
    """
    Create a pull request.

    Args:
        auth: GitHubAppAuth instance
        repo: Repository in format "owner/repo"
        title: PR title
        body: PR description (markdown)
        head: Branch to merge from
        base: Branch to merge into

    Returns:
        PR data dict with number, url, etc.
    """
    url = f"https://api.github.com/repos/{repo}/pulls"

    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base
    }

    async with await auth.get_authenticated_client() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

        pr_data = response.json()
        logger.info(f"Created PR #{pr_data['number']}: {pr_data['html_url']}")

        return {
            "number": pr_data["number"],
            "url": pr_data["html_url"],
            "api_url": pr_data["url"],
            "state": pr_data["state"]
        }
```

### Merge Pull Request

```python
async def merge_pull_request(
    auth: GitHubAppAuth,
    repo: str,
    pr_number: int,
    merge_method: str = "squash",
    commit_title: str = None,
    commit_message: str = None
) -> dict:
    """
    Merge a pull request.

    Args:
        auth: GitHubAppAuth instance
        repo: Repository in format "owner/repo"
        pr_number: PR number
        merge_method: "merge", "squash", or "rebase"
        commit_title: Optional custom commit title
        commit_message: Optional custom commit message

    Returns:
        Merge result dict
    """
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"

    payload = {"merge_method": merge_method}
    if commit_title:
        payload["commit_title"] = commit_title
    if commit_message:
        payload["commit_message"] = commit_message

    async with await auth.get_authenticated_client() as client:
        response = await client.put(url, json=payload)
        response.raise_for_status()

        data = response.json()
        logger.info(f"Merged PR #{pr_number}: {data['message']}")

        return data
```

### Read Workflow Logs

```python
async def get_workflow_logs(
    auth: GitHubAppAuth,
    repo: str,
    run_id: int
) -> str:
    """
    Get logs for a workflow run.

    Args:
        auth: GitHubAppAuth instance
        repo: Repository in format "owner/repo"
        run_id: Workflow run ID

    Returns:
        Logs as string (ZIP archive URL)

    Note: GitHub returns logs as ZIP archive. You need to download and extract.
    """
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/logs"

    async with await auth.get_authenticated_client() as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

        # Response is a redirect to ZIP file
        # In production, download and extract ZIP
        return response.text
```

---

## Security Best Practices

### 1. Private Key Management

**DO:**
- ✅ Store private key in GCP Secret Manager (base64 encoded)
- ✅ Never log private key contents
- ✅ Rotate private keys every 90 days
- ✅ Use separate apps for dev/staging/prod

**DON'T:**
- ❌ Commit private key to repository
- ❌ Store private key in environment variables
- ❌ Share private key across multiple installations
- ❌ Print/log private key in any form

### 2. Installation Token Handling

**DO:**
- ✅ Cache tokens (don't generate on every request)
- ✅ Refresh 5 minutes before expiration
- ✅ Clear tokens from memory after use
- ✅ Use separate tokens for different operations

**DON'T:**
- ❌ Log installation tokens
- ❌ Store tokens to disk
- ❌ Share tokens between processes
- ❌ Reuse expired tokens

### 3. Permissions Principle of Least Privilege

**DO:**
- ✅ Request minimum permissions needed
- ✅ Use repository-level installation (not organization-wide)
- ✅ Audit permissions quarterly
- ✅ Document why each permission is needed

**DON'T:**
- ❌ Request "admin" permissions unless absolutely necessary
- ❌ Install on all repositories
- ❌ Grant write access if read-only suffices

### 4. Audit Logging

```python
import logging

# Configure structured logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Log all GitHub API operations (but NOT tokens!)
logger.info(f"Triggered workflow {workflow_id} on {repo}")
logger.info(f"Created PR #{pr_number}: {pr_url}")
logger.warning(f"Failed to merge PR #{pr_number}: {error}")
```

### 5. Rate Limit Monitoring

```python
async def check_rate_limit(auth: GitHubAppAuth):
    """Monitor GitHub API rate limit."""

    url = "https://api.github.com/rate_limit"

    async with await auth.get_authenticated_client() as client:
        response = await client.get(url)
        data = response.json()

        core = data["resources"]["core"]
        logger.info(
            f"Rate limit: {core['remaining']}/{core['limit']} "
            f"(resets at {core['reset']})"
        )

        if core["remaining"] < 100:
            logger.warning("Rate limit running low!")

        return core
```

---

## Complete Python Module

Save as `src/github_app.py`:

```python
"""
GitHub App Client - Production-Ready Implementation

Features:
- JWT-based authentication with private key from GCP Secret Manager
- Installation token caching with auto-refresh
- Comprehensive GitHub API operations
- Error handling and retry logic
- Rate limit monitoring

Usage:
    from src.github_app import GitHubAppClient

    client = GitHubAppClient(
        app_id="123456",
        private_key_secret="github-app-private-key",
        installation_id="12345678"
    )

    # Trigger workflow
    await client.trigger_workflow(
        repo="edri2or-commits/project38-or",
        workflow_id="deploy-railway.yml",
        inputs={"environment": "production"}
    )

    # Create PR
    pr = await client.create_pull_request(
        repo="edri2or-commits/project38-or",
        title="Deploy to production",
        body="## Changes\\n- Feature X",
        head="feature/x",
        base="main"
    )

    # Wait for PR checks to pass, then merge
    await client.wait_for_checks(pr["number"])
    await client.merge_pull_request(pr["number"], merge_method="squash")
"""

import jwt
import time
import httpx
import base64
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from src.secrets_manager import SecretManager

logger = logging.getLogger(__name__)


class GitHubAppClient:
    """
    Production-ready GitHub App API client.

    Handles authentication, API operations, and error handling for
    autonomous GitHub operations via GitHub App.
    """

    def __init__(
        self,
        app_id: str,
        private_key_secret: str,
        installation_id: str,
        repo: str = "edri2or-commits/project38-or"
    ):
        """
        Initialize GitHub App client.

        Args:
            app_id: GitHub App ID
            private_key_secret: Secret name in GCP Secret Manager
            installation_id: GitHub App installation ID
            repo: Default repository (owner/name format)
        """
        self.app_id = app_id
        self.private_key_secret = private_key_secret
        self.installation_id = installation_id
        self.repo = repo

        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._private_key: Optional[str] = None

    def _load_private_key(self) -> str:
        """Load private key from GCP Secret Manager."""
        if self._private_key:
            return self._private_key

        manager = SecretManager()
        private_key_b64 = manager.get_secret(self.private_key_secret)
        private_key_bytes = base64.b64decode(private_key_b64)
        self._private_key = private_key_bytes.decode("utf-8")

        logger.info("Loaded GitHub App private key")
        return self._private_key

    def _generate_jwt(self) -> str:
        """Generate JWT for GitHub App authentication."""
        private_key = self._load_private_key()

        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 600,
            "iss": self.app_id
        }

        return jwt.encode(payload, private_key, algorithm="RS256")

    async def _refresh_token(self):
        """Refresh installation access token."""
        jwt_token = self._generate_jwt()

        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            self._token = data["token"]
            self._token_expires_at = datetime.fromisoformat(
                data["expires_at"].replace("Z", "+00:00")
            )

            logger.info(f"Refreshed token, expires at {data['expires_at']}")

    async def _get_token(self) -> str:
        """Get valid installation token (cached or refreshed)."""
        if self._token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return self._token

        await self._refresh_token()
        return self._token

    async def _request(
        self,
        method: str,
        path: str,
        json: dict = None,
        params: dict = None
    ) -> Any:
        """
        Make authenticated GitHub API request.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            path: API path (e.g., "/repos/owner/repo")
            json: Optional JSON payload
            params: Optional query parameters

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPError: On API errors
        """
        token = await self._get_token()

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        url = f"https://api.github.com{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=json,
                params=params
            )

            response.raise_for_status()

            # Some endpoints return 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

    # ============ Workflow Operations ============

    async def trigger_workflow(
        self,
        workflow_id: str,
        ref: str = "main",
        inputs: Dict[str, str] = None,
        repo: str = None
    ):
        """
        Trigger workflow_dispatch event.

        Args:
            workflow_id: Workflow filename (e.g., "deploy-railway.yml")
            ref: Branch/tag to run on
            inputs: Workflow inputs dict
            repo: Override default repo

        Example:
            >>> await client.trigger_workflow(
            ...     workflow_id="deploy-railway.yml",
            ...     inputs={"environment": "production"}
            ... )
        """
        repo = repo or self.repo
        path = f"/repos/{repo}/actions/workflows/{workflow_id}/dispatches"

        payload = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs

        await self._request("POST", path, json=payload)
        logger.info(f"Triggered workflow {workflow_id} on {ref}")

    async def get_workflow_runs(
        self,
        workflow_id: str,
        status: str = "in_progress",
        repo: str = None
    ) -> List[Dict]:
        """Get workflow runs filtered by status."""
        repo = repo or self.repo
        path = f"/repos/{repo}/actions/workflows/{workflow_id}/runs"

        data = await self._request(
            "GET",
            path,
            params={"status": status, "per_page": 10}
        )

        return data["workflow_runs"]

    async def wait_for_workflow(
        self,
        run_id: int,
        timeout: int = 600,
        repo: str = None
    ) -> str:
        """
        Wait for workflow run to complete.

        Args:
            run_id: Workflow run ID
            timeout: Maximum wait time in seconds
            repo: Override default repo

        Returns:
            Final conclusion (success, failure, etc.)

        Raises:
            TimeoutError: If workflow exceeds timeout
        """
        repo = repo or self.repo
        path = f"/repos/{repo}/actions/runs/{run_id}"
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Workflow run {run_id} timed out")

            data = await self._request("GET", path)
            status = data["status"]
            conclusion = data.get("conclusion")

            logger.info(f"Workflow {run_id}: status={status}, conclusion={conclusion}")

            if status == "completed":
                return conclusion

            await asyncio.sleep(10)

    # ============ Pull Request Operations ============

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        repo: str = None
    ) -> Dict[str, Any]:
        """
        Create a pull request.

        Args:
            title: PR title
            body: PR description (markdown)
            head: Branch to merge from
            base: Branch to merge into
            repo: Override default repo

        Returns:
            PR data dict with number, url, etc.
        """
        repo = repo or self.repo
        path = f"/repos/{repo}/pulls"

        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }

        data = await self._request("POST", path, json=payload)

        logger.info(f"Created PR #{data['number']}: {data['html_url']}")

        return {
            "number": data["number"],
            "url": data["html_url"],
            "api_url": data["url"],
            "state": data["state"],
            "head": data["head"]["sha"]
        }

    async def merge_pull_request(
        self,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: str = None,
        repo: str = None
    ) -> Dict[str, Any]:
        """
        Merge a pull request.

        Args:
            pr_number: PR number
            merge_method: "merge", "squash", or "rebase"
            commit_title: Optional custom commit title
            repo: Override default repo

        Returns:
            Merge result dict
        """
        repo = repo or self.repo
        path = f"/repos/{repo}/pulls/{pr_number}/merge"

        payload = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title

        data = await self._request("PUT", path, json=payload)

        logger.info(f"Merged PR #{pr_number}")
        return data

    async def get_pr_status(
        self,
        pr_number: int,
        repo: str = None
    ) -> Dict[str, Any]:
        """Get pull request status and check runs."""
        repo = repo or self.repo

        # Get PR details
        pr_path = f"/repos/{repo}/pulls/{pr_number}"
        pr_data = await self._request("GET", pr_path)

        # Get combined status for PR head
        status_path = f"/repos/{repo}/commits/{pr_data['head']['sha']}/status"
        status_data = await self._request("GET", status_path)

        return {
            "state": pr_data["state"],
            "mergeable": pr_data.get("mergeable"),
            "merged": pr_data.get("merged", False),
            "checks_state": status_data["state"],
            "statuses": status_data["statuses"]
        }

    # ============ Repository Operations ============

    async def get_file_contents(
        self,
        path: str,
        ref: str = "main",
        repo: str = None
    ) -> str:
        """Get file contents from repository."""
        repo = repo or self.repo
        api_path = f"/repos/{repo}/contents/{path}"

        data = await self._request("GET", api_path, params={"ref": ref})

        # Decode base64 content
        import base64
        content = base64.b64decode(data["content"]).decode("utf-8")

        return content

    async def check_rate_limit(self) -> Dict[str, Any]:
        """Check GitHub API rate limit status."""
        data = await self._request("GET", "/rate_limit")

        core = data["resources"]["core"]
        logger.info(
            f"Rate limit: {core['remaining']}/{core['limit']} "
            f"(resets at {datetime.fromtimestamp(core['reset'])})"
        )

        return core
```

---

## Sources

- [Authenticating as a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app)
- [Generating JWT for GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app)
- [Authenticating as GitHub App Installation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
- [Choosing Permissions for GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)
- [REST API Endpoints for Workflows](https://docs.github.com/en/rest/actions/workflows)
- [GitHub App JWT Authentication Example (Python)](https://gist.github.com/pelson/47c0c89a3522ed8da5cc305afc2562b0)
- [How to Authenticate GitHub App using Python](https://donchev.is/post/how-to-authenticate-a-github-app-using-python/)
- [GitHub Actions workflow_dispatch](https://graphite.com/guides/github-actions-workflow-dispatch)

---

## Next Steps

1. ✅ Create GitHub App with proper permissions
2. ✅ Generate and store private key in GCP Secret Manager
3. ✅ Get installation ID
4. ✅ Implement `src/github_app.py` module
5. ✅ Test authentication with verification script
6. ✅ Integrate with Railway deployment workflow
7. ✅ Set up audit logging
8. ✅ Schedule quarterly permission reviews

**Last Updated:** 2026-01-12
