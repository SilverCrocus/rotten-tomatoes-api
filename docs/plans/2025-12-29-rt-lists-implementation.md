# RT Editorial Lists Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add endpoints to fetch movies from RT editorial lists and browse filters.

**Architecture:** New list scraper services parse RT editorial and browse pages. Results cached in PostgreSQL with 7-day TTL. Curated lists stored in a config registry. All endpoints return basic movie identifiers (RT slug, title, year).

**Tech Stack:** FastAPI, asyncpg, httpx, BeautifulSoup, Pydantic

---

## Task 1: Add Database Table for List Cache

**Files:**
- Modify: `app/db/postgres.py:23-64`

**Step 1: Add list_cache table creation to init_db**

Add after the existing `rt_cache` table creation (around line 44):

```python
        # List cache table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS list_cache (
                id SERIAL PRIMARY KEY,
                url_hash VARCHAR(64) UNIQUE NOT NULL,
                source_url TEXT NOT NULL,
                title VARCHAR(500),
                movies JSONB NOT NULL DEFAULT '[]',
                cached_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_list_cache_url_hash
            ON list_cache(url_hash)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_list_cache_cached_at
            ON list_cache(cached_at)
        """)
```

**Step 2: Verify by running the app locally**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.db.postgres import init_db; import asyncio; asyncio.run(init_db())"`

Expected: No errors (table created)

**Step 3: Commit**

```bash
git add app/db/postgres.py
git commit -m "feat: add list_cache table for RT lists"
```

---

## Task 2: Add Pydantic Schemas for List Endpoints

**Files:**
- Modify: `app/models/schemas.py`

**Step 1: Add list-related schemas at the end of the file**

```python
# =============================================================================
# List Endpoint Schemas
# =============================================================================


class ListMovie(BaseModel):
    """A movie entry in a list."""

    rt_slug: str = Field(..., alias="rtSlug")
    title: str
    year: Optional[int] = None

    class Config:
        populate_by_name = True


class ListResponse(BaseModel):
    """Response model for list endpoints."""

    source: str = Field(..., description="Source RT URL")
    title: str = Field(..., description="List title")
    movie_count: int = Field(..., alias="movieCount")
    movies: list[ListMovie]
    cached_at: Optional[datetime] = Field(None, alias="cachedAt")
    stale: bool = Field(False, description="True if cache is expired")

    class Config:
        populate_by_name = True


class CuratedListInfo(BaseModel):
    """Info about an available curated list."""

    slug: str
    title: str
    description: Optional[str] = None


class CuratedListsResponse(BaseModel):
    """Response for listing available curated lists."""

    lists: list[CuratedListInfo]


class BrowseOptionsResponse(BaseModel):
    """Response for available browse filter options."""

    certifications: list[str]
    genres: list[str]
    affiliates: list[str]
    sorts: list[str]
    types: list[str]
    audience_ratings: list[str] = Field(..., alias="audienceRatings")

    class Config:
        populate_by_name = True
```

**Step 2: Verify syntax**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.models.schemas import ListResponse, CuratedListsResponse, BrowseOptionsResponse; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add app/models/schemas.py
git commit -m "feat: add Pydantic schemas for list endpoints"
```

---

## Task 3: Create Curated Lists Registry

**Files:**
- Create: `app/services/curated_lists.py`

**Step 1: Create the curated lists registry file**

```python
"""Registry of known RT editorial lists."""

from typing import Optional

