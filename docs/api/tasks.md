# Task Management API Reference

The Task Management API provides endpoints for managing agent execution tasks, viewing execution history, and manually triggering agent runs.

## Overview

Tasks represent individual executions of agents. Each task tracks:

- Execution status (pending/running/completed/failed)
- Start and completion timestamps
- Output (stdout) and errors (stderr)
- Retry attempts

## Base URL

```
/api/tasks
```

## Endpoints

### List All Tasks

Get a list of all agent execution tasks with optional filtering.

**Endpoint:** `GET /api/tasks`

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| agent_id | integer | No | Filter by agent ID |
| status | string | No | Filter by status (pending/running/completed/failed) |
| limit | integer | No | Maximum number of results (1-1000, default: 100) |
| offset | integer | No | Offset for pagination (default: 0) |

**Response:** `200 OK`

```json
[
  {
    "id": 123,
    "agent_id": 1,
    "status": "completed",
    "scheduled_at": "2026-01-11T18:00:00Z",
    "started_at": "2026-01-11T18:00:01Z",
    "completed_at": "2026-01-11T18:00:15Z",
    "result": "Stock price: $850.00\nAlert sent: No",
    "error": null,
    "retry_count": 0,
    "created_at": "2026-01-11T18:00:00Z"
  }
]
```

**Example:**

```bash
# Get all tasks
curl http://localhost:8000/api/tasks

# Get tasks for agent 1
curl http://localhost:8000/api/tasks?agent_id=1

# Get failed tasks
curl http://localhost:8000/api/tasks?status=failed

# Pagination
curl http://localhost:8000/api/tasks?limit=20&offset=40
```

### Get Task Details

Get detailed information about a specific task.

