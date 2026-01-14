"""Cost Alert n8n Workflow Configuration.

Defines the n8n workflow for sending cost alerts when budget thresholds
are exceeded. Integrates with Telegram for notifications.

This module provides:
- n8n workflow node definitions
- Workflow connection graph
- Telegram message templates
- Budget threshold configuration

Example:
    >>> from src.workflows.cost_alert_workflow import create_cost_alert_workflow
    >>> from src.n8n_client import N8nClient
    >>>
    >>> client = N8nClient(base_url="...", api_key="...")
    >>> workflow = await client.create_workflow(**create_cost_alert_workflow())
"""

from typing import Any

# =============================================================================
# WORKFLOW CONFIGURATION
# =============================================================================


def create_cost_alert_workflow() -> dict[str, Any]:
    """Create n8n workflow definition for cost alerts.

    Returns:
        Dictionary with workflow configuration:
        - name: Workflow name
        - nodes: List of node definitions
        - connections: Connection graph
        - active: Whether workflow is active
        - settings: Workflow settings

    Example:
        >>> workflow_config = create_cost_alert_workflow()
        >>> client.create_workflow(**workflow_config)
    """
    return {
        "name": "Cost Alert - Railway Budget Monitor",
        "nodes": get_workflow_nodes(),
        "connections": get_workflow_connections(),
        "active": True,
        "settings": {
            "saveExecutionProgress": True,
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
            "timezone": "UTC",
        },
    }


def get_workflow_nodes() -> list[dict[str, Any]]:
    """Get node definitions for cost alert workflow.

    Node Flow:
    1. Webhook (receives alert from Cost API)
    2. Switch (route by alert severity)
    3. Format Message (prepare Telegram message)
    4. Telegram (send notification)

    Returns:
        List of n8n node definitions
    """
    return [
        # Node 1: Webhook Trigger
        {
            "id": "webhook_trigger",
            "name": "Cost Alert Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [250, 300],
            "parameters": {
                "path": "cost-alert",
                "httpMethod": "POST",
                "responseMode": "onReceived",
                "responseData": "allEntries",
            },
            "webhookId": "cost-alert-webhook",
        },
        # Node 2: Switch by Severity
        {
            "id": "severity_switch",
            "name": "Check Severity",
            "type": "n8n-nodes-base.switch",
            "typeVersion": 2,
            "position": [450, 300],
            "parameters": {
                "dataType": "string",
                "value1": "={{ $json.severity }}",
                "rules": {
                    "rules": [
                        {
                            "value2": "critical",
                            "operation": "equals",
                            "output": 0,
                        },
                        {
                            "value2": "warning",
                            "operation": "equals",
                            "output": 1,
                        },
                        {
                            "value2": "info",
                            "operation": "equals",
                            "output": 2,
                        },
                    ],
                },
                "fallbackOutput": 2,
            },
        },
        # Node 3a: Format Critical Alert
        {
            "id": "format_critical",
            "name": "Format Critical Alert",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [650, 200],
            "parameters": {
                "assignments": {
                    "assignments": [
                        {
                            "id": "message",
                            "name": "message",
                            "type": "string",
                            "value": (
                                "🚨 *CRITICAL: Budget Exceeded*\n\n"
                                "📊 *Cost Report*\n"
                                "• Budget: ${{ $json.budget }}\n"
                                "• Projected: ${{ $json.projected_cost }}\n"
                                "• Usage: {{ $json.percentage_used }}%\n\n"
                                "⚠️ *Action Required*\n"
                                "Review Railway usage immediately.\n\n"
                                "🔗 [View Dashboard](https://railway.app/dashboard)"
                            ),
                        },
                    ],
                },
            },
        },
        # Node 3b: Format Warning Alert
        {
            "id": "format_warning",
            "name": "Format Warning Alert",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [650, 300],
            "parameters": {
                "assignments": {
                    "assignments": [
                        {
                            "id": "message",
                            "name": "message",
                            "type": "string",
                            "value": (
                                "⚠️ *WARNING: Approaching Budget Limit*\n\n"
                                "📊 *Cost Report*\n"
                                "• Budget: ${{ $json.budget }}\n"
                                "• Projected: ${{ $json.projected_cost }}\n"
                                "• Usage: {{ $json.percentage_used }}%\n\n"
                                "💡 *Recommendations*\n"
                                "{{ $json.recommendations }}\n\n"
                                "🔗 [View Details](https://or-infra.com/costs/report)"
                            ),
                        },
                    ],
                },
            },
        },
        # Node 3c: Format Info Alert
        {
            "id": "format_info",
            "name": "Format Info Alert",
            "type": "n8n-nodes-base.set",
            "typeVersion": 2,
            "position": [650, 400],
            "parameters": {
                "assignments": {
                    "assignments": [
                        {
                            "id": "message",
                            "name": "message",
                            "type": "string",
                            "value": (
                                "ℹ️ *Cost Report - Weekly Summary*\n\n"
                                "📊 *Current Status*\n"
                                "• Budget: ${{ $json.budget }}\n"
                                "• Projected: ${{ $json.projected_cost }}\n"
                                "• Usage: {{ $json.percentage_used }}%\n\n"
                                "✅ Status: {{ $json.status }}"
                            ),
                        },
                    ],
                },
            },
        },
        # Node 4: Merge Results
        {
            "id": "merge_results",
            "name": "Merge Results",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 2,
            "position": [850, 300],
            "parameters": {
                "mode": "multiplex",
            },
        },
        # Node 5: Send Telegram
        {
            "id": "send_telegram",
            "name": "Send Telegram Notification",
            "type": "n8n-nodes-base.telegram",
            "typeVersion": 1,
            "position": [1050, 300],
            "parameters": {
                "chatId": "={{ $env.TELEGRAM_CHAT_ID }}",
                "text": "={{ $json.message }}",
                "additionalFields": {
                    "parse_mode": "Markdown",
                    "disable_notification": False,
                },
            },
            "credentials": {
                "telegramApi": {
                    "id": "telegram_bot",
                    "name": "Telegram Bot",
                },
            },
        },
    ]


