"""Memory layer for Smart Email Agent.

Phase 4.10: Sender Intelligence - Long-term memory with PostgreSQL

Implements three types of memory (based on CoALA paper):
- Semantic Memory: Facts about senders, relationships, preferences
- Episodic Memory: Past interactions, threads, outcomes
- Procedural Memory: How to respond, action patterns

Architecture:
    PostgreSQL (Railway) ← Store/Retrieve → Memory Layer → Agent

References:
- LangGraph Memory: https://docs.langchain.com/oss/python/langgraph/memory
- MongoDB + LangGraph: https://www.mongodb.com/blog/langgraph-memory
- DeepLearning.AI Course: Long-Term Agentic Memory with LangGraph
"""

from src.agents.smart_email.memory.types import (
    SenderProfile,
    InteractionRecord,
    ThreadSummary,
    ActionOutcome,
    MemoryType,
    RelationshipType,
)
from src.agents.smart_email.memory.store import MemoryStore

__all__ = [
    # Types
    "SenderProfile",
    "InteractionRecord",
    "ThreadSummary",
    "ActionOutcome",
    "MemoryType",
    "RelationshipType",
    # Store
    "MemoryStore",
]
