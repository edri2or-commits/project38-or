"""Memory node for Smart Email Agent.

Phase 4.10: Sender Intelligence integration.

This node enriches emails with sender memory context:
- Loads sender profiles from PostgreSQL
- Records new interactions
- Provides context for LLM classification
"""

import logging
import os
from typing import Any

from apps.personal.agents.smart_email.memory.store import MemoryStore
from apps.personal.agents.smart_email.memory.types import RelationshipType
from apps.personal.agents.smart_email.state import EmailItem, EmailState

logger = logging.getLogger(__name__)

# Singleton memory store instance
_memory_store: MemoryStore | None = None


async def get_memory_store() -> MemoryStore:
    """Get or create the memory store singleton.

    Returns:
        Initialized MemoryStore instance
    """
    global _memory_store

    if _memory_store is None:
        _memory_store = MemoryStore()
        await _memory_store.initialize()

    return _memory_store


def classify_relationship(total_interactions: int, is_vip: bool = False) -> str:
    """Classify relationship type based on interaction count.

    Args:
        total_interactions: Number of interactions with sender
        is_vip: Whether sender is marked as VIP

    Returns:
        Relationship type string
    """
    if is_vip:
        return RelationshipType.VIP.value

    if total_interactions == 0:
        return RelationshipType.NEW.value
    elif total_interactions <= 5:
        return RelationshipType.OCCASIONAL.value
    elif total_interactions <= 15:
        return RelationshipType.RECURRING.value
    else:
        return RelationshipType.FREQUENT.value


async def enrich_email_with_memory(
    email_data: dict,
    store: MemoryStore,
) -> dict:
    """Enrich a single email with sender memory context.

    Args:
        email_data: Raw email data dict
        store: Memory store instance

    Returns:
        Enriched email data with sender context
    """
    sender_email = email_data.get("sender_email", "").lower()
    if not sender_email:
        return email_data

    # Get or create sender profile
    profile = await store.get_sender_profile(sender_email)

    if profile:
        # Existing sender - enrich with history
        total = profile.get("total_interactions", 0)
        is_vip = profile.get("is_vip", False)

        email_data["sender_relationship"] = classify_relationship(total, is_vip)
        email_data["sender_total_interactions"] = total
        email_data["sender_typical_priority"] = profile.get("typical_priority", "P3")
        email_data["sender_typical_urgency"] = profile.get("typical_urgency", 0.3)
        email_data["sender_is_vip"] = is_vip
        email_data["sender_role"] = profile.get("role", "")
        email_data["sender_notes"] = profile.get("notes", "")

        # Get recent interactions for context
        history = await store.get_sender_history(sender_email, limit=3)
        if history:
            recent_subjects = [h.get("subject", "")[:40] for h in history[:3]]
            email_data["sender_recent_subjects"] = recent_subjects

        # Build context string for LLM
        email_data["sender_context"] = await store.get_sender_context_for_llm(sender_email)

    else:
        # New sender - create profile
        sender_name = email_data.get("sender", "")
        await store.create_sender_profile(sender_email, sender_name)

        email_data["sender_relationship"] = RelationshipType.NEW.value
        email_data["sender_total_interactions"] = 0
        email_data["sender_is_vip"] = False
        email_data["sender_context"] = f"שולח חדש: {sender_name or sender_email}"

    return email_data


async def record_email_interaction(
    email: EmailItem,
    store: MemoryStore,
) -> None:
    """Record an email interaction in memory.

    Args:
        email: Classified email item
        store: Memory store instance
    """
    sender_email = getattr(email, "sender_email", "") or ""
    if not sender_email:
        # Try to extract from sender field
        sender = getattr(email, "sender", "")
        if "<" in sender and ">" in sender:
            sender_email = sender.split("<")[1].split(">")[0]
        else:
            sender_email = sender

    if not sender_email:
        return

    try:
        await store.record_interaction(
            sender_email=sender_email.lower(),
            email_id=email.id,
            thread_id=email.thread_id,
            subject=email.subject,
            priority=email.priority.value if hasattr(email.priority, 'value') else str(email.priority),
            category=email.category.value if hasattr(email.category, 'value') else str(email.category),
            was_urgent=(email.priority.value if hasattr(email.priority, 'value') else str(email.priority)) in ["P1", "P2"],
            had_deadline=bool(email.deadline),
        )
    except Exception as e:
        logger.warning(f"Failed to record interaction: {e}")


