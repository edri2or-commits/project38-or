# GitHub App Client API Reference

Complete API reference for `GitHubAppClient` - autonomous GitHub operations with JWT-based authentication.

---

## Overview

The `GitHubAppClient` provides a production-ready interface to GitHub's API using GitHub App authentication. It implements:

- **JWT-based authentication** with automatic token refresh
- **Exponential backoff retry logic** for resilience
- **Comprehensive API operations** (workflows, issues, PRs, commits)
- **Rate limit handling** with automatic retries
- **Type-safe async operations** with full error handling

---

## Installation

The client is included in the `src/github_app_client.py` module. Dependencies:

```bash
pip install httpx jwt tenacity
```

---

## Quick Start

### Basic Usage

```python
from src.secrets_manager import SecretManager
from src.github_app_client import GitHubAppClient

# Initialize from GCP Secret Manager
manager = SecretManager()
private_key = manager.get_secret("github-app-private-key")

client = GitHubAppClient(
    app_id="2497877",
    private_key=private_key,
    installation_id="100231961"
)

# Trigger a deployment workflow
await client.trigger_workflow(
    owner="edri2or-commits",
    repo="project38-or",
    workflow_id="deploy-railway.yml",
    inputs={"environment": "production"}
)

# Create an issue for deployment failure
issue = await client.create_issue(
    owner="edri2or-commits",
    repo="project38-or",
    title="Deployment Failed",
    body="## Error Details\n\nSee logs for details.",
    labels=["bug", "deployment"]
)
print(f"Issue created: {issue['html_url']}")
```

---

## API Reference

### Initialization

#### `GitHubAppClient.__init__()`

Initialize the GitHub App client.

**Parameters:**
- `app_id` (str): GitHub App ID (e.g., "2497877")
- `private_key` (str): PEM-formatted RSA private key (from GCP Secret Manager)
- `installation_id` (str): Installation ID for the repository (e.g., "100231961")
- `base_url` (str, optional): GitHub API base URL (default: "https://api.github.com")

**Example:**
```python
client = GitHubAppClient(
    app_id="2497877",
    private_key=private_key,
    installation_id="100231961"
)
```

---

### Authentication Methods

#### `generate_jwt() -> str`

Generate a JWT for GitHub App authentication.

**Returns:** Signed JWT string (valid for 10 minutes)

**Raises:** `GitHubAppAuthenticationError` if JWT generation fails

**Security Notes:**
- Clock drift tolerance: issued 60s in the past
- Short expiration: 10 minutes
- RS256 algorithm

**Example:**
```python
jwt_token = client.generate_jwt()
# Use jwt_token to request Installation Access Token
```

---

#### `get_installation_token() -> str` (async)

Get Installation Access Token (IAT) with automatic caching and refresh.

**Returns:** Installation Access Token (valid for 1 hour)

**Raises:** `GitHubAppAuthenticationError` if token generation fails

**Caching Strategy:**
- Token is cached until 5 minutes before expiration
- Automatic refresh prevents mid-operation expiration

**Example:**
```python
token = await client.get_installation_token()
# Token auto-refreshes on next call after 55 minutes
```

---

### Workflow Operations

#### `trigger_workflow()` (async)

Trigger a `workflow_dispatch` event.

**Parameters:**
- `owner` (str): Repository owner (e.g., "edri2or-commits")
- `repo` (str): Repository name (e.g., "project38-or")
- `workflow_id` (str): Workflow file name (e.g., "deploy-railway.yml")
- `ref` (str, optional): Branch/tag to run on (default: "main")
- `inputs` (Dict[str, Any], optional): Input parameters for workflow

**Returns:** None (triggers workflow asynchronously)

**Raises:** `GitHubAppError` if workflow trigger fails

**Example:**
```python
await client.trigger_workflow(
    owner="edri2or-commits",
    repo="project38-or",
    workflow_id="deploy-railway.yml",
    ref="main",
    inputs={"environment": "production", "version": "1.2.3"}
)
```

---

#### `get_workflow_runs()` (async)

Get recent workflow runs with optional filtering.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `workflow_id` (str, optional): Filter by workflow file name
- `status` (str, optional): Filter by status ("completed", "in_progress", "queued")
- `limit` (int, optional): Max results (default: 10)

**Returns:** List of workflow run objects

