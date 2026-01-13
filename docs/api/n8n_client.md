# n8n Client API Reference

Complete API reference for `N8nClient` - workflow orchestration for autonomous operations.

---

## Overview

The `N8nClient` provides programmatic access to n8n workflow automation, enabling autonomous agents to create, execute, and monitor workflows dynamically.

**Features:**
- Create/update/delete workflows programmatically
- Execute workflows with custom data
- Monitor execution status and results
- Import/export workflows (version control)
- Exponential backoff retry logic

---

## Quick Start

```python
from src.secrets_manager import SecretManager
from src.n8n_client import N8nClient

# Initialize from GCP Secret Manager
manager = SecretManager()
api_key = manager.get_secret("N8N-API")

client = N8nClient(
    base_url="https://n8n.railway.app",
    api_key=api_key
)

# Create workflow
workflow = await client.create_workflow(
    name="Railway Deployment Alert",
    nodes=[...],
    connections={...}
)

# Execute workflow
execution_id = await client.execute_workflow(
    workflow_id=workflow["id"],
    data={"alert": {"severity": "critical"}}
)

# Monitor execution
status = await client.get_execution_status(execution_id)
print(f"Status: {status.get('status', 'unknown')}")
```

---

## API Reference

### Initialization

#### `N8nClient.__init__()`

Initialize the n8n client.

**Parameters:**
- `base_url` (str): n8n instance URL (e.g., "https://n8n.railway.app")
- `api_key` (str): n8n API key (from GCP Secret Manager: N8N-API)

---

### Workflow Management

#### `create_workflow()` (async)

Create a new workflow programmatically.

**Parameters:**
- `name` (str): Workflow name
- `nodes` (list): List of node definitions
- `connections` (dict): Connection graph
- `active` (bool, optional): Activate immediately (default: True)
- `settings` (dict, optional): Workflow settings

**Returns:** Created workflow object with id, name, active status

**Example:**
```python
workflow = await client.create_workflow(
    name="Deployment Alert",
    nodes=[
        {"name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300]},
        {"name": "Telegram", "type": "n8n-nodes-base.telegram", "position": [450, 300]}
    ],
    connections={"Webhook": {"main": [[{"node": "Telegram"}]]}},
    active=True
)
```

---

#### `get_workflow()` (async)

Get workflow details by ID.

**Parameters:** `workflow_id` (str)

**Returns:** Workflow object

---

#### `list_workflows()` (async)

List all workflows.

**Parameters:** `active_only` (bool, optional): Filter active workflows only

**Returns:** List of workflow objects

---

#### `update_workflow()` (async)

Update an existing workflow.

**Parameters:**
- `workflow_id` (str): Workflow ID
- `name` (str, optional): New name
- `nodes` (list, optional): Updated nodes
- `connections` (dict, optional): Updated connections
- `active` (bool, optional): Update active status

**Returns:** Updated workflow object

---

#### `delete_workflow()` (async)

Delete a workflow.

**Parameters:** `workflow_id` (str)

**Returns:** None

---

#### `activate_workflow()` / `deactivate_workflow()` (async)

Activate or deactivate a workflow.

**Parameters:** `workflow_id` (str)

**Returns:** Updated workflow object

---

### Workflow Execution

#### `execute_workflow()` (async)

Execute a workflow with custom input data.

**Parameters:**
- `workflow_id` (str): Workflow ID
- `data` (dict, optional): Input data for workflow

**Returns:** Execution ID (string)

**Example:**
```python
execution_id = await client.execute_workflow(
    workflow_id="wf-abc123",
    data={"alert": {"severity": "critical", "title": "Deployment Failed"}}
)
```

---

#### `get_execution_status()` (async)

Get execution status and results.

**Parameters:** `execution_id` (str)

**Returns:** Execution object with:
- `finished` (bool): True if complete
- `status` (str): "success", "error", or "running"
- `data` (dict): Execution result data
- `startedAt` / `stoppedAt` (str): ISO timestamps

