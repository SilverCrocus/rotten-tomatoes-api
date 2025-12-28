"""Unit tests for browse options service."""

import pytest
from app.services.browse_options import (
    get_browse_options,
    validate_browse_params,
    build_browse_url,
)


class TestBrowseOptions:
    """Test browse options retrieval."""

    def test_get_all_options(self):
        """Should return all browse options."""
        options = get_browse_options()
        assert "certifications" in options
        assert "genres" in options
        assert "affiliates" in options
        assert "sorts" in options
        assert "types" in options
        assert "audience_ratings" in options

    def test_certifications_include_certified_fresh(self):
        """Certifications should include certified_fresh."""
        options = get_browse_options()
        assert "certified_fresh" in options["certifications"]

    def test_certifications_include_fresh(self):
        """Certifications should include fresh."""
        options = get_browse_options()
        assert "fresh" in options["certifications"]

    def test_certifications_include_rotten(self):
        """Certifications should include rotten."""
        options = get_browse_options()
        assert "rotten" in options["certifications"]

    def test_genres_include_horror(self):
        """Genres should include horror."""
        options = get_browse_options()
        assert "horror" in options["genres"]

    def test_genres_include_comedy(self):
        """Genres should include comedy."""
        options = get_browse_options()
        assert "comedy" in options["genres"]

    def test_affiliates_include_netflix(self):
        """Affiliates should include netflix."""
        options = get_browse_options()
        assert "netflix" in options["affiliates"]

    def test_affiliates_include_amazon_prime(self):
        """Affiliates should include amazon_prime."""
        options = get_browse_options()
        assert "amazon_prime" in options["affiliates"]


class TestParamValidation:
    """Test browse parameter validation."""

    def test_valid_certification(self):
        """Valid certification should pass."""
        is_valid, error = validate_browse_params(certification="certified_fresh")
        assert is_valid is True
        assert error is None

    def test_invalid_certification(self):
        """Invalid certification should fail."""
        is_valid, error = validate_browse_params(certification="invalid")
        assert is_valid is False
        assert "certification" in error.lower()

    def test_valid_genre(self):
        """Valid genre should pass."""
        is_valid, error = validate_browse_params(genre="horror")
        assert is_valid is True

    def test_invalid_genre(self):
        """Invalid genre should fail."""
        is_valid, error = validate_browse_params(genre="not_a_genre")
        assert is_valid is False
        assert "genre" in error.lower()

    def test_valid_affiliate(self):
        """Valid affiliate should pass."""
        is_valid, error = validate_browse_params(affiliate="netflix")
        assert is_valid is True

    def test_invalid_affiliate(self):
        """Invalid affiliate should fail."""
        is_valid, error = validate_browse_params(affiliate="blockbuster")
        assert is_valid is False
        assert "affiliate" in error.lower()

    def test_valid_sort(self):
        """Valid sort should pass."""
        is_valid, error = validate_browse_params(sort="popular")
        assert is_valid is True

    def test_invalid_sort(self):
        """Invalid sort should fail."""
        is_valid, error = validate_browse_params(sort="random")
        assert is_valid is False
        assert "sort" in error.lower()

    def test_valid_browse_type(self):
        """Valid browse type should pass."""
        is_valid, error = validate_browse_params(browse_type="movies_at_home")
        assert is_valid is True

    def test_invalid_browse_type(self):
        """Invalid browse type should fail."""
        is_valid, error = validate_browse_params(browse_type="movies_on_vhs")
        assert is_valid is False
        assert "type" in error.lower()

    def test_valid_audience(self):
        """Valid audience should pass."""
        is_valid, error = validate_browse_params(audience="upright")
        assert is_valid is True

    def test_invalid_audience(self):
        """Invalid audience should fail."""
        is_valid, error = validate_browse_params(audience="thumbs_up")
        assert is_valid is False
        assert "audience" in error.lower()

    def test_multiple_valid_params(self):
        """Multiple valid params should pass."""
        is_valid, error = validate_browse_params(
            certification="certified_fresh",
            genre="horror",
            affiliate="netflix",
            sort="popular",
        )
        assert is_valid is True

    def test_no_params_is_valid(self):
        """No params should be valid."""
        is_valid, error = validate_browse_params()
        assert is_valid is True
        assert error is None


class TestUrlBuilding:
    """Test browse URL construction."""

    def test_base_url_no_filters(self):
        """No filters should return base URL."""
        url = build_browse_url()
        assert url == "https://www.rottentomatoes.com/browse/movies_at_home"

    def test_single_certification_filter(self):
        """Single certification filter should be appended."""
        url = build_browse_url(certification="certified_fresh")
        assert "critics:certified_fresh" in url

    def test_single_genre_filter(self):
        """Single genre filter should be appended."""
        url = build_browse_url(genre="horror")
        assert "genres:horror" in url

    def test_single_affiliate_filter(self):
        """Single affiliate filter should be appended."""
        url = build_browse_url(affiliate="netflix")
        assert "affiliates:netflix" in url

    def test_single_sort_filter(self):
        """Single sort filter should be appended."""
        url = build_browse_url(sort="popular")
        assert "sort:popular" in url

    def test_multiple_filters_joined_with_tilde(self):
        """Multiple filters should be joined with ~."""
        url = build_browse_url(
            certification="certified_fresh",
            genre="horror",
        )
        assert "~" in url
        assert "critics:certified_fresh" in url
        assert "genres:horror" in url

    def test_different_browse_type(self):
        """Different browse type should change base URL."""
        url = build_browse_url(browse_type="movies_in_theaters")
        assert "movies_in_theaters" in url

    def test_audience_filter(self):
        """Audience filter should be included."""
        url = build_browse_url(audience="upright")
        assert "audience:upright" in url

    def test_full_url_with_all_filters(self):
        """URL with all filters should be properly formed."""
        url = build_browse_url(
            certification="certified_fresh",
            genre="horror",
            affiliate="netflix",
            sort="popular",
            browse_type="movies_at_home",
            audience="upright",
        )
        assert url.startswith("https://www.rottentomatoes.com/browse/movies_at_home/")
        assert "critics:certified_fresh" in url
        assert "genres:horror" in url
        assert "affiliates:netflix" in url
        assert "sort:popular" in url
        assert "audience:upright" in url
