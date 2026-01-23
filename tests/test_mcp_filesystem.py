"""Tests for MCP Filesystem module.

Tests the sandboxed filesystem module in src/mcp/filesystem.py.
Covers:
- FilesystemTool enum
- FilesystemResult dataclass
- FilesystemServer initialization and operations
- Sandbox security (path traversal prevention)
- File operations (read, write, list, delete)
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest


class TestFilesystemTool:
    """Tests for FilesystemTool enum."""

    def test_filesystem_tool_values(self):
        """Test that FilesystemTool has expected values."""
        from src.mcp.filesystem import FilesystemTool

        assert FilesystemTool.READ_FILE == "read_file"
        assert FilesystemTool.WRITE_FILE == "write_file"
        assert FilesystemTool.LIST_FILES == "list_files"
        assert FilesystemTool.DELETE_FILE == "delete_file"
        assert FilesystemTool.CREATE_DIR == "create_dir"
        assert FilesystemTool.FILE_INFO == "file_info"


class TestFilesystemResult:
    """Tests for FilesystemResult dataclass."""

    def test_default_values(self):
        """Test that FilesystemResult initializes with correct defaults."""
        from src.mcp.filesystem import FilesystemResult

        result = FilesystemResult(tool="read_file", success=True)

        assert result.tool == "read_file"
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.path is None
        assert result.duration == 0.0
        assert result.timestamp is not None

    def test_timestamp_auto_set(self):
        """Test that timestamp is auto-set on initialization."""
        from src.mcp.filesystem import FilesystemResult

        before = datetime.now(UTC)
        result = FilesystemResult(tool="read_file", success=True)
        after = datetime.now(UTC)

        assert before <= result.timestamp <= after

    def test_to_dict(self):
        """Test that to_dict returns correct structure."""
        from src.mcp.filesystem import FilesystemResult

        result = FilesystemResult(
            tool="write_file",
            success=True,
            data={"size": 1024},
            path="/tmp/test.txt",
            duration=0.5,
        )

        data = result.to_dict()

        assert data["tool"] == "write_file"
        assert data["success"] is True
        assert data["data"] == {"size": 1024}
        assert data["error"] is None
        assert data["path"] == "/tmp/test.txt"
        assert data["duration"] == 0.5
        assert "timestamp" in data

    def test_to_dict_with_error(self):
        """Test to_dict includes error message."""
        from src.mcp.filesystem import FilesystemResult

        result = FilesystemResult(
            tool="read_file",
            success=False,
            error="File not found",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["error"] == "File not found"


class TestFilesystemServer:
    """Tests for FilesystemServer class."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    def test_init(self, temp_workspace):
        """Test server initialization."""
        from src.mcp.filesystem import FilesystemServer

        server = FilesystemServer(agent_id=42, base_path=temp_workspace)

        assert server.agent_id == 42
        assert server.base_path == temp_workspace
        assert server.sandbox_path == temp_workspace / "agent_42"
        assert server.sandbox_path.exists()

    def test_sandbox_root_property(self, server):
        """Test sandbox_root property."""
        assert server.sandbox_root == server.sandbox_path

    def test_resolve_path_valid(self, server):
        """Test _resolve_path with valid relative path."""
        resolved = server._resolve_path("test/file.txt")

        assert resolved == server.sandbox_path / "test" / "file.txt"

    def test_resolve_path_absolute_rejected(self, server):
        """Test _resolve_path rejects absolute paths."""
        with pytest.raises(ValueError, match="escapes sandbox"):
            server._resolve_path("/etc/passwd")

    def test_resolve_path_traversal_rejected(self, server):
        """Test _resolve_path rejects path traversal."""
        with pytest.raises(ValueError, match="escapes sandbox"):
            server._resolve_path("../../../etc/passwd")

    def test_resolve_path_nested_valid(self, server):
        """Test _resolve_path handles nested paths correctly."""
        # Nested path within sandbox should work
        resolved = server._resolve_path("data/subdir/file.txt")

        # Should be within sandbox
        assert str(resolved).startswith(str(server.sandbox_path))
        assert resolved == server.sandbox_path / "data" / "subdir" / "file.txt"


