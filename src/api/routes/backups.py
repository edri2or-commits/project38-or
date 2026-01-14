"""
API endpoints for database backup management.

Provides endpoints for:
- Creating backups
- Listing backups
- Verifying backup integrity
- Checking backup status

Based on Week 3 requirements from implementation-roadmap.md.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backups", tags=["backups"])


# Request/Response Models


class CreateBackupRequest(BaseModel):
    """Request body for creating a backup."""

    retention_days: int | None = Field(
        default=30, description="Number of days to retain backup", ge=1, le=365
    )
    verify: bool = Field(default=True, description="Whether to verify backup after creation")
    custom_backup_id: str | None = Field(default=None, description="Optional custom backup ID")


class BackupMetadataResponse(BaseModel):
    """Backup metadata response."""

    backup_id: str
    database_name: str
    created_at: str  # ISO 8601 format
    size_bytes: int
    size_mb: float
    checksum_sha256: str
    gcs_path: str
    pg_dump_version: str
    compression: str
    encrypted: bool
    verified: bool
    retention_days: int
    expiry_date: str  # ISO 8601 format


class CreateBackupResponse(BaseModel):
    """Response for backup creation."""

    success: bool
    backup_id: str | None = None
    metadata: BackupMetadataResponse | None = None
    error: str | None = None
    duration_seconds: float
    message: str


class VerifyBackupRequest(BaseModel):
    """Request body for verifying a backup."""

    backup_id: str = Field(description="Backup ID to verify")


class VerifyBackupResponse(BaseModel):
    """Response for backup verification."""

    success: bool
    backup_id: str
    verified: bool
    checksum_valid: bool
    gcs_path: str
    error: str | None = None
    message: str


class ListBackupsResponse(BaseModel):
    """Response for listing backups."""

    count: int
    backups: list[BackupMetadataResponse]


# Endpoints


@router.post(
    "/create",
    response_model=CreateBackupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create database backup",
    description="Create a new PostgreSQL backup with GCS upload and verification",
)
async def create_backup(request: CreateBackupRequest) -> CreateBackupResponse:
    """
    Create a new database backup.

    Steps:
    1. Run pg_dump to create SQL dump
    2. Compress with gzip
    3. Calculate SHA256 checksum
    4. Upload to GCP Cloud Storage
    5. Verify upload integrity
    6. Save metadata

    Args:
        request: Backup creation parameters

    Returns:
        Backup creation result with metadata

    Raises:
        HTTPException: If backup creation fails

    Example:
        ```
        POST /api/backups/create
        {
            "retention_days": 30,
            "verify": true
        }
        ```

        Response:
        ```json
        {
            "success": true,
            "backup_id": "backup-testdb-20260114-120000",
            "metadata": {
                "backup_id": "backup-testdb-20260114-120000",
                "database_name": "testdb",
                "created_at": "2026-01-14T12:00:00Z",
                "size_bytes": 52428800,
                "size_mb": 50.0,
                "checksum_sha256": "abc123...",
                "gcs_path": "gs://bucket/backups/backup-testdb-20260114-120000.sql.gz",
                "pg_dump_version": "PostgreSQL 15.3",
                "compression": "gzip",
                "encrypted": true,
                "verified": true,
                "retention_days": 30,
                "expiry_date": "2026-02-13T12:00:00Z"
            },
            "duration_seconds": 45.2,
            "message": "Backup created successfully"
        }
        ```
    """
    try:
        # Import here to avoid circular imports and slow startup
        from src.backup_manager import create_backup_manager

        logger.info(
            f"Creating backup: retention={request.retention_days}d, "
            f"verify={request.verify}, custom_id={request.custom_backup_id}"
        )

        # Create backup manager
        manager = create_backup_manager(retention_days=request.retention_days)

        # Create backup
        result = await manager.create_backup(
            backup_id=request.custom_backup_id,
            custom_retention_days=request.retention_days,
        )

        if not result.success:
            logger.error(f"Backup creation failed: {result.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Backup creation failed: {result.error}",
            )

        # Convert metadata to response model
        metadata_response = None
        if result.metadata:
            metadata_dict = result.metadata.to_dict()
            metadata_response = BackupMetadataResponse(**metadata_dict)

        logger.info(
            f"Backup created successfully: {result.backup_id} ({result.duration_seconds:.1f}s)"
        )

        return CreateBackupResponse(
            success=True,
            backup_id=result.backup_id,
            metadata=metadata_response,
            duration_seconds=result.duration_seconds,
            message="Backup created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating backup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        ) from e


@router.get(
    "",
    response_model=ListBackupsResponse,
    summary="List backups",
    description="List available database backups from GCS",
)
async def list_backups(
    limit: int = Query(
        default=100, description="Maximum number of backups to return", ge=1, le=1000
    ),
) -> ListBackupsResponse:
    """
    List available database backups.

    Returns backups sorted by creation date (newest first).

    Args:
        limit: Maximum number of backups to return (default: 100)

    Returns:
        List of backup metadata

    Example:
        ```
        GET /api/backups?limit=10
        ```

        Response:
        ```json
        {
            "count": 10,
            "backups": [
                {
                    "backup_id": "backup-testdb-20260114-120000",
                    "database_name": "testdb",
                    "created_at": "2026-01-14T12:00:00Z",
                    "size_mb": 50.0,
                    ...
                }
            ]
        }
        ```
    """
    try:
        from src.backup_manager import create_backup_manager

        logger.info(f"Listing backups: limit={limit}")

        manager = create_backup_manager()
        backups = await manager.list_backups(limit=limit)

        # Convert to response models
        backup_responses = [BackupMetadataResponse(**backup.to_dict()) for backup in backups]

        logger.info(f"Found {len(backup_responses)} backups")

        return ListBackupsResponse(count=len(backup_responses), backups=backup_responses)

    except Exception as e:
        logger.error(f"Error listing backups: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing backups: {str(e)}",
        ) from e


@router.post(
    "/verify",
    response_model=VerifyBackupResponse,
    summary="Verify backup",
    description="Verify backup integrity by checking file existence and checksum",
)
async def verify_backup(request: VerifyBackupRequest) -> VerifyBackupResponse:
    """
    Verify backup integrity.

    Checks:
    1. Backup file exists in GCS
    2. Checksum matches metadata

    Args:
        request: Backup verification parameters

    Returns:
        Verification result

    Raises:
        HTTPException: If verification fails

    Example:
        ```
        POST /api/backups/verify
        {
            "backup_id": "backup-testdb-20260114-120000"
        }
        ```

        Response:
        ```json
        {
            "success": true,
            "backup_id": "backup-testdb-20260114-120000",
            "verified": true,
            "checksum_valid": true,
            "gcs_path": "gs://bucket/backups/backup-testdb-20260114-120000.sql.gz",
            "message": "Backup verified successfully"
        }
        ```
    """
    try:
        from src.backup_manager import create_backup_manager

        logger.info(f"Verifying backup: {request.backup_id}")

        manager = create_backup_manager()

        # List backups and find the requested one
        backups = await manager.list_backups(limit=1000)
        backup = next((b for b in backups if b.backup_id == request.backup_id), None)

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup not found: {request.backup_id}",
            )

        # Verify using existing method
        verified = await manager._verify_gcs_upload(backup.gcs_path, backup.checksum_sha256)

        logger.info(f"Backup verification: {request.backup_id} -> {verified}")

        return VerifyBackupResponse(
            success=True,
            backup_id=request.backup_id,
            verified=verified,
            checksum_valid=verified,
            gcs_path=backup.gcs_path,
            message="Backup verified successfully" if verified else "Backup verification failed",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying backup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying backup: {str(e)}",
        ) from e


@router.get(
    "/health",
    summary="Backup system health",
    description="Check backup system health (BackupManager initialization)",
)
async def backup_health() -> dict:
    """
    Check backup system health.

    Verifies:
    - BackupManager can be initialized
    - Database URL is configured
    - GCS bucket is configured

    Returns:
        Health status

    Example:
        ```
        GET /api/backups/health
        ```

        Response:
        ```json
        {
            "status": "healthy",
            "database_configured": true,
            "gcs_bucket_configured": true,
            "message": "Backup system operational"
        }
        ```
    """
    try:
        from src.backup_manager import create_backup_manager

        # Try to initialize manager
        manager = create_backup_manager()

        return {
            "status": "healthy",
            "database_configured": bool(manager.database_url),
            "database_name": manager.database_name,
            "gcs_bucket_configured": bool(manager.gcs_bucket),
            "gcs_bucket": manager.gcs_bucket,
            "retention_days": manager.retention_days,
            "message": "Backup system operational",
        }

    except ValueError as e:
        # Configuration error
        logger.warning(f"Backup system configuration error: {e}")
        return {
            "status": "degraded",
            "database_configured": False,
            "gcs_bucket_configured": False,
            "error": str(e),
            "message": "Backup system not configured",
        }

    except Exception as e:
        logger.error(f"Backup system health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Backup system error",
        }
