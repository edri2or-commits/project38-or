"""Google Sheets MCP Tools.

Provides tools for spreadsheet operations:
- sheets_read: Read data from a spreadsheet
- sheets_write: Write data to a spreadsheet
- sheets_create: Create a new spreadsheet
- sheets_append: Append rows to a spreadsheet
- sheets_clear: Clear a range in a spreadsheet
"""

import logging
from typing import Any

import httpx

from src.workspace_mcp_bridge.auth import GoogleOAuthManager

logger = logging.getLogger(__name__)

SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


def register_sheets_tools(mcp: Any, oauth_manager: GoogleOAuthManager) -> None:
    """Register Sheets tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        oauth_manager: OAuth manager for authentication
    """

    @mcp.tool()
    async def sheets_read(
        spreadsheet_id: str,
        range_notation: str = "Sheet1",
    ) -> dict[str, Any]:
        """Read data from a spreadsheet.

        Args:
            spreadsheet_id: Spreadsheet ID
            range_notation: A1 notation range (e.g., "Sheet1!A1:D10")

        Returns:
            Spreadsheet data as 2D array
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{range_notation}",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to read spreadsheet: {response.text}",
                    }

                data = response.json()
                values = data.get("values", [])

                return {
                    "success": True,
                    "spreadsheet_id": spreadsheet_id,
                    "range": data.get("range"),
                    "rows": len(values),
                    "values": values,
                }

        except Exception as e:
            logger.error(f"sheets_read failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def sheets_write(
        spreadsheet_id: str,
        range_notation: str,
        values: str,
    ) -> dict[str, Any]:
        """Write data to a spreadsheet.

        Args:
            spreadsheet_id: Spreadsheet ID
            range_notation: A1 notation range (e.g., "Sheet1!A1")
            values: JSON array of arrays (e.g., '[["A","B"],["C","D"]]')

        Returns:
            Update result with cells affected
        """
        try:
            import json
            token = await oauth_manager.get_access_token()

            # Parse values from JSON string
            try:
                parsed_values = json.loads(values)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "Invalid JSON format for values",
                }

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{range_notation}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"valueInputOption": "USER_ENTERED"},
                    json={"values": parsed_values},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to write: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "spreadsheet_id": spreadsheet_id,
                    "updated_range": data.get("updatedRange"),
                    "updated_rows": data.get("updatedRows"),
                    "updated_columns": data.get("updatedColumns"),
                    "updated_cells": data.get("updatedCells"),
                }

        except Exception as e:
            logger.error(f"sheets_write failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def sheets_create(
        title: str,
        sheet_names: str = "Sheet1",
    ) -> dict[str, Any]:
        """Create a new spreadsheet.

        Args:
            title: Spreadsheet title
            sheet_names: Comma-separated sheet names (default: "Sheet1")

        Returns:
            Created spreadsheet details
        """
        try:
            token = await oauth_manager.get_access_token()

            sheets = [
                {"properties": {"title": name.strip()}}
                for name in sheet_names.split(",")
            ]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    SHEETS_API_BASE,
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "properties": {"title": title},
                        "sheets": sheets,
                    },
                )

                if response.status_code not in (200, 201):
                    return {
                        "success": False,
                        "error": f"Failed to create spreadsheet: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "spreadsheet_id": data.get("spreadsheetId"),
                    "title": data.get("properties", {}).get("title"),
                    "url": data.get("spreadsheetUrl"),
                    "sheets": [
                        s.get("properties", {}).get("title")
                        for s in data.get("sheets", [])
                    ],
                }

        except Exception as e:
            logger.error(f"sheets_create failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def sheets_append(
        spreadsheet_id: str,
        range_notation: str,
        values: str,
    ) -> dict[str, Any]:
        """Append rows to a spreadsheet.

        Args:
            spreadsheet_id: Spreadsheet ID
            range_notation: A1 notation range (e.g., "Sheet1")
            values: JSON array of arrays to append

        Returns:
            Append result with range updated
        """
        try:
            import json
            token = await oauth_manager.get_access_token()

            try:
                parsed_values = json.loads(values)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "Invalid JSON format for values",
                }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{range_notation}:append",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "valueInputOption": "USER_ENTERED",
                        "insertDataOption": "INSERT_ROWS",
                    },
                    json={"values": parsed_values},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to append: {response.text}",
                    }

                data = response.json()
                updates = data.get("updates", {})
                return {
                    "success": True,
                    "spreadsheet_id": spreadsheet_id,
                    "updated_range": updates.get("updatedRange"),
                    "updated_rows": updates.get("updatedRows"),
                    "updated_cells": updates.get("updatedCells"),
                }

        except Exception as e:
            logger.error(f"sheets_append failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def sheets_clear(
        spreadsheet_id: str,
        range_notation: str,
    ) -> dict[str, Any]:
        """Clear a range in a spreadsheet.

        Args:
            spreadsheet_id: Spreadsheet ID
            range_notation: A1 notation range to clear

        Returns:
            Clear result
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{range_notation}:clear",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to clear: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "spreadsheet_id": spreadsheet_id,
                    "cleared_range": data.get("clearedRange"),
                }

        except Exception as e:
            logger.error(f"sheets_clear failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def sheets_get_metadata(
        spreadsheet_id: str,
    ) -> dict[str, Any]:
        """Get spreadsheet metadata (sheets, title, etc.).

        Args:
            spreadsheet_id: Spreadsheet ID

        Returns:
            Spreadsheet metadata
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SHEETS_API_BASE}/{spreadsheet_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"fields": "spreadsheetId,properties,sheets.properties"},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to get metadata: {response.text}",
                    }

                data = response.json()

                def extract_sheet_info(s: dict) -> dict:
                    props = s.get("properties", {})
                    grid = props.get("gridProperties", {})
                    return {
                        "sheet_id": props.get("sheetId"),
                        "title": props.get("title"),
                        "index": props.get("index"),
                        "row_count": grid.get("rowCount"),
                        "column_count": grid.get("columnCount"),
                    }

                sheets_info = [
                    extract_sheet_info(s) for s in data.get("sheets", [])
                ]

                return {
                    "success": True,
                    "spreadsheet_id": data.get("spreadsheetId"),
                    "title": data.get("properties", {}).get("title"),
                    "locale": data.get("properties", {}).get("locale"),
                    "sheets": sheets_info,
                }

        except Exception as e:
            logger.error(f"sheets_get_metadata failed: {e}")
            return {"success": False, "error": str(e)}
