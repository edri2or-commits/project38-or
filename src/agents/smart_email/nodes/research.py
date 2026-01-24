"""Research node - Web research for important emails.

Performs web research for P1/P2 emails to gather context,
find deadlines, and locate relevant forms or documents.
"""

import logging
import re

from src.agents.smart_email.state import (
    EmailItem,
    EmailState,
    Priority,
    ResearchResult,
)

logger = logging.getLogger(__name__)


# Research-worthy categories
RESEARCH_CATEGORIES = [
    "בירוקרטיה",  # Bureaucracy - government sites
    "כספים",      # Finance - bank info
    "דחוף",       # Urgent - deadlines
    "דורש פעולה",  # Action required
]

# Domain patterns for targeted research
DOMAIN_PATTERNS = {
    "gov.il": "ממשלת ישראל",
    "btl.gov.il": "ביטוח לאומי",
    "taxes.gov.il": "רשות המיסים",
    "misim.gov.il": "רשות המיסים",
    "bank": "בנק",
    "leumi": "בנק לאומי",
    "hapoalim": "בנק הפועלים",
    "discount": "בנק דיסקונט",
    "mizrahi": "בנק מזרחי",
}


def extract_search_query(email: EmailItem) -> str:
    """Extract search query from email content.

    Args:
        email: Email to analyze

    Returns:
        Search query string
    """
    # Build query from subject and key terms
    query_parts = []

    # Add sender domain if recognizable
    sender_domain = email.sender_email.split("@")[-1] if "@" in email.sender_email else ""
    for pattern, name in DOMAIN_PATTERNS.items():
        if pattern in sender_domain.lower():
            query_parts.append(name)
            break

    # Add subject (cleaned)
    subject = email.subject
    # Remove common prefixes
    for prefix in ["Re:", "Fwd:", "RE:", "FW:", "תשובה:", "העברה:"]:
        subject = subject.replace(prefix, "").strip()
    if subject:
        query_parts.append(subject[:50])

    # Look for form numbers or reference codes
    ref_patterns = [
        r"טופס\s*(\d+)",           # טופס 101
        r"form\s*(\d+)",           # Form 101
        r"אסמכתא[:\s]*(\d+)",      # אסמכתא: 12345
        r"מספר\s*בקשה[:\s]*(\d+)",  # מספר בקשה: 12345
    ]
    for pattern in ref_patterns:
        match = re.search(pattern, email.snippet, re.IGNORECASE)
        if match:
            query_parts.append(f"טופס {match.group(1)}")
            break

    return " ".join(query_parts) if query_parts else email.subject[:40]


def should_research(email: EmailItem) -> bool:
    """Determine if email needs web research.

    Args:
        email: Email to check

    Returns:
        True if research would be valuable
    """
    # Only research P1/P2 emails
    if email.priority not in [Priority.P1, Priority.P2]:
        return False

    # Check if category is research-worthy
    if email.category.value in RESEARCH_CATEGORIES:
        return True

    # Check for government/bank senders
    sender = email.sender_email.lower()
    for pattern in DOMAIN_PATTERNS:
        if pattern in sender:
            return True

    return False


async def research_with_llm(
    email: EmailItem,
    litellm_url: str,
) -> ResearchResult | None:
    """Perform web research using LLM.

    Uses the LLM to search and summarize relevant information.

    Args:
        email: Email to research
        litellm_url: LiteLLM Gateway URL

    Returns:
        Research result or None if failed
    """
    try:
        from openai import AsyncOpenAI

        query = extract_search_query(email)
        logger.info(f"Researching: {query}")

        # Build research prompt
        prompt = f"""אתה עוזר מחקר. המשתמש קיבל מייל ואתה צריך לעזור לו להבין:
1. מה נדרש ממנו
2. מה הדדליינים
3. איפה למצוא טפסים או מידע נוסף

מייל:
- שולח: {email.sender} ({email.sender_email})
- נושא: {email.subject}
- תוכן: {email.snippet[:500]}

ענה בפורמט JSON:
{{
    "summary": "סיכום קצר של מה נדרש",
    "deadlines": ["דדליין 1", "דדליין 2"],
    "forms": ["טופס או קישור 1"],
    "action_steps": ["צעד 1", "צעד 2"],
    "sources": ["מקור מידע 1"]
}}"""

        client = AsyncOpenAI(base_url=litellm_url, api_key="dummy")

        response = await client.chat.completions.create(
            model="claude-haiku",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        import json
        # Clean markdown if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

        data = json.loads(content)

        return ResearchResult(
            email_id=email.id,
            query=query,
            summary=data.get("summary", ""),
            findings=data.get("action_steps", []),
            sources=data.get("sources", []),
            relevant_deadlines=data.get("deadlines", []),
            forms_found=data.get("forms", []),
        )

    except Exception as e:
        logger.warning(f"Research failed for {email.id}: {e}")
        return None


async def research_node(state: EmailState) -> EmailState:
    """Perform web research for important emails via LangGraph node.

    Researches P1/P2 emails to find relevant information,
    deadlines, forms, and action steps.

    Args:
        state: Current graph state with classified emails

    Returns:
        Updated state with research results
    """
    # Check if research is enabled
    if not state.get("enable_research", True):
        logger.info("Research disabled, skipping")
        return state

    emails = state.get("emails", [])
    litellm_url = "https://litellm-gateway-production-0339.up.railway.app"

    research_results: list[ResearchResult] = []
    research_count = 0

    for email in emails:
        if should_research(email):
            result = await research_with_llm(email, litellm_url)
            if result:
                research_results.append(result)
                # Attach to email
                email.research = result
                research_count += 1

                # Update AI suggestion with research findings
                if result.summary:
                    email.ai_action_suggestion = result.summary

    logger.info(f"Researched {research_count} emails")

    return {
        **state,
        "emails": emails,
        "research_results": research_results,
        "research_count": research_count,
    }
