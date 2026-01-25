# WAT Framework Workflows

This directory contains workflow definitions for the WAT (Workflows, Agents, Tools) Framework.

## What is a Workflow?

In the WAT Framework, a **Workflow** is a declarative definition of a goal and the steps to achieve it. Unlike traditional automation pipelines that are rigid and brittle, WAT workflows are:

- **Declarative**: Define *what* you want, not *how* to do it step-by-step
- **Self-Healing**: Automatic error recovery with configurable strategies
- **Cost-Aware**: Built-in cost tracking and budget enforcement
- **Adaptive**: Agents can modify execution based on intermediate results

## Workflow Format

Workflows can be defined in two formats:

### 1. YAML Format (Recommended)

```yaml
name: my-workflow
description: What this workflow accomplishes
version: "1.0.0"

inputs:
  location:
    type: str
    description: Target location
    required: true

steps:
  - id: step_1
    tool: search_places
    description: Search for businesses
    inputs:
      query: "$inputs.niche"
      location: "$inputs.location"

  - id: step_2
    tool: enrich_data
    description: Enrich with contact info
    input_mappings:
      results: "$prev.output"

constraints:
  - "Do not fabricate data"
  - "Respect rate limits"

error_handlers:
  - error_type: rate_limit
    action: retry_with_backoff
    max_attempts: 5

timeout_seconds: 300
cost_budget_usd: 1.0

tags:
  - category-tag
```

### 2. Markdown Format (Natural Language)

```markdown
# Workflow: Lead Generation

## Objective
Generate 50 leads for dental practices in San Francisco.

## Inputs
- Location: "San Francisco, CA"
- Niche: "Dentist"

## Process Steps
1. **Discovery**: Use the search_places tool to find businesses.
2. **Enrichment**: Visit websites to extract contact emails.
3. **Validation**: Verify email formats.
4. **Export**: Save to CSV file.

## Constraints
- Do not hallucinate contact info
- Respect robots.txt
```

## Input References

Steps can reference:
- `$inputs.field_name` - Workflow inputs
- `$prev.field` - Previous step's output
- `$step_id.field` - Specific step's output

## Error Handling

### Error Types
- `network` - Connection failures
- `rate_limit` - API throttling
- `authentication` - Auth failures
- `validation` - Input/output errors
- `dependency` - Missing modules
- `timeout` - Operation timeouts

### Recovery Actions
- `retry` - Simple retry
- `retry_with_backoff` - Exponential backoff
- `fallback` - Use alternative tool
- `skip` - Skip this step
- `abort` - Stop workflow
- `install_dependency` - Auto-install missing packages

## Available Workflows

| Workflow | Description |
|----------|-------------|
| `lead-gen-dentist.yaml` | Dentist lead generation with Google Maps |
| `data-enrichment.yaml` | Company data enrichment pipeline |

## Usage

```python
from src.wat import Workflow, WorkflowEngine, SelfHealingExecutor

# Load workflow
engine = WorkflowEngine("workflows")
workflow = engine.load("lead-gen-dentist")

# Execute with self-healing
executor = SelfHealingExecutor(registry)
result = await executor.run(
    workflow,
    agent,
    inputs={"location": "San Francisco, CA"}
)

print(f"Status: {result.status}")
print(f"Cost: ${result.total_cost_usd:.4f}")
```

## Creating New Workflows

1. Copy an existing workflow as a template
2. Define your inputs and steps
3. Add appropriate constraints
4. Configure error handlers for expected failures
5. Set timeout and cost budget

## Best Practices

1. **Be Specific**: Clear step descriptions help the agent understand intent
2. **Handle Errors**: Configure recovery strategies for expected failure modes
3. **Set Budgets**: Always set `cost_budget_usd` to prevent runaway costs
4. **Add Constraints**: Natural language constraints guide agent behavior
5. **Use References**: Leverage `$prev` and `$step_id` for data flow
