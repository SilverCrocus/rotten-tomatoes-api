# Rotten Tomatoes API

A REST API for fetching Rotten Tomatoes movie data using IMDB IDs. Get critic scores, audience scores, ratings, and more.

**Live API:** https://rotten-tomatoes-api-clrb.onrender.com

## Features

- **IMDB ID Lookup** - Use familiar IMDB IDs (e.g., `tt0468569`) to fetch RT data
- **Batch Requests** - Fetch up to 50 movies in a single request with SSE streaming
- **RT Lists** - Fetch movies from RT editorial lists and browse pages
- **Automatic Mapping** - Uses Wikidata to map IMDB IDs to RT slugs
- **Comprehensive Data** - Returns critic score, audience score, ratings, consensus, and RT URL
- **Smart Caching** - PostgreSQL caching with 7-day TTL for fast responses
- **Graceful Degradation** - Returns stale cache if fresh data unavailable
- **Rate Limiting** - Configurable rate limits per API key
- **Admin Management** - Create and manage API keys via admin endpoints

## Quick Start

### 1. Get an API Key

Contact the API administrator to get an API key, or if you're deploying your own instance, use the `ADMIN_API_KEY` from your environment.

### 2. Make Your First Request

```bash
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/movie/tt0468569" \
  -H "X-API-Key: your-api-key-here"
```

### 3. Get the Response

```json
{
  "imdbId": "tt0468569",
  "rtUrl": "https://www.rottentomatoes.com/m/the_dark_knight",
  "title": "The Dark Knight",
  "year": 2008,
  "criticScore": 94,
  "audienceScore": 94,
  "criticRating": "certified_fresh",
  "audienceRating": "upright",
  "consensus": "Dark, complex, and unforgettable, The Dark Knight succeeds not just as an entertaining comic book film, but as a richly thrilling crime saga.",
  "cachedAt": "2025-12-28T04:15:00Z"
}
```

---

## API Reference

### Base URL

```
https://rotten-tomatoes-api-clrb.onrender.com/api/v1
```

### Authentication

All endpoints (except `/health`) require an API key passed in the `X-API-Key` header:

```bash
-H "X-API-Key: your-api-key-here"
```

---

## Endpoints

### GET /movie/{imdb_id}

Fetch Rotten Tomatoes data for a movie.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `imdb_id` | path | Yes | IMDB ID (format: `tt` followed by 7-8 digits) |

**Example Request:**

```bash
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/movie/tt0111161" \
  -H "X-API-Key: your-api-key-here"
```

**Success Response (200):**

