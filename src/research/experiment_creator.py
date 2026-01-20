"""Experiment creator for ADR-009 Phase 5.

Automatically creates experiment skeletons for Spike-classified research notes.
Generates:
- experiments/exp_NNN_description/README.md
- experiments/exp_NNN_description/run.py
- experiments/exp_NNN_description/config.yaml
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.research.classifier import (
    Classification,
    ImpactScope,
    ResearchNote,
    parse_research_note,
)


@dataclass
class ExperimentConfig:
    """Configuration for a new experiment."""

    experiment_id: str
    title: str
    hypothesis: str
    research_note_path: Path
    scope: Optional[ImpactScope] = None
    baseline_provider: str = "mock"
    test_provider: str = "mock"
    golden_set_path: str = "tests/golden/basic_queries.json"
    success_criteria: dict = None

    def __post_init__(self):
        """Set default success criteria."""
        if self.success_criteria is None:
            self.success_criteria = {
                "quality_min": 0.85,
                "quality_regression_max": -0.02,
                "latency_max_ratio": 2.0,
                "cost_max_ratio": 1.5,
            }


def get_next_experiment_id(experiments_dir: Path) -> str:
    """Get the next available experiment ID.

    Args:
        experiments_dir: Path to experiments/ directory

    Returns:
        Next experiment ID (e.g., "exp_002")
    """
    if not experiments_dir.exists():
        return "exp_001"

    existing_ids = []
    for exp_dir in experiments_dir.iterdir():
        if exp_dir.is_dir() and exp_dir.name.startswith("exp_"):
            match = re.match(r"exp_(\d+)", exp_dir.name)
            if match:
                existing_ids.append(int(match.group(1)))

    if not existing_ids:
        return "exp_001"

    next_id = max(existing_ids) + 1
    return f"exp_{next_id:03d}"


def create_experiment_readme(config: ExperimentConfig) -> str:
    """Generate README.md content for experiment.

    Args:
        config: Experiment configuration

    Returns:
        README.md content
    """
    today = datetime.now().strftime("%Y-%m-%d")

    return f"""# Experiment: {config.title}

**ID:** {config.experiment_id}
**Created:** {today}
**Status:** Not Started
**Research Note:** [{config.research_note_path.name}](../../{config.research_note_path})

---

## Hypothesis

> {config.hypothesis}

---

## Background

This experiment was auto-generated from research note classification.
It tests whether the proposed change improves system performance.

---

## Success Criteria

| Metric | Threshold | Description |
|--------|-----------|-------------|
| Quality | >= {config.success_criteria['quality_min']:.0%} | Must meet minimum quality |
| Quality Regression | <= {config.success_criteria['quality_regression_max']:.1%} | Max allowed regression |
| Latency | <= {config.success_criteria['latency_max_ratio']:.1f}x baseline | Max latency increase |
| Cost | <= {config.success_criteria['cost_max_ratio']:.1f}x baseline | Max cost increase |

---

## Methodology

1. **Baseline Measurement**
   - Run evaluation with `{config.baseline_provider}` provider
   - Record: quality score, latency, cost

2. **Experiment Measurement**
   - Run evaluation with `{config.test_provider}` provider
   - Record: quality score, latency, cost

3. **Comparison**
   - Calculate deltas
   - Apply decision matrix

---

## How to Run

```bash
# Run the experiment
python experiments/{config.experiment_id}_{_slugify(config.title)}/run.py

# Or run with specific provider
python experiments/{config.experiment_id}_{_slugify(config.title)}/run.py --provider claude
```

---

## Results

**Status:** Not yet run

| Metric | Baseline | Experiment | Delta | Pass? |
|--------|----------|------------|-------|-------|
| Quality | - | - | - | - |
| Latency | - | - | - | - |
| Cost | - | - | - | - |

---

## Decision

**Outcome:** PENDING

**Reasoning:** Experiment not yet run.

---

## Files

- `README.md` - This file
- `run.py` - Experiment execution script
- `config.yaml` - Experiment configuration
- `results.json` - Results (generated after run)
- `conclusion.md` - Conclusion (generated after analysis)
"""


def create_experiment_script(config: ExperimentConfig) -> str:
    """Generate run.py script for experiment.

    Args:
        config: Experiment configuration

    Returns:
        run.py content
    """
    return f'''#!/usr/bin/env python3
"""Experiment runner for {config.experiment_id}: {config.title}.

