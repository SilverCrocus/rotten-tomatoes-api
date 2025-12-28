"""Unit tests for cache service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.services.cache import CachedMovie, is_cache_fresh


def make_cached_movie(cached_at: datetime) -> CachedMovie:
    """Create a CachedMovie with specified cached_at time."""
    return CachedMovie(
        imdb_id="tt0468569",
        rt_slug="m/the_dark_knight",
        rt_url="https://www.rottentomatoes.com/m/the_dark_knight",
        title="The Dark Knight",
        year=2008,
        critic_score=94,
        audience_score=94,
        critic_rating="certified_fresh",
        audience_rating="upright",
        consensus="Great movie",
        cached_at=cached_at,
    )


@pytest.fixture
def mock_settings():
    """Mock settings with 7-day TTL."""
    settings = MagicMock()
    settings.cache_ttl_days = 7
    with patch("app.services.cache.get_settings", return_value=settings):
        yield settings


class TestCacheFreshness:
    """Test cache TTL logic."""

    def test_fresh_cache_within_ttl(self, mock_settings):
        """Cache within TTL should be fresh."""
        cached = make_cached_movie(datetime.utcnow() - timedelta(days=3))
        assert is_cache_fresh(cached) is True

    def test_stale_cache_beyond_ttl(self, mock_settings):
        """Cache beyond TTL should be stale."""
        cached = make_cached_movie(datetime.utcnow() - timedelta(days=10))
        assert is_cache_fresh(cached) is False

    def test_cache_at_ttl_boundary(self, mock_settings):
        """Cache exactly at TTL boundary should be stale."""
        cached = make_cached_movie(datetime.utcnow() - timedelta(days=7, seconds=1))
        assert is_cache_fresh(cached) is False

    def test_just_cached_is_fresh(self, mock_settings):
        """Just-cached data should be fresh."""
        cached = make_cached_movie(datetime.utcnow())
        assert is_cache_fresh(cached) is True


class TestCachedMovieClass:
    """Test CachedMovie class."""

    def test_cached_movie_stores_all_fields(self):
        """CachedMovie should store all provided fields."""
        now = datetime.utcnow()
        movie = CachedMovie(
            imdb_id="tt1234567",
            rt_slug="m/test_movie",
            rt_url="https://www.rottentomatoes.com/m/test_movie",
            title="Test Movie",
            year=2023,
            critic_score=85,
            audience_score=90,
            critic_rating="fresh",
            audience_rating="upright",
            consensus="A great test movie.",
            cached_at=now,
        )

        assert movie.imdb_id == "tt1234567"
        assert movie.rt_slug == "m/test_movie"
        assert movie.title == "Test Movie"
        assert movie.year == 2023
        assert movie.critic_score == 85
        assert movie.audience_score == 90
        assert movie.critic_rating == "fresh"
        assert movie.audience_rating == "upright"
        assert movie.consensus == "A great test movie."
        assert movie.cached_at == now

    def test_cached_movie_allows_none_scores(self):
        """CachedMovie should allow None for optional fields."""
        movie = CachedMovie(
            imdb_id="tt9999999",
            rt_slug="m/unknown",
            rt_url="https://www.rottentomatoes.com/m/unknown",
            title="Unknown Movie",
            year=None,
            critic_score=None,
            audience_score=None,
            critic_rating=None,
            audience_rating=None,
            consensus=None,
            cached_at=datetime.utcnow(),
        )

        assert movie.year is None
        assert movie.critic_score is None
        assert movie.audience_score is None
