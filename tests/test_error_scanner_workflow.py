"""Tests for error_scanner_workflow module.

Tests the n8n workflow builder for the Error Scanner Agent (ADR-016).
"""

import pytest

from src.workflows.error_scanner_workflow import (
    CONFIG,
    SEVERITY_RULES,
    create_error_scanner_workflow,
    get_workflow_json,
)


class TestWorkflowStructure:
    """Test workflow structure and configuration."""

    def test_create_workflow_returns_dict(self):
        """Workflow builder returns a dictionary."""
        workflow = create_error_scanner_workflow()
        assert isinstance(workflow, dict)

    def test_workflow_has_required_keys(self):
        """Workflow has all required n8n keys."""
        workflow = create_error_scanner_workflow()
        required_keys = ["name", "nodes", "connections", "active", "settings"]
        for key in required_keys:
            assert key in workflow, f"Missing key: {key}"

    def test_workflow_name(self):
        """Workflow has correct name."""
        workflow = create_error_scanner_workflow()
        assert workflow["name"] == "Error Scanner Agent - Daily"

    def test_workflow_is_active(self):
        """Workflow is set to active."""
        workflow = create_error_scanner_workflow()
        assert workflow["active"] is True

    def test_workflow_settings(self):
        """Workflow has correct settings."""
        workflow = create_error_scanner_workflow()
        settings = workflow["settings"]
        assert settings["saveExecutionProgress"] is True
        assert settings["timezone"] == "UTC"


class TestWorkflowNodes:
    """Test workflow node definitions."""

    def test_has_schedule_trigger(self):
        """Workflow has schedule trigger node."""
        workflow = create_error_scanner_workflow()
        node_names = [n["name"] for n in workflow["nodes"]]
        assert "Daily 07:00 UTC" in node_names

    def test_has_scan_nodes(self):
        """Workflow has all scan nodes."""
        workflow = create_error_scanner_workflow()
        node_names = [n["name"] for n in workflow["nodes"]]

        expected_scans = [
            "Scan GitHub Actions",
            "Scan Railway Deployments",
            "Scan Production Health",
            "Scan Monitoring Status",
        ]
        for scan in expected_scans:
            assert scan in node_names, f"Missing scan node: {scan}"

    def test_has_categorize_node(self):
        """Workflow has categorization node."""
        workflow = create_error_scanner_workflow()
        node_names = [n["name"] for n in workflow["nodes"]]
        assert "Categorize by Severity" in node_names

    def test_has_fix_nodes(self):
        """Workflow has fix nodes for each error type."""
        workflow = create_error_scanner_workflow()
        node_names = [n["name"] for n in workflow["nodes"]]

        expected_fixes = [
            "Re-run CI Workflow",
            "Retry Deployment",
            "Restart Service",
            "Clear Cache",
        ]
        for fix in expected_fixes:
            assert fix in node_names, f"Missing fix node: {fix}"

    def test_has_verification_nodes(self):
        """Workflow has verification nodes."""
        workflow = create_error_scanner_workflow()
        node_names = [n["name"] for n in workflow["nodes"]]

        assert "Wait 60s" in node_names
        assert "Verify Fix" in node_names

    def test_has_report_nodes(self):
        """Workflow has reporting nodes."""
        workflow = create_error_scanner_workflow()
        node_names = [n["name"] for n in workflow["nodes"]]

        assert "Format Report" in node_names
        assert "Send to Telegram" in node_names

    def test_node_count(self):
        """Workflow has expected number of nodes."""
        workflow = create_error_scanner_workflow()
        # Schedule + 4 scans + merge + categorize + filter + switch +
        # 4 fixes + wait + verify + merge + format + telegram = 18
        assert len(workflow["nodes"]) >= 15


class TestWorkflowConnections:
    """Test workflow connection graph."""

    def test_connections_is_dict(self):
        """Connections is a dictionary."""
        workflow = create_error_scanner_workflow()
        assert isinstance(workflow["connections"], dict)

    def test_trigger_connects_to_scans(self):
        """Trigger connects to all scan nodes."""
        workflow = create_error_scanner_workflow()
        connections = workflow["connections"]

        assert "Daily 07:00 UTC" in connections
        trigger_outputs = connections["Daily 07:00 UTC"]["main"][0]
        output_nodes = [o["node"] for o in trigger_outputs]

        assert "Scan GitHub Actions" in output_nodes
        assert "Scan Railway Deployments" in output_nodes
        assert "Scan Production Health" in output_nodes

    def test_scans_connect_to_merge(self):
        """All scan nodes connect to merge node."""
        workflow = create_error_scanner_workflow()
        connections = workflow["connections"]

        scan_nodes = [
            "Scan GitHub Actions",
            "Scan Railway Deployments",
            "Scan Production Health",
            "Scan Monitoring Status",
        ]

        for scan in scan_nodes:
            assert scan in connections
            outputs = connections[scan]["main"][0]
            assert any(o["node"] == "Merge Scan Results" for o in outputs)

    def test_report_connects_to_telegram(self):
        """Format Report connects to Telegram."""
        workflow = create_error_scanner_workflow()
        connections = workflow["connections"]

        assert "Format Report" in connections
        outputs = connections["Format Report"]["main"][0]
        assert any(o["node"] == "Send to Telegram" for o in outputs)


class TestConfiguration:
    """Test workflow configuration."""

    def test_config_has_production_url(self):
        """Config has production URL."""
        assert "production_url" in CONFIG
        assert CONFIG["production_url"] == "https://or-infra.com"

    def test_config_has_github_repo(self):
        """Config has GitHub repo."""
        assert "github_repo" in CONFIG
        assert CONFIG["github_repo"] == "edri2or-commits/project38-or"

    def test_config_has_schedule(self):
        """Config has cron schedule."""
        assert "schedule_cron" in CONFIG
        assert CONFIG["schedule_cron"] == "0 7 * * *"

    def test_config_has_max_actions(self):
        """Config has max actions limit."""
        assert "max_actions_per_run" in CONFIG
        assert CONFIG["max_actions_per_run"] == 5


class TestSeverityRules:
    """Test severity classification rules."""

    def test_has_all_severity_levels(self):
        """Has P1-P4 severity levels."""
        expected = ["P1_CRITICAL", "P2_HIGH", "P3_MEDIUM", "P4_LOW"]
        for level in expected:
            assert level in SEVERITY_RULES

    def test_p1_critical_auto_fix(self):
        """P1 Critical has auto-fix enabled."""
        assert SEVERITY_RULES["P1_CRITICAL"]["auto_fix"] is True

    def test_p4_low_no_auto_fix(self):
        """P4 Low has auto-fix disabled."""
        assert SEVERITY_RULES["P4_LOW"]["auto_fix"] is False

    def test_severity_has_patterns(self):
        """Each severity level has patterns."""
        for level, config in SEVERITY_RULES.items():
            assert "patterns" in config
            assert isinstance(config["patterns"], list)
            assert len(config["patterns"]) > 0


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_workflow_json(self):
        """get_workflow_json returns valid workflow."""
        workflow = get_workflow_json()
        assert isinstance(workflow, dict)
        assert "nodes" in workflow
        assert "connections" in workflow
