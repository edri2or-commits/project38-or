"""Database models for Telegram Bot service.

This module defines SQLModel models for storing conversation history.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ConversationMessage(SQLModel, table=True):
    """Stores individual messages in conversations.

    Attributes:
        id: Auto-incrementing primary key
        chat_id: Telegram chat ID
        user_id: Telegram user ID
        username: Telegram username (optional)
        role: Message role ("user" or "assistant")
        content: Message text content
        model: LLM model used for assistant messages
        tokens_used: Number of tokens used (for cost tracking)
        created_at: Message timestamp
    """

    __tablename__ = "conversation_messages"

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)
    user_id: int = Field(index=True)
    username: str | None = Field(default=None)
    role: str = Field(max_length=20)  # "user" or "assistant"
    content: str
    model: str | None = Field(default=None)
    tokens_used: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationStats(SQLModel, table=True):
    """Aggregated statistics per user.

    Attributes:
        id: Auto-incrementing primary key
        user_id: Telegram user ID
        username: Telegram username (optional)
        total_messages: Total messages sent by user
        total_tokens: Total tokens consumed
        total_cost_usd: Estimated cost in USD
        first_interaction: First message timestamp
        last_interaction: Last message timestamp
    """

    __tablename__ = "conversation_stats"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(unique=True, index=True)
    username: str | None = Field(default=None)
    total_messages: int = Field(default=0)
    total_tokens: int = Field(default=0)
    total_cost_usd: float = Field(default=0.0)
    first_interaction: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_interaction: datetime = Field(default_factory=lambda: datetime.now(UTC))
