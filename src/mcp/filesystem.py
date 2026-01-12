"""Filesystem MCP Server - Sandboxed file operations for agents.

Provides safe file read/write operations with strict sandboxing.
Each agent gets isolated workspace at /workspace/{agent_id}/.
"""

import asyncio
import hashlib
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FilesystemTool(str, Enum):
    """Available filesystem tools."""

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    LIST_FILES = "list_files"
    DELETE_FILE = "delete_file"
    CREATE_DIR = "create_dir"
    FILE_INFO = "file_info"


@dataclass
class FilesystemResult:
    """Result from filesystem operation.

    Attributes:
        tool: Tool that was used
        success: Whether operation succeeded
        data: Operation result (file content, file list, etc.)
        error: Error message if failed
        path: Absolute path of file/directory
        duration: Operation duration in seconds
        timestamp: When operation completed
    """

    tool: str
    success: bool
    data: Any = None
    error: str | None = None
    path: str | None = None
    duration: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        """Set default timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict:
        """Serialize to dictionary.

        Returns:
            Dictionary representation

        Example:
            >>> result = FilesystemResult(tool="read_file", success=True)
            >>> data = result.to_dict()
        """
        return {
            "tool": self.tool,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "path": self.path,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class FilesystemServer:
    """Sandboxed filesystem server for agents.

    Each agent gets isolated workspace at /workspace/{agent_id}/.
    No access to parent directories, secrets, or system files.

    Security features:
    - Path traversal prevention (no .., absolute paths outside sandbox)
    - File size limits (max 10MB per file)
    - No symlink following
    - No access to /etc, /proc, /sys, /root, ~/.ssh, etc.

    Example:
        >>> server = FilesystemServer(agent_id=1)
        >>> await server.write_file("output.txt", "Hello, World!")
        >>> content = await server.read_file("output.txt")
    """

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    WORKSPACE_ROOT = Path("/workspace")

    def __init__(self, agent_id: int, base_path: Path | None = None):
        """Initialize filesystem server for agent.

        Args:
            agent_id: Agent ID (used for sandbox isolation)
            base_path: Custom workspace root (default: /workspace)

        Example:
            >>> server = FilesystemServer(agent_id=1)
        """
        self.agent_id = agent_id
        self.base_path = base_path or self.WORKSPACE_ROOT
        self.sandbox_path = self.base_path / f"agent_{agent_id}"

        # Create sandbox directory
        self.sandbox_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            "FilesystemServer initialized for agent %d (sandbox: %s)",
            agent_id,
            self.sandbox_path,
        )

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve and validate path within sandbox.

        Args:
            relative_path: Relative path within sandbox

        Returns:
            Absolute Path within sandbox

        Raises:
            ValueError: If path escapes sandbox or is invalid

        Example:
            >>> path = server._resolve_path("data/output.txt")
        """
        # Check for absolute path (security: prevent access outside sandbox)
        if Path(relative_path).is_absolute():
            msg = f"Path escapes sandbox: {relative_path}"
            logger.error(msg)
            raise ValueError(msg)

        # Remove leading slashes (force relative)
        relative_path = relative_path.lstrip("/")

        # Resolve path
        full_path = (self.sandbox_path / relative_path).resolve()

        # Check sandbox containment
        try:
            full_path.relative_to(self.sandbox_path)
        except ValueError as e:
            msg = f"Path escapes sandbox: {relative_path}"
            logger.error(msg)
            raise ValueError(msg) from e

        return full_path

    async def read_file(self, path: str, encoding: str = "utf-8") -> FilesystemResult:
        """Read file from sandbox.

        Args:
            path: Relative path within sandbox
            encoding: Text encoding (default: utf-8)

        Returns:
            FilesystemResult with file content in data field

        Example:
            >>> result = await server.read_file("output.txt")
            >>> print(result.data)
            "Hello, World!"
        """
        start_time = datetime.now(UTC)
        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            if not full_path.is_file():
                raise ValueError(f"Not a file: {path}")

            # Check file size
            size = full_path.stat().st_size
            if size > self.MAX_FILE_SIZE:
                raise ValueError(f"File too large: {size} bytes (max {self.MAX_FILE_SIZE})")

            # Read file
            content = await asyncio.to_thread(full_path.read_text, encoding=encoding)

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info(
                "Read file %s (%d bytes, %.2fs)",
                path,
                len(content),
                duration,
            )

            return FilesystemResult(
                tool=FilesystemTool.READ_FILE,
                success=True,
                data=content,
                path=str(full_path),
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Read file %s failed: %s", path, e)
            return FilesystemResult(
                tool=FilesystemTool.READ_FILE,
                success=False,
                error=str(e),
                path=path,
                duration=duration,
            )

    async def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        overwrite: bool = True,
    ) -> FilesystemResult:
        """Write file to sandbox.

        Args:
            path: Relative path within sandbox
            content: File content
            encoding: Text encoding (default: utf-8)
            overwrite: Allow overwriting existing files (default: True)

        Returns:
            FilesystemResult with success status

        Example:
            >>> result = await server.write_file("output.txt", "Hello, World!")
        """
        start_time = datetime.now(UTC)
        try:
            full_path = self._resolve_path(path)

            # Check content size
            content_bytes = content.encode(encoding)
            if len(content_bytes) > self.MAX_FILE_SIZE:
                raise ValueError(
                    f"Content too large: {len(content_bytes)} bytes (max {self.MAX_FILE_SIZE})"
                )

            # Check if file exists and overwrite is False
            if full_path.exists() and not overwrite:
                raise FileExistsError(f"File exists: {path}")

            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            await asyncio.to_thread(full_path.write_text, content, encoding=encoding)

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info(
                "Wrote file %s (%d bytes, %.2fs)",
                path,
                len(content_bytes),
                duration,
            )

            return FilesystemResult(
                tool=FilesystemTool.WRITE_FILE,
                success=True,
                data={"size": len(content_bytes)},
                path=str(full_path),
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Write file %s failed: %s", path, e)
            return FilesystemResult(
                tool=FilesystemTool.WRITE_FILE,
                success=False,
                error=str(e),
                path=path,
                duration=duration,
            )

    async def list_files(self, path: str = ".", pattern: str = "*") -> FilesystemResult:
        """List files in directory.

        Args:
            path: Relative directory path (default: ".")
            pattern: Glob pattern (default: "*")

        Returns:
            FilesystemResult with file list in data field

        Example:
            >>> result = await server.list_files()
            >>> print(result.data)
            ["file1.txt", "file2.json"]
        """
        start_time = datetime.now(UTC)
        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")

            if not full_path.is_dir():
                raise ValueError(f"Not a directory: {path}")

            # List files
            files = []
            for item in full_path.glob(pattern):
                relative = item.relative_to(self.sandbox_path)
                files.append(
                    {
                        "path": str(relative),
                        "name": item.name,
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else None,
                    }
                )

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info("Listed %d files in %s (%.2fs)", len(files), path, duration)

            return FilesystemResult(
                tool=FilesystemTool.LIST_FILES,
                success=True,
                data=files,
                path=str(full_path),
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("List files %s failed: %s", path, e)
            return FilesystemResult(
                tool=FilesystemTool.LIST_FILES,
                success=False,
                error=str(e),
                path=path,
                duration=duration,
            )

    async def delete_file(self, path: str, recursive: bool = False) -> FilesystemResult:
        """Delete file or directory.

        Args:
            path: Relative path within sandbox
            recursive: Delete directories recursively (default: False)

        Returns:
            FilesystemResult with success status

        Example:
            >>> result = await server.delete_file("output.txt")
        """
        start_time = datetime.now(UTC)
        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                raise FileNotFoundError(f"Path not found: {path}")

            # Delete file or directory
            if full_path.is_file():
                await asyncio.to_thread(full_path.unlink)
            elif full_path.is_dir():
                if not recursive:
                    raise ValueError(f"Directory not empty: {path} (use recursive=True)")
                await asyncio.to_thread(shutil.rmtree, full_path)
            else:
                raise ValueError(f"Unknown file type: {path}")

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info("Deleted %s (%.2fs)", path, duration)

            return FilesystemResult(
                tool=FilesystemTool.DELETE_FILE,
                success=True,
                path=str(full_path),
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Delete %s failed: %s", path, e)
            return FilesystemResult(
                tool=FilesystemTool.DELETE_FILE,
                success=False,
                error=str(e),
                path=path,
                duration=duration,
            )

    async def create_dir(self, path: str) -> FilesystemResult:
        """Create directory.

        Args:
            path: Relative directory path

        Returns:
            FilesystemResult with success status

        Example:
            >>> result = await server.create_dir("data/processed")
        """
        start_time = datetime.now(UTC)
        try:
            full_path = self._resolve_path(path)

            # Create directory
            await asyncio.to_thread(full_path.mkdir, parents=True, exist_ok=True)

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info("Created directory %s (%.2fs)", path, duration)

            return FilesystemResult(
                tool=FilesystemTool.CREATE_DIR,
                success=True,
                path=str(full_path),
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("Create directory %s failed: %s", path, e)
            return FilesystemResult(
                tool=FilesystemTool.CREATE_DIR,
                success=False,
                error=str(e),
                path=path,
                duration=duration,
            )

    async def file_info(self, path: str) -> FilesystemResult:
        """Get file information.

        Args:
            path: Relative path within sandbox

        Returns:
            FilesystemResult with file metadata in data field

        Example:
            >>> result = await server.file_info("output.txt")
            >>> print(result.data)
            {"size": 1024, "is_dir": False, "modified": "2026-01-12T..."}
        """
        start_time = datetime.now(UTC)
        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                raise FileNotFoundError(f"Path not found: {path}")

            # Get file stats
            stats = full_path.stat()
            info = {
                "path": str(full_path.relative_to(self.sandbox_path)),
                "name": full_path.name,
                "size": stats.st_size,
                "is_dir": full_path.is_dir(),
                "is_file": full_path.is_file(),
                "modified": datetime.fromtimestamp(stats.st_mtime, tz=UTC).isoformat(),
                "created": datetime.fromtimestamp(stats.st_ctime, tz=UTC).isoformat(),
            }

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info("Got info for %s (%.2fs)", path, duration)

            return FilesystemResult(
                tool=FilesystemTool.FILE_INFO,
                success=True,
                data=info,
                path=str(full_path),
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error("File info %s failed: %s", path, e)
            return FilesystemResult(
                tool=FilesystemTool.FILE_INFO,
                success=False,
                error=str(e),
                path=path,
                duration=duration,
            )

    @property
    def sandbox_root(self) -> Path:
        """Get sandbox root path.

        Returns:
            Absolute path to agent sandbox

        Example:
            >>> root = server.sandbox_root
        """
        return self.sandbox_path

    async def cleanup_sandbox(self) -> bool:
        """Delete all files in agent sandbox.

        WARNING: This deletes ALL files for this agent!

        Returns:
            True if successful, False otherwise

        Example:
            >>> success = await server.cleanup_sandbox()
        """
        try:
            if self.sandbox_path.exists():
                await asyncio.to_thread(shutil.rmtree, self.sandbox_path)
                self.sandbox_path.mkdir(parents=True, exist_ok=True)
                logger.info("Cleaned up sandbox for agent %d", self.agent_id)
                return True
            return True
        except Exception as e:
            logger.error("Cleanup sandbox for agent %d failed: %s", self.agent_id, e)
            return False
