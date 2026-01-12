# n8n Orchestration: The Nervous System of Autonomous Operations

## Overview

n8n serves as the **Nervous System** of the autonomous platform - coordinating signals between Railway, GitHub, and external services like Telegram. This document details complete n8n integration from deployment to dynamic workflow creation.

---

## Why n8n for Autonomous Systems?

**n8n** is a low-code workflow automation platform (think Zapier, but self-hosted and programmable).

### Key Advantages for Autonomy

| Feature | Benefit for Autonomous System |
|---------|------------------------------|
| **Visual Workflows** | Humans can audit agent's automation logic |
| **200+ Integrations** | Connect Railway/GitHub to Telegram, Slack, email, etc. |
| **REST API** | Agent can create/modify workflows programmatically |
| **Self-hosted** | Full control, no third-party rate limits |
| **JSON-based** | Workflows stored as code (version control) |
| **Webhooks** | Real-time event triggers (GitHub push → n8n → Railway deploy) |

### Architecture Pattern

```
┌────────────────────────────────────────────────────────┐
│                 AUTONOMOUS AGENT (Claude)               │
│                                                         │
│  Orchestrator (OODA Loop) coordinates:                 │
│  - Railway Worker                                      │
│  - GitHub Worker                                       │
│  - n8n Worker ← Handles cross-platform coordination    │
└────────────┬───────────────────────────────────────────┘
             │
             ▼
    ┌────────────────┐
    │   n8n Worker   │
    │  (API Client)  │
    └────────┬───────┘
             │
             ▼
┌────────────────────────────────────────────────────────┐
│                    n8n Instance                         │
│                (Railway Template)                       │
│                                                         │
│  Workflow 1: GitHub Push → Railway Deploy              │
│  Workflow 2: Railway Deploy Failed → Telegram Alert    │
│  Workflow 3: Agent Request → Multi-platform Action     │
└────────────────────────────────────────────────────────┘
             │
    ┌────────┴─────────┐
    ▼                  ▼
┌─────────┐      ┌──────────┐
│ Telegram│      │  Email   │
│  Bot    │      │  SMTP    │
└─────────┘      └──────────┘
```

---

## n8n Deployment on Railway (5-Minute Setup)

### Railway Template Discovery

**Critical Finding**: Railway provides an official n8n template at `railway.com/deploy/n8n`

**Deployment Steps**:

1. **Visit**: https://railway.com/deploy/n8n
2. **Click**: "Deploy on Railway"
3. **Configure** (auto-filled by template):
   - PostgreSQL database (for workflow storage)
   - n8n service (with persistent volume)
   - Environment variables (N8N_ENCRYPTION_KEY, etc.)
4. **Deploy**: Railway builds and deploys in ~2 minutes
5. **Access**: Public URL provided (e.g., `https://n8n.up.railway.app`)

**Post-Deployment**:
- Set admin credentials via Railway environment variables
- Enable API access: `N8N_API_KEY_AUTH_ENABLED=true`
- Store API key in GCP Secret Manager: `N8N-API`

---

## Production-Ready N8nClient

Complete implementation for autonomous workflow management:

