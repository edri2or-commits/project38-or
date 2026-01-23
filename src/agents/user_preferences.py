"""User Preferences - Learns from user actions and personalizes the email agent.

Tracks user behavior and preferences to improve:
- Email priority classification
- Reply tone selection
- Important senders identification
- Time preferences for notifications

ADR-014 Phase 3: Learning from User Feedback
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of user actions to learn from."""

    # Email actions
    MARKED_IMPORTANT = "marked_important"
    MARKED_SPAM = "marked_spam"
    ARCHIVED = "archived"
    REPLIED = "replied"
    IGNORED = "ignored"

    # Draft actions
    DRAFT_ACCEPTED = "draft_accepted"
    DRAFT_MODIFIED = "draft_modified"
    DRAFT_REJECTED = "draft_rejected"

    # Deadline actions
    DEADLINE_COMPLETED = "deadline_completed"
    DEADLINE_SNOOZED = "deadline_snoozed"
    DEADLINE_DISMISSED = "deadline_dismissed"

    # Notification preferences
    NOTIFICATION_HELPFUL = "notification_helpful"
    NOTIFICATION_NOT_HELPFUL = "notification_not_helpful"


@dataclass
class UserAction:
    """Record of a user action."""

    action_type: ActionType
    timestamp: datetime
    context: dict[str, Any]  # Email ID, sender, category, etc.


@dataclass
class SenderProfile:
    """Profile of a known sender."""

    email: str
    display_name: str
    importance: float  # 0.0 to 1.0
    category: str  # work, personal, bureaucracy, etc.
    preferred_tone: str  # formal, professional, friendly
    total_emails: int = 0
    replied_count: int = 0
    ignored_count: int = 0
    last_contact: datetime | None = None


@dataclass
class UserProfile:
    """User's personal profile for form pre-filling."""

    id_number: str = ""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    birth_date: str = ""
    bank_account: str = ""
    bank_branch: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {
            "id_number": self.id_number,
            "full_name": self.full_name,
            "name": self.full_name,  # Alias
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "birth_date": self.birth_date,
            "bank_account": self.bank_account,
            "bank_branch": self.bank_branch,
        }


@dataclass
class NotificationPreferences:
    """User's notification preferences."""

    # Quiet hours (no notifications)
    quiet_start_hour: int = 22  # 22:00
    quiet_end_hour: int = 7  # 07:00

    # Daily summary time
    summary_hour: int = 7  # 07:00

    # Notification types
    notify_p1_immediately: bool = True
    notify_p2_in_summary: bool = True
    notify_deadlines: bool = True
    notify_draft_ready: bool = False

    # Language
    language: str = "he"  # Hebrew