# Curated editorial lists - add more as needed
CURATED_LISTS: dict[str, dict] = {
    "best-horror": {
        "title": "Best Horror Movies of All Time",
        "description": "RT's definitive ranking of the greatest horror films",
        "url": "https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/",
    },
    "best-2024": {
        "title": "Best Movies of 2024",
        "description": "The top-rated films of 2024",
        "url": "https://editorial.rottentomatoes.com/guide/best-movies-of-2024/",
    },
    "best-comedies": {
        "title": "Best Comedies of All Time",
        "description": "The funniest movies ever made according to critics",
        "url": "https://editorial.rottentomatoes.com/guide/best-comedies/",
    },
    "best-action": {
        "title": "Best Action Movies of All Time",
        "description": "The greatest action films ranked",
        "url": "https://editorial.rottentomatoes.com/guide/best-action-movies/",
    },
    "best-sci-fi": {
        "title": "Best Sci-Fi Movies of All Time",
        "description": "The greatest science fiction films",
        "url": "https://editorial.rottentomatoes.com/guide/best-sci-fi-movies/",
    },
    "best-animated": {
        "title": "Best Animated Movies of All Time",
        "description": "The greatest animated films ranked",
        "url": "https://editorial.rottentomatoes.com/guide/best-animated-movies/",
    },
}


def get_curated_list(slug: str) -> Optional[dict]:
    """Get a curated list by slug."""
    return CURATED_LISTS.get(slug)


def get_all_curated_lists() -> list[dict]:
    """Get all available curated lists."""
    return [
        {"slug": slug, "title": info["title"], "description": info.get("description")}
        for slug, info in CURATED_LISTS.items()
    ]
```

**Step 2: Verify import**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.services.curated_lists import get_all_curated_lists; print(len(get_all_curated_lists()), 'lists')"`

Expected: `6 lists`

**Step 3: Commit**

```bash
git add app/services/curated_lists.py
git commit -m "feat: add curated lists registry"
```

---

## Task 4: Create Browse Filter Options

**Files:**
- Create: `app/services/browse_options.py`

**Step 1: Create the browse options configuration file**

```python
"""Browse filter options for RT browse pages."""

# Valid filter values - these map to RT's URL parameters
BROWSE_OPTIONS = {
    "certifications": ["certified_fresh", "fresh", "rotten"],
    "genres": [
        "action",
        "adventure",
        "animation",
        "anime",
        "biography",
        "comedy",
        "crime",
        "documentary",
        "drama",
        "fantasy",
        "history",
        "horror",
        "music",
        "mystery",
        "romance",
        "sci_fi",
        "sport",
        "thriller",
        "war",
        "western",
    ],
    "affiliates": [
        "netflix",
        "amazon_prime",
        "hulu",
        "max",
        "disney_plus",
        "paramount_plus",
        "apple_tv_plus",
        "peacock",
    ],
    "sorts": [
        "popular",
        "newest",
        "a_z",
        "critic_highest",
        "critic_lowest",
        "audience_highest",
        "audience_lowest",
    ],
    "types": [
        "movies_at_home",
        "movies_in_theaters",
        "movies_coming_soon",
    ],
    "audience_ratings": ["upright", "spilled"],
}


def get_browse_options() -> dict:
    """Get all available browse filter options."""
    return BROWSE_OPTIONS.copy()


def validate_browse_params(
    certification: str | None = None,
    genre: str | None = None,
    affiliate: str | None = None,
    sort: str | None = None,
    browse_type: str | None = None,
    audience: str | None = None,
) -> tuple[bool, str | None]:
    """
    Validate browse parameters.

    Returns:
        (is_valid, error_message)
    """
    if certification and certification not in BROWSE_OPTIONS["certifications"]:
        return False, f"Invalid certification: {certification}. Valid: {BROWSE_OPTIONS['certifications']}"

    if genre and genre not in BROWSE_OPTIONS["genres"]:
        return False, f"Invalid genre: {genre}. Valid: {BROWSE_OPTIONS['genres']}"

    if affiliate and affiliate not in BROWSE_OPTIONS["affiliates"]:
        return False, f"Invalid affiliate: {affiliate}. Valid: {BROWSE_OPTIONS['affiliates']}"

    if sort and sort not in BROWSE_OPTIONS["sorts"]:
        return False, f"Invalid sort: {sort}. Valid: {BROWSE_OPTIONS['sorts']}"

    if browse_type and browse_type not in BROWSE_OPTIONS["types"]:
        return False, f"Invalid type: {browse_type}. Valid: {BROWSE_OPTIONS['types']}"

    if audience and audience not in BROWSE_OPTIONS["audience_ratings"]:
        return False, f"Invalid audience: {audience}. Valid: {BROWSE_OPTIONS['audience_ratings']}"

    return True, None


def build_browse_url(
    certification: str | None = None,
    genre: str | None = None,
    affiliate: str | None = None,
    sort: str | None = None,
    browse_type: str = "movies_at_home",
    audience: str | None = None,
) -> str:
    """
    Build RT browse URL from filter parameters.

    Example output:
    https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh~genres:horror~sort:popular
    """
    base = f"https://www.rottentomatoes.com/browse/{browse_type}"

    filters = []

    if certification:
        filters.append(f"critics:{certification}")

    if audience:
        filters.append(f"audience:{audience}")

    if genre:
        filters.append(f"genres:{genre}")

    if affiliate:
        filters.append(f"affiliates:{affiliate}")

    if sort:
        filters.append(f"sort:{sort}")

    if filters:
        return f"{base}/{'/'.join(filters)}"

    return base
```

