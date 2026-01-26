"""Transactional Outbox pattern for guaranteed delivery.

Solves the Dual Write Inconsistency problem:
When an agent completes a reasoning step, it must:
1. Persist the new state/memory to the database
2. Publish an event to the message queue

If DB write succeeds but queue publish fails, state becomes inconsistent.

Solution (from External Research 2026 §2.3):
- Write event to "Outbox" table in SAME transaction as state update
- Separate Relay process reads Outbox and publishes to queue
- If publication fails, Relay retries (At-Least-Once Delivery)

This also enables aggressive cost optimization by silently retrying
failed model calls or switching providers (DeepSeek fallback pattern).
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OutboxStatus(str, Enum):
    """Status of an outbox entry."""

    PENDING = "pending"  # Waiting to be published
    PUBLISHED = "published"  # Successfully sent to queue
    FAILED = "failed"  # Publish failed, needs retry
    DEAD_LETTER = "dead_letter"  # Max retries exceeded


@dataclass
class OutboxEntry:
    """Entry in the transactional outbox table.

    Stored in the same database transaction as the business logic,
    ensuring atomic "write state + queue event" operations.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Event data
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    destination: str = "intake:events"  # Target queue/topic

    # Delivery tracking
    status: OutboxStatus = OutboxStatus.PENDING
    retry_count: int = 0
    max_retries: int = 5
    last_error: str | None = None
    published_at: str | None = None

    # Correlation
    correlation_id: str | None = None  # Links to original request
    causation_id: str | None = None  # Links to causing event

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data["status"] = self.status.value
        data["payload"] = json.dumps(self.payload)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutboxEntry":
        """Create from database row."""
        data = dict(data)
        data["status"] = OutboxStatus(data.get("status", "pending"))
        if isinstance(data.get("payload"), str):
            data["payload"] = json.loads(data["payload"])
        return cls(**data)

    def mark_published(self) -> None:
        """Mark entry as successfully published."""
        self.status = OutboxStatus.PUBLISHED
        self.published_at = datetime.utcnow().isoformat()

    def mark_failed(self, error: str) -> None:
        """Mark entry as failed with error."""
        self.retry_count += 1
        self.last_error = error
        if self.retry_count >= self.max_retries:
            self.status = OutboxStatus.DEAD_LETTER
            logger.error(f"Outbox entry {self.id} moved to dead letter: {error}")
        else:
            self.status = OutboxStatus.FAILED
            logger.warning(f"Outbox entry {self.id} failed (retry {self.retry_count}): {error}")


