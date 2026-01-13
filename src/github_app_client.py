"""GitHub App Client for autonomous GitHub operations.

Implements JWT-based authentication with automatic token refresh and
comprehensive GitHub API operations for autonomous agent control.

Example:
    >>> from src.secrets_manager import SecretManager
    >>> from src.github_app_client import GitHubAppClient
    >>>
    >>> # Initialize from GCP Secret Manager
    >>> manager = SecretManager()
    >>> private_key = manager.get_secret("github-app-private-key")
    >>>
    >>> client = GitHubAppClient(
    ...     app_id="2497877",
    ...     private_key=private_key,
    ...     installation_id="100231961"
    ... )
    >>>
    >>> # Trigger deployment workflow
    >>> await client.trigger_workflow(
    ...     owner="edri2or-commits",
    ...     repo="project38-or",
    ...     workflow_id="deploy-railway.yml",
    ...     inputs={"environment": "production"}
    ... )
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# ============================================================================
# EXCEPTION CLASSES
# ============================================================================


class GitHubAppError(Exception):
    """Base exception for GitHub App operations."""

    pass


class GitHubAppAuthenticationError(GitHubAppError):
    """Raised when authentication fails (JWT or IAT generation)."""

    pass


class GitHubAppRateLimitError(GitHubAppError):
    """Raised when GitHub API rate limit is exceeded."""

    pass


class GitHubAppNotFoundError(GitHubAppError):
    """Raised when requested resource is not found."""

    pass


# ============================================================================
# GITHUB APP CLIENT
# ============================================================================


class GitHubAppClient:
    """Client for GitHub App authentication and API operations.

    Implements JWT-based authentication with automatic token refresh.

    Features:
    - JWT generation with RS256 signing
    - Automatic IAT refresh (5 minutes before expiration)
    - Exponential backoff retry logic
    - Full API operations (workflows, issues, PRs, commits)

    Attributes:
        app_id: GitHub App ID (e.g., "2497877")
        private_key: PEM-formatted RSA private key
        installation_id: Installation ID for the repository
        base_url: GitHub API base URL (default: https://api.github.com)
    """

    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str,
        base_url: str = "https://api.github.com",
    ):
        """Initialize GitHub App client.

        Args:
            app_id: GitHub App ID (e.g., "2497877")
            private_key: PEM-formatted RSA private key (from GCP Secret Manager)
            installation_id: Installation ID for the repository (e.g., "100231961")
            base_url: GitHub API base URL (default: https://api.github.com)
        """
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.base_url = base_url

        # Token cache
        self._installation_token: str | None = None
        self._token_expires_at: datetime | None = None

    def __del__(self):
        """Clear sensitive data from memory on cleanup."""
        if hasattr(self, "private_key"):
            self.private_key = None
        if hasattr(self, "_installation_token"):
            self._installation_token = None

    # ========================================================================
    # AUTHENTICATION
    # ========================================================================

    def generate_jwt(self) -> str:
        """Generate JWT for GitHub App authentication.

        JWT is signed with RS256 and valid for 10 minutes.
        Used to request Installation Access Tokens (IAT).

        Returns:
            Signed JWT string

        Raises:
            GitHubAppAuthenticationError: If JWT generation fails

        Security:
        - Clock drift tolerance: issued 60s in the past (iat: now-60)
        - Short expiration: 10 minutes (exp: now+600)
        - Issuer claim: GitHub App ID (iss: app_id)

        Example:
            >>> client = GitHubAppClient(...)
            >>> jwt_token = client.generate_jwt()
            >>> # Use jwt_token to request IAT
        """
        try:
            now = int(time.time())
            payload = {
                "iat": now - 60,  # Issued 60s ago (clock drift tolerance)
                "exp": now + 600,  # Expires in 10 minutes
                "iss": self.app_id,  # Issuer = App ID
            }

            return jwt.encode(payload, self.private_key, algorithm="RS256")
        except Exception as e:
            raise GitHubAppAuthenticationError(f"Failed to generate JWT: {e}") from e

    async def get_installation_token(self) -> str:
        """Get Installation Access Token (IAT).

        IAT is valid for 1 hour and scoped to specific repositories.
        This is the token used for all GitHub API operations.

        Caching Strategy:
        - Token is cached until 5 minutes before expiration
        - Automatic refresh prevents mid-operation expiration

        Returns:
            Installation Access Token (IAT)

        Raises:
            GitHubAppAuthenticationError: If token generation fails

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

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/app/installations/{self.installation_id}/access_tokens",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()

                data = response.json()
                self._installation_token = data["token"]

                # Parse expiration (ISO 8601 format: 2026-01-12T21:45:00Z)
                expires_at_str = data["expires_at"].replace("Z", "+00:00")
                self._token_expires_at = datetime.fromisoformat(expires_at_str)

                return self._installation_token
        except httpx.HTTPStatusError as e:
            raise GitHubAppAuthenticationError(
                f"Failed to get installation token: HTTP {e.response.status_code}"
            ) from e
        except Exception as e:
            raise GitHubAppAuthenticationError(f"Failed to get installation token: {e}") from e

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError, GitHubAppRateLimitError)
        ),
        reraise=True,
    )
    async def _api_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated GitHub API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE, PUT)
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
            json_data: Request body (for POST/PATCH/PUT)
            params: Query parameters (for GET)

        Returns:
            Parsed JSON response

        Raises:
            GitHubAppRateLimitError: If rate limit exceeded
            GitHubAppNotFoundError: If resource not found
            GitHubAppError: For other API errors
        """
        token = await self.get_installation_token()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=f"{self.base_url}{endpoint}",
                    json=json_data,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    timeout=30.0,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    raise GitHubAppRateLimitError(f"Rate limit exceeded. Resets at {reset_time}")

                # Handle not found
                if response.status_code == 404:
                    raise GitHubAppNotFoundError(f"Resource not found: {endpoint}")

                response.raise_for_status()

                # Handle 204 No Content
                if response.status_code == 204:
                    return {}

                return response.json()
        except httpx.HTTPStatusError as e:
            raise GitHubAppError(f"GitHub API error: HTTP {e.response.status_code}") from e
        except httpx.TimeoutException as e:
            raise GitHubAppError(f"GitHub API timeout: {e}") from e
        except httpx.NetworkError as e:
            raise GitHubAppError(f"GitHub API network error: {e}") from e

    # ========================================================================
    # WORKFLOW OPERATIONS
    # ========================================================================

    async def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Trigger a workflow_dispatch event.

        Use Case: Agent triggers deployment workflow after successful build.

        Args:
            owner: Repository owner (e.g., "edri2or-commits")
            repo: Repository name (e.g., "project38-or")
            workflow_id: Workflow file name (e.g., "deploy-railway.yml")
            ref: Branch/tag to run on (default: "main")
            inputs: Input parameters for workflow

        Raises:
            GitHubAppError: If workflow trigger fails

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
            json_data={"ref": ref, "inputs": inputs or {}},
        )

    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
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

        Example:
            >>> runs = await client.get_workflow_runs(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     status="completed",
            ...     limit=5
            ... )
            >>> for run in runs:
            ...     print(f"{run['name']}: {run['conclusion']}")
        """
        params = {"per_page": limit}
        if workflow_id:
            params["workflow_id"] = workflow_id
        if status:
            params["status"] = status

        result = await self._api_request(
            method="GET", endpoint=f"/repos/{owner}/{repo}/actions/runs", params=params
        )
        return result.get("workflow_runs", [])

    # ========================================================================
    # ISSUE OPERATIONS
    # ========================================================================

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        r"""Create a GitHub issue.

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
                "assignees": assignees or [],
            },
        )

    async def add_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        """Add a comment to an existing issue.

        Use Case: Agent provides status updates on autonomous tasks.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            body: Comment body (Markdown supported)

        Returns:
            Created comment object

        Example:
            >>> comment = await client.add_issue_comment(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     issue_number=42,
            ...     body="Deployment successful. Issue can be closed."
            ... )
        """
        return await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json_data={"body": body},
        )

    async def close_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Close an issue (optionally with a final comment).

        Use Case: Agent closes issue after autonomous fix is deployed.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            comment: Optional final comment before closing

        Returns:
            Updated issue object

        Example:
            >>> await client.close_issue(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     issue_number=42,
            ...     comment="Fixed in PR #123"
            ... )
        """
        if comment:
            await self.add_issue_comment(owner, repo, issue_number, comment)

        return await self._api_request(
            method="PATCH",
            endpoint=f"/repos/{owner}/{repo}/issues/{issue_number}",
            json_data={"state": "closed"},
        )

    # ========================================================================
    # PULL REQUEST OPERATIONS
    # ========================================================================

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        r"""Create a pull request.

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

        Example:
            >>> pr = await client.create_pull_request(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     title="Fix deployment configuration",
            ...     body="## Changes\n\n- Updated railway.toml\n- Fixed health check",
            ...     head="fix/deployment-config",
            ...     base="main"
            ... )
            >>> print(f"PR created: {pr['html_url']}")
        """
        return await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/pulls",
            json_data={"title": title, "body": body, "head": head, "base": base},
        )

    async def merge_pull_request(
        self, owner: str, repo: str, pull_number: int, merge_method: str = "squash"
    ) -> dict[str, Any]:
        """Merge a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR number
            merge_method: "merge", "squash", or "rebase"

        Returns:
            Merge result

        Example:
            >>> result = await client.merge_pull_request(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     pull_number=123,
            ...     merge_method="squash"
            ... )
            >>> print(f"Merged: {result['merged']}")
        """
        return await self._api_request(
            method="PUT",
            endpoint=f"/repos/{owner}/{repo}/pulls/{pull_number}/merge",
            json_data={"merge_method": merge_method},
        )

    async def get_pull_request(self, owner: str, repo: str, pull_number: int) -> dict[str, Any]:
        """Get pull request details.

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR number

        Returns:
            Pull request object

        Example:
            >>> pr = await client.get_pull_request(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     pull_number=123
            ... )
            >>> print(f"PR status: {pr['state']}")
        """
        return await self._api_request(
            method="GET", endpoint=f"/repos/{owner}/{repo}/pulls/{pull_number}"
        )

    # ========================================================================
    # COMMIT & REF OPERATIONS
    # ========================================================================

    async def get_recent_commits(
        self, owner: str, repo: str, ref: str = "main", limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent commits from a branch.

        Use Case: Agent correlates Railway deployment failure with recent commits.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Branch name (default: "main")
            limit: Max results

        Returns:
            List of commit objects with sha, message, author, timestamp

        Example:
            >>> commits = await client.get_recent_commits(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     limit=5
            ... )
            >>> for commit in commits:
            ...     print(f"{commit['sha'][:7]}: {commit['commit']['message']}")
        """
        params = {"sha": ref, "per_page": limit}
        result = await self._api_request(
            method="GET", endpoint=f"/repos/{owner}/{repo}/commits", params=params
        )
        return result

    async def get_commit_details(self, owner: str, repo: str, commit_sha: str) -> dict[str, Any]:
        """Get detailed information about a specific commit.

        Use Case: Agent analyzes what changed in a failing deployment.

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Full or short SHA

        Returns:
            Commit object with files, stats, etc.

        Example:
            >>> commit = await client.get_commit_details(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     commit_sha="abc1234"
            ... )
            >>> print(f"Files changed: {len(commit['files'])}")
        """
        return await self._api_request(
            method="GET", endpoint=f"/repos/{owner}/{repo}/commits/{commit_sha}"
        )

    # ========================================================================
    # REPOSITORY OPERATIONS
    # ========================================================================

    async def get_repository_info(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository metadata.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository object with name, description, default_branch, etc.

        Example:
            >>> repo_info = await client.get_repository_info(
            ...     owner="edri2or-commits",
            ...     repo="project38-or"
            ... )
            >>> print(f"Default branch: {repo_info['default_branch']}")
        """
        return await self._api_request(method="GET", endpoint=f"/repos/{owner}/{repo}")

    async def create_repository_dispatch(
        self,
        owner: str,
        repo: str,
        event_type: str,
        client_payload: dict[str, Any] | None = None,
    ) -> None:
        """Trigger a repository_dispatch event.

        Use Case: Agent notifies external systems via webhook.

        Args:
            owner: Repository owner
            repo: Repository name
            event_type: Custom event name (e.g., "deployment-complete")
            client_payload: Custom data (max 64KB JSON)

        Example:
            >>> await client.create_repository_dispatch(
            ...     owner="edri2or-commits",
            ...     repo="project38-or",
            ...     event_type="deployment-complete",
            ...     client_payload={"environment": "production", "status": "success"}
            ... )
        """
        await self._api_request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo}/dispatches",
            json_data={"event_type": event_type, "client_payload": client_payload or {}},
        )
