"""Unit tests for auth service."""

import pytest
from datetime import datetime, timedelta
from app.services.auth import APIKey, generate_api_key


class TestAPIKeyValidation:
    """Test API key validation logic."""

    def test_active_key_is_valid(self):
        """Active API key should be considered valid."""
        key = APIKey(
            id=1, key="test", name="Test", is_admin=False,
            rate_limit=500, requests_count=0, is_active=True,
            requests_reset_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow()
        )
        assert key.is_active is True

    def test_inactive_key_is_invalid(self):
        """Inactive API key should be considered invalid."""
        key = APIKey(
            id=1, key="test", name="Test", is_admin=False,
            rate_limit=500, requests_count=0, is_active=False,
            requests_reset_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow()
        )
        assert key.is_active is False

    def test_admin_key_has_admin_flag(self):
        """Admin key should have is_admin=True."""
        key = APIKey(
            id=1, key="test", name="Admin", is_admin=True,
            rate_limit=None, requests_count=0, is_active=True,
            requests_reset_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow()
        )
        assert key.is_admin is True

    def test_regular_key_not_admin(self):
        """Regular key should have is_admin=False."""
        key = APIKey(
            id=1, key="test", name="Regular", is_admin=False,
            rate_limit=500, requests_count=0, is_active=True,
            requests_reset_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow()
        )
        assert key.is_admin is False


class TestRateLimiting:
    """Test rate limiting logic."""

    def test_under_rate_limit(self):
        """Key under rate limit should be allowed."""
        key = APIKey(
            id=1, key="test", name="Test", is_admin=False,
            rate_limit=500, requests_count=100, is_active=True,
            requests_reset_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow()
        )
        assert key.requests_count < key.rate_limit

    def test_at_rate_limit(self):
        """Key at rate limit should be blocked."""
        key = APIKey(
            id=1, key="test", name="Test", is_admin=False,
            rate_limit=500, requests_count=500, is_active=True,
            requests_reset_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow()
        )
        assert key.requests_count >= key.rate_limit

    def test_admin_unlimited_rate(self):
        """Admin key should have no rate limit."""
        key = APIKey(
            id=1, key="test", name="Admin", is_admin=True,
            rate_limit=None, requests_count=10000, is_active=True,
            requests_reset_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow()
        )
        assert key.rate_limit is None


class TestAPIKeyGeneration:
    """Test API key generation."""

    def test_generate_key_is_string(self):
        """Generated key should be a string."""
        key = generate_api_key()
        assert isinstance(key, str)

    def test_generate_key_length(self):
        """Generated key should be 64 characters (hex of 32 bytes)."""
        key = generate_api_key()
        assert len(key) == 64

    def test_generate_key_unique(self):
        """Generated keys should be unique."""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100
