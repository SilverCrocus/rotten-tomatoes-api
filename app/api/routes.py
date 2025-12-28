import re
import asyncio
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
import logging

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
    # List schemas
    ListResponse,
    ListMovie,
    CuratedListInfo,
    CuratedListsResponse,
    BrowseOptionsResponse,
)
from app.services import wikidata, scraper, cache, auth
from app.services import list_scraper, list_cache
from app.services.curated_lists import get_curated_list, get_all_curated_lists
from app.services.browse_options import get_browse_options, validate_browse_params, build_browse_url
from app.api.dependencies import get_api_key, get_admin_api_key
from app.services.auth import APIKey
from app.services.cache import CachedMovie

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
# Batch Endpoint (SSE streaming)
# =============================================================================


def _format_sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _cached_to_event(cached: CachedMovie, status: str) -> BatchMovieEvent:
    """Convert CachedMovie to BatchMovieEvent."""
    return BatchMovieEvent(
        imdbId=cached.imdb_id,
        status=status,
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


async def _fetch_single_movie(
    imdb_id: str,
    stale_cache: CachedMovie | None,
) -> BatchMovieEvent | BatchErrorEvent:
    """
    Fetch a single movie that wasn't in fresh cache.
    Returns either a movie event or an error event.
    """
    # Query Wikidata for RT slug
    rt_slug = await wikidata.get_rt_slug(imdb_id)

    if not rt_slug:
        if stale_cache:
            logger.warning(f"Wikidata miss, returning stale cache for {imdb_id}")
            return _cached_to_event(stale_cache, "stale")
        return BatchErrorEvent(
            imdbId=imdb_id,
            error="not_found",
            message=f"Movie not found in Wikidata: {imdb_id}",
        )

    # Scrape RT page
    rt_data = await scraper.scrape_movie(rt_slug)

    if not rt_data:
        if stale_cache:
            logger.warning(f"Scrape failed, returning stale cache for {imdb_id}")
            return _cached_to_event(stale_cache, "stale")
        return BatchErrorEvent(
            imdbId=imdb_id,
            error="scrape_failed",
            message=f"Failed to scrape Rotten Tomatoes for {imdb_id}",
        )

    # Cache and return
    cached = await cache.upsert_cache(imdb_id, rt_data)
    logger.info(f"Fetched and cached RT data for {imdb_id}")
    return _cached_to_event(cached, "fetched")


@router.post(
    "/movies/batch",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    tags=["Batch"],
)
async def get_movies_batch(
    request: Request,
    batch_request: BatchRequest,
    api_key: APIKey = Depends(get_api_key),
):
    """
    Get Rotten Tomatoes data for multiple movies by IMDB IDs.
    Returns a Server-Sent Events stream with results as they become available.

    - **imdbIds**: List of IMDB IDs (max 50)

    Events:
    - `movie`: Successfully resolved movie data
    - `error`: Failed to resolve a specific movie
    - `done`: Stream complete with summary stats
    """
    imdb_ids = batch_request.imdb_ids
    logger.info(f"Batch request for {len(imdb_ids)} movies")

    async def generate_events():
        stats = {"cached": 0, "fetched": 0, "errors": 0}

        # 1. Batch cache lookup
        cached_movies = await cache.get_cached_batch(imdb_ids)

        # 2. Separate fresh cache hits from misses/stale
        fresh_cached = {}
        to_fetch = []  # (imdb_id, stale_cache_or_none)

        for imdb_id in imdb_ids:
            cached = cached_movies.get(imdb_id)
            if cached and cache.is_cache_fresh(cached):
                fresh_cached[imdb_id] = cached
            else:
                to_fetch.append((imdb_id, cached))  # cached might be stale or None

        # 3. Stream fresh cached results immediately
        for imdb_id, cached in fresh_cached.items():
            event = _cached_to_event(cached, "cached")
            stats["cached"] += 1
            yield _format_sse("movie", event.model_dump(by_alias=True))

        # 4. Fetch cache misses in parallel
        if to_fetch:
            tasks = [
                _fetch_single_movie(imdb_id, stale_cache)
                for imdb_id, stale_cache in to_fetch
            ]

            # Process results as they complete
            for coro in asyncio.as_completed(tasks):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Client disconnected, stopping batch processing")
                    break

                result = await coro

                if isinstance(result, BatchMovieEvent):
                    if result.status == "fetched":
                        stats["fetched"] += 1
                    else:  # stale
                        stats["cached"] += 1  # Count stale as cached for stats
                    yield _format_sse("movie", result.model_dump(by_alias=True))
                else:  # BatchErrorEvent
                    stats["errors"] += 1
                    yield _format_sse("error", result.model_dump(by_alias=True))

        # 5. Send done event
        done_event = BatchDoneEvent(
            total=len(imdb_ids),
            cached=stats["cached"],
            fetched=stats["fetched"],
            errors=stats["errors"],
        )
        yield _format_sse("done", done_event.model_dump())

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


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
