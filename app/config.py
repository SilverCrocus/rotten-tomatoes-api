from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/rt_api"
    cache_ttl_days: int = 7
    log_level: str = "INFO"

    # Rate limiting
    rt_request_delay: float = 1.0  # seconds between RT requests

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
