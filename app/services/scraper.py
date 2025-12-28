import httpx
import asyncio
import json
import re
from typing import Optional
from bs4 import BeautifulSoup
import logging

from app.models.schemas import RTMovieData
from app.config import get_settings

logger = logging.getLogger(__name__)

RT_BASE_URL = "https://www.rottentomatoes.com"

# Rate limiting semaphore
_rt_semaphore = asyncio.Semaphore(1)


async def scrape_movie(rt_slug: str) -> Optional[RTMovieData]:
    """
    Scrape Rotten Tomatoes movie page for scores and metadata.

    Args:
        rt_slug: RT slug (e.g., 'm/the_dark_knight')

    Returns:
        RTMovieData with scraped information, or None if scraping fails
    """
    settings = get_settings()
    url = f"{RT_BASE_URL}/{rt_slug}"

    async with _rt_semaphore:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    },
                    follow_redirects=True,
                )
                response.raise_for_status()

            # Polite delay between requests
            await asyncio.sleep(settings.rt_request_delay)

            html = response.text
            soup = BeautifulSoup(html, "lxml")

            # Try JSON-LD first (most reliable)
            data = _parse_json_ld(soup, rt_slug)

            # Fall back to HTML parsing
            if not data:
                data = _parse_html(soup, rt_slug)

            # Enrich with additional HTML data
            if data:
                data = _enrich_with_html(soup, data)

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"RT HTTP error for {rt_slug}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"RT request error for {rt_slug}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping RT {rt_slug}: {e}")
            return None


def _parse_json_ld(soup: BeautifulSoup, rt_slug: str) -> Optional[RTMovieData]:
    """Parse JSON-LD structured data from the page."""
    try:
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)

                # Handle both single object and array formats
                if isinstance(data, list):
                    data = next((d for d in data if d.get("@type") == "Movie"), None)

                if data and data.get("@type") == "Movie":
                    # Extract aggregate rating
                    agg_rating = data.get("aggregateRating", {})

                    return RTMovieData(
                        rt_slug=rt_slug,
                        title=data.get("name", ""),
                        year=_extract_year(data.get("datePublished")),
                        critic_score=_safe_int(agg_rating.get("ratingValue")),
                        audience_score=None,  # Not in JSON-LD, get from HTML
                        critic_rating=None,  # Get from HTML
                        audience_rating=None,  # Get from HTML
                        consensus=None,  # Get from HTML
                    )
            except json.JSONDecodeError:
                continue

    except Exception as e:
        logger.debug(f"JSON-LD parsing failed for {rt_slug}: {e}")

    return None


def _parse_html(soup: BeautifulSoup, rt_slug: str) -> Optional[RTMovieData]:
    """Parse scores directly from HTML elements."""
    try:
        title = ""
        year = None

        # Get title
        title_elem = soup.find("h1", {"data-qa": "score-panel-title"})
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Alternative title location
        if not title:
            title_elem = soup.find("h1", class_=re.compile(r"title"))
            if title_elem:
                title = title_elem.get_text(strip=True)

        # Get year from title or metadata
        year_match = soup.find("span", {"data-qa": "score-panel-subtitle"})
        if year_match:
            year_text = year_match.get_text(strip=True)
            year = _extract_year(year_text)

        return RTMovieData(
            rt_slug=rt_slug,
            title=title,
            year=year,
            critic_score=None,
            audience_score=None,
            critic_rating=None,
            audience_rating=None,
            consensus=None,
        )

    except Exception as e:
        logger.debug(f"HTML parsing failed for {rt_slug}: {e}")
        return None


def _enrich_with_html(soup: BeautifulSoup, data: RTMovieData) -> RTMovieData:
    """Enrich RTMovieData with additional data from HTML."""
    try:
        # Find score-board or media-scorecard element
        score_board = soup.find("media-scorecard")
        if not score_board:
            score_board = soup.find("score-board")

        if score_board:
            # Critic score (Tomatometer)
            critic_score = score_board.get("tomatometerscore")
            if critic_score:
                data.critic_score = _safe_int(critic_score)

            # Audience score
            audience_score = score_board.get("audiencescore")
            if audience_score:
                data.audience_score = _safe_int(audience_score)

            # Critic rating (certified_fresh, fresh, rotten)
            critic_state = score_board.get("tomatometerstate")
            if critic_state:
                data.critic_rating = critic_state.lower().replace("-", "_")

            # Audience rating (upright, spilled)
            audience_state = score_board.get("audiencestate")
            if audience_state:
                data.audience_rating = audience_state.lower()

        # Alternative: look for rt-button or score elements
        if not data.critic_score:
            tomatometer = soup.find("rt-button", {"slot": "criticsScore"})
            if tomatometer:
                score_text = tomatometer.get_text(strip=True)
                data.critic_score = _safe_int(score_text.replace("%", ""))

        if not data.audience_score:
            audience = soup.find("rt-button", {"slot": "audienceScore"})
            if audience:
                score_text = audience.get_text(strip=True)
                data.audience_score = _safe_int(score_text.replace("%", ""))

        # Get consensus
        consensus_elem = soup.find("span", {"data-qa": "critics-consensus"})
        if consensus_elem:
            data.consensus = consensus_elem.get_text(strip=True)

        # Alternative consensus location
        if not data.consensus:
            consensus_elem = soup.find("p", {"data-qa": "critics-consensus"})
            if consensus_elem:
                data.consensus = consensus_elem.get_text(strip=True)

    except Exception as e:
        logger.debug(f"HTML enrichment failed: {e}")

    return data


def _extract_year(date_str: Optional[str]) -> Optional[int]:
    """Extract year from a date string."""
    if not date_str:
        return None

    # Try to find a 4-digit year
    match = re.search(r"\b(19|20)\d{2}\b", str(date_str))
    if match:
        return int(match.group())

    return None


def _safe_int(value) -> Optional[int]:
    """Safely convert value to int."""
    if value is None:
        return None
    try:
        # Handle string percentages like "94%"
        if isinstance(value, str):
            value = value.replace("%", "").strip()
        return int(float(value))
    except (ValueError, TypeError):
        return None
