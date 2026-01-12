# Railway Integration: Infrastructure as Autonomous Domain

## Overview

Railway serves as the **Body** of the autonomous system - the physical infrastructure where code runs, deployments happen, and services live. This document details complete integration from GraphQL API authentication to autonomous deployment lifecycle management.

---

## The Railway Deployment Lifecycle

Understanding Railway's deployment lifecycle is critical for autonomous operation. Each deployment transitions through a **finite state machine** with deterministic rules.

### The Deployment State Machine

```
┌──────────────┐
│ TRIGGER API  │ (Agent initiates deployment)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ INITIALIZING │ ← Railway receives request, allocates resources
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   BUILDING   │ ← Docker image build (Nixpacks or Dockerfile)
└──────┬───────┘
       │
       ├──[Build Success]──┐
       │                   │
       │                   ▼
       │            ┌──────────────┐
       │            │  DEPLOYING   │ ← Container starting, health checks
       │            └──────┬───────┘
       │                   │
       │                   ├──[Health Check Pass]─┐
       │                   │                       │
       │                   │                       ▼
       │                   │                ┌─────────────┐
       │                   │                │   ACTIVE    │ ← Success
       │                   │                └─────────────┘
       │                   │
       │                   └──[Health Check Fail]─┐
       │                                           │
       │                                           ▼
       │                                    ┌─────────────┐
       │                                    │   CRASHED   │ ← Runtime error
       │                                    └─────────────┘
       │
       └──[Build Failure]────────────────┐
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │   FAILED    │ ← Build error
                                  └─────────────┘
```

---

### State Transition Rules

**Agent Decision Logic** for each state:

| Current State | Expected Duration | Agent Action | Rationale |
|---------------|-------------------|--------------|-----------|
| **INITIALIZING** | 5-10 seconds | Poll every 5s | Waiting for Railway resource allocation |
| **BUILDING** | 30-300 seconds | Monitor build logs | Detect syntax errors, missing deps early |
| **DEPLOYING** | 10-60 seconds | Monitor health checks | Detect crashloop, port binding issues |
| **ACTIVE** | Indefinite | Monitor metrics | Service is healthy, watch for degradation |
| **FAILED** | Terminal | Parse logs → Rollback OR Fix | Build failed (syntax error, missing file) |
| **CRASHED** | Terminal | Analyze runtime logs → Restart OR Rollback | Runtime error (OOM, uncaught exception) |

**Critical Insight**: FAILED vs CRASHED requires different strategies:
- **FAILED** = code won't build → likely needs human intervention (syntax error)
- **CRASHED** = code built but won't run → may be transient (OOM, timeout) → retry first

---

## Railway GraphQL API: Complete Reference

Railway exposes all functionality via a GraphQL API at `https://backboard.railway.com/graphql/v2`.

### Authentication

**Token Type**: Railway API Token (from GCP Secret Manager: `RAILWAY-API`)

**Header Format**:
```
Authorization: Bearer <token>
```

### Critical Discovery: Cloudflare Workaround

⚠️ **Railway's Cloudflare configuration blocks GraphQL requests without query parameters**, returning Error 1015 "You are being rate limited."

**Solution** (verified in production):
```python
def _build_url(self) -> str:
    """Build GraphQL URL with Cloudflare workaround.

    CRITICAL: Railway's Cloudflare blocks requests without query params.
    Adding ?t={timestamp} prevents Error 1015.
    """
    return f"{self.base_url}?t={int(time.time())}"
```

**Why this works**: Cloudflare sees each request as unique due to timestamp, preventing false-positive rate limiting.

---

## Production-Ready RailwayClient

Complete implementation with all autonomous capabilities:

