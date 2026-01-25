"""
WAT Framework - Workflows, Agents, Tools

A framework for building probabilistic agentic automation systems with
self-healing capabilities. Implements the WAT (Workflows, Agents, Tools)
pattern for robust, adaptive automation.

Architecture:
    - Tools: Atomic units of execution (Python functions, MCP servers, APIs)
    - Agents: Cognitive engines that interpret workflows and invoke tools
    - Workflows: Goal definitions in natural language or structured YAML

Key Components:
    - ToolRegistry: Unified tool discovery and registration
    - WorkflowEngine: Workflow definition and execution
    - AgentDefinition: Agent specification with capability matching
    - SelfHealingExecutor: Error recovery with the Loop pattern

Example:
    from src.wat import ToolRegistry, Workflow, AgentDefinition
    from src.wat.executor import SelfHealingExecutor

    # Register tools
    registry = ToolRegistry()
    registry.discover_mcp_tools("src/mcp_gateway/tools")

    # Define workflow
    workflow = Workflow.from_yaml("workflows/lead-gen.yaml")

    # Create agent
    agent = AgentDefinition(
        name="lead-gen-agent",
        capabilities=["search", "scrape", "enrich"],
        tools=registry.get_by_category("data")
    )

    # Execute with self-healing
    executor = SelfHealingExecutor(max_retries=3)
    result = await executor.run(workflow, agent)
"""

from src.wat.types import (
    ToolDefinition,
    ToolCategory,
    ToolInput,
    ToolOutput,
    WorkflowStep,
    WorkflowDefinition,
    AgentCapability,
    ExecutionResult,
    ExecutionStatus,
    ErrorRecoveryStrategy,
)
from src.wat.registry import ToolRegistry
from src.wat.workflow import Workflow, WorkflowEngine
from src.wat.agent import AgentDefinition, AgentDispatcher
from src.wat.executor import SelfHealingExecutor, ExecutionContext

__version__ = "1.0.0"

__all__ = [
    # Types
    "ToolDefinition",
    "ToolCategory",
    "ToolInput",
    "ToolOutput",
    "WorkflowStep",
    "WorkflowDefinition",
    "AgentCapability",
    "ExecutionResult",
    "ExecutionStatus",
    "ErrorRecoveryStrategy",
    # Registry
    "ToolRegistry",
    # Workflow
    "Workflow",
    "WorkflowEngine",
    # Agent
    "AgentDefinition",
    "AgentDispatcher",
    # Executor
    "SelfHealingExecutor",
    "ExecutionContext",
]
