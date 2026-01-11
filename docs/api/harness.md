# Agent Harness API Reference

The Agent Harness provides 24/7 orchestration for autonomous agent execution, including scheduling, resource management, and context preservation.

## Overview

The harness consists of four main components:

1. **Executor** - Loads and executes agent code in sandboxed subprocesses
2. **Scheduler** - APScheduler integration with distributed locking
3. **Resources** - Resource monitoring and limits (memory, CPU)
4. **Handoff** - Context preservation between agent runs (Dual-Agent Pattern)

## Executor

### `AgentExecutor`

Executes agent code in sandboxed subprocess with safety constraints.

```python
from src.harness.executor import AgentExecutor

executor = AgentExecutor(
    timeout=300,  # 5 minutes
    max_output_size=1024*1024  # 1MB
)

result = await executor.execute_agent(agent_id=1, session=session)
```

**Parameters:**

- `timeout` (int): Maximum execution time in seconds (default: 300)
- `max_output_size` (int): Maximum stdout/stderr size in bytes (default: 1MB)

**Methods:**

#### `execute_agent(agent_id: int, session: AsyncSession) -> dict`

Execute an agent and create a task record.

**Returns:**

```python
{
    "status": "completed" | "failed",
    "result": "Agent output (stdout)",
    "error": "Error message if failed",
    "duration": 12.5  # seconds
}
```

**Raises:**

- `ValueError`: If agent not found or has no code

### `execute_agent_by_id()`

Convenience function to execute an agent by ID.

```python
from src.harness.executor import execute_agent_by_id

result = await execute_agent_by_id(
    agent_id=1,
    session=session,
    timeout=30  # Optional timeout override
)
```

## Scheduler

### `AgentScheduler`

Schedules and manages periodic agent execution with distributed locking.

```python
from src.harness.scheduler import get_scheduler

scheduler = await get_scheduler()
await scheduler.start()

# Schedule agent to run hourly
await scheduler.schedule_agent(agent_id=1, cron_expression="0 * * * *")
```

**Methods:**

#### `start()`

Start the scheduler and load agent schedules from database.

```python
await scheduler.start()
```

#### `stop()`

Stop the scheduler gracefully.

```python
await scheduler.stop()
```

#### `schedule_agent(agent_id: int, cron_expression: str, job_id: str = None)`

Schedule an agent to run on a cron schedule.

**Parameters:**

- `agent_id`: ID of the agent to schedule
- `cron_expression`: Cron expression (e.g., "0 * * * *" for hourly)
- `job_id`: Optional job ID (defaults to "agent_{agent_id}")

**Examples:**

```python
# Every hour
await scheduler.schedule_agent(1, "0 * * * *")

# Daily at midnight
await scheduler.schedule_agent(1, "0 0 * * *")

# Every 5 minutes
await scheduler.schedule_agent(1, "*/5 * * * *")

# Monday-Friday at 9 AM
await scheduler.schedule_agent(1, "0 9 * * 1-5")
```

#### `unschedule_agent(agent_id: int)`

Remove an agent from the schedule.

```python
await scheduler.unschedule_agent(1)
```

#### `execute_now(agent_id: int) -> dict`

Execute an agent immediately (manual trigger).

```python
result = await scheduler.execute_now(1)
```

### `distributed_lock()`

Acquire a distributed lock using PostgreSQL Advisory Locks.

```python
from src.harness.scheduler import distributed_lock

async with distributed_lock(session, "agent_1") as acquired:
    if acquired:
        # Lock acquired, execute task
        print("Running task")
    else:
        # Another instance is running this task
        print("Task already running")
```

**Parameters:**

- `session`: Database session
- `lock_name`: Unique name for the lock

**Yields:**

- `bool`: True if lock was acquired, False otherwise

## Resources

### `ResourceManager`

Manages resource allocation and monitoring for agent execution.

```python
from src.harness.resources import ResourceManager, ResourceLimits

limits = ResourceLimits(
    max_memory_mb=256,
    max_cpu_percent=50.0,
    max_concurrent_agents=5,
    max_execution_time=300
)

manager = ResourceManager(limits)

# Acquire resources
if await manager.acquire():
    try:
        # Run agent
        pass
    finally:
        await manager.release()
```

