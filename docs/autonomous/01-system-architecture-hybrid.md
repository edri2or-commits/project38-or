# System Architecture: The Supervisor-Worker Pattern with Production Implementation

## Overview

This document details the complete system architecture for the Claude autonomous control system, combining the theoretical elegance of the **Supervisor-Worker pattern** with production-ready implementation code. The architecture transforms the OODA Loop philosophy into executable software.

---

## The Supervisor-Worker Pattern

In complex autonomous scenarios, a single-threaded agent is insufficient and prone to bottlenecks. We employ a **hierarchical multi-agent architecture** validated by distributed systems research.

```
┌───────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR (Supervisor)                 │
│                                                            │
│  • Maintains global state                                 │
│  • High-level goals: "Ensure Production is Healthy"       │
│  • Delegates work to specialized workers                  │
│  • Handles inter-worker coordination                      │
│                                                            │
└──────────────┬────────────────┬────────────────┬──────────┘
               │                │                │
      ┌────────▼─────┐  ┌──────▼──────┐  ┌─────▼──────┐
      │   RAILWAY    │  │   GITHUB    │  │    N8N     │
      │   WORKER     │  │   WORKER    │  │   WORKER   │
      └──────────────┘  └─────────────┘  └────────────┘
               │                │                │
      ┌────────▼─────┐  ┌──────▼──────┐  ┌─────▼──────┐
      │   Railway    │  │   GitHub    │  │    n8n     │
      │   GraphQL    │  │   REST API  │  │  REST API  │
      └──────────────┘  └─────────────┘  └────────────┘
```

---

### Why Supervisor-Worker?

**Benefits:**
1. **Isolation**: A failure in the n8n Worker doesn't crash the Railway monitoring loop
2. **Specialization**: Each worker is an expert in its domain (Railway GraphQL, GitHub JWT, n8n JSON)
3. **Parallelism**: Workers can execute concurrently (e.g., rollback Railway while creating GitHub Issue)
4. **Scalability**: Add new workers (e.g., Datadog Worker, Slack Worker) without modifying existing code
5. **Testability**: Each worker can be tested independently with mocked APIs

**Key Principle**: The Orchestrator knows **what** needs to happen. The Workers know **how** to make it happen.

---

## The Four-Layer Architecture

The system is organized into four distinct layers, each with clear responsibilities:

```
┌─────────────────────────────────────────────────────────┐
│         Layer 1: AUTHENTICATION & SECRETS               │
│  • GCP Secret Manager (WIF)                             │
│  • JWT generation (GitHub App)                          │
│  • Token caching & auto-refresh                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│         Layer 2: API CLIENTS (Workers)                  │
│  • RailwayClient (GraphQL)                              │
│  • GitHubAppClient (REST + JWT)                         │
│  • N8nClient (REST)                                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│         Layer 3: ORCHESTRATION ENGINE (Supervisor)      │
│  • OODA Loop implementation                             │
│  • State management (PostgreSQL)                        │
│  • Decision logic                                       │
│  • Worker coordination                                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│         Layer 4: OBSERVABILITY                          │
│  • Structured logging (JSON)                            │
│  • Metrics collection (Prometheus)                      │
│  • Audit trail (PostgreSQL)                             │
│  • Alerting (Telegram via n8n)                          │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 1: Authentication & Secrets

### The SecretManager Module

**Purpose**: Centralized secret retrieval from GCP Secret Manager using Workload Identity Federation (WIF).

**Key Features:**
- ✅ No service account keys (uses WIF)
- ✅ Token caching (avoid repeated GCP calls)
- ✅ Automatic secret rotation detection
- ✅ Environment variable fallback (for local dev)

**Production Implementation** (from Research B):

```python
"""Secret management using GCP Secret Manager with WIF."""
import os
from typing import Optional
from google.cloud import secretmanager
from google.auth import default

