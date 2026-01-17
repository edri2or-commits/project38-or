"""Configuration management for Telegram Bot service.

This module handles environment variables and GCP Secret Manager integration.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and GCP Secret Manager.

    Attributes:
        app_name: Application name
        debug: Debug mode flag
        port: HTTP port for FastAPI
        telegram_bot_token: Telegram Bot API token
        telegram_webhook_url: Public webhook URL
        telegram_webhook_path: Webhook endpoint path
        litellm_gateway_url: LiteLLM Gateway base URL
        database_url: PostgreSQL connection string
        gcp_project_id: GCP project ID for Secret Manager
        max_conversation_history: Maximum messages to keep in context
        default_model: Default LLM model to use
        max_tokens: Maximum tokens per response
    """

    # Application
    app_name: str = "Telegram Bot"
    debug: bool = False
    port: int = 8000

    # Telegram
    telegram_bot_token: str = ""  # Loaded from GCP Secret Manager
    telegram_webhook_url: str = ""  # e.g., https://telegram-bot.railway.app
    telegram_webhook_path: str = "/webhook"

    # LiteLLM Gateway
    litellm_gateway_url: str = "https://litellm-gateway-production-0339.up.railway.app"
    default_model: str = "claude-sonnet"
    max_tokens: int = 1000

    # Database
    database_url: str = ""  # Provided by Railway

    # GCP
    gcp_project_id: str = "project38-483612"

    # Conversation settings
    max_conversation_history: int = 10  # Last N messages to include in context

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Application settings

    Example:
        >>> settings = get_settings()
        >>> print(settings.litellm_gateway_url)
    """
    return Settings()


def load_secrets_from_gcp() -> None:
    """Load secrets from GCP Secret Manager into environment variables.

    This function should be called at application startup before creating Settings.
    It loads the Telegram bot token from GCP Secret Manager.

    Environment variables set:
        - TELEGRAM_BOT_TOKEN: from GCP secret "TELEGRAM-BOT-TOKEN"
    """
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        project_id = os.environ.get("GCP_PROJECT_ID", "project38-483612")

        # Load Telegram bot token
        secret_name = f"projects/{project_id}/secrets/TELEGRAM-BOT-TOKEN/versions/latest"
        try:
            response = client.access_secret_version(request={"name": secret_name})
            token = response.payload.data.decode("UTF-8")
            os.environ["TELEGRAM_BOT_TOKEN"] = token
            print("✅ Loaded TELEGRAM_BOT_TOKEN from GCP Secret Manager")
        except Exception as e:
            print(f"⚠️  Failed to load TELEGRAM_BOT_TOKEN: {e}")

    except ImportError:
        print("⚠️  google-cloud-secret-manager not installed, skipping GCP secrets")
    except Exception as e:
        print(f"⚠️  Error loading secrets from GCP: {e}")
