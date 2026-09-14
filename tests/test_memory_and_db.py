"""Unit tests for memory deduplication, 90-day TTL expiration, and SQLite database."""

import os
import pytest
from datetime import datetime, timezone, timedelta
from src.memory import clean_expired_events, is_new, mark_seen, _hash_title
from src.db import init_db, upsert_event, save_event_score, get_connection


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_monitor.db")


def test_clean_expired_events_ttl():
    """Verify that events older than 90 days are pruned while recent events are retained."""
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=95)).isoformat()
    recent_date = (now - timedelta(days=10)).isoformat()

    memory = {
        "hash_old": {
            "title": "Ancient Hackathon 2025",
            "date_first_seen": old_date,
            "source": "devpost"
        },
        "hash_recent": {
            "title": "Fresh Hackathon 2026",
            "date_first_seen": recent_date,
            "source": "devpost"
        }
    }

    cleaned, removed = clean_expired_events(memory, ttl_days=90)
    assert removed == 1
    assert "hash_old" not in cleaned
    assert "hash_recent" in cleaned


def test_sqlite_schema_init_and_upsert(test_db_path):
    """Verify SQLite table creation and event upsert."""
    init_db(test_db_path)

    sample_event = {
        "title": "Agentic AI Hackathon 2026",
        "event_type": "hackathon",
        "source": "devpost",
        "source_type": "global_platform",
        "link": "https://devpost.com/agentic-ai",
        "mode": "online",
        "registration_deadline": "2026-10-01",
        "prize_pool": "$100,000",
        "sponsors": ["OpenAI", "Google"],
        "description": "Build autonomous agents.",
        "tags": ["AI", "agents"]
    }

    event_id = upsert_event(sample_event, db_path=test_db_path)
    assert event_id > 0

    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title, link, source_type FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        assert row["title"] == "Agentic AI Hackathon 2026"
        assert row["link"] == "https://devpost.com/agentic-ai"
        assert row["source_type"] == "global_platform"

    # Test score insertion
    score_data = {
        "relevance_score": 9.5,
        "relevance_explanation": "Direct match for AI interest",
        "fos_score": 9.2,
        "easy_winning_potential": 8.0,
        "fos_verdict": "🔥",
        "recommendation": "APPLY IMMEDIATELY",
        "why_relevant": "Top sponsor brands and prizes."
    }
    save_event_score(event_id, user_id=1, score=score_data, db_path=test_db_path)

    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT relevance_score, verdict FROM event_scores WHERE event_id = ?", (event_id,))
        srow = cursor.fetchone()
        assert srow["relevance_score"] == 9.5
        assert srow["verdict"] == "🔥"