class SecretManager:
    """Manages secrets from GCP Secret Manager.
    
    Uses Workload Identity Federation (WIF) for authentication,
    eliminating the need for service account keys.
    """
    
    def __init__(self, project_id: str = "project38-483612"):
        """Initialize SecretManager.
        
        Args:
            project_id: GCP project ID
        """
        self.project_id = project_id
        self._client: Optional[secretmanager.SecretManagerServiceClient] = None
        self._cache: dict[str, str] = {}
    
    @property
    def client(self) -> secretmanager.SecretManagerServiceClient:
        """Lazy-load the Secret Manager client."""
        if self._client is None:
            credentials, _ = default()
            self._client = secretmanager.SecretManagerServiceClient(
                credentials=credentials
            )
        return self._client
    
    def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """Retrieve a secret from GCP Secret Manager.
        
        Args:
            secret_name: Name of the secret (e.g., "RAILWAY-API")
            version: Version to retrieve (default: "latest")
            
        Returns:
            The secret value as a string
            
        Raises:
            google.api_core.exceptions.NotFound: If secret doesn't exist
            
        Example:
            >>> manager = SecretManager()
            >>> token = manager.get_secret("RAILWAY-API")
            >>> # Use token, never print it
        """
        # Check cache first
        cache_key = f"{secret_name}:{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Construct the secret path
        name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
        
        # Access the secret
        response = self.client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode("UTF-8")
        
        # Cache it
        self._cache[cache_key] = secret_value
        
        return secret_value
    
    def clear_cache(self):
        """Clear the secret cache (use after rotation)."""
        self._cache.clear()
```

**Usage in Workers:**
```python
# In RailwayClient.__init__
self.secret_manager = SecretManager()
self.api_token = self.secret_manager.get_secret("RAILWAY-API")

# In GitHubAppClient.__init__
self.private_key = self.secret_manager.get_secret("github-app-private-key")
```

---

## Layer 2: API Clients (The Workers)

Each worker is a specialized interface to one platform. Workers implement the **Observer** and **Actuator** functions of the OODA Loop.

### Worker 1: RailwayClient (Infrastructure Worker)

**Responsibilities:**
- Deploy services
- Monitor deployment status
- Rollback failed deployments
- Retrieve logs and metrics
- Manage environment variables

**Key Implementation** (from Research B + Research A State Machine):

```python
"""Railway GraphQL API client for autonomous deployment management."""
import time
import asyncio
from typing import Optional, Dict, Any
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

