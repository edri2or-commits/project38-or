# Experiments Directory

This directory contains isolated experiments for testing new approaches before integration.

**Architecture Decision:** [ADR-009](../docs/decisions/ADR-009-research-integration-architecture.md)

## Creating an Experiment

### 1. Create Directory

```bash
# Format: exp_NNN_short_description
mkdir experiments/exp_001_new_model_provider
cd experiments/exp_001_new_model_provider
```

### 2. Create README.md

```markdown
# Experiment: [Title]

**ID:** exp_001
**Date:** YYYY-MM-DD
**Status:** Planning | Running | Complete | Archived
**Research Note:** docs/research/notes/YYYY-MM-DD-title.md

## Hypothesis

> If we [ACTION], then [METRIC] will [CHANGE] by [AMOUNT].

## Success Criteria

Define BEFORE running:

| Metric | Baseline | Target | Must Meet |
|--------|----------|--------|-----------|
| Quality Score | 0.85 | >= 0.85 | Yes |
| Avg Latency (ms) | 500 | <= 1000 | Yes |
| P99 Latency (ms) | 2000 | <= 4000 | No |
| Cost per 1K tokens | $0.003 | <= $0.005 | Yes |
| Error Rate | 1% | <= 2% | Yes |

## Test Cases

- Total cases: 100
- Source: tests/golden/basic_queries.json
- Categories covered: [list]

## Setup

[Instructions to run experiment]

## Results

_Filled after experiment completes_

| Metric | Baseline | Actual | Delta | Pass? |
|--------|----------|--------|-------|-------|
| | | | | |

## Conclusion

**Decision:** ADOPT / REJECT / NEEDS_MORE_DATA

**Reasoning:**

## Next Steps

- [ ] ...
```

### 3. Create run.py

```python
"""
Experiment: [Title]
ID: exp_001

Run with:
    python experiments/exp_001_description/run.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

# Define experiment
EXPERIMENT_ID = "exp_001"
HYPOTHESIS = "If we use X, then Y will improve by Z"
BASELINE_PROVIDER = "claude"
EXPERIMENT_PROVIDER = "new_provider"

async def run_experiment():
    results = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "hypothesis": HYPOTHESIS,
        "baseline": {},
        "experiment": {},
        "comparison": {},
    }

    # 1. Load test cases
    test_cases = load_test_cases()

    # 2. Run baseline
    results["baseline"] = await run_with_provider(BASELINE_PROVIDER, test_cases)

    # 3. Run experiment
    results["experiment"] = await run_with_provider(EXPERIMENT_PROVIDER, test_cases)

    # 4. Compare
    results["comparison"] = compare(results["baseline"], results["experiment"])

    # 5. Save results
    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # 6. Print summary
    print_summary(results)

    return results

def load_test_cases():
    # Load from golden set
    pass

async def run_with_provider(provider_name, test_cases):
    # Run all test cases
    pass

def compare(baseline, experiment):
    # Calculate deltas
    pass

def print_summary(results):
    # Print human-readable summary
    pass

if __name__ == "__main__":
    asyncio.run(run_experiment())
```

### 4. Run and Document

```bash
# Run experiment
python experiments/exp_001_description/run.py

# Results saved to results.json
# Update README.md with results and conclusion
```

## Experiment Lifecycle

```
Planning → Running → Complete → (ADOPT/REJECT) → Archived
```

1. **Planning**: Hypothesis defined, success criteria set
2. **Running**: Experiment in progress
3. **Complete**: Results collected, analysis done
4. **ADOPT**: Changes integrated (create PR)
5. **REJECT**: Documented why, archive
6. **Archived**: No longer active

## Naming Convention

```
exp_NNN_short_description/
│
├── README.md       # Hypothesis, criteria, results
├── run.py          # Experiment code
├── results.json    # Raw results data
└── conclusion.md   # Detailed analysis (optional)
```

## Example Experiments

```
experiments/
├── README.md                      # This file
├── exp_001_gpt4_comparison/       # Model comparison
├── exp_002_parallel_tools/        # Parallel tool execution
├── exp_003_new_prompting/         # Prompting technique
└── ...
```

## Guidelines

### DO

- ✅ Define success criteria BEFORE running
- ✅ Use the golden set for consistent comparison
- ✅ Document both positive and negative results
- ✅ Include enough test cases (100+ minimum)
- ✅ Run baseline and experiment in same conditions

### DON'T

- ❌ Change success criteria after seeing results
- ❌ Cherry-pick favorable test cases
- ❌ Skip documenting failed experiments
- ❌ Compare results from different time periods
- ❌ Use production data without anonymization
