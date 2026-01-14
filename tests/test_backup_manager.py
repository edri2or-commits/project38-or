"""
Tests for src/backup_manager.py.

Tests:
- BackupManager initialization
- Backup creation workflow
- Checksum validation
- GCS upload/download
- Backup listing
- Metadata handling
- Error scenarios

Uses mocking to avoid real PostgreSQL and GCS calls.
"""

import asyncio
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.backup_manager import (
    BackupManager,
    BackupMetadata,
    BackupResult,
    create_backup_manager,
)


# Fixtures


@pytest.fixture
def mock_database_url():
    """Mock PostgreSQL connection URL."""
    return "postgresql://user:pass@localhost:5432/testdb"


@pytest.fixture
def mock_gcs_bucket():
    """Mock GCS bucket name."""
    return "test-backups-bucket"


@pytest.fixture
def backup_manager(mock_database_url, mock_gcs_bucket):
    """Create BackupManager instance for testing."""
    return BackupManager(
        database_url=mock_database_url,
        gcs_bucket=mock_gcs_bucket,
        retention_days=30,
    )


@pytest.fixture
def sample_backup_metadata():
    """Sample backup metadata for testing."""
    return BackupMetadata(
        backup_id="backup-testdb-20260114-120000",
        database_name="testdb",
        created_at=datetime(2026, 1, 14, 12, 0, 0),
        size_bytes=1024 * 1024 * 50,  # 50MB
        checksum_sha256="a" * 64,
        gcs_path="gs://test-backups-bucket/backups/backup-testdb-20260114-120000.sql.gz",
        pg_dump_version="PostgreSQL 15.3",
        compression="gzip",
        encrypted=True,
        verified=True,
        retention_days=30,
    )


# BackupMetadata Tests


def test_backup_metadata_creation(sample_backup_metadata):
    """Test BackupMetadata dataclass initialization."""
    assert sample_backup_metadata.backup_id == "backup-testdb-20260114-120000"
    assert sample_backup_metadata.database_name == "testdb"
    assert sample_backup_metadata.size_bytes == 1024 * 1024 * 50


def test_backup_metadata_size_mb(sample_backup_metadata):
    """Test size_mb property calculation."""
    assert sample_backup_metadata.size_mb == 50.0


def test_backup_metadata_expiry_date(sample_backup_metadata):
    """Test expiry_date calculation."""
    expected_expiry = datetime(2026, 2, 13, 12, 0, 0)  # 30 days later
    assert sample_backup_metadata.expiry_date == expected_expiry


def test_backup_metadata_to_dict(sample_backup_metadata):
    """Test to_dict() method for JSON serialization."""
    data = sample_backup_metadata.to_dict()

    assert data["backup_id"] == "backup-testdb-20260114-120000"
    assert data["database_name"] == "testdb"
    assert data["size_bytes"] == 1024 * 1024 * 50
    assert data["size_mb"] == 50.0
    assert data["checksum_sha256"] == "a" * 64
    assert data["verified"] is True
    assert "created_at" in data
    assert "expiry_date" in data


# BackupManager Initialization Tests


def test_backup_manager_initialization(mock_database_url, mock_gcs_bucket):
    """Test BackupManager initialization."""
    manager = BackupManager(
        database_url=mock_database_url,
        gcs_bucket=mock_gcs_bucket,
        retention_days=30,
    )

    assert manager.database_url == mock_database_url
    assert manager.gcs_bucket == mock_gcs_bucket
    assert manager.retention_days == 30
    assert manager.database_name == "testdb"


def test_backup_manager_invalid_database_url():
    """Test BackupManager with invalid database URL."""
    with pytest.raises(ValueError, match="Invalid database_url"):
        BackupManager(database_url="invalid-url", gcs_bucket="test-bucket")


def test_backup_manager_missing_gcs_bucket(mock_database_url):
    """Test BackupManager with missing GCS bucket."""
    with pytest.raises(ValueError, match="gcs_bucket is required"):
        BackupManager(database_url=mock_database_url, gcs_bucket="")