class TestFilesystemRead:
    """Tests for file read operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_read_file_success(self, server):
        """Test successful file read."""
        from src.mcp.filesystem import FilesystemTool

        # Create test file
        test_file = server.sandbox_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = await server.read_file("test.txt")

        assert result.success is True
        assert result.tool == FilesystemTool.READ_FILE
        assert result.data == "Hello, World!"
        assert result.duration > 0

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, server):
        """Test read file that doesn't exist."""
        result = await server.read_file("nonexistent.txt")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_read_file_is_directory(self, server):
        """Test read file that is a directory."""
        # Create test directory
        test_dir = server.sandbox_path / "testdir"
        test_dir.mkdir()

        result = await server.read_file("testdir")

        assert result.success is False
        assert "not a file" in result.error.lower()

    @pytest.mark.asyncio
    async def test_read_file_too_large(self, server):
        """Test read file that exceeds size limit."""
        # Create large file
        test_file = server.sandbox_path / "large.txt"
        test_file.write_bytes(b"x" * (server.MAX_FILE_SIZE + 1))

        result = await server.read_file("large.txt")

        assert result.success is False
        assert "too large" in result.error.lower()


class TestFilesystemWrite:
    """Tests for file write operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_write_file_success(self, server):
        """Test successful file write."""
        from src.mcp.filesystem import FilesystemTool

        result = await server.write_file("output.txt", "Test content")

        assert result.success is True
        assert result.tool == FilesystemTool.WRITE_FILE
        assert result.data["size"] > 0

        # Verify file exists
        assert (server.sandbox_path / "output.txt").read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_write_file_creates_directories(self, server):
        """Test write creates parent directories."""
        result = await server.write_file("deep/nested/path/file.txt", "Content")

        assert result.success is True
        assert (server.sandbox_path / "deep/nested/path/file.txt").exists()

    @pytest.mark.asyncio
    async def test_write_file_no_overwrite(self, server):
        """Test write fails when overwrite=False and file exists."""
        # Create existing file
        test_file = server.sandbox_path / "existing.txt"
        test_file.write_text("Original")

        result = await server.write_file("existing.txt", "New content", overwrite=False)

        assert result.success is False
        assert "exists" in result.error.lower()

    @pytest.mark.asyncio
    async def test_write_file_overwrite(self, server):
        """Test write overwrites when overwrite=True."""
        # Create existing file
        test_file = server.sandbox_path / "existing.txt"
        test_file.write_text("Original")

        result = await server.write_file("existing.txt", "New content", overwrite=True)

        assert result.success is True
        assert test_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_write_file_too_large(self, server):
        """Test write fails for content too large."""
        large_content = "x" * (server.MAX_FILE_SIZE + 1)

        result = await server.write_file("large.txt", large_content)

        assert result.success is False
        assert "too large" in result.error.lower()


class TestFilesystemList:
    """Tests for file list operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_list_files_empty(self, server):
        """Test list empty directory."""
        from src.mcp.filesystem import FilesystemTool

        result = await server.list_files()

        assert result.success is True
        assert result.tool == FilesystemTool.LIST_FILES
        assert result.data == []

    @pytest.mark.asyncio
    async def test_list_files_with_content(self, server):
        """Test list directory with files."""
        # Create test files
        (server.sandbox_path / "file1.txt").write_text("content1")
        (server.sandbox_path / "file2.txt").write_text("content2")
        (server.sandbox_path / "subdir").mkdir()

        result = await server.list_files()

        assert result.success is True
        assert len(result.data) == 3

        names = [f["name"] for f in result.data]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_list_files_with_pattern(self, server):
        """Test list with glob pattern."""
        # Create test files
        (server.sandbox_path / "test.txt").write_text("content")
        (server.sandbox_path / "test.json").write_text("{}")
        (server.sandbox_path / "other.txt").write_text("other")

        result = await server.list_files(pattern="*.txt")

        assert result.success is True
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_list_files_not_found(self, server):
        """Test list nonexistent directory."""
        result = await server.list_files("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_files_not_directory(self, server):
        """Test list path that is a file."""
        # Create file
        (server.sandbox_path / "file.txt").write_text("content")

        result = await server.list_files("file.txt")

        assert result.success is False
        assert "not a directory" in result.error.lower()


class TestFilesystemDelete:
    """Tests for file delete operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_delete_file_success(self, server):
        """Test successful file delete."""
        from src.mcp.filesystem import FilesystemTool

        # Create file
        test_file = server.sandbox_path / "to_delete.txt"
        test_file.write_text("content")

        result = await server.delete_file("to_delete.txt")

        assert result.success is True
        assert result.tool == FilesystemTool.DELETE_FILE
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, server):
        """Test delete nonexistent file."""
        result = await server.delete_file("nonexistent.txt")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_delete_directory_non_recursive(self, server):
        """Test delete directory without recursive."""
        # Create directory with content
        test_dir = server.sandbox_path / "dir_with_content"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        result = await server.delete_file("dir_with_content", recursive=False)

        assert result.success is False
        assert "not empty" in result.error.lower() or "recursive" in result.error.lower()

    @pytest.mark.asyncio
    async def test_delete_directory_recursive(self, server):
        """Test delete directory with recursive=True."""
        # Create directory with content
        test_dir = server.sandbox_path / "dir_to_delete"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        (test_dir / "subdir").mkdir()

        result = await server.delete_file("dir_to_delete", recursive=True)

        assert result.success is True
        assert not test_dir.exists()


class TestFilesystemCreateDir:
    """Tests for directory creation operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_create_dir_success(self, server):
        """Test successful directory creation."""
        from src.mcp.filesystem import FilesystemTool

        result = await server.create_dir("new_directory")

        assert result.success is True
        assert result.tool == FilesystemTool.CREATE_DIR
        assert (server.sandbox_path / "new_directory").is_dir()

    @pytest.mark.asyncio
    async def test_create_dir_nested(self, server):
        """Test create nested directory."""
        result = await server.create_dir("deep/nested/directory")

        assert result.success is True
        assert (server.sandbox_path / "deep/nested/directory").is_dir()

    @pytest.mark.asyncio
    async def test_create_dir_exists(self, server):
        """Test create directory that already exists."""
        # Create directory
        (server.sandbox_path / "existing").mkdir()

        result = await server.create_dir("existing")

        assert result.success is True  # exist_ok=True


class TestFilesystemFileInfo:
    """Tests for file info operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_file_info_success(self, server):
        """Test successful file info."""
        from src.mcp.filesystem import FilesystemTool

        # Create file
        test_file = server.sandbox_path / "info_test.txt"
        test_file.write_text("content")

        result = await server.file_info("info_test.txt")

        assert result.success is True
        assert result.tool == FilesystemTool.FILE_INFO
        assert result.data["name"] == "info_test.txt"
        assert result.data["is_file"] is True
        assert result.data["is_dir"] is False
        assert result.data["size"] > 0
        assert "modified" in result.data
        assert "created" in result.data

    @pytest.mark.asyncio
    async def test_file_info_directory(self, server):
        """Test file info for directory."""
        # Create directory
        (server.sandbox_path / "test_dir").mkdir()

        result = await server.file_info("test_dir")

        assert result.success is True
        assert result.data["is_dir"] is True
        assert result.data["is_file"] is False

    @pytest.mark.asyncio
    async def test_file_info_not_found(self, server):
        """Test file info for nonexistent file."""
        result = await server.file_info("nonexistent.txt")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestFilesystemCleanup:
    """Tests for sandbox cleanup operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_cleanup_sandbox(self, server):
        """Test sandbox cleanup."""
        # Create files
        (server.sandbox_path / "file1.txt").write_text("content1")
        (server.sandbox_path / "subdir").mkdir()
        (server.sandbox_path / "subdir/file2.txt").write_text("content2")

        result = await server.cleanup_sandbox()

        assert result is True
        assert server.sandbox_path.exists()
        assert list(server.sandbox_path.iterdir()) == []

    @pytest.mark.asyncio
    async def test_cleanup_empty_sandbox(self, server):
        """Test cleanup when sandbox is already empty."""
        result = await server.cleanup_sandbox()

        assert result is True


class TestFilesystemSecurity:
    """Tests for security features."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def server(self, temp_workspace):
        """Create filesystem server with temp workspace."""
        from src.mcp.filesystem import FilesystemServer

        return FilesystemServer(agent_id=1, base_path=temp_workspace)

    @pytest.mark.asyncio
    async def test_cannot_read_outside_sandbox(self, server):
        """Test reading outside sandbox fails."""
        result = await server.read_file("../../../etc/passwd")

        assert result.success is False
        assert "escapes sandbox" in result.error.lower()

    @pytest.mark.asyncio
    async def test_cannot_write_outside_sandbox(self, server):
        """Test writing outside sandbox fails."""
        result = await server.write_file("../../../tmp/malicious.txt", "bad")

        assert result.success is False
        assert "escapes sandbox" in result.error.lower()

    @pytest.mark.asyncio
    async def test_cannot_list_outside_sandbox(self, server):
        """Test listing outside sandbox fails."""
        result = await server.list_files("../../../etc")

        assert result.success is False
        assert "escapes sandbox" in result.error.lower()

    @pytest.mark.asyncio
    async def test_cannot_delete_outside_sandbox(self, server):
        """Test deleting outside sandbox fails."""
        result = await server.delete_file("../../../tmp/test.txt")

        assert result.success is False
        assert "escapes sandbox" in result.error.lower()

    def test_max_file_size_constant(self, server):
        """Test MAX_FILE_SIZE is set."""
        assert server.MAX_FILE_SIZE == 10 * 1024 * 1024  # 10MB
