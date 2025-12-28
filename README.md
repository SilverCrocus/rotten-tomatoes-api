# Rotten Tomatoes API

A personal REST API for fetching Rotten Tomatoes movie data. Designed to provide RT scores, audience ratings, and links for movie applications.

## Features

- Lookup RT data by IMDB ID
- Automatic IMDB → RT slug mapping via Wikidata
- Postgres caching (7-day TTL)
- Graceful degradation with stale cache fallback

## API Endpoints

### GET /api/v1/movie/{imdb_id}

Returns RT data for a movie.

```bash
curl http://localhost:8000/api/v1/movie/tt0468569
```

Response:
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

### GET /api/v1/health

Health check endpoint.

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL

### Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database URL
```

4. Run the server:
```bash
uvicorn app.main:app --reload
```

5. Open http://localhost:8000/docs for the API documentation.

## Deployment (Render)

1. Push to GitHub
2. Connect to Render
3. Use `render.yaml` for infrastructure-as-code deployment

Or manually:
- Create a PostgreSQL database
- Create a Web Service with Python runtime
- Set `DATABASE_URL` environment variable
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Tech Stack

- **FastAPI** - Web framework
- **httpx** - Async HTTP client
- **BeautifulSoup** - HTML parsing
- **asyncpg** - Async PostgreSQL driver
- **Wikidata SPARQL** - IMDB to RT mapping
