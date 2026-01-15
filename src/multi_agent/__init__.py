"""Multi-Agent Orchestration System for Autonomous Operations.

This module provides a framework for specialized agents that work together
to manage different aspects of the autonomous system:

- DeployAgent: Railway deployments, rollbacks, and scaling
- MonitoringAgent: Observability, metrics, and alerting
- IntegrationAgent: GitHub PRs/issues and n8n workflows
- AgentOrchestrator: Coordinates all agents and routes tasks

Example:
    >>> from src.multi_agent import AgentOrchestrator, AgentTask, AgentDomain
    >>> from src.multi_agent.deploy_agent import DeployAgent
    >>>
    >>> orchestrator = AgentOrchestrator()
    >>> orchestrator.register_agent(DeployAgent(railway_client=railway_client))
    >>> task = AgentTask(
    ...     task_type="deploy",
    ...     domain=AgentDomain.DEPLOY,
    ...     parameters={"project_id": "..."}
    ... )
    >>> result = await orchestrator.submit_and_wait(task)
"""

from src.multi_agent.base import (
    AgentCapability,
    AgentDomain,
    AgentMessage,
    AgentResult,
    AgentTask,
    SpecializedAgent,
    TaskPriority,
    TaskStatus,
)
from src.multi_agent.deploy_agent import DeployAgent, DeploymentConfig
from src.multi_agent.integration_agent import IntegrationAgent, IntegrationConfig
from src.multi_agent.monitoring_agent import MonitoringAgent, MonitoringConfig
from src.multi_agent.orchestrator import (
    AgentOrchestrator,
    OrchestratorConfig,
    create_orchestrator,
)

__all__ = [
    # Base classes
    "AgentCapability",
    "AgentDomain",
    "AgentMessage",
    "AgentResult",
    "AgentTask",
    "SpecializedAgent",
    "TaskPriority",
    "TaskStatus",
    # Specialized agents
    "DeployAgent",
    "DeploymentConfig",
    "MonitoringAgent",
    "MonitoringConfig",
    "IntegrationAgent",
    "IntegrationConfig",
    # Orchestrator
    "AgentOrchestrator",
    "OrchestratorConfig",
    "create_orchestrator",
]
