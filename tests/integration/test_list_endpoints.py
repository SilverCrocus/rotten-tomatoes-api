"""Integration tests for list endpoints."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.list_cache import CachedList
from app.services.auth import APIKey


def make_mock_api_key() -> APIKey:
    """Create a mock APIKey."""
    now = datetime.utcnow()
    return APIKey(
        id=1,
        key="test-key",
        name="Test",
        is_admin=False,
        rate_limit=500,
        requests_count=0,
        requests_reset_at=now + timedelta(hours=1),
        is_active=True,
        created_at=now,
    )


def make_mock_cached_list(
    url: str = "https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/",
    title: str = "Best Horror Movies",
    movies: list = None,
) -> CachedList:
    """Create a mock CachedList."""
    if movies is None:
        movies = [
            {"rtSlug": "m/get_out", "title": "Get Out", "year": 2017},
            {"rtSlug": "m/the_exorcist", "title": "The Exorcist", "year": 1973},
        ]
    return CachedList(
        url_hash="abc123",
        source_url=url,
        title=title,
        movies=movies,
        cached_at=datetime.utcnow(),
    )


class TestListEndpoints:
    """Test list endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_auth(self):
        """Mock auth to accept any key."""
        async def mock_validate(key: str):
            return make_mock_api_key()

        with patch("app.api.dependencies.validate_api_key", mock_validate):
            with patch("app.api.dependencies.check_rate_limit", AsyncMock(return_value=(True, 500))):
                yield

    # --- Curated Lists ---

    def test_get_curated_lists(self, client, mock_auth):
        """Should return list of curated lists."""
        response = client.get(
            "/api/v1/lists/curated",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "lists" in data
        assert len(data["lists"]) > 0

    def test_curated_list_has_required_fields(self, client, mock_auth):
        """Each curated list should have slug, title, description."""
        response = client.get(
            "/api/v1/lists/curated",
            headers={"X-API-Key": "test-key"},
        )
        data = response.json()
        for lst in data["lists"]:
            assert "slug" in lst
            assert "title" in lst
            assert "description" in lst

    def test_get_curated_list_by_slug_cache_hit(self, client, mock_auth):
        """Curated list by slug with cache hit."""
        cached = make_mock_cached_list()

        with patch("app.services.list_cache.get_cached_list", AsyncMock(return_value=cached)):
            with patch("app.services.list_cache.is_list_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/lists/curated/best-horror",
                    headers={"X-API-Key": "test-key"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["movieCount"] == 2
        assert data["movies"][0]["title"] == "Get Out"

    def test_unknown_curated_slug_returns_404(self, client, mock_auth):
        """Unknown curated slug should return 404."""
        response = client.get(
            "/api/v1/lists/curated/not-a-real-list",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 404

    # --- Browse Options ---

    def test_get_browse_options(self, client, mock_auth):
        """Should return browse filter options."""
        response = client.get(
            "/api/v1/lists/browse/options",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "certifications" in data
        assert "genres" in data
        assert "affiliates" in data

    def test_browse_options_contains_values(self, client, mock_auth):
        """Browse options should contain actual values."""
        response = client.get(
            "/api/v1/lists/browse/options",
            headers={"X-API-Key": "test-key"},
        )
        data = response.json()
        assert "certified_fresh" in data["certifications"]
        assert "horror" in data["genres"]
        assert "netflix" in data["affiliates"]

    # --- Browse ---

    def test_browse_with_valid_filters(self, client, mock_auth):
        """Browse with valid filters should work."""
        cached = make_mock_cached_list(
            url="https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh~genres:horror",
            title="Browse Results",
        )

        with patch("app.services.list_cache.get_cached_list", AsyncMock(return_value=cached)):
            with patch("app.services.list_cache.is_list_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/lists/browse?certification=certified_fresh&genre=horror",
                    headers={"X-API-Key": "test-key"},
                )

        assert response.status_code == 200

    def test_browse_invalid_certification_returns_400(self, client, mock_auth):
        """Browse with invalid certification should return 400."""
        response = client.get(
            "/api/v1/lists/browse?certification=invalid",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400

    def test_browse_invalid_genre_returns_400(self, client, mock_auth):
        """Browse with invalid genre should return 400."""
        response = client.get(
            "/api/v1/lists/browse?genre=not_a_genre",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400

    # --- URL-based List ---

    def test_list_by_url_editorial(self, client, mock_auth):
        """Fetch list by editorial URL."""
        cached = make_mock_cached_list(
            url="https://editorial.rottentomatoes.com/guide/best-action-movies/",
            title="Best Action Movies",
        )

        with patch("app.services.list_cache.get_cached_list", AsyncMock(return_value=cached)):
            with patch("app.services.list_cache.is_list_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/list?url=https://editorial.rottentomatoes.com/guide/best-action-movies/",
                    headers={"X-API-Key": "test-key"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["movieCount"] == 2

    def test_list_by_url_unsupported_returns_400(self, client, mock_auth):
        """Unsupported URL format should return 400."""
        response = client.get(
            "/api/v1/list?url=https://www.google.com/",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400
