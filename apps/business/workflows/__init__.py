"""n8n Workflow configurations for autonomous operations.

This package contains pre-built workflow configurations that can be
imported into n8n for various automation tasks.

Available Workflows:
- cost_alert_workflow: Budget monitoring and Telegram alerts
"""

from .cost_alert_workflow import (
    COST_ALERT_REGISTRY,
    create_alert_payload,
    create_cost_alert_workflow,
    get_severity_from_percentage,
    get_workflow_connections,
    get_workflow_nodes,
)

__all__ = [
    "create_cost_alert_workflow",
    "create_alert_payload",
    "get_severity_from_percentage",
    "get_workflow_nodes",
    "get_workflow_connections",
    "COST_ALERT_REGISTRY",
]