```python
"""n8n workflow orchestration client."""
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

class N8nClient:
    """Client for n8n REST API.

    Enables dynamic workflow creation and execution for autonomous operations.

    Features:
    - Create workflows programmatically (JSON definition)
    - Execute workflows with custom data
    - Monitor execution status
    - Import/export workflows (version control)
    """

    def __init__(self, base_url: str, api_key: str):
        """Initialize n8n client.

        Args:
            base_url: n8n instance URL (e.g., "https://n8n.railway.app")
            api_key: n8n API key (from GCP Secret Manager: N8N-API)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True
    )
    async def _api_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated n8n API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/workflows")
            json_data: Request body

        Returns:
            Parsed JSON response
        """
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{self.base_url}/api/v1{endpoint}",
                json=json_data,
                headers={
                    "X-N8N-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            response.raise_for_status()

            # Handle 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

    # =========================================================================
    # WORKFLOW MANAGEMENT
    # =========================================================================

    async def create_workflow(
        self,
        name: str,
        nodes: List[Dict[str, Any]],
        connections: Dict[str, Any],
        active: bool = True
    ) -> Dict[str, Any]:
        """Create a new workflow programmatically.

        Use Case: Agent creates alert workflow on first deployment.

        Args:
            name: Workflow name
            nodes: List of node definitions (see node examples below)
            connections: Connection graph (defines flow between nodes)
            active: Whether to activate immediately

        Returns:
            Created workflow object with id, name, active status

        Example:
            >>> workflow = await n8n.create_workflow(
            ...     name="Railway Deployment Alert",
            ...     nodes=[...],  # See examples below
            ...     connections={...},
            ...     active=True
            ... )
            >>> print(f"Workflow created: {workflow['id']}")
        """
        return await self._api_request(
            method="POST",
            endpoint="/workflows",
            json_data={
                "name": name,
                "nodes": nodes,
                "connections": connections,
                "active": active,
                "settings": {}
            }
        )

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow details by ID.

        Returns:
            Workflow object with nodes, connections, active status
        """
        return await self._api_request(
            method="GET",
            endpoint=f"/workflows/{workflow_id}"
        )

    async def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows.

        Use Case: Agent audits existing automation.
        """
        result = await self._api_request(
            method="GET",
            endpoint="/workflows"
        )
        return result.get("data", [])

    async def update_workflow(
        self,
        workflow_id: str,
        name: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        connections: Optional[Dict[str, Any]] = None,
        active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update an existing workflow.

        Use Case: Agent modifies alert thresholds or routing logic.
        """
        workflow = await self.get_workflow(workflow_id)

        # Update only provided fields
        if name:
            workflow["name"] = name
        if nodes:
            workflow["nodes"] = nodes
        if connections:
            workflow["connections"] = connections
        if active is not None:
            workflow["active"] = active

        return await self._api_request(
            method="PUT",
            endpoint=f"/workflows/{workflow_id}",
            json_data=workflow
        )

    async def delete_workflow(self, workflow_id: str) -> None:
        """Delete a workflow.

        Use Case: Agent cleans up temporary test workflows.
        """
        await self._api_request(
            method="DELETE",
            endpoint=f"/workflows/{workflow_id}"
        )

    # =========================================================================
    # WORKFLOW EXECUTION
    # =========================================================================

    async def execute_workflow(
        self,
        workflow_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Execute a workflow with custom input data.

        Use Case: Agent triggers alert workflow with deployment details.

        Args:
            workflow_id: n8n workflow ID
            data: Input data for the workflow (accessible in nodes)

        Returns:
            Execution ID (for monitoring)

        Example:
            >>> execution_id = await n8n.execute_workflow(
            ...     workflow_id="wf-alert-123",
            ...     data={
            ...         "alert": {
            ...             "severity": "critical",
            ...             "title": "Deployment Failed",
            ...             "deployment_id": "deploy-456"
            ...         }
            ...     }
            ... )
            >>> print(f"Workflow execution started: {execution_id}")
        """
        result = await self._api_request(
            method="POST",
            endpoint=f"/workflows/{workflow_id}/execute",
            json_data={"data": data or {}}
        )
        return result["data"]["executionId"]

    async def get_execution_status(
        self,
        execution_id: str
    ) -> Dict[str, Any]:
        """Get execution status and results.

        Returns:
            Execution object with:
            - finished: bool (True if complete)
            - data: Execution result data
            - mode: "manual" or "trigger"
            - startedAt: Timestamp
            - stoppedAt: Timestamp (if finished)
        """
        return await self._api_request(
            method="GET",
            endpoint=f"/executions/{execution_id}"
        )

    async def get_recent_executions(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent workflow executions.

        Use Case: Agent audits automation health.
        """
        result = await self._api_request(
            method="GET",
            endpoint=f"/executions?limit={limit}"
        )
        return result.get("data", [])

    # =========================================================================
    # WORKFLOW IMPORT/EXPORT
    # =========================================================================

    async def export_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Export workflow as JSON (for version control).

        Use Case: Agent backs up critical workflows to GitHub repo.

        Returns:
            Complete workflow definition (can be re-imported)
        """
        return await self.get_workflow(workflow_id)

    async def import_workflow(
        self,
        workflow_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Import workflow from JSON.

        Use Case: Agent restores workflow from backup.
        """
        return await self._api_request(
            method="POST",
            endpoint="/workflows",
            json_data=workflow_json
        )
```

