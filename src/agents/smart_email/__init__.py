"""Smart Email Agent v2.0 - LangGraph-based email processing.

ADR-014: Smart Email Agent Architecture
Phase 1 MVP: LangGraph skeleton + Haiku classification + Hebrish formatting

Architecture:
    FETCH → CLASSIFY → FORMAT → SEND
       ↓        ↓         ↓       ↓
    Gmail    Haiku    Hebrish  Telegram

Components:
    - graph.py: LangGraph state machine
    - state.py: State definitions
    - nodes/classify.py: LLM-based classification
    - nodes/format_rtl.py: Hebrish RTL formatting
    - persona.py: Smart friend personality
"""

from src.agents.smart_email.graph import SmartEmailGraph, run_smart_email_agent
from src.agents.smart_email.state import EmailCategory, EmailState, Priority

__all__ = [
    "SmartEmailGraph",
    "run_smart_email_agent",
    "EmailState",
    "Priority",
    "EmailCategory",
]
