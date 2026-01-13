# Railway GraphQL API Client

Complete async client for Railway's GraphQL API with autonomous deployment management capabilities.

## Overview

The `RailwayClient` class provides async access to Railway's infrastructure management via GraphQL, implementing:

- **Cloudflare workaround** - Timestamp query parameter prevents rate limiting
- **Exponential backoff retry** - Handles transient failures with Tenacity
- **State machine monitoring** - Tracks deployments through lifecycle (INITIALIZING → ACTIVE/FAILED)
- **Rollback capability** - Recovery mechanism for failed deployments
- **Log retrieval** - Build and runtime logs for debugging
- **Environment management** - Dynamic configuration updates

## Installation

```python
from src.secrets_manager import SecretManager
from src.railway_client import RailwayClient

# Initialize with token from GCP Secret Manager
manager = SecretManager()
token = manager.get_secret("RAILWAY-API")
client = RailwayClient(api_token=token)
```

## Class Reference

### RailwayClient

```python
class RailwayClient:
    """Async client for Railway GraphQL API."""

    def __init__(self, api_token: str):
        """Initialize Railway API client.

        Args:
            api_token: Railway API token from GCP Secret Manager
        """
```

## Deployment Operations

### trigger_deployment()

Trigger a new deployment for a service.

```python
async def trigger_deployment(
    self,
    environment_id: str,
    service_id: str
) -> str:
    """Trigger a new deployment.

    Args:
        environment_id: Railway environment ID
        service_id: Railway service ID

    Returns:
        New deployment ID

    Raises:
        RailwayAPIError: If deployment trigger fails
    """
```

**Example:**

```python
deployment_id = await client.trigger_deployment(
    environment_id="99c99a18-aea2-4d01-9360-6a93705102a0",
    service_id="svc-456"
)
print(f"Deployment initiated: {deployment_id}")
```

**Use Case:** Agent detects new commit on main branch → trigger deployment.

---

### get_deployment_status()

Get current deployment status.

```python
async def get_deployment_status(self, deployment_id: str) -> str:
    """Get current deployment status.

    Args:
        deployment_id: Railway deployment ID

    Returns:
        Status string (INITIALIZING, BUILDING, DEPLOYING, ACTIVE,
                      FAILED, CRASHED, REMOVED)
    """
```

**Example:**

```python
status = await client.get_deployment_status("deploy-123")
print(f"Status: {status}")
```

**Use Case:** Agent polls this during monitoring phase.

---

### get_deployment_details()

Get full deployment details including metadata.

```python
async def get_deployment_details(
    self,
    deployment_id: str
) -> DeploymentStatus:
    """Get full deployment details (status + metadata).

    Args:
        deployment_id: Railway deployment ID

    Returns:
        DeploymentStatus object with all details
    """
```

**DeploymentStatus Dataclass:**

```python
@dataclass
class DeploymentStatus:
    """Deployment status information."""
    id: str
    status: str
    static_url: Optional[str]
    created_at: str
    updated_at: str
    meta: Optional[Dict[str, Any]] = None
```

**Example:**

```python
details = await client.get_deployment_details("deploy-123")
print(f"Status: {details.status}")
print(f"URL: {details.static_url}")
print(f"Created: {details.created_at}")
```

---

### rollback_deployment()

Rollback to a previous stable deployment.

```python
async def rollback_deployment(self, deployment_id: str) -> str:
    """Rollback to a previous deployment.

    CRITICAL: This is the agent's primary recovery mechanism.
    Use when current deployment has status FAILED or CRASHED.

    Args:
        deployment_id: ID of stable deployment to rollback to

    Returns:
        New deployment ID

    Raises:
        RailwayAPIError: If rollback fails
    """
```

**Example:**

```python
# Current deployment failed
last_stable = await client.get_last_active_deployment(
    project_id="proj-123",
    environment_id="env-456"
)

if last_stable:
    rollback_id = await client.rollback_deployment(last_stable["id"])
    print(f"Rolled back to: {rollback_id}")
```

**Use Case:** Current deployment failed → agent automatically rolls back to last known good state.

