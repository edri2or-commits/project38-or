"""Database connection management for Telegram Bot service.

This module handles PostgreSQL connection pooling and session management
using SQLModel and asyncpg.
"""

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

# Database connection URL from environment variable
# Railway provides postgres:// but SQLAlchemy async requires postgresql+asyncpg://
DATABASE_URL_RAW = os.environ.get("DATABASE_URL")

if DATABASE_URL_RAW:
    if DATABASE_URL_RAW.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL_RAW.replace("postgres://", "postgresql+asyncpg://", 1)
        logger.info("Converted Railway postgres:// URL to postgresql+asyncpg://")
    elif DATABASE_URL_RAW.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL_RAW.replace("postgresql://", "postgresql+asyncpg://", 1)
        logger.info("Converted postgresql:// URL to postgresql+asyncpg://")
    else:
        DATABASE_URL = DATABASE_URL_RAW
        logger.info("Using DATABASE_URL as provided")
else:
    # Development fallback
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/telegrambot"
    logger.warning("DATABASE_URL not set, using development default")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True if os.environ.get("DEBUG") == "true" else False,
    future=True,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,  # Verify connections before using
)

# Create async session factory
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables() -> None:
    """Create database tables if they don't exist.

    Should be called on application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables created/verified")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session.

    Yields:
        AsyncSession: Database session

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/messages")
        >>> async def get_messages(session: AsyncSession = Depends(get_session)):
        >>>     result = await session.execute(select(ConversationMessage))
        >>>     return result.scalars().all()
    """
    async with async_session_maker() as session:
        yield session


async def close_db_connection() -> None:
    """Close database connection pool.

    Should be called on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connection pool closed")


async def check_database_connection() -> bool:
    """Check if database connection is alive.

    Returns:
        bool: True if database is reachable, False otherwise

    Example:
        >>> is_healthy = await check_database_connection()
        >>> print(f"Database: {'healthy' if is_healthy else 'unhealthy'}")
    """
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
