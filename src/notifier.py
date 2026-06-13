"""
Telegram Notifier Module.

Delivers a two-part notification to the user's Telegram chat:
1. A rich, HTML-formatted summary message (with inline keyboard buttons for registration links).
2. The full Markdown analysis report attached as a document.
"""

import json
import logging
import os
import requests

log = logging.getLogger(__name__)

TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_SEND_DOCUMENT_URL = "https://api.telegram.org/bot{token}/sendDocument"


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


def _escape_html(text: str) -> str:
    """Escape special HTML characters for Telegram HTML parse mode."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_html_summary(scored_events: list[dict]) -> tuple[str, dict]:
    """
    Format events into a rich HTML message.
    Also returns inline keyboard buttons for event links.
    """
    lines = [
        "🤖 <b>Hackathon Opportunity Intelligence Alert!</b>\n",
        f"Found <b>{len(scored_events)}</b> opportunities passing our quality threshold:\n"
    ]
    
    inline_keyboard = []

    for i, e in enumerate(scored_events, start=1):
        title = _escape_html(e.get("title", "Unknown"))
        fos = e.get("fos_score", 0.0)
        easy_win = e.get("easy_winning_potential", 0.0)
        verdict = e.get("fos_verdict", "⚠️")
        mode = _escape_html(e.get("mode", "online"))
        source = _escape_html(e.get("source", "unknown").upper())
        why = _escape_html(e.get("why_relevant", ""))

        lines.append(f"{i}️⃣ <b>{title}</b> ({source})")
        lines.append(f"• FOS: <b>{fos:.1f}/10</b> | Win Prob: <b>{easy_win:.1f}/10</b> {verdict}")
        lines.append(f"• Mode: {mode.title()} | Team: {e.get('team_size', 'N/A')}")
        if why:
            # Truncate why relevant pitch if too long
            short_why = why[:150] + "..." if len(why) > 150 else why
            lines.append(f"• <i>Pitch: {short_why}</i>")
        lines.append("")

        link = e.get("link")
        if link:
            # Add inline button for registration
            inline_keyboard.append([{"text": f"🔗 Register: {title[:25]}", "url": link}])

    reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else {}
    return "\n".join(lines).strip(), reply_markup


def send_telegram(scored_events: list[dict], report_path: str) -> bool:
    """
    Send HTML summary message with registration links, then send the full report file.

    Args:
        scored_events: Scored events to summarize.
        report_path: Path to the generated Markdown report.

    Returns:
        True if successful, False otherwise.
    """
    if not scored_events:
        log.info("No events to send — staying silent")
        return True

    credentials = _get_credentials()
    if not credentials:
        return False

    token, chat_id = credentials
    
    # 1. Format and send the summary message
    summary_text, reply_markup = _format_html_summary(scored_events)
    
    # Check 4096 character limit
    if len(summary_text) > 4000:
        summary_text = summary_text[:3950] + "\n\n<i>[Truncated - see full report document]</i>"

    log.info(f"Sending HTML summary to Telegram...")
    msg_url = TELEGRAM_SEND_MESSAGE_URL.format(token=token)
    
    payload = {
        "chat_id": chat_id,
        "text": summary_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        resp = requests.post(msg_url, json=payload, timeout=20)
        if resp.ok:
            log.info("Telegram summary message sent successfully")
        else:
            log.error(f"Failed to send Telegram summary: {resp.status_code} {resp.text}")
    except Exception as e:
        log.error(f"Error sending Telegram summary: {e}")

    # 2. Send the full Markdown report as a document
    if not report_path or not os.path.exists(report_path):
        log.warning(f"No report file found at {report_path} - skipping document attachment")
        return True

    log.info("Sending Markdown report document to Telegram...")
    doc_url = TELEGRAM_SEND_DOCUMENT_URL.format(token=token)
    
    try:
        filename = os.path.basename(report_path)
        with open(report_path, "rb") as f:
            files = {"document": (filename, f, "text/markdown")}
            data = {
                "chat_id": chat_id,
                "caption": f"📊 Full Hackathon Opportunity Intelligence Report ({len(scored_events)} events)",
                "parse_mode": "HTML"
            }
            resp = requests.post(doc_url, data=data, files=files, timeout=30)
            
            if resp.ok:
                log.info("Telegram report document sent successfully")
                return True
            else:
                log.error(f"Failed to send Telegram document: {resp.status_code} {resp.text}")
                return False
                
    except Exception as e:
        log.error(f"Error sending Telegram report document: {e}")
        return False
