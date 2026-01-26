"""Secrets health check API endpoints.

Provides endpoints for monitoring GCP Secret Manager health,
WIF authentication status, and token rotation operations.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


@router.get("/health")
async def get_secrets_health() -> dict[str, Any]:
    """Get comprehensive secrets health status.

    Returns:
        Health status including WIF authentication, metrics, and alerts.
    """
    try:
        from apps.business.core.secrets_health import get_wif_monitor

        monitor = get_wif_monitor()
        wif_health = await monitor.check_wif_health()
        health_report = monitor.get_health_report()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "wif": wif_health,
            "metrics": health_report["metrics"],
            "status": health_report["status"],
            "alerting": health_report["alerting"],
        }
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error": f"Health check failed: {type(e).__name__}",
            "status": "error",
        }


@router.get("/credentials")
async def get_credentials_health() -> dict[str, Any]:
    """Get health status of all managed credentials.

    Returns:
        Status of each credential type with expiration info.
    """
    try:
        from apps.business.core.credential_lifecycle import CredentialLifecycleManager

        manager = CredentialLifecycleManager()
        health = await manager.check_all_credentials()
        report = manager.get_expiration_report(health)
        await manager.close()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "all_healthy": health.all_healthy,
            "failed": [c.value for c in health.failed_credentials],
            "expiring_soon": [c.value for c in health.expiring_soon],
            "report": report,
        }
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error": f"Credential check failed: {type(e).__name__}",
            "all_healthy": False,
        }


@router.post("/credentials/refresh")
async def trigger_credential_refresh() -> dict[str, Any]:
    """Trigger credential health check and auto-refresh.

    Returns:
        Results of the refresh attempt.
    """
    try:
        from apps.business.core.credential_lifecycle import CredentialLifecycleManager

        manager = CredentialLifecycleManager()
        health = await manager.check_all_credentials()

        results = {}
        if health.failed_credentials:
            recovery_results = await manager.trigger_recovery(health.failed_credentials)
            results["recovery"] = {k.value: v for k, v in recovery_results.items()}

        if health.expiring_soon:
            results["refreshed"] = [c.value for c in health.expiring_soon]

        await manager.close()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "success": True,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Refresh failed: {type(e).__name__}",
        ) from e


@router.get("/rotation/history")
async def get_rotation_history(secret_name: str | None = None) -> dict[str, Any]:
    """Get token rotation history.

    Args:
        secret_name: Optional filter by secret name.

    Returns:
        List of rotation operations.
    """
    try:
        from apps.business.core.token_rotation import get_rotation_interlock

        interlock = get_rotation_interlock()
        history = interlock.get_rotation_history(secret_name)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(history),
            "history": history,
        }
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error": f"Failed to get history: {type(e).__name__}",
            "history": [],
        }


@router.post("/rotation/{secret_name}")
async def rotate_secret(secret_name: str, new_value: str) -> dict[str, Any]:
    """Rotate a secret with safety interlock.

    Args:
        secret_name: Name of the secret to rotate.
        new_value: New secret value.

    Returns:
        Rotation result with success/failure and version info.

    Note:
        This endpoint is protected and should only be called
        by authorized automation.
    """
    try:
        from apps.business.core.token_rotation import get_rotation_interlock

        interlock = get_rotation_interlock()
        result = await interlock.rotate_token(secret_name, new_value)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "success": result.success,
            "secret_name": result.secret_name,
            "old_version": result.old_version,
            "new_version": result.new_version,
            "state": result.state.value,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Rotation failed: {type(e).__name__}",
        ) from e


@router.post("/rotation/{secret_name}/rollback")
async def rollback_secret(secret_name: str, to_version: str) -> dict[str, Any]:
    """Rollback a secret to a previous version.

    Args:
        secret_name: Name of the secret.
        to_version: Version to rollback to.

    Returns:
        Rollback result.
    """
    try:
        from apps.business.core.token_rotation import get_rotation_interlock

        interlock = get_rotation_interlock()
        success = interlock.rollback(secret_name, to_version)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "secret_name": secret_name,
            "rolled_back_to": to_version if success else None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Rollback failed: {type(e).__name__}",
        ) from e
