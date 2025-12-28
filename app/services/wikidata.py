import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# SPARQL query to get RT ID from IMDB ID
# P345 = IMDB ID, P1258 = Rotten Tomatoes ID
SPARQL_QUERY = """
SELECT ?rtId WHERE {{
  ?film wdt:P345 "{imdb_id}" .
  ?film wdt:P1258 ?rtId .
}}
"""


async def get_rt_slug(imdb_id: str) -> Optional[str]:
    """
    Query Wikidata to get the Rotten Tomatoes slug for a given IMDB ID.

    Args:
        imdb_id: IMDB ID (e.g., 'tt0468569')

    Returns:
        RT slug (e.g., 'm/the_dark_knight') or None if not found
    """
    query = SPARQL_QUERY.format(imdb_id=imdb_id)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                WIKIDATA_SPARQL_URL,
                params={"query": query, "format": "json"},
                headers={
                    "Accept": "application/sparql-results+json",
                    "User-Agent": "RT-API/1.0 (Personal movie data service)",
                },
            )
            response.raise_for_status()

            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])

            if bindings:
                rt_id = bindings[0].get("rtId", {}).get("value")
                logger.info(f"Found RT slug for {imdb_id}: {rt_id}")
                return rt_id

            logger.warning(f"No RT slug found in Wikidata for {imdb_id}")
            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"Wikidata HTTP error for {imdb_id}: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Wikidata request error for {imdb_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error querying Wikidata for {imdb_id}: {e}")
        return None
