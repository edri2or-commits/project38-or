"""
Configuration management for MCP Gateway.

Loads credentials from GCP Secret Manager and environment variables.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPGatewayConfig:
    """MCP Gateway configuration."""

    railway_token: str
    railway_service_id: str
    railway_environment_id: str
    railway_project_id: str
    n8n_base_url: str
    n8n_api_key: str
    gateway_token: str
    production_url: str
    # GitHub Relay configuration
    github_app_id: str = ""
    github_installation_id: str = ""
    github_private_key: str = ""
    github_relay_repo: str = "edri2or-commits/project38-or"
    github_relay_issue: int = 183


_config: MCPGatewayConfig | None = None


def get_config() -> MCPGatewayConfig:
    """
    Load configuration from GCP Secret Manager and environment.

    Returns:
        MCPGatewayConfig with all required credentials.

    Raises:
        RuntimeError: If required secrets cannot be loaded.
    """
    global _config

    if _config is not None:
        return _config

    # Try to load from GCP Secret Manager
    try:
        from src.secrets_manager import SecretManager

        manager = SecretManager()

        railway_token = manager.get_secret("RAILWAY-API")
        n8n_api_key = manager.get_secret("N8N-API")
        gateway_token = manager.get_secret("MCP-GATEWAY-TOKEN")
        github_private_key = manager.get_secret("github-app-private-key")

        if railway_token and n8n_api_key and gateway_token:
            logger.info("Successfully loaded secrets from GCP Secret Manager")
        else:
            missing = []
            if not railway_token:
                missing.append("RAILWAY-API")
            if not n8n_api_key:
                missing.append("N8N-API")
            if not gateway_token:
                missing.append("MCP-GATEWAY-TOKEN")
            logger.warning(f"Missing secrets in GCP: {', '.join(missing)}")

    except Exception as e:
        # Log the actual error to help debug GCP authentication issues
        logger.warning(
            f"GCP Secret Manager access failed: {type(e).__name__}. "
            "Falling back to environment variables. "
            "This may indicate WIF authentication issues."
        )
        railway_token = os.environ.get("RAILWAY_API_TOKEN", "")
        n8n_api_key = os.environ.get("N8N_API_KEY", "")
        gateway_token = os.environ.get("MCP_GATEWAY_TOKEN", "")
        github_private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")

        if not railway_token or not n8n_api_key or not gateway_token:
            logger.error(
                "Environment variable fallback also missing secrets. "
                "MCP Gateway tools may not function correctly."
            )

    _config = MCPGatewayConfig(
        railway_token=railway_token,
        railway_service_id=os.environ.get("RAILWAY_SERVICE_ID", ""),
        railway_environment_id=os.environ.get(
            "RAILWAY_ENVIRONMENT_ID", "99c99a18-aea2-4d01-9360-6a93705102a0"
        ),
        railway_project_id=os.environ.get(
            "RAILWAY_PROJECT_ID", "95ec21cc-9ada-41c5-8485-12f9a00e0116"
        ),
        n8n_base_url=os.environ.get("N8N_BASE_URL", ""),
        n8n_api_key=n8n_api_key,
        gateway_token=gateway_token,
        production_url=os.environ.get("PRODUCTION_URL", "https://or-infra.com"),
        # GitHub Relay configuration
        github_app_id=os.environ.get("GITHUB_APP_ID", "2497877"),
        github_installation_id=os.environ.get("GITHUB_INSTALLATION_ID", "100231961"),
        github_private_key=github_private_key,
        github_relay_repo=os.environ.get(
            "GITHUB_RELAY_REPO", "edri2or-commits/project38-or"
        ),
        github_relay_issue=int(os.environ.get("GITHUB_RELAY_ISSUE", "183")),
    )

    return _config


def clear_config() -> None:
    """Clear cached configuration (for testing)."""
    global _config
    _config = None
