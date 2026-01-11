"""
Database connection management for Agent Platform.

This module handles PostgreSQL connection pooling and session management
using SQLModel and asyncpg.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Database connection URL from environment variable
# Format: postgresql+asyncpg://user:password@host:port/database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/agentplatform",
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True if os.environ.get("DEBUG") == "true" else False,
    future=True,
    pool_size=20,
    max_overflow=10,
)

# Create async session factory
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def create_db_and_tables() -> None:
    """
    Create database tables if they don't exist.

    Should be called on application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.

    Yields:
        AsyncSession: Database session

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/agents")
        >>> async def get_agents(session: AsyncSession = Depends(get_session)):
        >>>     result = await session.execute(select(Agent))
        >>>     return result.scalars().all()
    """
    async with async_session_maker() as session:
        yield session


async def close_db_connection() -> None:
    """
    Close database connection pool.

    Should be called on application shutdown.
    """
    await engine.dispose()


# Health check function
async def check_database_connection() -> bool:
    """
    Check if database connection is alive.

    Returns:
        bool: True if database is reachable, False otherwise

    Example:
        >>> is_healthy = await check_database_connection()
        >>> print(f"Database: {'healthy' if is_healthy else 'unhealthy'}")
    """
    try:
        async with async_session_maker() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:  # noqa: BLE001
        return False