**Example:**
```python
runs = await client.get_workflow_runs(
    owner="edri2or-commits",
    repo="project38-or",
    workflow_id="test.yml",
    status="completed",
    limit=5
)

for run in runs:
    print(f"{run['name']}: {run['conclusion']}")
```

---

### Issue Operations

#### `create_issue()` (async)

Create a GitHub issue.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `title` (str): Issue title
- `body` (str): Issue body (Markdown supported)
- `labels` (List[str], optional): Labels to apply
- `assignees` (List[str], optional): GitHub usernames to assign

**Returns:** Created issue object with `number`, `html_url`, etc.

**Example:**
```python
issue = await client.create_issue(
    owner="edri2or-commits",
    repo="project38-or",
    title="Deployment Failed: Syntax Error",
    body="""
## Error Details

```
SyntaxError: invalid syntax in main.py line 42
```

## Context
- Commit: abc1234
- Branch: main
- Environment: production
    """,
    labels=["bug", "deployment", "high-priority"],
    assignees=["edri2or-commits"]
)

print(f"Issue #{issue['number']} created: {issue['html_url']}")
```

---

#### `add_issue_comment()` (async)

Add a comment to an existing issue.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `issue_number` (int): Issue number
- `body` (str): Comment body (Markdown supported)

**Returns:** Created comment object

**Example:**
```python
comment = await client.add_issue_comment(
    owner="edri2or-commits",
    repo="project38-or",
    issue_number=42,
    body="Deployment retried and succeeded. Closing issue."
)
```

---

#### `close_issue()` (async)

Close an issue, optionally with a final comment.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `issue_number` (int): Issue number
- `comment` (str, optional): Final comment before closing

**Returns:** Updated issue object

**Example:**
```python
await client.close_issue(
    owner="edri2or-commits",
    repo="project38-or",
    issue_number=42,
    comment="Fixed in PR #123. Deployed to production."
)
```

---

### Pull Request Operations

#### `create_pull_request()` (async)

Create a pull request.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `title` (str): PR title
- `body` (str): PR description (Markdown supported)
- `head` (str): Branch with changes (e.g., "feature/autonomous-fix")
- `base` (str, optional): Target branch (default: "main")

**Returns:** Created PR object with `number`, `html_url`, etc.

**Example:**
```python
pr = await client.create_pull_request(
    owner="edri2or-commits",
    repo="project38-or",
    title="Fix deployment configuration",
    body="""
## Summary
- Updated railway.toml healthcheck path
- Fixed CORS configuration in main.py

## Test Plan
- [x] Local testing completed
- [x] CI passing
- [ ] Deploy to staging
    """,
    head="fix/deployment-config",
    base="main"
)

print(f"PR #{pr['number']} created: {pr['html_url']}")
```

---

#### `merge_pull_request()` (async)

Merge a pull request.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `pull_number` (int): PR number
- `merge_method` (str, optional): "merge", "squash", or "rebase" (default: "squash")

**Returns:** Merge result object

**Example:**
```python
result = await client.merge_pull_request(
    owner="edri2or-commits",
    repo="project38-or",
    pull_number=123,
    merge_method="squash"
)

if result['merged']:
    print(f"Merged commit: {result['sha']}")
```

---

#### `get_pull_request()` (async)

Get pull request details.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `pull_number` (int): PR number

**Returns:** Pull request object

**Example:**
```python
pr = await client.get_pull_request(
    owner="edri2or-commits",
    repo="project38-or",
    pull_number=123
)

print(f"PR status: {pr['state']}")
print(f"Mergeable: {pr['mergeable']}")
print(f"Checks: {pr['mergeable_state']}")
```

---

### Commit Operations

#### `get_recent_commits()` (async)

Get recent commits from a branch.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `ref` (str, optional): Branch name (default: "main")
- `limit` (int, optional): Max results (default: 10)

**Returns:** List of commit objects

**Example:**
```python
commits = await client.get_recent_commits(
    owner="edri2or-commits",
    repo="project38-or",
    ref="main",
    limit=5
)

for commit in commits:
    sha = commit['sha'][:7]
    message = commit['commit']['message'].split('\n')[0]
    author = commit['commit']['author']['name']
    print(f"{sha}: {message} ({author})")
```

---

#### `get_commit_details()` (async)

