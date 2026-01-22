"""Tests for cost monitoring API routes.

Tests the /costs/* endpoints defined in src/api/routes/costs.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Import the router to test
from src.api.routes.costs import (
    BudgetStatusResponse,
    CostEstimateResponse,
    CostRecommendation,
    CostReportResponse,
    get_mock_budget_status,
    get_mock_estimate,
    get_mock_recommendations,
    router,
)


# Create a test app with just the costs router
def create_test_app():
    """Create a FastAPI app with the costs router for testing."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_test_app()
    return TestClient(app)


class TestCostEstimateEndpoint:
    """Tests for GET /costs/estimate endpoint."""

    def test_estimate_returns_mock_without_railway(self, client):
        """Test that mock data is returned when Railway is not configured."""
        # No RAILWAY_API_TOKEN set
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/estimate")

        assert response.status_code == 200
        data = response.json()

        # Verify mock data structure
        assert "period_start" in data
        assert "period_end" in data
        assert "usage" in data
        assert "costs" in data
        assert "currency" in data
        assert data["currency"] == "USD"

        # Verify usage fields
        assert "vcpu_minutes" in data["usage"]
        assert "memory_gb_minutes" in data["usage"]
        assert "egress_gb" in data["usage"]

        # Verify costs fields
        assert "total" in data["costs"]

    def test_estimate_with_railway_no_deployment_id(self, client):
        """Test error when Railway is configured but no deployment ID."""
        with patch.dict("os.environ", {"RAILWAY_API_TOKEN": "test-token"}, clear=True):
            with patch("src.api.routes.costs.get_cost_monitor") as mock_monitor:
                mock_monitor.return_value = MagicMock()

                response = client.get("/costs/estimate")

        assert response.status_code == 400
        assert "deployment_id required" in response.json()["detail"]

    def test_estimate_with_deployment_id_param(self, client):
        """Test with deployment_id query parameter."""
        mock_cost_data = {
            "period_start": "2026-01-01T00:00:00Z",
            "period_end": "2026-01-22T00:00:00Z",
            "usage": {"vcpu_minutes": 1000, "memory_gb_minutes": 500, "egress_gb": 0.5},
            "costs": {"vcpu": 0.5, "memory": 0.25, "egress": 0.05, "base": 5.0, "total": 5.8},
            "currency": "USD",
        }

        with patch.dict("os.environ", {"RAILWAY_API_TOKEN": "test-token"}, clear=True):
            with patch("src.api.routes.costs.get_cost_monitor") as mock_get_monitor:
                mock_monitor = AsyncMock()
                mock_estimate = MagicMock()
                mock_estimate.to_dict.return_value = mock_cost_data
                mock_monitor.get_current_month_cost = AsyncMock(return_value=mock_estimate)
                mock_get_monitor.return_value = mock_monitor

                response = client.get("/costs/estimate?deployment_id=test-dep-123")

        assert response.status_code == 200
        data = response.json()
        assert data["costs"]["total"] == 5.8


class TestBudgetEndpoint:
    """Tests for GET /costs/budget endpoint."""

    def test_budget_returns_mock_without_railway(self, client):
        """Test mock budget status when Railway not configured."""
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/budget?budget=100")

        assert response.status_code == 200
        data = response.json()

        assert "budget" in data
        assert "projected_cost" in data
        assert "exceeded" in data
        assert "percentage_used" in data
        assert "status" in data

        assert data["budget"] == 100.0

    def test_budget_default_value(self, client):
        """Test default budget of $50."""
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/budget")

        assert response.status_code == 200
        data = response.json()
        assert data["budget"] == 50.0

    def test_budget_status_ok(self, client):
        """Test budget status is 'ok' when under 80%."""
        with patch.dict("os.environ", {}, clear=True):
            # Mock returns projected ~6.89, budget 100 = 6.89%
            response = client.get("/costs/budget?budget=100")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["exceeded"] is False

    def test_budget_validation_minimum(self, client):
        """Test budget must be at least $1."""
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/budget?budget=0.5")

        assert response.status_code == 422  # Validation error


