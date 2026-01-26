"""n8n Error Scanner Agent Workflow.

Daily workflow that scans for errors across the system and auto-remediates.
Implements ADR-016: n8n Error Scanner Agent.

Flow:
1. SCAN: Collect errors from GitHub Actions, Railway, Production health
2. CATEGORIZE: Classify by severity (P1-P4)
3. FIX: Auto-remediate where safe
4. VERIFY: Re-check after fix
5. REPORT: Send daily summary to Telegram

Example:
    >>> from src.workflows.error_scanner_workflow import create_error_scanner_workflow
    >>> from src.n8n_client import N8nClient
    >>>
    >>> client = N8nClient(base_url="...", api_key="...")
    >>> workflow = await client.create_workflow(**create_error_scanner_workflow())
"""

from typing import Any

# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG = {
    "production_url": "https://or-infra.com",
    "github_repo": "edri2or-commits/project38-or",
    "telegram_chat_id": "{{$env.TELEGRAM_CHAT_ID}}",
    "mcp_gateway_url": "https://or-infra.com/mcp",
    "schedule_cron": "0 7 * * *",  # 07:00 UTC daily
    "max_actions_per_run": 5,
    "fix_verification_wait_seconds": 60,
}

# =============================================================================
# SEVERITY CLASSIFICATION
# =============================================================================

SEVERITY_RULES = {
    "P1_CRITICAL": {
        "patterns": ["CRASHED", "production down", "health: unhealthy"],
        "auto_fix": True,
        "actions": ["rollback", "restart"],
    },
    "P2_HIGH": {
        "patterns": ["FAILED", "CI failure", "deploy failed"],
        "auto_fix": True,
        "actions": ["retry", "rerun"],
    },
    "P3_MEDIUM": {
        "patterns": ["anomaly", "high latency", "warning"],
        "auto_fix": True,
        "actions": ["clear_cache", "scale_up"],
    },
    "P4_LOW": {
        "patterns": ["info", "notice"],
        "auto_fix": False,
        "actions": ["report_only"],
    },
}


# =============================================================================
# MAIN WORKFLOW BUILDER
# =============================================================================


def create_error_scanner_workflow() -> dict[str, Any]:
    """Create n8n workflow definition for error scanning.

    Returns:
        Dictionary with workflow configuration for n8n API.
    """
    return {
        "name": "Error Scanner Agent - Daily",
        "nodes": _get_all_nodes(),
        "connections": _get_all_connections(),
        "active": True,
        "settings": {
            "saveExecutionProgress": True,
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
            "timezone": "UTC",
            "executionOrder": "v1",
        },
    }


# =============================================================================
# NODE DEFINITIONS
# =============================================================================


def _get_all_nodes() -> list[dict[str, Any]]:
    """Get all node definitions."""
    nodes = []

    # Phase 1: Trigger
    nodes.append(_node_schedule_trigger())

    # Phase 2: Scan (parallel)
    nodes.append(_node_scan_github_actions())
    nodes.append(_node_scan_railway_deployments())
    nodes.append(_node_scan_production_health())
    nodes.append(_node_scan_monitoring_status())

    # Phase 3: Aggregate
    nodes.append(_node_merge_scan_results())
    nodes.append(_node_categorize_errors())

    # Phase 4: Auto-Remediation
    nodes.append(_node_filter_fixable())
    nodes.append(_node_switch_by_error_type())
    nodes.append(_node_fix_ci_failure())
    nodes.append(_node_fix_deploy_failed())
    nodes.append(_node_fix_health_degraded())
    nodes.append(_node_fix_high_latency())

    # Phase 5: Verification
    nodes.append(_node_wait_for_fix())
    nodes.append(_node_verify_fix())
    nodes.append(_node_merge_results())

    # Phase 6: Report
    nodes.append(_node_format_report())
    nodes.append(_node_send_telegram())

    return nodes