**Endpoint:** `GET /api/tasks/{task_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| task_id | integer | Yes | Task ID |

**Response:** `200 OK`

```json
{
  "id": 123,
  "agent_id": 1,
  "status": "completed",
  "scheduled_at": "2026-01-11T18:00:00Z",
  "started_at": "2026-01-11T18:00:01Z",
  "completed_at": "2026-01-11T18:00:15Z",
  "result": "Stock price: $850.00\nAlert sent: No",
  "error": null,
  "retry_count": 0,
  "created_at": "2026-01-11T18:00:00Z"
}
```

**Response:** `404 Not Found`

```json
{
  "detail": "Task 123 not found"
}
```

**Example:**

```bash
curl http://localhost:8000/api/tasks/123
```

### Execute Agent Manually

Trigger immediate execution of an agent (bypasses schedule).

**Endpoint:** `POST /api/tasks/execute`

**Request Body:**

```json
{
  "agent_id": 1
}
```

**Response:** `200 OK`

```json
{
  "status": "completed",
  "result": "Stock price: $850.00",
  "error": "",
  "duration": 14.2,
  "task_id": 124
}
```

**Response:** `404 Not Found`

```json
{
  "detail": "Agent with id 1 not found"
}
```

**Response:** `500 Internal Server Error`

```json
{
  "detail": "Execution failed: timeout exceeded"
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{"agent_id": 1}'
```

**Special Cases:**

If the agent is already running, execution will be skipped:

```json
{
  "status": "skipped",
  "result": "",
  "error": "Agent is already running in another instance",
  "duration": 0,
  "task_id": 123
}
```

### Get Agent Task History

Get execution history for a specific agent.

**Endpoint:** `GET /api/tasks/agents/{agent_id}/tasks`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| agent_id | integer | Yes | Agent ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | integer | No | Maximum number of results (1-500, default: 50) |

**Response:** `200 OK`

```json
[
  {
    "id": 125,
    "agent_id": 1,
    "status": "completed",
    "scheduled_at": "2026-01-11T19:00:00Z",
    "started_at": "2026-01-11T19:00:01Z",
    "completed_at": "2026-01-11T19:00:12Z",
    "result": "Stock price: $855.00\nAlert sent: Yes",
    "error": null,
    "retry_count": 0,
    "created_at": "2026-01-11T19:00:00Z"
  },
  {
    "id": 124,
    "agent_id": 1,
    "status": "completed",
    "scheduled_at": "2026-01-11T18:00:00Z",
    "started_at": "2026-01-11T18:00:01Z",
    "completed_at": "2026-01-11T18:00:15Z",
    "result": "Stock price: $850.00\nAlert sent: No",
    "error": null,
    "retry_count": 0,
    "created_at": "2026-01-11T18:00:00Z"
  }
]
```

**Example:**

```bash
# Get last 50 tasks for agent 1
curl http://localhost:8000/api/tasks/agents/1/tasks

# Get last 10 tasks
curl http://localhost:8000/api/tasks/agents/1/tasks?limit=10
```

## Task Status Values

| Status | Description |
|--------|-------------|
| `pending` | Task is scheduled but not yet started |
| `running` | Task is currently executing |
| `completed` | Task finished successfully |
| `failed` | Task failed with an error |

## Task Lifecycle

```
pending → running → completed
                 ↘ failed
```

1. **pending**: Task is created and scheduled
2. **running**: Agent code is executing
3. **completed**: Execution finished successfully (exit code 0)
4. **failed**: Execution failed (exit code non-zero or timeout)

## Error Handling

### Common Errors

**Agent Not Found:**

```json
{
  "detail": "Agent with id 999 not found"
}
```

**Task Not Found:**

```json
{
  "detail": "Task 999 not found"
}
```

**Execution Timeout:**

```json
{
  "detail": "Execution failed: timed out after 300 seconds"
}
```

**Resource Exhaustion:**

```json
{
  "detail": "Execution failed: max concurrent agents reached"
}
```

## Integration with Harness

Tasks are automatically created by the Agent Harness when:

1. An agent is scheduled to run (via cron schedule)
2. An agent is manually executed via `POST /api/tasks/execute`

The harness uses distributed locking to prevent duplicate task execution during rolling deployments.

## Database Schema

```sql
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    agent_id INT REFERENCES agents(id),
    status VARCHAR(50) DEFAULT 'pending',
    scheduled_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result TEXT,
    error TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_agent_created (agent_id, created_at DESC),
    INDEX idx_status (status)
);
```

## Best Practices

1. **Monitor task status** regularly to detect failing agents
2. **Use filters** to query specific agent history
3. **Implement retries** for transient failures
4. **Set reasonable timeouts** to prevent runaway agents
5. **Archive old tasks** to prevent database bloat

## Performance Considerations

- Tasks are indexed by `agent_id` and `created_at` for fast history queries
- Result and error fields are stored as TEXT (unlimited length)
- Recommended to archive tasks older than 90 days

## Example Workflows

### Monitor Agent Execution

```python
import httpx

async with httpx.AsyncClient() as client:
    # Get recent tasks for agent 1
    response = await client.get(
        "http://localhost:8000/api/tasks/agents/1/tasks",
        params={"limit": 10}
    )
    tasks = response.json()

    # Check for failures
    failed = [t for t in tasks if t["status"] == "failed"]
    if failed:
        print(f"Alert: {len(failed)} failed tasks")
```

### Trigger Manual Execution

```python
import httpx

async with httpx.AsyncClient() as client:
    # Execute agent immediately
    response = await client.post(
        "http://localhost:8000/api/tasks/execute",
        json={"agent_id": 1}
    )
    result = response.json()

    if result["status"] == "completed":
        print(f"Success: {result['result']}")
    else:
        print(f"Error: {result['error']}")
```

### Query Task History

```python
import httpx

async with httpx.AsyncClient() as client:
    # Get all failed tasks
    response = await client.get(
        "http://localhost:8000/api/tasks",
        params={"status": "failed", "limit": 100}
    )
    failed_tasks = response.json()

    # Group by agent
    by_agent = {}
    for task in failed_tasks:
        agent_id = task["agent_id"]
        by_agent.setdefault(agent_id, []).append(task)

    for agent_id, tasks in by_agent.items():
        print(f"Agent {agent_id}: {len(tasks)} failures")
```

## See Also

- [Agent API Reference](factory.md)
- [Harness API Reference](harness.md)
- [Database Documentation](database.md)
