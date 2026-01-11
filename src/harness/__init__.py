"""
Agent Harness - 24/7 Orchestration of Agent Execution.

This module provides infrastructure for running agents continuously with:
- Code execution in sandboxed environments
- State preservation between runs (Handoff Artifacts)
- Automatic scheduling with retry logic
- Resource management (memory, CPU limits)

Example:
    >>> from src.harness import AgentExecutor, TaskScheduler
    >>> executor = AgentExecutor()
    >>> result = await executor.execute_agent(agent_id=1)
"""

from src.harness.executor import AgentExecutor, ExecutionResult
from src.harness.handoff import HandoffManager, HandoffArtifact
from src.harness.scheduler import TaskScheduler
from src.harness.resources import ResourceManager, ResourceLimits

__all__ = [
    "AgentExecutor",
    "ExecutionResult",
    "HandoffManager",
    "HandoffArtifact",
    "TaskScheduler",
    "ResourceManager",
    "ResourceLimits",
]
