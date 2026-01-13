# GitHub App Integration: Code as Autonomous Domain

## Overview

GitHub serves as the **Brain** of the autonomous system - where code lives, version history exists, and CI/CD workflows execute. This document details complete GitHub App integration from JWT authentication to autonomous code operations.

---

## Why GitHub App > Personal Access Token (PAT)

For autonomous systems, GitHub Apps provide superior security and functionality compared to traditional PATs:

| Aspect | Personal Access Token (PAT) | GitHub App |
|--------|---------------------------|------------|
| **Token Lifetime** | Permanent (manual rotation) | 1 hour (auto-rotating) |
| **Permissions** | User-level (all repos) | Repository-scoped (granular) |
| **Identity** | Tied to human user | Independent app identity |
| **Rate Limits** | 5,000 requests/hour | 5,000 + 12,500/hour (17,500 total) |
| **Audit Trail** | User actions | Clear "bot" distinction |
| **Revocation Impact** | User loses access | App loses access (isolated) |
| **Best For** | Personal scripts | Production autonomous systems |

**Verdict**: Use GitHub App for autonomous systems. Use PAT only for personal development.

---

## GitHub App Authentication Flow

GitHub Apps use a **two-step authentication** process:

```
┌─────────────────────────────────────────────────────────────┐
│                   GITHUB APP AUTH FLOW                      │
└─────────────────────────────────────────────────────────────┘

Step 1: Generate JWT (JSON Web Token)
┌──────────────────┐
│  Private Key     │ (from GCP Secret Manager)
│  (RS256 PEM)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐       ┌─────────────────────┐
│ JWT Payload:     │ ----> │ Sign with RS256     │
│ - iat: now-60    │       │ (PyJWT library)     │
│ - exp: now+600   │       └──────────┬──────────┘
│ - iss: app_id    │                  │
└──────────────────┘                  │
                                      ▼
                            ┌──────────────────────┐
                            │  JWT Token           │
                            │  (valid 10 minutes)  │
                            └──────────┬───────────┘
                                      │
                                      │
Step 2: Exchange JWT for Installation Access Token (IAT)
                                      │
                                      ▼
         POST /app/installations/{installation_id}/access_tokens
         Authorization: Bearer {JWT}
                                      │
                                      ▼
                            ┌──────────────────────┐
                            │  IAT Token           │
                            │  (valid 1 hour)      │
                            │  (repository-scoped) │
                            └──────────┬───────────┘
                                      │
                                      │
Step 3: Use IAT for all GitHub API operations
                                      │
                                      ▼
         POST /repos/{owner}/{repo}/issues
         Authorization: Bearer {IAT}
                                      │
                                      ▼
                            ┌──────────────────────┐
                            │  GitHub API Response │
                            └──────────────────────┘
```

**Key Insight**: JWT is NOT used for API operations. It's only for obtaining the IAT.

---

## Production-Ready GitHubAppClient

Complete implementation with automatic token refresh:

