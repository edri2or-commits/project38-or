"""Agent Harness - 24/7 orchestration for autonomous agent execution.

This package provides the core infrastructure for running agents continuously
with scheduling, resource management, and context preservation.

Modules:
    executor: Load and execute agent code in sandboxed subprocesses
    scheduler: APScheduler integration with distributed locking
    resources: Resource monitoring and limits (memory, CPU)
    handoff: Context preservation between agent runs (Dual-Agent Pattern)
"""

from src.harness.executor import AgentExecutor, execute_agent_by_id
from src.harness.handoff import (
    HandoffArtifact,
    HandoffContext,
    HandoffManager,
)
from src.harness.resources import (
    ResourceLimits,
    ResourceManager,
    ResourceUsage,
    get_resource_manager,
)
from src.harness.scheduler import AgentScheduler, distributed_lock, get_scheduler

__all__ = [
    # Executor
    "AgentExecutor",
    "execute_agent_by_id",
    # Scheduler
    "AgentScheduler",
    "distributed_lock",
    "get_scheduler",
    # Resources
    "ResourceLimits",
    "ResourceManager",
    "ResourceUsage",
    "get_resource_manager",
    # Handoff
    "HandoffArtifact",
    "HandoffContext",
    "HandoffManager",
]