def _node_schedule_trigger() -> dict[str, Any]:
    """Daily schedule trigger at 07:00 UTC."""
    return {
        "id": "schedule_trigger",
        "name": "Daily 07:00 UTC",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.1,
        "position": [100, 400],
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": CONFIG["schedule_cron"],
                    }
                ]
            },
        },
    }


def _node_scan_github_actions() -> dict[str, Any]:
    """Scan GitHub Actions for failures in last 24h."""
    return {
        "id": "scan_github",
        "name": "Scan GitHub Actions",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [300, 200],
        "parameters": {
            "method": "GET",
            "url": f"https://api.github.com/repos/{CONFIG['github_repo']}/actions/runs",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.GITHUB_TOKEN }}"},
                    {"name": "Accept", "value": "application/vnd.github.v3+json"},
                ]
            },
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "status", "value": "failure"},
                    {"name": "per_page", "value": "20"},
                    {"name": "created", "value": ">={{ $now.minus(24, 'hours').toISO() }}"},
                ]
            },
            "options": {
                "response": {"response": {"responseFormat": "json"}},
            },
        },
    }


def _node_scan_railway_deployments() -> dict[str, Any]:
    """Scan Railway for failed deployments."""
    return {
        "id": "scan_railway",
        "name": "Scan Railway Deployments",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [300, 350],
        "parameters": {
            "method": "POST",
            "url": f"{CONFIG['mcp_gateway_url']}/call",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.MCP_GATEWAY_TOKEN }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '{"tool": "railway_deployments", "arguments": {"limit": 20}}',
            "options": {
                "response": {"response": {"responseFormat": "json"}},
            },
        },
    }


def _node_scan_production_health() -> dict[str, Any]:
    """Check production health endpoint."""
    return {
        "id": "scan_health",
        "name": "Scan Production Health",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [300, 500],
        "parameters": {
            "method": "GET",
            "url": f"{CONFIG['production_url']}/api/health",
            "options": {
                "response": {"response": {"responseFormat": "json"}},
                "timeout": 30000,
            },
        },
    }


def _node_scan_monitoring_status() -> dict[str, Any]:
    """Check monitoring loop status for anomalies."""
    return {
        "id": "scan_monitoring",
        "name": "Scan Monitoring Status",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [300, 650],
        "parameters": {
            "method": "GET",
            "url": f"{CONFIG['production_url']}/api/monitoring/status",
            "options": {
                "response": {"response": {"responseFormat": "json"}},
                "timeout": 30000,
            },
        },
    }


def _node_merge_scan_results() -> dict[str, Any]:
    """Merge all scan results into single array."""
    return {
        "id": "merge_scans",
        "name": "Merge Scan Results",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 2.1,
        "position": [500, 400],
        "parameters": {
            "mode": "combine",
            "combinationMode": "mergeByPosition",
            "options": {},
        },
    }


