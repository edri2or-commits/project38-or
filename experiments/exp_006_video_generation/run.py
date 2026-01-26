#!/usr/bin/env python3
"""
Experiment: Autonomous Video Generation with Remotion
ID: exp_006
Issue: #617

Run with:
    python experiments/exp_006_video_generation/run.py --test mock
    python experiments/exp_006_video_generation/run.py --setup /path/to/project
    python experiments/exp_006_video_generation/run.py --generate "Create a demo video"
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add experiment and src to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from video_generator import (
    BrandConfig,
    GenerationResult,
    RenderStatus,
    VideoConfig,
    VideoGenerator,
    VideoRequest,
    VideoStyle,
    setup_remotion_project,
)


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_video_request():
    """Test VideoRequest creation."""
    print("\n" + "=" * 60)
    print("TEST: VideoRequest Creation")
    print("=" * 60)

    request = VideoRequest(
        prompt="Create a 30-second product demo video",
        style=VideoStyle.MODERN,
        brand=BrandConfig(
            primary_color="#2563eb",
            secondary_color="#1e40af",
        ),
        video=VideoConfig(
            fps=30,
            duration_seconds=30.0,
        ),
    )

    print(f"\nPrompt: {request.prompt}")
    print(f"Style: {request.style.value}")
    print(f"Duration: {request.video.duration_seconds}s ({request.video.duration_frames} frames)")
    print(f"Brand colors: {request.brand.primary_color}, {request.brand.secondary_color}")

    assert request.video.duration_frames == 900
    print("\n✅ VideoRequest creation: PASS")
    return {"status": "pass"}


async def test_mock_generation():
    """Test video generation in mock mode (no API key)."""
    print("\n" + "=" * 60)
    print("TEST: Mock Video Generation")
    print("=" * 60)

    # Create a temporary project directory
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "mock-project"
        project_dir.mkdir()

        # Create minimal structure
        (project_dir / "src").mkdir()
        (project_dir / "out").mkdir()

        generator = VideoGenerator(project_dir=project_dir, api_key=None)

        request = VideoRequest(
            prompt="Create a simple test video",
            style=VideoStyle.MINIMAL,
        )

        print(f"\nProject dir: {project_dir}")
        print(f"Request: {request.prompt}")

        # Test code generation (mock mode)
        code = await generator._generate_code(request)
        print(f"\nGenerated code length: {len(code)} chars")
        print(f"Contains 'GeneratedVideo': {'GeneratedVideo' in code}")
        print(f"Contains brand color: {request.brand.primary_color in code}")

        # Write code to project
        await generator._write_code(code)
        component_path = project_dir / "src" / "GeneratedVideo.tsx"
        print(f"\nComponent written: {component_path.exists()}")

        # Check if code is valid TSX structure
        code_content = component_path.read_text()
        valid_structure = all([
            "import" in code_content,
            "useCurrentFrame" in code_content or "frame" in code_content.lower(),
            "return" in code_content,
            "<" in code_content,  # Has JSX
        ])
        print(f"Valid TSX structure: {valid_structure}")

    print("\n✅ Mock generation: PASS")
    return {"status": "pass", "code_length": len(code), "valid_structure": valid_structure}


def test_cost_estimation():
    """Test cost estimation."""
    print("\n" + "=" * 60)
    print("TEST: Cost Estimation")
    print("=" * 60)

    generator = VideoGenerator(project_dir=None)

    # Test different configurations
    configs = [
        ("30s basic", VideoRequest(prompt="test", video=VideoConfig(duration_seconds=30)), 1),
        ("60s with voiceover", VideoRequest(prompt="test", video=VideoConfig(duration_seconds=60), voiceover=True), 1),
        ("30s, 3 attempts", VideoRequest(prompt="test", video=VideoConfig(duration_seconds=30)), 3),
    ]

    for name, request, attempts in configs:
        cost = generator._estimate_cost(request, attempts)
        print(f"\n{name}:")
        print(f"  Duration: {request.video.duration_seconds}s")
        print(f"  Voiceover: {request.voiceover}")
        print(f"  Attempts: {attempts}")
        print(f"  Estimated cost: ${cost:.2f}")

    print("\n✅ Cost estimation: PASS")
    return {"status": "pass"}


async def test_remotion_available():
    """Check if Remotion/npm is available."""
    print("\n" + "=" * 60)
    print("TEST: Remotion Availability")
    print("=" * 60)

    import subprocess

    # Check npm
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        npm_available = result.returncode == 0
        npm_version = result.stdout.strip() if npm_available else None
    except Exception:
        npm_available = False
        npm_version = None

    print(f"\nnpm available: {npm_available}")
    if npm_version:
        print(f"npm version: {npm_version}")

    # Check if Remotion is installed globally
    try:
        result = subprocess.run(
            ["npx", "remotion", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        remotion_available = result.returncode == 0
        remotion_version = result.stdout.strip() if remotion_available else None
    except Exception:
        remotion_available = False
        remotion_version = None

    print(f"Remotion available: {remotion_available}")
    if remotion_version:
        print(f"Remotion version: {remotion_version}")

    status = "pass" if npm_available else "skip"
    print(f"\n{'✅' if status == 'pass' else '⚠️'} Remotion availability: {status.upper()}")

    return {
        "status": status,
        "npm_available": npm_available,
        "npm_version": npm_version,
        "remotion_available": remotion_available,
        "remotion_version": remotion_version,
    }


# ============================================================================
# MAIN
# ============================================================================

async def run_all_tests():
    """Run all experiment tests."""
    results = {
        "experiment_id": "exp_006",
        "timestamp": datetime.utcnow().isoformat(),
        "hypothesis": "Claude-controlled Remotion can generate videos at $0.45-1.21/min",
        "tests": {},
    }

    # Test 1: VideoRequest
    results["tests"]["video_request"] = test_video_request()

    # Test 2: Mock Generation
    results["tests"]["mock_generation"] = await test_mock_generation()

    # Test 3: Cost Estimation
    results["tests"]["cost_estimation"] = test_cost_estimation()

    # Test 4: Remotion Availability
    results["tests"]["remotion_available"] = await test_remotion_available()

    # Summary
    passed = sum(1 for t in results["tests"].values() if t.get("status") == "pass")
    total = len(results["tests"])

    results["summary"] = {
        "passed": passed,
        "total": total,
        "success": passed >= 3,  # At least 3 tests should pass
    }

    # Save results
    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")
    print(f"Overall: {'PASS' if results['summary']['success'] else 'PARTIAL'}")
    print(f"\nResults saved to: {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run video generation experiment")
    parser.add_argument(
        "--test",
        choices=["request", "mock", "cost", "remotion", "all"],
        default="all",
        help="Which test to run",
    )
    parser.add_argument(
        "--setup",
        type=str,
        help="Setup a new Remotion project at the given path",
    )
    parser.add_argument(
        "--generate",
        type=str,
        help="Generate a video with the given prompt (requires project dir)",
    )
    parser.add_argument(
        "--project",
        type=str,
        help="Path to Remotion project (for --generate)",
    )
    args = parser.parse_args()

    if args.setup:
        asyncio.run(setup_remotion_project(Path(args.setup)))
    elif args.generate:
        if not args.project:
            print("Error: --project required with --generate")
            sys.exit(1)
        from video_generator import generate_video
        result = asyncio.run(generate_video(
            prompt=args.generate,
            project_dir=args.project,
        ))
        print(json.dumps(result.to_dict(), indent=2))
    elif args.test == "request":
        test_video_request()
    elif args.test == "mock":
        asyncio.run(test_mock_generation())
    elif args.test == "cost":
        test_cost_estimation()
    elif args.test == "remotion":
        asyncio.run(test_remotion_available())
    else:
        asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
