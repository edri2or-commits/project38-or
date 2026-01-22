# GitHub Actions Autonomous Results Retrieval

**Date:** 2026-01-22
**Status:** Spike → Implementation
**Author:** Claude Code Agent

## Problem Statement

When running experiments via GitHub Actions from Claude Code sessions:
1. **Proxy blocks artifact downloads** - Azure Blob Storage returns 403
2. **Proxy blocks Playwright installs** - cdn.playwright.dev blocked
3. **Job Summary API doesn't exist** - No official REST/GraphQL endpoint
4. **`summary_raw` deprecated** - Undocumented endpoint removed by GitHub

**Impact:** Cannot autonomously retrieve CI results, breaking the autonomous loop.

## Research Findings

### What Doesn't Work

| Approach | Issue | Source |
|----------|-------|--------|
| Download artifacts | Proxy blocks `productionresultssa2.blob.core.windows.net` | Tested 2026-01-22 |
| Job Summary API | Doesn't exist - [Community Discussion #27649](https://github.com/orgs/community/discussions/27649) | GitHub Docs |
| `summary_raw` endpoint | Deprecated/removed - [Discussion #123637](https://github.com/orgs/community/discussions/123637) | GitHub Community |
| Direct log download | Proxy blocks Azure Blob Storage | Tested 2026-01-22 |

### What Works

| Approach | Reliability | API Accessible | Proxy Safe |
|----------|-------------|----------------|------------|
| **Issue Comments** | ✅ High | ✅ Yes | ✅ Yes |
| **Gists** | ✅ High | ✅ Yes | ✅ Yes |
| **Webhook to MCP Gateway** | ✅ High | ✅ Yes | ✅ Yes |
| **Repository Dispatch** | ⚠️ Medium | ✅ Yes | ✅ Yes |

## Recommended Solution: Issue Comments

### Why Issue Comments?

1. **API Accessible** - `GET /repos/{owner}/{repo}/issues/{issue_number}/comments`
2. **Proxy Safe** - Goes through `api.github.com` (whitelisted)
3. **Searchable** - Can find by labels, title patterns
4. **Persistent** - Won't expire like artifacts
5. **Simple** - Uses `gh issue create` in workflow

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflow                   │
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌──────────────────────┐   │
│  │ Run     │ →  │ Generate│ →  │ Create Issue with    │   │
│  │ Tests   │    │ Results │    │ Results (JSON + MD)  │   │
│  └─────────┘    └─────────┘    └──────────────────────┘   │
│                                          │                  │
└──────────────────────────────────────────│──────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code Session                       │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Poll for Issue  │ →  │ Parse Results   │                │
│  │ by Label/Title  │    │ from Issue Body │                │
│  └─────────────────┘    └─────────────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

#### Workflow Side (write results to issue)

```yaml
- name: Create issue with results
  if: always()
  env:
    GH_TOKEN: ${{ github.token }}
  run: |
    if [ -f results.json ]; then
      # Extract key metrics
      DECISION=$(python3 -c "import json; print(json.load(open('results.json')).get('decision', 'UNKNOWN'))")

      # Create issue with full JSON in code block
      cat << 'EOF' > issue_body.md
    ## Experiment Results

    **Decision:** $DECISION
    **Run:** ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

    ### Raw Results
    ```json
    $(cat results.json)
    ```
    EOF

      gh issue create \
        --title "exp_NNN Results: $DECISION" \
        --body-file issue_body.md \
        --label "experiment,automated"
    fi
```

#### Claude Code Side (read results from issue)

```python
import os
import json
import re
import requests

def get_experiment_results(experiment_id: str) -> dict:
    """Retrieve experiment results from GitHub Issue."""
    token = os.environ.get('GH_TOKEN')
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # Search for issue by title pattern
    response = requests.get(
        'https://api.github.com/repos/edri2or-commits/project38-or/issues',
        headers=headers,
        params={
            'labels': 'experiment,automated',
            'state': 'open',
            'per_page': 10
        }
    )

    for issue in response.json():
        if experiment_id in issue['title']:
            # Extract JSON from code block
            body = issue['body']
            json_match = re.search(r'```json\n(.*?)\n```', body, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

    return None
```

## Alternative Solutions

### 1. Webhook to MCP Gateway

Send results directly to our MCP Gateway which stores them in memory/DB.

```yaml
- name: Send results to MCP Gateway
  run: |
    curl -X POST https://or-infra.com/mcp/experiment-results \
      -H "Authorization: Bearer ${{ secrets.MCP_GATEWAY_TOKEN }}" \
      -H "Content-Type: application/json" \
      -d @results.json
```

**Pros:** Real-time, no polling needed
**Cons:** Requires MCP Gateway endpoint, token management

### 2. Gists

Create a gist with results, retrieve via Gist API.

```yaml
- name: Create gist with results
  env:
    GH_TOKEN: ${{ secrets.GIST_TOKEN }}
  run: |
    gh gist create results.json --desc "exp_003 results $(date)"
```

**Pros:** Simple, fast
**Cons:** Requires separate PAT with gist scope

### 3. Repository Dispatch

Trigger a repository_dispatch event with results payload.

**Pros:** Can trigger follow-up workflows
**Cons:** Payload size limited, complex setup

## Decision

**Recommended:** Issue Comments approach

**Reasoning:**
1. Works with existing `github.token` (no extra secrets)
2. Simple to implement and debug
3. Results are human-readable in GitHub UI
4. API is stable and well-documented
5. Proxy-safe (uses api.github.com)

## Implementation Checklist

- [ ] Update workflow to create issue with JSON results
- [ ] Add `experiment` and `automated` labels to repo
- [ ] Create `src/github_results.py` module for reading results
- [ ] Test end-to-end: trigger → run → create issue → read results
- [ ] Document in CLAUDE.md

## Sources

- [GitHub Community Discussion #27649 - API to read job summary](https://github.com/orgs/community/discussions/27649)
- [GitHub Blog - Supercharging GitHub Actions with Job Summaries](https://github.blog/news-insights/product-news/supercharging-github-actions-with-job-summaries/)
- [Create or Update Comment Action](https://github.com/marketplace/actions/create-or-update-comment)
- [GitHub REST API - Issues](https://docs.github.com/en/rest/issues/issues)
- [Simon Willison's TIL - GitHub Actions job summaries](https://til.simonwillison.net/github-actions/job-summaries)
