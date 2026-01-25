"""
ADHD UX Module - Context-Aware Interruption Management.

Part of Zero-Loss Intake System (Phase 4).
Implements ADHD-friendly UX patterns from External Research 2026.

Key principles:
- Never interrupt flow state
- Batch notifications intelligently
- "Gentle nudge" instead of alerts
- Time-boxing awareness
- Task momentum tracking

Author: Claude Code Agent
Date: 2026-01-25
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Callable, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class InterruptionUrgency(Enum):
    """Urgency levels for interruptions."""

    CRITICAL = "critical"      # Security threat, system failure - always interrupt
    HIGH = "high"              # Important but not emergency - interrupt if not in flow
    MEDIUM = "medium"          # Can wait for batch - queue for next break
    LOW = "low"                # Informational - add to daily digest
    BACKGROUND = "background"  # Silent logging only


class FlowState(Enum):
    """User's current cognitive state."""

    DEEP_FOCUS = "deep_focus"      # In flow - never interrupt unless critical
    LIGHT_WORK = "light_work"      # Working but interruptible
    BREAK = "break"                # Taking a break - good time for updates
    TRANSITION = "transition"      # Between tasks - ideal for notifications
    UNAVAILABLE = "unavailable"    # Quiet mode - only critical


class NudgeType(Enum):
    """Types of gentle engagement."""

    TASK_REMINDER = "task_reminder"      # "You mentioned wanting to..."
    CONTEXT_RESTORE = "context_restore"  # "Last time you were working on..."
    BREAK_SUGGESTION = "break_suggestion"  # "You've been focused for 2 hours..."
    MOMENTUM_CHECK = "momentum_check"    # "How's the task going?"
    DAILY_SUMMARY = "daily_summary"      # End-of-day recap


@dataclass
class QuietWindow:
    """Time window where interruptions are minimized."""

    start: time
    end: time
    name: str
    allow_critical: bool = True

    def is_active(self, current_time: Optional[time] = None) -> bool:
        """Check if quiet window is currently active."""
        if current_time is None:
            current_time = datetime.now().time()

        # Handle overnight windows (e.g., 22:00 - 07:00)
        if self.start > self.end:
            return current_time >= self.start or current_time <= self.end
        return self.start <= current_time <= self.end


@dataclass
class PendingNotification:
    """A notification waiting for the right moment."""

    message: str
    urgency: InterruptionUrgency
    created_at: datetime = field(default_factory=datetime.now)
    context: dict = field(default_factory=dict)
    callback: Optional[Callable] = None

    @property
    def age_minutes(self) -> float:
        """How long this notification has been waiting."""
        return (datetime.now() - self.created_at).total_seconds() / 60


