"""
Unstop Fetcher — API-first with Playwright fallback.

Primary: Hits Unstop's public search API for structured JSON data.
Fallback: Uses Playwright headless Chromium if the API is blocked or structure changes.
Both approaches are 100% free forever.
"""

import json
import logging
import requests as http_requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

UNSTOP_API_URL = "https://unstop.com/api/public/opportunity/search-new"
UNSTOP_PAGE_URL = "https://unstop.com/hackathons"
TIMEOUT_MS = 60_000  # 60 seconds


def _fetch_via_api() -> str | None:
    """
    Try Unstop's search API directly.
    Returns a formatted text summary of hackathons, or None on failure.
    """
    log.info("Attempting Unstop API call...")

    payload = {
        "opportunity": ["hackathons"],
        "oppstatus": ["open", "recent"],
        "page": 1,
        "per_page": 20,
        "sort": "recency"
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
            UNSTOP_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            log.warning(f"Unstop API returned HTTP {response.status_code}")
            return None

        data = response.json()
        
        # Unstop search api response contains data inside data.data or data.data.data
        opps_data = data.get("data", {})
        if isinstance(opps_data, dict):
            opps = opps_data.get("data", [])
        elif isinstance(opps_data, list):
            opps = opps_data
        else:
            opps = []

        if not opps:
            log.warning("Unstop API returned empty or unexpected structure")
            return f"--- SOURCE: UNSTOP (raw API response) ---\n{json.dumps(data, indent=2)[:5000]}"

        lines = ["--- SOURCE: UNSTOP ---"]
        for o in opps:
            if isinstance(o, dict):
                title = o.get("title", "Unknown")
                reg_end = o.get("reg_end_date", o.get("end_date", ""))
                slug = o.get("public_url", "")
                link = f"https://unstop.com/{slug}" if slug else ""
                
                # Check for nested keys
                company_info = o.get("company", {})
                company_name = company_info.get("name", "") if isinstance(company_info, dict) else ""
                if not company_name:
                    company_name = o.get("organisation", {}).get("name", "") if isinstance(o.get("organisation"), dict) else ""
                
                banner_text = o.get("banner_text", "")
                prizes = o.get("prizes", [])
                prize_text = ""
                if prizes and isinstance(prizes, list):
                    prize_text = ", ".join([str(p.get("cash_prize", p)) for p in prizes if isinstance(p, dict)])
                if not prize_text:
                    prize_text = o.get("prize_money_worth", "")
                
                eligible_text = o.get("eligible", "")
                
                lines.append(f"\nTitle: {title}")
                if company_name:
                    lines.append(f"Organiser: {company_name}")
                if reg_end:
                    lines.append(f"Registration Deadline: {reg_end}")
                if link:
                    lines.append(f"Link: {link}")
                if banner_text:
                    lines.append(f"Info: {banner_text}")
                if prize_text:
                    lines.append(f"Prize: {prize_text}")
                if eligible_text:
                    lines.append(f"Eligibility: {eligible_text}")

        result = "\n".join(lines)
        log.info(f"Unstop API returned {len(opps)} hackathons ({len(result)} chars)")
        return result

    except http_requests.RequestException as e:
        log.warning(f"Unstop API request failed: {e}")
        return None
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.warning(f"Unstop API response parsing error: {e}")
        return None


def _fetch_via_playwright() -> str | None:
    """
    Fallback: Use Playwright to render the Unstop page and extract text.
    """
    log.info(f"Falling back to Playwright for Unstop: {UNSTOP_PAGE_URL}")

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

            page.goto(UNSTOP_PAGE_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

            # Wait for content to render
            page.wait_for_timeout(3000)

            # Scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(2000)

            content = page.inner_text("body")
            browser.close()

            if not content or len(content.strip()) < 100:
                log.warning("Unstop Playwright returned very little content")
                return None

            log.info(f"Unstop Playwright scraped {len(content)} chars")
            return f"--- SOURCE: UNSTOP ---\n{content}"

    except PlaywrightTimeout:
        log.error(f"Unstop Playwright timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"Unstop Playwright failed: {e}")
        return None


def fetch_unstop() -> str | None:
    """
    Fetch hackathon listings from Unstop.
    Strategy: Try API first, fall back to Playwright.
    """
    result = _fetch_via_api()
    if result:
        return result
    return _fetch_via_playwright()