```python
"""Railway GraphQL API client for autonomous deployment management."""
import time
import asyncio
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

class RailwayClient:
    """Async client for Railway GraphQL API.

    Implements autonomous deployment management with:
    - Cloudflare workaround (timestamp query param)
    - Exponential backoff retry (transient failures)
    - State machine monitoring (INITIALIZING → ACTIVE/FAILED)
    - Rollback capability (recovery mechanism)
    - Log retrieval (debugging)
    """

    def __init__(self, api_token: str):
        """Initialize Railway client.

        Args:
            api_token: Railway API token from GCP Secret Manager
        """
        self.api_token = api_token
        self.base_url = "https://backboard.railway.com/graphql/v2"

    def _build_url(self) -> str:
        """Build GraphQL URL with Cloudflare workaround."""
        return f"{self.base_url}?t={int(time.time())}"

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        reraise=True
    )
    async def _execute_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL query with retry logic.

        Retry strategy:
        - Attempt 1: immediate
        - Attempt 2: wait 4s
        - Attempt 3: wait 8s
        - Attempt 4: wait 16s
        - Attempt 5: wait 32s
        - Attempt 6+: wait 60s (max)

        Args:
            query: GraphQL query or mutation
            variables: Query variables

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: If all retries fail
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._build_url(),
                json={"query": query, "variables": variables or {}},
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    # =========================================================================
    # DEPLOYMENT OPERATIONS
    # =========================================================================

    async def trigger_deployment(
        self,
        project_id: str,
        environment_id: str = "production"
    ) -> str:
        """Trigger a new deployment.

        Use Case: Agent detects new commit on main branch → trigger deployment.

        Args:
            project_id: Railway project ID (e.g., "95ec21cc-9ada-41c5-8485-12f9a00e0116")
            environment_id: Environment ID (default: production)

        Returns:
            New deployment ID

        Example:
            >>> client = RailwayClient(api_token)
            >>> deployment_id = await client.trigger_deployment(
            ...     project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
            ...     environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
            ... )
            >>> print(f"Deployment initiated: {deployment_id}")
        """
        mutation = """
        mutation DeploymentTrigger($projectId: String!, $environmentId: String!) {
          deploymentTrigger(
            input: { projectId: $projectId, environmentId: $environmentId }
          ) {
            id
            status
            createdAt
          }
        }
        """
        result = await self._execute_graphql(
            mutation,
            {"projectId": project_id, "environmentId": environment_id}
        )
        return result["data"]["deploymentTrigger"]["id"]

    async def get_deployment_status(self, deployment_id: str) -> str:
        """Get current deployment status.

        Use Case: Agent polls this during monitoring phase.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            Status string (INITIALIZING, BUILDING, DEPLOYING, ACTIVE,
                         FAILED, CRASHED, REMOVED)
        """
        query = """
        query GetDeployment($id: String!) {
          deployment(id: $id) {
            id
            status
            createdAt
            updatedAt
          }
        }
        """
        result = await self._execute_graphql(query, {"id": deployment_id})
        return result["data"]["deployment"]["status"]

    async def get_deployment_details(self, deployment_id: str) -> Dict[str, Any]:
        """Get full deployment details (status + metadata).

        Use Case: Agent needs context for decision-making (git commit, URL, etc.)

        Returns:
            Dictionary with:
            - status: Current state
            - createdAt: Timestamp
            - updatedAt: Last change
            - meta: Additional metadata
        """
        query = """
        query GetDeploymentDetails($id: String!) {
          deployment(id: $id) {
            id
            status
            createdAt
            updatedAt
            meta
            url
          }
        }
        """
        result = await self._execute_graphql(query, {"id": deployment_id})
        return result["data"]["deployment"]

    async def rollback_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Rollback to a previous deployment.

        CRITICAL: This is the agent's primary recovery mechanism.
        Use when current deployment has status FAILED or CRASHED.

        How it works:
        1. Railway finds last ACTIVE deployment
        2. Creates new deployment from that version
        3. Returns new deployment ID

        Args:
            deployment_id: ID of stable deployment to rollback to

        Returns:
            New deployment info (id, status, createdAt)

        Example:
            >>> # Current deployment failed
            >>> last_stable = await client.get_last_active_deployment(project_id)
            >>> rollback = await client.rollback_deployment(last_stable["id"])
            >>> print(f"Rolled back to: {rollback['id']}")
        """
        mutation = """
        mutation DeploymentRollback($id: String!) {
          deploymentRollback(id: $id) {
            id
            status
            createdAt
          }
        }
        """
        result = await self._execute_graphql(mutation, {"id": deployment_id})
        return result["data"]["deploymentRollback"]

    async def get_last_active_deployment(
        self,
        project_id: str,
        environment_id: str = "production"
    ) -> Optional[Dict[str, Any]]:
        """Get the last successful (ACTIVE) deployment.

        Use Case: Find stable version to rollback to.

        Returns:
            Deployment info or None if no ACTIVE deployment exists
        """
        query = """
        query GetDeployments($projectId: String!, $environmentId: String!) {
          deployments(
            input: { projectId: $projectId, environmentId: $environmentId }
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
        """
        result = await self._execute_graphql(
            query,
            {"projectId": project_id, "environmentId": environment_id}
        )

        deployments = result["data"]["deployments"]["edges"]
        for edge in deployments:
            if edge["node"]["status"] == "ACTIVE":
                return edge["node"]

        return None

    # =========================================================================
    # MONITORING & LOGS
    # =========================================================================

    async def get_build_logs(
        self,
        deployment_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve build logs for debugging.

        Use Case: Deployment FAILED → agent reads logs to identify error.

        Args:
            deployment_id: Railway deployment ID
            limit: Max number of log lines

        Returns:
            List of log entries with:
            - message: Log line text
            - timestamp: When logged
            - severity: ERROR, INFO, WARN

        Example:
            >>> logs = await client.get_build_logs(deployment_id)
            >>> errors = [log for log in logs if log["severity"] == "ERROR"]
            >>> if errors:
            ...     print(f"Build errors found: {errors[0]['message']}")
        """
        query = """
        query BuildLogs($deploymentId: String!, $limit: Int) {
          buildLogs(deploymentId: $deploymentId, limit: $limit) {
            lines {
              message
              timestamp
              severity
            }
          }
        }
        """
        result = await self._execute_graphql(
            query,
            {"deploymentId": deployment_id, "limit": limit}
        )
        return result["data"]["buildLogs"]["lines"]

    async def get_runtime_logs(
        self,
        deployment_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve runtime logs (stdout/stderr).

        Use Case: Deployment CRASHED → agent reads logs to identify exception.
        """
        query = """
        query RuntimeLogs($deploymentId: String!, $limit: Int) {
          runtimeLogs(deploymentId: $deploymentId, limit: $limit) {
            lines {
              message
              timestamp
              severity
            }
          }
        }
        """
        result = await self._execute_graphql(
            query,
            {"deploymentId": deployment_id, "limit": limit}
        )
        return result["data"]["runtimeLogs"]["lines"]

    async def get_deployment_metrics(
        self,
        deployment_id: str
    ) -> Dict[str, Any]:
        """Get resource utilization metrics.

        Use Case: Agent detects performance degradation → scales resources.

        Returns:
            Dictionary with:
            - cpu_usage: CPU percentage
            - memory_usage: RAM in MB
            - request_count: HTTP requests
            - response_time: Avg latency in ms
        """
        query = """
        query DeploymentMetrics($id: String!) {
          deploymentMetrics(deploymentId: $id) {
            cpuUsage
            memoryUsage
            requestCount
            responseTime
          }
        }
        """
        result = await self._execute_graphql(query, {"id": deployment_id})
        return result["data"]["deploymentMetrics"]

    # =========================================================================
    # AUTONOMOUS MONITORING
    # =========================================================================

    async def monitor_deployment_until_stable(
        self,
        deployment_id: str,
        timeout_seconds: int = 600,
        poll_interval: int = 5
    ) -> str:
        """Monitor deployment until it reaches a stable state.

        Implements the State Machine monitoring logic.

        Stable States: ACTIVE (success), FAILED (build error), CRASHED (runtime error)
        Transient States: INITIALIZING, BUILDING, DEPLOYING (keep polling)

        Args:
            deployment_id: Deployment to monitor
            timeout_seconds: Max time to wait (default: 10 minutes)
            poll_interval: Seconds between status checks

        Returns:
            Final status (ACTIVE, FAILED, or CRASHED)

        Raises:
            TimeoutError: If deployment doesn't stabilize in time

        Example:
            >>> deployment_id = await client.trigger_deployment(...)
            >>> final_status = await client.monitor_deployment_until_stable(deployment_id)
            >>> if final_status == "ACTIVE":
            ...     print("Deployment successful!")
            >>> elif final_status == "FAILED":
            ...     logs = await client.get_build_logs(deployment_id)
            ...     print(f"Build failed: {logs}")
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout_seconds:
            status = await self.get_deployment_status(deployment_id)

            # Stable states - return immediately
            if status in ("ACTIVE", "FAILED", "CRASHED", "REMOVED"):
                return status

            # Transient states - keep polling
            if status in ("INITIALIZING", "BUILDING", "DEPLOYING"):
                await asyncio.sleep(poll_interval)
                continue

            # Unknown state - raise error
            raise ValueError(f"Unknown deployment status: {status}")

        raise TimeoutError(
            f"Deployment {deployment_id} did not stabilize within {timeout_seconds}s"
        )

    # =========================================================================
    # ENVIRONMENT VARIABLES
    # =========================================================================

    async def set_environment_variable(
        self,
        project_id: str,
        environment_id: str,
        key: str,
        value: str
    ) -> None:
        """Set an environment variable.

        Use Case: Agent updates configuration dynamically.

        ⚠️ Security: Never log the value parameter.
        """
        mutation = """
        mutation SetEnvVar(
          $projectId: String!,
          $environmentId: String!,
          $key: String!,
          $value: String!
        ) {
          variableUpsert(
            input: {
              projectId: $projectId,
              environmentId: $environmentId,
              name: $key,
              value: $value
            }
          ) {
            id
          }
        }
        """
        await self._execute_graphql(
            mutation,
            {
                "projectId": project_id,
                "environmentId": environment_id,
                "key": key,
                "value": value
            }
        )
```

