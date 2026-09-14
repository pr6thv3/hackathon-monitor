"""
HackerEarth Fetcher — API-first with Playwright structured DOM fallback.

Primary: Queries HackerEarth's public upcoming events API (https://www.hackerearth.com/api/events/upcoming/)
         for structured challenge objects with guaranteed URLs and deadlines.
Secondary: HackerEarth chrome-extension events endpoint.
Fallback: Playwright headless Chromium with card-level DOM extraction (never plain body inner_text).
"""

import json
import logging
import requests as http_requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

HACKEREARTH_UPCOMING_API = "https://www.hackerearth.com/api/events/upcoming/"
HACKEREARTH_CHROME_API = "https://www.hackerearth.com/chrome-extension/events/"
HACKEREARTH_PAGE_URL = "https://www.hackerearth.com/challenges/"
TIMEOUT_MS = 60_000


def _fetch_upcoming_api() -> str | None:
    """Try HackerEarth public upcoming events API."""
    log.info(f"Attempting HackerEarth upcoming events API ({HACKEREARTH_UPCOMING_API})...")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    try:
        resp = http_requests.get(HACKEREARTH_UPCOMING_API, headers=headers, timeout=20)
        if resp.status_code != 200:
            log.warning(f"HackerEarth upcoming API returned HTTP {resp.status_code}")
            return None

        data = resp.json()
        events = data.get("response", []) if isinstance(data, dict) else []
        if not events:
            return None

        lines = ["--- SOURCE: HACKEREARTH ---"]
        for e in events:
            if isinstance(e, dict):
                title = e.get("title", "Unknown")
                url = e.get("url", "")
                desc = e.get("description", "")
                ctype = e.get("challenge_type", "")
                start = e.get("date", "")
                end = e.get("end_date", "")

                if url and not url.startswith("http"):
                    url = f"https://www.hackerearth.com{url}" if url.startswith("/") else f"https://{url}"

                lines.append(f"\nTitle: {title}")
                if url:
                    lines.append(f"Link: {url}")
                if ctype:
                    lines.append(f"Type: {ctype}")
                if start or end:
                    lines.append(f"Dates: {start} to {end}".strip())
                if desc:
                    lines.append(f"Description: {str(desc)[:300]}")

        result = "\n".join(lines)
        log.info(f"HackerEarth upcoming API returned {len(events)} events ({len(result)} chars)")
        return result
    except Exception as e:
        log.warning(f"HackerEarth upcoming API failed: {e}")
        return None


def _fetch_chrome_api() -> str | None:
    """Secondary: HackerEarth chrome-extension events endpoint."""
    log.info(f"Attempting HackerEarth chrome API ({HACKEREARTH_CHROME_API})...")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    try:
        resp = http_requests.get(HACKEREARTH_CHROME_API, headers=headers, timeout=20)
        if resp.status_code != 200:
            return None

        data = resp.json()
        events = []
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict):
            events = data.get("response", data.get("events", data.get("challenges", [])))
            if not events:
                events = data.get("ongoing", []) + data.get("upcoming", [])

        if not events:
            return None

        lines = ["--- SOURCE: HACKEREARTH ---"]
        for e in events:
            if isinstance(e, dict):
                title = e.get("title", e.get("name", "Unknown"))
                url = e.get("url", e.get("link", ""))
                start = e.get("start_datetime", e.get("start_time", ""))
                end = e.get("end_datetime", e.get("end_time", ""))
                ctype = e.get("challenge_type", e.get("type", ""))
                desc = e.get("description", e.get("tagline", ""))

                if url and not url.startswith("http"):
                    url = f"https://www.hackerearth.com{url}" if url.startswith("/") else f"https://{url}"

                lines.append(f"\nTitle: {title}")
                if url:
                    lines.append(f"Link: {url}")
                if ctype:
                    lines.append(f"Type: {ctype}")
                if start or end:
                    lines.append(f"Dates: {start} to {end}".strip())
                if desc:
                    lines.append(f"Description: {str(desc)[:300]}")

        result = "\n".join(lines)
        log.info(f"HackerEarth chrome API returned {len(events)} events ({len(result)} chars)")
        return result
    except Exception as e:
        log.warning(f"HackerEarth chrome API failed: {e}")
        return None


def _fetch_via_playwright() -> str | None:
    """Fallback: Playwright structured card extraction from HackerEarth challenges page."""
    log.info(f"Falling back to Playwright for HackerEarth: {HACKEREARTH_PAGE_URL}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
            )
            page.goto(HACKEREARTH_PAGE_URL, wait_until="networkidle", timeout=TIMEOUT_MS)
            page.wait_for_timeout(3000)

            # Query challenge cards
            cards = page.query_selector_all(".challenge-card, .challenge-card-modern, [class*='challenge-card']")
            events = []
            for c in cards:
                title_el = c.query_selector(".challenge-name, .challenge-title, h3, h4")
                link_el = c.query_selector("a[href*='/challenges/']")
                date_el = c.query_selector(".date, .challenge-date, .time")
                type_el = c.query_selector(".challenge-type, .badge")

                title = title_el.inner_text().strip() if title_el else ""
                link = link_el.get_attribute("href") if link_el else ""
                if link and not link.startswith("http"):
                    link = f"https://www.hackerearth.com{link}" if link.startswith("/") else f"https://{link}"
                date = date_el.inner_text().strip() if date_el else ""
                ctype = type_el.inner_text().strip() if type_el else ""

                if title:
                    events.append({"title": title, "link": link, "date": date, "type": ctype})

            browser.close()
            if not events:
                return None

            lines = ["--- SOURCE: HACKEREARTH ---"]
            for e in events:
                lines.append(f"\nTitle: {e['title']}")
                if e["link"]:
                    lines.append(f"Link: {e['link']}")
                if e["type"]:
                    lines.append(f"Type: {e['type']}")
                if e["date"]:
                    lines.append(f"Dates: {e['date']}")

            result = "\n".join(lines)
            log.info(f"HackerEarth Playwright extracted {len(events)} cards ({len(result)} chars)")
            return result
    except PlaywrightTimeout:
        log.error(f"HackerEarth Playwright timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"HackerEarth Playwright failed: {e}")
        return None


def fetch_hackerearth() -> str | None:
    """Fetch HackerEarth listings with multi-tier resilience."""
    # 1. Primary: upcoming events API
    res = _fetch_upcoming_api()
    if res:
        return res

    # 2. Secondary: chrome extension endpoint
    res = _fetch_chrome_api()
    if res:
        return res

    # 3. Fallback: structured Playwright
    return _fetch_via_playwright()
