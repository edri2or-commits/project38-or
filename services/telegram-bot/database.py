"""Database connection management for Telegram Bot service.

This module handles PostgreSQL connection pooling and session management
using SQLModel and asyncpg.
"""

import logging
import os
from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

# Global engine and session maker (lazy initialization)
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[sessionmaker] = None


def _get_database_url() -> Optional[str]:
    """Get and convert database URL from environment.

    Returns:
        Optional[str]: Converted DATABASE_URL or None if not set
    """
    database_url_raw = os.environ.get("DATABASE_URL")

    if not database_url_raw:
        return None

    # Railway provides postgres:// but SQLAlchemy async requires postgresql+asyncpg://
    if database_url_raw.startswith("postgres://"):
        return database_url_raw.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url_raw.startswith("postgresql://"):
        return database_url_raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        return database_url_raw


def _get_engine() -> Optional[AsyncEngine]:
    """Get or create the database engine (lazy initialization).

    Returns:
        Optional[AsyncEngine]: Database engine or None if DATABASE_URL not set
    """
    global _engine

    if _engine is not None:
        return _engine

    database_url = _get_database_url()
    if not database_url:
        logger.warning("DATABASE_URL not set - database features unavailable")
        return None

    logger.info("Creating database engine...")
    _engine = create_async_engine(
        database_url,
        echo=os.environ.get("DEBUG", "").lower() == "true",
        future=True,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,  # Verify connections before using
    )
    logger.info("Database engine created successfully")
    return _engine


def _get_session_maker() -> Optional[sessionmaker]:
    """Get or create the async session maker (lazy initialization).

    Returns:
        Optional[sessionmaker]: Session maker or None if no engine
    """
    global _async_session_maker

    if _async_session_maker is not None:
        return _async_session_maker

    engine = _get_engine()
    if engine is None:
        return None

    _async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _async_session_maker


async def create_db_and_tables() -> None:
    """Create database tables if they don't exist.

    Should be called on application startup.
    """
    engine = _get_engine()
    if engine is None:
        logger.warning("Skipping table creation - no database connection")
        return

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables created/verified")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session.

    Yields:
        AsyncSession: Database session

    Raises:
        RuntimeError: If database is not configured

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/messages")
        >>> async def get_messages(session: AsyncSession = Depends(get_session)):
        >>>     result = await session.execute(select(ConversationMessage))
        >>>     return result.scalars().all()
    """
    session_maker = _get_session_maker()
    if session_maker is None:
        raise RuntimeError("Database not configured - DATABASE_URL not set")

    async with session_maker() as session:
        yield session


async def close_db_connection() -> None:
    """Close database connection pool.

    Should be called on application shutdown.
    """
    global _engine, _async_session_maker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("Database connection pool closed")


async def check_database_connection() -> bool:
    """Check if database connection is alive.

    Returns:
        bool: True if database is reachable, False otherwise

    Example:
        >>> is_healthy = await check_database_connection()
        >>> print(f"Database: {'healthy' if is_healthy else 'unhealthy'}")
    """
    session_maker = _get_session_maker()
    if session_maker is None:
        return False

    try:
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
