"""Comprehensive tests for IntegrationAgent.

Tests cover all task handlers and edge cases:
- create_issue: Create GitHub issue
- close_issue: Close GitHub issue
- add_comment: Add comment to issue/PR
- create_pr: Create pull request
- merge_pr: Merge pull request
- trigger_workflow: Trigger GitHub Actions workflow
- check_ci_status: Check CI/CD status
- trigger_n8n: Trigger n8n workflow
- Message handlers
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.multi_agent.base import AgentDomain, AgentTask
from src.multi_agent.integration_agent import IntegrationAgent, IntegrationConfig


class TestIntegrationAgentInitialization:
    """Tests for IntegrationAgent initialization."""

    def test_default_initialization(self):
        """Test agent initializes with defaults."""
        agent = IntegrationAgent()

        assert agent.domain == AgentDomain.INTEGRATION
        assert agent.github is None
        assert agent.n8n is None
        assert agent.config.github_repo == ""
        assert agent.config.default_labels == []
        assert agent.config.default_assignees == []
        assert agent._created_issues == []
        assert agent._created_prs == []
        assert agent._triggered_workflows == []

    def test_initialization_with_config(self):
        """Test agent initializes with custom config."""
        config = IntegrationConfig(
            github_repo="owner/repo",
            n8n_base_url="https://n8n.example.com",
            default_labels=["bug", "automated"],
            default_assignees=["user1"],
        )
        agent = IntegrationAgent(config=config)

        assert agent.config.github_repo == "owner/repo"
        assert agent.config.n8n_base_url == "https://n8n.example.com"
        assert agent.config.default_labels == ["bug", "automated"]

    def test_initialization_with_clients(self):
        """Test agent initializes with clients."""
        mock_github = MagicMock()
        mock_n8n = MagicMock()

        agent = IntegrationAgent(
            github_client=mock_github,
            n8n_client=mock_n8n,
        )

        assert agent.github is mock_github
        assert agent.n8n is mock_n8n

    def test_message_handlers_registered(self):
        """Test message handlers are registered on init."""
        agent = IntegrationAgent()

        assert "deployment_failed" in agent._message_handlers
        assert "anomaly_detected" in agent._message_handlers


class TestIntegrationAgentCapabilities:
    """Tests for IntegrationAgent capabilities."""

    def test_has_eight_capabilities(self):
        """Test agent has exactly 8 capabilities."""
        agent = IntegrationAgent()
        assert len(agent.capabilities) == 8

    def test_all_capabilities_present(self):
        """Test all expected capabilities are present."""
        agent = IntegrationAgent()
        cap_names = [c.name for c in agent.capabilities]

        assert "create_issue" in cap_names
        assert "close_issue" in cap_names
        assert "add_comment" in cap_names
        assert "create_pr" in cap_names
        assert "merge_pr" in cap_names
        assert "trigger_workflow" in cap_names
        assert "check_ci_status" in cap_names
        assert "trigger_n8n" in cap_names

    def test_pr_operations_require_approval(self):
        """Test create_pr and merge_pr require approval."""
        agent = IntegrationAgent()

        create_pr_cap = agent.get_capability("create_pr")
        merge_pr_cap = agent.get_capability("merge_pr")

        assert create_pr_cap.requires_approval is True
        assert merge_pr_cap.requires_approval is True


class TestCreateIssueHandler:
    """Tests for _handle_create_issue."""

    @pytest.mark.asyncio
    async def test_create_issue_missing_title_fails(self):
        """Test create issue fails when title missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="create_issue",
            parameters={"body": "Issue body"},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "title is required" in result.error

    @pytest.mark.asyncio
    async def test_create_issue_missing_repo_fails(self):
        """Test create issue fails when repo missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="create_issue",
            parameters={"title": "Test Issue"},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "repo is required" in result.error

    @pytest.mark.asyncio
    async def test_create_issue_with_github_client(self):
        """Test create issue with GitHub client."""
        mock_github = AsyncMock()
        mock_github.create_issue.return_value = {
            "number": 42,
            "html_url": "https://github.com/owner/repo/issues/42",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="create_issue",
            parameters={
                "title": "Bug Report",
                "body": "Description",
                "labels": ["bug"],
                "assignees": ["dev1"],
            },
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["number"] == 42
        assert "42" in result.data["url"]
        mock_github.create_issue.assert_called_once_with(
            owner="owner",
            repo="repo",
            title="Bug Report",
            body="Description",
            labels=["bug"],
            assignees=["dev1"],
        )

    @pytest.mark.asyncio
    async def test_create_issue_uses_default_labels(self):
        """Test create issue uses default labels from config."""
        mock_github = AsyncMock()
        mock_github.create_issue.return_value = {"number": 1, "html_url": "url"}

        config = IntegrationConfig(
            github_repo="owner/repo",
            default_labels=["automated"],
        )
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="create_issue",
            parameters={"title": "Test"},
            domain=AgentDomain.INTEGRATION,
        )

        await agent.execute_task(task)

        call_kwargs = mock_github.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["automated"]

    @pytest.mark.asyncio
    async def test_create_issue_fallback_to_gh_cli(self):
        """Test create issue falls back to gh CLI."""
        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(config=config)  # No github_client

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="https://github.com/owner/repo/issues/1",
                returncode=0,
            )

            task = AgentTask(
                task_type="create_issue",
                parameters={"title": "Test", "body": "Body"},
                domain=AgentDomain.INTEGRATION,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["created_via"] == "gh_cli"
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_issue_tracked(self):
        """Test created issue is tracked."""
        mock_github = AsyncMock()
        mock_github.create_issue.return_value = {
            "number": 10,
            "html_url": "https://github.com/owner/repo/issues/10",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="create_issue",
            parameters={"title": "Tracked Issue"},
            domain=AgentDomain.INTEGRATION,
        )

        await agent.execute_task(task)

        assert len(agent._created_issues) == 1
        assert agent._created_issues[0]["number"] == 10


class TestCloseIssueHandler:
    """Tests for _handle_close_issue."""

    @pytest.mark.asyncio
    async def test_close_issue_missing_number_fails(self):
        """Test close issue fails when issue_number missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="close_issue",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "issue_number is required" in result.error

    @pytest.mark.asyncio
    async def test_close_issue_with_github_client(self):
        """Test close issue with GitHub client."""
        mock_github = AsyncMock()
        mock_github.close_issue.return_value = None

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="close_issue",
            parameters={"issue_number": 42, "comment": "Closing as resolved"},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["issue_number"] == 42
        assert result.data["state"] == "closed"

    @pytest.mark.asyncio
    async def test_close_issue_fallback_to_gh_cli(self):
        """Test close issue falls back to gh CLI."""
        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            task = AgentTask(
                task_type="close_issue",
                parameters={"issue_number": 42},
                domain=AgentDomain.INTEGRATION,
            )

            result = await agent.execute_task(task)

        assert result.success is True


