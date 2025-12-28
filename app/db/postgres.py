import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

from app.config import get_settings

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def init_db() -> None:
    """Initialize the database connection pool and create tables."""
    global _pool
    settings = get_settings()

    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
    )

    # Create tables if they don't exist
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rt_cache (
                imdb_id VARCHAR(15) PRIMARY KEY,
                rt_slug VARCHAR(255) NOT NULL,
                title VARCHAR(255),
                year INTEGER,
                critic_score INTEGER,
                audience_score INTEGER,
                critic_rating VARCHAR(20),
                audience_rating VARCHAR(20),
                consensus TEXT,
                rt_url VARCHAR(255),
                cached_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rt_cache_updated
            ON rt_cache(updated_at)
        """)

        # API keys table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                key VARCHAR(64) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                rate_limit INTEGER,
                requests_count INTEGER DEFAULT 0,
                requests_reset_at TIMESTAMP DEFAULT NOW(),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_key
            ON api_keys(key)
        """)


async def close_db() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    if _pool is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _pool


@asynccontextmanager
async def get_connection():
    """Get a database connection from the pool."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