---

## Workflow Node Examples

### Example 1: Simple Telegram Alert Workflow

**Use Case**: Agent sends alert to Telegram when Railway deployment fails.

```python
# Node definitions
nodes = [
    {
        "parameters": {},
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [250, 300],
        "webhookId": "deployment-alert"
    },
    {
        "parameters": {
            "chatId": "YOUR_TELEGRAM_CHAT_ID",
            "text": "🚨 *Deployment Failed*\n\nDeployment: {{$json[\"deployment_id\"]}}\nError: {{$json[\"error\"]}}"
        },
        "name": "Telegram",
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1,
        "position": [450, 300],
        "credentials": {
            "telegramApi": {
                "id": "1",
                "name": "Telegram Bot"
            }
        }
    }
]

# Connection graph (Webhook → Telegram)
connections = {
    "Webhook": {
        "main": [
            [
                {
                    "node": "Telegram",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }
}

# Create workflow
workflow = await n8n.create_workflow(
    name="Deployment Failure Alert",
    nodes=nodes,
    connections=connections,
    active=True
)

# Later, agent triggers it
await n8n.execute_workflow(
    workflow_id=workflow["id"],
    data={
        "deployment_id": "deploy-abc123",
        "error": "Build failed: SyntaxError at line 42"
    }
)
```

---

### Example 2: Multi-Step Alert Routing

**Use Case**: Route alerts based on severity (INFO → log, WARNING → Telegram, CRITICAL → Telegram + GitHub Issue)

```python
nodes = [
    {
        "parameters": {},
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [250, 300]
    },
    {
        "parameters": {
            "conditions": {
                "string": [
                    {
                        "value1": "={{$json[\"severity\"]}}",
                        "operation": "equal",
                        "value2": "critical"
                    }
                ]
            }
        },
        "name": "IF Critical",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [450, 300]
    },
    {
        "parameters": {
            "chatId": "YOUR_CHAT_ID",
            "text": "🚨 *CRITICAL ALERT*\n\n{{$json[\"title\"]}}\n\n{{$json[\"message\"]}}"
        },
        "name": "Telegram",
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1,
        "position": [650, 200]
    },
    {
        "parameters": {
            "resource": "issue",
            "operation": "create",
            "owner": "edri2or-commits",
            "repository": "project38-or",
            "title": "={{$json[\"title\"]}}",
            "body": "={{$json[\"message\"]}}"
        },
        "name": "GitHub",
        "type": "n8n-nodes-base.github",
        "typeVersion": 1,
        "position": [650, 400],
        "credentials": {
            "githubApi": {
                "id": "1",
                "name": "GitHub API"
            }
        }
    }
]

connections = {
    "Webhook": {
        "main": [[{"node": "IF Critical", "type": "main", "index": 0}]]
    },
    "IF Critical": {
        "main": [
            [
                {"node": "Telegram", "type": "main", "index": 0},
                {"node": "GitHub", "type": "main", "index": 0}
            ],
            []  # False branch (no action for non-critical)
        ]
    }
}
```

---

### Example 3: GitHub Webhook → Railway Deploy

**Use Case**: Automated deployment on git push (alternative to GitHub Actions)

```python
nodes = [
    {
        "parameters": {
            "path": "github-webhook",
            "options": {}
        },
        "name": "GitHub Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [250, 300]
    },
    {
        "parameters": {
            "conditions": {
                "string": [
                    {
                        "value1": "={{$json[\"ref\"]}}",
                        "operation": "equal",
                        "value2": "refs/heads/main"
                    }
                ]
            }
        },
        "name": "IF Main Branch",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [450, 300]
    },
    {
        "parameters": {
            "requestMethod": "POST",
            "url": "https://backboard.railway.com/graphql/v2",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": true,
            "headerParameters": {
                "parameter": [
                    {
                        "name": "Authorization",
                        "value": "Bearer {{$credentials.railwayApi.token}}"
                    }
                ]
            },
            "sendBody": true,
            "bodyParameters": {
                "parameter": [
                    {
                        "name": "query",
                        "value": "mutation { deploymentTrigger(...) }"
                    }
                ]
            }
        },
        "name": "Railway Deploy",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 3,
        "position": [650, 300]
    }
]
```