---

### get_last_active_deployment()

Find the last successful (ACTIVE) deployment.

```python
async def get_last_active_deployment(
    self,
    project_id: str,
    environment_id: str
) -> Optional[Dict[str, Any]]:
    """Get the last successful (ACTIVE) deployment.

    Args:
        project_id: Railway project ID
        environment_id: Railway environment ID

    Returns:
        Deployment info dict or None if no ACTIVE deployment exists
    """
```

**Example:**

```python
last_stable = await client.get_last_active_deployment(
    project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
    environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
)

if last_stable:
    print(f"Last stable: {last_stable['id']} at {last_stable['createdAt']}")
else:
    print("No stable deployment found")
```

---

## Monitoring & Logs

### get_build_logs()

Retrieve build logs for debugging failed deployments.

```python
async def get_build_logs(
    self,
    deployment_id: str,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Retrieve build logs for debugging.

    Args:
        deployment_id: Railway deployment ID
        limit: Max number of log lines

    Returns:
        List of log entries with:
        - message: Log line text
        - timestamp: When logged
        - severity: ERROR, INFO, WARN
    """
```

**Example:**

```python
logs = await client.get_build_logs("deploy-123", limit=50)

# Find errors
errors = [log for log in logs if log["severity"] == "ERROR"]
if errors:
    print(f"Build error: {errors[0]['message']}")
```

**Use Case:** Deployment FAILED → agent reads logs to identify error.

---

### get_runtime_logs()

Retrieve runtime logs (stdout/stderr).

```python
async def get_runtime_logs(
    self,
    deployment_id: str,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Retrieve runtime logs (stdout/stderr).

    Args:
        deployment_id: Railway deployment ID
        limit: Max number of log lines

    Returns:
        List of log entries with message, timestamp, severity
    """
```

**Example:**

```python
logs = await client.get_runtime_logs("deploy-123")

for log in logs:
    print(f"{log['timestamp']}: {log['message']}")
```

**Use Case:** Deployment CRASHED → agent reads logs to identify exception.

---

### get_deployment_metrics()

Get resource utilization metrics.

```python
async def get_deployment_metrics(
    self,
    deployment_id: str
) -> Dict[str, Any]:
    """Get resource utilization metrics.

    Args:
        deployment_id: Railway deployment ID

    Returns:
        Dictionary with:
        - cpu_usage: CPU percentage
        - memory_usage: RAM in MB
        - request_count: HTTP requests
        - response_time: Avg latency in ms
    """
```

**Example:**

```python
metrics = await client.get_deployment_metrics("deploy-123")

print(f"CPU: {metrics['cpuUsage']}%")
print(f"Memory: {metrics['memoryUsage']} MB")
print(f"Requests: {metrics['requestCount']}")
print(f"Avg latency: {metrics['responseTime']} ms")
```

**Use Case:** Agent detects performance degradation → scales resources.

---

## Autonomous Monitoring

### monitor_deployment_until_stable()

Monitor deployment until it reaches a stable state.

```python
async def monitor_deployment_until_stable(
    self,
    deployment_id: str,
    timeout_seconds: int = 600,
    poll_interval: int = 5
) -> str:
    """Monitor deployment until it reaches a stable state.

    Implements the State Machine monitoring logic:
    - Stable States: ACTIVE (success), FAILED (build error),
                    CRASHED (runtime error)
    - Transient States: INITIALIZING, BUILDING, DEPLOYING (keep polling)

    Args:
        deployment_id: Deployment to monitor
        timeout_seconds: Max time to wait (default: 10 minutes)
        poll_interval: Seconds between status checks

    Returns:
        Final status (ACTIVE, FAILED, or CRASHED)

    Raises:
        TimeoutError: If deployment doesn't stabilize in time
    """
```

**Example:**

