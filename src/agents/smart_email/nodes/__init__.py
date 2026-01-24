"""LangGraph nodes for Smart Email Agent.

Each node is a function that takes state and returns modified state.
Nodes are wired together in graph.py.

Phase 1 (MVP):
    - classify_emails_node: Haiku LLM classification
    - format_telegram_node: Hebrish RTL formatting

Phase 2 (Intelligence):
    - research_node: Web research for P1/P2 emails
    - history_node: Sender history lookup
    - draft_node: Reply draft generation
"""

from src.agents.smart_email.nodes.classify import classify_emails_node
from src.agents.smart_email.nodes.draft import draft_node
from src.agents.smart_email.nodes.format_rtl import format_telegram_node
from src.agents.smart_email.nodes.history import history_node
from src.agents.smart_email.nodes.research import research_node

__all__ = [
    # Phase 1
    "classify_emails_node",
    "format_telegram_node",
    # Phase 2
    "research_node",
    "history_node",
    "draft_node",
]