---

## Operational Scenarios

### Scenario 1: Autonomous Deployment with Success

**Trigger**: New commit pushed to main branch (detected via GitHub webhook)

**Agent Flow**:

1. **Observe**: GitHub webhook → new commit `abc123` on main
2. **Orient**: Commit passed CI tests, author is trusted developer
3. **Decide**: Trigger Railway deployment
4. **Act**:
   ```python
   deployment_id = await railway_client.trigger_deployment(
       project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
       environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
   )

   final_status = await railway_client.monitor_deployment_until_stable(
       deployment_id=deployment_id,
       timeout_seconds=600
   )

   if final_status == "ACTIVE":
       logger.info("Deployment successful", deployment_id=deployment_id)
       await alert_manager.send_alert(
           severity=AlertSeverity.INFO,
           title="Deployment Successful",
           message=f"Commit {commit_sha} deployed to production"
       )
   ```

**Timeline**:
- T+0s: Trigger deployment (INITIALIZING)
- T+5s: Building (BUILDING)
- T+120s: Build complete (DEPLOYING)
- T+135s: Health check passed (ACTIVE)
- T+136s: Alert sent to Telegram

---

### Scenario 2: Autonomous Recovery from Build Failure

**Trigger**: Deployment fails with status FAILED

**Agent Flow**:

1. **Observe**: Deployment status = FAILED
2. **Orient**: Parse build logs → identify syntax error in line 45
3. **Decide**: Rollback to last stable deployment + create GitHub Issue
4. **Act**:
   ```python
   # Get build logs
   logs = await railway_client.get_build_logs(failed_deployment_id)
   error_message = next(
       log["message"] for log in logs if log["severity"] == "ERROR"
   )

   # Find last stable deployment
   last_stable = await railway_client.get_last_active_deployment(
       project_id=project_id,
       environment_id=environment_id
   )

   # Rollback
   rollback = await railway_client.rollback_deployment(last_stable["id"])

   # Monitor rollback
   rollback_status = await railway_client.monitor_deployment_until_stable(
       rollback["id"]
   )

   # Create GitHub Issue
   await github_client.create_issue(
       owner="edri2or-commits",
       repo="project38-or",
       title=f"Deployment Failed: {error_message[:100]}",
       body=f"""
       ## Deployment Failure Report

       **Failed Deployment**: `{failed_deployment_id}`
       **Error**: {error_message}
       **Rollback Status**: {rollback_status}

       **Build Logs**:
       ```
       {chr(10).join(log["message"] for log in logs[-10:])}
       ```

       **Action Required**: Review and fix the build error.
       """,
       labels=["bug", "deployment", "autonomous-agent"]
   )

   # Alert humans
   await alert_manager.send_alert(
       severity=AlertSeverity.CRITICAL,
       title="Deployment Failed - Rollback Complete",
       message=f"Deployment failed with error: {error_message}. Rolled back to {last_stable['id']}.",
       context={
           "failed_deployment": failed_deployment_id,
           "error": error_message,
           "rollback_deployment": rollback["id"]
       }
   )
   ```