class TestAddCommentHandler:
    """Tests for _handle_add_comment."""

    @pytest.mark.asyncio
    async def test_add_comment_missing_params_fails(self):
        """Test add comment fails when required params missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="add_comment",
            parameters={"issue_number": 42},  # Missing comment
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "issue_number and comment are required" in result.error

    @pytest.mark.asyncio
    async def test_add_comment_with_github_client(self):
        """Test add comment with GitHub client."""
        mock_github = AsyncMock()
        mock_github.add_issue_comment.return_value = {"id": 12345}

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="add_comment",
            parameters={"issue_number": 42, "comment": "This is a comment"},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["issue_number"] == 42
        assert result.data["comment_id"] == 12345


class TestCreatePRHandler:
    """Tests for _handle_create_pr."""

    @pytest.mark.asyncio
    async def test_create_pr_missing_required_params_fails(self):
        """Test create PR fails when required params missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="create_pr",
            parameters={"title": "Test PR"},  # Missing head branch
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "title and head branch are required" in result.error

    @pytest.mark.asyncio
    async def test_create_pr_with_github_client(self):
        """Test create PR with GitHub client."""
        mock_github = AsyncMock()
        mock_github.create_pull_request.return_value = {
            "number": 100,
            "html_url": "https://github.com/owner/repo/pull/100",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="create_pr",
            parameters={
                "title": "Add feature X",
                "body": "## Summary\nAdds feature X",
                "head": "feature/x",
                "base": "main",
            },
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["number"] == 100
        assert result.data["head"] == "feature/x"
        assert result.data["base"] == "main"
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_create_pr_default_base_main(self):
        """Test create PR defaults base to main."""
        mock_github = AsyncMock()
        mock_github.create_pull_request.return_value = {"number": 1, "html_url": "url"}

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="create_pr",
            parameters={"title": "PR", "head": "feature"},
            domain=AgentDomain.INTEGRATION,
        )

        await agent.execute_task(task)

        call_kwargs = mock_github.create_pull_request.call_args.kwargs
        assert call_kwargs["base"] == "main"

    @pytest.mark.asyncio
    async def test_create_pr_tracked(self):
        """Test created PR is tracked."""
        mock_github = AsyncMock()
        mock_github.create_pull_request.return_value = {
            "number": 50,
            "html_url": "https://github.com/owner/repo/pull/50",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="create_pr",
            parameters={"title": "PR", "head": "feature"},
            domain=AgentDomain.INTEGRATION,
        )

        await agent.execute_task(task)

        assert len(agent._created_prs) == 1
        assert agent._created_prs[0]["number"] == 50