def test_backup_manager_database_name_extraction(mock_database_url):
    """Test database name extraction from URL."""
    manager = BackupManager(
        database_url="postgresql://user:pass@host:5432/mydb?sslmode=require",
        gcs_bucket="bucket",
    )
    assert manager.database_name == "mydb"


# Backup Creation Tests


@pytest.mark.asyncio
async def test_create_backup_success(backup_manager):
    """Test successful backup creation."""
    with patch.object(
        backup_manager, "_run_pg_dump", new_callable=AsyncMock
    ) as mock_pg_dump, patch.object(
        backup_manager, "_compress_file", new_callable=AsyncMock
    ) as mock_compress, patch.object(
        backup_manager, "_calculate_checksum", new_callable=AsyncMock
    ) as mock_checksum, patch.object(
        backup_manager, "_get_pg_dump_version", new_callable=AsyncMock
    ) as mock_version, patch.object(
        backup_manager, "_upload_to_gcs", new_callable=AsyncMock
    ) as mock_upload, patch.object(
        backup_manager, "_verify_gcs_upload", new_callable=AsyncMock
    ) as mock_verify, patch.object(
        backup_manager, "_save_metadata", new_callable=AsyncMock
    ) as mock_save_metadata, patch.object(
        backup_manager, "_cleanup_temp_files"
    ) as mock_cleanup, patch(
        "src.backup_manager.Path.stat"
    ) as mock_stat, patch(
        "src.backup_manager.Path.mkdir"
    ):
        # Mock file stat
        mock_stat.return_value = Mock(st_size=1024 * 1024 * 50)  # 50MB

        # Mock checksum
        mock_checksum.return_value = "a" * 64

        # Mock version
        mock_version.return_value = "PostgreSQL 15.3"

        # Mock verification
        mock_verify.return_value = True

        # Run backup
        result = await backup_manager.create_backup(
            backup_id="test-backup-001", custom_retention_days=60
        )

        # Assertions
        assert result.success is True
        assert result.backup_id == "test-backup-001"
        assert result.metadata is not None
        assert result.metadata.size_mb == 50.0
        assert result.metadata.verified is True
        assert result.metadata.retention_days == 60
        assert result.error is None
        assert result.duration_seconds > 0

        # Verify method calls
        mock_pg_dump.assert_called_once()
        mock_compress.assert_called_once()
        mock_checksum.assert_called_once()
        mock_version.assert_called_once()
        mock_upload.assert_called_once()
        mock_verify.assert_called_once()
        mock_save_metadata.assert_called_once()
        mock_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_create_backup_with_generated_id(backup_manager):
    """Test backup creation with auto-generated ID."""
    with patch.object(
        backup_manager, "_run_pg_dump", new_callable=AsyncMock
    ), patch.object(
        backup_manager, "_compress_file", new_callable=AsyncMock
    ), patch.object(
        backup_manager, "_calculate_checksum", new_callable=AsyncMock
    ) as mock_checksum, patch.object(
        backup_manager, "_get_pg_dump_version", new_callable=AsyncMock
    ) as mock_version, patch.object(
        backup_manager, "_upload_to_gcs", new_callable=AsyncMock
    ), patch.object(
        backup_manager, "_verify_gcs_upload", new_callable=AsyncMock
    ) as mock_verify, patch.object(
        backup_manager, "_save_metadata", new_callable=AsyncMock
    ), patch.object(
        backup_manager, "_cleanup_temp_files"
    ), patch(
        "src.backup_manager.Path.stat"
    ) as mock_stat, patch(
        "src.backup_manager.Path.mkdir"
    ):
        mock_stat.return_value = Mock(st_size=1024 * 1024)
        mock_checksum.return_value = "b" * 64
        mock_version.return_value = "PostgreSQL 15.3"
        mock_verify.return_value = True

        result = await backup_manager.create_backup()

        assert result.success is True
        assert result.backup_id.startswith("backup-testdb-")
        assert len(result.backup_id) > len("backup-testdb-")


@pytest.mark.asyncio
async def test_create_backup_failure(backup_manager):
    """Test backup creation failure handling."""
    with patch.object(
        backup_manager, "_run_pg_dump", new_callable=AsyncMock
    ) as mock_pg_dump, patch("src.backup_manager.Path.mkdir"):
        # Simulate pg_dump failure
        mock_pg_dump.side_effect = RuntimeError("pg_dump not found")

        result = await backup_manager.create_backup()

        assert result.success is False
        assert result.error == "pg_dump not found"
        assert result.backup_id is None
        assert result.metadata is None