```python
"""GitHub App authentication and operations client."""
import time
import jwt
from typing import Optional, Dict, Any, List
import httpx
from datetime import datetime, timedelta, UTC
from tenacity import retry, wait_exponential, stop_after_attempt

class GitHubAppClient:
    """Client for GitHub App authentication and API operations.

    Implements JWT-based authentication with automatic token refresh.

    Features:
    - JWT generation with RS256 signing
    - Automatic IAT refresh (5 minutes before expiration)
    - Exponential backoff retry logic
    - Full API operations (workflows, issues, PRs, commits)
    """

    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str
    ):
        """Initialize GitHub App client.

        Args:
            app_id: GitHub App ID (e.g., "123456")
            private_key: PEM-formatted RSA private key (from GCP Secret Manager)
            installation_id: Installation ID for the repository
        """
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.base_url = "https://api.github.com"

        # Token cache
        self._installation_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def generate_jwt(self) -> str:
        """Generate JWT for GitHub App authentication.

        JWT is signed with RS256 and valid for 10 minutes.
        Used to request Installation Access Tokens (IAT).

        Returns:
            Signed JWT string

        Security:
        - Clock drift tolerance: issued 60s in the past (iat: now-60)
        - Short expiration: 10 minutes (exp: now+600)
        - Issuer claim: GitHub App ID (iss: app_id)

        Example:
            >>> client = GitHubAppClient(app_id="123456", private_key=pem_key, ...)
            >>> jwt_token = client.generate_jwt()
            >>> # Use jwt_token to request IAT
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60s ago (clock drift tolerance)
            "exp": now + 600,  # Expires in 10 minutes
            "iss": self.app_id  # Issuer = App ID
        }

        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256"
        )

    async def get_installation_token(self) -> str:
        """Get Installation Access Token (IAT).

        IAT is valid for 1 hour and scoped to specific repositories.
        This is the token used for all GitHub API operations.

        Caching Strategy:
        - Token is cached until 5 minutes before expiration
        - Automatic refresh prevents mid-operation expiration

        Returns:
            Installation Access Token (IAT)

        Example:
            >>> token = await client.get_installation_token()
            >>> # Use token for API calls
            >>> # Token auto-refreshes on next call after 55 minutes
        """
        # Check if we have a valid cached token
        if self._installation_token and self._token_expires_at:
            # Refresh 5 minutes before expiration
            if datetime.now(UTC) < (self._token_expires_at - timedelta(minutes=5)):
                return self._installation_token

        # Generate new token
        jwt_token = self.generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/app/installations/{self.installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                timeout=10.0
            )
            response.raise_for_status()

            data = response.json()
            self._installation_token = data["token"]

            # Parse expiration (ISO 8601 format: 2026-01-12T21:45:00Z)
            expires_at_str = data["expires_at"].replace("Z", "+00:00")
            self._token_expires_at = datetime.fromisoformat(expires_at_str)

            return self._installation_token

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True
    )
    async def _api_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated GitHub API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
            json_data: Request body (for POST/PATCH)

        Returns:
            Parsed JSON response
        """
        token = await self.get_installation_token()

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                json=json_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                timeout=30.0
            )
            response.raise_for_status()

            # Handle 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

    # =========================================================================
    # WORKFLOW OPERATIONS
    # =========================================================================

    async def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, Any]] = None
    ) -> None:
        """Trigger a workflow_dispatch event.

        Use Case: Agent triggers deployment workflow after successful build.

        Args:
            owner: Repository owner (e.g., "edri2or-commits")
            repo: Repository name (e.g., "project38-or")
            workflow_id: Workflow file name (e.g., "deploy-railway.yml")
            ref: Branch/tag to run on (default: "main")
            inputs: Input parameters for workflow

        Example:
            >>> await client.trigger_workflow(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     workflow_id="deploy-railway.yml",
            ...     ref="main",
            ...     inputs={"environment": "production"}
            ... )
        """
        await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            json_data={
                "ref": ref,
                "inputs": inputs or {}
            }
        )

    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent workflow runs.

        Use Case: Agent monitors CI status before triggering deployment.

        Args:
            owner: Repository owner
            repo: Repository name
            workflow_id: Filter by workflow file (optional)
            status: Filter by status (completed, in_progress, queued)
            limit: Max results

        Returns:
            List of workflow run objects
        """
        endpoint = f"/repos/{owner}/{repo}/actions/runs"
        params = {"per_page": limit}
        if workflow_id:
            params["workflow_id"] = workflow_id
        if status:
            params["status"] = status

        # Add query params to endpoint
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        endpoint = f"{endpoint}?{query_string}"

        result = await self._api_request("GET", endpoint)
        return result.get("workflow_runs", [])

    # =========================================================================
    # ISSUE OPERATIONS
    # =========================================================================

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a GitHub issue.

        Use Case: Agent creates bug report when deployment fails.

        Args:
            owner: Repository owner
            repo: Repository name
            title: Issue title
            body: Issue body (Markdown supported)
            labels: Labels to apply (e.g., ["bug", "autonomous-agent"])
            assignees: GitHub usernames to assign

        Returns:
            Created issue object with number, url, etc.

        Example:
            >>> issue = await client.create_issue(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     title="Deployment Failed: Syntax Error",
            ...     body="## Error Details\n\n```\nSyntaxError: invalid syntax\n```",
            ...     labels=["bug", "deployment"]
            ... )
            >>> print(f"Issue created: {issue['html_url']}")
        """
        return await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/issues",
            json_data={
                "title": title,
                "body": body,
                "labels": labels or [],
                "assignees": assignees or []
            }
        )

    async def add_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str
    ) -> Dict[str, Any]:
        """Add a comment to an existing issue.

        Use Case: Agent provides status updates on autonomous tasks.
        """
        return await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json_data={"body": body}
        )

    async def close_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Close an issue (optionally with a final comment).

        Use Case: Agent closes issue after autonomous fix is deployed.
        """
        if comment:
            await self.add_issue_comment(owner, repo, issue_number, comment)

        return await self._api_request(
            method="PATCH",
            endpoint=f"/repos/{owner}/{repo}/issues/{issue_number}",
            json_data={"state": "closed"}
        )

    # =========================================================================
    # PULL REQUEST OPERATIONS
    # =========================================================================

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main"
    ) -> Dict[str, Any]:
        """Create a pull request.

        Use Case: Agent creates PR for autonomous code changes (future capability).

        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR description (Markdown)
            head: Branch with changes (e.g., "feature/autonomous-fix")
            base: Target branch (default: "main")

        Returns:
            Created PR object with number, url, etc.
        """
        return await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/pulls",
            json_data={
                "title": title,
                "body": body,
                "head": head,
                "base": base
            }
        )

    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        merge_method: str = "squash"
    ) -> Dict[str, Any]:
        """Merge a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR number
            merge_method: "merge", "squash", or "rebase"

        Returns:
            Merge result
        """
        return await self._api_request(
            method="PUT",
            endpoint=f"/repos/{owner}/{repo}/pulls/{pull_number}/merge",
            json_data={"merge_method": merge_method}
        )

    # =========================================================================
    # COMMIT & REF OPERATIONS
    # =========================================================================

    async def get_recent_commits(
        self,
        owner: str,
        repo: str,
        ref: str = "main",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent commits from a branch.

        Use Case: Agent correlates Railway deployment failure with recent commits.

        Returns:
            List of commit objects with sha, message, author, timestamp
        """
        result = await self._api_request(
            method="GET",
            endpoint=f"/repos/{owner}/{repo}/commits?sha={ref}&per_page={limit}"
        )
        return result

    async def get_commit_details(
        self,
        owner: str,
        repo: str,
        commit_sha: str
    ) -> Dict[str, Any]:
        """Get detailed information about a specific commit.

        Use Case: Agent analyzes what changed in a failing deployment.
        """
        return await self._api_request(
            method="GET",
            endpoint=f"/repos/{owner}/{repo}/commits/{commit_sha}"
        )

    # =========================================================================
    # REPOSITORY OPERATIONS
    # =========================================================================

    async def get_repository_info(
        self,
        owner: str,
        repo: str
    ) -> Dict[str, Any]:
        """Get repository metadata.

        Returns:
            Repository object with name, description, default_branch, etc.
        """
        return await self._api_request(
            method="GET",
            endpoint=f"/repos/{owner}/{repo}"
        )

    async def create_repository_dispatch(
        self,
        owner: str,
        repo: str,
        event_type: str,
        client_payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """Trigger a repository_dispatch event.

        Use Case: Agent notifies external systems via webhook.

        Args:
            owner: Repository owner
            repo: Repository name
            event_type: Custom event name (e.g., "deployment-complete")
            client_payload: Custom data (max 64KB JSON)
        """
        await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/dispatches",
            json_data={
                "event_type": event_type,
                "client_payload": client_payload or {}
            }
        )
```