**Timeline**:
- T+0s: Deployment FAILED detected
- T+2s: Build logs retrieved
- T+3s: Last stable deployment identified
- T+5s: Rollback initiated
- T+25s: Rollback ACTIVE
- T+26s: GitHub Issue created
- T+27s: Telegram alert sent

**Result**: Service restored in <30 seconds, human notified with full context.

---

### Scenario 3: Handling CRASHED Deployments

**Difference from FAILED**: Code builds successfully but crashes at runtime.

**Possible Causes**:
- Out of Memory (OOM)
- Uncaught exception
- Database connection timeout
- Missing environment variable

**Agent Strategy**:

```python
if deployment_status == "CRASHED":
    # Get runtime logs (not build logs)
    runtime_logs = await railway_client.get_runtime_logs(deployment_id)

    # Analyze crash reason
    if "Out of memory" in str(runtime_logs):
        # OOM → scale up resources (future capability)
        decision = "scale_up"
    elif "ECONNREFUSED" in str(runtime_logs):
        # Database connection issue → check database status
        decision = "check_dependencies"
    else:
        # Unknown crash → rollback
        decision = "rollback"

    # Execute decision...
```

---

## Integration with OODA Loop

The RailwayClient serves as the **Infrastructure Worker** in the OODA Loop:

| OODA Phase | Railway Operations |
|------------|-------------------|
| **OBSERVE** | `get_deployment_status()`, `get_deployment_metrics()` |
| **ORIENT** | Correlate deployment state with GitHub commits, n8n workflow status |
| **DECIDE** | Determine action: deploy, rollback, scale, alert |
| **ACT** | `trigger_deployment()`, `rollback_deployment()`, `set_environment_variable()` |

**Key Principle**: The RailwayClient is stateless. The Orchestrator maintains state and makes decisions.

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
   - ❌ Never construct queries with f-strings: `f"query {{ deployment(id: \"{user_input}\") }}"` ← WRONG

---

## Production Configuration

**Current Deployment** (project38-or):
- **Project**: delightful-cat
- **Project ID**: `95ec21cc-9ada-41c5-8485-12f9a00e0116`
- **Environment**: production
- **Environment ID**: `99c99a18-aea2-4d01-9360-6a93705102a0`
- **URL**: https://web-production-47ff.up.railway.app
- **Health Check**: `/health` endpoint (database connectivity check)

**Usage Example**:
```python
from src.secrets_manager import SecretManager
from src.railway_client import RailwayClient

# Initialize
secret_manager = SecretManager()
railway_token = secret_manager.get_secret("RAILWAY-API")
railway = RailwayClient(api_token=railway_token)

# Monitor production
status = await railway.get_deployment_status("current-deployment-id")
metrics = await railway.get_deployment_metrics("current-deployment-id")

print(f"Status: {status}")
print(f"CPU: {metrics['cpuUsage']}%")
print(f"Memory: {metrics['memoryUsage']} MB")
```

---

**Next Document**: [GitHub App Integration](03-github-app-integration-hybrid.md) - Code Control and Automation