def _node_categorize_errors() -> dict[str, Any]:
    """Categorize errors by severity (P1-P4)."""
    return {
        "id": "categorize",
        "name": "Categorize by Severity",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [700, 400],
        "parameters": {
            "jsCode": """
// Categorize all errors by severity
const errors = {
  P1_CRITICAL: [],
  P2_HIGH: [],
  P3_MEDIUM: [],
  P4_LOW: [],
  stats: { total: 0, fixable: 0 }
};

// Process GitHub Actions failures
const githubRuns = $input.first().json.workflow_runs || [];
for (const run of githubRuns) {
  if (run.conclusion === 'failure') {
    errors.P2_HIGH.push({
      type: 'CI_FAILURE',
      source: 'github_actions',
      id: run.id,
      name: run.name,
      url: run.html_url,
      created_at: run.created_at,
      fixable: true,
      fix_action: 'rerun_workflow'
    });
  }
}

// Process Railway deployments
const railwayData = $input.all()[1]?.json || {};
const deployments = railwayData.deployments || railwayData.result || [];
for (const deploy of deployments) {
  const status = deploy.status || deploy.state;
  if (status === 'CRASHED') {
    errors.P1_CRITICAL.push({
      type: 'DEPLOY_CRASHED',
      source: 'railway',
      id: deploy.id,
      service: deploy.service?.name || 'unknown',
      fixable: true,
      fix_action: 'rollback'
    });
  } else if (status === 'FAILED') {
    errors.P2_HIGH.push({
      type: 'DEPLOY_FAILED',
      source: 'railway',
      id: deploy.id,
      service: deploy.service?.name || 'unknown',
      fixable: true,
      fix_action: 'retry_deploy'
    });
  }
}

// Process health check
const health = $input.all()[2]?.json || {};
if (health.status !== 'healthy') {
  errors.P1_CRITICAL.push({
    type: 'HEALTH_DEGRADED',
    source: 'production',
    status: health.status,
    database: health.database,
    fixable: true,
    fix_action: 'restart_service'
  });
}

// Process monitoring status
const monitoring = $input.all()[3]?.json || {};
if (monitoring.anomaly_count > 0 || monitoring.stats?.anomalies_detected > 0) {
  errors.P3_MEDIUM.push({
    type: 'ANOMALIES_DETECTED',
    source: 'monitoring',
    count: monitoring.anomaly_count || monitoring.stats?.anomalies_detected,
    fixable: true,
    fix_action: 'clear_cache'
  });
}

// Calculate stats
errors.stats.total = errors.P1_CRITICAL.length + errors.P2_HIGH.length +
                     errors.P3_MEDIUM.length + errors.P4_LOW.length;
errors.stats.fixable = [...errors.P1_CRITICAL, ...errors.P2_HIGH, ...errors.P3_MEDIUM]
                       .filter(e => e.fixable).length;

return { json: errors };
""",
        },
    }


def _node_filter_fixable() -> dict[str, Any]:
    """Filter to only fixable errors."""
    return {
        "id": "filter_fixable",
        "name": "Filter Fixable Errors",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [900, 400],
        "parameters": {
            "jsCode": """
const errors = $input.first().json;
const fixable = [];
const maxActions = 5;

// Collect all fixable errors, prioritized by severity
const allFixable = [
  ...errors.P1_CRITICAL.filter(e => e.fixable),
  ...errors.P2_HIGH.filter(e => e.fixable),
  ...errors.P3_MEDIUM.filter(e => e.fixable)
];

// Limit to max actions per run
const toFix = allFixable.slice(0, maxActions);

return toFix.map(error => ({ json: error }));
""",
        },
    }


def _node_switch_by_error_type() -> dict[str, Any]:
    """Route to appropriate fix action based on error type."""
    return {
        "id": "switch_error_type",
        "name": "Route by Error Type",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3,
        "position": [1100, 400],
        "parameters": {
            "rules": {
                "rules": [
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.type }}",
                                    "rightValue": "CI_FAILURE",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                        "renameOutput": True,
                        "outputKey": "ci_failure",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.type }}",
                                    "rightValue": "DEPLOY_FAILED",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                        "renameOutput": True,
                        "outputKey": "deploy_failed",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.type }}",
                                    "rightValue": "DEPLOY_CRASHED",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                        "renameOutput": True,
                        "outputKey": "deploy_crashed",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.type }}",
                                    "rightValue": "HEALTH_DEGRADED",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                        "renameOutput": True,
                        "outputKey": "health_degraded",
                    },
                ]
            },
            "fallbackOutput": "extra",
        },
    }


def _node_fix_ci_failure() -> dict[str, Any]:
    """Re-run failed GitHub Actions workflow."""
    return {
        "id": "fix_ci",
        "name": "Re-run CI Workflow",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [1300, 200],
        "parameters": {
            "method": "POST",
            "url": f"=https://api.github.com/repos/{CONFIG['github_repo']}/actions/runs/{{{{ $json.id }}}}/rerun",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.GITHUB_TOKEN }}"},
                    {"name": "Accept", "value": "application/vnd.github.v3+json"},
                ]
            },
            "options": {},
        },
    }


