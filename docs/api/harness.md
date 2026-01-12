# Agent Harness API Documentation

## Overview

The Agent Harness provides 24/7 orchestration and execution infrastructure for autonomous agents. It handles scheduling, resource management, state persistence, and task execution.

**Module:** `src.harness`

**Components:**
- **Executor** - Executes agent code in isolated subprocesses
- **Scheduler** - Orchestrates scheduled execution with APScheduler
- **Resources** - Manages memory/CPU limits and concurrency control
- **Handoff** - Preserves state between agent runs

---

## Executor (`src/harness/executor.py`)

### Core Function

#### `execute_agent_code(agent_code, config=None, timeout=300)`

Executes agent code in an isolated subprocess with timeout protection.

**Parameters:**
- `agent_code` (str): Python code containing Agent class definition
- `config` (dict, optional): Configuration dictionary passed to Agent.__init__()
- `timeout` (int, optional): Maximum execution time in seconds (default: 300)

**Returns:**
- `ExecutionResult` object with status, result, stdout, stderr, exit_code, duration

**Raises:**
- `ValueError`: If agent_code is empty
- `ExecutionError`: If execution setup fails

**Example:**
```python
from src.harness import execute_agent_code

code = '''
class Agent:
    def __init__(self, config):
        self.config = config

    async def execute(self):
        return {"status": "success", "result": "Hello, World!"}
'''

result = await execute_agent_code(code, config={}, timeout=60)
print(result.status)  # 'success'
print(result.result)  # {'status': 'success', 'result': 'Hello, World!'}
```

### Classes

#### `ExecutionResult`

Container for execution results.

**Attributes:**
- `status` (str): 'success', 'error', or 'timeout'
- `result` (dict): Output data from agent.execute()
- `error` (str | None): Error message if failed
- `stdout` (str): Standard output captured
- `stderr` (str): Standard error captured
- `exit_code` (int): Process exit code
- `duration` (float): Execution duration in seconds

**Methods:**
- `to_dict()` → dict: Serialize to dictionary

#### `ExecutionError`

Exception raised when agent execution fails.

---

## Scheduler (`src/harness/scheduler.py`)

### Core Class

#### `AgentScheduler(session_factory)`

24/7 orchestration of agent execution using APScheduler.

**Parameters:**
- `session_factory`: Callable that returns AsyncSession (async context manager)

**Example:**
```python
from src.harness import AgentScheduler
from src.api.database import get_session

scheduler = AgentScheduler(get_session)
await scheduler.start()

# Scheduler now runs agents based on their cron schedules
```

### Methods

#### `await start()`

Start the scheduler and load agent schedules from database.

Loads all active agents and schedules their execution based on config.schedule.

**Raises:**
- `SchedulerError`: If scheduler is already running

#### `await stop()`

Stop the scheduler and cancel all jobs.

#### `await add_agent(agent)`

Dynamically add agent to scheduler without restart.

**Parameters:**
- `agent` (Agent): Agent model instance

#### `await remove_agent(agent_id)`

Remove agent from scheduler.

**Parameters:**
- `agent_id` (int): ID of agent to remove

### Functions

#### `await execute_scheduled_task(agent_id, session)`

Execute a scheduled agent task with idempotency protection.

Uses PostgreSQL advisory locks to prevent duplicate execution across replicas.

**Parameters:**
- `agent_id` (int): ID of agent to execute
- `session` (AsyncSession): Database session

**Raises:**
- `SchedulerError`: If agent not found

### Agent Schedule Configuration

Agents are scheduled using cron expressions in their `config` JSON field:

```json
{
  "schedule": "0 */6 * * *",
  "timeout": 300,
  "max_retries": 3
}
```

**Cron Format:** `minute hour day month day_of_week`

**Examples:**
- `"0 * * * *"` - Every hour at minute 0
- `"*/15 * * * *"` - Every 15 minutes
- `"0 */6 * * *"` - Every 6 hours
- `"0 9 * * 1-5"` - 9am Monday-Friday

### Advisory Locks

#### `async with advisory_lock(session, lock_name) as acquired:`

PostgreSQL advisory lock context manager for idempotent execution.

**Parameters:**
- `session` (AsyncSession): Database session
- `lock_name` (str): Unique lock identifier

**Yields:**
- `bool`: True if lock acquired, False otherwise

**Example:**
```python
async with advisory_lock(session, "agent_1_execution") as acquired:
    if acquired:
        # Only one process executes this
        await execute_agent(agent_id=1)
    else:
        # Another process is already running it
        logger.info("Skipping duplicate execution")
```

---

## Resources (`src/harness/resources.py`)

### Core Class

#### `ResourceMonitor(limits=None)`

