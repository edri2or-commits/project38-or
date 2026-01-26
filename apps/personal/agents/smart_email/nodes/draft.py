"""Draft node - Reply draft generation.

Generates contextual draft replies for emails that need responses,
matching the appropriate tone and including relevant information.
"""

import json
import logging

from apps.personal.agents.smart_email.state import (
    DraftReply,
    EmailCategory,
    EmailItem,
    EmailState,
    Priority,
)

logger = logging.getLogger(__name__)


# Categories that typically need replies
REPLY_CATEGORIES = [
    EmailCategory.ACTION_REQUIRED,
    EmailCategory.URGENT,
    EmailCategory.BUREAUCRACY,
    EmailCategory.PERSONAL,
]

# Tone mapping based on sender domain
TONE_PATTERNS = {
    "gov.il": "formal",
    "bank": "formal",
    "gmail.com": "friendly",
    "hotmail.com": "friendly",
    "yahoo.com": "friendly",
}


def determine_tone(email: EmailItem) -> str:
    """Determine appropriate reply tone based on sender.

    Args:
        email: Email to analyze

    Returns:
        Tone string: formal, professional, or friendly
    """
    sender = email.sender_email.lower()

    for pattern, tone in TONE_PATTERNS.items():
        if pattern in sender:
            return tone

    # Default to professional for business
    if email.category in [EmailCategory.BUREAUCRACY, EmailCategory.FINANCE]:
        return "formal"

    return "professional"


def determine_action_type(email: EmailItem) -> str:
    """Determine the type of action needed.

    Args:
        email: Email to analyze

    Returns:
        Action type string
    """
    snippet = email.snippet.lower()
    subject = email.subject.lower()
    combined = f"{snippet} {subject}"

    # Check for meeting/calendar mentions
    meeting_keywords = ["פגישה", "תיאום", "זום", "meeting", "schedule", "calendar", "zoom"]
    if any(kw in combined for kw in meeting_keywords):
        return "schedule_meeting"

    # Check for forward requests
    forward_keywords = ["העבר", "forward", "share with", "שתף עם"]
    if any(kw in combined for kw in forward_keywords):
        return "forward"

    # Default to reply
    return "reply"


def should_generate_draft(email: EmailItem) -> bool:
    """Determine if a draft reply should be generated.

    Args:
        email: Email to check

    Returns:
        True if draft would be helpful
    """
    # Generate drafts for P1/P2 action items
    if email.priority in [Priority.P1, Priority.P2]:
        if email.category in REPLY_CATEGORIES:
            return True

    # Generate for any action-required
    if email.category == EmailCategory.ACTION_REQUIRED:
        return True

    return False


DRAFT_PROMPT = """אתה עוזר כתיבה בעברית. צריך לכתוב טיוטת תשובה למייל.

פרטי המייל:
- שולח: {sender}
- נושא: {subject}
- תוכן: {snippet}

{history_context}
{research_context}

הנחיות:
- סגנון: {tone}
- סוג פעולה: {action_type}
- להיות קצר וענייני
- לא לחתום בשם (המשתמש יוסיף)

כתוב בפורמט JSON:
{{
    "subject": "נושא התשובה (אם שונה מהמקורי)",
    "body": "גוף ההודעה",
    "confidence": 0.8
}}"""


async def generate_draft_with_llm(
    email: EmailItem,
    litellm_url: str,
) -> DraftReply | None:
    """Generate draft reply using LLM.

    Args:
        email: Email to reply to
        litellm_url: LiteLLM Gateway URL

    Returns:
        Draft reply or None if failed
    """
    try:
        from openai import AsyncOpenAI

        tone = determine_tone(email)
        action_type = determine_action_type(email)

        # Build context from research and history
        history_context = ""
        if email.sender_history:
            h = email.sender_history
            history_context = f"""
היסטוריה עם השולח:
- מספר הודעות קודמות: {h.total_emails}
- נושאים נפוצים: {', '.join(h.common_topics) if h.common_topics else 'אין'}
- סוג קשר: {h.relationship_type}"""

        research_context = ""
        if email.research:
            r = email.research
            research_context = f"""
מחקר רלוונטי:
- סיכום: {r.summary}
- דדליינים: {', '.join(r.relevant_deadlines) if r.relevant_deadlines else 'אין'}"""

        prompt = DRAFT_PROMPT.format(
            sender=email.sender,
            subject=email.subject,
            snippet=email.snippet[:500],
            history_context=history_context,
            research_context=research_context,
            tone=tone,
            action_type=action_type,
        )

        client = AsyncOpenAI(base_url=litellm_url, api_key="dummy")

        response = await client.chat.completions.create(
            model="claude-haiku",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=400,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

        data = json.loads(content)

        return DraftReply(
            email_id=email.id,
            subject=data.get("subject", f"Re: {email.subject}"),
            body=data.get("body", ""),
            tone=tone,
            action_type=action_type,
            confidence=data.get("confidence", 0.7),
        )

    except Exception as e:
        logger.warning(f"Draft generation failed for {email.id}: {e}")
        return None


async def draft_node(state: EmailState) -> EmailState:
    """Generate draft replies for action items via LangGraph node.

    Creates contextual draft replies for emails that need responses,
    using sender history and research for context.

    Args:
        state: Current graph state with classified emails

    Returns:
        Updated state with draft replies
    """
    # Check if drafts are enabled
    if not state.get("enable_drafts", True):
        logger.info("Draft generation disabled, skipping")
        return state

    emails = state.get("emails", [])
    litellm_url = "https://litellm-gateway-production-0339.up.railway.app"

    draft_replies: list[DraftReply] = []
    drafts_count = 0

    for email in emails:
        if should_generate_draft(email):
            draft = await generate_draft_with_llm(email, litellm_url)
            if draft:
                draft_replies.append(draft)
                email.draft_reply = draft
                drafts_count += 1

    logger.info(f"Generated {drafts_count} draft replies")

    return {
        **state,
        "emails": emails,
        "draft_replies": draft_replies,
        "drafts_count": drafts_count,
    }
