"""Conversation module for Smart Email Agent.

Phase 4.11: Conversational Telegram Interface

Enables natural language interaction with the email agent:
- Intent classification (email query, action request, etc.)
- Context-aware responses using memory layer
- Action confirmation flow

Example:
    from apps.personal.agents.smart_email.conversation import ConversationHandler

    handler = ConversationHandler()
    await handler.initialize()

    response = await handler.process_message(
        user_id="user_123",
        chat_id="chat_456",
        message="מה עם המייל מדני?"
    )
    print(response.text)
"""

from apps.personal.agents.smart_email.conversation.handler import (
    ConversationHandler,
    ConversationResponse,
    PendingAction,
)
from apps.personal.agents.smart_email.conversation.intents import (
    ActionType,
    Intent,
    IntentResult,
    classify_intent,
    get_action_description_hebrew,
    get_intent_description_hebrew,
)

__all__ = [
    # Handler
    "ConversationHandler",
    "ConversationResponse",
    "PendingAction",
    # Intents
    "Intent",
    "IntentResult",
    "ActionType",
    "classify_intent",
    "get_intent_description_hebrew",
    "get_action_description_hebrew",
]
