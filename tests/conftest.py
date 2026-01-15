"""
Pytest configuration and shared fixtures.

This module provides fixtures for testing with PostgreSQL database.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Check if PostgreSQL is available
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/agentplatform_test"
)


# Check if required modules are available
def _check_module_available(module_name: str) -> bool:
    """Check if a module is available for import."""
    try:
        import subprocess

        result = subprocess.run(
            ["python", "-c", f"import {module_name}"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


HAS_ASYNCPG = _check_module_available("asyncpg")
HAS_GCP_SECRETMANAGER = _check_module_available("google.cloud.secretmanager")


def _check_database_available() -> bool:
    """Check if the database is actually reachable."""
    if not HAS_ASYNCPG:
        return False
    try:
        import asyncpg  # noqa: PLC0415

        async def check_connection():
            # Parse the DATABASE_URL to get connection parameters
            url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            try:
                conn = await asyncio.wait_for(asyncpg.connect(url), timeout=5.0)
                await conn.close()
                return True
            except Exception:
                return False

        # Use asyncio.run() for Python 3.10+ compatibility
        return asyncio.run(check_connection())
    except Exception:
        return False


DATABASE_AVAILABLE = _check_database_available()


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring database"
    )
    config.addinivalue_line("markers", "requires_gcp: mark test as requiring GCP credentials")


def pytest_collection_modifyitems(config, items):
    """Skip tests based on available dependencies."""
    skip_integration = pytest.mark.skip(
        reason="PostgreSQL not available (database unreachable or asyncpg not installed)"
    )
    skip_gcp = pytest.mark.skip(reason="GCP Secret Manager not available")

    for item in items:
        if "integration" in item.keywords and not DATABASE_AVAILABLE:
            item.add_marker(skip_integration)
        if "requires_gcp" in item.keywords and not HAS_GCP_SECRETMANAGER:
            item.add_marker(skip_gcp)


@pytest.fixture(scope="session")
def database_url() -> str:
    """Return the test database URL."""
    return DATABASE_URL


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    if not DATABASE_AVAILABLE:
        pytest.skip("PostgreSQL database not available")

    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    return engine


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a database session for testing.

    This fixture creates tables, provides a session, and rolls back after test.
    """
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
def mock_db_session():
    """Create a mock database session for unit tests."""
    session = MagicMock(spec=AsyncSession)
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a FastAPI test client."""
    from src.api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client for testing code generation."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text='''```python
def generated_agent():
    """A simple generated agent."""
    return "Hello from generated agent"
```'''
        )
    ]
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def sample_agent_data():
    """Return sample agent data for testing."""
    return {
        "name": "Test Agent",
        "description": "A test agent for integration testing",
        "code": '''def run():
    """Execute the agent."""
    return {"status": "success", "message": "Agent executed"}
''',
        "status": "active",
        "created_by": "test_user",
        "config": '{"schedule": "0 * * * *"}',
    }


@pytest.fixture
def sample_task_data():
    """Return sample task data for testing."""
    return {
        "agent_id": 1,
        "status": "pending",
        "result": None,
        "error": None,
        "retry_count": 0,
    }
