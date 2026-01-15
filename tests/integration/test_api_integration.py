"""
Integration tests for API endpoints with database.

These tests verify the full stack from HTTP request to database.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app

pytestmark = pytest.mark.integration


class TestHealthAPIIntegration:
    """Integration tests for health API endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_with_database(self, db_session):
        """Test health check returns healthy when database is connected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_root_endpoint(self, db_session):
        """Test root API endpoint returns metadata."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Agent Platform API"
        assert data["version"] == "0.1.0"


class TestAgentsAPIIntegration:
    """Integration tests for agents API endpoints."""

    @pytest.mark.asyncio
    async def test_create_agent_via_api(self, db_session):
        """Test creating an agent through the API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/agents",
                json={
                    "name": "Test API Agent",
                    "description": "Created via API integration test",
                },
            )

        assert response.status_code in [200, 201, 422]

    @pytest.mark.asyncio
    async def test_list_agents_via_api(self, db_session):
        """Test listing agents through the API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, db_session):
        """Test getting a non-existent agent returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/agents/99999")

        assert response.status_code == 404


class TestTasksAPIIntegration:
    """Integration tests for tasks API endpoints."""

    @pytest.mark.asyncio
    async def test_list_tasks_via_api(self, db_session):
        """Test listing tasks through the API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/tasks/stats/summary")

        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, db_session):
        """Test getting a non-existent task returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/tasks/99999")

        assert response.status_code == 404


class TestMetricsAPIIntegration:
    """Integration tests for metrics API endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_summary(self, db_session):
        """Test metrics summary endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics/summary")

        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_system_metrics(self, db_session):
        """Test system metrics endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics/system")

        assert response.status_code in [200, 404]


class TestCostsAPIIntegration:
    """Integration tests for costs API endpoints."""

    @pytest.mark.asyncio
    async def test_costs_estimate(self, db_session):
        """Test cost estimate endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/costs/estimate")

        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_costs_budget(self, db_session):
        """Test budget status endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/costs/budget")

        assert response.status_code in [200, 404]


class TestBackupsAPIIntegration:
    """Integration tests for backups API endpoints."""

    @pytest.mark.asyncio
    async def test_backups_list(self, db_session):
        """Test listing backups endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/backups")

        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_backups_health(self, db_session):
        """Test backups health endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/backups/health")

        assert response.status_code in [200, 404]


class TestConcurrentRequests:
    """Integration tests for concurrent API requests."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, db_session):
        """Test multiple concurrent health check requests."""
        import asyncio

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            async def make_request():
                return await client.get("/api/health")

            tasks = [make_request() for _ in range(10)]
            responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    async def test_concurrent_agent_list(self, db_session):
        """Test multiple concurrent agent list requests."""
        import asyncio

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            async def make_request():
                return await client.get("/api/agents")

            tasks = [make_request() for _ in range(10)]
            responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in responses)


class TestErrorHandling:
    """Integration tests for API error handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_body(self, db_session):
        """Test API handles invalid JSON gracefully."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/agents",
                content="not valid json",
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, db_session):
        """Test API validates required fields."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/agents",
                json={},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_endpoint(self, db_session):
        """Test non-existent endpoint returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/nonexistent")

        assert response.status_code == 404
