"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import APIKey
from app.services.cache import CachedMovie


# =============================================================================
# Mock Data
# =============================================================================

MOCK_MOVIE_DATA = {
    "rt_slug": "m/the_dark_knight",
    "rt_url": "https://www.rottentomatoes.com/m/the_dark_knight",
    "title": "The Dark Knight",
    "year": 2008,
    "critic_score": 94,
    "audience_score": 94,
    "critic_rating": "certified_fresh",
    "audience_rating": "upright",
    "consensus": "Dark, complex, and unforgettable.",
}


def make_mock_cached_movie(imdb_id: str = "tt0468569", cached_at: datetime = None) -> CachedMovie:
    """Create a mock CachedMovie with default or custom values."""
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


def make_mock_api_key(
    id: int = 1,
    key: str = "test-api-key-12345",
    name: str = "Test Key",
    is_admin: bool = False,
    rate_limit: int = 500,
    requests_count: int = 0,
) -> APIKey:
    """Create a mock APIKey with default or custom values."""
    now = datetime.utcnow()
    return APIKey(
        id=id,
        key=key,
        name=name,
        is_admin=is_admin,
        rate_limit=None if is_admin else rate_limit,
        requests_count=requests_count,
        requests_reset_at=now + timedelta(hours=1),
        is_active=True,
        created_at=now,
    )


MOCK_API_KEY = make_mock_api_key()
MOCK_ADMIN_KEY = make_mock_api_key(
    id=2,
    key="admin-api-key-67890",
    name="Admin Key",
    is_admin=True,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_auth():
    """Mock auth to accept test API keys."""
    async def mock_validate(key: str):
        if key == "test-api-key-12345":
            return MOCK_API_KEY
        elif key == "admin-api-key-67890":
            return MOCK_ADMIN_KEY
        return None

    with patch("app.services.auth.validate_api_key", mock_validate):
        yield


@pytest.fixture
def mock_cache():
    """Mock cache operations."""
    cache_store = {}

    async def mock_get_cached(imdb_id: str):
        return cache_store.get(imdb_id)

    async def mock_upsert_cache(imdb_id: str, rt_data):
        movie = CachedMovie(
            imdb_id=imdb_id,
            rt_slug=rt_data.rt_slug,
            rt_url=f"https://www.rottentomatoes.com/{rt_data.rt_slug}",
            title=rt_data.title,
            year=rt_data.year,
            critic_score=rt_data.critic_score,
            audience_score=rt_data.audience_score,
            critic_rating=rt_data.critic_rating,
            audience_rating=rt_data.audience_rating,
            consensus=rt_data.consensus,
            cached_at=datetime.utcnow(),
        )
        cache_store[imdb_id] = movie
        return movie

    async def mock_get_cached_batch(imdb_ids: list):
        return {id: cache_store.get(id) for id in imdb_ids if id in cache_store}

    with patch("app.services.cache.get_cached", mock_get_cached), \
         patch("app.services.cache.upsert_cache", mock_upsert_cache), \
         patch("app.services.cache.get_cached_batch", mock_get_cached_batch):
        yield cache_store


@pytest.fixture
def mock_wikidata():
    """Mock Wikidata SPARQL queries."""
    slugs = {
        "tt0468569": "the_dark_knight",
        "tt0111161": "shawshank_redemption",
    }

    async def mock_get_rt_slug(imdb_id: str):
        return slugs.get(imdb_id)

    with patch("app.services.wikidata.get_rt_slug", mock_get_rt_slug):
        yield slugs


@pytest.fixture
def mock_scraper():
    """Mock RT scraper."""
    from app.models.schemas import RTMovieData

    async def mock_scrape_movie(rt_slug: str):
        return RTMovieData(
            rt_slug=f"m/{rt_slug}",
            title="The Dark Knight",
            year=2008,
            critic_score=94,
            audience_score=94,
            critic_rating="certified_fresh",
            audience_rating="upright",
            consensus="Dark, complex, and unforgettable.",
        )

    with patch("app.services.scraper.scrape_movie", mock_scrape_movie):
        yield


@pytest.fixture
def client(mock_auth):
    """FastAPI test client with mocked auth."""
    return TestClient(app)


@pytest.fixture
def valid_api_key():
    """Valid test API key."""
    return "test-api-key-12345"


@pytest.fixture
def admin_api_key():
    """Admin test API key."""
    return "admin-api-key-67890"
