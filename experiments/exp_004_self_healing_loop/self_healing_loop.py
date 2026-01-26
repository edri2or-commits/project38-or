"""
Self-Healing Loop - Try-Heal-Retry pattern for autonomous error recovery.

Experiment: exp_004
Issue: #615
Research: docs/research/notes/2026-01-25-autonomous-media-systems-claude-remotion.md

This module implements the self-healing loop pattern from the autonomous media
systems research, adapted for Railway deployments and CI/CD failures.

Example:
    >>> from self_healing_loop import SelfHealingLoop, Operation
    >>>
    >>> async def deploy():
    ...     # Your deployment logic
    ...     pass
    >>>
    >>> loop = SelfHealingLoop(max_retries=3)
    >>> result = await loop.execute(Operation(
    ...     name="railway_deploy",
    ...     func=deploy,
    ...     args={"service": "api"}
    ... ))
"""

import asyncio
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND TYPES
# ============================================================================

class ErrorType(Enum):
    """Categories of errors that can be auto-healed."""

    BUILD_FAILURE = "build_failure"
    DEPENDENCY_MISSING = "dependency_missing"
    PORT_CONFLICT = "port_conflict"
    MEMORY_LIMIT = "memory_limit"
    TIMEOUT = "timeout"
    AUTH_FAILURE = "auth_failure"
    CONFIG_ERROR = "config_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


class FixStrategy(Enum):
    """Strategies for fixing errors."""

    RETRY = "retry"  # Simple retry with backoff
    INSTALL_DEPS = "install_deps"  # Install missing dependencies
    INCREASE_TIMEOUT = "increase_timeout"  # Increase timeout value
    INCREASE_MEMORY = "increase_memory"  # Increase memory limit
    REFRESH_TOKEN = "refresh_token"  # Refresh authentication token
    CHANGE_PORT = "change_port"  # Use different port
    ESCALATE = "escalate"  # Cannot auto-fix, escalate to human
    NONE = "none"  # No fix needed (success)


class HealingResult(Enum):
    """Result of a healing attempt."""

    SUCCESS = "success"
    FIXED = "fixed"
    ESCALATED = "escalated"
    MAX_RETRIES = "max_retries"
    FAILED = "failed"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ParsedError:
    """Result of parsing an error."""

    error_type: ErrorType
    message: str
    file_path: str | None = None
    line_number: int | None = None
    suggested_fix: FixStrategy = FixStrategy.ESCALATE
    confidence: float = 0.0
    raw_output: str = ""


@dataclass
class Operation:
    """An operation to execute with self-healing."""

    name: str
    func: Callable
    args: dict = field(default_factory=dict)
    timeout: float = 60.0
    can_retry: bool = True


@dataclass
class HealingAttempt:
    """Record of a healing attempt."""

    attempt_number: int
    error: ParsedError
    fix_applied: FixStrategy
    success: bool
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LoopResult:
    """Final result of the self-healing loop."""

    operation: str
    result: HealingResult
    output: Any = None
    attempts: list[HealingAttempt] = field(default_factory=list)
    total_duration_ms: float = 0
    final_error: ParsedError | None = None


# ============================================================================
# ERROR PATTERNS
# ============================================================================