Monitor system resources and enforce execution limits.

**Parameters:**
- `limits` (ResourceLimits, optional): Resource limit configuration

**Example:**
```python
from src.harness import ResourceMonitor, ResourceLimits

limits = ResourceLimits(
    max_concurrent_agents=5,
    max_memory_mb=256,
    max_cpu_percent=50.0
)

monitor = ResourceMonitor(limits)
resources = await monitor.check_resources()
print(resources['memory_percent'])  # 42.5
```

### Methods

#### `await check_resources()`

Check current system resource usage.

**Returns:**
- dict with `memory_percent`, `memory_available_mb`, `cpu_percent`

#### `async with acquire_slot():`

Acquire execution slot (semaphore) for agent.

Blocks if max concurrent agents are already running.

**Example:**
```python
async with monitor.acquire_slot():
    # Execute agent (releases slot automatically on exit)
    result = await execute_agent_code(agent_code)
```

#### `is_resource_available()`

Check if resources are available for new agent execution.

**Returns:**
- `bool`: True if sufficient resources available

#### `await wait_for_resources(timeout=60.0)`

Wait for resources to become available.

**Parameters:**
- `timeout` (float): Maximum seconds to wait

**Returns:**
- `bool`: True if resources became available, False if timed out

### Classes

#### `ResourceLimits`

Configuration for agent resource limits.

**Attributes:**
- `max_concurrent_agents` (int): Max parallel executions (default: 5)
- `max_memory_mb` (int): Max memory per agent in MB (default: 256)
- `max_cpu_percent` (float): Max CPU per agent 0-100 (default: 50.0)
- `memory_warning_threshold` (float): Log warning at % (default: 80.0)
- `cpu_warning_threshold` (float): Log warning at % (default: 75.0)

### Global Functions

#### `get_resource_monitor()`

Get global ResourceMonitor singleton.

#### `set_resource_limits(limits)`

Set resource limits for global monitor.

---

## Handoff Artifacts (`src/harness/handoff.py`)

### Core Class

#### `HandoffArtifact`

Container for state passed between agent executions.

**Attributes:**
- `agent_id` (int): Agent ID
- `run_number` (int): Sequential execution count
- `state` (dict): Arbitrary state data
- `metadata` (dict): Execution metadata
- `created_at` (datetime): Artifact creation timestamp
- `compressed` (bool): Whether state is compressed
- `summary` (str): Human-readable run summary

**Methods:**
- `to_dict()` → dict: Serialize to dictionary
- `to_json()` → str: Serialize to JSON string
- `from_dict(data)` → HandoffArtifact: Deserialize from dict (classmethod)
- `from_json(json_str)` → HandoffArtifact: Deserialize from JSON (classmethod)

**Example:**
```python
from src.harness import HandoffArtifact

artifact = HandoffArtifact(
    agent_id=1,
    run_number=5,
    state={"count": 42, "last_value": "xyz"},
    summary="Processed 42 items"
)

# Serialize for storage
json_str = artifact.to_json()

# Deserialize from storage
restored = HandoffArtifact.from_json(json_str)
```

#### `HandoffManager`

Manages handoff artifacts for agent state persistence.

**Methods:**

#### `await save_artifact(artifact)`

Save handoff artifact for agent.

**Parameters:**
- `artifact` (HandoffArtifact): Artifact to save

#### `await load_artifact(agent_id)`

Load previous handoff artifact for agent.

**Parameters:**
- `agent_id` (int): Agent ID

**Returns:**
- `HandoffArtifact | None`: Previous artifact or None

#### `await create_next_artifact(agent_id, result, execution_metadata=None)`

Create handoff artifact for next run based on current results.

Automatically increments run_number and preserves relevant state.

**Parameters:**
- `agent_id` (int): Agent ID
- `result` (dict): Results from current execution
- `execution_metadata` (dict, optional): Metadata (duration, status, etc.)

**Returns:**
- `HandoffArtifact`: New artifact for next run

#### `await clear_artifact(agent_id)`

Clear handoff artifact for agent.

**Parameters:**
- `agent_id` (int): Agent ID

#### `compress_state(state, max_size=10000)`

Compress state by removing old or large data.

**Parameters:**
- `state` (dict): State to compress
- `max_size` (int): Maximum size in characters

**Returns:**
- `dict`: Compressed state

### Global Function

#### `get_handoff_manager()`

Get global HandoffManager singleton.

**Example:**
```python
from src.harness import get_handoff_manager

manager = get_handoff_manager()

# After agent execution
await manager.create_next_artifact(
    agent_id=1,
    result={"processed": 100},
    execution_metadata={"duration": 5.2}
)

# On next execution
previous = await manager.load_artifact(agent_id=1)
if previous:
    print(f"Previous run #{previous.run_number}: {previous.state}")
```

