# Agent Harness API

## Overview

The Agent Harness provides 24/7 orchestration infrastructure for autonomous agent execution. It handles code execution, state preservation, automatic scheduling, and resource management.

**Key Components:**

- **Executor** - Safe code execution in isolated subprocesses
- **Handoff Manager** - State preservation between runs (Dual-Agent Pattern)
- **Task Scheduler** - Automatic scheduling with cron/interval triggers
- **Resource Manager** - Memory, CPU, and process monitoring

---

## AgentExecutor

Execute generated agent code safely with timeout protection and resource limits.

### Class: `AgentExecutor`

```python
from src.harness import AgentExecutor

executor = AgentExecutor(
    timeout_seconds=300,  # 5 minutes default
    max_memory_mb=256
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout_seconds` | int | 300 | Maximum execution time (5 minutes) |
| `max_memory_mb` | int | 256 | Maximum memory usage in MB |

### Method: `execute_agent()`

Execute an agent and create task record.

```python
result = await executor.execute_agent(
    agent_id=1,
    context={"key": "value"}  # Optional context dict
)
```

#### Returns: `ExecutionResult`

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether execution succeeded |
| `stdout` | str | Captured standard output |
| `stderr` | str | Captured standard error |
| `exit_code` | int | Process exit code |
| `duration_seconds` | float | Execution duration |
| `error_message` | str \| None | Error description if failed |

#### Example

```python
from src.harness import AgentExecutor

executor = AgentExecutor(timeout_seconds=60)
result = await executor.execute_agent(agent_id=1)

if result.success:
    print(f"Output: {result.stdout}")
else:
    print(f"Error: {result.error_message}")
```

---

## HandoffManager

Manage state persistence for long-running agents using the Dual-Agent Pattern.

### Class: `HandoffManager`

```python
from src.harness import HandoffManager

manager = HandoffManager()
```

### Method: `load_artifact()`

Load latest handoff artifact for an agent.

```python
artifact = await manager.load_artifact(agent_id=1)
```

#### Returns: `HandoffArtifact | None`

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | int | Database ID of agent |
| `state` | dict | Serializable state dictionary |
| `summary` | str | Human-readable summary |
| `created_at` | datetime | When artifact was created |
| `run_count` | int | Number of runs since initialization |

Returns `None` on first run (no artifact yet).

### Method: `save_artifact()`

Save handoff artifact after agent execution.

```python
artifact = await manager.save_artifact(
    agent_id=1,
    state={"counter": 42, "last_value": "test"},
    summary="Processed 10 items"
)
```

### Method: `clear_artifact()`

Reset agent state (clear artifact).

```python
await manager.clear_artifact(agent_id=1)
```

### Method: `compress_context()`

Compress execution output into compact state.

```python
compressed = await manager.compress_context(
    agent_id=1,
    raw_output="Long output...",
    previous_state={"key": "value"}
)
```

#### Example: Long-Running Agent with State

```python
from src.harness import AgentExecutor, HandoffManager

executor = AgentExecutor()
manager = HandoffManager()

# Load previous state
artifact = await manager.load_artifact(agent_id=1)
context = artifact.state if artifact else {}

# Execute with context
result = await executor.execute_agent(agent_id=1, context=context)

# Save new state
if result.success:
    new_state = await manager.compress_context(
        agent_id=1,
        raw_output=result.stdout,
        previous_state=context
    )
    await manager.save_artifact(agent_id=1, state=new_state)
```

---

## TaskScheduler

Automatic agent execution scheduling with cron or interval triggers.

### Class: `TaskScheduler`

```python
from src.harness import TaskScheduler

scheduler = TaskScheduler(
    max_concurrent=5,       # Max concurrent executions
    retry_max_attempts=3    # Max retry attempts
)
```

### Method: `start()`

Start the scheduler and load all agent schedules.

```python
await scheduler.start()
```

### Method: `stop()`

Stop the scheduler gracefully.

```python
await scheduler.stop()
```

### Method: `add_agent_schedule()`

Add or update schedule for an agent.

```python
await scheduler.add_agent_schedule(agent_id=1)
```

Schedule configuration is stored in `agent.config` JSON:

```json
{
  "schedule": {
    "type": "interval",
    "interval_minutes": 60,
    "enabled": true
  }
}
```

**Or with cron syntax:**

```json
{
  "schedule": {
    "type": "cron",
    "cron": "0 * * * *",
    "enabled": true
  }
}
```

### Method: `remove_agent_schedule()`

Remove schedule for an agent.

```python
await scheduler.remove_agent_schedule(agent_id=1)
```

### Method: `retry_failed_task()`

Retry a failed task with exponential backoff.

```python
await scheduler.retry_failed_task(task_id=123)
```

Retry delays: 2s, 4s, 8s (exponential backoff).

#### Example: Scheduled Agent Execution

```python
from src.harness import TaskScheduler

scheduler = TaskScheduler()
await scheduler.start()

# Schedule runs every 30 minutes
await scheduler.add_agent_schedule(agent_id=1)

# Keep running...
# (scheduler executes agents automatically in background)
```

