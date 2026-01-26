"""Approval flow for email actions.

Phase 4.12: Action System with Approval

Manages the approval workflow:
1. AI proposes action → Creates ActionRequest
2. User sees proposal → Can approve/reject
3. If approved → ActionExecutor runs
4. All actions logged for audit

Flow:
    User: "תשלח לו שאני מאשר"
        ↓
    ConversationHandler detects ACTION_REQUEST
        ↓
    ApprovalManager.create_proposal()
        ↓
    Telegram shows: "האם לשלוח תשובה: 'אני מאשר' לדני?"
                    [כן ✓] [לא ✗] [עריכה ✏️]
        ↓
    User clicks [כן]
        ↓
    ApprovalManager.approve() → ActionExecutor.execute()
        ↓
    Telegram shows: "✅ התשובה נשלחה לדני"
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from apps.personal.agents.smart_email.actions.executor import ActionExecutor
from apps.personal.agents.smart_email.actions.types import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
)

logger = logging.getLogger(__name__)

# Default approval expiration (5 minutes)
DEFAULT_APPROVAL_TIMEOUT_MINUTES = 5


class ApprovalManager:
    """Manages action approval workflow.

    Coordinates between:
    - ConversationHandler (creates proposals)
    - Telegram Bot (shows approve/reject buttons)
    - ActionExecutor (runs approved actions)

    Example:
        manager = ApprovalManager()

        # Create proposal
        proposal = manager.create_proposal(
            action_type=ActionType.REPLY,
            user_id="user_123",
            email_id="msg_abc",
            reply_content="אני מאשר את ההצעה",
        )

        # User approves
        result = await manager.approve(proposal.id)

        # Or user rejects
        manager.reject(proposal.id, reason="לא מתאים")
    """

    def __init__(
        self,
        executor: ActionExecutor | None = None,
        approval_timeout_minutes: int = DEFAULT_APPROVAL_TIMEOUT_MINUTES,
    ):
        """Initialize approval manager.

        Args:
            executor: ActionExecutor instance (creates default if None)
            approval_timeout_minutes: How long approvals are valid
        """
        self.executor = executor or ActionExecutor()
        self.approval_timeout = timedelta(minutes=approval_timeout_minutes)
        self._pending: dict[str, ActionRequest] = {}
        self._history: list[ActionRequest] = []

    def create_proposal(
        self,
        action_type: ActionType,
        user_id: str,
        chat_id: str,
        email_id: str | None = None,
        thread_id: str | None = None,
        email_subject: str | None = None,
        email_sender: str | None = None,
        reply_content: str | None = None,
        forward_to: str | None = None,
        label_name: str | None = None,
        snooze_until: datetime | None = None,
        ai_reasoning: str | None = None,
        confidence_score: float = 0.0,
    ) -> ActionRequest:
        """Create action proposal awaiting approval.

        Args:
            action_type: Type of action
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            email_id: Target email ID
            thread_id: Thread ID for replies
            email_subject: Email subject (for display)
            email_sender: Email sender (for display)
            reply_content: Content for REPLY action
            forward_to: Recipient for FORWARD action
            label_name: Label for LABEL action
            snooze_until: When to unsnooze
            ai_reasoning: Why AI suggested this
            confidence_score: AI confidence (0-1)

        Returns:
            ActionRequest with PENDING status
        """
        request_id = f"req_{uuid.uuid4().hex[:12]}"

        request = ActionRequest(
            id=request_id,
            action_type=action_type,
            user_id=user_id,
            chat_id=chat_id,
            email_id=email_id,
            thread_id=thread_id,
            email_subject=email_subject,
            email_sender=email_sender,
            reply_content=reply_content,
            forward_to=forward_to,
            label_name=label_name,
            snooze_until=snooze_until,
            status=ActionStatus.PENDING,
            created_at=datetime.now(),
            expires_at=datetime.now() + self.approval_timeout,
            ai_reasoning=ai_reasoning,
            confidence_score=confidence_score,
        )

        self._pending[request_id] = request

        logger.info(
            f"Created proposal {request_id}: {action_type.value} "
            f"for user {user_id}"
        )

        return request

    async def approve(
        self,
        request_id: str,
        modified_content: str | None = None,
    ) -> ActionResult:
        """Approve and execute an action.

        Args:
            request_id: ID of the pending request
            modified_content: Optional modified content (for edits)

        Returns:
            ActionResult from execution

        Raises:
            ValueError: If request not found or expired
        """
        request = self._pending.get(request_id)

        if request is None:
            raise ValueError(f"Request {request_id} not found")

        if request.is_expired():
            request.status = ActionStatus.EXPIRED
            self._move_to_history(request_id)
            raise ValueError(f"Request {request_id} has expired")

        # Apply modifications if provided
        if modified_content and request.action_type == ActionType.REPLY:
            request.reply_content = modified_content

        # Update status
        request.status = ActionStatus.APPROVED
        request.approved_at = datetime.now()

        logger.info(f"Approved request {request_id}")

        # Execute the action
        result = await self.executor.execute(request)

        # Update request status based on result
        request.status = result.status
        request.executed_at = result.executed_at

        # Move to history
        self._move_to_history(request_id)

        return result

    def reject(
        self,
        request_id: str,
        reason: str | None = None,
    ) -> bool:
        """Reject a pending action.

        Args:
            request_id: ID of the pending request
            reason: Optional rejection reason

        Returns:
            True if rejected, False if not found
        """
        request = self._pending.get(request_id)

        if request is None:
            return False

        request.status = ActionStatus.REJECTED

        logger.info(
            f"Rejected request {request_id}"
            + (f": {reason}" if reason else "")
        )

        self._move_to_history(request_id)
        return True

    def cancel(self, request_id: str) -> bool:
        """Cancel a pending action.

        Args:
            request_id: ID of the pending request

        Returns:
            True if cancelled, False if not found
        """
        request = self._pending.get(request_id)

        if request is None:
            return False

        request.status = ActionStatus.CANCELLED
        self._move_to_history(request_id)
        return True

    def get_pending(self, user_id: str | None = None) -> list[ActionRequest]:
        """Get pending requests.

        Args:
            user_id: Optional filter by user

        Returns:
            List of pending requests
        """
        # Clean expired first
        self._clean_expired()

        if user_id:
            return [
                r for r in self._pending.values()
                if r.user_id == user_id
            ]
        return list(self._pending.values())

    def get_pending_for_user(self, user_id: str) -> ActionRequest | None:
        """Get the most recent pending request for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Most recent pending request or None
        """
        pending = self.get_pending(user_id)
        if pending:
            return max(pending, key=lambda r: r.created_at)
        return None

    def _move_to_history(self, request_id: str) -> None:
        """Move request from pending to history."""
        request = self._pending.pop(request_id, None)
        if request:
            self._history.append(request)

    def _clean_expired(self) -> None:
        """Clean up expired requests."""
        now = datetime.now()
        expired = [
            rid for rid, req in self._pending.items()
            if req.expires_at and req.expires_at < now
        ]

        for rid in expired:
            self._pending[rid].status = ActionStatus.EXPIRED
            self._move_to_history(rid)

        if expired:
            logger.info(f"Cleaned {len(expired)} expired requests")

    def format_proposal_hebrew(self, request: ActionRequest) -> str:
        """Format proposal for Telegram display.

        Args:
            request: Action request

        Returns:
            Hebrew formatted string
        """
        action_descriptions = {
            ActionType.REPLY: "לשלוח תשובה",
            ActionType.FORWARD: "להעביר את המייל",
            ActionType.ARCHIVE: "לארכב את המייל",
            ActionType.MARK_READ: "לסמן כנקרא",
            ActionType.MARK_IMPORTANT: "לסמן כחשוב",
            ActionType.SNOOZE: "לדחות את המייל",
            ActionType.LABEL: "להוסיף תווית",
            ActionType.DELETE: "למחוק את המייל",
            ActionType.TRASH: "להעביר לאשפה",
            ActionType.STAR: "לסמן בכוכב",
        }

        action_desc = action_descriptions.get(
            request.action_type,
            request.action_type.value
        )

        lines = [f"🤔 האם {action_desc}?"]

        # Add target info
        if request.email_sender:
            lines.append(f"📧 מאת: {request.email_sender}")

        if request.email_subject:
            # Truncate long subjects
            subject = request.email_subject[:50]
            if len(request.email_subject) > 50:
                subject += "..."
            lines.append(f"📝 נושא: {subject}")

        # Action-specific details
        if request.action_type == ActionType.REPLY and request.reply_content:
            content_preview = request.reply_content[:100]
            if len(request.reply_content) > 100:
                content_preview += "..."
            lines.append(f"\n💬 תוכן התשובה:\n\"{content_preview}\"")

        if request.action_type == ActionType.FORWARD and request.forward_to:
            lines.append(f"📤 יועבר ל: {request.forward_to}")

        if request.action_type == ActionType.LABEL and request.label_name:
            lines.append(f"🏷️ תווית: {request.label_name}")

        if request.action_type == ActionType.SNOOZE and request.snooze_until:
            snooze_str = request.snooze_until.strftime("%H:%M %d/%m")
            lines.append(f"⏰ יוצג שוב: {snooze_str}")

        # Add AI reasoning if present
        if request.ai_reasoning:
            lines.append(f"\n💡 {request.ai_reasoning}")

        # Add expiration
        if request.expires_at:
            minutes_left = (request.expires_at - datetime.now()).seconds // 60
            if minutes_left > 0:
                lines.append(f"\n⏳ יפוג בעוד {minutes_left} דקות")

        return "\n".join(lines)

    def get_keyboard_options(self, request: ActionRequest) -> list[dict[str, str]]:
        """Get Telegram keyboard options for approval.

        Args:
            request: Action request

        Returns:
            List of button options
        """
        buttons = [
            {"text": "✅ אשר", "callback_data": f"approve:{request.id}"},
            {"text": "❌ בטל", "callback_data": f"reject:{request.id}"},
        ]

        # Add edit option for reply/forward
        if request.action_type in (ActionType.REPLY, ActionType.FORWARD):
            buttons.append({
                "text": "✏️ ערוך",
                "callback_data": f"edit:{request.id}",
            })

        return buttons


def create_approval_manager(
    use_mcp_gateway: bool = True,
    timeout_minutes: int = DEFAULT_APPROVAL_TIMEOUT_MINUTES,
) -> ApprovalManager:
    """Create configured approval manager.

    Args:
        use_mcp_gateway: Whether to use MCP Gateway
        timeout_minutes: Approval timeout

    Returns:
        Configured ApprovalManager
    """
    executor = ActionExecutor(use_mcp_gateway=use_mcp_gateway)
    return ApprovalManager(
        executor=executor,
        approval_timeout_minutes=timeout_minutes,
    )