class TestMergePRHandler:
    """Tests for _handle_merge_pr."""

    @pytest.mark.asyncio
    async def test_merge_pr_missing_number_fails(self):
        """Test merge PR fails when pr_number missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="merge_pr",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "pr_number is required" in result.error

    @pytest.mark.asyncio
    async def test_merge_pr_with_github_client(self):
        """Test merge PR with GitHub client."""
        mock_github = AsyncMock()
        mock_github.merge_pull_request.return_value = {"sha": "abc123"}

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="merge_pr",
            parameters={"pr_number": 100, "merge_method": "squash"},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["pr_number"] == 100
        assert result.data["merged"] is True
        assert result.data["sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_merge_pr_failure_includes_recommendations(self):
        """Test merge PR failure includes recommendations."""
        mock_github = AsyncMock()
        mock_github.merge_pull_request.side_effect = Exception("Merge conflict")

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="merge_pr",
            parameters={"pr_number": 100},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert len(result.recommendations) > 0


class TestTriggerWorkflowHandler:
    """Tests for _handle_trigger_workflow."""

    @pytest.mark.asyncio
    async def test_trigger_workflow_missing_id_fails(self):
        """Test trigger workflow fails when workflow_id missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="trigger_workflow",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "workflow_id is required" in result.error

    @pytest.mark.asyncio
    async def test_trigger_workflow_with_github_client(self):
        """Test trigger workflow with GitHub client."""
        mock_github = AsyncMock()
        mock_github.trigger_workflow.return_value = None

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="trigger_workflow",
            parameters={
                "workflow_id": "deploy.yml",
                "ref": "main",
                "inputs": {"environment": "production"},
            },
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["workflow_id"] == "deploy.yml"
        assert result.data["ref"] == "main"

    @pytest.mark.asyncio
    async def test_trigger_workflow_tracked(self):
        """Test triggered workflow is tracked."""
        mock_github = AsyncMock()

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="trigger_workflow",
            parameters={"workflow_id": "test.yml"},
            domain=AgentDomain.INTEGRATION,
        )

        await agent.execute_task(task)

        assert len(agent._triggered_workflows) == 1
        assert agent._triggered_workflows[0]["workflow_id"] == "test.yml"


