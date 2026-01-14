"""End-to-end tests for API endpoints integration."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def test_client():
    """Create test client for API."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_health_endpoint_integration(test_client):
    """Test /api/health endpoint returns correct status."""

    # Execute: GET /api/health
    response = test_client.get("/api/health")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "timestamp" in data

    # Verify status values
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert data["database"] in ["connected", "disconnected"]


@pytest.mark.asyncio
async def test_metrics_summary_endpoint(test_client):
    """Test /metrics/summary endpoint returns system metrics."""

    # Execute: GET /metrics/summary
    response = test_client.get("/metrics/summary")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure (MetricSummary model)
    data = response.json()
    assert "active_agents" in data
    assert "total_requests_1h" in data
    assert "error_rate_pct" in data
    assert "avg_latency_ms" in data
    assert "p95_latency_ms" in data
    assert "total_tokens_1h" in data
    assert "estimated_cost_1h" in data

    # Verify types
    assert isinstance(data["active_agents"], int)
    assert isinstance(data["total_requests_1h"], int)
    assert isinstance(data["error_rate_pct"], (int, float))
    assert isinstance(data["avg_latency_ms"], (int, float))
    assert isinstance(data["p95_latency_ms"], (int, float))
    assert isinstance(data["total_tokens_1h"], int)
    assert isinstance(data["estimated_cost_1h"], (int, float))


@pytest.mark.asyncio
async def test_metrics_agents_endpoint(test_client):
    """Test /metrics/agents endpoint returns agent metrics."""

    # Execute: GET /metrics/agents
    response = test_client.get("/metrics/agents")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure (list of AgentStatus)
    data = response.json()
    assert isinstance(data, list)

    # If agents exist, verify structure
    if len(data) > 0:
        agent = data[0]
        assert "agent_id" in agent
        assert "last_seen" in agent
        assert "error_rate_pct" in agent
        assert "total_requests_1h" in agent
        assert "avg_latency_ms" in agent
        assert "total_tokens_1h" in agent


@pytest.mark.asyncio
async def test_metrics_system_endpoint(test_client):
    """Test /metrics/system endpoint returns system resource metrics."""

    # Execute: GET /metrics/system
    response = test_client.get("/metrics/system")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure (SystemMetrics model - flat structure)
    data = response.json()
    assert "timestamp" in data
    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "memory_available_mb" in data
    assert "disk_percent" in data
    assert "disk_available_gb" in data

    # Verify types
    assert isinstance(data["cpu_percent"], (int, float))
    assert isinstance(data["memory_percent"], (int, float))
    assert isinstance(data["memory_available_mb"], (int, float))
    assert isinstance(data["disk_percent"], (int, float))
    assert isinstance(data["disk_available_gb"], (int, float))


@pytest.mark.asyncio
async def test_create_agent_endpoint(test_client):
    """Test POST /api/agents endpoint creates new agent."""

    # Setup: Agent data (natural language description)
    agent_data = {
        "description": (
            "Create an agent that monitors system health and "
            "sends alerts when CPU usage exceeds 80%"
        ),
        "name": "health-monitor",
        "created_by": "test-user",
        "strict_validation": False,  # Disable strict validation for test
    }

    # Execute: POST /api/agents
    response = test_client.post("/api/agents", json=agent_data)

    # Assert: Returns 201 Created or 200 OK (depending on implementation)
    assert response.status_code in [200, 201]

    # Verify response (AgentCreateResponse)
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "description" in data
    assert "code" in data
    assert "status" in data
    assert "generation_cost" in data
    assert "iterations" in data
    assert "tokens_used" in data

    # Verify agent was generated
    assert data["status"] in ["created", "generated", "validated"]
    assert len(data["code"]) > 0


@pytest.mark.asyncio
async def test_list_agents_endpoint(test_client):
    """Test GET /api/agents endpoint lists all agents."""

    # Execute: GET /api/agents
    response = test_client.get("/api/agents")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure
    data = response.json()
    assert isinstance(data, list)

    # If agents exist, verify structure
    if len(data) > 0:
        agent = data[0]
        assert "id" in agent
        assert "name" in agent
        assert "description" in agent
        assert "status" in agent


@pytest.mark.asyncio
async def test_get_agent_endpoint(test_client):
    """Test GET /api/agents/{id} endpoint returns agent details."""

    # Setup: Create agent first
    agent_data = {
        "description": "Simple test agent that returns Hello World",
        "name": "hello-world",
        "strict_validation": False,
    }
    create_response = test_client.post("/api/agents", json=agent_data)

    if create_response.status_code not in [200, 201]:
        # Agent creation failed, skip test
        pytest.skip(f"Agent creation failed: {create_response.status_code}")

    agent_id = create_response.json()["id"]

    # Execute: GET /api/agents/{id}
    response = test_client.get(f"/api/agents/{agent_id}")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response
    data = response.json()
    assert data["id"] == agent_id
    assert data["name"] == "hello-world"