**Step 2: Verify import and URL building**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.services.browse_options import build_browse_url; print(build_browse_url(certification='certified_fresh', genre='horror', sort='popular'))"`

Expected: URL like `https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh/genres:horror/sort:popular`

**Step 3: Commit**

```bash
git add app/services/browse_options.py
git commit -m "feat: add browse filter options and URL builder"
```

---

## Task 5: Create List Scraper - Editorial Pages

**Files:**
- Create: `app/services/list_scraper.py`

**Step 1: Create the list scraper service with editorial scraper**

```python
"""Scraper for RT editorial lists and browse pages."""

import httpx
import asyncio
import re
import json
import hashlib
from typing import Optional
from bs4 import BeautifulSoup
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

RT_BASE_URL = "https://www.rottentomatoes.com"

# Rate limiting semaphore - allow 2 concurrent RT requests
_rt_semaphore = asyncio.Semaphore(2)


class ListMovie:
    """A movie from a list."""

    def __init__(self, rt_slug: str, title: str, year: Optional[int] = None):
        self.rt_slug = rt_slug
        self.title = title
        self.year = year

    def to_dict(self) -> dict:
        return {"rtSlug": self.rt_slug, "title": self.title, "year": self.year}


class ListResult:
    """Result of scraping a list."""

    def __init__(
        self,
        source_url: str,
        title: str,
        movies: list[ListMovie],
    ):
        self.source_url = source_url
        self.title = title
        self.movies = movies

    @property
    def url_hash(self) -> str:
        """Generate hash for cache key."""
        normalized = self.source_url.lower().rstrip("/")
        return hashlib.sha256(normalized.encode()).hexdigest()


async def _fetch_page(url: str) -> Optional[str]:
    """Fetch an RT page with rate limiting."""
    settings = get_settings()

    async with _rt_semaphore:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    },
                    follow_redirects=True,
                )
                response.raise_for_status()

            await asyncio.sleep(settings.rt_request_delay)
            return response.text

        except httpx.HTTPStatusError as e:
            logger.error(f"RT HTTP error for {url}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"RT request error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None


async def scrape_editorial_list(url: str) -> Optional[ListResult]:
    """
    Scrape an RT editorial list page.

    Editorial pages are at URLs like:
    https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/
    """
    html = await _fetch_page(url)
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "lxml")
        movies = []
        title = ""

        # Get list title
        title_elem = soup.find("h1")
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Editorial pages have movie rows with links to /m/slug
        # Look for movie links in various formats

        # Method 1: Look for links with /m/ pattern
        movie_links = soup.find_all("a", href=re.compile(r"/m/[^/\"]+"))
        seen_slugs = set()

        for link in movie_links:
            href = link.get("href", "")
            match = re.search(r"/m/([^/?\"]+)", href)
            if not match:
                continue

            slug = match.group(1)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # Try to get title from link text or nearby elements
            movie_title = link.get_text(strip=True)
            if not movie_title or len(movie_title) < 2:
                # Try parent element
                parent = link.find_parent("div")
                if parent:
                    title_elem = parent.find(["h2", "h3", "strong"])
                    if title_elem:
                        movie_title = title_elem.get_text(strip=True)

            # Try to extract year
            year = None
            year_match = re.search(r"\((\d{4})\)", movie_title)
            if year_match:
                year = int(year_match.group(1))
                movie_title = re.sub(r"\s*\(\d{4}\)\s*", "", movie_title).strip()

            if movie_title:
                movies.append(ListMovie(rt_slug=f"m/{slug}", title=movie_title, year=year))

        if not movies:
            logger.warning(f"No movies found in editorial list: {url}")
            return None

        return ListResult(source_url=url, title=title, movies=movies)

    except Exception as e:
        logger.error(f"Error parsing editorial list {url}: {e}")
        return None


async def scrape_browse_page(url: str) -> Optional[ListResult]:
    """
    Scrape an RT browse page.

    Browse pages are at URLs like:
    https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh
    """
    html = await _fetch_page(url)
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "lxml")
        movies = []
        title = "Browse Results"

        # Try to build a title from the URL path
        if "/browse/" in url:
            parts = url.split("/browse/")[1].split("/")
            title_parts = []
            for part in parts:
                if ":" in part:
                    key, val = part.split(":", 1)
                    title_parts.append(val.replace("_", " ").title())
                else:
                    title_parts.append(part.replace("_", " ").title())
            if title_parts:
                title = " - ".join(title_parts)

        # Browse pages embed movie data in JSON within script tags
        # Look for the hydration data
        scripts = soup.find_all("script")
        for script in scripts:
            if not script.string:
                continue

            # Look for movie data in various JSON structures
            # RT uses different formats, try to find movie arrays

            # Pattern 1: Look for items array with movie objects
            items_match = re.search(r'"items"\s*:\s*(\[[^\]]*\])', script.string)
            if items_match:
                try:
                    items = json.loads(items_match.group(1))
                    for item in items:
                        if isinstance(item, dict):
                            slug = item.get("mediaUrl", "").replace("/m/", "")
                            if not slug:
                                slug = item.get("slug", "")
                            title_text = item.get("title", "")
                            year = item.get("releaseYear") or item.get("year")
                            if slug and title_text:
                                movies.append(ListMovie(
                                    rt_slug=f"m/{slug}" if not slug.startswith("m/") else slug,
                                    title=title_text,
                                    year=year,
                                ))
                except json.JSONDecodeError:
                    pass

        # Fallback: parse HTML directly for movie tiles
        if not movies:
            # Look for tile elements with movie data
            tiles = soup.find_all(["a", "div"], {"data-qa": re.compile(r"discovery-media")})
            for tile in tiles:
                href = tile.get("href", "")
                match = re.search(r"/m/([^/?]+)", href)
                if match:
                    slug = match.group(1)
                    title_elem = tile.find(["span", "div"], {"data-qa": "discovery-media-list-item-title"})
                    movie_title = title_elem.get_text(strip=True) if title_elem else slug.replace("_", " ").title()
                    movies.append(ListMovie(rt_slug=f"m/{slug}", title=movie_title, year=None))

        # Another fallback: look for any /m/ links in tile containers
        if not movies:
            movie_links = soup.select('a[href*="/m/"]')
            seen_slugs = set()
            for link in movie_links:
                href = link.get("href", "")
                match = re.search(r"/m/([^/?]+)", href)
                if match:
                    slug = match.group(1)
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    movie_title = link.get_text(strip=True) or slug.replace("_", " ").title()
                    if len(movie_title) > 2:
                        movies.append(ListMovie(rt_slug=f"m/{slug}", title=movie_title, year=None))

        if not movies:
            logger.warning(f"No movies found in browse page: {url}")
            return None

        return ListResult(source_url=url, title=title, movies=movies)

    except Exception as e:
        logger.error(f"Error parsing browse page {url}: {e}")
        return None


def detect_url_type(url: str) -> str:
    """
    Detect the type of RT URL.

    Returns: 'editorial', 'browse', or 'unknown'
    """
    url_lower = url.lower()

    if "editorial.rottentomatoes.com" in url_lower or "/guide/" in url_lower:
        return "editorial"

    if "/browse/" in url_lower:
        return "browse"

    return "unknown"


async def scrape_list(url: str) -> Optional[ListResult]:
    """
    Scrape a list from any supported RT URL.

    Automatically detects URL type and uses appropriate scraper.
    """
    url_type = detect_url_type(url)

    if url_type == "editorial":
        return await scrape_editorial_list(url)
    elif url_type == "browse":
        return await scrape_browse_page(url)
    else:
        logger.error(f"Unknown URL type: {url}")
        return None
```