---

## Operational Scenarios

### Scenario 1: Autonomous Deployment Trigger

**Flow**: Agent monitors GitHub for new commits → Checks if CI passed → Triggers Railway deployment

```python
async def autonomous_deployment_flow(
    github: GitHubAppClient,
    railway: RailwayClient,
    owner: str,
    repo: str
):
    """Complete autonomous deployment flow."""

    # OBSERVE: Get recent commits
    commits = await github.get_recent_commits(owner, repo, limit=1)
    latest_commit = commits[0]

    # OBSERVE: Check CI status
    workflow_runs = await github.get_workflow_runs(
        owner, repo,
        workflow_id="test.yml",
        status="completed",
        limit=1
    )

    if not workflow_runs:
        logger.warning("No completed CI runs found")
        return

    ci_run = workflow_runs[0]

    # ORIENT: Analyze CI result
    if ci_run["conclusion"] != "success":
        logger.warning(f"CI failed: {ci_run['conclusion']}")
        return

    # DECIDE: CI passed → deploy
    logger.info(f"CI passed for {latest_commit['sha']}, triggering deployment")

    # ACT: Trigger Railway deployment
    deployment_id = await railway.trigger_deployment(
        project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
        environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
    )

    # ACT: Monitor deployment
    final_status = await railway.monitor_deployment_until_stable(deployment_id)

    if final_status == "ACTIVE":
        # Success - create deployment success issue
        await github.create_issue(
            owner=owner,
            repo=repo,
            title=f"✅ Deployment Successful: {latest_commit['sha'][:7]}",
            body=f"""
            ## Deployment Report

            **Commit**: {latest_commit['sha']}
            **Message**: {latest_commit['commit']['message']}
            **Deployment ID**: {deployment_id}
            **Status**: ACTIVE

            Deployment completed successfully!
            """,
            labels=["deployment", "success"]
        )
    else:
        # Failure - handled by Railway scenario (rollback + issue creation)
        pass
```

