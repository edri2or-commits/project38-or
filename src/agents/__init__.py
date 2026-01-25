"""
Agents module - Autonomous AI agents for task execution.

This module contains the Smart Email Agent (v2.0) which uses LangGraph
for email processing, classification, and response generation.

Note:
    Legacy agents (email_agent, deadline_tracker, etc.) were removed
    in system audit cleanup (2026-01-25). If historical reference needed,
    see git history before commit that removed them.

Usage:
    from src.agents.smart_email import SmartEmailGraph, EmailState
"""

from src.agents.smart_email import SmartEmailGraph, EmailState

__all__ = ["SmartEmailGraph", "EmailState"]
