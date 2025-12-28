"""Browse filter options for RT browse pages."""

# Valid filter values - these map to RT's URL parameters
BROWSE_OPTIONS = {
    "certifications": ["certified_fresh", "fresh", "rotten"],
    "genres": [
        "action",
        "adventure",
        "animation",
        "anime",
        "biography",
        "comedy",
        "crime",
        "documentary",
        "drama",
        "fantasy",
        "history",
        "horror",
        "music",
        "mystery",
        "romance",
        "sci_fi",
        "sport",
        "thriller",
        "war",
        "western",
    ],
    "affiliates": [
        "netflix",
        "amazon_prime",
        "hulu",
        "max",
        "disney_plus",
        "paramount_plus",
        "apple_tv_plus",
        "peacock",
    ],
    "sorts": [
        "popular",
        "newest",
        "a_z",
        "critic_highest",
        "critic_lowest",
        "audience_highest",
        "audience_lowest",
    ],
    "types": [
        "movies_at_home",
        "movies_in_theaters",
        "movies_coming_soon",
    ],
    "audience_ratings": ["upright", "spilled"],
}


def get_browse_options() -> dict:
    """Get all available browse filter options."""
    return BROWSE_OPTIONS.copy()


def validate_browse_params(
    certification: str | None = None,
    genre: str | None = None,
    affiliate: str | None = None,
    sort: str | None = None,
    browse_type: str | None = None,
    audience: str | None = None,
) -> tuple[bool, str | None]:
    """
    Validate browse parameters.

    Returns:
        (is_valid, error_message)
    """
    if certification and certification not in BROWSE_OPTIONS["certifications"]:
        return False, f"Invalid certification: {certification}. Valid: {BROWSE_OPTIONS['certifications']}"

    if genre and genre not in BROWSE_OPTIONS["genres"]:
        return False, f"Invalid genre: {genre}. Valid: {BROWSE_OPTIONS['genres']}"

    if affiliate and affiliate not in BROWSE_OPTIONS["affiliates"]:
        return False, f"Invalid affiliate: {affiliate}. Valid: {BROWSE_OPTIONS['affiliates']}"

    if sort and sort not in BROWSE_OPTIONS["sorts"]:
        return False, f"Invalid sort: {sort}. Valid: {BROWSE_OPTIONS['sorts']}"

    if browse_type and browse_type not in BROWSE_OPTIONS["types"]:
        return False, f"Invalid type: {browse_type}. Valid: {BROWSE_OPTIONS['types']}"

    if audience and audience not in BROWSE_OPTIONS["audience_ratings"]:
        return False, f"Invalid audience: {audience}. Valid: {BROWSE_OPTIONS['audience_ratings']}"

    return True, None


def build_browse_url(
    certification: str | None = None,
    genre: str | None = None,
    affiliate: str | None = None,
    sort: str | None = None,
    browse_type: str = "movies_at_home",
    audience: str | None = None,
) -> str:
    """
    Build RT browse URL from filter parameters.

    Example output:
    https://www.rottentomatoes.com/browse/movies_at_home/critics:certified_fresh~genres:horror~sort:popular
    """
    base = f"https://www.rottentomatoes.com/browse/{browse_type}"

    filters = []

    if certification:
        filters.append(f"critics:{certification}")

    if audience:
        filters.append(f"audience:{audience}")

    if genre:
        filters.append(f"genres:{genre}")

    if affiliate:
        filters.append(f"affiliates:{affiliate}")

    if sort:
        filters.append(f"sort:{sort}")

    if filters:
        return f"{base}/{'/'.join(filters)}"

    return base
