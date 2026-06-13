"""
DoraHacks Fetcher — API-first with Playwright fallback.

Primary: Hits DoraHacks' REST API for structured JSON.
Fallback: Uses Playwright headless Chromium if the API is blocked or structure changes.
Both approaches are 100% free forever.
"""

import json
import logging
import requests as http_requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

DORAHACKS_API_URL = "https://dorahacks.io/api/hackathon/list"
DORAHACKS_PAGE_URL = "https://dorahacks.io/hackathon"
TIMEOUT_MS = 60_000  # 60 seconds


def _fetch_via_api() -> str | None:
    """
    Try DoraHacks' REST API directly.
    Returns a formatted text summary of hackathons, or None on failure.
    """
    log.info("Attempting DoraHacks API call...")

    payload = {
        "page": 1,
        "page_size": 20,
        "status": "active"
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
            DORAHACKS_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            log.warning(f"DoraHacks API returned HTTP {response.status_code}")
            return None

        data = response.json()
        
        # DoraHacks list response typically has a structure like data.list, or data.data.list, or results
        opps = []
        if isinstance(data, dict):
            # Try nested list
            nested_data = data.get("data", {})
            if isinstance(nested_data, dict):
                opps = nested_data.get("list", nested_data.get("items", []))
            else:
                opps = data.get("list", data.get("items", data.get("results", [])))
        elif isinstance(data, list):
            opps = data

        if not opps:
            log.warning("DoraHacks API returned empty or unexpected structure")
            return f"--- SOURCE: DORAHACKS (raw API response) ---\n{json.dumps(data, indent=2)[:5000]}"

        lines = ["--- SOURCE: DORAHACKS ---"]
        for o in opps:
            if isinstance(o, dict):
                title = o.get("name", o.get("title", "Unknown"))
                # DoraHacks might have a slug or ID for links
                slug = o.get("slug", o.get("id", ""))
                link = f"https://dorahacks.io/hackathon/{slug}" if slug else ""
                
                # Check for start/end times
                start = o.get("start_time", o.get("startTime", ""))
                end = o.get("end_time", o.get("endTime", ""))
                prize = o.get("prize", o.get("prizePool", o.get("reward", "")))
                tagline = o.get("tagline", o.get("description", ""))

                lines.append(f"\nTitle: {title}")
                if start:
                    lines.append(f"Start: {start}")
                if end:
                    lines.append(f"End: {end}")
                if link:
                    lines.append(f"Link: {link}")
                if tagline:
                    lines.append(f"Description: {str(tagline)[:300]}")
                if prize:
                    lines.append(f"Prize Pool: {prize}")

        result = "\n".join(lines)
        log.info(f"DoraHacks API returned {len(opps)} hackathons ({len(result)} chars)")
        return result

    except http_requests.RequestException as e:
        log.warning(f"DoraHacks API request failed: {e}")
        return None
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.warning(f"DoraHacks API response parsing error: {e}")
        return None


def _fetch_via_playwright() -> str | None:
    """
    Fallback: Use Playwright to render the DoraHacks page and extract text.
    """
    log.info(f"Falling back to Playwright for DoraHacks: {DORAHACKS_PAGE_URL}")

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

            page.goto(DORAHACKS_PAGE_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

            # Wait for content to render
            page.wait_for_timeout(3000)

            # Scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(2000)

            content = page.inner_text("body")
            browser.close()

            if not content or len(content.strip()) < 100:
                log.warning("DoraHacks Playwright returned very little content")
                return None

            log.info(f"DoraHacks Playwright scraped {len(content)} chars")
            return f"--- SOURCE: DORAHACKS ---\n{content}"

    except PlaywrightTimeout:
        log.error(f"DoraHacks Playwright timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"DoraHacks Playwright failed: {e}")
        return None


def fetch_dorahacks() -> str | None:
    """
    Fetch hackathon listings from DoraHacks.
    Strategy: Try API first, fall back to Playwright.
    """
    result = _fetch_via_api()
    if result:
        return result
    return _fetch_via_playwright()
