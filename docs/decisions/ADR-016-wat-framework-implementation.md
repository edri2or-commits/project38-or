# ADR-016: WAT Framework Implementation

**Status**: Accepted
**Date**: 2026-01-25
**Deciders**: Or Edri
**Technical Story**: Transition from deterministic workflows to probabilistic agentic automation

## Context and Problem Statement

The project currently has sophisticated automation capabilities spread across multiple systems:
- MCP Gateway with 30+ tools
- Multi-agent system with specialized agents
- Skills system with 18 reusable behaviors
- Automation Orchestrator with 5-path fallback

However, these systems lack unification:
1. **Tools are scattered** across MCP servers, agents, and skills
2. **Workflows are heterogeneous** - LangGraph, Python dicts, Markdown
3. **Agent routing is manual** - no automatic capability matching
4. **Error handling is per-component** - no unified recovery strategy

The industry is shifting from **Deterministic Linear Workflows** (n8n, Zapier) to **Probabilistic Agentic Automation**. Traditional automation requires explicit handling of every edge case, leading to:
- Brittleness when APIs change
- Maintenance burden growing exponentially with complexity
- Inability to handle "unknown unknowns"

## Decision Drivers

1. **Self-Healing Requirement**: Automations must recover from transient failures without human intervention
2. **Tool Discovery**: 70+ tools need unified registry for agent access
3. **Cost Control**: LLM-based automation needs budget enforcement
4. **Observability**: Cross-component tracing for debugging
5. **Future-Proofing**: Architecture should support next-gen LLM capabilities

## Considered Options

### Option 1: Enhance n8n Integration
Continue using n8n as the orchestration layer with improved error handling.

**Pros**:
- Visual workflow builder
- Existing infrastructure
- Community nodes

**Cons**:
- Deterministic execution - cannot adapt to changes
- Limited LLM integration
- Node-based errors cascade
- No self-healing beyond simple retry

### Option 2: LangGraph Everywhere
Standardize on LangGraph for all workflows (as used in Smart Email Agent).

**Pros**:
- State machine patterns
- Cycle support
- Persistence built-in

**Cons**:
- Python-only
- Complex for simple flows
- No YAML definition
- Steep learning curve

### Option 3: WAT Framework (Selected)
Implement the Workflows, Agents, Tools framework as a unification layer.

**Pros**:
- Unified tool registry
- Self-healing execution loop
- YAML workflow definitions
- Agent capability matching
- Cost tracking built-in
- Works with existing infrastructure

**Cons**:
- New abstraction to learn
- Initial implementation effort
- Requires migration of existing workflows

## Decision

Implement the **WAT Framework** as an enhancement layer over existing infrastructure.

The WAT Framework provides:
1. **ToolRegistry**: Unified discovery and registration of all tools
2. **Workflow Engine**: YAML-based workflow definitions with Markdown support
3. **AgentDefinition**: Declarative agent specifications with capability matching
4. **SelfHealingExecutor**: The Loop pattern for automatic error recovery

## Technical Architecture

### The WAT Ontology

```
Workflows (W): Goal definitions in YAML/Markdown
    ↓ interpreted by
Agents (A): Cognitive engines (Claude) with capability matching
    ↓ invoke
Tools (T): Atomic execution units (MCP tools, Python functions)
```

### The Self-Healing Loop

```
1. Execute Tool
2. If error:
   a. Classify error type (network, rate_limit, auth, etc.)
   b. Match to recovery strategy
   c. Apply recovery action:
      - retry: Simple retry
      - retry_with_backoff: Exponential backoff
      - install_dependency: Auto-install missing packages
      - refresh_auth: Trigger re-authentication
      - fallback: Switch to alternative tool
   d. Retry up to max_attempts
3. If still failing:
   a. Log failure
   b. Escalate to human
```

### Component Architecture

```
src/wat/
├── __init__.py         # Module exports
├── types.py            # Data structures (ToolDefinition, WorkflowStep, etc.)
├── registry.py         # ToolRegistry for unified discovery
├── workflow.py         # Workflow engine and YAML parsing
├── agent.py            # AgentDefinition and AgentDispatcher
└── executor.py         # SelfHealingExecutor with Loop pattern

workflows/
├── README.md           # Workflow documentation
├── lead-gen-dentist.yaml
└── data-enrichment.yaml
```

### Error Classification

