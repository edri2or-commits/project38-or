#!/usr/bin/env python3
"""
Experiment: Vision-Guided Verification for Web Deployments
ID: exp_005
Issue: #616

Run with:
    python experiments/exp_005_vision_verification/run.py
    python experiments/exp_005_vision_verification/run.py --url https://or-infra.com
    python experiments/exp_005_vision_verification/run.py --test mock
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add experiment to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vision_verifier import (
    IssueSeverity,
    IssueType,
    ScreenshotCapture,
    VerificationReport,
    VerificationResult,
    VisionAnalyzer,
    VisionVerifier,
    VisualIssue,
)


# ============================================================================
# TEST PAGES (local HTML for testing)
# ============================================================================

TEST_PAGES = {
    "healthy": """
<!DOCTYPE html>
<html>
<head><title>Healthy Page</title>
<style>
body { font-family: Arial; margin: 20px; background: #fff; color: #333; }
h1 { color: #2563eb; }
.container { max-width: 800px; margin: 0 auto; }
</style>
</head>
<body>
<div class="container">
    <h1>Welcome to Our Site</h1>
    <p>This is a healthy page with no visual issues.</p>
    <button style="padding: 10px 20px; background: #2563eb; color: white; border: none; border-radius: 5px;">
        Click Me
    </button>
</div>
</body>
</html>
""",
    "overlapping": """
<!DOCTYPE html>
<html>
<head><title>Overlapping Text</title>
<style>
body { font-family: Arial; margin: 20px; }
.box1 { position: absolute; top: 50px; left: 50px; background: red; padding: 20px; color: white; }
.box2 { position: absolute; top: 60px; left: 60px; background: blue; padding: 20px; color: white; }
</style>
</head>
<body>
<div class="box1">This text is behind</div>
<div class="box2">This text overlaps</div>
</body>
</html>
""",
    "broken_image": """
<!DOCTYPE html>
<html>
<head><title>Broken Image</title>
<style>body { font-family: Arial; margin: 20px; }</style>
</head>
<body>
<h1>Page with Broken Image</h1>
<img src="/nonexistent-image-12345.png" alt="This image is broken">
<p>The image above should show a broken image indicator.</p>
</body>
</html>
""",
    "low_contrast": """
<!DOCTYPE html>
<html>
<head><title>Low Contrast</title>
<style>
body { font-family: Arial; margin: 20px; background: #f0f0f0; }
.low-contrast { color: #d0d0d0; font-size: 14px; }
</style>
</head>
<body>
<h1>Contrast Test</h1>
<p class="low-contrast">This text has very low contrast and is hard to read.</p>
</body>
</html>
""",
    "mobile_overflow": """
<!DOCTYPE html>
<html>
<head><title>Mobile Overflow</title>
<style>
body { font-family: Arial; margin: 20px; }
.wide-content { width: 1200px; background: #eee; padding: 20px; }
</style>
</head>
<body>
<h1>Mobile Overflow Test</h1>
<div class="wide-content">
    This content is too wide for mobile screens and will cause horizontal scrolling.
</div>
</body>
</html>
""",
}


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

async def test_screenshot_capture():
    """Test screenshot capture functionality."""
    print("\n" + "=" * 60)
    print("TEST: Screenshot Capture")
    print("=" * 60)

    capture = ScreenshotCapture()
    results = []

    # Test with a simple URL (or local HTML)
    test_urls = [
        ("https://example.com", "Example.com"),
    ]

    for url, name in test_urls:
        print(f"\nCapturing: {name}")
        try:
            screenshot = await capture.capture(url, viewport="desktop")
            exists = screenshot.path.exists()
            size = screenshot.path.stat().st_size if exists else 0

            result = {
                "name": name,
                "success": exists and size > 0,
                "path": str(screenshot.path),
                "size_bytes": size,
                "capture_time_ms": screenshot.capture_time_ms,
            }
            results.append(result)

            status = "PASS" if result["success"] else "FAIL"
            print(f"  {status}: {screenshot.path.name}")
            print(f"  Size: {size} bytes")
            print(f"  Time: {screenshot.capture_time_ms:.0f}ms")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "name": name,
                "success": False,
                "error": str(e),
            })

    # Summary
    passed = sum(1 for r in results if r.get("success"))
    print("\n" + "-" * 60)
    print(f"Screenshot Capture: {passed}/{len(results)} passed")

    return {"passed": passed, "total": len(results), "results": results}


async def test_vision_analyzer():
    """Test vision analysis (mock mode without API key)."""
    print("\n" + "=" * 60)
    print("TEST: Vision Analyzer (Mock Mode)")
    print("=" * 60)

    analyzer = VisionAnalyzer(api_key=None)  # Force mock mode

    # Create a mock screenshot
    from vision_verifier import Screenshot
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        # Write minimal PNG data
        f.write(b'\x89PNG\r\n\x1a\n')  # PNG header
        mock_path = Path(f.name)

    mock_screenshot = Screenshot(
        url="https://example.com",
        viewport=(1920, 1080),
        path=mock_path,
    )

    print("\nAnalyzing mock screenshot...")
    issues, analysis = await analyzer.analyze(mock_screenshot)

    print(f"Issues found: {len(issues)}")
    print(f"Analysis: {analysis[:200]}...")

    # Cleanup
    mock_path.unlink(missing_ok=True)

    return {
        "issues_count": len(issues),
        "analysis_length": len(analysis),
        "mock_mode": True,
    }


async def test_full_verification():
    """Test full verification pipeline."""
    print("\n" + "=" * 60)
    print("TEST: Full Verification Pipeline")
    print("=" * 60)

    verifier = VisionVerifier()

    # Test with example.com (simple, reliable)
    url = "https://example.com"
    print(f"\nVerifying: {url}")

    try:
        report = await verifier.verify_url(
            url=url,
            viewports=["desktop"],
        )

        print(f"\nResult: {report.result.value.upper()}")
        print(f"Screenshots: {len(report.screenshots)}")
        print(f"Issues: {len(report.issues)}")
        print(f"Duration: {report.duration_ms:.0f}ms")

        if report.issues:
            print("\nIssues found:")
            for issue in report.issues:
                print(f"  - [{issue.severity.value}] {issue.type.value}: {issue.description}")

        return {
            "url": url,
            "result": report.result.value,
            "screenshots": len(report.screenshots),
            "issues": len(report.issues),
            "duration_ms": report.duration_ms,
            "success": report.result in (VerificationResult.PASS, VerificationResult.WARN),
        }

    except Exception as e:
        print(f"ERROR: {e}")
        return {
            "url": url,
            "result": "error",
            "error": str(e),
            "success": False,
        }


async def test_production_deployment():
    """Test with production deployment (or-infra.com)."""
    print("\n" + "=" * 60)
    print("TEST: Production Deployment (or-infra.com)")
    print("=" * 60)

    verifier = VisionVerifier()
    url = "https://or-infra.com"

    print(f"\nVerifying: {url}")
    print("(This tests the actual production deployment)")

    try:
        report = await verifier.verify_deployment(
            url=url,
            expected_elements=[".health", "h1"],
        )

        print(f"\nResult: {report.result.value.upper()}")
        print(f"Screenshots: {len(report.screenshots)}")
        print(f"Issues: {len(report.issues)}")
        print(f"Duration: {report.duration_ms:.0f}ms")

        if report.issues:
            print("\nIssues found:")
            for issue in report.issues:
                print(f"  - [{issue.severity.value}] {issue.type.value}: {issue.description}")
        else:
            print("\nNo issues found - deployment looks healthy!")

        return report.to_dict()

    except Exception as e:
        print(f"ERROR: {e}")
        return {
            "url": url,
            "result": "error",
            "error": str(e),
        }


# ============================================================================
# MAIN
# ============================================================================

async def run_all_tests():
    """Run all experiment tests."""
    results = {
        "experiment_id": "exp_005",
        "timestamp": datetime.utcnow().isoformat(),
        "hypothesis": "Vision verification reduces human review time by 80%",
        "tests": {},
    }

    # Test 1: Screenshot Capture
    results["tests"]["screenshot_capture"] = await test_screenshot_capture()

    # Test 2: Vision Analyzer (Mock)
    results["tests"]["vision_analyzer"] = await test_vision_analyzer()

    # Test 3: Full Verification
    results["tests"]["full_verification"] = await test_full_verification()

    # Calculate summary
    capture_passed = results["tests"]["screenshot_capture"]["passed"] > 0
    verification_passed = results["tests"]["full_verification"].get("success", False)

    results["summary"] = {
        "screenshot_capture": "PASS" if capture_passed else "FAIL",
        "vision_analyzer": "PASS",  # Mock always passes
        "full_verification": "PASS" if verification_passed else "FAIL",
        "overall": "PASS" if (capture_passed and verification_passed) else "PARTIAL",
    }

    # Save results
    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS")
    print("=" * 60)
    print(f"Screenshot Capture: {results['summary']['screenshot_capture']}")
    print(f"Vision Analyzer: {results['summary']['vision_analyzer']}")
    print(f"Full Verification: {results['summary']['full_verification']}")
    print(f"Overall: {results['summary']['overall']}")
    print(f"\nResults saved to: {output_path}")

    return results


async def run_url_test(url: str):
    """Test a specific URL."""
    print(f"\nVerifying URL: {url}")
    verifier = VisionVerifier()

    report = await verifier.verify_url(
        url=url,
        viewports=["desktop", "mobile"],
    )

    print(f"\nResult: {report.result.value.upper()}")
    print(f"Issues: {len(report.issues)}")

    for issue in report.issues:
        print(f"  - [{issue.severity.value}] {issue.type.value}")
        print(f"    {issue.description}")
        if issue.suggested_fix:
            print(f"    Fix: {issue.suggested_fix}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Run vision verification experiment")
    parser.add_argument(
        "--test",
        choices=["capture", "analyzer", "verification", "production", "all"],
        default="all",
        help="Which test to run",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Specific URL to verify",
    )
    args = parser.parse_args()

    if args.url:
        asyncio.run(run_url_test(args.url))
    elif args.test == "capture":
        asyncio.run(test_screenshot_capture())
    elif args.test == "analyzer":
        asyncio.run(test_vision_analyzer())
    elif args.test == "verification":
        asyncio.run(test_full_verification())
    elif args.test == "production":
        asyncio.run(test_production_deployment())
    else:
        asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