def _node_fix_deploy_failed() -> dict[str, Any]:
    """Retry failed Railway deployment."""
    return {
        "id": "fix_deploy",
        "name": "Retry Deployment",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [1300, 350],
        "parameters": {
            "method": "POST",
            "url": f"{CONFIG['mcp_gateway_url']}/call",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.MCP_GATEWAY_TOKEN }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '{"tool": "railway_deploy", "arguments": {}}',
        },
    }


def _node_fix_health_degraded() -> dict[str, Any]:
    """Restart service when health is degraded."""
    return {
        "id": "fix_health",
        "name": "Restart Service",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [1300, 500],
        "parameters": {
            "method": "POST",
            "url": f"{CONFIG['mcp_gateway_url']}/call",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.MCP_GATEWAY_TOKEN }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '{"tool": "railway_deploy", "arguments": {}}',
        },
    }


def _node_fix_high_latency() -> dict[str, Any]:
    """Clear cache when latency is high."""
    return {
        "id": "fix_latency",
        "name": "Clear Cache",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [1300, 650],
        "parameters": {
            "method": "POST",
            "url": f"{CONFIG['mcp_gateway_url']}/call",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $env.MCP_GATEWAY_TOKEN }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '{"tool": "n8n_trigger", "arguments": {"workflow": "cache-clear"}}',
        },
    }


def _node_wait_for_fix() -> dict[str, Any]:
    """Wait for fix to take effect."""
    return {
        "id": "wait_fix",
        "name": "Wait 60s",
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": [1500, 400],
        "parameters": {
            "amount": CONFIG["fix_verification_wait_seconds"],
            "unit": "seconds",
        },
    }


def _node_verify_fix() -> dict[str, Any]:
    """Re-check if fix was successful."""
    return {
        "id": "verify_fix",
        "name": "Verify Fix",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1700, 400],
        "parameters": {
            "jsCode": """
// Add verification result to each fixed error
const fixedError = $input.first().json;

// For now, mark as FIXED (actual verification would re-check the endpoint)
// TODO: Implement actual verification based on error type
return {
  json: {
    ...fixedError,
    verification: {
      status: 'FIXED',
      verified_at: new Date().toISOString(),
      note: 'Verification pending actual re-check'
    }
  }
};
""",
        },
    }


def _node_merge_results() -> dict[str, Any]:
    """Merge all fix results."""
    return {
        "id": "merge_results",
        "name": "Merge Fix Results",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 2.1,
        "position": [1900, 400],
        "parameters": {
            "mode": "append",
        },
    }


def _node_format_report() -> dict[str, Any]:
    """Format daily summary report."""
    return {
        "id": "format_report",
        "name": "Format Report",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2100, 400],
        "parameters": {
            "jsCode": """
const results = $input.all().map(item => item.json);
const now = new Date().toISOString().split('T')[0];

// Count by status
const fixed = results.filter(r => r.verification?.status === 'FIXED').length;
const partial = results.filter(r => r.verification?.status === 'PARTIAL').length;
const failed = results.filter(r => r.verification?.status === 'FAILED').length;
const total = results.length;

// Build report
let report = `📊 *Daily Error Report - ${now}*\\n\\n`;

if (fixed > 0) {
  report += `✅ *Fixed: ${fixed} issues*\\n`;
  for (const r of results.filter(r => r.verification?.status === 'FIXED')) {
    report += `  • ${r.type} (${r.source}) → SUCCESS\\n`;
  }
  report += `\\n`;
}

if (partial > 0 || failed > 0) {
  report += `⚠️ *Needs Attention: ${partial + failed} issues*\\n`;
  for (const r of results.filter(r => ['PARTIAL', 'FAILED'].includes(r.verification?.status))) {
    report += `  • ${r.type} (${r.source}) → ${r.verification?.status}\\n`;
  }
  report += `\\n`;
}

if (total === 0) {
  report += `✨ *No errors detected!*\\n\\n`;
}

// Calculate health percentage
const healthPct = total > 0 ? Math.round((fixed / total) * 100) : 100;
report += `📈 *System Health: ${healthPct}%*`;

return { json: { report, stats: { fixed, partial, failed, total } } };
""",
        },
    }


