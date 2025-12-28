# RT API Test Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a comprehensive test suite with ~45 tests covering all API endpoints and services.

**Architecture:** pytest-based test suite with mocked external services (RT, Wikidata, Postgres). Unit tests for pure logic, integration tests for endpoints, live tests for manual verification.

**Tech Stack:** pytest, pytest-asyncio, pytest-cov, respx (httpx mocking), unittest.mock

---

## Task 1: Set Up Test Infrastructure

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create requirements-dev.txt**

```txt
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==4.1.0
respx==0.21.1
```

**Step 2: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
filterwarnings = ignore::DeprecationWarning
```

**Step 3: Create tests/__init__.py**

```python
# Tests package
```

**Step 4: Create tests/conftest.py with core fixtures**

```python
"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import APIKey
from app.services.cache import CachedMovie


# =============================================================================
# Mock Data
# =============================================================================

MOCK_MOVIE_DATA = {
    "rt_url": "https://www.rottentomatoes.com/m/the_dark_knight",
    "title": "The Dark Knight",
    "year": 2008,
    "critic_score": 94,
    "audience_score": 94,
    "critic_rating": "certified_fresh",
    "audience_rating": "upright",
    "consensus": "Dark, complex, and unforgettable.",
}

MOCK_CACHED_MOVIE = CachedMovie(
    imdb_id="tt0468569",
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

MOCK_API_KEY = APIKey(
    id=1,
    key="test-api-key-12345",
    name="Test Key",
    is_admin=False,
    rate_limit=500,
    requests_count=0,
    is_active=True,
    created_at=datetime.utcnow(),
)

MOCK_ADMIN_KEY = APIKey(
    id=2,
    key="admin-api-key-67890",
    name="Admin Key",
    is_admin=True,
    rate_limit=None,
    requests_count=0,
    is_active=True,
    created_at=datetime.utcnow(),
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_auth():
    """Mock auth to accept test API keys."""
    async def mock_get_api_key(key: str):
        if key == "test-api-key-12345":
            return MOCK_API_KEY
        elif key == "admin-api-key-67890":
            return MOCK_ADMIN_KEY
        return None

    async def mock_check_rate_limit(api_key: APIKey):
        if api_key.requests_count >= (api_key.rate_limit or float('inf')):
            return False
        return True

    with patch("app.services.auth.get_api_key", mock_get_api_key), \
         patch("app.services.auth.check_rate_limit", mock_check_rate_limit), \
         patch("app.services.auth.increment_request_count", AsyncMock()):
        yield


@pytest.fixture
def mock_cache():
    """Mock cache operations."""
    cache_store = {}

    async def mock_get_cached(imdb_id: str):
        return cache_store.get(imdb_id)

    async def mock_upsert_cache(imdb_id: str, data: dict):
        movie = CachedMovie(
            imdb_id=imdb_id,
            rt_url=data["rt_url"],
            title=data["title"],
            year=data["year"],
            critic_score=data["critic_score"],
            audience_score=data["audience_score"],
            critic_rating=data["critic_rating"],
            audience_rating=data["audience_rating"],
            consensus=data["consensus"],
            cached_at=datetime.utcnow(),
        )
        cache_store[imdb_id] = movie
        return movie

    async def mock_get_cached_batch(imdb_ids: list):
        return {id: cache_store.get(id) for id in imdb_ids}

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
    async def mock_scrape_movie(rt_slug: str):
        return MOCK_MOVIE_DATA.copy()

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
```

**Step 5: Install dev dependencies and verify setup**

Run: `pip install -r requirements-dev.txt`

**Step 6: Commit**

```bash
git add requirements-dev.txt pytest.ini tests/
git commit -m "test: add test infrastructure and fixtures"
```

---

## Task 2: Unit Tests - Auth Service

**Files:**
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_auth.py`

**Step 1: Create tests/unit/__init__.py**

```python
# Unit tests package
```

**Step 2: Write auth unit tests**

```python
"""Unit tests for auth service."""

import pytest
from datetime import datetime, timedelta
from app.services.auth import APIKey


class TestAPIKeyValidation:
    """Test API key validation logic."""

    def test_active_key_is_valid(self):
        """Active API key should be considered valid."""
        key = APIKey(
            id=1, key="test", name="Test", is_admin=False,
            rate_limit=500, requests_count=0, is_active=True,
            created_at=datetime.utcnow()
        )
        assert key.is_active is True

    def test_inactive_key_is_invalid(self):
        """Inactive API key should be considered invalid."""
        key = APIKey(
            id=1, key="test", name="Test", is_admin=False,
            rate_limit=500, requests_count=0, is_active=False,
            created_at=datetime.utcnow()
        )
        assert key.is_active is False

    def test_admin_key_has_admin_flag(self):
        """Admin key should have is_admin=True."""
        key = APIKey(
            id=1, key="test", name="Admin", is_admin=True,
            rate_limit=None, requests_count=0, is_active=True,
            created_at=datetime.utcnow()
        )
        assert key.is_admin is True

    def test_regular_key_not_admin(self):
        """Regular key should have is_admin=False."""
        key = APIKey(
            id=1, key="test", name="Regular", is_admin=False,
            rate_limit=500, requests_count=0, is_active=True,
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
            created_at=datetime.utcnow()
        )
        assert key.requests_count < key.rate_limit

    def test_at_rate_limit(self):
        """Key at rate limit should be blocked."""
        key = APIKey(
            id=1, key="test", name="Test", is_admin=False,
            rate_limit=500, requests_count=500, is_active=True,
            created_at=datetime.utcnow()
        )
        assert key.requests_count >= key.rate_limit

    def test_admin_unlimited_rate(self):
        """Admin key should have no rate limit."""
        key = APIKey(
            id=1, key="test", name="Admin", is_admin=True,
            rate_limit=None, requests_count=10000, is_active=True,
            created_at=datetime.utcnow()
        )
        assert key.rate_limit is None
```

**Step 3: Run tests**

Run: `pytest tests/unit/test_auth.py -v`
Expected: All 7 tests PASS

**Step 4: Commit**

```bash
git add tests/unit/
git commit -m "test: add auth service unit tests"
```

---

## Task 3: Unit Tests - Cache Service

**Files:**
- Create: `tests/unit/test_cache.py`

**Step 1: Write cache unit tests**

```python
"""Unit tests for cache service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.services.cache import CachedMovie, is_cache_fresh
from app.config import Settings


@pytest.fixture
def mock_settings():
    """Mock settings with 7-day TTL."""
    settings = Settings(
        database_url="postgresql://localhost:5432/test",
        cache_ttl_days=7,
        admin_api_key="test"
    )
    with patch("app.services.cache.get_settings", return_value=settings):
        yield settings


class TestCacheFreshness:
    """Test cache TTL logic."""

    def test_fresh_cache_within_ttl(self, mock_settings):
        """Cache within TTL should be fresh."""
        cached = CachedMovie(
            imdb_id="tt0468569",
            rt_url="https://www.rottentomatoes.com/m/the_dark_knight",
            title="The Dark Knight",
            year=2008,
            critic_score=94,
            audience_score=94,
            critic_rating="certified_fresh",
            audience_rating="upright",
            consensus="Great movie",
            cached_at=datetime.utcnow() - timedelta(days=3),
        )
        assert is_cache_fresh(cached) is True

    def test_stale_cache_beyond_ttl(self, mock_settings):
        """Cache beyond TTL should be stale."""
        cached = CachedMovie(
            imdb_id="tt0468569",
            rt_url="https://www.rottentomatoes.com/m/the_dark_knight",
            title="The Dark Knight",
            year=2008,
            critic_score=94,
            audience_score=94,
            critic_rating="certified_fresh",
            audience_rating="upright",
            consensus="Great movie",
            cached_at=datetime.utcnow() - timedelta(days=10),
        )
        assert is_cache_fresh(cached) is False

    def test_cache_at_ttl_boundary(self, mock_settings):
        """Cache exactly at TTL boundary should be stale."""
        cached = CachedMovie(
            imdb_id="tt0468569",
            rt_url="https://www.rottentomatoes.com/m/the_dark_knight",
            title="The Dark Knight",
            year=2008,
            critic_score=94,
            audience_score=94,
            critic_rating="certified_fresh",
            audience_rating="upright",
            consensus="Great movie",
            cached_at=datetime.utcnow() - timedelta(days=7, seconds=1),
        )
        assert is_cache_fresh(cached) is False

    def test_just_cached_is_fresh(self, mock_settings):
        """Just-cached data should be fresh."""
        cached = CachedMovie(
            imdb_id="tt0468569",
            rt_url="https://www.rottentomatoes.com/m/the_dark_knight",
            title="The Dark Knight",
            year=2008,
            critic_score=94,
            audience_score=94,
            critic_rating="certified_fresh",
            audience_rating="upright",
            consensus="Great movie",
            cached_at=datetime.utcnow(),
        )
        assert is_cache_fresh(cached) is True
```

**Step 2: Run tests**

Run: `pytest tests/unit/test_cache.py -v`
Expected: All 4 tests PASS

**Step 3: Commit**

```bash
git add tests/unit/test_cache.py
git commit -m "test: add cache service unit tests"
```

---

## Task 4: Unit Tests - Browse Options

**Files:**
- Create: `tests/unit/test_browse_options.py`

**Step 1: Write browse options unit tests**

```python
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

    def test_certifications_include_certified_fresh(self):
        """Certifications should include certified_fresh."""
        options = get_browse_options()
        assert "certified_fresh" in options["certifications"]

    def test_genres_include_horror(self):
        """Genres should include horror."""
        options = get_browse_options()
        assert "horror" in options["genres"]


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

    def test_multiple_valid_params(self):
        """Multiple valid params should pass."""
        is_valid, error = validate_browse_params(
            certification="certified_fresh",
            genre="horror",
            affiliate="netflix"
        )
        assert is_valid is True


class TestUrlBuilding:
    """Test browse URL construction."""

    def test_base_url_no_filters(self):
        """No filters should return base URL."""
        url = build_browse_url()
        assert url == "https://www.rottentomatoes.com/browse/movies_at_home"

    def test_single_filter(self):
        """Single filter should be appended."""
        url = build_browse_url(certification="certified_fresh")
        assert "critics:certified_fresh" in url

    def test_multiple_filters_joined_with_tilde(self):
        """Multiple filters should be joined with ~."""
        url = build_browse_url(
            certification="certified_fresh",
            genre="horror"
        )
        assert "~" in url
        assert "critics:certified_fresh" in url
        assert "genres:horror" in url

    def test_different_browse_type(self):
        """Different browse type should change base URL."""
        url = build_browse_url(browse_type="movies_in_theaters")
        assert "movies_in_theaters" in url
```

**Step 2: Run tests**

Run: `pytest tests/unit/test_browse_options.py -v`
Expected: All 14 tests PASS

**Step 3: Commit**

```bash
git add tests/unit/test_browse_options.py
git commit -m "test: add browse options unit tests"
```

---

## Task 5: Unit Tests - Curated Lists

**Files:**
- Create: `tests/unit/test_curated_lists.py`

**Step 1: Write curated lists unit tests**

```python
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
        """Each list should have slug, title, description, url."""
        lists = get_all_curated_lists()
        for lst in lists:
            assert "slug" in lst
            assert "title" in lst
            assert "description" in lst
            assert "url" in lst

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
```

**Step 2: Run tests**

Run: `pytest tests/unit/test_curated_lists.py -v`
Expected: All 5 tests PASS

**Step 3: Commit**

```bash
git add tests/unit/test_curated_lists.py
git commit -m "test: add curated lists unit tests"
```

---

## Task 6: Integration Tests - Health Endpoint

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_health.py`

**Step 1: Create tests/integration/__init__.py**

```python
# Integration tests package
```

**Step 2: Write health endpoint tests**

```python
"""Integration tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestHealthEndpoint:
    """Test /health endpoint."""

    @pytest.fixture
    def client(self):
        """Test client without auth mocking."""
        return TestClient(app)

    def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_no_auth_required(self, client):
        """Health endpoint should not require API key."""
        response = client.get("/api/v1/health")
        # No X-API-Key header, should still work
        assert response.status_code == 200

    def test_health_returns_version(self, client):
        """Health endpoint should return version."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "version" in data
```

**Step 3: Run tests**

Run: `pytest tests/integration/test_health.py -v`
Expected: All 4 tests PASS

**Step 4: Commit**

```bash
git add tests/integration/
git commit -m "test: add health endpoint integration tests"
```

---

## Task 7: Integration Tests - Movie Endpoint

**Files:**
- Create: `tests/integration/test_movie_endpoint.py`

**Step 1: Write movie endpoint tests**

```python
"""Integration tests for movie endpoint."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.cache import CachedMovie


# Mock data
MOCK_MOVIE = {
    "rt_url": "https://www.rottentomatoes.com/m/the_dark_knight",
    "title": "The Dark Knight",
    "year": 2008,
    "critic_score": 94,
    "audience_score": 94,
    "critic_rating": "certified_fresh",
    "audience_rating": "upright",
    "consensus": "Dark, complex, and unforgettable.",
}


class TestMovieEndpoint:
    """Test /movie/{imdb_id} endpoint."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_auth(self):
        """Mock auth to accept any key."""
        with patch("app.api.dependencies.auth.get_api_key") as mock:
            from app.services.auth import APIKey
            mock.return_value = APIKey(
                id=1, key="test", name="Test", is_admin=False,
                rate_limit=500, requests_count=0, is_active=True,
                created_at=datetime.utcnow()
            )
            with patch("app.api.dependencies.auth.check_rate_limit", return_value=True):
                with patch("app.api.dependencies.auth.increment_request_count", new_callable=AsyncMock):
                    yield

    def test_missing_api_key_returns_401(self, client):
        """Request without API key should return 401."""
        response = client.get("/api/v1/movie/tt0468569")
        assert response.status_code in [401, 422]

    def test_invalid_imdb_format_returns_400(self, client, mock_auth):
        """Invalid IMDB ID format should return 400."""
        response = client.get(
            "/api/v1/movie/invalid",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 400
        assert "Invalid IMDB ID" in response.json()["detail"]

    def test_imdb_without_tt_prefix_returns_400(self, client, mock_auth):
        """IMDB ID without tt prefix should return 400."""
        response = client.get(
            "/api/v1/movie/0468569",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 400

    def test_cache_hit_returns_cached_data(self, client, mock_auth):
        """Cache hit should return cached movie data."""
        cached = CachedMovie(
            imdb_id="tt0468569",
            rt_url=MOCK_MOVIE["rt_url"],
            title=MOCK_MOVIE["title"],
            year=MOCK_MOVIE["year"],
            critic_score=MOCK_MOVIE["critic_score"],
            audience_score=MOCK_MOVIE["audience_score"],
            critic_rating=MOCK_MOVIE["critic_rating"],
            audience_rating=MOCK_MOVIE["audience_rating"],
            consensus=MOCK_MOVIE["consensus"],
            cached_at=datetime.utcnow(),
        )

        with patch("app.services.cache.get_cached", return_value=cached):
            with patch("app.services.cache.is_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/movie/tt0468569",
                    headers={"X-API-Key": "test-key"}
                )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Dark Knight"
        assert data["criticScore"] == 94

    def test_cache_miss_fetches_from_rt(self, client, mock_auth):
        """Cache miss should fetch from Wikidata and RT."""
        with patch("app.services.cache.get_cached", return_value=None):
            with patch("app.services.wikidata.get_rt_slug", return_value="the_dark_knight"):
                with patch("app.services.scraper.scrape_movie", return_value=MOCK_MOVIE):
                    with patch("app.services.cache.upsert_cache") as mock_upsert:
                        mock_upsert.return_value = CachedMovie(
                            imdb_id="tt0468569",
                            cached_at=datetime.utcnow(),
                            **MOCK_MOVIE
                        )
                        response = client.get(
                            "/api/v1/movie/tt0468569",
                            headers={"X-API-Key": "test-key"}
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Dark Knight"

    def test_not_found_in_wikidata_returns_404(self, client, mock_auth):
        """Movie not in Wikidata should return 404."""
        with patch("app.services.cache.get_cached", return_value=None):
            with patch("app.services.wikidata.get_rt_slug", return_value=None):
                response = client.get(
                    "/api/v1/movie/tt9999999",
                    headers={"X-API-Key": "test-key"}
                )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_scrape_failure_with_stale_cache_returns_stale(self, client, mock_auth):
        """Scrape failure with stale cache should return stale data."""
        stale_cached = CachedMovie(
            imdb_id="tt0468569",
            rt_url=MOCK_MOVIE["rt_url"],
            title=MOCK_MOVIE["title"],
            year=MOCK_MOVIE["year"],
            critic_score=MOCK_MOVIE["critic_score"],
            audience_score=MOCK_MOVIE["audience_score"],
            critic_rating=MOCK_MOVIE["critic_rating"],
            audience_rating=MOCK_MOVIE["audience_rating"],
            consensus=MOCK_MOVIE["consensus"],
            cached_at=datetime.utcnow() - timedelta(days=10),
        )

        with patch("app.services.cache.get_cached", return_value=stale_cached):
            with patch("app.services.cache.is_cache_fresh", return_value=False):
                with patch("app.services.wikidata.get_rt_slug", return_value="the_dark_knight"):
                    with patch("app.services.scraper.scrape_movie", return_value=None):
                        response = client.get(
                            "/api/v1/movie/tt0468569",
                            headers={"X-API-Key": "test-key"}
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Dark Knight"

    def test_scrape_failure_no_cache_returns_502(self, client, mock_auth):
        """Scrape failure without cache should return 502."""
        with patch("app.services.cache.get_cached", return_value=None):
            with patch("app.services.wikidata.get_rt_slug", return_value="the_dark_knight"):
                with patch("app.services.scraper.scrape_movie", return_value=None):
                    response = client.get(
                        "/api/v1/movie/tt0468569",
                        headers={"X-API-Key": "test-key"}
                    )

        assert response.status_code == 502
```

**Step 2: Run tests**

Run: `pytest tests/integration/test_movie_endpoint.py -v`
Expected: All 9 tests PASS

**Step 3: Commit**

```bash
git add tests/integration/test_movie_endpoint.py
git commit -m "test: add movie endpoint integration tests"
```

---

## Task 8: Integration Tests - List Endpoints

**Files:**
- Create: `tests/integration/test_list_endpoints.py`

**Step 1: Write list endpoint tests**

```python
"""Integration tests for list endpoints."""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.list_cache import CachedList
from app.services.list_scraper import ListResult, ListMovie


class TestListEndpoints:
    """Test list endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_auth(self):
        """Mock auth to accept any key."""
        with patch("app.api.dependencies.auth.get_api_key") as mock:
            from app.services.auth import APIKey
            mock.return_value = APIKey(
                id=1, key="test", name="Test", is_admin=False,
                rate_limit=500, requests_count=0, is_active=True,
                created_at=datetime.utcnow()
            )
            with patch("app.api.dependencies.auth.check_rate_limit", return_value=True):
                with patch("app.api.dependencies.auth.increment_request_count", new_callable=AsyncMock):
                    yield

    # --- Curated Lists ---

    def test_get_curated_lists(self, client, mock_auth):
        """Should return list of curated lists."""
        response = client.get(
            "/api/v1/lists/curated",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "lists" in data
        assert len(data["lists"]) > 0

    def test_curated_list_has_required_fields(self, client, mock_auth):
        """Each curated list should have slug, title, description."""
        response = client.get(
            "/api/v1/lists/curated",
            headers={"X-API-Key": "test-key"}
        )
        data = response.json()
        for lst in data["lists"]:
            assert "slug" in lst
            assert "title" in lst
            assert "description" in lst

    def test_get_curated_list_by_slug_cache_hit(self, client, mock_auth):
        """Curated list by slug with cache hit."""
        cached = CachedList(
            url_hash="abc123",
            source_url="https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/",
            title="Best Horror Movies",
            movies=[{"rtSlug": "m/get_out", "title": "Get Out", "year": 2017}],
            cached_at=datetime.utcnow(),
        )

        with patch("app.services.list_cache.get_cached_list", return_value=cached):
            with patch("app.services.list_cache.is_list_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/lists/curated/best-horror",
                    headers={"X-API-Key": "test-key"}
                )

        assert response.status_code == 200
        data = response.json()
        assert data["movieCount"] == 1
        assert data["movies"][0]["title"] == "Get Out"

    def test_unknown_curated_slug_returns_404(self, client, mock_auth):
        """Unknown curated slug should return 404."""
        response = client.get(
            "/api/v1/lists/curated/not-a-real-list",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 404

    # --- Browse Options ---

    def test_get_browse_options(self, client, mock_auth):
        """Should return browse filter options."""
        response = client.get(
            "/api/v1/lists/browse/options",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "certifications" in data
        assert "genres" in data
        assert "affiliates" in data

    # --- Browse ---

    def test_browse_with_valid_filters(self, client, mock_auth):
        """Browse with valid filters should work."""
        cached = CachedList(
            url_hash="def456",
            source_url="https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh~genres:horror",
            title="Browse Results",
            movies=[{"rtSlug": "m/get_out", "title": "Get Out", "year": 2017}],
            cached_at=datetime.utcnow(),
        )

        with patch("app.services.list_cache.get_cached_list", return_value=cached):
            with patch("app.services.list_cache.is_list_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/lists/browse?certification=certified_fresh&genre=horror",
                    headers={"X-API-Key": "test-key"}
                )

        assert response.status_code == 200

    def test_browse_invalid_certification_returns_400(self, client, mock_auth):
        """Browse with invalid certification should return 400."""
        response = client.get(
            "/api/v1/lists/browse?certification=invalid",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 400

    def test_browse_invalid_genre_returns_400(self, client, mock_auth):
        """Browse with invalid genre should return 400."""
        response = client.get(
            "/api/v1/lists/browse?genre=not_a_genre",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 400

    # --- URL-based List ---

    def test_list_by_url_editorial(self, client, mock_auth):
        """Fetch list by editorial URL."""
        cached = CachedList(
            url_hash="ghi789",
            source_url="https://editorial.rottentomatoes.com/guide/best-action-movies/",
            title="Best Action Movies",
            movies=[{"rtSlug": "m/mad_max_fury_road", "title": "Mad Max: Fury Road", "year": 2015}],
            cached_at=datetime.utcnow(),
        )

        with patch("app.services.list_cache.get_cached_list", return_value=cached):
            with patch("app.services.list_cache.is_list_cache_fresh", return_value=True):
                response = client.get(
                    "/api/v1/list?url=https://editorial.rottentomatoes.com/guide/best-action-movies/",
                    headers={"X-API-Key": "test-key"}
                )

        assert response.status_code == 200
        data = response.json()
        assert data["movieCount"] == 1

    def test_list_by_url_unsupported_returns_400(self, client, mock_auth):
        """Unsupported URL format should return 400."""
        response = client.get(
            "/api/v1/list?url=https://www.google.com/",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 400
```

**Step 2: Run tests**

Run: `pytest tests/integration/test_list_endpoints.py -v`
Expected: All 11 tests PASS

**Step 3: Commit**

```bash
git add tests/integration/test_list_endpoints.py
git commit -m "test: add list endpoints integration tests"
```

---

## Task 9: Integration Tests - Admin Endpoints

**Files:**
- Create: `tests/integration/test_admin_endpoints.py`

**Step 1: Write admin endpoint tests**

```python
"""Integration tests for admin endpoints."""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import APIKey


class TestAdminEndpoints:
    """Test admin endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_admin_auth(self):
        """Mock auth for admin user."""
        with patch("app.api.dependencies.auth.get_api_key") as mock:
            mock.return_value = APIKey(
                id=1, key="admin-key", name="Admin", is_admin=True,
                rate_limit=None, requests_count=0, is_active=True,
                created_at=datetime.utcnow()
            )
            with patch("app.api.dependencies.auth.check_rate_limit", return_value=True):
                with patch("app.api.dependencies.auth.increment_request_count", new_callable=AsyncMock):
                    yield

    @pytest.fixture
    def mock_regular_auth(self):
        """Mock auth for regular user."""
        with patch("app.api.dependencies.auth.get_api_key") as mock:
            mock.return_value = APIKey(
                id=2, key="regular-key", name="Regular", is_admin=False,
                rate_limit=500, requests_count=0, is_active=True,
                created_at=datetime.utcnow()
            )
            with patch("app.api.dependencies.auth.check_rate_limit", return_value=True):
                with patch("app.api.dependencies.auth.increment_request_count", new_callable=AsyncMock):
                    yield

    def test_create_api_key_as_admin(self, client, mock_admin_auth):
        """Admin should be able to create API keys."""
        new_key = APIKey(
            id=3, key="new-key-abc123", name="New Key", is_admin=False,
            rate_limit=500, requests_count=0, is_active=True,
            created_at=datetime.utcnow()
        )

        with patch("app.services.auth.create_api_key", return_value=new_key):
            response = client.post(
                "/api/v1/admin/keys",
                headers={"X-API-Key": "admin-key"},
                json={"name": "New Key"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Key"
        assert "key" in data

    def test_create_api_key_as_regular_returns_403(self, client, mock_regular_auth):
        """Regular user should not be able to create API keys."""
        response = client.post(
            "/api/v1/admin/keys",
            headers={"X-API-Key": "regular-key"},
            json={"name": "New Key"}
        )
        assert response.status_code == 403

    def test_list_api_keys_as_admin(self, client, mock_admin_auth):
        """Admin should be able to list API keys."""
        keys = [
            APIKey(
                id=1, key="key1...masked", name="Key 1", is_admin=False,
                rate_limit=500, requests_count=10, is_active=True,
                created_at=datetime.utcnow()
            ),
        ]

        with patch("app.services.auth.list_api_keys", return_value=keys):
            response = client.get(
                "/api/v1/admin/keys",
                headers={"X-API-Key": "admin-key"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert len(data["keys"]) == 1

    def test_list_api_keys_as_regular_returns_403(self, client, mock_regular_auth):
        """Regular user should not be able to list API keys."""
        response = client.get(
            "/api/v1/admin/keys",
            headers={"X-API-Key": "regular-key"}
        )
        assert response.status_code == 403

    def test_revoke_api_key_as_admin(self, client, mock_admin_auth):
        """Admin should be able to revoke API keys."""
        with patch("app.services.auth.revoke_api_key", return_value=True):
            response = client.delete(
                "/api/v1/admin/keys/5",
                headers={"X-API-Key": "admin-key"}
            )

        assert response.status_code == 200
        assert "revoked" in response.json()["message"].lower()

    def test_revoke_nonexistent_key_returns_404(self, client, mock_admin_auth):
        """Revoking nonexistent key should return 404."""
        with patch("app.services.auth.revoke_api_key", return_value=False):
            response = client.delete(
                "/api/v1/admin/keys/999",
                headers={"X-API-Key": "admin-key"}
            )

        assert response.status_code == 404

    def test_revoke_api_key_as_regular_returns_403(self, client, mock_regular_auth):
        """Regular user should not be able to revoke API keys."""
        response = client.delete(
            "/api/v1/admin/keys/5",
            headers={"X-API-Key": "regular-key"}
        )
        assert response.status_code == 403
```

**Step 2: Run tests**

Run: `pytest tests/integration/test_admin_endpoints.py -v`
Expected: All 7 tests PASS

**Step 3: Commit**

```bash
git add tests/integration/test_admin_endpoints.py
git commit -m "test: add admin endpoints integration tests"
```

---

## Task 10: Integration Tests - Batch Endpoint

**Files:**
- Create: `tests/integration/test_batch_endpoint.py`

**Step 1: Write batch endpoint tests**

```python
"""Integration tests for batch endpoint."""

import pytest
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.cache import CachedMovie


MOCK_MOVIE = {
    "rt_url": "https://www.rottentomatoes.com/m/the_dark_knight",
    "title": "The Dark Knight",
    "year": 2008,
    "critic_score": 94,
    "audience_score": 94,
    "critic_rating": "certified_fresh",
    "audience_rating": "upright",
    "consensus": "Dark, complex, and unforgettable.",
}


class TestBatchEndpoint:
    """Test /movies/batch endpoint."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_auth(self):
        """Mock auth to accept any key."""
        with patch("app.api.dependencies.auth.get_api_key") as mock:
            from app.services.auth import APIKey
            mock.return_value = APIKey(
                id=1, key="test", name="Test", is_admin=False,
                rate_limit=500, requests_count=0, is_active=True,
                created_at=datetime.utcnow()
            )
            with patch("app.api.dependencies.auth.check_rate_limit", return_value=True):
                with patch("app.api.dependencies.auth.increment_request_count", new_callable=AsyncMock):
                    yield

    def _parse_sse_events(self, response_text: str) -> list:
        """Parse SSE events from response text."""
        events = []
        current_event = {}

        for line in response_text.split("\n"):
            if line.startswith("event: "):
                current_event["type"] = line[7:]
            elif line.startswith("data: "):
                current_event["data"] = json.loads(line[6:])
                events.append(current_event)
                current_event = {}

        return events

    def test_batch_empty_list_returns_done(self, client, mock_auth):
        """Empty batch should return done event immediately."""
        response = client.post(
            "/api/v1/movies/batch",
            headers={"X-API-Key": "test-key"},
            json={"imdbIds": []}
        )

        assert response.status_code == 200
        events = self._parse_sse_events(response.text)
        assert any(e["type"] == "done" for e in events)

    def test_batch_all_cached(self, client, mock_auth):
        """All cached movies should return immediately."""
        cached = CachedMovie(
            imdb_id="tt0468569",
            cached_at=datetime.utcnow(),
            **MOCK_MOVIE
        )

        with patch("app.services.cache.get_cached_batch", return_value={"tt0468569": cached}):
            with patch("app.services.cache.is_cache_fresh", return_value=True):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt0468569"]}
                )

        assert response.status_code == 200
        events = self._parse_sse_events(response.text)

        movie_events = [e for e in events if e["type"] == "movie"]
        assert len(movie_events) == 1
        assert movie_events[0]["data"]["status"] == "cached"

    def test_batch_cache_miss_fetches(self, client, mock_auth):
        """Cache miss should fetch from RT."""
        with patch("app.services.cache.get_cached_batch", return_value={}):
            with patch("app.services.wikidata.get_rt_slug", return_value="the_dark_knight"):
                with patch("app.services.scraper.scrape_movie", return_value=MOCK_MOVIE):
                    with patch("app.services.cache.upsert_cache") as mock_upsert:
                        mock_upsert.return_value = CachedMovie(
                            imdb_id="tt0468569",
                            cached_at=datetime.utcnow(),
                            **MOCK_MOVIE
                        )
                        response = client.post(
                            "/api/v1/movies/batch",
                            headers={"X-API-Key": "test-key"},
                            json={"imdbIds": ["tt0468569"]}
                        )

        assert response.status_code == 200
        events = self._parse_sse_events(response.text)

        movie_events = [e for e in events if e["type"] == "movie"]
        assert len(movie_events) == 1
        assert movie_events[0]["data"]["status"] == "fetched"

    def test_batch_error_event_for_not_found(self, client, mock_auth):
        """Not found should return error event."""
        with patch("app.services.cache.get_cached_batch", return_value={}):
            with patch("app.services.wikidata.get_rt_slug", return_value=None):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt9999999"]}
                )

        assert response.status_code == 200
        events = self._parse_sse_events(response.text)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["error"] == "not_found"

    def test_batch_done_event_has_summary(self, client, mock_auth):
        """Done event should have total, cached, fetched, errors counts."""
        with patch("app.services.cache.get_cached_batch", return_value={}):
            with patch("app.services.wikidata.get_rt_slug", return_value=None):
                response = client.post(
                    "/api/v1/movies/batch",
                    headers={"X-API-Key": "test-key"},
                    json={"imdbIds": ["tt9999999"]}
                )

        events = self._parse_sse_events(response.text)
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
            json={"imdbIds": ids}
        )

        assert response.status_code == 422  # Validation error
```

**Step 2: Run tests**

Run: `pytest tests/integration/test_batch_endpoint.py -v`
Expected: All 6 tests PASS

**Step 3: Commit**

```bash
git add tests/integration/test_batch_endpoint.py
git commit -m "test: add batch endpoint integration tests"
```

---

## Task 11: Live Tests

**Files:**
- Create: `tests/live/__init__.py`
- Create: `tests/live/test_live_scraper.py`
- Create: `tests/live/test_live_wikidata.py`

**Step 1: Create tests/live/__init__.py**

```python
# Live tests - run against real RT/Wikidata
# Skipped in CI, run manually with: pytest tests/live/ -v
```

**Step 2: Create live scraper tests**

```python
"""Live tests for RT scraper - hits real RT servers."""

import pytest
from app.services.scraper import scrape_movie
from app.services.list_scraper import scrape_editorial_list, scrape_browse_page


# Mark all tests to skip in CI
pytestmark = pytest.mark.skipif(
    True,  # Change to False to run live tests
    reason="Live tests disabled by default - run with: pytest tests/live/ -v --override-ini='addopts='"
)


class TestLiveScraper:
    """Live tests against real RT."""

    @pytest.mark.asyncio
    async def test_scrape_known_movie(self):
        """Scrape a known movie from RT."""
        result = await scrape_movie("the_dark_knight")

        assert result is not None
        assert result["title"] == "The Dark Knight"
        assert result["year"] == 2008
        assert isinstance(result["critic_score"], int)
        assert 0 <= result["critic_score"] <= 100

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
```

**Step 3: Create live Wikidata tests**

```python
"""Live tests for Wikidata - hits real Wikidata SPARQL."""

import pytest
from app.services.wikidata import get_rt_slug


# Mark all tests to skip in CI
pytestmark = pytest.mark.skipif(
    True,  # Change to False to run live tests
    reason="Live tests disabled by default"
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
    async def test_unknown_imdb_id(self):
        """Query Wikidata for an unknown IMDB ID."""
        slug = await get_rt_slug("tt0000001")  # Very old/obscure

        # May or may not have RT data
        # Just verify it doesn't crash
        assert slug is None or isinstance(slug, str)
```

**Step 4: Commit**

```bash
git add tests/live/
git commit -m "test: add live tests for manual RT/Wikidata verification"
```

---

## Task 12: GitHub Actions CI Workflow

**Files:**
- Create: `.github/workflows/test.yml`

**Step 1: Create workflow directory**

```bash
mkdir -p .github/workflows
```

**Step 2: Create test workflow**

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests
        run: |
          pytest tests/ -v --ignore=tests/live/ --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          fail_ci_if_error: false
```

**Step 3: Commit**

```bash
git add .github/
git commit -m "ci: add GitHub Actions test workflow"
```

---

## Task 13: Final Verification

**Step 1: Run all tests**

Run: `pytest tests/ --ignore=tests/live/ -v`
Expected: All ~45 tests PASS

**Step 2: Run with coverage**

Run: `pytest tests/ --ignore=tests/live/ --cov=app --cov-report=term-missing`
Expected: Coverage report showing tested lines

**Step 3: Push to trigger CI**

```bash
git push origin main
```

**Step 4: Verify CI passes**

Check GitHub Actions at: https://github.com/SilverCrocus/rotten-tomatoes-api/actions

---

## Summary

| Task | Tests | Description |
|------|-------|-------------|
| 1 | - | Test infrastructure setup |
| 2 | 7 | Auth unit tests |
| 3 | 4 | Cache unit tests |
| 4 | 14 | Browse options unit tests |
| 5 | 5 | Curated lists unit tests |
| 6 | 4 | Health endpoint tests |
| 7 | 9 | Movie endpoint tests |
| 8 | 11 | List endpoints tests |
| 9 | 7 | Admin endpoints tests |
| 10 | 6 | Batch endpoint tests |
| 11 | 5 | Live tests (manual) |
| 12 | - | GitHub Actions CI |
| 13 | - | Final verification |

**Total: ~47 tests**