```python
deployment_id = await client.trigger_deployment(
    environment_id="env-123",
    service_id="svc-456"
)

# Monitor until stable
final_status = await client.monitor_deployment_until_stable(
    deployment_id,
    timeout_seconds=600
)

if final_status == "ACTIVE":
    print("✅ Deployment successful!")
elif final_status == "FAILED":
    logs = await client.get_build_logs(deployment_id)
    print(f"❌ Build failed: {logs[-1]['message']}")
elif final_status == "CRASHED":
    logs = await client.get_runtime_logs(deployment_id)
    print(f"❌ Runtime crashed: {logs[-1]['message']}")
```

**State Machine:**

```
INITIALIZING → BUILDING → DEPLOYING → ACTIVE (success)
                  ↓           ↓
                FAILED      CRASHED
```

---

## Service Management

### list_services()

List all services in a project environment.

```python
async def list_services(
    self,
    project_id: str,
    environment_id: str
) -> List[Dict[str, Any]]:
    """List all services in a project environment.

    Args:
        project_id: Railway project ID
        environment_id: Railway environment ID

    Returns:
        List of service dicts with id, name, icon, createdAt
    """
```

**Example:**

```python
services = await client.list_services(
    project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
    environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
)

for service in services:
    print(f"{service['name']}: {service['id']}")
```

---

### get_service_details()

Get detailed information about a service.

```python
async def get_service_details(self, service_id: str) -> Dict[str, Any]:
    """Get detailed information about a service.

    Args:
        service_id: Railway service ID

    Returns:
        Service details dict with deployments list
    """
```

**Example:**

```python
details = await client.get_service_details("svc-123")

print(f"Service: {details['name']}")
print(f"Created: {details['createdAt']}")
print(f"Recent deployments: {len(details['deployments'])}")

for deployment in details['deployments']:
    print(f"  - {deployment['id']}: {deployment['status']}")
```

---

## Environment Variables

### set_environment_variable()

Set an environment variable dynamically.

```python
async def set_environment_variable(
    self,
    service_id: str,
    environment_id: str,
    key: str,
    value: str
) -> None:
    """Set an environment variable.

    Args:
        service_id: Railway service ID
        environment_id: Railway environment ID
        key: Variable name
        value: Variable value

    Security:
        Never log the value parameter.
    """
```

**Example:**

```python
await client.set_environment_variable(
    service_id="svc-123",
    environment_id="env-456",
    key="MAX_WORKERS",
    value="4"
)

print("Environment variable updated")
```

**Use Case:** Agent updates configuration dynamically based on load.

---

## Exception Classes

### RailwayAPIError

Base exception for all Railway API errors.

```python
class RailwayAPIError(Exception):
    """Base exception for Railway API errors."""
    pass
```

### RailwayAuthenticationError

Authentication failed (invalid or expired token).

```python
class RailwayAuthenticationError(RailwayAPIError):
    """Authentication failed (invalid or expired token)."""
    pass
```

**Example:**

```python
try:
    await client.trigger_deployment(...)
except RailwayAuthenticationError:
    # Token expired, fetch new token
    token = manager.get_secret("RAILWAY-API", use_cache=False)
    client = RailwayClient(api_token=token)
```

### RailwayRateLimitError

Rate limit exceeded.

```python
class RailwayRateLimitError(RailwayAPIError):
    """Rate limit exceeded."""
    pass
```

### RailwayDeploymentError

Deployment operation failed.

```python
class RailwayDeploymentError(RailwayAPIError):
    """Deployment operation failed."""
    pass
```

---

## Complete Example: Autonomous Deployment

Full example of autonomous deployment with monitoring and rollback:

```python
import asyncio
from src.secrets_manager import SecretManager
from src.railway_client import RailwayClient, RailwayDeploymentError

async def autonomous_deployment():
    """Autonomous deployment with monitoring and rollback."""

    # Initialize client
    manager = SecretManager()
    token = manager.get_secret("RAILWAY-API")
    client = RailwayClient(api_token=token)

    # Configuration
    project_id = "95ec21cc-9ada-41c5-8485-12f9a00e0116"
    environment_id = "99c99a18-aea2-4d01-9360-6a93705102a0"
    service_id = "svc-456"

    try:
        # 1. Trigger deployment
        print("🚀 Triggering deployment...")
        deployment_id = await client.trigger_deployment(
            environment_id=environment_id,
            service_id=service_id
        )
        print(f"  Deployment ID: {deployment_id}")

        # 2. Monitor until stable
        print("⏳ Monitoring deployment...")
        final_status = await client.monitor_deployment_until_stable(
            deployment_id,
            timeout_seconds=600,
            poll_interval=5
        )

        # 3. Handle result
        if final_status == "ACTIVE":
            print("✅ Deployment successful!")
            details = await client.get_deployment_details(deployment_id)
            print(f"  URL: {details.static_url}")

        elif final_status == "FAILED":
            print("❌ Build failed, rolling back...")

            # Get build logs
            logs = await client.get_build_logs(deployment_id, limit=20)
            errors = [log for log in logs if log["severity"] == "ERROR"]
            print(f"  Error: {errors[0]['message'] if errors else 'Unknown'}")

            # Rollback
            last_stable = await client.get_last_active_deployment(
                project_id=project_id,
                environment_id=environment_id
            )

            if last_stable:
                rollback_id = await client.rollback_deployment(last_stable["id"])
                print(f"  Rolled back to: {rollback_id}")

                # Monitor rollback
                rollback_status = await client.monitor_deployment_until_stable(
                    rollback_id
                )
                print(f"  Rollback status: {rollback_status}")

        elif final_status == "CRASHED":
            print("❌ Runtime crashed, rolling back...")

            # Get runtime logs
            logs = await client.get_runtime_logs(deployment_id, limit=20)
            print(f"  Last log: {logs[-1]['message']}")

            # Rollback (same as FAILED case)
            last_stable = await client.get_last_active_deployment(
                project_id=project_id,
                environment_id=environment_id
            )

            if last_stable:
                rollback_id = await client.rollback_deployment(last_stable["id"])
                print(f"  Rolled back to: {rollback_id}")

    except TimeoutError:
        print("⏰ Deployment timed out after 10 minutes")
    except RailwayDeploymentError as e:
        print(f"❌ Deployment error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

# Run
asyncio.run(autonomous_deployment())
```

---

## Production Configuration

**Current Deployment** (project38-or):

| Setting | Value |
|---------|-------|
| Project | delightful-cat |
| Project ID | `95ec21cc-9ada-41c5-8485-12f9a00e0116` |
| Environment | production |
| Environment ID | `99c99a18-aea2-4d01-9360-6a93705102a0` |
| Public URL | https://or-infra.com |
| Health Check | `/api/health` endpoint |

---

## Security Considerations

1. **API Token Storage**:
   - ✅ Token stored in GCP Secret Manager (never in code)
   - ✅ Retrieved at runtime via WIF
   - ✅ Never logged or printed

2. **Environment Variables**:
   - ✅ `set_environment_variable()` never logs the value
   - ❌ Never set secrets via Railway API (use GCP Secret Manager instead)

3. **GraphQL Injection**:
   - ✅ All variables passed via `variables` parameter (GraphQL sanitizes automatically)
   - ❌ Never construct queries with f-strings

---

## Cloudflare Workaround

**Critical Discovery:** Railway's Cloudflare configuration blocks GraphQL requests without query parameters, returning Error 1015 "You are being rate limited."

**Solution:**

```python
def _build_url(self) -> str:
    """Build GraphQL URL with Cloudflare workaround.

    CRITICAL: Railway's Cloudflare blocks requests without query params.
    Adding ?t={timestamp} prevents Error 1015.
    """
    return f"{self.base_url}?t={int(time.time())}"
```

**Why this works:** Cloudflare sees each request as unique due to timestamp, preventing false-positive rate limiting.

---

## Related Documentation

- [Railway Integration (Hybrid)](../autonomous/02-railway-integration-hybrid.md) - Complete Railway integration guide
- [Railway API Guide](../integrations/railway-api-guide.md) - Original research document
- [Implementation Roadmap](../integrations/implementation-roadmap.md) - 7-day development plan

---

## Module Source

**File:** `src/railway_client.py`
**Tests:** `tests/test_railway_client.py`
**Dependencies:** `httpx`, `tenacity`
