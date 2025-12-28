"""Integration tests for admin endpoints."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import APIKey


def make_mock_api_key(is_admin: bool = False, key_id: int = 1) -> APIKey:
    """Create a mock APIKey."""
    now = datetime.utcnow()
    return APIKey(
        id=key_id,
        key="test-key-abc123",
        name="Test Key" if not is_admin else "Admin Key",
        is_admin=is_admin,
        rate_limit=None if is_admin else 500,
        requests_count=0,
        requests_reset_at=now + timedelta(hours=1),
        is_active=True,
        created_at=now,
    )


class TestAdminEndpoints:
    """Test admin endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_admin_auth(self):
        """Mock auth for admin user."""
        async def mock_validate(key: str):
            return make_mock_api_key(is_admin=True)

        with patch("app.api.dependencies.validate_api_key", mock_validate):
            with patch("app.api.dependencies.check_rate_limit", AsyncMock(return_value=(True, None))):
                yield

    @pytest.fixture
    def mock_regular_auth(self):
        """Mock auth for regular user."""
        async def mock_validate(key: str):
            return make_mock_api_key(is_admin=False)

        with patch("app.api.dependencies.validate_api_key", mock_validate):
            with patch("app.api.dependencies.check_rate_limit", AsyncMock(return_value=(True, 500))):
                yield

    def test_create_api_key_as_admin(self, client, mock_admin_auth):
        """Admin should be able to create API keys."""
        new_key = make_mock_api_key(is_admin=False, key_id=3)

        with patch("app.services.auth.create_api_key", AsyncMock(return_value=new_key)):
            response = client.post(
                "/api/v1/admin/keys",
                headers={"X-API-Key": "admin-key"},
                json={"name": "New Key"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Key"
        assert "key" in data

    def test_create_api_key_as_regular_returns_403(self, client, mock_regular_auth):
        """Regular user should not be able to create API keys."""
        response = client.post(
            "/api/v1/admin/keys",
            headers={"X-API-Key": "regular-key"},
            json={"name": "New Key"},
        )
        assert response.status_code == 403

    def test_list_api_keys_as_admin(self, client, mock_admin_auth):
        """Admin should be able to list API keys."""
        keys = [make_mock_api_key(key_id=1), make_mock_api_key(key_id=2)]

        with patch("app.services.auth.list_api_keys", AsyncMock(return_value=keys)):
            response = client.get(
                "/api/v1/admin/keys",
                headers={"X-API-Key": "admin-key"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert len(data["keys"]) == 2

    def test_list_api_keys_as_regular_returns_403(self, client, mock_regular_auth):
        """Regular user should not be able to list API keys."""
        response = client.get(
            "/api/v1/admin/keys",
            headers={"X-API-Key": "regular-key"},
        )
        assert response.status_code == 403

    def test_revoke_api_key_as_admin(self, client, mock_admin_auth):
        """Admin should be able to revoke API keys."""
        with patch("app.services.auth.revoke_api_key", AsyncMock(return_value=True)):
            response = client.delete(
                "/api/v1/admin/keys/5",
                headers={"X-API-Key": "admin-key"},
            )

        assert response.status_code == 200
        assert "revoked" in response.json()["message"].lower()

    def test_revoke_nonexistent_key_returns_404(self, client, mock_admin_auth):
        """Revoking nonexistent key should return 404."""
        with patch("app.services.auth.revoke_api_key", AsyncMock(return_value=False)):
            response = client.delete(
                "/api/v1/admin/keys/999",
                headers={"X-API-Key": "admin-key"},
            )

        assert response.status_code == 404

    def test_revoke_api_key_as_regular_returns_403(self, client, mock_regular_auth):
        """Regular user should not be able to revoke API keys."""
        response = client.delete(
            "/api/v1/admin/keys/5",
            headers={"X-API-Key": "regular-key"},
        )
        assert response.status_code == 403

    def test_create_admin_key_as_admin(self, client, mock_admin_auth):
        """Admin should be able to create admin keys."""
        new_admin = make_mock_api_key(is_admin=True, key_id=4)

        with patch("app.services.auth.create_api_key", AsyncMock(return_value=new_admin)):
            response = client.post(
                "/api/v1/admin/keys",
                headers={"X-API-Key": "admin-key"},
                json={"name": "New Admin", "isAdmin": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["isAdmin"] is True
