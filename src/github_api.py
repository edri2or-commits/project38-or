"""
GitHub API Utility Module.

Provides GitHub API access using Python requests library.
This module works in ALL Claude Code environments including Anthropic cloud
where gh CLI is not available and curl fails due to proxy interference.

The requests library handles the Anthropic proxy correctly, making this
the recommended approach for all GitHub API operations.

Usage:
    from src.github_api import GitHubAPI

    api = GitHubAPI()  # Uses GH_TOKEN from environment

    # Get workflow runs
    runs = api.get_workflow_runs(limit=5)

    # Trigger a workflow
    api.trigger_workflow('setup-cloudrun-permissions.yml', {'action': 'full-setup'})

    # Get workflow run status
    status = api.get_run_status(run_id)

Why this exists:
    - gh CLI is not installed in Anthropic cloud environments
    - curl with Authorization header fails due to proxy interference
    - Python requests library works correctly with the proxy
    - This provides a permanent, environment-agnostic solution

Source: CLAUDE.md Proxy Constraints section
"""

import os
import time
from typing import Any

import requests


class GitHubAPI:
    """
    GitHub API client using requests library.

    Works in all Claude Code environments including those with proxy restrictions.
    """

    def __init__(
        self,
        token: str | None = None,
        repo: str = "edri2or-commits/project38-or"
    ):
        """
        Initialize GitHub API client.

        Args:
            token: GitHub token. If not provided, uses GH_TOKEN or GITHUB_TOKEN env var.
            repo: Repository in format "owner/repo".
        """
        self.token = token or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not self.token:
            raise ValueError("No GitHub token found. Set GH_TOKEN or GITHUB_TOKEN environment variable.")

        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        timeout: int = 30
    ) -> requests.Response:
        """
        Make an API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base_url)
            params: Query parameters
            json_data: JSON body data
            timeout: Request timeout in seconds

        Returns:
            Response object
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        return requests.request(
            method=method,
            url=url,
            headers=self.headers,
            params=params,
            json=json_data,
            timeout=timeout
        )

    def get_workflow_runs(
        self,
        workflow_file: str | None = None,
        status: str | None = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get recent workflow runs.

        Args:
            workflow_file: Filter by workflow file name (e.g., 'test.yml')
            status: Filter by status ('queued', 'in_progress', 'completed')
            limit: Maximum number of runs to return

        Returns:
            List of workflow run objects
        """
        params = {'per_page': limit}
        if status:
            params['status'] = status

        if workflow_file:
            endpoint = f"actions/workflows/{workflow_file}/runs"
        else:
            endpoint = "actions/runs"

        response = self._request('GET', endpoint, params=params)
        response.raise_for_status()
        return response.json().get('workflow_runs', [])

    def get_run_status(self, run_id: int) -> dict[str, Any]:
        """
        Get status of a specific workflow run.

        Args:
            run_id: The workflow run ID

        Returns:
            Dictionary with run details including status and conclusion
        """
        response = self._request('GET', f"actions/runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        return {
            'id': run['id'],
            'name': run['name'],
            'status': run['status'],
            'conclusion': run.get('conclusion'),
            'html_url': run['html_url'],
            'created_at': run['created_at'],
            'updated_at': run['updated_at']
        }

    def get_run_jobs(self, run_id: int) -> list[dict[str, Any]]:
        """
        Get jobs for a workflow run.

        Args:
            run_id: The workflow run ID

        Returns:
            List of job objects with steps
        """
        response = self._request('GET', f"actions/runs/{run_id}/jobs")
        response.raise_for_status()
        jobs = response.json().get('jobs', [])

        result = []
        for job in jobs:
            job_info = {
                'id': job['id'],
                'name': job['name'],
                'status': job['status'],
                'conclusion': job.get('conclusion'),
                'steps': []
            }
            for step in job.get('steps', []):
                job_info['steps'].append({
                    'name': step['name'],
                    'status': step['status'],
                    'conclusion': step.get('conclusion')
                })
            result.append(job_info)
        return result

    def trigger_workflow(
        self,
        workflow_file: str,
        inputs: dict | None = None,
        ref: str = "main"
    ) -> bool:
        """
        Trigger a workflow dispatch event.

        Args:
            workflow_file: Workflow file name (e.g., 'deploy.yml')
            inputs: Input parameters for the workflow
            ref: Git ref to run the workflow on

        Returns:
            True if workflow was triggered successfully
        """
        data = {'ref': ref}
        if inputs:
            data['inputs'] = inputs

        response = self._request(
            'POST',
            f"actions/workflows/{workflow_file}/dispatches",
            json_data=data
        )
        # 204 No Content means success
        return response.status_code == 204

    def wait_for_workflow(
        self,
        workflow_file: str,
        timeout: int = 300,
        poll_interval: int = 10
    ) -> dict[str, Any] | None:
        """
        Wait for a workflow to complete after triggering.

        Args:
            workflow_file: Workflow file name
            timeout: Maximum wait time in seconds
            poll_interval: Time between status checks

        Returns:
            Final run status dict, or None if timeout
        """
        start_time = time.time()

        # Wait a moment for the run to be created
        time.sleep(3)

        while time.time() - start_time < timeout:
            runs = self.get_workflow_runs(workflow_file=workflow_file, limit=1)
            if runs:
                run = runs[0]
                if run['status'] == 'completed':
                    return self.get_run_status(run['id'])
            time.sleep(poll_interval)

        return None

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Create a GitHub issue.

        Args:
            title: Issue title
            body: Issue body (markdown)
            labels: List of label names

        Returns:
            Created issue data
        """
        data = {'title': title, 'body': body}
        if labels:
            data['labels'] = labels

        response = self._request('POST', 'issues', json_data=data)
        response.raise_for_status()
        return response.json()

    def add_issue_comment(self, issue_number: int, body: str) -> dict[str, Any]:
        """
        Add a comment to an issue.

        Args:
            issue_number: Issue number
            body: Comment body (markdown)

        Returns:
            Created comment data
        """
        response = self._request(
            'POST',
            f'issues/{issue_number}/comments',
            json_data={'body': body}
        )
        response.raise_for_status()
        return response.json()


def get_api() -> GitHubAPI:
    """
    Get a configured GitHubAPI instance.

    Convenience function for quick access.

    Returns:
        GitHubAPI instance
    """
    return GitHubAPI()


# CLI interface for direct execution
if __name__ == "__main__":
    import sys

    try:
        api = GitHubAPI()
        print("✅ GitHub API initialized successfully")

        if len(sys.argv) > 1:
            command = sys.argv[1]

            if command == "runs":
                runs = api.get_workflow_runs(limit=5)
                for run in runs:
                    status_icon = "✅" if run.get('conclusion') == 'success' else "❌" if run.get('conclusion') == 'failure' else "🔄"
                    print(f"{status_icon} {run['name']}: {run['status']} ({run.get('conclusion', 'running')})")

            elif command == "trigger" and len(sys.argv) > 2:
                workflow = sys.argv[2]
                inputs = {}
                for arg in sys.argv[3:]:
                    if '=' in arg:
                        key, value = arg.split('=', 1)
                        inputs[key] = value

                if api.trigger_workflow(workflow, inputs):
                    print(f"✅ Triggered {workflow}")
                else:
                    print(f"❌ Failed to trigger {workflow}")

            else:
                print("Usage: python github_api.py [runs|trigger <workflow.yml> [key=value ...]]")
        else:
            # Default: show recent runs
            runs = api.get_workflow_runs(limit=3)
            print(f"Recent workflow runs:")
            for run in runs:
                print(f"  - {run['name']}: {run.get('conclusion', run['status'])}")

    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {e}")
        sys.exit(1)
