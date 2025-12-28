import re
from fastapi import APIRouter, HTTPException, Depends
import logging

from app.models.schemas import (
    RTMovieResponse,
    HealthResponse,
    ErrorResponse,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyListResponse,
)
from app.services import wikidata, scraper, cache, auth
from app.api.dependencies import get_api_key, get_admin_api_key
from app.services.auth import APIKey

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
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Movie not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        502: {"model": ErrorResponse, "description": "Failed to fetch RT data"},
    },
)
async def get_movie(imdb_id: str, api_key: APIKey = Depends(get_api_key)):
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


# =============================================================================
# Admin Endpoints (require admin API key)
# =============================================================================


@router.post(
    "/admin/keys",
    response_model=APIKeyResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
    },
    tags=["Admin"],
)
async def create_api_key(
    request: APIKeyCreate,
    admin_key: APIKey = Depends(get_admin_api_key),
):
    """
    Create a new API key. Requires admin access.

    - **name**: A descriptive name for the key
    - **isAdmin**: Whether this key has admin privileges (default: false)
    - **rateLimit**: Custom rate limit in requests/hour (default: 500)
    """
    new_key = await auth.create_api_key(
        name=request.name,
        is_admin=request.is_admin,
        rate_limit=request.rate_limit,
    )

    logger.info(f"Admin {admin_key.name} created API key: {new_key.name}")

    return APIKeyResponse(
        id=new_key.id,
        key=new_key.key,  # Full key only shown on creation
        name=new_key.name,
        isAdmin=new_key.is_admin,
        rateLimit=new_key.rate_limit,
        requestsCount=new_key.requests_count,
        isActive=new_key.is_active,
        createdAt=new_key.created_at,
    )


@router.get(
    "/admin/keys",
    response_model=APIKeyListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
    },
    tags=["Admin"],
)
async def list_api_keys(admin_key: APIKey = Depends(get_admin_api_key)):
    """
    List all API keys. Requires admin access.
    Keys are masked for security (only first 8 and last 4 characters shown).
    """
    keys = await auth.list_api_keys()

    return APIKeyListResponse(
        keys=[
            APIKeyResponse(
                id=k.id,
                key=k.key,  # Already masked by list_api_keys
                name=k.name,
                isAdmin=k.is_admin,
                rateLimit=k.rate_limit,
                requestsCount=k.requests_count,
                isActive=k.is_active,
                createdAt=k.created_at,
            )
            for k in keys
        ]
    )


@router.delete(
    "/admin/keys/{key_id}",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
        404: {"model": ErrorResponse, "description": "Key not found"},
    },
    tags=["Admin"],
)
async def revoke_api_key(
    key_id: int,
    admin_key: APIKey = Depends(get_admin_api_key),
):
    """
    Revoke an API key by ID. Requires admin access.
    The key will be deactivated but not deleted from the database.
    """
    success = await auth.revoke_api_key(key_id)

    if not success:
        raise HTTPException(status_code=404, detail="API key not found")

    logger.info(f"Admin {admin_key.name} revoked API key ID: {key_id}")

    return {"message": f"API key {key_id} has been revoked"}
