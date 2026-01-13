## Main Orchestrator

Complete autonomous deployment orchestration with OODA Loop pattern.

**Module:** `src.orchestrator`

## Overview

The Main Orchestrator coordinates Railway, GitHub, and n8n clients to autonomously manage deployments, handle failures, and maintain system health. Implements the OODA Loop (Observe-Orient-Decide-Act) for intelligent autonomous operations.

**Key Features:**
- ✅ OODA Loop implementation (Observe, Orient, Decide, Act)
- ✅ Multi-source data collection (Railway, GitHub, n8n)
- ✅ Context-aware decision making with policy engine
- ✅ Autonomous deployment management
- ✅ Automatic rollback on failure
- ✅ GitHub issue creation for investigation
- ✅ n8n workflow execution for alerts
- ✅ State machine integration for deployment lifecycle

---

## Quick Start

### Basic Usage

```python
from src.orchestrator import MainOrchestrator
from src.railway_client import RailwayClient
from src.github_app_client import GitHubAppClient
from src.n8n_client import N8nClient
from src.secrets_manager import SecretManager

# Initialize clients
manager = SecretManager()
railway = RailwayClient(api_key=manager.get_secret("RAILWAY-API"))
github = GitHubAppClient(
    app_id=123456,
    installation_id=789012,
    private_key=manager.get_secret("github-app-private-key")
)
n8n = N8nClient(
    base_url="https://n8n.railway.app",
    api_key=manager.get_secret("N8N-API")
)

# Initialize orchestrator
orchestrator = MainOrchestrator(
    railway=railway,
    github=github,
    n8n=n8n,
    project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
    environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
)

# Run single OODA cycle
decision = await orchestrator.run_cycle()
if decision:
    print(f"Executed action: {decision.action}")
```

### Continuous Operation

```python
# Run orchestrator continuously (production)
await orchestrator.run_continuous(interval_seconds=60)
```

### Event-Driven Operation

```python
# Handle GitHub webhook event
event = {
    "type": "push",
    "commit": "abc123",
    "ref": "refs/heads/main",
    "head_commit": {
        "sha": "abc123",
        "message": "fix: critical bug",
        "author": {"name": "developer@example.com"}
    }
}

result = await orchestrator.handle_deployment_event(event)
print(f"Deployment: {result['deployment_id']}")
```

---

## Core Classes

### MainOrchestrator

Main orchestrator implementing OODA loop for autonomous operations.

**Constructor:**
```python
MainOrchestrator(
    railway: RailwayClient,
    github: GitHubAppClient,
    n8n: N8nClient,
    project_id: str,
    environment_id: str,
    owner: str = "edri2or-commits",
    repo: str = "project38-or"
)
```

**Parameters:**
- `railway` - Railway GraphQL API client
- `github` - GitHub App REST API client
- `n8n` - n8n workflow orchestration client
- `project_id` - Railway project ID
- `environment_id` - Railway environment ID
- `owner` - GitHub repository owner
- `repo` - GitHub repository name

---

## OODA Loop Methods

### observe()

**Phase 1: OBSERVE** - Collect data from all sources (Railway, GitHub, n8n).

```python
observations = await orchestrator.observe()
for obs in observations:
    print(f"{obs.source}: {obs.data}")
```

**Returns:** `list[Observation]`

**Example Output:**
```python
[
    Observation(source='railway', data={'services': [...]}),
    Observation(source='github', data={'workflow_runs': {...}}),
    Observation(source='n8n', data={'recent_executions': [...]})
]
```

---

### orient()

**Phase 2: ORIENT** - Analyze observations and build world model.

```python
observations = await orchestrator.observe()
world_model = await orchestrator.orient(observations)
print(f"Railway services: {len(world_model.railway_state.get('services', []))}")
```

**Parameters:**
- `observations` - List of observations to analyze

**Returns:** `WorldModel` - Updated world model with context

---

### decide()

**Phase 3: DECIDE** - Make decision based on world model.

```python
world_model = await orchestrator.orient(observations)
decision = await orchestrator.decide(world_model)
if decision:
    print(f"Action: {decision.action}, Reason: {decision.reasoning}")
```

**Parameters:**
- `world_model` - Current understanding of system state

**Returns:** `Decision | None` - Decision to execute, or None if no action needed

**Decision Types:**
- `ActionType.DEPLOY` - Trigger new deployment
- `ActionType.ROLLBACK` - Rollback failed deployment
- `ActionType.CREATE_ISSUE` - Create GitHub issue for investigation
- `ActionType.MERGE_PR` - Merge pull request
- `ActionType.ALERT` - Send alert via n8n workflow
- `ActionType.EXECUTE_WORKFLOW` - Execute arbitrary n8n workflow