Auto-generated from research note classification.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.evaluation import EvaluationHarness, Decision


# Success criteria from ADR-009
SUCCESS_CRITERIA = {{
    "quality_min": {config.success_criteria['quality_min']},
    "quality_regression_max": {config.success_criteria['quality_regression_max']},
    "latency_max_ratio": {config.success_criteria['latency_max_ratio']},
    "cost_max_ratio": {config.success_criteria['cost_max_ratio']},
}}


async def run_evaluation(provider_name: str, golden_set: str) -> dict:
    """Run evaluation with specified provider.

    Args:
        provider_name: Name of provider to evaluate
        golden_set: Path to golden set JSON

    Returns:
        Evaluation results dict
    """
    harness = EvaluationHarness()
    result = await harness.evaluate(
        provider_name=provider_name,
        golden_set_path=golden_set,
    )
    return result.to_dict()


def compare_results(baseline: dict, experiment: dict) -> tuple[str, str]:
    """Compare baseline and experiment results.

    Args:
        baseline: Baseline evaluation results
        experiment: Experiment evaluation results

    Returns:
        Tuple of (decision, reasoning)
    """
    quality_delta = experiment["avg_quality_score"] - baseline["avg_quality_score"]
    latency_ratio = experiment["avg_latency_ms"] / max(baseline["avg_latency_ms"], 1)
    cost_ratio = experiment["estimated_cost_usd"] / max(baseline["estimated_cost_usd"], 0.0001)

    # Decision logic from ADR-009
    # REJECT: Quality regression
    if quality_delta < SUCCESS_CRITERIA["quality_regression_max"]:
        return "REJECT", f"Quality dropped {{quality_delta:.1%}}"

    # REJECT: Too expensive without improvement
    if cost_ratio > SUCCESS_CRITERIA["cost_max_ratio"] and quality_delta < 0.05:
        return "REJECT", f"Cost +{{(cost_ratio-1)*100:.0f}}% without quality improvement"

    # ADOPT: All metrics better or same
    if quality_delta >= 0 and latency_ratio <= 1 and cost_ratio <= 1:
        return "ADOPT", "All metrics improved or stable"

    # ADOPT: Quality significantly better
    if quality_delta > 0.10 and cost_ratio <= 3.0:
        return "ADOPT", f"Quality +{{quality_delta:.1%}} justifies cost"

    # ADOPT: Faster and cheaper
    if latency_ratio < 0.9 and cost_ratio < 1 and quality_delta >= -0.01:
        return "ADOPT", "Faster and cheaper with stable quality"

    return "NEEDS_MORE_DATA", "Mixed results, expand test set"


def main():
    """Run experiment."""
    parser = argparse.ArgumentParser(description="Run {config.experiment_id} experiment")
    parser.add_argument(
        "--baseline",
        default="{config.baseline_provider}",
        help="Baseline provider name",
    )
    parser.add_argument(
        "--provider",
        default="{config.test_provider}",
        help="Experiment provider name",
    )
    parser.add_argument(
        "--golden-set",
        default="{config.golden_set_path}",
        help="Path to golden set JSON",
    )
    parser.add_argument(
        "--output",
        default="results.json",
        help="Output file for results",
    )
    args = parser.parse_args()

    print(f"=== {config.experiment_id}: {config.title} ===")
    print()

    # Run baseline
    print(f"Running baseline evaluation with {{args.baseline}}...")
    baseline_results = asyncio.run(run_evaluation(args.baseline, args.golden_set))
    print(f"  Quality: {{baseline_results['avg_quality_score']:.2%}}")
    print(f"  Latency: {{baseline_results['avg_latency_ms']:.0f}}ms")
    print(f"  Cost: ${{baseline_results['estimated_cost_usd']:.4f}}")
    print()

    # Run experiment
    print(f"Running experiment evaluation with {{args.provider}}...")
    experiment_results = asyncio.run(run_evaluation(args.provider, args.golden_set))
    print(f"  Quality: {{experiment_results['avg_quality_score']:.2%}}")
    print(f"  Latency: {{experiment_results['avg_latency_ms']:.0f}}ms")
    print(f"  Cost: ${{experiment_results['estimated_cost_usd']:.4f}}")
    print()

    # Compare
    decision, reasoning = compare_results(baseline_results, experiment_results)

    print("=== Results ===")
    print(f"Decision: {{decision}}")
    print(f"Reasoning: {{reasoning}}")

    # Save results
    output_path = Path(__file__).parent / args.output
    results = {{
        "experiment_id": "{config.experiment_id}",
        "title": "{config.title}",
        "timestamp": datetime.utcnow().isoformat(),
        "baseline": {{
            "provider": args.baseline,
            "results": baseline_results,
        }},
        "experiment": {{
            "provider": args.provider,
            "results": experiment_results,
        }},
        "comparison": {{
            "quality_delta": experiment_results["avg_quality_score"] - baseline_results["avg_quality_score"],
            "latency_ratio": experiment_results["avg_latency_ms"] / max(baseline_results["avg_latency_ms"], 1),
            "cost_ratio": experiment_results["estimated_cost_usd"] / max(baseline_results["estimated_cost_usd"], 0.0001),
        }},
        "decision": decision,
        "reasoning": reasoning,
    }}

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\\nResults saved to {{output_path}}")

    return 0 if decision == "ADOPT" else 1


