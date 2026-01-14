"""
MCP Gateway Tools.

This package provides tool implementations for:
- Railway: Deployment, rollback, status monitoring
- n8n: Workflow triggering and management
- Monitoring: Health checks and metrics
"""

from .monitoring import (
    check_health,
    get_metrics,
)
from .n8n import (
    get_workflow_status,
    list_workflows,
    trigger_workflow,
)
from .railway import (
    execute_rollback,
    get_deployment_status,
    get_recent_deployments,
    trigger_deployment,
)

__all__ = [
    # Railway
    "trigger_deployment",
    "get_deployment_status",
    "execute_rollback",
    "get_recent_deployments",
    # n8n
    "trigger_workflow",
    "list_workflows",
    "get_workflow_status",
    # Monitoring
    "check_health",
    "get_metrics",
]