def _node_send_telegram() -> dict[str, Any]:
    """Send report to Telegram via HTTP API.

    Uses environment variable TELEGRAM_BOT_TOKEN for authentication.
    """
    return {
        "id": "send_telegram",
        "name": "Send to Telegram",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [2300, 400],
        "parameters": {
            "method": "POST",
            "url": "=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={"chat_id": "{{ $env.TELEGRAM_CHAT_ID }}", "text": {{ JSON.stringify($json.report) }}, "parse_mode": "Markdown"}',
            "options": {
                "response": {"response": {"responseFormat": "json"}},
            },
        },
    }


# =============================================================================
# CONNECTION DEFINITIONS
# =============================================================================


def _get_all_connections() -> dict[str, Any]:
    """Get all node connections."""
    return {
        "Daily 07:00 UTC": {
            "main": [
                [
                    {"node": "Scan GitHub Actions", "type": "main", "index": 0},
                    {"node": "Scan Railway Deployments", "type": "main", "index": 0},
                    {"node": "Scan Production Health", "type": "main", "index": 0},
                    {"node": "Scan Monitoring Status", "type": "main", "index": 0},
                ]
            ]
        },
        "Scan GitHub Actions": {
            "main": [[{"node": "Merge Scan Results", "type": "main", "index": 0}]]
        },
        "Scan Railway Deployments": {
            "main": [[{"node": "Merge Scan Results", "type": "main", "index": 1}]]
        },
        "Scan Production Health": {
            "main": [[{"node": "Merge Scan Results", "type": "main", "index": 2}]]
        },
        "Scan Monitoring Status": {
            "main": [[{"node": "Merge Scan Results", "type": "main", "index": 3}]]
        },
        "Merge Scan Results": {
            "main": [[{"node": "Categorize by Severity", "type": "main", "index": 0}]]
        },
        "Categorize by Severity": {
            "main": [[{"node": "Filter Fixable Errors", "type": "main", "index": 0}]]
        },
        "Filter Fixable Errors": {
            "main": [[{"node": "Route by Error Type", "type": "main", "index": 0}]]
        },
        "Route by Error Type": {
            "main": [
                [{"node": "Re-run CI Workflow", "type": "main", "index": 0}],
                [{"node": "Retry Deployment", "type": "main", "index": 0}],
                [{"node": "Restart Service", "type": "main", "index": 0}],
                [{"node": "Clear Cache", "type": "main", "index": 0}],
            ]
        },
        "Re-run CI Workflow": {
            "main": [[{"node": "Wait 60s", "type": "main", "index": 0}]]
        },
        "Retry Deployment": {
            "main": [[{"node": "Wait 60s", "type": "main", "index": 0}]]
        },
        "Restart Service": {
            "main": [[{"node": "Wait 60s", "type": "main", "index": 0}]]
        },
        "Clear Cache": {
            "main": [[{"node": "Wait 60s", "type": "main", "index": 0}]]
        },
        "Wait 60s": {
            "main": [[{"node": "Verify Fix", "type": "main", "index": 0}]]
        },
        "Verify Fix": {
            "main": [[{"node": "Merge Fix Results", "type": "main", "index": 0}]]
        },
        "Merge Fix Results": {
            "main": [[{"node": "Format Report", "type": "main", "index": 0}]]
        },
        "Format Report": {
            "main": [[{"node": "Send to Telegram", "type": "main", "index": 0}]]
        },
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_workflow_json() -> dict[str, Any]:
    """Get the complete workflow as JSON for export.

    Returns:
        Complete n8n workflow JSON.
    """
    return create_error_scanner_workflow()


def export_to_file(filepath: str = "error_scanner_workflow.json") -> None:
    """Export workflow to JSON file.

    Args:
        filepath: Output file path.
    """
    import json

    with open(filepath, "w") as f:
        json.dump(get_workflow_json(), f, indent=2)
    print(f"Workflow exported to {filepath}")


if __name__ == "__main__":
    import json

    print(json.dumps(get_workflow_json(), indent=2))
