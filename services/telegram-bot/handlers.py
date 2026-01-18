"""Telegram message handlers.

This module contains handlers for Telegram commands and messages.
"""

import logging
from datetime import UTC, datetime

from config import get_settings
from database import async_session_maker
from litellm_client import LiteLLMClient
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

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