---

### act()

**Phase 4: ACT** - Execute decision through worker agents.

```python
decision = Decision(
    action=ActionType.ROLLBACK,
    reasoning="Deployment failed",
    parameters={"deployment_id": "abc123"}
)
result = await orchestrator.act(decision)
print(f"Rollback result: {result}")
```

**Parameters:**
- `decision` - Decision to execute

**Returns:** `dict[str, Any]` - Result of action execution

**Raises:**
- `ValueError` - If action type is not supported

---

## Complete Cycle

### run_cycle()

Run complete OODA cycle: Observe → Orient → Decide → Act.

```python
decision = await orchestrator.run_cycle()
if decision:
    print(f"Executed: {decision.action}")
else:
    print("No action needed")
```

**Returns:** `Decision | None` - Decision executed, or None if no action needed

---

### run_continuous()

Run OODA loop continuously with specified interval.

```python
# Run orchestrator every 60 seconds (production mode)
await orchestrator.run_continuous(interval_seconds=60)
```

**Parameters:**
- `interval_seconds` - Seconds between cycles (default: 60)

**Use Case:** Production deployment monitoring

---

## Event Handlers

### handle_deployment_event()

Handle deployment event from GitHub webhook.

```python
event = {
    "type": "push",
    "commit": "abc123",
    "ref": "refs/heads/main",
    "head_commit": {"sha": "abc123"}
}
result = await orchestrator.handle_deployment_event(event)
```

**Parameters:**
- `event` - GitHub webhook event data

**Returns:** `dict[str, Any]` - Result of deployment handling

**Behavior:**
- Only deploys `main` branch
- Skips feature branches
- Triggers Railway deployment
- Returns deployment ID and status

---

### handle_deployment_failure()

Handle deployment failure - automatically rollback and create issue.

```python
result = await orchestrator.handle_deployment_failure("deploy-123")
print(f"Rolled back to: {result.get('rollback_deployment_id')}")
```

**Parameters:**
- `deployment_id` - Failed deployment ID

**Returns:** `dict[str, Any] | None` - Result of failure handling

**Actions Taken:**
1. Find last successful deployment
2. Execute rollback
3. Create GitHub issue with logs
4. Return rollback result

---

## Supporting Classes

### Observation

Represents a single observation from a data source.

```python
obs = Observation(
    source="railway",
    timestamp=datetime.now(UTC),
    data={"status": "ACTIVE"},
    metadata={"project_id": "123"}
)
```

**Attributes:**
- `source` - Source system (railway, github, n8n)
- `timestamp` - When observation was made
- `data` - Observation data
- `metadata` - Additional context

---

### WorldModel

Represents the agent's understanding of current system state.

```python
wm = WorldModel()
wm.update(observation)
recent = wm.get_recent_observations(limit=10)
```

**Attributes:**
- `railway_state` - Railway deployment state
- `github_state` - GitHub CI/PR state
- `n8n_state` - n8n workflow state
- `observations` - Complete observation history
- `last_update` - Timestamp of last update

**Methods:**
- `update(observation)` - Integrate new observation
- `get_recent_observations(limit)` - Get recent observations

---

### Decision

Represents a decision made by the policy engine.

```python
decision = Decision(
    action=ActionType.DEPLOY,
    reasoning="New commit to main",
    parameters={"commit": "abc123"},
    priority=8
)
```

**Attributes:**
- `action` - Action to take (ActionType enum)
- `reasoning` - Why this decision was made
- `parameters` - Action parameters
- `priority` - Decision priority (1-10, higher = more urgent)
- `timestamp` - When decision was made

---

## Enums

### DeploymentState

Orchestrator state during OODA loop execution.

```python
class DeploymentState(str, Enum):
    IDLE = "idle"                  # No active operation
    OBSERVING = "observing"        # Collecting data
    ORIENTING = "orienting"        # Analyzing data
    DECIDING = "deciding"          # Making decision
    ACTING = "acting"              # Executing action
    SUCCESS = "success"            # Action succeeded
    FAILED = "failed"              # Action failed
    ROLLED_BACK = "rolled_back"    # Rolled back to previous version
```

---

### ActionType

Available action types for the orchestrator.

```python
class ActionType(str, Enum):
    DEPLOY = "deploy"                      # Trigger deployment
    ROLLBACK = "rollback"                  # Rollback deployment
    SCALE = "scale"                        # Scale resources
    ALERT = "alert"                        # Send alert
    CREATE_ISSUE = "create_issue"          # Create GitHub issue
    MERGE_PR = "merge_pr"                  # Merge pull request
    EXECUTE_WORKFLOW = "execute_workflow"  # Execute n8n workflow
```