**Step 2: Verify import**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.services.list_scraper import scrape_list, detect_url_type; print(detect_url_type('https://editorial.rottentomatoes.com/guide/best-horror-movies/'))"`

Expected: `editorial`

**Step 3: Commit**

```bash
git add app/services/list_scraper.py
git commit -m "feat: add list scraper for editorial and browse pages"
```

---

## Task 6: Create List Cache Service

**Files:**
- Create: `app/services/list_cache.py`

**Step 1: Create the list cache service**

```python
"""Cache service for RT lists."""

import json
import hashlib
from typing import Optional
from datetime import datetime, timedelta
import logging

from app.db.postgres import get_connection
from app.config import get_settings
from app.services.list_scraper import ListResult, ListMovie

logger = logging.getLogger(__name__)


class CachedList:
    """Represents a cached list."""

    def __init__(
        self,
        url_hash: str,
        source_url: str,
        title: str,
        movies: list[dict],
        cached_at: datetime,
    ):
        self.url_hash = url_hash
        self.source_url = source_url
        self.title = title
        self.movies = movies
        self.cached_at = cached_at


def _normalize_url(url: str) -> str:
    """Normalize URL for consistent hashing."""
    # Remove trailing slashes, lowercase
    normalized = url.lower().rstrip("/")
    # Remove common tracking params
    for param in ["?ref=", "&ref=", "?utm_", "&utm_"]:
        if param in normalized:
            normalized = normalized.split(param)[0]
    return normalized


def _hash_url(url: str) -> str:
    """Generate hash for URL."""
    normalized = _normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()


async def get_cached_list(url: str) -> Optional[CachedList]:
    """Get cached list data for a URL."""
    url_hash = _hash_url(url)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT url_hash, source_url, title, movies, cached_at
            FROM list_cache
            WHERE url_hash = $1
            """,
            url_hash,
        )

        if row:
            return CachedList(
                url_hash=row["url_hash"],
                source_url=row["source_url"],
                title=row["title"],
                movies=row["movies"],  # JSONB auto-converts to list
                cached_at=row["cached_at"],
            )

        return None


def is_list_cache_fresh(cached: CachedList) -> bool:
    """Check if cached list data is still fresh."""
    settings = get_settings()
    ttl = timedelta(days=settings.cache_ttl_days)
    return datetime.utcnow() - cached.cached_at < ttl


async def upsert_list_cache(result: ListResult) -> CachedList:
    """Insert or update cached list data."""
    url_hash = _hash_url(result.source_url)
    movies_json = [m.to_dict() for m in result.movies]
    now = datetime.utcnow()

    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO list_cache (url_hash, source_url, title, movies, cached_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (url_hash) DO UPDATE SET
                source_url = $2,
                title = $3,
                movies = $4,
                cached_at = $5
            """,
            url_hash,
            result.source_url,
            result.title,
            json.dumps(movies_json),
            now,
        )

    return CachedList(
        url_hash=url_hash,
        source_url=result.source_url,
        title=result.title,
        movies=movies_json,
        cached_at=now,
    )
```