def get_workflow_connections() -> dict[str, Any]:
    """Get connection graph for cost alert workflow.

    Defines how nodes are connected:
    Webhook → Switch → Format (by severity) → Merge → Telegram

    Returns:
        n8n connections dictionary
    """
    return {
        "Cost Alert Webhook": {
            "main": [[{"node": "Check Severity", "type": "main", "index": 0}]],
        },
        "Check Severity": {
            "main": [
                [{"node": "Format Critical Alert", "type": "main", "index": 0}],
                [{"node": "Format Warning Alert", "type": "main", "index": 0}],
                [{"node": "Format Info Alert", "type": "main", "index": 0}],
            ],
        },
        "Format Critical Alert": {
            "main": [[{"node": "Merge Results", "type": "main", "index": 0}]],
        },
        "Format Warning Alert": {
            "main": [[{"node": "Merge Results", "type": "main", "index": 1}]],
        },
        "Format Info Alert": {
            "main": [[{"node": "Merge Results", "type": "main", "index": 2}]],
        },
        "Merge Results": {
            "main": [
                [{"node": "Send Telegram Notification", "type": "main", "index": 0}]
            ],
        },
    }


# =============================================================================
# WEBHOOK PAYLOAD TEMPLATES
# =============================================================================


def create_alert_payload(
    severity: str,
    budget: float,
    projected_cost: float,
    percentage_used: float,
    status: str,
    recommendations: str = "",
) -> dict[str, Any]:
    """Create webhook payload for cost alert.

    Args:
        severity: Alert severity (critical, warning, info)
        budget: Monthly budget in USD
        projected_cost: Projected monthly cost in USD
        percentage_used: Percentage of budget used
        status: Current status (ok, warning, alert)
        recommendations: Optional recommendations text

    Returns:
        Dictionary payload for webhook

    Example:
        >>> payload = create_alert_payload(
        ...     severity="warning",
        ...     budget=50.0,
        ...     projected_cost=42.0,
        ...     percentage_used=84.0,
        ...     status="warning",
        ...     recommendations="Consider reducing vCPU allocation"
        ... )
        >>> await httpx.post(webhook_url, json=payload)
    """
    return {
        "severity": severity,
        "budget": round(budget, 2),
        "projected_cost": round(projected_cost, 2),
        "percentage_used": round(percentage_used, 1),
        "status": status,
        "recommendations": recommendations,
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").UTC
        ).isoformat(),
    }


def get_severity_from_percentage(percentage: float) -> str:
    """Determine alert severity from budget percentage.

    Args:
        percentage: Percentage of budget used (0-100+)

    Returns:
        Severity level: "info", "warning", or "critical"
    """
    if percentage >= 100:
        return "critical"
    elif percentage >= 80:
        return "warning"
    else:
        return "info"


# =============================================================================
# WORKFLOW REGISTRY ENTRY
# =============================================================================


COST_ALERT_REGISTRY = {
    "cost-alert": {
        "path": "/webhook/cost-alert",
        "method": "POST",
        "description": "Receive cost alerts and send Telegram notifications",
    },
    "cost-weekly-report": {
        "path": "/webhook/cost-weekly-report",
        "method": "POST",
        "description": "Weekly cost summary report to Telegram",
    },
}
