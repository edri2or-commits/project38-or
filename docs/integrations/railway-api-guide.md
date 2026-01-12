# Railway GraphQL API - Complete Guide for Autonomous Control

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [API Endpoint and Schema](#api-endpoint-and-schema)
4. [Rate Limits](#rate-limits)
5. [Deployment Management](#deployment-management)
6. [Service Management](#service-management)
7. [Logs and Monitoring](#logs-and-monitoring)
8. [Python Implementation](#python-implementation)
9. [Error Handling](#error-handling)
10. [Complete Python Client](#complete-python-client)

---

## Overview

Railway's public API is built with GraphQL and is the **same API that powers the Railway dashboard**. This means every operation you can perform in the UI can be automated via the API.

**Key Features:**
- ✅ Deploy services programmatically
- ✅ Monitor deployment status in real-time
- ✅ Stream build and runtime logs
- ✅ Restart/rollback deployments
- ✅ Manage environment variables
- ✅ Scale resources (CPU/memory)
- ✅ Set up webhooks for events

**API Endpoint:** `https://backboard.railway.com/graphql/v2`

---

## Authentication

### Creating API Tokens

1. Go to [Railway Account Settings > Tokens](https://railway.app/account/tokens)
2. Click "Create Token"
3. Choose token type:
   - **Personal Access Token**: Full account access
   - **Project Token**: Limited to specific project
   - **Team Token**: Team-level access
4. Copy token immediately (shown only once)
5. Store in GCP Secret Manager

### Token Storage in GCP

```python
from src.secrets_manager import SecretManager

manager = SecretManager()
railway_token = manager.get_secret("RAILWAY-API")
```

### Authentication Headers

```python
headers = {
    "Authorization": f"Bearer {railway_token}",
    "Content-Type": "application/json"
}
```

---

## API Endpoint and Schema

### GraphQL Endpoint

```
https://backboard.railway.com/graphql/v2
```

### Schema Introspection

Railway supports GraphQL introspection for discovering the schema:

```python
import httpx

introspection_query = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      name
      kind
      description
      fields {
        name
        description
        type {
          name
          kind
        }
      }
    }
  }
}
"""

async def fetch_schema(token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": introspection_query},
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()
```

### GraphiQL Playground

Railway provides an interactive GraphiQL playground:

1. Visit the GraphQL endpoint in browser
2. Add Authorization header: `Bearer <YOUR_TOKEN>`
3. Explore schema documentation
4. Test queries interactively

**Pro Tip:** When unsure about a query/mutation, perform the action in Railway dashboard and inspect the Network tab to see the exact GraphQL operation.

---

## Rate Limits

### Tier-Based Limits

| Plan | Requests Per Hour | Requests Per Second |
|------|-------------------|---------------------|
| Free | 100 | N/A |
| Hobby | 1,000 | 10 |
| Pro | 10,000 | 50 |
| Enterprise | Custom | Custom |

### Rate Limit Headers

Railway includes rate limit information in response headers:

```python
response.headers['X-RateLimit-Limit']      # Total limit
response.headers['X-RateLimit-Remaining']  # Remaining requests
response.headers['X-RateLimit-Reset']      # Reset timestamp
```

### Cloudflare Rate Limiting Issue

**Critical Discovery:** Railway has a 10 RPS limit applied by Cloudflare to API requests **without query strings**. This causes Error 1015.

**Solution:** Add query parameters to avoid Cloudflare blocking:

```python
# ❌ WRONG - may hit Cloudflare 1015 error
url = "https://backboard.railway.com/graphql/v2"

# ✅ RIGHT - add query parameter
url = "https://backboard.railway.com/graphql/v2?timestamp=1234567890"
```

### Rate Limit Handling

```python
import asyncio
from typing import Optional

async def graphql_request_with_retry(
    query: str,
    variables: dict,
    token: str,
    max_retries: int = 3
) -> Optional[dict]:
    """Execute GraphQL request with exponential backoff."""

    for attempt in range(max_retries):
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Add query parameter to avoid Cloudflare rate limiting
            timestamp = int(time.time())
            url = f"https://backboard.railway.com/graphql/v2?t={timestamp}"

            response = await client.post(
                url,
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:  # Rate limited
                wait_time = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(wait_time)
                continue

            # Other errors
            response.raise_for_status()

    return None
```

---

## Deployment Management

### Trigger Deployment

```python
deployment_trigger_mutation = """
mutation DeploymentTrigger($environmentId: String!, $serviceId: String!) {
  serviceInstanceDeploy(
    environmentId: $environmentId
    serviceId: $serviceId
  )
}
"""

async def trigger_deployment(project_id: str, environment_id: str, service_id: str, token: str):
    """Trigger a new deployment for a service."""

    variables = {
        "environmentId": environment_id,
        "serviceId": service_id
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": deployment_trigger_mutation, "variables": variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        if "errors" in data:
            raise Exception(f"Deployment trigger failed: {data['errors']}")

        return data["data"]["serviceInstanceDeploy"]
```

### Query Deployment Status

```python
deployment_status_query = """
query DeploymentStatus($deploymentId: String!) {
  deployment(id: $deploymentId) {
    id
    status
    staticUrl
    createdAt
    updatedAt
    meta
  }
}
"""

# Deployment statuses (from Railway GraphQL schema):
# - BUILDING
# - DEPLOYING
# - SUCCESS
# - FAILED
# - CRASHED
# - REMOVED
# - SKIPPED
# - SLEEPING

async def get_deployment_status(deployment_id: str, token: str) -> dict:
    """Get current status of a deployment."""

    variables = {"deploymentId": deployment_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": deployment_status_query, "variables": variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        return data["data"]["deployment"]
```

### Monitor Deployment Until Complete

```python
async def wait_for_deployment(deployment_id: str, token: str, timeout: int = 600):
    """
    Monitor deployment until it completes (SUCCESS) or fails.

    Args:
        deployment_id: Railway deployment ID
        token: Railway API token
        timeout: Maximum wait time in seconds

    Returns:
        Final deployment status dict

    Raises:
        TimeoutError: If deployment takes longer than timeout
        Exception: If deployment fails
    """
    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Deployment {deployment_id} timed out after {timeout}s")

        status_data = await get_deployment_status(deployment_id, token)
        status = status_data["status"]

        print(f"Deployment status: {status}")

        if status == "SUCCESS":
            return status_data

        if status in ["FAILED", "CRASHED", "REMOVED"]:
            raise Exception(f"Deployment failed with status: {status}")

        # Still in progress
        await asyncio.sleep(5)  # Poll every 5 seconds
```

### Restart Deployment

```python
restart_deployment_mutation = """
mutation RestartDeployment($deploymentId: String!) {
  deploymentRestart(id: $deploymentId)
}
"""

async def restart_deployment(deployment_id: str, token: str):
    """
    Restart a deployment (restart process within container).
    Useful for crashed services or locked-up applications.
    """

    variables = {"deploymentId": deployment_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": restart_deployment_mutation, "variables": variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        if "errors" in data:
            raise Exception(f"Restart failed: {data['errors']}")

        return data["data"]["deploymentRestart"]
```

### Rollback to Previous Deployment

**Note:** Rollback is not a direct GraphQL mutation. Instead, Railway uses the concept of redeploying a previous deployment:

```python
rollback_mutation = """
mutation RollbackDeployment($deploymentId: String!) {
  serviceInstanceRedeploy(deploymentId: $deploymentId)
}
"""

async def rollback_deployment(previous_deployment_id: str, token: str):
    """
    Rollback to a previous deployment by redeploying it.

    Note: Deployments older than your plan's retention policy cannot be restored.
    Railway automatically keeps deployment history based on plan tier.
    """

    variables = {"deploymentId": previous_deployment_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": rollback_mutation, "variables": variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        if "errors" in data:
            raise Exception(f"Rollback failed: {data['errors']}")

        return data["data"]["serviceInstanceRedeploy"]
```

---

## Service Management

### List All Services in Project

```python
list_services_query = """
query ListServices($projectId: String!, $environmentId: String!) {
  project(id: $projectId) {
    id
    name
    services(environmentId: $environmentId) {
      edges {
        node {
          id
          name
          icon
          createdAt
          updatedAt
        }
      }
    }
  }
}
"""

async def list_services(project_id: str, environment_id: str, token: str) -> list:
    """List all services in a project environment."""

    variables = {
        "projectId": project_id,
        "environmentId": environment_id
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": list_services_query, "variables": variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        edges = data["data"]["project"]["services"]["edges"]
        return [edge["node"] for edge in edges]
```

### Get Service Details

```python
service_details_query = """
query ServiceDetails($serviceId: String!) {
  service(id: $serviceId) {
    id
    name
    icon
    createdAt
    deployments(first: 10) {
      edges {
        node {
          id
          status
          staticUrl
          createdAt
        }
      }
    }
  }
}
"""

async def get_service_details(service_id: str, token: str) -> dict:
    """Get detailed information about a service including recent deployments."""

    variables = {"serviceId": service_id}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": service_details_query, "variables": variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        return data["data"]["service"]
```

### Update Environment Variables

```python
update_env_vars_mutation = """
mutation UpdateVariables($serviceId: String!, $environmentId: String!, $variables: String!) {
  variableCollectionUpsert(
    input: {
      serviceId: $serviceId
      environmentId: $environmentId
      variables: $variables
    }
  )
}
"""

async def update_environment_variables(
    service_id: str,
    environment_id: str,
    variables: dict,
    token: str
):
    """
    Update environment variables for a service.

    Args:
        service_id: Railway service ID
        environment_id: Railway environment ID
        variables: Dict of environment variable key-value pairs
        token: Railway API token
    """

    # Convert dict to Railway's expected format
    variables_str = "\n".join([f"{key}={value}" for key, value in variables.items()])

    mutation_variables = {
        "serviceId": service_id,
        "environmentId": environment_id,
        "variables": variables_str
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": update_env_vars_mutation, "variables": mutation_variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        if "errors" in data:
            raise Exception(f"Failed to update env vars: {data['errors']}")

        return data["data"]["variableCollectionUpsert"]
```

---

## Logs and Monitoring

### Viewing Logs via CLI

For local/script usage:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# View logs (requires being in project directory or linking)
railway logs --deployment <deployment-id>
railway logs --service <service-id>

# Build logs only
railway logs --build

# Real-time streaming
railway logs --follow
```

### Logs via API (Discovery Required)

**Current Status:** The GraphQL schema includes deployment logs, but the exact query structure requires introspection.

**Discovery Process:**

1. Use GraphiQL playground at `https://backboard.railway.com/graphql/v2`
2. Search schema for "logs" or "deploymentLogs"
3. Alternative: Monitor Network tab in Railway dashboard while viewing logs

**Expected Query Structure:**

```python
# This is a hypothetical structure - verify via introspection
deployment_logs_query = """
query DeploymentLogs($deploymentId: String!, $limit: Int) {
  deployment(id: $deploymentId) {
    id
    logs(limit: $limit) {
      message
      timestamp
      severity
    }
  }
}
"""
```

**Recommended Approach for Production:**

Since direct log streaming via GraphQL is not well-documented, use Railway CLI programmatically:

```python
import subprocess
import json

async def get_deployment_logs(deployment_id: str, follow: bool = False) -> str:
    """
    Get deployment logs using Railway CLI.

    Args:
        deployment_id: Railway deployment ID
        follow: If True, stream logs in real-time

    Returns:
        Log output as string
    """
    cmd = ["railway", "logs", "--deployment", deployment_id]

    if follow:
        cmd.append("--follow")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if follow:
            # Stream logs
            for line in process.stdout:
                yield line.strip()
        else:
            # Get all logs at once
            stdout, stderr = process.communicate()
            return stdout

    except Exception as e:
        raise Exception(f"Failed to fetch logs: {e}")
```

### Webhooks for Real-Time Updates

Railway supports webhooks for deployment status changes:

```python
webhook_create_mutation = """
mutation CreateWebhook($projectId: String!, $url: String!) {
  webhookCreate(
    input: {
      projectId: $projectId
      url: $url
    }
  ) {
    id
    url
  }
}
"""

async def create_webhook(project_id: str, webhook_url: str, token: str):
    """
    Create a webhook to receive deployment status updates.

    Webhook payload will be sent when:
    - Deployment status changes
    - Service alert triggers
    """

    variables = {
        "projectId": project_id,
        "url": webhook_url
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": webhook_create_mutation, "variables": variables},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        return data["data"]["webhookCreate"]
```

**Webhook Payload Example:**

```json
{
  "type": "DEPLOY",
  "status": "SUCCESS",
  "project": {
    "id": "project-id",
    "name": "project-name"
  },
  "environment": {
    "id": "env-id",
    "name": "production"
  },
  "deployment": {
    "id": "deployment-id",
    "status": "SUCCESS",
    "url": "https://..."
  },
  "timestamp": "2026-01-12T20:00:00Z"
}
```

### Service Metrics (Observability)

Railway provides real-time metrics through the dashboard:
- CPU usage
- Memory usage
- Disk usage
- Network traffic (ingress/egress)
- Up to 30 days of historical data

**API Access:** Use GraphiQL introspection to discover metrics queries, or monitor dashboard Network tab.

---

## Python Implementation

### Using httpx (Recommended)

```python
import httpx
import asyncio
from typing import Optional, Dict, Any

class RailwayClient:
    """Async Railway GraphQL API client using httpx."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://backboard.railway.com/graphql/v2"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query or mutation.

        Args:
            query: GraphQL query or mutation string
            variables: Optional variables dict

        Returns:
            Response data dict

        Raises:
            Exception: If GraphQL errors occur
        """
        # Add timestamp query param to avoid Cloudflare rate limiting
        import time
        url = f"{self.base_url}?t={int(time.time())}"

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self.headers
            )

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")

            return data.get("data", {})
```

### Using gql (Alternative)

```python
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

class RailwayClientGQL:
    """Railway GraphQL API client using gql library."""

    def __init__(self, api_token: str):
        transport = AIOHTTPTransport(
            url="https://backboard.railway.com/graphql/v2",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
        )

        self.client = Client(
            transport=transport,
            fetch_schema_from_transport=True
        )

    async def execute(self, query_string: str, variables: dict = None):
        """Execute GraphQL query."""
        query = gql(query_string)

        async with self.client as session:
            result = await session.execute(
                query,
                variable_values=variables
            )
            return result
```

---

## Error Handling

### Common Error Scenarios

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RailwayAPIError(Exception):
    """Base exception for Railway API errors."""
    pass

class RailwayAuthenticationError(RailwayAPIError):
    """Authentication failed."""
    pass

class RailwayRateLimitError(RailwayAPIError):
    """Rate limit exceeded."""
    pass

class RailwayDeploymentError(RailwayAPIError):
    """Deployment operation failed."""
    pass

async def execute_with_error_handling(
    query: str,
    variables: dict,
    token: str
) -> Optional[dict]:
    """Execute GraphQL query with comprehensive error handling."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://backboard.railway.com/graphql/v2?t={int(time.time())}",
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {token}"}
            )

            # HTTP-level errors
            if response.status_code == 401:
                raise RailwayAuthenticationError("Invalid or expired token")

            if response.status_code == 429:
                raise RailwayRateLimitError("Rate limit exceeded")

            if response.status_code == 503:
                logger.warning("Railway API temporarily unavailable, retrying...")
                await asyncio.sleep(5)
                return await execute_with_error_handling(query, variables, token)

            response.raise_for_status()

            # GraphQL-level errors
            data = response.json()

            if "errors" in data:
                errors = data["errors"]
                error_messages = [e.get("message", str(e)) for e in errors]
                logger.error(f"GraphQL errors: {error_messages}")
                raise RailwayAPIError(f"GraphQL errors: {error_messages}")

            return data.get("data")

    except httpx.TimeoutException:
        logger.error("Request timed out")
        raise RailwayAPIError("Request timed out after 30s")

    except httpx.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        raise RailwayAPIError(f"HTTP error: {e}")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise RailwayAPIError(f"Unexpected error: {e}")
```

---

## Complete Python Client

```python
"""
Railway GraphQL API Client - Production-Ready Implementation

Usage:
    from railway_client import RailwayClient

    client = RailwayClient(api_token="your-token")

    # Trigger deployment
    deployment_id = await client.trigger_deployment(
        project_id="proj-123",
        environment_id="env-456",
        service_id="svc-789"
    )

    # Wait for completion
    result = await client.wait_for_deployment(deployment_id, timeout=600)
"""

import httpx
import asyncio
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DeploymentStatus:
    """Deployment status information."""
    id: str
    status: str
    static_url: Optional[str]
    created_at: str
    updated_at: str
    meta: Optional[Dict[str, Any]] = None


class RailwayClient:
    """
    Production-ready Railway GraphQL API client.

    Features:
    - Async operations with httpx
    - Automatic rate limit handling
    - Comprehensive error handling
    - Type hints
    - Logging

    Example:
        >>> client = RailwayClient(api_token="your-token")
        >>> deployment_id = await client.trigger_deployment(...)
        >>> status = await client.wait_for_deployment(deployment_id)
    """

    def __init__(self, api_token: str):
        """
        Initialize Railway API client.

        Args:
            api_token: Railway API token from GCP Secret Manager
        """
        self.api_token = api_token
        self.base_url = "https://backboard.railway.com/graphql/v2"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute GraphQL query with retry logic.

        Args:
            query: GraphQL query or mutation
            variables: Optional variables dict
            max_retries: Maximum number of retries for rate limits

        Returns:
            Response data dict

        Raises:
            RailwayAPIError: On API errors
        """
        for attempt in range(max_retries):
            try:
                # Add timestamp to avoid Cloudflare rate limiting
                url = f"{self.base_url}?t={int(time.time())}"

                payload = {"query": query}
                if variables:
                    payload["variables"] = variables

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=self.headers
                    )

                    if response.status_code == 429:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    if "errors" in data:
                        raise RailwayAPIError(f"GraphQL errors: {data['errors']}")

                    return data.get("data", {})

            except httpx.HTTPStatusError as e:
                if attempt == max_retries - 1:
                    raise RailwayAPIError(f"HTTP error after {max_retries} attempts: {e}")
                await asyncio.sleep(2 ** attempt)

        raise RailwayAPIError(f"Failed after {max_retries} attempts")

    async def trigger_deployment(
        self,
        environment_id: str,
        service_id: str
    ) -> str:
        """
        Trigger a new deployment.

        Args:
            environment_id: Railway environment ID
            service_id: Railway service ID

        Returns:
            Deployment ID
        """
        mutation = """
        mutation DeployService($environmentId: String!, $serviceId: String!) {
          serviceInstanceDeploy(
            environmentId: $environmentId
            serviceId: $serviceId
          )
        }
        """

        variables = {
            "environmentId": environment_id,
            "serviceId": service_id
        }

        data = await self.execute(mutation, variables)
        deployment_id = data["serviceInstanceDeploy"]

        logger.info(f"Triggered deployment: {deployment_id}")
        return deployment_id

    async def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        """
        Get deployment status.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            DeploymentStatus object
        """
        query = """
        query DeploymentStatus($deploymentId: String!) {
          deployment(id: $deploymentId) {
            id
            status
            staticUrl
            createdAt
            updatedAt
            meta
          }
        }
        """

        variables = {"deploymentId": deployment_id}
        data = await self.execute(query, variables)
        deployment = data["deployment"]

        return DeploymentStatus(
            id=deployment["id"],
            status=deployment["status"],
            static_url=deployment.get("staticUrl"),
            created_at=deployment["createdAt"],
            updated_at=deployment["updatedAt"],
            meta=deployment.get("meta")
        )

    async def wait_for_deployment(
        self,
        deployment_id: str,
        timeout: int = 600,
        poll_interval: int = 5
    ) -> DeploymentStatus:
        """
        Wait for deployment to complete.

        Args:
            deployment_id: Railway deployment ID
            timeout: Maximum wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Final DeploymentStatus

        Raises:
            TimeoutError: If deployment exceeds timeout
            RailwayDeploymentError: If deployment fails
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(
                    f"Deployment {deployment_id} timed out after {timeout}s"
                )

            status = await self.get_deployment_status(deployment_id)
            logger.info(f"Deployment status: {status.status}")

            if status.status == "SUCCESS":
                logger.info(f"Deployment succeeded: {status.static_url}")
                return status

            if status.status in ["FAILED", "CRASHED", "REMOVED"]:
                raise RailwayDeploymentError(
                    f"Deployment failed with status: {status.status}"
                )

            await asyncio.sleep(poll_interval)

    async def restart_deployment(self, deployment_id: str) -> bool:
        """
        Restart a deployment.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            True if successful
        """
        mutation = """
        mutation RestartDeployment($deploymentId: String!) {
          deploymentRestart(id: $deploymentId)
        }
        """

        variables = {"deploymentId": deployment_id}
        await self.execute(mutation, variables)

        logger.info(f"Restarted deployment: {deployment_id}")
        return True

    async def rollback_deployment(self, previous_deployment_id: str) -> str:
        """
        Rollback to a previous deployment.

        Args:
            previous_deployment_id: ID of previous successful deployment

        Returns:
            New deployment ID
        """
        mutation = """
        mutation RollbackDeployment($deploymentId: String!) {
          serviceInstanceRedeploy(deploymentId: $deploymentId)
        }
        """

        variables = {"deploymentId": previous_deployment_id}
        data = await self.execute(mutation, variables)

        new_deployment_id = data["serviceInstanceRedeploy"]
        logger.info(f"Rolled back to deployment: {previous_deployment_id}, new ID: {new_deployment_id}")

        return new_deployment_id

    async def list_services(
        self,
        project_id: str,
        environment_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all services in a project environment.

        Args:
            project_id: Railway project ID
            environment_id: Railway environment ID

        Returns:
            List of service dicts
        """
        query = """
        query ListServices($projectId: String!, $environmentId: String!) {
          project(id: $projectId) {
            services(environmentId: $environmentId) {
              edges {
                node {
                  id
                  name
                  icon
                  createdAt
                }
              }
            }
          }
        }
        """

        variables = {
            "projectId": project_id,
            "environmentId": environment_id
        }

        data = await self.execute(query, variables)
        edges = data["project"]["services"]["edges"]

        return [edge["node"] for edge in edges]


# Exception classes
class RailwayAPIError(Exception):
    """Base Railway API error."""
    pass


class RailwayDeploymentError(RailwayAPIError):
    """Deployment operation failed."""
    pass
```

---

## Sources

- [Railway Public API Documentation](https://docs.railway.com/reference/public-api)
- [Use the Public API Guide](https://docs.railway.com/guides/public-api)
- [Manage Deployments with Public API](https://docs.railway.com/guides/manage-deployments)
- [Railway GraphQL API Postman Collection](https://www.postman.com/railway-4865/railway/documentation/adgthpg/railway-graphql-api)
- [Viewing Logs Documentation](https://docs.railway.com/guides/logs)
- [Deployments Reference](https://docs.railway.com/reference/deployments)
- [Webhooks Guide](https://docs.railway.com/guides/webhooks)
- [Railway API Rate Limiting Discussion](https://station.railway.com/questions/frequent-graph-ql-api-rate-limiting-erro-d4316760)
- [GraphQL Introspection](https://graphql.org/learn/introspection/)
- [gql Python Library](https://github.com/graphql-python/gql)

---

## Next Steps

1. Store Railway API token in GCP Secret Manager
2. Test connection with introspection query
3. Implement deployment monitoring in Claude agent
4. Set up webhooks for real-time updates
5. Create dashboards for observability metrics

**Last Updated:** 2026-01-12
