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
