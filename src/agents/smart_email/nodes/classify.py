"""Classification node - LLM-based email classification using Haiku.

Uses Claude Haiku for cost-efficient classification (~$0.001 per email).
Falls back to regex patterns if LLM fails.
"""

import json
import logging
import re
from typing import Any

from src.agents.smart_email.persona import CLASSIFICATION_PROMPT
from src.agents.smart_email.state import (
    EmailCategory,
    EmailItem,
    EmailState,
    Priority,
)

logger = logging.getLogger(__name__)


# System email patterns for filtering
SYSTEM_PATTERNS = [
    # Git/CI platforms
    "github.com", "gitlab", "bitbucket", "jenkins", "circleci",
    "travis-ci", "azure-pipelines", "actions@github",
    # Hosting/Infrastructure
    "railway.app", "railway", "vercel", "netlify", "heroku",
    "digitalocean", "aws.amazon", "cloud.google", "azure.microsoft",
    # Generic automated
    "noreply", "no-reply", "notifications@", "notification@",
    "automated", "donotreply", "do-not-reply", "mailer-daemon",
    "postmaster", "system@", "alerts@", "monitoring@",
]


def is_system_email(sender: str, sender_email: str) -> bool:
    """Check if email is from automated/system source."""
    combined = f"{sender} {sender_email}".lower()
    return any(pattern in combined for pattern in SYSTEM_PATTERNS)


def classify_with_regex(
    subject: str,
    sender: str,
    snippet: str,
) -> tuple[EmailCategory, Priority, str]:
    """Fallback regex-based classification.

    Used when LLM is unavailable or fails.

    Returns:
        Tuple of (category, priority, reason)
    """
    combined = f"{subject} {sender} {snippet}".lower()

    # Urgent patterns
    urgent_patterns = [
        r"דחוף", r"urgent", r"מיידי", r"immediate",
        r"אחרון", r"last chance", r"deadline", r"expires",
        r"תוך \d+ (ימים|שעות)", r"within \d+ (days|hours)",
    ]
    for pattern in urgent_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return EmailCategory.URGENT, Priority.P1, "זוהה כדחוף לפי מילות מפתח"

    # Bureaucracy patterns
    bureaucracy_patterns = [
        r"משרד", r"ממשל", r"gov\.il", r"ביטוח לאומי",
        r"מס הכנסה", r"עירייה", r"רשות",
    ]
    for pattern in bureaucracy_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return EmailCategory.BUREAUCRACY, Priority.P1, "מייל ממוסד ממשלתי"

    # Finance patterns
    finance_patterns = [
        r"בנק", r"bank", r"חשבונית", r"invoice",
        r"תשלום", r"payment", r"חיוב", r"₪", r"\$",
    ]
    for pattern in finance_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return EmailCategory.FINANCE, Priority.P1, "מייל פיננסי"

    # Promotional
    promo_patterns = [
        r"sale", r"מבצע", r"discount", r"הנחה",
        r"unsubscribe", r"הסר", r"newsletter",
    ]
    for pattern in promo_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return EmailCategory.PROMOTIONAL, Priority.P4, "מייל פרסומי"

    # Default
    return EmailCategory.INFORMATIONAL, Priority.P3, "סיווג ברירת מחדל"


async def classify_with_llm(
    subject: str,
    sender: str,
    sender_email: str,
    snippet: str,
    litellm_url: str,
) -> dict[str, Any] | None:
    """Classify email using Claude Haiku via LiteLLM.

    Args:
        subject: Email subject
        sender: Sender name
        sender_email: Sender email address
        snippet: Email snippet/preview
        litellm_url: LiteLLM Gateway URL

    Returns:
        Classification dict or None if failed
    """
    try:
        from openai import AsyncOpenAI

        prompt = CLASSIFICATION_PROMPT.format(
            sender=sender,
            sender_email=sender_email,
            subject=subject,
            snippet=snippet[:500],  # Limit snippet length
        )

        client = AsyncOpenAI(base_url=litellm_url, api_key="dummy")

        response = await client.chat.completions.create(
            model="claude-haiku",  # Cost-efficient model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Low temperature for consistency
            max_tokens=300,
        )

        content = response.choices[0].message.content.strip()

        # Clean markdown if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

        return json.loads(content)

    except Exception as e:
        logger.warning(f"LLM classification failed: {e}")
        return None


