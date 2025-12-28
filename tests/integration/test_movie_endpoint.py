"""Integration tests for movie endpoint."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.cache import CachedMovie
from app.services.auth import APIKey
from app.models.schemas import RTMovieData


# Mock data
MOCK_RT_DATA = RTMovieData(
    rt_slug="m/the_dark_knight",
    title="The Dark Knight",
    year=2008,
    critic_score=94,
    audience_score=94,
    critic_rating="certified_fresh",
    audience_rating="upright",
    consensus="Dark, complex, and unforgettable.",
)


def make_mock_cached_movie(imdb_id: str = "tt0468569", cached_at: datetime = None) -> CachedMovie:
    """Create a mock CachedMovie."""
    return CachedMovie(
        imdb_id=imdb_id,
        rt_slug="m/the_dark_knight",
        rt_url="https://www.rottentomatoes.com/m/the_dark_knight",
        title="The Dark Knight",
        year=2008,
        critic_score=94,
        audience_score=94,
        critic_rating="certified_fresh",
        audience_rating="upright",
        consensus="Dark, complex, and unforgettable.",
        cached_at=cached_at or datetime.utcnow(),
    )


def make_mock_api_key(is_admin: bool = False) -> APIKey:
    """Create a mock APIKey."""
    now = datetime.utcnow()
    return APIKey(
        id=1,
        key="test-key",
        name="Test",
        is_admin=is_admin,
        rate_limit=None if is_admin else 500,
        requests_count=0,
        requests_reset_at=now + timedelta(hours=1),
        is_active=True,
        created_at=now,
    )


class TestMovieEndpoint:
    """Test /movie/{imdb_id} endpoint."""

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

    def test_missing_api_key_returns_422(self, client):
        """Request without API key should return 422 (missing header)."""
        response = client.get("/api/v1/movie/tt0468569")
        assert response.status_code == 422

    def test_invalid_api_key_returns_401(self, client):
        """Invalid API key should return 401."""
        async def mock_validate(key: str):
            return None

        with patch("app.api.dependencies.validate_api_key", mock_validate):
            with patch("app.api.dependencies.check_rate_limit", AsyncMock(return_value=(True, 500))):
                response = client.get(
                    "/api/v1/movie/tt0468569",
                    headers={"X-API-Key": "invalid-key"},
                )
        assert response.status_code == 401

    def test_invalid_imdb_format_returns_400(self, client, mock_auth):
        """Invalid IMDB ID format should return 400."""
        response = client.get(
            "/api/v1/movie/invalid",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400
        assert "Invalid IMDB ID" in response.json()["detail"]

    def test_imdb_without_tt_prefix_returns_400(self, client, mock_auth):
        """IMDB ID without tt prefix should return 400."""
        response = client.get(
            "/api/v1/movie/0468569",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400

    def test_cache_hit_returns_cached_data(self, client, mock_auth):
        """Cache hit should return cached movie data."""
        cached = make_mock_cached_movie()

        with patch("app.services.cache.get_cached", AsyncMock(return_value=cached)):
            with patch("app.services.cache.is_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/movie/tt0468569",
                    headers={"X-API-Key": "test-key"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Dark Knight"
        assert data["criticScore"] == 94

    def test_cache_miss_fetches_from_rt(self, client, mock_auth):
        """Cache miss should fetch from Wikidata and RT."""
        cached = make_mock_cached_movie()

        with patch("app.services.cache.get_cached", AsyncMock(return_value=None)):
            with patch("app.services.wikidata.get_rt_slug", AsyncMock(return_value="m/the_dark_knight")):
                with patch("app.services.scraper.scrape_movie", AsyncMock(return_value=MOCK_RT_DATA)):
                    with patch("app.services.cache.upsert_cache", AsyncMock(return_value=cached)):
                        response = client.get(
                            "/api/v1/movie/tt0468569",
                            headers={"X-API-Key": "test-key"},
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Dark Knight"

    def test_not_found_in_wikidata_returns_404(self, client, mock_auth):
        """Movie not in Wikidata should return 404."""
        with patch("app.services.cache.get_cached", AsyncMock(return_value=None)):
            with patch("app.services.wikidata.get_rt_slug", AsyncMock(return_value=None)):
                response = client.get(
                    "/api/v1/movie/tt9999999",
                    headers={"X-API-Key": "test-key"},
                )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_scrape_failure_with_stale_cache_returns_stale(self, client, mock_auth):
        """Scrape failure with stale cache should return stale data."""
        stale_cached = make_mock_cached_movie(
            cached_at=datetime.utcnow() - timedelta(days=10)
        )

        with patch("app.services.cache.get_cached", AsyncMock(return_value=stale_cached)):
            with patch("app.services.cache.is_cache_fresh", return_value=False):
                with patch("app.services.wikidata.get_rt_slug", AsyncMock(return_value="m/the_dark_knight")):
                    with patch("app.services.scraper.scrape_movie", AsyncMock(return_value=None)):
                        response = client.get(
                            "/api/v1/movie/tt0468569",
                            headers={"X-API-Key": "test-key"},
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Dark Knight"

    def test_scrape_failure_no_cache_returns_502(self, client, mock_auth):
        """Scrape failure without cache should return 502."""
        with patch("app.services.cache.get_cached", AsyncMock(return_value=None)):
            with patch("app.services.wikidata.get_rt_slug", AsyncMock(return_value="m/the_dark_knight")):
                with patch("app.services.scraper.scrape_movie", AsyncMock(return_value=None)):
                    response = client.get(
                        "/api/v1/movie/tt0468569",
                        headers={"X-API-Key": "test-key"},
                    )

        assert response.status_code == 502

    def test_response_contains_required_fields(self, client, mock_auth):
        """Response should contain all required fields."""
        cached = make_mock_cached_movie()

        with patch("app.services.cache.get_cached", AsyncMock(return_value=cached)):
            with patch("app.services.cache.is_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/movie/tt0468569",
                    headers={"X-API-Key": "test-key"},
                )

        data = response.json()
        assert "imdbId" in data
        assert "rtUrl" in data
        assert "title" in data
        assert "year" in data
        assert "criticScore" in data
        assert "audienceScore" in data
