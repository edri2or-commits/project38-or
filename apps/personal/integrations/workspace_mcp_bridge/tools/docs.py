"""Google Docs MCP Tools.

Provides tools for document operations:
- docs_read: Read document content
- docs_create: Create a new document
- docs_append: Append text to document
- docs_insert: Insert text at position
"""

import logging
from typing import Any

import httpx

from apps.personal.integrations.workspace_mcp_bridge.auth import GoogleOAuthManager

logger = logging.getLogger(__name__)

DOCS_API_BASE = "https://docs.googleapis.com/v1/documents"


def register_docs_tools(mcp: Any, oauth_manager: GoogleOAuthManager) -> None:
    """Register Docs tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        oauth_manager: OAuth manager for authentication
    """

    @mcp.tool()
    async def docs_read(document_id: str) -> dict[str, Any]:
        """Read document content.

        Args:
            document_id: Document ID

        Returns:
            Document title and content as plain text
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{DOCS_API_BASE}/{document_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to read document: {response.text}",
                    }

                data = response.json()

                # Extract plain text from document body
                def extract_text(content: list) -> str:
                    """Extract plain text from document content."""
                    text_parts = []
                    for element in content:
                        if "paragraph" in element:
                            para = element["paragraph"]
                            for elem in para.get("elements", []):
                                if "textRun" in elem:
                                    text_parts.append(elem["textRun"].get("content", ""))
                        elif "table" in element:
                            # Handle tables
                            for row in element["table"].get("tableRows", []):
                                for cell in row.get("tableCells", []):
                                    cell_content = cell.get("content", [])
                                    text_parts.append(extract_text(cell_content))
                                    text_parts.append("\t")
                                text_parts.append("\n")
                    return "".join(text_parts)

                body = data.get("body", {}).get("content", [])
                content = extract_text(body)

                return {
                    "success": True,
                    "document_id": document_id,
                    "title": data.get("title", ""),
                    "content": content,
                    "revision_id": data.get("revisionId"),
                }

        except Exception as e:
            logger.error(f"docs_read failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def docs_create(
        title: str,
        content: str = "",
    ) -> dict[str, Any]:
        """Create a new document.

        Args:
            title: Document title
            content: Initial content (optional)

        Returns:
            Created document details
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                # Create empty document
                create_response = await client.post(
                    DOCS_API_BASE,
                    headers={"Authorization": f"Bearer {token}"},
                    json={"title": title},
                )

                if create_response.status_code not in (200, 201):
                    return {
                        "success": False,
                        "error": f"Failed to create document: {create_response.text}",
                    }

                doc_data = create_response.json()
                document_id = doc_data.get("documentId")

                # Add content if provided
                if content:
                    update_response = await client.post(
                        f"{DOCS_API_BASE}/{document_id}:batchUpdate",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "requests": [
                                {
                                    "insertText": {
                                        "location": {"index": 1},
                                        "text": content,
                                    }
                                }
                            ]
                        },
                    )

                    if update_response.status_code != 200:
                        logger.warning(f"Failed to add content: {update_response.text}")

                return {
                    "success": True,
                    "document_id": document_id,
                    "title": doc_data.get("title"),
                    "url": f"https://docs.google.com/document/d/{document_id}/edit",
                }

        except Exception as e:
            logger.error(f"docs_create failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def docs_append(
        document_id: str,
        text: str,
    ) -> dict[str, Any]:
        """Append text to the end of a document.

        Args:
            document_id: Document ID
            text: Text to append

        Returns:
            Update result
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                # Get document to find end index
                get_response = await client.get(
                    f"{DOCS_API_BASE}/{document_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if get_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Document not found: {get_response.text}",
                    }

                doc_data = get_response.json()

                # Find the end index
                body = doc_data.get("body", {})
                content = body.get("content", [])

                # Get the last element's end index
                end_index = 1
                if content:
                    last_element = content[-1]
                    end_index = last_element.get("endIndex", 1) - 1

                # Append text
                update_response = await client.post(
                    f"{DOCS_API_BASE}/{document_id}:batchUpdate",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "requests": [
                            {
                                "insertText": {
                                    "location": {"index": end_index},
                                    "text": text,
                                }
                            }
                        ]
                    },
                )

                if update_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to append: {update_response.text}",
                    }

                return {
                    "success": True,
                    "document_id": document_id,
                    "appended_at_index": end_index,
                    "text_length": len(text),
                }

        except Exception as e:
            logger.error(f"docs_append failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def docs_insert(
        document_id: str,
        text: str,
        index: int = 1,
    ) -> dict[str, Any]:
        """Insert text at a specific position in a document.

        Args:
            document_id: Document ID
            text: Text to insert
            index: Position to insert at (default: 1, beginning)

        Returns:
            Update result
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DOCS_API_BASE}/{document_id}:batchUpdate",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "requests": [
                            {
                                "insertText": {
                                    "location": {"index": index},
                                    "text": text,
                                }
                            }
                        ]
                    },
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to insert: {response.text}",
                    }

                return {
                    "success": True,
                    "document_id": document_id,
                    "inserted_at_index": index,
                    "text_length": len(text),
                }

        except Exception as e:
            logger.error(f"docs_insert failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def docs_replace(
        document_id: str,
        find_text: str,
        replace_text: str,
        match_case: bool = True,
    ) -> dict[str, Any]:
        """Find and replace text in a document.

        Args:
            document_id: Document ID
            find_text: Text to find
            replace_text: Text to replace with
            match_case: Whether to match case (default: True)

        Returns:
            Number of replacements made
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DOCS_API_BASE}/{document_id}:batchUpdate",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "requests": [
                            {
                                "replaceAllText": {
                                    "containsText": {
                                        "text": find_text,
                                        "matchCase": match_case,
                                    },
                                    "replaceText": replace_text,
                                }
                            }
                        ]
                    },
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to replace: {response.text}",
                    }

                data = response.json()
                replies = data.get("replies", [])
                occurrences = 0
                if replies:
                    occurrences = replies[0].get("replaceAllText", {}).get("occurrencesChanged", 0)

                return {
                    "success": True,
                    "document_id": document_id,
                    "find_text": find_text,
                    "replace_text": replace_text,
                    "occurrences_replaced": occurrences,
                }

        except Exception as e:
            logger.error(f"docs_replace failed: {e}")
            return {"success": False, "error": str(e)}
