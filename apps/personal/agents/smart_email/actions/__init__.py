"""Actions module for Smart Email Agent.

Phase 4.12: Action System with Approval

Enables execution of email actions with user approval:
- Reply, forward, archive, label
- Approval workflow with timeout
- Full audit logging

Example:
    from apps.personal.agents.smart_email.actions import (
        ApprovalManager,
        ActionExecutor,
        ActionType,
    )

    # Create manager
    manager = ApprovalManager()

    # Propose action
    proposal = manager.create_proposal(
        action_type=ActionType.REPLY,
        user_id="user_123",
        chat_id="chat_456",
        email_sender="dan@example.com",
        reply_content="אני מאשר את ההצעה",
    )

    # Show to user via Telegram
    text = manager.format_proposal_hebrew(proposal)
    buttons = manager.get_keyboard_options(proposal)

    # When user approves
    result = await manager.approve(proposal.id)
    print(result.to_hebrew())  # "✅ תשובה בוצעה בהצלחה"
"""

from apps.personal.agents.smart_email.actions.approval import (
    ApprovalManager,
    create_approval_manager,
)
from apps.personal.agents.smart_email.actions.executor import ActionExecutor
from apps.personal.agents.smart_email.actions.types import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
    AuditRecord,
)

__all__ = [
    # Types
    "ActionType",
    "ActionStatus",
    "ActionRequest",
    "ActionResult",
    "AuditRecord",
    # Executor
    "ActionExecutor",
    # Approval
    "ApprovalManager",
    "create_approval_manager",
]
