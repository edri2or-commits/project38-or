"""Pytest configuration and fixtures for test suite."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.harness.handoff import HandoffArtifact  # noqa: F401
from src.models.agent import Agent  # noqa: F401
from src.models.task import Task  # noqa: F401

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an async session for testing.

    Creates an in-memory SQLite database for each test function.
    """
    # Create async engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Create session with SQLModel's AsyncSession
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    # Cleanup
    await engine.dispose()