ERROR_PATTERNS: list[tuple[str, ErrorType, FixStrategy, float]] = [
    # Build failures
    (r"npm ERR!", ErrorType.BUILD_FAILURE, FixStrategy.INSTALL_DEPS, 0.9),
    (r"ModuleNotFoundError", ErrorType.DEPENDENCY_MISSING, FixStrategy.INSTALL_DEPS, 0.95),
    (r"ImportError", ErrorType.DEPENDENCY_MISSING, FixStrategy.INSTALL_DEPS, 0.9),
    (r"cannot find module", ErrorType.DEPENDENCY_MISSING, FixStrategy.INSTALL_DEPS, 0.85),
    (r"No module named", ErrorType.DEPENDENCY_MISSING, FixStrategy.INSTALL_DEPS, 0.95),

    # Port conflicts
    (r"EADDRINUSE", ErrorType.PORT_CONFLICT, FixStrategy.CHANGE_PORT, 0.95),
    (r"port.*already in use", ErrorType.PORT_CONFLICT, FixStrategy.CHANGE_PORT, 0.9),
    (r"address already in use", ErrorType.PORT_CONFLICT, FixStrategy.CHANGE_PORT, 0.9),

    # Memory issues
    (r"ENOMEM", ErrorType.MEMORY_LIMIT, FixStrategy.INCREASE_MEMORY, 0.95),
    (r"heap out of memory", ErrorType.MEMORY_LIMIT, FixStrategy.INCREASE_MEMORY, 0.9),
    (r"JavaScript heap", ErrorType.MEMORY_LIMIT, FixStrategy.INCREASE_MEMORY, 0.85),
    (r"MemoryError", ErrorType.MEMORY_LIMIT, FixStrategy.INCREASE_MEMORY, 0.9),

    # Timeouts
    (r"TimeoutError", ErrorType.TIMEOUT, FixStrategy.INCREASE_TIMEOUT, 0.9),
    (r"ETIMEDOUT", ErrorType.TIMEOUT, FixStrategy.RETRY, 0.85),
    (r"timed out", ErrorType.TIMEOUT, FixStrategy.RETRY, 0.8),
    (r"deadline exceeded", ErrorType.TIMEOUT, FixStrategy.INCREASE_TIMEOUT, 0.85),

    # Auth failures - ALWAYS escalate (security)
    (r"401.*Unauthorized", ErrorType.AUTH_FAILURE, FixStrategy.ESCALATE, 0.95),
    (r"403.*Forbidden", ErrorType.AUTH_FAILURE, FixStrategy.ESCALATE, 0.95),
    (r"authentication failed", ErrorType.AUTH_FAILURE, FixStrategy.ESCALATE, 0.9),
    (r"invalid.*token", ErrorType.AUTH_FAILURE, FixStrategy.ESCALATE, 0.85),

    # Config errors
    (r"missing.*env", ErrorType.CONFIG_ERROR, FixStrategy.ESCALATE, 0.8),
    (r"undefined.*variable", ErrorType.CONFIG_ERROR, FixStrategy.ESCALATE, 0.75),
    (r"config.*not found", ErrorType.CONFIG_ERROR, FixStrategy.ESCALATE, 0.8),

    # Network errors - retry with backoff
    (r"ECONNREFUSED", ErrorType.NETWORK_ERROR, FixStrategy.RETRY, 0.9),
    (r"ECONNRESET", ErrorType.NETWORK_ERROR, FixStrategy.RETRY, 0.85),
    (r"network.*unreachable", ErrorType.NETWORK_ERROR, FixStrategy.RETRY, 0.8),
]


# ============================================================================
# ERROR PARSER
# ============================================================================