Get detailed information about a specific commit.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `commit_sha` (str): Full or short SHA

**Returns:** Commit object with files, stats, etc.

**Example:**
```python
commit = await client.get_commit_details(
    owner="edri2or-commits",
    repo="project38-or",
    commit_sha="abc1234"
)

print(f"Files changed: {len(commit['files'])}")
print(f"Additions: +{commit['stats']['additions']}")
print(f"Deletions: -{commit['stats']['deletions']}")

for file in commit['files']:
    print(f"  {file['filename']}: +{file['additions']} -{file['deletions']}")
```

---

### Repository Operations

#### `get_repository_info()` (async)

Get repository metadata.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name

**Returns:** Repository object with name, description, default_branch, etc.

**Example:**
```python
repo = await client.get_repository_info(
    owner="edri2or-commits",
    repo="project38-or"
)

print(f"Repository: {repo['full_name']}")
print(f"Default branch: {repo['default_branch']}")
print(f"Description: {repo['description']}")
print(f"Private: {repo['private']}")
```

---

#### `create_repository_dispatch()` (async)

Trigger a `repository_dispatch` event.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `event_type` (str): Custom event name (e.g., "deployment-complete")
- `client_payload` (Dict[str, Any], optional): Custom data (max 64KB JSON)

**Returns:** None (triggers event asynchronously)

**Example:**
```python
await client.create_repository_dispatch(
    owner="edri2or-commits",
    repo="project38-or",
    event_type="deployment-complete",
    client_payload={
        "environment": "production",
        "version": "1.2.3",
        "status": "success",
        "url": "https://or-infra.com"
    }
)
```

---

## Exception Handling

### Exception Hierarchy

```
GitHubAppError (base)
├── GitHubAppAuthenticationError (JWT/IAT failures)
├── GitHubAppRateLimitError (429 rate limit exceeded)
└── GitHubAppNotFoundError (404 resource not found)
```

### Handling Exceptions

```python
from src.github_app_client import (
    GitHubAppError,
    GitHubAppAuthenticationError,
    GitHubAppRateLimitError,
    GitHubAppNotFoundError
)

try:
    await client.trigger_workflow(
        owner="edri2or-commits",
        repo="project38-or",
        workflow_id="deploy.yml"
    )
except GitHubAppAuthenticationError as e:
    print(f"Authentication failed: {e}")
    # Verify app_id, private_key, installation_id
except GitHubAppRateLimitError as e:
    print(f"Rate limit exceeded: {e}")
    # Wait until X-RateLimit-Reset timestamp
except GitHubAppNotFoundError as e:
    print(f"Resource not found: {e}")
    # Check repository/workflow exists
except GitHubAppError as e:
    print(f"GitHub API error: {e}")
    # General error handling
```

---

## Advanced Usage

### Retry Logic

The client includes automatic exponential backoff retry for transient failures:

- **Initial delay**: 2 seconds
- **Max delay**: 60 seconds
- **Max attempts**: 5
- **Retries on**: Timeout, network errors, rate limits

```python
# Automatic retries - no configuration needed
await client.trigger_workflow(...)  # Retries up to 5 times on failure
```

### Token Caching

Installation Access Tokens are cached automatically and refreshed 5 minutes before expiration:

```python
# First call: generates new token
token1 = await client.get_installation_token()

# Subsequent calls within 55 minutes: uses cached token
token2 = await client.get_installation_token()

assert token1 == token2  # Same token
```

### Parallel Operations

The client is async-safe and supports concurrent operations:

```python
import asyncio

# Trigger multiple workflows in parallel
await asyncio.gather(
    client.trigger_workflow(owner="...", repo="...", workflow_id="test.yml"),
    client.trigger_workflow(owner="...", repo="...", workflow_id="lint.yml"),
    client.trigger_workflow(owner="...", repo="...", workflow_id="docs.yml")
)
```

---

## Production Configuration

### GitHub App Setup

1. **Create GitHub App** at https://github.com/settings/apps:
   - App name: `claude-autonomous-agent`
   - Webhook: Inactive (API-only)

2. **Configure Permissions**:
   - Repository permissions:
     - Contents: Read and write
     - Pull requests: Read and write
     - Issues: Read and write
     - Workflows: Read and write
     - Metadata: Read (automatic)

