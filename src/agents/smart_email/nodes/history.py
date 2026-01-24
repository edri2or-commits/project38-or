"""History node - Sender communication history lookup.

Looks up past email history with each sender to provide
context about the relationship and previous conversations.
"""

import logging
from collections import Counter
from datetime import UTC
from typing import Any

from src.agents.smart_email.state import (
    EmailItem,
    EmailState,
    Priority,
    SenderHistory,
)

logger = logging.getLogger(__name__)


def classify_relationship(total_emails: int, days_since_last: int) -> str:
    """Classify relationship type based on communication patterns.

    Args:
        total_emails: Total emails from this sender
        days_since_last: Days since last email

    Returns:
        Relationship type string
    """
    if total_emails == 1:
        return "new"  # First contact
    elif total_emails > 10 and days_since_last < 30:
        return "frequent"  # Regular contact
    elif total_emails > 3:
        return "recurring"  # Occasional contact
    else:
        return "occasional"


def extract_topics(subjects: list[str]) -> list[str]:
    """Extract common topics from email subjects.

    Args:
        subjects: List of email subjects

    Returns:
        List of common topics
    """
    # Simple word frequency for topics
    words: list[str] = []
    stop_words = {
        "re", "fwd", "fw", "את", "של", "עם", "על", "או", "אם",
        "the", "a", "an", "is", "are", "was", "were", "be",
    }

    for subject in subjects:
        # Clean and split
        subject = subject.lower()
        for prefix in ["re:", "fwd:", "fw:", "תשובה:", "העברה:"]:
            subject = subject.replace(prefix, "")
        subject_words = subject.split()
        words.extend([w for w in subject_words if w not in stop_words and len(w) > 2])

    # Get most common
    counter = Counter(words)
    return [word for word, _ in counter.most_common(3)]


async def lookup_sender_history(
    sender_email: str,
    gmail_client: Any,
    max_results: int = 20,
) -> SenderHistory | None:
    """Look up history with a specific sender.

    Args:
        sender_email: Email address to look up
        gmail_client: Gmail client instance
        max_results: Maximum emails to retrieve

    Returns:
        Sender history or None if lookup failed
    """
    try:
        # Search for emails from this sender
        query = f"from:{sender_email}"
        messages = gmail_client.search_emails(query=query, max_results=max_results)

        if not messages:
            return SenderHistory(
                sender_email=sender_email,
                total_emails=0,
                relationship_type="new",
            )

        # Extract data
        subjects = [msg.subject for msg in messages]
        thread_ids = list({msg.thread_id for msg in messages})
        dates = [msg.date for msg in messages if msg.date]

        # Calculate days since last contact
        days_since_last = 0
        if dates:
            from datetime import datetime
            try:
                # Parse the most recent date
                last_date_str = dates[0]
                # Handle various date formats
                for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z"]:
                    try:
                        last_date = datetime.strptime(last_date_str, fmt)
                        now = datetime.now(UTC)
                        days_since_last = (now - last_date).days
                        break
                    except ValueError:
                        continue
            except Exception as e:
                logger.debug(f"Date parsing failed: {e}")

        return SenderHistory(
            sender_email=sender_email,
            total_emails=len(messages),
            last_contact=dates[0] if dates else "",
            common_topics=extract_topics(subjects),
            previous_threads=thread_ids[:5],  # Max 5 threads
            relationship_type=classify_relationship(len(messages), days_since_last),
        )

    except Exception as e:
        logger.warning(f"History lookup failed for {sender_email}: {e}")
        return None


def should_lookup_history(email: EmailItem) -> bool:
    """Determine if sender history lookup is valuable.

    Args:
        email: Email to check

    Returns:
        True if history lookup would be helpful
    """
    # Always lookup for P1/P2
    if email.priority in [Priority.P1, Priority.P2]:
        return True

    # Lookup for action-required emails
    if email.category.value == "דורש פעולה":
        return True

    return False


async def history_node(state: EmailState) -> EmailState:
    """Look up sender history for important emails via LangGraph node.

    Queries Gmail for past communications with senders of
    P1/P2 emails to provide relationship context.

    Args:
        state: Current graph state with classified emails

    Returns:
        Updated state with sender histories
    """
    # Check if history is enabled
    if not state.get("enable_history", True):
        logger.info("History lookup disabled, skipping")
        return state

    emails = state.get("emails", [])

    # Try to get Gmail client
    try:
        from src.agents.gmail_client import GmailClient
        gmail = GmailClient()
    except Exception as e:
        logger.warning(f"Gmail client unavailable: {e}")
        return state

    sender_histories: list[SenderHistory] = []
    processed_senders: set[str] = set()

    for email in emails:
        # Skip if we already looked up this sender
        if email.sender_email in processed_senders:
            continue

        if should_lookup_history(email):
            history = await lookup_sender_history(
                sender_email=email.sender_email,
                gmail_client=gmail,
            )
            if history:
                sender_histories.append(history)
                # Attach to all emails from this sender
                for e in emails:
                    if e.sender_email == email.sender_email:
                        e.sender_history = history

            processed_senders.add(email.sender_email)

    logger.info(f"Looked up history for {len(sender_histories)} senders")

    return {
        **state,
        "emails": emails,
        "sender_histories": sender_histories,
    }