**Step 2: Verify import**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.services.list_cache import get_cached_list, is_list_cache_fresh; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add app/services/list_cache.py
git commit -m "feat: add list cache service"
```

---

## Task 7: Add List Routes - URL-based Endpoint

**Files:**
- Modify: `app/api/routes.py`

**Step 1: Add imports at top of routes.py**

Add to the existing imports section:

```python
from app.models.schemas import (
    RTMovieResponse,
    HealthResponse,
    ErrorResponse,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyListResponse,
    BatchRequest,
    BatchMovieEvent,
    BatchErrorEvent,
    BatchDoneEvent,
    # New list schemas
    ListResponse,
    ListMovie,
    CuratedListInfo,
    CuratedListsResponse,
    BrowseOptionsResponse,
)
from app.services import wikidata, scraper, cache, auth, list_scraper, list_cache
from app.services.curated_lists import get_curated_list, get_all_curated_lists
from app.services.browse_options import get_browse_options, validate_browse_params, build_browse_url
```

**Step 2: Add URL-based list endpoint after the batch endpoint**

Add after the batch endpoint (around line 313):

```python
# =============================================================================
# List Endpoints
# =============================================================================


@router.get(
    "/list",
    response_model=ListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or unsupported URL"},
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        502: {"model": ErrorResponse, "description": "Failed to fetch RT list"},
    },
    tags=["Lists"],
)
async def get_list_by_url(url: str, api_key: APIKey = Depends(get_api_key)):
    """
    Fetch movies from an RT list by URL.

    Supports:
    - Editorial lists: https://editorial.rottentomatoes.com/guide/best-horror-movies/
    - Browse pages: https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh
    """
    # Validate URL type
    url_type = list_scraper.detect_url_type(url)
    if url_type == "unknown":
        raise HTTPException(
            status_code=400,
            detail="Unsupported RT URL format. Must be /editorial/*, /guide/*, or /browse/* URL",
        )

    # Check cache first
    cached = await list_cache.get_cached_list(url)
    if cached and list_cache.is_list_cache_fresh(cached):
        logger.info(f"List cache hit for {url}")
        return ListResponse(
            source=cached.source_url,
            title=cached.title,
            movieCount=len(cached.movies),
            movies=[ListMovie(**m) for m in cached.movies],
            cachedAt=cached.cached_at,
            stale=False,
        )

    # Scrape the list
    logger.info(f"List cache miss for {url}, scraping")
    result = await list_scraper.scrape_list(url)

    if not result:
        # Return stale cache if available
        if cached:
            logger.warning(f"Scrape failed, returning stale cache for {url}")
            return ListResponse(
                source=cached.source_url,
                title=cached.title,
                movieCount=len(cached.movies),
                movies=[ListMovie(**m) for m in cached.movies],
                cachedAt=cached.cached_at,
                stale=True,
            )

        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch RT list from {url}",
        )

    # Cache and return
    cached = await list_cache.upsert_list_cache(result)
    logger.info(f"Cached list from {url} with {len(cached.movies)} movies")

    return ListResponse(
        source=cached.source_url,
        title=cached.title,
        movieCount=len(cached.movies),
        movies=[ListMovie(**m) for m in cached.movies],
        cachedAt=cached.cached_at,
        stale=False,
    )
