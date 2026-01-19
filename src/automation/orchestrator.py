"""
Automation Orchestrator - Multi-path execution engine.

Implements ADR-008: Robust Automation Strategy Beyond GitHub API.

This module tries multiple execution paths in order of speed and reliability,
only falling back to slower/less reliable paths when faster ones fail.

Path Order:
1. Direct Python - Execute locally if possible (<1s)
2. Cloud Run - Call GCP MCP Server directly (<10s)
3. n8n Webhook - Trigger n8n workflow (<5s)
4. GitHub API - Traditional dispatch (30-60s)
5. Manual - Create issue for human (last resort)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)


class ExecutionPath(Enum):
    """Available execution paths."""

    DIRECT_PYTHON = "direct_python"
    CLOUD_RUN = "cloud_run"
    N8N_WEBHOOK = "n8n_webhook"
    GITHUB_API = "github_api"
    MANUAL = "manual"


@dataclass
class AutomationResult:
    """Result of an automation execution."""

    success: bool
    path: ExecutionPath | None = None
    data: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "path": self.path.value if self.path else None,
            "data": self.data,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class PathConfig:
    """Configuration for an execution path."""

    enabled: bool = True
    timeout_seconds: float = 30
    max_retries: int = 1


class AutomationOrchestrator:
    """
    Multi-path automation orchestrator.

    Tries execution paths in order of speed and reliability.
    Does not depend on any single external API.

    Example:
        orchestrator = AutomationOrchestrator()
        result = await orchestrator.execute("test-gcp-tools", {"verbose": True})

        if result.success:
            print(f"Completed via {result.path.value} in {result.duration_ms}ms")
    """

    def __init__(
        self,
        cloud_run_url: str | None = None,
        cloud_run_token: str | None = None,
        n8n_url: str | None = None,
        github_token: str | None = None,
        github_repo: str = "edri2or-commits/project38-or",
    ):
        """
        Initialize the orchestrator.

        Args:
            cloud_run_url: GCP MCP Server URL (default: from env)
            cloud_run_token: Bearer token for Cloud Run (default: from env)
            n8n_url: n8n webhook base URL (default: from env)
            github_token: GitHub token (default: from env)
            github_repo: GitHub repository (owner/repo)
        """
        self.cloud_run_url = cloud_run_url or os.environ.get(
            "GCP_MCP_URL", "https://gcp-mcp-gateway-3e7yyrd7xq-uc.a.run.app"
        )
        self.cloud_run_token = cloud_run_token or os.environ.get("GCP_MCP_TOKEN")
        self.n8n_url = n8n_url or os.environ.get(
            "N8N_WEBHOOK_URL", "https://n8n-production-2fe0.up.railway.app/webhook"
        )
        self.github_token = github_token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self.github_repo = github_repo

        # Path configurations
        self.path_configs: dict[ExecutionPath, PathConfig] = {
            ExecutionPath.DIRECT_PYTHON: PathConfig(timeout_seconds=5),
            ExecutionPath.CLOUD_RUN: PathConfig(timeout_seconds=30),
            ExecutionPath.N8N_WEBHOOK: PathConfig(timeout_seconds=15),
            ExecutionPath.GITHUB_API: PathConfig(timeout_seconds=60),
            ExecutionPath.MANUAL: PathConfig(timeout_seconds=10),
        }

        # Action handlers for direct Python execution
        self._direct_handlers: dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default direct Python handlers."""
        # These will be populated when specific modules are available
        pass

    def register_handler(self, action: str, handler: Callable) -> None:
        """
        Register a direct Python handler for an action.

        Args:
            action: Action name (e.g., "test-gcp-tools")
            handler: Async function to execute
        """
        self._direct_handlers[action] = handler

    async def execute(
        self,
        action: str,
        params: dict | None = None,
        paths: list[ExecutionPath] | None = None,
    ) -> AutomationResult:
        """
        Execute an automation action using multi-path strategy.

        Args:
            action: Action to execute (e.g., "test-gcp-tools", "deploy")
            params: Parameters for the action
            paths: Specific paths to try (default: all in order)

        Returns:
            AutomationResult with success status and details
        """
        params = params or {}
        paths = paths or [
            ExecutionPath.DIRECT_PYTHON,
            ExecutionPath.CLOUD_RUN,
            ExecutionPath.N8N_WEBHOOK,
            ExecutionPath.GITHUB_API,
            ExecutionPath.MANUAL,
        ]

        errors: list[str] = []
        start_time = datetime.utcnow()

        for path in paths:
            config = self.path_configs.get(path, PathConfig())
            if not config.enabled:
                continue

            logger.info(f"Trying path: {path.value} for action: {action}")

            try:
                result = await self._execute_path(path, action, params, config)
                if result.success:
                    result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    logger.info(f"Success via {path.value} in {result.duration_ms:.0f}ms")
                    return result
                else:
                    errors.extend(result.errors)
            except Exception as e:
                error_msg = f"{path.value}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Path {path.value} failed: {e}")

        # All paths failed
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        return AutomationResult(
            success=False,
            path=None,
            errors=errors,
            duration_ms=duration_ms,
        )

    async def _execute_path(
        self,
        path: ExecutionPath,
        action: str,
        params: dict,
        config: PathConfig,
    ) -> AutomationResult:
        """Execute a specific path."""
        handlers = {
            ExecutionPath.DIRECT_PYTHON: self._try_direct_python,
            ExecutionPath.CLOUD_RUN: self._try_cloud_run,
            ExecutionPath.N8N_WEBHOOK: self._try_n8n_webhook,
            ExecutionPath.GITHUB_API: self._try_github_api,
            ExecutionPath.MANUAL: self._try_manual,
        }

        handler = handlers.get(path)
        if not handler:
            return AutomationResult(success=False, errors=[f"Unknown path: {path}"])

        try:
            return await asyncio.wait_for(
                handler(action, params),
                timeout=config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            return AutomationResult(
                success=False,
                path=path,
                errors=[f"Timeout after {config.timeout_seconds}s"],
            )

    async def _try_direct_python(self, action: str, params: dict) -> AutomationResult:
        """
        Path 1: Direct Python execution.

        Fastest path - executes code locally without network calls.
        """
        handler = self._direct_handlers.get(action)
        if not handler:
            return AutomationResult(
                success=False,
                path=ExecutionPath.DIRECT_PYTHON,
                errors=[f"No direct handler for action: {action}"],
            )

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**params)
            else:
                result = handler(**params)

            return AutomationResult(
                success=True,
                path=ExecutionPath.DIRECT_PYTHON,
                data=result if isinstance(result, dict) else {"result": result},
            )
        except Exception as e:
            return AutomationResult(
                success=False,
                path=ExecutionPath.DIRECT_PYTHON,
                errors=[str(e)],
            )

    async def _try_cloud_run(self, action: str, params: dict) -> AutomationResult:
        """
        Path 2: Cloud Run direct call.

        Calls GCP MCP Server directly via HTTP.
        """
        if not self.cloud_run_url:
            return AutomationResult(
                success=False,
                path=ExecutionPath.CLOUD_RUN,
                errors=["Cloud Run URL not configured"],
            )

        headers = {"Content-Type": "application/json"}
        if self.cloud_run_token:
            headers["Authorization"] = f"Bearer {self.cloud_run_token}"

        # Map actions to MCP tool calls
        action_mapping = {
            "test-gcp-tools": {"method": "tools/list", "params": {}},
            "list-secrets": {"method": "tools/call", "params": {"name": "secret_list", "arguments": {}}},
            "gcloud-version": {"method": "tools/call", "params": {"name": "gcloud_version", "arguments": {}}},
        }

        mcp_request = action_mapping.get(action, {"method": action, "params": params})

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": mcp_request["method"],
            "params": mcp_request["params"],
        }

        try:
            # Try multiple endpoints (FastMCP can mount at different paths)
            endpoints = ["/mcp", "/", "/sse"]

            for endpoint in endpoints:
                url = f"{self.cloud_run_url.rstrip('/')}{endpoint}"
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=25,
                )

                if response.status_code == 200:
                    try:
                        data = response.json()
                        return AutomationResult(
                            success=True,
                            path=ExecutionPath.CLOUD_RUN,
                            data={"endpoint": endpoint, "response": data},
                        )
                    except Exception:
                        continue

            return AutomationResult(
                success=False,
                path=ExecutionPath.CLOUD_RUN,
                errors=["No endpoint responded successfully"],
            )

        except requests.Timeout:
            return AutomationResult(
                success=False,
                path=ExecutionPath.CLOUD_RUN,
                errors=["Request timed out"],
            )
        except Exception as e:
            return AutomationResult(
                success=False,
                path=ExecutionPath.CLOUD_RUN,
                errors=[str(e)],
            )

    async def _try_n8n_webhook(self, action: str, params: dict) -> AutomationResult:
        """
        Path 3: n8n webhook.

        Triggers n8n workflow via webhook.
        """
        if not self.n8n_url:
            return AutomationResult(
                success=False,
                path=ExecutionPath.N8N_WEBHOOK,
                errors=["n8n URL not configured"],
            )

        # Construct webhook URL for the action
        webhook_url = f"{self.n8n_url.rstrip('/')}/{action}"

        try:
            response = requests.post(
                webhook_url,
                json={"action": action, "params": params},
                timeout=10,
            )

            if response.status_code in (200, 201, 202):
                return AutomationResult(
                    success=True,
                    path=ExecutionPath.N8N_WEBHOOK,
                    data={"status_code": response.status_code, "response": response.text[:500]},
                )

            return AutomationResult(
                success=False,
                path=ExecutionPath.N8N_WEBHOOK,
                errors=[f"HTTP {response.status_code}: {response.text[:200]}"],
            )

        except Exception as e:
            return AutomationResult(
                success=False,
                path=ExecutionPath.N8N_WEBHOOK,
                errors=[str(e)],
            )

    async def _try_github_api(self, action: str, params: dict) -> AutomationResult:
        """
        Path 4: GitHub API.

        Triggers GitHub Actions workflow. Known to be unreliable (ADR-008).
        """
        if not self.github_token:
            return AutomationResult(
                success=False,
                path=ExecutionPath.GITHUB_API,
                errors=["GitHub token not configured"],
            )

        # Map actions to workflow files
        workflow_mapping = {
            "test-gcp-tools": "gcp-mcp-phase3-setup.yml",
            "deploy": "deploy-railway.yml",
            "health-check": "production-health-check.yml",
        }

        workflow = workflow_mapping.get(action)
        if not workflow:
            return AutomationResult(
                success=False,
                path=ExecutionPath.GITHUB_API,
                errors=[f"No workflow mapping for action: {action}"],
            )

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            response = requests.post(
                f"https://api.github.com/repos/{self.github_repo}/actions/workflows/{workflow}/dispatches",
                headers=headers,
                json={"ref": "main", "inputs": params},
                timeout=30,
            )

            if response.status_code == 204:
                return AutomationResult(
                    success=True,
                    path=ExecutionPath.GITHUB_API,
                    data={"workflow": workflow, "note": "No run ID returned (GitHub API limitation)"},
                )

            return AutomationResult(
                success=False,
                path=ExecutionPath.GITHUB_API,
                errors=[f"HTTP {response.status_code}: {response.text[:200]}"],
            )

        except Exception as e:
            return AutomationResult(
                success=False,
                path=ExecutionPath.GITHUB_API,
                errors=[str(e)],
            )

    async def _try_manual(self, action: str, params: dict) -> AutomationResult:
        """
        Path 5: Manual (Last Resort).

        Creates a GitHub issue with instructions for manual execution.
        """
        if not self.github_token:
            return AutomationResult(
                success=False,
                path=ExecutionPath.MANUAL,
                errors=["GitHub token not configured for issue creation"],
            )

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        issue_body = f"""## Manual Automation Required

All automated paths failed for action: `{action}`

### Parameters
```json
{params}
```

### Manual Steps

1. Go to Actions tab
2. Find the appropriate workflow
3. Click "Run workflow"
4. Enter the parameters above

### Why This Happened

The automation orchestrator tried all available paths:
1. Direct Python - Not available for this action
2. Cloud Run - Connection failed or timed out
3. n8n Webhook - Not configured or failed
4. GitHub API - Known reliability issues (see ADR-008)

This issue was created as a last resort.
"""

        try:
            response = requests.post(
                f"https://api.github.com/repos/{self.github_repo}/issues",
                headers=headers,
                json={
                    "title": f"[Manual Required] Automation: {action}",
                    "body": issue_body,
                    "labels": ["automation", "manual-required"],
                },
                timeout=10,
            )

            if response.status_code == 201:
                issue = response.json()
                return AutomationResult(
                    success=True,  # Issue creation succeeded
                    path=ExecutionPath.MANUAL,
                    data={"issue_number": issue["number"], "issue_url": issue["html_url"]},
                )

            return AutomationResult(
                success=False,
                path=ExecutionPath.MANUAL,
                errors=[f"Failed to create issue: {response.status_code}"],
            )

        except Exception as e:
            return AutomationResult(
                success=False,
                path=ExecutionPath.MANUAL,
                errors=[str(e)],
            )


# Convenience function for simple usage
async def run_automation(action: str, params: dict | None = None) -> AutomationResult:
    """
    Run an automation action using the multi-path strategy.

    Args:
        action: Action to execute
        params: Parameters for the action

    Returns:
        AutomationResult
    """
    orchestrator = AutomationOrchestrator()
    return await orchestrator.execute(action, params)
