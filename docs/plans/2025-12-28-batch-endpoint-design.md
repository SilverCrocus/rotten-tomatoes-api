# Batch Endpoint Design: SSE Streaming for Bulk Movie Loading

## Problem

When Cinematch loads 30-50 movies for swiping, it makes sequential API calls to the RT API. Each cache miss requires Wikidata lookup + RT scraping (~1-2s each). With the current semaphore limit of 1 concurrent scrape, loading 30 movies with cache misses takes 30+ seconds.

## Solution

Add a batch endpoint that accepts multiple IMDB IDs and streams results via Server-Sent Events (SSE). Cached movies return instantly; cache misses are processed in parallel with controlled concurrency.

## API Contract

### Endpoint: `POST /api/v1/movies/batch`

**Request:**
```json
{
  "imdbIds": ["tt0468569", "tt0111161", "tt0137523"]
}
```

**Response:** Server-Sent Events stream

```
Content-Type: text/event-stream

event: movie
data: {"imdbId":"tt0468569","status":"cached","title":"The Dark Knight",...}

event: movie
data: {"imdbId":"tt0111161","status":"cached","title":"The Shawshank Redemption",...}

event: movie
data: {"imdbId":"tt0137523","status":"fetched","title":"Fight Club",...}

event: error
data: {"imdbId":"tt9999999","error":"not_found","message":"Movie not found in Wikidata"}

event: done
data: {"total":30,"cached":25,"fetched":3,"errors":2}
```

**Event types:**
- `movie` - Successfully resolved movie (cached or freshly fetched)
- `error` - Failed to resolve a specific movie
- `done` - Stream complete with summary stats

**Status field in movie events:**
- `cached` - Returned from fresh cache
- `stale` - Returned from stale cache (fetch failed)
- `fetched` - Freshly scraped from RT

## Processing Flow

```
POST /movies/batch (30 IDs)
         │
         ▼
┌─────────────────────────────────┐
│  1. Batch Cache Lookup          │
│     SELECT * FROM rt_cache      │
│     WHERE imdb_id IN (...)      │
└─────────────────────────────────┘
         │
         ├──────────────────────────────────┐
         ▼                                  ▼
┌─────────────────────┐          ┌─────────────────────┐
│  2a. Stream cached  │          │  2b. Queue misses   │
│      immediately    │          │      for fetching   │
└─────────────────────┘          └─────────────────────┘
                                          │
                                          ▼
                                ┌─────────────────────┐
                                │  3. Parallel fetch  │
                                │     with limits     │
                                │  - Wikidata: 5 conc │
                                │  - RT scrape: 2 conc│
                                └─────────────────────┘
                                          │
                                          ▼
                                ┌─────────────────────┐
                                │  4. Send 'done'     │
                                └─────────────────────┘
```

## Concurrency Limits

| Operation | Current | Proposed | Reasoning |
|-----------|---------|----------|-----------|
| Wikidata queries | 1 (implicit) | 5 parallel | Wikidata allows ~5 req/sec |
| RT scraping | 1 (semaphore) | 2 parallel | Conservative to avoid IP ban |
| DB queries | 1 per request | 1 batch query | Single SELECT with IN clause |

## Error Handling

### Per-Movie Errors

Each movie is processed independently - one failure doesn't break the batch.

| Scenario | Event Type | Behavior |
|----------|------------|----------|
| Cache hit (fresh) | `movie` | Return immediately, status=`cached` |
| Cache hit (stale) + fetch succeeds | `movie` | Return fresh data, status=`fetched` |
| Cache hit (stale) + fetch fails | `movie` | Return stale data, status=`stale` |
| Cache miss + fetch succeeds | `movie` | Return fresh data, status=`fetched` |
| Cache miss + Wikidata miss | `error` | `{"error": "not_found"}` |
| Cache miss + RT scrape fails | `error` | `{"error": "scrape_failed"}` |
| Invalid IMDB ID format | `error` | `{"error": "invalid_id"}` |

### Request-Level Validation

- Validate all IMDB IDs match `tt\d{7,8}` pattern
- Reject entire request if any ID is malformed
- Cap batch size at 50 IDs

### Timeout & Disconnect

- Overall request timeout: 60 seconds
- If timeout hit, send `done` event with partial results
- If client disconnects, cancel pending fetch tasks

## Implementation

### RT API Changes

| File | Changes |
|------|---------|
| `app/api/routes.py` | Add `POST /movies/batch` endpoint with SSE response |
| `app/services/cache.py` | Add `get_cached_batch(imdb_ids: list[str])` for bulk SELECT |
| `app/services/scraper.py` | Increase semaphore from 1 → 2 |
| `app/services/wikidata.py` | Add semaphore (5 concurrent) |
| `app/models/schemas.py` | Add `BatchRequest` and `BatchMovieEvent` schemas |

### Cinematch Integration

```typescript
async function getBatchRTRatings(imdbIds: string[]): Promise<Map<string, RTData>> {
  const results = new Map<string, RTData>();

  const response = await fetch(`${RT_API_URL}/api/v1/movies/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
    body: JSON.stringify({ imdbIds }),
  });

  // Parse SSE stream
  for await (const chunk of readSSEStream(response)) {
    if (chunk.event === 'movie') {
      results.set(chunk.data.imdbId, chunk.data);
    }
  }

  return results;
}
```

## Expected Performance

| Scenario | Before | After |
|----------|--------|-------|
| 30 movies, all cached | ~3s | <200ms |
| 30 movies, 10 cache miss | ~25s | ~6s |
| 30 movies, all cache miss | ~60s+ | ~18s |

First cached results arrive in <100ms regardless of cache misses.