class UserPreferences:
    """Manages user preferences and learns from behavior.

    Tracks user actions to improve email classification, reply generation,
    and notification timing.

    Example:
        prefs = UserPreferences()

        # Record an action
        prefs.record_action(
            ActionType.MARKED_IMPORTANT,
            {"email_id": "123", "sender": "boss@company.com"}
        )

        # Get sender importance
        importance = prefs.get_sender_importance("boss@company.com")

        # Get profile for form filling
        profile = prefs.get_user_profile()
    """

    def __init__(self, storage_path: str | None = None):
        """Initialize UserPreferences.

        Args:
            storage_path: Path to JSON storage file
        """
        self.storage_path = Path(storage_path or "/tmp/user_preferences.json")
        self._actions: list[UserAction] = []
        self._senders: dict[str, SenderProfile] = {}
        self._user_profile: UserProfile = UserProfile()
        self._notification_prefs: NotificationPreferences = NotificationPreferences()
        self._category_weights: dict[str, float] = {}  # Learned category importance
        self._load()

    def _load(self) -> None:
        """Load preferences from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())

                # Load user profile
                if "user_profile" in data:
                    up = data["user_profile"]
                    self._user_profile = UserProfile(
                        id_number=up.get("id_number", ""),
                        full_name=up.get("full_name", ""),
                        email=up.get("email", ""),
                        phone=up.get("phone", ""),
                        address=up.get("address", ""),
                        birth_date=up.get("birth_date", ""),
                        bank_account=up.get("bank_account", ""),
                        bank_branch=up.get("bank_branch", ""),
                    )

                # Load notification preferences
                if "notification_prefs" in data:
                    np = data["notification_prefs"]
                    self._notification_prefs = NotificationPreferences(
                        quiet_start_hour=np.get("quiet_start_hour", 22),
                        quiet_end_hour=np.get("quiet_end_hour", 7),
                        summary_hour=np.get("summary_hour", 7),
                        notify_p1_immediately=np.get("notify_p1_immediately", True),
                        notify_p2_in_summary=np.get("notify_p2_in_summary", True),
                        notify_deadlines=np.get("notify_deadlines", True),
                        notify_draft_ready=np.get("notify_draft_ready", False),
                        language=np.get("language", "he"),
                    )

                # Load senders
                for sender_data in data.get("senders", []):
                    sender = SenderProfile(
                        email=sender_data["email"],
                        display_name=sender_data.get("display_name", ""),
                        importance=sender_data.get("importance", 0.5),
                        category=sender_data.get("category", "unknown"),
                        preferred_tone=sender_data.get("preferred_tone", "professional"),
                        total_emails=sender_data.get("total_emails", 0),
                        replied_count=sender_data.get("replied_count", 0),
                        ignored_count=sender_data.get("ignored_count", 0),
                    )
                    self._senders[sender.email] = sender

                # Load category weights
                self._category_weights = data.get("category_weights", {})

                # Load recent actions (last 100)
                for action_data in data.get("actions", [])[-100:]:
                    try:
                        action = UserAction(
                            action_type=ActionType(action_data["action_type"]),
                            timestamp=datetime.fromisoformat(action_data["timestamp"]),
                            context=action_data.get("context", {}),
                        )
                        self._actions.append(action)
                    except (ValueError, KeyError):
                        continue

                logger.info(
                    f"Loaded preferences: {len(self._senders)} senders, "
                    f"{len(self._actions)} actions"
                )

            except Exception as e:
                logger.error(f"Failed to load preferences: {e}")

    def _save(self) -> None:
        """Save preferences to storage."""
        try:
            data = {
                "user_profile": {
                    "id_number": self._user_profile.id_number,
                    "full_name": self._user_profile.full_name,
                    "email": self._user_profile.email,
                    "phone": self._user_profile.phone,
                    "address": self._user_profile.address,
                    "birth_date": self._user_profile.birth_date,
                    "bank_account": self._user_profile.bank_account,
                    "bank_branch": self._user_profile.bank_branch,
                },
                "notification_prefs": {
                    "quiet_start_hour": self._notification_prefs.quiet_start_hour,
                    "quiet_end_hour": self._notification_prefs.quiet_end_hour,
                    "summary_hour": self._notification_prefs.summary_hour,
                    "notify_p1_immediately": self._notification_prefs.notify_p1_immediately,
                    "notify_p2_in_summary": self._notification_prefs.notify_p2_in_summary,
                    "notify_deadlines": self._notification_prefs.notify_deadlines,
                    "notify_draft_ready": self._notification_prefs.notify_draft_ready,
                    "language": self._notification_prefs.language,
                },
                "senders": [
                    {
                        "email": s.email,
                        "display_name": s.display_name,
                        "importance": s.importance,
                        "category": s.category,
                        "preferred_tone": s.preferred_tone,
                        "total_emails": s.total_emails,
                        "replied_count": s.replied_count,
                        "ignored_count": s.ignored_count,
                    }
                    for s in self._senders.values()
                ],
                "category_weights": self._category_weights,
                "actions": [
                    {
                        "action_type": a.action_type.value,
                        "timestamp": a.timestamp.isoformat(),
                        "context": a.context,
                    }
                    for a in self._actions[-100:]  # Keep last 100
                ],
                "updated_at": datetime.now(UTC).isoformat(),
            }

            self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            logger.info("Saved user preferences")

        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")

    def record_action(self, action_type: ActionType, context: dict[str, Any]) -> None:
        """Record a user action for learning.

        Args:
            action_type: Type of action
            context: Additional context (email_id, sender, etc.)
        """
        action = UserAction(
            action_type=action_type,
            timestamp=datetime.now(UTC),
            context=context,
        )
        self._actions.append(action)

        # Update sender profile based on action
        sender_email = context.get("sender", "").lower()
        if sender_email:
            self._update_sender_from_action(sender_email, action_type, context)

        # Update category weights
        category = context.get("category")
        if category:
            self._update_category_weight(category, action_type)

        self._save()

    def _update_sender_from_action(
        self,
        email: str,
        action_type: ActionType,
        context: dict,
    ) -> None:
        """Update sender profile based on action.

        Args:
            email: Sender email
            action_type: Action taken
            context: Action context
        """
        if email not in self._senders:
            self._senders[email] = SenderProfile(
                email=email,
                display_name=context.get("sender_name", email.split("@")[0]),
                importance=0.5,
                category="unknown",
                preferred_tone="professional",
            )

        sender = self._senders[email]
        sender.total_emails += 1
        sender.last_contact = datetime.now(UTC)

        # Adjust importance based on action
        importance_adjustments = {
            ActionType.MARKED_IMPORTANT: 0.1,
            ActionType.REPLIED: 0.05,
            ActionType.DRAFT_ACCEPTED: 0.03,
            ActionType.MARKED_SPAM: -0.3,
            ActionType.IGNORED: -0.02,
            ActionType.ARCHIVED: -0.01,
        }

        adjustment = importance_adjustments.get(action_type, 0)
        sender.importance = max(0.0, min(1.0, sender.importance + adjustment))

        # Update reply counts
        if action_type == ActionType.REPLIED:
            sender.replied_count += 1
        elif action_type == ActionType.IGNORED:
            sender.ignored_count += 1

        # Update category if provided
        if context.get("category"):
            sender.category = context["category"]

        # Update preferred tone if modified
        if action_type == ActionType.DRAFT_MODIFIED and context.get("new_tone"):
            sender.preferred_tone = context["new_tone"]

    def _update_category_weight(self, category: str, action_type: ActionType) -> None:
        """Update category importance weight.

        Args:
            category: Email category
            action_type: Action taken
        """
        if category not in self._category_weights:
            self._category_weights[category] = 1.0

        weight_adjustments = {
            ActionType.MARKED_IMPORTANT: 0.1,
            ActionType.REPLIED: 0.05,
            ActionType.MARKED_SPAM: -0.2,
            ActionType.IGNORED: -0.03,
        }

        adjustment = weight_adjustments.get(action_type, 0)
        self._category_weights[category] = max(
            0.1, min(2.0, self._category_weights[category] + adjustment)
        )

    def get_sender_importance(self, email: str) -> float:
        """Get importance score for a sender.

        Args:
            email: Sender email

        Returns:
            Importance score (0.0 to 1.0)
        """
        email = email.lower()
        if email in self._senders:
            return self._senders[email].importance
        return 0.5  # Default

    def get_sender_profile(self, email: str) -> SenderProfile | None:
        """Get full profile for a sender.

        Args:
            email: Sender email

        Returns:
            SenderProfile or None
        """
        return self._senders.get(email.lower())

    def get_preferred_tone(self, email: str) -> str:
        """Get preferred reply tone for a sender.

        Args:
            email: Sender email

        Returns:
            Preferred tone (formal, professional, friendly)
        """
        profile = self.get_sender_profile(email)
        if profile:
            return profile.preferred_tone
        return "professional"

    def get_category_weight(self, category: str) -> float:
        """Get importance weight for a category.

        Args:
            category: Email category

        Returns:
            Weight multiplier (default 1.0)
        """
        return self._category_weights.get(category, 1.0)

    def get_user_profile(self) -> dict[str, str]:
        """Get user profile for form pre-filling.

        Returns:
            Dict of profile fields
        """
        return self._user_profile.to_dict()

    def update_user_profile(self, **kwargs) -> None:
        """Update user profile fields.

        Args:
            **kwargs: Profile fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self._user_profile, key):
                setattr(self._user_profile, key, value)
        self._save()

    def get_notification_prefs(self) -> NotificationPreferences:
        """Get notification preferences.

        Returns:
            NotificationPreferences object
        """
        return self._notification_prefs

    def update_notification_prefs(self, **kwargs) -> None:
        """Update notification preferences.

        Args:
            **kwargs: Preference fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self._notification_prefs, key):
                setattr(self._notification_prefs, key, value)
        self._save()

    def is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours.

        Returns:
            True if in quiet hours
        """
        now = datetime.now(UTC)
        hour = now.hour

        start = self._notification_prefs.quiet_start_hour
        end = self._notification_prefs.quiet_end_hour

        if start > end:
            # Crosses midnight (e.g., 22:00 to 07:00)
            return hour >= start or hour < end
        else:
            return start <= hour < end

    def should_notify_immediately(self, priority: str, category: str) -> bool:
        """Check if an email should trigger immediate notification.

        Args:
            priority: Email priority (P1, P2, etc.)
            category: Email category

        Returns:
            True if should notify immediately
        """
        if self.is_quiet_hours():
            return False

        if priority == "P1":
            return self._notification_prefs.notify_p1_immediately

        return False

    def get_vip_senders(self, min_importance: float = 0.8) -> list[str]:
        """Get list of VIP senders.

        Args:
            min_importance: Minimum importance score

        Returns:
            List of VIP email addresses
        """
        return [
            email for email, profile in self._senders.items()
            if profile.importance >= min_importance
        ]

    def get_statistics(self) -> dict:
        """Get usage statistics.

        Returns:
            Dict with statistics
        """
        action_counts = {}
        for action in self._actions:
            action_type = action.action_type.value
            action_counts[action_type] = action_counts.get(action_type, 0) + 1

        return {
            "total_senders": len(self._senders),
            "vip_senders": len(self.get_vip_senders()),
            "total_actions": len(self._actions),
            "action_counts": action_counts,
            "category_weights": self._category_weights,
        }