class ErrorParser:
    """Parses error output to identify error type and suggested fix."""

    def __init__(self, patterns: list[tuple[str, ErrorType, FixStrategy, float]] | None = None):
        self.patterns = patterns or ERROR_PATTERNS

    def parse(self, output: str, exit_code: int | None = None) -> ParsedError:
        """
        Parse error output and return structured error info.

        Args:
            output: Combined stdout/stderr output
            exit_code: Process exit code if available

        Returns:
            ParsedError with type, message, and suggested fix
        """
        if not output and exit_code == 0:
            return ParsedError(
                error_type=ErrorType.UNKNOWN,
                message="No error detected",
                suggested_fix=FixStrategy.NONE,
                confidence=1.0,
                raw_output=output,
            )

        # Try to match patterns
        best_match: ParsedError | None = None
        best_confidence = 0.0

        for pattern, error_type, fix_strategy, confidence in self.patterns:
            if re.search(pattern, output, re.IGNORECASE):
                if confidence > best_confidence:
                    # Extract more context
                    file_path, line_number = self._extract_location(output)
                    message = self._extract_message(output, pattern)

                    best_match = ParsedError(
                        error_type=error_type,
                        message=message,
                        file_path=file_path,
                        line_number=line_number,
                        suggested_fix=fix_strategy,
                        confidence=confidence,
                        raw_output=output,
                    )
                    best_confidence = confidence

        if best_match:
            return best_match

        # Unknown error
        return ParsedError(
            error_type=ErrorType.UNKNOWN,
            message=output[:500] if output else "Unknown error",
            suggested_fix=FixStrategy.ESCALATE,
            confidence=0.3,
            raw_output=output,
        )

    def _extract_location(self, output: str) -> tuple[str | None, int | None]:
        """Extract file path and line number from error output."""
        # Python traceback
        match = re.search(r'File "([^"]+)", line (\d+)', output)
        if match:
            return match.group(1), int(match.group(2))

        # Node.js/TypeScript
        match = re.search(r'at\s+.*\(([^:]+):(\d+):\d+\)', output)
        if match:
            return match.group(1), int(match.group(2))

        # Generic path:line pattern
        match = re.search(r'([/\w.-]+\.\w+):(\d+)', output)
        if match:
            return match.group(1), int(match.group(2))

        return None, None

    def _extract_message(self, output: str, matched_pattern: str) -> str:
        """Extract a clean error message from the output."""
        # Find the line containing the pattern
        for line in output.split('\n'):
            if re.search(matched_pattern, line, re.IGNORECASE):
                return line.strip()[:200]

        # Fall back to first non-empty line
        for line in output.split('\n'):
            if line.strip():
                return line.strip()[:200]

        return "Error detected"


# ============================================================================
# FIX EXECUTORS
# ============================================================================

