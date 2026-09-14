"""
Telegram Notifier Module (v4).

Delivers authentic, human-written, high-signal project and opportunity check-ins:
- Natural personal tone (no corporate/robotic AI jargon or percentage spam)
- Project repository & branch status check-in
- Urgency tiers (⚡ ≤7d, 🔥 ≤30d, 📌 >30d)
- Concise explanation of why each opportunity is worth attention
- Maximum 3 items per notification to eliminate fatigue
- Clear search warnings if direct URLs are unavailable
- Clean HTML formatting with inline application buttons
"""

import json
import logging
import os
import re
from datetime import datetime, date, timezone
from typing import Any
import requests

log = logging.getLogger(__name__)

TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_ITEMS_PER_MESSAGE = 3


def _get_credentials() -> tuple[str, str] | None:
    """Read Telegram credentials from environment variables."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        log.warning("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — skipping Telegram delivery.")
        return None

    return token, chat_id


def _escape_html(text: str) -> str:
    """Escape special characters for Telegram HTML parse mode."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _parse_days_left(deadline_str: str | None) -> int | None:
    """Extract remaining days from date string or text like '23 days left'."""
    if not deadline_str:
        return None

    # Check for regex like 'X days left' or 'X day left'
    match = re.search(r"(\d+)\s*days?\s*left", deadline_str, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Try standard date parsing
    clean_date = deadline_str.split("T")[0].split()[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y"):
        try:
            target = datetime.strptime(clean_date, fmt).date()
            today = date.today()
            return (target - today).days
        except Exception:
            continue

    return None


def _get_urgency_tier(days_left: int | None) -> tuple[str, str]:
    """Return urgency emoji and label based on deadline proximity."""
    if days_left is None:
        return "📌", "OPPORTUNITY"
    if days_left <= 7:
        return "⚡", f"{days_left}d left" if days_left > 0 else "Closing Today"
    if days_left <= 30:
        return "🔥", f"{days_left}d left"
    return "📌", f"{days_left}d left"


def format_notification(
    events: list[dict[str, Any]],
    is_digest: bool = False,
    user_name: str = "Builder",
    project_status: str | None = None,
) -> tuple[str, dict]:
    """
    Format top-ranked events into an authentic, human-style Telegram message.
    Returns: (html_text, reply_markup_dict)
    """
    if not events:
        return "", {}

    events_to_show = events[:MAX_ITEMS_PER_MESSAGE]
    lines = []

    # Authentic, human header
    if is_digest:
        lines.append(f"👋 <b>Hey {user_name}</b> — periodic check-in on project status & upcoming deadlines:\n")
    else:
        lines.append(f"👋 <b>Hey {user_name}</b> — new opportunities matched for your stack:\n")

    # Optional Project Status integration
    if project_status:
        lines.append(f"📦 <b>Project Status:</b> {project_status}\n")
    else:
        try:
            from src.git_status import get_project_status_summary
            p_status = get_project_status_summary()
            if p_status:
                lines.append(f"📦 <b>Project Status:</b> {p_status}\n")
        except Exception:
            pass

    lines.append("🎯 <b>Opportunities worth your time:</b>\n")

    inline_keyboard = []

    for i, e in enumerate(events_to_show, start=1):
        title = _escape_html(e.get("title", "Unknown"))
        etype = _escape_html(e.get("event_type", "hackathon").replace("_", " ").title())
        source = _escape_html(e.get("source", "web").title())
        mode = _escape_html(e.get("mode", "Online").title())
        team = _escape_html(e.get("team_size", "Solo / Team"))
        link = e.get("link")
        prize = _escape_html(e.get("prize_pool", ""))
        why_relevant = _escape_html(e.get("why_relevant", ""))
        rel_explanation = _escape_html(e.get("relevance_explanation", ""))

        # Urgency
        deadline = e.get("registration_deadline") or e.get("dates")
        days_left = _parse_days_left(deadline)
        emoji, urgency_label = _get_urgency_tier(days_left)

        # Header line (e.g. ⚡ Global Autonomous Agent Challenge (Devpost))
        lines.append(f"{emoji} <b>{title}</b> ({source})")

        # Key facts line
        facts = [f"⏰ <b>{urgency_label}</b>", f"📍 {mode}"]
        if team and team != "N/A":
            facts.append(f"👥 {team}")
        lines.append(" · ".join(facts))

        # Prize line if notable
        if prize and prize.lower() not in ("n/a", "none", ""):
            lines.append(f"💰 <b>Prize:</b> {prize}")

        # Authentic, human pitch
        pitch = rel_explanation or why_relevant or "Strong alignment with your builder profile and interests."
        if len(pitch) > 180:
            pitch = pitch[:177] + "..."
        lines.append(f"💡 <i>{pitch}</i>")

        # Link status
        if link:
            inline_keyboard.append([{"text": f"🚀 Apply: {title[:28]}", "url": link}])
        else:
            lines.append(f"⚠️ <i>Direct URL unavailable — search '{title}' on {source}</i>")

        lines.append("")

    lines.append("<i>(Staying quiet until next scheduled check-in unless an urgent deadline pops up.)</i>")

    reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else {}
    return "\n".join(lines).strip(), reply_markup


def send_telegram(
    scored_events: list[dict[str, Any]],
    report_path: str = None,
    is_digest_of_active: bool = False,
    user_name: str = "Builder",
    project_status: str | None = None,
) -> bool:
    """
    Deliver high-signal Telegram alert.
    Capped at top 3 items to avoid fatigue.
    """
    if not scored_events:
        log.info("No high-value events to notify — staying silent to prevent spam.")
        return True

    credentials = _get_credentials()
    if not credentials:
        return False

    token, chat_id = credentials
    text, reply_markup = format_notification(
        scored_events,
        is_digest=is_digest_of_active,
        user_name=user_name,
        project_status=project_status,
    )

    if not text:
        return True

    log.info(f"Sending Telegram notification ({len(scored_events)} events evaluated)...")
    msg_url = TELEGRAM_SEND_MESSAGE_URL.format(token=token)

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        resp = requests.post(msg_url, json=payload, timeout=20)
        if resp.ok:
            log.info("✅ Telegram notification delivered successfully")
            return True
        else:
            log.error(f"Telegram send failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        log.error(f"Telegram delivery exception: {e}")
        return False
