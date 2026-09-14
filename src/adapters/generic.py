"""
Generic College Portal Adapter — Playwright DOM card scraper.

Provides pluggable support for any university or collegiate portal
by querying semantic HTML elements (.event-card, [data-event-id], article)
and strictly extracting actual hyperlinks.
"""

import logging
from typing import Any
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from src.adapters.base import CollegePortalAdapter

log = logging.getLogger(__name__)

TIMEOUT_MS = 60_000

COMMON_EVENT_SELECTORS = [
    ".event-card",
    ".event-item",
    "[data-event-id]",
    ".opportunity-card",
    ".activity-card",
    "article.event",
    "[class*='event'][class*='card']",
    ".card",
]


class GenericPlaywrightAdapter(CollegePortalAdapter):
    adapter_id = "generic"

    def fetch_events(self, config: dict[str, Any]) -> str | None:
        url = config.get("url")
        if not url:
            log.warning("GenericPlaywrightAdapter requires a 'url' in configuration")
            return None

        log.info(f"Generic Adapter: Fetching {url}")
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

                page.goto(url, wait_until="networkidle", timeout=TIMEOUT_MS)
                page.wait_for_timeout(2500)

                # Find cards
                cards = []
                for sel in COMMON_EVENT_SELECTORS:
                    els = page.query_selector_all(sel)
                    if els:
                        cards = els
                        log.info(f"Found {len(cards)} event elements using selector '{sel}'")
                        break

                events = []
                for c in cards:
                    title_el = c.query_selector("h2, h3, h4, .title, .name")
                    link_el = c.query_selector("a[href]")
                    date_el = c.query_selector(".date, .time, [class*='date']")
                    desc_el = c.query_selector("p, .desc, .description")

                    title = title_el.inner_text().strip() if title_el else ""
                    link = link_el.get_attribute("href") if link_el else ""
                    if link and not link.startswith("http"):
                        link = f"{url.rstrip('/')}/{link.lstrip('/')}"
                    date = date_el.inner_text().strip() if date_el else ""
                    desc = desc_el.inner_text().strip() if desc_el else ""

                    if title:
                        events.append({
                            "title": title,
                            "link": link,
                            "date": date,
                            "desc": desc,
                        })

                browser.close()

                if not events:
                    log.warning(f"No structured event cards found on {url}")
                    return None

                portal_name = config.get("name", "COLLEGE PORTAL").upper()
                lines = [f"--- SOURCE: {portal_name} ---"]
                for e in events:
                    lines.append(f"\nTitle: {e['title']}")
                    if e["link"]:
                        lines.append(f"Link: {e['link']}")
                    if e["date"]:
                        lines.append(f"Date: {e['date']}")
                    if e["desc"]:
                        lines.append(f"Description: {e['desc'][:300]}")

                result = "\n".join(lines)
                log.info(f"Generic adapter extracted {len(events)} events ({len(result)} chars)")
                return result

        except PlaywrightTimeout:
            log.error(f"Generic adapter timed out for {url}")
            return None
        except Exception as e:
            log.error(f"Generic adapter failed for {url}: {e}")
            return None
