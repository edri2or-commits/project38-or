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

Phase 4 (Full Capabilities):
    - verify_completeness_node: Proof that no emails were missed
    - memory_enrich_node: Sender intelligence from memory
    - memory_record_node: Record interactions to memory
"""

from src.agents.smart_email.nodes.classify import classify_emails_node
from src.agents.smart_email.nodes.draft import draft_node
from src.agents.smart_email.nodes.format_rtl import format_telegram_node
from src.agents.smart_email.nodes.history import history_node
from src.agents.smart_email.nodes.memory import (
    format_sender_context_hebrew,
    get_sender_badge,
    memory_enrich_node,
    memory_record_node,
)
from src.agents.smart_email.nodes.research import research_node
from src.agents.smart_email.nodes.verify import verify_completeness_node

__all__ = [
    # Phase 1
    "classify_emails_node",
    "format_telegram_node",
    # Phase 2
    "research_node",
    "history_node",
    "draft_node",
    # Phase 4
    "verify_completeness_node",
    "memory_enrich_node",
    "memory_record_node",
    "get_sender_badge",
    "format_sender_context_hebrew",
]
