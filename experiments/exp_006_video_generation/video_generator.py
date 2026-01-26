"""
Video Generator - Autonomous video generation with Remotion.

Experiment: exp_006
Issue: #617
Research: docs/research/notes/2026-01-25-autonomous-media-systems-claude-remotion.md

This module provides Python orchestration for Claude-controlled Remotion
video generation pipelines.

Example:
    >>> from video_generator import VideoGenerator
    >>>
    >>> generator = VideoGenerator(project_dir="/path/to/remotion-project")
    >>> result = await generator.generate(
    ...     prompt="Create a 30-second explainer video about AI safety",
    ...     style="modern",
    ... )
"""

import asyncio
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

class VideoStyle(Enum):
    """Predefined video styles."""

    MODERN = "modern"
    MINIMAL = "minimal"
    CORPORATE = "corporate"
    PLAYFUL = "playful"
    TECH = "tech"


class RenderStatus(Enum):
    """Status of video rendering."""

    PENDING = "pending"
    RENDERING = "rendering"
    SUCCESS = "success"
    FAILED = "failed"
    HEALING = "healing"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class BrandConfig:
    """Brand configuration for video generation."""

    primary_color: str = "#2563eb"
    secondary_color: str = "#1e40af"
    font_family: str = "Inter, sans-serif"
    logo_url: str | None = None


@dataclass
class VideoConfig:
    """Video configuration."""

    fps: int = 30
    width: int = 1920
    height: int = 1080
    duration_seconds: float = 30.0

    @property
    def duration_frames(self) -> int:
        return int(self.fps * self.duration_seconds)


@dataclass
class VideoRequest:
    """Request for video generation."""

    prompt: str
    style: VideoStyle = VideoStyle.MODERN
    brand: BrandConfig = field(default_factory=BrandConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    voiceover: bool = False
    background_music: bool = False


@dataclass
class GenerationResult:
    """Result of video generation."""

    status: RenderStatus
    video_path: Path | None = None
    duration_ms: float = 0
    attempts: int = 0
    errors: list[str] = field(default_factory=list)
    cost_estimate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "video_path": str(self.video_path) if self.video_path else None,
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
            "errors": self.errors,
            "cost_estimate": self.cost_estimate,
        }


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

CODE_GENERATION_PROMPT = """Generate a Remotion video component for:

**Topic:** {prompt}

**Duration:** {duration_seconds} seconds ({duration_frames} frames at {fps}fps)

**Style:** {style}

**Brand:**
- Primary color: {primary_color}
- Secondary color: {secondary_color}
- Font: {font_family}

**Structure:**
1. Intro (3 seconds) - Title with fade-in animation
2. Main content ({main_duration} seconds) - Key points with animations
3. Outro (5 seconds) - Call to action with logo

**Technical Requirements:**
- Import from 'remotion': useCurrentFrame, useVideoConfig, interpolate, spring, Sequence, staticFile
- Use the provided brand colors as CSS values
- Use random('unique-seed') for any randomness, NOT Math.random()
- Use Sequence components for timing different sections
- Use interpolate() for smooth animations
- Use spring() for natural motion

**Output Format:**
Return ONLY the TypeScript code for a React component. No explanations.
The component should be named 'GeneratedVideo' and be the default export.

```tsx
import {{ useCurrentFrame, useVideoConfig, interpolate, Sequence }} from 'remotion';

export const GeneratedVideo: React.FC = () => {{
  const frame = useCurrentFrame();
  const {{ fps }} = useVideoConfig();

  // Your implementation here

  return (
    <div style={{{{ backgroundColor: '{primary_color}' }}}}>
      {{/* Video content */}}
    </div>
  );
}};

export default GeneratedVideo;
```
"""


# ============================================================================
# VIDEO GENERATOR
# ============================================================================

