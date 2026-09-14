"""
Devpost Fetcher — API-first with Playwright structured DOM fallback.

Primary: Queries Devpost's public hackathons API for clean, structured JSON
         with guaranteed real URLs, prizes, tags, and deadlines.
Fallback: Uses Playwright headless Chromium with card-level DOM extraction
          to preserve hyperlinks (never plain body inner_text).
"""

import json
import logging
import re
import requests as http_requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

DEVPOST_API_URL = "https://devpost.com/api/hackathons"
DEVPOST_PAGE_URL = "https://devpost.com/hackathons"
TIMEOUT_MS = 60_000


def _clean_html_tags(text: str) -> str:
    """Strip HTML markup from strings (e.g. <span> tags in prize values)."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _fetch_via_api(pages: int = 2) -> str | None:
    """
    Fetch hackathon listings directly from Devpost's public API.
    Guarantees non-null hyperlinks and structured data.
    """
    log.info(f"Attempting Devpost public API fetch ({DEVPOST_API_URL})...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    all_hackathons = []
    for page in range(1, pages + 1):
        try:
            params = {
                "status[]": ["upcoming", "open"],
                "page": page,
            }
            resp = http_requests.get(
                DEVPOST_API_URL,
                headers=headers,
                params=params,
                timeout=20,
            )
            if resp.status_code != 200:
                log.warning(f"Devpost API returned HTTP {resp.status_code} for page {page}")
                break

            data = resp.json()
            hackathons = data.get("hackathons", [])
            if not hackathons:
                break
            all_hackathons.extend(hackathons)
        except Exception as e:
            log.warning(f"Devpost API request failed on page {page}: {e}")
            break

    if not all_hackathons:
        log.warning("Devpost API returned no hackathons")
        return None

    lines = ["--- SOURCE: DEVPOST ---"]
    for h in all_hackathons:
        title = h.get("title", "Unknown")
        url = h.get("url", "")
        dates = h.get("submission_period_dates", "")
        time_left = h.get("time_left_to_submission", "")
        prize_raw = h.get("prize_amount", "")
        prize = _clean_html_tags(prize_raw)
        org = h.get("organization_name", "")
        location_dict = h.get("displayed_location", {})
        location = location_dict.get("location", "Online") if isinstance(location_dict, dict) else "Online"
        themes = [t.get("name") for t in h.get("themes", []) if isinstance(t, dict) and t.get("name")]

        lines.append(f"\nTitle: {title}")
        if url:
            lines.append(f"Link: {url}")
        if dates:
            lines.append(f"Dates: {dates}")
        if time_left:
            lines.append(f"Time Left: {time_left}")
        if prize:
            lines.append(f"Prize: {prize}")
        if org:
            lines.append(f"Organizer: {org}")
        if location:
            lines.append(f"Mode: {location}")
        if themes:
            lines.append(f"Themes: {', '.join(themes)}")

    result = "\n".join(lines)
    log.info(f"Devpost API returned {len(all_hackathons)} hackathons ({len(result)} chars)")
    return result


def _fetch_via_playwright() -> str | None:
    """
    Fallback: Scrape Devpost using Playwright with card-level DOM extraction.
    Extracts explicit <a> tags and attributes rather than flattening to body text.
    """
    log.info(f"Falling back to Playwright structured extraction for Devpost: {DEVPOST_PAGE_URL}")

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

            page.goto(DEVPOST_PAGE_URL, wait_until="networkidle", timeout=TIMEOUT_MS)
            page.wait_for_timeout(2500)

            # Query individual hackathon cards
            card_selectors = [
                ".hackathon-tile",
                "article.hackathon-tile",
                "[data-hackathon-id]",
                ".challenge-card",
            ]
            cards = []
            for sel in card_selectors:
                elements = page.query_selector_all(sel)
                if elements:
                    cards = elements
                    break

            events = []
            if cards:
                for card in cards:
                    title_el = card.query_selector("h3, .title, h2, [data-role='title']")
                    link_el = card.query_selector("a[href]")
                    deadline_el = card.query_selector(".deadline, .submission-period, .time-left")
                    prize_el = card.query_selector(".prize-amount, .prize")

                    title = title_el.inner_text().strip() if title_el else ""
                    link = link_el.get_attribute("href") if link_el else ""
                    if link and not link.startswith("http"):
                        link = f"https://devpost.com{link}" if link.startswith("/") else link
                    deadline = deadline_el.inner_text().strip() if deadline_el else ""
                    prize = prize_el.inner_text().strip() if prize_el else ""

                    if title:
                        events.append({
                            "title": title,
                            "link": link,
                            "deadline": deadline,
                            "prize": prize,
                        })

            browser.close()

            if not events:
                log.warning("Devpost Playwright fallback found 0 structured cards")
                return None

            lines = ["--- SOURCE: DEVPOST ---"]
            for e in events:
                lines.append(f"\nTitle: {e['title']}")
                if e["link"]:
                    lines.append(f"Link: {e['link']}")
                if e["deadline"]:
                    lines.append(f"Dates: {e['deadline']}")
                if e["prize"]:
                    lines.append(f"Prize: {e['prize']}")

            result = "\n".join(lines)
            log.info(f"Devpost Playwright extracted {len(events)} cards ({len(result)} chars)")
            return result

    except PlaywrightTimeout:
        log.error(f"Devpost Playwright timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"Devpost Playwright fallback failed: {e}")
        return None


def fetch_devpost() -> str | None:
    """
    Fetch hackathon listings from Devpost.
    Strategy: Try API first (reliable, guaranteed links), fall back to Playwright.
    """
    result = _fetch_via_api()
    if result:
        return result
    return _fetch_via_playwright()