# Helper Method Tests


@pytest.mark.asyncio
async def test_run_pg_dump_success(backup_manager, tmp_path):
    """Test _run_pg_dump success."""
    output_file = tmp_path / "test.sql"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process

        await backup_manager._run_pg_dump(output_file)

        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0]
        assert args[0] == "pg_dump"
        assert str(output_file) in args


@pytest.mark.asyncio
async def test_run_pg_dump_failure(backup_manager, tmp_path):
    """Test _run_pg_dump failure."""
    output_file = tmp_path / "test.sql"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"pg_dump error")
        mock_subprocess.return_value = mock_process

        with pytest.raises(RuntimeError, match="pg_dump failed"):
            await backup_manager._run_pg_dump(output_file)


@pytest.mark.asyncio
async def test_compress_file_success(backup_manager, tmp_path):
    """Test _compress_file success."""
    input_file = tmp_path / "test.sql"
    output_file = tmp_path / "test.sql.gz"
    input_file.write_text("SELECT 1;")

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"\x1f\x8b\x08\x00", b"")  # gzip magic
        mock_subprocess.return_value = mock_process

        await backup_manager._compress_file(input_file, output_file)

        mock_subprocess.assert_called_once()
        assert output_file.exists()


@pytest.mark.asyncio
async def test_calculate_checksum(backup_manager, tmp_path):
    """Test _calculate_checksum."""
    test_file = tmp_path / "test.txt"
    test_content = b"Hello, World!"
    test_file.write_bytes(test_content)

    expected_checksum = hashlib.sha256(test_content).hexdigest()

    checksum = await backup_manager._calculate_checksum(test_file)

    assert checksum == expected_checksum


@pytest.mark.asyncio
async def test_get_pg_dump_version_success(backup_manager):
    """Test _get_pg_dump_version success."""
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"pg_dump (PostgreSQL) 15.3\n",
            b"",
        )
        mock_subprocess.return_value = mock_process

        version = await backup_manager._get_pg_dump_version()

        assert version == "pg_dump (PostgreSQL) 15.3"


@pytest.mark.asyncio
async def test_get_pg_dump_version_failure(backup_manager):
    """Test _get_pg_dump_version failure handling."""
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_subprocess.side_effect = Exception("Command not found")

        version = await backup_manager._get_pg_dump_version()

        assert version == "Unknown"


@pytest.mark.asyncio
async def test_upload_to_gcs_success(backup_manager, tmp_path):
    """Test _upload_to_gcs success."""
    local_file = tmp_path / "test.sql.gz"
    local_file.write_bytes(b"\x1f\x8b")
    gcs_path = "gs://bucket/test.sql.gz"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process

        await backup_manager._upload_to_gcs(local_file, gcs_path)

        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0]
        assert args[0] == "gsutil"
        assert gcs_path in args


@pytest.mark.asyncio
async def test_verify_gcs_upload_success(backup_manager):
    """Test _verify_gcs_upload success."""
    gcs_path = "gs://bucket/test.sql.gz"
    checksum = "a" * 64

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"gs://bucket/test.sql.gz\n", b"")
        mock_subprocess.return_value = mock_process

        verified = await backup_manager._verify_gcs_upload(gcs_path, checksum)

        assert verified is True


@pytest.mark.asyncio
async def test_verify_gcs_upload_failure(backup_manager):
    """Test _verify_gcs_upload failure."""
    gcs_path = "gs://bucket/test.sql.gz"
    checksum = "a" * 64

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Not found")
        mock_subprocess.return_value = mock_process

        verified = await backup_manager._verify_gcs_upload(gcs_path, checksum)

        assert verified is False


# Backup Listing Tests