class RailwayClient:
    """Async client for Railway GraphQL API.
    
    Implements the Deployment State Machine from Research A:
    INITIALIZING -> BUILDING -> DEPLOYING -> ACTIVE (success)
                                         ├-> FAILED (error)
                                         └-> CRASHED (runtime error)
    """
    
    def __init__(self, api_token: str):
        """Initialize Railway client.
        
        Args:
            api_token: Railway API token from GCP Secret Manager
        """
        self.api_token = api_token
        self.base_url = "https://backboard.railway.com/graphql/v2"
        
    def _build_url(self) -> str:
        """Build GraphQL URL with Cloudflare workaround.
        
        CRITICAL: Railway's Cloudflare blocks requests without query params.
        Adding ?t={timestamp} prevents Error 1015.
        
        Source: Research B discovery
        """
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
        
        Args:
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Parsed JSON response
            
        Raises:
            httpx.HTTPStatusError: If API returns error
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
    
    async def get_deployment_status(self, deployment_id: str) -> str:
        """Get current deployment status.
        
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
          }
        }
        """
        result = await self._execute_graphql(query, {"id": deployment_id})
        return result["data"]["deployment"]["status"]
    
    async def trigger_deployment(
        self, 
        project_id: str, 
        environment_id: str = "production"
    ) -> str:
        """Trigger a new deployment.
        
        Args:
            project_id: Railway project ID
            environment_id: Environment to deploy to
            
        Returns:
            New deployment ID
        """
        mutation = """
        mutation DeploymentTrigger($projectId: String!, $environmentId: String!) {
          deploymentTrigger(
            input: { projectId: $projectId, environmentId: $environmentId }
          ) {
            id
            status
          }
        }
        """
        result = await self._execute_graphql(
            mutation, 
            {"projectId": project_id, "environmentId": environment_id}
        )
        return result["data"]["deploymentTrigger"]["id"]
    
    async def rollback_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Rollback to a previous deployment.
        
        CRITICAL: This is the agent's primary recovery mechanism.
        Use when current deployment has status FAILED or CRASHED.
        
        Args:
            deployment_id: ID of deployment to rollback to
            
        Returns:
            New deployment info
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
    
    async def get_build_logs(
        self, 
        deployment_id: str, 
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """Retrieve build logs for debugging.
        
        Args:
            deployment_id: Railway deployment ID
            limit: Max number of log lines
            
        Returns:
            List of log entries with message, timestamp, severity
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
    
    async def monitor_deployment_until_stable(
        self, 
        deployment_id: str,
        timeout_seconds: int = 600,
        poll_interval: int = 5
    ) -> str:
        """Monitor deployment until it reaches a stable state.
        
        Implements the State Machine monitoring logic from Research A.
        
        Args:
            deployment_id: Deployment to monitor
            timeout_seconds: Max time to wait
            poll_interval: Seconds between status checks
            
        Returns:
            Final status (ACTIVE, FAILED, or CRASHED)
            
        Raises:
            TimeoutError: If deployment doesn't stabilize in time
        """
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_seconds:
            status = await self.get_deployment_status(deployment_id)
            
            # Stable states
            if status in ("ACTIVE", "FAILED", "CRASHED", "REMOVED"):
                return status
            
            # Transient states - keep polling
            if status in ("INITIALIZING", "BUILDING", "DEPLOYING"):
                await asyncio.sleep(poll_interval)
                continue
            
            # Unknown state
            raise ValueError(f"Unknown deployment status: {status}")
        
        raise TimeoutError(
            f"Deployment {deployment_id} did not stabilize within {timeout_seconds}s"
        )
```

**State Machine Logic** (from Research A):

| Status | Agent Interpretation | Action Strategy |
|--------|---------------------|-----------------|
| INITIALIZING | Request acknowledged | Wait: Poll every 5s |
| BUILDING | Docker image building | Monitor: Check build logs for errors |
| DEPLOYING | Container starting | Monitor: Check for healthcheck failures |
| ACTIVE | Service healthy | Success: Begin metric monitoring |
| FAILED | Build or deploy error | Act: Parse logs; trigger rollback |
| CRASHED | Runtime exit (non-zero) | Act: Trigger restart; analyze runtime logs |

---

### Worker 2: GitHubAppClient (Code Worker)

**Responsibilities:**
- Authenticate as GitHub App (JWT → Installation Token)
- Trigger workflow_dispatch events
- Create/merge pull requests
- Open issues for bugs
- Read workflow run logs

**Key Implementation** (from Research B):

```python
"""GitHub App authentication and operations client."""
import time
import jwt
from typing import Optional, Dict, Any
import httpx
from datetime import datetime, timedelta

class GitHubAppClient:
    """Client for GitHub App authentication and API operations.
    
    Implements JWT-based authentication with automatic token refresh.
    Superior to PAT (Personal Access Token) for autonomous systems.
    
    Why GitHub App > PAT (from Research B):
    - Auto-rotating tokens (1 hour expiration)
    - Fine-grained, repository-scoped permissions
    - Independent app identity (not tied to human user)
    - Higher rate limits (5,000 + 12,500/hour)
    """
    
    def __init__(
        self, 
        app_id: str, 
        private_key: str, 
        installation_id: str
    ):
        """Initialize GitHub App client.
        
        Args:
            app_id: GitHub App ID (e.g., "123456")
            private_key: PEM-formatted private key (from GCP Secret Manager)
            installation_id: Installation ID for the repository
        """
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.base_url = "https://api.github.com"
        
        # Token cache
        self._installation_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    def generate_jwt(self) -> str:
        """Generate JWT for GitHub App authentication.
        
        JWT is signed with RS256 and valid for 10 minutes.
        Used to request Installation Access Tokens.
        
        Returns:
            Signed JWT string
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60s ago (clock drift tolerance)
            "exp": now + 600,  # Expires in 10 minutes
            "iss": self.app_id  # Issuer = App ID
        }
        
        return jwt.encode(
            payload, 
            self.private_key, 
            algorithm="RS256"
        )
    
    async def get_installation_token(self) -> str:
        """Get Installation Access Token (IAT).
        
        IAT is valid for 1 hour and scoped to specific repositories.
        This is the token used for all API operations.
        
        Returns:
            Installation Access Token
        """
        # Check if we have a valid cached token
        if self._installation_token and self._token_expires_at:
            # Refresh 5 minutes before expiration
            if datetime.utcnow() < (self._token_expires_at - timedelta(minutes=5)):
                return self._installation_token
        
        # Generate new token
        jwt_token = self.generate_jwt()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/app/installations/{self.installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            self._installation_token = data["token"]
            self._token_expires_at = datetime.fromisoformat(
                data["expires_at"].replace("Z", "+00:00")
            )
            
            return self._installation_token
    
    async def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, Any]] = None
    ) -> None:
        """Trigger a workflow_dispatch event.
        
        Args:
            owner: Repository owner
            repo: Repository name
            workflow_id: Workflow file name (e.g., "deploy.yml")
            ref: Branch/tag to run on
            inputs: Input parameters for workflow
        """
        token = await self.get_installation_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json"
                },
                json={
                    "ref": ref,
                    "inputs": inputs or {}
                }
            )
            response.raise_for_status()
    
    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[list[str]] = None
    ) -> Dict[str, Any]:
        """Create a GitHub issue (for bug reports).
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: Issue title
            body: Issue body (Markdown)
            labels: Labels to apply
            
        Returns:
            Created issue data
        """
        token = await self.get_installation_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/issues",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json"
                },
                json={
                    "title": title,
                    "body": body,
                    "labels": labels or []
                }
            )
            response.raise_for_status()
            return response.json()