```

**Step 3: Verify syntax**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.api.routes import router; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add URL-based list endpoint"
```

---

## Task 8: Add Curated Lists Endpoints

**Files:**
- Modify: `app/api/routes.py`

**Step 1: Add curated lists endpoints after the URL-based endpoint**

```python
@router.get(
    "/lists/curated",
    response_model=CuratedListsResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    tags=["Lists"],
)
async def list_curated_lists(api_key: APIKey = Depends(get_api_key)):
    """
    List all available curated editorial lists.
    """
    lists = get_all_curated_lists()
    return CuratedListsResponse(
        lists=[CuratedListInfo(**lst) for lst in lists]
    )


@router.get(
    "/lists/curated/{slug}",
    response_model=ListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Unknown list slug"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        502: {"model": ErrorResponse, "description": "Failed to fetch RT list"},
    },
    tags=["Lists"],
)
async def get_curated_list_by_slug(slug: str, api_key: APIKey = Depends(get_api_key)):
    """
    Fetch movies from a curated editorial list by slug.

    Use GET /lists/curated to see available lists.
    """
    list_info = get_curated_list(slug)
    if not list_info:
        available = [lst["slug"] for lst in get_all_curated_lists()]
        raise HTTPException(
            status_code=404,
            detail=f"Unknown list: {slug}. Available: {available}",
        )

    url = list_info["url"]

    # Check cache first
    cached = await list_cache.get_cached_list(url)
    if cached and list_cache.is_list_cache_fresh(cached):
        logger.info(f"Curated list cache hit for {slug}")
        return ListResponse(
            source=cached.source_url,
            title=cached.title,
            movieCount=len(cached.movies),
            movies=[ListMovie(**m) for m in cached.movies],
            cachedAt=cached.cached_at,
            stale=False,
        )

    # Scrape the list
    logger.info(f"Curated list cache miss for {slug}, scraping")
    result = await list_scraper.scrape_editorial_list(url)

    if not result:
        if cached:
            logger.warning(f"Scrape failed, returning stale cache for {slug}")
            return ListResponse(
                source=cached.source_url,
                title=cached.title,
                movieCount=len(cached.movies),
                movies=[ListMovie(**m) for m in cached.movies],
                cachedAt=cached.cached_at,
                stale=True,
            )

        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch RT list: {slug}",
        )

    # Cache and return
    cached = await list_cache.upsert_list_cache(result)
    logger.info(f"Cached curated list {slug} with {len(cached.movies)} movies")

    return ListResponse(
        source=cached.source_url,
        title=cached.title,
        movieCount=len(cached.movies),
        movies=[ListMovie(**m) for m in cached.movies],
        cachedAt=cached.cached_at,
        stale=False,
    )
```

