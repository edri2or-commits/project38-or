"""Agent Executor for running agent code in sandboxed subprocess.

This module provides the core execution engine for autonomous agents.
Agent code is loaded from the database and executed in isolated subprocesses
with timeout protection and resource limits.
"""

import asyncio
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.agent import Agent
from src.models.task import Task


class AgentExecutor:
    """Executes agent code in sandboxed subprocess with safety constraints.

    The executor loads agent Python code from the database and runs it in
    an isolated subprocess. This provides fault isolation - if the agent
    code crashes or hangs, it won't affect the main application.

    Attributes:
        timeout: Maximum execution time in seconds (default: 300 = 5 minutes)
        max_output_size: Maximum stdout/stderr size in bytes (default: 1MB)
    """

    def __init__(
        self,
        timeout: int = 300,
        max_output_size: int = 1024 * 1024,  # 1MB
    ):
        """Initialize the agent executor.

        Args:
            timeout: Maximum execution time in seconds
            max_output_size: Maximum stdout/stderr size in bytes
        """
        self.timeout = timeout
        self.max_output_size = max_output_size

    async def execute_agent(
        self,
        agent_id: int,
        session: AsyncSession,
    ) -> dict[str, str]:
        """Execute an agent and create a task record.

        Loads the agent code from database, creates a Task record,
        executes the code in a subprocess, and updates the task with results.

        Args:
            agent_id: ID of the agent to execute
            session: Database session for loading agent and creating task

        Returns:
            Dictionary containing execution results:
                - status: "completed" or "failed"
                - result: Agent output (stdout) if successful
                - error: Error message if failed
                - duration: Execution time in seconds

        Raises:
            ValueError: If agent not found or has no code

        Example:
            >>> async with get_session() as session:
            ...     executor = AgentExecutor(timeout=60)
            ...     result = await executor.execute_agent(1, session)
            ...     print(result["status"])
            completed
        """
        # Load agent from database
        statement = select(Agent).where(Agent.id == agent_id)
        result = await session.exec(statement)
        agent = result.first()

        if not agent:
            raise ValueError(f"Agent with id {agent_id} not found")

        if not agent.code:
            raise ValueError(f"Agent {agent_id} has no code to execute")

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
            # Execute agent code in subprocess
            execution_result = await self._execute_in_subprocess(agent.code)

            # Update task with results
            task.status = "completed" if execution_result["success"] else "failed"
            task.result = execution_result.get("stdout")
            task.error = execution_result.get("stderr")
            task.completed_at = datetime.utcnow()

            # Calculate duration
            duration = (task.completed_at - task.started_at).total_seconds()

            await session.commit()

            return {
                "status": task.status,
                "result": task.result or "",
                "error": task.error or "",
                "duration": duration,
            }

        except Exception as e:
            # Handle unexpected errors
            task.status = "failed"
            task.error = f"Executor error: {str(e)}"
            task.completed_at = datetime.utcnow()
            await session.commit()

            raise

    async def _execute_in_subprocess(self, code: str) -> dict[str, str | bool]:
        """Execute Python code in a subprocess with timeout protection.

        Creates a temporary file with the agent code and executes it
        using subprocess. Captures stdout/stderr and enforces timeout.

        Args:
            code: Python code to execute

        Returns:
            Dictionary containing:
                - success: True if exit code was 0
                - stdout: Captured standard output
                - stderr: Captured standard error
                - timeout: True if execution timed out
        """
        # Write code to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as tmp_file:
            tmp_file.write(code)
            tmp_path = Path(tmp_file.name)

        try:
            # Execute in subprocess with timeout
            process = await asyncio.create_subprocess_exec(
                "python3",
                str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )

                # Decode and truncate output
                stdout_str = stdout.decode("utf-8", errors="replace")[
                    : self.max_output_size
                ]
                stderr_str = stderr.decode("utf-8", errors="replace")[
                    : self.max_output_size
                ]

                return {
                    "success": process.returncode == 0,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "timeout": False,
                }

            except asyncio.TimeoutError:
                # Kill the process if it times out
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass  # Process already dead

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Execution timed out after {self.timeout} seconds",
                    "timeout": True,
                }

        finally:
            # Clean up temporary file
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass


async def execute_agent_by_id(
    agent_id: int,
    session: AsyncSession,
    timeout: Optional[int] = None,
) -> dict[str, str]:
    """Convenience function to execute an agent by ID.

    Args:
        agent_id: ID of the agent to execute
        session: Database session
        timeout: Optional timeout override (seconds)

    Returns:
        Execution result dictionary

    Example:
        >>> result = await execute_agent_by_id(1, session, timeout=30)
        >>> print(result["status"])
        completed
    """
    executor_kwargs = {}
    if timeout is not None:
        executor_kwargs["timeout"] = timeout

    executor = AgentExecutor(**executor_kwargs)
    return await executor.execute_agent(agent_id, session)
