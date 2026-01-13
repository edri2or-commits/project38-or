"""
Integration tests for Agent CRUD API endpoints.

This module tests the agent creation, listing, retrieval, update, and deletion
endpoints with mocked database operations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.database import get_session
from src.api.main import app
from src.models.agent import Agent


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def test_client(mock_db_session):
    """Create test client with mocked database."""

    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def sample_agent_data():
    """Sample agent data for testing."""
    return {
        "id": 1,
        "name": "Test Agent",
        "description": "Test agent for testing",
        "code": "def test():\n    pass",
        "status": "active",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "created_by": "test_user",
        "config": '{"test": true}',
    }


class TestCreateAgent:
    """Tests for POST /agents endpoint."""

    def test_create_agent(self, test_client, mock_db_session, mocker):
        """Test creating an agent (mocking factory functions and DB)."""
        # Mock factory functions to avoid calling Claude API
        mocker.patch(
            "src.api.routes.agents.generate_agent_code",
            return_value={
                "code": "def generated_code():\n    pass",
                "tokens_used": 100,
            },
        )

        mocker.patch(
            "src.api.routes.agents.ralph_wiggum_loop",
            return_value={
                "code": "def fixed_code():\n    pass",
                "passed": True,
                "iterations": 1,
                "tokens_used": 50,
                "errors": [],
                "warnings": [],
            },
        )

        mocker.patch(
            "src.api.routes.agents.get_loop_summary",
            return_value="Ralph loop completed successfully",
        )

        # Mock database operations
        mock_agent = MagicMock(spec=Agent)
        mock_agent.id = 1
        mock_agent.name = "Tesla Monitor"
        mock_agent.description = "Test agent that monitors Tesla stock"
        mock_agent.code = "def fixed_code():\n    pass"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()
        mock_agent.created_by = "test_user"
        mock_agent.config = None

        # Mock session methods
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # When refresh is called, populate the agent with an ID
        async def mock_refresh(obj):
            obj.id = 1

        mock_db_session.refresh.side_effect = mock_refresh

        # Create agent
        response = test_client.post(
            "/api/agents",
            json={
                "description": "Test agent that monitors Tesla stock",
                "name": "Tesla Monitor",
                "created_by": "test_user",
                "strict_validation": True,
            },
        )

        # Assertions
        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Tesla Monitor"
        assert data["description"] == "Test agent that monitors Tesla stock"
        assert data["code"] == "def fixed_code():\n    pass"
        assert data["status"] == "active"
        assert data["created_by"] == "test_user"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["generation_cost"] > 0
        assert data["iterations"] == 1
        assert data["tokens_used"] == 150


class TestListAgents:
    """Tests for GET /agents endpoint."""

    def test_list_agents_empty(self, test_client, mock_db_session):
        """Test listing agents when database is empty."""
        # Mock execute to return empty list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_agents_with_data(self, test_client, mock_db_session, sample_agent_data):
        """Test listing agents with data."""
        # Create mock agent
        mock_agent = MagicMock(spec=Agent)
        for key, value in sample_agent_data.items():
            setattr(mock_agent, key, value)

        # Mock execute to return agent list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_agent]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        agent = data[0]
        assert agent["id"] == 1
        assert agent["name"] == "Test Agent"
        assert agent["status"] == "active"


class TestGetAgent:
    """Tests for GET /agents/{agent_id} endpoint."""

    def test_get_agent_success(self, test_client, mock_db_session, sample_agent_data):
        """Test retrieving a specific agent."""
        # Create mock agent
        mock_agent = MagicMock(spec=Agent)
        for key, value in sample_agent_data.items():
            setattr(mock_agent, key, value)

        # Mock execute to return agent
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/agents/1")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == 1
        assert data["name"] == "Test Agent"
        assert data["description"] == "Test agent for testing"
        assert data["status"] == "active"
        assert data["created_by"] == "test_user"

    def test_get_agent_not_found(self, test_client, mock_db_session):
        """Test retrieving a non-existent agent."""
        # Mock execute to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/agents/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestUpdateAgent:
    """Tests for PUT /agents/{agent_id} endpoint."""

    def test_update_agent_status(self, test_client, mock_db_session, sample_agent_data):
        """Test updating agent status."""
        # Create mock agent
        mock_agent = MagicMock(spec=Agent)
        for key, value in sample_agent_data.items():
            setattr(mock_agent, key, value)

        # Mock execute to return agent
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock session methods
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = test_client.put(
            "/api/agents/1",
            json={"status": "paused"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == 1
        assert data["status"] == "paused"

    def test_update_agent_not_found(self, test_client, mock_db_session):
        """Test updating a non-existent agent."""
        # Mock execute to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.put(
            "/agents/99999",
            json={"status": "paused"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestDeleteAgent:
    """Tests for DELETE /agents/{agent_id} endpoint."""

    def test_delete_agent_success(self, test_client, mock_db_session, sample_agent_data):
        """Test deleting an agent."""
        # Create mock agent
        mock_agent = MagicMock(spec=Agent)
        for key, value in sample_agent_data.items():
            setattr(mock_agent, key, value)

        # Mock execute to return agent
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock session methods
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        response = test_client.delete("/api/agents/1")

        assert response.status_code == 204

    def test_delete_agent_not_found(self, test_client, mock_db_session):
        """Test deleting a non-existent agent."""
        # Mock execute to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.delete("/api/agents/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
