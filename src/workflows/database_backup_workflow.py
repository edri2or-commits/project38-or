"""
n8n Workflow Configuration for Automated Database Backups.

Creates n8n workflow with:
- Daily schedule trigger (midnight UTC)
- Backup execution via FastAPI endpoint
- Success/failure notifications via Telegram
- Backup verification checks

Based on Week 3 requirements from implementation-roadmap.md.

Example:
    >>> from src.workflows.database_backup_workflow import create_backup_workflow
    >>> from src.n8n_client import N8nClient
    >>> client = N8nClient(api_key="...", base_url="...")
    >>> workflow = create_backup_workflow()
    >>> result = await client.import_workflow(workflow)
    >>> print(f"Workflow ID: {result['id']}")
"""

import json
from typing import Any

# Workflow configuration
WORKFLOW_NAME = "Database Backup - Daily Automated"
WORKFLOW_TAGS = ["backup", "database", "postgresql", "automated"]

# Schedule: Daily at midnight UTC
CRON_SCHEDULE = "0 0 * * *"  # Every day at 00:00 UTC


def create_backup_workflow(
    api_base_url: str = "https://or-infra.com",
    telegram_chat_id: str = "",
    backup_retention_days: int = 30,
) -> dict[str, Any]:
    """
    Generate n8n workflow JSON for automated database backups.

    Workflow Steps:
    1. Cron Trigger - Daily at midnight UTC
    2. HTTP Request - POST /api/backups/create
    3. Conditional - Check backup success
    4. Success Branch - Send Telegram notification (success)
    5. Failure Branch - Send Telegram alert (failure)

    Args:
        api_base_url: Base URL of FastAPI application (default: https://or-infra.com)
        telegram_chat_id: Telegram chat ID for notifications
        backup_retention_days: Backup retention period (default: 30)

    Returns:
        n8n workflow JSON configuration

    Example:
        >>> workflow = create_backup_workflow(
        ...     api_base_url="https://or-infra.com",
        ...     telegram_chat_id="123456789",
        ...     backup_retention_days=30
        ... )
        >>> print(workflow["name"])
        Database Backup - Daily Automated
    """
    workflow = {
        "name": WORKFLOW_NAME,
        "nodes": [
            # Node 1: Cron Trigger
            {
                "parameters": {
                    "rule": {
                        "interval": [
                            {
                                "field": "cronExpression",
                                "expression": CRON_SCHEDULE,
                            }
                        ]
                    }
                },
                "name": "Daily Backup Trigger",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [240, 300],
                "id": "node-1-trigger",
            },
            # Node 2: HTTP Request to create backup
            {
                "parameters": {
                    "url": f"{api_base_url}/api/backups/create",
                    "method": "POST",
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": json.dumps(
                        {
                            "retention_days": backup_retention_days,
                            "verify": True,
                        }
                    ),
                    "options": {
                        "timeout": 3600000,  # 1 hour timeout
                        "response": {
                            "response": {
                                "fullResponse": True,
                            }
                        },
                    },
                },
                "name": "Create Database Backup",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [460, 300],
                "id": "node-2-create-backup",
            },
            # Node 3: Check backup result
            {
                "parameters": {
                    "conditions": {
                        "options": {
                            "leftValue": "",
                            "caseSensitive": True,
                            "typeValidation": "strict",
                        },
                        "combinator": "and",
                        "conditions": [
                            {
                                "id": "condition-1",
                                "leftValue": "={{$json.body.success}}",
                                "rightValue": True,
                                "operator": {
                                    "type": "boolean",
                                    "operation": "equals",
                                },
                            },
                            {
                                "id": "condition-2",
                                "leftValue": "={{$json.statusCode}}",
                                "rightValue": 200,
                                "operator": {
                                    "type": "number",
                                    "operation": "equals",
                                },
                            },
                        ],
                    },
                    "options": {},
                },
                "name": "Backup Success?",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2.1,
                "position": [680, 300],
                "id": "node-3-check-success",
            },
            # Node 4: Success notification
            {
                "parameters": {
                    "chatId": telegram_chat_id,
                    "text": "=✅ **Database Backup Successful**\n\n"
                    + "📦 Backup ID: {{ $json.body.backup_id }}\n"
                    + "💾 Size: {{ $json.body.size_mb }} MB\n"
                    + "🔐 Checksum: {{ $json.body.checksum_sha256.slice(0, 16) }}...\n"
                    + "📍 Location: {{ $json.body.gcs_path }}\n"
                    + "⏱️ Duration: {{ $json.body.duration_seconds }} seconds\n"
                    + "📅 Retention: {{ $json.body.retention_days }} days\n"
                    + "✅ Verified: {{ $json.body.verified }}",
                    "additionalFields": {
                        "parse_mode": "Markdown",
                    },
                },
                "name": "Telegram Success Notification",
                "type": "n8n-nodes-base.telegram",
                "typeVersion": 1.2,
                "position": [900, 200],
                "id": "node-4-telegram-success",
                "credentials": {
                    "telegramApi": {
                        "id": "telegram-bot-credentials",
                        "name": "Telegram Bot",
                    }
                },
            },
            # Node 5: Failure alert
            {
                "parameters": {
                    "chatId": telegram_chat_id,
                    "text": "=🚨 **Database Backup FAILED**\n\n"
                    + "❌ Status Code: {{ $json.statusCode }}\n"
                    + "⚠️ Error: {{ $json.body.error || 'Unknown error' }}\n"
                    + "🕐 Time: {{ $now.format('YYYY-MM-DD HH:mm:ss') }} UTC\n\n"
                    + "**Action Required:**\n"
                    + "- Check database connectivity\n"
                    + "- Verify GCP Cloud Storage access\n"
                    + "- Review application logs\n"
                    + "- Manual backup may be needed",
                    "additionalFields": {
                        "parse_mode": "Markdown",
                    },
                },
                "name": "Telegram Failure Alert",
                "type": "n8n-nodes-base.telegram",
                "typeVersion": 1.2,
                "position": [900, 400],
                "id": "node-5-telegram-failure",
                "credentials": {
                    "telegramApi": {
                        "id": "telegram-bot-credentials",
                        "name": "Telegram Bot",
                    }
                },
            },
            # Node 6: Log backup metadata
            {
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "event_type",
                                "value": "database_backup_success",
                            },
                            {
                                "name": "backup_id",
                                "value": "={{ $json.body.backup_id }}",
                            },
                            {
                                "name": "size_mb",
                                "value": "={{ $json.body.size_mb }}",
                            },
                            {
                                "name": "gcs_path",
                                "value": "={{ $json.body.gcs_path }}",
                            },
                        ]
                    },
                    "options": {},
                },
                "name": "Log Metadata",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [900, 100],
                "id": "node-6-log-metadata",
            },
        ],
        "connections": {
            "Daily Backup Trigger": {
                "main": [[{"node": "Create Database Backup", "type": "main", "index": 0}]]
            },
            "Create Database Backup": {
                "main": [[{"node": "Backup Success?", "type": "main", "index": 0}]]
            },
            "Backup Success?": {
                "main": [
                    # True branch (success)
                    [
                        {"node": "Telegram Success Notification", "type": "main", "index": 0},
                        {"node": "Log Metadata", "type": "main", "index": 0},
                    ],
                    # False branch (failure)
                    [{"node": "Telegram Failure Alert", "type": "main", "index": 0}],
                ]
            },
        },
        "active": True,
        "settings": {
            "executionOrder": "v1",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
        },
        "tags": WORKFLOW_TAGS,
        "meta": {
            "templateCredsSetupCompleted": True,
            "instanceId": "project38-or",
        },
    }

    return workflow