3. **Install App** on repository:
   - https://github.com/settings/installations
   - Select `edri2or-commits/project38-or`
   - Note the installation ID

4. **Store Secrets in GCP**:
   ```bash
   # Private key
   gcloud secrets create github-app-private-key \
     --data-file=github-app.pem \
     --replication-policy=automatic

   # App ID (optional, can be hardcoded)
   gcloud secrets create github-app-id \
     --data-file=- <<< "2497877"
   ```

### Rate Limits

GitHub App installations have:
- **5,000 requests/hour** per installation
- **12,500 requests/hour** for search endpoints
- **Total: 17,500 requests/hour**

Monitor rate limits:
```python
# Check headers in _api_request (for debugging)
# X-RateLimit-Limit: 5000
# X-RateLimit-Remaining: 4999
# X-RateLimit-Reset: 1234567890
```

---

## Testing

### Unit Tests

```bash
# Run GitHub App Client tests
pytest tests/test_github_app_client.py -v

# Run with coverage
pytest tests/test_github_app_client.py --cov=src/github_app_client --cov-report=html
```

### Integration Tests

```python
# Test with real GitHub API (requires valid credentials)
import asyncio
from src.secrets_manager import SecretManager
from src.github_app_client import GitHubAppClient

async def test_integration():
    manager = SecretManager()
    private_key = manager.get_secret("github-app-private-key")

    client = GitHubAppClient(
        app_id="2497877",
        private_key=private_key,
        installation_id="100231961"
    )

    # Test workflow runs
    runs = await client.get_workflow_runs(
        owner="edri2or-commits",
        repo="project38-or",
        limit=1
    )
    print(f"Found {len(runs)} workflow runs")

asyncio.run(test_integration())
```

---

## Security Considerations

### Private Key Security

- ✅ **DO**: Store private key in GCP Secret Manager
- ✅ **DO**: Use WIF authentication for GitHub Actions
- ✅ **DO**: Rotate private key quarterly
- ❌ **DON'T**: Commit private key to code
- ❌ **DON'T**: Log or print private key
- ❌ **DON'T**: Store private key in environment files

### Token Security

- ✅ Installation tokens expire after 1 hour (automatic)
- ✅ Tokens are cached in memory only (never persisted)
- ✅ Tokens are scoped to specific repositories
- ✅ Revocation: Uninstall app to revoke all tokens

### Audit Logging

All GitHub App operations are logged in:
- Repository Settings → Integrations → GitHub Apps
- View all actions taken by the app
- Audit trail for compliance

---

## Troubleshooting

### Authentication Failures

**Error**: `GitHubAppAuthenticationError: Failed to get installation token: HTTP 401`

**Solutions**:
1. Verify app_id is correct (2497877)
2. Verify installation_id is correct (100231961)
3. Verify private key matches the GitHub App
4. Check app is installed on the repository

### Rate Limit Errors

**Error**: `GitHubAppRateLimitError: Rate limit exceeded. Resets at 1234567890`

**Solutions**:
1. Wait until reset time (Unix timestamp)
2. Reduce API call frequency
3. Use conditional requests (ETags)
4. Consider multiple GitHub Apps for horizontal scaling

### Not Found Errors

**Error**: `GitHubAppNotFoundError: Resource not found: /repos/owner/repo/workflows/deploy.yml/dispatches`

**Solutions**:
1. Verify workflow file exists in `.github/workflows/`
2. Verify repository name is correct
3. Check app has "Workflows" permission
4. Ensure workflow has `workflow_dispatch` trigger

---

## Related Documentation

- [GitHub App Setup Guide](../integrations/github-app-setup.md)
- [GitHub App Integration (Hybrid)](../autonomous/03-github-app-integration-hybrid.md)
- [ADR-003: Railway Autonomous Control](../decisions/ADR-003-railway-autonomous-control.md)
- [GitHub Apps Documentation](https://docs.github.com/en/apps)

---

## Changelog

### Version 1.0.0 (2026-01-13)

- Initial implementation
- JWT-based authentication with automatic token refresh
- Complete API operations (workflows, issues, PRs, commits, repository)
- Exponential backoff retry logic
- Comprehensive error handling
- 30+ unit tests with 100% coverage

---

*Last Updated: 2026-01-13*
*Status: Production Ready*
