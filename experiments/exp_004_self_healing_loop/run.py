#!/usr/bin/env python3
"""
Experiment: Self-Healing Loop for Railway/CI Failures
ID: exp_004
Issue: #615

Run with:
    python experiments/exp_004_self_healing_loop/run.py
    python experiments/exp_004_self_healing_loop/run.py --test build_failure
    python experiments/exp_004_self_healing_loop/run.py --test all
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add experiment to path
sys.path.insert(0, str(Path(__file__).parent))

from self_healing_loop import (
    ErrorParser,
    ErrorType,
    FixStrategy,
    HealingResult,
    Operation,
    SelfHealingLoop,
    self_heal,
    self_heal_shell,
)


# ============================================================================
# TEST CASES
# ============================================================================

TEST_CASES = {
    "build_failure": {
        "description": "Simulates npm build failure with missing module",
        "error_output": """
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /app/node_modules/missing-package/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory
Cannot find module 'lodash'
    at Function.Module._resolveFilename (node:internal/modules/cjs/loader:933:15)
    at /app/src/index.js:5:1
        """,
        "expected_type": ErrorType.DEPENDENCY_MISSING,
        "expected_fix": FixStrategy.INSTALL_DEPS,
    },
    "python_import": {
        "description": "Simulates Python import error",
        "error_output": """
Traceback (most recent call last):
  File "/app/main.py", line 3, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
        """,
        "expected_type": ErrorType.DEPENDENCY_MISSING,
        "expected_fix": FixStrategy.INSTALL_DEPS,
    },
    "port_conflict": {
        "description": "Simulates port already in use error",
        "error_output": """
Error: listen EADDRINUSE: address already in use :::3000
    at Server.setupListenHandle [as _listen2] (node:net:1330:16)
    at listenInCluster (node:net:1378:12)
        """,
        "expected_type": ErrorType.PORT_CONFLICT,
        "expected_fix": FixStrategy.CHANGE_PORT,
    },
    "memory_limit": {
        "description": "Simulates out of memory error",
        "error_output": """
FATAL ERROR: CALL_AND_RETRY_LAST Allocation failed - JavaScript heap out of memory
 1: 0x10003a8b8 node::Abort() [/usr/local/bin/node]
 2: 0x10003a9c4 node::OOMErrorHandler(char const*, bool) [/usr/local/bin/node]
        """,
        "expected_type": ErrorType.MEMORY_LIMIT,
        "expected_fix": FixStrategy.INCREASE_MEMORY,
    },
    "timeout": {
        "description": "Simulates timeout error",
        "error_output": """
Error: ETIMEDOUT: connection timed out
    at TCPConnectWrap.afterConnect [as oncomplete] (node:net:1157:16)
    at /app/api/client.js:45:10
        """,
        "expected_type": ErrorType.TIMEOUT,
        "expected_fix": FixStrategy.RETRY,
    },
    "auth_failure": {
        "description": "Simulates authentication failure (should escalate)",
        "error_output": """
Error: 401 Unauthorized
Response: {"error": "invalid_token", "message": "The access token expired"}
    at AuthClient.validate (/app/auth.js:23:11)
        """,
        "expected_type": ErrorType.AUTH_FAILURE,
        "expected_fix": FixStrategy.ESCALATE,
    },
    "network_error": {
        "description": "Simulates network connection refused",
        "error_output": """
