import secrets
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from app.db.postgres import get_connection
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class APIKey:
    """Represents an API key."""
    id: int
    key: str
    name: str
    is_admin: bool
    rate_limit: Optional[int]
    requests_count: int
    requests_reset_at: datetime
    is_active: bool
    created_at: datetime


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_hex(32)


async def validate_api_key(key: str) -> Optional[APIKey]:
    """
    Validate an API key and return the key info if valid.
    Also checks rate limits and increments usage count.
    """
    settings = get_settings()

    # Check if it's the admin key from environment
    if settings.admin_api_key and key == settings.admin_api_key:
        return APIKey(
            id=0,
            key=key,
            name="Admin (ENV)",
            is_admin=True,
            rate_limit=None,
            requests_count=0,
            requests_reset_at=datetime.utcnow(),
            is_active=True,
            created_at=datetime.utcnow(),
        )

    # Check database for the key
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, key, name, is_admin, rate_limit, requests_count,
                   requests_reset_at, is_active, created_at
            FROM api_keys
            WHERE key = $1 AND is_active = TRUE
            """,
            key,
        )

        if not row:
            return None

        api_key = APIKey(
            id=row["id"],
            key=row["key"],
            name=row["name"],
            is_admin=row["is_admin"],
            rate_limit=row["rate_limit"],
            requests_count=row["requests_count"],
            requests_reset_at=row["requests_reset_at"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )

        # Admin keys have no rate limit
        if api_key.is_admin:
            return api_key

        # Check and update rate limit
        now = datetime.utcnow()
        rate_limit = api_key.rate_limit or settings.default_rate_limit

        # Reset counter if hour has passed
        if now >= api_key.requests_reset_at:
            await conn.execute(
                """
                UPDATE api_keys
                SET requests_count = 1, requests_reset_at = $1
                WHERE id = $2
                """,
                now + timedelta(hours=1),
                api_key.id,
            )
            api_key.requests_count = 1
            api_key.requests_reset_at = now + timedelta(hours=1)
        else:
            # Check if over limit
            if api_key.requests_count >= rate_limit:
                return None  # Rate limited

            # Increment counter
            await conn.execute(
                """
                UPDATE api_keys
                SET requests_count = requests_count + 1
                WHERE id = $1
                """,
                api_key.id,
            )
            api_key.requests_count += 1

        return api_key


async def check_rate_limit(key: str) -> tuple[bool, Optional[int]]:
    """
    Check if an API key is rate limited.
    Returns (is_allowed, remaining_requests).
    """
    settings = get_settings()

    # Admin key from environment is never rate limited
    if settings.admin_api_key and key == settings.admin_api_key:
        return True, None

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT is_admin, rate_limit, requests_count, requests_reset_at
            FROM api_keys
            WHERE key = $1 AND is_active = TRUE
            """,
            key,
        )

        if not row:
            return False, 0

        if row["is_admin"]:
            return True, None

        rate_limit = row["rate_limit"] or settings.default_rate_limit
        now = datetime.utcnow()

        # Reset if hour passed
        if now >= row["requests_reset_at"]:
            return True, rate_limit

        remaining = rate_limit - row["requests_count"]
        return remaining > 0, max(0, remaining)


async def create_api_key(
    name: str,
    is_admin: bool = False,
    rate_limit: Optional[int] = None,
) -> APIKey:
    """Create a new API key."""
    key = generate_api_key()
    now = datetime.utcnow()

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO api_keys (key, name, is_admin, rate_limit, requests_reset_at, created_at)
            VALUES ($1, $2, $3, $4, $5, $5)
            RETURNING id, key, name, is_admin, rate_limit, requests_count,
                      requests_reset_at, is_active, created_at
            """,
            key,
            name,
            is_admin,
            rate_limit,
            now,
        )

        return APIKey(
            id=row["id"],
            key=row["key"],
            name=row["name"],
            is_admin=row["is_admin"],
            rate_limit=row["rate_limit"],
            requests_count=row["requests_count"],
            requests_reset_at=row["requests_reset_at"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )


async def list_api_keys() -> list[APIKey]:
    """List all API keys (without the actual key values for security)."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, key, name, is_admin, rate_limit, requests_count,
                   requests_reset_at, is_active, created_at
            FROM api_keys
            ORDER BY created_at DESC
            """
        )

        return [
            APIKey(
                id=row["id"],
                key=row["key"][:8] + "..." + row["key"][-4:],  # Mask key
                name=row["name"],
                is_admin=row["is_admin"],
                rate_limit=row["rate_limit"],
                requests_count=row["requests_count"],
                requests_reset_at=row["requests_reset_at"],
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


async def revoke_api_key(key_id: int) -> bool:
    """Revoke an API key by ID."""
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE api_keys
            SET is_active = FALSE
            WHERE id = $1
            """,
            key_id,
        )
        return "UPDATE 1" in result


async def delete_api_key(key_id: int) -> bool:
    """Permanently delete an API key by ID."""
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM api_keys
            WHERE id = $1
            """,
            key_id,
        )
        return "DELETE 1" in result