---

## ResourceManager

Monitor and enforce resource limits for agent execution.

### Class: `ResourceManager`

```python
from src.harness import ResourceManager, ResourceLimits

manager = ResourceManager()
limits = ResourceLimits(
    max_memory_mb=256,
    max_cpu_percent=80.0,
    max_processes=5
)
```

### Method: `get_process_usage()`

Get current resource usage for a process.

```python
usage = manager.get_process_usage(process_id=12345)
```

#### Returns: `dict`

| Field | Type | Description |
|-------|------|-------------|
| `memory_mb` | float | Memory usage in MB |
| `cpu_percent` | float | CPU usage percentage |
| `num_threads` | int | Number of threads |
| `num_children` | int | Number of child processes |

### Method: `exceeds_limits()`

Check if resource usage exceeds limits.

```python
if manager.exceeds_limits(usage, limits):
    print("Resource limit exceeded!")
```

### Method: `get_system_resources()`

Get overall system resource availability.

```python
resources = manager.get_system_resources()
# Returns: total_memory_mb, available_memory_mb, memory_percent, cpu_count, cpu_percent
```

### Method: `kill_process()`

Terminate a process.

```python
manager.kill_process(process_id=12345, force=False)
```

#### Example: Resource Monitoring

```python
from src.harness import ResourceManager, ResourceLimits
import time

manager = ResourceManager()
limits = ResourceLimits(max_memory_mb=128)

# Monitor process
process_id = 12345
while True:
    usage = manager.get_process_usage(process_id)

    if manager.exceeds_limits(usage, limits):
        print(f"Memory limit exceeded: {usage['memory_mb']:.2f}MB")
        manager.kill_process(process_id)
        break

    time.sleep(1)
```

---

## Task API Endpoints

REST API for viewing execution history and managing tasks.

### `GET /api/tasks/agents/{agent_id}/tasks`

Get execution history for an agent.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (pending/running/completed/failed) |
| `limit` | int | Maximum results (default: 100) |
| `offset` | int | Pagination offset (default: 0) |

**Response:**

```json
{
  "tasks": [
    {
      "id": 1,
      "agent_id": 1,
      "status": "completed",
      "started_at": "2026-01-11T10:00:00Z",
      "completed_at": "2026-01-11T10:00:15Z",
      "result": "Processed 10 items",
      "retry_count": 0
    }
  ],
  "total_count": 42,
  "limit": 100,
  "offset": 0
}
```

**Example:**

```bash
curl http://localhost:8000/api/tasks/agents/1/tasks?status=completed&limit=10
```

### `GET /api/tasks/{task_id}`

Get details for a specific task.

**Response:**

```json
{
  "id": 123,
  "agent_id": 1,
  "status": "completed",
  "scheduled_at": "2026-01-11T10:00:00Z",
  "started_at": "2026-01-11T10:00:01Z",
  "completed_at": "2026-01-11T10:00:15Z",
  "result": "Success output",
  "error": null,
  "retry_count": 0,
  "created_at": "2026-01-11T09:59:55Z"
}
```

**Example:**

```bash
curl http://localhost:8000/api/tasks/123
```

### `POST /api/tasks/{task_id}/retry`

Retry a failed task.

**Response:**

```json
{
  "message": "Task 123 scheduled for retry",
  "retry_count": 2,
  "max_retries": 3
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/tasks/123/retry
```

---

## Complete Example: 24/7 Agent System

```python
import asyncio
from src.harness import AgentExecutor, HandoffManager, TaskScheduler

async def main():
    # Initialize components
    executor = AgentExecutor()
    manager = HandoffManager()
    scheduler = TaskScheduler()

    # Start scheduler
    await scheduler.start()

    # Add agent schedule (runs every hour)
    await scheduler.add_agent_schedule(agent_id=1)

    print("Agent system running 24/7...")
    print("Press Ctrl+C to stop")

    try:
        # Keep running
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        await scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Architecture: Execute-Summarize-Reset Loop

The harness implements a continuous execution loop:

```
1. LOAD: Load handoff artifact (previous state)
   ↓
2. EXECUTE: Run agent code with context
   ↓
3. SUMMARIZE: Compress output into new state
   ↓
4. RESET: Save artifact for next run
   ↓
5. SCHEDULE: Wait for next trigger
   ↓
(repeat)
```

This pattern allows agents to maintain long-running memory across hundreds of executions without context overflow.

---

## Success Criteria

| Metric | Target | Status |
|--------|--------|--------|
| Agent uptime | 24/7 | ✅ |
| Context preservation | 100+ runs | ✅ |
| Execution timeout | < 5 minutes | ✅ |
| Resource limits enforced | 100% | ✅ |
| Retry max attempts | 3 | ✅ |

---

## Next Steps

- **Phase 3.4: MCP Tools** - Browser automation, filesystem, notifications
- **Production deployment** - Railway integration
- **Monitoring** - Prometheus metrics, alerting
- **Advanced features** - Multi-agent coordination, dependency graphs