async def memory_enrich_node(state: EmailState) -> dict[str, Any]:
    """Enrich emails with sender memory (LangGraph node).

    This node runs BEFORE classification to provide sender context
    that helps with more accurate prioritization.

    Args:
        state: Current graph state with raw_emails

    Returns:
        Updated state with enriched emails
    """
    raw_emails = state.get("raw_emails", [])
    if not raw_emails:
        return {"memory_enabled": False}

    # Check if memory is enabled
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.info("Memory disabled (no DATABASE_URL)")
        return {"memory_enabled": False}

    try:
        store = await get_memory_store()

        # Enrich each email with sender context
        enriched_emails = []
        for email_data in raw_emails:
            enriched = await enrich_email_with_memory(email_data, store)
            enriched_emails.append(enriched)

        logger.info(f"Enriched {len(enriched_emails)} emails with sender memory")

        return {
            "raw_emails": enriched_emails,
            "memory_enabled": True,
        }

    except Exception as e:
        logger.warning(f"Memory enrichment failed: {e}")
        return {"memory_enabled": False}


async def memory_record_node(state: EmailState) -> dict[str, Any]:
    """Record email interactions in memory (LangGraph node).

    This node runs AFTER classification to record what was processed.

    Args:
        state: Current graph state with classified emails

    Returns:
        Updated state with recording status
    """
    emails = state.get("emails", [])
    if not emails:
        return {"interactions_recorded": 0}

    # Check if memory is enabled
    if not state.get("memory_enabled", False):
        return {"interactions_recorded": 0}

    try:
        store = await get_memory_store()

        recorded = 0
        for email in emails:
            await record_email_interaction(email, store)
            recorded += 1

        logger.info(f"Recorded {recorded} interactions in memory")

        return {"interactions_recorded": recorded}

    except Exception as e:
        logger.warning(f"Recording interactions failed: {e}")
        return {"interactions_recorded": 0}


def get_sender_badge(relationship: str) -> str:
    """Get emoji badge for relationship type.

    Args:
        relationship: Relationship type string

    Returns:
        Emoji badge
    """
    badges = {
        "new": "🆕",
        "occasional": "👤",
        "recurring": "🔄",
        "frequent": "⭐",
        "vip": "👑",
        "government": "🏛️",
        "bank": "🏦",
        "accountant": "📊",
        "lawyer": "⚖️",
        "family": "👨‍👩‍👧",
        "friend": "🤝",
    }
    return badges.get(relationship, "👤")


def format_sender_context_hebrew(
    relationship: str,
    total_interactions: int,
    typical_priority: str | None = None,
    notes: str | None = None,
) -> str:
    """Format sender context in Hebrew for Telegram.

    Args:
        relationship: Relationship type
        total_interactions: Total interaction count
        typical_priority: Typical email priority
        notes: Any notes about sender

    Returns:
        Formatted Hebrew string
    """
    parts = []

    # Badge and relationship
    badge = get_sender_badge(relationship)

    rel_hebrew = {
        "new": "חדש",
        "occasional": "מזדמן",
        "recurring": "חוזר",
        "frequent": "תכוף",
        "vip": "חשוב",
    }

    rel_text = rel_hebrew.get(relationship, relationship)
    parts.append(f"{badge} {rel_text}")

    if total_interactions > 0:
        parts.append(f"({total_interactions} הודעות)")

    if typical_priority and typical_priority in ["P1", "P2"]:
        parts.append(f"• בד\"כ {typical_priority}")

    if notes:
        parts.append(f"• {notes[:50]}")

    return " ".join(parts)
