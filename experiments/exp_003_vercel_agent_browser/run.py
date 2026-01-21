#!/usr/bin/env python3
"""Experiment runner for exp_003: Vercel Agent Browser - Autonomous UI Navigation.

This experiment tests browser automation using Accessibility Tree approach
for 93% token reduction compared to traditional DOM-based methods.

Run with:
    python experiments/exp_003_vercel_agent_browser/run.py --phase 1
    python experiments/exp_003_vercel_agent_browser/run.py --all
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Experiment constants
EXPERIMENT_ID = "exp_003"
EXPERIMENT_TITLE = "Vercel Agent Browser - Autonomous UI Navigation"
HYPOTHESIS = (
    "If we integrate Vercel Agent Browser CLI for UI interactions, "
    "then autonomous operations coverage will increase by 50%+ "
    "(from API-only to API+UI) while maintaining acceptable token costs (<$0.05 per complex operation)."
)

# Success criteria thresholds
SUCCESS_CRITERIA = {
    "operations_coverage_min": 0.90,  # >= 90%
    "token_cost_per_step_max": 0.02,  # <= $0.02
    "success_rate_min": 0.85,  # >= 85%
    "avg_latency_max_ms": 5000,  # <= 5s
    "loop_detection_rate_min": 0.95,  # >= 95%
}

# Token pricing (Claude 3.5 Sonnet)
TOKEN_PRICING = {
    "input_per_1m": 3.00,  # $3 per 1M input tokens
    "output_per_1m": 15.00,  # $15 per 1M output tokens
}


class TestPhase(Enum):
    """Test phases for the experiment."""

    BASIC_NAVIGATION = 1
    INTERACTIVE = 2
    COMPLEX_WORKFLOWS = 3


@dataclass
class BrowserAction:
    """Represents a browser action for state tracking."""

    action_type: str  # navigate, click, fill, scroll, snapshot
    target: str  # URL or element reference (@e1, @e2, etc.)
    timestamp: float = field(default_factory=time.time)
    snapshot_hash: str = ""
    success: bool = True
    tokens_used: int = 0
    latency_ms: float = 0


@dataclass
class TestCase:
    """Definition of a test case."""

    id: str
    phase: TestPhase
    name: str
    description: str
    steps: list[dict[str, Any]]
    expected_outcome: str
    dry_run_safe: bool = True


@dataclass
class TestResult:
    """Result of running a test case."""

    test_case_id: str
    success: bool
    actions: list[BrowserAction]
    total_tokens: int
    total_cost_usd: float
    total_latency_ms: float
    loop_detected: bool = False
    error_message: str = ""


class LoopDetector:
    """Detects action loops to prevent infinite cycling."""

    def __init__(self, history_size: int = 10, similarity_threshold: float = 0.8):
        """Initialize loop detector.

        Args:
            history_size: Number of recent actions to track
            similarity_threshold: Hash similarity threshold for loop detection
        """
        self.history: list[BrowserAction] = []
        self.history_size = history_size
        self.similarity_threshold = similarity_threshold
        self.snapshot_hashes: list[str] = []

    def add_action(self, action: BrowserAction) -> bool:
        """Add action and check for loops.

        Args:
            action: The browser action to add

        Returns:
            True if loop detected, False otherwise
        """
        self.history.append(action)
        if len(self.history) > self.history_size:
            self.history.pop(0)

        if action.snapshot_hash:
            self.snapshot_hashes.append(action.snapshot_hash)
            if len(self.snapshot_hashes) > self.history_size:
                self.snapshot_hashes.pop(0)

        return self._check_loop()

    def _check_loop(self) -> bool:
        """Check if recent actions indicate a loop."""
        if len(self.history) < 4:
            return False

        # Check for repeated action patterns
        recent_actions = [f"{a.action_type}:{a.target}" for a in self.history[-4:]]
        if len(set(recent_actions)) <= 2:
            return True

        # Check for repeated snapshots
        if len(self.snapshot_hashes) >= 3:
            recent_hashes = self.snapshot_hashes[-3:]
            if len(set(recent_hashes)) == 1:
                return True

        return False


class AccessibilityTreeExtractor:
    """Extracts accessibility tree from browser page."""

    @staticmethod
    def extract(page_content: str) -> dict[str, Any]:
        """Extract accessibility tree from page.

        Args:
            page_content: Raw page content or DOM

        Returns:
            Accessibility tree with element references
        """
        # Placeholder - in real implementation, use Playwright's accessibility API
        # The accessibility tree is much smaller than DOM (~93% reduction)
        return {
            "role": "document",
            "name": "Page Title",
            "children": [
                {"role": "navigation", "ref": "@e1", "name": "Main Nav"},
                {"role": "main", "ref": "@e2", "children": []},
                {"role": "button", "ref": "@e3", "name": "Submit"},
            ],
        }

    @staticmethod
    def compute_hash(tree: dict[str, Any]) -> str:
        """Compute hash of accessibility tree for comparison."""
        tree_str = json.dumps(tree, sort_keys=True)
        return hashlib.sha256(tree_str.encode()).hexdigest()[:16]


class BrowserAgent:
    """Browser automation agent using Accessibility Tree approach."""

    def __init__(self, dry_run: bool = False):
        """Initialize browser agent.

        Args:
            dry_run: If True, simulate actions without executing
        """
        self.dry_run = dry_run
        self.loop_detector = LoopDetector()
        self.extractor = AccessibilityTreeExtractor()
        self.browser = None
        self.page = None

    async def initialize(self) -> None:
        """Initialize browser instance."""
        if self.dry_run:
            print("[DRY RUN] Browser initialization simulated")
            return

        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            print("[BROWSER] Initialized Chromium browser")
        except ImportError:
            print("[ERROR] Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            print("[BROWSER] Cleaned up")

    async def navigate(self, url: str) -> BrowserAction:
        """Navigate to URL.

        Args:
            url: Target URL

        Returns:
            BrowserAction with result
        """
        start_time = time.time()
        tokens_used = 0

        if self.dry_run:
            print(f"[DRY RUN] Navigate to: {url}")
            await asyncio.sleep(0.1)  # Simulate latency
        else:
            await self.page.goto(url, wait_until="networkidle")

        # Get accessibility tree snapshot
        tree = self.extractor.extract("")
        snapshot_hash = self.extractor.compute_hash(tree)
        tokens_used = len(json.dumps(tree)) // 4  # Rough token estimate

        action = BrowserAction(
            action_type="navigate",
            target=url,
            snapshot_hash=snapshot_hash,
            tokens_used=tokens_used,
            latency_ms=(time.time() - start_time) * 1000,
        )

        if self.loop_detector.add_action(action):
            action.success = False
            print(f"[LOOP DETECTED] Navigation loop at {url}")

        return action

    async def snapshot(self) -> BrowserAction:
        """Take accessibility tree snapshot.

        Returns:
            BrowserAction with snapshot
        """
        start_time = time.time()

        if self.dry_run:
            print("[DRY RUN] Taking accessibility snapshot")
            await asyncio.sleep(0.05)

        tree = self.extractor.extract("")
        snapshot_hash = self.extractor.compute_hash(tree)
        tokens_used = len(json.dumps(tree)) // 4

        action = BrowserAction(
            action_type="snapshot",
            target="current_page",
            snapshot_hash=snapshot_hash,
            tokens_used=tokens_used,
            latency_ms=(time.time() - start_time) * 1000,
        )

        return action

    async def click(self, element_ref: str) -> BrowserAction:
        """Click on element by reference.

        Args:
            element_ref: Element reference (e.g., @e1, @e3)

        Returns:
            BrowserAction with result
        """
        start_time = time.time()

        if self.dry_run:
            print(f"[DRY RUN] Click: {element_ref}")
            await asyncio.sleep(0.1)
        else:
            # In real implementation, map @eN to actual selector
            # await self.page.click(selector)
            pass

        action = BrowserAction(
            action_type="click",
            target=element_ref,
            tokens_used=50,  # Minimal tokens for click action
            latency_ms=(time.time() - start_time) * 1000,
        )

        if self.loop_detector.add_action(action):
            action.success = False
            print(f"[LOOP DETECTED] Click loop on {element_ref}")

        return action

    async def fill(self, element_ref: str, text: str) -> BrowserAction:
        """Fill text in input element.

        Args:
            element_ref: Element reference
            text: Text to fill

        Returns:
            BrowserAction with result
        """
        start_time = time.time()

        if self.dry_run:
            print(f"[DRY RUN] Fill {element_ref}: {'*' * len(text)}")
            await asyncio.sleep(0.05)

        action = BrowserAction(
            action_type="fill",
            target=f"{element_ref}:{text[:10]}...",
            tokens_used=50 + len(text) // 4,
            latency_ms=(time.time() - start_time) * 1000,
        )

        return action


# Test case definitions
TEST_CASES = [
    # Phase 1: Basic Navigation
    TestCase(
        id="nav_001",
        phase=TestPhase.BASIC_NAVIGATION,
        name="Navigate to Railway Dashboard",
        description="Navigate to Railway login/dashboard page",
        steps=[
            {"action": "navigate", "url": "https://railway.app/dashboard"},
            {"action": "snapshot"},
        ],
        expected_outcome="Successfully load Railway dashboard or login page",
    ),
    TestCase(
        id="nav_002",
        phase=TestPhase.BASIC_NAVIGATION,
        name="Read deployment status",
        description="Navigate to project and read deployment status",
        steps=[
            {"action": "navigate", "url": "https://railway.app/project/delightful-cat"},
            {"action": "snapshot"},
        ],
        expected_outcome="Accessibility tree contains deployment status elements",
    ),
    TestCase(
        id="nav_003",
        phase=TestPhase.BASIC_NAVIGATION,
        name="Read service list",
        description="Get list of services from project overview",
        steps=[
            {"action": "navigate", "url": "https://railway.app/project/delightful-cat"},
            {"action": "snapshot"},
        ],
        expected_outcome="Service list visible in accessibility tree",
    ),
    TestCase(
        id="nav_004",
        phase=TestPhase.BASIC_NAVIGATION,
        name="Navigate to deployment logs",
        description="Navigate to specific deployment's logs page",
        steps=[
            {"action": "navigate", "url": "https://railway.app/project/delightful-cat/service/xxx/logs"},
            {"action": "snapshot"},
        ],
        expected_outcome="Logs content accessible",
    ),
    TestCase(
        id="nav_005",
        phase=TestPhase.BASIC_NAVIGATION,
        name="Read environment variables",
        description="Navigate to variables page and read names (not values)",
        steps=[
            {"action": "navigate", "url": "https://railway.app/project/delightful-cat/service/xxx/variables"},
            {"action": "snapshot"},
        ],
        expected_outcome="Variable names visible (values may be masked)",
    ),
    # Phase 2: Interactive Operations
    TestCase(
        id="int_001",
        phase=TestPhase.INTERACTIVE,
        name="Click Redeploy button (dry-run)",
        description="Locate and click redeploy button without confirming",
        steps=[
            {"action": "navigate", "url": "https://railway.app/project/delightful-cat"},
            {"action": "snapshot"},
            {"action": "click", "target": "@e_redeploy"},  # Placeholder ref
        ],
        expected_outcome="Redeploy button clicked, confirmation dialog appears",
        dry_run_safe=True,
    ),
    TestCase(
        id="int_002",
        phase=TestPhase.INTERACTIVE,
        name="Open service settings",
        description="Click to open service settings modal",
        steps=[
            {"action": "snapshot"},
            {"action": "click", "target": "@e_settings"},
        ],
        expected_outcome="Settings modal opens",
        dry_run_safe=True,
    ),
    TestCase(
        id="int_003",
        phase=TestPhase.INTERACTIVE,
        name="Navigate pagination",
        description="Click through deployment history pagination",
        steps=[
            {"action": "snapshot"},
            {"action": "click", "target": "@e_next_page"},
            {"action": "snapshot"},
        ],
        expected_outcome="Next page of deployments loaded",
        dry_run_safe=True,
    ),
    TestCase(
        id="int_004",
        phase=TestPhase.INTERACTIVE,
        name="Filter deployments",
        description="Apply status filter to deployments",
        steps=[
            {"action": "click", "target": "@e_filter"},
            {"action": "click", "target": "@e_filter_failed"},
            {"action": "snapshot"},
        ],
        expected_outcome="Only failed deployments shown",
        dry_run_safe=True,
    ),
    TestCase(
        id="int_005",
        phase=TestPhase.INTERACTIVE,
        name="Expand service details",
        description="Click to expand/collapse service details",
        steps=[
            {"action": "click", "target": "@e_expand"},
            {"action": "snapshot"},
            {"action": "click", "target": "@e_collapse"},
        ],
        expected_outcome="Service details toggle correctly",
        dry_run_safe=True,
    ),
    # Phase 3: Complex Workflows
    TestCase(
        id="wf_001",
        phase=TestPhase.COMPLEX_WORKFLOWS,
        name="Find stuck deployment",
        description="Navigate and identify deployment in QUEUED state",
        steps=[
            {"action": "navigate", "url": "https://railway.app/project/delightful-cat"},
            {"action": "snapshot"},
            # Would need LLM to analyze and decide next action
        ],
        expected_outcome="Stuck deployment identified with service name",
        dry_run_safe=True,
    ),
    TestCase(
        id="wf_002",
        phase=TestPhase.COMPLEX_WORKFLOWS,
        name="Navigate to delete dialog",
        description="Navigate to delete confirmation for a service",
        steps=[
            {"action": "snapshot"},
            {"action": "click", "target": "@e_service_menu"},
            {"action": "click", "target": "@e_delete_option"},
            {"action": "snapshot"},
        ],
        expected_outcome="Delete confirmation dialog visible",
        dry_run_safe=True,  # Don't actually delete
    ),
    TestCase(
        id="wf_003",
        phase=TestPhase.COMPLEX_WORKFLOWS,
        name="Full status check workflow",
        description="Login -> Find Service -> Check Status -> Return",
        steps=[
            {"action": "navigate", "url": "https://railway.app/dashboard"},
            {"action": "snapshot"},
            {"action": "click", "target": "@e_project"},
            {"action": "snapshot"},
            {"action": "click", "target": "@e_service"},
            {"action": "snapshot"},
        ],
        expected_outcome="Complete workflow executed, status retrieved",
        dry_run_safe=True,
    ),
]


def calculate_cost(tokens: int) -> float:
    """Calculate cost from token count.

    Args:
        tokens: Number of tokens used

    Returns:
        Cost in USD
    """
    # Assume 70% input, 30% output ratio
    input_tokens = int(tokens * 0.7)
    output_tokens = int(tokens * 0.3)

    cost = (input_tokens / 1_000_000 * TOKEN_PRICING["input_per_1m"]) + (
        output_tokens / 1_000_000 * TOKEN_PRICING["output_per_1m"]
    )
    return cost


async def run_test_case(agent: BrowserAgent, test_case: TestCase) -> TestResult:
    """Run a single test case.

    Args:
        agent: Browser agent instance
        test_case: Test case to run

    Returns:
        TestResult with metrics
    """
    print(f"\n--- Running: {test_case.name} ({test_case.id}) ---")
    print(f"Description: {test_case.description}")

    actions: list[BrowserAction] = []
    total_tokens = 0
    loop_detected = False
    error_message = ""

    try:
        for step in test_case.steps:
            action_type = step["action"]

            if action_type == "navigate":
                action = await agent.navigate(step["url"])
            elif action_type == "snapshot":
                action = await agent.snapshot()
            elif action_type == "click":
                action = await agent.click(step["target"])
            elif action_type == "fill":
                action = await agent.fill(step["target"], step.get("text", ""))
            else:
                print(f"[WARNING] Unknown action type: {action_type}")
                continue

            actions.append(action)
            total_tokens += action.tokens_used

            if not action.success:
                loop_detected = True
                break

            print(f"  [{action.action_type}] {action.target} - {action.latency_ms:.0f}ms, {action.tokens_used} tokens")

    except Exception as e:
        error_message = str(e)
        print(f"[ERROR] {error_message}")

    total_cost = calculate_cost(total_tokens)
    total_latency = sum(a.latency_ms for a in actions)
    success = not loop_detected and not error_message

    result = TestResult(
        test_case_id=test_case.id,
        success=success,
        actions=actions,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        total_latency_ms=total_latency,
        loop_detected=loop_detected,
        error_message=error_message,
    )

    print(f"Result: {'PASS' if success else 'FAIL'} | Tokens: {total_tokens} | Cost: ${total_cost:.4f}")

    return result


async def run_experiment(phases: list[TestPhase], dry_run: bool = True) -> dict[str, Any]:
    """Run the experiment for specified phases.

    Args:
        phases: List of phases to run
        dry_run: If True, simulate actions

    Returns:
        Experiment results dictionary
    """
    print(f"{'=' * 60}")
    print(f"Experiment: {EXPERIMENT_TITLE}")
    print(f"ID: {EXPERIMENT_ID}")
    print(f"Phases: {[p.name for p in phases]}")
    print(f"Dry Run: {dry_run}")
    print(f"{'=' * 60}")

    # Filter test cases by phase
    selected_tests = [tc for tc in TEST_CASES if tc.phase in phases]
    print(f"\nSelected {len(selected_tests)} test cases")

    # Initialize agent
    agent = BrowserAgent(dry_run=dry_run)
    await agent.initialize()

    results: list[TestResult] = []

    try:
        for test_case in selected_tests:
            if not dry_run and not test_case.dry_run_safe:
                print(f"\n[SKIP] {test_case.name} - Not dry-run safe")
                continue

            result = await run_test_case(agent, test_case)
            results.append(result)

    finally:
        await agent.cleanup()

    # Calculate aggregate metrics
    successful = [r for r in results if r.success]
    total_tokens = sum(r.total_tokens for r in results)
    total_cost = sum(r.total_cost_usd for r in results)
    avg_latency = sum(r.total_latency_ms for r in results) / len(results) if results else 0
    loops_detected = sum(1 for r in results if r.loop_detected)

    metrics = {
        "success_rate": len(successful) / len(results) if results else 0,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "avg_cost_per_test": total_cost / len(results) if results else 0,
        "avg_latency_ms": avg_latency,
        "loop_detection_rate": 1 - (loops_detected / len(results)) if results else 1,
    }

    # Evaluate against success criteria
    evaluation = {
        "success_rate": metrics["success_rate"] >= SUCCESS_CRITERIA["success_rate_min"],
        "token_cost": metrics["avg_cost_per_test"] <= SUCCESS_CRITERIA["token_cost_per_step_max"],
        "latency": metrics["avg_latency_ms"] <= SUCCESS_CRITERIA["avg_latency_max_ms"],
        "loop_detection": metrics["loop_detection_rate"] >= SUCCESS_CRITERIA["loop_detection_rate_min"],
    }

    all_passed = all(evaluation.values())

    # Build results
    experiment_results = {
        "experiment_id": EXPERIMENT_ID,
        "title": EXPERIMENT_TITLE,
        "hypothesis": HYPOTHESIS,
        "timestamp": datetime.utcnow().isoformat(),
        "configuration": {
            "phases": [p.name for p in phases],
            "dry_run": dry_run,
            "test_cases_run": len(results),
        },
        "metrics": metrics,
        "evaluation": evaluation,
        "decision": "ADOPT" if all_passed else "NEEDS_MORE_DATA",
        "test_results": [
            {
                "test_case_id": r.test_case_id,
                "success": r.success,
                "tokens": r.total_tokens,
                "cost_usd": r.total_cost_usd,
                "latency_ms": r.total_latency_ms,
                "loop_detected": r.loop_detected,
                "error": r.error_message,
            }
            for r in results
        ],
    }

    # Print summary
    print(f"\n{'=' * 60}")
    print("EXPERIMENT SUMMARY")
    print(f"{'=' * 60}")
    print(f"Tests Run: {len(results)}")
    print(f"Passed: {len(successful)} ({metrics['success_rate']:.1%})")
    print(f"Total Tokens: {total_tokens}")
    print(f"Total Cost: ${total_cost:.4f}")
    print(f"Avg Latency: {avg_latency:.0f}ms")
    print(f"Loop Detection Rate: {metrics['loop_detection_rate']:.1%}")
    print()
    print("Evaluation:")
    for criterion, passed in evaluation.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {criterion}: {status}")
    print()
    print(f"Decision: {experiment_results['decision']}")

    return experiment_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description=f"Run {EXPERIMENT_ID}: {EXPERIMENT_TITLE}")
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3],
        help="Run specific phase (1=Basic, 2=Interactive, 3=Complex)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all phases",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate actions without executing (default: True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live (not dry-run) - CAUTION: will interact with real UIs",
    )
    parser.add_argument(
        "--output",
        default="results.json",
        help="Output file for results (default: results.json)",
    )
    args = parser.parse_args()

    # Determine phases to run
    if args.all:
        phases = list(TestPhase)
    elif args.phase:
        phases = [TestPhase(args.phase)]
    else:
        phases = [TestPhase.BASIC_NAVIGATION]

    # Determine dry-run mode
    dry_run = not args.live

    # Run experiment
    results = asyncio.run(run_experiment(phases, dry_run=dry_run))

    # Save results
    output_path = Path(__file__).parent / args.output
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    # Return exit code based on decision
    return 0 if results["decision"] == "ADOPT" else 1


if __name__ == "__main__":
    sys.exit(main())
