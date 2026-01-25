"""
WAT Framework Agent Definition and Dispatch

Agent specification with capability matching and automatic routing.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from src.wat.types import (
    AgentCapability,
    ToolCategory,
    ToolDefinition,
    WorkflowDefinition,
)
from src.wat.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentDomain(str, Enum):
    """Domain specialization for agents."""

    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    INTEGRATION = "integration"
    DATA = "data"
    COMMUNICATION = "communication"
    SECURITY = "security"
    GENERAL = "general"


class ModelTier(str, Enum):
    """LLM model tier for cost optimization."""

    FAST = "fast"  # Haiku - simple tasks
    BALANCED = "balanced"  # Sonnet - most tasks
    POWERFUL = "powerful"  # Opus - complex reasoning


@dataclass
class AgentDefinition:
    """
    Complete agent definition in the WAT framework.

    Agents are cognitive engines that interpret workflows and invoke tools.
    """

    name: str
    description: str
    domain: AgentDomain = AgentDomain.GENERAL
    # Capabilities this agent provides
    capabilities: List[AgentCapability] = field(default_factory=list)
    # Tools this agent can use
    tools: List[str] = field(default_factory=list)
    # Model tier for this agent
    model_tier: ModelTier = ModelTier.BALANCED
    # Custom system prompt additions
    system_prompt_additions: Optional[str] = None
    # Maximum concurrent tool calls
    max_concurrent_tools: int = 5
    # Memory configuration
    memory_window: int = 10  # Number of turns to remember
    # Cost constraints
    max_cost_per_task_usd: float = 1.0
    max_tokens_per_task: int = 100000
    # Whether this agent can create sub-agents
    can_delegate: bool = False
    # Tags for filtering
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize derived attributes."""
        if not self.capabilities and self.tools:
            # Auto-generate capabilities from tools
            self.capabilities = [
                AgentCapability(
                    name=f"can_use_{tool}",
                    description=f"Ability to use {tool}",
                    provided_by=[tool],
                )
                for tool in self.tools
            ]

    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has a specific capability."""
        return any(c.name == capability_name for c in self.capabilities)

    def can_handle(self, workflow: WorkflowDefinition, registry: ToolRegistry) -> float:
        """
        Calculate how well this agent can handle a workflow.

        Args:
            workflow: Workflow to evaluate
            registry: Tool registry for capability checking

        Returns:
            Score from 0.0 (cannot handle) to 1.0 (perfect match)
        """
        required_tools = set(workflow.required_tools)
        available_tools = set(self.tools)

        # Check tool coverage
        covered = required_tools & available_tools
        if not required_tools:
            tool_score = 1.0
        else:
            tool_score = len(covered) / len(required_tools)

        # Check domain match
        domain_score = 0.0
        category_domain_map = {
            ToolCategory.DEPLOYMENT: AgentDomain.DEPLOYMENT,
            ToolCategory.MONITORING: AgentDomain.MONITORING,
            ToolCategory.INTEGRATION: AgentDomain.INTEGRATION,
            ToolCategory.DATA: AgentDomain.DATA,
            ToolCategory.COMMUNICATION: AgentDomain.COMMUNICATION,
            ToolCategory.SECURITY: AgentDomain.SECURITY,
        }

        # Determine workflow's primary domain from required tools
        workflow_domains: Dict[AgentDomain, int] = {}
        for tool_name in required_tools:
            tool = registry.get(tool_name)
            if tool:
                domain = category_domain_map.get(tool.category, AgentDomain.GENERAL)
                workflow_domains[domain] = workflow_domains.get(domain, 0) + 1

        if workflow_domains:
            primary_domain = max(workflow_domains.keys(), key=lambda d: workflow_domains[d])
            if self.domain == primary_domain:
                domain_score = 1.0
            elif self.domain == AgentDomain.GENERAL:
                domain_score = 0.5
            else:
                domain_score = 0.2

        # Weighted score
        final_score = (tool_score * 0.7) + (domain_score * 0.3)
        return final_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "tools": self.tools,
            "model_tier": self.model_tier.value,
            "system_prompt_additions": self.system_prompt_additions,
            "max_concurrent_tools": self.max_concurrent_tools,
            "memory_window": self.memory_window,
            "max_cost_per_task_usd": self.max_cost_per_task_usd,
            "max_tokens_per_task": self.max_tokens_per_task,
            "can_delegate": self.can_delegate,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentDefinition":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            domain=AgentDomain(data.get("domain", "general")),
            capabilities=[
                AgentCapability(**c) for c in data.get("capabilities", [])
            ],
            tools=data.get("tools", []),
            model_tier=ModelTier(data.get("model_tier", "balanced")),
            system_prompt_additions=data.get("system_prompt_additions"),
            max_concurrent_tools=data.get("max_concurrent_tools", 5),
            memory_window=data.get("memory_window", 10),
            max_cost_per_task_usd=data.get("max_cost_per_task_usd", 1.0),
            max_tokens_per_task=data.get("max_tokens_per_task", 100000),
            can_delegate=data.get("can_delegate", False),
            tags=data.get("tags", []),
        )


class AgentDispatcher:
    """
    Dispatcher for routing tasks to appropriate agents.

    Provides:
    - Agent discovery and registration
    - Automatic capability matching
    - Load balancing and fallback
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """
        Initialize dispatcher with tool registry.

        Args:
            registry: Tool registry for capability checking
        """
        self._registry = registry
        self._agents: Dict[str, AgentDefinition] = {}
        self._domain_agents: Dict[AgentDomain, List[str]] = {
            domain: [] for domain in AgentDomain
        }

    def register(self, agent: AgentDefinition) -> None:
        """
        Register an agent with the dispatcher.

        Args:
            agent: Agent definition to register
        """
        self._agents[agent.name] = agent
        self._domain_agents[agent.domain].append(agent.name)
        logger.debug(f"Registered agent: {agent.name} (domain: {agent.domain.value})")

    def unregister(self, name: str) -> bool:
        """
        Remove an agent from the dispatcher.

        Args:
            name: Agent name

        Returns:
            True if removed, False if not found
        """
        if name not in self._agents:
            return False

        agent = self._agents.pop(name)
        self._domain_agents[agent.domain].remove(name)
        return True

    def get(self, name: str) -> Optional[AgentDefinition]:
        """Get an agent by name."""
        return self._agents.get(name)

    def list(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def get_by_domain(self, domain: AgentDomain) -> List[AgentDefinition]:
        """Get all agents in a domain."""
        return [self._agents[name] for name in self._domain_agents.get(domain, [])]

    def find_best_agent(
        self,
        workflow: WorkflowDefinition,
        exclude: Optional[Set[str]] = None,
    ) -> Optional[AgentDefinition]:
        """
        Find the best agent for a workflow.

        Args:
            workflow: Workflow to match
            exclude: Agent names to exclude (for fallback scenarios)

        Returns:
            Best matching agent or None
        """
        exclude = exclude or set()
        best_agent: Optional[AgentDefinition] = None
        best_score = 0.0

        for name, agent in self._agents.items():
            if name in exclude:
                continue

            score = agent.can_handle(workflow, self._registry)
            if score > best_score:
                best_score = score
                best_agent = agent

        if best_agent:
            logger.debug(
                f"Best agent for {workflow.name}: {best_agent.name} (score: {best_score:.2f})"
            )
        else:
            logger.warning(f"No suitable agent found for workflow: {workflow.name}")

        return best_agent

    def find_agents_with_capability(
        self,
        capability: str,
        min_confidence: float = 0.5,
    ) -> List[AgentDefinition]:
        """
        Find all agents with a specific capability.

        Args:
            capability: Capability name to match
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching agents
        """
        matching = []
        for agent in self._agents.values():
            for cap in agent.capabilities:
                if cap.name == capability and cap.confidence >= min_confidence:
                    matching.append(agent)
                    break
        return matching

    def route(
        self,
        workflow: WorkflowDefinition,
        fallback_count: int = 2,
    ) -> List[AgentDefinition]:
        """
        Route a workflow to appropriate agents with fallbacks.

        Args:
            workflow: Workflow to route
            fallback_count: Number of fallback agents to include

        Returns:
            Ordered list of agents (primary + fallbacks)
        """
        agents = []
        exclude: Set[str] = set()

        # Find primary agent
        primary = self.find_best_agent(workflow, exclude)
        if primary:
            agents.append(primary)
            exclude.add(primary.name)

        # Find fallbacks
        for _ in range(fallback_count):
            fallback = self.find_best_agent(workflow, exclude)
            if fallback:
                agents.append(fallback)
                exclude.add(fallback.name)

        return agents

    def to_dict(self) -> Dict[str, Any]:
        """Export dispatcher state to dictionary."""
        return {
            "agents": {name: agent.to_dict() for name, agent in self._agents.items()},
            "domains": {
                domain.value: agents
                for domain, agents in self._domain_agents.items()
                if agents
            },
            "total_agents": len(self._agents),
        }


def create_default_agents(registry: ToolRegistry) -> List[AgentDefinition]:
    """
    Create default agents based on available tools in the registry.

    Args:
        registry: Tool registry to analyze

    Returns:
        List of default agent definitions
    """
    agents = []

    # Deployment agent
    deployment_tools = [t.name for t in registry.get_by_category(ToolCategory.DEPLOYMENT)]
    if deployment_tools:
        agents.append(
            AgentDefinition(
                name="deploy-agent",
                description="Handles deployments, rollbacks, and infrastructure operations",
                domain=AgentDomain.DEPLOYMENT,
                tools=deployment_tools,
                model_tier=ModelTier.BALANCED,
                tags=["infrastructure", "railway", "cloud"],
            )
        )

    # Monitoring agent
    monitoring_tools = [t.name for t in registry.get_by_category(ToolCategory.MONITORING)]
    if monitoring_tools:
        agents.append(
            AgentDefinition(
                name="monitor-agent",
                description="Handles health checks, metrics, and alerting",
                domain=AgentDomain.MONITORING,
                tools=monitoring_tools,
                model_tier=ModelTier.FAST,
                tags=["observability", "health", "metrics"],
            )
        )

    # Integration agent
    integration_tools = [t.name for t in registry.get_by_category(ToolCategory.INTEGRATION)]
    if integration_tools:
        agents.append(
            AgentDefinition(
                name="integration-agent",
                description="Handles GitHub, n8n, and external API integrations",
                domain=AgentDomain.INTEGRATION,
                tools=integration_tools,
                model_tier=ModelTier.BALANCED,
                tags=["github", "n8n", "webhooks"],
            )
        )

    # Data agent
    data_tools = [t.name for t in registry.get_by_category(ToolCategory.DATA)]
    browser_tools = [t.name for t in registry.get_by_category(ToolCategory.BROWSER)]
    if data_tools or browser_tools:
        agents.append(
            AgentDefinition(
                name="data-agent",
                description="Handles data retrieval, scraping, and enrichment",
                domain=AgentDomain.DATA,
                tools=data_tools + browser_tools,
                model_tier=ModelTier.BALANCED,
                tags=["scraping", "enrichment", "search"],
            )
        )

    # Communication agent
    communication_tools = [t.name for t in registry.get_by_category(ToolCategory.COMMUNICATION)]
    workspace_tools = [t.name for t in registry.get_by_category(ToolCategory.WORKSPACE)]
    if communication_tools or workspace_tools:
        agents.append(
            AgentDefinition(
                name="communication-agent",
                description="Handles email, notifications, and messaging",
                domain=AgentDomain.COMMUNICATION,
                tools=communication_tools + workspace_tools,
                model_tier=ModelTier.BALANCED,
                tags=["email", "notifications", "messaging"],
            )
        )

    # General purpose agent
    all_tools = [t.name for t in registry.get_by_category(ToolCategory.GENERAL)]
    agents.append(
        AgentDefinition(
            name="general-agent",
            description="General purpose agent for miscellaneous tasks",
            domain=AgentDomain.GENERAL,
            tools=all_tools,
            model_tier=ModelTier.BALANCED,
            can_delegate=True,
            tags=["fallback", "general"],
        )
    )

    return agents
