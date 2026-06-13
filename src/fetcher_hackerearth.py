"""
HackerEarth Fetcher — API-first (Chrome extension endpoint) with Playwright fallback.

Primary: Hits HackerEarth's chrome-extension API for structured JSON.
Fallback: Uses Playwright headless Chromium if the API is blocked or structure changes.
Both approaches are 100% free forever.
"""

import json
import logging
import requests as http_requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

HACKEREARTH_API_URL = "https://www.hackerearth.com/chrome-extension/events/"
HACKEREARTH_PAGE_URL = "https://www.hackerearth.com/challenges/"
TIMEOUT_MS = 60_000  # 60 seconds


def _fetch_via_api() -> str | None:
    """
    Try HackerEarth's chrome-extension API endpoint.
    Returns a formatted text summary of hackathons, or None on failure.
    """
    log.info("Attempting HackerEarth API call...")

    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }

    try:
        response = http_requests.get(
            HACKEREARTH_API_URL,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            log.warning(f"HackerEarth API returned HTTP {response.status_code}")
            return None

        data = response.json()
        
        # HackerEarth chrome extension response typically has a structure with list of events
        # Let's inspect data structures. It could be a list or a dict.
        events = []
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict):
            # Try some common keys
            events = data.get("response", data.get("events", data.get("challenges", [])))
            if not events and "upcoming" in data or "ongoing" in data:
                events = data.get("ongoing", []) + data.get("upcoming", [])

        if not events:
            log.warning("HackerEarth API returned empty or unexpected structure")
            return f"--- SOURCE: HACKEREARTH (raw API response) ---\n{json.dumps(data, indent=2)[:5000]}"

        lines = ["--- SOURCE: HACKEREARTH ---"]
        for e in events:
            if isinstance(e, dict):
                title = e.get("title", e.get("name", "Unknown"))
                # Sometimes starts and ends are formatted differently
                start = e.get("start_datetime", e.get("start_time", ""))
                end = e.get("end_datetime", e.get("end_time", ""))
                link = e.get("url", e.get("link", ""))
                challenge_type = e.get("challenge_type", e.get("type", ""))
                description = e.get("description", e.get("tagline", ""))
                
                # Check for clean URL
                if link and not link.startswith("http"):
                    link = f"https://www.hackerearth.com{link}" if link.startswith("/") else f"https://{link}"

                lines.append(f"\nTitle: {title}")
                if challenge_type:
                    lines.append(f"Type: {challenge_type}")
                if start:
                    lines.append(f"Start: {start}")
                if end:
                    lines.append(f"End: {end}")
                if link:
                    lines.append(f"Link: {link}")
                if description:
                    lines.append(f"Description: {str(description)[:300]}")

        result = "\n".join(lines)
        log.info(f"HackerEarth API returned {len(events)} hackathons ({len(result)} chars)")
        return result

    except http_requests.RequestException as e:
        log.warning(f"HackerEarth API request failed: {e}")
        return None
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.warning(f"HackerEarth API response parsing error: {e}")
        return None


def _fetch_via_playwright() -> str | None:
    """
    Fallback: Use Playwright to render the HackerEarth challenges page and extract text.
    """
    log.info(f"Falling back to Playwright for HackerEarth: {HACKEREARTH_PAGE_URL}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )

            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
            )

            page.goto(HACKEREARTH_PAGE_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

            # Wait for content to render
            page.wait_for_timeout(3000)

            # Scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(2000)

            content = page.inner_text("body")
            browser.close()

            if not content or len(content.strip()) < 100:
                log.warning("HackerEarth Playwright returned very little content")
                return None

            log.info(f"HackerEarth Playwright scraped {len(content)} chars")
            return f"--- SOURCE: HACKEREARTH ---\n{content}"

    except PlaywrightTimeout:
        log.error(f"HackerEarth Playwright timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"HackerEarth Playwright failed: {e}")
        return None


def fetch_hackerearth() -> str | None:
    """
    Fetch hackathon listings from HackerEarth.
    Strategy: Try API first, fall back to Playwright.
    """
    result = _fetch_via_api()
    if result:
        return result
    return _fetch_via_playwright()
