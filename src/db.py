"""
SQLite Relational Database Engine (v4).

Provides persistent, queryable storage for:
- Users & structured PreferenceProfiles
- Normalized Events & Deduplication Hashes
- User-specific Scores (Relevance, FOS/SOS, Urgency)
- Notification History & Interaction Tracking
- Feedback signals for adaptive relevance

Maintains two-way sync with seen_events.json for GitHub Actions CI/CD compatibility.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/monitor.db"


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Get SQLite database connection with row factory."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Create relational database schema if not already initialized."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Preference profiles table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS preference_profiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER REFERENCES users(id),
            raw_text        TEXT NOT NULL,
            topics          TEXT,        -- JSON list
            wanted_types    TEXT,        -- JSON list
            excluded_types  TEXT,        -- JSON list
            online_pref     TEXT,
            primary_goal    TEXT,
            updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Portal configurations
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS portal_configs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER REFERENCES users(id),
            name        TEXT NOT NULL,
            url         TEXT NOT NULL,
            adapter     TEXT NOT NULL,
            auth_type   TEXT NOT NULL,
            active      BOOLEAN DEFAULT 1
        );
        """)

        # Normalized events table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            title                   TEXT NOT NULL,
            title_hash              TEXT NOT NULL UNIQUE,
            event_type              TEXT NOT NULL,
            source                  TEXT NOT NULL,
            source_type             TEXT DEFAULT 'global_platform',
            link                    TEXT,
            mode                    TEXT,
            start_date              TEXT,
            end_date                TEXT,
            registration_deadline   TEXT,
            prize_pool              TEXT,
            sponsors                TEXT,        -- JSON list
            description             TEXT,
            tags                    TEXT,        -- JSON list
            raw_data                TEXT,        -- Full JSON payload
            first_seen_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at              DATETIME
        );
        """)

        # Event scores table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_scores (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id                INTEGER REFERENCES events(id),
            user_id                 INTEGER REFERENCES users(id),
            relevance_score         REAL,
            relevance_explanation   TEXT,
            opportunity_score       REAL,
            easy_win_score          REAL,
            urgency_score           REAL,
            final_rank              REAL,
            verdict                 TEXT,
            recommendation          TEXT,
            why_relevant            TEXT,
            scored_at               DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Notifications table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER REFERENCES users(id),
            event_id        INTEGER REFERENCES events(id),
            channel         TEXT DEFAULT 'telegram',
            message_id      TEXT,
            sent_at         DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Feedback actions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER REFERENCES users(id),
            event_id        INTEGER REFERENCES events(id),
            action          TEXT NOT NULL, -- 'applied', 'dismissed', 'opened', 'bookmarked'
            timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Seed default user if none exists
        cursor.execute("SELECT COUNT(*) FROM users;")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (name) VALUES ('Default User');")

        conn.commit()
        log.info(f"Initialized SQLite database schema at {db_path}")


def migrate_seen_events_to_sqlite(json_path: str = "seen_events.json", db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Migrate historical seen_events.json entries into SQLite.
    Returns the number of events imported.
    """
    if not os.path.exists(json_path):
        return 0

    init_db(db_path)
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.error(f"Failed to read {json_path} for migration: {e}")
        return 0

    migrated = 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for hash_key, entry in data.items():
            title = entry.get("title", "Unknown")
            source = entry.get("source", "unknown")
            source_type = "college_portal" if "vit" in source.lower() else "global_platform"
            link = entry.get("link")
            mode = entry.get("mode")
            deadline = entry.get("registration_deadline")
            date_first_seen = entry.get("date_first_seen", datetime.now(timezone.utc).isoformat())

            # Upsert into events
            cursor.execute("""
            INSERT INTO events (
                title, title_hash, event_type, source, source_type, link, mode,
                registration_deadline, first_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(title_hash) DO UPDATE SET
                link = COALESCE(excluded.link, events.link),
                last_seen_at = CURRENT_TIMESTAMP;
            """, (
                title,
                hash_key,
                entry.get("event_type", "hackathon"),
                source,
                source_type,
                link,
                mode,
                deadline,
                date_first_seen,
            ))

            event_id = cursor.lastrowid
            if not event_id:
                cursor.execute("SELECT id FROM events WHERE title_hash = ?", (hash_key,))
                row = cursor.fetchone()
                event_id = row[0] if row else None

            # Upsert historical score if present
            if event_id and (entry.get("fos_score") is not None or entry.get("fos_verdict") is not None):
                cursor.execute("""
                INSERT INTO event_scores (
                    event_id, user_id, opportunity_score, easy_win_score,
                    verdict, why_relevant
                ) VALUES (?, 1, ?, ?, ?, ?);
                """, (
                    event_id,
                    entry.get("fos_score"),
                    entry.get("easy_winning_potential"),
                    entry.get("fos_verdict"),
                    entry.get("why_relevant"),
                ))

            migrated += 1

        conn.commit()
    log.info(f"Migrated {migrated} entries from {json_path} to SQLite ({db_path})")
    return migrated


