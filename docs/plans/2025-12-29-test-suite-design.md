# RT API Test Suite Design

## Overview

Comprehensive test suite for the Rotten Tomatoes API with fast mocked tests for CI and optional live tests for manual verification.

## Goals

- **Regression protection**: Catch breaking changes on every commit
- **Fast CI**: All automated tests run in <30 seconds
- **Live verification**: Optional tests to verify RT scraping still works

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (mock client, mock services)
├── unit/                    # Fast, isolated tests
│   ├── test_auth.py         # API key validation, rate limiting logic
│   ├── test_cache.py        # Cache freshness checks, TTL logic
│   ├── test_browse_options.py  # URL building, param validation
│   └── test_curated_lists.py   # Registry lookups
├── integration/             # Tests with mocked external services
│   ├── test_movie_endpoint.py     # /movie/{imdb_id}
│   ├── test_batch_endpoint.py     # /movies/batch (SSE streaming)
│   ├── test_list_endpoints.py     # /list, /lists/curated, /lists/browse
│   ├── test_admin_endpoints.py    # /admin/keys CRUD
│   └── test_health.py             # /health
└── live/                    # Optional tests against real RT (not in CI)
    ├── test_live_scraper.py       # Verify RT scraping still works
    └── test_live_wikidata.py      # Verify Wikidata queries work
```

## Fixtures & Mocking Strategy

### Core Fixtures (conftest.py)

```python
@pytest.fixture
def client():
    # FastAPI TestClient with mocked dependencies

@pytest.fixture
def valid_api_key():
    # Returns a test API key that passes auth

@pytest.fixture
def admin_api_key():
    # Returns a test admin key

@pytest.fixture
def mock_cache():
    # Patches cache.get_cached, cache.upsert_cache

@pytest.fixture
def mock_wikidata():
    # Patches wikidata.get_rt_slug to return test slugs

@pytest.fixture
def mock_scraper():
    # Patches scraper.scrape_movie with sample RT data
```

### Mocking Approach

- Use `unittest.mock.patch` to replace service functions
- Use `respx` to mock httpx requests for Wikidata/RT
- Each fixture returns predictable test data
- Tests can override fixtures for specific scenarios (cache miss, scrape failure, etc.)

### Sample Mock Data

```python
MOCK_MOVIE = {
    "rt_url": "https://www.rottentomatoes.com/m/the_dark_knight",
    "title": "The Dark Knight",
    "year": 2008,
    "critic_score": 94,
    "audience_score": 94,
    "critic_rating": "certified_fresh",
    "audience_rating": "upright",
    "consensus": "Dark, complex, and unforgettable...",
}
```

## Test Cases

### Unit Tests (~12 tests)

| File | Tests |
|------|-------|
| `test_auth.py` | Valid key passes, invalid key fails, inactive key fails, rate limit exceeded, admin check |
| `test_cache.py` | Fresh cache (< 7 days), stale cache (> 7 days), TTL boundary |
| `test_browse_options.py` | URL building with filters, invalid param rejection, all filter combos |
| `test_curated_lists.py` | Known slug returns URL, unknown slug returns None |

### Integration Tests (~30 tests)

| File | Tests |
|------|-------|
| `test_movie_endpoint.py` | Cache hit, cache miss → fetch, invalid IMDB format, not found in Wikidata, scrape failure with stale fallback, scrape failure no cache |
| `test_batch_endpoint.py` | All cached, all fresh fetch, mixed cached/fetch, SSE event format, error events, done summary |
| `test_list_endpoints.py` | Curated list lookup, curated slug not found, browse with filters, browse invalid filter, URL-based fetch, editorial vs browse detection |
| `test_admin_endpoints.py` | Create key, list keys (masked), revoke key, non-admin rejected |
| `test_health.py` | Returns healthy, no auth required |

### Live Tests (~5 tests, skipped in CI)

| File | Tests |
|------|-------|
| `test_live_scraper.py` | Scrape real RT movie page, scrape editorial list, scrape browse page |
| `test_live_wikidata.py` | Query known IMDB ID, query unknown ID |

## GitHub Actions CI

### Workflow: `.github/workflows/test.yml`

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
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov respx
      - name: Run tests
        run: pytest tests/ -v --ignore=tests/live/ --cov=app
```

- Runs on every push to `main` and all PRs
- Skips `tests/live/` directory
- Takes ~30 seconds to run

## Dependencies

### New Dev Dependencies

```
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==4.1.0
respx==0.21.1
```

### pytest.ini

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
filterwarnings = ignore::DeprecationWarning
```

## Running Tests

```bash
# Run all fast tests (unit + integration)
pytest tests/ --ignore=tests/live/ -v

# Run with coverage
pytest tests/ --ignore=tests/live/ --cov=app --cov-report=html

# Run specific test file
pytest tests/integration/test_movie_endpoint.py -v

# Run live tests (hits real RT/Wikidata)
pytest tests/live/ -v
```
