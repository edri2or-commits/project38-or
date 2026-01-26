"""Conversation handler for Smart Email Agent.

Phase 4.11: Conversational Telegram Interface

Handles natural language queries about emails:
- "מה עם המייל מדני?" -> Looks up sender, shows recent emails
- "תזכיר לי מה הוא רצה" -> Shows email context from memory
- "שלח לו שאני מאשר" -> Queues action for approval

Uses memory layer for context persistence.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from apps.personal.agents.smart_email.conversation.intents import (
    ActionType,
    Intent,
    IntentResult,
    classify_intent,
    get_action_description_hebrew,
    get_intent_description_hebrew,
)
from apps.personal.agents.smart_email.memory.store import MemoryStore
from apps.personal.agents.smart_email.memory.types import ConversationContext

logger = logging.getLogger(__name__)


@dataclass
class ConversationResponse:
    """Response from conversation handler."""

    text: str
    requires_confirmation: bool = False
    action_to_confirm: ActionType | None = None
    action_details: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    show_keyboard: bool = False
    keyboard_options: list[str] = field(default_factory=list)


@dataclass
class PendingAction:
    """Action waiting for user confirmation."""

    action_type: ActionType
    target_email_id: str | None = None
    target_sender: str | None = None
    message_content: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class ConversationHandler:
    """Handles conversational email queries.

    Uses memory layer for:
    - Sender profiles and history
    - Conversation context persistence
    - Action tracking

    Example:
        handler = ConversationHandler()
        await handler.initialize()

        response = await handler.process_message(
            user_id="user_123",
            chat_id="chat_456",
            message="מה עם המייל מדני?"
        )
        print(response.text)
    """

    def __init__(self, memory_store: MemoryStore | None = None):
        """Initialize conversation handler.

        Args:
            memory_store: Optional pre-initialized MemoryStore
        """
        self._store = memory_store
        self._initialized = False
        self._pending_actions: dict[str, PendingAction] = {}

    async def initialize(self) -> bool:
        """Initialize memory store connection.

        Returns:
            True if initialized successfully
        """
        if self._initialized:
            return True

        if self._store is None:
            self._store = MemoryStore()

        success = await self._store.initialize()
        self._initialized = success
        return success

    async def process_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
    ) -> ConversationResponse:
        """Process user message and generate response.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message: User message text

        Returns:
            ConversationResponse with text and optional actions
        """
        # Ensure initialized
        if not self._initialized:
            await self.initialize()

        # Classify intent
        intent_result = classify_intent(message)

        logger.info(
            f"Intent: {intent_result.intent.value} "
            f"(confidence: {intent_result.confidence:.2f})"
        )

        # Update conversation context
        await self._update_context(user_id, chat_id, message, intent_result)

        # Route to appropriate handler
        if intent_result.intent == Intent.EMAIL_QUERY:
            return await self._handle_email_query(user_id, intent_result)

        elif intent_result.intent == Intent.SENDER_QUERY:
            return await self._handle_sender_query(user_id, intent_result)

        elif intent_result.intent == Intent.ACTION_REQUEST:
            return await self._handle_action_request(user_id, intent_result)

        elif intent_result.intent == Intent.SUMMARY_REQUEST:
            return await self._handle_summary_request(user_id)

        elif intent_result.intent == Intent.INBOX_STATUS:
            return await self._handle_inbox_status(user_id)

        elif intent_result.intent == Intent.HELP_REQUEST:
            return self._handle_help_request()

        else:
            return await self._handle_general(user_id, intent_result)

    async def confirm_action(
        self,
        user_id: str,
        confirmed: bool = True,
    ) -> ConversationResponse:
        """Handle user confirmation of pending action.

        Args:
            user_id: Telegram user ID
            confirmed: True if user confirmed, False if cancelled

        Returns:
            ConversationResponse with result
        """
        pending = self._pending_actions.get(user_id)

        if not pending:
            return ConversationResponse(
                text="אין פעולה ממתינה לאישור.",
            )

        # Remove pending action
        del self._pending_actions[user_id]

        if not confirmed:
            return ConversationResponse(
                text="הפעולה בוטלה. ✖️",
            )

        # Execute action
        return await self._execute_action(user_id, pending)

    async def _update_context(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        intent: IntentResult,
    ) -> None:
        """Update conversation context in memory.

        Args:
            user_id: User ID
            chat_id: Chat ID
            message: User message
            intent: Classified intent
        """
        if not self._store:
            return

        try:
            # Get or create context
            context = await self._store.get_conversation_context(user_id)

            if not context:
                await self._store.save_conversation_context(
                    user_id=user_id,
                    chat_id=chat_id,
                )

            # Add message to context
            await self._store.add_message_to_context(
                user_id=user_id,
                role="user",
                content=message,
            )

            # Update current focus based on intent
            if intent.entities.get("sender_ref") or intent.entities.get("sender_name"):
                sender = intent.entities.get("sender_ref") or intent.entities.get("sender_name")
                await self._store._update_conversation_fields(
                    user_id,
                    current_sender=sender,
                )

        except Exception as e:
            logger.warning(f"Failed to update context: {e}")

    async def _handle_email_query(
        self,
        user_id: str,
        intent: IntentResult,
    ) -> ConversationResponse:
        """Handle question about specific email.

        Args:
            user_id: User ID
            intent: Classified intent with entities

        Returns:
            Response about the email
        """
        sender_ref = intent.entities.get("sender_ref")
        email_id = intent.entities.get("email_id")

        if not sender_ref and not email_id:
            # Try to get from context
            if self._store:
                context = await self._store.get_conversation_context(user_id)
                if context:
                    sender_ref = context.get("current_sender")

        if not sender_ref and not email_id:
            return ConversationResponse(
                text="על איזה מייל אתה מדבר? תוכל לציין את שם השולח או מספר המייל.",
                suggestions=["המייל האחרון", "המייל מהבנק", "תסכם לי את המיילים"],
            )

        # Look up sender in memory
        if sender_ref and self._store:
            context = await self._store.get_sender_context_for_llm(sender_ref)
            history = await self._store.get_sender_history(sender_ref, limit=3)

            if history:
                # Found history
                lines = [f"🔍 מצאתי מידע על {sender_ref}:", ""]
                lines.append(context)
                lines.append("")
                lines.append("📧 מיילים אחרונים:")

                for h in history[:3]:
                    subject = h.get("subject", "")[:40]
                    date = h.get("timestamp")
                    if isinstance(date, datetime):
                        date_str = date.strftime("%d/%m")
                    else:
                        date_str = str(date)[:10] if date else ""
                    priority = h.get("priority", "P3")
                    lines.append(f"  • [{priority}] {date_str}: {subject}")

                return ConversationResponse(
                    text="\n".join(lines),
                    suggestions=["תפתח את המייל", "תענה לו", "תארכב"],
                    show_keyboard=True,
                    keyboard_options=["📖 הצג עוד", "✏️ טיוטה", "📁 ארכיון"],
                )
            else:
                return ConversationResponse(
                    text=f"לא מצאתי מיילים מ-{sender_ref} בזיכרון. "
                    f"אולי השם כתוב אחרת?",
                    suggestions=["תראה את כל המיילים", "תחפש לפי נושא"],
                )

        return ConversationResponse(
            text="לא הצלחתי למצוא את המייל. תנסה שוב?",
        )

    async def _handle_sender_query(
        self,
        user_id: str,
        intent: IntentResult,
    ) -> ConversationResponse:
        """Handle question about sender.

        Args:
            user_id: User ID
            intent: Classified intent with entities

        Returns:
            Response about the sender
        """
        sender_name = intent.entities.get("sender_name")

        if not sender_name:
            return ConversationResponse(
                text="על מי אתה שואל?",
                suggestions=["דני מהבנק", "רואה החשבון", "הבוס"],
            )

        # Look up sender in memory
        if self._store:
            # Search for sender by name (fuzzy match would be nice but simple for now)
            profile = await self._store.get_sender_profile(sender_name)

            if profile:
                context = await self._store.get_sender_context_for_llm(sender_name)

                lines = [f"👤 מידע על {sender_name}:", ""]
                lines.append(context)

                return ConversationResponse(
                    text="\n".join(lines),
                    suggestions=["תראה מיילים ממנו", "תשלח לו הודעה"],
                )

            # Try to find similar senders
            frequent = await self._store.get_frequent_senders(limit=10)
            similar = [
                s for s in frequent
                if sender_name.lower() in (s.get("name", "") or "").lower()
                or sender_name.lower() in (s.get("email", "") or "").lower()
            ]

            if similar:
                names = [s.get("name") or s.get("email") for s in similar[:3]]
                return ConversationResponse(
                    text=f"לא מצאתי בדיוק את {sender_name}, אבל אולי התכוונת ל:\n"
                    + "\n".join(f"  • {n}" for n in names),
                    suggestions=names,
                )

        return ConversationResponse(
            text=f"לא מצאתי מידע על {sender_name} בזיכרון.",
            suggestions=["תראה שולחים תכופים", "תחפש לפי אימייל"],
        )

    async def _handle_action_request(
        self,
        user_id: str,
        intent: IntentResult,
    ) -> ConversationResponse:
        """Handle action request (reply, forward, etc).

        Args:
            user_id: User ID
            intent: Classified intent with action type

        Returns:
            Response requesting confirmation
        """
        action_type = intent.action_type

        if not action_type:
            return ConversationResponse(
                text="לא הבנתי איזו פעולה אתה רוצה. תנסה להיות יותר ספציפי.",
                suggestions=["שלח תשובה", "ארכב את המייל", "העבר למישהו"],
            )

        action_desc = get_action_description_hebrew(action_type)
        message_content = intent.entities.get("message_content")
        recipient = intent.entities.get("recipient")

        # Create pending action
        pending = PendingAction(
            action_type=action_type,
            message_content=message_content,
            details={
                "recipient": recipient,
                "raw_message": intent.raw_message,
            },
        )

        self._pending_actions[user_id] = pending

        # Build confirmation message
        confirm_text = f"🔔 פעולה לאישור: {action_desc}\n"

        if message_content:
            confirm_text += f"\n📝 תוכן ההודעה:\n\"{message_content}\"\n"

        if recipient:
            confirm_text += f"\n👤 נמען: {recipient}\n"

        confirm_text += "\nלאשר?"

        return ConversationResponse(
            text=confirm_text,
            requires_confirmation=True,
            action_to_confirm=action_type,
            action_details=pending.details,
            show_keyboard=True,
            keyboard_options=["✅ אשר", "❌ בטל"],
        )

    async def _handle_summary_request(
        self,
        user_id: str,
    ) -> ConversationResponse:
        """Handle summary request.

        Args:
            user_id: User ID

        Returns:
            Summary of recent emails
        """
        if not self._store:
            return ConversationResponse(
                text="הזיכרון לא מחובר. לא יכול לסכם.",
            )

        # Get VIP senders
        vips = await self._store.get_vip_senders()

        # Get frequent senders
        frequent = await self._store.get_frequent_senders(limit=5)

        lines = ["📬 סיכום התיבה:", ""]

        if vips:
            lines.append("⭐ שולחים חשובים:")
            for v in vips[:3]:
                name = v.get("name") or v.get("email", "")
                pending = v.get("pending_from_them", 0)
                if pending > 0:
                    lines.append(f"  • {name} - {pending} ממתינים")
                else:
                    lines.append(f"  • {name}")
            lines.append("")

        if frequent:
            lines.append("🔄 שולחים תכופים:")
            for f in frequent[:3]:
                name = f.get("name") or f.get("email", "")
                total = f.get("total_interactions", 0)
                lines.append(f"  • {name} ({total} הודעות)")

        return ConversationResponse(
            text="\n".join(lines),
            suggestions=["תראה מיילים חדשים", "מה דחוף?"],
        )

    async def _handle_inbox_status(
        self,
        user_id: str,
    ) -> ConversationResponse:
        """Handle inbox status request.

        Args:
            user_id: User ID

        Returns:
            Current inbox status
        """
        # In production, this would query the actual Gmail API
        # For now, return based on memory
        if not self._store:
            return ConversationResponse(
                text="צריך להפעיל את הסוכן כדי לקבל סטטוס.",
            )

        vips = await self._store.get_vip_senders()
        pending_from_vips = sum(v.get("pending_from_them", 0) for v in vips)

        lines = ["📊 סטטוס התיבה:", ""]

        if pending_from_vips > 0:
            lines.append(f"⚠️ {pending_from_vips} מיילים ממתינים משולחים חשובים")
        else:
            lines.append("✅ אין מיילים דחופים ממתינים")

        lines.append("")
        lines.append("💡 טיפ: כתוב 'תסכם' לסיכום מלא")

        return ConversationResponse(
            text="\n".join(lines),
            suggestions=["תסכם לי", "מה עם הבנק?", "תראה דחופים"],
        )

    def _handle_help_request(self) -> ConversationResponse:
        """Handle help request.

        Returns:
            Help message with available commands
        """
        help_text = """🤖 אני עוזר המיילים שלך!