---

## Integration Patterns

### Pattern 1: n8n → Claude (Event Notification)

**Flow**: External event (GitHub push, Railway crash) → n8n webhook → Notifies Claude agent → Agent runs OODA loop

```
GitHub Push Event
    ↓
n8n Webhook
    ↓
n8n HTTP Request Node → Claude Agent API (/notify endpoint)
    ↓
Claude Agent receives event
    ↓
OODA Loop: Observe → Orient → Decide → Act
```

**Implementation**:
```python
# In Claude Agent FastAPI app
@app.post("/notify")
async def receive_notification(event: Dict[str, Any]):
    """Receive event notification from n8n."""
    event_type = event.get("type")  # "github.push", "railway.deploy_failed"

    if event_type == "railway.deploy_failed":
        # Trigger autonomous recovery flow
        await orchestrator.handle_deployment_failure(event["deployment_id"])

    return {"status": "received"}
```

---

### Pattern 2: Claude → n8n (Action Delegation)

**Flow**: Agent decides action → Delegates to n8n workflow → n8n handles multi-platform coordination

```
Claude Agent (Orchestrator)
    ↓
Decide: "Send critical alert to Telegram + Email + GitHub Issue"
    ↓
Execute n8n workflow (id: "critical-alert-workflow")
    ↓
n8n handles multi-platform fan-out:
    ├─ Telegram notification
    ├─ Email to on-call engineer
    └─ GitHub Issue creation
```

**Why delegate to n8n?**
- **Separation of concerns**: Agent focuses on decision logic, n8n handles routing
- **Visual debugging**: Humans can inspect n8n workflows in UI
- **Easy modification**: Change alert routing without touching agent code

---

### Pattern 3: Bidirectional (Feedback Loop)

**Flow**: Agent → n8n → External service → n8n → Agent (completion notification)

```
Agent: "Deploy to production"
    ↓
n8n: Trigger Railway deployment
    ↓
Railway: Building... Deploying... (3 minutes)
    ↓
n8n: Poll Railway status
    ↓
Railway: Status = ACTIVE
    ↓
n8n: POST to Agent API (/deployment-complete)
    ↓
Agent: Log success, continue monitoring
```

---

## Operational Scenarios

### Scenario 1: Dynamic Workflow Creation

**Use Case**: Agent creates alert workflow on first deployment (bootstrap automation).

```python
async def bootstrap_n8n_automation(n8n: N8nClient):
    """Create essential workflows on system startup."""

    # Check if workflows already exist
    existing = await n8n.list_workflows()
    if any(w["name"] == "Deployment Failure Alert" for w in existing):
        logger.info("Automation already bootstrapped")
        return

    # Create deployment failure alert workflow
    alert_workflow = await n8n.create_workflow(
        name="Deployment Failure Alert",
        nodes=[
            # Webhook node (entry point)
            {
                "parameters": {},
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300],
                "webhookId": "deploy-fail"
            },
            # Telegram node
            {
                "parameters": {
                    "chatId": "123456789",
                    "text": "🚨 Deployment {{$json[\"deployment_id\"]}} failed!\n\nError: {{$json[\"error\"]}}"
                },
                "name": "Telegram",
                "type": "n8n-nodes-base.telegram",
                "typeVersion": 1,
                "position": [450, 300],
                "credentials": {"telegramApi": {"id": "1", "name": "Telegram Bot"}}
            }
        ],
        connections={
            "Webhook": {
                "main": [[{"node": "Telegram", "type": "main", "index": 0}]]
            }
        },
        active=True
    )

    logger.info(f"Created workflow: {alert_workflow['id']}")

    # Store workflow ID in database for later use
    await db.store_config("n8n_alert_workflow_id", alert_workflow["id"])
```

---

### Scenario 2: Autonomous Alert Routing

**Use Case**: Agent detects Railway deployment failure → Routes alert via n8n.

