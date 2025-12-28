# RT Editorial Lists Feature Design

## Overview

Add the ability to pull movies from Rotten Tomatoes editorial lists and browse filters. This enables discovery of curated movie collections for use in other apps and side projects.

## Use Case

- Pull movies from RT editorial lists (e.g., "Best Horror Movies", "Best of 2024")
- Query RT browse filters programmatically (e.g., Certified Fresh + Horror + Netflix)
- Get basic movie identifiers (RT slug, title, year) to use with existing endpoints or external lookups

## Endpoints

### URL-based List Fetch

```
GET /api/v1/list?url={rt_list_url}
```

Takes any RT list/browse URL and returns the movies. Works with:
- Editorial articles: `rottentomatoes.com/editorial/best-horror-movies`
- Browse pages: `rottentomatoes.com/browse/movies_at_home/critics:certified_fresh`

### Curated Lists

```
GET /api/v1/lists/curated
```
Returns available curated editorial lists.

```
GET /api/v1/lists/curated/{list_slug}
```
Fetches a specific curated list by slug.

### Browse Filters

```
GET /api/v1/lists/browse?certification=certified_fresh&genre=horror&sort=popular
```
Programmatic access to RT's browse filters.

```
GET /api/v1/lists/browse/options
```
Returns all valid filter values for building UIs.

## Response Format

All list endpoints return the same format:

```json
{
  "source": "https://www.rottentomatoes.com/...",
  "title": "Best Horror Movies of All Time",
  "movieCount": 85,
  "movies": [
    {"rtSlug": "the_exorcist", "title": "The Exorcist", "year": 1973},
    {"rtSlug": "get_out", "title": "Get Out", "year": 2017}
  ],
  "cachedAt": "2025-12-29T..."
}
```

**Note:** Only RT data is returned (slug, title, year). No IMDB ID resolution - clients can search IMDB separately if needed.

## Browse Filter Parameters

| Parameter | Values | Example |
|-----------|--------|---------|
| `certification` | `certified_fresh`, `fresh`, `rotten` | `?certification=certified_fresh` |
| `genre` | `action`, `comedy`, `horror`, `drama`, `sci_fi`, etc. | `?genre=horror` |
| `audience` | `upright`, `spilled` | `?audience=upright` |
| `affiliate` | `netflix`, `amazon_prime`, `hulu`, `max`, etc. | `?affiliate=netflix` |
| `sort` | `popular`, `newest`, `a_z`, `critic_highest`, `audience_highest` | `?sort=popular` |
| `type` | `movies_at_home`, `movies_in_theaters`, `movies_coming_soon` | `?type=movies_at_home` |

Filters are combinable: `?type=movies_at_home&certification=certified_fresh&genre=horror&sort=popular`

## Data Architecture

### New Database Table: `list_cache`

```sql
CREATE TABLE list_cache (
    id SERIAL PRIMARY KEY,
    url_hash VARCHAR(64) UNIQUE,  -- SHA256 of normalized URL
    source_url TEXT,              -- Original RT URL
    title VARCHAR(500),           -- List title
    movies JSONB,                 -- Array of {rtSlug, title, year}
    cached_at TIMESTAMP           -- When cached
);
```

### Cache Behavior

- 7-day TTL (same as movie cache)
- Cache key is normalized URL hash (strips tracking params, normalizes browse filters)
- Stale cache returned if RT is unavailable (graceful degradation)

### Curated Lists Registry

A config stores known editorial lists:

```python
CURATED_LISTS = {
    "best-horror": {
        "title": "Best Horror Movies",
        "url": "https://www.rottentomatoes.com/editorial/best-horror-movies-of-all-time"
    },
    "best-2024": {
        "title": "Best Movies of 2024",
        "url": "https://www.rottentomatoes.com/editorial/best-movies-of-2024"
    },
    # ... more lists added manually
}
```

## Scraping Strategy

### Editorial List Scraper

For `/editorial/*` URLs:
- Article-style pages with movie cards embedded
- Parse HTML for movie links in format `/m/{slug}`
- Extract title and year from surrounding elements

### Browse Page Scraper

For `/browse/*` URLs:
- Parse initial HTML payload (server-rendered data)
- No JavaScript execution required
- Extract movie data from embedded JSON or HTML structure

### Module Structure

```
scrapers/
  list_scraper.py      # Main entry point, routes to correct scraper
  editorial_scraper.py # Parses editorial article pages
  browse_scraper.py    # Parses browse/filter pages
```

Both scrapers return: `list[{rtSlug, title, year}]`

## Error Handling

| Scenario | Response |
|----------|----------|
| Invalid/unsupported URL | 400: `"Unsupported RT URL format"` |
| RT unavailable (with cache) | Return stale cache with `"stale": true` |
| RT unavailable (no cache) | 502: `"Failed to fetch RT list"` |
| Empty list results | 200: `{"movies": [], "movieCount": 0}` |
| Unknown curated list slug | 404: `"Unknown list: {slug}"` |
| Invalid browse params | 400: `"Invalid genre: {value}"` |

## Authentication & Rate Limiting

- Same API key system as existing endpoints
- List fetches count as 1 request regardless of movie count
- Requires valid API key (no admin required)

## Implementation Notes

- All movies returned (no pagination) - keeps it simple for side project use
- HTML parsing approach for stability (avoids relying on internal RT APIs)
- Curated list registry is manually maintained - add lists as needed
