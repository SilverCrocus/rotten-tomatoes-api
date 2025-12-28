# Rotten Tomatoes API Design

## Overview

A standalone REST API that provides Rotten Tomatoes movie data by scraping RT pages. Designed for personal use, primarily to enhance the Cine Match movie swiping app with RT scores and links.

## Problem

- Official RT API costs $60K+/year
- OMDB provides incomplete RT data (no audience score, no RT URL, unreliable coverage)
- No free API exists for RT data

## Solution

A self-hosted Python FastAPI service that:
1. Accepts IMDB ID as input
2. Uses Wikidata to resolve IMDB ID → RT slug (avoids title matching edge cases)
3. Scrapes RT page for scores and metadata
4. Caches results in Postgres for 7 days

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI
- **HTTP Client**: httpx (async)
- **HTML Parser**: BeautifulSoup + lxml
- **Database**: PostgreSQL (asyncpg)
- **Hosting**: Render

## API Endpoints

### GET /api/v1/movie/{imdb_id}

Returns RT data for a movie.

**Request:**
```
GET /api/v1/movie/tt0468569
```

**Response:**
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
  "consensus": "Dark, complex, and unforgettable...",
  "cachedAt": "2025-12-28T04:15:00Z"
}
```

**Error Responses:**
- `400` - Invalid IMDB ID format
- `404` - Movie not found in Wikidata
- `502` - RT scrape failed

### GET /api/v1/health

Health check endpoint.

### POST /api/v1/movies/batch (Future)

Batch lookup for multiple IMDB IDs.

## Data Flow

```
Request (/tt0468569)
       │
       ▼
┌──────────────────┐
│  Check Postgres  │──── Cache hit & fresh? ──── Return cached
│      Cache       │
└──────────────────┘
       │ Cache miss
       ▼
┌──────────────────┐
│ Query Wikidata   │
│ SPARQL Endpoint  │──── Get RT slug (m/the_dark_knight)
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Scrape RT Page  │──── Parse scores, consensus, ratings
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Cache & Return  │
└──────────────────┘
```

## Database Schema

```sql
CREATE TABLE rt_cache (
  imdb_id VARCHAR(15) PRIMARY KEY,
  rt_slug VARCHAR(255),
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
);

CREATE INDEX idx_rt_cache_updated ON rt_cache(updated_at);
```

## Project Structure

```
rt_api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Settings (env vars)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── wikidata.py      # Wikidata SPARQL queries
│   │   ├── scraper.py       # RT page scraping
│   │   └── cache.py         # Database caching logic
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # Pydantic models
│   └── db/
│       ├── __init__.py
│       └── postgres.py      # DB connection & queries
├── requirements.txt
├── Dockerfile
├── render.yaml
├── .env.example
└── README.md
```

## Dependencies

```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
httpx==0.28.0
beautifulsoup4==4.12.0
lxml==5.3.0
asyncpg==0.30.0
pydantic-settings==2.6.0
python-dotenv==1.0.0
```

## Wikidata Integration

SPARQL query to get RT slug from IMDB ID:

```sparql
SELECT ?rtId WHERE {
  ?film wdt:P345 "tt0468569" .
  ?film wdt:P1258 ?rtId .
}
```

Endpoint: `https://query.wikidata.org/sparql`

## Scraping Strategy

1. **Primary**: Parse JSON-LD structured data embedded in RT pages
2. **Fallback**: CSS selectors for score-board elements

Target elements:
- Critic Score: `score-board` component or JSON-LD
- Audience Score: `score-board` data attributes
- Consensus: `[data-qa="critics-consensus"]`
- Ratings: Icon classes (certified_fresh, fresh, rotten, upright, spilled)

## Rate Limiting

Self-imposed limits to avoid IP blocks:
- RT scraping: 1 request/second (async semaphore)
- Wikidata: 5 requests/second

## Error Handling

| Scenario | Response | Fallback |
|----------|----------|----------|
| IMDB ID not in Wikidata | 404 | None |
| RT scrape fails | 502 | Return stale cache if available |
| Invalid IMDB format | 400 | None |
| RT structure changed | 500 | Log for investigation |

## Cine Match Integration

```typescript
// lib/api/rt.ts
const RT_API_URL = process.env.RT_API_URL;

export async function getRTData(imdbId: string): Promise<RTData | null> {
  const response = await fetch(`${RT_API_URL}/api/v1/movie/${imdbId}`, {
    next: { revalidate: 86400 },
  });
  if (!response.ok) return null;
  return response.json();
}
```

Benefits over OMDB:
- Audience score (OMDB doesn't have this)
- RT page URL for linking out
- Consensus text
- Certified Fresh status
- More reliable coverage

## Deployment

Render configuration:

```yaml
services:
  - type: web
    name: rt-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: rt-api-db
          property: connectionString

databases:
  - name: rt-api-db
    plan: free
```

## Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host:5432/rt_api
CACHE_TTL_DAYS=7
LOG_LEVEL=INFO
```

## Future Enhancements

- Batch endpoint for deck building
- TV show support
- Full reviews/cast data
- Webhook for cache refresh
