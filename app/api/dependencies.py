from fastapi import Header, HTTPException, Depends
from typing import Optional

from app.services.auth import validate_api_key, APIKey, check_rate_limit
from app.config import get_settings


async def get_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> APIKey:
    """
    Dependency to validate API key from X-API-Key header.
    Raises 401 if key is invalid or 429 if rate limited.
    """
    api_key = await validate_api_key(x_api_key)

    if api_key is None:
        # Check if it's a rate limit issue
        is_allowed, remaining = await check_rate_limit(x_api_key)
        if not is_allowed and remaining == 0:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before making more requests.",
                headers={"Retry-After": "3600"},
            )
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key",
        )

    return api_key


async def get_admin_api_key(api_key: APIKey = Depends(get_api_key)) -> APIKey:
    """
    Dependency to require admin API key.
    Raises 403 if key is not an admin key.
    """
    if not api_key.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
    return api_key


async def get_optional_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[APIKey]:
    """
    Dependency for optional API key authentication.
    Returns None if no key provided, validates if provided.
    """
    if x_api_key is None:
        return None

    return await get_api_key(x_api_key)
