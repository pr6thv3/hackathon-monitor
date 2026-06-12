"""
Hackathon & Workshop Monitor — Main Orchestrator

Wires all modules together into a single pipeline:
  1. Fetch from Devpost, Devfolio, VIT EventHub
  2. Analyze with Gemini AI
  3. Deduplicate against seen_events.json
  4. Send Telegram alert (only if new matches exist)
"""

import logging
import sys

from src.fetcher_devpost import fetch_devpost
from src.fetcher_devfolio import fetch_devfolio
from src.fetcher_college import fetch_college_events
from src.brain import analyze_events
from src.memory import load_memory, save_memory, is_new, mark_seen
from src.notifier import send_telegram

# ── Load .env for local development (optional, ignored in CI) ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — running in CI with env vars set

# ── Logging setup ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("hackathon-monitor")


def main() -> int:
    """
    Run the full monitoring pipeline.
    Returns 0 on success, 1 on critical failure.
    """
    log.info("=" * 60)
    log.info("🚀 Hackathon & Workshop Monitor — Starting daily run")
    log.info("=" * 60)

    # ── Step 1: Fetch from all sources ──
    # Continue even if one or two sources fail
    contents = {}

    log.info("── Step 1/4: Fetching from all sources ──")

    devpost = fetch_devpost()
    if devpost:
        contents["devpost"] = devpost
        log.info(f"✅ Devpost: {len(devpost)} chars")
    else:
        log.warning("⚠️ Devpost fetch failed — continuing with other sources")

    devfolio = fetch_devfolio()
    if devfolio:
        contents["devfolio"] = devfolio
        log.info(f"✅ Devfolio: {len(devfolio)} chars")
    else:
        log.warning("⚠️ Devfolio fetch failed — continuing with other sources")

    college = fetch_college_events()
    if college:
        contents["vit_eventhub"] = college
        log.info(f"✅ VIT EventHub: {len(college)} chars")
    else:
        log.warning("⚠️ VIT EventHub fetch failed — continuing with other sources")

    if not contents:
        log.error("❌ All fetchers failed. Nothing to analyze. Exiting.")
        return 1

    log.info(f"📊 Successfully fetched from {len(contents)}/3 sources")

    # ── Step 2: Analyze with Gemini AI ──
    log.info("── Step 2/4: Analyzing with Gemini AI ──")
    events = analyze_events(contents)
    log.info(f"🧠 Gemini found {len(events)} matching events across all sources")

    if not events:
        log.info("No events matched your interest profile. Pipeline complete.")
        return 0

    # ── Step 3: Deduplicate ──
    log.info("── Step 3/4: Deduplicating against memory ──")
    memory = load_memory()
    new_events = [e for e in events if is_new(memory, e["title"])]
    log.info(
        f"💾 {len(new_events)} new events "
        f"({len(events) - len(new_events)} already seen)"
    )

    # ── Step 4: Notify via Telegram ──
    if new_events:
        log.info("── Step 4/4: Sending Telegram notification ──")
        for e in new_events:
            log.info(f"  📌 [{e['event_type'].upper()}] {e['title']} ({e['source']})")

        success = send_telegram(new_events)

        if success:
            # Only update memory AFTER successful send
            # This way, if WhatsApp fails, we'll retry next run
            for e in new_events:
                memory = mark_seen(
                    memory,
                    e["title"],
                    e.get("link", ""),
                    e["source"],
                )
            save_memory(memory)
            log.info(f"✅ Sent {len(new_events)} events and updated memory")
        else:
            log.error(
                "❌ Telegram send failed — memory NOT updated. "
                "Events will be retried on next run."
            )
            return 1
    else:
        log.info("── Step 4/4: No new events — phone stays silent ──")
        log.info("🔇 All matched events were already seen. No message sent.")

    log.info("=" * 60)
    log.info("✅ Pipeline complete")
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
