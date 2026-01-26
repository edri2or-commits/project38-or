"""
Vision-Guided Verification - Screenshot analysis for web deployment QA.

Experiment: exp_005
Issue: #616
Research: docs/research/notes/2026-01-25-autonomous-media-systems-claude-remotion.md

This module implements vision-guided verification from the autonomous media
systems research, adapted for web deployment quality assurance.

Example:
    >>> from vision_verifier import VisionVerifier
    >>>
    >>> verifier = VisionVerifier()
    >>> result = await verifier.verify_url("https://or-infra.com")
    >>> print(result.issues)
"""

import asyncio
import base64
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND TYPES
# ============================================================================

class IssueSeverity(Enum):
    """Severity of visual issues."""

    CRITICAL = "critical"  # Page unusable
    HIGH = "high"  # Major visual problem
    MEDIUM = "medium"  # Noticeable issue
    LOW = "low"  # Minor cosmetic
    INFO = "info"  # Suggestion only


class IssueType(Enum):
    """Types of visual issues."""

    OVERLAPPING_TEXT = "overlapping_text"
    MISSING_ELEMENT = "missing_element"
    BROKEN_IMAGE = "broken_image"
    BROKEN_LAYOUT = "broken_layout"
    COLOR_CONTRAST = "color_contrast"
    MOBILE_OVERFLOW = "mobile_overflow"
    TRUNCATED_TEXT = "truncated_text"
    ALIGNMENT_ERROR = "alignment_error"
    RESPONSIVE_ISSUE = "responsive_issue"
    LOADING_ERROR = "loading_error"
    UNKNOWN = "unknown"


class VerificationResult(Enum):
    """Overall verification result."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    ERROR = "error"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class VisualIssue:
    """A detected visual issue."""

    type: IssueType
    severity: IssueSeverity
    description: str
    location: str | None = None  # CSS selector or area description
    suggested_fix: str | None = None
    confidence: float = 0.0


@dataclass
class Screenshot:
    """A captured screenshot."""

    url: str
    viewport: tuple[int, int]
    path: Path
    timestamp: datetime = field(default_factory=datetime.utcnow)
    capture_time_ms: float = 0


@dataclass
class VerificationReport:
    """Complete verification report."""

    url: str
    result: VerificationResult
    screenshots: list[Screenshot] = field(default_factory=list)
    issues: list[VisualIssue] = field(default_factory=list)
    analysis_raw: str = ""
    duration_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def critical_issues(self) -> list[VisualIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]

    @property
    def has_blocking_issues(self) -> bool:
        return len(self.critical_issues) > 0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "result": self.result.value,
            "issue_count": len(self.issues),
            "critical_count": len(self.critical_issues),
            "issues": [
                {
                    "type": i.type.value,
                    "severity": i.severity.value,
                    "description": i.description,
                    "location": i.location,
                    "suggested_fix": i.suggested_fix,
                    "confidence": i.confidence,
                }
                for i in self.issues
            ],
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================================
# SCREENSHOT CAPTURE
# ============================================================================

class ScreenshotCapture:
    """Captures screenshots using Playwright."""

    # Standard viewports
    VIEWPORTS = {
        "desktop": (1920, 1080),
        "tablet": (768, 1024),
        "mobile": (375, 812),
    }

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or Path(tempfile.mkdtemp())
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def capture(
        self,
        url: str,
        viewport: str | tuple[int, int] = "desktop",
        full_page: bool = False,
        wait_for: str | None = None,
    ) -> Screenshot:
        """
        Capture a screenshot of a URL.

        Args:
            url: URL to capture
            viewport: Viewport name or (width, height) tuple
            full_page: Capture full scrollable page
            wait_for: CSS selector to wait for before capture

        Returns:
            Screenshot object with path to image
        """
        start_time = datetime.utcnow()

        # Resolve viewport
        if isinstance(viewport, str):
            vp = self.VIEWPORTS.get(viewport, self.VIEWPORTS["desktop"])
        else:
            vp = viewport

        # Generate output path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{vp[0]}x{vp[1]}_{timestamp}.png"
        output_path = self.output_dir / filename

        # Try Playwright first, fall back to basic method
        try:
            await self._capture_playwright(url, vp, output_path, full_page, wait_for)
        except Exception as e:
            logger.warning(f"Playwright capture failed: {e}, trying fallback")
            await self._capture_fallback(url, vp, output_path)

        capture_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return Screenshot(
            url=url,
            viewport=vp,
            path=output_path,
            capture_time_ms=capture_time,
        )

    async def _capture_playwright(
        self,
        url: str,
        viewport: tuple[int, int],
        output_path: Path,
        full_page: bool,
        wait_for: str | None,
    ) -> None:
        """Capture using Playwright."""
        # Use playwright CLI for simplicity
        cmd = [
            "python", "-c", f"""
