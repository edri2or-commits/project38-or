"""Tests for src/api/routes/backups.py - Backup API Routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip all tests if fastapi not installed
pytest.importorskip("fastapi")


class TestBackupRequestModels:
    """Tests for backup request/response models."""

    def test_create_backup_request_import(self):
        """CreateBackupRequest should be importable."""
        from src.api.routes.backups import CreateBackupRequest

        assert CreateBackupRequest is not None

    def test_create_backup_request_defaults(self):
        """CreateBackupRequest should have sensible defaults."""
        from src.api.routes.backups import CreateBackupRequest

        request = CreateBackupRequest()
        assert request.retention_days == 30
        assert request.verify is True
        assert request.custom_backup_id is None

    def test_create_backup_request_custom(self):
        """CreateBackupRequest should accept custom values."""
        from src.api.routes.backups import CreateBackupRequest

        request = CreateBackupRequest(
            retention_days=60,
            verify=False,
            custom_backup_id="my-backup-123",
        )
        assert request.retention_days == 60
        assert request.verify is False
        assert request.custom_backup_id == "my-backup-123"

    def test_verify_backup_request(self):
        """VerifyBackupRequest should require backup_id."""
        from src.api.routes.backups import VerifyBackupRequest

        request = VerifyBackupRequest(backup_id="backup-test-001")
        assert request.backup_id == "backup-test-001"


class TestBackupResponseModels:
    """Tests for backup response models."""

    def test_backup_metadata_response(self):
        """BackupMetadataResponse should include all fields."""
        from src.api.routes.backups import BackupMetadataResponse

        response = BackupMetadataResponse(
            backup_id="backup-test-001",
            database_name="testdb",
            created_at="2026-01-15T12:00:00Z",
            size_bytes=52428800,
            size_mb=50.0,
            checksum_sha256="abc123def456",
            gcs_path="gs://bucket/backups/backup-test-001.sql.gz",
            pg_dump_version="PostgreSQL 15.3",
            compression="gzip",
            encrypted=True,
            verified=True,
            retention_days=30,
            expiry_date="2026-02-14T12:00:00Z",
        )
        assert response.backup_id == "backup-test-001"
        assert response.size_mb == 50.0
        assert response.encrypted is True

    def test_create_backup_response(self):
        """CreateBackupResponse should include success and metadata."""
        from src.api.routes.backups import CreateBackupResponse

        response = CreateBackupResponse(
            success=True,
            backup_id="backup-test-001",
            metadata=None,
            duration_seconds=45.2,
            message="Backup created",
        )
        assert response.success is True
        assert response.duration_seconds == 45.2

    def test_verify_backup_response(self):
        """VerifyBackupResponse should include verification results."""
        from src.api.routes.backups import VerifyBackupResponse

        response = VerifyBackupResponse(
            success=True,
            backup_id="backup-test-001",
            verified=True,
            checksum_valid=True,
            gcs_path="gs://bucket/backups/backup-test-001.sql.gz",
            message="Verified",
        )
        assert response.verified is True
        assert response.checksum_valid is True

    def test_list_backups_response(self):
        """ListBackupsResponse should include count and backups."""
        from src.api.routes.backups import ListBackupsResponse

        response = ListBackupsResponse(
            count=0,
            backups=[],
        )
        assert response.count == 0
        assert response.backups == []


class TestBackupRouterSetup:
    """Tests for backup router configuration."""

    def test_router_import(self):
        """Router should be importable."""
        from src.api.routes.backups import router

        assert router is not None

    def test_router_prefix(self):
        """Router should have /backups prefix."""
        from src.api.routes.backups import router

        assert router.prefix == "/backups"

    def test_router_tags(self):
        """Router should have backups tag."""
        from src.api.routes.backups import router

        assert "backups" in router.tags


class TestCreateBackupEndpoint:
    """Tests for POST /backups/create endpoint."""

    @pytest.mark.asyncio
    async def test_create_backup_success(self):
        """create_backup should return success response."""
        from src.api.routes.backups import CreateBackupRequest, create_backup

        # Mock the backup manager
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.backup_id = "backup-test-001"
        mock_result.duration_seconds = 10.5
        mock_result.metadata = None
        mock_result.error = None

        mock_manager = MagicMock()
        mock_manager.create_backup = AsyncMock(return_value=mock_result)

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            request = CreateBackupRequest(retention_days=30)
            response = await create_backup(request)

        assert response.success is True
        assert response.backup_id == "backup-test-001"

    @pytest.mark.asyncio
    async def test_create_backup_failure(self):
        """create_backup should raise HTTPException on failure."""
        from fastapi import HTTPException

        from src.api.routes.backups import CreateBackupRequest, create_backup

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Database connection failed"

        mock_manager = MagicMock()
        mock_manager.create_backup = AsyncMock(return_value=mock_result)

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            request = CreateBackupRequest()
            with pytest.raises(HTTPException) as exc_info:
                await create_backup(request)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_create_backup_with_metadata(self):
        """create_backup should include metadata in response."""
        from src.api.routes.backups import CreateBackupRequest, create_backup

        mock_metadata = MagicMock()
        mock_metadata.to_dict.return_value = {
            "backup_id": "backup-test-001",
            "database_name": "testdb",
            "created_at": "2026-01-15T12:00:00Z",
            "size_bytes": 1000,
            "size_mb": 0.001,
            "checksum_sha256": "abc123",
            "gcs_path": "gs://bucket/test",
            "pg_dump_version": "15.3",
            "compression": "gzip",
            "encrypted": True,
            "verified": True,
            "retention_days": 30,
            "expiry_date": "2026-02-14T12:00:00Z",
        }

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.backup_id = "backup-test-001"
        mock_result.duration_seconds = 10.5
        mock_result.metadata = mock_metadata

        mock_manager = MagicMock()
        mock_manager.create_backup = AsyncMock(return_value=mock_result)

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            request = CreateBackupRequest()
            response = await create_backup(request)

        assert response.metadata is not None
        assert response.metadata.backup_id == "backup-test-001"


class TestListBackupsEndpoint:
    """Tests for GET /backups endpoint."""

    @pytest.mark.asyncio
    async def test_list_backups_empty(self):
        """list_backups should return empty list when no backups."""
        from src.api.routes.backups import list_backups

        mock_manager = MagicMock()
        mock_manager.list_backups = AsyncMock(return_value=[])

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            response = await list_backups(limit=100)

        assert response.count == 0
        assert response.backups == []

    @pytest.mark.asyncio
    async def test_list_backups_with_data(self):
        """list_backups should return backup list."""
        from src.api.routes.backups import list_backups

        mock_backup = MagicMock()
        mock_backup.to_dict.return_value = {
            "backup_id": "backup-001",
            "database_name": "testdb",
            "created_at": "2026-01-15T12:00:00Z",
            "size_bytes": 1000,
            "size_mb": 0.001,
            "checksum_sha256": "abc123",
            "gcs_path": "gs://bucket/test",
            "pg_dump_version": "15.3",
            "compression": "gzip",
            "encrypted": True,
            "verified": True,
            "retention_days": 30,
            "expiry_date": "2026-02-14T12:00:00Z",
        }

        mock_manager = MagicMock()
        mock_manager.list_backups = AsyncMock(return_value=[mock_backup])

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            response = await list_backups(limit=10)

        assert response.count == 1
        assert len(response.backups) == 1

    @pytest.mark.asyncio
    async def test_list_backups_respects_limit(self):
        """list_backups should pass limit to manager."""
        from src.api.routes.backups import list_backups

        mock_manager = MagicMock()
        mock_manager.list_backups = AsyncMock(return_value=[])

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            await list_backups(limit=50)

        mock_manager.list_backups.assert_called_once_with(limit=50)


class TestVerifyBackupEndpoint:
    """Tests for POST /backups/verify endpoint."""

    @pytest.mark.asyncio
    async def test_verify_backup_success(self):
        """verify_backup should return verified status."""
        from src.api.routes.backups import VerifyBackupRequest, verify_backup

        mock_backup = MagicMock()
        mock_backup.backup_id = "backup-001"
        mock_backup.gcs_path = "gs://bucket/backup.sql.gz"
        mock_backup.checksum_sha256 = "abc123"

        mock_manager = MagicMock()
        mock_manager.list_backups = AsyncMock(return_value=[mock_backup])
        mock_manager._verify_gcs_upload = AsyncMock(return_value=True)

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            request = VerifyBackupRequest(backup_id="backup-001")
            response = await verify_backup(request)

        assert response.success is True
        assert response.verified is True
        assert response.checksum_valid is True

    @pytest.mark.asyncio
    async def test_verify_backup_not_found(self):
        """verify_backup should return 404 for unknown backup."""
        from fastapi import HTTPException

        from src.api.routes.backups import VerifyBackupRequest, verify_backup

        mock_manager = MagicMock()
        mock_manager.list_backups = AsyncMock(return_value=[])

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            request = VerifyBackupRequest(backup_id="nonexistent")
            with pytest.raises(HTTPException) as exc_info:
                await verify_backup(request)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_verify_backup_failed(self):
        """verify_backup should return verified=False on checksum mismatch."""
        from src.api.routes.backups import VerifyBackupRequest, verify_backup

        mock_backup = MagicMock()
        mock_backup.backup_id = "backup-001"
        mock_backup.gcs_path = "gs://bucket/backup.sql.gz"
        mock_backup.checksum_sha256 = "abc123"

        mock_manager = MagicMock()
        mock_manager.list_backups = AsyncMock(return_value=[mock_backup])
        mock_manager._verify_gcs_upload = AsyncMock(return_value=False)

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            request = VerifyBackupRequest(backup_id="backup-001")
            response = await verify_backup(request)

        assert response.verified is False
        assert response.checksum_valid is False


class TestBackupHealthEndpoint:
    """Tests for GET /backups/health endpoint."""

    @pytest.mark.asyncio
    async def test_backup_health_healthy(self):
        """backup_health should return healthy status."""
        from src.api.routes.backups import backup_health

        mock_manager = MagicMock()
        mock_manager.database_url = "postgresql://localhost/test"
        mock_manager.database_name = "test"
        mock_manager.gcs_bucket = "test-bucket"
        mock_manager.retention_days = 30

        with patch("src.backup_manager.create_backup_manager", return_value=mock_manager):
            response = await backup_health()

        assert response["status"] == "healthy"
        assert response["database_configured"] is True
        assert response["gcs_bucket_configured"] is True

    @pytest.mark.asyncio
    async def test_backup_health_config_error(self):
        """backup_health should return degraded on config error."""
        from src.api.routes.backups import backup_health

        with patch("src.backup_manager.create_backup_manager", side_effect=ValueError("Missing DATABASE_URL")):
            response = await backup_health()

        assert response["status"] == "degraded"
        assert response["database_configured"] is False

    @pytest.mark.asyncio
    async def test_backup_health_exception(self):
        """backup_health should return unhealthy on exception."""
        from src.api.routes.backups import backup_health

        with patch("src.backup_manager.create_backup_manager", side_effect=Exception("Connection failed")):
            response = await backup_health()

        assert response["status"] == "unhealthy"
        assert "error" in response