---

#### `get_recent_executions()` (async)

Get recent workflow executions.

**Parameters:** `limit` (int, optional): Max results (default: 20, max: 100)

**Returns:** List of execution objects

---

### Import/Export

#### `export_workflow()` (async)

Export workflow as JSON (for version control).

**Parameters:** `workflow_id` (str)

**Returns:** Complete workflow definition

**Example:**
```python
workflow_json = await client.export_workflow("wf-abc123")
# Save to GitHub
with open("workflow.json", "w") as f:
    json.dump(workflow_json, f, indent=2)
```

---

#### `import_workflow()` (async)

Import workflow from JSON definition.

**Parameters:**
- `workflow_data` (dict): Complete workflow definition
- `activate` (bool, optional): Activate after import (default: False)

**Returns:** Created workflow object with new ID

---

## Exception Handling

### Exception Hierarchy

```
N8nError (base)
├── N8nAuthenticationError (401 Unauthorized)
├── N8nNotFoundError (404 Not Found)
└── N8nValidationError (400 Bad Request)
```

### Example

```python
from src.n8n_client import (
    N8nError,
    N8nAuthenticationError,
    N8nNotFoundError,
    N8nValidationError
)

try:
    workflow = await client.create_workflow(...)
except N8nAuthenticationError:
    print("Invalid API key")
except N8nValidationError as e:
    print(f"Workflow validation failed: {e}")
except N8nNotFoundError:
    print("Workflow not found")
except N8nError as e:
    print(f"n8n API error: {e}")
```

---

## Production Configuration

### n8n Deployment on Railway

1. **Deploy n8n Template:**
   - Visit: https://railway.com/deploy/n8n
   - Click "Deploy on Railway"
   - Railway auto-configures PostgreSQL and environment variables

2. **Get API Key:**
   - Log in to n8n instance
   - Settings → API → Generate new API key
   - Store in GCP Secret Manager:
     ```bash
     echo -n "your-api-key" | gcloud secrets create N8N-API --data-file=-
     ```

3. **Environment Variables** (Railway auto-configures):
   ```bash
   N8N_ENCRYPTION_KEY=<auto-generated>
   N8N_API_KEY_AUTH_ENABLED=true
   DB_TYPE=postgresdb
   ```

---

## Troubleshooting

### Authentication Errors

**Error:** `N8nAuthenticationError: Invalid n8n API key`

**Solutions:**
1. Verify API key in n8n Settings → API
2. Check GCP Secret Manager has correct key: `N8N-API`
3. Ensure `N8N_API_KEY_AUTH_ENABLED=true` in Railway

### Validation Errors

**Error:** `N8nValidationError: Workflow validation failed`

**Solutions:**
1. Verify node types are correct (e.g., "n8n-nodes-base.webhook")
2. Check connections syntax: `{"NodeName": {"main": [[{"node": "NextNode"}]]}}`
3. Ensure required node parameters are provided

### Not Found Errors

**Error:** `N8nNotFoundError: Resource not found`

**Solutions:**
1. Verify workflow ID exists: `await client.list_workflows()`
2. Check execution ID is valid
3. Ensure workflow hasn't been deleted

---

## Related Documentation

- [n8n Integration Guide](../integrations/n8n-integration.md)
- [n8n Orchestration (Hybrid)](../autonomous/04-n8n-orchestration-hybrid.md)
- [ADR-003: Railway Autonomous Control](../decisions/ADR-003-railway-autonomous-control.md)
- [n8n Official Docs](https://docs.n8n.io/api/)

---

## Changelog

### Version 1.0.0 (2026-01-13)

- Initial implementation
- Workflow management (create, update, delete, list)
- Workflow execution with custom data
- Execution monitoring
- Import/export capabilities
- Exponential backoff retry logic
- Comprehensive error handling
- 30+ unit tests with 100% coverage

---

*Last Updated: 2026-01-13*
*Status: Production Ready*
