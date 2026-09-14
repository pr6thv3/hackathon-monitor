"""
VIT EventHub Adapter — Playwright with persistent session state caching.

Scrapes https://eventhubcc.vit.ac.in/EventHub/mainDashboard
Handles VIT student authentication with cookie/token session reuse (auth_state_vit.json)
to prevent frequent re-logins and account lockout risks.
Captures structured data via network interception (primary) and DOM extraction (fallback).
"""

import json
import logging
import os
from typing import Any
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from src.adapters.base import CollegePortalAdapter

log = logging.getLogger(__name__)

DEFAULT_EVENTHUB_URL = "https://eventhubcc.vit.ac.in/EventHub/mainDashboard"
AUTH_STATE_PATH = "auth_state_vit.json"
TIMEOUT_MS = 60_000


class VITEventHubAdapter(CollegePortalAdapter):
    adapter_id = "vit_eventhub"

    def __init__(self, auth_state_path: str = AUTH_STATE_PATH):
        self.auth_state_path = auth_state_path

    def _handle_login(self, page, username: str, password: str) -> bool:
        """Attempt to sign in if redirected to an authentication page."""
        current_url = page.url.lower()

        # Check if we're on a login page
        is_login_page = any(
            kw in current_url for kw in ["login", "signin", "sign-in", "auth", "cas"]
        )
        if not is_login_page:
            try:
                login_form = page.locator(
                    "input[type='password'], form[action*='login'], form[action*='auth'], button:has-text('Login'), button:has-text('Sign In')"
                )
                if login_form.count() > 0:
                    is_login_page = True
            except Exception:
                pass

        if not is_login_page:
            log.info("No login required — active session loaded directly")
            return True

        if not username or not password:
            log.warning("VIT EventHub login required but credentials are not set in environment.")
            return False

        log.info("Login page detected — attempting sign-in with credentials...")

        try:
            # Username selectors
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
            for sel in username_selectors:
                try:
                    f = page.locator(sel)
                    if f.count() > 0 and f.first.is_visible():
                        f.first.fill(username)
                        username_filled = True
                        break
                except Exception:
                    continue

            if not username_filled:
                log.error("Could not find username input field on VIT login page")
                return False

            # Password selectors
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "#password",
            ]
            password_filled = False
            for sel in password_selectors:
                try:
                    f = page.locator(sel)
                    if f.count() > 0 and f.first.is_visible():
                        f.first.fill(password)
                        password_filled = True
                        break
                except Exception:
                    continue

            if not password_filled:
                log.error("Could not find password input field on VIT login page")
                return False

            # Submit
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Login')",
                "button:has-text('Sign In')",
                "button:has-text('Submit')",
                "a:has-text('Login')",
            ]
            submitted = False
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel)
                    if btn.count() > 0 and btn.first.is_visible():
                        btn.first.click()
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                page.keyboard.press("Enter")

            page.wait_for_load_state("networkidle", timeout=30_000)

            post_login_url = page.url.lower()
            if any(kw in post_login_url for kw in ["login", "signin", "auth", "error"]):
                log.error("VIT login failed — still on authentication page")
                return False

            log.info("VIT login successful!")
            return True

        except Exception as e:
            log.error(f"VIT login execution error: {e}")
            return False

    def fetch_events(self, config: dict[str, Any] = None) -> str | None:
        """
        Fetch events from VIT EventHub using cached session state or fresh login.
        """
        cfg = config or {}
        url = cfg.get("url") or DEFAULT_EVENTHUB_URL
        auth = cfg.get("auth", {})
        user_env = auth.get("username_env", "VIT_USERNAME")
        pass_env = auth.get("password_env", "VIT_PASSWORD")

        username = os.environ.get(user_env, "").strip()
        password = os.environ.get(pass_env, "").strip()

        log.info(f"VIT EventHub Adapter: Accessing {url}")

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

                # Attempt to restore cached session state
                context = None
                if os.path.exists(self.auth_state_path):
                    try:
                        context = browser.new_context(
                            storage_state=self.auth_state_path,
                            user_agent=(
                                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                            ),
                        )
                        log.info(f"Restored cached browser session state from {self.auth_state_path}")
                    except Exception as e:
                        log.warning(f"Could not restore session state: {e}")

                if context is None:
                    context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                        )
                    )

                page = context.new_page()

                # Intercept JSON API calls
                api_data = []

                def handle_response(response):
                    try:
                        r_url = response.url.lower()
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type or any(
                            kw in r_url for kw in ["api", "event", "dashboard", "fetch", "list"]
                        ):
                            try:
                                body = response.json()
                                api_data.append({"url": response.url, "data": body})
                            except Exception:
                                pass
                    except Exception:
                        pass

                page.on("response", handle_response)

                page.goto(url, wait_until="networkidle", timeout=TIMEOUT_MS)

                # Check if session expired or login required
                if self._handle_login(page, username, password):
                    # Save refreshed browser state
                    try:
                        context.storage_state(path=self.auth_state_path)
                        log.info(f"Saved authenticated session state to {self.auth_state_path}")
                    except Exception as e:
                        log.warning(f"Could not save session state: {e}")
                else:
                    browser.close()
                    log.warning("Could not establish authenticated session with VIT EventHub.")
                    return None

                page.wait_for_timeout(3000)

                # Format results
                if api_data:
                    log.info(f"VIT EventHub: Captured {len(api_data)} API responses")
                    formatted_lines = ["--- SOURCE: VIT EVENTHUB (API data) ---"]

                    for entry in api_data:
                        data = entry["data"]
                        events_list = None
                        if isinstance(data, list):
                            events_list = data
                        elif isinstance(data, dict):
                            for k in ["events", "data", "results", "items", "content"]:
                                if k in data and isinstance(data[k], list):
                                    events_list = data[k]
                                    break

                        if events_list:
                            for ev in events_list:
                                if isinstance(ev, dict):
                                    name = ev.get("name", ev.get("title", ev.get("eventName", "")))
                                    link = ev.get("link", ev.get("url", ev.get("eventUrl", "")))
                                    if not link and "id" in ev:
                                        link = f"https://eventhubcc.vit.ac.in/EventHub/eventDetails?id={ev['id']}"
                                    if name:
                                        formatted_lines.append(f"\nTitle: {name}")
                                        if link:
                                            formatted_lines.append(f"Link: {link}")
                                        for fld in ["date", "startDate", "start_date", "eventDate"]:
                                            if fld in ev:
                                                formatted_lines.append(f"Date: {ev[fld]}")
                                                break
                                        for fld in ["category", "type", "domain", "eventType"]:
                                            if fld in ev:
                                                formatted_lines.append(f"Category: {ev[fld]}")
                                                break
                                        for fld in ["description", "desc", "about"]:
                                            if fld in ev:
                                                formatted_lines.append(f"Description: {str(ev[fld])[:300]}")
                                                break
                                        for fld in ["club", "organizer", "organization", "clubName"]:
                                            if fld in ev:
                                                formatted_lines.append(f"Organizer: {ev[fld]}")
                                                break
                        else:
                            formatted_lines.append(json.dumps(data, indent=2, default=str)[:3000])

                    result = "\n".join(formatted_lines)
                    browser.close()
                    if len(result) > 200:
                        log.info(f"Extracted {len(result)} chars from VIT EventHub API")
                        return result

                # Fallback to DOM card extraction
                log.info("No API data captured — scraping rendered DOM cards")
                cards = page.query_selector_all(".event-card, .card, [data-event-id], article")
                dom_lines = ["--- SOURCE: VIT EVENTHUB ---"]
                for c in cards:
                    title_el = c.query_selector("h2, h3, h4, .title, .event-title")
                    link_el = c.query_selector("a[href]")
                    date_el = c.query_selector(".date, .time, .event-date")
                    desc_el = c.query_selector(".desc, .description, p")

                    t = title_el.inner_text().strip() if title_el else ""
                    lnk = link_el.get_attribute("href") if link_el else ""
                    if lnk and not lnk.startswith("http"):
                        lnk = f"https://eventhubcc.vit.ac.in{lnk}" if lnk.startswith("/") else lnk
                    d = date_el.inner_text().strip() if date_el else ""
                    dsc = desc_el.inner_text().strip() if desc_el else ""

                    if t:
                        dom_lines.append(f"\nTitle: {t}")
                        if lnk:
                            dom_lines.append(f"Link: {lnk}")
                        if d:
                            dom_lines.append(f"Date: {d}")
                        if dsc:
                            dom_lines.append(f"Description: {dsc[:300]}")

                if len(dom_lines) > 1:
                    result = "\n".join(dom_lines)
                else:
                    body_text = page.inner_text("body")
                    result = f"--- SOURCE: VIT EVENTHUB ---\n{body_text[:10000]}"

                browser.close()
                return result

        except PlaywrightTimeout:
            log.error(f"VIT EventHub timed out after {TIMEOUT_MS // 1000}s")
            return None
        except Exception as e:
            log.error(f"Failed to fetch VIT EventHub: {e}")
            return None
