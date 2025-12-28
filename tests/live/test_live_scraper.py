"""Live tests for RT scraper - hits real RT servers.

Run manually with: pytest tests/live/test_live_scraper.py -v
"""

import pytest
import os
from app.services.scraper import scrape_movie
from app.services.list_scraper import scrape_editorial_list, scrape_browse_page


# Skip live tests in CI - only run manually
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS", "false").lower() != "true",
    reason="Live tests disabled by default - run with: RUN_LIVE_TESTS=true pytest tests/live/ -v",
)


class TestLiveScraper:
    """Live tests against real RT."""

    @pytest.mark.asyncio
    async def test_scrape_known_movie(self):
        """Scrape a known movie from RT."""
        result = await scrape_movie("m/the_dark_knight")

        assert result is not None
        assert result.title == "The Dark Knight"
        assert result.year == 2008
        assert isinstance(result.critic_score, int)
        assert 0 <= result.critic_score <= 100

    @pytest.mark.asyncio
    async def test_scrape_movie_with_no_audience_score(self):
        """Scrape a movie that might not have audience score."""
        # Try a very old movie
        result = await scrape_movie("m/nosferatu_a_symphony_of_horror_1922")

        assert result is not None
        assert result.title is not None

    @pytest.mark.asyncio
    async def test_scrape_editorial_list(self):
        """Scrape an editorial list from RT."""
        result = await scrape_editorial_list(
            "https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/"
        )

        assert result is not None
        assert len(result.movies) > 50  # Should have many movies
        assert result.title  # Should have a title

    @pytest.mark.asyncio
    async def test_scrape_browse_page(self):
        """Scrape a browse page from RT."""
        result = await scrape_browse_page(
            "https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh~genres:horror"
        )

        assert result is not None
        assert len(result.movies) > 0

    @pytest.mark.asyncio
    async def test_scrape_nonexistent_movie(self):
        """Scraping a nonexistent movie should return None."""
        result = await scrape_movie("m/this_movie_does_not_exist_12345")

        assert result is None
