"""Google Drive MCP Tools.

Provides tools for file storage operations:
- drive_list: List files and folders
- drive_search: Search for files
- drive_read: Read file content
- drive_create_folder: Create a folder
- drive_upload: Upload a file
- drive_delete: Delete a file
- drive_share: Share a file
"""

import logging
from typing import Any

import httpx

from apps.personal.integrations.workspace_mcp_bridge.auth import GoogleOAuthManager

logger = logging.getLogger(__name__)

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"


def register_drive_tools(mcp: Any, oauth_manager: GoogleOAuthManager) -> None:
    """Register Drive tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        oauth_manager: OAuth manager for authentication
    """

    @mcp.tool()
    async def drive_list(
        folder_id: str = "root",
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List files in a folder.

        Args:
            folder_id: Folder ID (default: "root" for My Drive)
            page_size: Number of files to return (default: 20)

        Returns:
            List of files and folders
        """
        try:
            token = await oauth_manager.get_access_token()

            query = f"'{folder_id}' in parents and trashed = false"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{DRIVE_API_BASE}/files",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "q": query,
                        "pageSize": page_size,
                        "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink)",
                        "orderBy": "modifiedTime desc",
                    },
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to list files: {response.text}",
                    }

                data = response.json()

                def get_file_type(mime: str) -> str:
                    return "folder" if mime == "application/vnd.google-apps.folder" else "file"

                files = [
                    {
                        "id": f["id"],
                        "name": f["name"],
                        "type": get_file_type(f["mimeType"]),
                        "mime_type": f["mimeType"],
                        "size": f.get("size"),
                        "modified": f.get("modifiedTime"),
                        "link": f.get("webViewLink"),
                    }
                    for f in data.get("files", [])
                ]

                return {
                    "success": True,
                    "folder_id": folder_id,
                    "count": len(files),
                    "files": files,
                }

        except Exception as e:
            logger.error(f"drive_list failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def drive_search(
        query: str,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Search for files in Drive.

        Args:
            query: Search query (file name or content)
            page_size: Number of results (default: 20)

        Returns:
            List of matching files
        """
        try:
            token = await oauth_manager.get_access_token()

            # Build Drive API query
            api_query = f"name contains '{query}' and trashed = false"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{DRIVE_API_BASE}/files",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "q": api_query,
                        "pageSize": page_size,
                        "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink,parents)",
                        "orderBy": "modifiedTime desc",
                    },
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Search failed: {response.text}",
                    }

                data = response.json()

                def get_file_type(mime: str) -> str:
                    folder_mime = "application/vnd.google-apps.folder"
                    return "folder" if mime == folder_mime else "file"

                files = [
                    {
                        "id": f["id"],
                        "name": f["name"],
                        "type": get_file_type(f["mimeType"]),
                        "mime_type": f["mimeType"],
                        "size": f.get("size"),
                        "modified": f.get("modifiedTime"),
                        "link": f.get("webViewLink"),
                        "parent_id": f.get("parents", [None])[0],
                    }
                    for f in data.get("files", [])
                ]

                return {
                    "success": True,
                    "query": query,
                    "count": len(files),
                    "files": files,
                }

        except Exception as e:
            logger.error(f"drive_search failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def drive_read(file_id: str) -> dict[str, Any]:
        """Read file content from Drive.

        Args:
            file_id: File ID to read

        Returns:
            File metadata and content (for text files)
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                # Get file metadata
                meta_response = await client.get(
                    f"{DRIVE_API_BASE}/files/{file_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"fields": "id,name,mimeType,size,modifiedTime,webViewLink"},
                )

                if meta_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"File not found: {meta_response.text}",
                    }

                metadata = meta_response.json()
                mime_type = metadata.get("mimeType", "")

                # For Google Docs/Sheets/Slides, export as text
                export_mime = None
                if mime_type == "application/vnd.google-apps.document":
                    export_mime = "text/plain"
                elif mime_type == "application/vnd.google-apps.spreadsheet":
                    export_mime = "text/csv"
                elif mime_type == "application/vnd.google-apps.presentation":
                    export_mime = "text/plain"

                content = ""
                if export_mime:
                    content_response = await client.get(
                        f"{DRIVE_API_BASE}/files/{file_id}/export",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"mimeType": export_mime},
                    )
                    if content_response.status_code == 200:
                        content = content_response.text
                elif mime_type.startswith("text/"):
                    content_response = await client.get(
                        f"{DRIVE_API_BASE}/files/{file_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"alt": "media"},
                    )
                    if content_response.status_code == 200:
                        content = content_response.text

                return {
                    "success": True,
                    "id": file_id,
                    "name": metadata.get("name"),
                    "mime_type": mime_type,
                    "size": metadata.get("size"),
                    "modified": metadata.get("modifiedTime"),
                    "link": metadata.get("webViewLink"),
                    "content": content if content else "(binary file - content not shown)",
                }

        except Exception as e:
            logger.error(f"drive_read failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def drive_create_folder(
        name: str,
        parent_id: str = "root",
    ) -> dict[str, Any]:
        """Create a folder in Drive.

        Args:
            name: Folder name
            parent_id: Parent folder ID (default: "root")

        Returns:
            Created folder details
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DRIVE_API_BASE}/files",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "name": name,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [parent_id],
                    },
                )

                if response.status_code not in (200, 201):
                    return {
                        "success": False,
                        "error": f"Failed to create folder: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "folder_id": data.get("id"),
                    "name": data.get("name"),
                }

        except Exception as e:
            logger.error(f"drive_create_folder failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def drive_upload(
        name: str,
        content: str,
        parent_id: str = "root",
        mime_type: str = "text/plain",
    ) -> dict[str, Any]:
        """Upload a text file to Drive.

        Args:
            name: File name
            content: File content (text)
            parent_id: Parent folder ID (default: "root")
            mime_type: MIME type (default: "text/plain")

        Returns:
            Uploaded file details
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                # Create file metadata
                metadata = {
                    "name": name,
                    "parents": [parent_id],
                }

                # Use multipart upload
                response = await client.post(
                    "https://www.googleapis.com/upload/drive/v3/files",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"uploadType": "multipart"},
                    files={
                        "metadata": ("metadata", str(metadata), "application/json"),
                        "file": (name, content, mime_type),
                    },
                )

                if response.status_code not in (200, 201):
                    # Fallback: simple upload
                    create_response = await client.post(
                        f"{DRIVE_API_BASE}/files",
                        headers={"Authorization": f"Bearer {token}"},
                        json=metadata,
                    )
                    if create_response.status_code in (200, 201):
                        file_id = create_response.json().get("id")
                        await client.patch(
                            f"https://www.googleapis.com/upload/drive/v3/files/{file_id}",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": mime_type,
                            },
                            params={"uploadType": "media"},
                            content=content.encode(),
                        )
                        return {
                            "success": True,
                            "file_id": file_id,
                            "name": name,
                        }
                    return {
                        "success": False,
                        "error": f"Failed to upload file: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "file_id": data.get("id"),
                    "name": data.get("name"),
                    "link": data.get("webViewLink"),
                }

        except Exception as e:
            logger.error(f"drive_upload failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def drive_delete(file_id: str) -> dict[str, Any]:
        """Delete a file or folder from Drive.

        Args:
            file_id: File or folder ID to delete

        Returns:
            Deletion result
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{DRIVE_API_BASE}/files/{file_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code not in (200, 204):
                    return {
                        "success": False,
                        "error": f"Failed to delete: {response.text}",
                    }

                return {
                    "success": True,
                    "file_id": file_id,
                    "deleted": True,
                }

        except Exception as e:
            logger.error(f"drive_delete failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def drive_share(
        file_id: str,
        email: str,
        role: str = "reader",
    ) -> dict[str, Any]:
        """Share a file with another user.

        Args:
            file_id: File ID to share
            email: Email address to share with
            role: Permission role ("reader", "writer", "commenter")

        Returns:
            Sharing result
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DRIVE_API_BASE}/files/{file_id}/permissions",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "type": "user",
                        "role": role,
                        "emailAddress": email,
                    },
                )

                if response.status_code not in (200, 201):
                    return {
                        "success": False,
                        "error": f"Failed to share: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "file_id": file_id,
                    "permission_id": data.get("id"),
                    "email": email,
                    "role": role,
                }

        except Exception as e:
            logger.error(f"drive_share failed: {e}")
            return {"success": False, "error": str(e)}
