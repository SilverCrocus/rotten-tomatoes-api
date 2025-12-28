"""Unit tests for curated lists service."""

import pytest
from app.services.curated_lists import get_curated_list, get_all_curated_lists


class TestCuratedLists:
    """Test curated list registry."""

    def test_get_all_lists_not_empty(self):
        """Should return at least one curated list."""
        lists = get_all_curated_lists()
        assert len(lists) > 0

    def test_each_list_has_required_fields(self):
        """Each list should have slug, title, description."""
        lists = get_all_curated_lists()
        for lst in lists:
            assert "slug" in lst
            assert "title" in lst
            assert "description" in lst

    def test_get_known_list_by_slug(self):
        """Known slug should return list info."""
        result = get_curated_list("best-horror")
        assert result is not None
        assert "url" in result
        assert "rottentomatoes" in result["url"]

    def test_get_unknown_list_returns_none(self):
        """Unknown slug should return None."""
        result = get_curated_list("not-a-real-list")
        assert result is None

    def test_best_horror_list_exists(self):
        """best-horror list should exist."""
        lists = get_all_curated_lists()
        slugs = [lst["slug"] for lst in lists]
        assert "best-horror" in slugs

    def test_best_2024_list_exists(self):
        """best-2024 list should exist."""
        lists = get_all_curated_lists()
        slugs = [lst["slug"] for lst in lists]
        assert "best-2024" in slugs

    def test_best_comedies_list_exists(self):
        """best-comedies list should exist."""
        lists = get_all_curated_lists()
        slugs = [lst["slug"] for lst in lists]
        assert "best-comedies" in slugs

    def test_curated_list_has_url(self):
        """get_curated_list should return dict with url."""
        result = get_curated_list("best-horror")
        assert result is not None
        assert result["url"].startswith("https://editorial.rottentomatoes.com/")

    def test_curated_list_has_title(self):
        """get_curated_list should return dict with title."""
        result = get_curated_list("best-horror")
        assert result is not None
        assert "Horror" in result["title"]
