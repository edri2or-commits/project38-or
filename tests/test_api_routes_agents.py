"""Tests for Agent CRUD API endpoints.

Tests the agents module in src/api/routes/agents.py.
Covers:
- Agent creation with code generation
- Agent listing with filters
- Agent retrieval by ID
- Agent updates
- Agent deletion
- Agent execution (not implemented)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Mock dependencies before importing the routes
import sys

# Mock factory modules
_mock_generator = MagicMock()
_mock_generator.estimate_cost = MagicMock(return_value=0.05)
_mock_generator.generate_agent_code = AsyncMock(return_value={
    "code": "def agent(): pass",
    "tokens_used": 100,
})
sys.modules["src.factory.generator"] = _mock_generator

_mock_ralph = MagicMock()
_mock_ralph.ralph_wiggum_loop = AsyncMock(return_value={
    "passed": True,
    "code": "def agent(): pass",
    "iterations": 1,
    "errors": [],
    "warnings": [],
    "tokens_used": 50,
})
_mock_ralph.get_loop_summary = MagicMock(return_value="Passed in 1 iteration")
sys.modules["src.factory.ralph_loop"] = _mock_ralph

# Mock database
_mock_database = MagicMock()
_mock_database.get_session = MagicMock()
sys.modules["src.api.database"] = _mock_database

# Now import the routes
from src.api.routes.agents import (
    AgentCreateRequest,
    AgentCreateResponse,
    AgentResponse,
    AgentUpdateRequest,
    AgentExecuteRequest,
    create_agent,
    list_agents,
    get_agent,
    update_agent,
    delete_agent,
    execute_agent,
)


class TestAgentCreateRequest:
    """Tests for AgentCreateRequest model."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = AgentCreateRequest(
            description="Monitor stock prices and alert on changes",
            name="Stock Monitor",
            created_by="user-123",
        )

        assert request.description == "Monitor stock prices and alert on changes"
        assert request.name == "Stock Monitor"
        assert request.created_by == "user-123"
        assert request.strict_validation is True  # Default

    def test_minimal_request(self):
        """Test request with only required fields."""
        request = AgentCreateRequest(
            description="A simple agent that does something useful"
        )

        assert request.name is None
        assert request.created_by is None

    def test_strict_validation_override(self):
        """Test overriding strict validation."""
        request = AgentCreateRequest(
            description="Test agent description here",
            strict_validation=False,
        )

        assert request.strict_validation is False


