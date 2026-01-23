"""Task Integration module for Smart Email Agent.

Creates and manages tasks from emails, integrating with external
task management systems.

Part of Phase 3 - ADR-014: Smart Email Agent with Telegram Integration.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""

    CRITICAL = "critical"  # Must do today
    HIGH = "high"  # Within 2 days
    MEDIUM = "medium"  # This week
    LOW = "low"  # When possible
    SOMEDAY = "someday"  # No deadline


class TaskStatus(Enum):
    """Task status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"  # Waiting for someone else
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskSource(Enum):
    """Where the task originated."""

    EMAIL = "email"
    FORM = "form"
    DEADLINE = "deadline"
    MANUAL = "manual"


@dataclass
class TaskItem:
    """Represents a task extracted from email."""

    id: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    source: TaskSource
    source_email_id: str | None = None
    source_sender: str | None = None
    due_date: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    subtasks: list[str] = field(default_factory=list)
    external_id: str | None = None  # ID in external system (Todoist, Notion)
    external_url: str | None = None  # Link to external task
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "source": self.source.value,
            "source_email_id": self.source_email_id,
            "source_sender": self.source_sender,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": self.tags,
            "subtasks": self.subtasks,
            "external_id": self.external_id,
            "external_url": self.external_url,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskItem":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            priority=TaskPriority(data["priority"]),
            status=TaskStatus(data["status"]),
            source=TaskSource(data["source"]),
            source_email_id=data.get("source_email_id"),
            source_sender=data.get("source_sender"),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at") else None
            ),
            tags=data.get("tags", []),
            subtasks=data.get("subtasks", []),
            external_id=data.get("external_id"),
            external_url=data.get("external_url"),
            context=data.get("context", {}),
        )


