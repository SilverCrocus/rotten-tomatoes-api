"""Integration tests for batch endpoint."""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.cache import CachedMovie
from app.services.auth import APIKey
from app.models.schemas import RTMovieData


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


def make_mock_cached_movie(imdb_id: str = "tt0468569") -> CachedMovie:
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
        cached_at=datetime.utcnow(),
    )


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


def parse_sse_events(response_text: str) -> list:
    """Parse SSE events from response text."""
    events = []
    current_event = {}

    for line in response_text.split("\n"):
        if line.startswith("event: "):
            current_event["type"] = line[7:]
        elif line.startswith("data: "):
            try:
                current_event["data"] = json.loads(line[6:])
                events.append(current_event)
                current_event = {}
            except json.JSONDecodeError:
                pass

    return events


class TestBatchEndpoint:
    """Test /movies/batch endpoint."""

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

    def test_batch_empty_list_returns_422(self, client, mock_auth):
        """Empty batch should return 422 (validation error - min_length=1)."""
        response = client.post(
            "/api/v1/movies/batch",
            headers={"X-API-Key": "test-key"},
            json={"imdbIds": []},
        )
        # min_length=1 constraint
        assert response.status_code == 422

    def test_batch_all_cached(self, client, mock_auth):
        """All cached movies should return immediately."""
        cached = make_mock_cached_movie()

        with patch("app.services.cache.get_cached_batch", AsyncMock(return_value={"tt0468569": cached})):
            with patch("app.services.cache.is_cache_fresh", return_value=True):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt0468569"]},
                )

        assert response.status_code == 200
        events = parse_sse_events(response.text)

        movie_events = [e for e in events if e["type"] == "movie"]
        assert len(movie_events) == 1
        assert movie_events[0]["data"]["status"] == "cached"

    def test_batch_cache_miss_fetches(self, client, mock_auth):
        """Cache miss should fetch from RT."""
        cached = make_mock_cached_movie()

        with patch("app.services.cache.get_cached_batch", AsyncMock(return_value={})):
            with patch("app.services.wikidata.get_rt_slug", AsyncMock(return_value="m/the_dark_knight")):
                with patch("app.services.scraper.scrape_movie", AsyncMock(return_value=MOCK_RT_DATA)):
                    with patch("app.services.cache.upsert_cache", AsyncMock(return_value=cached)):
                        response = client.post(
                            "/api/v1/movies/batch",
                            headers={"X-API-Key": "test-key"},
                            json={"imdbIds": ["tt0468569"]},
                        )

        assert response.status_code == 200
        events = parse_sse_events(response.text)

        movie_events = [e for e in events if e["type"] == "movie"]
        assert len(movie_events) == 1
        assert movie_events[0]["data"]["status"] == "fetched"

    def test_batch_error_event_for_not_found(self, client, mock_auth):
        """Not found should return error event."""
        with patch("app.services.cache.get_cached_batch", AsyncMock(return_value={})):
            with patch("app.services.wikidata.get_rt_slug", AsyncMock(return_value=None)):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt9999999"]},
                )

        assert response.status_code == 200
        events = parse_sse_events(response.text)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["error"] == "not_found"

    def test_batch_done_event_has_summary(self, client, mock_auth):
        """Done event should have total, cached, fetched, errors counts."""
        with patch("app.services.cache.get_cached_batch", AsyncMock(return_value={})):
            with patch("app.services.wikidata.get_rt_slug", AsyncMock(return_value=None)):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt9999999"]},
                )

        events = parse_sse_events(response.text)
        done_events = [e for e in events if e["type"] == "done"]

        assert len(done_events) == 1
        done_data = done_events[0]["data"]
        assert "total" in done_data
        assert "cached" in done_data
        assert "fetched" in done_data
        assert "errors" in done_data

    def test_batch_max_50_ids(self, client, mock_auth):
        """Batch should reject more than 50 IDs."""
        ids = [f"tt{str(i).zfill(7)}" for i in range(51)]

        response = client.post(
            "/api/v1/movies/batch",
            headers={"X-API-Key": "test-key"},
            json={"imdbIds": ids},
        )

        assert response.status_code == 422  # Validation error

    def test_batch_response_is_sse(self, client, mock_auth):
        """Batch response should be text/event-stream."""
        cached = make_mock_cached_movie()

        with patch("app.services.cache.get_cached_batch", AsyncMock(return_value={"tt0468569": cached})):
            with patch("app.services.cache.is_cache_fresh", return_value=True):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt0468569"]},
                )

        assert "text/event-stream" in response.headers["content-type"]

    def test_batch_multiple_movies(self, client, mock_auth):
        """Batch with multiple movies should return all."""
        cached1 = make_mock_cached_movie("tt0468569")
        cached2 = make_mock_cached_movie("tt0111161")

        with patch("app.services.cache.get_cached_batch", AsyncMock(return_value={
            "tt0468569": cached1,
            "tt0111161": cached2,
        })):
            with patch("app.services.cache.is_cache_fresh", return_value=True):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt0468569", "tt0111161"]},
                )

        events = parse_sse_events(response.text)
        movie_events = [e for e in events if e["type"] == "movie"]
        assert len(movie_events) == 2

        done_events = [e for e in events if e["type"] == "done"]
        assert done_events[0]["data"]["total"] == 2
        assert done_events[0]["data"]["cached"] == 2
