"""
Telegram Notifier — Bot API delivery.

Formats event alerts and sends them to a Telegram chat via Bot API.
Only fires when there are actual new matches — silent on quiet days.
"""

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _get_credentials() -> tuple[str, str] | None:
    """Read Telegram credentials from environment variables."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        log.error(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables. "
            "Cannot send Telegram notifications."
        )
        return None

    return token, chat_id


def _format_event(event: dict, number: int) -> str:
    """Format a single event into a readable Telegram message block."""
    parts = [f"{number}️⃣ *{event.get('title', 'Unknown')}*"]

    source = event.get("source", "")
    if source:
        parts.append(f"📍 {source.replace('_', ' ').title()}")

    date = event.get("date")
    if date:
        parts.append(f"📅 {date}")

    link = event.get("link")
    if link:
        parts.append(f"🔗 {link}")

    why = event.get("why_relevant", "")
    if why:
        parts.append(f"💡 {why}")

    return "\n".join(parts) + "\n"


def _format_message(events: list[dict]) -> str:
    """
    Format a list of events into a readable Telegram message.
    Groups by event type (hackathons first, then workshops).
    Uses Telegram Markdown: *bold*, _italic_
    """
    hackathons = [e for e in events if e.get("event_type") == "hackathon"]
    workshops = [e for e in events if e.get("event_type") == "workshop"]

    lines = [f"🎯 *Event Alert!* ({len(events)} new found)\n"]
    counter = 1

    if hackathons:
        lines.append("🏆 *HACKATHONS*")
        for e in hackathons:
            lines.append(_format_event(e, counter))
            counter += 1

    if workshops:
        lines.append("🛠️ *WORKSHOPS*")
        for e in workshops:
            lines.append(_format_event(e, counter))
            counter += 1

    return "\n".join(lines).strip()


def _split_message(text: str, limit: int = 4000) -> list[str]:
    """Split a long message into chunks that fit within Telegram's 4096-char limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""

    for block in text.split("\n\n"):
        if len(current) + len(block) + 2 > limit:
            if current.strip():
                chunks.append(current.strip())
            current = block + "\n\n"
        else:
            current += block + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


def send_telegram(events: list[dict]) -> bool:
    """
    Format and send event alerts to Telegram via Bot API.

    Only call this when events is non-empty.
    Returns True if all messages were sent successfully.
    """
    if not events:
        log.info("No events to send — staying silent")
        return True

    credentials = _get_credentials()
    if not credentials:
        return False

    token, chat_id = credentials

    # Format the full message
    message = _format_message(events)
    log.info(f"Formatted message ({len(message)} chars) for {len(events)} events")

    # Split if necessary (Telegram limit: 4096 chars)
    chunks = _split_message(message)
    log.info(f"Sending {len(chunks)} message chunk(s)")

    url = TELEGRAM_API.format(token=token)

    all_success = True
    for i, chunk in enumerate(chunks):
        if i > 0:
            # Wait between messages to avoid rate limiting
            time.sleep(2)

        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                },
                timeout=15,
            )

            if resp.ok:
                log.info(f"Telegram message chunk {i + 1}/{len(chunks)} sent successfully")
            else:
                log.error(f"Telegram send failed: {resp.status_code} {resp.text}")
                all_success = False

        except requests.RequestException as e:
            log.error(f"Failed to send Telegram message: {e}")
            all_success = False

    return all_success