class TaskIntegration:
    """Creates and manages tasks from emails.

    Features:
    - Extract actionable tasks from email content
    - Prioritize based on urgency and importance
    - Sync with external task managers (Todoist, Notion)
    - Track completion and follow-up
    - Link tasks back to original emails

    Example:
        >>> integration = TaskIntegration()
        >>> task = await integration.create_task_from_email(
        ...     email_id="abc123",
        ...     subject="Please review the contract by Friday",
        ...     body="Attached is the contract. Please review and sign.",
        ...     sender="legal@company.com"
        ... )
        >>> print(task.title)
        "סקירת חוזה - legal@company.com"
    """

    # Task action keywords (Hebrew and English)
    ACTION_KEYWORDS = {
        "high_priority": [
            "דחוף", "מיידי", "urgent", "asap", "immediately",
            "חשוב מאוד", "critical", "בהקדם",
        ],
        "review": [
            "לבדוק", "לסקור", "review", "check", "בדיקה",
            "עיון", "examine",
        ],
        "sign": [
            "לחתום", "חתימה", "sign", "signature", "חתימת",
        ],
        "submit": [
            "להגיש", "הגשה", "submit", "send", "שליחה",
            "למסור", "deliver",
        ],
        "pay": [
            "לשלם", "תשלום", "pay", "payment", "העברה",
            "חשבונית", "invoice",
        ],
        "respond": [
            "להגיב", "לענות", "respond", "reply", "תגובה",
            "מענה",
        ],
        "schedule": [
            "לתאם", "לקבוע", "schedule", "book", "תיאום",
            "פגישה", "meeting",
        ],
        "prepare": [
            "להכין", "הכנה", "prepare", "create", "לייצר",
            "לבנות", "build",
        ],
    }

    # Israeli organization tags
    ORGANIZATION_TAGS = {
        "btl.gov.il": ["ביטוח-לאומי", "government"],
        "taxes.gov.il": ["מס-הכנסה", "government", "tax"],
        "gov.il": ["government", "ממשלתי"],
        "bank": ["banking", "בנק", "finance"],
        "leumi": ["בנק-לאומי", "banking"],
        "hapoalim": ["בנק-הפועלים", "banking"],
        "discount": ["בנק-דיסקונט", "banking"],
        "mizrahi": ["מזרחי-טפחות", "banking"],
        "municipality": ["עירייה", "local-gov"],
        "iriya": ["עירייה", "local-gov"],
    }

    def __init__(
        self,
        storage_path: str | None = None,
        litellm_url: str | None = None,
        todoist_token: str | None = None,
        notion_token: str | None = None,
    ):
        """Initialize task integration.

        Args:
            storage_path: Path to store tasks locally
            litellm_url: LiteLLM Gateway URL for AI analysis
            todoist_token: Todoist API token (optional)
            notion_token: Notion API token (optional)
        """
        self.storage_path = Path(storage_path or "/tmp/email_agent_tasks")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.litellm_url = litellm_url or os.getenv(
            "LITELLM_URL", "https://litellm-gateway-production-0339.up.railway.app"
        )
        self.todoist_token = todoist_token or os.getenv("TODOIST_API_TOKEN")
        self.notion_token = notion_token or os.getenv("NOTION_API_TOKEN")

        self.tasks: dict[str, TaskItem] = {}
        self._load_tasks()

    def _load_tasks(self) -> None:
        """Load tasks from local storage."""
        tasks_file = self.storage_path / "tasks.json"
        if tasks_file.exists():
            try:
                with open(tasks_file) as f:
                    data = json.load(f)
                    for task_data in data.get("tasks", []):
                        task = TaskItem.from_dict(task_data)
                        self.tasks[task.id] = task
                logger.info(f"Loaded {len(self.tasks)} tasks from storage")
            except Exception as e:
                logger.error(f"Error loading tasks: {e}")

    def _save_tasks(self) -> None:
        """Save tasks to local storage."""
        tasks_file = self.storage_path / "tasks.json"
        try:
            data = {
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "updated_at": datetime.now().isoformat(),
            }
            with open(tasks_file, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving tasks: {e}")

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        import uuid
        return f"task_{uuid.uuid4().hex[:12]}"

    def _detect_action_type(self, text: str) -> list[str]:
        """Detect action types from text."""
        text_lower = text.lower()
        actions = []
        for action, keywords in self.ACTION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                actions.append(action)
        return actions

    def _detect_organization_tags(self, sender: str, text: str) -> list[str]:
        """Detect organization-specific tags."""
        tags = []
        combined = f"{sender} {text}".lower()
        for pattern, org_tags in self.ORGANIZATION_TAGS.items():
            if pattern in combined:
                tags.extend(org_tags)
        return list(set(tags))

    def _estimate_priority(
        self,
        actions: list[str],
        due_date: datetime | None,
        sender: str,
    ) -> TaskPriority:
        """Estimate task priority."""
        # High priority actions
        if "high_priority" in actions:
            return TaskPriority.CRITICAL

        # Check due date
        if due_date:
            days_until = (due_date - datetime.now()).days
            if days_until <= 0:
                return TaskPriority.CRITICAL
            elif days_until <= 2:
                return TaskPriority.HIGH
            elif days_until <= 7:
                return TaskPriority.MEDIUM

        # Government/official sources are usually important
        org_tags = self._detect_organization_tags(sender, "")
        if any(tag in ["government", "banking"] for tag in org_tags):
            return TaskPriority.HIGH

        # Payment and signing actions are high priority
        if "pay" in actions or "sign" in actions:
            return TaskPriority.HIGH

        # Review and respond are medium
        if "review" in actions or "respond" in actions:
            return TaskPriority.MEDIUM

        return TaskPriority.LOW

    async def _analyze_with_ai(
        self,
        email_subject: str,
        email_body: str,
        sender: str,
    ) -> dict[str, Any]:
        """Use AI to extract task details."""
        prompt = f"""אנא נתח את המייל הבא וחלץ משימות אקטיביות.

נושא: {email_subject}
שולח: {sender}
תוכן:
{email_body[:2000]}

אנא החזר JSON עם:
{{
    "tasks": [
        {{
            "title": "כותרת המשימה בעברית",
            "description": "תיאור מפורט",
            "subtasks": ["משימת משנה 1", "משימת משנה 2"],
            "due_date": "YYYY-MM-DD או null",
            "priority": "critical/high/medium/low",
            "action_type": "review/sign/submit/pay/respond/schedule/prepare"
        }}
    ],
    "has_actionable_items": true/false,
    "urgency_reason": "סיבת הדחיפות אם יש"
}}

החזר רק JSON חוקי, ללא טקסט נוסף."""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.litellm_url}/v1/chat/completions",
                    json={
                        "model": "claude-sonnet",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1000,
                        "temperature": 0.3,
                    },
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Extract JSON from response
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")

        return {"tasks": [], "has_actionable_items": False}

    async def create_task_from_email(
        self,
        email_id: str,
        subject: str,
        body: str,
        sender: str,
        due_date: datetime | None = None,
        use_ai: bool = True,
    ) -> list[TaskItem]:
        """Create tasks from an email.

        Args:
            email_id: Gmail message ID
            subject: Email subject
            body: Email body content
            sender: Sender email address
            due_date: Optional deadline from email
            use_ai: Whether to use AI for analysis

        Returns:
            List of created tasks
        """
        created_tasks = []
        combined_text = f"{subject} {body}"

        # Detect actions and tags
        actions = self._detect_action_type(combined_text)
        tags = self._detect_organization_tags(sender, combined_text)

        # Use AI for detailed extraction if enabled
        if use_ai:
            ai_result = await self._analyze_with_ai(subject, body, sender)
            if ai_result.get("has_actionable_items"):
                for task_data in ai_result.get("tasks", []):
                    # Parse due date from AI
                    task_due = due_date
                    if task_data.get("due_date"):
                        try:
                            task_due = datetime.strptime(task_data["due_date"], "%Y-%m-%d")
                        except ValueError:
                            pass

                    # Map AI priority to enum
                    priority_map = {
                        "critical": TaskPriority.CRITICAL,
                        "high": TaskPriority.HIGH,
                        "medium": TaskPriority.MEDIUM,
                        "low": TaskPriority.LOW,
                    }
                    priority = priority_map.get(
                        task_data.get("priority", "medium"),
                        TaskPriority.MEDIUM
                    )

                    task = TaskItem(
                        id=self._generate_task_id(),
                        title=task_data.get("title", subject),
                        description=task_data.get("description", ""),
                        priority=priority,
                        status=TaskStatus.PENDING,
                        source=TaskSource.EMAIL,
                        source_email_id=email_id,
                        source_sender=sender,
                        due_date=task_due,
                        tags=tags + [task_data.get("action_type", "general")],
                        subtasks=task_data.get("subtasks", []),
                        context={
                            "email_subject": subject,
                            "urgency_reason": ai_result.get("urgency_reason"),
                        },
                    )
                    self.tasks[task.id] = task
                    created_tasks.append(task)

        # Fallback: Create basic task if no AI tasks and actions detected
        if not created_tasks and actions:
            priority = self._estimate_priority(actions, due_date, sender)
            task = TaskItem(
                id=self._generate_task_id(),
                title=f"📧 {subject[:50]}",
                description=f"משימה ממייל של {sender}",
                priority=priority,
                status=TaskStatus.PENDING,
                source=TaskSource.EMAIL,
                source_email_id=email_id,
                source_sender=sender,
                due_date=due_date,
                tags=tags + actions,
                context={"email_subject": subject},
            )
            self.tasks[task.id] = task
            created_tasks.append(task)

        if created_tasks:
            self._save_tasks()
            logger.info(f"Created {len(created_tasks)} tasks from email {email_id}")

        return created_tasks

    async def create_task_from_form(
        self,
        form_title: str,
        form_fields: list[str],
        deadline: datetime | None,
        source_email_id: str | None = None,
    ) -> TaskItem:
        """Create a task for filling out a form.

        Args:
            form_title: Form title/name
            form_fields: Required fields to fill
            deadline: Form submission deadline
            source_email_id: Original email ID

        Returns:
            Created task
        """
        priority = TaskPriority.HIGH if deadline else TaskPriority.MEDIUM
        if deadline:
            days_until = (deadline - datetime.now()).days
            if days_until <= 2:
                priority = TaskPriority.CRITICAL

        deadline_str = f"עד {deadline.strftime('%d/%m/%Y')}" if deadline else ""
        task = TaskItem(
            id=self._generate_task_id(),
            title=f"📝 מילוי טופס: {form_title}",
            description=f"יש למלא את הטופס ולהגיש{deadline_str}",
            priority=priority,
            status=TaskStatus.PENDING,
            source=TaskSource.FORM,
            source_email_id=source_email_id,
            due_date=deadline,
            tags=["form", "טופס"],
            subtasks=[f"למלא שדה: {field}" for field in form_fields[:10]],
            context={"form_title": form_title, "total_fields": len(form_fields)},
        )

        self.tasks[task.id] = task
        self._save_tasks()
        logger.info(f"Created form task: {task.title}")
        return task

    async def create_task_from_deadline(
        self,
        deadline_title: str,
        deadline_date: datetime,
        action_required: str,
        source_email_id: str | None = None,
        sender: str | None = None,
    ) -> TaskItem:
        """Create a task from a deadline.

        Args:
            deadline_title: Deadline description
            deadline_date: When it's due
            action_required: What needs to be done
            source_email_id: Original email ID
            sender: Original sender

        Returns:
            Created task
        """
        days_until = (deadline_date - datetime.now()).days
        if days_until <= 0:
            priority = TaskPriority.CRITICAL
        elif days_until <= 2:
            priority = TaskPriority.HIGH
        elif days_until <= 7:
            priority = TaskPriority.MEDIUM
        else:
            priority = TaskPriority.LOW

        task = TaskItem(
            id=self._generate_task_id(),
            title=f"⏰ {deadline_title}",
            description=action_required,
            priority=priority,
            status=TaskStatus.PENDING,
            source=TaskSource.DEADLINE,
            source_email_id=source_email_id,
            source_sender=sender,
            due_date=deadline_date,
            tags=["deadline", "דדליין"],
            context={"days_until": days_until},
        )

        self.tasks[task.id] = task
        self._save_tasks()
        logger.info(f"Created deadline task: {task.title}")
        return task

    def get_pending_tasks(
        self,
        priority: TaskPriority | None = None,
        source: TaskSource | None = None,
    ) -> list[TaskItem]:
        """Get pending tasks with optional filters.

        Args:
            priority: Filter by priority
            source: Filter by source

        Returns:
            List of pending tasks, sorted by priority and due date
        """
        tasks = [
            t for t in self.tasks.values()
            if t.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ]

        if priority:
            tasks = [t for t in tasks if t.priority == priority]

        if source:
            tasks = [t for t in tasks if t.source == source]

        # Sort by priority (critical first) then by due date
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3,
            TaskPriority.SOMEDAY: 4,
        }

        tasks.sort(key=lambda t: (
            priority_order[t.priority],
            t.due_date or datetime.max,
        ))

        return tasks

    def get_tasks_due_today(self) -> list[TaskItem]:
        """Get all tasks due today."""
        today = datetime.now().date()
        return [
            t for t in self.tasks.values()
            if t.due_date and t.due_date.date() == today
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]

    def get_overdue_tasks(self) -> list[TaskItem]:
        """Get all overdue tasks."""
        now = datetime.now()
        return [
            t for t in self.tasks.values()
            if t.due_date and t.due_date < now
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]

    def complete_task(self, task_id: str) -> TaskItem | None:
        """Mark a task as completed.

        Args:
            task_id: Task ID to complete

        Returns:
            Updated task or None if not found
        """
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        self._save_tasks()
        logger.info(f"Completed task: {task.title}")
        return task

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
    ) -> TaskItem | None:
        """Update task status.

        Args:
            task_id: Task ID
            status: New status

        Returns:
            Updated task or None if not found
        """
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        task.status = status
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
        self._save_tasks()
        return task

    async def sync_to_todoist(self, task: TaskItem) -> str | None:
        """Sync task to Todoist.

        Args:
            task: Task to sync

        Returns:
            Todoist task ID or None on failure
        """
        if not self.todoist_token:
            logger.warning("Todoist token not configured")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Map priority (Todoist uses 1-4, 4 being highest)
                priority_map = {
                    TaskPriority.CRITICAL: 4,
                    TaskPriority.HIGH: 3,
                    TaskPriority.MEDIUM: 2,
                    TaskPriority.LOW: 1,
                    TaskPriority.SOMEDAY: 1,
                }

                data = {
                    "content": task.title,
                    "description": task.description,
                    "priority": priority_map[task.priority],
                    "labels": task.tags,
                }

                if task.due_date:
                    data["due_datetime"] = task.due_date.isoformat()

                response = await client.post(
                    "https://api.todoist.com/rest/v2/tasks",
                    headers={"Authorization": f"Bearer {self.todoist_token}"},
                    json=data,
                )
                response.raise_for_status()
                result = response.json()

                task.external_id = result["id"]
                task.external_url = result.get("url")
                self._save_tasks()

                logger.info(f"Synced task to Todoist: {result['id']}")
                return result["id"]
        except Exception as e:
            logger.error(f"Failed to sync to Todoist: {e}")
            return None

    async def sync_to_notion(
        self,
        task: TaskItem,
        database_id: str,
    ) -> str | None:
        """Sync task to Notion database.

        Args:
            task: Task to sync
            database_id: Notion database ID

        Returns:
            Notion page ID or None on failure
        """
        if not self.notion_token:
            logger.warning("Notion token not configured")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Build Notion properties
                properties = {
                    "Name": {"title": [{"text": {"content": task.title}}]},
                    "Status": {"select": {"name": task.status.value}},
                    "Priority": {"select": {"name": task.priority.value}},
                    "Tags": {"multi_select": [{"name": t} for t in task.tags[:5]]},
                }

                if task.due_date:
                    properties["Due Date"] = {
                        "date": {"start": task.due_date.isoformat()}
                    }

                response = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers={
                        "Authorization": f"Bearer {self.notion_token}",
                        "Notion-Version": "2022-06-28",
                    },
                    json={
                        "parent": {"database_id": database_id},
                        "properties": properties,
                        "children": [
                            {
                                "object": "block",
                                "paragraph": {
                                    "rich_text": [{"text": {"content": task.description}}]
                                },
                            }
                        ],
                    },
                )
                response.raise_for_status()
                result = response.json()

                task.external_id = result["id"]
                task.external_url = result.get("url")
                self._save_tasks()

                logger.info(f"Synced task to Notion: {result['id']}")
                return result["id"]
        except Exception as e:
            logger.error(f"Failed to sync to Notion: {e}")
            return None

    def format_tasks_for_telegram(self, tasks: list[TaskItem]) -> str:
        """Format tasks for Telegram message.

        Args:
            tasks: Tasks to format

        Returns:
            Formatted Hebrew message
        """
        if not tasks:
            return "✅ אין משימות ממתינות!"

        # Group by priority
        critical = [t for t in tasks if t.priority == TaskPriority.CRITICAL]
        high = [t for t in tasks if t.priority == TaskPriority.HIGH]
        medium = [t for t in tasks if t.priority == TaskPriority.MEDIUM]
        low = [t for t in tasks if t.priority in [TaskPriority.LOW, TaskPriority.SOMEDAY]]

        lines = ["📋 *משימות ממתינות*\n"]

        if critical:
            lines.append("🔴 *קריטי:*")
            for task in critical:
                due = f" (עד {task.due_date.strftime('%d/%m')})" if task.due_date else ""
                lines.append(f"  • {task.title}{due}")

        if high:
            lines.append("\n🟠 *גבוה:*")
            for task in high:
                due = f" ({task.due_date.strftime('%d/%m')})" if task.due_date else ""
                lines.append(f"  • {task.title}{due}")

        if medium:
            lines.append("\n🟡 *בינוני:*")
            for task in medium[:5]:  # Limit to 5
                lines.append(f"  • {task.title}")
            if len(medium) > 5:
                lines.append(f"  + {len(medium) - 5} נוספות...")

        if low:
            lines.append(f"\n⚪ *נמוך:* {len(low)} משימות")

        # Summary
        total = len(tasks)
        overdue = len([t for t in tasks if t.due_date and t.due_date < datetime.now()])
        if overdue:
            lines.append(f"\n⚠️ {overdue} משימות באיחור!")

        lines.append(f"\n📊 סה\"כ: {total} משימות פתוחות")

        return "\n".join(lines)

    def get_daily_summary(self) -> dict[str, Any]:
        """Get daily task summary.

        Returns:
            Summary statistics
        """
        pending = self.get_pending_tasks()
        today = self.get_tasks_due_today()
        overdue = self.get_overdue_tasks()

        # Calculate completion rate (last 7 days)
        week_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_completed = [
            t for t in self.tasks.values()
            if t.status == TaskStatus.COMPLETED
            and t.completed_at and t.completed_at >= week_ago
        ]

        return {
            "total_pending": len(pending),
            "due_today": len(today),
            "overdue": len(overdue),
            "critical": len([t for t in pending if t.priority == TaskPriority.CRITICAL]),
            "high": len([t for t in pending if t.priority == TaskPriority.HIGH]),
            "completed_this_week": len(recent_completed),
            "tasks_today": today,
            "tasks_overdue": overdue,
            "telegram_message": self.format_tasks_for_telegram(pending),
        }