def create_backup_verification_workflow(
    api_base_url: str = "https://or-infra.com",
    telegram_chat_id: str = "",
) -> dict[str, Any]:
    """
    Generate n8n workflow JSON for backup verification.

    Runs weekly to verify backup integrity:
    1. List recent backups
    2. Download random backup
    3. Verify checksum
    4. Report results

    Args:
        api_base_url: Base URL of FastAPI application
        telegram_chat_id: Telegram chat ID for notifications

    Returns:
        n8n workflow JSON configuration

    Example:
        >>> workflow = create_backup_verification_workflow()
        >>> print(workflow["name"])
        Database Backup - Weekly Verification
    """
    workflow = {
        "name": "Database Backup - Weekly Verification",
        "nodes": [
            # Node 1: Weekly trigger (Sunday midnight)
            {
                "parameters": {
                    "rule": {
                        "interval": [
                            {
                                "field": "cronExpression",
                                "expression": "0 0 * * 0",  # Every Sunday at 00:00 UTC
                            }
                        ]
                    }
                },
                "name": "Weekly Verification Trigger",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [240, 300],
                "id": "node-1-weekly-trigger",
            },
            # Node 2: List backups
            {
                "parameters": {
                    "url": f"{api_base_url}/api/backups?limit=10",
                    "method": "GET",
                    "options": {
                        "response": {
                            "response": {
                                "fullResponse": True,
                            }
                        },
                    },
                },
                "name": "List Recent Backups",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [460, 300],
                "id": "node-2-list-backups",
            },
            # Node 3: Select random backup
            {
                "parameters": {
                    "jsCode": (  # noqa: S608
                        "// Select random backup from list\n"
                        "const backups = $input.item.json.body.backups;\n"
                        "if (!backups || backups.length === 0) {\n"
                        '  throw new Error("No backups found");\n'
                        "}\n"
                        "const randomIndex = Math.floor(Math.random() * backups.length);\n"
                        "const selectedBackup = backups[randomIndex];\n"
                        "return { backup_id: selectedBackup.backup_id, "
                        "gcs_path: selectedBackup.gcs_path, "
                        "checksum_sha256: selectedBackup.checksum_sha256 };"
                    ),
                },
                "name": "Select Random Backup",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2.0,
                "position": [680, 300],
                "id": "node-3-select-random",
            },
            # Node 4: Verify backup
            {
                "parameters": {
                    "url": f"{api_base_url}/api/backups/verify",
                    "method": "POST",
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": '={{ {"backup_id": $json.backup_id} }}',
                    "options": {
                        "timeout": 300000,  # 5 minutes
                        "response": {
                            "response": {
                                "fullResponse": True,
                            }
                        },
                    },
                },
                "name": "Verify Backup Integrity",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [900, 300],
                "id": "node-4-verify-backup",
            },
            # Node 5: Verification report
            {
                "parameters": {
                    "chatId": telegram_chat_id,
                    "text": "=🔍 **Backup Verification Report**\n\n"
                    + "📦 Backup ID: {{ $json.body.backup_id }}\n"
                    + "✅ Verified: {{ $json.body.verified }}\n"
                    + "🔐 Checksum Match: {{ $json.body.checksum_valid }}\n"
                    + "📍 Location: {{ $json.body.gcs_path }}\n"
                    + "🕐 Verified At: {{ $now.format('YYYY-MM-DD HH:mm:ss') }} UTC",
                    "additionalFields": {
                        "parse_mode": "Markdown",
                    },
                },
                "name": "Telegram Verification Report",
                "type": "n8n-nodes-base.telegram",
                "typeVersion": 1.2,
                "position": [1120, 300],
                "id": "node-5-telegram-report",
                "credentials": {
                    "telegramApi": {
                        "id": "telegram-bot-credentials",
                        "name": "Telegram Bot",
                    }
                },
            },
        ],
        "connections": {
            "Weekly Verification Trigger": {
                "main": [[{"node": "List Recent Backups", "type": "main", "index": 0}]]
            },
            "List Recent Backups": {
                "main": [[{"node": "Select Random Backup", "type": "main", "index": 0}]]
            },
            "Select Random Backup": {
                "main": [[{"node": "Verify Backup Integrity", "type": "main", "index": 0}]]
            },
            "Verify Backup Integrity": {
                "main": [[{"node": "Telegram Verification Report", "type": "main", "index": 0}]]
            },
        },
        "active": True,
        "settings": {
            "executionOrder": "v1",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
        "tags": ["backup", "verification", "integrity-check"],
    }

    return workflow


# Helper function to export workflows to files
def export_workflows_to_file(
    daily_backup_path: str = "n8n-workflows/daily-backup.json",
    weekly_verification_path: str = "n8n-workflows/weekly-verification.json",
    api_base_url: str = "https://or-infra.com",
    telegram_chat_id: str = "",
) -> None:
    """
    Export workflow configurations to JSON files.

    Args:
        daily_backup_path: Path for daily backup workflow JSON
        weekly_verification_path: Path for weekly verification workflow JSON
        api_base_url: Base URL of FastAPI application
        telegram_chat_id: Telegram chat ID for notifications

    Example:
        >>> export_workflows_to_file(
        ...     telegram_chat_id="123456789"
        ... )
        Exported n8n-workflows/daily-backup.json
        Exported n8n-workflows/weekly-verification.json
    """
    import pathlib

    # Create directory if needed
    pathlib.Path(daily_backup_path).parent.mkdir(parents=True, exist_ok=True)

    # Generate workflows
    daily_workflow = create_backup_workflow(
        api_base_url=api_base_url,
        telegram_chat_id=telegram_chat_id,
    )

    weekly_workflow = create_backup_verification_workflow(
        api_base_url=api_base_url,
        telegram_chat_id=telegram_chat_id,
    )

    # Write to files
    with open(daily_backup_path, "w") as f:
        json.dump(daily_workflow, f, indent=2)
    print(f"Exported {daily_backup_path}")

    with open(weekly_verification_path, "w") as f:
        json.dump(weekly_workflow, f, indent=2)
    print(f"Exported {weekly_verification_path}")


if __name__ == "__main__":
    # Export workflows when run directly
    import sys

    telegram_chat_id = sys.argv[1] if len(sys.argv) > 1 else ""
    export_workflows_to_file(telegram_chat_id=telegram_chat_id)