אפשר לשאול אותי:
• "מה עם המייל מ[שם]?" - מידע על מייל
• "תזכיר לי על [שולח]" - היסטוריה עם שולח
• "תסכם לי" - סיכום התיבה
• "מה המצב?" - סטטוס דחופים

אפשר לבקש ממני:
• "שלח לו ש[תוכן]" - לשלוח תשובה
• "ארכב את זה" - לארכב מייל
• "סמן כחשוב" - לסמן מייל

כל פעולה דורשת אישור שלך! ✅"""

        return ConversationResponse(
            text=help_text,
            suggestions=["תסכם לי", "מה דחוף?", "מה עם הבנק?"],
        )

    async def _handle_general(
        self,
        user_id: str,
        intent: IntentResult,
    ) -> ConversationResponse:
        """Handle general/unclassified message.

        Args:
            user_id: User ID
            intent: Classified intent

        Returns:
            General response
        """
        # Check if there's context to work with
        if self._store:
            context = await self._store.get_conversation_context(user_id)
            if context and context.get("current_sender"):
                sender = context.get("current_sender")
                return ConversationResponse(
                    text=f"אני לא בטוח מה אתה רוצה. "
                    f"עדיין מדברים על {sender}?",
                    suggestions=[
                        f"כן, על {sender}",
                        "לא, נושא אחר",
                        "עזרה",
                    ],
                )

        return ConversationResponse(
            text="לא הבנתי. תנסה לשאול על מייל ספציפי, "
            "או כתוב 'עזרה' לרשימת האפשרויות.",
            suggestions=["עזרה", "תסכם לי", "מה דחוף?"],
        )

    async def _execute_action(
        self,
        user_id: str,
        action: PendingAction,
    ) -> ConversationResponse:
        """Execute confirmed action.

        Args:
            user_id: User ID
            action: Action to execute

        Returns:
            Result of action execution
        """
        action_desc = get_action_description_hebrew(action.action_type)

        # In production, this would call actual Gmail/MCP tools
        # For now, simulate success
        if action.action_type == ActionType.REPLY:
            return ConversationResponse(
                text=f"✅ נשלח בהצלחה!\n\n"
                f"📝 תוכן: \"{action.message_content or '(ריק)'}\"\n\n"
                f"💡 ההודעה נוספה לטיוטות לבדיקה.",
            )

        elif action.action_type == ActionType.ARCHIVE:
            return ConversationResponse(
                text="✅ המייל עבר לארכיון.",
            )

        elif action.action_type == ActionType.APPROVE:
            return ConversationResponse(
                text="✅ נשלח אישור.",
            )

        elif action.action_type == ActionType.REJECT:
            return ConversationResponse(
                text="✅ נשלחה דחייה.",
            )

        else:
            return ConversationResponse(
                text=f"✅ פעולה בוצעה: {action_desc}",
            )

    async def close(self) -> None:
        """Close memory store connection."""
        if self._store:
            await self._store.close()
        self._initialized = False