---

## Integration Example

Complete autonomous deployment flow:

```python
from src.orchestrator import MainOrchestrator
from src.railway_client import RailwayClient
from src.github_app_client import GitHubAppClient
from src.n8n_client import N8nClient
from src.secrets_manager import SecretManager

async def main():
    # Setup
    manager = SecretManager()
    railway = RailwayClient(api_key=manager.get_secret("RAILWAY-API"))
    github = GitHubAppClient(
        app_id=123456,
        installation_id=789012,
        private_key=manager.get_secret("github-app-private-key")
    )
    n8n = N8nClient(
        base_url="https://n8n.railway.app",
        api_key=manager.get_secret("N8N-API")
    )

    orchestrator = MainOrchestrator(
        railway=railway,
        github=github,
        n8n=n8n,
        project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
        environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
    )

    # Scenario: Handle new commit to main
    event = {
        "type": "push",
        "commit": "abc123",
        "ref": "refs/heads/main",
        "head_commit": {
            "sha": "abc123",
            "message": "feat: new feature",
            "author": {"name": "developer@example.com"}
        }
    }

    # OODA Loop executes:
    # 1. OBSERVE: Check Railway, GitHub, n8n state
    # 2. ORIENT: Analyze commit is on main branch
    # 3. DECIDE: Should deploy to production
    # 4. ACT: Trigger Railway deployment

    result = await orchestrator.handle_deployment_event(event)
    print(f"Deployment: {result['deployment_id']}")

    # If deployment fails, orchestrator automatically:
    # 1. Detects failure in next OODA cycle
    # 2. Decides to rollback
    # 3. Executes rollback
    # 4. Creates GitHub issue
    # 5. Sends alert via n8n

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## State Machine Integration

The orchestrator integrates with the deployment state machine for lifecycle management:

```python
from src.state_machine import StateMachineManager, DeploymentStatus

# Create state machine manager
sm_manager = StateMachineManager()

# During deployment
sm = sm_manager.create("deploy-123", metadata={"commit": "abc123"})
sm.transition(DeploymentStatus.BUILDING)
sm.transition(DeploymentStatus.DEPLOYING)
sm.transition(DeploymentStatus.ACTIVE)

# Check deployment health
if sm.is_healthy():
    print("Deployment successful")
elif sm.should_rollback():
    await orchestrator.handle_deployment_failure("deploy-123")
```

---

## Error Handling

The orchestrator handles errors gracefully:

```python
# Observation failures are logged but don't stop the cycle
observations = await orchestrator.observe()
# If Railway API fails, still get GitHub and n8n observations

# Decision execution failures are logged and state is set to FAILED
try:
    await orchestrator.act(decision)
except Exception as e:
    logger.error(f"Action execution failed: {e}")
    # Orchestrator state set to FAILED
```

---

## Production Configuration

### Recommended Settings

```python
# Production orchestrator with 60-second cycle
orchestrator = MainOrchestrator(
    railway=railway,
    github=github,
    n8n=n8n,
    project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
    environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
)

# Run continuously
await orchestrator.run_continuous(interval_seconds=60)
```

### Monitoring

```python
# Log orchestrator state
print(f"State: {orchestrator.state}")

# Get world model statistics
wm = orchestrator.world_model
print(f"Last update: {wm.last_update}")
print(f"Railway services: {len(wm.railway_state.get('services', []))}")
print(f"Recent observations: {len(wm.get_recent_observations())}")
```

---

## Testing

See `tests/test_orchestrator.py` for comprehensive test suite.

**Test Coverage:**
- ✅ OODA loop phases (observe, orient, decide, act)
- ✅ Decision types (deploy, rollback, create_issue, merge_pr, alert)
- ✅ Event handlers (deployment event, deployment failure)
- ✅ Error handling (client failures, invalid actions)
- ✅ Complete OODA cycles
- ✅ Integration with state machine

---

## Related Documentation

- [Railway Client API](railway_client.md) - Railway GraphQL API integration
- [GitHub App Client API](github_app_client.md) - GitHub App authentication and operations
- [n8n Client API](n8n_client.md) - n8n workflow orchestration
- [State Machine](../autonomous/01-system-architecture-hybrid.md#state-machine) - Deployment lifecycle management
- [OODA Loop Philosophy](../autonomous/00-autonomous-philosophy.md) - Observe-Orient-Decide-Act pattern
- [Operational Scenarios](../autonomous/07-operational-scenarios-hybrid.md) - Real-world deployment scenarios
