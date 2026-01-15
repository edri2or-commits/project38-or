"""Configuration for Google Workspace MCP Bridge."""

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkspaceConfig:
    """Configuration for Google Workspace MCP Bridge.

    Attributes:
        oauth_client_id: Google OAuth Client ID
        oauth_client_secret: Google OAuth Client Secret
        oauth_refresh_token: OAuth refresh token for API access
        bridge_token: Bearer token for authenticating MCP requests
        gcp_project_id: GCP project for Secret Manager
        scopes: OAuth scopes to request
    """

    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_refresh_token: str = ""
    bridge_token: str = ""
    gcp_project_id: str = "project38-483612"
    scopes: list[str] = field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/documents",
        ]
    )

    @classmethod
    def from_env(cls) -> "WorkspaceConfig":
        """Load configuration from environment variables.

        Returns:
            WorkspaceConfig with values from environment
        """
        return cls(
            oauth_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            oauth_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            oauth_refresh_token=os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", ""),
            bridge_token=os.getenv("WORKSPACE_MCP_BRIDGE_TOKEN", ""),
            gcp_project_id=os.getenv("GCP_PROJECT_ID", "project38-483612"),
        )

    @classmethod
    def from_gcp_secrets(cls) -> "WorkspaceConfig":
        """Load configuration from GCP Secret Manager.

        Returns:
            WorkspaceConfig with values from GCP secrets
        """
        try:
            from google.cloud import secretmanager

            client = secretmanager.SecretManagerServiceClient()
            project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")

            def get_secret(name: str) -> str:
                """Fetch a secret from GCP Secret Manager."""
                try:
                    secret_path = f"projects/{project_id}/secrets/{name}/versions/latest"
                    response = client.access_secret_version(name=secret_path)
                    return response.payload.data.decode("UTF-8")
                except Exception:
                    return ""

            return cls(
                oauth_client_id=get_secret("GOOGLE-OAUTH-CLIENT-ID"),
                oauth_client_secret=get_secret("GOOGLE-OAUTH-CLIENT-SECRET"),
                oauth_refresh_token=get_secret("GOOGLE-OAUTH-REFRESH-TOKEN"),
                bridge_token=get_secret("WORKSPACE-MCP-BRIDGE-TOKEN"),
                gcp_project_id=project_id,
            )
        except ImportError:
            return cls.from_env()

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary (without secrets).

        Returns:
            Dictionary with non-sensitive configuration
        """
        return {
            "gcp_project_id": self.gcp_project_id,
            "scopes": self.scopes,
            "has_oauth_client": bool(self.oauth_client_id),
            "has_oauth_secret": bool(self.oauth_client_secret),
            "has_refresh_token": bool(self.oauth_refresh_token),
            "has_bridge_token": bool(self.bridge_token),
        }
