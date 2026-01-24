"""Smart Email Agent v2.0 - LangGraph-based email processing.

ADR-014: Smart Email Agent Architecture

Phase 1 MVP: LangGraph skeleton + Haiku classification + Hebrish formatting
Phase 2 Intelligence: Web research + Sender history + Draft replies

Architecture (Phase 2):
    FETCH → CLASSIFY → RESEARCH → HISTORY → DRAFT → FORMAT → SEND
       ↓        ↓          ↓          ↓        ↓        ↓       ↓
    Gmail    Haiku      Web/LLM    Gmail    LLM    Hebrish  Telegram

Components:
    - graph.py: LangGraph state machine
    - state.py: State definitions (EmailItem, ResearchResult, etc.)
    - nodes/classify.py: LLM-based classification
    - nodes/research.py: Web research for P1/P2 emails
    - nodes/history.py: Sender history lookup
    - nodes/draft.py: Reply draft generation
    - nodes/format_rtl.py: Hebrish RTL formatting
    - persona.py: Smart friend personality
"""

from src.agents.smart_email.graph import SmartEmailGraph, run_smart_email_agent
from src.agents.smart_email.state import (
    DraftReply,
    EmailCategory,
    EmailItem,
    EmailState,
    Priority,
    ResearchResult,
    SenderHistory,
)

__all__ = [
    # Main interface
    "SmartEmailGraph",
    "run_smart_email_agent",
    # State types
    "EmailState",
    "EmailItem",
    "Priority",
    "EmailCategory",
    # Phase 2 types
    "ResearchResult",
    "SenderHistory",
    "DraftReply",
]
