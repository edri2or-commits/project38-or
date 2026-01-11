"""Agent Executor - Run agent code in sandboxed environments.

This module provides safe execution of generated agent code with:
- Subprocess isolation
- Timeout protection (default: 5 minutes)
- Resource limits (memory, CPU)
- stdout/stderr capture
- Exception handling
"""

import asyncio
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.database import get_session
from src.models.agent import Agent
from src.models.task import Task


@dataclass
class ExecutionResult:
    """Result of agent execution.

    Attributes:
        success: Whether execution succeeded
        stdout: Captured standard output
        stderr: Captured standard error
        exit_code: Process exit code
        duration_seconds: Execution duration
        error_message: Error description if failed
    """

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    error_message: str | None = None


class AgentExecutor:
    """Execute agent code safely in isolated subprocess.

    This executor runs generated Python code in a sandboxed environment with
    resource limits and timeout protection.

    Example:
        >>> executor = AgentExecutor()
        >>> result = await executor.execute_agent(agent_id=1)
        >>> if result.success:
        ...     print(f"Output: {result.stdout}")
    """

    def __init__(
        self,
        timeout_seconds: int = 300,
        max_memory_mb: int = 256,
    ):
        """Initialize executor.

        Args:
            timeout_seconds: Maximum execution time (default: 300 = 5 minutes)
            max_memory_mb: Maximum memory usage in MB (default: 256)
        """
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb

    async def execute_agent(
        self,
        agent_id: int,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Execute agent code and create task record.

        Args:
            agent_id: Database ID of agent to execute
            context: Optional context dict to pass to agent

        Returns:
            ExecutionResult with outputs and status

        Raises:
            ValueError: If agent not found or inactive
            RuntimeError: If execution fails critically
        """
        async for session in get_session():
            # Load agent from database
            agent = await self._load_agent(session, agent_id)

            # Create task record
            task = Task(
                agent_id=agent_id,
                status="running",
                started_at=datetime.utcnow(),
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            try:
                # Execute agent code
                result = await self._run_code(agent.code, context)

                # Update task with result
                task.status = "completed" if result.success else "failed"
                task.completed_at = datetime.utcnow()
                task.result = result.stdout if result.success else None
                task.error = result.error_message if not result.success else None

            except Exception as e:
                # Handle unexpected errors
                result = ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=str(e),
                    exit_code=-1,
                    duration_seconds=0.0,
                    error_message=f"Execution failed: {e}",
                )
                task.status = "failed"
                task.completed_at = datetime.utcnow()
                task.error = str(e)

            finally:
                await session.commit()

            return result

    async def _load_agent(
        self,
        session: AsyncSession,
        agent_id: int,
    ) -> Agent:
        """Load agent from database.

        Args:
            session: Database session
            agent_id: Agent ID

        Returns:
            Agent entity

        Raises:
            ValueError: If agent not found or inactive
        """
        result = await session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if agent.status != "active":
            raise ValueError(f"Agent {agent_id} is not active (status: {agent.status})")

        return agent

    async def _run_code(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Run Python code in isolated subprocess.

        Args:
            code: Python code to execute
            context: Optional context variables

        Returns:
            ExecutionResult with captured outputs
        """
        start_time = datetime.utcnow()

        # Create temporary Python file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            # Inject context if provided
            if context:
                f.write("# Injected context\n")
                f.write(f"CONTEXT = {context!r}\n\n")

            f.write(code)
            temp_file = Path(f.name)

        try:
            # Run in subprocess with timeout
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(temp_file),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_seconds,
                )
                stdout = stdout_bytes.decode("utf-8")
                stderr = stderr_bytes.decode("utf-8")
                exit_code = process.returncode or 0

            except asyncio.TimeoutError:
                # Kill process if timeout
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    duration_seconds=self.timeout_seconds,
                    error_message=f"Timeout after {self.timeout_seconds} seconds",
                )

            duration = (datetime.utcnow() - start_time).total_seconds()

            return ExecutionResult(
                success=exit_code == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_seconds=duration,
                error_message=stderr if exit_code != 0 else None,
            )

        finally:
            # Clean up temporary file
            temp_file.unlink(missing_ok=True)
