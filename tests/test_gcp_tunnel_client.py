"""Tests for GCP Tunnel Client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.gcp_tunnel_client import GCPTunnelClient


class TestGCPTunnelClient:
    """Tests for GCPTunnelClient class."""

    @patch.dict("os.environ", {"MCP_TUNNEL_TOKEN": "test_token_123"})
    def test_init_with_env_token(self):
        """Test initialization with environment token."""
        client = GCPTunnelClient()
        assert client.token == "test_token_123"

    def test_init_with_explicit_token(self):
        """Test initialization with explicit token."""
        client = GCPTunnelClient(token="explicit_token")
        assert client.token == "explicit_token"

    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_token_raises(self):
        """Test that initialization without token raises ValueError."""
        # Clear any MCP_TUNNEL_TOKEN that might be set
        import os
        if "MCP_TUNNEL_TOKEN" in os.environ:
            del os.environ["MCP_TUNNEL_TOKEN"]

        with pytest.raises(ValueError, match="No MCP_TUNNEL_TOKEN found"):
            GCPTunnelClient()

    @patch("requests.post")
    def test_call_tool_success(self, mock_post):
        """Test successful tool call."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": '{"status": "healthy"}'}
                    ]
                }
            })
        }
        mock_post.return_value = mock_response

        client = GCPTunnelClient(token="test_token")
        result = client.call_tool("health_check")

        assert result == {"status": "healthy"}
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_list_tools(self, mock_post):
        """Test listing available tools."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {"name": "health_check", "description": "Check health"},
                        {"name": "railway_status", "description": "Get status"}
                    ]
                }
            })
        }
        mock_post.return_value = mock_response

        client = GCPTunnelClient(token="test_token")
        tools = client.list_tools()

        assert len(tools) == 2
        assert tools[0]["name"] == "health_check"

    @patch("requests.post")
    def test_health_check_convenience_method(self, mock_post):
        """Test health_check convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": '{"status": "healthy", "version": "0.1.0"}'}
                    ]
                }
            })
        }
        mock_post.return_value = mock_response

        client = GCPTunnelClient(token="test_token")
        health = client.health_check()

        assert health["status"] == "healthy"
        assert health["version"] == "0.1.0"

    @patch("requests.post")
    def test_railway_status_convenience_method(self, mock_post):
        """Test railway_status convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": '{"deployments": []}'}
                    ]
                }
            })
        }
        mock_post.return_value = mock_response

        client = GCPTunnelClient(token="test_token")
        status = client.railway_status()

        assert "deployments" in status

    def test_tunnel_url_constant(self):
        """Test that tunnel URL is correct."""
        assert (
            GCPTunnelClient.GCP_TUNNEL_URL ==
            "https://us-central1-project38-483612.cloudfunctions.net/mcp-router"
        )

    @patch("requests.post")
    def test_request_includes_auth_header(self, mock_post):
        """Test that requests include proper auth header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": '{"jsonrpc": "2.0", "id": 1, "result": {}}'}
        mock_post.return_value = mock_response

        client = GCPTunnelClient(token="my_secret_token")
        client.call_tool("test_tool")

        # Verify authorization header
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer my_secret_token"
