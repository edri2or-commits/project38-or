"""LangGraph nodes for Smart Email Agent.

Each node is a function that takes state and returns modified state.
Nodes are wired together in graph.py.
"""

from src.agents.smart_email.nodes.classify import classify_emails_node
from src.agents.smart_email.nodes.format_rtl import format_telegram_node

__all__ = [
    "classify_emails_node",
    "format_telegram_node",
]
