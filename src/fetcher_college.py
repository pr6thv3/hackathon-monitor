"""
VIT EventHub Fetcher — Playwright with login automation.

Scrapes https://eventhubcc.vit.ac.in/EventHub/mainDashboard
using headless Chromium. Handles the VIT student login flow
using credentials from environment variables.
"""

import json
import logging
import os

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

EVENTHUB_URL = "https://eventhubcc.vit.ac.in/EventHub/mainDashboard"
TIMEOUT_MS = 60_000  # 60 seconds


def _handle_login(page) -> bool:
    """
    Detect if we've been redirected to a login page and attempt to log in.

    Returns True if login was successful or not needed, False on failure.
    """
    username = os.environ.get("VIT_USERNAME", "").strip()
    password = os.environ.get("VIT_PASSWORD", "").strip()

    current_url = page.url.lower()

    # Check if we're on a login page
    is_login_page = any(
        keyword in current_url
        for keyword in ["login", "signin", "sign-in", "auth", "cas"]
    )

    # Also check for login form elements in the DOM
    if not is_login_page:
        try:
            login_form = page.locator(
                "input[type='password'], "
                "form[action*='login'], "
                "form[action*='auth'], "
                "button:has-text('Login'), "
                "button:has-text('Sign In')"
            )
            if login_form.count() > 0:
                is_login_page = True
        except Exception:
            pass

    if not is_login_page:
        log.info("No login required — dashboard loaded directly")
        return True

    # Login is required
    if not username or not password:
        log.warning(
            "VIT EventHub requires login but VIT_USERNAME/VIT_PASSWORD "
            "environment variables are not set. Skipping college events."
        )
        return False

    log.info("Login page detected — attempting to sign in...")

    try:
        # Try common username/email field selectors
        username_selectors = [
            "input[name='username']",
            "input[name='email']",
            "input[name='userId']",
            "input[name='user']",
            "input[name='loginId']",
            "input[type='email']",
            "input[type='text']:first-of-type",
            "#username",
            "#email",
            "#loginId",
        ]

        username_filled = False
        for selector in username_selectors:
            try:
                field = page.locator(selector)
                if field.count() > 0 and field.first.is_visible():
                    field.first.fill(username)
                    username_filled = True
                    log.debug(f"Username filled using selector: {selector}")
                    break
            except Exception:
                continue

        if not username_filled:
            log.error("Could not find username input field on login page")
            return False

        # Fill password
        password_selectors = [
            "input[name='password']",
            "input[type='password']",
            "#password",
        ]

        password_filled = False
        for selector in password_selectors:
            try:
                field = page.locator(selector)
                if field.count() > 0 and field.first.is_visible():
                    field.first.fill(password)
                    password_filled = True
                    log.debug(f"Password filled using selector: {selector}")
                    break
            except Exception:
                continue

        if not password_filled:
            log.error("Could not find password input field on login page")
            return False

        # Submit the form
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Login')",
            "button:has-text('Sign In')",
            "button:has-text('Submit')",
            "a:has-text('Login')",
        ]

        submitted = False
        for selector in submit_selectors:
            try:
                btn = page.locator(selector)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    submitted = True
                    log.debug(f"Form submitted using selector: {selector}")
                    break
            except Exception:
                continue

        if not submitted:
            # Try pressing Enter as fallback
            page.keyboard.press("Enter")
            log.debug("Form submitted via Enter key")

        # Wait for navigation after login
        page.wait_for_load_state("networkidle", timeout=30_000)

        # Check if login was successful (not still on login page)
        post_login_url = page.url.lower()
        if any(kw in post_login_url for kw in ["login", "signin", "auth", "error"]):
            log.error("Login appears to have failed — still on login/error page")
            return False

        log.info("Login successful — dashboard loaded")
        return True

    except PlaywrightTimeout:
        log.error("Login timed out")
        return False
    except Exception as e:
        log.error(f"Login failed: {e}")
        return False


def fetch_college_events() -> str | None:
    """
    Scrape VIT EventHub dashboard for events.

    Handles login if required, then extracts event data via
    network interception (primary) or DOM text extraction (fallback).

    Returns:
        Formatted text content for Gemini analysis, or None on failure.
    """
    log.info(f"Fetching VIT EventHub from {EVENTHUB_URL}")

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

            # Set up network interception to capture API responses
            api_data = []

            def handle_response(response):
                """Capture JSON responses that might contain event data."""
                try:
                    url = response.url.lower()
                    content_type = response.headers.get("content-type", "")

                    if "json" in content_type or any(
                        kw in url for kw in ["api", "event", "dashboard", "fetch", "list"]
                    ):
                        try:
                            body = response.json()
                            api_data.append({
                                "url": response.url,
                                "data": body,
                            })
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on("response", handle_response)

            # Navigate to the dashboard
            page.goto(EVENTHUB_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

            # Handle login if redirected
            if not _handle_login(page):
                browser.close()
                return None

            # Wait for content to load after login
            page.wait_for_timeout(3000)

            # Try to extract from intercepted API data first
            if api_data:
                log.info(f"Captured {len(api_data)} API responses")
                formatted_lines = ["--- SOURCE: VIT EVENTHUB (API data) ---"]

                for entry in api_data:
                    data = entry["data"]

                    # Handle different data structures
                    events_list = None
                    if isinstance(data, list):
                        events_list = data
                    elif isinstance(data, dict):
                        # Look for common keys that might contain event arrays
                        for key in ["events", "data", "results", "items", "content"]:
                            if key in data and isinstance(data[key], list):
                                events_list = data[key]
                                break

                    if events_list:
                        for event in events_list:
                            if isinstance(event, dict):
                                name = event.get("name", event.get("title", event.get("eventName", "")))
                                if name:
                                    formatted_lines.append(f"\nTitle: {name}")
                                    for field in ["date", "startDate", "start_date", "eventDate"]:
                                        if field in event:
                                            formatted_lines.append(f"Date: {event[field]}")
                                            break
                                    for field in ["category", "type", "domain", "eventType"]:
                                        if field in event:
                                            formatted_lines.append(f"Category: {event[field]}")
                                            break
                                    for field in ["description", "desc", "about"]:
                                        if field in event:
                                            formatted_lines.append(f"Description: {str(event[field])[:300]}")
                                            break
                                    for field in ["club", "organizer", "organization", "clubName"]:
                                        if field in event:
                                            formatted_lines.append(f"Organizer: {event[field]}")
                                            break
                    else:
                        # Dump raw JSON for Gemini to parse
                        formatted_lines.append(json.dumps(data, indent=2, default=str)[:3000])

                result = "\n".join(formatted_lines)
                if len(result) > 200:  # Has meaningful content
                    browser.close()
                    log.info(f"VIT EventHub API data extracted ({len(result)} chars)")
                    return result

            # Fallback: extract text from rendered DOM
            log.info("No API data captured — falling back to DOM text extraction")
            content = page.inner_text("body")
            browser.close()

            if not content or len(content.strip()) < 100:
                log.warning("VIT EventHub returned very little content")
                return None

            log.info(f"VIT EventHub DOM text extracted ({len(content)} chars)")
            return f"--- SOURCE: VIT EVENTHUB ---\n{content}"

    except PlaywrightTimeout:
        log.error(f"VIT EventHub timed out after {TIMEOUT_MS // 1000}s")
        return None
    except Exception as e:
        log.error(f"Failed to scrape VIT EventHub: {e}")
        return None
