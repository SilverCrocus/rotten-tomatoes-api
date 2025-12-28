from typing import Optional
from datetime import datetime, timedelta
import logging

from app.db.postgres import get_connection
from app.models.schemas import RTMovieData
from app.config import get_settings

logger = logging.getLogger(__name__)

RT_BASE_URL = "https://www.rottentomatoes.com"


class CachedMovie:
    """Represents a cached movie record."""

    def __init__(
        self,
        imdb_id: str,
        rt_slug: str,
        title: str,
        year: Optional[int],
        critic_score: Optional[int],
        audience_score: Optional[int],
        critic_rating: Optional[str],
        audience_rating: Optional[str],
        consensus: Optional[str],
        rt_url: str,
        cached_at: datetime,
    ):
        self.imdb_id = imdb_id
        self.rt_slug = rt_slug
        self.title = title
        self.year = year
        self.critic_score = critic_score
        self.audience_score = audience_score
        self.critic_rating = critic_rating
        self.audience_rating = audience_rating
        self.consensus = consensus
        self.rt_url = rt_url
        self.cached_at = cached_at


async def get_cached(imdb_id: str) -> Optional[CachedMovie]:
    """Get cached RT data for an IMDB ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT imdb_id, rt_slug, title, year, critic_score, audience_score,
                   critic_rating, audience_rating, consensus, rt_url, cached_at
            FROM rt_cache
            WHERE imdb_id = $1
            """,
            imdb_id,
        )

        if row:
            return CachedMovie(
                imdb_id=row["imdb_id"],
                rt_slug=row["rt_slug"],
                title=row["title"],
                year=row["year"],
                critic_score=row["critic_score"],
                audience_score=row["audience_score"],
                critic_rating=row["critic_rating"],
                audience_rating=row["audience_rating"],
                consensus=row["consensus"],
                rt_url=row["rt_url"],
                cached_at=row["cached_at"],
            )

        return None


def is_cache_fresh(cached: CachedMovie) -> bool:
    """Check if cached data is still fresh."""
    settings = get_settings()
    ttl = timedelta(days=settings.cache_ttl_days)
    return datetime.utcnow() - cached.cached_at < ttl


async def upsert_cache(imdb_id: str, rt_data: RTMovieData) -> CachedMovie:
    """Insert or update cached RT data."""
    rt_url = f"{RT_BASE_URL}/{rt_data.rt_slug}"
    now = datetime.utcnow()

    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO rt_cache (
                imdb_id, rt_slug, title, year, critic_score, audience_score,
                critic_rating, audience_rating, consensus, rt_url, cached_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11)
            ON CONFLICT (imdb_id) DO UPDATE SET
                rt_slug = $2,
                title = $3,
                year = $4,
                critic_score = $5,
                audience_score = $6,
                critic_rating = $7,
                audience_rating = $8,
                consensus = $9,
                rt_url = $10,
                cached_at = $11,
                updated_at = $11
            """,
            imdb_id,
            rt_data.rt_slug,
            rt_data.title,
            rt_data.year,
            rt_data.critic_score,
            rt_data.audience_score,
            rt_data.critic_rating,
            rt_data.audience_rating,
            rt_data.consensus,
            rt_url,
            now,
        )

    return CachedMovie(
        imdb_id=imdb_id,
        rt_slug=rt_data.rt_slug,
        title=rt_data.title,
        year=rt_data.year,
        critic_score=rt_data.critic_score,
        audience_score=rt_data.audience_score,
        critic_rating=rt_data.critic_rating,
        audience_rating=rt_data.audience_rating,
        consensus=rt_data.consensus,
        rt_url=rt_url,
        cached_at=now,
    )