class VideoGenerator:
    """
    Orchestrates autonomous video generation with Remotion.

    This class manages the pipeline from natural language prompt
    to rendered video file.

    Example:
        generator = VideoGenerator(project_dir="/path/to/remotion-project")
        result = await generator.generate(
            prompt="Create a product demo video",
            style="modern",
        )

        if result.status == RenderStatus.SUCCESS:
            print(f"Video generated: {result.video_path}")
    """

    def __init__(
        self,
        project_dir: Path | str | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
    ):
        self.project_dir = Path(project_dir) if project_dir else None
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.max_retries = max_retries

        # Try to get API key from GCP
        if not self.api_key:
            try:
                from src.secrets_manager import SecretManager
                manager = SecretManager()
                self.api_key = manager.get_secret("ANTHROPIC-API")
            except Exception:
                pass

    async def generate(self, request: VideoRequest) -> GenerationResult:
        """
        Generate a video from a request.

        Args:
            request: VideoRequest with prompt and configuration

        Returns:
            GenerationResult with status and video path
        """
        start_time = datetime.utcnow()
        errors = []
        attempts = 0

        # Validate project directory
        if not self.project_dir or not self.project_dir.exists():
            return GenerationResult(
                status=RenderStatus.FAILED,
                errors=["Remotion project directory not found. Run setup first."],
            )

        for attempt in range(self.max_retries):
            attempts += 1
            try:
                # Step 1: Generate code
                logger.info(f"Generating video code (attempt {attempt + 1})")
                code = await self._generate_code(request)

                # Step 2: Write code to project
                logger.info("Writing code to project")
                await self._write_code(code)

                # Step 3: Render video
                logger.info("Rendering video")
                video_path = await self._render()

                # Success!
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                cost = self._estimate_cost(request, attempts)

                return GenerationResult(
                    status=RenderStatus.SUCCESS,
                    video_path=video_path,
                    duration_ms=duration,
                    attempts=attempts,
                    cost_estimate=cost,
                )

            except Exception as e:
                error_msg = str(e)
                errors.append(f"Attempt {attempt + 1}: {error_msg}")
                logger.warning(f"Generation failed (attempt {attempt + 1}): {error_msg}")

                # Try to heal
                if attempt < self.max_retries - 1:
                    logger.info("Attempting self-healing...")
                    # Add error context to next attempt
                    request.prompt += f"\n\nPrevious error: {error_msg}\nPlease fix this issue."

        # All attempts failed
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        return GenerationResult(
            status=RenderStatus.FAILED,
            duration_ms=duration,
            attempts=attempts,
            errors=errors,
        )

    async def _generate_code(self, request: VideoRequest) -> str:
        """Generate Remotion component code using Claude."""
        if not self.api_key:
            # Return mock code for testing
            return self._get_mock_code(request)

        import httpx

        prompt = CODE_GENERATION_PROMPT.format(
            prompt=request.prompt,
            duration_seconds=request.video.duration_seconds,
            duration_frames=request.video.duration_frames,
            fps=request.video.fps,
            style=request.style.value,
            primary_color=request.brand.primary_color,
            secondary_color=request.brand.secondary_color,
            font_family=request.brand.font_family,
            main_duration=request.video.duration_seconds - 8,  # Minus intro/outro
        )

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
                    "max_tokens": 4000,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                raise Exception(f"Claude API error: {response.status_code}")

            result = response.json()
            code = result["content"][0]["text"]

            # Extract code from markdown if present
            if "```tsx" in code:
                code = code.split("```tsx")[1].split("```")[0]
            elif "```typescript" in code:
                code = code.split("```typescript")[1].split("```")[0]

            return code.strip()

    async def _write_code(self, code: str) -> None:
        """Write generated code to the Remotion project."""
        component_path = self.project_dir / "src" / "GeneratedVideo.tsx"

        # Ensure directory exists
        component_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the component
        component_path.write_text(code)
        logger.info(f"Wrote component to {component_path}")

        # Update Root.tsx to use the generated component
        root_code = '''
import { Composition } from 'remotion';
import { GeneratedVideo } from './GeneratedVideo';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="GeneratedVideo"
        component={GeneratedVideo}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
'''
        root_path = self.project_dir / "src" / "Root.tsx"
        root_path.write_text(root_code)

    async def _render(self) -> Path:
        """Render the video using Remotion CLI."""
        output_path = self.project_dir / "out" / f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "npx", "remotion", "render",
            "GeneratedVideo",
            str(output_path),
        ]

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300,
            ),
        )

        if result.returncode != 0:
            raise Exception(f"Render failed: {result.stderr}")

        if not output_path.exists():
            raise Exception("Render completed but output file not found")

        return output_path

    def _estimate_cost(self, request: VideoRequest, attempts: int) -> float:
        """Estimate cost of generation."""
        duration_min = request.video.duration_seconds / 60

        # Base costs per minute
        llm_cost = 0.80 * attempts  # Per attempt
        render_cost = 0.02 * duration_min
        tts_cost = 0.24 * duration_min if request.voiceover else 0
        image_cost = 0.15  # Flat fee for any images

        return llm_cost + render_cost + tts_cost + image_cost

    def _get_mock_code(self, request: VideoRequest) -> str:
        """Return mock code for testing without API."""
        return f'''
import {{ useCurrentFrame, useVideoConfig, interpolate, Sequence }} from 'remotion';

export const GeneratedVideo: React.FC = () => {{
  const frame = useCurrentFrame();
  const {{ fps, width, height }} = useVideoConfig();

  const opacity = interpolate(frame, [0, 30], [0, 1], {{
    extrapolateRight: 'clamp',
  }});

  return (
    <div style={{{{
      flex: 1,
      backgroundColor: '{request.brand.primary_color}',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}}}>
      <h1 style={{{{
        fontFamily: '{request.brand.font_family}',
        color: 'white',
        fontSize: 72,
        opacity,
      }}}}>
        {request.prompt[:50]}...
      </h1>
    </div>
  );
}};

export default GeneratedVideo;
'''


# ============================================================================
# SETUP HELPERS
# ============================================================================

async def setup_remotion_project(target_dir: Path) -> bool:
    """
    Initialize a new Remotion project.

    Args:
        target_dir: Directory to create project in

    Returns:
        True if successful
    """
    logger.info(f"Setting up Remotion project in {target_dir}")

    # Check if npm is available
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.error("npm not found")
            return False
    except Exception as e:
        logger.error(f"npm check failed: {e}")
        return False

    # Create project
    try:
        result = subprocess.run(
            ["npx", "create-video@latest", "--blank", str(target_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"Project creation failed: {result.stderr}")
            return False

        logger.info("Remotion project created successfully")
        return True

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return False


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def generate_video(
    prompt: str,
    project_dir: Path | str,
    style: str = "modern",
    duration: float = 30.0,
) -> GenerationResult:
    """
    Quick video generation.

    Example:
        result = await generate_video(
            prompt="Create a product demo",
            project_dir="/path/to/remotion",
        )
    """
    generator = VideoGenerator(project_dir=project_dir)
    request = VideoRequest(
        prompt=prompt,
        style=VideoStyle(style),
        video=VideoConfig(duration_seconds=duration),
    )
    return await generator.generate(request)