if __name__ == "__main__":
    sys.exit(main())
'''


def create_experiment_config(config: ExperimentConfig) -> str:
    """Generate config.yaml for experiment.

    Args:
        config: Experiment configuration

    Returns:
        config.yaml content
    """
    return f"""# Experiment Configuration
# Auto-generated from research note classification

experiment:
  id: "{config.experiment_id}"
  title: "{config.title}"
  hypothesis: "{config.hypothesis}"

research_note:
  path: "{config.research_note_path}"

providers:
  baseline: "{config.baseline_provider}"
  experiment: "{config.test_provider}"

golden_set:
  path: "{config.golden_set_path}"

success_criteria:
  quality_min: {config.success_criteria['quality_min']}
  quality_regression_max: {config.success_criteria['quality_regression_max']}
  latency_max_ratio: {config.success_criteria['latency_max_ratio']}
  cost_max_ratio: {config.success_criteria['cost_max_ratio']}
"""


def _slugify(title: str) -> str:
    """Convert title to slug.

    Args:
        title: Title string

    Returns:
        URL-safe slug
    """
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())
    return slug[:30].strip("_")


def create_experiment_skeleton(
    note_path: Path,
    experiments_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Create experiment skeleton from research note.

    Args:
        note_path: Path to research note
        experiments_dir: Path to experiments directory

    Returns:
        Path to created experiment directory, or None if note is not a Spike
    """
    # Read and parse note
    content = note_path.read_text()
    note = parse_research_note(content, note_path)

    # Only create experiments for Spike classification
    from src.research.classifier import auto_classify
    classification, _ = auto_classify(note)

    if classification != Classification.SPIKE:
        return None

    # Set up paths
    if experiments_dir is None:
        experiments_dir = Path("experiments")
    experiments_dir.mkdir(parents=True, exist_ok=True)

    # Get experiment ID
    exp_id = get_next_experiment_id(experiments_dir)
    slug = _slugify(note.title or "untitled")
    exp_dir_name = f"{exp_id}_{slug}"
    exp_dir = experiments_dir / exp_dir_name

    # Create experiment directory
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Create configuration
    config = ExperimentConfig(
        experiment_id=exp_id,
        title=note.title or "Untitled Experiment",
        hypothesis=note.hypothesis or "To be determined",
        research_note_path=note_path,
        scope=note.impact.scope,
    )

    # Create files
    readme_path = exp_dir / "README.md"
    readme_path.write_text(create_experiment_readme(config))

    run_path = exp_dir / "run.py"
    run_path.write_text(create_experiment_script(config))
    run_path.chmod(0o755)  # Make executable

    config_path = exp_dir / "config.yaml"
    config_path.write_text(create_experiment_config(config))

    return exp_dir


def create_experiment_for_note(
    note: ResearchNote,
    experiments_dir: Optional[Path] = None,
) -> Optional[tuple[Path, str]]:
    """Create experiment from parsed note object.

    Args:
        note: Parsed ResearchNote
        experiments_dir: Path to experiments directory

    Returns:
        Tuple of (experiment directory, experiment ID) or None
    """
    if note.file_path is None:
        return None

    exp_dir = create_experiment_skeleton(note.file_path, experiments_dir)
    if exp_dir is None:
        return None

    exp_id = exp_dir.name.split("_")[0] + "_" + exp_dir.name.split("_")[1]
    return exp_dir, exp_id
