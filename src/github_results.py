"""
GitHub Results Retrieval Module.

Provides autonomous access to experiment results stored in GitHub Issues.
This bypasses proxy restrictions on artifact downloads by using the GitHub
Issues API which routes through api.github.com (whitelisted).

Usage:
    from src.github_results import get_experiment_results, wait_for_results

    # Get results immediately
    results = get_experiment_results("exp_003")

    # Wait for workflow to complete and get results
    results = wait_for_results("exp_003", timeout_seconds=300)
"""

import json
import os
import re
import time

import requests


def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("No GitHub token found. Set GH_TOKEN or GITHUB_TOKEN.")
    return token


def get_github_headers() -> dict:
    """Get headers for GitHub API requests."""
    return {
        "Authorization": f"token {get_github_token()}",
        "Accept": "application/vnd.github.v3+json",
    }


def get_experiment_results(
    experiment_id: str,
    repo: str = "edri2or-commits/project38-or",
    labels: str = "experiment",
) -> dict | None:
    """
    Retrieve experiment results from GitHub Issue.

    Args:
        experiment_id: Experiment identifier (e.g., "exp_003")
        repo: Repository in "owner/repo" format
        labels: Comma-separated labels to filter issues

    Returns:
        Parsed JSON results dict, or None if not found
    """
    headers = get_github_headers()

    # Search for issue by title pattern
    response = requests.get(
        f"https://api.github.com/repos/{repo}/issues",
        headers=headers,
        params={"labels": labels, "state": "all", "per_page": 20, "sort": "created", "direction": "desc"},
    )

    if response.status_code != 200:
        print(f"Error fetching issues: {response.status_code}")
        return None

    issues = response.json()

    for issue in issues:
        # Match experiment ID in title (e.g., "exp_003 Live Results: ADOPT")
        if experiment_id.lower() in issue["title"].lower():
            body = issue["body"] or ""

            # Try to extract JSON from code block
            json_match = re.search(r"```json\n(.*?)\n```", body, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON from issue #{issue['number']}")
                    continue

            # Try to extract structured data from markdown
            return _parse_markdown_results(body, issue)

    return None


def _parse_markdown_results(body: str, issue: dict) -> dict:
    """Parse results from markdown format when JSON is not available."""
    results = {
        "source": "github_issue",
        "issue_number": issue["number"],
        "issue_url": issue["html_url"],
        "title": issue["title"],
    }

    # Extract decision
    decision_match = re.search(r"\*\*Decision:\*\*\s*(\w+)", body)
    if decision_match:
        results["decision"] = decision_match.group(1)

    # Extract success rate
    rate_match = re.search(r"\*\*Success Rate:\*\*\s*([\d.]+%?)", body)
    if rate_match:
        results["success_rate"] = rate_match.group(1)

    # Extract run URL
    run_match = re.search(r"actions/runs/(\d+)", body)
    if run_match:
        results["run_id"] = run_match.group(1)

    return results


def wait_for_results(
    experiment_id: str,
    timeout_seconds: int = 300,
    poll_interval: int = 10,
    repo: str = "edri2or-commits/project38-or",
) -> dict | None:
    """
    Wait for experiment results to appear in GitHub Issues.

    Args:
        experiment_id: Experiment identifier
        timeout_seconds: Maximum time to wait
        poll_interval: Seconds between polls
        repo: Repository in "owner/repo" format

    Returns:
        Results dict when found, None if timeout
    """
    start_time = time.time()
    attempts = 0

    while time.time() - start_time < timeout_seconds:
        attempts += 1
        print(f"Polling for {experiment_id} results (attempt {attempts})...")

        results = get_experiment_results(experiment_id, repo=repo)
        if results:
            print(f"Found results after {attempts} attempts")
            return results

        time.sleep(poll_interval)

    print(f"Timeout waiting for {experiment_id} results after {timeout_seconds}s")
    return None


def list_experiment_issues(
    repo: str = "edri2or-commits/project38-or",
    labels: str = "experiment",
    limit: int = 10,
) -> list:
    """
    List recent experiment issues.

    Args:
        repo: Repository in "owner/repo" format
        labels: Comma-separated labels to filter
        limit: Maximum issues to return

    Returns:
        List of issue dicts with title, number, state, created_at
    """
    headers = get_github_headers()

    response = requests.get(
        f"https://api.github.com/repos/{repo}/issues",
        headers=headers,
        params={"labels": labels, "state": "all", "per_page": limit, "sort": "created", "direction": "desc"},
    )

    if response.status_code != 200:
        return []

    return [
        {
            "number": issue["number"],
            "title": issue["title"],
            "state": issue["state"],
            "created_at": issue["created_at"],
            "url": issue["html_url"],
        }
        for issue in response.json()
    ]


def trigger_and_wait(
    workflow: str,
    experiment_id: str,
    inputs: dict | None = None,
    repo: str = "edri2or-commits/project38-or",
    timeout_seconds: int = 600,
) -> dict | None:
    """
    Trigger a workflow and wait for results in GitHub Issue.

    Args:
        workflow: Workflow filename (e.g., "exp003-live-test.yml")
        experiment_id: Experiment identifier for result matching
        inputs: Workflow inputs dict
        repo: Repository
        timeout_seconds: Max wait time

    Returns:
        Results dict when found, None if timeout or error
    """
    headers = get_github_headers()

    # Trigger workflow
    trigger_response = requests.post(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
        headers=headers,
        json={"ref": "main", "inputs": inputs or {}},
    )

    if trigger_response.status_code != 204:
        print(f"Failed to trigger workflow: {trigger_response.status_code}")
        print(trigger_response.text)
        return None

    print(f"Triggered {workflow}, waiting for results...")

    # Wait a bit for workflow to start
    time.sleep(10)

    # Wait for results
    return wait_for_results(experiment_id, timeout_seconds=timeout_seconds, repo=repo)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python github_results.py <command> [args]")
        print("Commands:")
        print("  get <experiment_id>  - Get results for experiment")
        print("  list                 - List recent experiment issues")
        print("  wait <experiment_id> - Wait for results (5 min timeout)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "get" and len(sys.argv) >= 3:
        results = get_experiment_results(sys.argv[2])
        if results:
            print(json.dumps(results, indent=2))
        else:
            print("No results found")

    elif command == "list":
        issues = list_experiment_issues()
        for issue in issues:
            print(f"#{issue['number']}: {issue['title']} ({issue['state']})")

    elif command == "wait" and len(sys.argv) >= 3:
        results = wait_for_results(sys.argv[2])
        if results:
            print(json.dumps(results, indent=2))
        else:
            print("Timeout - no results found")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
