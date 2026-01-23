"""RTL formatting node - Hebrish Telegram message formatting.

Formats classified emails into a beautiful RTL Telegram message
using the "smart friend" Hebrish persona.
"""

import logging
from datetime import UTC, datetime

from src.agents.smart_email.persona import (
    MESSAGE_TEMPLATES,
    format_priority_header,
    format_stats,
    format_work_report,
    get_greeting,
)
from src.agents.smart_email.state import EmailItem, EmailState, Priority

logger = logging.getLogger(__name__)


# Unicode RTL marker for mixed text
RLM = "\u200F"


def wrap_english(text: str) -> str:
    """Wrap English text in RTL markers for proper display.

    Args:
        text: Text that may contain English

    Returns:
        Text with RTL markers
    """
    # Simple approach: wrap known English terms
    english_terms = [
        "API", "OAuth", "webhook", "deploy", "PR", "CI/CD",
        "Railway", "GitHub", "Gmail", "Telegram",
    ]
    for term in english_terms:
        if term in text:
            text = text.replace(term, f"{RLM}{term}{RLM}")
    return text


def format_email_item(email: EmailItem, include_details: bool = True) -> list[str]:
    """Format a single email item for Telegram.

    Args:
        email: Classified email item
        include_details: Whether to include full details

    Returns:
        List of formatted lines
    """
    lines = []

    # Sender and subject
    sender_display = email.sender[:25] if len(email.sender) > 25 else email.sender
    subject_display = email.subject[:40] + ("..." if len(email.subject) > 40 else "")

    lines.append(f"  📍 *{sender_display}*")
    lines.append(f"     {subject_display}")

    if include_details:
        # Category
        lines.append(f"     🏷️ {email.category.value}")

        # Deadline
        if email.deadline:
            lines.append(f"     ⏰ דד-ליין: {email.deadline}")

        # Amount
        if email.amount:
            lines.append(f"     💰 {email.amount}")

        # AI suggestion
        if email.ai_action_suggestion:
            lines.append(f"     💡 {email.ai_action_suggestion}")

        # Reason (for P1)
        if email.priority == Priority.P1 and email.priority_reason:
            lines.append(f"     📋 _{email.priority_reason}_")

    return lines


def format_telegram_message_hebrish(
    emails: list[EmailItem],
    p1_count: int,
    p2_count: int,
    p3_count: int,
    p4_count: int,
    system_count: int,
    duration_seconds: float,
) -> str:
    """Format full Telegram message in Hebrish style.

    Args:
        emails: Classified emails
        p1_count: P1 email count
        p2_count: P2 email count
        p3_count: P3 email count
        p4_count: P4 email count
        system_count: Filtered system emails count
        duration_seconds: Processing duration

    Returns:
        Formatted Telegram message
    """
    total = len(emails)
    lines = []

    # Greeting
    lines.append(get_greeting())
    lines.append("")

    # No emails case
    if total == 0:
        lines.append(MESSAGE_TEMPLATES["no_emails"])
        if system_count > 0:
            lines.append(f"_({system_count} התראות מערכת הוסתרו)_")
        lines.append("")
        lines.append(MESSAGE_TEMPLATES["footer"])
        return "\n".join(lines)

    # Stats
    lines.append(format_stats(total, p1_count, p2_count))
    if system_count > 0:
        lines.append(f"🔇 _{system_count} התראות מערכת הוסתרו_")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    # P1 - Urgent (full details)
    p1_emails = [e for e in emails if e.priority == Priority.P1]
    if p1_emails:
        lines.append("")
        lines.append(format_priority_header("P1"))
        for email in p1_emails[:5]:  # Max 5
            lines.extend(format_email_item(email, include_details=True))
            lines.append("")

    # P2 - Important (medium details)
    p2_emails = [e for e in emails if e.priority == Priority.P2]
    if p2_emails:
        lines.append("")
        lines.append(format_priority_header("P2"))
        for email in p2_emails[:5]:  # Max 5
            lines.extend(format_email_item(email, include_details=False))
            lines.append("")

    # P3 - Info (compact)
    p3_emails = [e for e in emails if e.priority == Priority.P3]
    if p3_emails:
        lines.append("")
        lines.append(format_priority_header("P3"))
        for email in p3_emails[:7]:  # Max 7
            sender = email.sender[:20]
            subject = email.subject[:30] + ("..." if len(email.subject) > 30 else "")
            lines.append(f"  • {sender}")
            lines.append(f"    _{subject}_")

    # P4 - Low (summary only)
    p4_emails = [e for e in emails if e.priority == Priority.P4]
    if p4_emails:
        lines.append("")
        lines.append(f"⚪ *נמוך:* {len(p4_emails)} מיילים")

    # Footer
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(format_work_report(duration_seconds, sources=0))
    lines.append("_Smart Email Agent v2.0_")

    return "\n".join(lines)


def format_adhd_friendly(
    emails: list[EmailItem],
    p1_count: int,
) -> str:
    """Format ADHD-friendly message (one urgent item at a time).

    Args:
        emails: Classified emails
        p1_count: P1 email count

    Returns:
        ADHD-friendly Telegram message
    """
    now = datetime.now(UTC).strftime("%H:%M")
    lines = []

    p1_emails = [e for e in emails if e.priority == Priority.P1]

    if p1_emails:
        urgent = p1_emails[0]  # Just the first one
        lines.extend([
            f"⏰ {now} | יש לך דבר אחד דחוף",
            "",
            f"🔴 {urgent.sender}",
            f"   {urgent.subject[:40]}",
        ])

        if urgent.deadline:
            lines.append(f"   ⏳ {urgent.deadline}")

        if urgent.ai_action_suggestion:
            lines.append(f"   💡 {urgent.ai_action_suggestion}")

        lines.extend([
            "",
            "   [טפל עכשיו] או [תזכיר מחר]",
            "",
            "━━━━━━━━━━━━",
            "",
        ])

    else:
        lines.extend([
            f"⏰ {now} | אין שום דבר דחוף 🎉",
            "",
        ])

    # Other items count
    other_count = len(emails) - len(p1_emails[:1])
    if other_count > 0:
        lines.append(f"📬 עוד {other_count} מיילים")
        lines.append("   [הראה הכל] או [סמן כנקרא]")

    return "\n".join(lines)


async def format_telegram_node(state: EmailState) -> EmailState:
    """LangGraph node: Format classified emails for Telegram.

    Takes classified emails and formats them into a Hebrish
    Telegram message.

    Args:
        state: Current graph state with classified emails

    Returns:
        Updated state with telegram_message
    """
    import time

    logger.info("Formatting Telegram message")

    emails = state.get("emails", [])
    duration = time.time() - state.get("start_time", time.time())

    # Format message
    message = format_telegram_message_hebrish(
        emails=emails,
        p1_count=state.get("p1_count", 0),
        p2_count=state.get("p2_count", 0),
        p3_count=state.get("p3_count", 0),
        p4_count=state.get("p4_count", 0),
        system_count=state.get("system_emails_count", 0),
        duration_seconds=duration,
    )

    return {
        **state,
        "telegram_message": message,
        "duration_ms": int(duration * 1000),
    }