def main() -> None:
    """Test UserPreferences."""
    logging.basicConfig(level=logging.INFO)

    prefs = UserPreferences(storage_path="/tmp/test_prefs.json")

    # Update user profile
    prefs.update_user_profile(
        id_number="123456789",
        full_name="ישראל ישראלי",
        email="israel@example.com",
        phone="050-1234567",
    )

    # Record some actions
    prefs.record_action(
        ActionType.MARKED_IMPORTANT,
        {"sender": "boss@company.com", "sender_name": "הבוס", "category": "work"},
    )

    prefs.record_action(
        ActionType.REPLIED,
        {"sender": "boss@company.com", "category": "work"},
    )

    prefs.record_action(
        ActionType.IGNORED,
        {"sender": "spam@marketing.com", "category": "promotional"},
    )

    # Check results
    print("\n=== User Profile ===")
    print(json.dumps(prefs.get_user_profile(), ensure_ascii=False, indent=2))

    print("\n=== Sender Importance ===")
    print(f"boss@company.com: {prefs.get_sender_importance('boss@company.com')}")
    print(f"spam@marketing.com: {prefs.get_sender_importance('spam@marketing.com')}")

    print("\n=== VIP Senders ===")
    print(prefs.get_vip_senders(min_importance=0.5))

    print("\n=== Statistics ===")
    print(json.dumps(prefs.get_statistics(), indent=2))


if __name__ == "__main__":
    main()