| Error Type | Examples | Default Recovery |
|------------|----------|------------------|
| `network` | Connection refused, timeout | retry_with_backoff |
| `rate_limit` | 429 responses | retry_with_backoff (longer) |
| `authentication` | 401/403 errors | refresh_auth |
| `dependency` | ModuleNotFoundError | install_dependency |
| `validation` | Invalid input | abort (report error) |
| `timeout` | Operation timeout | increase_timeout |

### Workflow Definition Format

```yaml
name: example-workflow
description: What this workflow accomplishes
version: "1.0.0"

inputs:
  param_name:
    type: str
    description: Parameter description
    required: true

steps:
  - id: step_1
    tool: tool_name
    description: What this step does
    inputs:
      key: "$inputs.param_name"  # Reference inputs

  - id: step_2
    tool: another_tool
    input_mappings:
      data: "$prev.output"  # Reference previous step
    condition: "$step_1.status == 'success'"
    on_error: skip  # abort | skip | retry

constraints:
  - "Natural language constraint for agent"

error_handlers:
  - error_type: rate_limit
    action: retry_with_backoff
    max_attempts: 5

timeout_seconds: 300
cost_budget_usd: 1.0
```

## Integration with Existing Infrastructure

### MCP Tools → ToolRegistry

```python
registry = ToolRegistry()
registry.discover_mcp_tools("src/mcp_gateway/tools")
# Discovers: railway_deploy, railway_status, n8n_trigger, etc.
```

### Existing Agents → AgentDefinition

```python
# DeployAgent becomes:
deploy_agent = AgentDefinition(
    name="deploy-agent",
    domain=AgentDomain.DEPLOYMENT,
    tools=["railway_deploy", "railway_status", "railway_rollback"],
    capabilities=[AgentCapability("deploy_service"), ...]
)
```

### Skills → Workflow Components

Skills can be composed into workflows:
```yaml
steps:
  - id: preflight
    tool: "skill:preflight-check"
  - id: test
    tool: "skill:test-runner"
  - id: create_pr
    tool: "skill:pr-helper"
```

## Implementation Phases

### Phase 1: Core Framework (This PR) ✅
- [x] `src/wat/types.py` - Core data structures
- [x] `src/wat/registry.py` - Tool registry with discovery
- [x] `src/wat/workflow.py` - Workflow engine
- [x] `src/wat/agent.py` - Agent definitions
- [x] `src/wat/executor.py` - Self-healing executor
- [x] Example workflows

### Phase 2: Integration (Future)
- [ ] Wire registry to existing MCP servers
- [ ] Create default agents from existing infrastructure
- [ ] Add API endpoints for workflow management
- [ ] Integrate with observability system

### Phase 3: Migration (Future)
- [ ] Convert existing workflows to WAT format
- [ ] Migrate n8n workflows where beneficial
- [ ] Update skills to use WAT patterns
- [ ] Deprecate duplicate patterns

### Phase 4: Enhancement (Future)
- [ ] LLM-based workflow generation from natural language
- [ ] Auto-discovery of new tool capabilities
- [ ] Cross-workflow learning
- [ ] Cost optimization based on historical data

## Consequences

### Positive
- **Unified Tool Access**: All 70+ tools accessible through single registry
- **Self-Healing**: Automatic recovery from 80%+ of transient failures
- **Cost Control**: Built-in budget enforcement prevents runaway spending
- **Observability**: Consistent tracing across all automation
- **Declarative Workflows**: YAML definitions enable version control and review

### Negative
- **Learning Curve**: New abstraction for developers to understand
- **Migration Effort**: Existing workflows need conversion
- **Abstraction Overhead**: Additional layer between intent and execution

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Over-abstraction | Medium | Medium | Keep WAT layer thin; direct tool access still available |
| Recovery loops | Low | High | Max retry limits; circuit breaker pattern |
| Cost overruns | Low | Medium | Default budgets; alerts at thresholds |

## References

- [WAT Framework Research Report](docs/research/notes/2026-01-25-wat-framework.md)
- [ADR-008: Robust Automation Strategy](ADR-008-robust-automation-strategy.md)
- [ADR-014: Smart Email Agent](ADR-014-smart-email-agent.md) - LangGraph pattern
- [Nate Herk WAT Framework](https://www.youtube.com/watch?v=example) - Original concept
- [LangChain State of Agents 2026](https://www.langchain.com/state-of-agent-engineering)

## Update Log

| Date | Change | PR |
|------|--------|-----|
| 2026-01-25 | Initial implementation | #TBD |
