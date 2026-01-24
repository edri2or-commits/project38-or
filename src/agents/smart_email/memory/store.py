"""Memory Store for Smart Email Agent.

PostgreSQL-backed persistent memory for:
- Sender profiles (semantic memory)
- Interaction records (episodic memory)
- Conversation context (short-term memory)

Uses Railway PostgreSQL (already deployed).
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# SQL Schema for memory tables
SCHEMA_SQL = """
-- Sender Profiles (Semantic Memory)
CREATE TABLE IF NOT EXISTS sender_profiles (
    email VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    display_name VARCHAR(255),
    relationship_type VARCHAR(50) DEFAULT 'new',
    role VARCHAR(255),
    organization VARCHAR(255),
    first_contact TIMESTAMP,
    last_contact TIMESTAMP,
    total_interactions INTEGER DEFAULT 0,
    typical_topics JSONB DEFAULT '[]',
    typical_priority VARCHAR(10) DEFAULT 'P3',
    typical_category VARCHAR(50) DEFAULT 'מידע',
    typical_urgency FLOAT DEFAULT 0.3,
    avg_response_expected_hours FLOAT DEFAULT 48.0,
    user_avg_response_hours FLOAT DEFAULT 24.0,
    best_contact_time VARCHAR(50),
    preferred_tone VARCHAR(50) DEFAULT 'professional',
    language VARCHAR(20) DEFAULT 'hebrew',
    uses_formal_greeting BOOLEAN DEFAULT TRUE,
    is_vip BOOLEAN DEFAULT FALSE,
    requires_immediate_attention BOOLEAN DEFAULT FALSE,
    auto_archive BOOLEAN DEFAULT FALSE,
    notes TEXT,
    recent_threads JSONB DEFAULT '[]',
    pending_from_them INTEGER DEFAULT 0,
    pending_to_them INTEGER DEFAULT 0,
    relationship_summary TEXT,
    last_summary_update TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Interaction Records (Episodic Memory)
CREATE TABLE IF NOT EXISTS interaction_records (
    id VARCHAR(255) PRIMARY KEY,
    sender_email VARCHAR(255) REFERENCES sender_profiles(email) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    email_id VARCHAR(255),
    thread_id VARCHAR(255),
    subject TEXT,
    direction VARCHAR(20) DEFAULT 'incoming',
    priority VARCHAR(10) DEFAULT 'P3',
    category VARCHAR(50) DEFAULT 'מידע',
    action_type VARCHAR(50),
    action_details TEXT,
    action_outcome TEXT,
    action_success BOOLEAN,
    was_correct_action BOOLEAN,
    was_urgent BOOLEAN DEFAULT FALSE,
    had_deadline BOOLEAN DEFAULT FALSE,
    deadline_date TIMESTAMP,
    had_attachments BOOLEAN DEFAULT FALSE,
    user_response_time_hours FLOAT,
    importance_score FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Thread Summaries (Episodic Memory)
CREATE TABLE IF NOT EXISTS thread_summaries (
    thread_id VARCHAR(255) PRIMARY KEY,
    subject TEXT,
    participants JSONB DEFAULT '[]',
    started TIMESTAMP,
    last_activity TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    summary TEXT,
    key_points JSONB DEFAULT '[]',
    decisions_made JSONB DEFAULT '[]',
    pending_actions JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'active',
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversation Context (Short-term Memory)
CREATE TABLE IF NOT EXISTS conversation_contexts (
    user_id VARCHAR(255) PRIMARY KEY,
    chat_id VARCHAR(255),
    started_at TIMESTAMP,
    last_message_at TIMESTAMP,
    current_email_id VARCHAR(255),
    current_thread_id VARCHAR(255),
    current_sender VARCHAR(255),
    awaiting_response BOOLEAN DEFAULT FALSE,
    awaiting_action VARCHAR(100),
    pending_action_data JSONB DEFAULT '{}',
    recent_messages JSONB DEFAULT '[]',
    discussed_emails JSONB DEFAULT '[]',
    discussed_senders JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Procedural Memory (Action Rules)
CREATE TABLE IF NOT EXISTS action_rules (
    id SERIAL PRIMARY KEY,
    rule_type VARCHAR(50) NOT NULL,  -- sender_rule, category_rule, keyword_rule
    condition JSONB NOT NULL,         -- {"sender_domain": "gov.il"} or {"category": "בירוקרטיה"}
    action VARCHAR(50) NOT NULL,      -- prioritize, auto_archive, remind, etc.
    action_params JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 0,       -- Higher = checked first
    enabled BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(50) DEFAULT 'system',
    times_triggered INTEGER DEFAULT 0,
    last_triggered TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_interactions_sender ON interaction_records(sender_email);
CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interaction_records(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_thread ON interaction_records(thread_id);
CREATE INDEX IF NOT EXISTS idx_sender_last_contact ON sender_profiles(last_contact DESC);
CREATE INDEX IF NOT EXISTS idx_sender_vip ON sender_profiles(is_vip) WHERE is_vip = TRUE;
"""


class MemoryStore:
    """PostgreSQL-backed memory store for email agent.

    Handles all CRUD operations for:
    - Sender profiles
    - Interaction records
    - Thread summaries
    - Conversation context
    - Action rules

    Example:
        store = MemoryStore()
        await store.initialize()

        # Get or create sender profile
        profile = await store.get_sender_profile("danny@example.com")
        if not profile:
            profile = await store.create_sender_profile("danny@example.com", "Danny")

        # Record interaction
        await store.record_interaction(sender_email, email_id, ...)

        # Get context for LLM
        context = await store.get_sender_context("danny@example.com")
    """

    def __init__(self, database_url: str | None = None):
        """Initialize memory store.

        Args:
            database_url: PostgreSQL connection URL.
                         If None, uses DATABASE_URL env var.
        """
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        self._pool = None

    async def initialize(self) -> bool:
        """Initialize database connection and create schema.

        Returns:
            True if successful
        """
        if not self.database_url:
            logger.warning("DATABASE_URL not set, memory store disabled")
            return False

        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(self.database_url)

            # Create schema
            async with self._pool.acquire() as conn:
                await conn.execute(SCHEMA_SQL)

            logger.info("Memory store initialized successfully")
            return True

        except ImportError:
            logger.warning("asyncpg not installed, memory store disabled")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize memory store: {e}")
            return False

    async def close(self) -> None:
        """Close database connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    # === Sender Profile Operations ===

    async def get_sender_profile(self, email: str) -> dict | None:
        """Get sender profile by email.

        Args:
            email: Sender email address

        Returns:
            Profile dict or None if not found
        """
        if not self._pool:
            return None

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM sender_profiles WHERE email = $1",
                    email.lower()
                )
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting sender profile: {e}")
            return None

    async def create_sender_profile(
        self,
        email: str,
        name: str = "",
        **kwargs
    ) -> dict:
        """Create new sender profile.

        Args:
            email: Sender email address
            name: Sender name
            **kwargs: Additional fields

        Returns:
            Created profile dict
        """
        if not self._pool:
            # Return in-memory only profile
            return {
                "email": email.lower(),
                "name": name,
                "relationship_type": "new",
                "total_interactions": 0,
                "created_at": datetime.now(),
                **kwargs
            }

        try:
            async with self._pool.acquire() as conn:
                # Build dynamic insert
                fields = ["email", "name", "first_contact", "created_at"]
                values = [email.lower(), name, datetime.now(), datetime.now()]
                placeholders = ["$1", "$2", "$3", "$4"]

                i = 5
                for key, value in kwargs.items():
                    fields.append(key)
                    if isinstance(value, (list, dict)):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
                    placeholders.append(f"${i}")
                    i += 1

                sql = f"""
                    INSERT INTO sender_profiles ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (email) DO UPDATE SET
                        name = EXCLUDED.name,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING *
                """
                row = await conn.fetchrow(sql, *values)
                return dict(row)

        except Exception as e:
            logger.error(f"Error creating sender profile: {e}")
            return {"email": email.lower(), "name": name, "error": str(e)}

    async def update_sender_profile(self, email: str, **updates) -> bool:
        """Update sender profile fields.

        Args:
            email: Sender email address
            **updates: Fields to update

        Returns:
            True if successful
        """
        if not self._pool or not updates:
            return False

        try:
            async with self._pool.acquire() as conn:
                # Build dynamic update
                sets = ["updated_at = CURRENT_TIMESTAMP"]
                values = []
                i = 1

                for key, value in updates.items():
                    if isinstance(value, (list, dict)):
                        sets.append(f"{key} = ${i}::jsonb")
                        values.append(json.dumps(value))
                    else:
                        sets.append(f"{key} = ${i}")
                        values.append(value)
                    i += 1

                values.append(email.lower())
                sql = f"""
                    UPDATE sender_profiles
                    SET {', '.join(sets)}
                    WHERE email = ${i}
                """
                await conn.execute(sql, *values)
                return True

        except Exception as e:
            logger.error(f"Error updating sender profile: {e}")
            return False

    async def increment_interaction(self, email: str) -> None:
        """Increment interaction count and update last_contact.

        Args:
            email: Sender email address
        """
        if not self._pool:
            return

        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE sender_profiles
                    SET total_interactions = total_interactions + 1,
                        last_contact = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = $1
                """, email.lower())
        except Exception as e:
            logger.error(f"Error incrementing interaction: {e}")

    async def get_frequent_senders(self, limit: int = 20) -> list[dict]:
        """Get most frequent senders.

        Args:
            limit: Max senders to return

        Returns:
            List of sender profiles
        """
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM sender_profiles
                    ORDER BY total_interactions DESC
                    LIMIT $1
                """, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting frequent senders: {e}")
            return []

    async def get_vip_senders(self) -> list[dict]:
        """Get all VIP senders.

        Returns:
            List of VIP sender profiles
        """
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM sender_profiles
                    WHERE is_vip = TRUE OR requires_immediate_attention = TRUE
                    ORDER BY last_contact DESC
                """)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting VIP senders: {e}")
            return []

    # === Interaction Recording ===

    async def record_interaction(
        self,
        sender_email: str,
        email_id: str,
        thread_id: str,
        subject: str,
        priority: str = "P3",
        category: str = "מידע",
        **kwargs
    ) -> str:
        """Record an interaction with a sender.

        Also updates sender profile stats.

        Args:
            sender_email: Sender email address
            email_id: Email ID
            thread_id: Thread ID
            subject: Email subject
            priority: Priority level
            category: Email category
            **kwargs: Additional fields

        Returns:
            Interaction ID
        """
        interaction_id = f"int_{email_id}_{int(datetime.now().timestamp())}"

        if not self._pool:
            return interaction_id

        try:
            # Ensure sender profile exists
            profile = await self.get_sender_profile(sender_email)
            if not profile:
                await self.create_sender_profile(sender_email)

            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO interaction_records
                    (id, sender_email, timestamp, email_id, thread_id, subject, priority, category)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO NOTHING
                """, interaction_id, sender_email.lower(), datetime.now(),
                    email_id, thread_id, subject, priority, category)

            # Update sender stats
            await self.increment_interaction(sender_email)

            # Update typical patterns
            await self._update_sender_patterns(sender_email, priority, category)

            return interaction_id

        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            return interaction_id

    async def _update_sender_patterns(
        self,
        email: str,
        priority: str,
        category: str
    ) -> None:
        """Update sender's typical patterns based on new interaction.

        Uses simple frequency counting to determine typical priority/category.
        """
        if not self._pool:
            return

        try:
            async with self._pool.acquire() as conn:
                # Get recent interactions
                rows = await conn.fetch("""
                    SELECT priority, category FROM interaction_records
                    WHERE sender_email = $1
                    ORDER BY timestamp DESC
                    LIMIT 20
                """, email.lower())

                if not rows:
                    return

                # Count frequencies
                priorities = {}
                categories = {}
                for row in rows:
                    p = row["priority"]
                    c = row["category"]
                    priorities[p] = priorities.get(p, 0) + 1
                    categories[c] = categories.get(c, 0) + 1

                # Get most common
                typical_priority = max(priorities, key=priorities.get)
                typical_category = max(categories, key=categories.get)

                # Calculate urgency score
                urgent_count = priorities.get("P1", 0) + priorities.get("P2", 0)
                typical_urgency = urgent_count / len(rows)

                # Update profile
                await conn.execute("""
                    UPDATE sender_profiles
                    SET typical_priority = $2,
                        typical_category = $3,
                        typical_urgency = $4,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = $1
                """, email.lower(), typical_priority, typical_category, typical_urgency)

        except Exception as e:
            logger.error(f"Error updating sender patterns: {e}")

    async def get_sender_history(
        self,
        email: str,
        limit: int = 20
    ) -> list[dict]:
        """Get interaction history with sender.

        Args:
            email: Sender email address
            limit: Max interactions to return

        Returns:
            List of interaction records
        """
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM interaction_records
                    WHERE sender_email = $1
                    ORDER BY timestamp DESC
                    LIMIT $2
                """, email.lower(), limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting sender history: {e}")
            return []

    # === Conversation Context ===

    async def get_conversation_context(self, user_id: str) -> dict | None:
        """Get current conversation context for user.

        Args:
            user_id: User ID

        Returns:
            Context dict or None
        """
        if not self._pool:
            return None

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM conversation_contexts WHERE user_id = $1",
                    user_id
                )
                if row:
                    result = dict(row)
                    # Parse JSON fields
                    for field in ["pending_action_data", "recent_messages",
                                  "discussed_emails", "discussed_senders"]:
                        if result.get(field) and isinstance(result[field], str):
                            result[field] = json.loads(result[field])
                    return result
                return None
        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return None

    async def save_conversation_context(
        self,
        user_id: str,
        chat_id: str,
        **kwargs
    ) -> bool:
        """Save conversation context.

        Args:
            user_id: User ID
            chat_id: Chat ID
            **kwargs: Context fields

        Returns:
            True if successful
        """
        if not self._pool:
            return False

        try:
            async with self._pool.acquire() as conn:
                # Convert complex types to JSON
                for key in ["pending_action_data", "recent_messages",
                            "discussed_emails", "discussed_senders"]:
                    if key in kwargs and isinstance(kwargs[key], (list, dict)):
                        kwargs[key] = json.dumps(kwargs[key])

                await conn.execute("""
                    INSERT INTO conversation_contexts
                    (user_id, chat_id, started_at, last_message_at, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        chat_id = $2,
                        last_message_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                """, user_id, chat_id)

                # Update additional fields
                if kwargs:
                    await self._update_conversation_fields(user_id, **kwargs)

                return True

        except Exception as e:
            logger.error(f"Error saving conversation context: {e}")
            return False

    async def _update_conversation_fields(self, user_id: str, **kwargs) -> None:
        """Update specific conversation context fields."""
        if not self._pool or not kwargs:
            return

        try:
            async with self._pool.acquire() as conn:
                sets = []
                values = []
                i = 1

                for key, value in kwargs.items():
                    if isinstance(value, (list, dict)):
                        sets.append(f"{key} = ${i}::jsonb")
                        values.append(json.dumps(value))
                    else:
                        sets.append(f"{key} = ${i}")
                        values.append(value)
                    i += 1

                values.append(user_id)
                sql = f"""
                    UPDATE conversation_contexts
                    SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ${i}
                """
                await conn.execute(sql, *values)

        except Exception as e:
            logger.error(f"Error updating conversation fields: {e}")

    async def add_message_to_context(
        self,
        user_id: str,
        role: str,
        content: str
    ) -> None:
        """Add message to conversation context.

        Args:
            user_id: User ID
            role: "user" or "assistant"
            content: Message content
        """
        if not self._pool:
            return

        try:
            async with self._pool.acquire() as conn:
                # Get current messages
                row = await conn.fetchrow(
                    "SELECT recent_messages FROM conversation_contexts WHERE user_id = $1",
                    user_id
                )

                messages = []
                if row and row["recent_messages"]:
                    if isinstance(row["recent_messages"], str):
                        messages = json.loads(row["recent_messages"])
                    else:
                        messages = row["recent_messages"]

                # Add new message
                messages.append({
                    "role": role,
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                })

                # Keep only last 30
                if len(messages) > 30:
                    messages = messages[-30:]

                await conn.execute("""
                    UPDATE conversation_contexts
                    SET recent_messages = $2::jsonb,
                        last_message_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, json.dumps(messages))

        except Exception as e:
            logger.error(f"Error adding message to context: {e}")

    # === Context Building ===

    async def get_sender_context_for_llm(self, email: str) -> str:
        """Get comprehensive context about a sender for LLM.

        Combines sender profile, recent interactions, and patterns.

        Args:
            email: Sender email address

        Returns:
            Context string for LLM prompt
        """
        parts = []

        # Get profile
        profile = await self.get_sender_profile(email)
        if profile:
            # Identity
            name = profile.get("name") or email
            role = profile.get("role", "")
            org = profile.get("organization", "")

            if role:
                parts.append(f"{name} הוא {role}")
            elif org:
                parts.append(f"{name} מ-{org}")
            else:
                parts.append(f"שולח: {name}")

            # Relationship
            rel_type = profile.get("relationship_type", "new")
            total = profile.get("total_interactions", 0)
            parts.append(f"סוג קשר: {rel_type} ({total} אינטראקציות)")

            # Patterns
            topics = profile.get("typical_topics", [])
            if topics:
                parts.append(f"נושאים טיפוסיים: {', '.join(topics[:3])}")

            typical_priority = profile.get("typical_priority", "P3")
            if typical_priority in ["P1", "P2"]:
                parts.append(f"בדרך כלל עדיפות {typical_priority}")

            # Notes
            notes = profile.get("notes", "")
            if notes:
                parts.append(f"הערות: {notes}")

            # Summary
            summary = profile.get("relationship_summary", "")
            if summary:
                parts.append(f"סיכום: {summary}")

        # Get recent history
        history = await self.get_sender_history(email, limit=5)
        if history:
            recent = []
            for h in history[:3]:
                subject = h.get("subject", "")[:30]
                date = h.get("timestamp")
                if date:
                    if isinstance(date, datetime):
                        date_str = date.strftime("%d/%m")
                    else:
                        date_str = str(date)[:10]
                    recent.append(f"- {date_str}: {subject}")
            if recent:
                parts.append("אינטראקציות אחרונות:\n" + "\n".join(recent))

        return "\n".join(parts) if parts else f"שולח חדש: {email}"

    async def get_email_context_for_llm(
        self,
        email_id: str,
        sender_email: str
    ) -> str:
        """Get comprehensive context about an email for LLM.

        Args:
            email_id: Email ID
            sender_email: Sender email address

        Returns:
            Context string for LLM prompt
        """
        parts = []

        # Get sender context
        sender_context = await self.get_sender_context_for_llm(sender_email)
        parts.append(f"=== שולח ===\n{sender_context}")

        # Get thread history if available
        # (Would need thread_id to look up)

        return "\n\n".join(parts)