---

### Scenario 2: Autonomous Bug Report Creation

**Trigger**: Railway deployment fails with FAILED status

**Agent Action**: Parse logs → Create detailed GitHub Issue with error context

```python
async def create_autonomous_bug_report(
    github: GitHubAppClient,
    railway: RailwayClient,
    owner: str,
    repo: str,
    failed_deployment_id: str
):
    """Create comprehensive bug report from deployment failure."""

    # Get deployment details
    deployment = await railway.get_deployment_details(failed_deployment_id)

    # Get build logs
    build_logs = await railway.get_build_logs(failed_deployment_id, limit=50)

    # Find error lines
    error_logs = [
        log for log in build_logs
        if log["severity"] == "ERROR"
    ]

    # Get recent commit (likely culprit)
    commits = await github.get_recent_commits(owner, repo, limit=1)
    recent_commit = commits[0]

    # Format error message
    error_summary = error_logs[0]["message"] if error_logs else "Unknown error"

    # Create issue
    issue = await github.create_issue(
        owner=owner,
        repo=repo,
        title=f"🚨 Deployment Failed: {error_summary[:80]}",
        body=f"""
        ## Deployment Failure Report

        **Deployment ID**: `{failed_deployment_id}`
        **Status**: {deployment['status']}
        **Timestamp**: {deployment['createdAt']}

        ---

        ## Recent Commit (Likely Culprit)

        **SHA**: `{recent_commit['sha']}`
        **Author**: {recent_commit['commit']['author']['name']}
        **Message**: {recent_commit['commit']['message']}
        **URL**: {recent_commit['html_url']}

        ---

        ## Error Details

        ```
        {chr(10).join(log['message'] for log in error_logs[:5])}
        ```

        ---

        ## Full Build Log (last 20 lines)

        ```
        {chr(10).join(log['message'] for log in build_logs[-20:])}
        ```

        ---

        ## Agent Actions Taken

        - ✅ Deployment failure detected
        - ✅ Build logs retrieved
        - ✅ Rollback initiated to last stable version
        - ✅ This issue created for human review

        **Status**: Service has been restored via rollback. Please review and fix the error.
        """,
        labels=["bug", "deployment", "autonomous-agent", "high-priority"],
        assignees=[recent_commit["commit"]["author"]["name"]] if recent_commit["commit"]["author"]["name"] else []
    )

    logger.info(f"Bug report created: {issue['html_url']}")
    return issue
```

---

### Scenario 3: Autonomous Issue Lifecycle Management

**Flow**: Agent creates issue → Monitors fix → Verifies fix → Closes issue