class FixExecutor:
    """Executes fixes based on error type."""

    def __init__(self):
        self.fix_handlers: dict[FixStrategy, Callable] = {
            FixStrategy.RETRY: self._fix_retry,
            FixStrategy.INSTALL_DEPS: self._fix_install_deps,
            FixStrategy.INCREASE_TIMEOUT: self._fix_increase_timeout,
            FixStrategy.INCREASE_MEMORY: self._fix_increase_memory,
            FixStrategy.CHANGE_PORT: self._fix_change_port,
            FixStrategy.REFRESH_TOKEN: self._fix_refresh_token,
            FixStrategy.ESCALATE: self._fix_escalate,
            FixStrategy.NONE: self._fix_none,
        }

    async def execute(
        self,
        strategy: FixStrategy,
        error: ParsedError,
        operation: Operation,
        attempt: int,
    ) -> dict[str, Any]:
        """
        Execute a fix strategy.

        Returns:
            Dict with fix result and any modified operation parameters
        """
        handler = self.fix_handlers.get(strategy, self._fix_escalate)
        return await handler(error, operation, attempt)

    async def _fix_retry(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """Simple retry with exponential backoff."""
        backoff = min(2 ** attempt, 30)  # Max 30 seconds
        logger.info(f"Retry fix: waiting {backoff}s before retry #{attempt + 1}")
        await asyncio.sleep(backoff)
        return {"action": "retry", "backoff": backoff}

    async def _fix_install_deps(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """Install missing dependencies."""
        logger.info(f"Attempting to install missing dependencies")

        # Detect package manager and missing package
        output = error.raw_output

        # Python
        if "ModuleNotFoundError" in output or "No module named" in output:
            match = re.search(r"No module named ['\"]?(\w+)", output)
            if match:
                package = match.group(1)
                logger.info(f"Installing Python package: {package}")
                try:
                    result = subprocess.run(
                        ["pip", "install", package],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode == 0:
                        return {"action": "installed", "package": package, "type": "python"}
                except Exception as e:
                    logger.warning(f"Failed to install {package}: {e}")

        # Node.js
        if "npm ERR!" in output or "cannot find module" in output.lower():
            match = re.search(r"Cannot find module ['\"]([^'\"]+)", output)
            if match:
                package = match.group(1)
                if not package.startswith('.'):  # Not a relative import
                    logger.info(f"Installing npm package: {package}")
                    try:
                        result = subprocess.run(
                            ["npm", "install", package],
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        if result.returncode == 0:
                            return {"action": "installed", "package": package, "type": "npm"}
                    except Exception as e:
                        logger.warning(f"Failed to install {package}: {e}")

        return {"action": "install_failed", "reason": "Could not determine package"}

    async def _fix_increase_timeout(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """Increase operation timeout."""
        new_timeout = operation.timeout * 1.5
        operation.timeout = new_timeout
        logger.info(f"Increased timeout to {new_timeout}s")
        return {"action": "timeout_increased", "new_timeout": new_timeout}

    async def _fix_increase_memory(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """Suggest memory increase (cannot auto-fix infrastructure)."""
        logger.warning("Memory limit exceeded - requires infrastructure change")
        return {
            "action": "escalate",
            "reason": "Memory limit requires infrastructure change",
            "suggestion": "Increase NODE_OPTIONS=--max-old-space-size or Railway memory limit",
        }

    async def _fix_change_port(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """Suggest port change."""
        logger.warning("Port conflict detected")
        return {
            "action": "escalate",
            "reason": "Port conflict requires configuration change",
            "suggestion": "Change PORT environment variable or kill existing process",
        }

    async def _fix_refresh_token(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """Token refresh - always escalate for security."""
        logger.warning("Auth failure - escalating (security-sensitive)")
        return {
            "action": "escalate",
            "reason": "Authentication failure requires human intervention",
            "suggestion": "Check API keys, tokens, and permissions",
        }

    async def _fix_escalate(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """Escalate to human."""
        logger.warning(f"Escalating error: {error.message}")
        return {
            "action": "escalate",
            "reason": error.message,
            "error_type": error.error_type.value,
        }

    async def _fix_none(
        self, error: ParsedError, operation: Operation, attempt: int
    ) -> dict[str, Any]:
        """No fix needed."""
        return {"action": "none"}


# ============================================================================
# SELF-HEALING LOOP
# ============================================================================

class SelfHealingLoop:
    """
    Self-healing loop that executes operations with automatic error recovery.

    The loop follows this pattern:
    1. Execute operation
    2. If error: parse error output
    3. Determine fix strategy
    4. Apply fix
    5. Retry (max 3 times)
    6. If still failing: escalate to human

    Example:
        loop = SelfHealingLoop(max_retries=3)
        result = await loop.execute(Operation(
            name="deploy",
            func=railway_deploy,
            args={"service": "api"}
        ))

        if result.result == HealingResult.SUCCESS:
            print("Deployment successful!")
        elif result.result == HealingResult.FIXED:
            print(f"Fixed after {len(result.attempts)} attempts")
        else:
            print(f"Failed: {result.final_error}")
    """

    def __init__(
        self,
        max_retries: int = 3,
        parser: ErrorParser | None = None,
        executor: FixExecutor | None = None,
    ):
        self.max_retries = max_retries
        self.parser = parser or ErrorParser()
        self.executor = executor or FixExecutor()

    async def execute(self, operation: Operation) -> LoopResult:
        """
        Execute an operation with self-healing.

        Args:
            operation: The operation to execute

        Returns:
            LoopResult with outcome and healing attempts
        """
        start_time = datetime.utcnow()
        attempts: list[HealingAttempt] = []
        last_error: ParsedError | None = None

        for attempt_num in range(self.max_retries + 1):
            attempt_start = datetime.utcnow()

            try:
                # Execute the operation
                logger.info(f"Executing {operation.name} (attempt {attempt_num + 1}/{self.max_retries + 1})")

                if asyncio.iscoroutinefunction(operation.func):
                    output = await asyncio.wait_for(
                        operation.func(**operation.args),
                        timeout=operation.timeout,
                    )
                else:
                    output = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: operation.func(**operation.args),
                    )

                # Success!
                duration = (datetime.utcnow() - attempt_start).total_seconds() * 1000

                if attempt_num == 0:
                    result = HealingResult.SUCCESS
                else:
                    result = HealingResult.FIXED

                return LoopResult(
                    operation=operation.name,
                    result=result,
                    output=output,
                    attempts=attempts,
                    total_duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                )

            except Exception as e:
                # Operation failed
                duration = (datetime.utcnow() - attempt_start).total_seconds() * 1000
                error_output = str(e)

                # Parse the error
                parsed_error = self.parser.parse(error_output, exit_code=1)
                last_error = parsed_error

                logger.warning(
                    f"Attempt {attempt_num + 1} failed: {parsed_error.error_type.value} "
                    f"- {parsed_error.message[:100]}"
                )

                # Check if we should escalate immediately
                if parsed_error.suggested_fix == FixStrategy.ESCALATE:
                    attempts.append(HealingAttempt(
                        attempt_number=attempt_num + 1,
                        error=parsed_error,
                        fix_applied=FixStrategy.ESCALATE,
                        success=False,
                        duration_ms=duration,
                    ))

                    return LoopResult(
                        operation=operation.name,
                        result=HealingResult.ESCALATED,
                        attempts=attempts,
                        total_duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                        final_error=parsed_error,
                    )

                # Check if we have retries left
                if attempt_num >= self.max_retries:
                    attempts.append(HealingAttempt(
                        attempt_number=attempt_num + 1,
                        error=parsed_error,
                        fix_applied=FixStrategy.NONE,
                        success=False,
                        duration_ms=duration,
                    ))
                    break

                # Try to fix
                fix_result = await self.executor.execute(
                    parsed_error.suggested_fix,
                    parsed_error,
                    operation,
                    attempt_num,
                )

                attempts.append(HealingAttempt(
                    attempt_number=attempt_num + 1,
                    error=parsed_error,
                    fix_applied=parsed_error.suggested_fix,
                    success=False,
                    duration_ms=duration,
                ))

                # If fix said escalate, stop
                if fix_result.get("action") == "escalate":
                    return LoopResult(
                        operation=operation.name,
                        result=HealingResult.ESCALATED,
                        attempts=attempts,
                        total_duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                        final_error=parsed_error,
                    )

        # Max retries exceeded
        return LoopResult(
            operation=operation.name,
            result=HealingResult.MAX_RETRIES,
            attempts=attempts,
            total_duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            final_error=last_error,
        )

    async def execute_shell(self, command: str, name: str = "shell_command") -> LoopResult:
        """
        Execute a shell command with self-healing.

        Convenience method for running shell commands.

        Args:
            command: Shell command to execute
            name: Name for logging

        Returns:
            LoopResult with outcome
        """
        async def run_command():
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise Exception(f"{result.stderr}\n{result.stdout}")
            return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

        return await self.execute(Operation(
            name=name,
            func=run_command,
            timeout=300,
        ))


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def self_heal(
    func: Callable,
    *args,
    max_retries: int = 3,
    name: str = "operation",
    **kwargs,
) -> LoopResult:
    """
    Execute a function with self-healing.

    Convenience wrapper for SelfHealingLoop.

    Example:
        result = await self_heal(deploy_to_railway, service="api", max_retries=3)
    """
    loop = SelfHealingLoop(max_retries=max_retries)
    return await loop.execute(Operation(
        name=name,
        func=func,
        args=kwargs,
    ))


async def self_heal_shell(command: str, max_retries: int = 3) -> LoopResult:
    """
    Execute a shell command with self-healing.

    Example:
        result = await self_heal_shell("npm run build", max_retries=3)
    """
    loop = SelfHealingLoop(max_retries=max_retries)
    return await loop.execute_shell(command)
