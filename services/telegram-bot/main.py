"""Telegram Bot service - FastAPI application.

This service receives Telegram webhooks and generates responses using LiteLLM Gateway.

Architecture:
    User → Telegram → This Service (webhook) → LiteLLM Gateway → Claude/GPT/Gemini
"""

import logging
from contextlib import asynccontextmanager

from config import get_settings, load_secrets_from_gcp
from database import check_database_connection, close_db_connection, create_db_and_tables
from fastapi import FastAPI, Request, Response
from handlers import error_handler, generate_command, start_command, text_message_handler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

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
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