class TestCheckCIStatusHandler:
    """Tests for _handle_check_ci_status."""

    @pytest.mark.asyncio
    async def test_check_ci_status_missing_params_fails(self):
        """Test check CI status fails when neither pr_number nor commit_sha provided."""
        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(config=config)

        task = AgentTask(
            task_type="check_ci_status",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "pr_number or commit_sha is required" in result.error

    @pytest.mark.asyncio
    async def test_check_ci_status_for_pr(self):
        """Test check CI status for PR."""
        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps([
                    {"name": "test", "status": "completed", "conclusion": "success"},
                    {"name": "lint", "status": "completed", "conclusion": "success"},
                ]),
                returncode=0,
            )

            task = AgentTask(
                task_type="check_ci_status",
                parameters={"pr_number": 100},
                domain=AgentDomain.INTEGRATION,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["overall_status"] == "success"
        assert result.data["all_passed"] is True
        assert result.data["has_pending"] is False

    @pytest.mark.asyncio
    async def test_check_ci_status_pending(self):
        """Test check CI status with pending checks."""
        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps([
                    {"name": "test", "status": "in_progress", "conclusion": None},
                    {"name": "lint", "status": "completed", "conclusion": "success"},
                ]),
                returncode=0,
            )

            task = AgentTask(
                task_type="check_ci_status",
                parameters={"pr_number": 100},
                domain=AgentDomain.INTEGRATION,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["overall_status"] == "pending"
        assert result.data["has_pending"] is True


class TestTriggerN8nHandler:
    """Tests for _handle_trigger_n8n."""

    @pytest.mark.asyncio
    async def test_trigger_n8n_missing_workflow_id_fails(self):
        """Test trigger n8n fails when workflow_id missing."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="trigger_n8n",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "workflow_id is required" in result.error

    @pytest.mark.asyncio
    async def test_trigger_n8n_with_client(self):
        """Test trigger n8n with n8n client."""
        mock_n8n = AsyncMock()
        mock_n8n.execute_workflow.return_value = "exec-12345"

        agent = IntegrationAgent(n8n_client=mock_n8n)

        task = AgentTask(
            task_type="trigger_n8n",
            parameters={"workflow_id": "alert-workflow", "data": {"alert": "test"}},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["execution_id"] == "exec-12345"
        assert result.data["workflow_id"] == "alert-workflow"

    @pytest.mark.asyncio
    async def test_trigger_n8n_via_webhook(self):
        """Test trigger n8n via direct webhook."""
        config = IntegrationConfig(n8n_base_url="https://n8n.example.com")
        agent = IntegrationAgent(config=config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            task = AgentTask(
                task_type="trigger_n8n",
                parameters={"workflow_id": "deploy-webhook", "data": {"env": "prod"}},
                domain=AgentDomain.INTEGRATION,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["workflow_id"] == "deploy-webhook"


class TestMessageHandlers:
    """Tests for message handlers."""

    @pytest.mark.asyncio
    async def test_handle_deployment_failure(self):
        """Test deployment failure creates issue."""
        mock_github = AsyncMock()
        mock_github.create_issue.return_value = {
            "number": 999,
            "html_url": "https://github.com/owner/repo/issues/999",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        response = await agent._handle_deployment_failure({
            "deployment_id": "deploy-fail-abc",
            "error": "Health check failed after deploy",
        })

        assert "number" in response
        mock_github.create_issue.assert_called_once()
        # Verify issue title contains deployment info
        call_args = mock_github.create_issue.call_args
        assert "deploy-fail-abc" in call_args.kwargs["title"]

    @pytest.mark.asyncio
    async def test_handle_anomaly_event_critical(self):
        """Test critical anomaly creates issue."""
        mock_github = AsyncMock()
        mock_github.create_issue.return_value = {
            "number": 888,
            "html_url": "url",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        response = await agent._handle_anomaly_event({
            "metric": "error_rate",
            "severity": "CRITICAL",
            "value": 0.5,
        })

        assert response["action"] == "issue_created"
        mock_github.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_anomaly_event_warning(self):
        """Test warning anomaly is only logged."""
        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(config=config)

        response = await agent._handle_anomaly_event({
            "metric": "latency",
            "severity": "WARNING",
        })

        assert response["action"] == "logged"


class TestGetCreatedResources:
    """Tests for get_created_resources."""

    def test_get_created_resources(self):
        """Test get_created_resources returns all tracked resources."""
        agent = IntegrationAgent()
        agent._created_issues.append({"number": 1})
        agent._created_prs.append({"number": 10})
        agent._triggered_workflows.append({"workflow_id": "test"})

        resources = agent.get_created_resources()

        assert resources["issues"] == [{"number": 1}]
        assert resources["pull_requests"] == [{"number": 10}]
        assert resources["workflows"] == [{"workflow_id": "test"}]

    def test_get_created_resources_returns_copy(self):
        """Test get_created_resources returns copies."""
        agent = IntegrationAgent()
        agent._created_issues.append({"number": 1})

        resources = agent.get_created_resources()
        resources["issues"].append({"number": 2})

        assert len(agent._created_issues) == 1


class TestUnknownTaskType:
    """Tests for unknown task types."""

    @pytest.mark.asyncio
    async def test_unknown_task_type_fails(self):
        """Test unknown task type returns error."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="unknown_task",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "cannot handle task type" in result.error.lower()
