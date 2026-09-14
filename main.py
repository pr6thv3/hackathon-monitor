"""
Hackathon & Opportunity Intelligence Agent — Main Orchestrator (v4)

Wires all modules together into a multi-stage AI opportunity pipeline:
  1. Load user configuration (config.yaml) and resolve PreferenceProfile
  2. Initialize SQLite database and clean stale events (90-day TTL)
  3. Concurrent multi-source ingestion (Devpost, Devfolio, Unstop, HackerEarth, DoraHacks, MLH, College Portals)
  4. Stage 1: Gemini event extraction with prompt injection defense & 11-category taxonomy
  5. Deduplication against SQLite/seen_events.json memory
  6. GitHub Community Intelligence enrichment
  7. Stage 2: Dual Scoring (Student SOS for campus portals, Founder FOS for global platforms) with batching (≤5/call)
  8. Stage 3: Personalized Relevance Scoring matching user interests
  9. Stage 4: Composite Ranking (relevance × urgency × link_penalty) and adaptive quality gates
  10. Stage 5: Telegram Notification delivery (max 3 items, mobile-optimized) + Markdown report
  11. Persistence: Store in SQLite and sync active items to seen_events.json for CI/CD auto-commits
"""

import argparse
import concurrent.futures
import logging
import os
import sys
import uuid

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.config import load_config
from src.db import init_db, migrate_seen_events_to_sqlite, upsert_event, save_event_score, sync_sqlite_to_seen_events_json, get_connection
from src.memory import load_memory, save_memory, is_new, mark_seen, clean_expired_events
from src.health import SourceHealthTracker, RunMetrics
from src.brain import extract_events, score_events, score_relevance
from src.github_intel import get_github_intel
from src.report import generate_report
from src.notifier import send_telegram
from src.feedback import FeedbackProcessor

# Fetchers
from src.fetcher_devpost import fetch_devpost
from src.fetcher_devfolio import fetch_devfolio
from src.fetcher_unstop import fetch_unstop
from src.fetcher_hackerearth import fetch_hackerearth
from src.fetcher_dorahacks import fetch_dorahacks
from src.fetcher_mlh import fetch_mlh
from src.fetcher_college import fetch_college_events

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("hackathon-monitor")


def calculate_composite_rank(event: dict) -> float:
    """
    Calculate composite rank combining relevance, opportunity framework score (FOS/SOS),
    easy-winning potential (win probability), urgency, and link availability.
    Formula: (50% Relevance + 30% OppScore + 20% EasyWin) * Urgency * LinkPenalty
    """
    rel = float(event.get("relevance_score", 5.0))
    is_college = event.get("source_type") == "college_portal"
    opp_score = float(event.get("sos_score", 5.0) if is_college else event.get("fos_score", 5.0))
    easy_win = float(event.get("easy_winning_potential", 5.0))

    blended_score = (rel * 0.5) + (opp_score * 0.3) + (easy_win * 0.2)

    # Urgency multiplier
    deadline = str(event.get("registration_deadline", "")).lower()
    if any(k in deadline for k in ["1 day", "2 days", "3 days", "4 days", "5 days", "6 days", "7 days"]):
        urgency = 2.0
    elif "day" in deadline:
        urgency = 1.3
    else:
        urgency = 1.0

    # Link penalty (penalize items where user cannot easily register)
    link_penalty = 1.0 if event.get("link") else 0.7

    return round(blended_score * urgency * link_penalty, 2)


