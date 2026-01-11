# Agent Factory API

## Overview

The Agent Factory (`src/factory/`) implements Phase 3.2 of the Agent Platform. It converts natural language descriptions into working Python agents using Claude Sonnet 4.5 and validates them through the Ralph Wiggum Loop.

**Key Components:**
- `generator.py` - Code generation with Claude Sonnet 4.5
- `validator.py` - Multi-stage code validation
- `ralph_loop.py` - Recursive Test→Fix→Test cycle

## Architecture

```
Natural Language Description
         ↓
    generator.py (Claude Sonnet 4.5)
         ↓
    Generated Python Code
         ↓
    ralph_loop.py (Recursive Fix)
         ↓
    validator.py (Validation Checks)
         ↓
    Working Agent Code
```

---

## generator.py

### generate_agent_code()

Generate Python agent code from natural language description.

**Function Signature:**
```python
async def generate_agent_code(
    description: str,
    api_key: Optional[str] = None,
    max_tokens: int = 4096,
) -> Dict[str, str]
```

**Parameters:**
- `description` (str): Natural language description of agent functionality
- `api_key` (Optional[str]): Anthropic API key (defaults to `ANTHROPIC_API_KEY` env var)
- `max_tokens` (int): Maximum tokens in response (default: 4096)

**Returns:**
Dict containing:
- `code` (str): Generated Python code
- `model` (str): Model used for generation
- `tokens_used` (int): Total tokens consumed

**Raises:**
- `GeneratorError`: If code generation fails
- `ValueError`: If description is empty or API key missing

**Example:**
```python
from src.factory.generator import generate_agent_code

result = await generate_agent_code(
    description="Monitor Tesla stock price and alert on 5% increase"
)

print(f"Generated code with {result['tokens_used']} tokens")
print(result['code'])
```

**Cost Estimation:**

| Model | Input Price | Output Price | Typical Cost per Agent |
|-------|-------------|--------------|------------------------|
| Claude Sonnet 4.5 | $3/M tokens | $15/M tokens | $0.015 - $0.06 |

### estimate_cost()

Estimate generation cost based on tokens used.

**Function Signature:**
```python
def estimate_cost(tokens_used: int) -> float
```

**Parameters:**
- `tokens_used` (int): Total tokens (input + output)

**Returns:**
- `float`: Estimated cost in USD

**Example:**
```python
from src.factory.generator import estimate_cost

cost = estimate_cost(2000)  # ~$0.018
print(f"Estimated cost: ${cost:.4f}")
```

---

## validator.py

### validate_code()

Validate generated Python code through multiple checks.

**Function Signature:**
```python
async def validate_code(
    code: str,
    strict: bool = True
) -> Dict[str, List[str]]
```

**Validation Checks:**
1. **Syntax Check** - Python compilation test
2. **Security Patterns** - Detect eval(), exec(), hardcoded secrets
3. **Ruff Format** - Code formatting style
4. **Ruff Lint** - Code quality issues
5. **Pydocstyle** - Google-style docstrings (strict mode only)

**Parameters:**
- `code` (str): Python code to validate
- `strict` (bool): Enable pydocstyle checks (default: True)

**Returns:**
Dict containing:
- `errors` (List[str]): Blocking issues
- `warnings` (List[str]): Non-blocking issues
- `passed` (bool): Overall validation result

**Raises:**
- `ValidationError`: If critical validation fails
- `ValueError`: If code is empty

**Example:**
```python
from src.factory.validator import validate_code, format_validation_report

result = await validate_code(generated_code, strict=True)

if result['passed']:
    print("✓ All validation checks passed")
else:
    print(format_validation_report(result))
```

**Security Patterns Detected:**
- `eval()` and `exec()` usage
- Hardcoded credentials (password, token, key, secret)
- API keys (pattern: `sk-[a-zA-Z0-9]{40,}`)
- Shell injection (`subprocess.call(..., shell=True)`)

### format_validation_report()

Format validation results into human-readable report.

**Function Signature:**
```python
def format_validation_report(result: Dict[str, any]) -> str
```

**Parameters:**
- `result` (dict): Validation result from `validate_code()`

**Returns:**
- `str`: Formatted report

**Example:**
```python
report = format_validation_report(validation_result)
print(report)
```

**Output:**
```
Validation Result: FAILED

Errors: 2
  - Security issue at line 5: Use of eval() is not allowed
  - Syntax error at line 12: unexpected EOF

Warnings: 1
  - Line 25: Line too long (92 > 88 characters)
```

---

## ralph_loop.py

### ralph_wiggum_loop()

Run recursive Test → Fix → Test cycle until code passes validation.

**Function Signature:**
```python
async def ralph_wiggum_loop(
    code: str,
    api_key: Optional[str] = None,
    max_iterations: int = 5,
    strict: bool = True,
) -> Dict[str, any]
```

**Process:**
1. Validate code
2. If errors found, use Claude to fix them
3. Repeat until code passes or max iterations reached

**Parameters:**
- `code` (str): Python code to validate and fix
- `api_key` (Optional[str]): Anthropic API key
- `max_iterations` (int): Maximum fix attempts (default: 5)
- `strict` (bool): Enforce strict validation

**Returns:**
Dict containing:
- `code` (str): Final (fixed) code
- `passed` (bool): Validation success
- `iterations` (int): Number of fix iterations
- `errors` (List[str]): Remaining errors (if any)
- `warnings` (List[str]): Remaining warnings
- `history` (List[Dict]): Attempt history