**Step 2: Verify syntax**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.api.routes import router; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add curated lists endpoints"
```

---

## Task 9: Add Browse Endpoints

**Files:**
- Modify: `app/api/routes.py`

**Step 1: Add browse endpoints**

```python
@router.get(
    "/lists/browse/options",
    response_model=BrowseOptionsResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    tags=["Lists"],
)
async def get_browse_filter_options(api_key: APIKey = Depends(get_api_key)):
    """
    Get available browse filter options.

    Use these values with GET /lists/browse to query RT.
    """
    options = get_browse_options()
    return BrowseOptionsResponse(
        certifications=options["certifications"],
        genres=options["genres"],
        affiliates=options["affiliates"],
        sorts=options["sorts"],
        types=options["types"],
        audienceRatings=options["audience_ratings"],
    )


@router.get(
    "/lists/browse",
    response_model=ListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid filter parameter"},
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        502: {"model": ErrorResponse, "description": "Failed to fetch RT browse results"},
    },
    tags=["Lists"],
)
async def browse_movies(
    api_key: APIKey = Depends(get_api_key),
    certification: Optional[str] = None,
    genre: Optional[str] = None,
    affiliate: Optional[str] = None,
    sort: Optional[str] = None,
    type: str = "movies_at_home",
    audience: Optional[str] = None,
):
    """
    Browse RT movies with filters.

    Use GET /lists/browse/options to see valid filter values.

    Examples:
    - /lists/browse?certification=certified_fresh&genre=horror
    - /lists/browse?affiliate=netflix&sort=popular
    """
    # Validate parameters
    is_valid, error = validate_browse_params(
        certification=certification,
        genre=genre,
        affiliate=affiliate,
        sort=sort,
        browse_type=type,
        audience=audience,
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Build URL
    url = build_browse_url(
        certification=certification,
        genre=genre,
        affiliate=affiliate,
        sort=sort,
        browse_type=type,
        audience=audience,
    )

    # Check cache first
    cached = await list_cache.get_cached_list(url)
    if cached and list_cache.is_list_cache_fresh(cached):
        logger.info(f"Browse cache hit for {url}")
        return ListResponse(
            source=cached.source_url,
            title=cached.title,
            movieCount=len(cached.movies),
            movies=[ListMovie(**m) for m in cached.movies],
            cachedAt=cached.cached_at,
            stale=False,
        )

    # Scrape browse page
    logger.info(f"Browse cache miss, scraping {url}")
    result = await list_scraper.scrape_browse_page(url)

    if not result:
        if cached:
            logger.warning(f"Browse scrape failed, returning stale cache")
            return ListResponse(
                source=cached.source_url,
                title=cached.title,
                movieCount=len(cached.movies),
                movies=[ListMovie(**m) for m in cached.movies],
                cachedAt=cached.cached_at,
                stale=True,
            )

        # Empty results are valid for browse
        return ListResponse(
            source=url,
            title="Browse Results",
            movieCount=0,
            movies=[],
            cachedAt=None,
            stale=False,
        )

    # Cache and return
    cached = await list_cache.upsert_list_cache(result)
    logger.info(f"Cached browse results with {len(cached.movies)} movies")

    return ListResponse(
        source=cached.source_url,
        title=cached.title,
        movieCount=len(cached.movies),
        movies=[ListMovie(**m) for m in cached.movies],
        cachedAt=cached.cached_at,
        stale=False,
    )
```

**Step 2: Add Optional import if not present**

Make sure this import is at the top of the file:

```python
from typing import Optional
```

**Step 3: Verify syntax**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.api.routes import router; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add browse filter endpoints"
```

---

## Task 10: Update Services __init__.py

**Files:**
- Modify: `app/services/__init__.py`

**Step 1: Check current content and add new services**

Read the file first, then add the new imports:

```python
from app.services import (
    wikidata,
    scraper,
    cache,
    auth,
    list_scraper,
    list_cache,
    curated_lists,
    browse_options,
)
```

**Step 2: Verify imports work**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && python -c "from app.services import list_scraper, list_cache; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add app/services/__init__.py
git commit -m "feat: export new list services"
```

---

## Task 11: Manual Testing

**Step 1: Start the server locally**

Run: `cd /Users/diyagamah/Documents/rt_api && source .venv/bin/activate && uvicorn app.main:app --reload`

**Step 2: Test browse options endpoint**

Run in another terminal:
```bash
curl -X GET "http://localhost:8000/api/v1/lists/browse/options" \
  -H "X-API-Key: YOUR_API_KEY"
```

Expected: JSON with filter options

**Step 3: Test curated lists endpoint**

```bash
curl -X GET "http://localhost:8000/api/v1/lists/curated" \
  -H "X-API-Key: YOUR_API_KEY"
```

Expected: JSON with available curated lists

**Step 4: Test browse endpoint**

```bash
curl -X GET "http://localhost:8000/api/v1/lists/browse?certification=certified_fresh&genre=horror" \
  -H "X-API-Key: YOUR_API_KEY"
```

Expected: JSON with horror movies

**Step 5: Check Swagger docs**

Visit: `http://localhost:8000/docs`

Verify all new endpoints appear under "Lists" tag.

---

## Task 12: Update README Documentation

**Files:**
- Modify: `README.md`

**Step 1: Add Lists section after the Batch section**

Add documentation for the new list endpoints including:
- GET /list?url=...
- GET /lists/curated
- GET /lists/curated/{slug}
- GET /lists/browse/options
- GET /lists/browse

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add list endpoints documentation"
```

---

## Summary

This plan creates:
1. **Database table** `list_cache` for caching list results
2. **Schemas** for list responses (`ListResponse`, `ListMovie`, etc.)
3. **Curated lists registry** with predefined editorial lists
4. **Browse options** configuration for filter validation
5. **List scraper** for editorial and browse pages
6. **List cache service** for PostgreSQL caching
7. **API routes** for all list endpoints
8. **Documentation** updates

All commits are atomic and build on each other sequentially.