```python
async def send_autonomous_alert(
    n8n: N8nClient,
    severity: str,
    title: str,
    message: str,
    context: Dict[str, Any]
):
    """Send alert through n8n workflow."""

    # Get workflow ID from config
    workflow_id = await db.get_config("n8n_alert_workflow_id")

    # Execute workflow with alert data
    execution_id = await n8n.execute_workflow(
        workflow_id=workflow_id,
        data={
            "severity": severity,
            "title": title,
            "message": message,
            "context": context,
            "timestamp": datetime.now(UTC).isoformat()
        }
    )

    logger.info(f"Alert sent via n8n execution: {execution_id}")

    # Optional: Wait for completion
    while True:
        status = await n8n.get_execution_status(execution_id)
        if status["finished"]:
            logger.info(f"Alert delivered: {status['data']}")
            break
        await asyncio.sleep(2)
```

---

### Scenario 3: Workflow Version Control

**Use Case**: Agent exports critical workflows to GitHub for backup/audit.

```python
async def backup_n8n_workflows(
    n8n: N8nClient,
    github: GitHubAppClient,
    owner: str,
    repo: str
):
    """Backup all n8n workflows to GitHub repository."""

    workflows = await n8n.list_workflows()

    for workflow in workflows:
        # Export workflow as JSON
        workflow_json = await n8n.export_workflow(workflow["id"])

        # Create/update file in GitHub
        file_path = f"n8n-workflows/{workflow['name']}.json"
        content = json.dumps(workflow_json, indent=2)

        # Use GitHub API to create file
        await github._api_request(
            method="PUT",
            endpoint=f"/repos/{owner}/{repo}/contents/{file_path}",
            json_data={
                "message": f"backup: n8n workflow '{workflow['name']}'",
                "content": base64.b64encode(content.encode()).decode()
            }
        )

        logger.info(f"Backed up workflow: {workflow['name']}")
```

---

## Integration with OODA Loop

The N8nClient serves as the **Coordination Worker** in the OODA Loop:

| OODA Phase | n8n Operations |
|------------|---------------|
| **OBSERVE** | `get_recent_executions()` (monitor automation health) |
| **ORIENT** | Analyze workflow execution patterns, identify bottlenecks |
| **DECIDE** | Determine: create new workflow, modify routing, send alert |
| **ACT** | `execute_workflow()`, `create_workflow()`, `update_workflow()` |

---

## Security Considerations

1. **API Key Storage**:
   - ✅ Stored in GCP Secret Manager: `N8N-API`
   - ✅ Never logged or committed
   - ✅ Use environment variable in n8n: `N8N_API_KEY_AUTH_ENABLED=true`

2. **Webhook Security**:
   - ⚠️ n8n webhooks are public by default
   - ✅ Use webhook authentication: Add secret token to URL
   - ✅ Validate webhook source (check IP, signature)

3. **Credential Management**:
   - ✅ Store third-party credentials (Telegram, GitHub) in n8n credentials store
   - ❌ Never pass credentials in workflow data (use credential references)

4. **Workflow Permissions**:
   - ✅ Limit workflows to read-only operations where possible
   - ❌ Never create workflows that delete data without confirmation

---

## Production Configuration

**Current Setup** (to be deployed):
- **Deployment**: Railway template at `railway.com/deploy/n8n`
- **Database**: PostgreSQL (via Railway template)
- **URL**: (To be provided after deployment)
- **API Authentication**: Enabled with key in GCP Secret Manager
- **Essential Workflows**:
  1. Deployment Failure Alert (Railway → Telegram)
  2. Critical Issue Notification (GitHub → Telegram + Email)
  3. Weekly Health Report (Scheduled → Agent API)

**Usage**:
```python
from src.secrets_manager import SecretManager
from src.n8n_client import N8nClient

secret_manager = SecretManager()
n8n_api_key = secret_manager.get_secret("N8N-API")

n8n = N8nClient(
    base_url="https://n8n.railway.app",
    api_key=n8n_api_key
)

# Create workflow
await n8n.create_workflow(...)

# Execute workflow
await n8n.execute_workflow(workflow_id="...", data={...})
```

---

**Next Document**: [Resilience Patterns](05-resilience-patterns-hybrid.md) - Error Handling and Recovery