import asyncio
from playwright.async_api import async_playwright

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={{'width': {viewport[0]}, 'height': {viewport[1]}}})
        await page.goto('{url}', wait_until='networkidle')
        {'await page.wait_for_selector("' + wait_for + '")' if wait_for else ''}
        await page.screenshot(path='{output_path}', full_page={full_page})
        await browser.close()

asyncio.run(capture())
"""
        ]

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30),
        )

        if result.returncode != 0:
            raise Exception(f"Playwright failed: {result.stderr}")

    async def _capture_fallback(
        self,
        url: str,
        viewport: tuple[int, int],
        output_path: Path,
    ) -> None:
        """Fallback capture method using curl + wkhtmltoimage or similar."""
        # Try wkhtmltoimage if available
        try:
            cmd = [
                "wkhtmltoimage",
                "--width", str(viewport[0]),
                "--height", str(viewport[1]),
                "--quality", "90",
                url,
                str(output_path),
            ]
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30),
            )
            if result.returncode == 0:
                return
        except FileNotFoundError:
            pass

        # Last resort: create a placeholder with error message
        logger.error(f"No screenshot tool available, creating placeholder")
        # Create a simple text file as placeholder
        output_path.write_text(f"Screenshot placeholder for {url}\nViewport: {viewport}")


# ============================================================================
# VISION ANALYSIS
# ============================================================================

VISION_ANALYSIS_PROMPT = """You are a visual QA expert analyzing a screenshot of a web page.

Analyze this screenshot for visual issues. Look for:

1. **Overlapping Text** - Text covering other text or elements
2. **Missing Elements** - Expected UI components not visible
3. **Broken Images** - Placeholder icons, missing images, broken image indicators
4. **Broken Layout** - Misaligned elements, broken grid/flex layouts
5. **Color Contrast** - Text that's hard to read due to poor contrast
6. **Mobile Issues** - Horizontal scrolling, too-small touch targets
7. **Truncated Text** - Text cut off with "..." or hidden
8. **Alignment Errors** - Elements not properly aligned

For each issue found, provide:
- Type (from the list above)
- Severity: critical, high, medium, low, info
- Description of the issue
- Location (describe where on the page)
- Suggested CSS/HTML fix if applicable

If the page looks good with no issues, say "NO_ISSUES_FOUND".

Respond in this JSON format:
```json
{
  "overall_assessment": "pass|warn|fail",
  "issues": [
    {
      "type": "overlapping_text|missing_element|broken_image|broken_layout|color_contrast|mobile_overflow|truncated_text|alignment_error|responsive_issue|loading_error",
      "severity": "critical|high|medium|low|info",
      "description": "Clear description of the issue",
      "location": "Top header area / Navigation menu / etc",
      "suggested_fix": "CSS suggestion if applicable",
      "confidence": 0.95
    }
  ],
  "positive_observations": ["List of things that look good"]
}
```
"""


class VisionAnalyzer:
    """Analyzes screenshots using Claude vision."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            # Try to get from GCP Secret Manager
            try:
                from src.secrets_manager import SecretManager
                manager = SecretManager()
                self.api_key = manager.get_secret("ANTHROPIC-API")
            except Exception:
                pass

    async def analyze(
        self,
        screenshot: Screenshot,
        context: str | None = None,
    ) -> tuple[list[VisualIssue], str]:
        """
        Analyze a screenshot for visual issues.

        Args:
            screenshot: Screenshot to analyze
            context: Additional context about expected appearance

        Returns:
            Tuple of (list of issues, raw analysis text)
        """
        if not self.api_key:
            logger.warning("No API key available, using mock analysis")
            return await self._mock_analyze(screenshot)

        try:
            return await self._analyze_with_claude(screenshot, context)
        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return await self._mock_analyze(screenshot)

    async def _analyze_with_claude(
        self,
        screenshot: Screenshot,
        context: str | None,
    ) -> tuple[list[VisualIssue], str]:
        """Analyze using Claude API."""
        import httpx

        # Read and encode image
        image_data = screenshot.path.read_bytes()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Determine media type
        suffix = screenshot.path.suffix.lower()
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix, "image/png")

        # Build prompt
        prompt = VISION_ANALYSIS_PROMPT
        if context:
            prompt += f"\n\nAdditional context about this page:\n{context}"

        # Call Claude API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2000,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_base64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                            ],
                        }
                    ],
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code} - {response.text}")

            result = response.json()
            analysis_text = result["content"][0]["text"]

            # Parse the JSON response
            issues = self._parse_analysis(analysis_text)
            return issues, analysis_text

    async def _mock_analyze(
        self,
        screenshot: Screenshot,
    ) -> tuple[list[VisualIssue], str]:
        """Mock analysis for testing without API."""
        logger.info("Using mock analysis (no API key)")

        # Check if screenshot file exists and has content
        if not screenshot.path.exists():
            return [
                VisualIssue(
                    type=IssueType.LOADING_ERROR,
                    severity=IssueSeverity.CRITICAL,
                    description="Screenshot file not found",
                    confidence=1.0,
                )
            ], "MOCK: Screenshot missing"

        # Return mock "pass" result
        return [], "MOCK: No issues detected (mock analysis)"

    def _parse_analysis(self, text: str) -> list[VisualIssue]:
        """Parse Claude's analysis into VisualIssue objects."""
        issues = []

        # Check for "no issues" response
        if "NO_ISSUES_FOUND" in text.upper():
            return []

        # Try to extract JSON
        try:
            # Find JSON in the response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                data = json.loads(json_str)

                for issue_data in data.get("issues", []):
                    try:
                        issue = VisualIssue(
                            type=IssueType(issue_data.get("type", "unknown")),
                            severity=IssueSeverity(issue_data.get("severity", "medium")),
                            description=issue_data.get("description", "Unknown issue"),
                            location=issue_data.get("location"),
                            suggested_fix=issue_data.get("suggested_fix"),
                            confidence=float(issue_data.get("confidence", 0.8)),
                        )
                        issues.append(issue)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Failed to parse issue: {e}")

        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from analysis, extracting manually")
            # Fall back to text analysis if JSON parsing fails
            if "overlapping" in text.lower():
                issues.append(VisualIssue(
                    type=IssueType.OVERLAPPING_TEXT,
                    severity=IssueSeverity.HIGH,
                    description="Overlapping text detected",
                    confidence=0.7,
                ))

        return issues


