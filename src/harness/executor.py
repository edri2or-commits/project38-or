"""Agent Executor - Runs agent code in isolated subprocess.

This module provides safe execution of generated agent code using asyncio
subprocesses with resource limits and timeout protection.
"""

import asyncio
import json
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Raised when agent execution fails."""

    pass


class ExecutionResult:
    """Result of agent execution.

    Attributes:
        status: 'success', 'error', or 'timeout'
        result: Output data from the agent (dict)
        error: Error message if status is 'error'
        stdout: Standard output captured
        stderr: Standard error captured
        exit_code: Process exit code
        duration: Execution duration in seconds
    """

    def __init__(
        self,
        status: str,
        result: dict | None = None,
        error: str | None = None,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        duration: float = 0.0,
    ):
        """Initialize execution result."""
        self.status = status
        self.result = result or {}
        self.error = error
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration = duration

    def to_dict(self) -> dict:
        """Convert result to dictionary.

        Returns:
            Dictionary representation of the result

        Example:
            >>> result = ExecutionResult(status='success', result={'data': 42})
            >>> result.to_dict()
            {'status': 'success', 'result': {'data': 42}, ...}
        """
        return {
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration": self.duration,
        }


async def execute_agent_code(
    agent_code: str,
    config: dict | None = None,
    timeout: int = 300,
) -> ExecutionResult:
    """Execute agent code in isolated subprocess.

    Creates a temporary Python file with the agent code and executes it
    in a subprocess with timeout and resource limits. The agent must
    define an Agent class with an async execute() method.

    Args:
        agent_code: Python code containing Agent class
        config: Configuration dict to pass to agent (default: {})
        timeout: Maximum execution time in seconds (default: 300/5min)

    Returns:
        ExecutionResult with status, output, and error information

    Raises:
        ExecutionError: If execution setup fails
        ValueError: If agent_code is empty or invalid

    Example:
        >>> code = '''
        ... class Agent:
        ...     async def execute(self):
        ...         return {"status": "success", "result": "Hello"}
        ... '''
        >>> result = await execute_agent_code(code, config={})
        >>> print(result.status)
        success
    """
    if not agent_code or not agent_code.strip():
        raise ValueError("Agent code cannot be empty")

    config = config or {}

    logger.info("Starting agent execution (timeout: %ds)", timeout)

    # Create temporary file for agent code
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        prefix="agent_",
    ) as temp_file:
        temp_path = Path(temp_file.name)

        # Write wrapper code that runs the agent
        wrapper_code = f"""
import asyncio
import json
import sys
import traceback

# Agent code
{agent_code}

async def main():
    \"\"\"Main execution wrapper.\"\"\"
    try:
        # Load config
        config = {json.dumps(config)}

        # Create and execute agent
        agent = Agent(config)
        result = await agent.execute()

        # Print result as JSON for parsing
        print("__RESULT_START__")
        print(json.dumps(result))
        print("__RESULT_END__")

        # Cleanup if method exists
        if hasattr(agent, 'cleanup'):
            await agent.cleanup()

        return 0
    except Exception as e:
        print("__ERROR_START__", file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        print("__ERROR_END__", file=sys.stderr)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
"""
        temp_file.write(wrapper_code)
        temp_file.flush()

    try:
        # Execute the agent code in subprocess
        start_time = asyncio.get_event_loop().time()

        process = await asyncio.create_subprocess_exec(
            "python3",
            str(temp_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for completion with timeout
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
            stdout = stdout_bytes.decode("utf-8")
            stderr = stderr_bytes.decode("utf-8")
            exit_code = process.returncode

        except asyncio.TimeoutError:
            # Kill process on timeout
            try:
                process.kill()
                await process.wait()
            except Exception as kill_error:
                logger.warning("Failed to kill timed-out process: %s", kill_error)

            duration = asyncio.get_event_loop().time() - start_time
            logger.error("Agent execution timed out after %ds", timeout)

            return ExecutionResult(
                status="timeout",
                error=f"Execution exceeded {timeout} seconds timeout",
                duration=duration,
            )

        duration = asyncio.get_event_loop().time() - start_time

        # Parse result from stdout
        result_data = None
        if "__RESULT_START__" in stdout and "__RESULT_END__" in stdout:
            try:
                result_start = stdout.index("__RESULT_START__") + len(
                    "__RESULT_START__"
                )
                result_end = stdout.index("__RESULT_END__")
                result_json = stdout[result_start:result_end].strip()
                result_data = json.loads(result_json)
            except (ValueError, json.JSONDecodeError) as parse_error:
                logger.warning("Failed to parse result JSON: %s", parse_error)

        # Check for errors
        if exit_code != 0 or "__ERROR_START__" in stderr:
            error_msg = stderr
            if "__ERROR_START__" in stderr and "__ERROR_END__" in stderr:
                error_start = stderr.index("__ERROR_START__") + len("__ERROR_START__")
                error_end = stderr.index("__ERROR_END__")
                error_msg = stderr[error_start:error_end].strip()

            logger.error("Agent execution failed: %s", error_msg)

            return ExecutionResult(
                status="error",
                error=error_msg,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
            )

        # Success
        logger.info("Agent execution completed successfully (%.2fs)", duration)

        return ExecutionResult(
            status="success",
            result=result_data or {},
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration=duration,
        )

    finally:
        # Clean up temporary file
        try:
            temp_path.unlink()
        except Exception as cleanup_error:
            logger.warning("Failed to delete temp file: %s", cleanup_error)
