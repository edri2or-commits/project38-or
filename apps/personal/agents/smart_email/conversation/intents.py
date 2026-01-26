"""Intent classification for email conversations.

Phase 4.11: Conversational Telegram Interface

Detects user intent from natural language:
- EMAIL_QUERY: "מה עם המייל מהבנק?"
- SENDER_QUERY: "תזכיר לי על דני"
- ACTION_REQUEST: "שלח לו שאני מאשר"
- SUMMARY_REQUEST: "תסכם לי את המיילים"
- HELP_REQUEST: "עזרה", "מה אתה יכול לעשות?"
- GENERAL: Other messages
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intent(Enum):
    """User intent categories."""

    EMAIL_QUERY = "email_query"  # Question about specific email
    SENDER_QUERY = "sender_query"  # Question about sender
    ACTION_REQUEST = "action_request"  # Request to do something
    SUMMARY_REQUEST = "summary_request"  # Request for summary
    HELP_REQUEST = "help_request"  # Help/capabilities question
    INBOX_STATUS = "inbox_status"  # Current inbox state
    GENERAL = "general"  # General conversation


class ActionType(Enum):
    """Types of actions user can request."""

    REPLY = "reply"  # Reply to email
    FORWARD = "forward"  # Forward email
    ARCHIVE = "archive"  # Archive email
    MARK_READ = "mark_read"  # Mark as read
    MARK_IMPORTANT = "mark_important"  # Mark as important
    SNOOZE = "snooze"  # Snooze email
    LABEL = "label"  # Add label
    DELETE = "delete"  # Delete email
    APPROVE = "approve"  # Approve something in email
    REJECT = "reject"  # Reject something in email


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: Intent
    confidence: float = 0.0
    entities: dict[str, Any] = field(default_factory=dict)
    action_type: ActionType | None = None
    raw_message: str = ""

    def is_confident(self, threshold: float = 0.6) -> bool:
        """Check if confidence is above threshold."""
        return self.confidence >= threshold


# Intent patterns (Hebrew-focused)
INTENT_PATTERNS: dict[Intent, list[re.Pattern]] = {
    Intent.EMAIL_QUERY: [
        re.compile(r"מה\s+(?:עם|בקשר\s+ל|לגבי)\s+(?:ה)?מייל", re.IGNORECASE),
        re.compile(r"(?:תזכיר|ספר)\s+לי\s+על\s+(?:ה)?מייל", re.IGNORECASE),
        re.compile(r"מה\s+(?:הוא\s+)?(?:כתב|רצה|ביקש)", re.IGNORECASE),
        re.compile(r"(?:איזה|מה)\s+מייל", re.IGNORECASE),
        re.compile(r"(?:הצג|תראה)\s+(?:את\s+)?(?:ה)?מייל", re.IGNORECASE),
    ],
    Intent.SENDER_QUERY: [
        re.compile(r"מה\s+(?:עם|בקשר\s+ל|לגבי)\s+(?!ה?מייל)(\w+)", re.IGNORECASE),
        re.compile(r"^(?:מי\s+)?(?:זה|הוא)\s+(\w+)\??$", re.IGNORECASE),  # Only at start/end
        re.compile(r"(?:תזכיר|ספר)\s+לי\s+על\s+(?!ה?מייל)(\w+)", re.IGNORECASE),
        re.compile(r"(?:היסטוריה|קשר)\s+(?:עם|של)\s+(\w+)", re.IGNORECASE),
        re.compile(r"(?:מ)?מתי\s+(?:ה)?(?:אחרון|קודם)\s+(?:מ)?(\w+)", re.IGNORECASE),
        re.compile(r"(?:ה)?מייל\s+(?:של|מ)\s*(\w{2,})", re.IGNORECASE),
    ],
    Intent.ACTION_REQUEST: [
        re.compile(r"(?:שלח|תשלח)\s+(?:לו|לה|להם)", re.IGNORECASE),
        re.compile(r"(?:ענה|תענה)\s+(?:לו|לה|להם)(?:\s+ש)?", re.IGNORECASE),
        re.compile(r"(?:תגיד|אמור)\s+(?:לו|לה|להם)(?:\s+ש)?", re.IGNORECASE),
        re.compile(r"(?:אשר|תאשר|מאשר)(?:\s+את)?\s*(?:זה|ה)?", re.IGNORECASE),
        re.compile(r"(?:דחה|תדחה|דוחה)(?:\s+את)?\s*(?:זה|ה)?", re.IGNORECASE),
        re.compile(r"(?:תעביר|העבר)(?:\s+את)?\s*(?:ה)?מייל", re.IGNORECASE),
        re.compile(r"(?:ארכב|תארכב|ארכיון)", re.IGNORECASE),
        re.compile(r"(?:מחק|תמחק)(?:\s+את)?\s*(?:ה)?מייל", re.IGNORECASE),
        re.compile(r"(?:סמן|תסמן)\s+(?:כ)?(?:נקרא|חשוב)", re.IGNORECASE),
    ],
    Intent.SUMMARY_REQUEST: [
        re.compile(r"(?:תסכם|סכם)\s+(?:לי)?", re.IGNORECASE),
        re.compile(r"סיכום\s+(?:ה)?(?:מיילים|תיבה|inbox)", re.IGNORECASE),
        re.compile(r"מה\s+(?:יש|חדש)\s+(?:ב)?(?:ה)?(?:תיבה|inbox|מיילים)", re.IGNORECASE),
        re.compile(r"(?:תעדכן|עדכון)\s+(?:מה\s+)?(?:יש|חדש)", re.IGNORECASE),
        re.compile(r"(?:כמה|מה)\s+(?:יש\s+)?מיילים", re.IGNORECASE),
    ],
    Intent.HELP_REQUEST: [
        re.compile(r"עזרה", re.IGNORECASE),
        re.compile(r"מה\s+(?:אתה\s+)?יכול\s+(?:לעשות|לעזור)", re.IGNORECASE),
        re.compile(r"(?:איך|כיצד)\s+(?:אני\s+)?(?:יכול|משתמש)", re.IGNORECASE),
        re.compile(r"(?:פקודות|commands|help)", re.IGNORECASE),
    ],
    Intent.INBOX_STATUS: [
        re.compile(r"מה\s+המצב\s+(?:ב)?(?:ה)?(?:תיבה|inbox)", re.IGNORECASE),
        re.compile(r"כמה\s+(?:מיילים\s+)?(?:לא\s+)?נקראו", re.IGNORECASE),
        re.compile(r"(?:יש|כמה)\s+דברים\s+(?:דחופים|חשובים)", re.IGNORECASE),
        re.compile(r"סטטוס\s+(?:ה)?(?:תיבה|מיילים|inbox)", re.IGNORECASE),
    ],
}

# Action patterns
ACTION_PATTERNS: dict[ActionType, list[re.Pattern]] = {
    ActionType.REPLY: [
        re.compile(r"(?:שלח|תשלח|ענה|תענה)", re.IGNORECASE),
        re.compile(r"(?:תגיד|אמור)\s+(?:לו|לה|להם)", re.IGNORECASE),
    ],
    ActionType.APPROVE: [
        re.compile(r"(?:אשר|תאשר|מאשר|אישור)", re.IGNORECASE),
        re.compile(r"(?:אוקיי|ok|בסדר|מסכים)", re.IGNORECASE),
    ],
    ActionType.REJECT: [
        re.compile(r"(?:דחה|תדחה|דוחה|דחייה)", re.IGNORECASE),
        re.compile(r"(?:לא\s+)?מסכים", re.IGNORECASE),
    ],
    ActionType.FORWARD: [
        re.compile(r"(?:תעביר|העבר)\s+(?:ל)?", re.IGNORECASE),
        re.compile(r"(?:forward|פורוורד)", re.IGNORECASE),
    ],
    ActionType.ARCHIVE: [
        re.compile(r"(?:ארכב|תארכב|ארכיון|archive)", re.IGNORECASE),
    ],
    ActionType.DELETE: [
        re.compile(r"(?:מחק|תמחק|delete)", re.IGNORECASE),
    ],
    ActionType.MARK_IMPORTANT: [
        re.compile(r"(?:סמן|תסמן)\s+(?:כ)?חשוב", re.IGNORECASE),
        re.compile(r"(?:חשוב|כוכב|star)", re.IGNORECASE),
    ],
    ActionType.MARK_READ: [
        re.compile(r"(?:סמן|תסמן)\s+(?:כ)?נקרא", re.IGNORECASE),
    ],
}

# Entity extraction patterns
# Hebrew-aware sender name extraction
SENDER_NAME_PATTERN = re.compile(
    r"(?:מ|של|עם|לגבי|על|ל)[\s\-]?[\"']?(\w{2,20})[\"']?(?:\?|!|$|\s)",
    re.IGNORECASE,
)

# Pattern for "מה עם X" or "מה בקשר ל X"
WHATS_WITH_PATTERN = re.compile(
    r"(?:מה\s+(?:עם|בקשר\s+ל))\s*[\"']?(\w{2,20})[\"']?",
    re.IGNORECASE,
)

# Pattern for "המייל מ[שם]"
EMAIL_FROM_PATTERN = re.compile(
    r"(?:ה)?מייל\s+(?:מ|של)\s*[\"']?(\w{2,20})[\"']?",
    re.IGNORECASE,
)

EMAIL_ID_PATTERN = re.compile(r"מייל\s+(?:מספר\s+)?(\d+)", re.IGNORECASE)


def classify_intent(message: str) -> IntentResult:
    """Classify user message intent.

    Args:
        message: User message text

    Returns:
        IntentResult with detected intent and entities
    """
    message = message.strip()

    # Check each intent pattern
    best_match: IntentResult | None = None
    highest_confidence = 0.0

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(message)
            if match:
                # Base confidence from pattern match
                confidence = 0.7

                # Boost confidence for longer matches
                match_length = len(match.group())
                if match_length > 10:
                    confidence += 0.1
                if match_length > 20:
                    confidence += 0.1

                if confidence > highest_confidence:
                    highest_confidence = confidence
                    entities = {}

                    # Extract entities based on intent
                    if intent == Intent.SENDER_QUERY:
                        entities = extract_sender_entity(message)
                    elif intent == Intent.EMAIL_QUERY:
                        entities = extract_email_entity(message)
                    elif intent == Intent.ACTION_REQUEST:
                        entities = extract_action_entity(message)

                    action_type = None
                    if intent == Intent.ACTION_REQUEST:
                        action_type = detect_action_type(message)

                    best_match = IntentResult(
                        intent=intent,
                        confidence=confidence,
                        entities=entities,
                        action_type=action_type,
                        raw_message=message,
                    )

    # Default to general if no match
    if best_match is None:
        return IntentResult(
            intent=Intent.GENERAL,
            confidence=0.5,
            raw_message=message,
        )

    return best_match


def extract_sender_entity(message: str) -> dict[str, Any]:
    """Extract sender-related entities from message.

    Args:
        message: User message

    Returns:
        Dict with sender_name if found
    """
    entities = {}
    common_words = {
        "מה", "עם", "על", "את", "זה", "הוא", "היא", "לי", "לו", "לה",
        "מייל", "המייל", "תזכיר", "ספר", "בקשר",
    }

    # Try "המייל של X" or "המייל מ X" pattern first
    match = EMAIL_FROM_PATTERN.search(message)
    if match:
        name = match.group(1)
        if name.lower() not in common_words and len(name) >= 2:
            entities["sender_name"] = name
            return entities

    # Try "מה עם X" pattern
    match = WHATS_WITH_PATTERN.search(message)
    if match:
        name = match.group(1)
        if name.lower() not in common_words and len(name) >= 2:
            entities["sender_name"] = name
            return entities

    # Try general pattern
    match = SENDER_NAME_PATTERN.search(message)
    if match:
        name = match.group(1)
        if name.lower() not in common_words and len(name) >= 2:
            entities["sender_name"] = name

    return entities


def extract_email_entity(message: str) -> dict[str, Any]:
    """Extract email-related entities from message.

    Args:
        message: User message

    Returns:
        Dict with email_id or sender_ref if found
    """
    entities = {}
    common_words = {
        "מה", "עם", "על", "את", "זה", "הוא", "היא", "לי", "לו", "לה",
        "מייל", "המייל", "תזכיר", "ספר", "בקשר",
    }

    # Look for email ID
    match = EMAIL_ID_PATTERN.search(message)
    if match:
        entities["email_id"] = match.group(1)

    # Look for "המייל מ[שם]" pattern
    from_match = EMAIL_FROM_PATTERN.search(message)
    if from_match:
        name = from_match.group(1)
        if name.lower() not in common_words and len(name) >= 2:
            entities["sender_ref"] = name
            return entities

    # Look for "מה עם X" pattern
    whats_match = WHATS_WITH_PATTERN.search(message)
    if whats_match:
        name = whats_match.group(1)
        if name.lower() not in common_words and len(name) >= 2:
            entities["sender_ref"] = name
            return entities

    # Fallback to general sender pattern
    sender_match = SENDER_NAME_PATTERN.search(message)
    if sender_match:
        name = sender_match.group(1)
        if name.lower() not in common_words and len(name) >= 2:
            entities["sender_ref"] = name

    return entities


def extract_action_entity(message: str) -> dict[str, Any]:
    """Extract action-related entities from message.

    Args:
        message: User message

    Returns:
        Dict with action details
    """
    entities = {}

    # Look for what to say/send
    say_match = re.search(
        r"(?:שלח|תגיד|אמור|תשלח)\s+(?:לו|לה|להם)?\s+(?:ש)?[\"']?(.+?)[\"']?$",
        message,
        re.IGNORECASE,
    )
    if say_match:
        entities["message_content"] = say_match.group(1).strip()

    # Look for recipient
    to_match = re.search(r"(?:ל|אל)\s+(\w+)", message, re.IGNORECASE)
    if to_match:
        entities["recipient"] = to_match.group(1)

    return entities


def detect_action_type(message: str) -> ActionType | None:
    """Detect specific action type from message.

    Args:
        message: User message

    Returns:
        ActionType if detected, None otherwise
    """
    for action_type, patterns in ACTION_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(message):
                return action_type

    return None


def get_intent_description_hebrew(intent: Intent) -> str:
    """Get Hebrew description of intent.

    Args:
        intent: Intent enum

    Returns:
        Hebrew description
    """
    descriptions = {
        Intent.EMAIL_QUERY: "שאלה על מייל ספציפי",
        Intent.SENDER_QUERY: "שאלה על שולח",
        Intent.ACTION_REQUEST: "בקשה לביצוע פעולה",
        Intent.SUMMARY_REQUEST: "בקשת סיכום",
        Intent.HELP_REQUEST: "בקשת עזרה",
        Intent.INBOX_STATUS: "סטטוס התיבה",
        Intent.GENERAL: "שיחה כללית",
    }
    return descriptions.get(intent, "לא ידוע")


def get_action_description_hebrew(action: ActionType) -> str:
    """Get Hebrew description of action.

    Args:
        action: ActionType enum

    Returns:
        Hebrew description
    """
    descriptions = {
        ActionType.REPLY: "לענות",
        ActionType.FORWARD: "להעביר",
        ActionType.ARCHIVE: "לארכב",
        ActionType.MARK_READ: "לסמן כנקרא",
        ActionType.MARK_IMPORTANT: "לסמן כחשוב",
        ActionType.SNOOZE: "לדחות",
        ActionType.LABEL: "להוסיף תווית",
        ActionType.DELETE: "למחוק",
        ActionType.APPROVE: "לאשר",
        ActionType.REJECT: "לדחות",
    }
    return descriptions.get(action, "פעולה")
