"""Base classes for Multi-Agent Orchestration System.

Provides foundation for specialized agents that work together:
- SpecializedAgent: Base class for domain-specific agents
- AgentCapability: Describes what an agent can do
- AgentTask: Unit of work assigned to an agent
- AgentResult: Result from agent task execution

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │              AgentOrchestrator (Coordinator)            │
    │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ │
    │  │  DeployAgent  │ │MonitoringAgent│ │IntegrationAgent│ │
    │  │  (Railway)    │ │ (Observability)│ │ (GitHub+n8n)  │ │
    │  └───────────────┘ └───────────────┘ └───────────────┘ │
    │                         ↓                               │
    │              Inter-Agent Communication                  │
    │              (Message Queue + Events)                   │
    └─────────────────────────────────────────────────────────┘

Example:
    >>> from apps.business.core.multi_agent.base import SpecializedAgent
    >>> from apps.business.core.multi_agent.deploy_agent import DeployAgent
    >>>
    >>> deploy_agent = DeployAgent(railway_client=railway_client)
    >>> result = await deploy_agent.execute_task(AgentTask(
    ...     task_type="deploy",
    ...     parameters={"branch": "main"}
    ... ))
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class AgentDomain(str, Enum):
    """Domain specialization for agents."""

    DEPLOY = "deploy"  # Railway deployments, rollbacks, scaling
    MONITORING = "monitoring"  # Observability, metrics, alerting
    INTEGRATION = "integration"  # GitHub PRs/issues, n8n workflows
    SECURITY = "security"  # Secret rotation, audit, compliance
    GENERAL = "general"  # Fallback for unspecialized tasks


class TaskPriority(int, Enum):
    """Priority levels for agent tasks."""

    CRITICAL = 1  # Immediate execution (system down)
    HIGH = 2  # Urgent (degraded performance)
    MEDIUM = 3  # Standard operations
    LOW = 4  # Background/optimization tasks
    INFO = 5  # Informational/reporting only


class TaskStatus(str, Enum):
    """Status of an agent task."""

    PENDING = "pending"  # Waiting to be picked up
    IN_PROGRESS = "in_progress"  # Currently executing
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Execution failed
    CANCELLED = "cancelled"  # Cancelled before completion
    DELEGATED = "delegated"  # Handed off to another agent


@dataclass
class AgentCapability:
    """Describes a capability that an agent provides.

    Attributes:
        name: Unique identifier for the capability
        domain: Which domain this capability belongs to
        description: Human-readable description
        requires_approval: Whether human approval needed
        max_concurrent: Maximum concurrent executions
        cooldown_seconds: Minimum time between executions
    """

    name: str
    domain: AgentDomain
    description: str
    requires_approval: bool = False
    max_concurrent: int = 3
    cooldown_seconds: int = 0


@dataclass
class AgentTask:
    """Unit of work assigned to an agent.

    Attributes:
        task_id: Unique task identifier
        task_type: Type of task (maps to capability)
        domain: Target domain for routing
        parameters: Task-specific parameters
        priority: Execution priority
        status: Current status
        created_at: When task was created
        started_at: When execution began
        completed_at: When execution finished
        assigned_agent: Which agent is handling this
        parent_task_id: For subtasks, the parent's ID
        metadata: Additional context
    """

    task_type: str
    parameters: dict[str, Any]
    domain: AgentDomain = AgentDomain.GENERAL
    priority: TaskPriority = TaskPriority.MEDIUM
    task_id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_agent: str | None = None
    parent_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result from agent task execution.

    Attributes:
        task_id: ID of the executed task
        success: Whether execution succeeded
        data: Result data
        error: Error message if failed
        duration_ms: Execution duration in milliseconds
        subtasks_created: IDs of any spawned subtasks
        recommendations: Suggested follow-up actions
    """

    task_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    subtasks_created: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class AgentMessage:
    """Message for inter-agent communication.

    Attributes:
        message_id: Unique message identifier
        from_agent: Sender agent ID
        to_agent: Target agent ID (None for broadcast)
        message_type: Type of message
        payload: Message content
        timestamp: When message was sent
        requires_response: Whether response expected
        response_to: If this is a response, original message ID
    """

    from_agent: str
    message_type: str
    payload: dict[str, Any]
    to_agent: str | None = None
    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    requires_response: bool = False
    response_to: str | None = None