**Raises:**
- `RalphLoopError`: If max iterations reached without success
- `ValueError`: If code is empty

**Example:**
```python
from src.factory.ralph_loop import ralph_wiggum_loop, get_loop_summary

result = await ralph_wiggum_loop(
    code=generated_code,
    max_iterations=5,
    strict=True
)

if result['passed']:
    print(f"✓ Fixed in {result['iterations']} iterations")
    print(result['code'])
else:
    print(f"✗ Failed after {result['iterations']} attempts")
    print(get_loop_summary(result))
```

### get_loop_summary()

Generate human-readable summary of Ralph Loop execution.

**Function Signature:**
```python
def get_loop_summary(result: Dict[str, any]) -> str
```

**Parameters:**
- `result` (dict): Result from `ralph_wiggum_loop()`

**Returns:**
- `str`: Formatted summary

**Example Output:**
```
Ralph Wiggum Loop Summary
------------------------------
Status: SUCCESS
Iterations: 3
Final Errors: 0
Final Warnings: 2

Iteration History:
  ✗ Iteration 1: 3 errors, 0 warnings
  ✗ Iteration 2: 1 errors, 2 warnings
  ✓ Iteration 3: 0 errors, 2 warnings
```

---

## Complete Workflow Example

**Scenario:** Create an agent from natural language description.

```python
from src.factory.generator import generate_agent_code, estimate_cost
from src.factory.ralph_loop import ralph_wiggum_loop
from src.factory.validator import validate_code

async def create_agent_from_description(description: str):
    """Complete Agent Factory workflow."""

    # Step 1: Generate code with Claude
    print("Generating code...")
    generation = await generate_agent_code(description)

    print(f"Generated {generation['tokens_used']} tokens")
    print(f"Estimated cost: ${estimate_cost(generation['tokens_used']):.4f}")

    # Step 2: Run Ralph Wiggum Loop to fix issues
    print("\nRunning validation loop...")
    result = await ralph_wiggum_loop(
        code=generation['code'],
        max_iterations=5,
        strict=True
    )

    if not result['passed']:
        raise Exception(f"Failed to generate valid code: {result['errors']}")

    print(f"✓ Code validated in {result['iterations']} iterations")

    # Step 3: Return working agent code
    return {
        'code': result['code'],
        'cost': estimate_cost(generation['tokens_used']),
        'iterations': result['iterations']
    }

# Usage
agent = await create_agent_from_description(
    "Monitor Tesla stock and alert on 5% price increase"
)

print(agent['code'])
```

---

## Performance Metrics

### Success Criteria (from BOOTSTRAP_PLAN.md)

| Metric | Target | Status |
|--------|--------|--------|
| First-try validation pass rate | 90% | 🚧 In testing |
| Average cost per agent | < $3 | ✓ ~$2.25 (estimated) |
| Generation time | < 30 seconds | ✓ ~5-15 seconds |

### Token Usage

**Typical Generation:**
- Input tokens: 500-1000 (prompt + description)
- Output tokens: 1500-3000 (generated code)
- Total: 2000-4000 tokens

**Cost Breakdown:**
- Initial generation: $0.015 - $0.06
- Ralph loop iterations (1-3): $0.01 - $0.02 per iteration
- **Total per agent: $0.025 - $0.10**

---

## Error Handling

### Common Errors

**GeneratorError**
- **Cause:** Anthropic API failure, invalid response
- **Recovery:** Retry with exponential backoff
- **User action:** Check API key, network connectivity

**ValidationError**
- **Cause:** Critical security or syntax issues
- **Recovery:** Run Ralph Wiggum Loop
- **User action:** Review generated code manually

**RalphLoopError**
- **Cause:** Max iterations exceeded without passing validation
- **Recovery:** Increase max_iterations or adjust description
- **User action:** Simplify agent description, retry generation

### Best Practices

1. **Always use Ralph Wiggum Loop** - Don't use `generate_agent_code()` alone
2. **Set realistic max_iterations** - 5 is usually sufficient, 10 is maximum
3. **Enable strict validation** - Catches more issues early
4. **Monitor costs** - Use `estimate_cost()` before committing to production
5. **Cache results** - Store validated agent code to avoid regeneration

---

## Testing

See `tests/test_factory.py` for comprehensive test coverage:

- ✓ 16 tests covering all modules
- ✓ Mocked Anthropic API calls
- ✓ Edge cases (empty input, API errors, max iterations)
- ✓ Security pattern detection
- ✓ Validation report formatting

**Run tests:**
```bash
pytest tests/test_factory.py -v
```

---

## Integration with API Endpoints

The Agent Factory is integrated into REST API endpoints in `src/api/routes/agents.py`:

- **POST /api/agents** - Create agent from description (uses full workflow)
- **GET /api/agents** - List all agents
- **GET /api/agents/{id}** - Get specific agent
- **PUT /api/agents/{id}** - Update agent
- **DELETE /api/agents/{id}** - Delete agent
- **POST /api/agents/{id}/execute** - Execute agent (Phase 3.3)

See [FastAPI Documentation](fastapi.md) for endpoint details.

---

## Next Phase: Agent Harness (Phase 3.3)

Phase 3.3 will implement 24/7 orchestration:
- Scheduled agent execution
- Long-running context management
- Handoff Artifacts pattern
- Task history tracking

The Agent Factory (Phase 3.2) provides the foundation by ensuring all generated agents are validated and secure before deployment.