def parse_classification_result(
    result: dict[str, Any],
) -> tuple[EmailCategory, Priority, str, str | None, str | None, str]:
    """Parse LLM classification result.

    Returns:
        Tuple of (category, priority, reason, deadline, amount, action_suggestion)
    """
    # Parse category
    category_map = {
        "בירוקרטיה": EmailCategory.BUREAUCRACY,
        "כספים": EmailCategory.FINANCE,
        "דחוף": EmailCategory.URGENT,
        "יומן": EmailCategory.CALENDAR,
        "דורש פעולה": EmailCategory.ACTION_REQUIRED,
        "מידע": EmailCategory.INFORMATIONAL,
        "פרסום": EmailCategory.PROMOTIONAL,
        "אישי": EmailCategory.PERSONAL,
    }
    category = category_map.get(
        result.get("category", "מידע"),
        EmailCategory.INFORMATIONAL
    )

    # Parse priority
    priority_str = result.get("priority", "P3")
    priority_map = {
        "P1": Priority.P1,
        "P2": Priority.P2,
        "P3": Priority.P3,
        "P4": Priority.P4,
    }
    priority = priority_map.get(priority_str, Priority.P3)

    reason = result.get("reason", "")
    deadline = result.get("deadline")
    amount = result.get("amount")
    action = result.get("action_suggestion", "")

    return category, priority, reason, deadline, amount, action


async def classify_emails_node(state: EmailState) -> EmailState:
    """LangGraph node: Classify all fetched emails.

    Takes raw emails from state, classifies each one using LLM,
    and returns EmailItem objects with classifications.

    Args:
        state: Current graph state

    Returns:
        Updated state with classified emails
    """
    logger.info(f"Classifying {len(state.get('raw_emails', []))} emails")

    raw_emails = state.get("raw_emails", [])
    litellm_url = "https://litellm-gateway-production-0339.up.railway.app"

    classified_emails: list[EmailItem] = []
    system_count = 0

    for raw in raw_emails:
        sender = raw.get("sender", "")
        sender_email = raw.get("sender_email", "")
        subject = raw.get("subject", "")
        snippet = raw.get("snippet", "")

        # Filter system emails
        if is_system_email(sender, sender_email):
            system_count += 1
            continue

        # Try LLM classification
        llm_result = await classify_with_llm(
            subject=subject,
            sender=sender,
            sender_email=sender_email,
            snippet=snippet,
            litellm_url=litellm_url,
        )

        if llm_result:
            result = parse_classification_result(llm_result)
            category, priority, reason, deadline, amount, action = result
        else:
            # Fallback to regex
            category, priority, reason = classify_with_regex(subject, sender, snippet)
            deadline = None
            amount = None
            action = ""

        # Create EmailItem
        email_item = EmailItem(
            id=raw.get("id", ""),
            thread_id=raw.get("thread_id", ""),
            subject=subject,
            sender=sender,
            sender_email=sender_email,
            date=raw.get("date", ""),
            snippet=snippet,
            category=category,
            priority=priority,
            priority_reason=reason,
            deadline=deadline,
            amount=amount,
            ai_action_suggestion=action,
        )

        classified_emails.append(email_item)

    # Sort by priority
    classified_emails.sort(key=lambda e: e.priority.value)

    # Count by priority
    p1 = sum(1 for e in classified_emails if e.priority == Priority.P1)
    p2 = sum(1 for e in classified_emails if e.priority == Priority.P2)
    p3 = sum(1 for e in classified_emails if e.priority == Priority.P3)
    p4 = sum(1 for e in classified_emails if e.priority == Priority.P4)

    logger.info(f"Classified {len(classified_emails)} emails: P1={p1}, P2={p2}, P3={p3}, P4={p4}")

    return {
        **state,
        "emails": classified_emails,
        "system_emails_count": system_count,
        "total_count": len(classified_emails),
        "p1_count": p1,
        "p2_count": p2,
        "p3_count": p3,
        "p4_count": p4,
    }