Error: connect ECONNREFUSED 127.0.0.1:5432
    at TCPConnectWrap.afterConnect [as oncomplete] (node:net:1157:16)
    at /app/db/connection.js:12:5
        """,
        "expected_type": ErrorType.NETWORK_ERROR,
        "expected_fix": FixStrategy.RETRY,
    },
}


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_error_parser():
    """Test error parsing accuracy."""
    print("\n" + "=" * 60)
    print("TEST: Error Parser Accuracy")
    print("=" * 60)

    parser = ErrorParser()
    results = []

    for name, test in TEST_CASES.items():
        parsed = parser.parse(test["error_output"], exit_code=1)

        type_match = parsed.error_type == test["expected_type"]
        fix_match = parsed.suggested_fix == test["expected_fix"]

        result = {
            "name": name,
            "type_match": type_match,
            "fix_match": fix_match,
            "confidence": parsed.confidence,
            "file_found": parsed.file_path is not None,
            "line_found": parsed.line_number is not None,
        }
        results.append(result)

        status = "PASS" if (type_match and fix_match) else "FAIL"
        print(f"\n{status}: {name}")
        print(f"  Description: {test['description']}")
        print(f"  Detected Type: {parsed.error_type.value} (expected: {test['expected_type'].value})")
        print(f"  Suggested Fix: {parsed.suggested_fix.value} (expected: {test['expected_fix'].value})")
        print(f"  Confidence: {parsed.confidence:.0%}")
        if parsed.file_path:
            print(f"  File: {parsed.file_path}:{parsed.line_number or '?'}")

    # Summary
    total = len(results)
    type_correct = sum(1 for r in results if r["type_match"])
    fix_correct = sum(1 for r in results if r["fix_match"])
    both_correct = sum(1 for r in results if r["type_match"] and r["fix_match"])

    print("\n" + "-" * 60)
    print("SUMMARY")
    print("-" * 60)
    print(f"Error Type Accuracy: {type_correct}/{total} ({type_correct/total:.0%})")
    print(f"Fix Strategy Accuracy: {fix_correct}/{total} ({fix_correct/total:.0%})")
    print(f"Full Accuracy: {both_correct}/{total} ({both_correct/total:.0%})")

    return {
        "type_accuracy": type_correct / total,
        "fix_accuracy": fix_correct / total,
        "full_accuracy": both_correct / total,
        "details": results,
    }


async def test_self_healing_loop():
    """Test the self-healing loop with simulated failures."""
    print("\n" + "=" * 60)
    print("TEST: Self-Healing Loop")
    print("=" * 60)

    loop = SelfHealingLoop(max_retries=3)

    # Test 1: Operation that succeeds immediately
    print("\n--- Test 1: Immediate Success ---")

    async def always_succeeds():
        return {"status": "ok"}

    result = await loop.execute(Operation(
        name="always_succeeds",
        func=always_succeeds,
    ))

    print(f"Result: {result.result.value}")
    print(f"Attempts: {len(result.attempts)}")
    assert result.result == HealingResult.SUCCESS, "Should succeed immediately"

    # Test 2: Operation that fails then succeeds
    print("\n--- Test 2: Fail Once Then Succeed ---")

    attempt_count = 0

    async def fails_once():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise Exception("ETIMEDOUT: connection timed out")
        return {"status": "ok", "attempt": attempt_count}

    attempt_count = 0
    result = await loop.execute(Operation(
        name="fails_once",
        func=fails_once,
    ))

    print(f"Result: {result.result.value}")
    print(f"Attempts: {len(result.attempts)}")
    assert result.result == HealingResult.FIXED, "Should fix after retry"

    # Test 3: Operation that always fails (should escalate)
    print("\n--- Test 3: Auth Failure (Should Escalate) ---")

    async def auth_fails():
        raise Exception("Error: 401 Unauthorized - invalid token")

    result = await loop.execute(Operation(
        name="auth_fails",
        func=auth_fails,
    ))

    print(f"Result: {result.result.value}")
    print(f"Attempts: {len(result.attempts)}")
    assert result.result == HealingResult.ESCALATED, "Should escalate auth failure"

    # Test 4: Max retries exceeded
    print("\n--- Test 4: Max Retries Exceeded ---")

    async def always_timeout():
        raise Exception("ETIMEDOUT: connection timed out")

    result = await loop.execute(Operation(
        name="always_timeout",
        func=always_timeout,
    ))

    print(f"Result: {result.result.value}")
    print(f"Attempts: {len(result.attempts)}")
    assert result.result == HealingResult.MAX_RETRIES, "Should hit max retries"
    assert len(result.attempts) == 4, "Should have 4 attempts (1 initial + 3 retries)"

    print("\n" + "-" * 60)
    print("All self-healing loop tests passed!")
    print("-" * 60)

    return {"status": "passed", "tests": 4}


async def test_shell_command():
    """Test shell command healing."""
    print("\n" + "=" * 60)
    print("TEST: Shell Command Healing")
    print("=" * 60)

    # Test successful command
    print("\n--- Test: Successful Command ---")
    result = await self_heal_shell("echo 'Hello World'", max_retries=2)
    print(f"Result: {result.result.value}")
    assert result.result == HealingResult.SUCCESS

    # Test failing command
    print("\n--- Test: Failing Command (non-existent) ---")
    result = await self_heal_shell("nonexistent_command_xyz", max_retries=1)
    print(f"Result: {result.result.value}")
    # This will likely hit max retries since we can't fix a missing command

    print("\n" + "-" * 60)
    print("Shell command tests completed!")
    print("-" * 60)

    return {"status": "completed"}


# ============================================================================
# MAIN
# ============================================================================

async def run_all_tests():
    """Run all experiment tests."""
    results = {
        "experiment_id": "exp_004",
        "timestamp": datetime.utcnow().isoformat(),
        "hypothesis": "Self-healing loops can auto-fix 79% of deployment failures",
        "tests": {},
    }

    # Test 1: Error Parser
    results["tests"]["error_parser"] = test_error_parser()

    # Test 2: Self-Healing Loop
    results["tests"]["self_healing_loop"] = await test_self_healing_loop()

    # Test 3: Shell Commands
    results["tests"]["shell_commands"] = await test_shell_command()

    # Calculate overall metrics
    parser_accuracy = results["tests"]["error_parser"]["full_accuracy"]
    loop_status = results["tests"]["self_healing_loop"]["status"]

    results["summary"] = {
        "error_parse_accuracy": f"{parser_accuracy:.0%}",
        "loop_tests_passed": loop_status == "passed",
        "success_criteria_met": parser_accuracy >= 0.8 and loop_status == "passed",
    }

    # Save results
    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS")
    print("=" * 60)
    print(f"Error Parse Accuracy: {parser_accuracy:.0%} (target: >= 80%)")
    print(f"Loop Tests: {'PASSED' if loop_status == 'passed' else 'FAILED'}")
    print(f"Success Criteria Met: {'YES' if results['summary']['success_criteria_met'] else 'NO'}")
    print(f"\nResults saved to: {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run self-healing loop experiment")
    parser.add_argument(
        "--test",
        choices=["parser", "loop", "shell", "all"],
        default="all",
        help="Which test to run",
    )
    args = parser.parse_args()

    if args.test == "parser":
        test_error_parser()
    elif args.test == "loop":
        asyncio.run(test_self_healing_loop())
    elif args.test == "shell":
        asyncio.run(test_shell_command())
    else:
        asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
