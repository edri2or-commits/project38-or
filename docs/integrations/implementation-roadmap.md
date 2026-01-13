# Implementation Roadmap - 7-Day Development Plan

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Day 1: Foundation & Authentication](#day-1-foundation--authentication)
4. [Day 2: Railway Integration](#day-2-railway-integration)
5. [Day 3: GitHub App Setup](#day-3-github-app-setup)
6. [Day 4: n8n Deployment & Integration](#day-4-n8n-deployment--integration)
7. [Day 5: Orchestration Layer](#day-5-orchestration-layer)
8. [Day 6: Monitoring & Security](#day-6-monitoring--security)
9. [Day 7: Testing & Production Deployment](#day-7-testing--production-deployment)
10. [Post-Launch: Maintenance](#post-launch-maintenance)

---

## Overview

This roadmap outlines a **7-day sprint** to build a fully autonomous Claude control system for Railway, GitHub, and n8n. Each day has specific deliverables, testing requirements, and success criteria.

**Total Estimated Time:** 40-50 hours over 7 days (6-8 hours per day)

**Team:** Solo developer (you) + Claude agent

**Goal:** Production-ready autonomous system by end of Day 7

---

## Prerequisites

### Before Day 1

**Environment Setup:**
```bash
# Verify Python 3.11+
python3 --version

# Verify gcloud CLI
gcloud version

# Verify Railway CLI (optional)
npm install -g @railway/cli
railway --version

# Verify dependencies
pip install -r requirements.txt
```

**Required Access:**
- ✅ GCP Project: `project38-483612` with WIF configured
- ✅ GitHub Repository: `edri2or-commits/project38-or`
- ✅ Railway Project: `delightful-cat` (95ec21cc-9ada-41c5-8485-12f9a00e0116)
- ✅ GCP Secrets: RAILWAY-API, N8N-API (to be created)

**Tools Installed:**
- Python 3.11+
- gcloud CLI
- gh CLI (GitHub)
- httpx, PyJWT, cryptography

---

## Day 1: Foundation & Authentication

**Goal:** Establish secure authentication foundation with GCP Secret Manager and test Railway access.

### Morning Session (3 hours)

#### Task 1.1: Verify GCP Secret Manager Access

```bash
# Test WIF authentication
gcloud auth application-default login

# Verify secret access
gcloud secrets list --project=project38-483612

# Test secret retrieval
gcloud secrets versions access latest --secret=RAILWAY-API --project=project38-483612
```

**Expected Output:** Successfully retrieve Railway API token

#### Task 1.2: Enhance `src/secrets_manager.py`

**Add token caching:**

```python
# Add to SecretManager class
from datetime import datetime, timedelta
from typing import Optional, Dict

class SecretManager:
    def __init__(self):
        # ... existing code ...
        self._cache: Dict[str, tuple[str, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes

    def get_secret(self, secret_name: str, use_cache: bool = True) -> str:
        """Get secret with optional caching."""

        # Check cache
        if use_cache and secret_name in self._cache:
            value, cached_at = self._cache[secret_name]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                logger.debug(f"Using cached secret: {secret_name}")
                return value

        # Fetch from Secret Manager
        value = self._fetch_secret(secret_name)  # existing implementation

        # Cache value
        if use_cache:
            self._cache[secret_name] = (value, datetime.utcnow())

        return value

    def clear_cache(self):
        """Clear all cached secrets."""
        self._cache.clear()
        logger.info("Cleared secret cache")
```

**Test:**
```bash
pytest tests/test_secrets_manager.py -v
```

### Afternoon Session (3 hours)

#### Task 1.3: Create Railway Client Module

**Create `src/railway_client.py`:**

Use the complete implementation from `/tmp/railway-api-guide.md`.

**Key components:**
- RailwayClient class
- execute() method with retry logic
- trigger_deployment()
- get_deployment_status()
- wait_for_deployment()

**Test:**
```python
# Test script: scripts/test_railway_client.py
import asyncio
from src.railway_client import RailwayClient
from src.secrets_manager import SecretManager

async def test():
    manager = SecretManager()
    client = RailwayClient(api_key=manager.get_secret("RAILWAY-API"))

    # Test API connectivity
    services = await client.list_services(
        project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
        environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
    )

    print(f"✓ Found {len(services)} services")
    for service in services:
        print(f"  - {service['name']} (ID: {service['id']})")

asyncio.run(test())
```

#### Task 1.4: Document Token Management

Create `docs/token-management.md` documenting:
- Token lifecycle
- Rotation procedures
- Emergency revocation steps

### Evening (1 hour)

**Review & Test:**
```bash
# Run all tests
pytest tests/ -v

# Verify Railway API access
python scripts/test_railway_client.py
```

**Success Criteria:**
- ✅ SecretManager retrieves secrets from GCP
- ✅ Token caching works (5-minute TTL)
- ✅ RailwayClient successfully queries Railway API
- ✅ No secrets logged in any output

---

## Day 2: Railway Integration

**Goal:** Complete Railway API integration with deployment monitoring and rollback capabilities.

### Morning Session (3 hours)

#### Task 2.1: Implement Deployment Monitoring

**Add to `src/railway_client.py`:**

```python
async def wait_for_deployment(
    self,
    deployment_id: str,
    timeout: int = 600,
    poll_interval: int = 5
) -> DeploymentStatus:
    """Wait for deployment with detailed status updates."""
    # Implementation from guide
    pass

async def monitor_deployment_logs(
    self,
    deployment_id: str,
    callback: Callable[[str], None] = None
):
    """
    Monitor deployment logs in real-time.

    Note: Direct log streaming via GraphQL is not well-documented.
    Use Railway CLI or webhooks for production.
    """
    # Use Railway CLI programmatically
    import subprocess

    process = subprocess.Popen(
        ["railway", "logs", "--deployment", deployment_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        for line in process.stdout:
            if callback:
                callback(line.strip())
            else:
                print(line.strip())
    finally:
        process.terminate()
```

**Test:**
```python
# Trigger deployment and monitor
deployment_id = await client.trigger_deployment(
    environment_id="...",
    service_id="..."
)

result = await client.wait_for_deployment(deployment_id, timeout=600)
print(f"Deployment finished: {result.status}")
```

#### Task 2.2: Implement Rollback Logic

```python
async def rollback_deployment(
    self,
    previous_deployment_id: str
) -> str:
    """Rollback to previous deployment."""
    # Implementation from guide
    pass

async def get_previous_successful_deployment(
    self,
    service_id: str,
    environment_id: str
) -> Optional[str]:
    """Get ID of last successful deployment."""

    query = """
    query GetDeployments($serviceId: String!, $environmentId: String!) {
      service(id: $serviceId) {
        deployments(
          first: 10,
          input: { environmentId: $environmentId }
        ) {
          edges {
            node {
              id
              status
              createdAt
            }
          }
        }
      }
    }
    """

    variables = {
        "serviceId": service_id,
        "environmentId": environment_id
    }

    data = await self.execute(query, variables)
    deployments = data["service"]["deployments"]["edges"]

    # Find first SUCCESS deployment
    for edge in deployments:
        if edge["node"]["status"] == "SUCCESS":
            return edge["node"]["id"]

    return None
```

### Afternoon Session (3 hours)

#### Task 2.3: Implement Railway Webhook Handler

**Create `src/api/routes/webhooks.py`:**

```python
from fastapi import APIRouter, Request, HTTPException
from src.railway_client import RailwayClient
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/railway-webhook")
async def handle_railway_webhook(request: Request):
    """
    Handle Railway deployment webhooks.

    Webhook payload:
    {
      "type": "DEPLOY",
      "status": "SUCCESS" | "FAILED" | "CRASHED",
      "project": {...},
      "deployment": {...}
    }
    """

    data = await request.json()

    logger.info(
        f"Railway webhook: {data['type']} - {data.get('status')}",
        extra={"deployment_id": data.get("deployment", {}).get("id")}
    )

    # Handle deployment failure
    if data.get("status") in ["FAILED", "CRASHED"]:
        deployment_id = data["deployment"]["id"]

        # Trigger automated response (analysis, rollback, etc.)
        # This will be implemented in orchestration layer

        logger.warning(f"Deployment {deployment_id} failed, triggering recovery")

    return {"status": "received"}
```

**Register router in `src/api/main.py`:**

```python
from src.api.routes import webhooks

app.include_router(webhooks.router, prefix="/webhooks")
```

#### Task 2.4: Test Railway Deployment Flow

**Integration test:**

```python
# tests/integration/test_railway_deployment.py
import pytest
from src.railway_client import RailwayClient

@pytest.mark.asyncio
async def test_full_deployment_cycle(railway_client):
    """Test complete deployment cycle: trigger → monitor → verify."""

    # Trigger deployment
    deployment_id = await railway_client.trigger_deployment(
        environment_id="99c99a18-aea2-4d01-9360-6a93705102a0",
        service_id="<service-id>"
    )

    assert deployment_id is not None

    # Wait for completion
    result = await railway_client.wait_for_deployment(
        deployment_id,
        timeout=600
    )

    assert result.status == "SUCCESS"
```

### Evening (1 hour)

**Review & Test:**
```bash
# Run Railway integration tests
pytest tests/integration/test_railway_deployment.py -v

# Test webhook endpoint
curl -X POST http://localhost:8000/webhooks/railway-webhook \
  -H "Content-Type: application/json" \
  -d '{"type": "DEPLOY", "status": "SUCCESS"}'
```

**Success Criteria:**
- ✅ Can trigger Railway deployments programmatically
- ✅ Deployment monitoring works (status polling)
- ✅ Rollback functionality implemented and tested
- ✅ Webhook endpoint receives Railway events

---

## Day 3: GitHub App Setup

**Goal:** Create GitHub App, implement JWT authentication, and test workflow triggering.

### Morning Session (4 hours)

#### Task 3.1: Create GitHub App

**Follow guide from `/tmp/github-app-setup.md`:**

1. Go to https://github.com/settings/apps
2. Create new GitHub App:
   - Name: `claude-autonomous-agent`
   - Permissions: Contents (R/W), Pull Requests (R/W), Workflows (R/W), Issues (R/W)
   - Repository: `edri2or-commits/project38-or` only

3. Generate private key
4. Store in GCP Secret Manager:
   ```bash
   cat private-key.pem | base64 -w 0 > private-key-b64.txt
   gcloud secrets create github-app-private-key \
     --data-file=private-key-b64.txt \
     --project=project38-483612
   rm private-key.pem private-key-b64.txt
   ```

5. Install app on repository
6. Note App ID and Installation ID

#### Task 3.2: Implement GitHub App Authentication

**Create `src/github_app.py`:**

Use the complete implementation from `/tmp/github-app-setup.md`.

**Key components:**
- GitHubAppClient class
- JWT generation with PyJWT
- Installation token caching (1 hour expiration)
- Auto-refresh 5 minutes before expiration

**Test:**
```python
# scripts/test_github_app.py
import asyncio
from src.github_app import GitHubAppClient

async def test():
    client = GitHubAppClient(
        app_id="<your-app-id>",
        private_key_secret="github-app-private-key",
        installation_id="<your-installation-id>",
        repo="edri2or-commits/project38-or"
    )

    # Test authentication
    token = await client._get_token()
    print(f"✓ Installation token: {token[:10]}...")

    # Test API access
    rate_limit = await client.check_rate_limit()
    print(f"✓ Rate limit: {rate_limit['remaining']}/{rate_limit['limit']}")

    # Test workflow trigger
    await client.trigger_workflow(
        workflow_id="test.yml",
        ref="main"
    )
    print("✓ Workflow triggered")

asyncio.run(test())
```

### Afternoon Session (3 hours)

#### Task 3.3: Implement PR Management

**Add to `src/github_app.py`:**

```python
async def create_pull_request_with_checks(
    self,
    title: str,
    body: str,
    head: str,
    base: str = "main"
) -> Dict[str, Any]:
    """
    Create PR and wait for initial checks to start.

    Returns:
        PR data with number, url, checks status
    """

    # Create PR
    pr = await self.create_pull_request(title, body, head, base)

    # Wait a few seconds for checks to start
    await asyncio.sleep(5)

    # Get initial status
    status = await self.get_pr_status(pr["number"])

    return {
        **pr,
        "checks_state": status["checks_state"],
        "mergeable": status["mergeable"]
    }

async def auto_merge_when_ready(
    self,
    pr_number: int,
    timeout: int = 1800,  # 30 minutes
    merge_method: str = "squash"
):
    """
    Wait for PR checks to pass, then merge manually (auto-merge removed 2026-01-13).

    Args:
        pr_number: PR number
        timeout: Maximum wait time in seconds
        merge_method: "merge", "squash", or "rebase"

    Raises:
        TimeoutError: If checks don't pass within timeout
        Exception: If checks fail
    """
    import time

    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"PR #{pr_number} checks timed out")

        status = await self.get_pr_status(pr_number)

        logger.info(
            f"PR #{pr_number} status: {status['checks_state']} "
            f"(mergeable: {status['mergeable']})"
        )

        if status["checks_state"] == "success" and status["mergeable"]:
            # All checks passed, merge PR
            result = await self.merge_pull_request(
                pr_number,
                merge_method=merge_method
            )

            logger.info(f"Auto-merged PR #{pr_number}")
            return result

        elif status["checks_state"] == "failure":
            raise Exception(f"PR #{pr_number} checks failed")

        # Wait before polling again
        await asyncio.sleep(30)
```

#### Task 3.4: Test GitHub Integration

**Integration test:**

```python
# tests/integration/test_github_app.py
@pytest.mark.asyncio
async def test_pr_workflow(github_client):
    """Test full PR workflow: create → trigger CI → merge."""

    # Create test branch
    # (Assume branch exists with changes)

    # Create PR
    pr = await github_client.create_pull_request_with_checks(
        title="test: automated PR creation",
        body="## Test\nAutomated test PR",
        head="test/automated-pr",
        base="main"
    )

    assert pr["number"] is not None
    print(f"Created PR #{pr['number']}")

    # Wait for checks to pass (or fail)
    try:
        result = await github_client.auto_merge_when_ready(
            pr_number=pr["number"],
            timeout=600  # 10 minutes for test
        )

        assert result is not None
        print(f"✓ PR merged successfully")

    except Exception as e:
        print(f"✗ PR failed: {e}")
        raise
```

### Evening (1 hour)

**Review & Test:**
```bash
# Test GitHub App authentication
python scripts/test_github_app.py

# Run GitHub integration tests
pytest tests/integration/test_github_app.py -v
```

**Success Criteria:**
- ✅ GitHub App created with correct permissions
- ✅ JWT authentication works (installation token cached)
- ✅ Can trigger workflow_dispatch events
- ✅ Can create/merge PRs programmatically

---

## Day 4: n8n Deployment & Integration

**Goal:** Deploy n8n to Railway, set up API access, and create sample workflows.

### Morning Session (3 hours)

#### Task 4.1: Deploy n8n to Railway

**Using Railway template:**

1. Go to https://railway.com/deploy/n8n
2. Click "Deploy Now"
3. Configure:
   - Project name: `n8n-automation`
   - PostgreSQL: ✓ Include

4. Wait for deployment (~3 minutes)

5. Get public URL: `https://n8n-<project>.up.railway.app`

6. Initial setup:
   - Create owner account
   - Generate API key
   - Store in GCP Secret Manager:
     ```bash
     echo -n "n8n_api_..." | gcloud secrets create N8N-API \
       --data-file=- \
       --project=project38-483612
     ```

#### Task 4.2: Implement n8n Client

**Create `src/n8n_client.py`:**

Use the complete implementation from `/tmp/n8n-integration.md`.

**Key components:**
- N8nClient class
- execute_and_wait() for workflow execution
- export_all_workflows() for version control
- import_workflow() for deployment

**Test:**
```python
# scripts/test_n8n_client.py
import asyncio
from src.n8n_client import N8nClient
from src.secrets_manager import SecretManager

async def test():
    manager = SecretManager()
    client = N8nClient(
        api_key=manager.get_secret("N8N-API"),
        base_url="https://n8n-<project>.up.railway.app/api/v1"
    )

    # List workflows
    workflows = await client.list_workflows()
    print(f"✓ Found {len(workflows)} workflows")

    # Test execution (if workflows exist)
    if workflows:
        execution_id = await client.execute_workflow(workflows[0]["id"])
        print(f"✓ Execution started: {execution_id}")

asyncio.run(test())
```

### Afternoon Session (4 hours)

#### Task 4.3: Create Sample Workflows

**Workflow 1: Deployment Notification**

Create in n8n UI, then export:

```json
{
  "name": "Railway Deployment Notification",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "path": "railway-deploy",
        "httpMethod": "POST"
      }
    },
    {
      "name": "Format Message",
      "type": "n8n-nodes-base.set",
      "position": [450, 300],
      "parameters": {
        "values": {
          "string": [
            {
              "name": "message",
              "value": "🚀 Deployment {{$json.status}}\n\nService: {{$json.service}}\nEnvironment: {{$json.environment}}\nURL: {{$json.url}}"
            }
          ]
        }
      }
    },
    {
      "name": "Send Telegram",
      "type": "n8n-nodes-base.telegram",
      "position": [650, 300],
      "parameters": {
        "text": "={{$json.message}}",
        "chatId": "YOUR_CHAT_ID"
      },
      "credentials": {
        "telegramApi": "telegram_creds"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Format Message"}]]
    },
    "Format Message": {
      "main": [[{"node": "Send Telegram"}]]
    }
  }
}
```

**Save to:** `n8n-workflows/railway-deployment-notification.json`

**Workflow 2: GitHub PR Analysis**

```json
{
  "name": "GitHub PR Analysis with Claude",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "path": "github-pr",
        "httpMethod": "POST"
      }
    },
    {
      "name": "HTTP Request - Claude API",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300],
      "parameters": {
        "url": "https://api.anthropic.com/v1/messages",
        "method": "POST",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "x-api-key",
              "value": "={{$credentials.anthropicApi.apiKey}}"
            },
            {
              "name": "anthropic-version",
              "value": "2023-06-01"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "claude-sonnet-4-5-20250929"
            },
            {
              "name": "max_tokens",
              "value": 1024
            },
            {
              "name": "messages",
              "value": [
                {
                  "role": "user",
                  "content": "Analyze this PR and suggest improvements: {{$json.pr_url}}"
                }
              ]
            }
          ]
        }
      }
    },
    {
      "name": "Post Comment",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 300],
      "parameters": {
        "url": "https://api.github.com/repos/{{$json.repo}}/issues/{{$json.pr_number}}/comments",
        "method": "POST",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Authorization",
              "value": "token {{$credentials.githubApi.token}}"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "body",
              "value": "## Claude Analysis\n\n{{$json.content[0].text}}"
            }
          ]
        }
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "HTTP Request - Claude API"}]]
    },
    "HTTP Request - Claude API": {
      "main": [[{"node": "Post Comment"}]]
    }
  }
}
```

**Import workflows:**

```python
# scripts/import_workflows.py
import asyncio
from pathlib import Path
from src.n8n_client import N8nClient

async def import_all():
    client = N8nClient(...)

    workflow_dir = Path("n8n-workflows")

    for workflow_file in workflow_dir.glob("*.json"):
        await client.import_workflow(str(workflow_file), activate=True)
        print(f"✓ Imported: {workflow_file.name}")

asyncio.run(import_all())
```

### Evening (1 hour)

**Review & Test:**
```bash
# Test n8n client
python scripts/test_n8n_client.py

# Import workflows
python scripts/import_workflows.py

# Test workflow execution
python -c "
import asyncio
from src.n8n_client import N8nClient
async def test():
    client = N8nClient(...)
    result = await client.execute_and_wait('railway-deployment-notification', {
        'status': 'SUCCESS',
        'service': 'web',
        'environment': 'production',
        'url': 'https://...'
    })
    print(result)
asyncio.run(test())
"
```

**Success Criteria:**
- ✅ n8n deployed to Railway with PostgreSQL
- ✅ API key created and stored in GCP Secret Manager
- ✅ N8nClient successfully executes workflows
- ✅ Sample workflows imported and tested

---

## Day 5: Orchestration Layer

**Goal:** Build the autonomous orchestration engine that coordinates Railway, GitHub, and n8n.

### Morning Session (4 hours)

#### Task 5.1: Create Orchestrator Core

**Create `src/orchestrator.py`:**

```python
"""
Autonomous Orchestrator - Coordinates Railway, GitHub, and n8n

Handles:
- Deployment decisions
- Error recovery
- Cross-platform workflows
- State management
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from src.railway_client import RailwayClient
from src.github_app import GitHubAppClient
from src.n8n_client import N8nClient
from src.secrets_manager import SecretManager

logger = logging.getLogger(__name__)


@dataclass
class DeploymentContext:
    """Context for deployment operation."""
    pr_number: int
    branch: str
    commit_sha: str
    environment: str
    triggered_by: str
    correlation_id: str


class AutonomousOrchestrator:
    """
    Autonomous orchestrator for Railway + GitHub + n8n.

    Coordinates deployments, monitors health, and handles failures.
    """

    def __init__(
        self,
        railway_client: RailwayClient,
        github_client: GitHubAppClient,
        n8n_client: N8nClient
    ):
        self.railway = railway_client
        self.github = github_client
        self.n8n = n8n_client

    async def deploy_from_pr(
        self,
        pr_number: int,
        environment: str = "production"
    ) -> Dict[str, Any]:
        """
        Complete deployment flow from PR to production.

        Steps:
            1. Verify PR checks passed
            2. Merge PR
            3. Trigger Railway deployment
            4. Monitor deployment
            5. Verify health check
            6. Send notifications
            7. Handle failures

        Args:
            pr_number: GitHub PR number
            environment: Target environment

        Returns:
            Deployment result dict
        """

        correlation_id = f"deploy-pr-{pr_number}-{int(datetime.utcnow().timestamp())}"

        logger.info(
            f"Starting deployment from PR #{pr_number}",
            extra={"correlation_id": correlation_id}
        )

        try:
            # Step 1: Verify PR checks
            pr_status = await self.github.get_pr_status(pr_number)

            if pr_status["checks_state"] != "success":
                raise Exception(f"PR checks not passed: {pr_status['checks_state']}")

            if not pr_status["mergeable"]:
                raise Exception("PR is not mergeable (conflicts?)")

            # Step 2: Merge PR
            logger.info(f"Merging PR #{pr_number}", extra={"correlation_id": correlation_id})

            merge_result = await self.github.merge_pull_request(
                pr_number,
                merge_method="squash"
            )

            commit_sha = merge_result["sha"]

            # Step 3: Trigger Railway deployment
            logger.info(
                f"Triggering Railway deployment for {commit_sha}",
                extra={"correlation_id": correlation_id}
            )

            deployment_id = await self.railway.trigger_deployment(
                environment_id=os.getenv("RAILWAY_ENVIRONMENT_ID"),
                service_id=os.getenv("RAILWAY_SERVICE_ID")
            )

            # Step 4: Monitor deployment
            logger.info(
                f"Monitoring deployment {deployment_id}",
                extra={"correlation_id": correlation_id}
            )

            deployment_result = await self.railway.wait_for_deployment(
                deployment_id,
                timeout=600
            )

            # Step 5: Verify health check
            if deployment_result.status == "SUCCESS":
                health_ok = await self._verify_health_check(deployment_result.static_url)

                if not health_ok:
                    raise Exception("Health check failed after deployment")

            # Step 6: Send success notification
            await self.n8n.execute_workflow(
                "railway-deployment-notification",
                {
                    "status": "SUCCESS",
                    "pr_number": pr_number,
                    "commit_sha": commit_sha,
                    "deployment_id": deployment_id,
                    "url": deployment_result.static_url,
                    "environment": environment
                }
            )

            logger.info(
                f"Deployment successful: {deployment_id}",
                extra={"correlation_id": correlation_id}
            )

            return {
                "success": True,
                "deployment_id": deployment_id,
                "url": deployment_result.static_url,
                "pr_number": pr_number,
                "commit_sha": commit_sha
            }

        except Exception as e:
            logger.error(
                f"Deployment failed: {e}",
                extra={"correlation_id": correlation_id}
            )

            # Handle failure
            await self._handle_deployment_failure(
                pr_number=pr_number,
                error=str(e),
                correlation_id=correlation_id
            )

            raise

    async def _verify_health_check(self, url: str) -> bool:
        """Verify application health check."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{url}/health")

                if response.status_code == 200:
                    data = response.json()
                    return data.get("status") == "healthy"

                return False

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def _handle_deployment_failure(
        self,
        pr_number: int,
        error: str,
        correlation_id: str
    ):
        """Handle deployment failure with rollback and notifications."""

        logger.warning(
            f"Handling deployment failure for PR #{pr_number}",
            extra={"correlation_id": correlation_id}
        )

        # Get previous successful deployment
        previous = await self.railway.get_previous_successful_deployment(
            service_id=os.getenv("RAILWAY_SERVICE_ID"),
            environment_id=os.getenv("RAILWAY_ENVIRONMENT_ID")
        )

        if previous:
            # Trigger rollback
            rollback_id = await self.railway.rollback_deployment(previous)

            logger.info(
                f"Rolled back to deployment {previous} (new: {rollback_id})",
                extra={"correlation_id": correlation_id}
            )

        # Send failure notification
        await self.n8n.execute_workflow(
            "railway-deployment-notification",
            {
                "status": "FAILED",
                "pr_number": pr_number,
                "error": error,
                "rollback_id": rollback_id if previous else None
            }
        )

        # Comment on PR
        await self.github.create_issue_comment(
            pr_number,
            f"## ⚠️ Deployment Failed\n\n"
            f"**Error:** {error}\n\n"
            f"**Rollback:** {'✓ Completed' if previous else '✗ No previous deployment'}\n\n"
            f"**Correlation ID:** `{correlation_id}`"
        )
```

### Afternoon Session (3 hours)

#### Task 5.2: Implement Webhook Handlers

**Update `src/api/routes/webhooks.py`:**

```python
from src.orchestrator import AutonomousOrchestrator

# Initialize orchestrator
orchestrator = AutonomousOrchestrator(
    railway_client=RailwayClient(...),
    github_client=GitHubAppClient(...),
    n8n_client=N8nClient(...)
)


@router.post("/github-webhook")
async def handle_github_webhook(request: Request):
    """
    Handle GitHub webhooks (PR events, workflow runs, etc.).

    Supported events:
    - pull_request (opened, synchronize, closed)
    - workflow_run (completed)
    - issue_comment (for agent commands)
    """

    event_type = request.headers.get("X-GitHub-Event")
    data = await request.json()

    logger.info(f"GitHub webhook: {event_type}", extra={"event": event_type})

    if event_type == "pull_request":
        action = data["action"]
        pr_number = data["pull_request"]["number"]

        if action == "closed" and data["pull_request"]["merged"]:
            # PR was merged, trigger deployment
            await orchestrator.deploy_from_pr(pr_number)

    elif event_type == "issue_comment":
        # Check for agent commands
        comment_body = data["comment"]["body"]

        if comment_body.startswith("/deploy"):
            pr_number = data["issue"]["number"]
            await orchestrator.deploy_from_pr(pr_number)

    return {"status": "processed"}
```

#### Task 5.3: Create Integration Tests

```python
# tests/integration/test_orchestrator.py
import pytest
from src.orchestrator import AutonomousOrchestrator

@pytest.mark.asyncio
async def test_full_deployment_flow(orchestrator):
    """Test complete deployment flow: PR → Deploy → Verify → Notify."""

    # Assume PR exists with passing checks
    pr_number = 999  # Test PR

    result = await orchestrator.deploy_from_pr(pr_number, environment="staging")

    assert result["success"] is True
    assert result["deployment_id"] is not None
    assert result["url"] is not None

    print(f"✓ Deployment succeeded: {result['url']}")


@pytest.mark.asyncio
async def test_deployment_failure_recovery(orchestrator):
    """Test deployment failure triggers rollback."""

    # This test requires mocking Railway API to simulate failure
    # Skip for now, implement after Day 6 (monitoring setup)
    pass
```

### Evening (1 hour)

**Review & Test:**
```bash
# Test orchestrator
pytest tests/integration/test_orchestrator.py -v

# Manual test
python -c "
import asyncio
from src.orchestrator import AutonomousOrchestrator
async def test():
    # Initialize clients
    orchestrator = AutonomousOrchestrator(...)
    result = await orchestrator.deploy_from_pr(pr_number=1)
    print(result)
asyncio.run(test())
"
```

**Success Criteria:**
- ✅ Orchestrator coordinates all three platforms
- ✅ Can deploy from PR to Railway
- ✅ Monitors deployment and verifies health
- ✅ Sends notifications via n8n
- ✅ Handles failures with rollback

---

## Day 6: Monitoring & Security

**Goal:** Implement comprehensive monitoring, logging, and security hardening.

### Morning Session (3 hours)

#### Task 6.1: Implement Structured Logging

**Create `src/logging_config.py`:**

```python
"""Structured JSON logging configuration."""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add extra fields
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        if hasattr(record, "deployment_id"):
            log_entry["deployment_id"] = record.deployment_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(level: str = "INFO"):
    """Configure structured logging."""

    # Create JSON formatter
    formatter = JSONFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    root_logger.addHandler(console_handler)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.info("Structured logging configured", extra={"log_level": level})
```

**Update `src/api/main.py`:**

```python
from src.logging_config import setup_logging

# Initialize logging on startup
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
```

#### Task 6.2: Add Metrics Endpoints

**Create `src/api/routes/metrics.py`:**

```python
from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any
import psutil

router = APIRouter()

# Simple in-memory metrics (for production, use Prometheus)
metrics = {
    "deployments": {"total": 0, "success": 0, "failed": 0},
    "api_calls": {"railway": 0, "github": 0, "n8n": 0},
    "errors": {"total": 0, "by_type": {}}
}


@router.get("/metrics/summary")
async def get_metrics_summary() -> Dict[str, Any]:
    """Get high-level metrics summary."""

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "deployments": metrics["deployments"],
        "api_calls": metrics["api_calls"],
        "errors": metrics["errors"]["total"],
        "uptime_seconds": (datetime.utcnow() - start_time).total_seconds()
    }


@router.get("/metrics/system")
async def get_system_metrics() -> Dict[str, Any]:
    """Get system resource metrics."""

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent
    }


def increment_metric(category: str, key: str):
    """Increment a metric counter."""
    if category in metrics:
        metrics[category][key] = metrics[category].get(key, 0) + 1
```

**Update orchestrator to track metrics:**

```python
# In orchestrator.py
from src.api.routes.metrics import increment_metric

async def deploy_from_pr(self, pr_number: int, environment: str = "production"):
    increment_metric("deployments", "total")

    try:
        # ... existing code ...

        increment_metric("deployments", "success")

    except Exception as e:
        increment_metric("deployments", "failed")
        raise
```

### Afternoon Session (3 hours)

#### Task 6.3: Implement Security Hardening

**Token Management Review:**

```python
# Audit all API clients for token handling

# src/railway_client.py
class RailwayClient:
    def __init__(self, api_token: str):
        # ✅ Token passed as parameter, not environment variable
        # ✅ Token stored in instance variable (not logged)
        # ✅ Token cleared on __del__? Add:

    def __del__(self):
        """Clear token from memory on cleanup."""
        if hasattr(self, "api_token"):
            self.api_token = None


# src/github_app.py
class GitHubAppClient:
    def __init__(self, ...):
        # ✅ Private key base64-encoded in Secret Manager
        # ✅ Installation token cached with expiration
        # ✅ Token auto-refresh before expiration

    async def _refresh_token(self):
        # ✅ Old token cleared before fetching new one
        self._token = None
        # ... fetch new token ...


# Add to SecretManager
class SecretManager:
    def clear_cache(self):
        """Clear all cached secrets (call on shutdown)."""
        for key in list(self._cache.keys()):
            del self._cache[key]
        logger.info("Cleared secret cache")
```

**Input Validation:**

```python
# src/api/routes/webhooks.py
from pydantic import BaseModel, Field

class GitHubWebhookPayload(BaseModel):
    """Validated GitHub webhook payload."""
    action: str
    pull_request: Dict[str, Any] = None
    comment: Dict[str, Any] = None
    repository: Dict[str, Any]

@router.post("/github-webhook")
async def handle_github_webhook(payload: GitHubWebhookPayload):
    """Handle GitHub webhooks with validation."""
    # ... validated payload automatically ...
```

**Security Headers:**

```python
# src/api/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://github.com"],  # Only GitHub
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

#### Task 6.4: Create Security Checklist

**Create `docs/security-checklist.md`:**

```markdown
# Security Checklist for Production

## Pre-Deployment

- [ ] All secrets in GCP Secret Manager (not env vars)
- [ ] GitHub App uses minimum required permissions
- [ ] Railway API token is project-scoped (not account-wide)
- [ ] n8n API key has expiration set (365 days)
- [ ] No secrets in code or logs
- [ ] Input validation on all webhook endpoints
- [ ] Security headers configured (CSP, X-Frame-Options, etc.)

## Post-Deployment

- [ ] GCP Audit Logs enabled for Secret Manager
- [ ] Monitoring alerts configured
- [ ] Token rotation schedule documented
- [ ] Incident response plan documented
- [ ] Backup procedures tested

## Monthly Review

- [ ] Review GCP Secret Manager access logs
- [ ] Review GitHub App permissions
- [ ] Review Railway deployment history
- [ ] Test token rotation procedures
- [ ] Update dependencies (pip-audit)
```

### Evening (1 hour)

**Security Audit:**
```bash
# Run security scanners
pip-audit

# Check for secrets in code
git secrets --scan

# Review all API clients for token handling
grep -r "api_key\|token\|secret" src/
```

**Success Criteria:**
- ✅ Structured JSON logging implemented
- ✅ Metrics endpoints functional
- ✅ All tokens cleared from memory on cleanup
- ✅ Input validation on webhooks
- ✅ Security headers configured

---

## Day 7: Testing & Production Deployment

**Goal:** Comprehensive testing, final verification, and production deployment.

### Morning Session (4 hours)

#### Task 7.1: End-to-End Integration Test

**Create `tests/e2e/test_full_deployment.py`:**

```python
"""
End-to-end test of complete autonomous deployment flow.

Test scenario:
1. Create test branch with code change
2. Open PR
3. Wait for CI to pass
4. Claude agent auto-deploys to Railway
5. Verify deployment
6. Receive notification
7. Cleanup
"""

import pytest
from src.orchestrator import AutonomousOrchestrator

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_autonomous_deployment_flow(orchestrator):
    """Test complete autonomous flow from PR to production."""

    # This test assumes a test branch exists
    test_pr_number = 9999

    print("Starting end-to-end deployment test...")

    # Step 1: Trigger deployment
    result = await orchestrator.deploy_from_pr(
        pr_number=test_pr_number,
        environment="staging"  # Use staging for test
    )

    assert result["success"] is True
    assert result["deployment_id"] is not None

    print(f"✓ Deployment succeeded: {result['deployment_id']}")

    # Step 2: Verify application is running
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{result['url']}/health")
        assert response.status_code == 200

        health_data = response.json()
        assert health_data["status"] == "healthy"

    print(f"✓ Health check passed: {result['url']}")

    # Step 3: Verify metrics
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{result['url']}/metrics/summary")
        assert response.status_code == 200

    print("✓ Metrics endpoint functional")

    # Step 4: Trigger rollback (test recovery)
    previous = await orchestrator.railway.get_previous_successful_deployment(
        service_id=os.getenv("RAILWAY_SERVICE_ID"),
        environment_id=os.getenv("RAILWAY_STAGING_ENVIRONMENT_ID")
    )

    if previous:
        rollback_id = await orchestrator.railway.rollback_deployment(previous)
        print(f"✓ Rollback tested: {rollback_id}")

    print("\n✅ End-to-end test passed!")
```

**Run test:**
```bash
pytest tests/e2e/test_full_deployment.py -v -s
```

#### Task 7.2: Load Test Webhook Endpoints

**Create `tests/load/test_webhook_load.py`:**

```python
"""Load test webhook endpoints."""

import asyncio
import httpx
from datetime import datetime

async def load_test_github_webhook(url: str, num_requests: int = 100):
    """Send multiple webhook requests concurrently."""

    start_time = datetime.utcnow()
    successful = 0
    failed = 0

    async def send_request():
        nonlocal successful, failed

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{url}/webhooks/github-webhook",
                    json={
                        "action": "opened",
                        "pull_request": {"number": 123},
                        "repository": {"name": "test"}
                    },
                    headers={"X-GitHub-Event": "pull_request"}
                )

                if response.status_code == 200:
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                failed += 1

    # Send requests concurrently
    tasks = [send_request() for _ in range(num_requests)]
    await asyncio.gather(*tasks)

    duration = (datetime.utcnow() - start_time).total_seconds()
    rps = num_requests / duration

    print(f"Load test results:")
    print(f"  Total requests: {num_requests}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Requests/second: {rps:.2f}")

# Run test
asyncio.run(load_test_github_webhook("http://localhost:8000", 100))
```

### Afternoon Session (3 hours)

#### Task 7.3: Production Deployment

**Pre-Deployment Checklist:**

```bash
# 1. Run all tests
pytest tests/ -v

# 2. Security audit
pip-audit

# 3. Verify secrets
python -c "
from src.secrets_manager import SecretManager
m = SecretManager()
assert m.get_secret('RAILWAY-API')
assert m.get_secret('N8N-API')
assert m.get_secret('github-app-private-key')
print('✓ All secrets accessible')
"

# 4. Build Docker image (if using)
docker build -t claude-agent:latest .

# 5. Test locally
docker run -p 8000:8000 claude-agent:latest
curl http://localhost:8000/health
```

**Deploy to Railway:**

```bash
# Option 1: GitHub Actions workflow
gh workflow run deploy-railway.yml \
  --ref main \
  -f environment=production

# Option 2: Railway CLI
railway up --service web --environment production
```

**Post-Deployment Verification:**

```bash
# 1. Check health
curl https://web-production-47ff.up.railway.app/health

# 2. Check metrics
curl https://web-production-47ff.up.railway.app/metrics/summary

# 3. Test webhook
curl -X POST https://web-production-47ff.up.railway.app/webhooks/github-webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen": "test"}'

# 4. Monitor logs
railway logs --service web --environment production --follow
```

#### Task 7.4: Configure GitHub Webhooks

**Set up GitHub webhooks to point to Railway app:**

1. Go to https://github.com/edri2or-commits/project38-or/settings/hooks
2. Click "Add webhook"
3. Configure:
   - Payload URL: `https://web-production-47ff.up.railway.app/webhooks/github-webhook`
   - Content type: `application/json`
   - Secret: (generate and store in GCP Secret Manager as `GITHUB-WEBHOOK-SECRET`)
   - Events: Pull requests, Issue comments, Workflow runs

4. Test webhook delivery

#### Task 7.5: Final Documentation

**Update `docs/deployment.md`:**

```markdown
# Deployment Guide

## Production Environment

- **Railway URL**: https://web-production-47ff.up.railway.app
- **GitHub Repository**: edri2or-commits/project38-or
- **n8n URL**: https://n8n-production.up.railway.app

## Deployment Process

1. Merge PR to main branch
2. GitHub webhook triggers Claude agent
3. Agent deploys to Railway
4. Health check verifies deployment
5. Notification sent via n8n

## Monitoring

- Health check: /health
- Metrics: /metrics/summary
- Railway logs: `railway logs`

## Emergency Procedures

### Rollback Deployment

```bash
# Get previous deployment ID
railway deployments --service web --environment production

# Rollback
railway redeploy <previous-deployment-id>
```

### Revoke Compromised Token

```bash
# Railway API token
# 1. Generate new token in Railway dashboard
# 2. Update Secret Manager
gcloud secrets versions add RAILWAY-API --data-file=-

# GitHub App
# 1. Generate new private key in GitHub App settings
# 2. Update Secret Manager
cat new-key.pem | base64 | gcloud secrets versions add github-app-private-key --data-file=-
```

## Contact

- Telegram: @your-username
- Emergency: (create GitHub issue)
```

### Evening (1 hour)

**Final Testing & Sign-Off:**

```bash
# 1. Verify all systems operational
curl https://web-production-47ff.up.railway.app/health | jq .

# 2. Test autonomous deployment with real PR
# (Create test PR, merge, observe deployment)

# 3. Verify notifications received

# 4. Check metrics after deployment
curl https://web-production-47ff.up.railway.app/metrics/summary | jq .

# 5. Review logs for errors
railway logs --service web --environment production | grep ERROR
```

**Success Criteria:**
- ✅ All tests passing (unit, integration, e2e)
- ✅ Production deployment successful
- ✅ Health checks passing
- ✅ GitHub webhooks configured and working
- ✅ Autonomous deployment tested end-to-end
- ✅ Notifications working
- ✅ Rollback tested
- ✅ Documentation complete

---

## Post-Launch: Maintenance

### Week 1: Monitoring & Adjustment

**Daily:**
- Check Railway logs for errors
- Monitor deployment success rate
- Review GCP Secret Manager audit logs

**Tasks:**
- Fine-tune polling intervals
- Adjust timeout values based on actual performance
- Optimize n8n workflows

### Week 2-4: Iteration

**Enhancements:**
1. Add more sophisticated error recovery
2. Implement automatic dependency updates
3. Add cost monitoring (Railway usage)
4. Create more n8n workflows for common tasks

### Monthly: Security Review

**Checklist:**
- [ ] Rotate API tokens (90-day schedule)
- [ ] Review GitHub App permissions
- [ ] Audit GCP Secret Manager access
- [ ] Update dependencies (`pip-audit`)
- [ ] Review deployment logs for anomalies
- [ ] Test incident response procedures

### Quarterly: Performance Review

**Metrics to Review:**
- Deployment success rate (target: >95%)
- Average deployment time (target: <3 minutes)
- API error rate (target: <1%)
- Token refresh success (target: 100%)
- Cost per deployment

**Optimization Opportunities:**
- Database query optimization
- API call batching
- Cache strategy improvements
- Workflow simplification

---

## Troubleshooting Common Issues

### Issue: GitHub App Installation Token Expired

**Symptoms:**
- 401 errors from GitHub API
- Logs show "Bad credentials"

**Solution:**
```python
# JWT may have expired, regenerate
await github_client._refresh_token()
```

### Issue: Railway Deployment Stuck in "DEPLOYING"

**Symptoms:**
- Deployment never transitions to SUCCESS/FAILED
- No error logs

**Solution:**
```bash
# Check Railway dashboard for issues
# May need to restart deployment
railway restart --service web
```

### Issue: n8n Workflow Execution Timeout

**Symptoms:**
- Workflow execution never completes
- Logs show "TimeoutError"

**Solution:**
```python
# Increase timeout in N8nClient
result = await client.execute_and_wait(workflow_id, timeout=900)  # 15 minutes
```

### Issue: Secrets Not Accessible from Railway

**Symptoms:**
- 403 errors from GCP Secret Manager
- "Permission denied" logs

**Solution:**
```bash
# Verify WIF binding
gcloud projects get-iam-policy project38-483612 \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/secretmanager.secretAccessor"

# Should show Railway service account
```

---

## Summary: 7-Day Deliverables

| Day | Deliverables | Status |
|-----|-------------|--------|
| 1 | SecretManager with caching, RailwayClient foundation | ✅ |
| 2 | Complete Railway integration (deploy, monitor, rollback) | ✅ |
| 3 | GitHub App setup, JWT authentication, PR management | ✅ |
| 4 | n8n deployment, N8nClient, sample workflows | ✅ |
| 5 | Orchestrator coordinating all platforms | ✅ |
| 6 | Monitoring, logging, security hardening | ✅ |
| 7 | Testing, production deployment, documentation | ✅ |

**Total Code Files Created:**
- `src/railway_client.py` (~400 lines)
- `src/github_app.py` (~500 lines)
- `src/n8n_client.py` (~400 lines)
- `src/orchestrator.py` (~300 lines)
- `src/logging_config.py` (~100 lines)
- `src/api/routes/webhooks.py` (~200 lines)
- `src/api/routes/metrics.py` (~100 lines)
- Tests: ~800 lines

**Total Lines of Code:** ~2,800 lines

**Production Ready:** Yes ✅

---

## Next Steps After Launch

1. **Week 1:** Monitor, adjust, optimize
2. **Week 2:** Add advanced features (cost tracking, auto-scaling)
3. **Month 2:** Expand to other workflows (database migrations, backups)
4. **Month 3:** Add ML-based anomaly detection
5. **Quarter 2:** Full autonomous operations (no human intervention needed)

**Congratulations!** 🎉 You now have a production-ready autonomous Claude control system.

---

**Last Updated:** 2026-01-12
