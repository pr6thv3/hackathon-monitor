"""
Hackathon & Workshop Monitor — Main Orchestrator

Wires all modules together into a two-stage AI pipeline:
  1. Fetch from 7 sources (Devpost, Devfolio, Unstop, HackerEarth, DoraHacks, MLH, VIT EventHub)
  2. Stage 1: Extract tech events via Gemini 2.5 Flash
  3. Deduplicate events against seen_events.json memory
  4. Perform GitHub Intelligence on new events
  5. Stage 2: Score events using Founder Opportunity Score (FOS) & Easy-Win Potential
  6. Filter by Quality Gate (FOS >= 7.0 OR Easy-Win >= 7.0)
  7. Generate detailed Markdown intelligence report
  8. Deliver Telegram HTML summary with inline registration buttons + PDF-style Markdown attachment
"""

import logging
import sys

from src.fetcher_devpost import fetch_devpost
from src.fetcher_devfolio import fetch_devfolio
from src.fetcher_unstop import fetch_unstop
from src.fetcher_hackerearth import fetch_hackerearth
from src.fetcher_dorahacks import fetch_dorahacks
from src.fetcher_mlh import fetch_mlh
from src.fetcher_college import fetch_college_events

from src.brain import extract_events, score_events
from src.github_intel import get_github_intel
from src.report import generate_report
from src.memory import load_memory, save_memory, is_new, mark_seen
from src.notifier import send_telegram

# Load .env for local development (optional, ignored in CI)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("hackathon-monitor")


def main() -> int:
    """
    Run the full two-stage monitoring and evaluation pipeline.
    Returns 0 on success, 1 on critical failure.
    """
    log.info("=" * 60)
    log.info("🚀 Hackathon Opportunity Intelligence Agent — Starting Run")
    log.info("=" * 60)

    # ── Step 1: Fetch from all 7 sources ──
    contents = {}
    log.info("── Step 1/7: Fetching from all sources ──")

    sources = [
        ("devpost", fetch_devpost),
        ("devfolio", fetch_devfolio),
        ("unstop", fetch_unstop),
        ("hackerearth", fetch_hackerearth),
        ("dorahacks", fetch_dorahacks),
        ("mlh", fetch_mlh),
        ("vit_eventhub", fetch_college_events)
    ]

    for source_name, fetcher in sources:
        try:
            res = fetcher()
            if res:
                # Add source label header if not present
                header = f"--- SOURCE: {source_name.upper()} ---"
                if header not in res:
                    contents[source_name] = f"{header}\n{res}"
                else:
                    contents[source_name] = res
                log.info(f"✅ {source_name.upper()} fetcher: {len(res)} chars")
            else:
                log.warning(f"⚠️ {source_name.upper()} fetcher returned no data")
        except Exception as e:
            log.error(f"❌ {source_name.upper()} fetcher crashed: {e}")

    if not contents:
        log.error("❌ All fetchers failed. Nothing to process. Exiting.")
        return 1

    log.info(f"📊 Successfully fetched from {len(contents)}/{len(sources)} sources")

    # ── Step 2: Stage 1 Event Extraction ──
    log.info("── Step 2/7: Running Stage 1 Gemini Event Extraction ──")
    extracted_events = extract_events(contents)
    log.info(f"🧠 Gemini extracted {len(extracted_events)} raw events across all sources")

    if not extracted_events:
        log.info("No tech events found in scraped content. Pipeline complete.")
        return 0

    # ── Step 3: Deduplication ──
    log.info("── Step 3/7: Deduplicating against memory ──")
    memory = load_memory()
    
    # Track which events are truly new
    new_events = [e for e in extracted_events if is_new(memory, e["title"])]
    log.info(
        f"💾 {len(new_events)} new events found "
        f"({len(extracted_events) - len(new_events)} already seen)"
    )

    if not new_events:
        log.info("No new events to evaluate. Pipeline complete.")
        return 0

    # ── Step 4: GitHub Intelligence ──
    log.info("── Step 4/7: Performing GitHub Intelligence Scans ──")
    github_data = {}
    for i, event in enumerate(new_events, start=1):
        title = event["title"]
        sponsors = event.get("sponsors", [])
        log.info(f" [{i}/{len(new_events)}] Scanning GitHub for '{title}'...")
        github_data[title] = get_github_intel(title, sponsors)

    # ── Step 5: Stage 2 Gemini Scoring (FOS & Easy-Win) ──
    log.info("── Step 5/7: Running Stage 2 Gemini Scoring & Evaluation ──")
    scored_events = score_events(new_events, github_data)

    # ── Step 6: Quality Gate Filter ──
    log.info("── Step 6/7: Applying Quality Gate Filters ──")
    
    # Filter: FOS >= 7.0 OR Easy-Win >= 7.0
    top_events = [
        e for e in scored_events 
        if e.get("fos_score", 0.0) >= 7.0 or e.get("easy_winning_potential", 0.0) >= 7.0
    ]
    
    # Sort primarily by FOS score, secondarily by Easy-Win potential
    top_events.sort(key=lambda e: (e.get("fos_score", 0.0), e.get("easy_winning_potential", 0.0)), reverse=True)
    top_events = top_events[:10]  # Cap at top 10

    log.info(f"🏆 {len(top_events)} events passed the Quality Gate (FOS >= 7.0 or Easy-Win >= 7.0)")

    # ── Step 7: Report Generation and Delivery ──
    log.info("── Step 7/7: Delivering reports and updating memory ──")
    if top_events:
        # Generate Markdown report
        report_path = generate_report(top_events, github_data)
        
        # Send notifications
        success = send_telegram(top_events, report_path)
        
        if success:
            # Mark all new events as seen (even those that didn't pass the quality gate, so we don't score them again)
            for e in new_events:
                memory = mark_seen(memory, e["title"], e.get("link", ""), e["source"])
            save_memory(memory)
            log.info("✅ Sent Telegram notification and updated seen events memory")
        else:
            log.error("❌ Telegram delivery failed — seen events memory NOT updated")
            return 1
    else:
        log.info("No high-potential events to notify today. Updating seen events memory for all processed events...")
        for e in new_events:
            memory = mark_seen(memory, e["title"], e.get("link", ""), e["source"])
        save_memory(memory)
        log.info("💾 Seen events memory updated successfully.")

    log.info("=" * 60)
    log.info("✅ Pipeline Complete")
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
