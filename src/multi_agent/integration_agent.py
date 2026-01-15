"""IntegrationAgent - Specialized Agent for GitHub and n8n Operations.

Handles all integration operations:
- Create and manage GitHub issues
- Create and merge pull requests
- Trigger and monitor n8n workflows
- Coordinate multi-system automations

Integrates with:
- GitHubAppClient for GitHub API operations
- N8nClient for workflow orchestration
- Other agents for cross-domain coordination

Example:
    >>> from src.multi_agent.integration_agent import IntegrationAgent
    >>> from src.github_app_client import GitHubAppClient
    >>> from src.n8n_client import N8nClient
    >>>
    >>> agent = IntegrationAgent(
    ...     github_client=GitHubAppClient(...),
    ...     n8n_client=N8nClient(...),
    ... )
    >>> result = await agent.execute_task(AgentTask(
    ...     task_type="create_issue",
    ...     parameters={"title": "Bug Report", "body": "..."}
    ... ))
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.multi_agent.base import (
    AgentCapability,
    AgentDomain,
    AgentResult,
    AgentTask,
    SpecializedAgent,
)

if TYPE_CHECKING:
    from src.github_app_client import GitHubAppClient
    from src.n8n_client import N8nClient


@dataclass
class IntegrationConfig:
    """Configuration for integration operations.

    Attributes:
        github_repo: Default GitHub repository (owner/repo)
        n8n_base_url: n8n instance URL
        default_labels: Default labels for issues
        default_assignees: Default assignees for issues
    """

    github_repo: str = ""
    n8n_base_url: str = ""
    default_labels: list[str] | None = None
    default_assignees: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        if self.default_labels is None:
            self.default_labels = []
        if self.default_assignees is None:
            self.default_assignees = []


class IntegrationAgent(SpecializedAgent):
    """Specialized agent for GitHub and n8n integration operations.

    Capabilities:
    - create_issue: Create GitHub issue
    - close_issue: Close GitHub issue
    - create_pr: Create pull request
    - merge_pr: Merge pull request
    - trigger_workflow: Trigger GitHub Actions or n8n workflow
    - check_ci_status: Check CI/CD status

    Attributes:
        github: GitHubAppClient for GitHub operations
        n8n: N8nClient for workflow operations
        config: Integration configuration
    """

    def __init__(
        self,
        github_client: "GitHubAppClient | None" = None,
        n8n_client: "N8nClient | None" = None,
        config: IntegrationConfig | None = None,
        agent_id: str | None = None,
    ):
        """Initialize IntegrationAgent.

        Args:
            github_client: GitHubAppClient for GitHub API operations
            n8n_client: N8nClient for workflow operations
            config: Integration configuration
            agent_id: Unique agent identifier
        """
        super().__init__(agent_id=agent_id, domain=AgentDomain.INTEGRATION)
        self.github = github_client
        self.n8n = n8n_client
        self.config = config or IntegrationConfig()
        self.logger = logging.getLogger(f"agent.integration.{self.agent_id}")

        # Track created resources
        self._created_issues: list[dict[str, Any]] = []
        self._created_prs: list[dict[str, Any]] = []
        self._triggered_workflows: list[dict[str, Any]] = []

        # Register message handlers
        self.register_message_handler("deployment_failed", self._handle_deployment_failure)
        self.register_message_handler("anomaly_detected", self._handle_anomaly_event)

    @property
    def capabilities(self) -> list[AgentCapability]:
        """List of integration capabilities."""
        return [
            AgentCapability(
                name="create_issue",
                domain=AgentDomain.INTEGRATION,
                description="Create GitHub issue",
                requires_approval=False,
                max_concurrent=5,
                cooldown_seconds=5,
            ),
            AgentCapability(
                name="close_issue",
                domain=AgentDomain.INTEGRATION,
                description="Close GitHub issue",
                requires_approval=False,
                max_concurrent=5,
                cooldown_seconds=0,
            ),
            AgentCapability(
                name="add_comment",
                domain=AgentDomain.INTEGRATION,
                description="Add comment to GitHub issue/PR",
                requires_approval=False,
                max_concurrent=10,
                cooldown_seconds=0,
            ),
            AgentCapability(
                name="create_pr",
                domain=AgentDomain.INTEGRATION,
                description="Create pull request",
                requires_approval=True,  # PRs can affect code
                max_concurrent=2,
                cooldown_seconds=30,
            ),
            AgentCapability(
                name="merge_pr",
                domain=AgentDomain.INTEGRATION,
                description="Merge pull request",
                requires_approval=True,  # Merging affects main branch
                max_concurrent=1,
                cooldown_seconds=60,
            ),
            AgentCapability(
                name="trigger_workflow",
                domain=AgentDomain.INTEGRATION,
                description="Trigger GitHub Actions or n8n workflow",
                requires_approval=False,
                max_concurrent=3,
                cooldown_seconds=10,
            ),
            AgentCapability(
                name="check_ci_status",
                domain=AgentDomain.INTEGRATION,
                description="Check CI/CD status",
                requires_approval=False,
                max_concurrent=5,
                cooldown_seconds=0,
            ),
            AgentCapability(
                name="trigger_n8n",
                domain=AgentDomain.INTEGRATION,
                description="Trigger n8n workflow via webhook",
                requires_approval=False,
                max_concurrent=5,
                cooldown_seconds=5,
            ),
        ]

    async def _execute_task_internal(self, task: AgentTask) -> AgentResult:
        """Execute integration task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with execution outcome
        """
        task_handlers = {
            "create_issue": self._handle_create_issue,
            "close_issue": self._handle_close_issue,
            "add_comment": self._handle_add_comment,
            "create_pr": self._handle_create_pr,
            "merge_pr": self._handle_merge_pr,
            "trigger_workflow": self._handle_trigger_workflow,
            "check_ci_status": self._handle_check_ci_status,
            "trigger_n8n": self._handle_trigger_n8n,
        }

        handler = task_handlers.get(task.task_type)
        if not handler:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"Unknown task type: {task.task_type}",
            )

        return await handler(task)

    async def _handle_create_issue(self, task: AgentTask) -> AgentResult:
        """Create GitHub issue.

        Args:
            task: Task with parameters:
                - title: Issue title
                - body: Issue body
                - labels: List of labels
                - assignees: List of assignees
                - repo: Repository (owner/repo)

        Returns:
            AgentResult with issue info
        """
        title = task.parameters.get("title")
        body = task.parameters.get("body", "")
        labels = task.parameters.get("labels", self.config.default_labels)
        assignees = task.parameters.get("assignees", self.config.default_assignees)
        repo = task.parameters.get("repo", self.config.github_repo)

        if not title:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="title is required",
            )

        if not repo:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="repo is required (format: owner/repo)",
            )

        try:
            if self.github:
                owner, repo_name = repo.split("/")
                issue = await self.github.create_issue(
                    owner=owner,
                    repo=repo_name,
                    title=title,
                    body=body,
                    labels=labels,
                    assignees=assignees,
                )

                issue_data = {
                    "number": issue.get("number"),
                    "url": issue.get("html_url"),
                    "created_at": datetime.now(UTC).isoformat(),
                    "title": title,
                }
                self._created_issues.append(issue_data)

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data=issue_data,
                )
            else:
                # Fallback to gh CLI
                import subprocess

                cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
                for label in labels or []:
                    cmd.extend(["--label", label])
                for assignee in assignees or []:
                    cmd.extend(["--assignee", assignee])

                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                url = result.stdout.strip()

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"url": url, "created_via": "gh_cli"},
                )

        except Exception as e:
            self.logger.error(f"Failed to create issue: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_close_issue(self, task: AgentTask) -> AgentResult:
        """Close GitHub issue.

        Args:
            task: Task with parameters:
                - issue_number: Issue number to close
                - comment: Optional closing comment
                - repo: Repository (owner/repo)

        Returns:
            AgentResult with close status
        """
        issue_number = task.parameters.get("issue_number")
        comment = task.parameters.get("comment")
        repo = task.parameters.get("repo", self.config.github_repo)

        if not issue_number:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="issue_number is required",
            )

        try:
            if self.github:
                owner, repo_name = repo.split("/")
                await self.github.close_issue(
                    owner=owner,
                    repo=repo_name,
                    issue_number=issue_number,
                    comment=comment,
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"issue_number": issue_number, "state": "closed"},
                )
            else:
                import subprocess

                if comment:
                    cmd = [
                        "gh", "issue", "comment", str(issue_number),
                        "--repo", repo, "--body", comment,
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)
                subprocess.run(
                    ["gh", "issue", "close", str(issue_number), "--repo", repo],
                    capture_output=True,
                    check=True,
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"issue_number": issue_number, "state": "closed"},
                )

        except Exception as e:
            self.logger.error(f"Failed to close issue: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_add_comment(self, task: AgentTask) -> AgentResult:
        """Add comment to GitHub issue/PR.

        Args:
            task: Task with parameters:
                - issue_number: Issue or PR number
                - comment: Comment text
                - repo: Repository (owner/repo)

        Returns:
            AgentResult with comment status
        """
        issue_number = task.parameters.get("issue_number")
        comment = task.parameters.get("comment")
        repo = task.parameters.get("repo", self.config.github_repo)

        if not issue_number or not comment:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="issue_number and comment are required",
            )

        try:
            if self.github:
                owner, repo_name = repo.split("/")
                result = await self.github.add_issue_comment(
                    owner=owner,
                    repo=repo_name,
                    issue_number=issue_number,
                    body=comment,
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"issue_number": issue_number, "comment_id": result.get("id")},
                )
            else:
                import subprocess

                cmd = [
                    "gh", "issue", "comment", str(issue_number),
                    "--repo", repo, "--body", comment,
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"issue_number": issue_number},
                )

        except Exception as e:
            self.logger.error(f"Failed to add comment: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_create_pr(self, task: AgentTask) -> AgentResult:
        """Create pull request.

        Args:
            task: Task with parameters:
                - title: PR title
                - body: PR body
                - head: Source branch
                - base: Target branch (default: main)
                - repo: Repository (owner/repo)

        Returns:
            AgentResult with PR info
        """
        title = task.parameters.get("title")
        body = task.parameters.get("body", "")
        head = task.parameters.get("head")
        base = task.parameters.get("base", "main")
        repo = task.parameters.get("repo", self.config.github_repo)

        if not title or not head:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="title and head branch are required",
            )

        try:
            if self.github:
                owner, repo_name = repo.split("/")
                pr = await self.github.create_pull_request(
                    owner=owner,
                    repo=repo_name,
                    title=title,
                    body=body,
                    head=head,
                    base=base,
                )

                pr_data = {
                    "number": pr.get("number"),
                    "url": pr.get("html_url"),
                    "created_at": datetime.now(UTC).isoformat(),
                    "head": head,
                    "base": base,
                }
                self._created_prs.append(pr_data)

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data=pr_data,
                    recommendations=[
                        "Wait for CI checks to complete before merging",
                        "Review changes before approving merge",
                    ],
                )
            else:
                import subprocess

                cmd = [
                    "gh", "pr", "create",
                    "--repo", repo,
                    "--title", title,
                    "--body", body,
                    "--head", head,
                    "--base", base,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                url = result.stdout.strip()
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"url": url, "head": head, "base": base},
                )

        except Exception as e:
            self.logger.error(f"Failed to create PR: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_merge_pr(self, task: AgentTask) -> AgentResult:
        """Merge pull request.

        Args:
            task: Task with parameters:
                - pr_number: PR number to merge
                - merge_method: squash, merge, or rebase
                - delete_branch: Whether to delete branch after merge
                - repo: Repository (owner/repo)

        Returns:
            AgentResult with merge status
        """
        pr_number = task.parameters.get("pr_number")
        merge_method = task.parameters.get("merge_method", "squash")
        delete_branch = task.parameters.get("delete_branch", True)
        repo = task.parameters.get("repo", self.config.github_repo)

        if not pr_number:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="pr_number is required",
            )

        try:
            if self.github:
                owner, repo_name = repo.split("/")
                result = await self.github.merge_pull_request(
                    owner=owner,
                    repo=repo_name,
                    pull_number=pr_number,
                    merge_method=merge_method,
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={
                        "pr_number": pr_number,
                        "merged": True,
                        "sha": result.get("sha"),
                    },
                )
            else:
                import subprocess

                cmd = ["gh", "pr", "merge", str(pr_number), "--repo", repo, f"--{merge_method}"]
                if delete_branch:
                    cmd.append("--delete-branch")
                subprocess.run(cmd, capture_output=True, check=True)
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"pr_number": pr_number, "merged": True},
                )

        except Exception as e:
            self.logger.error(f"Failed to merge PR: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                recommendations=[
                    "Check if PR has merge conflicts",
                    "Verify CI checks have passed",
                    "Ensure you have merge permissions",
                ],
            )

    async def _handle_trigger_workflow(self, task: AgentTask) -> AgentResult:
        """Trigger GitHub Actions workflow.

        Args:
            task: Task with parameters:
                - workflow_id: Workflow file name or ID
                - ref: Branch or tag reference
                - inputs: Workflow inputs
                - repo: Repository (owner/repo)

        Returns:
            AgentResult with workflow status
        """
        workflow_id = task.parameters.get("workflow_id")
        ref = task.parameters.get("ref", "main")
        inputs = task.parameters.get("inputs", {})
        repo = task.parameters.get("repo", self.config.github_repo)

        if not workflow_id:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="workflow_id is required",
            )

        try:
            if self.github:
                owner, repo_name = repo.split("/")
                await self.github.trigger_workflow(
                    owner=owner,
                    repo=repo_name,
                    workflow_id=workflow_id,
                    ref=ref,
                    inputs=inputs,
                )

                workflow_data = {
                    "workflow_id": workflow_id,
                    "ref": ref,
                    "triggered_at": datetime.now(UTC).isoformat(),
                }
                self._triggered_workflows.append(workflow_data)

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data=workflow_data,
                )
            else:
                import subprocess

                cmd = ["gh", "workflow", "run", workflow_id, "--repo", repo, "--ref", ref]
                for key, value in inputs.items():
                    cmd.extend(["--field", f"{key}={value}"])
                subprocess.run(cmd, capture_output=True, check=True)
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"workflow_id": workflow_id, "ref": ref},
                )

        except Exception as e:
            self.logger.error(f"Failed to trigger workflow: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_check_ci_status(self, task: AgentTask) -> AgentResult:
        """Check CI/CD status for a PR or commit.

        Args:
            task: Task with parameters:
                - pr_number: PR number to check
                - commit_sha: Or commit SHA to check
                - repo: Repository (owner/repo)

        Returns:
            AgentResult with CI status
        """
        pr_number = task.parameters.get("pr_number")
        commit_sha = task.parameters.get("commit_sha")
        repo = task.parameters.get("repo", self.config.github_repo)

        if not pr_number and not commit_sha:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="Either pr_number or commit_sha is required",
            )

        try:
            import subprocess

            if pr_number:
                cmd = [
                    "gh", "pr", "checks", str(pr_number),
                    "--repo", repo, "--json", "name,status,conclusion",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            else:
                api_path = f"/repos/{repo}/commits/{commit_sha}/check-runs"
                cmd = ["gh", "api", api_path, "--jq", ".check_runs"]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            import json

            checks = json.loads(result.stdout)

            passed = all(c.get("conclusion") == "success" for c in checks if c.get("conclusion"))
            pending = any(c.get("status") == "in_progress" for c in checks)

            overall_status = "pending" if pending else ("success" if passed else "failure")

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "overall_status": overall_status,
                    "checks": checks,
                    "all_passed": passed,
                    "has_pending": pending,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to check CI status: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_trigger_n8n(self, task: AgentTask) -> AgentResult:
        """Trigger n8n workflow.

        Args:
            task: Task with parameters:
                - workflow_id: n8n workflow ID
                - data: Data to pass to workflow

        Returns:
            AgentResult with execution info
        """
        workflow_id = task.parameters.get("workflow_id")
        data = task.parameters.get("data", {})

        if not workflow_id:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="workflow_id is required",
            )

        try:
            if self.n8n:
                execution_id = await self.n8n.execute_workflow(
                    workflow_id=workflow_id,
                    data=data,
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={
                        "execution_id": execution_id,
                        "workflow_id": workflow_id,
                    },
                )
            else:
                # Direct webhook call
                import httpx

                webhook_url = f"{self.config.n8n_base_url}/webhook/{workflow_id}"
                async with httpx.AsyncClient() as client:
                    response = await client.post(webhook_url, json=data, timeout=30)
                    return AgentResult(
                        task_id=task.task_id,
                        success=response.status_code < 400,
                        data={
                            "status_code": response.status_code,
                            "workflow_id": workflow_id,
                        },
                    )

        except Exception as e:
            self.logger.error(f"Failed to trigger n8n workflow: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_deployment_failure(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle deployment failure notification from DeployAgent.

        Creates a GitHub issue for tracking.

        Args:
            payload: Failure details

        Returns:
            Created issue info
        """
        deployment_id = payload.get("deployment_id", "unknown")
        error = payload.get("error", "Unknown error")

        task = AgentTask(
            task_type="create_issue",
            parameters={
                "title": f"🚨 Deployment Failure: {deployment_id}",
                "body": f"""## Deployment Failure Report

**Deployment ID:** `{deployment_id}`
**Time:** {datetime.now(UTC).isoformat()}

### Error Details
```
{error}
```

### Recommended Actions
1. Check Railway deployment logs
2. Verify recent code changes
3. Consider rollback if issue persists

---
*This issue was automatically created by IntegrationAgent*
""",
                "labels": ["production", "deployment-failure", "automated"],
            },
        )

        result = await self._handle_create_issue(task)
        return result.data

    async def _handle_anomaly_event(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle anomaly detection notification from MonitoringAgent.

        Triggers n8n workflow for alerting.

        Args:
            payload: Anomaly details

        Returns:
            Action taken
        """
        metric = payload.get("metric", "unknown")
        severity = payload.get("severity", "INFO")

        if severity in ("CRITICAL", "EMERGENCY"):
            # Create issue for critical anomalies
            task = AgentTask(
                task_type="create_issue",
                parameters={
                    "title": f"⚠️ {severity}: Anomaly in {metric}",
                    "body": f"""## Anomaly Detection Report

**Metric:** `{metric}`
**Severity:** {severity}
**Time:** {datetime.now(UTC).isoformat()}

### Details
```json
{payload}
```

---
*This issue was automatically created by IntegrationAgent*
""",
                    "labels": ["anomaly", severity.lower(), "automated"],
                },
            )
            result = await self._handle_create_issue(task)
            return {"action": "issue_created", "data": result.data}

        return {"action": "logged", "severity": severity}

    def get_created_resources(self) -> dict[str, Any]:
        """Get resources created by this agent.

        Returns:
            Dictionary of created issues, PRs, workflows
        """
        return {
            "issues": self._created_issues.copy(),
            "pull_requests": self._created_prs.copy(),
            "workflows": self._triggered_workflows.copy(),
        }