**Methods:**

#### `acquire() -> bool`

Acquire resources for agent execution.

**Returns:**

- `bool`: True if resources acquired, False if limits exceeded

#### `release()`

Release resources after agent execution completes.

Must be called in a finally block to ensure resources are freed.

#### `get_usage() -> ResourceUsage`

Get current resource usage statistics.

```python
usage = manager.get_usage()
print(f"Memory: {usage.memory_mb:.0f}MB")
print(f"CPU: {usage.cpu_percent:.1f}%")
print(f"Active agents: {usage.active_agents}")
```

**Returns:**

```python
ResourceUsage(
    memory_mb=150.5,
    memory_percent=45.2,
    cpu_percent=32.1,
    active_agents=3
)
```

#### `check_limits(usage: ResourceUsage) -> tuple[bool, str]`

Check if resource usage is within limits.

**Returns:**

- Tuple of `(within_limits: bool, violation_message: str)`

```python
ok, msg = manager.check_limits(usage)
if not ok:
    print(f"Limit violation: {msg}")
```

### `ResourceLimits`

Resource limits configuration.

```python
from src.harness.resources import ResourceLimits

limits = ResourceLimits(
    max_memory_mb=256,           # Maximum memory per agent in MB
    max_cpu_percent=50.0,        # Maximum CPU usage per agent (0-100)
    max_concurrent_agents=5,     # Maximum concurrent executions
    max_execution_time=300       # Maximum execution time in seconds
)
```

## Handoff Artifacts

### `HandoffManager`

Manages handoff artifacts for agent context preservation.

```python
from src.harness.handoff import HandoffManager, HandoffContext

manager = HandoffManager()

# Save handoff after execution
context = HandoffContext(
    observations={"price": 850.0, "volume": 1000000},
    actions=[{"type": "alert", "message": "Price increased"}],
    state={"last_price": 840.0},
    metadata={"run_count": 5}
)

artifact = await manager.save_handoff(
    agent_id=1,
    task_id=123,
    context=context,
    summary="Monitored stock price",
    session=session,
    ttl_days=30
)

# Load latest handoff before next execution
context = await manager.load_latest_handoff(agent_id=1, session=session)
if context:
    print(f"Last state: {context.state}")
```

**Methods:**

#### `save_handoff(agent_id, task_id, context, summary, session, ttl_days=30) -> HandoffArtifact`

Save a handoff artifact after agent execution.

**Parameters:**

- `agent_id`: ID of the agent
- `task_id`: ID of the task that created this artifact
- `context`: HandoffContext to preserve
- `summary`: Human-readable summary
- `session`: Database session
- `ttl_days`: Time-to-live in days (default: 30)

**Returns:**

- `HandoffArtifact`: Created artifact

#### `load_latest_handoff(agent_id, session) -> HandoffContext | None`

Load the most recent handoff artifact for an agent.

**Returns:**

- `HandoffContext` if found, `None` otherwise

#### `load_handoff_history(agent_id, session, limit=10) -> list[tuple[HandoffArtifact, HandoffContext]]`

Load handoff history for an agent.

**Parameters:**

- `agent_id`: ID of the agent
- `session`: Database session
- `limit`: Maximum number of artifacts to load (default: 10)

**Returns:**

- List of (artifact, context) tuples, newest first

#### `cleanup_expired(session) -> int`

Delete expired handoff artifacts.

**Returns:**

- Number of artifacts deleted

### `HandoffContext`

Context data structure for agent handoff.

```python
from src.harness.handoff import HandoffContext

context = HandoffContext(
    observations={"key": "value"},  # What the agent observed
    actions=[{"type": "action"}],   # What actions were taken
    state={"key": "value"},          # Current state variables
    metadata={"key": "value"}        # Additional metadata
)

# Serialize to JSON
json_str = context.to_json()

# Deserialize from JSON
loaded = HandoffContext.from_json(json_str)
```

**Attributes:**

