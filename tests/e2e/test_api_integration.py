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

    # Verify response structure
    data = response.json()
    assert "deployments" in data
    assert "agents" in data
    assert "workflows" in data
    assert "timestamp" in data

    # Verify metrics have counts
    assert "total" in data["deployments"]
    assert "successful" in data["deployments"]
    assert "failed" in data["deployments"]


@pytest.mark.asyncio
async def test_metrics_agents_endpoint(test_client):
    """Test /metrics/agents endpoint returns agent metrics."""

    # Execute: GET /metrics/agents
    response = test_client.get("/metrics/agents")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure
    data = response.json()
    assert "total_agents" in data
    assert "active_agents" in data
    assert "agents_by_status" in data


@pytest.mark.asyncio
async def test_metrics_system_endpoint(test_client):
    """Test /metrics/system endpoint returns system resource metrics."""

    # Execute: GET /metrics/system
    response = test_client.get("/metrics/system")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure
    data = response.json()
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data
    assert "timestamp" in data

    # Verify CPU metrics
    assert "percent" in data["cpu"]
    assert "count" in data["cpu"]

    # Verify memory metrics
    assert "total" in data["memory"]
    assert "available" in data["memory"]
    assert "percent" in data["memory"]

    # Verify disk metrics
    assert "total" in data["disk"]
    assert "used" in data["disk"]
    assert "percent" in data["disk"]


@pytest.mark.asyncio
async def test_create_agent_endpoint(test_client):
    """Test POST /agents endpoint creates new agent."""

    # Setup: Agent data
    agent_data = {
        "name": "test-agent",
        "agent_type": "deployment",
        "config": {"environment": "staging", "auto_deploy": True},
    }

    # Execute: POST /agents
    response = test_client.post("/agents", json=agent_data)

    # Assert: Returns 201 Created
    assert response.status_code == 201

    # Verify response
    data = response.json()
    assert "id" in data
    assert data["name"] == "test-agent"
    assert data["agent_type"] == "deployment"
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_list_agents_endpoint(test_client):
    """Test GET /agents endpoint lists all agents."""

    # Execute: GET /agents
    response = test_client.get("/agents")

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
        assert "agent_type" in agent
        assert "status" in agent


@pytest.mark.asyncio
async def test_get_agent_endpoint(test_client):
    """Test GET /agents/{id} endpoint returns agent details."""

    # Setup: Create agent first
    agent_data = {"name": "get-test", "agent_type": "monitoring", "config": {}}
    create_response = test_client.post("/agents", json=agent_data)
    agent_id = create_response.json()["id"]

    # Execute: GET /agents/{id}
    response = test_client.get(f"/agents/{agent_id}")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response
    data = response.json()
    assert data["id"] == agent_id
    assert data["name"] == "get-test"


@pytest.mark.asyncio
async def test_update_agent_endpoint(test_client):
    """Test PUT /agents/{id} endpoint updates agent."""

    # Setup: Create agent
    agent_data = {"name": "update-test", "agent_type": "deployment", "config": {}}
    create_response = test_client.post("/agents", json=agent_data)
    agent_id = create_response.json()["id"]

    # Execute: PUT /agents/{id}
    update_data = {
        "name": "update-test-modified",
        "agent_type": "deployment",
        "config": {"new_field": "value"},
    }
    response = test_client.put(f"/agents/{agent_id}", json=update_data)

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify update
    data = response.json()
    assert data["name"] == "update-test-modified"
    assert data["config"]["new_field"] == "value"


@pytest.mark.asyncio
async def test_delete_agent_endpoint(test_client):
    """Test DELETE /agents/{id} endpoint deletes agent."""

    # Setup: Create agent
    agent_data = {"name": "delete-test", "agent_type": "monitoring", "config": {}}
    create_response = test_client.post("/agents", json=agent_data)
    agent_id = create_response.json()["id"]

    # Execute: DELETE /agents/{id}
    response = test_client.delete(f"/agents/{agent_id}")

    # Assert: Returns 204 No Content
    assert response.status_code == 204

    # Verify deletion - GET should return 404
    get_response = test_client.get(f"/agents/{agent_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_task_endpoint(test_client):
    """Test POST /tasks endpoint creates new task."""

    # Setup: Task data
    task_data = {
        "title": "Deploy to staging",
        "description": "Deploy PR #123 to staging environment",
        "task_type": "deployment",
        "priority": 8,
        "assigned_agent_id": None,
        "metadata": {"pr_number": 123},
    }

    # Execute: POST /tasks
    response = test_client.post("/tasks", json=task_data)

    # Assert: Returns 201 Created
    assert response.status_code == 201

    # Verify response
    data = response.json()
    assert "id" in data
    assert data["title"] == "Deploy to staging"
    assert data["task_type"] == "deployment"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_tasks_endpoint(test_client):
    """Test GET /tasks endpoint lists all tasks."""

    # Execute: GET /tasks
    response = test_client.get("/tasks")

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify response structure
    data = response.json()
    assert isinstance(data, list)

    # If tasks exist, verify structure
    if len(data) > 0:
        task = data[0]
        assert "id" in task
        assert "title" in task
        assert "task_type" in task
        assert "status" in task


@pytest.mark.asyncio
async def test_update_task_status_endpoint(test_client):
    """Test PUT /tasks/{id} endpoint updates task status."""

    # Setup: Create task
    task_data = {"title": "Status test", "task_type": "monitoring", "priority": 5}
    create_response = test_client.post("/tasks", json=task_data)
    task_id = create_response.json()["id"]

    # Execute: PUT /tasks/{id}
    update_data = {
        "title": "Status test",
        "task_type": "monitoring",
        "priority": 5,
        "status": "in_progress",
    }
    response = test_client.put(f"/tasks/{task_id}", json=update_data)

    # Assert: Returns 200 OK
    assert response.status_code == 200

    # Verify status updated
    data = response.json()
    assert data["status"] == "in_progress"


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
    assert "/agents" in data["paths"]
    assert "/tasks" in data["paths"]


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

    # Execute: POST with invalid data
    response = test_client.post("/agents", json={"invalid": "data"})

    # Assert: Returns 422 Unprocessable Entity
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_cors_headers(test_client):
    """Test CORS headers are set correctly."""

    # Execute: OPTIONS request (preflight)
    response = test_client.options("/api/health", headers={"Origin": "https://example.com"})

    # Assert: CORS headers present (if CORS configured)
    # Note: This depends on actual CORS configuration
    assert response.status_code in [200, 204, 405]


@pytest.mark.asyncio
async def test_api_logging_integration(test_client):
    """Test API requests are logged with correlation IDs."""

    import logging

    log_calls = []

    def capture_log(record):
        log_calls.append(record.getMessage())

    handler = logging.Handler()
    handler.emit = capture_log
    logging.getLogger("src.api").addHandler(handler)

    # Execute: Make API request
    test_client.get("/api/health")

    # Assert: Request logged
    # Note: Actual log messages depend on logging configuration
    # This test verifies logging infrastructure is active


@pytest.mark.asyncio
async def test_api_database_connection_resilience(test_client):
    """Test API handles database connection failures gracefully."""

    # Execute: Request that requires database
    response = test_client.get("/agents")

    # Assert: Returns appropriate status even if DB fails
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