@dataclass
class GentleNudge:
    """A proactive, non-intrusive engagement."""

    nudge_type: NudgeType
    message: str
    context: dict = field(default_factory=dict)
    expires_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        """Check if nudge is still relevant."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class CognitiveLoadEstimate:
    """Estimated cognitive load based on activity patterns."""

    score: float  # 0.0 (relaxed) to 1.0 (overloaded)
    factors: dict = field(default_factory=dict)
    estimated_at: datetime = field(default_factory=datetime.now)

    @property
    def level(self) -> str:
        """Human-readable load level."""
        if self.score < 0.3:
            return "low"
        elif self.score < 0.6:
            return "moderate"
        elif self.score < 0.8:
            return "high"
        return "overloaded"


class CognitiveLoadDetector:
    """
    Estimates cognitive load based on activity patterns.

    Uses heuristics (can be enhanced with ML later):
    - Time since last break
    - Number of context switches
    - Task complexity
    - Time of day
    """

    def __init__(self):
        self.last_break: Optional[datetime] = None
        self.context_switches: list[datetime] = []
        self.active_tasks: int = 0
        self._session_start: datetime = datetime.now()

    def record_break(self) -> None:
        """Record that user took a break."""
        self.last_break = datetime.now()
        # Clear recent context switches after break
        cutoff = datetime.now() - timedelta(minutes=30)
        self.context_switches = [t for t in self.context_switches if t > cutoff]

    def record_context_switch(self) -> None:
        """Record a context switch (changed tasks/topics)."""
        self.context_switches.append(datetime.now())
        # Keep only last hour of switches
        cutoff = datetime.now() - timedelta(hours=1)
        self.context_switches = [t for t in self.context_switches if t > cutoff]

    def estimate(self) -> CognitiveLoadEstimate:
        """Estimate current cognitive load."""
        factors = {}

        # Factor 1: Time since break (0.0-0.3)
        if self.last_break:
            minutes_since_break = (datetime.now() - self.last_break).total_seconds() / 60
        else:
            minutes_since_break = (datetime.now() - self._session_start).total_seconds() / 60

        break_factor = min(minutes_since_break / 120, 1.0) * 0.3  # Max after 2 hours
        factors["time_since_break"] = break_factor

        # Factor 2: Context switches in last hour (0.0-0.3)
        recent_switches = len(self.context_switches)
        switch_factor = min(recent_switches / 10, 1.0) * 0.3  # Max after 10 switches
        factors["context_switches"] = switch_factor

        # Factor 3: Time of day (0.0-0.2)
        hour = datetime.now().hour
        if 9 <= hour <= 11 or 14 <= hour <= 16:  # Peak focus hours
            time_factor = 0.0
        elif 12 <= hour <= 13 or 17 <= hour <= 18:  # Post-lunch/end of day slump
            time_factor = 0.15
        elif hour < 7 or hour > 22:  # Very early/late
            time_factor = 0.2
        else:
            time_factor = 0.1
        factors["time_of_day"] = time_factor

        # Factor 4: Active tasks (0.0-0.2)
        task_factor = min(self.active_tasks / 5, 1.0) * 0.2  # Max at 5+ active tasks
        factors["active_tasks"] = task_factor

        total_score = sum(factors.values())

        return CognitiveLoadEstimate(
            score=min(total_score, 1.0),
            factors=factors
        )


class InterruptionManager:
    """
    Decides when and how to deliver notifications.

    Key behaviors:
    1. Critical: Always deliver immediately
    2. High: Deliver unless in deep focus
    3. Medium: Queue for next break/transition
    4. Low: Add to daily digest
    5. Background: Log only
    """

    def __init__(
        self,
        quiet_windows: Optional[list[QuietWindow]] = None,
        flow_decay_minutes: int = 25,  # Pomodoro-style
    ):
        self.quiet_windows = quiet_windows or []
        self.flow_decay_minutes = flow_decay_minutes

        self._current_state = FlowState.LIGHT_WORK
        self._state_changed_at = datetime.now()
        self._pending_queue: list[PendingNotification] = []
        self._delivered_today: list[PendingNotification] = []

        self.cognitive_detector = CognitiveLoadDetector()

    def set_flow_state(self, state: FlowState) -> None:
        """Update current flow state."""
        if state != self._current_state:
            self.cognitive_detector.record_context_switch()

        self._current_state = state
        self._state_changed_at = datetime.now()

        if state == FlowState.BREAK:
            self.cognitive_detector.record_break()

        logger.info(f"Flow state changed to: {state.value}")

    def get_effective_state(self) -> FlowState:
        """Get current state, accounting for quiet windows and time decay."""
        # Check quiet windows first
        for window in self.quiet_windows:
            if window.is_active():
                return FlowState.UNAVAILABLE

        # Check if deep focus has naturally decayed
        if self._current_state == FlowState.DEEP_FOCUS:
            minutes_in_state = (datetime.now() - self._state_changed_at).total_seconds() / 60
            if minutes_in_state > self.flow_decay_minutes:
                # Suggest transition but don't force it
                return FlowState.TRANSITION

        return self._current_state

    def should_interrupt(self, urgency: InterruptionUrgency) -> bool:
        """Decide if notification should interrupt now."""
        state = self.get_effective_state()

        # Critical always interrupts (unless in quiet window that blocks it)
        if urgency == InterruptionUrgency.CRITICAL:
            if state == FlowState.UNAVAILABLE:
                # Check if current quiet window allows critical
                for window in self.quiet_windows:
                    if window.is_active():
                        return window.allow_critical
            return True

        # Background never interrupts
        if urgency == InterruptionUrgency.BACKGROUND:
            return False

        # State-based decisions
        if state == FlowState.DEEP_FOCUS:
            return False  # Only critical can interrupt deep focus

        if state == FlowState.UNAVAILABLE:
            return False  # Quiet mode

        if state in (FlowState.BREAK, FlowState.TRANSITION):
            return True  # Good time for any notification

        # Light work: interrupt for high urgency
        if state == FlowState.LIGHT_WORK:
            return urgency == InterruptionUrgency.HIGH

        return False

    def queue_notification(self, notification: PendingNotification) -> None:
        """Add notification to pending queue."""
        self._pending_queue.append(notification)
        logger.debug(f"Queued notification: {notification.message[:50]}...")

    def get_pending_count(self) -> int:
        """Get number of pending notifications."""
        return len(self._pending_queue)

    def flush_pending(self, max_items: int = 5) -> list[PendingNotification]:
        """
        Get pending notifications for delivery.

        Called during breaks/transitions.
        Returns highest urgency items first, limited to max_items.
        """
        if not self._pending_queue:
            return []

        # Sort by urgency (higher first) then age (older first)
        urgency_order = {
            InterruptionUrgency.CRITICAL: 0,
            InterruptionUrgency.HIGH: 1,
            InterruptionUrgency.MEDIUM: 2,
            InterruptionUrgency.LOW: 3,
            InterruptionUrgency.BACKGROUND: 4,
        }

        sorted_queue = sorted(
            self._pending_queue,
            key=lambda n: (urgency_order[n.urgency], -n.age_minutes)
        )

        # Take top items
        to_deliver = sorted_queue[:max_items]

        # Remove from pending
        for notification in to_deliver:
            self._pending_queue.remove(notification)
            self._delivered_today.append(notification)

        return to_deliver

    def get_daily_digest(self) -> list[PendingNotification]:
        """Get all low-priority items for daily digest."""
        low_priority = [
            n for n in self._pending_queue
            if n.urgency in (InterruptionUrgency.LOW, InterruptionUrgency.BACKGROUND)
        ]

        # Remove from pending
        for notification in low_priority:
            self._pending_queue.remove(notification)

        return low_priority

    def process_notification(
        self,
        message: str,
        urgency: InterruptionUrgency,
        context: Optional[dict] = None,
        callback: Optional[Callable] = None,
    ) -> tuple[bool, Optional[PendingNotification]]:
        """
        Process a new notification.

        Returns:
            (delivered_now, pending_notification)
            - (True, None) if delivered immediately
            - (False, notification) if queued for later
        """
        notification = PendingNotification(
            message=message,
            urgency=urgency,
            context=context or {},
            callback=callback,
        )

        if self.should_interrupt(urgency):
            self._delivered_today.append(notification)
            logger.info(f"Delivering notification now: {message[:50]}...")
            return (True, None)

        self.queue_notification(notification)
        return (False, notification)


class ProactiveEngagement:
    """
    Generates gentle, non-intrusive nudges.

    ADHD-friendly principles:
    - "Breadcrumb" reminders (not demands)
    - Context restoration (where was I?)
    - Break suggestions (prevent burnout)
    - Momentum encouragement
    """

    def __init__(self, interruption_manager: InterruptionManager):
        self.manager = interruption_manager
        self._task_mentions: dict[str, datetime] = {}  # task_id -> last_mentioned
        self._context_stack: list[dict] = []  # Recent work contexts

    def record_task_mention(self, task_id: str, description: str) -> None:
        """Record when user mentions a task."""
        self._task_mentions[task_id] = datetime.now()

        # Add to context stack
        self._context_stack.append({
            "task_id": task_id,
            "description": description,
            "timestamp": datetime.now(),
        })

        # Keep last 10 contexts
        self._context_stack = self._context_stack[-10:]

    def generate_task_reminder(self, hours_threshold: float = 24) -> Optional[GentleNudge]:
        """
        Generate reminder for mentioned but not completed tasks.

        Only if task was mentioned but not touched for threshold hours.
        """
        if not self._task_mentions:
            return None

        cutoff = datetime.now() - timedelta(hours=hours_threshold)

        # Find oldest untouched task
        stale_tasks = [
            (task_id, mentioned_at)
            for task_id, mentioned_at in self._task_mentions.items()
            if mentioned_at < cutoff
        ]

        if not stale_tasks:
            return None

        # Get oldest
        oldest_task_id, mentioned_at = min(stale_tasks, key=lambda x: x[1])

        # Find description from context
        description = None
        for ctx in self._context_stack:
            if ctx.get("task_id") == oldest_task_id:
                description = ctx.get("description", oldest_task_id)
                break

        hours_ago = (datetime.now() - mentioned_at).total_seconds() / 3600

        return GentleNudge(
            nudge_type=NudgeType.TASK_REMINDER,
            message=f"הזכרת שרצית לעשות: '{description or oldest_task_id}' (לפני {hours_ago:.0f} שעות). עדיין רלוונטי?",
            context={"task_id": oldest_task_id, "mentioned_at": mentioned_at.isoformat()},
            expires_at=datetime.now() + timedelta(hours=12),  # Reminder valid for 12 hours
        )

    def generate_context_restore(self) -> Optional[GentleNudge]:
        """
        Generate context restoration nudge.

        Useful when returning from a break or starting new session.
        """
        if not self._context_stack:
            return None

        # Get most recent context
        last_context = self._context_stack[-1]

        # Only if context is from previous session (> 30 min ago)
        context_age = datetime.now() - last_context["timestamp"]
        if context_age < timedelta(minutes=30):
            return None

        return GentleNudge(
            nudge_type=NudgeType.CONTEXT_RESTORE,
            message=f"בפעם האחרונה עבדת על: '{last_context.get('description', 'unknown')}'. רוצה להמשיך?",
            context=last_context,
            expires_at=datetime.now() + timedelta(hours=4),
        )

    def generate_break_suggestion(self) -> Optional[GentleNudge]:
        """
        Generate break suggestion based on cognitive load.
        """
        load = self.manager.cognitive_detector.estimate()

        # Only suggest if load is high
        if load.score < 0.6:
            return None

        minutes_focused = 0
        if self.manager.cognitive_detector.last_break:
            minutes_focused = (
                datetime.now() - self.manager.cognitive_detector.last_break
            ).total_seconds() / 60
        else:
            minutes_focused = (
                datetime.now() - self.manager.cognitive_detector._session_start
            ).total_seconds() / 60

        return GentleNudge(
            nudge_type=NudgeType.BREAK_SUGGESTION,
            message=f"עובד כבר {minutes_focused:.0f} דקות. אולי הפסקה קצרה? (עומס קוגניטיבי: {load.level})",
            context={"cognitive_load": load.score, "factors": load.factors},
            expires_at=datetime.now() + timedelta(minutes=30),
        )

    def generate_momentum_check(self) -> Optional[GentleNudge]:
        """
        Generate momentum check for ongoing work.

        Gentle "how's it going?" when working for a while.
        """
        state = self.manager.get_effective_state()

        # Only during light work (deep focus = don't interrupt, break = already resting)
        if state != FlowState.LIGHT_WORK:
            return None

        # Check if in light work for at least 45 minutes
        minutes_in_state = (
            datetime.now() - self.manager._state_changed_at
        ).total_seconds() / 60

        if minutes_in_state < 45:
            return None

        return GentleNudge(
            nudge_type=NudgeType.MOMENTUM_CHECK,
            message="איך מתקדם? צריך עזרה במשהו?",
            context={"minutes_working": minutes_in_state},
            expires_at=datetime.now() + timedelta(minutes=30),
        )


class ADHDUXManager:
    """
    Main ADHD UX coordinator.

    Combines:
    - Interruption management
    - Cognitive load detection
    - Proactive engagement
    - Quiet windows
    """

    def __init__(
        self,
        quiet_windows: Optional[list[QuietWindow]] = None,
    ):
        # Default quiet windows
        if quiet_windows is None:
            quiet_windows = [
                QuietWindow(
                    start=time(22, 0),
                    end=time(7, 0),
                    name="night",
                    allow_critical=True,
                ),
                QuietWindow(
                    start=time(12, 0),
                    end=time(13, 0),
                    name="lunch",
                    allow_critical=True,
                ),
            ]

        self.interruption_manager = InterruptionManager(
            quiet_windows=quiet_windows,
        )
        self.engagement = ProactiveEngagement(self.interruption_manager)

        # Track nudge delivery to avoid spam
        self._last_nudge_times: dict[NudgeType, datetime] = {}
        self._nudge_cooldowns: dict[NudgeType, timedelta] = {
            NudgeType.TASK_REMINDER: timedelta(hours=4),
            NudgeType.CONTEXT_RESTORE: timedelta(hours=2),
            NudgeType.BREAK_SUGGESTION: timedelta(hours=1),
            NudgeType.MOMENTUM_CHECK: timedelta(hours=2),
            NudgeType.DAILY_SUMMARY: timedelta(hours=20),
        }

    def enter_focus_mode(self) -> None:
        """User entering deep focus."""
        self.interruption_manager.set_flow_state(FlowState.DEEP_FOCUS)

    def exit_focus_mode(self) -> None:
        """User exiting deep focus."""
        self.interruption_manager.set_flow_state(FlowState.LIGHT_WORK)

    def start_break(self) -> list[PendingNotification]:
        """
        User starting a break.

        Returns pending notifications that accumulated.
        """
        self.interruption_manager.set_flow_state(FlowState.BREAK)
        return self.interruption_manager.flush_pending()

    def end_break(self) -> Optional[GentleNudge]:
        """
        User ending break.

        Returns context restoration nudge if appropriate.
        """
        self.interruption_manager.set_flow_state(FlowState.TRANSITION)
        return self._try_nudge(self.engagement.generate_context_restore)

    def notify(
        self,
        message: str,
        urgency: InterruptionUrgency = InterruptionUrgency.MEDIUM,
        context: Optional[dict] = None,
    ) -> tuple[bool, Optional[PendingNotification]]:
        """
        Send a notification through the ADHD-friendly system.

        Returns:
            (delivered_now, pending) tuple
        """
        return self.interruption_manager.process_notification(
            message=message,
            urgency=urgency,
            context=context,
        )

    def record_task(self, task_id: str, description: str) -> None:
        """Record user mentioning a task."""
        self.engagement.record_task_mention(task_id, description)

    def get_nudge(self) -> Optional[GentleNudge]:
        """
        Get an appropriate nudge if conditions are right.

        Checks all nudge generators and returns first valid one
        that isn't in cooldown.
        """
        # Order by priority/helpfulness
        generators = [
            self.engagement.generate_break_suggestion,
            self.engagement.generate_context_restore,
            self.engagement.generate_momentum_check,
            self.engagement.generate_task_reminder,
        ]

        for generator in generators:
            nudge = self._try_nudge(generator)
            if nudge:
                return nudge

        return None

    def _try_nudge(self, generator: Callable[[], Optional[GentleNudge]]) -> Optional[GentleNudge]:
        """Try to generate nudge, respecting cooldowns."""
        nudge = generator()

        if nudge is None:
            return None

        # Check cooldown
        nudge_type = nudge.nudge_type
        last_time = self._last_nudge_times.get(nudge_type)
        cooldown = self._nudge_cooldowns.get(nudge_type, timedelta(hours=1))

        if last_time and (datetime.now() - last_time) < cooldown:
            return None  # Still in cooldown

        # Record delivery
        self._last_nudge_times[nudge_type] = datetime.now()
        return nudge

    def get_status(self) -> dict:
        """Get current ADHD UX status."""
        load = self.interruption_manager.cognitive_detector.estimate()
        state = self.interruption_manager.get_effective_state()

        return {
            "flow_state": state.value,
            "cognitive_load": {
                "score": load.score,
                "level": load.level,
                "factors": load.factors,
            },
            "pending_notifications": self.interruption_manager.get_pending_count(),
            "quiet_mode_active": state == FlowState.UNAVAILABLE,
            "active_quiet_windows": [
                w.name for w in self.interruption_manager.quiet_windows
                if w.is_active()
            ],
        }
