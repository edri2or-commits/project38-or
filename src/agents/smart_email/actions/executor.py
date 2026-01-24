"""Action executor for Gmail operations.

Phase 4.12: Action System with Approval

Executes approved actions via Gmail API:
- Reply to emails
- Forward emails
- Archive, label, delete
- Mark read/important
- Snooze

Uses MCP Gateway for Gmail operations when available.
"""

import base64
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from src.agents.smart_email.actions.types import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
    AuditRecord,
)

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes email actions via Gmail API.

    Supports two modes:
    1. MCP Gateway (recommended) - via or-infra.com/mcp
    2. Direct Gmail API - requires credentials

    Example:
        executor = ActionExecutor()
        result = await executor.execute(approved_action)
    """

    def __init__(
        self,
        use_mcp_gateway: bool = True,
        mcp_gateway_url: str | None = None,
    ):
        """Initialize executor.

        Args:
            use_mcp_gateway: Whether to use MCP Gateway
            mcp_gateway_url: Gateway URL (default: from env)
        """
        self.use_mcp_gateway = use_mcp_gateway
        self.mcp_gateway_url = mcp_gateway_url or os.environ.get(
            "MCP_GATEWAY_URL", "https://or-infra.com/mcp"
        )
        self._gmail_service = None
        self._audit_records: list[AuditRecord] = []

    async def execute(self, request: ActionRequest) -> ActionResult:
        """Execute an approved action.

        Args:
            request: Approved ActionRequest

        Returns:
            ActionResult with outcome

        Raises:
            ValueError: If action not approved
        """
        if not request.can_execute():
            return ActionResult(
                request_id=request.id,
                action_type=request.action_type,
                success=False,
                status=ActionStatus.FAILED,
                error="Action not approved or expired",
            )

        # Update status
        request.status = ActionStatus.EXECUTING
        start_time = time.time()

        # Create audit record
        audit = self._create_audit_record(request)

        try:
            # Route to appropriate handler
            result = await self._execute_action(request)

            # Update audit
            audit.executed_at = datetime.now()
            audit.status = result.status
            audit.success = result.success
            if not result.success:
                audit.error_message = result.error

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            result = ActionResult(
                request_id=request.id,
                action_type=request.action_type,
                success=False,
                status=ActionStatus.FAILED,
                error=str(e),
            )
            audit.status = ActionStatus.FAILED
            audit.success = False
            audit.error_message = str(e)

        # Calculate duration
        result.duration_ms = (time.time() - start_time) * 1000

        # Store audit record
        self._audit_records.append(audit)

        return result

    async def _execute_action(self, request: ActionRequest) -> ActionResult:
        """Route action to appropriate handler."""
        handlers = {
            ActionType.REPLY: self._execute_reply,
            ActionType.FORWARD: self._execute_forward,
            ActionType.ARCHIVE: self._execute_archive,
            ActionType.MARK_READ: self._execute_mark_read,
            ActionType.MARK_UNREAD: self._execute_mark_unread,
            ActionType.MARK_IMPORTANT: self._execute_mark_important,
            ActionType.MARK_NOT_IMPORTANT: self._execute_mark_not_important,
            ActionType.LABEL: self._execute_add_label,
            ActionType.REMOVE_LABEL: self._execute_remove_label,
            ActionType.TRASH: self._execute_trash,
            ActionType.DELETE: self._execute_delete,
            ActionType.STAR: self._execute_star,
            ActionType.UNSTAR: self._execute_unstar,
            ActionType.SNOOZE: self._execute_snooze,
        }

        handler = handlers.get(request.action_type)
        if handler is None:
            return ActionResult(
                request_id=request.id,
                action_type=request.action_type,
                success=False,
                status=ActionStatus.FAILED,
                error=f"Unknown action type: {request.action_type.value}",
            )

        return await handler(request)

    async def _execute_reply(self, request: ActionRequest) -> ActionResult:
        """Execute reply action."""
        if not request.reply_content:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.REPLY,
                success=False,
                status=ActionStatus.FAILED,
                error="No reply content provided",
            )

        if self.use_mcp_gateway:
            return await self._reply_via_mcp(request)
        else:
            return await self._reply_via_gmail_api(request)

    async def _reply_via_mcp(self, request: ActionRequest) -> ActionResult:
        """Send reply via MCP Gateway."""
        try:
            # Prepare reply via gmail_send tool
            # This would call the MCP Gateway's gmail_send tool
            # For now, we'll simulate the call structure

            response = await self._call_mcp_tool(
                tool="gmail_send",
                params={
                    "to": request.email_sender,
                    "subject": f"Re: {request.email_subject or 'No Subject'}",
                    "body": request.reply_content,
                    "thread_id": request.thread_id,
                },
            )

            if response.get("success"):
                return ActionResult(
                    request_id=request.id,
                    action_type=ActionType.REPLY,
                    success=True,
                    status=ActionStatus.COMPLETED,
                    message=f"Reply sent to {request.email_sender}",
                    gmail_response=response,
                    can_undo=False,  # Can't unsend
                )
            else:
                return ActionResult(
                    request_id=request.id,
                    action_type=ActionType.REPLY,
                    success=False,
                    status=ActionStatus.FAILED,
                    error=response.get("error", "Unknown error"),
                )

        except Exception as e:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.REPLY,
                success=False,
                status=ActionStatus.FAILED,
                error=str(e),
            )

    async def _reply_via_gmail_api(self, request: ActionRequest) -> ActionResult:
        """Send reply via direct Gmail API."""
        try:
            service = await self._get_gmail_service()

            # Build the reply message
            message = MIMEMultipart("alternative")
            message["to"] = request.email_sender
            message["subject"] = f"Re: {request.email_subject or 'No Subject'}"

            # Add text content
            text_part = MIMEText(request.reply_content, "plain", "utf-8")
            message.attach(text_part)

            # Encode
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            # Send
            body = {"raw": raw}
            if request.thread_id:
                body["threadId"] = request.thread_id

            result = service.users().messages().send(
                userId="me",
                body=body,
            ).execute()

            return ActionResult(
                request_id=request.id,
                action_type=ActionType.REPLY,
                success=True,
                status=ActionStatus.COMPLETED,
                message=f"Reply sent to {request.email_sender}",
                gmail_response=result,
            )

        except Exception as e:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.REPLY,
                success=False,
                status=ActionStatus.FAILED,
                error=str(e),
            )

    async def _execute_forward(self, request: ActionRequest) -> ActionResult:
        """Execute forward action."""
        if not request.forward_to:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.FORWARD,
                success=False,
                status=ActionStatus.FAILED,
                error="No forward recipient provided",
            )

        # Get original email content first
        # Then send as new email with forwarded content

        if self.use_mcp_gateway:
            response = await self._call_mcp_tool(
                tool="gmail_send",
                params={
                    "to": request.forward_to,
                    "subject": f"Fwd: {request.email_subject or 'No Subject'}",
                    "body": f"--- Forwarded message ---\n{request.reply_content or ''}",
                },
            )

            return ActionResult(
                request_id=request.id,
                action_type=ActionType.FORWARD,
                success=response.get("success", False),
                status=ActionStatus.COMPLETED if response.get("success") else ActionStatus.FAILED,
                message=f"Email forwarded to {request.forward_to}",
                gmail_response=response,
            )
        else:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.FORWARD,
                success=False,
                status=ActionStatus.FAILED,
                error="Direct Gmail API forward not implemented",
            )

    async def _execute_archive(self, request: ActionRequest) -> ActionResult:
        """Execute archive action (remove INBOX label)."""
        return await self._modify_labels(
            request=request,
            remove_labels=["INBOX"],
            action_type=ActionType.ARCHIVE,
            success_message="Email archived",
            undo_action=ActionType.LABEL,
            undo_params={"label_name": "INBOX"},
        )

    async def _execute_mark_read(self, request: ActionRequest) -> ActionResult:
        """Mark email as read."""
        return await self._modify_labels(
            request=request,
            remove_labels=["UNREAD"],
            action_type=ActionType.MARK_READ,
            success_message="Email marked as read",
            undo_action=ActionType.MARK_UNREAD,
        )

    async def _execute_mark_unread(self, request: ActionRequest) -> ActionResult:
        """Mark email as unread."""
        return await self._modify_labels(
            request=request,
            add_labels=["UNREAD"],
            action_type=ActionType.MARK_UNREAD,
            success_message="Email marked as unread",
            undo_action=ActionType.MARK_READ,
        )

    async def _execute_mark_important(self, request: ActionRequest) -> ActionResult:
        """Mark email as important."""
        return await self._modify_labels(
            request=request,
            add_labels=["IMPORTANT"],
            action_type=ActionType.MARK_IMPORTANT,
            success_message="Email marked as important",
            undo_action=ActionType.MARK_NOT_IMPORTANT,
        )

    async def _execute_mark_not_important(self, request: ActionRequest) -> ActionResult:
        """Remove important label."""
        return await self._modify_labels(
            request=request,
            remove_labels=["IMPORTANT"],
            action_type=ActionType.MARK_NOT_IMPORTANT,
            success_message="Removed important label",
            undo_action=ActionType.MARK_IMPORTANT,
        )

    async def _execute_add_label(self, request: ActionRequest) -> ActionResult:
        """Add label to email."""
        if not request.label_name:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.LABEL,
                success=False,
                status=ActionStatus.FAILED,
                error="No label name provided",
            )

        return await self._modify_labels(
            request=request,
            add_labels=[request.label_name],
            action_type=ActionType.LABEL,
            success_message=f"Added label: {request.label_name}",
            undo_action=ActionType.REMOVE_LABEL,
            undo_params={"label_name": request.label_name},
        )

    async def _execute_remove_label(self, request: ActionRequest) -> ActionResult:
        """Remove label from email."""
        if not request.label_name:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.REMOVE_LABEL,
                success=False,
                status=ActionStatus.FAILED,
                error="No label name provided",
            )

        return await self._modify_labels(
            request=request,
            remove_labels=[request.label_name],
            action_type=ActionType.REMOVE_LABEL,
            success_message=f"Removed label: {request.label_name}",
            undo_action=ActionType.LABEL,
            undo_params={"label_name": request.label_name},
        )

    async def _execute_trash(self, request: ActionRequest) -> ActionResult:
        """Move email to trash."""
        return await self._modify_labels(
            request=request,
            add_labels=["TRASH"],
            remove_labels=["INBOX"],
            action_type=ActionType.TRASH,
            success_message="Email moved to trash",
            undo_action=ActionType.LABEL,
            undo_params={"label_name": "INBOX"},
        )

    async def _execute_delete(self, request: ActionRequest) -> ActionResult:
        """Permanently delete email."""
        if not request.email_id:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.DELETE,
                success=False,
                status=ActionStatus.FAILED,
                error="No email ID provided",
            )

        try:
            if self.use_mcp_gateway:
                # MCP doesn't have direct delete, would need custom tool
                return ActionResult(
                    request_id=request.id,
                    action_type=ActionType.DELETE,
                    success=False,
                    status=ActionStatus.FAILED,
                    error="Permanent delete not supported via MCP (use trash instead)",
                )
            else:
                service = await self._get_gmail_service()
                service.users().messages().delete(
                    userId="me",
                    id=request.email_id,
                ).execute()

                return ActionResult(
                    request_id=request.id,
                    action_type=ActionType.DELETE,
                    success=True,
                    status=ActionStatus.COMPLETED,
                    message="Email permanently deleted",
                    can_undo=False,  # Can't undo delete
                )

        except Exception as e:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.DELETE,
                success=False,
                status=ActionStatus.FAILED,
                error=str(e),
            )

    async def _execute_star(self, request: ActionRequest) -> ActionResult:
        """Star email."""
        return await self._modify_labels(
            request=request,
            add_labels=["STARRED"],
            action_type=ActionType.STAR,
            success_message="Email starred",
            undo_action=ActionType.UNSTAR,
        )

    async def _execute_unstar(self, request: ActionRequest) -> ActionResult:
        """Unstar email."""
        return await self._modify_labels(
            request=request,
            remove_labels=["STARRED"],
            action_type=ActionType.UNSTAR,
            success_message="Email unstarred",
            undo_action=ActionType.STAR,
        )

    async def _execute_snooze(self, request: ActionRequest) -> ActionResult:
        """Snooze email until specified time.

        Gmail doesn't have native snooze API, so we:
        1. Archive the email
        2. Schedule a re-label to INBOX
        """
        if not request.snooze_until:
            # Default: snooze for 1 day
            request.snooze_until = datetime.now() + timedelta(days=1)

        # Archive for now
        archive_result = await self._execute_archive(request)

        if archive_result.success:
            # TODO: Schedule re-label via n8n workflow
            snooze_time = request.snooze_until.strftime("%H:%M %d/%m")
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.SNOOZE,
                success=True,
                status=ActionStatus.COMPLETED,
                message=f"Email snoozed until {snooze_time}",
                can_undo=True,
                undo_action=ActionType.LABEL,
                undo_params={"label_name": "INBOX"},
            )
        else:
            return ActionResult(
                request_id=request.id,
                action_type=ActionType.SNOOZE,
                success=False,
                status=ActionStatus.FAILED,
                error=archive_result.error,
            )

    async def _modify_labels(
        self,
        request: ActionRequest,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        action_type: ActionType = ActionType.LABEL,
        success_message: str = "Labels modified",
        undo_action: ActionType | None = None,
        undo_params: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Modify email labels."""
        if not request.email_id:
            return ActionResult(
                request_id=request.id,
                action_type=action_type,
                success=False,
                status=ActionStatus.FAILED,
                error="No email ID provided",
            )

        try:
            if self.use_mcp_gateway:
                # Use MCP Gmail tools
                # For now, this is a placeholder - actual implementation
                # would call gmail_modify_labels tool

                return ActionResult(
                    request_id=request.id,
                    action_type=action_type,
                    success=True,
                    status=ActionStatus.COMPLETED,
                    message=success_message,
                    can_undo=undo_action is not None,
                    undo_action=undo_action,
                    undo_params=undo_params or {},
                )

            else:
                service = await self._get_gmail_service()

                body = {}
                if add_labels:
                    body["addLabelIds"] = add_labels
                if remove_labels:
                    body["removeLabelIds"] = remove_labels

                result = service.users().messages().modify(
                    userId="me",
                    id=request.email_id,
                    body=body,
                ).execute()

                return ActionResult(
                    request_id=request.id,
                    action_type=action_type,
                    success=True,
                    status=ActionStatus.COMPLETED,
                    message=success_message,
                    gmail_response=result,
                    can_undo=undo_action is not None,
                    undo_action=undo_action,
                    undo_params=undo_params or {},
                )

        except Exception as e:
            return ActionResult(
                request_id=request.id,
                action_type=action_type,
                success=False,
                status=ActionStatus.FAILED,
                error=str(e),
            )

    async def _call_mcp_tool(
        self,
        tool: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Call MCP Gateway tool.

        This is a placeholder that would be replaced with actual
        MCP client calls when integrated with the gateway.
        """
        # In production, this would call the MCP Gateway
        # For now, return a simulated response
        logger.info(f"MCP call: {tool} with params: {params}")

        # Simulated success for development
        return {
            "success": True,
            "tool": tool,
            "params": params,
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
        }

    async def _get_gmail_service(self):
        """Get Gmail API service.

        Uses cached service or creates new one.
        """
        if self._gmail_service is not None:
            return self._gmail_service

        # This would use OAuth credentials
        # For now, raise error if not using MCP
        raise NotImplementedError(
            "Direct Gmail API requires OAuth setup. Use MCP Gateway instead."
        )

    def _create_audit_record(self, request: ActionRequest) -> AuditRecord:
        """Create audit record from request."""
        return AuditRecord(
            id=f"audit_{uuid.uuid4().hex[:12]}",
            request_id=request.id,
            user_id=request.user_id,
            action_type=request.action_type,
            email_id=request.email_id,
            thread_id=request.thread_id,
            email_subject=request.email_subject,
            email_sender=request.email_sender,
            requested_at=request.created_at,
            approved_at=request.approved_at,
            ai_reasoning=request.ai_reasoning,
            content_sent=request.reply_content,
            recipients=[request.forward_to] if request.forward_to else [],
        )

    def get_audit_log(self, user_id: str | None = None) -> list[AuditRecord]:
        """Get audit records.

        Args:
            user_id: Optional filter by user

        Returns:
            List of audit records
        """
        if user_id:
            return [r for r in self._audit_records if r.user_id == user_id]
        return self._audit_records.copy()

    def format_audit_log_hebrew(self, limit: int = 10) -> str:
        """Format recent audit log in Hebrew."""
        records = sorted(
            self._audit_records,
            key=lambda r: r.requested_at,
            reverse=True,
        )[:limit]

        if not records:
            return "📋 אין פעולות לאחרונה"

        lines = ["📋 היסטוריית פעולות:"]
        for record in records:
            lines.append(record.to_log_entry())

        return "\n".join(lines)