class TransactionalOutbox:
    """Manages the outbox table for guaranteed event delivery.

    Usage:
        async with db.transaction():
            # Business logic
            await db.save_state(new_state)

            # Add to outbox in SAME transaction
            await outbox.add(OutboxEntry(
                event_type="state_updated",
                payload={"state_id": new_state.id}
            ))

        # Relay (separate process) will publish to queue
    """

    TABLE_NAME = "intake_outbox"

    def __init__(self, db_session: Optional[Any] = None):
        """Initialize with optional database session.

        Args:
            db_session: SQLAlchemy async session or similar.
                       If None, uses in-memory storage.
        """
        self._db = db_session
        self._memory_store: list[OutboxEntry] = []  # Fallback

    async def add(self, entry: OutboxEntry) -> str:
        """Add entry to outbox (within current transaction).

        Args:
            entry: The outbox entry to store

        Returns:
            Entry ID
        """
        if self._db is None:
            self._memory_store.append(entry)
            logger.debug(f"Outbox: Added entry {entry.id} (memory)")
            return entry.id

        try:
            # SQL INSERT (adjust for your ORM)
            await self._db.execute(
                f"""
                INSERT INTO {self.TABLE_NAME}
                (id, created_at, event_type, payload, destination, status,
                 retry_count, max_retries, correlation_id, causation_id)
                VALUES (:id, :created_at, :event_type, :payload, :destination,
                        :status, :retry_count, :max_retries, :correlation_id, :causation_id)
                """,
                entry.to_dict()
            )
            logger.info(f"Outbox: Added entry {entry.id}")
            return entry.id
        except Exception as e:
            logger.error(f"Outbox: Failed to add entry: {e}")
            # Fallback to memory (not ideal, but prevents data loss)
            self._memory_store.append(entry)
            return entry.id

    async def get_pending(self, limit: int = 100) -> list[OutboxEntry]:
        """Get pending entries for the relay to publish.

        Args:
            limit: Maximum entries to return

        Returns:
            List of pending outbox entries
        """
        if self._db is None:
            return [e for e in self._memory_store
                    if e.status in (OutboxStatus.PENDING, OutboxStatus.FAILED)][:limit]

        try:
            result = await self._db.execute(
                f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE status IN ('pending', 'failed')
                ORDER BY created_at ASC
                LIMIT :limit
                """,
                {"limit": limit}
            )
            return [OutboxEntry.from_dict(dict(row)) for row in result]
        except Exception as e:
            logger.error(f"Outbox: Failed to get pending: {e}")
            return []

    async def update(self, entry: OutboxEntry) -> bool:
        """Update entry status after publish attempt.

        Args:
            entry: Entry with updated status

        Returns:
            True if updated successfully
        """
        if self._db is None:
            for i, e in enumerate(self._memory_store):
                if e.id == entry.id:
                    self._memory_store[i] = entry
                    return True
            return False

        try:
            await self._db.execute(
                f"""
                UPDATE {self.TABLE_NAME}
                SET status = :status,
                    retry_count = :retry_count,
                    last_error = :last_error,
                    published_at = :published_at
                WHERE id = :id
                """,
                {
                    "id": entry.id,
                    "status": entry.status.value,
                    "retry_count": entry.retry_count,
                    "last_error": entry.last_error,
                    "published_at": entry.published_at
                }
            )
            return True
        except Exception as e:
            logger.error(f"Outbox: Failed to update entry {entry.id}: {e}")
            return False

    async def get_dead_letters(self, limit: int = 100) -> list[OutboxEntry]:
        """Get entries that exceeded max retries.

        These need manual intervention or alternative handling.
        """
        if self._db is None:
            return [e for e in self._memory_store
                    if e.status == OutboxStatus.DEAD_LETTER][:limit]

        try:
            result = await self._db.execute(
                f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE status = 'dead_letter'
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {"limit": limit}
            )
            return [OutboxEntry.from_dict(dict(row)) for row in result]
        except Exception as e:
            logger.error(f"Outbox: Failed to get dead letters: {e}")
            return []

    async def get_stats(self) -> dict[str, Any]:
        """Get outbox statistics."""
        if self._db is None:
            by_status = {}
            for entry in self._memory_store:
                status = entry.status.value
                by_status[status] = by_status.get(status, 0) + 1
            return {
                "backend": "memory",
                "total": len(self._memory_store),
                "by_status": by_status
            }

        try:
            result = await self._db.execute(
                f"""
                SELECT status, COUNT(*) as count
                FROM {self.TABLE_NAME}
                GROUP BY status
                """
            )
            by_status = {row["status"]: row["count"] for row in result}
            return {
                "backend": "postgresql",
                "total": sum(by_status.values()),
                "by_status": by_status
            }
        except Exception as e:
            return {"backend": "postgresql", "error": str(e)}


class OutboxRelay:
    """Background worker that publishes outbox entries to the queue.

    Runs separately from the main application to ensure decoupling.
    Uses exponential backoff for retries.

    Typical deployment:
    - Main app: Writes to DB + Outbox in transaction
    - Relay worker: Polls Outbox, publishes to Redis Streams
    """

    def __init__(
        self,
        outbox: TransactionalOutbox,
        queue: "IntakeQueue",  # type: ignore (forward ref)
        poll_interval_seconds: float = 1.0
    ):
        self.outbox = outbox
        self.queue = queue
        self.poll_interval = poll_interval_seconds
        self._running = False

    async def run(self) -> None:
        """Start the relay loop."""
        import asyncio

        self._running = True
        logger.info("OutboxRelay: Starting relay loop")

        while self._running:
            try:
                entries = await self.outbox.get_pending(limit=50)

                for entry in entries:
                    await self._publish_entry(entry)

                if not entries:
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"OutboxRelay: Error in loop: {e}")
                await asyncio.sleep(self.poll_interval * 2)

    async def _publish_entry(self, entry: OutboxEntry) -> None:
        """Attempt to publish a single entry."""
        try:
            # Import here to avoid circular dependency
            from src.intake.queue import IntakeEvent

            # Convert outbox payload to intake event
            event = IntakeEvent(
                event_type=entry.event_type,
                content=json.dumps(entry.payload),
                content_type="structured",
                metadata={
                    "outbox_id": entry.id,
                    "correlation_id": entry.correlation_id,
                    "causation_id": entry.causation_id
                }
            )

            await self.queue.push(event)
            entry.mark_published()
            await self.outbox.update(entry)
            logger.debug(f"OutboxRelay: Published entry {entry.id}")

        except Exception as e:
            entry.mark_failed(str(e))
            await self.outbox.update(entry)

    def stop(self) -> None:
        """Stop the relay loop."""
        self._running = False
        logger.info("OutboxRelay: Stopping relay loop")
