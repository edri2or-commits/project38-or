"""AgentOrchestrator - Central Coordinator for Multi-Agent System.

Coordinates multiple specialized agents:
- Routes tasks to appropriate agents based on domain
- Manages inter-agent communication
- Handles task prioritization and scheduling
- Provides unified status and control interface

Integrates with:
- AutonomousController for safety guardrails
- All specialized agents (Deploy, Monitoring, Integration)

Architecture:
    ┌────────────────────────────────────────────────────────────────┐
    │                    AgentOrchestrator                           │
    │  ┌──────────────────────────────────────────────────────────┐ │
    │  │                   Task Queue                              │ │
    │  │    [Priority 1] → [Priority 2] → ... → [Priority 5]      │ │
    │  └──────────────────────────────────────────────────────────┘ │
    │                              ↓                                 │
    │  ┌──────────────────────────────────────────────────────────┐ │
    │  │                   Task Router                             │ │
    │  │    Domain-based routing to specialized agents             │ │
    │  └──────────────────────────────────────────────────────────┘ │
    │                              ↓                                 │
    │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
    │  │ DeployAgent │ │ Monitoring  │ │  IntegrationAgent       │ │
    │  │  (Railway)  │ │   Agent     │ │   (GitHub + n8n)        │ │
    │  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
    │                              ↓                                 │
    │  ┌──────────────────────────────────────────────────────────┐ │
    │  │               Message Bus (Inter-Agent)                   │ │
    │  └──────────────────────────────────────────────────────────┘ │
    └────────────────────────────────────────────────────────────────┘

Example:
    >>> from src.multi_agent.orchestrator import AgentOrchestrator
    >>> from src.multi_agent.deploy_agent import DeployAgent
    >>> from src.multi_agent.monitoring_agent import MonitoringAgent
    >>>
    >>> orchestrator = AgentOrchestrator()
    >>> orchestrator.register_agent(DeployAgent(...))
    >>> orchestrator.register_agent(MonitoringAgent())
    >>>
    >>> task = AgentTask(task_type="deploy", domain=AgentDomain.DEPLOY, ...)
    >>> result = await orchestrator.submit_task(task)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.multi_agent.base import (
    AgentDomain,
    AgentMessage,
    AgentResult,
    AgentTask,
    SpecializedAgent,
    TaskStatus,
)

if TYPE_CHECKING:
    from src.autonomous_controller import AutonomousController


@dataclass
class OrchestratorConfig:
    """Configuration for AgentOrchestrator.

    Attributes:
        max_concurrent_tasks: Maximum tasks processing simultaneously
        task_timeout_seconds: Timeout for individual task execution
        enable_safety_guardrails: Whether to use AutonomousController
        message_retention_count: How many messages to retain in history
    """

    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 300
    enable_safety_guardrails: bool = True
    message_retention_count: int = 1000


@dataclass
class TaskQueueItem:
    """Item in the task queue with priority.

    Attributes:
        task: The task to execute
        submitted_at: When task was submitted
        attempts: Number of execution attempts
    """

    task: AgentTask
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0

    def __lt__(self, other: "TaskQueueItem") -> bool:
        """Compare by priority for heap queue."""
        return self.task.priority.value < other.task.priority.value


class AgentOrchestrator:
    """Central coordinator for multi-agent system.

    Manages task routing, inter-agent communication, and provides
    a unified interface for controlling all agents.

    Attributes:
        config: Orchestrator configuration
        agents: Registered specialized agents
        task_queue: Priority queue of pending tasks
        is_running: Whether orchestrator is active
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        autonomous_controller: "AutonomousController | None" = None,
    ):
        """Initialize AgentOrchestrator.

        Args:
            config: Orchestrator configuration
            autonomous_controller: Safety guardrails controller
        """
        self.config = config or OrchestratorConfig()
        self.autonomous_controller = autonomous_controller
        self.logger = logging.getLogger("orchestrator.multi_agent")

        # Agent registry
        self._agents: dict[str, SpecializedAgent] = {}
        self._domain_agents: dict[AgentDomain, list[str]] = {}

        # Task management
        self._task_queue: asyncio.PriorityQueue[TaskQueueItem] = asyncio.PriorityQueue()
        self._active_tasks: dict[str, AgentTask] = {}
        self._task_results: dict[str, AgentResult] = {}

        # Message bus
        self._message_history: list[AgentMessage] = []
        self._broadcast_handlers: list[Any] = []

        # State
        self.is_running = False
        self._processing_task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)

        # Statistics
        self._tasks_submitted = 0
        self._tasks_completed = 0
        self._tasks_failed = 0

    def register_agent(self, agent: SpecializedAgent) -> None:
        """Register a specialized agent.

        Args:
            agent: Agent to register
        """
        self._agents[agent.agent_id] = agent

        # Index by domain for routing
        if agent.domain not in self._domain_agents:
            self._domain_agents[agent.domain] = []
        self._domain_agents[agent.domain].append(agent.agent_id)

        self.logger.info(f"Registered agent: {agent.agent_id} (domain: {agent.domain.value})")

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent.

        Args:
            agent_id: ID of agent to unregister

        Returns:
            True if agent was found and removed
        """
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]
        del self._agents[agent_id]

        if agent.domain in self._domain_agents:
            self._domain_agents[agent.domain] = [
                aid for aid in self._domain_agents[agent.domain] if aid != agent_id
            ]

        self.logger.info(f"Unregistered agent: {agent_id}")
        return True

    def get_agent(self, agent_id: str) -> SpecializedAgent | None:
        """Get an agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent if found, None otherwise
        """
        return self._agents.get(agent_id)

    def get_agents_for_domain(self, domain: AgentDomain) -> list[SpecializedAgent]:
        """Get all agents for a domain.

        Args:
            domain: Target domain

        Returns:
            List of agents handling that domain
        """
        agent_ids = self._domain_agents.get(domain, [])
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def _select_agent_for_task(self, task: AgentTask) -> SpecializedAgent | None:
        """Select the best agent to handle a task.

        Selection criteria:
        1. Domain match
        2. Capability match
        3. Lowest current load

        Args:
            task: Task to route

        Returns:
            Selected agent or None
        """
        # Get domain-specific agents first
        candidate_agents = self.get_agents_for_domain(task.domain)

        # If no domain-specific agents, try general agents
        if not candidate_agents:
            candidate_agents = self.get_agents_for_domain(AgentDomain.GENERAL)

        # Filter by capability
        capable_agents = [a for a in candidate_agents if a.can_handle(task)]

        if not capable_agents:
            # Try all agents as fallback
            capable_agents = [a for a in self._agents.values() if a.can_handle(task)]

        if not capable_agents:
            return None

        # Select agent with lowest active task count
        return min(capable_agents, key=lambda a: len(a._active_tasks))

    async def submit_task(self, task: AgentTask) -> str:
        """Submit a task for execution.

        Args:
            task: Task to execute

        Returns:
            Task ID for tracking
        """
        self._tasks_submitted += 1
        task.status = TaskStatus.PENDING

        # Check safety guardrails if enabled
        if self.config.enable_safety_guardrails and self.autonomous_controller:
            if self.autonomous_controller.kill_switch_enabled:
                self.logger.warning(f"Task {task.task_id} blocked by kill switch")
                task.status = TaskStatus.CANCELLED
                self._task_results[task.task_id] = AgentResult(
                    task_id=task.task_id,
                    success=False,
                    error="Kill switch is active",
                )
                return task.task_id

        # Add to queue
        await self._task_queue.put(TaskQueueItem(task=task))
        self.logger.info(
            f"Task {task.task_id} submitted: type={task.task_type}, "
            f"domain={task.domain.value}, priority={task.priority.name}"
        )

        # If running, processing happens automatically
        # If not running, task will be processed when start() is called
        return task.task_id

    async def submit_and_wait(self, task: AgentTask) -> AgentResult:
        """Submit a task and wait for completion.

        Args:
            task: Task to execute

        Returns:
            Task result
        """
        task_id = await self.submit_task(task)

        # If not running continuous loop, execute directly
        if not self.is_running:
            return await self._execute_task(task)

        # Wait for result
        while task_id not in self._task_results:
            await asyncio.sleep(0.1)

        return self._task_results[task_id]

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a single task.

        Args:
            task: Task to execute

        Returns:
            Execution result
        """
        # Select agent
        agent = self._select_agent_for_task(task)
        if not agent:
            result = AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"No agent available for task type: {task.task_type}",
            )
            self._tasks_failed += 1
            return result

        # Execute with timeout
        task.assigned_agent = agent.agent_id
        self._active_tasks[task.task_id] = task

        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    agent.execute_task(task),
                    timeout=self.config.task_timeout_seconds,
                )

            if result.success:
                self._tasks_completed += 1
            else:
                self._tasks_failed += 1

        except TimeoutError:
            result = AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"Task timed out after {self.config.task_timeout_seconds}s",
            )
            self._tasks_failed += 1

        except Exception as e:
            result = AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )
            self._tasks_failed += 1

        finally:
            del self._active_tasks[task.task_id]

        self._task_results[task.task_id] = result
        return result

    async def _process_queue(self) -> None:
        """Process tasks from the queue continuously."""
        while self.is_running:
            try:
                # Wait for task with timeout
                item = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0,
                )
                item.attempts += 1

                # Execute task
                await self._execute_task(item.task)
                self._task_queue.task_done()

            except TimeoutError:
                # No tasks in queue, continue loop
                continue
            except Exception as e:
                self.logger.error(f"Error processing task: {e}")

    async def route_message(self, message: AgentMessage) -> AgentMessage | None:
        """Route a message between agents.

        Args:
            message: Message to route

        Returns:
            Response message if any
        """
        self._message_history.append(message)

        # Trim history if needed
        if len(self._message_history) > self.config.message_retention_count:
            self._message_history = self._message_history[-self.config.message_retention_count:]

        if message.to_agent:
            # Direct message to specific agent
            target = self._agents.get(message.to_agent)
            if target:
                return await target.receive_message(message)
        else:
            # Broadcast to all agents
            responses = []
            for agent in self._agents.values():
                if agent.agent_id != message.from_agent:
                    response = await agent.receive_message(message)
                    if response:
                        responses.append(response)

            # Return first response for now
            return responses[0] if responses else None

        return None

    async def broadcast_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event to all agents.

        Args:
            event_type: Type of event
            data: Event data
        """
        message = AgentMessage(
            from_agent="orchestrator",
            message_type=event_type,
            payload=data,
        )

        for agent in self._agents.values():
            try:
                await agent.receive_message(message)
            except Exception as e:
                self.logger.error(
                    f"Error broadcasting to {agent.agent_id}: {e}"
                )

    async def start(self) -> None:
        """Start the orchestrator and all agents."""
        if self.is_running:
            return

        self.is_running = True
        self.logger.info("Starting AgentOrchestrator")

        # Start all agents
        for agent in self._agents.values():
            await agent.start()

        # Start processing loop
        self._processing_task = asyncio.create_task(self._process_queue())

    async def stop(self) -> None:
        """Stop the orchestrator and all agents."""
        if not self.is_running:
            return

        self.is_running = False
        self.logger.info("Stopping AgentOrchestrator")

        # Cancel processing task
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        # Stop all agents
        for agent in self._agents.values():
            await agent.stop()

    def get_task_result(self, task_id: str) -> AgentResult | None:
        """Get result for a task.

        Args:
            task_id: Task identifier

        Returns:
            Result if available, None otherwise
        """
        return self._task_results.get(task_id)

    def get_status(self) -> dict[str, Any]:
        """Get orchestrator status.

        Returns:
            Status dictionary with agent states and statistics
        """
        return {
            "is_running": self.is_running,
            "agents_registered": len(self._agents),
            "agents": {
                aid: agent.get_status()
                for aid, agent in self._agents.items()
            },
            "domains": {
                domain.value: len(agent_ids)
                for domain, agent_ids in self._domain_agents.items()
            },
            "queue_size": self._task_queue.qsize(),
            "active_tasks": len(self._active_tasks),
            "statistics": {
                "tasks_submitted": self._tasks_submitted,
                "tasks_completed": self._tasks_completed,
                "tasks_failed": self._tasks_failed,
                "success_rate": (
                    self._tasks_completed / (self._tasks_completed + self._tasks_failed)
                    if (self._tasks_completed + self._tasks_failed) > 0
                    else 1.0
                ),
            },
            "messages_in_history": len(self._message_history),
        }

    def get_capabilities(self) -> dict[str, list[str]]:
        """Get all available capabilities by domain.

        Returns:
            Dictionary mapping domain to capability names
        """
        capabilities: dict[str, list[str]] = {}
        for agent in self._agents.values():
            domain = agent.domain.value
            if domain not in capabilities:
                capabilities[domain] = []
            capabilities[domain].extend(c.name for c in agent.capabilities)

        # Remove duplicates
        return {d: list(set(caps)) for d, caps in capabilities.items()}


def create_orchestrator(
    railway_client: Any = None,
    github_client: Any = None,
    n8n_client: Any = None,
    autonomous_controller: "AutonomousController | None" = None,
    config: OrchestratorConfig | None = None,
) -> AgentOrchestrator:
    """Factory function to create orchestrator with standard agents.

    Args:
        railway_client: RailwayClient for deploy operations
        github_client: GitHubAppClient for GitHub operations
        n8n_client: N8nClient for workflow operations
        autonomous_controller: Safety guardrails controller
        config: Orchestrator configuration

    Returns:
        Configured AgentOrchestrator with registered agents
    """
    from src.multi_agent.deploy_agent import DeployAgent
    from src.multi_agent.integration_agent import IntegrationAgent
    from src.multi_agent.monitoring_agent import MonitoringAgent

    orchestrator = AgentOrchestrator(
        config=config,
        autonomous_controller=autonomous_controller,
    )

    # Register specialized agents
    if railway_client:
        orchestrator.register_agent(DeployAgent(railway_client=railway_client))

    orchestrator.register_agent(MonitoringAgent())

    if github_client or n8n_client:
        orchestrator.register_agent(
            IntegrationAgent(
                github_client=github_client,
                n8n_client=n8n_client,
            )
        )

    return orchestrator
