#!/usr/bin/env python3
"""
Create GitHub Issue with experiment results.

Usage:
    python3 scripts/create_experiment_issue.py results.json

Environment variables:
    GITHUB_REPOSITORY - Repository name (e.g., owner/repo)
    GITHUB_RUN_ID - Workflow run ID
    GH_TOKEN - GitHub token for gh CLI
"""

import json
import os
import subprocess
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: create_experiment_issue.py <results.json>")
        sys.exit(1)

    results_file = sys.argv[1]

    if not os.path.exists(results_file):
        print(f"Error: {results_file} not found")
        sys.exit(1)

    with open(results_file) as f:
        data = json.load(f)

    decision = data.get("decision", "UNKNOWN")
    metrics = data.get("metrics", {})
    success_rate = int(metrics.get("success_rate", 0) * 100)
    total_cost = metrics.get("total_cost_usd", 0)
    avg_latency = int(metrics.get("avg_latency_ms", 0))

    repo = os.environ.get("GITHUB_REPOSITORY", "edri2or-commits/project38-or")
    run_id = os.environ.get("GITHUB_RUN_ID", "0")

    body = f"""## exp_003 Live Test Results

**Decision:** {decision}
**Success Rate:** {success_rate}%
**Total Cost:** ${total_cost}
**Avg Latency:** {avg_latency}ms
**Run:** https://github.com/{repo}/actions/runs/{run_id}

### Retrieval Methods (Proxy-Safe)

**1. GHCR (Recommended):**
```bash
oras pull ghcr.io/{repo}/exp003-results:run-{run_id}
```

**2. Git-Bridge:**
```bash
git fetch origin artifacts/exp003-run-{run_id}
git show FETCH_HEAD:results.json
```

**3. Issue API (this issue):**
Extract JSON from code block below.

### Raw Results (JSON)

<!-- MACHINE_READABLE_START -->
```json
{json.dumps(data, indent=2)}
```
<!-- MACHINE_READABLE_END -->
"""

    title = f"exp_003 Results [Run {run_id}]: {decision} ({success_rate}% success)"

    # Write to temp files
    with open("/tmp/issue_body.md", "w") as f:
        f.write(body)

    # Create issue using gh CLI
    result = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--title",
            title,
            "--body-file",
            "/tmp/issue_body.md",
            "--label",
            "experiment,automated",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"Issue created: {result.stdout.strip()}")
    else:
        print(f"Failed to create issue: {result.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    main()
