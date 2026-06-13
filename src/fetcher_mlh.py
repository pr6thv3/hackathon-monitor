"""
MLH Fetcher — requests + BeautifulSoup.

Scrapes Major League Hacking (MLH) events list directly from their static/server-rendered HTML.
MLH pages do not require a full headless browser since the Rails application renders cards server-side.
This approach is extremely fast, lightweight, and 100% free.
"""

import logging
import requests as http_requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

MLH_URL = "https://mlh.io/seasons/2026/events"
TIMEOUT_SECONDS = 30


def fetch_mlh() -> str | None:
    """
    Fetch hackathon listings from MLH using requests + BeautifulSoup.

    Returns:
        Formatted text content for Gemini analysis, or None on failure.
    """
    log.info(f"Fetching MLH events from {MLH_URL}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }

    try:
        response = http_requests.get(
            MLH_URL,
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            log.warning(f"MLH page returned HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Find all event wrappers
        # Typically MLH uses .event-wrapper, or div elements inside the event list container
        event_cards = soup.select(".event-wrapper, .event")
        
        lines = ["--- SOURCE: MLH ---"]
        
        if not event_cards:
            # Fallback: parse whatever cards/links are in the document body
            log.info("No explicit event cards found. Parsing body text...")
            body_text = soup.body.get_text() if soup.body else ""
            if len(body_text.strip()) > 100:
                return f"--- SOURCE: MLH ---\n{body_text[:10000]}"
            return None

        for card in event_cards:
            # Extract title
            title_el = card.select_one(".event-name, h3, .title")
            title = title_el.get_text(strip=True) if title_el else "Unknown"

            # Extract link
            link_el = card.select_one("a[href]")
            link = link_el["href"] if link_el else ""
            if link and not link.startswith("http"):
                link = f"https://mlh.io{link}" if link.startswith("/") else link

            # Extract date
            date_el = card.select_one(".event-date, .date")
            date = date_el.get_text(strip=True) if date_el else ""

            # Extract location
            loc_el = card.select_one(".event-location, .location")
            location = loc_el.get_text(strip=True) if loc_el else ""

            # Extract type (online vs hybrid vs in-person)
            # MLH cards sometimes have badges or icons
            badge_el = card.select_one(".event-type, .badge")
            badge = badge_el.get_text(strip=True) if badge_el else ""

            lines.append(f"\nTitle: {title}")
            if date:
                lines.append(f"Date: {date}")
            if location:
                lines.append(f"Location: {location}")
            if badge:
                lines.append(f"Type: {badge}")
            if link:
                lines.append(f"Link: {link}")

        result = "\n".join(lines)
        log.info(f"Successfully scraped MLH ({len(event_cards)} events, {len(result)} chars)")
        return result

    except http_requests.RequestException as e:
        log.error(f"Failed to scrape MLH: {e}")
        return None
    except Exception as e:
        log.error(f"Error parsing MLH content: {e}")
        return None