def upsert_event(event: dict, db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Insert or update a normalized event in SQLite.
    Returns the event database id.
    """
    init_db(db_path)
    from src.memory import _hash_title

    title = event.get("title", "")
    title_hash = _hash_title(title)
    event_type = event.get("event_type", "hackathon")
    source = event.get("source", "unknown")
    source_type = event.get("source_type", "global_platform")
    link = event.get("link")
    mode = event.get("mode")
    deadline = event.get("registration_deadline")
    prize = event.get("prize_pool")
    sponsors = json.dumps(event.get("sponsors", []))
    desc = event.get("description")
    tags = json.dumps(event.get("tags", []))
    raw = json.dumps(event)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO events (
            title, title_hash, event_type, source, source_type, link, mode,
            registration_deadline, prize_pool, sponsors, description, tags, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(title_hash) DO UPDATE SET
            link = COALESCE(excluded.link, events.link),
            registration_deadline = COALESCE(excluded.registration_deadline, events.registration_deadline),
            prize_pool = COALESCE(excluded.prize_pool, events.prize_pool),
            description = COALESCE(excluded.description, events.description),
            last_seen_at = CURRENT_TIMESTAMP;
        """, (
            title, title_hash, event_type, source, source_type, link, mode,
            deadline, prize, sponsors, desc, tags, raw
        ))
        conn.commit()

        cursor.execute("SELECT id FROM events WHERE title_hash = ?", (title_hash,))
        row = cursor.fetchone()
        return row[0] if row else 0


def save_event_score(event_id: int, user_id: int, score: dict, db_path: str = DEFAULT_DB_PATH) -> None:
    """Record an AI evaluation score in SQLite."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
        INSERT INTO event_scores (
            event_id, user_id, relevance_score, relevance_explanation,
            opportunity_score, easy_win_score, verdict, recommendation, why_relevant
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        is_college = score.get("source_type") == "college_portal"
        opp_score = (score.get("sos_score") if is_college else score.get("fos_score")) or score.get("fos_score") or score.get("sos_score") or 5.0
        verdict = (score.get("sos_verdict") if is_college else score.get("fos_verdict")) or score.get("fos_verdict") or score.get("sos_verdict") or "⚠️"

        cursor.execute(query, (
            event_id,
            user_id,
            score.get("relevance_score", 5.0),
            score.get("relevance_explanation", ""),
            opp_score,
            score.get("easy_winning_potential", 5.0),
            verdict,
            score.get("recommendation", "CONSIDER"),
            score.get("why_relevant", ""),
        ))
        conn.commit()


def sync_sqlite_to_seen_events_json(db_path: str = DEFAULT_DB_PATH, json_path: str = "seen_events.json") -> None:
    """
    Sync recent active events from SQLite back into seen_events.json
    so GitHub Actions auto-commit continues to function seamlessly.
    """
    if not os.path.exists(db_path):
        return

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT e.title, e.title_hash, e.source, e.source_type, e.link, e.mode,
               e.registration_deadline, e.first_seen_at,
               s.opportunity_score, s.easy_win_score, s.verdict, s.why_relevant, s.relevance_score
        FROM events e
        LEFT JOIN (
            SELECT event_id, opportunity_score, easy_win_score, verdict, why_relevant, relevance_score,
                   MAX(scored_at)
            FROM event_scores
            GROUP BY event_id
        ) s ON e.id = s.event_id
        WHERE e.first_seen_at >= datetime('now', '-90 days')
        ORDER BY e.first_seen_at DESC;
        """)
        rows = cursor.fetchall()

    export_data = {}
    for r in rows:
        export_data[r["title_hash"]] = {
            "title": r["title"],
            "source": r["source"],
            "source_type": r["source_type"],
            "link": r["link"],
            "mode": r["mode"],
            "registration_deadline": r["registration_deadline"],
            "date_first_seen": r["first_seen_at"],
            "fos_score": r["opportunity_score"],
            "easy_winning_potential": r["easy_win_score"],
            "fos_verdict": r["verdict"],
            "why_relevant": r["why_relevant"],
            "relevance_score": r["relevance_score"],
        }

    from src.memory import save_memory
    save_memory(export_data, path=json_path)
    log.info(f"Exported {len(export_data)} active events from SQLite to {json_path}")