```json
{
  "imdbId": "tt0111161",
  "rtUrl": "https://www.rottentomatoes.com/m/shawshank_redemption",
  "title": "The Shawshank Redemption",
  "year": 1994,
  "criticScore": 89,
  "audienceScore": 98,
  "criticRating": "certified_fresh",
  "audienceRating": "upright",
  "consensus": "The Shawshank Redemption is an uplifting, deeply satisfying prison drama with sensitive direction and fine performances.",
  "cachedAt": "2025-12-28T04:20:00Z"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `imdbId` | string | The IMDB ID you requested |
| `rtUrl` | string | Direct link to the Rotten Tomatoes page |
| `title` | string | Movie title |
| `year` | integer | Release year |
| `criticScore` | integer | Tomatometer score (0-100) |
| `audienceScore` | integer | Popcornmeter/Audience score (0-100) |
| `criticRating` | string | `certified_fresh`, `fresh`, or `rotten` |
| `audienceRating` | string | `upright` or `spilled` |
| `consensus` | string | Critics consensus text |
| `cachedAt` | string | ISO 8601 timestamp of when data was cached |

**Error Responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid IMDB ID format |
| 401 | Invalid or missing API key |
| 404 | Movie not found in Wikidata |
| 429 | Rate limit exceeded |
| 502 | Failed to fetch RT data |

---

### POST /movies/batch

Fetch Rotten Tomatoes data for multiple movies in a single request. Returns a **Server-Sent Events (SSE)** stream with results as they become available - cached movies return instantly while cache misses are fetched in parallel.

**Request Body:**

```json
{
  "imdbIds": ["tt0468569", "tt0111161", "tt0137523"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `imdbIds` | array | Yes | List of IMDB IDs (max 50) |

**Example Request:**

```bash
curl -X POST "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/movies/batch" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"imdbIds": ["tt0468569", "tt0111161", "tt0137523"]}'
```

**Response (SSE Stream):**

The response is a Server-Sent Events stream with three event types:

**`movie` event** - Successfully resolved movie:
```
event: movie
data: {"imdbId": "tt0468569", "status": "cached", "rtUrl": "https://www.rottentomatoes.com/m/the_dark_knight", "title": "The Dark Knight", "year": 2008, "criticScore": 94, "audienceScore": 94, "criticRating": "certified_fresh", "audienceRating": "upright", "consensus": "Dark, complex, and unforgettable...", "cachedAt": "2025-12-28T05:09:07Z"}
```

**`error` event** - Failed to resolve a movie:
```
event: error
data: {"imdbId": "tt9999999", "error": "not_found", "message": "Movie not found in Wikidata: tt9999999"}
```

**`done` event** - Stream complete with summary:
```
event: done
data: {"total": 3, "cached": 2, "fetched": 1, "errors": 0}
```

**Movie Event Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `cached` (from fresh cache), `stale` (from expired cache), or `fetched` (freshly scraped) |
| *(other fields)* | - | Same as single movie endpoint |

**Error Types:**

| Error | Description |
|-------|-------------|
| `not_found` | Movie not found in Wikidata |
| `scrape_failed` | Failed to scrape Rotten Tomatoes |
| `invalid_id` | Invalid IMDB ID format |

---

## List Endpoints

Fetch movies from Rotten Tomatoes editorial lists and browse pages.

### GET /list

Fetch movies from any RT list by URL.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | query | Yes | RT list URL (editorial or browse page) |

**Example Request:**

```bash
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/list?url=https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/" \
  -H "X-API-Key: your-api-key-here"
```

**Response (200):**

```json
{
  "source": "https://editorial.rottentomatoes.com/guide/best-horror-movies-of-all-time/",
  "title": "Best Horror Movies of All Time",
  "movieCount": 200,
  "movies": [
    {"rtSlug": "m/the_exorcist", "title": "The Exorcist", "year": 1973},
    {"rtSlug": "m/get_out", "title": "Get Out", "year": 2017}
  ],
  "cachedAt": "2025-12-29T12:00:00Z",
  "stale": false
}
```

---

### GET /lists/curated

List all available curated editorial lists.

**Example Request:**

```bash
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/lists/curated" \
  -H "X-API-Key: your-api-key-here"
```

**Response (200):**

```json
{
  "lists": [
    {"slug": "best-horror", "title": "Best Horror Movies of All Time", "description": "RT's definitive ranking of the greatest horror films"},
    {"slug": "best-2024", "title": "Best Movies of 2024", "description": "The top-rated films of 2024"},
    {"slug": "best-comedies", "title": "Best Comedies of All Time", "description": "The funniest movies ever made according to critics"}
  ]
}
```

---

### GET /lists/curated/{slug}

Fetch movies from a curated list by slug.

**Example Request:**

```bash
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/lists/curated/best-horror" \
  -H "X-API-Key: your-api-key-here"
```

**Response:** Same format as GET /list

---

### GET /lists/browse/options

Get available browse filter options.

**Example Request:**

```bash
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/lists/browse/options" \
  -H "X-API-Key: your-api-key-here"
```

**Response (200):**

```json
{
  "certifications": ["certified_fresh", "fresh", "rotten"],
  "genres": ["action", "comedy", "horror", "drama", "sci_fi", ...],
  "affiliates": ["netflix", "amazon_prime", "hulu", "max", ...],
  "sorts": ["popular", "newest", "a_z", "critic_highest", "audience_highest"],
  "types": ["movies_at_home", "movies_in_theaters", "movies_coming_soon"],
  "audienceRatings": ["upright", "spilled"]
}
```

---

### GET /lists/browse

Browse RT movies with filters.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `certification` | query | No | `certified_fresh`, `fresh`, or `rotten` |
| `genre` | query | No | Genre filter (see /lists/browse/options) |
| `affiliate` | query | No | Streaming service filter |
| `sort` | query | No | Sort order |
| `type` | query | No | `movies_at_home` (default), `movies_in_theaters`, `movies_coming_soon` |
| `audience` | query | No | `upright` or `spilled` |

**Example Request:**

```bash
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/lists/browse?certification=certified_fresh&genre=horror&sort=popular" \
  -H "X-API-Key: your-api-key-here"
```

**Response:** Same format as GET /list

---

### GET /health

Health check endpoint (no authentication required).

**Example Request:**

```bash
curl https://rotten-tomatoes-api-clrb.onrender.com/api/v1/health
```

**Response (200):**

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Admin Endpoints

These endpoints require an **admin** API key.

### POST /admin/keys

Create a new API key.

**Request Body:**

```json
{
  "name": "My App Key",
  "isAdmin": false,
  "rateLimit": 500
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Descriptive name for the key |
| `isAdmin` | boolean | No | `false` | Whether this is an admin key |
| `rateLimit` | integer | No | `500` | Requests per hour (null for unlimited) |

**Example Request:**

```bash
curl -X POST "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/admin/keys" \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Mobile App", "rateLimit": 1000}'
```

**Response (200):**

```json
{
  "id": 1,
  "key": "a1b2c3d4e5f6...",
  "name": "Mobile App",
  "isAdmin": false,
  "rateLimit": 1000,
  "requestsCount": 0,
  "isActive": true,
  "createdAt": "2025-12-28T05:00:00Z"
}
```

> **Important:** Save the `key` value immediately! It's only shown once at creation.

---

### GET /admin/keys

List all API keys (keys are masked for security).

**Example Request:**

```bash
curl "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/admin/keys" \
  -H "X-API-Key: your-admin-key"
```

**Response (200):**

```json
{
  "keys": [
    {
      "id": 1,
      "key": "a1b2c3d4...f6g7",
      "name": "Mobile App",
      "isAdmin": false,
      "rateLimit": 1000,
      "requestsCount": 42,
      "isActive": true,
      "createdAt": "2025-12-28T05:00:00Z"
    }
  ]
}
```

---

### DELETE /admin/keys/{key_id}

Revoke an API key.

**Example Request:**

```bash
curl -X DELETE "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/admin/keys/1" \
  -H "X-API-Key: your-admin-key"
```

**Response (200):**

```json
{
  "message": "API key 1 has been revoked"
}
```

---

## Rate Limiting

- **Admin keys:** Unlimited requests
- **Regular keys:** 500 requests/hour (configurable per key)
- Rate limits reset every hour

When rate limited, you'll receive a `429` response:

```json
{
  "detail": "Rate limit exceeded. Please wait before making more requests."
}
```

The response includes a `Retry-After: 3600` header.

---

## Error Handling

All errors return JSON with a `detail` field:

```json
{
  "detail": "Error message here"
}
```

### Common Errors

| Status | Detail | Solution |
|--------|--------|----------|
| 400 | "Invalid IMDB ID format" | Use format `tt0000000` (tt + 7-8 digits) |
| 401 | "Invalid or inactive API key" | Check your API key is correct and active |
| 404 | "Movie not found in Wikidata" | Movie may not have RT data in Wikidata |
| 429 | "Rate limit exceeded" | Wait for rate limit reset or upgrade your key |
| 502 | "Failed to scrape Rotten Tomatoes" | RT may be temporarily unavailable |

---

## Code Examples

### Python

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "https://rotten-tomatoes-api-clrb.onrender.com/api/v1"

def get_rt_data(imdb_id: str) -> dict:
    response = requests.get(
        f"{BASE_URL}/movie/{imdb_id}",
        headers={"X-API-Key": API_KEY}
    )
    response.raise_for_status()
    return response.json()

# Example usage
movie = get_rt_data("tt0468569")
print(f"{movie['title']}: {movie['criticScore']}% Tomatometer")
```

**Batch Request (Python):**

```python
import requests
import json

def get_rt_data_batch(imdb_ids: list[str]) -> dict:
    """Fetch multiple movies via SSE stream."""
    results = {}

    response = requests.post(
        f"{BASE_URL}/movies/batch",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json={"imdbIds": imdb_ids},
        stream=True
    )

    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if 'imdbId' in data:
                    results[data['imdbId']] = data

    return results

# Example usage
movies = get_rt_data_batch(["tt0468569", "tt0111161", "tt0137523"])
for imdb_id, movie in movies.items():
    print(f"{movie['title']}: {movie.get('criticScore', 'N/A')}%")
```

### JavaScript/TypeScript

```javascript
const API_KEY = 'your-api-key-here';
const BASE_URL = 'https://rotten-tomatoes-api-clrb.onrender.com/api/v1';

async function getRTData(imdbId) {
  const response = await fetch(`${BASE_URL}/movie/${imdbId}`, {
    headers: { 'X-API-Key': API_KEY }
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

// Example usage
const movie = await getRTData('tt0468569');
console.log(`${movie.title}: ${movie.criticScore}% Tomatometer`);
```

**Batch Request (JavaScript/TypeScript):**

```typescript
async function getRTDataBatch(imdbIds: string[]): Promise<Map<string, any>> {
  const results = new Map();

  const response = await fetch(`${BASE_URL}/movies/batch`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ imdbIds }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.imdbId) {
          results.set(data.imdbId, data);
        }
      }
    }
  }

  return results;
}

// Example usage
const movies = await getRTDataBatch(['tt0468569', 'tt0111161', 'tt0137523']);
movies.forEach((movie, imdbId) => {
  console.log(`${movie.title}: ${movie.criticScore}% Tomatometer`);
});
```

### cURL

```bash
# Get single movie
curl -X GET "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/movie/tt0468569" \
  -H "X-API-Key: your-api-key-here"

# Get multiple movies (batch)
curl -X POST "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/movies/batch" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"imdbIds": ["tt0468569", "tt0111161", "tt0137523"]}'

# Create a new API key (admin only)
curl -X POST "https://rotten-tomatoes-api-clrb.onrender.com/api/v1/admin/keys" \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Key"}'
```

---

## Interactive Documentation

Visit the Swagger UI for interactive API documentation:

**https://rotten-tomatoes-api-clrb.onrender.com/docs**

---

## How It Works

1. **IMDB ID Input** - You provide an IMDB ID (e.g., `tt0468569`)
2. **Cache Check** - API checks PostgreSQL cache for recent data (< 7 days old)
3. **Wikidata Lookup** - If cache miss, queries Wikidata SPARQL to map IMDB → RT slug
4. **RT Scraping** - Fetches and parses the Rotten Tomatoes page
5. **Cache & Return** - Stores data in cache and returns response

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  RT API     │────▶│  Wikidata   │────▶│     RT      │
│             │◀────│  (Cache)    │◀────│  SPARQL     │◀────│   Scraper   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

---

## Tech Stack

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Database for caching
- **httpx** - Async HTTP client
- **BeautifulSoup** - HTML parsing
- **Wikidata SPARQL** - IMDB to RT mapping
- **Render** - Cloud hosting

---

## Self-Hosting

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

---

## License

MIT License - feel free to use this for your projects!

---

## Support

- **GitHub Issues:** https://github.com/SilverCrocus/rotten-tomatoes-api/issues
- **API Status:** Check `/health` endpoint
