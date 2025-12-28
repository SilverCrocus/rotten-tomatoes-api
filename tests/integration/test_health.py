"""Integration tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestHealthEndpoint:
    """Test /health endpoint."""

    @pytest.fixture
    def client(self):
        """Test client without auth mocking."""
        return TestClient(app)

    def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_no_auth_required(self, client):
        """Health endpoint should not require API key."""
        response = client.get("/api/v1/health")
        # No X-API-Key header, should still work
        assert response.status_code == 200

    def test_health_returns_version(self, client):
        """Health endpoint should return version."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_json_content_type(self, client):
        """Health endpoint should return JSON."""
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers["content-type"]
