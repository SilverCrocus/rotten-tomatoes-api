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
