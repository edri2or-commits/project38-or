"""
gcloud CLI execution tools.

Provides safe execution of gcloud commands with proper authentication.
"""

import asyncio
import shutil
from typing import Optional


async def execute_gcloud_command(
    command: str, project_id: Optional[str] = None
) -> dict:
    """
    Execute a gcloud command safely.

    Args:
        command: gcloud command (without 'gcloud' prefix)
        project_id: GCP project ID (optional)

    Returns:
        dict with status, stdout, stderr, and exit_code
    """
    # Check if gcloud is installed
    gcloud_path = shutil.which("gcloud")
    if not gcloud_path:
        return {
            "status": "error",
            "error": "gcloud CLI not installed",
            "message": "Please install gcloud CLI: https://cloud.google.com/sdk/docs/install",
        }

    # Build command
    cmd_parts = ["gcloud"]

    # Add project flag if specified
    if project_id:
        cmd_parts.extend(["--project", project_id])

    # Add user command (split safely)
    cmd_parts.extend(command.split())

    # Add format flag for JSON output (if not already specified)
    if "--format" not in command:
        cmd_parts.extend(["--format", "json"])

    try:
        # Execute command
        process = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        # Decode output
        stdout_str = stdout.decode("utf-8")
        stderr_str = stderr.decode("utf-8")

        if process.returncode == 0:
            return {
                "status": "success",
                "output": stdout_str,
                "command": " ".join(cmd_parts),
            }
        else:
            return {
                "status": "error",
                "error": stderr_str,
                "command": " ".join(cmd_parts),
                "exit_code": process.returncode,
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "command": " ".join(cmd_parts),
        }


async def get_gcloud_version() -> dict:
    """
    Get gcloud version and configuration info.

    Returns:
        dict with version info and active config
    """
    gcloud_path = shutil.which("gcloud")
    if not gcloud_path:
        return {
            "status": "error",
            "error": "gcloud CLI not installed",
        }

    try:
        # Get version
        version_proc = await asyncio.create_subprocess_exec(
            "gcloud",
            "version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        version_out, _ = await version_proc.communicate()

        # Get active config
        config_proc = await asyncio.create_subprocess_exec(
            "gcloud",
            "config",
            "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        config_out, _ = await config_proc.communicate()

        return {
            "status": "success",
            "version": version_out.decode("utf-8"),
            "config": config_out.decode("utf-8"),
            "path": gcloud_path,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
