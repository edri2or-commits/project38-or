"""Google Calendar MCP Tools.

Provides tools for calendar operations:
- calendar_list: List calendars
- calendar_events: List events
- calendar_create_event: Create an event
- calendar_update_event: Update an event
- calendar_delete_event: Delete an event
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from src.workspace_mcp_bridge.auth import GoogleOAuthManager

logger = logging.getLogger(__name__)

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


def register_calendar_tools(mcp: Any, oauth_manager: GoogleOAuthManager) -> None:
    """Register Calendar tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        oauth_manager: OAuth manager for authentication
    """

    @mcp.tool()
    async def calendar_list() -> dict[str, Any]:
        """List all calendars.

        Returns:
            List of available calendars
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{CALENDAR_API_BASE}/users/me/calendarList",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to list calendars: {response.text}",
                    }

                data = response.json()
                calendars = [
                    {
                        "id": cal["id"],
                        "summary": cal.get("summary", ""),
                        "primary": cal.get("primary", False),
                        "access_role": cal.get("accessRole", ""),
                    }
                    for cal in data.get("items", [])
                ]

                return {
                    "success": True,
                    "count": len(calendars),
                    "calendars": calendars,
                }

        except Exception as e:
            logger.error(f"calendar_list failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def calendar_events(
        calendar_id: str = "primary",
        time_min: str = "",
        time_max: str = "",
        max_results: int = 10,
    ) -> dict[str, Any]:
        """List events from a calendar.

        Args:
            calendar_id: Calendar ID (default: "primary")
            time_min: Start time in ISO format (default: now)
            time_max: End time in ISO format (default: 7 days from now)
            max_results: Maximum number of events (default: 10)

        Returns:
            List of calendar events
        """
        try:
            token = await oauth_manager.get_access_token()

            # Default time range: now to 7 days from now
            if not time_min:
                time_min = datetime.utcnow().isoformat() + "Z"
            if not time_max:
                time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "maxResults": max_results,
                        "singleEvents": True,
                        "orderBy": "startTime",
                    },
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to list events: {response.text}",
                    }

                data = response.json()
                events = [
                    {
                        "id": event["id"],
                        "summary": event.get("summary", ""),
                        "start": event.get("start", {}).get("dateTime")
                            or event.get("start", {}).get("date"),
                        "end": event.get("end", {}).get("dateTime")
                            or event.get("end", {}).get("date"),
                        "location": event.get("location", ""),
                        "description": event.get("description", ""),
                        "attendees": [
                            a.get("email") for a in event.get("attendees", [])
                        ],
                        "html_link": event.get("htmlLink", ""),
                    }
                    for event in data.get("items", [])
                ]

                return {
                    "success": True,
                    "calendar_id": calendar_id,
                    "count": len(events),
                    "events": events,
                }

        except Exception as e:
            logger.error(f"calendar_events failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def calendar_create_event(
        summary: str,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        description: str = "",
        location: str = "",
        attendees: str = "",
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Create a calendar event.

        Args:
            summary: Event title
            start_time: Start time in ISO format
            end_time: End time in ISO format
            calendar_id: Calendar ID (default: "primary")
            description: Event description
            location: Event location
            attendees: Comma-separated email addresses
            timezone: Timezone (default: UTC)

        Returns:
            Created event details
        """
        try:
            token = await oauth_manager.get_access_token()

            event_body: dict[str, Any] = {
                "summary": summary,
                "start": {"dateTime": start_time, "timeZone": timezone},
                "end": {"dateTime": end_time, "timeZone": timezone},
            }

            if description:
                event_body["description"] = description
            if location:
                event_body["location"] = location
            if attendees:
                event_body["attendees"] = [
                    {"email": email.strip()}
                    for email in attendees.split(",")
                ]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events",
                    headers={"Authorization": f"Bearer {token}"},
                    json=event_body,
                )

                if response.status_code not in (200, 201):
                    return {
                        "success": False,
                        "error": f"Failed to create event: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "event_id": data.get("id"),
                    "summary": data.get("summary"),
                    "html_link": data.get("htmlLink"),
                    "start": data.get("start", {}).get("dateTime"),
                    "end": data.get("end", {}).get("dateTime"),
                }

        except Exception as e:
            logger.error(f"calendar_create_event failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def calendar_update_event(
        event_id: str,
        calendar_id: str = "primary",
        summary: str = "",
        start_time: str = "",
        end_time: str = "",
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """Update a calendar event.

        Args:
            event_id: Event ID to update
            calendar_id: Calendar ID (default: "primary")
            summary: New event title (optional)
            start_time: New start time in ISO format (optional)
            end_time: New end time in ISO format (optional)
            description: New description (optional)
            location: New location (optional)

        Returns:
            Updated event details
        """
        try:
            token = await oauth_manager.get_access_token()

            # First, get current event
            async with httpx.AsyncClient() as client:
                get_response = await client.get(
                    f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if get_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Event not found: {get_response.text}",
                    }

                event_body = get_response.json()

                # Update fields
                if summary:
                    event_body["summary"] = summary
                if start_time:
                    event_body["start"]["dateTime"] = start_time
                if end_time:
                    event_body["end"]["dateTime"] = end_time
                if description:
                    event_body["description"] = description
                if location:
                    event_body["location"] = location

                # Update event
                response = await client.put(
                    f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    json=event_body,
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to update event: {response.text}",
                    }

                data = response.json()
                return {
                    "success": True,
                    "event_id": data.get("id"),
                    "summary": data.get("summary"),
                    "html_link": data.get("htmlLink"),
                }

        except Exception as e:
            logger.error(f"calendar_update_event failed: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def calendar_delete_event(
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Delete a calendar event.

        Args:
            event_id: Event ID to delete
            calendar_id: Calendar ID (default: "primary")

        Returns:
            Deletion result
        """
        try:
            token = await oauth_manager.get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code not in (200, 204):
                    return {
                        "success": False,
                        "error": f"Failed to delete event: {response.text}",
                    }

                return {
                    "success": True,
                    "event_id": event_id,
                    "deleted": True,
                }

        except Exception as e:
            logger.error(f"calendar_delete_event failed: {e}")
            return {"success": False, "error": str(e)}