class TestAgentResponse:
    """Tests for AgentResponse model."""

    def test_full_response(self):
        """Test response with all fields."""
        response = AgentResponse(
            id=1,
            name="Test Agent",
            description="Test description",
            code="def run(): pass",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="user-123",
            config='{"key": "value"}',
        )

        assert response.id == 1
        assert response.name == "Test Agent"
        assert response.status == "active"

    def test_response_optional_fields(self):
        """Test response with optional fields as None."""
        response = AgentResponse(
            id=1,
            name="Test Agent",
            description="Test",
            code="def run(): pass",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert response.created_by is None
        assert response.config is None


class TestAgentCreateResponse:
    """Tests for AgentCreateResponse model."""

    def test_includes_generation_metrics(self):
        """Test that response includes generation metrics."""
        response = AgentCreateResponse(
            id=1,
            name="Test Agent",
            description="Test",
            code="def run(): pass",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            generation_cost=0.05,
            iterations=2,
            tokens_used=150,
        )

        assert response.generation_cost == 0.05
        assert response.iterations == 2
        assert response.tokens_used == 150


class TestCreateAgent:
    """Tests for create_agent endpoint."""

    @pytest.mark.asyncio
    async def test_create_agent_success(self):
        """Test successful agent creation."""
        # Mock the session
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test Agent"
        mock_agent.description = "Test description"
        mock_agent.code = "def agent(): pass"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()
        mock_agent.created_by = None
        mock_agent.config = None

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Reset mocks
        _mock_generator.generate_agent_code.reset_mock()
        _mock_ralph.ralph_wiggum_loop.reset_mock()

        request = AgentCreateRequest(
            description="Monitor stock prices and send alerts"
        )

        with patch("src.api.routes.agents.Agent", return_value=mock_agent):
            result = await create_agent(request, mock_session)

        assert result.status == "active"
        assert result.generation_cost >= 0
        _mock_generator.generate_agent_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_with_name(self):
        """Test agent creation with provided name."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Custom Name"
        mock_agent.description = "Test"
        mock_agent.code = "def agent(): pass"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()
        mock_agent.created_by = None
        mock_agent.config = None

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        request = AgentCreateRequest(
            description="Test agent description",
            name="Custom Name",
        )

        with patch("src.api.routes.agents.Agent", return_value=mock_agent):
            result = await create_agent(request, mock_session)

        # Name should be the custom one, not auto-generated
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_validation_failure(self):
        """Test agent creation when validation fails."""
        _mock_ralph.ralph_wiggum_loop.return_value = {
            "passed": False,
            "code": "def broken(): pass",
            "iterations": 5,
            "errors": ["Syntax error"],
            "warnings": [],
        }

        mock_session = AsyncMock()

        request = AgentCreateRequest(
            description="Test agent that will fail validation"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_agent(request, mock_session)

        assert exc_info.value.status_code == 422

        # Reset mock
        _mock_ralph.ralph_wiggum_loop.return_value = {
            "passed": True,
            "code": "def agent(): pass",
            "iterations": 1,
            "errors": [],
            "warnings": [],
            "tokens_used": 50,
        }


class TestListAgents:
    """Tests for list_agents endpoint."""

    @pytest.mark.asyncio
    async def test_list_agents_empty(self):
        """Test listing agents when none exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await list_agents(session=mock_session)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_agents_with_results(self):
        """Test listing agents with results."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test Agent"
        mock_agent.description = "Test"
        mock_agent.code = "def run(): pass"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()
        mock_agent.created_by = None
        mock_agent.config = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_agent]
        mock_session.execute.return_value = mock_result

        result = await list_agents(session=mock_session)

        assert len(result) == 1
        assert result[0].id == 1

    @pytest.mark.asyncio
    async def test_list_agents_with_status_filter(self):
        """Test listing agents with status filter."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await list_agents(status="active", session=mock_session)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_agents_with_pagination(self):
        """Test listing agents with pagination."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await list_agents(limit=10, offset=5, session=mock_session)

        mock_session.execute.assert_called_once()


class TestGetAgent:
    """Tests for get_agent endpoint."""

    @pytest.mark.asyncio
    async def test_get_agent_success(self):
        """Test getting an existing agent."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test Agent"
        mock_agent.description = "Test"
        mock_agent.code = "def run(): pass"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()
        mock_agent.created_by = None
        mock_agent.config = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_result

        result = await get_agent(agent_id=1, session=mock_session)

        assert result.id == 1
        assert result.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self):
        """Test getting a non-existent agent."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_agent(agent_id=999, session=mock_session)

        assert exc_info.value.status_code == 404


class TestUpdateAgent:
    """Tests for update_agent endpoint."""

    @pytest.mark.asyncio
    async def test_update_agent_success(self):
        """Test updating an existing agent."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test Agent"
        mock_agent.description = "Test"
        mock_agent.code = "def run(): pass"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()
        mock_agent.created_by = None
        mock_agent.config = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        request = AgentUpdateRequest(name="Updated Name")
        result = await update_agent(agent_id=1, request=request, session=mock_session)

        assert mock_agent.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_agent_not_found(self):
        """Test updating a non-existent agent."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        request = AgentUpdateRequest(name="New Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_agent(agent_id=999, request=request, session=mock_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_agent_status(self):
        """Test updating agent status."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "Test"
        mock_agent.description = "Test"
        mock_agent.code = "def run(): pass"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()
        mock_agent.created_by = None
        mock_agent.config = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        request = AgentUpdateRequest(status="paused")
        await update_agent(agent_id=1, request=request, session=mock_session)

        assert mock_agent.status == "paused"


class TestDeleteAgent:
    """Tests for delete_agent endpoint."""

    @pytest.mark.asyncio
    async def test_delete_agent_success(self):
        """Test deleting an existing agent."""
        mock_agent = MagicMock()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_result
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        await delete_agent(agent_id=1, session=mock_session)

        mock_session.delete.assert_called_once_with(mock_agent)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self):
        """Test deleting a non-existent agent."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_agent(agent_id=999, session=mock_session)

        assert exc_info.value.status_code == 404


class TestExecuteAgent:
    """Tests for execute_agent endpoint."""

    @pytest.mark.asyncio
    async def test_execute_agent_not_implemented(self):
        """Test that execute returns 501 Not Implemented."""
        request = AgentExecuteRequest(config={"key": "value"})

        with pytest.raises(HTTPException) as exc_info:
            await execute_agent(agent_id=1, request=request)

        assert exc_info.value.status_code == 501
        assert "not yet implemented" in str(exc_info.value.detail).lower()
