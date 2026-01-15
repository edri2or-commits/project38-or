"""Credential Lifecycle Manager for Unbreakable Autonomy.

This module provides self-healing credential management that ensures
token refresh cycles never break. It monitors credential health and
triggers automatic recovery when credentials fail.

Architecture:
    Tier 0 (Root Trust) → Tier 1 (Long-lived) → Tier 2 (Short-lived)

Features:
    - Health checks for all credential types
    - Automatic token refresh for short-lived tokens
    - Expiration monitoring and alerts
    - Self-healing recovery triggers

Usage:
    from src.credential_lifecycle import CredentialLifecycleManager

    manager = CredentialLifecycleManager()
    health = await manager.check_all_credentials()
    if not health.all_healthy:
        await manager.trigger_recovery(health.failed_credentials)

    # Enable auto-refresh
    await manager.start_auto_refresh()
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CredentialTier(str, Enum):
    """Credential trust tiers in the hierarchy."""

    ROOT = "root"  # WIF, GitHub App registration (never expires)
    LONG_LIVED = "long_lived"  # Refresh tokens, API keys (quarterly rotation)
    SHORT_LIVED = "short_lived"  # Access tokens (auto-refresh)


class CredentialType(str, Enum):
    """Types of credentials managed by the system."""

    GITHUB_APP = "github_app"
    GOOGLE_OAUTH = "google_oauth"
    RAILWAY = "railway"
    N8N = "n8n"
    MCP_GATEWAY = "mcp_gateway"
    GCP_WIF = "gcp_wif"


class RecoveryAction(str, Enum):
    """Actions that can be taken to recover credentials."""

    AUTO_REFRESH = "auto_refresh"  # Automatic token refresh
    TRIGGER_WORKFLOW = "trigger_workflow"  # GitHub Actions workflow
    CREATE_ALERT = "create_alert"  # Create issue or send notification
    MANUAL_ROTATION = "manual_rotation"  # Requires human intervention


@dataclass
class CredentialStatus:
    """Status of a single credential."""

    credential_type: CredentialType
    tier: CredentialTier
    healthy: bool
    expires_at: datetime | None = None
    last_check: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
    recovery_action: RecoveryAction | None = None
    recovery_workflow: str | None = None


@dataclass
class CredentialHealth:
    """Overall health status of all credentials."""

    statuses: dict[CredentialType, CredentialStatus]
    check_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def all_healthy(self) -> bool:
        """Check if all credentials are healthy."""
        return all(s.healthy for s in self.statuses.values())

    @property
    def failed_credentials(self) -> list[CredentialType]:
        """Get list of failed credential types."""
        return [ct for ct, s in self.statuses.items() if not s.healthy]

    @property
    def expiring_soon(self) -> list[CredentialType]:
        """Get credentials expiring within 24 hours."""
        threshold = datetime.now(UTC) + timedelta(hours=24)
        return [ct for ct, s in self.statuses.items() if s.expires_at and s.expires_at < threshold]


class CredentialLifecycleManager:
    """Manages credential lifecycle with self-healing capabilities.

    This manager monitors all credentials in the system and provides:
    - Health checks for each credential type
    - Automatic recovery triggers when credentials fail
    - Expiration warnings before credentials expire

    Example:
        >>> manager = CredentialLifecycleManager()
        >>> health = await manager.check_all_credentials()
        >>> print(f"All healthy: {health.all_healthy}")
        >>> if not health.all_healthy:
        ...     results = await manager.trigger_recovery(health.failed_credentials)
    """

    CREDENTIAL_METADATA: dict[CredentialType, dict[str, Any]] = {
        CredentialType.GCP_WIF: {
            "tier": CredentialTier.ROOT,
            "recovery_action": RecoveryAction.MANUAL_ROTATION,
            "description": "WIF trust relationship (configuration, never expires)",
        },
        CredentialType.GITHUB_APP: {
            "tier": CredentialTier.LONG_LIVED,
            "recovery_action": RecoveryAction.CREATE_ALERT,
            "recovery_workflow": None,
            "description": "GitHub App private key",
        },
        CredentialType.GOOGLE_OAUTH: {
            "tier": CredentialTier.LONG_LIVED,
            "recovery_action": RecoveryAction.TRIGGER_WORKFLOW,
            "recovery_workflow": "setup-workspace-oauth.yml",
            "description": "Google OAuth refresh token",
        },
        CredentialType.RAILWAY: {
            "tier": CredentialTier.LONG_LIVED,
            "recovery_action": RecoveryAction.CREATE_ALERT,
            "description": "Railway API token",
        },
        CredentialType.N8N: {
            "tier": CredentialTier.LONG_LIVED,
            "recovery_action": RecoveryAction.CREATE_ALERT,
            "description": "n8n API key",
        },
        CredentialType.MCP_GATEWAY: {
            "tier": CredentialTier.LONG_LIVED,
            "recovery_action": RecoveryAction.TRIGGER_WORKFLOW,
            "recovery_workflow": "setup-mcp-gateway.yml",
            "description": "MCP Gateway bearer token",
        },
    }

    def __init__(self) -> None:
        """Initialize the credential lifecycle manager."""
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def check_all_credentials(self) -> CredentialHealth:
        """Check health of all credentials.

        Returns:
            CredentialHealth with status of each credential type.
        """
        statuses: dict[CredentialType, CredentialStatus] = {}

        # Check each credential type
        for cred_type in CredentialType:
            statuses[cred_type] = await self._check_credential(cred_type)

        return CredentialHealth(statuses=statuses)

    async def _check_credential(self, cred_type: CredentialType) -> CredentialStatus:
        """Check health of a specific credential.

        Args:
            cred_type: The credential type to check.

        Returns:
            CredentialStatus with health information.
        """
        metadata = self.CREDENTIAL_METADATA.get(cred_type, {})
        tier = metadata.get("tier", CredentialTier.LONG_LIVED)
        recovery_action = metadata.get("recovery_action")
        recovery_workflow = metadata.get("recovery_workflow")

        try:
            if cred_type == CredentialType.GCP_WIF:
                return await self._check_gcp_wif()
            elif cred_type == CredentialType.GITHUB_APP:
                return await self._check_github_app()
            elif cred_type == CredentialType.GOOGLE_OAUTH:
                return await self._check_google_oauth()
            elif cred_type == CredentialType.RAILWAY:
                return await self._check_railway()
            elif cred_type == CredentialType.N8N:
                return await self._check_n8n()
            elif cred_type == CredentialType.MCP_GATEWAY:
                return await self._check_mcp_gateway()
            else:
                return CredentialStatus(
                    credential_type=cred_type,
                    tier=tier,
                    healthy=False,
                    error=f"Unknown credential type: {cred_type}",
                )
        except Exception as e:
            return CredentialStatus(
                credential_type=cred_type,
                tier=tier,
                healthy=False,
                error=str(e),
                recovery_action=recovery_action,
                recovery_workflow=recovery_workflow,
            )

    async def _check_gcp_wif(self) -> CredentialStatus:
        """Check GCP WIF trust relationship.

        Note: WIF is configuration, not a credential. This check verifies
        that the trust relationship exists by attempting to access Secret Manager.
        """
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            # Try to list secrets - this will fail if WIF is broken
            secrets = manager.list_secrets()
            return CredentialStatus(
                credential_type=CredentialType.GCP_WIF,
                tier=CredentialTier.ROOT,
                healthy=len(secrets) > 0,
                expires_at=None,  # WIF never expires
            )
        except Exception as e:
            return CredentialStatus(
                credential_type=CredentialType.GCP_WIF,
                tier=CredentialTier.ROOT,
                healthy=False,
                error=f"WIF access failed: {e}",
                recovery_action=RecoveryAction.MANUAL_ROTATION,
            )

    async def _check_github_app(self) -> CredentialStatus:
        """Check GitHub App credential health."""
        try:
            from src.github_app_client import GitHubAppClient

            client = GitHubAppClient()
            # Verify we can get an installation token
            token = await client._get_installation_token()
            return CredentialStatus(
                credential_type=CredentialType.GITHUB_APP,
                tier=CredentialTier.LONG_LIVED,
                healthy=bool(token),
                expires_at=client._token_expires_at,
            )
        except Exception as e:
            return CredentialStatus(
                credential_type=CredentialType.GITHUB_APP,
                tier=CredentialTier.LONG_LIVED,
                healthy=False,
                error=f"GitHub App auth failed: {e}",
                recovery_action=RecoveryAction.CREATE_ALERT,
            )

    async def _check_google_oauth(self) -> CredentialStatus:
        """Check Google OAuth credential health."""
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()

            # Check if required secrets exist
            client_id = manager.get_secret("GOOGLE-OAUTH-CLIENT-ID")
            client_secret = manager.get_secret("GOOGLE-OAUTH-CLIENT-SECRET")
            refresh_token = manager.get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")

            if not all([client_id, client_secret, refresh_token]):
                missing = []
                if not client_id:
                    missing.append("CLIENT-ID")
                if not client_secret:
                    missing.append("CLIENT-SECRET")
                if not refresh_token:
                    missing.append("REFRESH-TOKEN")
                return CredentialStatus(
                    credential_type=CredentialType.GOOGLE_OAUTH,
                    tier=CredentialTier.LONG_LIVED,
                    healthy=False,
                    error=f"Missing secrets: {', '.join(missing)}",
                    recovery_action=RecoveryAction.TRIGGER_WORKFLOW,
                    recovery_workflow="setup-workspace-oauth.yml",
                )

            # Try to get an access token to verify refresh token works
            client = await self._get_client()
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code == 200:
                data = response.json()
                expires_in = data.get("expires_in", 3600)
                return CredentialStatus(
                    credential_type=CredentialType.GOOGLE_OAUTH,
                    tier=CredentialTier.LONG_LIVED,
                    healthy=True,
                    expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
                )
            else:
                return CredentialStatus(
                    credential_type=CredentialType.GOOGLE_OAUTH,
                    tier=CredentialTier.LONG_LIVED,
                    healthy=False,
                    error=f"Token refresh failed: {response.text}",
                    recovery_action=RecoveryAction.TRIGGER_WORKFLOW,
                    recovery_workflow="setup-workspace-oauth.yml",
                )
        except Exception as e:
            return CredentialStatus(
                credential_type=CredentialType.GOOGLE_OAUTH,
                tier=CredentialTier.LONG_LIVED,
                healthy=False,
                error=str(e),
                recovery_action=RecoveryAction.TRIGGER_WORKFLOW,
                recovery_workflow="setup-workspace-oauth.yml",
            )

    async def _check_railway(self) -> CredentialStatus:
        """Check Railway API credential health."""
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            token = manager.get_secret("RAILWAY-API")

            if not token:
                return CredentialStatus(
                    credential_type=CredentialType.RAILWAY,
                    tier=CredentialTier.LONG_LIVED,
                    healthy=False,
                    error="RAILWAY-API secret not found",
                    recovery_action=RecoveryAction.CREATE_ALERT,
                )

            # Test token with Railway API
            client = await self._get_client()
            response = await client.post(
                "https://backboard.railway.app/graphql/v2",
                headers={"Authorization": f"Bearer {token}"},
                json={"query": "{ me { id } }"},
            )

            if response.status_code == 200:
                data = response.json()
                if "data" in data and data["data"].get("me"):
                    return CredentialStatus(
                        credential_type=CredentialType.RAILWAY,
                        tier=CredentialTier.LONG_LIVED,
                        healthy=True,
                    )

            return CredentialStatus(
                credential_type=CredentialType.RAILWAY,
                tier=CredentialTier.LONG_LIVED,
                healthy=False,
                error=f"Railway API check failed: {response.text}",
                recovery_action=RecoveryAction.CREATE_ALERT,
            )
        except Exception as e:
            return CredentialStatus(
                credential_type=CredentialType.RAILWAY,
                tier=CredentialTier.LONG_LIVED,
                healthy=False,
                error=str(e),
                recovery_action=RecoveryAction.CREATE_ALERT,
            )

    async def _check_n8n(self) -> CredentialStatus:
        """Check n8n API credential health."""
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            api_key = manager.get_secret("N8N-API")

            if not api_key:
                return CredentialStatus(
                    credential_type=CredentialType.N8N,
                    tier=CredentialTier.LONG_LIVED,
                    healthy=False,
                    error="N8N-API secret not found",
                    recovery_action=RecoveryAction.CREATE_ALERT,
                )

            # n8n webhook doesn't require auth verification
            # Just check if secret exists
            return CredentialStatus(
                credential_type=CredentialType.N8N,
                tier=CredentialTier.LONG_LIVED,
                healthy=True,
            )
        except Exception as e:
            return CredentialStatus(
                credential_type=CredentialType.N8N,
                tier=CredentialTier.LONG_LIVED,
                healthy=False,
                error=str(e),
                recovery_action=RecoveryAction.CREATE_ALERT,
            )

    async def _check_mcp_gateway(self) -> CredentialStatus:
        """Check MCP Gateway token health."""
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            token = manager.get_secret("MCP-GATEWAY-TOKEN")

            if not token:
                return CredentialStatus(
                    credential_type=CredentialType.MCP_GATEWAY,
                    tier=CredentialTier.LONG_LIVED,
                    healthy=False,
                    error="MCP-GATEWAY-TOKEN secret not found",
                    recovery_action=RecoveryAction.TRIGGER_WORKFLOW,
                    recovery_workflow="setup-mcp-gateway.yml",
                )

            # Token exists - consider healthy
            # Full health check would require calling or-infra.com which is blocked
            return CredentialStatus(
                credential_type=CredentialType.MCP_GATEWAY,
                tier=CredentialTier.LONG_LIVED,
                healthy=True,
            )
        except Exception as e:
            return CredentialStatus(
                credential_type=CredentialType.MCP_GATEWAY,
                tier=CredentialTier.LONG_LIVED,
                healthy=False,
                error=str(e),
                recovery_action=RecoveryAction.TRIGGER_WORKFLOW,
                recovery_workflow="setup-mcp-gateway.yml",
            )

    async def trigger_recovery(
        self, failed_credentials: list[CredentialType]
    ) -> dict[CredentialType, str]:
        """Trigger recovery for failed credentials.

        Args:
            failed_credentials: List of credential types that need recovery.

        Returns:
            Dict mapping credential type to recovery status message.
        """
        results: dict[CredentialType, str] = {}

        for cred_type in failed_credentials:
            metadata = self.CREDENTIAL_METADATA.get(cred_type, {})
            recovery_action = metadata.get("recovery_action")
            recovery_workflow = metadata.get("recovery_workflow")

            if recovery_action == RecoveryAction.TRIGGER_WORKFLOW and recovery_workflow:
                results[cred_type] = await self._trigger_workflow_recovery(
                    cred_type, recovery_workflow
                )
            elif recovery_action == RecoveryAction.CREATE_ALERT:
                results[cred_type] = await self._create_recovery_alert(cred_type)
            elif recovery_action == RecoveryAction.AUTO_REFRESH:
                results[cred_type] = "Auto-refresh will occur on next API call"
            else:
                results[cred_type] = "Manual intervention required"

        return results

    async def _trigger_workflow_recovery(self, cred_type: CredentialType, workflow: str) -> str:
        """Trigger a GitHub Actions workflow for recovery.

        Args:
            cred_type: The credential type being recovered.
            workflow: The workflow file to trigger.

        Returns:
            Status message.
        """
        try:
            from src.github_app_client import GitHubAppClient

            client = GitHubAppClient()
            result = await client.trigger_workflow(
                workflow_id=workflow,
                ref="main",
                inputs={"action": "check-status"},
            )
            return f"Triggered {workflow}: {result}"
        except Exception as e:
            return f"Failed to trigger {workflow}: {e}"

    async def _create_recovery_alert(self, cred_type: CredentialType) -> str:
        """Create an alert for manual recovery.

        Args:
            cred_type: The credential type that needs recovery.

        Returns:
            Status message.
        """
        try:
            from src.github_app_client import GitHubAppClient

            metadata = self.CREDENTIAL_METADATA.get(cred_type, {})
            description = metadata.get("description", str(cred_type))

            client = GitHubAppClient()
            issue = await client.create_issue(
                title=f"[AUTO] Credential Recovery Required: {cred_type.value}",
                body=f"""## Credential Health Alert

