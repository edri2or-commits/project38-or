"""Telegram Bot service - FastAPI application.

This service receives Telegram webhooks and generates responses using LiteLLM Gateway.

Architecture:
    User → Telegram → This Service (webhook) → LiteLLM Gateway → Claude/GPT/Gemini
"""

import logging
from contextlib import asynccontextmanager

from database import check_database_connection, close_db_connection, create_db_and_tables
from fastapi import FastAPI, Request, Response
from handlers import (
    error_handler,
    generate_command,
    start_command,
    text_message_handler,
    # Email agent handlers (Phase 4.12)
    email_command,
    inbox_command,
    email_callback_handler,
    smart_text_handler,
)
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config import get_settings, load_secrets_from_gcp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load secrets from GCP Secret Manager
load_secrets_from_gcp()

# Get settings
settings = get_settings()

# Global variable for Telegram application
telegram_app: Application | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan events - startup and shutdown.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("🚀 Starting Telegram Bot service...")

    # Create database tables
    await create_db_and_tables()

    # Initialize Telegram bot application
    global telegram_app
    telegram_app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .updater(None)  # No updater needed for webhook mode
        .build()
    )

    # Register handlers
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("generate", generate_command))
    # Email agent commands (Phase 4.12)
    telegram_app.add_handler(CommandHandler("email", email_command))
    telegram_app.add_handler(CommandHandler("inbox", inbox_command))
    # Use smart handler that routes email queries to ConversationHandler
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_text_handler))
    # Callback handler for action approval buttons
    telegram_app.add_handler(CallbackQueryHandler(email_callback_handler))
    telegram_app.add_error_handler(error_handler)

    # Initialize bot
    await telegram_app.initialize()
    await telegram_app.start()

    logger.info("✅ Telegram Bot service started")
    logger.info(f"📍 LiteLLM Gateway: {settings.litellm_gateway_url}")
    logger.info(f"🤖 Default model: {settings.default_model}")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Telegram Bot service...")
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()
    await close_db_connection()
    logger.info("✅ Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Telegram Bot Service",
    description="Multi-LLM Telegram bot using LiteLLM Gateway",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict:
    """Root endpoint.

    Returns:
        dict: Service information
    """
    return {
        "service": "Telegram Bot",
        "version": "0.1.0",
        "status": "running",
        "litellm_gateway": settings.litellm_gateway_url,
        "default_model": settings.default_model,
    }


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint.

    Returns:
        dict: Health status of service and dependencies
    """
    db_healthy = await check_database_connection()

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "bot_configured": bool(settings.telegram_bot_token),
        "litellm_gateway": settings.litellm_gateway_url,
    }


@app.get("/debug/routes")
async def debug_routes() -> dict:
    """Debug endpoint to list all registered routes.

    Returns:
        dict: List of all routes with their methods and paths
    """
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": route.name,
            })
    return {
        "webhook_path_setting": settings.telegram_webhook_path,
        "routes": routes,
    }


@app.post(settings.telegram_webhook_path)
async def telegram_webhook(request: Request) -> Response:
    """Telegram webhook endpoint.

    This endpoint receives updates from Telegram and processes them.

    Args:
        request: FastAPI request object with JSON body

    Returns:
        Response: Empty 200 OK response
    """
    try:
        # Parse Telegram update
        update_dict = await request.json()
        update = Update.de_json(update_dict, telegram_app.bot)

        # Process update
        await telegram_app.process_update(update)

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return Response(status_code=200)  # Always return 200 to avoid retries


@app.post("/webhook/setup")
async def setup_webhook() -> dict:
    """Setup Telegram webhook (for manual configuration).

    Returns:
        dict: Webhook setup result
    """
    try:
        webhook_url = f"{settings.telegram_webhook_url}{settings.telegram_webhook_path}"
        await telegram_app.bot.set_webhook(url=webhook_url)

        logger.info(f"✅ Webhook configured: {webhook_url}")

        return {
            "status": "success",
            "webhook_url": webhook_url,
        }
    except Exception as e:
        logger.error(f"Failed to setup webhook: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@app.get("/webhook/info")
async def webhook_info() -> dict:
    """Get current webhook configuration.

    Returns:
        dict: Webhook information
    """
    try:
        webhook = await telegram_app.bot.get_webhook_info()

        return {
            "url": webhook.url,
            "pending_update_count": webhook.pending_update_count,
            "last_error_date": webhook.last_error_date,
            "last_error_message": webhook.last_error_message,
        }
    except Exception as e:
        logger.error(f"Failed to get webhook info: {e}")
        return {
            "error": str(e),
        }


@app.post("/send")
async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> dict:
    """Send a proactive message to a user.

    This endpoint enables Night Watch and other services to send
    notifications to users without waiting for incoming messages.

    Args:
        chat_id: Telegram chat ID to send message to
        text: Message text (supports HTML formatting)
        parse_mode: Parse mode for formatting (HTML or Markdown)

    Returns:
        dict: Send result with message_id
    """
    try:
        message = await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )

        logger.info(f"Sent proactive message to chat_id={chat_id}")

        return {
            "status": "sent",
            "message_id": message.message_id,
            "chat_id": chat_id,
        }
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "chat_id": chat_id,
        }


@app.get("/chats")
async def list_chats() -> dict:
    """List all known chat IDs from conversation history.

    Returns chat IDs that have interacted with the bot,
    useful for Night Watch to know who to send summaries to.

    Returns:
        dict: List of unique chat_ids
    """
    from database import get_session
    from sqlmodel import select

    from models import ConversationMessage

    try:
        async with get_session() as session:
            result = await session.execute(
                select(ConversationMessage.chat_id).distinct()
            )
            chat_ids = [row[0] for row in result.fetchall()]

        return {
            "count": len(chat_ids),
            "chat_ids": chat_ids,
        }
    except Exception as e:
        logger.error(f"Failed to list chats: {e}")
        return {
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