class TestRecommendationsEndpoint:
    """Tests for GET /costs/recommendations endpoint."""

    def test_recommendations_returns_mock(self, client):
        """Test mock recommendations when Railway not configured."""
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/recommendations")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) > 0

        # Check recommendation structure
        rec = data[0]
        assert "priority" in rec
        assert "category" in rec
        assert "title" in rec
        assert "description" in rec
        assert "potential_savings" in rec


class TestCostReportEndpoint:
    """Tests for GET /costs/report endpoint."""

    def test_report_returns_mock(self, client):
        """Test mock report when Railway not configured."""
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/report")

        assert response.status_code == 200
        data = response.json()

        # Verify full report structure
        assert "generated_at" in data
        assert "pricing_plan" in data
        assert "estimate" in data
        assert "budget_status" in data
        assert "recommendations" in data
        assert "trends" in data

        assert data["pricing_plan"] == "Hobby"

    def test_report_with_custom_budget(self, client):
        """Test report with custom budget."""
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/report?budget=200")

        assert response.status_code == 200
        data = response.json()
        assert data["budget_status"]["budget"] == 200.0


class TestCostsHealthEndpoint:
    """Tests for GET /costs/health endpoint."""

    def test_health_without_railway(self, client):
        """Test health check when Railway not configured."""
        with patch.dict("os.environ", {}, clear=True):
            response = client.get("/costs/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "cost-monitoring-api"
        assert data["railway_configured"] is False
        assert "timestamp" in data

    def test_health_with_railway(self, client):
        """Test health check when Railway is configured."""
        with patch.dict("os.environ", {"RAILWAY_API_TOKEN": "test-token"}, clear=True):
            response = client.get("/costs/health")

        assert response.status_code == 200
        data = response.json()
        assert data["railway_configured"] is True


class TestMockHelpers:
    """Tests for mock helper functions."""

    def test_get_mock_estimate(self):
        """Test mock estimate generator."""
        estimate = get_mock_estimate()

        assert isinstance(estimate, CostEstimateResponse)
        assert estimate.currency == "USD"
        assert estimate.costs["total"] > 0

    def test_get_mock_budget_status_default(self):
        """Test mock budget with default value."""
        status = get_mock_budget_status()

        assert isinstance(status, BudgetStatusResponse)
        assert status.budget == 50.0

    def test_get_mock_budget_status_custom(self):
        """Test mock budget with custom value."""
        status = get_mock_budget_status(budget=200.0)

        assert status.budget == 200.0
        # With projected ~6.89, 200 budget = ~3.4%
        assert status.percentage_used < 10

    def test_get_mock_recommendations(self):
        """Test mock recommendations generator."""
        recs = get_mock_recommendations()

        assert isinstance(recs, list)
        assert len(recs) > 0
        assert all(isinstance(r, CostRecommendation) for r in recs)


class TestPydanticModels:
    """Tests for Pydantic response models."""

    def test_cost_estimate_response(self):
        """Test CostEstimateResponse model."""
        data = CostEstimateResponse(
            period_start="2026-01-01T00:00:00Z",
            period_end="2026-01-22T00:00:00Z",
            usage={"vcpu_minutes": 100, "memory_gb_minutes": 50, "egress_gb": 0.1},
            costs={"total": 5.0},
        )

        assert data.currency == "USD"
        assert data.costs["total"] == 5.0

    def test_budget_status_response(self):
        """Test BudgetStatusResponse model."""
        data = BudgetStatusResponse(
            budget=50.0,
            projected_cost=40.0,
            exceeded=False,
            percentage_used=80.0,
            status="warning",
        )

        assert data.budget == 50.0
        assert data.status == "warning"

    def test_cost_recommendation_model(self):
        """Test CostRecommendation model."""
        rec = CostRecommendation(
            priority="high",
            category="cpu",
            title="Reduce CPU allocation",
            description="CPU is underutilized",
            potential_savings="20%",
        )

        assert rec.priority == "high"
        assert "20%" in rec.potential_savings
