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
