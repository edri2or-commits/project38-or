"""Agent Harness - 24/7 orchestration and execution.

This module provides the infrastructure for running autonomous agents
continuously with scheduling, resource management, and state persistence.

Main components:
- executor: Executes agent code in isolated subprocesses
- scheduler: Orchestrates scheduled execution with APScheduler
- resources: Manages memory/CPU limits and concurrency
- handoff: Preserves state between agent runs

Example:
    >>> from src.harness import AgentScheduler, execute_agent_code
    >>>
    >>> # Execute agent immediately
    >>> result = await execute_agent_code(agent_code, config={})
    >>>
    >>> # Schedule agent for recurring execution
    >>> scheduler = AgentScheduler(get_session)
    >>> await scheduler.start()
"""

from .executor import ExecutionError, ExecutionResult, execute_agent_code
from .handoff import HandoffArtifact, HandoffManager, get_handoff_manager
from .resources import (
    ResourceLimits,
    ResourceMonitor,
    get_resource_monitor,
    set_resource_limits,
)
from .scheduler import AgentScheduler, SchedulerError, execute_scheduled_task

__all__ = [
    # Executor
    "execute_agent_code",
    "ExecutionResult",
    "ExecutionError",
    # Scheduler
    "AgentScheduler",
    "execute_scheduled_task",
    "SchedulerError",
    # Resources
    "ResourceMonitor",
    "ResourceLimits",
    "get_resource_monitor",
    "set_resource_limits",
    # Handoff
    "HandoffArtifact",
    "HandoffManager",
    "get_handoff_manager",
]
