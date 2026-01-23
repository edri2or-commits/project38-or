"""Agents module - Autonomous AI agents for project38-or.

This module contains specialized agents that run autonomously:
- EmailAgent: Daily email scanning, classification, and Telegram delivery
"""

from src.agents.email_agent import (
    DailySummary,
    EmailAgent,
    EmailCategory,
    EmailItem,
    Priority,
)

__all__ = [
    "EmailAgent",
    "EmailItem",
    "EmailCategory",
    "Priority",
    "DailySummary",
]