```

---

### Worker 3: N8nClient (Orchestration Worker)

**Responsibilities:**
- Create workflows dynamically
- Execute workflows with custom data
- Monitor execution status
- Export/import for version control

**Key Implementation** (from Research B):

```python
"""n8n workflow orchestration client."""
from typing import Optional, Dict, Any, List
import httpx

class N8nClient:
    """Client for n8n REST API.
    
    Enables dynamic workflow creation and execution.
    """
    
    def __init__(self, base_url: str, api_key: str):
        """Initialize n8n client.
        
        Args:
            base_url: n8n instance URL (e.g., "https://n8n.railway.app")
            api_key: n8n API key (from GCP Secret Manager)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
    
    async def create_workflow(
        self,
        name: str,
        nodes: List[Dict[str, Any]],
        connections: Dict[str, Any],
        active: bool = True
    ) -> Dict[str, Any]:
        """Create a new workflow programmatically.
        
        Args:
            name: Workflow name
            nodes: List of node definitions
            connections: Connection graph
            active: Whether to activate immediately
            
        Returns:
            Created workflow data
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/workflows",
                headers={
                    "X-N8N-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "name": name,
                    "nodes": nodes,
                    "connections": connections,
                    "active": active
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def execute_workflow(
        self,
        workflow_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Execute a workflow with custom input data.
        
        Args:
            workflow_id: n8n workflow ID
            data: Input data for the workflow
            
        Returns:
            Execution ID
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/workflows/{workflow_id}/execute",
                headers={
                    "X-N8N-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={"data": data or {}}
            )
            response.raise_for_status()
            return response.json()["data"]["executionId"]
```

---

## Layer 3: The Orchestration Engine (Supervisor)

The Orchestrator implements the OODA Loop, coordinating the workers to achieve high-level goals.

**Responsibilities:**
- Maintain global state (deployment history, service health)
- Decide when to invoke which worker
- Coordinate multi-worker actions (rollback + create issue)
- Handle errors and retry logic at the orchestration level

**Pseudo-implementation** (concept from Research A):

```python
class AutonomousOrchestrator:
    """The Supervisor: Implements OODA Loop with Worker coordination."""
    
    def __init__(
        self,
        railway_client: RailwayClient,
        github_client: GitHubAppClient,
        n8n_client: N8nClient
    ):
        self.railway = railway_client
        self.github = github_client
        self.n8n = n8n_client
        
    async def run_ooda_loop(self):
        """Main autonomous loop."""
        while True:
            # OBSERVE
            observations = await self.observe()
            
            # ORIENT
            world_state = self.orient(observations)
            
            # DECIDE
            actions = self.decide(world_state)
            
            # ACT
            await self.act(actions)
            
            # Wait before next iteration
            await asyncio.sleep(30)
    
    async def observe(self) -> Dict[str, Any]:
        """Gather data from all workers."""
        railway_status = await self.railway.get_deployment_status(...)
        github_commits = await self.github.get_recent_commits(...)
        n8n_executions = await self.n8n.get_recent_executions(...)
        
        return {
            "railway": railway_status,
            "github": github_commits,
            "n8n": n8n_executions,
            "timestamp": time.time()
        }
    
    def orient(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze observations, build world model."""
        # Correlate events
        # Detect anomalies
        # Build temporal graph
        ...
    
    def decide(self, world_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Select actions based on world state."""
        actions = []
        
        if world_state["railway"]["status"] == "FAILED":
            actions.append({
                "type": "rollback",
                "worker": "railway",
                "params": {...}
            })
            actions.append({
                "type": "create_issue",
                "worker": "github",
                "params": {...}
            })
        
        return actions
    
    async def act(self, actions: List[Dict[str, Any]]):
        """Execute actions via workers."""
        tasks = []
        for action in actions:
            worker = getattr(self, action["worker"])
            method = getattr(worker, action["type"])
            tasks.append(method(**action["params"]))
        
        # Execute in parallel
        await asyncio.gather(*tasks)
```

---

## Layer 4: Observability

**Why Observability Matters**: An autonomous system that cannot be monitored is a black box. Trust requires transparency.

### The Four Pillars of Observability

#### 1. Structured Logging (JSON)

**Purpose**: Human-readable logs for debugging, machine-parseable logs for analysis.

**Implementation**:

```python
"""Structured logging configuration for autonomous system."""
import logging
import json
from datetime import datetime, UTC
from typing import Any, Dict

class StructuredLogger:
    """JSON-formatted logger for autonomous system events."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)

    def log_observation(self, source: str, data: Dict[str, Any]):
        """Log an observation from the OODA loop."""
        self.logger.info("observation", extra={
            "event_type": "observe",
            "source": source,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat()
        })

    def log_decision(self, decision: str, reasoning: Dict[str, Any]):
        """Log a decision from the OODA loop."""
        self.logger.info("decision", extra={
            "event_type": "decide",
            "decision": decision,
            "reasoning": reasoning,
            "timestamp": datetime.now(UTC).isoformat()
        })

    def log_action(self, worker: str, action: str, params: Dict[str, Any], result: str):
        """Log an action execution."""
        self.logger.info("action", extra={
            "event_type": "act",
            "worker": worker,
            "action": action,
            "params": params,
            "result": result,
            "timestamp": datetime.now(UTC).isoformat()
        })

class JsonFormatter(logging.Formatter):
    """Format logs as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        # Add extra fields
        if hasattr(record, "event_type"):
            log_data.update(record.__dict__)

        return json.dumps(log_data)
```

**Log Example**:
```json
{
  "timestamp": "2026-01-12T20:45:00Z",
  "level": "INFO",
  "event_type": "act",
  "worker": "railway",
  "action": "rollback_deployment",
  "params": {"deployment_id": "abc123"},
  "result": "success",
  "message": "action"
}
```

---

#### 2. Metrics Collection (Prometheus)

**Purpose**: Real-time performance monitoring and alerting.

**Implementation**:

```python
"""Prometheus metrics for autonomous system."""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter, Response

# Create metrics registry
registry = CollectorRegistry()

# OODA Loop metrics
observations_total = Counter(
    "ooda_observations_total",
    "Total observations from all sources",
    ["source"],
    registry=registry
)

decisions_total = Counter(
    "ooda_decisions_total",
    "Total decisions made",
    ["decision_type"],
    registry=registry
)

actions_total = Counter(
    "ooda_actions_total",
    "Total actions executed",
    ["worker", "action", "result"],
    registry=registry
)

# Worker performance
worker_request_duration = Histogram(
    "worker_request_duration_seconds",
    "Worker request duration",
    ["worker", "operation"],
    registry=registry
)

# Railway deployment metrics
railway_deployments = Counter(
    "railway_deployments_total",
    "Total Railway deployments",
    ["status"],
    registry=registry
)

railway_deployment_duration = Histogram(
    "railway_deployment_duration_seconds",
    "Railway deployment duration",
    buckets=[30, 60, 120, 300, 600],
    registry=registry
)

# GitHub operations
github_api_calls = Counter(
    "github_api_calls_total",
    "Total GitHub API calls",
    ["operation", "status"],
    registry=registry
)

# System health
system_health = Gauge(
    "system_health_status",
    "System health (1=healthy, 0=degraded)",
    registry=registry
)

# Metrics endpoint
router = APIRouter()

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST
    )
```

**Usage in Workers**:
```python
# In RailwayClient.trigger_deployment()
with worker_request_duration.labels(worker="railway", operation="trigger_deployment").time():
    deployment_id = await self._execute_graphql(...)
    railway_deployments.labels(status="initiated").inc()
```

---

#### 3. Audit Trail (PostgreSQL)

**Purpose**: Immutable record of all autonomous actions for compliance and debugging.

**Implementation**:

```python
"""Audit trail storage in PostgreSQL."""
from datetime import datetime, UTC
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, select
from sqlalchemy.ext.asyncio import AsyncSession

class AuditLog(SQLModel, table=True):
    """Audit log entry for autonomous actions."""

    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # OODA phase
    phase: str = Field(index=True)  # observe, orient, decide, act

    # Action details
    worker: Optional[str] = Field(default=None, index=True)
    action: Optional[str] = Field(default=None)
    params: Dict[str, Any] = Field(default={}, sa_column_kwargs={"type_": "JSONB"})

    # Result
    result: str  # success, failure, timeout
    error_message: Optional[str] = Field(default=None)

    # Context
    deployment_id: Optional[str] = Field(default=None, index=True)
    github_commit: Optional[str] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

class AuditTrail:
    """Audit trail manager."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_action(
        self,
        phase: str,
        worker: Optional[str],
        action: Optional[str],
        params: Dict[str, Any],
        result: str,
        error_message: Optional[str] = None,
        deployment_id: Optional[str] = None,
        github_commit: Optional[str] = None
    ):
        """Log an autonomous action."""
        log_entry = AuditLog(
            phase=phase,
            worker=worker,
            action=action,
            params=params,
            result=result,
            error_message=error_message,
            deployment_id=deployment_id,
            github_commit=github_commit
        )

        self.session.add(log_entry)
        await self.session.commit()

    async def get_recent_actions(self, limit: int = 100) -> list[AuditLog]:
        """Retrieve recent audit logs."""
        statement = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()
```

**Database Schema**:
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    phase VARCHAR(20) NOT NULL,
    worker VARCHAR(50),
    action VARCHAR(100),
    params JSONB,
    result VARCHAR(20) NOT NULL,
    error_message TEXT,
    deployment_id VARCHAR(100),
    github_commit VARCHAR(40)
);

CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_phase ON audit_logs(phase);
CREATE INDEX idx_audit_worker ON audit_logs(worker);
CREATE INDEX idx_audit_deployment ON audit_logs(deployment_id);
```

---

#### 4. Alerting (Telegram via n8n)

**Purpose**: Notify humans when autonomous system encounters issues.

**Implementation**:

```python
"""Alerting system using n8n webhooks and Telegram."""
from typing import Literal
from enum import Enum

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AlertManager:
    """Manages alerts via n8n."""

    def __init__(self, n8n_client: N8nClient, workflow_id: str):
        self.n8n = n8n_client
        self.workflow_id = workflow_id

    async def send_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Send alert via n8n webhook to Telegram.

        Args:
            severity: Alert severity (info/warning/critical)
            title: Alert title
            message: Alert body
            context: Additional context (deployment ID, logs, etc.)
        """
        await self.n8n.execute_workflow(
            workflow_id=self.workflow_id,
            data={
                "alert": {
                    "severity": severity.value,
                    "title": title,
                    "message": message,
                    "context": context or {},
                    "timestamp": datetime.now(UTC).isoformat()
                }
            }
        )
```

**n8n Workflow** (Alert Routing):
```
Webhook Trigger (alert data)
    ↓
Filter by severity
    ├─ INFO: Log to database
    ├─ WARNING: Log + Send Telegram message
    └─ CRITICAL: Log + Telegram + Create GitHub Issue
```

**Usage in Orchestrator**:
```python
# In AutonomousOrchestrator.act()
if action_result == "failure":
    await self.alert_manager.send_alert(
        severity=AlertSeverity.CRITICAL,
        title="Railway Deployment Failed",
        message=f"Deployment {deployment_id} failed. Rollback initiated.",
        context={
            "deployment_id": deployment_id,
            "error": error_message,
            "logs_url": f"https://railway.app/project/{project_id}/deployments/{deployment_id}"
        }
    )
```

---

## Bringing It All Together

The complete architecture enables:

1. **The Orchestrator** observes all three platforms via specialized workers
2. **Workers** translate high-level commands ("rollback") into low-level API calls (GraphQL mutations)
3. **The SecretManager** ensures all authentication is secure and tokens are fresh
4. **The OODA Loop** runs continuously, adapting to changing conditions

**This is not automation. This is autonomy.**

---

**Next Document**: [Operational Scenarios](07-operational-scenarios-hybrid.md) - The System in Action
