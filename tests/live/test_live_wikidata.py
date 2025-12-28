"""Live tests for Wikidata - hits real Wikidata SPARQL.

Run manually with: pytest tests/live/test_live_wikidata.py -v
"""

import pytest
import os
from app.services.wikidata import get_rt_slug


# Skip live tests in CI - only run manually
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS", "false").lower() != "true",
    reason="Live tests disabled by default - run with: RUN_LIVE_TESTS=true pytest tests/live/ -v",
)


class TestLiveWikidata:
    """Live tests against real Wikidata."""

    @pytest.mark.asyncio
    async def test_known_imdb_id(self):
        """Query Wikidata for a known IMDB ID."""
        slug = await get_rt_slug("tt0468569")  # The Dark Knight

        assert slug is not None
        assert "dark_knight" in slug.lower()

    @pytest.mark.asyncio
    async def test_shawshank_redemption(self):
        """Query Wikidata for Shawshank Redemption."""
        slug = await get_rt_slug("tt0111161")

        assert slug is not None
        assert "shawshank" in slug.lower()

    @pytest.mark.asyncio
    async def test_unknown_imdb_id(self):
        """Query Wikidata for an unknown IMDB ID."""
        slug = await get_rt_slug("tt0000001")  # Very old/obscure

        # May or may not have RT data
        # Just verify it doesn't crash
        assert slug is None or isinstance(slug, str)

    @pytest.mark.asyncio
    async def test_invalid_imdb_format_returns_none(self):
        """Invalid IMDB format should return None gracefully."""
        slug = await get_rt_slug("invalid")

        assert slug is None
