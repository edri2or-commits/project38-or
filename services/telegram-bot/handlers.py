"""Telegram message handlers.

This module contains handlers for Telegram commands and messages.
"""

import logging
from datetime import UTC, datetime

from database import async_session_maker
from litellm_client import LiteLLMClient
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from config import get_settings
from models import ConversationMessage, ConversationStats

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize LiteLLM client
litellm_client = LiteLLMClient()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user

    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        f"I'm an AI assistant powered by multiple LLMs (Claude, GPT-4, Gemini) "
        f"via LiteLLM Gateway with automatic fallback.\n\n"
        f"🤖 Default model: {settings.default_model}\n"
        f"🔄 Auto-fallback: Enabled\n\n"
        f"Commands:\n"
        f"/start - Show this message\n"
        f"/generate <prompt> - Generate a response\n\n"
        f"Or just send me a message and I'll respond!"
    )

    await update.message.reply_text(welcome_message)

    # Save user interaction
    async with async_session_maker() as session:
        # Update or create stats
        result = await session.execute(
            select(ConversationStats).where(ConversationStats.user_id == user.id)
        )
        stats = result.scalar_one_or_none()

        if not stats:
            stats = ConversationStats(
                user_id=user.id,
                username=user.username,
                total_messages=1,
                first_interaction=datetime.now(UTC),
                last_interaction=datetime.now(UTC),
            )
            session.add(stats)
        else:
            stats.last_interaction = datetime.now(UTC)

        await session.commit()


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /generate command.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Extract prompt from command
    if not context.args:
        await update.message.reply_text(
            "Please provide a prompt. Example: /generate Tell me a joke"
        )
        return

    prompt = " ".join(context.args)

    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Generate response using LiteLLM Gateway
        messages = [{"role": "user", "content": prompt}]
        response_text, usage = await litellm_client.generate_response(messages)

        # Send response
        await update.message.reply_text(response_text)

        # Save to database
        await save_conversation(
            chat_id=chat_id,
            user_id=user.id,
            username=user.username,
            user_message=prompt,
            assistant_message=response_text,
            model=usage["model"],
            tokens_used=usage["total_tokens"],
        )

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        await update.message.reply_text("❌ Sorry, I encountered an error. Please try again later.")


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_message = update.message.text

    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Get conversation history
        conversation_history = await get_conversation_history(
            chat_id=chat_id,
            limit=settings.max_conversation_history,
        )

        # Add current message
        conversation_history.append({"role": "user", "content": user_message})

        # Generate response using LiteLLM Gateway
        response_text, usage = await litellm_client.generate_response(conversation_history)

        # Send response
        await update.message.reply_text(response_text)

        # Save to database
        await save_conversation(
            chat_id=chat_id,
            user_id=user.id,
            username=user.username,
            user_message=user_message,
            assistant_message=response_text,
            model=usage["model"],
            tokens_used=usage["total_tokens"],
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("❌ Sorry, I encountered an error. Please try again later.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    logger.error(f"Telegram error: {context.error}", exc_info=context.error)


async def get_conversation_history(chat_id: int, limit: int = 10) -> list[dict[str, str]]:
    """Get recent conversation history for a chat.

    Args:
        chat_id: Telegram chat ID
        limit: Maximum number of messages to retrieve

    Returns:
        List of messages in OpenAI format [{"role": "user", "content": "..."}, ...]
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.chat_id == chat_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()

        # Reverse to get chronological order
        messages = list(reversed(messages))

        # Convert to OpenAI format
        return [{"role": msg.role, "content": msg.content} for msg in messages]


async def save_conversation(
    chat_id: int,
    user_id: int,
    username: str | None,
    user_message: str,
    assistant_message: str,
    model: str,
    tokens_used: int,
) -> None:
    """Save conversation to database.

    Args:
        chat_id: Telegram chat ID
        user_id: Telegram user ID
        username: Telegram username
        user_message: User's message
        assistant_message: Assistant's response
        model: LLM model used
        tokens_used: Total tokens used
    """
    async with async_session_maker() as session:
        # Save user message
        user_msg = ConversationMessage(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            role="user",
            content=user_message,
        )
        session.add(user_msg)

        # Save assistant message
        assistant_msg = ConversationMessage(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            role="assistant",
            content=assistant_message,
            model=model,
            tokens_used=tokens_used,
        )
        session.add(assistant_msg)

        # Update stats
        result = await session.execute(
            select(ConversationStats).where(ConversationStats.user_id == user_id)
        )
        stats = result.scalar_one_or_none()

        if stats:
            stats.total_messages += 1
            stats.total_tokens += tokens_used
            stats.last_interaction = datetime.now(UTC)

            # Estimate cost (simplified - actual cost varies by model)
            # Claude Sonnet: $3/1M input, $15/1M output (avg ~$9/1M)
            stats.total_cost_usd += (tokens_used / 1_000_000) * 9
        else:
            # Create new stats if doesn't exist
            stats = ConversationStats(
                user_id=user_id,
                username=username,
                total_messages=1,
                total_tokens=tokens_used,
                total_cost_usd=(tokens_used / 1_000_000) * 9,
                first_interaction=datetime.now(UTC),
                last_interaction=datetime.now(UTC),
            )
            session.add(stats)

        await session.commit()


# =============================================================================
# Email Agent Handlers (Phase 4.12)
# =============================================================================

# Lazy import to avoid circular dependencies
_email_handler = None
_approval_manager = None
_email_agent_available = None


def _check_email_agent():
    """Check if email agent is available (lazy check)."""
    global _email_agent_available
    if _email_agent_available is None:
        try:
            from src.agents.smart_email.graph import run_smart_email_agent
            _email_agent_available = True
            logger.info("Smart Email Agent available")
        except ImportError as e:
            _email_agent_available = False
            logger.warning(f"Smart Email Agent not available: {e}")
    return _email_agent_available


def _get_email_handler():
    """Get or create email conversation handler (lazy initialization)."""
    global _email_handler
    if _email_handler is None:
        try:
            from src.agents.smart_email.conversation import ConversationHandler
            _email_handler = ConversationHandler()
            logger.info("Email ConversationHandler initialized")
        except ImportError as e:
            logger.warning(f"Email agent not available: {e}")
    return _email_handler


def _get_approval_manager():
    """Get or create approval manager (lazy initialization)."""
    global _approval_manager
    if _approval_manager is None:
        try:
            from src.agents.smart_email.actions import create_approval_manager
            _approval_manager = create_approval_manager()
            logger.info("ApprovalManager initialized")
        except ImportError as e:
            logger.warning(f"Approval manager not available: {e}")
    return _approval_manager


async def email_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /email command - run full email triage with LangGraph.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    chat_id = update.effective_chat.id

    if not _check_email_agent():
        await update.message.reply_text(
            "❌ Email agent not available. Missing dependencies."
        )
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Import and run the full email agent
        from src.agents.smart_email.graph import run_smart_email_agent

        # Run the full email scanning pipeline
        result = await run_smart_email_agent(
            hours=24,
            send_telegram=False,  # We'll send it ourselves
            enable_phase2=True,
            enable_memory=True,
        )

        # Get the formatted message
        message = result.get("telegram_message", "")
        if not message:
            message = "📬 לא נמצאו מיילים חדשים ב-24 השעות האחרונות."

        # Send to user (split if too long)
        if len(message) > 4096:
            # Telegram message limit is 4096 chars
            for i in range(0, len(message), 4096):
                await update.message.reply_text(
                    message[i:i+4096],
                    parse_mode="HTML",
                )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
            )

    except Exception as e:
        logger.error(f"Email command error: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ שגיאה בקריאת המיילים. נסה שוב מאוחר יותר."
        )


async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /inbox command - quick inbox status with counts.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    chat_id = update.effective_chat.id

    if not _check_email_agent():
        await update.message.reply_text(
            "❌ Email agent not available."
        )
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Import and run the email agent
        from src.agents.smart_email.graph import run_smart_email_agent

        # Run with phase2 disabled for faster response
        result = await run_smart_email_agent(
            hours=24,
            send_telegram=False,
            enable_phase2=False,  # Faster - no research/drafts
            enable_memory=False,
        )

        # Build quick summary
        total = result.get("total_count", 0)
        p1 = result.get("p1_count", 0)
        p2 = result.get("p2_count", 0)
        p3 = result.get("p3_count", 0)
        p4 = result.get("p4_count", 0)
        system = result.get("system_emails_count", 0)

        lines = [
            "📊 סטטוס התיבה (24 שעות):",
            "",
            f"📬 סה\"כ: {total} מיילים",
            f"🔴 דחוף (P1): {p1}",
            f"🟠 חשוב (P2): {p2}",
            f"🟡 מידע (P3): {p3}",
            f"⚪ נמוך (P4): {p4}",
            f"🔇 מערכת (מוסתר): {system}",
            "",
            "💡 כתוב /email לסקירה מלאה",
        ]

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Inbox command error: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ שגיאה בסיכום התיבה."
        )


async def email_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from email action buttons.

    Handles: approve:req_xxx, reject:req_xxx, edit:req_xxx
    """
    query = update.callback_query
    user = update.effective_user

    if not query.data:
        return

    # Parse callback data
    parts = query.data.split(":")
    if len(parts) != 2:
        return

    action, request_id = parts

    manager = _get_approval_manager()
    if manager is None:
        await query.answer("❌ Approval system unavailable")
        return

    try:
        if action == "approve":
            result = await manager.approve(request_id)
            await query.answer("✅ פעולה בוצעה!")
            await query.edit_message_text(
                f"{query.message.text}\n\n{result.to_hebrew()}"
            )

        elif action == "reject":
            manager.reject(request_id, reason="User rejected")
            await query.answer("❌ פעולה בוטלה")
            await query.edit_message_text(
                f"{query.message.text}\n\n❌ הפעולה בוטלה"
            )

        elif action == "edit":
            await query.answer("✏️ שלח את התוכן המעודכן")
            # Store pending edit state in context
            context.user_data["pending_edit"] = request_id

        else:
            await query.answer("Unknown action")

    except ValueError as e:
        await query.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.answer("❌ שגיאה בביצוע הפעולה")


def is_email_query(message: str) -> bool:
    """Check if message is an email-related query.

    Args:
        message: User message text

    Returns:
        True if message appears to be about email
    """
    email_keywords = [
        "מייל", "תיבה", "inbox", "email", "gmail",
        "שלח", "תענה", "תשלח", "העבר", "ארכב",
        "מי שלח", "מה עם", "לגבי המייל",
        "מיילים", "הודעות", "דואר",
    ]
    message_lower = message.lower()
    return any(kw in message_lower for kw in email_keywords)


def is_inbox_scan_query(message: str) -> bool:
    """Check if message requests a full inbox scan.

    Args:
        message: User message text

    Returns:
        True if message requests inbox scan/summary
    """
    scan_keywords = [
        "מה יש בתיבה", "תסרוק", "תבדוק מיילים", "סרוק",
        "מה חדש", "יש מיילים", "תראה מיילים",
        "check inbox", "scan email", "what's new",
        "מה בתיבה", "תסכם", "סיכום",
    ]
    message_lower = message.lower()
    return any(kw in message_lower for kw in scan_keywords)


async def smart_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Smart text handler that routes to email or general chat.

    Routes:
    - Inbox scan queries -> Full email agent (LangGraph)
    - Other email queries -> ConversationHandler
    - General queries -> LiteLLM

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_message = update.message.text

    # Check for pending edit action
    if context.user_data.get("pending_edit"):
        manager = _get_approval_manager()
        if manager:
            request_id = context.user_data.pop("pending_edit")
            try:
                result = await manager.approve(request_id, modified_content=user_message)
                await update.message.reply_text(result.to_hebrew())
                return
            except Exception as e:
                logger.error(f"Edit approval error: {e}")

    # Route inbox scan queries to full email agent
    if is_inbox_scan_query(user_message):
        if _check_email_agent():
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            try:
                from src.agents.smart_email.graph import run_smart_email_agent

                result = await run_smart_email_agent(
                    hours=24,
                    send_telegram=False,
                    enable_phase2=True,
                    enable_memory=True,
                )

                message = result.get("telegram_message", "")
                if not message:
                    message = "📬 לא נמצאו מיילים חדשים."

                if len(message) > 4096:
                    for i in range(0, len(message), 4096):
                        await update.message.reply_text(
                            message[i:i+4096],
                            parse_mode="HTML",
                        )
                else:
                    await update.message.reply_text(message, parse_mode="HTML")
                return

            except Exception as e:
                logger.error(f"Email agent error: {e}", exc_info=True)
                # Fall through to conversation handler

    # Route other email queries to conversation handler
    if is_email_query(user_message):
        handler = _get_email_handler()
        if handler:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

            try:
                response = await handler.process_message(
                    user_id=str(user.id),
                    chat_id=str(chat_id),
                    message=user_message,
                )

                # Check if action confirmation needed
                if response.requires_confirmation and response.show_keyboard:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                    manager = _get_approval_manager()
                    if manager:
                        # Create proposal
                        from src.agents.smart_email.actions import ActionType

                        action_type_map = {
                            "reply": ActionType.REPLY,
                            "forward": ActionType.FORWARD,
                            "archive": ActionType.ARCHIVE,
                        }
                        action_type = action_type_map.get(
                            response.action_to_confirm.value if response.action_to_confirm else "reply",
                            ActionType.REPLY
                        )

                        proposal = manager.create_proposal(
                            action_type=action_type,
                            user_id=str(user.id),
                            chat_id=str(chat_id),
                            **response.action_details,
                        )

                        # Build keyboard
                        keyboard = [
                            [
                                InlineKeyboardButton("✅ אשר", callback_data=f"approve:{proposal.id}"),
                                InlineKeyboardButton("❌ בטל", callback_data=f"reject:{proposal.id}"),
                            ]
                        ]
                        if action_type in (ActionType.REPLY, ActionType.FORWARD):
                            keyboard[0].append(
                                InlineKeyboardButton("✏️ ערוך", callback_data=f"edit:{proposal.id}")
                            )

                        reply_markup = InlineKeyboardMarkup(keyboard)
                        proposal_text = manager.format_proposal_hebrew(proposal)

                        await update.message.reply_text(
                            proposal_text,
                            reply_markup=reply_markup,
                            parse_mode="HTML",
                        )
                        return

                # Regular response
                await update.message.reply_text(
                    response.text,
                    parse_mode="HTML",
                )
                return

            except Exception as e:
                logger.error(f"Email handler error: {e}")
                # Fall through to general handler

    # Default: use general LiteLLM handler
    await text_message_handler(update, context)
