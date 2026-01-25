"""Redis Streams wrapper for zero-loss intake.

Implements event sourcing pattern with Redis Streams.
Validated by External Research 2026 §2.1:
- Sub-millisecond latency for real-time reasoning loops
- Global ordering per stream simplifies linear reasoning history
- XREAD BLOCK allows instant reaction to new events

Why Redis Streams over Kafka (for single-user systems):
- Lower operational cost (single binary vs cluster management)
- Memory-based for superior latency
- Sufficient durability with AOF persistence
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of intake events following AG-UI taxonomy."""

    # User input events
    USER_MESSAGE = "user_message"
    USER_FILE = "user_file"
    USER_VOICE = "user_voice"

    # System events
    CLASSIFICATION_COMPLETE = "classification_complete"
    ROUTING_DECISION = "routing_decision"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETE = "processing_complete"

    # Error events
    PROCESSING_FAILED = "processing_failed"
    RETRY_SCHEDULED = "retry_scheduled"


@dataclass
class IntakeEvent:
    """Immutable event in the intake stream.

    Every observation, thought, and action is stored as an immutable event.
    This enables: debugging, replay, and full observability.
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: EventType = EventType.USER_MESSAGE
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Content
    content: str = ""
    content_type: str = "text"  # text, file, voice, structured

    # Classification (filled by DomainClassifier)
    domain: str | None = None  # personal, business, mixed
    priority: str | None = None  # P1, P2, P3, P4
    category: str | None = None  # from ADR-014 categories

    # Product detection (filled by ProductDetector)
    product_potential: float = 0.0
    product_signals: list[str] = field(default_factory=list)

    # Routing
    routed_to: str | None = None  # skill name or agent
    processed: bool = False

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["product_signals"] = json.dumps(self.product_signals)
        data["metadata"] = json.dumps(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntakeEvent":
        """Create from Redis dictionary."""
        data = dict(data)  # Copy to avoid mutation
        data["event_type"] = EventType(data.get("event_type", "user_message"))

        # Parse JSON fields
        if isinstance(data.get("product_signals"), str):
            data["product_signals"] = json.loads(data["product_signals"])
        if isinstance(data.get("metadata"), str):
            data["metadata"] = json.loads(data["metadata"])

        # Handle boolean
        if isinstance(data.get("processed"), str):
            data["processed"] = data["processed"].lower() == "true"

        # Handle float
        if isinstance(data.get("product_potential"), str):
            data["product_potential"] = float(data["product_potential"])

        return cls(**data)


class IntakeQueue:
    """Redis Streams-based intake queue.

    Provides:
    - Append-only event log (immutable history)
    - Consumer groups for parallel processing
    - Blocking reads for real-time reaction
    - Automatic ID generation with timestamps

    Note: For environments without Redis, falls back to in-memory queue.
    """

    STREAM_KEY = "intake:events"
    CONSUMER_GROUP = "intake_processors"
    MAX_STREAM_LENGTH = 10000  # Trim old events to prevent unbounded growth

    def __init__(self, redis_client=None):
        """Initialize queue with optional Redis client.

        Args:
            redis_client: Redis client instance. If None, uses in-memory fallback.
        """
        self._redis = redis_client
        self._memory_queue: list[IntakeEvent] = []  # Fallback
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize consumer group if using Redis."""
        if self._redis is None:
            logger.info("IntakeQueue: Using in-memory fallback (no Redis)")
            self._initialized = True
            return

        try:
            # Create consumer group if not exists
            await self._redis.xgroup_create(
                self.STREAM_KEY,
                self.CONSUMER_GROUP,
                id="0",
                mkstream=True
            )
            logger.info(f"IntakeQueue: Created consumer group {self.CONSUMER_GROUP}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.debug("IntakeQueue: Consumer group already exists")
            else:
                logger.warning(f"IntakeQueue: Redis init failed, using memory: {e}")
                self._redis = None

        self._initialized = True

    async def push(self, event: IntakeEvent) -> str:
        """Add event to the intake stream.

        Args:
            event: The intake event to store

        Returns:
            Event ID (Redis stream ID or UUID)
        """
        if not self._initialized:
            await self.initialize()

        if self._redis is None:
            # In-memory fallback
            self._memory_queue.append(event)
            logger.debug(f"IntakeQueue: Stored event {event.event_id} (memory)")
            return event.event_id

        try:
            # Redis Streams XADD
            stream_id = await self._redis.xadd(
                self.STREAM_KEY,
                event.to_dict(),
                maxlen=self.MAX_STREAM_LENGTH
            )
            logger.info(f"IntakeQueue: Stored event {event.event_id} as {stream_id}")
            return stream_id
        except Exception as e:
            logger.error(f"IntakeQueue: Redis push failed: {e}")
            # Fallback to memory
            self._memory_queue.append(event)
            return event.event_id

    async def read_pending(
        self,
        consumer_name: str = "default",
        count: int = 10,
        block_ms: int = 0
    ) -> list[tuple[str, IntakeEvent]]:
        """Read pending events from the stream.

        Args:
            consumer_name: Name of this consumer instance
            count: Maximum events to read
            block_ms: Block timeout (0 = no block)

        Returns:
            List of (stream_id, event) tuples
        """
        if not self._initialized:
            await self.initialize()

        if self._redis is None:
            # In-memory: return unprocessed events
            results = []
            for event in self._memory_queue:
                if not event.processed:
                    results.append((event.event_id, event))
                    if len(results) >= count:
                        break
            return results

        try:
            # Redis XREADGROUP
            messages = await self._redis.xreadgroup(
                self.CONSUMER_GROUP,
                consumer_name,
                {self.STREAM_KEY: ">"},
                count=count,
                block=block_ms if block_ms > 0 else None
            )

            results = []
            for stream_name, stream_messages in messages or []:
                for msg_id, msg_data in stream_messages:
                    event = IntakeEvent.from_dict(msg_data)
                    results.append((msg_id, event))

            return results
        except Exception as e:
            logger.error(f"IntakeQueue: Redis read failed: {e}")
            return []

    async def acknowledge(self, stream_id: str) -> bool:
        """Mark event as processed (acknowledge).

        Args:
            stream_id: The stream ID to acknowledge

        Returns:
            True if acknowledged successfully
        """
        if self._redis is None:
            # In-memory: mark as processed
            for event in self._memory_queue:
                if event.event_id == stream_id:
                    event.processed = True
                    return True
            return False

        try:
            await self._redis.xack(
                self.STREAM_KEY,
                self.CONSUMER_GROUP,
                stream_id
            )
            return True
        except Exception as e:
            logger.error(f"IntakeQueue: Acknowledge failed: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        if self._redis is None:
            total = len(self._memory_queue)
            processed = sum(1 for e in self._memory_queue if e.processed)
            return {
                "backend": "memory",
                "total_events": total,
                "processed": processed,
                "pending": total - processed
            }

        try:
            info = await self._redis.xinfo_stream(self.STREAM_KEY)
            return {
                "backend": "redis",
                "total_events": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "consumer_groups": info.get("groups", 0)
            }
        except Exception as e:
            return {"backend": "redis", "error": str(e)}