@pytest.mark.asyncio
async def test_list_backups_success(backup_manager, sample_backup_metadata):
    """Test list_backups success."""
    with patch("asyncio.create_subprocess_exec") as mock_subprocess, patch.object(
        backup_manager, "_load_metadata", new_callable=AsyncMock
    ) as mock_load_metadata:
        # Mock gsutil ls
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"gs://bucket/backups/backup1.json\ngs://bucket/backups/backup2.json\n",
            b"",
        )
        mock_subprocess.return_value = mock_process

        # Mock metadata loading
        mock_load_metadata.return_value = sample_backup_metadata

        backups = await backup_manager.list_backups(limit=10)

        assert len(backups) == 2
        assert backups[0].backup_id == sample_backup_metadata.backup_id


@pytest.mark.asyncio
async def test_list_backups_no_backups(backup_manager):
    """Test list_backups when no backups exist."""
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"No URLs matched")
        mock_subprocess.return_value = mock_process

        backups = await backup_manager.list_backups()

        assert backups == []


@pytest.mark.asyncio
async def test_load_metadata_success(backup_manager, tmp_path):
    """Test _load_metadata success."""
    # Create sample metadata JSON
    metadata_dict = {
        "backup_id": "backup-test-001",
        "database_name": "testdb",
        "created_at": "2026-01-14T12:00:00",
        "size_bytes": 1024 * 1024,
        "checksum_sha256": "a" * 64,
        "gcs_path": "gs://bucket/backup-test-001.sql.gz",
        "pg_dump_version": "PostgreSQL 15.3",
        "retention_days": 30,
    }

    temp_json = tmp_path / "metadata.json"
    with open(temp_json, "w") as f:
        json.dump(metadata_dict, f)

    with patch("asyncio.create_subprocess_exec") as mock_subprocess, patch(
        "src.backup_manager.Path"
    ) as mock_path:
        # Mock gsutil cp
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process

        # Mock Path to use our temp_json
        mock_path_instance = Mock()
        mock_path_instance.__truediv__ = Mock(return_value=temp_json)
        mock_path.return_value = mock_path_instance

        with patch("builtins.open", side_effect=lambda path, *args, **kwargs: open(temp_json, *args, **kwargs)):
            metadata = await backup_manager._load_metadata("gs://bucket/metadata.json")

        assert metadata is not None
        assert metadata.backup_id == "backup-test-001"
        assert metadata.database_name == "testdb"


# Factory Function Tests


def test_create_backup_manager_with_params():
    """Test create_backup_manager with explicit parameters."""
    manager = create_backup_manager(
        database_url="postgresql://user:pass@host/db",
        gcs_bucket="test-bucket",
        retention_days=60,
    )

    assert manager.database_url == "postgresql://user:pass@host/db"
    assert manager.gcs_bucket == "test-bucket"
    assert manager.retention_days == 60


def test_create_backup_manager_with_env_vars():
    """Test create_backup_manager with environment variables."""
    import os

    os.environ["DATABASE_URL"] = "postgresql://user:pass@host/db"
    os.environ["GCS_BACKUP_BUCKET"] = "env-bucket"

    manager = create_backup_manager()

    assert manager.database_url == "postgresql://user:pass@host/db"
    assert manager.gcs_bucket == "env-bucket"

    # Cleanup
    del os.environ["DATABASE_URL"]
    del os.environ["GCS_BACKUP_BUCKET"]


def test_create_backup_manager_missing_database_url():
    """Test create_backup_manager without database URL."""
    import os

    # Ensure no env var set
    os.environ.pop("DATABASE_URL", None)

    with pytest.raises(ValueError, match="database_url required"):
        create_backup_manager()


# Cleanup Tests


def test_cleanup_temp_files(backup_manager, tmp_path):
    """Test _cleanup_temp_files."""
    temp_dir = tmp_path / "backup-temp"
    temp_dir.mkdir()
    (temp_dir / "test.sql").write_text("SELECT 1;")

    backup_manager._cleanup_temp_files(temp_dir)

    assert not temp_dir.exists()


def test_cleanup_temp_files_error_handling(backup_manager, tmp_path):
    """Test _cleanup_temp_files error handling."""
    # Try to cleanup non-existent directory
    non_existent_dir = tmp_path / "non-existent"

    # Should not raise exception
    backup_manager._cleanup_temp_files(non_existent_dir)
