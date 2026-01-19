"""
Automation module for multi-path execution.

This module provides reliable automation that doesn't depend solely on GitHub API.
It implements the strategy from ADR-008: try multiple paths in order of speed
and reliability.

Paths (in order):
1. Direct Python execution (<1s)
2. Cloud Run direct call (<10s)
3. n8n webhook (<5s)
4. GitHub API (30-60s, fallback)
5. Manual issue creation (last resort)

Usage:
    from src.automation import AutomationOrchestrator

    orchestrator = AutomationOrchestrator()
    result = await orchestrator.execute("test-gcp-tools", {})

    if result.success:
        print(f"Completed via {result.path}")
    else:
        print(f"All paths failed: {result.errors}")
"""

from .orchestrator import AutomationOrchestrator, AutomationResult

__all__ = ["AutomationOrchestrator", "AutomationResult"]
