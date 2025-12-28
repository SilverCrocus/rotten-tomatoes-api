import re
from fastapi import APIRouter, HTTPException
import logging

from app.models.schemas import RTMovieResponse, HealthResponse, ErrorResponse
from app.services import wikidata, scraper, cache

logger = logging.getLogger(__name__)

router = APIRouter()

# IMDB ID pattern: tt followed by 7-8 digits
IMDB_ID_PATTERN = re.compile(r"^tt\d{7,8}$")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy")


@router.get(
    "/movie/{imdb_id}",
    response_model=RTMovieResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid IMDB ID format"},
        404: {"model": ErrorResponse, "description": "Movie not found"},
        502: {"model": ErrorResponse, "description": "Failed to fetch RT data"},
    },
)
async def get_movie(imdb_id: str):
    """
    Get Rotten Tomatoes data for a movie by IMDB ID.

    - **imdb_id**: IMDB ID (e.g., tt0468569)
    """
    # Validate IMDB ID format
    imdb_id = imdb_id.lower()
    if not IMDB_ID_PATTERN.match(imdb_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid IMDB ID format: {imdb_id}. Expected format: tt0000000",
        )

    # Check cache first
    cached = await cache.get_cached(imdb_id)
    if cached and cache.is_cache_fresh(cached):
        logger.info(f"Cache hit for {imdb_id}")
        return RTMovieResponse(
            imdbId=cached.imdb_id,
            rtUrl=cached.rt_url,
            title=cached.title,
            year=cached.year,
            criticScore=cached.critic_score,
            audienceScore=cached.audience_score,
            criticRating=cached.critic_rating,
            audienceRating=cached.audience_rating,
            consensus=cached.consensus,
            cachedAt=cached.cached_at,
        )

    # Query Wikidata for RT slug
    logger.info(f"Cache miss for {imdb_id}, querying Wikidata")
    rt_slug = await wikidata.get_rt_slug(imdb_id)

    if not rt_slug:
        # Return stale cache if available
        if cached:
            logger.warning(f"Wikidata miss, returning stale cache for {imdb_id}")
            return RTMovieResponse(
                imdbId=cached.imdb_id,
                rtUrl=cached.rt_url,
                title=cached.title,
                year=cached.year,
                criticScore=cached.critic_score,
                audienceScore=cached.audience_score,
                criticRating=cached.critic_rating,
                audienceRating=cached.audience_rating,
                consensus=cached.consensus,
                cachedAt=cached.cached_at,
            )

        raise HTTPException(
            status_code=404,
            detail=f"Movie not found in Wikidata: {imdb_id}",
        )

    # Scrape RT page
    logger.info(f"Scraping RT for {imdb_id} ({rt_slug})")
    rt_data = await scraper.scrape_movie(rt_slug)

    if not rt_data:
        # Return stale cache if available
        if cached:
            logger.warning(f"Scrape failed, returning stale cache for {imdb_id}")
            return RTMovieResponse(
                imdbId=cached.imdb_id,
                rtUrl=cached.rt_url,
                title=cached.title,
                year=cached.year,
                criticScore=cached.critic_score,
                audienceScore=cached.audience_score,
                criticRating=cached.critic_rating,
                audienceRating=cached.audience_rating,
                consensus=cached.consensus,
                cachedAt=cached.cached_at,
            )

        raise HTTPException(
            status_code=502,
            detail=f"Failed to scrape Rotten Tomatoes for {imdb_id}",
        )

    # Cache and return
    cached = await cache.upsert_cache(imdb_id, rt_data)
    logger.info(f"Cached RT data for {imdb_id}")

    return RTMovieResponse(
        imdbId=cached.imdb_id,
        rtUrl=cached.rt_url,
        title=cached.title,
        year=cached.year,
        criticScore=cached.critic_score,
        audienceScore=cached.audience_score,
        criticRating=cached.critic_rating,
        audienceRating=cached.audience_rating,
        consensus=cached.consensus,
        cachedAt=cached.cached_at,
    )