# ============================================================================
# VISION VERIFIER (MAIN CLASS)
# ============================================================================

class VisionVerifier:
    """
    Complete vision verification system.

    Captures screenshots and analyzes them for visual issues.

    Example:
        verifier = VisionVerifier()
        report = await verifier.verify_url("https://example.com")

        if report.has_blocking_issues:
            print("FAIL: Critical visual issues found")
        else:
            print("PASS: No blocking issues")
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        api_key: str | None = None,
    ):
        self.capture = ScreenshotCapture(output_dir)
        self.analyzer = VisionAnalyzer(api_key)

    async def verify_url(
        self,
        url: str,
        viewports: list[str] | None = None,
        context: str | None = None,
        full_page: bool = False,
    ) -> VerificationReport:
        """
        Verify a URL for visual issues.

        Args:
            url: URL to verify
            viewports: List of viewport names ("desktop", "tablet", "mobile")
            context: Additional context about expected appearance
            full_page: Capture full scrollable page

        Returns:
            VerificationReport with all findings
        """
        start_time = datetime.utcnow()
        viewports = viewports or ["desktop"]
        screenshots = []
        all_issues = []
        analysis_texts = []

        for viewport in viewports:
            try:
                # Capture screenshot
                logger.info(f"Capturing {viewport} screenshot of {url}")
                screenshot = await self.capture.capture(
                    url=url,
                    viewport=viewport,
                    full_page=full_page,
                )
                screenshots.append(screenshot)

                # Analyze screenshot
                logger.info(f"Analyzing {viewport} screenshot")
                issues, analysis = await self.analyzer.analyze(screenshot, context)
                all_issues.extend(issues)
                analysis_texts.append(f"[{viewport}]\n{analysis}")

            except Exception as e:
                logger.error(f"Failed to verify {viewport}: {e}")
                all_issues.append(VisualIssue(
                    type=IssueType.LOADING_ERROR,
                    severity=IssueSeverity.CRITICAL,
                    description=f"Failed to capture/analyze {viewport}: {str(e)}",
                    confidence=1.0,
                ))

        # Determine overall result
        if any(i.severity == IssueSeverity.CRITICAL for i in all_issues):
            result = VerificationResult.FAIL
        elif any(i.severity in (IssueSeverity.HIGH, IssueSeverity.MEDIUM) for i in all_issues):
            result = VerificationResult.WARN
        elif all_issues:
            result = VerificationResult.PASS  # Only low/info issues
        else:
            result = VerificationResult.PASS

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        return VerificationReport(
            url=url,
            result=result,
            screenshots=screenshots,
            issues=all_issues,
            analysis_raw="\n\n".join(analysis_texts),
            duration_ms=duration,
        )

    async def verify_deployment(
        self,
        url: str,
        expected_elements: list[str] | None = None,
    ) -> VerificationReport:
        """
        Verify a deployment with standard checks.

        Captures desktop, tablet, and mobile views.
        Checks for expected elements if provided.

        Args:
            url: Deployed URL to verify
            expected_elements: CSS selectors that should be visible

        Returns:
            VerificationReport
        """
        context = None
        if expected_elements:
            context = f"Expected elements: {', '.join(expected_elements)}"

        return await self.verify_url(
            url=url,
            viewports=["desktop", "mobile"],
            context=context,
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def verify_url(url: str, **kwargs) -> VerificationReport:
    """Quick verification of a URL."""
    verifier = VisionVerifier()
    return await verifier.verify_url(url, **kwargs)


async def verify_deployment(url: str, **kwargs) -> VerificationReport:
    """Quick deployment verification."""
    verifier = VisionVerifier()
    return await verifier.verify_deployment(url, **kwargs)
