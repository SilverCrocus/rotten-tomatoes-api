from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Literal


class RTMovieResponse(BaseModel):
    """Response model for RT movie data."""

    imdb_id: str = Field(..., alias="imdbId")
    rt_url: str = Field(..., alias="rtUrl")
    title: str
    year: Optional[int] = None
    critic_score: Optional[int] = Field(None, alias="criticScore")
    audience_score: Optional[int] = Field(None, alias="audienceScore")
    critic_rating: Optional[str] = Field(None, alias="criticRating")
    audience_rating: Optional[str] = Field(None, alias="audienceRating")
    consensus: Optional[str] = None
    cached_at: datetime = Field(..., alias="cachedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class RTMovieData(BaseModel):
    """Internal model for scraped RT data."""

    rt_slug: str
    title: str
    year: Optional[int] = None
    critic_score: Optional[int] = None
    audience_score: Optional[int] = None
    critic_rating: Optional[str] = None
    audience_rating: Optional[str] = None
    consensus: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str


class APIKeyCreate(BaseModel):
    """Request model for creating an API key."""

    name: str = Field(..., min_length=1, max_length=100, description="Name/description for the key")
    is_admin: bool = Field(False, alias="isAdmin", description="Whether this is an admin key")
    rate_limit: Optional[int] = Field(None, alias="rateLimit", description="Custom rate limit (requests/hour)")

    class Config:
        populate_by_name = True


class APIKeyResponse(BaseModel):
    """Response model for API key."""

    id: int
    key: str = Field(..., description="The API key (only shown on creation)")
    name: str
    is_admin: bool = Field(..., alias="isAdmin")
    rate_limit: Optional[int] = Field(None, alias="rateLimit")
    requests_count: int = Field(..., alias="requestsCount")
    is_active: bool = Field(..., alias="isActive")
    created_at: datetime = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """Response model for listing API keys."""

    keys: list[APIKeyResponse]


# =============================================================================
# Batch Endpoint Schemas
# =============================================================================


class BatchRequest(BaseModel):
    """Request model for batch movie lookup."""

    imdb_ids: list[str] = Field(
        ...,
        alias="imdbIds",
        min_length=1,
        max_length=50,
        description="List of IMDB IDs to look up (max 50)",
    )

    @field_validator("imdb_ids")
    @classmethod
    def validate_imdb_ids(cls, v: list[str]) -> list[str]:
        import re
        pattern = re.compile(r"^tt\d{7,8}$")
        invalid = [id for id in v if not pattern.match(id.lower())]
        if invalid:
            raise ValueError(f"Invalid IMDB ID format: {invalid}")
        return [id.lower() for id in v]

    class Config:
        populate_by_name = True


class BatchMovieEvent(BaseModel):
    """SSE event for a successfully resolved movie."""

    imdb_id: str = Field(..., alias="imdbId")
    status: Literal["cached", "stale", "fetched"] = Field(
        ..., description="How the data was obtained"
    )
    rt_url: str = Field(..., alias="rtUrl")
    title: str
    year: Optional[int] = None
    critic_score: Optional[int] = Field(None, alias="criticScore")
    audience_score: Optional[int] = Field(None, alias="audienceScore")
    critic_rating: Optional[str] = Field(None, alias="criticRating")
    audience_rating: Optional[str] = Field(None, alias="audienceRating")
    consensus: Optional[str] = None
    cached_at: datetime = Field(..., alias="cachedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class BatchErrorEvent(BaseModel):
    """SSE event for a failed movie lookup."""

    imdb_id: str = Field(..., alias="imdbId")
    error: Literal["not_found", "scrape_failed", "invalid_id"] = Field(
        ..., description="Error type"
    )
    message: str = Field(..., description="Human-readable error message")

    class Config:
        populate_by_name = True


class BatchDoneEvent(BaseModel):
    """SSE event signaling batch completion."""

    total: int = Field(..., description="Total IDs requested")
    cached: int = Field(..., description="Count returned from cache")
    fetched: int = Field(..., description="Count freshly fetched")
    errors: int = Field(..., description="Count of failures")
