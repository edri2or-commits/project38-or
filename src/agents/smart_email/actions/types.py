"""Action types and results for email actions.

Phase 4.12: Action System with Approval

Defines action data structures:
- ActionRequest: What user wants to do
- ActionResult: Outcome of execution
- AuditRecord: Compliance logging
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ActionType(Enum):
    """Types of actions user can request."""

    REPLY = "reply"
    FORWARD = "forward"
    ARCHIVE = "archive"
    MARK_READ = "mark_read"
    MARK_UNREAD = "mark_unread"
    MARK_IMPORTANT = "mark_important"
    MARK_NOT_IMPORTANT = "mark_not_important"
    SNOOZE = "snooze"
    LABEL = "label"
    REMOVE_LABEL = "remove_label"
    DELETE = "delete"
    TRASH = "trash"
    STAR = "star"
    UNSTAR = "unstar"


class ActionStatus(Enum):
    """Status of an action."""

    PENDING = "pending"  # Awaiting approval
    APPROVED = "approved"  # Approved by user
    REJECTED = "rejected"  # Rejected by user
    EXECUTING = "executing"  # Currently running
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed to execute
    CANCELLED = "cancelled"  # Cancelled before execution
    EXPIRED = "expired"  # Approval window expired


@dataclass
class ActionRequest:
    """Request to perform an action.

    Created when user requests action, awaits approval.
    """

    id: str
    action_type: ActionType
    user_id: str
    chat_id: str

    # Target email
    email_id: str | None = None
    thread_id: str | None = None
    email_subject: str | None = None
    email_sender: str | None = None

    # Action-specific parameters
    reply_content: str | None = None  # For REPLY
    forward_to: str | None = None  # For FORWARD
    label_name: str | None = None  # For LABEL/REMOVE_LABEL
    snooze_until: datetime | None = None  # For SNOOZE

    # Metadata
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    expires_at: datetime | None = None

    # AI-generated context
    ai_reasoning: str | None = None
    confidence_score: float = 0.0

    def is_expired(self) -> bool:
        """Check if approval window expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def can_execute(self) -> bool:
        """Check if action can be executed."""
        return (
            self.status == ActionStatus.APPROVED
            and not self.is_expired()
        )


@dataclass
class ActionResult:
    """Result of action execution."""

    request_id: str
    action_type: ActionType
    success: bool
    status: ActionStatus

    # Result details
    message: str = ""
    error: str | None = None
    gmail_response: dict[str, Any] = field(default_factory=dict)

    # Timing
    executed_at: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0

    # Undo capability
    can_undo: bool = False
    undo_action: ActionType | None = None
    undo_params: dict[str, Any] = field(default_factory=dict)

    def to_hebrew(self) -> str:
        """Get Hebrew description of result."""
        action_names = {
            ActionType.REPLY: "תשובה",
            ActionType.FORWARD: "העברה",
            ActionType.ARCHIVE: "ארכיון",
            ActionType.MARK_READ: "סימון כנקרא",
            ActionType.MARK_UNREAD: "סימון כלא נקרא",
            ActionType.MARK_IMPORTANT: "סימון כחשוב",
            ActionType.SNOOZE: "דחייה",
            ActionType.LABEL: "הוספת תווית",
            ActionType.DELETE: "מחיקה",
            ActionType.TRASH: "העברה לאשפה",
            ActionType.STAR: "סימון בכוכב",
        }

        action_name = action_names.get(self.action_type, self.action_type.value)

        if self.success:
            return f"✅ {action_name} בוצעה בהצלחה"
        else:
            return f"❌ {action_name} נכשלה: {self.error or 'שגיאה לא ידועה'}"


@dataclass
class AuditRecord:
    """Audit record for compliance.

    All actions are logged for:
    - Compliance (who did what when)
    - Undo capability
    - Analytics
    """

    id: str
    request_id: str
    user_id: str
    action_type: ActionType

    # Target
    email_id: str | None = None
    thread_id: str | None = None
    email_subject: str | None = None
    email_sender: str | None = None

    # Timeline
    requested_at: datetime = field(default_factory=datetime.now)
    approved_at: datetime | None = None
    executed_at: datetime | None = None

    # Outcome
    status: ActionStatus = ActionStatus.PENDING
    success: bool | None = None
    error_message: str | None = None

    # For reply/forward
    content_sent: str | None = None
    recipients: list[str] = field(default_factory=list)

    # Context
    ai_reasoning: str | None = None
    user_message: str | None = None  # Original user request

    def to_log_entry(self) -> str:
        """Format as log entry."""
        status_emoji = {
            ActionStatus.PENDING: "⏳",
            ActionStatus.APPROVED: "👍",
            ActionStatus.REJECTED: "👎",
            ActionStatus.COMPLETED: "✅",
            ActionStatus.FAILED: "❌",
            ActionStatus.CANCELLED: "🚫",
        }

        emoji = status_emoji.get(self.status, "❓")
        timestamp = self.executed_at or self.requested_at

        return (
            f"{emoji} [{timestamp.isoformat()}] "
            f"User {self.user_id}: {self.action_type.value} "
            f"on email '{self.email_subject or self.email_id}' "
            f"- {self.status.value}"
        )