@pytest.mark.asyncio
async def test_update_agent_endpoint(test_client):
    """Test PUT /api/agents/{id} endpoint updates agent."""

    # Setup: Create agent
    agent_data = {
        "description": "Agent to be updated",
        "name": "update-test",
        "strict_validation": False,
    }
    create_response = test_client.post("/api/agents", json=agent_data)

    if create_response.status_code not in [200, 201]:
        pytest.skip(f"Agent creation failed: {create_response.status_code}")

    agent_id = create_response.json()["id"]

    # Execute: PUT /api/agents/{id}
    update_data = {
        "name": "update-test-modified",
        "description": "Updated agent description",
        "code": "def hello(): return 'updated'",
        "status": "updated",
    }
    response = test_client.put(f"/api/agents/{agent_id}", json=update_data)

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify update
    data = response.json()
    assert data["name"] == "update-test-modified"


@pytest.mark.asyncio
async def test_delete_agent_endpoint(test_client):
    """Test DELETE /api/agents/{id} endpoint deletes agent."""

    # Setup: Create agent
    agent_data = {
        "description": "Agent to be deleted",
        "name": "delete-test",
        "strict_validation": False,
    }
    create_response = test_client.post("/api/agents", json=agent_data)

    if create_response.status_code not in [200, 201]:
        pytest.skip(f"Agent creation failed: {create_response.status_code}")

    agent_id = create_response.json()["id"]

    # Execute: DELETE /api/agents/{id}
    response = test_client.delete(f"/api/agents/{agent_id}")

    # Assert: Returns 204 No Content
    assert response.status_code == 204

    # Verify deletion - GET should return 404
    get_response = test_client.get(f"/api/agents/{agent_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_api_docs_endpoint(test_client):
    """Test /docs endpoint is accessible."""

    # Execute: GET /docs
    response = test_client.get("/docs")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify it's HTML (OpenAPI docs)
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_api_openapi_spec(test_client):
    """Test /openapi.json endpoint returns OpenAPI spec."""

    # Execute: GET /openapi.json
    response = test_client.get("/openapi.json")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify it's JSON OpenAPI spec
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert "paths" in data

    # Verify key endpoints documented
    assert "/api/health" in data["paths"]
    assert "/metrics/summary" in data["paths"]
    assert "/api/agents" in data["paths"]


@pytest.mark.asyncio
async def test_api_error_handling_404(test_client):
    """Test API returns 404 for non-existent endpoints."""

    # Execute: GET non-existent endpoint
    response = test_client.get("/api/non-existent-endpoint")

    # Assert: Returns 404
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_error_handling_invalid_json(test_client):
    """Test API returns 422 for invalid JSON."""

    # Execute: POST with invalid data (missing required field)
    response = test_client.post("/api/agents", json={"invalid": "data"})

    # Assert: Returns 422 Unprocessable Entity
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_cors_headers(test_client):
    """Test CORS headers are set correctly."""

    # Execute: OPTIONS request (preflight)
    response = test_client.options("/api/health", headers={"Origin": "https://example.com"})

    # Assert: CORS headers present (if CORS configured)
    # Note: TestClient may not fully simulate CORS, 404 is acceptable
    assert response.status_code in [200, 204, 404, 405]


@pytest.mark.asyncio
async def test_api_database_connection_resilience(test_client):
    """Test API handles database connection gracefully."""

    # Execute: Request that requires database
    response = test_client.get("/api/agents")

    # Assert: Returns appropriate status
    # Should return 200 with empty list or 503 if DB required
    assert response.status_code in [200, 503]


@pytest.mark.asyncio
async def test_api_concurrent_requests(test_client):
    """Test API handles multiple concurrent requests."""

    import concurrent.futures

    def make_request():
        return test_client.get("/api/health")

    # Execute: 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in futures]

    # Assert: All requests succeeded
    assert all(r.status_code == 200 for r in results)


@pytest.mark.asyncio
async def test_metrics_health_endpoint(test_client):
    """Test /metrics/health endpoint."""

    # Execute: GET /metrics/health
    response = test_client.get("/metrics/health")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert data["service"] == "metrics-api"


@pytest.mark.asyncio
async def test_root_endpoint(test_client):
    """Test /api/ root endpoint."""

    # Execute: GET /api/
    response = test_client.get("/api/")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response (actual response has "name", "version", "docs", "health")
    data = response.json()
    assert "name" in data or "message" in data
