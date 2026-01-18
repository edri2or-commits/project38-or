"""
GCP MCP Server.

This module provides the FastMCP server with tools for autonomous
GCP operations including gcloud commands, Secret Manager, Compute Engine,
and Cloud Storage.

Usage:
    Standalone:
        python -m src.gcp_mcp.server

    With FastAPI (mount):
        from src.gcp_mcp.server import create_mcp_app
        app.mount("/gcp-mcp", create_mcp_app())
"""

import os
from typing import Any

# Check if fastmcp is available
try:
    from fastmcp import FastMCP

    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    FastMCP = None


def create_mcp_server() -> Any | None:
    """
    Create and configure the GCP FastMCP server.

    Returns:
        FastMCP server instance, or None if fastmcp is not installed.
    """
    if not FASTMCP_AVAILABLE:
        return None

    mcp = FastMCP("GCP Agent Gateway")

    # ========================================================================
    # GCLOUD TOOLS
    # ========================================================================

    @mcp.tool
    async def gcloud_run(command: str, project_id: str = "") -> dict:
        """
        Execute a gcloud command.

        Args:
            command: gcloud command to execute (without 'gcloud' prefix)
            project_id: GCP project ID (uses default if empty)

        Returns:
            Command output, status, and error (if any)

        Example:
            gcloud_run("compute instances list --limit=5")
        """
        from .tools.gcloud import execute_gcloud_command

        return await execute_gcloud_command(command, project_id or None)

    @mcp.tool
    async def gcloud_version() -> dict:
        """
        Get gcloud CLI version and configuration.

        Returns:
            gcloud version info and active configuration
        """
        from .tools.gcloud import get_gcloud_version

        return await get_gcloud_version()

    # ========================================================================
    # SECRET MANAGER TOOLS
    # ========================================================================

    @mcp.tool
    async def secret_get(secret_name: str, version: str = "latest") -> dict:
        """
        Get a secret value from Secret Manager.

        Args:
            secret_name: Name of the secret
            version: Version to retrieve (default: latest)

        Returns:
            Secret value (masked for security)

        Security:
            Returns only metadata by default. Use with caution.
        """
        from .tools.secrets import get_secret_value

        return await get_secret_value(secret_name, version)

    @mcp.tool
    async def secret_list() -> dict:
        """
        List all secrets in Secret Manager.

        Returns:
            List of secret names and metadata
        """
        from .tools.secrets import list_secrets

        return await list_secrets()

    @mcp.tool
    async def secret_create(secret_name: str, secret_value: str) -> dict:
        """
        Create a new secret in Secret Manager.

        Args:
            secret_name: Name for the new secret
            secret_value: Secret value to store

        Returns:
            Creation status and secret name
        """
        from .tools.secrets import create_secret

        return await create_secret(secret_name, secret_value)

    @mcp.tool
    async def secret_update(secret_name: str, secret_value: str) -> dict:
        """
        Update an existing secret (add new version).

        Args:
            secret_name: Name of the secret
            secret_value: New secret value

        Returns:
            Update status and new version number
        """
        from .tools.secrets import update_secret

        return await update_secret(secret_name, secret_value)

    # ========================================================================
    # COMPUTE ENGINE TOOLS
    # ========================================================================

    @mcp.tool
    async def compute_list(zone: str = "") -> dict:
        """
        List Compute Engine instances.

        Args:
            zone: GCP zone (lists all zones if empty)

        Returns:
            List of instances with status and metadata
        """
        from .tools.compute import list_instances

        return await list_instances(zone or None)

    @mcp.tool
    async def compute_get(instance_name: str, zone: str) -> dict:
        """
        Get details of a specific instance.

        Args:
            instance_name: Name of the instance
            zone: GCP zone where instance is located

        Returns:
            Instance details including status, IPs, and configuration
        """
        from .tools.compute import get_instance_details

        return await get_instance_details(instance_name, zone)

    @mcp.tool
    async def compute_start(instance_name: str, zone: str) -> dict:
        """
        Start a stopped Compute Engine instance.

        Args:
            instance_name: Name of the instance
            zone: GCP zone where instance is located

        Returns:
            Operation status
        """
        from .tools.compute import start_instance

        return await start_instance(instance_name, zone)

    @mcp.tool
    async def compute_stop(instance_name: str, zone: str) -> dict:
        """
        Stop a running Compute Engine instance.

        Args:
            instance_name: Name of the instance
            zone: GCP zone where instance is located

        Returns:
            Operation status
        """
        from .tools.compute import stop_instance

        return await stop_instance(instance_name, zone)

    # ========================================================================
    # CLOUD STORAGE TOOLS
    # ========================================================================

    @mcp.tool
    async def storage_list(bucket_name: str = "", prefix: str = "") -> dict:
        """
        List Cloud Storage buckets or objects.

        Args:
            bucket_name: Bucket name (lists all buckets if empty)
            prefix: Object prefix filter (optional)

        Returns:
            List of buckets or objects
        """
        from .tools.storage import list_storage

        return await list_storage(bucket_name or None, prefix or None)

    @mcp.tool
    async def storage_get(bucket_name: str, object_name: str) -> dict:
        """
        Get metadata for a Cloud Storage object.

        Args:
            bucket_name: Bucket name
            object_name: Object path

        Returns:
            Object metadata (size, content type, etc.)
        """
        from .tools.storage import get_object_metadata

        return await get_object_metadata(bucket_name, object_name)

    @mcp.tool
    async def storage_upload(
        bucket_name: str, source_path: str, destination_path: str
    ) -> dict:
        """
        Upload a file to Cloud Storage.

        Args:
            bucket_name: Bucket name
            source_path: Local file path
            destination_path: Destination path in bucket

        Returns:
            Upload status and object URL
        """
        from .tools.storage import upload_file

        return await upload_file(bucket_name, source_path, destination_path)

    # ========================================================================
    # IAM TOOLS
    # ========================================================================

    @mcp.tool
    async def iam_list_accounts() -> dict:
        """
        List service accounts in the project.

        Returns:
            List of service accounts with emails and display names
        """
        from .tools.iam import list_service_accounts

        return await list_service_accounts()

    @mcp.tool
    async def iam_get_policy(resource: str) -> dict:
        """
        Get IAM policy for a resource.

        Args:
            resource: Resource name (e.g., project ID)

        Returns:
            IAM policy bindings
        """
        from .tools.iam import get_iam_policy

        return await get_iam_policy(resource)

    return mcp


def create_mcp_app():
    """
    Create FastMCP ASGI application.

    Returns:
        ASGI application ready to be mounted or run standalone
    """
    mcp = create_mcp_server()
    if mcp is None:
        raise ImportError("fastmcp is not installed")
    return mcp.get_asgi_app()


def main():
    """Run the MCP server standalone."""
    import uvicorn

    mcp = create_mcp_server()
    if mcp is None:
        print("Error: fastmcp is not installed")
        print("Install with: pip install fastmcp")
        return 1

    app = mcp.get_asgi_app()

    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 GCP MCP Gateway starting on port {port}")
    print(f"📡 Tools available: {len(mcp._tools)} tools")
    print("✅ Ready for autonomous GCP operations")

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