class SpecializedAgent(ABC):
    """Base class for domain-specific agents.

    Specialized agents handle tasks within their domain:
    - DeployAgent: Railway deployments
    - MonitoringAgent: Observability and alerting
    - IntegrationAgent: GitHub and n8n operations

    Subclasses must implement:
    - capabilities: List of AgentCapability
    - _execute_task_internal: Actual task execution logic

    Attributes:
        agent_id: Unique agent identifier
        domain: Primary domain for this agent
        logger: Agent-specific logger
        is_running: Whether agent is currently active
    """

    def __init__(
        self,
        agent_id: str | None = None,
        domain: AgentDomain = AgentDomain.GENERAL,
    ):
        """Initialize specialized agent.

        Args:
            agent_id: Unique identifier (auto-generated if None)
            domain: Primary domain for this agent
        """
        self.agent_id = agent_id or f"{domain.value}-{str(uuid4())[:8]}"
        self.domain = domain
        self.logger = logging.getLogger(f"agent.{self.agent_id}")
        self.is_running = False

        # Task tracking
        self._active_tasks: dict[str, AgentTask] = {}
        self._task_history: list[AgentResult] = []

        # Communication
        self._message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._message_handlers: dict[str, Any] = {}

        # Statistics
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_execution_time_ms = 0

    @property
    @abstractmethod
    def capabilities(self) -> list[AgentCapability]:
        """List of capabilities this agent provides.

        Returns:
            List of AgentCapability objects describing what this agent can do.
        """
        pass

    @abstractmethod
    async def _execute_task_internal(self, task: AgentTask) -> AgentResult:
        """Internal task execution logic.

        Subclasses implement their domain-specific task handling here.

        Args:
            task: Task to execute

        Returns:
            AgentResult with execution outcome
        """
        pass

    def can_handle(self, task: AgentTask) -> bool:
        """Check if this agent can handle a task.

        Args:
            task: Task to check

        Returns:
            True if agent has capability to handle task
        """
        # Check domain match
        if task.domain != AgentDomain.GENERAL and task.domain != self.domain:
            return False

        # Check capability match
        capability_names = [c.name for c in self.capabilities]
        return task.task_type in capability_names

    def get_capability(self, task_type: str) -> AgentCapability | None:
        """Get capability for a task type.

        Args:
            task_type: Type of task

        Returns:
            AgentCapability if found, None otherwise
        """
        for cap in self.capabilities:
            if cap.name == task_type:
                return cap
        return None

    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a task with tracking and error handling.

        Args:
            task: Task to execute

        Returns:
            AgentResult with execution outcome
        """
        # Validate capability
        if not self.can_handle(task):
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"Agent {self.agent_id} cannot handle task type: {task.task_type}",
            )

        # Check concurrent limit
        capability = self.get_capability(task.task_type)
        if capability:
            active_count = sum(
                1 for t in self._active_tasks.values() if t.task_type == task.task_type
            )
            if active_count >= capability.max_concurrent:
                return AgentResult(
                    task_id=task.task_id,
                    success=False,
                    error=(
                        f"Max concurrent limit ({capability.max_concurrent}) "
                        f"reached for {task.task_type}"
                    ),
                )

        # Track task
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(UTC)
        task.assigned_agent = self.agent_id
        self._active_tasks[task.task_id] = task

        start_time = datetime.now(UTC)
        self.logger.info(f"Executing task {task.task_id}: {task.task_type}")

        try:
            result = await self._execute_task_internal(task)
            task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            self._tasks_completed += 1 if result.success else 0
            self._tasks_failed += 0 if result.success else 1

        except Exception as e:
            self.logger.error(f"Task {task.task_id} failed with exception: {e}")
            result = AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )
            task.status = TaskStatus.FAILED
            self._tasks_failed += 1

        # Calculate duration
        end_time = datetime.now(UTC)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        result.duration_ms = duration_ms
        self._total_execution_time_ms += duration_ms

        # Complete tracking
        task.completed_at = end_time
        del self._active_tasks[task.task_id]
        self._task_history.append(result)

        self.logger.info(
            f"Task {task.task_id} completed: success={result.success}, duration={duration_ms}ms"
        )

        return result

    async def send_message(
        self,
        to_agent: str | None,
        message_type: str,
        payload: dict[str, Any],
        requires_response: bool = False,
    ) -> AgentMessage:
        """Send a message to another agent.

        Args:
            to_agent: Target agent ID (None for broadcast)
            message_type: Type of message
            payload: Message content
            requires_response: Whether response is expected

        Returns:
            The sent message
        """
        message = AgentMessage(
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            requires_response=requires_response,
        )
        # Message will be routed by orchestrator
        return message

    async def receive_message(self, message: AgentMessage) -> AgentMessage | None:
        """Receive and process a message.

        Args:
            message: Incoming message

        Returns:
            Response message if required, None otherwise
        """
        handler = self._message_handlers.get(message.message_type)
        if handler:
            response_payload = await handler(message.payload)
            if message.requires_response:
                return AgentMessage(
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    message_type=f"{message.message_type}_response",
                    payload=response_payload or {},
                    response_to=message.message_id,
                )
        return None

    def register_message_handler(
        self,
        message_type: str,
        handler: Any,
    ) -> None:
        """Register a handler for a message type.

        Args:
            message_type: Type of message to handle
            handler: Async function to call with payload
        """
        self._message_handlers[message_type] = handler

    def get_status(self) -> dict[str, Any]:
        """Get current agent status.

        Returns:
            Status dictionary with agent state and statistics
        """
        return {
            "agent_id": self.agent_id,
            "domain": self.domain.value,
            "is_running": self.is_running,
            "capabilities": [c.name for c in self.capabilities],
            "active_tasks": len(self._active_tasks),
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "total_execution_time_ms": self._total_execution_time_ms,
            "success_rate": (
                self._tasks_completed / (self._tasks_completed + self._tasks_failed)
                if (self._tasks_completed + self._tasks_failed) > 0
                else 1.0
            ),
        }

    async def start(self) -> None:
        """Start the agent."""
        self.is_running = True
        self.logger.info(f"Agent {self.agent_id} started")

    async def stop(self) -> None:
        """Stop the agent gracefully."""
        self.is_running = False
        # Wait for active tasks to complete
        while self._active_tasks:
            await asyncio.sleep(0.1)
        self.logger.info(f"Agent {self.agent_id} stopped")