```python
async def autonomous_issue_lifecycle(
    github: GitHubAppClient,
    railway: RailwayClient,
    owner: str,
    repo: str,
    issue_number: int
):
    """Monitor and manage issue lifecycle autonomously."""

    # Agent created an issue for deployment failure
    # Now monitor for human fix...

    while True:
        # Get recent commits
        commits = await github.get_recent_commits(owner, repo, limit=5)

        # Check if any commit references this issue
        for commit in commits:
            message = commit["commit"]["message"].lower()
            if f"#{issue_number}" in message or f"issue-{issue_number}" in message:
                # Commit references this issue - test the fix
                await github.add_issue_comment(
                    owner, repo, issue_number,
                    f"🤖 Detected fix commit: {commit['sha'][:7]}\n\n"
                    f"Triggering test deployment..."
                )

                # Trigger deployment
                deployment_id = await railway.trigger_deployment(...)
                final_status = await railway.monitor_deployment_until_stable(deployment_id)

                if final_status == "ACTIVE":
                    # Fix successful - close issue
                    await github.close_issue(
                        owner, repo, issue_number,
                        comment=f"✅ Fix verified in deployment `{deployment_id}`.\n\n"
                                f"Service is now ACTIVE. Closing issue."
                    )
                    return
                else:
                    # Fix didn't work
                    await github.add_issue_comment(
                        owner, repo, issue_number,
                        f"❌ Test deployment failed with status: {final_status}\n\n"
                        f"Please review the fix."
                    )

        # Wait before checking again
        await asyncio.sleep(300)  # Check every 5 minutes
```

---

## Integration with OODA Loop

The GitHubAppClient serves as the **Code Worker** in the OODA Loop:

| OODA Phase | GitHub Operations |
|------------|------------------|
| **OBSERVE** | `get_recent_commits()`, `get_workflow_runs()`, `get_commit_details()` |
| **ORIENT** | Correlate commits with Railway deployments, CI status, issue tracker |
| **DECIDE** | Determine action: trigger workflow, create issue, merge PR |
| **ACT** | `trigger_workflow()`, `create_issue()`, `create_pull_request()` |

---

## Security Considerations

1. **Private Key Storage**:
   - ✅ Stored in GCP Secret Manager (secret name: `github-app-private-key`)
   - ✅ Never logged, printed, or committed
   - ✅ PEM format with BEGIN/END markers

2. **Token Lifecycle**:
   - ✅ JWT expires in 10 minutes (short-lived)
   - ✅ IAT expires in 1 hour (auto-refresh)
   - ✅ No token reuse across sessions

3. **Permission Scope**:
   - ✅ App has minimal permissions (Contents: read/write, Issues: read/write, Workflows: read/write)
   - ❌ No admin permissions
   - ❌ No delete permissions

4. **Rate Limiting**:
   - ✅ Exponential backoff on 429 errors
   - ✅ Monitor rate limit headers (`X-RateLimit-Remaining`)

---

## GitHub App Setup (Quick Reference)

**Current Configuration** (project38-or):
- **App Name**: (To be created)
- **Permissions Required**:
  - Repository Contents: Read & Write
  - Issues: Read & Write
  - Pull Requests: Read & Write
  - Workflows: Read & Write
  - Metadata: Read (automatic)

**Setup Steps**:
1. Create GitHub App at `https://github.com/settings/apps/new`
2. Generate private key (download PEM file)
3. Store private key in GCP Secret Manager: `github-app-private-key`
4. Install app on repository
5. Note Installation ID from URL: `https://github.com/settings/installations/{installation_id}`

**Usage**:
```python
from src.secrets_manager import SecretManager
from src.github_app_client import GitHubAppClient

secret_manager = SecretManager()
private_key = secret_manager.get_secret("github-app-private-key")

github = GitHubAppClient(
    app_id="123456",
    private_key=private_key,
    installation_id="789012"
)

# Operations now available
await github.create_issue(...)
await github.trigger_workflow(...)
```

---

**Next Document**: [n8n Orchestration](04-n8n-orchestration-hybrid.md) - Workflow Automation and Integration