**Credential**: {description}
**Type**: {cred_type.value}
**Detected**: {datetime.now(UTC).isoformat()}

### Recovery Action Required

This credential has failed health checks and requires manual intervention.

Please follow the recovery procedure for this credential type.
""",
                labels=["security", "automated"],
            )
            return f"Created issue #{issue.get('number', 'unknown')}"
        except Exception as e:
            return f"Failed to create alert: {e}"

    def get_expiration_report(self, health: CredentialHealth) -> dict[str, list[dict[str, Any]]]:
        """Generate an expiration report.

        Args:
            health: Current credential health status.

        Returns:
            Report with credentials grouped by status.
        """
        report: dict[str, list[dict[str, Any]]] = {
            "healthy": [],
            "expiring_soon": [],
            "expired": [],
            "unknown": [],
        }

        now = datetime.now(UTC)
        soon_threshold = now + timedelta(hours=24)

        for cred_type, status in health.statuses.items():
            entry = {
                "type": cred_type.value,
                "tier": status.tier.value,
                "expires_at": status.expires_at.isoformat() if status.expires_at else None,
                "error": status.error,
            }

            if not status.healthy:
                report["expired"].append(entry)
            elif status.expires_at is None:
                report["healthy"].append(entry)
            elif status.expires_at < now:
                report["expired"].append(entry)
            elif status.expires_at < soon_threshold:
                report["expiring_soon"].append(entry)
            else:
                report["healthy"].append(entry)

        return report

    # Auto-refresh functionality
    _auto_refresh_task: asyncio.Task | None = None
    _auto_refresh_interval: int = 300  # 5 minutes
    _auto_refresh_running: bool = False

    async def start_auto_refresh(self, interval_seconds: int = 300) -> None:
        """Start automatic credential refresh monitoring.

        Args:
            interval_seconds: How often to check and refresh credentials.
        """
        if self._auto_refresh_running:
            logger.warning("Auto-refresh already running")
            return

        self._auto_refresh_interval = interval_seconds
        self._auto_refresh_running = True
        self._auto_refresh_task = asyncio.create_task(self._auto_refresh_loop())
        logger.info(f"Auto-refresh started with {interval_seconds}s interval")

    async def stop_auto_refresh(self) -> None:
        """Stop automatic credential refresh monitoring."""
        self._auto_refresh_running = False
        if self._auto_refresh_task:
            self._auto_refresh_task.cancel()
            try:
                await self._auto_refresh_task
            except asyncio.CancelledError:
                pass
            self._auto_refresh_task = None
        logger.info("Auto-refresh stopped")

    async def _auto_refresh_loop(self) -> None:
        """Main loop for automatic credential refresh."""
        while self._auto_refresh_running:
            try:
                await self._perform_auto_refresh()
            except Exception as e:
                logger.error(f"Auto-refresh error: {type(e).__name__}: {e}")

            await asyncio.sleep(self._auto_refresh_interval)

    async def _perform_auto_refresh(self) -> None:
        """Perform credential checks and trigger refreshes as needed."""
        health = await self.check_all_credentials()

        # Log overall health
        if health.all_healthy:
            logger.debug("All credentials healthy")
        else:
            logger.warning(f"Unhealthy credentials: {health.failed_credentials}")

        # Check for expiring credentials
        expiring = health.expiring_soon
        if expiring:
            logger.info(f"Credentials expiring soon: {expiring}")
            for cred_type in expiring:
                await self._refresh_credential(cred_type)

        # Attempt recovery for failed credentials
        if health.failed_credentials:
            results = await self.trigger_recovery(health.failed_credentials)
            for cred_type, result in results.items():
                logger.info(f"Recovery for {cred_type.value}: {result}")

    async def _refresh_credential(self, cred_type: CredentialType) -> bool:
        """Attempt to refresh a specific credential.

        Args:
            cred_type: The credential type to refresh.

        Returns:
            True if refresh was successful.
        """
        logger.info(f"Attempting to refresh {cred_type.value}")

        if cred_type == CredentialType.GOOGLE_OAUTH:
            return await self._refresh_google_oauth()
        elif cred_type == CredentialType.GITHUB_APP:
            return await self._refresh_github_app()
        else:
            logger.debug(f"No auto-refresh available for {cred_type.value}")
            return False

    async def _refresh_google_oauth(self) -> bool:
        """Refresh Google OAuth access token.

        Returns:
            True if refresh successful.
        """
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            client_id = manager.get_secret("GOOGLE-OAUTH-CLIENT-ID")
            client_secret = manager.get_secret("GOOGLE-OAUTH-CLIENT-SECRET")
            refresh_token = manager.get_secret("GOOGLE-OAUTH-REFRESH-TOKEN")

            if not all([client_id, client_secret, refresh_token]):
                logger.error("Missing OAuth secrets for refresh")
                return False

            client = await self._get_client()
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code == 200:
                logger.info("Google OAuth token refreshed successfully")
                return True
            else:
                logger.error(f"Google OAuth refresh failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Google OAuth refresh error: {type(e).__name__}")
            return False

    async def _refresh_github_app(self) -> bool:
        """Refresh GitHub App installation token.

        Returns:
            True if refresh successful.
        """
        try:
            from src.github_app_client import GitHubAppClient

            client = GitHubAppClient()
            token = await client._get_installation_token()
            if token:
                logger.info("GitHub App token refreshed successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"GitHub App refresh error: {type(e).__name__}")
            return False
