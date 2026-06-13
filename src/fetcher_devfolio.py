"""
Devfolio Fetcher — API-first with Playwright fallback.

Primary: Hits Devfolio's internal search API for structured JSON data.
Fallback: Uses Playwright headless Chromium if the API is blocked/changed.
Both approaches are 100% free forever.
"""

import json
import logging

import requests as http_requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

DEVFOLIO_API_URL = "https://api.devfolio.co/api/search/hackathons"
DEVFOLIO_PAGE_URL = "https://devfolio.co/hackathons"
TIMEOUT_MS = 60_000  # 60 seconds


def _fetch_via_api() -> str | None:
    """
    Try Devfolio's internal search API directly.
    Returns a formatted text summary of hackathons, or None on failure.
    """
    log.info("Attempting Devfolio API call...")

    payload = {
        "q": "",
        "filter": {"status": ["open", "upcoming"]},
        "size": 30,
        "from": 0,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }

    try:
        response = http_requests.post(
            DEVFOLIO_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            log.warning(f"Devfolio API returned HTTP {response.status_code}")
            return None

        data = response.json()

        # Extract hackathon list from response
        hackathons = data.get("hits", data.get("results", []))
        if isinstance(hackathons, dict) and "hits" in hackathons:
            hackathons = hackathons["hits"]

        if not hackathons:
            # Try alternate response structure
            if isinstance(data, list):
                hackathons = data
            else:
                log.warning("Devfolio API returned unexpected structure")
                log.debug(f"API response keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                # Return raw JSON as text for Gemini to parse
                return f"--- SOURCE: DEVFOLIO (raw API response) ---\n{json.dumps(data, indent=2)[:5000]}"

        # Format into readable text for Gemini
        lines = ["--- SOURCE: DEVFOLIO ---"]
        for h in hackathons:
            # Handle different possible response structures
            if isinstance(h, dict):
                if "_source" in h:
                    h = h["_source"]
                name = h.get("name", h.get("title", "Unknown"))
                slug = h.get("slug", "")
                starts = h.get("starts_at", h.get("start_date", ""))
                ends = h.get("ends_at", h.get("end_date", ""))
                status = h.get("status", "")
                desc = h.get("desc", h.get("description", h.get("tagline", "")))
                prize = h.get("prize_amount", h.get("prize", ""))
                mode = h.get("mode", h.get("is_online", ""))
                themes = h.get("themes", h.get("tags", []))

                link = f"https://{slug}.devfolio.co" if slug else ""

                lines.append(f"\nTitle: {name}")
                if starts:
                    lines.append(f"Date: {starts}" + (f" to {ends}" if ends else ""))
                if status:
                    lines.append(f"Status: {status}")
                if link:
                    lines.append(f"Link: {link}")
                if desc:
                    lines.append(f"Description: {str(desc)[:300]}")
                if prize:
                    lines.append(f"Prize: {prize}")
                if mode:
                    lines.append(f"Mode: {mode}")
                if themes and isinstance(themes, list):
                    lines.append(f"Themes: {', '.join(str(t) for t in themes)}")

        result = "\n".join(lines)
        log.info(f"Devfolio API returned {len(hackathons)} hackathons ({len(result)} chars)")
        return result

    except http_requests.RequestException as e:
        log.warning(f"Devfolio API request failed: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        log.warning(f"Devfolio API response parsing error: {e}")
        return None


def _fetch_via_playwright() -> str | None:
    """
    Fallback: Use Playwright to render the Devfolio page and extract text.
    """
    log.info(f"Falling back to Playwright for Devfolio: {DEVFOLIO_PAGE_URL}")

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

            page.goto(DEVFOLIO_PAGE_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

            # Wait for content to render
            page.wait_for_timeout(3000)

            # Try scrolling to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(2000)

            content = page.inner_text("body")
            browser.close()

            if not content or len(content.strip()) < 100:
                log.warning("Devfolio Playwright returned very little content")
                return None

            log.info(f"Devfolio Playwright scraped {len(content)} chars")
            return f"--- SOURCE: DEVFOLIO ---\n{content}"

    except PlaywrightTimeout:
        log.error(f"Devfolio Playwright timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"Devfolio Playwright failed: {e}")
        return None


def fetch_devfolio() -> str | None:
    """
    Fetch hackathon listings from Devfolio.

    Strategy: Try internal API first (fast, structured), fall back to Playwright.

    Returns:
        Formatted text content for Gemini analysis, or None on total failure.
    """
    # Try API first
    result = _fetch_via_api()
    if result:
        return result

    # Fall back to Playwright
    log.info("Devfolio API failed — trying Playwright fallback")
    return _fetch_via_playwright()