- `observations` (dict): What the agent observed in this run
- `actions` (list[dict]): What actions the agent took
- `state` (dict): Current state variables to preserve
- `metadata` (dict): Additional metadata (run count, errors, etc.)

**Methods:**

- `to_json() -> str`: Serialize context to JSON string
- `from_json(json_str: str) -> HandoffContext`: Deserialize from JSON

### `HandoffArtifact`

Database model for handoff artifacts.

```python
class HandoffArtifact(SQLModel, table=True):
    id: int | None
    agent_id: int
    task_id: int
    context_data: str              # JSON-serialized context
    summary: str                   # Human-readable summary
    created_at: datetime
    expires_at: datetime | None
```

## Agent Configuration

Agents can be configured with schedules in their `config` JSON field:

```json
{
  "schedule": "0 * * * *",
  "enabled": true
}
```

**Fields:**

- `schedule`: Cron expression for scheduling
- `enabled`: Whether the agent should be scheduled (default: true)

## Task Endpoints

See the Tasks API endpoints for interacting with the harness:

- `GET /api/tasks` - List all tasks
- `GET /api/tasks/{id}` - Get task details
- `POST /api/tasks/execute` - Execute agent manually
- `GET /api/tasks/agents/{id}/tasks` - Get agent task history

## Integration Example

Complete example of using the harness:

```python
from src.api.database import get_session
from src.harness import get_scheduler, ResourceManager, HandoffManager

# Start scheduler
scheduler = await get_scheduler()
await scheduler.start()

# Schedule agent to run hourly
await scheduler.schedule_agent(
    agent_id=1,
    cron_expression="0 * * * *"
)

# Manual execution with resource management
async with get_session() as session:
    # Load previous context
    handoff_mgr = HandoffManager()
    prev_context = await handoff_mgr.load_latest_handoff(1, session)

    # Acquire resources
    resource_mgr = ResourceManager()
    if await resource_mgr.acquire():
        try:
            # Execute agent
            result = await scheduler.execute_now(1)

            # Save handoff for next run
            if result["status"] == "completed":
                context = HandoffContext(
                    observations={"result": result["result"]},
                    actions=[{"type": "execute"}],
                    state={"last_run": datetime.utcnow()},
                    metadata={"duration": result["duration"]}
                )
                await handoff_mgr.save_handoff(
                    agent_id=1,
                    task_id=result["task_id"],
                    context=context,
                    summary="Executed successfully",
                    session=session
                )
        finally:
            await resource_mgr.release()
```

## Database Schema

### handoff_artifacts Table

```sql
CREATE TABLE handoff_artifacts (
    id SERIAL PRIMARY KEY,
    agent_id INT REFERENCES agents(id),
    task_id INT REFERENCES tasks(id),
    context_data TEXT,              -- JSON-serialized context
    summary VARCHAR(2000),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    INDEX idx_agent_created (agent_id, created_at DESC),
    INDEX idx_expires (expires_at)
);
```

## Security Considerations

1. **Subprocess Isolation**: Agent code runs in isolated subprocesses to contain failures
2. **Resource Limits**: Memory and CPU limits prevent resource exhaustion
3. **Timeout Protection**: All executions have mandatory timeouts
4. **Distributed Locking**: Advisory locks prevent duplicate execution during rolling deployments
5. **Output Truncation**: stdout/stderr is truncated to prevent database bloat

## Performance Characteristics

- **Executor**: Subprocess overhead ~50-100ms per execution
- **Scheduler**: Advisory lock acquisition ~1-5ms
- **Resources**: Usage check ~10-20ms
- **Handoff**: Load/save artifact ~5-10ms

## Best Practices

1. **Use handoff artifacts** to maintain state between runs
2. **Set appropriate timeouts** based on agent complexity
3. **Monitor resource usage** to prevent bottlenecks
4. **Use cron expressions** for predictable scheduling
5. **Test agents locally** before deploying to production
6. **Cleanup expired handoffs** periodically to prevent database bloat

## See Also

- [Agent API Reference](factory.md)
- [Task API Reference](tasks.md)
- [Database Documentation](database.md)
