"""Tests for MCP Gateway configuration.

Tests the config module in src/mcp_gateway/config.py.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def _has_cryptography() -> bool:
    """Check if cryptography module is available."""
    try:
        import _cffi_backend
        import cryptography.hazmat.primitives
        return True
    except (ImportError, ModuleNotFoundError):
        return False
    except Exception:
        return False


def _can_import_config() -> bool:
    """Check if config module can be imported."""
    try:
        from src.mcp_gateway.config import MCPGatewayConfig, clear_config, get_config
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _can_import_config(),
        reason="mcp_gateway.config module not importable"
    ),
    pytest.mark.skipif(
        not _has_cryptography(),
        reason="cryptography module not available (required by SecretManager)"
    ),
]


class TestMCPGatewayConfig:
    """Tests for MCPGatewayConfig dataclass."""

    def test_config_has_required_fields(self):
        """Test that config dataclass has all required fields."""
        from src.mcp_gateway.config import MCPGatewayConfig

        config = MCPGatewayConfig(
            railway_token="rt",
            railway_service_id="rsid",
            railway_environment_id="reid",
            railway_project_id="rpid",
            n8n_base_url="http://n8n",
            n8n_api_key="n8k",
            gateway_token="gt",
            production_url="https://prod",
        )

        assert config.railway_token == "rt"
        assert config.railway_service_id == "rsid"
        assert config.railway_environment_id == "reid"
        assert config.railway_project_id == "rpid"
        assert config.n8n_base_url == "http://n8n"
        assert config.n8n_api_key == "n8k"
        assert config.gateway_token == "gt"
        assert config.production_url == "https://prod"

    def test_config_has_github_relay_defaults(self):
        """Test that config has default values for GitHub relay fields."""
        from src.mcp_gateway.config import MCPGatewayConfig

        config = MCPGatewayConfig(
            railway_token="rt",
            railway_service_id="rsid",
            railway_environment_id="reid",
            railway_project_id="rpid",
            n8n_base_url="http://n8n",
            n8n_api_key="n8k",
            gateway_token="gt",
            production_url="https://prod",
        )

        # Default values
        assert config.github_app_id == ""
        assert config.github_installation_id == ""
        assert config.github_private_key == ""
        assert config.github_relay_repo == "edri2or-commits/project38-or"
        assert config.github_relay_issue == 183


class TestGetConfig:
    """Tests for get_config function."""

    def setup_method(self):
        """Clear config cache before each test."""
        from src.mcp_gateway.config import clear_config
        clear_config()

    def teardown_method(self):
        """Clear config cache after each test."""
        from src.mcp_gateway.config import clear_config
        clear_config()

    def test_get_config_with_env_vars_fallback(self):
        """Test that get_config falls back to environment variables."""
        import src.mcp_gateway.config as config_module
        from src.mcp_gateway.config import clear_config, get_config

        env_vars = {
            "RAILWAY_API_TOKEN": "env-railway-token",
            "N8N_API_KEY": "env-n8n-key",
            "MCP_GATEWAY_TOKEN": "env-gateway-token",
            "RAILWAY_SERVICE_ID": "env-service-id",
            "RAILWAY_ENVIRONMENT_ID": "env-env-id",
            "RAILWAY_PROJECT_ID": "env-project-id",
            "N8N_BASE_URL": "http://env-n8n.local",
            "PRODUCTION_URL": "https://env-prod.local",
        }

        # Patch the import inside get_config to raise an exception
        with patch.dict(os.environ, env_vars, clear=False):
            with patch.object(config_module, "SecretManager", side_effect=Exception("No GCP"), create=True):
                # Force re-import by clearing cache
                clear_config()
                config = get_config()

        assert config.railway_token == "env-railway-token"
        assert config.n8n_api_key == "env-n8n-key"
        assert config.gateway_token == "env-gateway-token"

    def test_get_config_caches_result(self):
        """Test that get_config caches the configuration."""
        import src.mcp_gateway.config as config_module
        from src.mcp_gateway.config import clear_config, get_config

        clear_config()
        with patch.dict(os.environ, {"RAILWAY_API_TOKEN": "cached", "N8N_API_KEY": "k", "MCP_GATEWAY_TOKEN": "t"}):
            with patch.object(config_module, "SecretManager", side_effect=Exception("No GCP"), create=True):
                config1 = get_config()
                config2 = get_config()

        # Should be the same object (cached)
        assert config1 is config2

    def test_clear_config_clears_cache(self):
        """Test that clear_config clears the cached configuration."""
        import src.mcp_gateway.config as config_module
        from src.mcp_gateway.config import clear_config, get_config

        clear_config()
        with patch.dict(os.environ, {"RAILWAY_API_TOKEN": "first", "N8N_API_KEY": "k", "MCP_GATEWAY_TOKEN": "t"}):
            with patch.object(config_module, "SecretManager", side_effect=Exception("No GCP"), create=True):
                config1 = get_config()

        clear_config()

        with patch.dict(os.environ, {"RAILWAY_API_TOKEN": "second", "N8N_API_KEY": "k", "MCP_GATEWAY_TOKEN": "t"}):
            with patch.object(config_module, "SecretManager", side_effect=Exception("No GCP"), create=True):
                config2 = get_config()

        # Should be different objects after clear
        assert config1 is not config2
        assert config1.railway_token == "first"
        assert config2.railway_token == "second"


class TestLoadConfigAlias:
    """Tests for load_config alias."""

    def test_load_config_is_alias_for_get_config(self):
        """Test that load_config is an alias for get_config."""
        from src.mcp_gateway.config import get_config, load_config

        assert load_config is get_config