---

## Task Management API

### Endpoints

#### `GET /api/tasks/{task_id}`

Get specific task by ID.

**Response:** Task model

**Status Codes:**
- 200: Success
- 404: Task not found

#### `GET /api/tasks/agent/{agent_id}`

Get execution history for specific agent.

**Query Parameters:**
- `limit` (int): Max tasks to return (default: 50, max: 100)
- `offset` (int): Number to skip (default: 0)

**Response:** List of Task models (most recent first)

#### `POST /api/tasks/{task_id}/retry`

Retry a failed task.

Creates new task and executes immediately.

**Response:** Newly created Task model

**Status Codes:**
- 201: Task created and executed
- 400: Cannot retry (not failed/timeout)
- 404: Task not found

#### `DELETE /api/tasks/{task_id}`

Delete a task permanently.

**Status Codes:**
- 204: Deleted successfully
- 400: Cannot delete running task
- 404: Task not found

#### `GET /api/tasks/stats/summary`

Get task execution statistics.

**Response:**
```json
{
  "total": 100,
  "completed": 85,
  "failed": 10,
  "running": 5,
  "pending": 0,
  "success_rate": 85.0
}
```

---

## Integration Example

Complete example of using the harness:

```python
from src.harness import (
    AgentScheduler,
    execute_agent_code,
    get_resource_monitor,
    get_handoff_manager,
    ResourceLimits,
)
from src.api.database import get_session

# Configure resources
limits = ResourceLimits(max_concurrent_agents=10)
monitor = get_resource_monitor()

# Execute agent immediately
code = '''
class Agent:
    async def execute(self):
        return {"status": "success", "result": "Done!"}
'''

async with monitor.acquire_slot():
    result = await execute_agent_code(code, timeout=60)
    print(result.status)

# Start scheduler for recurring execution
scheduler = AgentScheduler(get_session)
await scheduler.start()

# Scheduler automatically runs agents based on config.schedule

# Manage state between runs
manager = get_handoff_manager()
artifact = await manager.load_artifact(agent_id=1)
if artifact:
    print(f"Previous run: {artifact.state}")
```

---

## Database Schema

### Task Table

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
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tasks_agent_id ON tasks(agent_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_scheduled_at ON tasks(scheduled_at);
```

---

## Performance Considerations

1. **Concurrency Control**
   - Default: 5 concurrent agents max
   - Increase for powerful machines: `ResourceLimits(max_concurrent_agents=20)`
   - Monitor memory usage per agent

2. **Timeout Configuration**
   - Default: 300 seconds (5 minutes)
   - Adjust per agent: `config={"timeout": 600}`
   - Set based on expected agent duration

3. **Advisory Locks**
   - Uses PostgreSQL pg_try_advisory_lock
   - Zero overhead (in-memory mutex)
   - Prevents duplicate execution on Railway multi-replica deploys

4. **State Compression**
   - Automatic for states > 10KB
   - Keeps last 100 items of lists
   - Preserves essential keys (status, error, count)

---

## Security Considerations

1. **Subprocess Isolation**
   - Agents run in separate processes
   - Failures don't crash main application
   - Timeout protection prevents runaway agents

2. **Resource Limits**
   - Memory limits per agent (default: 256MB)
   - CPU throttling (default: 50%)
   - Max concurrent executions enforced

3. **Input Validation**
   - Agent code is validated before execution
   - Config JSON is parsed safely
   - Timeout values are bounded

---

## Troubleshooting

### Agent Timeout

```python
# Symptom: ExecutionResult.status == 'timeout'
# Solution: Increase timeout in config
config = {"timeout": 600}  # 10 minutes
```

### Too Many Concurrent Executions

```python
# Symptom: ResourceMonitor logs "No execution slots available"
# Solution: Increase concurrent limit
from src.harness import set_resource_limits, ResourceLimits

set_resource_limits(ResourceLimits(max_concurrent_agents=10))
```

### High Memory Usage

```python
# Symptom: System memory > 80% warning
# Solution: Reduce concurrent agents or check for memory leaks
limits = ResourceLimits(
    max_concurrent_agents=3,
    max_memory_mb=512  # Increase per-agent limit
)
```

### Duplicate Execution on Railway

```python
# Symptom: Task runs twice on deployments
# Solution: Advisory locks prevent this automatically
# Verify: Check task.retry_count stays low
```

---

## Related Documentation

- [Agent Factory API](factory.md) - Agent code generation
- [Database API](database.md) - Database connection management
- [Models API](models.md) - Agent and Task schemas
- [FastAPI API](fastapi.md) - REST API endpoints
