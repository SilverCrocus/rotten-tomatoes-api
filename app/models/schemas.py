from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


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
