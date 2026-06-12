"""
Devpost Fetcher — Playwright-based scraper.

Scrapes https://devpost.com/hackathons using headless Chromium.
Devpost is a JS-rendered SPA, so requests+BeautifulSoup won't work.
Playwright is free forever — no API credits needed.
"""

import logging

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

DEVPOST_URL = "https://devpost.com/hackathons"
TIMEOUT_MS = 60_000  # 60 seconds


def fetch_devpost() -> str | None:
    """
    Launch headless Chromium, navigate to Devpost hackathons page,
    wait for JS to render, and return the page text content.

    Returns:
        Page text content as a string, or None on failure.
    """
    log.info(f"Fetching Devpost hackathons from {DEVPOST_URL}")

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

            # Navigate and wait for the page to finish loading
            page.goto(DEVPOST_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

            # Wait a moment for any lazy-loaded content
            page.wait_for_timeout(2000)

            # Extract the text content of the page body
            content = page.inner_text("body")

            browser.close()

            if not content or len(content.strip()) < 100:
                log.warning("Devpost returned very little content — page may not have rendered")
                return None

            log.info(f"Successfully scraped Devpost ({len(content)} chars)")
            return content

    except PlaywrightTimeout:
        log.error(f"Devpost page timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"Failed to scrape Devpost: {e}")
        return None
