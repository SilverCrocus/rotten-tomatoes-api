"""Registry of known RT editorial lists."""

from typing import Optional

# Curated editorial lists - add more as needed
CURATED_LISTS: dict[str, dict] = {
    "best-horror": {
        "title": "Best Horror Movies of All Time",
        "description": "RT's definitive ranking of the greatest horror films",
        "url": "https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/",
    },
    "best-2024": {
        "title": "Best Movies of 2024",
        "description": "The top-rated films of 2024",
        "url": "https://editorial.rottentomatoes.com/guide/best-movies-of-2024/",
    },
    "best-comedies": {
        "title": "Best Comedies of All Time",
        "description": "The funniest movies ever made according to critics",
        "url": "https://editorial.rottentomatoes.com/guide/best-comedies/",
    },
    "best-action": {
        "title": "Best Action Movies of All Time",
        "description": "The greatest action films ranked",
        "url": "https://editorial.rottentomatoes.com/guide/best-action-movies/",
    },
    "best-sci-fi": {
        "title": "Best Sci-Fi Movies of All Time",
        "description": "The greatest science fiction films",
        "url": "https://editorial.rottentomatoes.com/guide/best-sci-fi-movies/",
    },
    "best-animated": {
        "title": "Best Animated Movies of All Time",
        "description": "The greatest animated films ranked",
        "url": "https://editorial.rottentomatoes.com/guide/best-animated-movies/",
    },
}


def get_curated_list(slug: str) -> Optional[dict]:
    """Get a curated list by slug."""
    return CURATED_LISTS.get(slug)


def get_all_curated_lists() -> list[dict]:
    """Get all available curated lists."""
    return [
        {"slug": slug, "title": info["title"], "description": info.get("description")}
        for slug, info in CURATED_LISTS.items()
    ]