def main() -> int:
    """Run the complete v4 monitoring and intelligence pipeline."""
    parser = argparse.ArgumentParser(description="Hackathon Opportunity Intelligence Agent (v4)")
    parser.add_argument("--force", action="store_true", help="Ignore seen memory and force re-evaluation.")
    parser.add_argument("--dry-run", action="store_true", help="Run extraction and scoring without sending alerts.")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file.")
    parser.add_argument("--feedback", nargs=2, metavar=("EVENT_ID", "ACTION"), help="Record user feedback (e.g. --feedback 12 applied)")
    parser.add_argument("--stats", action="store_true", help="Show database & source metrics summary")
    parser.add_argument("--list-events", action="store_true", help="List recent stored opportunities")
    args = parser.parse_args()

    # ── Handle Utility Flags ──
    if args.feedback:
        event_id, action = args.feedback
        try:
            fb = FeedbackProcessor()
            fb.record_feedback(user_id=1, event_id=int(event_id), action=action)
            print(f"✅ Successfully recorded feedback '{action}' for event #{event_id}")
        except Exception as e:
            print(f"❌ Failed to record feedback: {e}")
        return 0

    if args.stats:
        init_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as total FROM events;")
            total_events = cursor.fetchone()["total"]
            cursor.execute("SELECT count(*) as total FROM event_scores WHERE verdict = '🔥';")
            fire_verdicts = cursor.fetchone()["total"]
            cursor.execute("SELECT count(*) as total FROM feedback;")
            total_fb = cursor.fetchone()["total"]
        print(f"📊 Hackathon Monitor System Metrics:")
        print(f" - Total Stored Events: {total_events}")
        print(f" - Top Opportunities (🔥): {fire_verdicts}")
        print(f" - User Feedback Count: {total_fb}")
        return 0

    if args.list_events:
        init_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.id, e.title, e.source, e.event_type, MAX(s.opportunity_score) as opportunity_score, s.verdict
                FROM events e
                LEFT JOIN event_scores s ON e.id = s.event_id
                GROUP BY e.id
                ORDER BY e.id DESC
                LIMIT 15;
            """)
            rows = cursor.fetchall()
            print("\n📋 Recent Stored Opportunities:")
            for r in rows:
                print(f" #{r['id']} | [{r['source'].upper()}] {r['title'][:40]} | Type: {r['event_type']} | Score: {r['opportunity_score'] or 'N/A'} {r['verdict'] or ''}")
        return 0

    run_id = uuid.uuid4().hex[:8]
    metrics = RunMetrics(run_id=run_id)
    health = SourceHealthTracker()

    log.info("=" * 65)
    log.info(f"🚀 Opportunity Intelligence Agent v4 Starting [Run: {run_id}]")
    if args.force:
        log.info("⚠️ Force mode enabled: memory deduplication bypassed.")
    if args.dry_run:
        log.info("🧪 Dry-run mode enabled: alerts will not be sent.")
    log.info("=" * 65)

    # ── Step 1: Configuration & Database Setup ──
    log.info("── Step 1/7: Initializing Configuration & Database ──")
    app_config = load_config(args.config)
    log.info(f"User: {app_config.user_name} | Interest Topics: {app_config.preference_profile.topics[:4]}")

    init_db()
    if os.path.exists("seen_events.json"):
        migrate_seen_events_to_sqlite("seen_events.json")

    memory = load_memory("seen_events.json", auto_clean=True, ttl_days=90)

    # Load dynamic behavioral feedback weights
    fb_processor = FeedbackProcessor()
    feedback_weights = fb_processor.get_behavioral_weights(user_id=1)
    if feedback_weights.get("type_multipliers"):
        log.info(f"Loaded behavioral feedback multipliers: {feedback_weights['type_multipliers']}")

    # ── Step 2: Concurrent Multi-Source Ingestion ──
    log.info("── Step 2/7: Ingesting from all monitored platforms (Concurrent) ──")
    contents = {}
    sources = [
        ("devpost", lambda: fetch_devpost()),
        ("devfolio", lambda: fetch_devfolio()),
        ("unstop", lambda: fetch_unstop()),
        ("hackerearth", lambda: fetch_hackerearth()),
        ("dorahacks", lambda: fetch_dorahacks()),
        ("mlh", lambda: fetch_mlh()),
    ]

    # Add configured college portals
    if app_config.portals:
        for p in app_config.portals:
            sources.append((p.id, lambda p_cfg=p.model_dump(): fetch_college_events(p_cfg)))
    else:
        sources.append(("vit_eventhub", lambda: fetch_college_events()))

    metrics.sources_attempted = len(sources)

    def _fetch_source(item):
        name, fetcher_fn = item
        try:
            res = fetcher_fn()
            return name, res, None
        except Exception as err:
            return name, None, err

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(sources))) as executor:
        future_to_source = {executor.submit(_fetch_source, s): s[0] for s in sources}
        for future in concurrent.futures.as_completed(future_to_source):
            source_name, res, err = future.result()
            if err:
                log.error(f"❌ {source_name.upper()} crashed: {err}")
                health.record_failure(source_name, err)
                metrics.sources_failed.append(source_name)
            elif res and len(res.strip()) > 50:
                header = f"--- SOURCE: {source_name.upper()} ---"
                contents[source_name] = res if header in res else f"{header}\n{res}"
                health.record_success(source_name)
                metrics.sources_succeeded += 1
                log.info(f"✅ {source_name.upper()}: {len(res)} chars retrieved")
            else:
                log.warning(f"⚠️ {source_name.upper()}: No data retrieved")
                health.record_failure(source_name, "Empty response")
                metrics.sources_failed.append(source_name)

    if not contents:
        log.error("❌ All sources failed. Exiting.")
        metrics.finish()
        return 1

    # ── Step 3: Stage 1 Event Extraction ──
    log.info("── Step 3/7: Stage 1 Extraction & Injection Sanitization ──")
    extracted_events = extract_events(contents)
    metrics.events_extracted = len(extracted_events)
    log.info(f"Extracted {len(extracted_events)} raw events across all sources")

    if not extracted_events:
        log.info("No technical events identified in scraped data. Run complete.")
        metrics.finish()
        return 0

    # ── Step 4: Deduplication against Memory ──
    log.info("── Step 4/7: Memory Deduplication ──")
    if args.force:
        new_events = extracted_events
    else:
        new_events = [e for e in extracted_events if is_new(memory, e["title"])]

    metrics.events_new = len(new_events)
    log.info(f"💾 {len(new_events)} new event(s) to evaluate ({len(extracted_events) - len(new_events)} already seen)")

    if not new_events:
        log.info("No new events found. Checking for urgent upcoming deadlines in tracked memory...")
        from src.notifier import _parse_days_left, format_notification
        active_candidates = []
        for e in extracted_events:
            from src.memory import _hash_title
            h = _hash_title(e["title"])
            if h in memory:
                rec = memory[h]
                if rec.get("fos_verdict") != "❌" and (rec.get("fos_score", 0) >= 5.0 or rec.get("sos_score", 0) >= 4.0):
                    d_left = _parse_days_left(rec.get("registration_deadline") or rec.get("dates"))
                    if d_left is not None and 0 <= d_left <= 7:
                        rec["days_left"] = d_left
                        active_candidates.append(rec)

        if active_candidates:
            active_candidates.sort(key=lambda x: (x.get("days_left", 999), -x.get("relevance_score", 0)))
            top_active = active_candidates[:app_config.notifications.max_per_run]
            log.info(f"⏰ Found {len(top_active)} urgent opportunity deadline(s) closing within 7 days.")

            if not args.dry_run:
                send_telegram(top_active, is_digest_of_active=True, user_name=app_config.user_name)
                metrics.notifications_sent = len(top_active)
            else:
                preview, _ = format_notification(top_active, is_digest=True, user_name=app_config.user_name)
                print("\n--- [PREVIEW OF TELEGRAM NOTIFICATION] ---")
                print(preview)
                print("------------------------------------------\n")
        else:
            log.info("✨ No new opportunities and no urgent deadlines (≤7 days). Staying silent to prevent notification spam.")

        metrics.finish()
        return 0

    # ── Step 5: GitHub Intelligence & Stage 2 Dual Scoring ──
    log.info("── Step 5/7: GitHub Intelligence & Stage 2 Dual Scoring (FOS / SOS) ──")
    github_intel = {}
    for i, ev in enumerate(new_events, start=1):
        title = ev["title"]
        sponsors = ev.get("sponsors", [])
        stype = ev.get("source_type", "global_platform")
        if stype != "college_portal":
            log.info(f" [{i}/{len(new_events)}] Scanning GitHub for '{title}'...")
            github_intel[title] = get_github_intel(title, sponsors)
        else:
            github_intel[title] = {}

    scored_events = score_events(new_events, github_intel)
    metrics.events_scored = len(scored_events)

    # ── Step 6: Stage 3 Personalized Relevance Scoring ──
    log.info("── Step 6/7: Stage 3 Personalized Relevance Evaluation ──")
    relevance_scored = score_relevance(
        scored_events,
        app_config.preference_profile.model_dump(),
        feedback_weights=feedback_weights,
    )

    # Calculate composite rank and apply adaptive quality gates
    passing_events = []
    for ev in relevance_scored:
        is_college = ev.get("source_type") == "college_portal"
        opp_score = ev.get("sos_score", 0.0) if is_college else ev.get("fos_score", 0.0)
        verdict = ev.get("sos_verdict") if is_college else ev.get("fos_verdict")
        recommendation = ev.get("recommendation", "CONSIDER")

        # Quality Gates:
        # College events: SOS >= 3.0 and verdict != '❌'
        # Global events: FOS >= 5.0 and verdict != '❌'
        # Neither should be SKIP
        passes_gate = False
        if is_college:
            passes_gate = (opp_score >= 3.0) and (verdict != "❌") and (recommendation != "SKIP")
        else:
            passes_gate = (opp_score >= 5.0) and (verdict != "❌") and (recommendation != "SKIP")

        if passes_gate:
            ev["composite_rank"] = calculate_composite_rank(ev)
            passing_events.append(ev)

    # Sort descending by composite rank
    passing_events.sort(key=lambda x: x.get("composite_rank", 0.0), reverse=True)
    top_candidates = passing_events[:app_config.notifications.max_per_run]

    log.info(f"🏆 {len(passing_events)} event(s) passed quality gates ({len(top_candidates)} selected for alert)")

    # ── Step 7: Notification Delivery & Persistence ──
    log.info("── Step 7/7: Delivery & Database Persistence ──")
    report_path = None
    if passing_events:
        report_path = generate_report(passing_events, github_intel)

    delivered = False
    if top_candidates:
        if not args.dry_run:
            delivered = send_telegram(
                top_candidates,
                report_path=report_path,
                user_name=app_config.user_name,
            )
            if delivered:
                metrics.notifications_sent = len(top_candidates)
        else:
            from src.notifier import format_notification
            preview, _ = format_notification(top_candidates, is_digest=False, user_name=app_config.user_name)
            print("\n--- [PREVIEW OF TELEGRAM NOTIFICATION] ---")
            print(preview)
            print("------------------------------------------\n")
            log.info("🧪 Dry-run: previewed Telegram alert without dispatching")
            delivered = True
    else:
        log.info("No new events passed quality gates. Checking for urgent existing deadlines...")
        from src.notifier import _parse_days_left, format_notification
        urgent_tracked = []
        for e in extracted_events:
            from src.memory import _hash_title
            h = _hash_title(e["title"])
            if h in memory:
                rec = memory[h]
                if rec.get("fos_verdict") != "❌" and (rec.get("fos_score", 0) >= 5.0 or rec.get("sos_score", 0) >= 4.0):
                    d_left = _parse_days_left(rec.get("registration_deadline") or rec.get("dates"))
                    if d_left is not None and 0 <= d_left <= 7:
                        rec["days_left"] = d_left
                        urgent_tracked.append(rec)
        if urgent_tracked:
            urgent_tracked.sort(key=lambda x: (x.get("days_left", 999), -x.get("relevance_score", 0)))
            top_urgent = urgent_tracked[:app_config.notifications.max_per_run]
            if not args.dry_run:
                send_telegram(top_urgent, is_digest_of_active=True, user_name=app_config.user_name)
                metrics.notifications_sent = len(top_urgent)
            else:
                preview, _ = format_notification(top_urgent, is_digest=True, user_name=app_config.user_name)
                print("\n--- [PREVIEW OF TELEGRAM NOTIFICATION] ---")
                print(preview)
                print("------------------------------------------\n")
        else:
            log.info("✨ No qualifying new events and no urgent deadlines (≤7 days). Staying silent to prevent notification spam.")

    # Persist all successfully evaluated new events to SQLite & memory
    for ev in scored_events:
        event_id = upsert_event(ev)
        save_event_score(event_id, user_id=1, score=ev)
        memory = mark_seen(memory, ev["title"], ev.get("link", ""), ev.get("source", ""), ev)

    save_memory(memory)
    sync_sqlite_to_seen_events_json()

    metrics.finish()
    log.info("=" * 65)
    log.info("✅ Hackathon Opportunity Agent v4 Run Complete")
    log.info("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())

